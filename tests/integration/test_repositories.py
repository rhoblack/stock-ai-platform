from datetime import date, datetime
from decimal import Decimal

import pytest

from app.data.repositories import (
    DailyPriceRepository,
    HoldingRepository,
    JobRunRepository,
    StockIndicatorRepository,
    StockRepository,
)
from app.db import Base
from app.db.models import Holding, JobRun, Stock, StockIndicator
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


def test_create_all_phase_2_tables(session):
    table_names = set(Base.metadata.tables)

    assert {
        "stocks",
        "holdings",
        "daily_prices",
        "stock_indicators",
        "job_runs",
    }.issubset(table_names)


def test_stock_repository_add_and_get_by_symbol(session):
    repository = StockRepository(session)

    repository.add(Stock(market="KOSPI", symbol="005930", name="Samsung Electronics"))
    session.commit()

    stock = repository.get_by_symbol("005930")

    assert stock is not None
    assert stock.market == "KOSPI"
    assert stock.name == "Samsung Electronics"


def test_holding_repository_lists_active_holdings(session):
    repository = HoldingRepository(session)

    repository.add(
        Holding(
            symbol="005930",
            quantity=Decimal("10"),
            avg_buy_price=Decimal("70000"),
            is_active=True,
        ),
    )
    repository.add(
        Holding(
            symbol="000660",
            quantity=Decimal("2"),
            avg_buy_price=Decimal("150000"),
            is_active=False,
        ),
    )
    session.commit()

    holdings = repository.list_active()

    assert len(holdings) == 1
    assert holdings[0].symbol == "005930"


def test_daily_price_repository_upsert_by_symbol_and_date(session):
    repository = DailyPriceRepository(session)
    price_date = date(2026, 5, 4)

    first = repository.upsert(
        symbol="005930",
        price_date=price_date,
        open_price=Decimal("70000"),
        high_price=Decimal("71000"),
        low_price=Decimal("69000"),
        close_price=Decimal("70500"),
        volume=1000000,
        trading_value=Decimal("70500000000"),
    )
    session.commit()

    second = repository.upsert(
        symbol="005930",
        price_date=price_date,
        open_price=Decimal("70100"),
        high_price=Decimal("72000"),
        low_price=Decimal("70000"),
        close_price=Decimal("71900"),
        volume=1200000,
        trading_value=Decimal("86280000000"),
    )
    session.commit()

    loaded = repository.get_by_symbol_date("005930", price_date)
    all_prices = repository.list()

    assert first.id == second.id
    assert loaded is not None
    assert loaded.close == Decimal("71900.0000")
    assert loaded.volume == 1200000
    assert len(all_prices) == 1


def test_stock_indicator_repository_add_and_get_by_symbol_date(session):
    repository = StockIndicatorRepository(session)
    indicator_date = date(2026, 5, 4)

    repository.add(
        StockIndicator(
            symbol="005930",
            date=indicator_date,
            ma5=Decimal("70000"),
            ma20=Decimal("68000"),
            breakout_20d=True,
            technical_score=Decimal("72"),
        ),
    )
    session.commit()

    indicator = repository.get_by_symbol_date("005930", indicator_date)

    assert indicator is not None
    assert indicator.breakout_20d is True
    assert indicator.technical_score == Decimal("72.0000")


def test_job_run_repository_add_and_list_by_status(session):
    repository = JobRunRepository(session)

    repository.add(
        JobRun(
            job_name="collect_close_data",
            started_at=datetime(2026, 5, 4, 18, 0, 0),
            finished_at=datetime(2026, 5, 4, 18, 1, 0),
            status="SUCCESS",
            result_summary={"rows": 500},
        ),
    )
    session.commit()

    job_runs = repository.list_by_status("SUCCESS")

    assert len(job_runs) == 1
    assert job_runs[0].job_name == "collect_close_data"
    assert job_runs[0].result_summary == {"rows": 500}
