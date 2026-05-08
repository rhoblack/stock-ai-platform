"""Integration tests for v0.14 Phase D paper trading scheduler jobs.

Covers:
  * ``execute_paper_orders`` — SKIPPED when paper_trading_enabled=False
  * ``execute_paper_orders`` — fills pending orders against today's
    daily_prices when enabled (one-account and multi-account paths)
  * ``execute_paper_orders`` — works through the ``run_job`` wrapper and
    leaves a SUCCESS row in ``job_runs``
  * ``create_paper_pnl_snapshot`` — SKIPPED when disabled
  * ``create_paper_pnl_snapshot`` — writes one snapshot per active account
    when enabled
  * Scheduler ``DEFAULT_SCHEDULE`` registers both jobs at the documented times
  * Forbidden imports: ``app/scheduler/jobs.py`` paper helpers reference
    only internal modules (no KIS / requests / httpx)
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_fill import VirtualFillRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import VirtualPositionRepository
from app.db.base import Base
from app.db.models import JobRun
from app.db.session import create_session_factory
from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_CREATE_PAPER_PNL_SNAPSHOT,
    JOB_NAME_EXECUTE_PAPER_ORDERS,
    create_paper_pnl_snapshot,
    execute_paper_orders,
    run_job,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_factory_in_memory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    Base.metadata.drop_all(engine)


def _settings(*, enabled: bool) -> Settings:
    return Settings(paper_trading_enabled=enabled)


def _seed_account(session, *, name="paper", initial_cash=Decimal("1000000")):
    repo = VirtualAccountRepository(session)
    acc = repo.create(name=name, initial_cash=initial_cash)
    session.commit()
    return acc.id


def _seed_close(session, *, symbol, target_date, close):
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=target_date,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1000,
    )
    session.commit()


def _seed_pending_order(session, *, account_id, symbol, side="BUY", quantity=1):
    order = VirtualOrderRepository(session).create(
        account_id=account_id, symbol=symbol, side=side, quantity=quantity
    )
    session.commit()
    return order.id


# ---------------------------------------------------------------------------
# execute_paper_orders
# ---------------------------------------------------------------------------


def test_execute_paper_orders_skipped_when_disabled(session_factory_in_memory):
    session = session_factory_in_memory()
    try:
        account_id = _seed_account(session)
        _seed_pending_order(session, account_id=account_id, symbol="005930")
        _seed_close(
            session,
            symbol="005930",
            target_date=date.today(),
            close=Decimal("10000"),
        )
        session.info["settings"] = _settings(enabled=False)
        result = execute_paper_orders(session)
    finally:
        session.close()

    assert result.summary["data_status"] == "SKIPPED"
    assert result.summary["reason"] == "paper_trading_disabled"
    assert result.summary["accounts_processed"] == 0
    # No fills were written.
    session = session_factory_in_memory()
    try:
        assert VirtualFillRepository(session).list_by_account(account_id) == []
    finally:
        session.close()


def test_execute_paper_orders_fills_pending_when_enabled(session_factory_in_memory):
    session = session_factory_in_memory()
    try:
        account_id = _seed_account(session)
        _seed_pending_order(session, account_id=account_id, symbol="005930")
        _seed_close(
            session,
            symbol="005930",
            target_date=date.today(),
            close=Decimal("10000"),
        )
        session.info["settings"] = _settings(enabled=True)
        result = execute_paper_orders(session)
        session.commit()
    finally:
        session.close()

    assert result.summary["data_status"] == "SUCCESS"
    assert result.summary["filled_count"] == 1
    assert result.summary["accounts_processed"] == 1


def test_execute_paper_orders_processes_each_active_account(
    session_factory_in_memory,
):
    session = session_factory_in_memory()
    try:
        a1 = _seed_account(session, name="acct-1")
        a2 = _seed_account(session, name="acct-2")
        # Disable the second account: it should NOT be processed.
        VirtualAccountRepository(session).set_paper_trading_enabled(
            VirtualAccountRepository(session).get_by_id(a2), enabled=False
        )
        session.commit()

        _seed_pending_order(session, account_id=a1, symbol="005930")
        _seed_pending_order(session, account_id=a2, symbol="005930")
        _seed_close(
            session,
            symbol="005930",
            target_date=date.today(),
            close=Decimal("10000"),
        )

        session.info["settings"] = _settings(enabled=True)
        result = execute_paper_orders(session)
        session.commit()
    finally:
        session.close()

    assert result.summary["accounts_processed"] == 1
    assert result.summary["filled_count"] == 1


def test_execute_paper_orders_through_run_job_records_success(
    session_factory_in_memory,
):
    s = session_factory_in_memory()
    try:
        account_id = _seed_account(s)
        _seed_pending_order(s, account_id=account_id, symbol="005930")
        _seed_close(
            s,
            symbol="005930",
            target_date=date.today(),
            close=Decimal("10000"),
        )
    finally:
        s.close()

    def _job(session):
        session.info["settings"] = _settings(enabled=True)
        return execute_paper_orders(session)

    outcome = run_job(
        session_factory=session_factory_in_memory,
        job_name=JOB_NAME_EXECUTE_PAPER_ORDERS,
        fn=_job,
    )
    assert outcome.status == "SUCCESS"
    assert outcome.result_summary["filled_count"] == 1

    # job_runs row written with the right job_name + status.
    s = session_factory_in_memory()
    try:
        from sqlalchemy import select

        rows = list(s.execute(select(JobRun)).scalars().all())
        assert len(rows) == 1
        assert rows[0].job_name == JOB_NAME_EXECUTE_PAPER_ORDERS
        assert rows[0].status == "SUCCESS"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# create_paper_pnl_snapshot
# ---------------------------------------------------------------------------


def test_create_paper_pnl_snapshot_skipped_when_disabled(session_factory_in_memory):
    session = session_factory_in_memory()
    try:
        _seed_account(session)
        session.info["settings"] = _settings(enabled=False)
        result = create_paper_pnl_snapshot(session)
    finally:
        session.close()

    assert result.summary["data_status"] == "SKIPPED"
    assert result.summary["accounts_processed"] == 0


def test_create_paper_pnl_snapshot_writes_one_snapshot_per_account(
    session_factory_in_memory,
):
    session = session_factory_in_memory()
    try:
        a1 = _seed_account(session, name="acct-1")
        a2 = _seed_account(session, name="acct-2")
        VirtualPositionRepository(session).apply_buy(
            account_id=a1,
            symbol="005930",
            fill_quantity=10,
            fill_price=Decimal("10000"),
            cash_spent=Decimal("100000"),
        )
        _seed_close(
            session,
            symbol="005930",
            target_date=date.today(),
            close=Decimal("11000"),
        )
        session.info["settings"] = _settings(enabled=True)
        result = create_paper_pnl_snapshot(session)
        session.commit()
    finally:
        session.close()

    assert result.summary["accounts_processed"] == 2
    assert result.summary["snapshots_written"] == 2

    session = session_factory_in_memory()
    try:
        snaps_a1 = VirtualPnLSnapshotRepository(session).list_by_account(a1)
        snaps_a2 = VirtualPnLSnapshotRepository(session).list_by_account(a2)
        assert len(snaps_a1) == 1
        assert len(snaps_a2) == 1
        # account 1 has an open position priced at 11,000 → market_value 110,000
        assert snaps_a1[0].market_value == Decimal("110000.0000")
        # account 2 has no positions → market_value 0
        assert snaps_a2[0].market_value == Decimal("0.0000")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# DEFAULT_SCHEDULE registration
# ---------------------------------------------------------------------------


def test_paper_jobs_registered_at_default_times():
    from app.scheduler.scheduler import DEFAULT_SCHEDULE

    assert DEFAULT_SCHEDULE[JOB_NAME_EXECUTE_PAPER_ORDERS] == (16, 0)
    assert DEFAULT_SCHEDULE[JOB_NAME_CREATE_PAPER_PNL_SNAPSHOT] == (16, 30)
    assert JOB_NAME_EXECUTE_PAPER_ORDERS in JOB_FUNCTIONS
    assert JOB_NAME_CREATE_PAPER_PNL_SNAPSHOT in JOB_FUNCTIONS


# ---------------------------------------------------------------------------
# Forbidden imports in scheduler/jobs.py paper paths
# ---------------------------------------------------------------------------


def test_paper_job_helpers_reference_only_internal_modules():
    """The two paper job functions and their lazy imports stay inside app.*.

    We don't ban the entire scheduler/jobs.py from importing httpx (other
    jobs already do). Instead, we walk the AST and confirm that the bodies
    of ``execute_paper_orders`` and ``create_paper_pnl_snapshot`` only
    reference ``app.*`` and stdlib modules.
    """
    src = (PROJECT_ROOT / "app" / "scheduler" / "jobs.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    target_names = {"execute_paper_orders", "create_paper_pnl_snapshot"}
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = (
        "app.kis",
        "app.data.dart_provider",
        "app.data.rss_provider",
        "app.data.collectors.kis_client",
    )

    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import):
                    for a in inner.names:
                        if a.name in forbidden_modules or any(
                            a.name == p or a.name.startswith(p + ".")
                            for p in forbidden_prefixes
                        ):
                            leaks.append(f"{node.name}: import {a.name}")
                elif isinstance(inner, ast.ImportFrom):
                    module = inner.module or ""
                    if module in forbidden_modules or any(
                        module == p or module.startswith(p + ".")
                        for p in forbidden_prefixes
                    ):
                        leaks.append(f"{node.name}: from {module}")

    assert leaks == [], (
        f"paper job helpers reference forbidden modules: {leaks!r}"
    )
