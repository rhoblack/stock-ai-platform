"""Integration tests for v0.6 Phase B earnings CSV import."""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest
from sqlalchemy import select

from app.data.dtos import EarningsEventDTO
from app.data.importers.earnings import (
    CsvForbiddenColumnError,
    CsvSchemaError,
    EarningsCsvImporter,
    calculate_surprise,
)
from app.data.interfaces import EarningsProviderInterface
from app.data.repositories import EarningsEventRepository
from app.db import Base
from app.db.models import EarningsEvent
from app.db.session import create_db_engine, create_session_factory
from tests.mocks.fake_earnings_provider import FakeEarningsProvider


SAMPLE_CSV_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "earnings_events_sample.csv"


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
    return EarningsCsvImporter(session).import_stream(StringIO(csv_text))


def test_earnings_event_dto_has_no_forbidden_body_fields():
    names = {field.name for field in fields(EarningsEventDTO)}
    forbidden = {
        "body",
        "content",
        "full_text",
        "paragraph",
        "raw_text",
        "html_body",
        "source_file_path",
        "본문",
        "원문",
        "전문",
    }
    assert names.isdisjoint(forbidden)
    # v0.12 Phase A: 18 base + data_source = 19
    assert len(names) == 19


def test_fake_earnings_provider_is_deterministic_and_filters():
    provider = FakeEarningsProvider()
    assert isinstance(provider, EarningsProviderInterface)

    first = provider.fetch_earnings_events(
        ["005930", "000660", "035420", "005380"],
        since=date(2026, 4, 1),
        until=date(2026, 5, 31),
    )
    second = provider.fetch_earnings_events(
        ["005930", "000660", "035420", "005380"],
        since=date(2026, 4, 1),
        until=date(2026, 5, 31),
    )
    beat_only = provider.fetch_earnings_events(["005930"], since=date(2026, 4, 1), limit=10)

    assert first == second
    assert {item.surprise_type for item in first} == {"BEAT", "MEET", "MISS", "UNKNOWN"}
    assert [item.symbol for item in beat_only] == ["005930"]


def test_csv_dry_run_does_not_persist(session):
    summary = EarningsCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.rollback()

    assert summary.total_rows == 4
    assert summary.inserted == 4
    assert summary.validation_errors == 0
    assert list(session.execute(select(EarningsEvent)).scalars().all()) == []


def test_csv_commit_persists_sample_rows_and_calculates_surprise(session):
    summary = EarningsCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary.inserted == 4
    repo = EarningsEventRepository(session)
    samsung = repo.get_latest_by_symbol("005930")
    sk = repo.get_latest_by_symbol("000660")
    naver = repo.get_latest_by_symbol("035420")
    hyundai = repo.get_latest_by_symbol("005380")
    assert samsung is not None
    assert samsung.surprise_type == "BEAT"
    assert samsung.surprise_pct == Decimal("9.2308")
    assert sk is not None
    assert sk.surprise_type == "MEET"
    assert sk.surprise_pct == Decimal("2.0408")
    assert naver is not None
    assert naver.surprise_type == "MISS"
    assert hyundai is not None
    assert hyundai.surprise_type == "UNKNOWN"


def test_reimport_is_idempotent_and_counts_unchanged(session):
    EarningsCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    summary = EarningsCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary.inserted == 0
    assert summary.updated == 0
    assert summary.unchanged == 4
    assert len(session.execute(select(EarningsEvent)).scalars().all()) == 4


def test_reimport_changed_metric_counts_updated(session):
    EarningsCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()
    csv_text = dedent(
        """
        symbol,event_date,fiscal_year,fiscal_quarter,event_type,operating_income_actual,operating_income_consensus
        005930,2026-04-30,2026,1,FINAL,8000000,6500000
        """,
    ).strip() + "\n"

    summary = _import_csv_text(session, csv_text)
    session.commit()

    assert summary.updated == 1
    row = EarningsEventRepository(session).get_latest_by_symbol("005930")
    assert row is not None
    assert row.operating_income_actual == Decimal("8000000.0000")
    assert row.surprise_type == "BEAT"


def test_forbidden_body_column_rejects_file(session):
    csv_text = dedent(
        """
        symbol,event_date,fiscal_year,event_type,body
        005930,2026-04-30,2026,FINAL,full text
        """,
    ).strip() + "\n"
    with pytest.raises(CsvForbiddenColumnError, match="forbidden column"):
        _import_csv_text(session, csv_text)


def test_missing_required_column_rejects_file(session):
    csv_text = dedent(
        """
        symbol,event_date,event_type
        005930,2026-04-30,FINAL
        """,
    ).strip() + "\n"
    with pytest.raises(CsvSchemaError, match="missing required"):
        _import_csv_text(session, csv_text)


@pytest.mark.parametrize(
    ("column", "value", "expected"),
    [
        ("event_date", "2026/04/30", "event_date"),
        ("fiscal_year", "20X6", "fiscal_year"),
        ("fiscal_quarter", "5", "fiscal_quarter"),
        ("event_type", "BAD", "event_type"),
        ("surprise_type", "GOOD", "surprise_type"),
    ],
)
def test_enum_date_year_quarter_validation(session, column, value, expected):
    row = {
        "symbol": "005930",
        "event_date": "2026-04-30",
        "fiscal_year": "2026",
        "fiscal_quarter": "1",
        "event_type": "FINAL",
        "surprise_type": "BEAT",
    }
    row[column] = value
    csv_text = ",".join(row.keys()) + "\n" + ",".join(row.values()) + "\n"

    summary = _import_csv_text(session, csv_text)

    assert summary.validation_errors == 1
    assert expected in summary.error_details[0][1]


@pytest.mark.parametrize(
    ("actual", "consensus", "expected_type"),
    [
        ("105", "100", "BEAT"),
        ("104.9", "100", "MEET"),
        ("95", "100", "MISS"),
        ("100", "0", "UNKNOWN"),
    ],
)
def test_surprise_auto_calculation_policy(session, actual, consensus, expected_type):
    csv_text = dedent(
        f"""
        symbol,event_date,fiscal_year,event_type,operating_income_actual,operating_income_consensus
        005930,2026-04-30,2026,FINAL,{actual},{consensus}
        """,
    ).strip() + "\n"

    summary = _import_csv_text(session, csv_text)
    session.commit()

    assert summary.validation_errors == 0
    row = EarningsEventRepository(session).get_latest_by_symbol("005930")
    assert row is not None
    assert row.surprise_type == expected_type
    if expected_type == "UNKNOWN":
        assert row.surprise_pct is None


def test_calculate_surprise_function_boundaries():
    assert calculate_surprise(
        operating_income_actual=Decimal("105"),
        operating_income_consensus=Decimal("100"),
    )[0] == "BEAT"
    assert calculate_surprise(
        operating_income_actual=Decimal("95"),
        operating_income_consensus=Decimal("100"),
    )[0] == "MISS"
    assert calculate_surprise(
        operating_income_actual=Decimal("104.999"),
        operating_income_consensus=Decimal("100"),
    )[0] == "MEET"


def test_memo_truncate_and_negative_policy(session):
    long_memo = "a" * 600
    csv_text = (
        "symbol,event_date,fiscal_year,event_type,revenue_actual,operating_income_actual,"
        "net_income_actual,eps_actual,memo\n"
        f"005930,2026-04-30,2026,FINAL,100,-10,-20,-30,{long_memo}\n"
    )
    summary = _import_csv_text(session, csv_text)
    session.commit()

    assert summary.validation_errors == 0
    assert summary.truncated_notes == 1
    row = EarningsEventRepository(session).get_latest_by_symbol("005930")
    assert row is not None
    assert row.operating_income_actual == Decimal("-10.0000")
    assert row.net_income_actual == Decimal("-20.0000")
    assert row.eps_actual == Decimal("-30.0000")
    assert len(row.memo) == 500

    bad_revenue = dedent(
        """
        symbol,event_date,fiscal_year,event_type,revenue_actual
        000660,2026-04-30,2026,FINAL,-1
        """,
    ).strip() + "\n"
    summary2 = _import_csv_text(session, bad_revenue)
    assert summary2.validation_errors == 1
    assert "revenue_actual" in summary2.error_details[0][1]


def test_run_import_dry_run_and_commit(tmp_path):
    from scripts import import_earnings as cli

    db_path = tmp_path / "earnings.db"
    db_url = f"sqlite:///{db_path}"
    dry_summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=False,
        database_url=db_url,
    )
    assert dry_summary.inserted == 4
    factory = cli._build_session_factory(db_url)
    s = factory()
    try:
        assert list(s.execute(select(EarningsEvent)).scalars().all()) == []
    finally:
        s.close()

    commit_summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=True,
        database_url=db_url,
    )
    assert commit_summary.inserted == 4
    s = factory()
    try:
        assert len(s.execute(select(EarningsEvent)).scalars().all()) == 4
    finally:
        s.close()
