"""Integration tests for v0.6 Phase B EarningsEvent repository."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select

from app.data.repositories import EarningsEventRepository
from app.db import Base
from app.db.models import EarningsEvent
from app.db.session import create_db_engine, create_session_factory


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


def _upsert_event(
    repo: EarningsEventRepository,
    *,
    symbol: str = "005930",
    event_date: date = date(2026, 4, 30),
    fiscal_year: int = 2026,
    fiscal_quarter: int | None = 1,
    event_type: str = "FINAL",
    surprise_type: str | None = "BEAT",
    operating_income_actual: Decimal | None = Decimal("7100000.0000"),
    operating_income_consensus: Decimal | None = Decimal("6500000.0000"),
):
    return repo.upsert_by_symbol_event(
        symbol=symbol,
        company_name=f"{symbol} Corp",
        event_date=event_date,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        event_type=event_type,
        revenue_actual=Decimal("77000000.0000"),
        revenue_consensus=Decimal("75000000.0000"),
        operating_income_actual=operating_income_actual,
        operating_income_consensus=operating_income_consensus,
        net_income_actual=Decimal("6200000.0000"),
        net_income_consensus=Decimal("5800000.0000"),
        eps_actual=Decimal("1100.0000"),
        eps_consensus=Decimal("1000.0000"),
        surprise_type=surprise_type,
        surprise_pct=Decimal("9.2308") if surprise_type == "BEAT" else None,
        source="TEST",
        memo="sample",
    )


def test_earnings_event_metadata_creates_table(session):
    assert EarningsEvent.__tablename__ == "earnings_events"
    inspector = inspect(session.bind)
    assert "earnings_events" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("earnings_events")}
    assert {
        "id",
        "symbol",
        "company_name",
        "event_date",
        "fiscal_year",
        "fiscal_quarter",
        "event_type",
        "revenue_actual",
        "revenue_consensus",
        "operating_income_actual",
        "operating_income_consensus",
        "net_income_actual",
        "net_income_consensus",
        "eps_actual",
        "eps_consensus",
        "surprise_type",
        "surprise_pct",
        "source",
        "memo",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_create_and_get_by_symbol_event(session):
    repo = EarningsEventRepository(session)
    event = repo.create(
        symbol="005930",
        event_date=date(2026, 4, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
        event_type="FINAL",
        operating_income_actual=Decimal("7100000.0000"),
        surprise_type="BEAT",
    )
    session.commit()

    fetched = repo.get_by_symbol_event(
        symbol="005930",
        event_date=date(2026, 4, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
        event_type="FINAL",
    )
    assert fetched is not None
    assert fetched.id == event.id
    assert fetched.operating_income_actual == Decimal("7100000.0000")


def test_upsert_by_symbol_event_is_idempotent_and_updates(session):
    repo = EarningsEventRepository(session)
    first = _upsert_event(repo, operating_income_actual=Decimal("7000000.0000"))
    session.commit()
    second = _upsert_event(repo, operating_income_actual=Decimal("7100000.0000"))
    session.commit()

    assert second.id == first.id
    assert second.operating_income_actual == Decimal("7100000.0000")
    assert len(session.execute(select(EarningsEvent)).scalars().all()) == 1


def test_nullable_fiscal_quarter_upsert_is_idempotent(session):
    repo = EarningsEventRepository(session)
    first = _upsert_event(repo, fiscal_quarter=None, event_type="FINAL")
    second = _upsert_event(repo, fiscal_quarter=None, event_type="FINAL")
    session.commit()

    assert second.id == first.id
    assert second.fiscal_quarter is None
    assert len(session.execute(select(EarningsEvent)).scalars().all()) == 1


def test_get_latest_and_list_recent_by_symbol(session):
    repo = EarningsEventRepository(session)
    older = _upsert_event(repo, event_date=date(2026, 4, 30), fiscal_quarter=1)
    newer = _upsert_event(repo, event_date=date(2026, 7, 30), fiscal_quarter=2)
    _upsert_event(repo, symbol="000660", event_date=date(2026, 8, 1), fiscal_quarter=2)
    session.commit()

    assert repo.get_latest_by_symbol("005930").id == newer.id
    rows = repo.list_recent_by_symbol("005930", limit=2)
    assert [row.id for row in rows] == [newer.id, older.id]


def test_list_upcoming_orders_ascending(session):
    repo = EarningsEventRepository(session)
    _upsert_event(repo, symbol="005930", event_date=date(2026, 5, 20), event_type="CONSENSUS")
    sk = _upsert_event(repo, symbol="000660", event_date=date(2026, 5, 10), event_type="CONSENSUS")
    naver = _upsert_event(repo, symbol="035420", event_date=date(2026, 5, 15), event_type="CONSENSUS")
    _upsert_event(repo, symbol="005380", event_date=date(2026, 4, 30), event_type="FINAL")
    session.commit()

    rows = repo.list_upcoming(since=date(2026, 5, 1), until=date(2026, 5, 31))
    assert [row.id for row in rows][:2] == [sk.id, naver.id]
    assert all(row.event_date >= date(2026, 5, 1) for row in rows)


def test_list_by_surprise_type(session):
    repo = EarningsEventRepository(session)
    beat = _upsert_event(repo, symbol="005930", surprise_type="BEAT")
    _upsert_event(repo, symbol="000660", surprise_type="MEET")
    miss = _upsert_event(repo, symbol="035420", surprise_type="MISS")
    session.commit()

    assert [row.id for row in repo.list_by_surprise_type("BEAT")] == [beat.id]
    assert [row.id for row in repo.list_by_surprise_type("MISS")] == [miss.id]


def test_earnings_event_has_no_body_or_full_text_columns():
    forbidden = {
        "body",
        "content",
        "full_text",
        "paragraph",
        "raw_text",
        "html_body",
        "source_file_path",
        "document_blob",
        "pdf_blob",
        "excel_blob",
    }
    assert set(EarningsEvent.__table__.columns.keys()).isdisjoint(forbidden)
