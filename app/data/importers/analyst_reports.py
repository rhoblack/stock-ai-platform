"""CSV importer for analyst reports + themes + theme→stock mappings + signal events.

A single CSV row may produce up to four rows in the database:
  1. one ``analyst_reports`` row (always, when row passes validation)
  2. one ``report_themes`` row (when ``theme_name`` + ``theme_category`` set)
  3. N ``theme_stock_mappings`` rows (when theme present and ``related_symbols``
     non-empty — semicolon-separated symbol list)
  4. one ``report_signal_events`` row (when ``signal_event_type`` set)

Validation policy
-----------------
Hard fail at HEADER parse:
  * any "원문 본문" column name (body / content / full_text / paragraph_text /
    article_body / raw_text / html_body / paragraphs / full_body / original_text
    or the Korean equivalents) — copyright protection, refuse the file outright
  * required columns missing (report_type / broker_name / published_at / title)

Row-level: caught and counted as ``validation_errors``, processing continues:
  * report_type / normalized_rating / theme_category / theme_direction /
    theme_time_horizon / impact_direction / impact_path / relation_type /
    benefit_type / signal_event_type / signal_direction — must match the spec
    enum (or be empty for optional fields)
  * published_at — must parse as ISO date (``YYYY-MM-DD``)
  * target_price / previous_target_price / current_price_at_report /
    signal_strength — must parse as Decimal (signal_strength is additionally
    clamped to 0~1)

Soft (counted but not error):
  * summary > 500 chars — truncated to 500, ``truncated_summaries`` incremented
  * positive_points / risk_points / reason / source_sentence_summary /
    signal_summary > 500 chars — truncated similarly (these go into Text columns
    so the truncation is purely policy, not a column-length forcing function)

Idempotency: ``get_by_unique`` is called before ``create`` for every entity, so
re-importing the same file produces 0 new rows and ``skipped_duplicates`` reflects
the count. Operators can safely re-run with ``--commit``.

Output safety: this module never echoes ``source_file_path`` content. The
:class:`ImportSummary` contains only counts and (optionally) sanitized error
messages where the offending value has been replaced with ``"<masked path>"``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import TextIOBase
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.data.repositories.analyst_reports import AnalystReportRepository
from app.data.repositories.report_signal_events import ReportSignalEventRepository
from app.data.repositories.report_themes import ReportThemeRepository
from app.data.repositories.theme_stock_mappings import ThemeStockMappingRepository

# ---------------------------------------------------------------------------
# Spec-defined enum sets (mirror the §0 v0.4 declaration in PROJECT_STATUS.md)
# ---------------------------------------------------------------------------

REPORT_TYPES = frozenset(
    {"COMPANY", "SECTOR", "INDUSTRY", "THEME", "COMMODITY", "MACRO", "STRATEGY"},
)
NORMALIZED_RATINGS = frozenset(
    {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"},
)
THEME_CATEGORIES = frozenset(
    {
        "SEMICONDUCTOR",
        "AI",
        "COMMODITY",
        "ENERGY",
        "DEFENSE",
        "SHIPBUILDING",
        "BIO",
        "AUTO",
        "BATTERY",
        "POWER_GRID",
        "DATA_CENTER",
        "MACRO",
        "CUSTOM",
    },
)
DIRECTIONS = frozenset({"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"})
TIME_HORIZONS = frozenset(
    {"IMMEDIATE", "SHORT_TERM", "MID_TERM", "LONG_TERM", "UNKNOWN"},
)
IMPACT_PATHS = frozenset(
    {
        "DEMAND_INCREASE",
        "PRICE_INCREASE",
        "COST_PRESSURE",
        "CAPEX_EXPANSION",
        "SUPPLY_SHORTAGE",
        "POLICY_SUPPORT",
        "EXPORT_GROWTH",
        "MARGIN_IMPROVEMENT",
        "INVENTORY_CYCLE",
        "RATE_FX_IMPACT",
        "CUSTOM",
    },
)
RELATION_TYPES = frozenset(
    {
        "PRODUCER",
        "CONSUMER",
        "SUPPLIER",
        "EQUIPMENT",
        "MATERIAL",
        "BENEFICIARY",
        "COST_PRESSURE",
        "COMPETITOR",
        "CUSTOMER",
        "CUSTOM",
    },
)
BENEFIT_TYPES = frozenset(
    {"DIRECT", "INDIRECT", "SUPPLY_CHAIN", "COST_PASS_THROUGH", "SENTIMENT", "CUSTOM"},
)
EVENT_TYPES = frozenset(
    {
        "RATING_UPGRADE",
        "RATING_DOWNGRADE",
        "TARGET_PRICE_UP",
        "TARGET_PRICE_DOWN",
        "EARNINGS_REVISION_UP",
        "EARNINGS_REVISION_DOWN",
        "SUPPLY_SHORTAGE",
        "DEMAND_RECOVERY",
        "ASP_RISE",
        "INVENTORY_DRAW_DOWN",
        "CAPEX_EXPANSION",
        "POLICY_SUPPORT",
        "COMMODITY_PRICE_RISE",
        "FX_RATE_IMPACT",
        "MARGIN_IMPROVEMENT",
        "MARGIN_PRESSURE",
        "RISK_WARNING",
        "CUSTOM",
    },
)

# Hard-rejected at header parse — operators must never attach paragraph-level
# original text to the import. The Korean variants catch translated columns.
FORBIDDEN_HEADERS = frozenset(
    {
        "body",
        "content",
        "full_text",
        "fulltext",
        "raw_text",
        "rawtext",
        "paragraph_text",
        "paragraphs",
        "article_body",
        "articlebody",
        "full_body",
        "original_text",
        "html_body",
        "report_body",
        "본문",
        "원문",
        "전문",
    },
)

REQUIRED_HEADERS = ("report_type", "broker_name", "published_at", "title")

SUMMARY_MAX_LEN = 500
TEXT_MAX_LEN = 500  # for positive_points / risk_points / reason / etc.

EXTRACTION_METHOD_CSV = "CSV_IMPORT"


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


class CsvSchemaError(ValueError):
    """Header is missing required columns or contains forbidden columns."""


class CsvForbiddenColumnError(CsvSchemaError):
    """Header contains a column suggesting full report-body text — refuse."""


class RowValidationError(ValueError):
    """Single-row validation failure — caught and counted, processing continues."""


@dataclass
class ImportSummary:
    total_rows: int = 0
    inserted_reports: int = 0
    skipped_duplicates: int = 0
    inserted_themes: int = 0
    inserted_mappings: int = 0
    inserted_signal_events: int = 0
    truncated_summaries: int = 0
    validation_errors: int = 0
    error_details: list[tuple[int, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "inserted_reports": self.inserted_reports,
            "skipped_duplicates": self.skipped_duplicates,
            "inserted_themes": self.inserted_themes,
            "inserted_mappings": self.inserted_mappings,
            "inserted_signal_events": self.inserted_signal_events,
            "truncated_summaries": self.truncated_summaries,
            "validation_errors": self.validation_errors,
            "error_details": list(self.error_details),
        }


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _enum(name: str, value: str, allowed: frozenset[str]) -> str | None:
    """Return the validated upper-cased value, or None if empty (optional)."""
    cleaned = value.strip().upper()
    if cleaned == "":
        return None
    if cleaned not in allowed:
        raise RowValidationError(f"{name}={value!r} is not one of {sorted(allowed)}")
    return cleaned


def _required_enum(name: str, value: str, allowed: frozenset[str]) -> str:
    cleaned = _enum(name, value, allowed)
    if cleaned is None:
        raise RowValidationError(f"{name} is required (got empty)")
    return cleaned


def _required_str(name: str, value: str) -> str:
    cleaned = value.strip()
    if cleaned == "":
        raise RowValidationError(f"{name} is required (got empty)")
    return cleaned


def _optional_str(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned if cleaned else None


def _optional_decimal(name: str, value: str) -> Decimal | None:
    cleaned = value.strip()
    if cleaned == "":
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise RowValidationError(f"{name}={value!r} is not a valid number") from exc


def _date(name: str, value: str) -> date:
    cleaned = value.strip()
    if cleaned == "":
        raise RowValidationError(f"{name} is required (got empty)")
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RowValidationError(
            f"{name}={value!r} is not ISO date YYYY-MM-DD",
        ) from exc


def _truncate(value: str | None, *, limit: int) -> tuple[str | None, bool]:
    """Return (possibly-truncated value, was_truncated)."""
    if value is None:
        return None, False
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _split_symbols(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    parts = [p.strip() for p in value.replace(",", ";").split(";")]
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class AnalystReportCsvImporter:
    """Parses + validates + persists a single CSV file of analyst reports.

    The repositories handle DB I/O. This class keeps validation pure (per-row,
    raises :class:`RowValidationError`) and orchestrates the four entity types
    that may be created from one row.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._reports = AnalystReportRepository(session)
        self._themes = ReportThemeRepository(session)
        self._mappings = ThemeStockMappingRepository(session)
        self._events = ReportSignalEventRepository(session)

    # ----- file entry points -----

    def import_file(
        self,
        file_path: str | Path,
        *,
        encoding: str = "utf-8-sig",
    ) -> ImportSummary:
        path = Path(file_path)
        with path.open("r", encoding=encoding, newline="") as fh:
            return self.import_stream(fh)

    def import_stream(self, fh: TextIOBase) -> ImportSummary:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise CsvSchemaError("CSV has no header row")
        self._validate_header(reader.fieldnames)
        return self.import_rows(reader)

    def import_rows(self, rows: Iterable[Mapping[str, Any]]) -> ImportSummary:
        summary = ImportSummary()
        for index, raw in enumerate(rows, start=1):  # 1-based for human-friendly errors
            summary.total_rows += 1
            try:
                self._import_row(raw, summary=summary)
            except RowValidationError as exc:
                summary.validation_errors += 1
                summary.error_details.append((index, str(exc)))
        return summary

    # ----- header / row processing -----

    def _validate_header(self, fieldnames: list[str]) -> None:
        normalized = {name.strip().lower() for name in fieldnames}
        forbidden_hits = sorted(normalized & FORBIDDEN_HEADERS)
        if forbidden_hits:
            raise CsvForbiddenColumnError(
                "CSV contains forbidden column(s) suggesting full report body: "
                f"{forbidden_hits}. Per v0.4 copyright policy, original report "
                "paragraphs / body text MUST NOT be imported. Drop these columns "
                "and re-run.",
            )
        missing = [c for c in REQUIRED_HEADERS if c not in normalized]
        if missing:
            raise CsvSchemaError(
                f"CSV is missing required column(s): {missing}. "
                f"Required: {list(REQUIRED_HEADERS)}",
            )

    def _import_row(self, raw: Mapping[str, Any], *, summary: ImportSummary) -> None:
        # Lowercase + strip the keys once so callers tolerate mixed-case headers.
        row = {(k or "").strip().lower(): _normalize(v) for k, v in raw.items()}

        report_type = _required_enum("report_type", row.get("report_type", ""), REPORT_TYPES)
        broker_name = _required_str("broker_name", row.get("broker_name", ""))
        published_at = _date("published_at", row.get("published_at", ""))
        title = _required_str("title", row.get("title", ""))

        # ----- analyst_reports -----
        existing_report = self._reports.get_by_unique(
            broker_name=broker_name,
            published_at=published_at,
            title=title,
        )
        if existing_report is not None:
            report = existing_report
            summary.skipped_duplicates += 1
        else:
            normalized_rating = _enum(
                "normalized_rating",
                row.get("normalized_rating", ""),
                NORMALIZED_RATINGS,
            )
            target_price = _optional_decimal("target_price", row.get("target_price", ""))
            previous_target_price = _optional_decimal(
                "previous_target_price",
                row.get("previous_target_price", ""),
            )
            current_price = _optional_decimal(
                "current_price_at_report",
                row.get("current_price_at_report", ""),
            )

            summary_text = _optional_str(row.get("summary", ""))
            summary_text, was_trunc = _truncate(summary_text, limit=SUMMARY_MAX_LEN)
            if was_trunc:
                summary.truncated_summaries += 1

            positive_points, _ = _truncate(
                _optional_str(row.get("positive_points", "")), limit=TEXT_MAX_LEN,
            )
            risk_points, _ = _truncate(
                _optional_str(row.get("risk_points", "")), limit=TEXT_MAX_LEN,
            )

            report = self._reports.create(
                broker_name=broker_name,
                published_at=published_at,
                title=title,
                report_type=report_type,
                extraction_method=EXTRACTION_METHOD_CSV,
                symbol=_optional_str(row.get("symbol", "")),
                company_name=_optional_str(row.get("company_name", "")),
                market=_optional_str(row.get("market", "")),
                exchange=_optional_str(row.get("exchange", "")),
                country=_optional_str(row.get("country", "")),
                broker_country=_optional_str(row.get("broker_country", "")),
                analyst_name=_optional_str(row.get("analyst_name", "")),
                rating=_optional_str(row.get("rating", "")),
                normalized_rating=normalized_rating,
                target_price=target_price,
                previous_target_price=previous_target_price,
                current_price_at_report=current_price,
                currency=_optional_str(row.get("currency", "")),
                summary=summary_text,
                positive_points=positive_points,
                risk_points=risk_points,
                source_url=_optional_str(row.get("source_url", "")),
                source_file_path=_optional_str(row.get("source_file_path", "")),
                language=_optional_str(row.get("language", "")),
            )
            summary.inserted_reports += 1

        # ----- report_themes (only if theme_name + theme_category present) -----
        theme = None
        theme_name = _optional_str(row.get("theme_name", ""))
        if theme_name is not None:
            theme_category = _required_enum(
                "theme_category", row.get("theme_category", ""), THEME_CATEGORIES,
            )
            theme_direction = _enum(
                "theme_direction", row.get("theme_direction", ""), DIRECTIONS,
            ) or "NEUTRAL"
            theme_horizon = _enum(
                "theme_time_horizon", row.get("theme_time_horizon", ""), TIME_HORIZONS,
            ) or "UNKNOWN"

            existing_theme = self._themes.get_by_report_and_name(
                source_report_id=report.id,
                theme_name=theme_name,
            )
            if existing_theme is not None:
                theme = existing_theme
            else:
                theme = self._themes.create(
                    theme_name=theme_name,
                    theme_category=theme_category,
                    direction=theme_direction,
                    time_horizon=theme_horizon,
                    source_report_id=report.id,
                    extraction_method=EXTRACTION_METHOD_CSV,
                )
                summary.inserted_themes += 1

        # ----- theme_stock_mappings (semicolon-separated related_symbols) -----
        if theme is not None:
            related = _split_symbols(row.get("related_symbols", ""))
            if related:
                impact_direction = _required_enum(
                    "impact_direction",
                    row.get("impact_direction", ""),
                    DIRECTIONS,
                )
                impact_path = _enum(
                    "impact_path", row.get("impact_path", ""), IMPACT_PATHS,
                )
                relation_type = _enum(
                    "relation_type", row.get("relation_type", ""), RELATION_TYPES,
                )
                benefit_type = _enum(
                    "benefit_type", row.get("benefit_type", ""), BENEFIT_TYPES,
                )
                for sym in related:
                    existing_map = self._mappings.get_by_theme_and_symbol(
                        theme_id=theme.id, symbol=sym,
                    )
                    if existing_map is not None:
                        continue
                    self._mappings.create(
                        theme_id=theme.id,
                        symbol=sym,
                        impact_direction=impact_direction,
                        extraction_method=EXTRACTION_METHOD_CSV,
                        impact_path=impact_path,
                        relation_type=relation_type,
                        benefit_type=benefit_type,
                    )
                    summary.inserted_mappings += 1

        # ----- report_signal_events (one per row when signal_event_type present) -----
        signal_event_type = _enum(
            "signal_event_type", row.get("signal_event_type", ""), EVENT_TYPES,
        )
        if signal_event_type is not None:
            signal_direction = _enum(
                "signal_direction", row.get("signal_direction", ""), DIRECTIONS,
            ) or "NEUTRAL"
            signal_strength = _optional_decimal(
                "signal_strength", row.get("signal_strength", ""),
            )
            if signal_strength is not None and not (
                Decimal("0") <= signal_strength <= Decimal("1")
            ):
                raise RowValidationError(
                    f"signal_strength={signal_strength} must be in [0, 1]",
                )
            signal_summary, _ = _truncate(
                _optional_str(row.get("signal_summary", "")), limit=TEXT_MAX_LEN,
            )
            signal_symbol = _optional_str(row.get("symbol", ""))
            existing_event = self._events.get_by_unique(
                report_id=report.id,
                event_type=signal_event_type,
                symbol=signal_symbol,
                theme_id=theme.id if theme is not None else None,
            )
            if existing_event is None:
                self._events.create(
                    report_id=report.id,
                    event_type=signal_event_type,
                    direction=signal_direction,
                    time_horizon="UNKNOWN",
                    extraction_method=EXTRACTION_METHOD_CSV,
                    symbol=signal_symbol,
                    theme_id=theme.id if theme is not None else None,
                    strength=signal_strength,
                    summary=signal_summary,
                )
                summary.inserted_signal_events += 1
