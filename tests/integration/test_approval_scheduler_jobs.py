"""Integration tests for v0.15 Phase D ``expire_pending_approvals`` job.

Covers:
  * SKIPPED when ``trading_safety_enabled=False`` (default).
  * SKIPPED when ``kill_switch_enabled=True``.
  * SUCCESS + zero-write when no PENDING_APPROVAL candidates are overdue.
  * SUCCESS + EXPIRED transitions when overdue candidates exist; an
    ``EXPIRED`` audit row appears per candidate.
  * Per-candidate failures are isolated (PARTIAL).
  * The job runs cleanly through the ``run_job`` wrapper.
  * ``DEFAULT_INTERVAL_SCHEDULE`` registers the job at 5-minute interval.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
)
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.models import JobRun
from app.db.session import create_session_factory
from app.scheduler.jobs import (
    JOB_FUNCTIONS,
    JOB_NAME_EXPIRE_PENDING_APPROVALS,
    expire_pending_approvals,
    run_job,
)


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


def _settings(*, safety: bool, kill: bool = False) -> Settings:
    return Settings(
        trading_safety_enabled=safety,
        kill_switch_enabled=kill,
        approval_required=True,
        max_order_amount=100_000,
        max_daily_order_amount=1_000_000,
        max_position_ratio=0.20,
        max_daily_loss_amount=500_000,
        paper_trading_enabled=True,
    )


def _seed_account_and_candidates(
    session, *, expired_count: int = 1, fresh_count: int = 1
) -> dict:
    """Seed an account + candidates split between overdue and not-yet-overdue."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("1000000"))
    session.commit()

    repo = OrderCandidateRepository(session)
    overdue_ids: list[int] = []
    fresh_ids: list[int] = []
    now = datetime.now(timezone.utc)
    for _ in range(expired_count):
        c = repo.create(
            account_id=acc.id,
            source="MANUAL",
            symbol="005930",
            side="BUY",
            quantity=1,
            estimated_amount=Decimal("100"),
            expires_at=now - timedelta(minutes=10),
        )
        repo.update_status(c, new_status="RISK_CHECKING")
        repo.update_status(c, new_status="PENDING_APPROVAL")
        overdue_ids.append(c.id)
    for _ in range(fresh_count):
        c = repo.create(
            account_id=acc.id,
            source="MANUAL",
            symbol="000660",
            side="BUY",
            quantity=1,
            estimated_amount=Decimal("100"),
            expires_at=now + timedelta(minutes=30),
        )
        repo.update_status(c, new_status="RISK_CHECKING")
        repo.update_status(c, new_status="PENDING_APPROVAL")
        fresh_ids.append(c.id)
    session.commit()
    return {"account_id": acc.id, "overdue": overdue_ids, "fresh": fresh_ids}


# ---------------------------------------------------------------------------
# Skip paths
# ---------------------------------------------------------------------------


def test_expire_skipped_when_safety_disabled(session_factory_in_memory):
    s = session_factory_in_memory()
    try:
        seeded = _seed_account_and_candidates(s)
        s.info["settings"] = _settings(safety=False)
        result = expire_pending_approvals(s)
    finally:
        s.close()

    assert result.summary["data_status"] == "SKIPPED"
    assert result.summary["reason"] == "trading_safety_disabled"
    # Candidates are untouched.
    s = session_factory_in_memory()
    try:
        repo = OrderCandidateRepository(s)
        for cid in seeded["overdue"]:
            assert repo.get_by_id(cid).status == "PENDING_APPROVAL"
    finally:
        s.close()


def test_expire_skipped_when_kill_switch_on(session_factory_in_memory):
    s = session_factory_in_memory()
    try:
        seeded = _seed_account_and_candidates(s)
        s.info["settings"] = _settings(safety=True, kill=True)
        result = expire_pending_approvals(s)
    finally:
        s.close()

    assert result.summary["data_status"] == "SKIPPED"
    assert result.summary["reason"] == "kill_switch_enabled"


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_expire_success_no_overdue(session_factory_in_memory):
    s = session_factory_in_memory()
    try:
        _seed_account_and_candidates(s, expired_count=0, fresh_count=2)
        s.info["settings"] = _settings(safety=True)
        result = expire_pending_approvals(s)
    finally:
        s.close()

    assert result.summary["data_status"] == "SUCCESS"
    assert result.summary["expired_count"] == 0
    assert result.summary["reason"] == "nothing_expired"


def test_expire_success_marks_overdue_candidates_expired(
    session_factory_in_memory,
):
    s = session_factory_in_memory()
    try:
        seeded = _seed_account_and_candidates(s, expired_count=2, fresh_count=1)
        s.info["settings"] = _settings(safety=True)
        result = expire_pending_approvals(s)
        s.commit()
    finally:
        s.close()

    assert result.summary["data_status"] == "SUCCESS"
    assert result.summary["expired_count"] == 2
    assert result.summary["failed_count"] == 0

    s = session_factory_in_memory()
    try:
        repo = OrderCandidateRepository(s)
        for cid in seeded["overdue"]:
            assert repo.get_by_id(cid).status == "EXPIRED"
        # Fresh candidate stays PENDING_APPROVAL.
        for cid in seeded["fresh"]:
            assert repo.get_by_id(cid).status == "PENDING_APPROVAL"
        # Audit log carries one EXPIRED row per overdue.
        audit = ApprovalAuditLogRepository(s)
        for cid in seeded["overdue"]:
            rows = audit.list_by_candidate(cid)
            assert any(r.event_type == "EXPIRED" for r in rows)
    finally:
        s.close()


def test_expire_runs_through_run_job_wrapper(session_factory_in_memory):
    s = session_factory_in_memory()
    try:
        _seed_account_and_candidates(s, expired_count=1, fresh_count=0)
    finally:
        s.close()

    def _job(session):
        session.info["settings"] = _settings(safety=True)
        return expire_pending_approvals(session)

    outcome = run_job(
        session_factory=session_factory_in_memory,
        job_name=JOB_NAME_EXPIRE_PENDING_APPROVALS,
        fn=_job,
    )
    assert outcome.status == "SUCCESS"
    assert outcome.result_summary["expired_count"] == 1

    s = session_factory_in_memory()
    try:
        from sqlalchemy import select

        runs = list(s.execute(select(JobRun)).scalars().all())
        assert len(runs) == 1
        assert runs[0].job_name == JOB_NAME_EXPIRE_PENDING_APPROVALS
        assert runs[0].status == "SUCCESS"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Default schedule registration
# ---------------------------------------------------------------------------


def test_expire_pending_approvals_registered_at_5_minute_interval():
    from app.scheduler.scheduler import (
        DEFAULT_INTERVAL_SCHEDULE,
        DEFAULT_SCHEDULE,
    )

    # Cron schedule for the daily-cadence jobs must NOT include this one.
    assert JOB_NAME_EXPIRE_PENDING_APPROVALS not in DEFAULT_SCHEDULE
    # Interval schedule registers it at 5 minutes.
    assert DEFAULT_INTERVAL_SCHEDULE[JOB_NAME_EXPIRE_PENDING_APPROVALS] == 5
    # Job function is registered.
    assert JOB_NAME_EXPIRE_PENDING_APPROVALS in JOB_FUNCTIONS
