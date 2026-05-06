"""Integration tests for v0.7 Phase B BacktestEngine + run_backtest CLI."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backtest.engine import (
    BUY_ONLY_METRICS_NOTE,
    BacktestEngine,
    build_score_snapshot,
)
from app.data.repositories import (
    BacktestResultRepository,
    BacktestRunRepository,
)
from app.data.repositories.backtest_runs import (
    STATUS_DRY_RUN,
    STATUS_SUCCESS,
)
from app.db import Base
from app.db.models import (
    BacktestRun,
    DataSnapshot,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
)
from app.db.session import create_db_engine, create_session_factory
from app.strategy.interfaces import (
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
)
from app.strategy.rule_based import (
    HighScoreStrategy,
    MultiSignalStrategy,
    TopGradeStrategy,
)


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
# Helpers
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


def _make_snapshot(session, run_date: date, *, market_context=None) -> DataSnapshot:
    snap = DataSnapshot(
        snapshot_time=datetime(run_date.year, run_date.month, run_date.day, 6, 0, tzinfo=timezone.utc),
        symbol="005930",
        snapshot_type="RECOMMENDATION",
        market_context_json=market_context or {},
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
    grade: str | None,
    total_score: Decimal | None,
    fundamental_score: Decimal | None = Decimal("60"),
    news_score: Decimal | None = Decimal("55"),
) -> Recommendation:
    rec = Recommendation(
        run_id=run.run_id,
        rank=rank,
        market="KOSPI",
        symbol=symbol,
        name=f"name-{symbol}",
        grade=grade,
        total_score=total_score,
        technical_score=Decimal("70") if total_score is not None else None,
        news_score=news_score,
        supply_score=Decimal("55"),
        fundamental_score=fundamental_score,
        ai_score=Decimal("50"),
        risk_score=Decimal("0"),
        snapshot_id=snapshot.snapshot_id if snapshot is not None else None,
    )
    session.add(rec)
    session.flush()
    return rec


def _make_results(
    session,
    rec: Recommendation,
    *,
    return_1d: Decimal | None = None,
    return_3d: Decimal | None = None,
    return_5d: Decimal | None = None,
    return_20d: Decimal | None = None,
    max_drawdown: Decimal | None = None,
    result_status: str | None = None,
) -> None:
    horizons = {
        1: return_1d,
        3: return_3d,
        5: return_5d,
        20: return_20d,
    }
    for days_after, value in horizons.items():
        session.add(
            RecommendationResult(
                recommendation_id=rec.id,
                result_date=date(2026, 5, 4 + days_after),
                days_after=days_after,
                close_return=value,
                max_drawdown=max_drawdown if days_after == 5 else None,
                result_status=result_status if days_after == 5 else None,
            ),
        )
    session.flush()


# ---------------------------------------------------------------------------
# build_score_snapshot
# ---------------------------------------------------------------------------


def test_build_score_snapshot_pulls_from_recommendation_and_snapshot(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(
        session,
        date(2026, 5, 4),
        market_context={
            "risk_summary": {"level": "LOW", "flags": ["NONE"]},
            "news_evidence": {"news_count": 1},
            "fundamental_evidence": {"per": "10"},
        },
    )
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))

    snapshot = build_score_snapshot(rec, snap)
    assert snapshot.symbol == "005930"
    assert snapshot.grade == "A"
    assert snapshot.total_score == Decimal("80")
    assert snapshot.risk_level == "LOW"
    assert snapshot.risk_flags == ["NONE"]
    assert snapshot.evidence is not None
    assert "news_evidence" in snapshot.evidence
    assert "fundamental_evidence" in snapshot.evidence
    # Disclosure / earnings absent → not in evidence dict (cleaned out)
    assert "disclosure_risk_evidence" not in snapshot.evidence
    assert "earnings_evidence" not in snapshot.evidence


def test_build_score_snapshot_handles_missing_snapshot(session):
    run = _make_run(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, None, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))

    snapshot = build_score_snapshot(rec, None)
    assert snapshot.symbol == "005930"
    assert snapshot.risk_level is None
    assert snapshot.risk_flags == []
    assert snapshot.evidence is None


def test_build_score_snapshot_handles_malformed_market_context(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(
        session,
        date(2026, 5, 4),
        market_context={
            "risk_summary": "not-a-dict",
            "news_evidence": "still-not-a-dict",
        },
    )
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))

    snapshot = build_score_snapshot(rec, snap)
    assert snapshot.risk_level is None
    assert snapshot.risk_flags == []
    assert snapshot.evidence is None


# ---------------------------------------------------------------------------
# BacktestEngine.run dry-run
# ---------------------------------------------------------------------------


def test_dry_run_does_not_persist_anything(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))
    _make_results(session, rec, return_1d=Decimal("1.5"), return_5d=Decimal("3.0"))

    engine = BacktestEngine(session)
    summary = engine.run(strategy=TopGradeStrategy(), dry_run=True)

    assert summary.dry_run is True
    assert summary.backtest_run_id is None
    assert summary.evaluated_recommendation_count == 1
    assert summary.signal_count == 1
    assert summary.buy_count == 1
    # No DB writes
    assert BacktestRunRepository(session).list_recent() == []
    assert BacktestResultRepository(session).aggregate_by_run(0) == {}


def test_commit_persists_backtest_run_and_results(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    rec = _make_recommendation(session, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))
    _make_results(session, rec, return_1d=Decimal("1.5"), return_5d=Decimal("3.0"))

    engine = BacktestEngine(session)
    summary = engine.run(strategy=TopGradeStrategy(), dry_run=False, run_date=date(2026, 5, 6))
    session.commit()

    run_repo = BacktestRunRepository(session)
    result_repo = BacktestResultRepository(session)

    runs = run_repo.list_recent()
    assert len(runs) == 1
    assert runs[0].id == summary.backtest_run_id
    assert runs[0].status == STATUS_SUCCESS
    assert runs[0].buy_count == 1
    assert runs[0].signal_count == 1

    results = result_repo.list_by_run(runs[0].id)
    assert len(results) == 1
    assert results[0].symbol == "005930"
    assert results[0].signal_action == STRATEGY_ACTION_BUY
    assert results[0].grade == "A"
    assert results[0].return_1d == Decimal("1.5")


# ---------------------------------------------------------------------------
# Strategy-specific behavior
# ---------------------------------------------------------------------------


def test_top_grade_strategy_buys_pass_avoid(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    _make_recommendation(session, run, snap, rank=1, symbol="A", grade="A", total_score=Decimal("80"))
    _make_recommendation(session, run, snap, rank=2, symbol="B", grade="C", total_score=Decimal("55"))
    _make_recommendation(session, run, snap, rank=3, symbol="C", grade="D", total_score=Decimal("30"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.buy_count == 1
    assert summary.pass_count == 1
    assert summary.avoid_count == 1


def test_high_score_strategy_action_split(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    _make_recommendation(session, run, snap, rank=1, symbol="A", grade="B", total_score=Decimal("85"))  # BUY
    _make_recommendation(session, run, snap, rank=2, symbol="B", grade="B", total_score=Decimal("60"))  # PASS
    _make_recommendation(session, run, snap, rank=3, symbol="C", grade="B", total_score=Decimal("20"))  # AVOID

    summary = BacktestEngine(session).run(strategy=HighScoreStrategy(), dry_run=True)
    assert summary.buy_count == 1
    assert summary.pass_count == 1
    assert summary.avoid_count == 1


def test_multi_signal_strategy_full_evidence(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(
        session,
        date(2026, 5, 4),
        market_context={
            "risk_summary": {"level": "LOW", "flags": []},
            "earnings_evidence": {"surprise_type": "BEAT"},
            "news_evidence": {"positive_count": 3, "negative_count": 0},
        },
    )
    rec = _make_recommendation(
        session, run, snap, rank=1, symbol="005930",
        grade="A", total_score=Decimal("70"),
        fundamental_score=Decimal("65"), news_score=Decimal("55"),
    )
    _make_results(session, rec, return_1d=Decimal("1.5"), return_5d=Decimal("3.0"))

    summary = BacktestEngine(session).run(strategy=MultiSignalStrategy(), dry_run=True)
    assert summary.buy_count == 1
    assert summary.win_rate_5d == Decimal("1.0000")
    assert summary.avg_return_5d == Decimal("3.0000")


# ---------------------------------------------------------------------------
# Metrics calculation
# ---------------------------------------------------------------------------


def test_win_rate_and_avg_return_only_consider_buy_signals(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    a = _make_recommendation(session, run, snap, rank=1, symbol="A", grade="A", total_score=Decimal("80"))  # BUY
    b = _make_recommendation(session, run, snap, rank=2, symbol="B", grade="A", total_score=Decimal("80"))  # BUY
    c = _make_recommendation(session, run, snap, rank=3, symbol="C", grade="A", total_score=Decimal("80"))  # BUY
    # PASS row should NOT contribute to win_rate / avg_return
    p = _make_recommendation(session, run, snap, rank=4, symbol="P", grade="C", total_score=Decimal("50"))  # PASS

    _make_results(session, a, return_5d=Decimal("2.0"), return_1d=Decimal("1.0"))
    _make_results(session, b, return_5d=Decimal("4.0"), return_1d=Decimal("-0.5"))
    _make_results(session, c, return_5d=Decimal("-1.0"), return_1d=Decimal("0.5"))
    _make_results(session, p, return_5d=Decimal("-50.0"), return_1d=Decimal("-30.0"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    # 3 BUY + 1 PASS = 4 signals
    assert summary.signal_count == 4
    assert summary.buy_count == 3
    assert summary.pass_count == 1
    # win_rate_5d over 3 BUY rows: 2 wins (2.0, 4.0) / 3 = 0.6667
    assert summary.win_rate_5d == Decimal("0.6667")
    # avg_return_5d over 3 BUY rows: (2 + 4 + -1) / 3 = 1.6667
    assert summary.avg_return_5d == Decimal("1.6667")
    # win_rate_1d over 3 BUY rows: 2 wins (1.0, 0.5) / 3 = 0.6667
    assert summary.win_rate_1d == Decimal("0.6667")


def test_missing_horizon_returns_increment_missing_count(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    a = _make_recommendation(session, run, snap, rank=1, symbol="A", grade="A", total_score=Decimal("80"))
    b = _make_recommendation(session, run, snap, rank=2, symbol="B", grade="A", total_score=Decimal("80"))
    # a has 5d return; b has only 1d return
    _make_results(session, a, return_5d=Decimal("3.0"))
    _make_results(session, b, return_1d=Decimal("0.8"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.missing_result_count_per_horizon[5] == 1
    assert summary.missing_result_count_per_horizon[1] == 1
    assert summary.missing_result_count_per_horizon[3] == 2  # neither set
    assert summary.missing_result_count_per_horizon[20] == 2


def test_no_buy_signals_yields_none_metrics(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    _make_recommendation(session, run, snap, rank=1, symbol="A", grade="C", total_score=Decimal("50"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.buy_count == 0
    assert summary.win_rate_5d is None
    assert summary.avg_return_5d is None
    assert summary.max_drawdown is None


def test_max_drawdown_is_minimum_across_buy_rows(session):
    run = _make_run(session, date(2026, 5, 4))
    snap = _make_snapshot(session, date(2026, 5, 4))
    a = _make_recommendation(session, run, snap, rank=1, symbol="A", grade="A", total_score=Decimal("80"))
    b = _make_recommendation(session, run, snap, rank=2, symbol="B", grade="A", total_score=Decimal("80"))
    _make_results(session, a, return_5d=Decimal("3.0"), max_drawdown=Decimal("-1.5"))
    _make_results(session, b, return_5d=Decimal("1.0"), max_drawdown=Decimal("-4.0"))

    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    # min(-1.5, -4.0) = -4.0
    assert summary.max_drawdown == Decimal("-4.0000")


def test_summary_carries_buy_only_note(session):
    summary = BacktestEngine(session).run(strategy=TopGradeStrategy(), dry_run=True)
    assert summary.notes == BUY_ONLY_METRICS_NOTE


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------


def test_date_range_filter_excludes_outside_runs(session):
    run_a = _make_run(session, date(2026, 5, 1))
    run_b = _make_run(session, date(2026, 5, 4))
    run_c = _make_run(session, date(2026, 5, 10))
    snap = _make_snapshot(session, date(2026, 5, 4))
    _make_recommendation(session, run_a, snap, rank=1, symbol="A", grade="A", total_score=Decimal("80"))
    _make_recommendation(session, run_b, snap, rank=1, symbol="B", grade="A", total_score=Decimal("80"))
    _make_recommendation(session, run_c, snap, rank=1, symbol="C", grade="A", total_score=Decimal("80"))

    summary = BacktestEngine(session).run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 6),
        dry_run=True,
    )
    assert summary.signal_count == 1  # only run_b


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_dry_run_does_not_persist(tmp_path, monkeypatch):
    from scripts.run_backtest import run_backtest

    db_path = tmp_path / "backtest_cli_dry.sqlite"
    db_url = f"sqlite:///{db_path}"

    # Seed minimal data via direct session
    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    sess = factory()
    run = _make_run(sess, date(2026, 5, 4))
    snap = _make_snapshot(sess, date(2026, 5, 4))
    rec = _make_recommendation(sess, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))
    _make_results(sess, rec, return_5d=Decimal("3.0"))
    sess.commit()
    sess.close()

    summary = run_backtest(
        strategy_name="top_grade",
        commit=False,
        database_url=db_url,
    )
    assert summary.dry_run is True
    assert summary.buy_count == 1
    assert summary.backtest_run_id is None

    # Verify nothing landed in backtest_runs
    sess2 = factory()
    assert BacktestRunRepository(sess2).list_recent() == []
    sess2.close()


def test_cli_commit_persists_to_db(tmp_path):
    from scripts.run_backtest import run_backtest

    db_path = tmp_path / "backtest_cli_commit.sqlite"
    db_url = f"sqlite:///{db_path}"

    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    sess = factory()
    run = _make_run(sess, date(2026, 5, 4))
    snap = _make_snapshot(sess, date(2026, 5, 4))
    rec = _make_recommendation(sess, run, snap, rank=1, symbol="005930", grade="A", total_score=Decimal("80"))
    _make_results(sess, rec, return_5d=Decimal("3.0"))
    sess.commit()
    sess.close()

    summary = run_backtest(
        strategy_name="top_grade",
        commit=True,
        database_url=db_url,
    )
    assert summary.dry_run is False
    assert summary.buy_count == 1
    assert summary.backtest_run_id is not None

    sess2 = factory()
    runs = BacktestRunRepository(sess2).list_recent()
    assert len(runs) == 1
    assert runs[0].status == STATUS_SUCCESS
    results = BacktestResultRepository(sess2).list_by_run(runs[0].id)
    assert len(results) == 1
    sess2.close()


def test_cli_rejects_unknown_strategy():
    from app.strategy.registry import UnknownStrategyError, get_strategy

    with pytest.raises(UnknownStrategyError):
        get_strategy("does_not_exist")


def test_cli_main_smoke(tmp_path, capsys):
    from scripts.run_backtest import main

    db_path = tmp_path / "backtest_cli_main.sqlite"
    db_url = f"sqlite:///{db_path}"

    # Make sure the schema exists so dry-run with empty data still works.
    from sqlalchemy import create_engine

    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    engine.dispose()

    rc = main(["--strategy", "top_grade", "--db-url", db_url])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "DRY-RUN" in captured
    assert "strategy_name" in captured
