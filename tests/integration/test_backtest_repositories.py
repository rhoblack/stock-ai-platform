"""Integration tests for v0.7 Phase B BacktestRun + BacktestResult repositories.

Scope:
  * ORM metadata + table creation (sqlite in-memory)
  * BacktestRunRepository CRUD + mark_finished + mark_failed
  * BacktestResultRepository create + bulk_insert + list_by_run + list_by_symbol
    + aggregate_by_run + aggregate_by_signal_action
  * Unique(backtest_run_id, recommendation_id) constraint
  * cascade delete from BacktestRun → BacktestResult

Out of scope:
  * BacktestEngine
  * CLI
  * API / frontend
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.data.repositories import (
    BacktestResultRepository,
    BacktestRunRepository,
)
from app.data.repositories.backtest_runs import (
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from app.db import Base
from app.db.models import (
    BacktestResult,
    BacktestRun,
    Recommendation,
    RecommendationRun,
)
from app.db.session import create_db_engine, create_session_factory
from app.strategy.interfaces import (
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
)


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    # Enable FK enforcement so ondelete=CASCADE works under sqlite.
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


def _seed_recommendation_run(session) -> RecommendationRun:
    from datetime import datetime as _dt, timezone as _tz

    run = RecommendationRun(
        run_date=date(2026, 5, 4),
        started_at=_dt(2026, 5, 4, 6, 0, tzinfo=_tz.utc),
        status="SUCCESS",
        telegram_sent=False,
    )
    session.add(run)
    session.flush()
    return run


def _seed_recommendation(session, run: RecommendationRun, symbol: str, rank: int) -> Recommendation:
    rec = Recommendation(
        run_id=run.run_id,
        rank=rank,
        market="KOSPI",
        symbol=symbol,
        name=f"name-{symbol}",
        grade="A",
        total_score=Decimal("80"),
    )
    session.add(rec)
    session.flush()
    return rec


# ---------------------------------------------------------------------------
# ORM metadata
# ---------------------------------------------------------------------------


def test_backtest_runs_table_exists_with_expected_columns(session):
    inspector = inspect(session.get_bind())
    assert "backtest_runs" in inspector.get_table_names()
    columns = {col["name"] for col in inspector.get_columns("backtest_runs")}
    expected = {
        "id",
        "strategy_name",
        "strategy_version",
        "run_date",
        "start_date",
        "end_date",
        "signal_count",
        "buy_count",
        "avoid_count",
        "pass_count",
        "win_rate_1d",
        "win_rate_3d",
        "win_rate_5d",
        "win_rate_20d",
        "avg_return_1d",
        "avg_return_3d",
        "avg_return_5d",
        "avg_return_20d",
        "max_drawdown",
        "status",
        "error_message",
        "config_json",
        "summary_json",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns)


def test_backtest_results_table_exists_with_expected_columns(session):
    inspector = inspect(session.get_bind())
    assert "backtest_results" in inspector.get_table_names()
    columns = {col["name"] for col in inspector.get_columns("backtest_results")}
    expected = {
        "id",
        "backtest_run_id",
        "symbol",
        "recommendation_id",
        "recommendation_result_id",
        "signal_action",
        "confidence",
        "reason",
        "grade",
        "total_score",
        "return_1d",
        "return_3d",
        "return_5d",
        "return_20d",
        "max_drawdown",
        "result_status",
        "evidence_json",
        "created_at",
    }
    assert expected.issubset(columns)


# ---------------------------------------------------------------------------
# BacktestRunRepository
# ---------------------------------------------------------------------------


def test_create_backtest_run_defaults(session):
    repo = BacktestRunRepository(session)
    run = repo.create(
        strategy_name="top_grade",
        strategy_version="v1.0.0",
        run_date=date(2026, 5, 6),
    )
    assert run.id is not None
    assert run.status == STATUS_DRY_RUN
    assert run.signal_count == 0
    assert run.buy_count == 0
    assert run.avoid_count == 0
    assert run.pass_count == 0
    assert run.config_json is None


def test_get_by_id_returns_existing_run(session):
    repo = BacktestRunRepository(session)
    created = repo.create(
        strategy_name="top_grade",
        strategy_version="v1.0.0",
        run_date=date(2026, 5, 6),
    )
    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_by_id_returns_none_for_missing(session):
    repo = BacktestRunRepository(session)
    assert repo.get_by_id(999) is None


def test_list_recent_orders_by_run_date_desc(session):
    repo = BacktestRunRepository(session)
    a = repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 1))
    b = repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 5))
    c = repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 3))
    rows = repo.list_recent(limit=10)
    assert [r.id for r in rows] == [b.id, c.id, a.id]


def test_list_by_strategy_filters(session):
    repo = BacktestRunRepository(session)
    repo.create(strategy_name="top_grade", strategy_version="v1", run_date=date(2026, 5, 1))
    repo.create(strategy_name="high_score", strategy_version="v1", run_date=date(2026, 5, 2))
    repo.create(strategy_name="top_grade", strategy_version="v1", run_date=date(2026, 5, 3))
    rows = repo.list_by_strategy("top_grade")
    assert len(rows) == 2
    assert all(r.strategy_name == "top_grade" for r in rows)


def test_mark_finished_sets_metrics_and_status(session):
    repo = BacktestRunRepository(session)
    run = repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo.mark_finished(
        run,
        signal_count=10,
        buy_count=3,
        avoid_count=2,
        pass_count=5,
        win_rate_1d=Decimal("0.6667"),
        win_rate_3d=None,
        win_rate_5d=Decimal("0.3333"),
        win_rate_20d=None,
        avg_return_1d=Decimal("1.5"),
        avg_return_3d=None,
        avg_return_5d=Decimal("2.5"),
        avg_return_20d=None,
        max_drawdown=Decimal("-5.0"),
        summary_json={"notes": "buy-only"},
    )
    assert run.status == STATUS_SUCCESS
    assert run.signal_count == 10
    assert run.buy_count == 3
    assert run.win_rate_1d == Decimal("0.6667")
    assert run.win_rate_3d is None
    assert run.summary_json == {"notes": "buy-only"}


def test_mark_failed_records_error(session):
    repo = BacktestRunRepository(session)
    run = repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo.mark_failed(run, error_message="boom")
    assert run.status == STATUS_FAILED
    assert run.error_message == "boom"


# ---------------------------------------------------------------------------
# BacktestResultRepository
# ---------------------------------------------------------------------------


def test_create_backtest_result_minimum(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    result = repo.create(
        backtest_run_id=run.id,
        symbol="005930",
        signal_action=STRATEGY_ACTION_BUY,
        confidence=Decimal("0.7"),
    )
    assert result.id is not None
    assert result.signal_action == STRATEGY_ACTION_BUY


def test_bulk_insert_returns_added_rows(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    rows = [
        BacktestResult(
            backtest_run_id=run.id,
            symbol=f"{i:06d}",
            signal_action=STRATEGY_ACTION_PASS,
        )
        for i in range(3)
    ]
    inserted = repo.bulk_insert(rows)
    assert len(inserted) == 3
    assert all(r.id is not None for r in inserted)


def test_bulk_insert_empty_is_noop(session):
    repo = BacktestResultRepository(session)
    assert list(repo.bulk_insert([])) == []


def test_list_by_run_orders_by_id(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(backtest_run_id=run.id, symbol="005930", signal_action=STRATEGY_ACTION_BUY)
    repo.create(backtest_run_id=run.id, symbol="000660", signal_action=STRATEGY_ACTION_PASS)
    repo.create(backtest_run_id=run.id, symbol="035420", signal_action=STRATEGY_ACTION_AVOID)
    rows = repo.list_by_run(run.id)
    assert [r.symbol for r in rows] == ["005930", "000660", "035420"]


def test_list_by_symbol_filters(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(backtest_run_id=run.id, symbol="005930", signal_action=STRATEGY_ACTION_BUY)
    repo.create(backtest_run_id=run.id, symbol="000660", signal_action=STRATEGY_ACTION_PASS)
    rows = repo.list_by_symbol("005930")
    assert len(rows) == 1
    assert rows[0].symbol == "005930"


def test_aggregate_by_run_groups_by_action(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(backtest_run_id=run.id, symbol="A", signal_action=STRATEGY_ACTION_BUY)
    repo.create(backtest_run_id=run.id, symbol="B", signal_action=STRATEGY_ACTION_BUY)
    repo.create(backtest_run_id=run.id, symbol="C", signal_action=STRATEGY_ACTION_PASS)
    repo.create(backtest_run_id=run.id, symbol="D", signal_action=STRATEGY_ACTION_AVOID)
    counts = repo.aggregate_by_run(run.id)
    assert counts == {
        STRATEGY_ACTION_BUY: 2,
        STRATEGY_ACTION_PASS: 1,
        STRATEGY_ACTION_AVOID: 1,
    }


def test_aggregate_by_signal_action_returns_rows(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(backtest_run_id=run.id, symbol="005930", signal_action=STRATEGY_ACTION_BUY)
    repo.create(backtest_run_id=run.id, symbol="000660", signal_action=STRATEGY_ACTION_BUY)
    rows = repo.aggregate_by_signal_action(STRATEGY_ACTION_BUY)
    assert len(rows) == 2
    assert all(r.signal_action == STRATEGY_ACTION_BUY for r in rows)


# ---------------------------------------------------------------------------
# Unique constraint + cascade
# ---------------------------------------------------------------------------


def test_unique_backtest_run_recommendation_pair(session):
    run_seed = _seed_recommendation_run(session)
    rec = _seed_recommendation(session, run_seed, "005930", rank=1)
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(
        backtest_run_id=run.id,
        symbol=rec.symbol,
        signal_action=STRATEGY_ACTION_BUY,
        recommendation_id=rec.id,
    )
    # The second insert with the same (run_id, recommendation_id) pair must
    # raise; repo.create flushes immediately, so the error surfaces here.
    with pytest.raises(IntegrityError):
        repo.create(
            backtest_run_id=run.id,
            symbol="002000",
            signal_action=STRATEGY_ACTION_BUY,
            recommendation_id=rec.id,
        )


def test_unique_constraint_allows_null_recommendation_id_duplicates(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    repo = BacktestResultRepository(session)
    repo.create(
        backtest_run_id=run.id,
        symbol="005930",
        signal_action=STRATEGY_ACTION_PASS,
        recommendation_id=None,
    )
    repo.create(
        backtest_run_id=run.id,
        symbol="000660",
        signal_action=STRATEGY_ACTION_PASS,
        recommendation_id=None,
    )
    rows = repo.list_by_run(run.id)
    assert len(rows) == 2


def test_cascade_delete_removes_results(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    result_repo = BacktestResultRepository(session)
    result_repo.create(
        backtest_run_id=run.id,
        symbol="005930",
        signal_action=STRATEGY_ACTION_BUY,
    )
    session.commit()

    session.delete(run)
    session.commit()

    remaining = session.execute(select(BacktestResult)).scalars().all()
    assert remaining == []


def test_run_results_relationship_loads_children(session):
    run_repo = BacktestRunRepository(session)
    run = run_repo.create(strategy_name="x", strategy_version="v1", run_date=date(2026, 5, 6))
    result_repo = BacktestResultRepository(session)
    result_repo.create(
        backtest_run_id=run.id,
        symbol="005930",
        signal_action=STRATEGY_ACTION_BUY,
    )
    session.flush()
    fetched = run_repo.get_by_id(run.id)
    assert fetched is not None
    assert len(fetched.results) == 1
    assert fetched.results[0].symbol == "005930"
