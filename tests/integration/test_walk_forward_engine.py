"""Integration tests for v0.12 Phase B WalkForwardBacktestEngine.

Covers:
* generate_folds() pure-logic tests (no DB)
* Engine dry-run: fold count, date assignment, gap, no DB writes
* Engine commit: single BacktestRun, summary_json["walk_forward_folds"], config_json
* Aggregate OOS metrics computation
* Edge case: date range too small (zero folds)
* CLI --walk-forward flag and date validation
* WalkForwardSummary / FoldResult serialization
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backtest.walk_forward import (
    FoldResult,
    WalkForwardBacktestEngine,
    WalkForwardSummary,
    generate_folds,
)
from app.data.repositories import BacktestRunRepository
from app.data.repositories.backtest_runs import STATUS_SUCCESS
from app.db import Base
from app.db.models import (
    DataSnapshot,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
)
from app.db.session import create_db_engine, create_session_factory
from app.strategy.rule_based import TopGradeStrategy


# ---------------------------------------------------------------------------
# Session fixture
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
# DB helpers
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


def _make_recommendation(session, run: RecommendationRun, snapshot: DataSnapshot) -> Recommendation:
    rec = Recommendation(
        run_id=run.run_id,
        rank=1,
        market="KOSPI",
        symbol="005930",
        name="Samsung",
        grade="A",
        total_score=Decimal("85"),
        technical_score=Decimal("80"),
        news_score=Decimal("70"),
        supply_score=Decimal("60"),
        fundamental_score=Decimal("75"),
        ai_score=Decimal("65"),
        risk_score=Decimal("0"),
        snapshot_id=snapshot.snapshot_id,
    )
    session.add(rec)
    session.flush()
    return rec


def _make_results(session, rec: Recommendation, *, return_5d: Decimal | None = Decimal("0.05")) -> None:
    for days_after in (1, 3, 5, 20):
        session.add(
            RecommendationResult(
                recommendation_id=rec.id,
                result_date=rec.run.run_date,
                days_after=days_after,
                close_return=return_5d,
                max_drawdown=Decimal("-0.02") if days_after == 5 else None,
                result_status="CLOSED" if days_after == 5 else None,
            ),
        )
    session.flush()


def _seed_db(session) -> None:
    """Seed one recommendation per date into DB for walk-forward tests.

    Windows used: start=2026-01-01, end=2026-04-30, train=30, validate=30.
    Fold 0: IS Jan01..Jan30, OOS Jan31..Mar01.
    Fold 1: IS Mar02..Mar31, OOS Apr01..Apr30.
    """
    for run_date in (
        date(2026, 1, 15),   # fold 0 IS
        date(2026, 2, 15),   # fold 0 OOS
        date(2026, 3, 15),   # fold 1 IS
        date(2026, 4, 15),   # fold 1 OOS
    ):
        run = _make_run(session, run_date)
        snap = _make_snapshot(session, run_date)
        rec = _make_recommendation(session, run, snap)
        _make_results(session, rec, return_5d=Decimal("0.05"))


# ---------------------------------------------------------------------------
# 1-5: generate_folds pure-logic tests (no DB)
# ---------------------------------------------------------------------------


def test_generate_folds_basic():
    """Three folds expected with 30/30 windows over a Jan-Apr range (120 days).

    Fold 0: IS Jan01..Jan30, OOS Jan31..Mar01
    Fold 1: IS Jan31..Mar01, OOS Mar02..Mar31
    Fold 2: IS Mar02..Mar31, OOS Apr01..Apr30
    Fold 3 would need OOS ending May30 which exceeds Apr30 → stops.
    """
    folds = generate_folds(
        date(2026, 1, 1),
        date(2026, 4, 30),
        train_window_days=30,
        validate_window_days=30,
        gap_days=0,
    )
    assert len(folds) == 3
    idx, ts, te, vs, ve = folds[0]
    assert idx == 0
    assert ts == date(2026, 1, 1)
    assert te == date(2026, 1, 30)
    assert vs == date(2026, 1, 31)
    assert ve == date(2026, 3, 1)


def test_generate_folds_no_room():
    """Range too small: validate_end would exceed end_date immediately."""
    folds = generate_folds(
        date(2026, 1, 1),
        date(2026, 1, 10),
        train_window_days=30,
        validate_window_days=20,
        gap_days=0,
    )
    assert folds == []


def test_generate_folds_with_gap():
    """Gap days push validate_start forward."""
    folds = generate_folds(
        date(2026, 1, 1),
        date(2026, 6, 30),
        train_window_days=30,
        validate_window_days=30,
        gap_days=5,
    )
    assert len(folds) >= 1
    _, _, train_end, validate_start, _ = folds[0]
    # validate_start should be train_end + gap_days + 1
    assert validate_start == train_end + __import__("datetime").timedelta(days=6)


def test_generate_folds_oos_windows_do_not_overlap():
    """Consecutive OOS windows abut: fold[n+1].validate_start == fold[n].validate_end + 1d."""
    from datetime import timedelta

    folds = generate_folds(
        date(2026, 1, 1),
        date(2026, 12, 31),
        train_window_days=60,
        validate_window_days=30,
        gap_days=0,
    )
    assert len(folds) >= 2
    for i in range(len(folds) - 1):
        _, _, _, _, ve_cur = folds[i]
        _, _, _, vs_next, _ = folds[i + 1]
        assert vs_next == ve_cur + timedelta(days=1), (
            f"fold {i} OOS end={ve_cur}, fold {i+1} OOS start={vs_next}"
        )


def test_generate_folds_exact_boundary():
    """validate_end == end_date is a valid fold (inclusive boundary)."""
    # train=5 days + validate=5 days → validate_end = Jan 1 + 9 = Jan 10
    folds = generate_folds(
        date(2026, 1, 1),
        date(2026, 1, 10),
        train_window_days=5,
        validate_window_days=5,
        gap_days=0,
    )
    assert len(folds) == 1
    _, _, _, _, ve = folds[0]
    assert ve == date(2026, 1, 10)


# ---------------------------------------------------------------------------
# 6-9: Engine dry-run tests
# ---------------------------------------------------------------------------


def test_dry_run_no_db_writes(session):
    """Dry run must leave backtest_runs table empty."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    assert summary.dry_run is True
    assert summary.backtest_run_id is None
    repo = BacktestRunRepository(session)
    assert repo.list_recent() == []


def test_dry_run_fold_count_and_dates(session):
    """Fold dates match generate_folds() output."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    expected = generate_folds(date(2026, 1, 1), date(2026, 4, 30), 30, 30, 0)
    assert summary.total_folds == len(expected)
    assert len(summary.fold_results) == len(expected)
    for fold, (_, ts, te, vs, ve) in zip(summary.fold_results, expected):
        assert fold.train_start == ts
        assert fold.train_end == te
        assert fold.validate_start == vs
        assert fold.validate_end == ve


def test_fold_is_oos_gap_reflected(session):
    """gap_days is stored in each FoldResult.is_oos_gap."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
        gap_days=7,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        dry_run=True,
    )
    for fold in summary.fold_results:
        assert fold.is_oos_gap == 7


def test_zero_folds_when_range_too_small(session):
    """Engine returns WalkForwardSummary with total_folds=0 for tiny date range."""
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=60,
        validate_window_days=20,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 15),
        dry_run=True,
    )
    assert summary.total_folds == 0
    assert summary.fold_results == []
    assert summary.avg_oos_win_rate_5d is None
    assert summary.avg_oos_avg_return_5d is None


# ---------------------------------------------------------------------------
# 10-12: Engine commit tests
# ---------------------------------------------------------------------------


def test_commit_persists_single_backtest_run(session):
    """Commit writes exactly one BacktestRun row regardless of fold count."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=False,
        run_date=date(2026, 5, 1),
    )
    session.commit()

    assert summary.backtest_run_id is not None
    repo = BacktestRunRepository(session)
    runs = repo.list_recent()
    assert len(runs) == 1
    run = runs[0]
    assert run.status == STATUS_SUCCESS
    assert run.start_date == date(2026, 1, 1)
    assert run.end_date == date(2026, 4, 30)


def test_commit_summary_json_has_walk_forward_folds(session):
    """summary_json must contain walk_forward_folds with one entry per fold."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=False,
        run_date=date(2026, 5, 1),
    )
    session.commit()

    repo = BacktestRunRepository(session)
    run = repo.get_by_id(summary.backtest_run_id)
    assert run is not None
    assert run.summary_json is not None
    assert run.summary_json["mode"] == "walk_forward"
    folds_data = run.summary_json["walk_forward_folds"]
    assert isinstance(folds_data, list)
    assert len(folds_data) == summary.total_folds
    for entry in folds_data:
        assert "fold_index" in entry
        assert "train_start" in entry
        assert "validate_start" in entry
        assert "oos_buy_count" in entry


def test_commit_config_json_mode(session):
    """config_json["mode"] must be "walk_forward" and contain window params."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
        gap_days=3,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=False,
        run_date=date(2026, 5, 1),
    )
    session.commit()

    repo = BacktestRunRepository(session)
    run = repo.get_by_id(summary.backtest_run_id)
    assert run.config_json["mode"] == "walk_forward"
    assert run.config_json["train_window_days"] == 30
    assert run.config_json["validate_window_days"] == 30
    assert run.config_json["gap_days"] == 3


# ---------------------------------------------------------------------------
# 13: Aggregate OOS metrics
# ---------------------------------------------------------------------------


def test_avg_oos_metrics_aggregated(session):
    """avg_oos_win_rate_5d is the mean of per-fold oos win_rate_5d values."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    # Collect per-fold OOS win_rate_5d values that are not None
    wr_values = [
        f.oos_metrics.win_rate_5d
        for f in summary.fold_results
        if f.oos_metrics.win_rate_5d is not None
    ]
    if wr_values:
        expected_avg = (sum(wr_values) / Decimal(len(wr_values))).quantize(Decimal("0.0001"))
        assert summary.avg_oos_win_rate_5d == expected_avg
    else:
        assert summary.avg_oos_win_rate_5d is None


# ---------------------------------------------------------------------------
# 14: CLI tests
# ---------------------------------------------------------------------------


def test_cli_walk_forward_requires_both_dates():
    """--walk-forward without --from-date or --to-date must return exit code 2."""
    from scripts.run_backtest import main

    # Missing --from-date
    code = main(["--strategy", "top_grade", "--walk-forward", "--to-date", "2026-04-30"])
    assert code == 2

    # Missing --to-date
    code = main(["--strategy", "top_grade", "--walk-forward", "--from-date", "2026-01-01"])
    assert code == 2


def test_cli_walk_forward_dry_run_exits_zero(session, tmp_path):
    """--walk-forward with valid dates runs without error (exit 0)."""
    import os

    from scripts.run_backtest import main

    db_path = str(tmp_path / "test.db")
    db_url = f"sqlite:///{db_path}"

    code = main([
        "--strategy", "top_grade",
        "--walk-forward",
        "--from-date", "2026-01-01",
        "--to-date", "2026-04-30",
        "--train-window-days", "30",
        "--validate-window-days", "30",
        "--db-url", db_url,
    ])
    assert code == 0


# ---------------------------------------------------------------------------
# 15: Serialization
# ---------------------------------------------------------------------------


def test_walk_forward_summary_as_dict(session):
    """WalkForwardSummary.as_dict() includes all required top-level keys."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    d = summary.as_dict()
    required_keys = {
        "strategy_name",
        "strategy_version",
        "run_date",
        "start_date",
        "end_date",
        "train_window_days",
        "validate_window_days",
        "gap_days",
        "dry_run",
        "backtest_run_id",
        "total_folds",
        "avg_oos_win_rate_5d",
        "avg_oos_avg_return_5d",
        "fold_results",
    }
    assert required_keys <= d.keys()
    assert isinstance(d["fold_results"], list)


def test_fold_result_as_dict(session):
    """FoldResult.as_dict() contains IS and OOS metric keys."""
    _seed_db(session)
    engine = WalkForwardBacktestEngine(
        session,
        train_window_days=30,
        validate_window_days=30,
    )
    summary = engine.run(
        strategy=TopGradeStrategy(),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    if not summary.fold_results:
        pytest.skip("no folds generated — seed data may need adjustment")
    d = summary.fold_results[0].as_dict()
    for key in (
        "fold_index",
        "train_start",
        "train_end",
        "validate_start",
        "validate_end",
        "is_oos_gap",
        "is_signal_count",
        "is_buy_count",
        "is_win_rate_5d",
        "is_avg_return_5d",
        "oos_signal_count",
        "oos_buy_count",
        "oos_win_rate_5d",
        "oos_avg_return_5d",
    ):
        assert key in d, f"missing key: {key}"
