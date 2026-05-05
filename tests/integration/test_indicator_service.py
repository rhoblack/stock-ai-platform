from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analysis.indicator_service import TechnicalIndicatorService
from app.data.repositories import DailyPriceRepository, StockIndicatorRepository
from app.db import Base
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


def _seed_rising_prices(
    repository: DailyPriceRepository,
    *,
    symbol: str,
    n_bars: int,
    start_close: int = 100,
    start_date: date = date(2026, 1, 1),
    base_volume: int = 1_000_000,
    last_volume_multiplier: int = 3,
) -> None:
    for i in range(n_bars):
        close = Decimal(str(start_close + i))
        is_last = i == n_bars - 1
        volume = base_volume * (last_volume_multiplier if is_last else 1)
        repository.upsert(
            symbol=symbol,
            price_date=start_date + timedelta(days=i),
            open_price=close,
            high_price=close,
            low_price=close,
            close_price=close,
            volume=volume,
        )


def test_indicator_service_returns_none_when_no_prices(session):
    service = TechnicalIndicatorService(
        daily_price_repository=DailyPriceRepository(session),
        indicator_repository=StockIndicatorRepository(session),
    )

    result = service.analyze_and_store("005930")
    session.commit()

    assert result is None
    assert StockIndicatorRepository(session).list() == []


def test_indicator_service_persists_full_snapshot_for_long_history(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=130)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshot = service.analyze_and_store("005930")
    session.commit()

    assert snapshot is not None
    indicator = StockIndicatorRepository(session).get_by_symbol_date(
        "005930", snapshot.date,
    )
    assert indicator is not None
    assert indicator.symbol == "005930"
    assert indicator.date == snapshot.date
    assert indicator.ma5 == snapshot.ma5
    assert indicator.ma20 == snapshot.ma20
    assert indicator.ma60 == snapshot.ma60
    assert indicator.ma120 == snapshot.ma120
    assert indicator.rsi14 == snapshot.rsi14
    assert indicator.macd == snapshot.macd
    assert indicator.macd_signal == snapshot.macd_signal
    assert indicator.volume_ratio_20d == snapshot.volume_ratio_20d
    assert indicator.breakout_20d == snapshot.breakout_20d
    assert indicator.breakout_60d == snapshot.breakout_60d
    assert indicator.ma_alignment == snapshot.ma_alignment
    assert indicator.technical_score == snapshot.technical_score


def test_indicator_service_idempotent_on_rerun(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=130)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    service.analyze_and_store("005930")
    session.commit()
    service.analyze_and_store("005930")
    session.commit()

    indicators = StockIndicatorRepository(session).list()
    assert len(indicators) == 1


def test_indicator_service_overwrites_with_new_snapshot_after_price_correction(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=130)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    first = service.analyze_and_store("005930")
    session.commit()

    # Correct the most recent close downward via upsert and rerun.
    last_date = first.date
    price_repo.upsert(
        symbol="005930",
        price_date=last_date,
        open_price=Decimal("100"),
        high_price=Decimal("100"),
        low_price=Decimal("100"),
        close_price=Decimal("100"),
        volume=1_000_000,
    )
    session.commit()
    second = service.analyze_and_store("005930")
    session.commit()

    assert first.technical_score is not None
    assert second is not None
    assert second.technical_score is not None
    assert second.technical_score < first.technical_score

    indicator = StockIndicatorRepository(session).get_by_symbol_date(
        "005930", last_date,
    )
    assert indicator is not None
    assert indicator.technical_score == second.technical_score


def test_indicator_service_short_history_persists_partial_snapshot(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=4)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshot = service.analyze_and_store("005930")
    session.commit()

    assert snapshot is not None
    indicator = StockIndicatorRepository(session).get_by_symbol_date(
        "005930", snapshot.date,
    )
    assert indicator is not None
    assert indicator.ma5 is None
    assert indicator.ma20 is None
    assert indicator.ma60 is None
    assert indicator.rsi14 is None
    assert indicator.breakout_20d is None
    assert indicator.ma_alignment is None
    assert indicator.technical_score == Decimal("0.0000")


def test_indicator_service_analyze_and_store_many_skips_missing_symbols(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=10)
    _seed_rising_prices(price_repo, symbol="000660", n_bars=10)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshots = service.analyze_and_store_many(["005930", "000660", "AAAAAA"])
    session.commit()

    assert len(snapshots) == 2
    indicators = StockIndicatorRepository(session).list()
    assert {i.symbol for i in indicators} == {"005930", "000660"}


def test_indicator_service_lookback_days_limits_input_window(session):
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=300)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshot = service.analyze_and_store("005930", lookback_days=30)
    session.commit()

    assert snapshot is not None
    assert snapshot.ma20 is not None  # 30 bars >= 20
    assert snapshot.ma60 is None      # 30 bars < 60
    assert snapshot.ma120 is None     # 30 bars < 120


# ---------- v0.3 Phase B: ATR + candle patterns persist ----------

def test_indicator_service_persists_atr_candle_patterns_volatility(session):
    """Phase B 의 신규 필드 (atr14 / candle_patterns / volatility_band) 가
    snapshot 에서 stock_indicators 테이블까지 그대로 흘러가는지 검증."""
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=130)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshot = service.analyze_and_store("005930")
    session.commit()

    assert snapshot is not None
    indicator = StockIndicatorRepository(session).get_by_symbol_date(
        "005930", snapshot.date,
    )
    assert indicator is not None
    assert indicator.atr14 == snapshot.atr14
    assert indicator.candle_patterns == snapshot.candle_patterns
    assert indicator.volatility_band == snapshot.volatility_band

    # 시드는 OHLC 가 모두 동일 close (high=low=close=open) → TR=|Δclose|=1 → ATR=1.
    # 130 bar 끝의 close=229, ATR/close ≈ 0.44% → LOW band.
    assert indicator.atr14 == Decimal("1.0000")
    assert indicator.volatility_band == "LOW"
    # OHLC 모두 동일하므로 DOJI 만 트리거
    assert indicator.candle_patterns == ["DOJI"]


def test_indicator_service_short_history_persists_none_atr(session):
    """Bar 수 부족 시 atr14 / volatility_band 가 None 으로 그대로 저장된다."""
    price_repo = DailyPriceRepository(session)
    _seed_rising_prices(price_repo, symbol="005930", n_bars=4)
    session.commit()

    service = TechnicalIndicatorService(
        daily_price_repository=price_repo,
        indicator_repository=StockIndicatorRepository(session),
    )
    snapshot = service.analyze_and_store("005930")
    session.commit()

    assert snapshot is not None
    indicator = StockIndicatorRepository(session).get_by_symbol_date(
        "005930", snapshot.date,
    )
    assert indicator is not None
    assert indicator.atr14 is None
    assert indicator.volatility_band is None
    # 짧은 히스토리에도 doji 자체는 단일 bar 만으로 트리거 가능
    assert indicator.candle_patterns == ["DOJI"]
    # base 컴포넌트가 모두 None 이라 score 0 유지 (DOJI bonus=0)
    assert indicator.technical_score == Decimal("0.0000")
