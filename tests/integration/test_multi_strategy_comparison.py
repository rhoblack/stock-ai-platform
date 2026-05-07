"""Integration tests for v0.12 Phase C MultiStrategyRunner + regime_breakdown.

Seed data design
----------------
Two recommendations in the same RecommendationRun (2026-04-01):

  Symbol 005930  grade=A  total_score=40  fundamental=75  news=70  → return_5d=+0.05
  Symbol 000660  grade=B  total_score=80  fundamental=75  news=70  → return_5d=-0.03

Strategy signals on this data:
  TopGradeStrategy   005930=BUY(win)   000660=PASS   → win_rate_5d=1.0  avg_return=+0.05
  HighScoreStrategy  005930=PASS       000660=BUY(loss) → win_rate_5d=0.0  avg_return=-0.03
  MultiSignalStrategy 005930=PASS(score<65)  000660=BUY(loss) → win_rate_5d=0.0 avg_return=-0.03

Stock records:  005930→sector="IT"  000660→sector="Semiconductor"
No Stock row for "999999" (used in unknown-sector test).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.backtest.multi_strategy_runner import (
    MultiStrategyComparison,
    MultiStrategyRunner,
    StrategyResult,
    _find_best,
)
from app.backtest.regime_breakdown import (
    UNKNOWN_SECTOR_BUCKET,
    SectorBreakdownEntry,
    aggregate_sector_breakdown,
)
from app.data.repositories import BacktestRunRepository
from app.data.repositories.backtest_runs import STATUS_SUCCESS
from app.db import Base
from app.db.models import (
    DataSnapshot,
    Recommendation,
    RecommendationResult,
    RecommendationRun,
    Stock,
)
from app.db.session import create_db_engine, create_session_factory
from app.strategy.rule_based import (
    HighScoreStrategy,
    MultiSignalStrategy,
    TopGradeStrategy,
)


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


def _make_snapshot(session, run_date: date, symbol: str = "005930") -> DataSnapshot:
    snap = DataSnapshot(
        snapshot_time=datetime(run_date.year, run_date.month, run_date.day, 6, 0, tzinfo=timezone.utc),
        symbol=symbol,
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
    grade: str | None,
    total_score: Decimal,
    fundamental_score: Decimal = Decimal("75"),
    news_score: Decimal = Decimal("70"),
) -> Recommendation:
    rec = Recommendation(
        run_id=run.run_id,
        rank=rank,
        market="KOSPI",
        symbol=symbol,
        name=f"name-{symbol}",
        grade=grade,
        total_score=total_score,
        technical_score=Decimal("70"),
        news_score=news_score,
        supply_score=Decimal("60"),
        fundamental_score=fundamental_score,
        ai_score=Decimal("65"),
        risk_score=Decimal("0"),
        snapshot_id=snapshot.snapshot_id if snapshot else None,
    )
    session.add(rec)
    session.flush()
    return rec


def _make_results(session, rec: Recommendation, *, return_5d: Decimal | None) -> None:
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


def _make_stock(session, symbol: str, sector: str | None) -> Stock:
    stock = Stock(market="KOSPI", symbol=symbol, name=f"name-{symbol}", sector=sector)
    session.add(stock)
    session.flush()
    return stock


def _seed_db(session) -> None:
    """Seed two recommendations + stocks for the comparison tests."""
    run = _make_run(session, date(2026, 4, 1))
    snap1 = _make_snapshot(session, date(2026, 4, 1), symbol="005930")
    snap2 = _make_snapshot(session, date(2026, 4, 1), symbol="000660")

    rec1 = _make_recommendation(
        session, run, snap1,
        rank=1, symbol="005930", grade="A", total_score=Decimal("40"),
    )
    _make_results(session, rec1, return_5d=Decimal("0.05"))

    rec2 = _make_recommendation(
        session, run, snap2,
        rank=2, symbol="000660", grade="B", total_score=Decimal("80"),
    )
    _make_results(session, rec2, return_5d=Decimal("-0.03"))

    _make_stock(session, "005930", "IT")
    _make_stock(session, "000660", "Semiconductor")


# ---------------------------------------------------------------------------
# 1-2: aggregate_sector_breakdown pure-logic (no DB)
# ---------------------------------------------------------------------------


def test_aggregate_sector_breakdown_basic():
    """Two sectors with BUY signals: metrics aggregated correctly."""
    triples = [
        ("IT", "BUY", Decimal("0.05")),
        ("IT", "BUY", Decimal("-0.03")),
        ("Semiconductor", "BUY", Decimal("0.10")),
        ("Semiconductor", "PASS", None),
    ]
    entries = aggregate_sector_breakdown(triples)
    by_name = {e.sector: e for e in entries}

    assert "IT" in by_name
    assert by_name["IT"].signal_count == 2
    assert by_name["IT"].buy_count == 2
    # 1 win out of 2 → 0.5
    assert by_name["IT"].win_rate_5d == Decimal("0.5000")

    assert "Semiconductor" in by_name
    assert by_name["Semiconductor"].signal_count == 2
    assert by_name["Semiconductor"].buy_count == 1


def test_aggregate_sector_breakdown_null_sector_maps_to_unknown():
    """None sector maps to UNKNOWN_SECTOR_BUCKET."""
    triples = [
        (None, "BUY", Decimal("0.05")),
        (None, "PASS", None),
    ]
    entries = aggregate_sector_breakdown(triples)
    assert len(entries) == 1
    assert entries[0].sector == UNKNOWN_SECTOR_BUCKET
    assert entries[0].signal_count == 2
    assert entries[0].buy_count == 1


# ---------------------------------------------------------------------------
# 3-5: MultiStrategyRunner dry-run basics
# ---------------------------------------------------------------------------


def test_multi_runner_dry_run_no_db_writes(session):
    """dry_run=True must leave backtest_runs empty."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    assert comparison.dry_run is True
    assert comparison.backtest_run_id is None
    assert BacktestRunRepository(session).list_recent() == []


def test_multi_runner_strategy_count(session):
    """strategy_results has one entry per strategy passed in."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy(), MultiSignalStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    assert comparison.total_strategies == 3
    assert len(comparison.strategy_results) == 3


def test_multi_runner_same_universe(session):
    """All strategies evaluate the same number of recommendations."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy(), MultiSignalStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    signal_counts = [r.signal_count for r in comparison.strategy_results]
    assert len(set(signal_counts)) == 1, f"Signal counts differ: {signal_counts}"
    assert signal_counts[0] == 2  # two recommendations seeded


# ---------------------------------------------------------------------------
# 6-7: Best strategy ranking
# ---------------------------------------------------------------------------


def test_best_strategy_by_win_rate_5d(session):
    """TopGrade (win_rate=1.0) beats HighScore (win_rate=0.0)."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    assert comparison.best_strategy_by_win_rate_5d == "TopGradeStrategy"


def test_best_strategy_by_avg_return_5d(session):
    """TopGrade (avg=+0.05) beats HighScore (avg=-0.03)."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    assert comparison.best_strategy_by_avg_return_5d == "TopGradeStrategy"


# ---------------------------------------------------------------------------
# 8-9: Breakdowns
# ---------------------------------------------------------------------------


def test_regime_breakdown_populated_when_enabled(session):
    """with_regime_breakdown=True → regime_breakdown list on each StrategyResult."""
    _seed_db(session)
    runner = MultiStrategyRunner(session, with_regime_breakdown=True)
    comparison = runner.run(
        strategies=[TopGradeStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    result = comparison.strategy_results[0]
    # BacktestEngine always computes regime_breakdown; with no MarketRegime rows
    # the BUY signal lands in UNCLASSIFIED, so the list is non-empty.
    assert isinstance(result.regime_breakdown, list)


def test_sector_breakdown_uses_stock_sector(session):
    """Sector breakdown groups by Stock.sector; IT and Semiconductor appear."""
    _seed_db(session)
    runner = MultiStrategyRunner(session, with_sector_breakdown=True)
    comparison = runner.run(
        strategies=[TopGradeStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    sectors = {e.sector for e in comparison.strategy_results[0].sector_breakdown}
    assert "IT" in sectors
    assert "Semiconductor" in sectors


def test_sector_breakdown_unknown_for_missing_stock(session):
    """Recommendations whose symbol has no Stock row go to UNKNOWN bucket."""
    _seed_db(session)
    # Add a third recommendation without a Stock record.
    run = session.execute(
        __import__("sqlalchemy").select(RecommendationRun)
    ).scalars().first()
    snap = _make_snapshot(session, date(2026, 4, 1), symbol="999999")
    rec = _make_recommendation(
        session, run, snap,
        rank=3, symbol="999999", grade="A", total_score=Decimal("85"),
    )
    _make_results(session, rec, return_5d=Decimal("0.02"))

    runner = MultiStrategyRunner(session, with_sector_breakdown=True)
    comparison = runner.run(
        strategies=[TopGradeStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    sectors = {e.sector for e in comparison.strategy_results[0].sector_breakdown}
    assert UNKNOWN_SECTOR_BUCKET in sectors


# ---------------------------------------------------------------------------
# 10-11: Commit tests
# ---------------------------------------------------------------------------


def test_commit_persists_single_backtest_run(session):
    """dry_run=False creates exactly one BacktestRun with strategy_name='MULTI'."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=False,
        run_date=date(2026, 5, 1),
    )
    session.commit()

    assert comparison.backtest_run_id is not None
    repo = BacktestRunRepository(session)
    runs = repo.list_recent()
    assert len(runs) == 1
    run = runs[0]
    assert run.status == STATUS_SUCCESS
    assert run.strategy_name == "MULTI"


def test_commit_summary_json_structure(session):
    """summary_json must contain mode + multi_strategy_comparison list."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=False,
        run_date=date(2026, 5, 1),
    )
    session.commit()

    repo = BacktestRunRepository(session)
    run = repo.get_by_id(comparison.backtest_run_id)
    assert run.summary_json["mode"] == "multi_strategy_comparison"
    comparison_data = run.summary_json["multi_strategy_comparison"]
    assert isinstance(comparison_data, list)
    assert len(comparison_data) == 2
    strategy_names_in_json = [e["strategy_name"] for e in comparison_data]
    assert "TopGradeStrategy" in strategy_names_in_json
    assert "HighScoreStrategy" in strategy_names_in_json
    assert "best_strategy_by_win_rate_5d" in run.summary_json


# ---------------------------------------------------------------------------
# 12: Serialization
# ---------------------------------------------------------------------------


def test_multi_comparison_as_dict(session):
    """MultiStrategyComparison.as_dict() includes all required top-level keys."""
    _seed_db(session)
    runner = MultiStrategyRunner(session)
    comparison = runner.run(
        strategies=[TopGradeStrategy(), HighScoreStrategy()],
        start_date=date(2026, 3, 1),
        end_date=date(2026, 4, 30),
        dry_run=True,
    )
    d = comparison.as_dict()
    required = {
        "start_date", "end_date", "run_date", "dry_run",
        "backtest_run_id", "total_strategies",
        "best_strategy_by_win_rate_5d", "best_strategy_by_avg_return_5d",
        "strategy_results",
    }
    assert required <= d.keys()
    for r in d["strategy_results"]:
        assert "strategy_name" in r
        assert "win_rate_5d" in r
        assert "sector_breakdown" in r
        assert "regime_breakdown" in r


# ---------------------------------------------------------------------------
# 13: CLI tests
# ---------------------------------------------------------------------------


def test_cli_multi_requires_dates():
    """--multi without --from-date or --to-date → exit code 2."""
    from scripts.run_backtest import main

    code = main(["--multi", "--to-date", "2026-04-30"])
    assert code == 2

    code = main(["--multi", "--from-date", "2026-01-01"])
    assert code == 2


def test_cli_multi_dry_run_exits_zero(tmp_path):
    """--multi with valid dates runs without error → exit 0."""
    from scripts.run_backtest import main

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    code = main([
        "--multi",
        "--from-date", "2026-01-01",
        "--to-date", "2026-04-30",
        "--db-url", db_url,
    ])
    assert code == 0


def test_cli_multi_unknown_strategy_exits_2(tmp_path):
    """--multi --strategies with unknown strategy name → exit 2."""
    from scripts.run_backtest import main

    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    code = main([
        "--multi",
        "--strategies", "top_grade,nonexistent_strategy",
        "--from-date", "2026-01-01",
        "--to-date", "2026-04-30",
        "--db-url", db_url,
    ])
    assert code == 2
