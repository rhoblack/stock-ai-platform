"""CSV importer for v0.6 EarningsEvent rows.

Default CLI behaviour is dry-run. No DART/KIS calls are made; the importer only
accepts normalized earnings event metrics and rejects original body/raw/blob
columns at header validation.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import TextIOBase
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.data.dtos import EarningsEventDTO
from app.data.repositories.earnings_events import EarningsEventRepository
from app.db.models import EarningsEvent


EVENT_TYPES = frozenset({"PRELIMINARY", "FINAL", "GUIDANCE", "CONSENSUS", "OTHER"})
SURPRISE_TYPES = frozenset({"BEAT", "MEET", "MISS", "UNKNOWN"})
REQUIRED_HEADERS = ("symbol", "event_date", "fiscal_year", "event_type")
NUMERIC_FIELDS = (
    "revenue_actual",
    "revenue_consensus",
    "operating_income_actual",
    "operating_income_consensus",
    "net_income_actual",
    "net_income_consensus",
    "eps_actual",
    "eps_consensus",
    "surprise_pct",
)
NON_NEGATIVE_FIELDS = frozenset({"revenue_actual", "revenue_consensus"})
NULL_TOKENS = frozenset({"", "-", "nan", "none", "null", "n/a"})
MEMO_MAX_LEN = 500
DECIMAL_SCALE = Decimal("0.0001")
FORBIDDEN_HEADERS = frozenset(
    {
        "body",
        "content",
        "full_text",
        "fulltext",
        "paragraph",
        "paragraph_text",
        "paragraphs",
        "raw_text",
        "rawtext",
        "html_body",
        "htmlbody",
        "source_file_path",
        "document_blob",
        "pdf_blob",
        "excel_blob",
        "본문",
        "원문",
        "전문",
    },
)


class CsvSchemaError(ValueError):
    """Header is missing required columns or contains forbidden columns."""


class CsvForbiddenColumnError(CsvSchemaError):
    """Header contains document body/path/blob columns; reject the file."""


class RowValidationError(ValueError):
    """Single-row validation failure; counted and import continues."""


@dataclass
class ImportSummary:
    total_rows: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    validation_errors: int = 0
    truncated_notes: int = 0
    error_details: list[tuple[int, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "validation_errors": self.validation_errors,
            "truncated_notes": self.truncated_notes,
            "error_details": list(self.error_details),
        }


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _required_str(name: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise RowValidationError(f"{name} is required (got empty)")
    return cleaned


def _date(name: str, value: str) -> date:
    cleaned = _required_str(name, value)
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RowValidationError(f"{name}={value!r} is not ISO date YYYY-MM-DD") from exc


def _int(name: str, value: str) -> int:
    cleaned = _required_str(name, value)
    try:
        return int(cleaned)
    except ValueError as exc:
        raise RowValidationError(f"{name}={value!r} is not a valid integer") from exc


def _optional_quarter(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned.lower() in NULL_TOKENS:
        return None
    try:
        quarter = int(cleaned)
    except ValueError as exc:
        raise RowValidationError(f"fiscal_quarter={value!r} is not a valid integer") from exc
    if quarter not in {1, 2, 3, 4}:
        raise RowValidationError("fiscal_quarter must be 1, 2, 3, 4, or empty")
    return quarter


def _optional_decimal(name: str, value: str) -> Decimal | None:
    cleaned = value.strip()
    if cleaned.lower() in NULL_TOKENS:
        return None
    try:
        parsed = Decimal(cleaned.replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise RowValidationError(f"{name}={value!r} is not a valid number") from exc
    if name in NON_NEGATIVE_FIELDS and parsed < 0:
        raise RowValidationError(f"{name} must be non-negative")
    return parsed


def _enum(name: str, value: str, allowed: frozenset[str]) -> str | None:
    cleaned = value.strip().upper()
    if cleaned.lower() in NULL_TOKENS:
        return None
    if cleaned not in allowed:
        raise RowValidationError(f"{name}={value!r} is not one of {sorted(allowed)}")
    return cleaned


def _required_enum(name: str, value: str, allowed: frozenset[str]) -> str:
    cleaned = _enum(name, value, allowed)
    if cleaned is None:
        raise RowValidationError(f"{name} is required (got empty)")
    return cleaned


def calculate_surprise(
    *,
    operating_income_actual: Decimal | None,
    operating_income_consensus: Decimal | None,
) -> tuple[str, Decimal | None]:
    if operating_income_actual is None or operating_income_consensus in (None, Decimal("0")):
        return "UNKNOWN", None
    surprise_pct = (
        (operating_income_actual - operating_income_consensus)
        / abs(operating_income_consensus)
        * Decimal("100")
    ).quantize(DECIMAL_SCALE)
    if surprise_pct >= Decimal("5"):
        return "BEAT", surprise_pct
    if surprise_pct <= Decimal("-5"):
        return "MISS", surprise_pct
    return "MEET", surprise_pct


def _dto_fields(dto: EarningsEventDTO) -> dict[str, Any]:
    return asdict(dto)


def _event_equal(existing: EarningsEvent, dto: EarningsEventDTO) -> bool:
    for name, value in _dto_fields(dto).items():
        if getattr(existing, name) != value:
            return False
    return True


class EarningsCsvImporter:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._repo = EarningsEventRepository(session)

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
        for index, raw in enumerate(rows, start=1):
            summary.total_rows += 1
            try:
                dto = self._parse_row(raw, summary)
                self._persist_dto(dto, summary)
            except RowValidationError as exc:
                summary.validation_errors += 1
                summary.error_details.append((index, str(exc)))
        return summary

    def _validate_header(self, fieldnames: list[str]) -> None:
        normalized = {(name or "").strip().lower() for name in fieldnames}
        forbidden_hits = sorted(normalized & FORBIDDEN_HEADERS)
        if forbidden_hits:
            raise CsvForbiddenColumnError(
                "CSV contains forbidden column(s): "
                f"{forbidden_hits}. Earnings import accepts normalized metrics "
                "only; remove body/raw/path/blob columns and re-run.",
            )
        missing = [name for name in REQUIRED_HEADERS if name not in normalized]
        if missing:
            raise CsvSchemaError(
                f"CSV is missing required column(s): {missing}. "
                f"Required: {list(REQUIRED_HEADERS)}",
            )

    def _parse_row(self, raw: Mapping[str, Any], summary: ImportSummary) -> EarningsEventDTO:
        row = {(k or "").strip().lower(): _normalize(v) for k, v in raw.items()}
        values: dict[str, Any] = {
            "symbol": _required_str("symbol", row.get("symbol", "")),
            "event_date": _date("event_date", row.get("event_date", "")),
            "fiscal_year": _int("fiscal_year", row.get("fiscal_year", "")),
            "fiscal_quarter": _optional_quarter(row.get("fiscal_quarter", "")),
            "event_type": _required_enum("event_type", row.get("event_type", ""), EVENT_TYPES),
            "company_name": row.get("company_name") or None,
            "source": row.get("source") or None,
        }
        for name in NUMERIC_FIELDS:
            values[name] = _optional_decimal(name, row.get(name, ""))

        supplied_surprise = _enum("surprise_type", row.get("surprise_type", ""), SURPRISE_TYPES)
        calculated_type, calculated_pct = calculate_surprise(
            operating_income_actual=values["operating_income_actual"],
            operating_income_consensus=values["operating_income_consensus"],
        )
        values["surprise_type"] = supplied_surprise or calculated_type
        if values["surprise_pct"] is None:
            values["surprise_pct"] = calculated_pct

        memo = row.get("memo") or None
        if memo is not None and len(memo) > MEMO_MAX_LEN:
            values["memo"] = memo[:MEMO_MAX_LEN]
            summary.truncated_notes += 1
        else:
            values["memo"] = memo
        return EarningsEventDTO(**values)

    def _persist_dto(self, dto: EarningsEventDTO, summary: ImportSummary) -> None:
        existing = self._repo.get_by_symbol_event(
            symbol=dto.symbol,
            event_date=dto.event_date,
            fiscal_year=dto.fiscal_year,
            fiscal_quarter=dto.fiscal_quarter,
            event_type=dto.event_type,
        )
        if existing is None:
            summary.inserted += 1
        elif _event_equal(existing, dto):
            summary.unchanged += 1
            return
        else:
            summary.updated += 1
        self._repo.upsert_by_symbol_event(**_dto_fields(dto))


__all__ = [
    "CsvForbiddenColumnError",
    "CsvSchemaError",
    "EarningsCsvImporter",
    "EVENT_TYPES",
    "ImportSummary",
    "RowValidationError",
    "SURPRISE_TYPES",
    "calculate_surprise",
]
