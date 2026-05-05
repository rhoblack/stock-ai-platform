"""Integration tests for v0.6 FundamentalSnapshot repository PR1.

Scope:
  * ORM metadata and table creation
  * FundamentalSnapshotRepository CRUD/upsert/read helpers
  * NULL fiscal_quarter idempotency
  * normalized metric storage only; no body/full_text/raw document columns

Out of scope:
  * CSV import
  * provider interfaces
  * scheduler jobs
  * API/frontend surfaces
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select

from app.data.repositories import FundamentalSnapshotRepository
from app.db import Base
from app.db.models import FundamentalSnapshot
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def _upsert_sample(
    repo: FundamentalSnapshotRepository,
    *,
    symbol: str = "005930",
    snapshot_date: date = date(2026, 5, 1),
    fiscal_year: int = 2025,
    fiscal_quarter: int | None = 4,
    revenue: Decimal = Decimal("258935500.1234"),
    per: Decimal = Decimal("12.3456"),
    source: str = "MANUAL_CSV",
):
    return repo.upsert_by_symbol_period(
        symbol=symbol,
        snapshot_date=snapshot_date,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        revenue=revenue,
        operating_income=Decimal("32726000.0000"),
        net_income=Decimal("34451000.0000"),
        total_assets=Decimal("455905000.0000"),
        total_liabilities=Decimal("112334000.0000"),
        total_equity=Decimal("343571000.0000"),
        eps=Decimal("5200.1234"),
        bps=Decimal("56000.5678"),
        per=per,
        pbr=Decimal("1.2345"),
        roe=Decimal("9.8765"),
        debt_ratio=Decimal("32.7000"),
        dividend_yield=Decimal("2.1000"),
        revenue_growth_yoy=Decimal("14.2500"),
        operating_income_growth_yoy=Decimal("30.5000"),
        source=source,
    )


def test_fundamental_snapshot_metadata_creates_table(session):
    table = FundamentalSnapshot.__table__
    assert table.name == "fundamental_snapshots"
    assert "fundamental_snapshots" in Base.metadata.tables

    inspector = inspect(session.bind)
    assert "fundamental_snapshots" in inspector.get_table_names()

    column_names = {column["name"] for column in inspector.get_columns("fundamental_snapshots")}
    assert {
        "id",
        "symbol",
        "snapshot_date",
        "fiscal_year",
        "fiscal_quarter",
        "revenue",
        "operating_income",
        "net_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "eps",
        "bps",
        "per",
        "pbr",
        "roe",
        "debt_ratio",
        "dividend_yield",
        "revenue_growth_yoy",
        "operating_income_growth_yoy",
        "source",
        "created_at",
        "updated_at",
    }.issubset(column_names)


def test_create_saves_and_reads_by_symbol_period(session):
    repo = FundamentalSnapshotRepository(session)
    row = repo.create(
        symbol="005930",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
        revenue=Decimal("258935500.1234"),
        per=Decimal("12.3456"),
        source="MANUAL_CSV",
    )
    session.commit()

    fetched = repo.get_by_symbol_period(
        symbol="005930",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
    )
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.symbol == "005930"
    assert fetched.revenue == Decimal("258935500.1234")
    assert fetched.per == Decimal("12.3456")


def test_upsert_by_symbol_period_is_idempotent_and_updates_metrics(session):
    repo = FundamentalSnapshotRepository(session)
    first = _upsert_sample(repo, revenue=Decimal("1000.0000"), per=Decimal("10.0000"))
    session.commit()

    second = _upsert_sample(repo, revenue=Decimal("2000.0000"), per=Decimal("11.5000"))
    session.commit()

    rows = session.execute(select(FundamentalSnapshot)).scalars().all()
    assert second.id == first.id
    assert len(rows) == 1
    assert second.revenue == Decimal("2000.0000")
    assert second.per == Decimal("11.5000")


def test_get_latest_by_symbol_uses_latest_snapshot_date(session):
    repo = FundamentalSnapshotRepository(session)
    _upsert_sample(repo, snapshot_date=date(2026, 3, 31), fiscal_year=2025, fiscal_quarter=4)
    latest = _upsert_sample(repo, snapshot_date=date(2026, 6, 30), fiscal_year=2026, fiscal_quarter=1)
    session.commit()

    assert repo.get_latest_by_symbol("005930").id == latest.id
    assert repo.get_latest_by_symbol("000660") is None


def test_list_recent_by_symbol_orders_desc_and_respects_limit(session):
    repo = FundamentalSnapshotRepository(session)
    old = _upsert_sample(repo, snapshot_date=date(2026, 3, 31), fiscal_year=2025, fiscal_quarter=4)
    middle = _upsert_sample(repo, snapshot_date=date(2026, 6, 30), fiscal_year=2026, fiscal_quarter=1)
    newest = _upsert_sample(repo, snapshot_date=date(2026, 9, 30), fiscal_year=2026, fiscal_quarter=2)
    _upsert_sample(repo, symbol="000660", snapshot_date=date(2026, 10, 1), fiscal_year=2026, fiscal_quarter=2)
    session.commit()

    rows = repo.list_recent_by_symbol("005930", limit=2)
    assert [row.id for row in rows] == [newest.id, middle.id]
    assert old.id not in [row.id for row in rows]


def test_list_by_fiscal_year_filters_and_orders_by_symbol(session):
    repo = FundamentalSnapshotRepository(session)
    samsung = _upsert_sample(repo, symbol="005930", fiscal_year=2025)
    sk = _upsert_sample(repo, symbol="000660", fiscal_year=2025)
    _upsert_sample(repo, symbol="035420", fiscal_year=2024)
    session.commit()

    rows = repo.list_by_fiscal_year(2025)
    assert [row.id for row in rows] == [sk.id, samsung.id]
    assert {row.fiscal_year for row in rows} == {2025}


def test_nullable_fiscal_quarter_is_allowed_and_upserted_idempotently(session):
    repo = FundamentalSnapshotRepository(session)
    first = _upsert_sample(
        repo,
        snapshot_date=date(2026, 4, 1),
        fiscal_year=2025,
        fiscal_quarter=None,
        revenue=Decimal("3000.0000"),
    )
    second = _upsert_sample(
        repo,
        snapshot_date=date(2026, 4, 1),
        fiscal_year=2025,
        fiscal_quarter=None,
        revenue=Decimal("3500.0000"),
    )
    session.commit()

    assert second.id == first.id
    assert second.fiscal_quarter is None
    assert second.revenue == Decimal("3500.0000")
    assert len(session.execute(select(FundamentalSnapshot)).scalars().all()) == 1


def test_decimal_metric_fields_round_trip(session):
    repo = FundamentalSnapshotRepository(session)
    row = _upsert_sample(repo)
    session.commit()

    fetched = repo.get(row.id)
    assert fetched is not None
    assert fetched.revenue == Decimal("258935500.1234")
    assert fetched.eps == Decimal("5200.1234")
    assert fetched.bps == Decimal("56000.5678")
    assert fetched.roe == Decimal("9.8765")
    assert fetched.revenue_growth_yoy == Decimal("14.2500")


def test_fundamental_snapshot_has_no_body_or_full_text_columns():
    forbidden_columns = {
        "body",
        "content",
        "full_text",
        "paragraph",
        "paragraph_text",
        "raw_text",
        "original_text",
        "report_body",
        "document_blob",
        "pdf_blob",
        "excel_blob",
        "source_file_path",
    }
    column_names = set(FundamentalSnapshot.__table__.columns.keys())
    assert column_names.isdisjoint(forbidden_columns)
