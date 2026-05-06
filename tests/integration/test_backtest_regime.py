"""Integration tests for v0.7 Phase C — regime split + cost model wiring."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backtest import (
    COST_MODEL_VERSION,
    UNCLASSIFIED_BUCKET,
    BacktestEngine,
    CostModel,
    assign_regime,
)
from app.data.repositories import (
    BacktestResultRepository,
    BacktestRunRepository,
)
from app.db import Base
from app.db.models import (
    DataSnapshot,
    MarketRegime,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
)
from app.db.session import create_db_engine, create_session_factory
from app.strategy.interfaces import (
    STRATEGY_ACTION_BUY,
)
from app.strategy.rule_based import TopGradeStrategy


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Helpers (mirror Phase B helpers)
# ---------------------------------------------------------------------------


def _make_run(session, run_date: date) -> RecommendationRun:
    run = RecommendationRun(
        run_date=run_date,
        started_at=datetime(run_date.year, run_date.month, run_date.day, 6, 0, tzinfo=timezone.utc),
        status="SUCCESS",
        telegram_sent=False,
    )
    session.add(run)
    session.flush()
    return run


def _make_snapshot(session, run_date: date) -> DataSnapshot:
    snap = DataSnapshot(
        snapshot_time=datetime(run_date.year, run_date.month, run_date.day, 6, 0, tzinfo=timezone.utc),
        symbol="005930",
        snapshot_type="RECOMMENDATION",
        market_context_json={},
    )
    session.add(snap)
    session.flush()
    return snap


def _make_recommendation(
    session,
    run: RecommendationRun,
    snapshot: DataSnapshot | None,
    *,
    rank: int,
    symbol: str,
    grade: str,
    total_score: Decimal = Decimal("80"),
) -> Recommendation:
    rec = Recommendation(
        run_id=run.run_id,
        rank=rank,
        market="KOSPI",
        symbol=symbol,
        name=f"name-{symbol}",
        grade=grade,
        total_score=total_score,
        snapshot_id=snapshot.snapshot_id if snapshot is not None else None,
    )
    session.add(rec)
    session.flush()
    return rec


def _make_results(
    session,
    rec: Recommendation,
    *,
    return_5d: Decimal | None = None,
):
    for days_after in (1, 3, 5, 20):
        session.add(
            RecommendationResult(
                recommendation_id=rec.id,
                result_date=date(2026, 5, 4 + days_after),
                days_after=days_after,
                close_return=return_5d if days_after == 5 else None,
            ),
        )
    session.flush()


def _make_regime(session, regime_date: date, regime: str, market: str = "KOSPI"):
    session.add(
        MarketRegime(
            date=regime_date,
            market=market,
            regime=regime,
            market_score=Decimal("60"),
            risk_level="MEDIUM",
            reason="seed",
        ),
    )
    session.flush()


# ---------------------------------------------------------------------------
# assign_regime (unit-style but uses session)
# ---------------------------------------------------------------------------


def test_assign_regime_returns_exact_match(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")
    assert assign_regime(session, date(2026, 5, 4)) == "UPTREND_EARLY"


def test_assign_regime_falls_back_to_most_recent_at_or_before(session):
    _make_regime(session, date(2026, 4, 25), "DOWNTREND")
    _make_regime(session, date(2026, 5, 1), "UPTREND_EARLY")
    # signal_date 5/4: nothing on 5/4 → use 5/1
    assert assign_regime(session, date(2026, 5, 4)) == "UPTREND_EARLY"


def test_assign_regime_returns_none_when_no_prior_regime(session):
    _make_regime(session, date(2026, 6, 1), "DOWNTREND")
    # signal_date precedes all regime data
    assert assign_regime(session, date(2026, 5, 4)) is None


def test_assign_regime_filters_by_market(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY", market="KOSPI")
    _make_regime(session, date(2026, 5, 4), "DOWNTREND", market="KOSDAQ")
    assert assign_regime(session, date(2026, 5, 4), market="KOSPI") == "UPTREND_EARLY"
    assert assign_regime(session, date(2026, 5, 4), market="KOSDAQ") == "DOWNTREND"


# ---------------------------------------------------------------------------
# BacktestEngine summary surfaces cost + regime fields
# ---------------------------------------------------------------------------


def test_dry_run_summary_carries_cost_and_regime_fields(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.dry_run is True
    assert summary.cost_model_version == COST_MODEL_VERSION
    assert summary.total_cost == Decimal("0.0033")
    # 3.0 - 0.33 = 2.67
    assert summary.cost_adjusted_avg_return_5d == Decimal("2.6700")
    # 1 BUY signal in UPTREND_EARLY bucket
    assert len(summary.regime_breakdown) == 1
    entry = summary.regime_breakdown[0]
    assert entry.regime == "UPTREND_EARLY"
    assert entry.buy_count == 1
    assert entry.win_rate_5d == Decimal("1.0000")
    assert entry.avg_return_5d == Decimal("3.0000")
    assert entry.cost_adjusted_avg_return_5d == Decimal("2.6700")


def test_dry_run_buckets_unmatched_regime_under_unclassified(session):
    # No MarketRegime row → assign_regime returns None
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("2.0"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert len(summary.regime_breakdown) == 1
    assert summary.regime_breakdown[0].regime == UNCLASSIFIED_BUCKET


def test_commit_persists_cost_and_regime_columns(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(
        strategy=TopGradeStrategy(),
        dry_run=False,
        run_date=date(2026, 5, 6),
    )
    session.commit()

    runs = BacktestRunRepository(session).list_recent()
    assert len(runs) == 1
    row = runs[0]
    # Run-level summary_json carries cost / regime payload.
    assert row.summary_json is not None
    assert row.summary_json["cost_model_version"] == COST_MODEL_VERSION
    # str(Decimal("0.00330")) preserves trailing zero from the rate sum
    assert row.summary_json["total_cost"] == "0.00330"
    assert row.summary_json["cost_adjusted_avg_return_5d"] == "2.6700"
    assert row.summary_json["regime_breakdown"][0]["regime"] == "UPTREND_EARLY"
    # config_json also carries cost_model + regime metadata.
    assert row.config_json["cost_model_version"] == COST_MODEL_VERSION

    results = BacktestResultRepository(session).list_by_run(row.id)
    assert len(results) == 1
    assert results[0].cost_adjusted_return_5d == Decimal("2.6700")
    assert results[0].regime == "UPTREND_EARLY"


def test_pass_or_avoid_rows_leave_cost_adjusted_return_null(session):
    _make_regime(session, date(2026, 5, 4), "DOWNTREND")
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    # grade=C → PASS, return_5d set
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="C")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(
        strategy=TopGradeStrategy(),
        dry_run=False,
        run_date=date(2026, 5, 6),
    )
    session.commit()

    rows = BacktestResultRepository(session).list_by_run(summary.backtest_run_id)
    assert len(rows) == 1
    assert rows[0].signal_action != STRATEGY_ACTION_BUY
    # PASS / AVOID rows leave cost_adjusted_return_5d NULL by design
    assert rows[0].cost_adjusted_return_5d is None
    # But regime is still assigned for analytical breakdowns
    assert rows[0].regime == "DOWNTREND"


def test_regime_breakdown_groups_buy_rows_by_regime(session):
    _make_regime(session, date(2026, 5, 1), "DOWNTREND")
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")

    run_a = _make_run(session, date(2026, 5, 2))  # → DOWNTREND (5/1 latest)
    run_b = _make_run(session, date(2026, 5, 5))  # → UPTREND_EARLY
    snap_a = _make_snapshot(session, date(2026, 5, 2))
    snap_b = _make_snapshot(session, date(2026, 5, 5))
    rec_a = _make_recommendation(session, run_a, snap_a, rank=1, symbol="005930", grade="A")
    rec_b1 = _make_recommendation(session, run_b, snap_b, rank=1, symbol="000660", grade="A")
    rec_b2 = _make_recommendation(session, run_b, snap_b, rank=2, symbol="035420", grade="A")
    _make_results(session, rec_a, return_5d=Decimal("-1.0"))
    _make_results(session, rec_b1, return_5d=Decimal("3.0"))
    _make_results(session, rec_b2, return_5d=Decimal("5.0"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    by_regime = {entry.regime: entry for entry in summary.regime_breakdown}
    # Sorted by buy_count desc → UPTREND_EARLY (2) first
    assert summary.regime_breakdown[0].regime == "UPTREND_EARLY"
    assert summary.regime_breakdown[1].regime == "DOWNTREND"

    uptrend = by_regime["UPTREND_EARLY"]
    assert uptrend.buy_count == 2
    assert uptrend.win_rate_5d == Decimal("1.0000")
    assert uptrend.avg_return_5d == Decimal("4.0000")
    # 4.0 - 0.33 = 3.67
    assert uptrend.cost_adjusted_avg_return_5d == Decimal("3.6700")

    downtrend = by_regime["DOWNTREND"]
    assert downtrend.buy_count == 1
    assert downtrend.win_rate_5d == Decimal("0.0000")
    assert downtrend.avg_return_5d == Decimal("-1.0000")
    # -1.0 - 0.33 = -1.33
    assert downtrend.cost_adjusted_avg_return_5d == Decimal("-1.3300")


def test_aggregate_by_regime_repository_method(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(
        strategy=TopGradeStrategy(),
        dry_run=False,
        run_date=date(2026, 5, 6),
    )
    session.commit()

    counts = BacktestResultRepository(session).aggregate_by_regime(summary.backtest_run_id)
    assert counts == {"UPTREND_EARLY": 1}


def test_aggregate_by_regime_buckets_null_under_unclassified(session):
    # No MarketRegime data
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(
        strategy=TopGradeStrategy(),
        dry_run=False,
        run_date=date(2026, 5, 6),
    )
    session.commit()

    counts = BacktestResultRepository(session).aggregate_by_regime(summary.backtest_run_id)
    assert counts == {UNCLASSIFIED_BUCKET: 1}


def test_custom_cost_model_propagates_through_summary(session):
    _make_regime(session, date(2026, 5, 4), "UPTREND_EARLY")
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A")
    _make_results(session, rec, return_5d=Decimal("3.0"))

    custom = CostModel(
        buy_fee=Decimal("0.0005"),
        sell_fee=Decimal("0.0005"),
        sell_tax=Decimal("0.0025"),
        slippage=Decimal("0.0020"),
        version="custom-v1",
    )
    engine = BacktestEngine(session, cost_model=custom)
    summary = engine.run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.cost_model_version == "custom-v1"
    assert summary.total_cost == Decimal("0.0055")
    # 3.0 - 0.55 = 2.45
    assert summary.cost_adjusted_avg_return_5d == Decimal("2.4500")
