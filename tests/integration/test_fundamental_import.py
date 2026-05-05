"""Integration tests for v0.6 Phase A PR2 fundamental CSV import."""

from __future__ import annotations

from dataclasses import fields
from decimal import Decimal
from io import StringIO
from pathlib import Path
from textwrap import dedent

import pytest
from sqlalchemy import select

from app.data.dtos import FundamentalSnapshotDTO
from app.data.importers.fundamentals import (
    CsvForbiddenColumnError,
    CsvSchemaError,
    FundamentalCsvImporter,
)
from app.data.interfaces import FundamentalProviderInterface
from app.data.repositories import FundamentalSnapshotRepository
from app.db import Base
from app.db.models import FundamentalSnapshot
from app.db.session import create_db_engine, create_session_factory
from tests.mocks.fake_fundamental_provider import FakeFundamentalProvider


SAMPLE_CSV_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "fundamentals_sample.csv"


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
    return FundamentalCsvImporter(session).import_stream(StringIO(csv_text))


def test_fundamental_snapshot_dto_has_no_forbidden_body_fields():
    names = {field.name for field in fields(FundamentalSnapshotDTO)}
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
    assert len(names) == 20


def test_fake_fundamental_provider_is_deterministic_and_filters():
    provider = FakeFundamentalProvider()
    assert isinstance(provider, FundamentalProviderInterface)

    first = provider.fetch_fundamentals(["005930", "000660", "035420"], 2025, 4)
    second = provider.fetch_fundamentals(["005930", "000660", "035420"], 2025, 4)
    samsung_only = provider.fetch_fundamentals(["005930"], 2025, 4)

    assert first == second
    assert {item.symbol for item in first} == {"005930", "000660", "035420"}
    assert [item.symbol for item in samsung_only] == ["005930"]
    assert provider.calls[-1] == (["005930"], 2025, 4)


def test_csv_dry_run_does_not_persist(session):
    summary = FundamentalCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.rollback()

    rows = list(session.execute(select(FundamentalSnapshot)).scalars().all())
    assert rows == []
    assert summary.total_rows == 3
    assert summary.inserted == 3
    assert summary.validation_errors == 0


def test_csv_commit_persists_sample_rows(session):
    summary = FundamentalCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary.total_rows == 3
    assert summary.inserted == 3
    assert summary.updated == 0
    repo = FundamentalSnapshotRepository(session)
    samsung = repo.get_latest_by_symbol("005930")
    assert samsung is not None
    assert samsung.revenue == Decimal("258935500.0000")
    assert samsung.source == "MANUAL_CSV_SAMPLE"


def test_reimport_is_idempotent_and_counts_unchanged(session):
    FundamentalCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    summary = FundamentalCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()

    assert summary.inserted == 0
    assert summary.updated == 0
    assert summary.unchanged == 3
    assert summary.skipped_duplicates == 3
    assert len(session.execute(select(FundamentalSnapshot)).scalars().all()) == 3


def test_reimport_with_changed_metric_counts_updated(session):
    FundamentalCsvImporter(session).import_file(SAMPLE_CSV_PATH)
    session.commit()
    csv_text = dedent(
        """
        symbol,snapshot_date,fiscal_year,fiscal_quarter,revenue,source
        005930,2026-05-01,2025,4,300000000.0000,MANUAL_CSV_SAMPLE
        """,
    ).strip() + "\n"

    summary = _import_csv_text(session, csv_text)
    session.commit()

    assert summary.inserted == 0
    assert summary.updated == 1
    assert summary.unchanged == 0
    latest = FundamentalSnapshotRepository(session).get_latest_by_symbol("005930")
    assert latest is not None
    assert latest.revenue == Decimal("300000000.0000")


def test_forbidden_body_column_rejects_file(session):
    csv_text = dedent(
        """
        symbol,snapshot_date,fiscal_year,source,body
        005930,2026-05-01,2025,MANUAL,full text
        """,
    ).strip() + "\n"
    with pytest.raises(CsvForbiddenColumnError, match="forbidden column"):
        _import_csv_text(session, csv_text)


def test_source_file_path_column_rejected(session):
    csv_text = dedent(
        """
        symbol,snapshot_date,fiscal_year,source,source_file_path
        005930,2026-05-01,2025,MANUAL,D:/secret/report.xlsx
        """,
    ).strip() + "\n"
    with pytest.raises(CsvForbiddenColumnError):
        _import_csv_text(session, csv_text)


def test_missing_required_column_rejects_file(session):
    csv_text = dedent(
        """
        symbol,snapshot_date,source
        005930,2026-05-01,MANUAL
        """,
    ).strip() + "\n"
    with pytest.raises(CsvSchemaError, match="missing required"):
        _import_csv_text(session, csv_text)


@pytest.mark.parametrize(
    ("column", "value", "expected"),
    [
        ("snapshot_date", "2026/05/01", "snapshot_date"),
        ("fiscal_year", "20X5", "fiscal_year"),
        ("fiscal_quarter", "5", "fiscal_quarter"),
    ],
)
def test_date_year_quarter_validation_errors(session, column, value, expected):
    row = {
        "symbol": "005930",
        "snapshot_date": "2026-05-01",
        "fiscal_year": "2025",
        "fiscal_quarter": "4",
        "source": "MANUAL",
    }
    row[column] = value
    csv_text = ",".join(row.keys()) + "\n" + ",".join(row.values()) + "\n"

    summary = _import_csv_text(session, csv_text)

    assert summary.validation_errors == 1
    assert expected in summary.error_details[0][1]


def test_decimal_parsing_and_null_tokens(session):
    csv_text = dedent(
        """
        symbol,snapshot_date,fiscal_year,fiscal_quarter,revenue,operating_income,total_assets,total_liabilities,total_equity,per,pbr,source
        005930,2026-05-01,2025,,"1,234.5000",-100.2500,NaN,-,,12.34,,MANUAL
        """,
    ).strip() + "\n"

    summary = _import_csv_text(session, csv_text)
    session.commit()

    assert summary.validation_errors == 0
    row = FundamentalSnapshotRepository(session).get_latest_by_symbol("005930")
    assert row is not None
    assert row.fiscal_quarter is None
    assert row.revenue == Decimal("1234.5000")
    assert row.operating_income == Decimal("-100.2500")
    assert row.total_assets is None
    assert row.total_liabilities is None
    assert row.total_equity is None
    assert row.per == Decimal("12.3400")
    assert row.pbr is None


def test_negative_policy_disallows_revenue_but_allows_income_growth_eps_roe(session):
    bad_revenue = dedent(
        """
        symbol,snapshot_date,fiscal_year,source,revenue
        005930,2026-05-01,2025,MANUAL,-1
        """,
    ).strip() + "\n"
    summary = _import_csv_text(session, bad_revenue)
    assert summary.validation_errors == 1
    assert "revenue" in summary.error_details[0][1]

    allowed_negative = dedent(
        """
        symbol,snapshot_date,fiscal_year,source,operating_income,net_income,eps,roe,revenue_growth_yoy
        000660,2026-05-01,2025,MANUAL,-100,-50,-10,-1.5,-3.2
        """,
    ).strip() + "\n"
    summary2 = _import_csv_text(session, allowed_negative)
    session.commit()
    assert summary2.validation_errors == 0
    row = FundamentalSnapshotRepository(session).get_latest_by_symbol("000660")
    assert row is not None
    assert row.operating_income == Decimal("-100.0000")
    assert row.net_income == Decimal("-50.0000")
    assert row.eps == Decimal("-10.0000")
    assert row.roe == Decimal("-1.5000")
    assert row.revenue_growth_yoy == Decimal("-3.2000")


def test_run_import_dry_run_and_commit(tmp_path):
    from scripts import import_fundamentals as cli

    db_path = tmp_path / "fundamentals.db"
    db_url = f"sqlite:///{db_path}"

    dry_summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=False,
        database_url=db_url,
    )
    assert dry_summary.inserted == 3
    factory = cli._build_session_factory(db_url)
    s = factory()
    try:
        assert list(s.execute(select(FundamentalSnapshot)).scalars().all()) == []
    finally:
        s.close()

    commit_summary = cli.run_import(
        file_path=str(SAMPLE_CSV_PATH),
        commit=True,
        database_url=db_url,
    )
    assert commit_summary.inserted == 3
    s = factory()
    try:
        assert len(s.execute(select(FundamentalSnapshot)).scalars().all()) == 3
    finally:
        s.close()
