from datetime import date
from decimal import Decimal

import pytest

from app.data.repositories import (
    DailyPriceRepository,
    DataSnapshotRepository,
    DecisionLogRepository,
    HoldingCheckRepository,
    HoldingRepository,
    StockIndicatorRepository,
)
from app.db import Base
from app.db.models import Holding
from app.db.session import create_db_engine, create_session_factory
from app.decision.holding_check_engine import (
    ALERT_MA20_BREAKDOWN,
    ALERT_SCORE_DROP,
    ALERT_STOP_LOSS_NEAR,
    CHECK_TYPE_POST_MARKET,
    CHECK_TYPE_PRE_MARKET,
    DECISION_HOLD,
    DECISION_REDUCE,
    DECISION_SELL_REVIEW,
    HoldingCheckEngine,
    HoldingCheckResult,
)
from app.decision.risk_engine import (
    RISK_FLAG_LOW_TECHNICAL_SCORE,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RiskEngine,
)
from app.decision.scoring_engine import ScoringEngine


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


def _make_engine(session) -> HoldingCheckEngine:
    return HoldingCheckEngine(
        scoring_engine=ScoringEngine(),
        risk_engine=RiskEngine(),
        holding_repository=HoldingRepository(session),
        daily_price_repository=DailyPriceRepository(session),
        indicator_repository=StockIndicatorRepository(session),
        snapshot_repository=DataSnapshotRepository(session),
        holding_check_repository=HoldingCheckRepository(session),
        decision_log_repository=DecisionLogRepository(session),
    )


def _seed_holding(
    session,
    *,
    symbol: str,
    quantity: Decimal = Decimal("10"),
    avg_buy_price: Decimal = Decimal("100"),
    is_active: bool = True,
) -> Holding:
    holding = HoldingRepository(session).add(
        Holding(
            symbol=symbol,
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            is_active=is_active,
        ),
    )
    session.flush()
    return holding


def _seed_price(
    session,
    *,
    symbol: str,
    price_date: date,
    close: Decimal,
):
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1_000_000,
    )
    session.flush()


def _seed_indicator(
    session,
    *,
    symbol: str,
    indicator_date: date,
    technical_score: Decimal | None = Decimal("70"),
    ma20: Decimal | None = Decimal("100"),
    ma_alignment: str | None = "BULL",
):
    StockIndicatorRepository(session).upsert(
        symbol=symbol,
        indicator_date=indicator_date,
        technical_score=technical_score,
        ma20=ma20,
        ma_alignment=ma_alignment,
    )
    session.flush()


# ---------- input validation ----------

def test_engine_rejects_invalid_check_type(session):
    engine = _make_engine(session)
    with pytest.raises(ValueError):
        engine.run(check_date=date(2026, 5, 4), check_type="MIDDAY")


# ---------- empty / skipped ----------

def test_engine_returns_empty_when_no_active_holdings(session):
    engine = _make_engine(session)
    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert isinstance(result, HoldingCheckResult)
    assert result.saved_count == 0
    assert result.alert_count == 0
    assert result.holding_check_ids == []
    assert HoldingCheckRepository(session).list() == []


def test_engine_skips_holding_without_daily_price(session):
    _seed_holding(session, symbol="005930")
    _seed_indicator(session, symbol="005930", indicator_date=date(2026, 5, 4))
    # no daily price seeded
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.saved_count == 0
    assert result.skipped_no_price == 1
    assert HoldingCheckRepository(session).list() == []


def test_engine_skips_holding_without_indicator(session):
    _seed_holding(session, symbol="005930")
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("105"))
    # no indicator seeded
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.saved_count == 0
    assert result.skipped_no_indicator == 1
    assert HoldingCheckRepository(session).list() == []


def test_engine_skips_inactive_holdings(session):
    _seed_holding(session, symbol="005930", is_active=False)
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("105"))
    _seed_indicator(session, symbol="005930", indicator_date=date(2026, 5, 4))
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.saved_count == 0
    assert HoldingCheckRepository(session).list() == []


# ---------- happy path ----------

def test_engine_persists_check_snapshot_and_decision_log(session):
    _seed_holding(
        session, symbol="005930",
        quantity=Decimal("10"), avg_buy_price=Decimal("100"),
    )
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("80"), ma20=Decimal("105"), ma_alignment="PERFECT_BULL",
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.saved_count == 1
    assert result.alert_count == 0

    checks = HoldingCheckRepository(session).list_by_symbol("005930")
    assert len(checks) == 1
    check = checks[0]
    assert check.check_date == date(2026, 5, 4)
    assert check.check_type == "PRE_MARKET"
    assert check.symbol == "005930"
    assert check.current_price == Decimal("110.0000")
    assert check.avg_buy_price == Decimal("100.0000")
    assert check.return_rate == Decimal("10.0000")
    assert check.technical_score == Decimal("80.0000")
    assert check.news_score is None
    assert check.earnings_score is None
    assert check.ai_score is None
    assert check.risk_score == Decimal("0.0000")
    assert check.total_score == Decimal("28.0000")  # 80 * 0.35; no penalty -> final = 28
    assert check.grade == "D"
    assert check.decision == DECISION_SELL_REVIEW  # tech-only Phase setup -> low total
    assert check.alert is False
    assert check.snapshot_id is not None

    snapshot = DataSnapshotRepository(session).get(check.snapshot_id)
    assert snapshot is not None
    assert snapshot.snapshot_type == "HOLDING_CHECK"
    assert snapshot.price_data_json["close"] == "110.0000"
    assert snapshot.indicator_data_json["ma20"] == "105.0000"
    assert snapshot.market_context_json["check_date"] == "2026-05-04"
    assert snapshot.market_context_json["check_type"] == "PRE_MARKET"
    assert snapshot.market_context_json["phase"] == "5-3"
    assert snapshot.market_context_json["risk_summary"] == {
        "level": RISK_LEVEL_LOW,
        "flags": [],
        "penalty": "0.0000",
    }

    logs = DecisionLogRepository(session).list_by_symbol("005930")
    assert len(logs) == 1
    log = logs[0]
    assert log.decision_type == "HOLDING"
    assert log.input_snapshot_id == check.snapshot_id
    assert log.final_decision == DECISION_SELL_REVIEW
    assert log.ai_result_json is None
    assert log.rule_result_json["return_rate"] == "10.0000"
    assert log.rule_result_json["current_price"] == "110.0000"
    assert log.rule_result_json["avg_buy_price"] == "100.0000"
    assert log.rule_result_json["weighted_components"]["technical"] == "28.0000"
    assert log.rule_result_json["placeholder_components"] == ["news", "earnings", "ai"]
    assert log.risk_result_json["alerts"] == []
    assert log.risk_result_json["risk_level"] == RISK_LEVEL_LOW
    assert log.risk_result_json["risk_penalty"] == "0.0000"
    assert log.risk_result_json["score_drop_threshold"] == "15"
    assert log.risk_result_json["stop_loss_return_threshold"] == "-5"
    assert log.risk_result_json["low_technical_score_threshold"] == "20"


def test_engine_idempotent_for_same_date_type_symbol(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("80"),
    )
    engine = _make_engine(session)

    engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()
    engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    checks = HoldingCheckRepository(session).list_by_symbol("005930")
    assert len(checks) == 1  # upsert kept it singular


def test_engine_creates_distinct_rows_for_pre_and_post_market(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("80"),
    )
    engine = _make_engine(session)

    engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()
    engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_POST_MARKET)
    session.commit()

    checks = HoldingCheckRepository(session).list_by_symbol("005930")
    assert {c.check_type for c in checks} == {"PRE_MARKET", "POST_MARKET"}


# ---------- alerts ----------

def test_alert_ma20_breakdown_when_close_below_ma20(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("99"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("60"), ma20=Decimal("105"),
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.alert_count == 1
    check = HoldingCheckRepository(session).list_by_symbol("005930")[0]
    assert check.alert is True
    assert "20일선 이탈" in check.reason

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert ALERT_MA20_BREAKDOWN in log.risk_result_json["alerts"]


def test_alert_stop_loss_near_when_return_le_minus_5_percent(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("94"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("60"), ma20=Decimal("90"),  # not below ma20
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.alert_count == 1
    check = HoldingCheckRepository(session).list_by_symbol("005930")[0]
    assert check.alert is True
    assert "손절 근접" in check.reason
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert log.risk_result_json["alerts"] == [ALERT_STOP_LOSS_NEAR]


def test_alert_score_drop_when_total_score_falls_15_or_more_vs_previous(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    # Day 1: high tech score
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 3), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 3),
        technical_score=Decimal("100"),  # weighted = 35
        ma20=Decimal("100"),
    )
    engine = _make_engine(session)
    engine.run(check_date=date(2026, 5, 3), check_type=CHECK_TYPE_POST_MARKET)
    session.commit()

    # Day 2: tech score drops sharply (35 -> ~3.5 = -31.5 drop, way over 15)
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("108"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("10"),
        ma20=Decimal("100"),
    )
    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.alert_count == 1
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]  # newest first
    assert ALERT_SCORE_DROP in log.risk_result_json["alerts"]
    assert log.risk_result_json["previous_total_score"] == "35.0000"


def test_alert_score_drop_does_not_fire_for_first_check(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("10"),
        ma20=Decimal("100"),
    )
    engine = _make_engine(session)
    engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert ALERT_SCORE_DROP not in log.risk_result_json["alerts"]


def test_multiple_alerts_combined_in_single_check(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))

    _seed_price(session, symbol="005930", price_date=date(2026, 5, 3), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 3),
        technical_score=Decimal("100"), ma20=Decimal("100"),
    )
    engine = _make_engine(session)
    engine.run(check_date=date(2026, 5, 3), check_type=CHECK_TYPE_POST_MARKET)
    session.commit()

    # Day 2: close (90) < ma20 (95), return (-10%), score drops sharply,
    # tech 10 also triggers LOW_TECHNICAL_SCORE
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("90"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("10"), ma20=Decimal("95"),
    )
    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    assert result.alert_count == 1
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert set(log.risk_result_json["alerts"]) == {
        ALERT_SCORE_DROP,
        ALERT_MA20_BREAKDOWN,
        ALERT_STOP_LOSS_NEAR,
        RISK_FLAG_LOW_TECHNICAL_SCORE,
    }
    assert log.risk_result_json["risk_level"] == RISK_LEVEL_HIGH
    check = HoldingCheckRepository(session).list_by_symbol("005930")[0]
    assert check.alert is True
    assert "점수 급락" in check.reason
    assert "20일선 이탈" in check.reason
    assert "손절 근접" in check.reason
    assert "기술 점수 낮음" in check.reason
    # Day 2 weighted = 10 * 0.35 = 3.5; penalty = 12+8+15+5 = 40; final = 0
    assert check.total_score == Decimal("0.0000")
    assert check.risk_score == Decimal("40.0000")


# ---------- decision derivation ----------

def test_decision_hold_when_total_score_in_a_range(session):
    """High enough score (>=70) -> HOLD."""
    from app.decision.holding_check_engine import _grade_for_score, _decision_from_grade

    assert _decision_from_grade(_grade_for_score(Decimal("90"))) == DECISION_HOLD
    assert _decision_from_grade(_grade_for_score(Decimal("70"))) == DECISION_HOLD
    assert _decision_from_grade(_grade_for_score(Decimal("60"))) == "WATCH"
    assert _decision_from_grade(_grade_for_score(Decimal("45"))) == DECISION_REDUCE
    assert _decision_from_grade(_grade_for_score(Decimal("20"))) == DECISION_SELL_REVIEW


def test_engine_writes_risk_summary_to_snapshot_market_context(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("99"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("60"), ma20=Decimal("105"),  # MA20 breakdown
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()
    assert result.alert_count == 1

    check = HoldingCheckRepository(session).list_by_symbol("005930")[0]
    snapshot = DataSnapshotRepository(session).get(check.snapshot_id)
    assert snapshot.market_context_json["risk_summary"]["level"] == RISK_LEVEL_MEDIUM
    assert snapshot.market_context_json["risk_summary"]["flags"] == [
        ALERT_MA20_BREAKDOWN,
    ]
    assert snapshot.market_context_json["risk_summary"]["penalty"] == "8.0000"


def test_engine_low_technical_score_flag_alone_records_alert_and_penalty(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("110"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("10"),  # < 20 -> LOW_TECHNICAL_SCORE
        ma20=Decimal("100"),
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()
    assert result.alert_count == 1

    check = HoldingCheckRepository(session).list_by_symbol("005930")[0]
    assert check.alert is True
    assert check.risk_score == Decimal("5.0000")  # PENALTY_LOW_TECH_HOLD
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert log.risk_result_json["alerts"] == [RISK_FLAG_LOW_TECHNICAL_SCORE]
    assert log.risk_result_json["risk_level"] == RISK_LEVEL_MEDIUM


def test_engine_does_not_compute_alerts_when_ma20_missing(session):
    _seed_holding(session, symbol="005930", avg_buy_price=Decimal("100"))
    _seed_price(session, symbol="005930", price_date=date(2026, 5, 4), close=Decimal("99"))
    _seed_indicator(
        session, symbol="005930", indicator_date=date(2026, 5, 4),
        technical_score=Decimal("60"), ma20=None,  # not enough history
    )
    engine = _make_engine(session)

    result = engine.run(check_date=date(2026, 5, 4), check_type=CHECK_TYPE_PRE_MARKET)
    session.commit()

    # Return rate is -1% (above -5), no MA20 to compare, no previous check -> no alerts
    assert result.alert_count == 0
    log = DecisionLogRepository(session).list_by_symbol("005930")[0]
    assert log.risk_result_json["alerts"] == []
    assert log.risk_result_json["ma20"] is None
