"""Integration tests for the v0.4 Phase B CSV import pipeline.

Covers:
  * Sample fixture import (dry-run + commit)
  * Re-import idempotency (skipped_duplicates)
  * Header validation: forbidden body columns + missing required columns
  * Row validation: enums / dates / numbers
  * Theme + mapping + signal extraction from a single row
  * source_file_path is stored but never echoed in error messages
  * `run_import` programmatic entry from `scripts.import_analyst_reports`
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest
from sqlalchemy import select

from app.data.importers.analyst_reports import (
    AnalystReportCsvImporter,
    CsvForbiddenColumnError,
    CsvSchemaError,
)
from app.data.repositories import (
    AnalystReportRepository,
    ReportConsensusSnapshotRepository,
    ReportSignalEventRepository,
    ReportThemeRepository,
    ThemeStockMappingRepository,
)
from app.db import Base
from app.db.models import AnalystReport
from app.db.session import create_db_engine, create_session_factory


SAMPLE_CSV_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "analyst_reports_sample.csv"
)


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def _import_csv_text(session, csv_text: str):
    return AnalystReportCsvImporter(session).import_stream(StringIO(csv_text))


# ---------- file fixture ----------


def test_sample_fixture_imports_three_reports_three_themes_five_mappings(session):
    summary = AnalystReportCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary.total_rows == 3
    assert summary.inserted_reports == 3
    assert summary.skipped_duplicates == 0
    assert summary.inserted_themes == 3
    # row 1: 1 mapping (000660) ; row 2: 2 mappings (005930;000660) ; row 3: 2 mappings (103140;006260)
    assert summary.inserted_mappings == 5
    assert summary.inserted_signal_events == 3
    assert summary.validation_errors == 0
    assert summary.error_details == []

    # COMPANY 리포트 샘플 검증
    rep = AnalystReportRepository(session).list_by_symbol("005930")
    assert len(rep) == 1
    assert rep[0].normalized_rating == "BUY"
    assert rep[0].target_price == Decimal("90000.0000")
    # source_file_path stored verbatim
    assert rep[0].source_file_path == "D:/local/reports/005930-2026-04-30.pdf"


def test_re_import_is_idempotent_with_skipped_duplicates(session):
    AnalystReportCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    summary2 = AnalystReportCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary2.total_rows == 3
    assert summary2.inserted_reports == 0
    assert summary2.skipped_duplicates == 3
    assert summary2.inserted_themes == 0
    assert summary2.inserted_mappings == 0
    assert summary2.inserted_signal_events == 0


def test_dry_run_does_not_persist(session):
    summary = AnalystReportCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    # rollback simulates dry-run
    session.rollback()
    rows = list(session.execute(select(AnalystReport)).scalars().all())
    assert rows == []
    # but the in-memory summary still reports projected counts
    assert summary.inserted_reports == 3


# ---------- header validation ----------


def test_forbidden_body_column_rejects_file(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,body
        COMPANY,A,2026-05-01,T1,full paragraph text here
        """,
    ).strip() + "\n"
    with pytest.raises(CsvForbiddenColumnError, match="forbidden column"):
        _import_csv_text(session, csv_text)


def test_korean_forbidden_body_column_rejected(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,본문
        COMPANY,A,2026-05-01,T1,paragraph
        """,
    ).strip() + "\n"
    with pytest.raises(CsvForbiddenColumnError):
        _import_csv_text(session, csv_text)


def test_missing_required_column_rejects_file(session):
    csv_text = dedent(
        """
        report_type,published_at,title
        COMPANY,2026-05-01,T1
        """,
    ).strip() + "\n"
    with pytest.raises(CsvSchemaError, match="missing required"):
        _import_csv_text(session, csv_text)


# ---------- row validation ----------


def test_invalid_report_type_enum_counts_as_validation_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title
        INVALID_TYPE,A증권,2026-05-01,T1
        COMPANY,B증권,2026-05-01,T2
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    session.commit()
    assert summary.total_rows == 2
    assert summary.validation_errors == 1
    assert summary.inserted_reports == 1
    # error message references the column + offending value, NOT any path
    assert "report_type" in summary.error_details[0][1]
    assert "INVALID_TYPE" in summary.error_details[0][1]


def test_invalid_date_counts_as_validation_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title
        COMPANY,A증권,2026/05/01,T1
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1
    assert "published_at" in summary.error_details[0][1]


def test_invalid_target_price_counts_as_validation_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,target_price
        COMPANY,A증권,2026-05-01,T1,not-a-number
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1
    assert "target_price" in summary.error_details[0][1]


def test_invalid_normalized_rating_counts_as_validation_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,normalized_rating
        COMPANY,A증권,2026-05-01,T1,BAD_RATING
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1


def test_summary_over_500_chars_is_truncated(session):
    long_summary = "가" * 600
    csv_text = (
        "report_type,broker_name,published_at,title,summary\n"
        f"COMPANY,A증권,2026-05-01,T1,{long_summary}\n"
    )
    summary = _import_csv_text(session, csv_text)
    session.commit()
    assert summary.inserted_reports == 1
    assert summary.truncated_summaries == 1
    saved = AnalystReportRepository(session).list_by_symbol("")
    # symbol filter empty matches nothing — fetch via list_recent
    saved = AnalystReportRepository(session).list_recent()
    assert len(saved[0].summary) == 500


def test_signal_strength_outside_0_1_counts_as_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,signal_event_type,signal_strength
        COMPANY,A증권,2026-05-01,T1,TARGET_PRICE_UP,1.5
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1
    assert "signal_strength" in summary.error_details[0][1]


# ---------- theme + mapping + signal extraction ----------


def test_theme_only_extracted_when_theme_name_and_category_present(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,theme_name,theme_category
        COMPANY,A증권,2026-05-01,T1,,
        COMPANY,A증권,2026-05-01,T2,HBM,SEMICONDUCTOR
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    session.commit()
    assert summary.inserted_reports == 2
    assert summary.inserted_themes == 1


def test_related_symbols_semicolon_creates_multiple_mappings(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,theme_name,theme_category,theme_direction,related_symbols,impact_direction,impact_path
        THEME,A증권,2026-05-01,T1,HBM,SEMICONDUCTOR,POSITIVE,005930;000660;042700,POSITIVE,DEMAND_INCREASE
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    session.commit()
    assert summary.inserted_themes == 1
    assert summary.inserted_mappings == 3
    # verify the mapping rows in DB
    theme = ReportThemeRepository(session).list_recent()[0]
    mappings = ThemeStockMappingRepository(session).list_by_theme(theme.id)
    assert {m.symbol for m in mappings} == {"005930", "000660", "042700"}


def test_signal_event_only_extracted_when_event_type_present(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,symbol,signal_event_type,signal_direction,signal_strength
        COMPANY,A증권,2026-05-01,T1,005930,TARGET_PRICE_UP,POSITIVE,0.7
        COMPANY,A증권,2026-05-01,T2,005930,,,
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    session.commit()
    assert summary.inserted_reports == 2
    assert summary.inserted_signal_events == 1
    events = ReportSignalEventRepository(session).list_by_symbol("005930")
    assert len(events) == 1
    assert events[0].strength == Decimal("0.700")


def test_invalid_signal_event_type_enum_counts_as_error(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,signal_event_type
        COMPANY,A증권,2026-05-01,T1,NOT_AN_EVENT
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1


# ---------- programmatic entry ----------


def test_run_import_dry_run_does_not_persist(tmp_path, monkeypatch):
    """The CLI's `run_import` should rollback when commit=False."""
    from scripts import import_analyst_reports as cli

    db_path = tmp_path / "import_test.db"
    db_url = f"sqlite:///{db_path}"

    summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=False,
        encoding="utf-8-sig",
        database_url=db_url,
    )
    assert summary.inserted_reports == 3

    # Re-open DB and confirm no rows
    factory = cli._build_session_factory(db_url)
    s = factory()
    try:
        rows = list(s.execute(select(AnalystReport)).scalars().all())
        assert rows == []
    finally:
        s.close()


def test_run_import_commit_persists(tmp_path):
    from scripts import import_analyst_reports as cli

    db_path = tmp_path / "import_commit_test.db"
    db_url = f"sqlite:///{db_path}"

    summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=True,
        encoding="utf-8-sig",
        database_url=db_url,
    )
    assert summary.inserted_reports == 3

    factory = cli._build_session_factory(db_url)
    s = factory()
    try:
        rows = list(s.execute(select(AnalystReport)).scalars().all())
        assert len(rows) == 3
    finally:
        s.close()


# ---------- source_file_path safety ----------


def test_source_file_path_not_in_error_messages(session):
    csv_text = dedent(
        """
        report_type,broker_name,published_at,title,source_file_path,target_price
        COMPANY,A증권,2026-05-01,T1,D:/secret/path/report.pdf,not-a-number
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, csv_text)
    assert summary.validation_errors == 1
    error_msg = summary.error_details[0][1]
    assert "D:/secret/path/report.pdf" not in error_msg
    assert "secret" not in error_msg
