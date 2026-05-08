"""Integration tests for v0.15 Phase D ``ApprovalAuditLog`` repository + ORM.

Covers:
  * ``append`` happy path + event_type validation + reason 256-char truncate.
  * ``list_by_candidate`` ascending id, ``list_recent`` descending id.
  * Forbidden ``details`` keys raise (api_key / token / secret / etc).
  * Repository surface contains NO ``update_*`` / ``delete_*`` / ``mutate``
    method names -- audit is append-only by construction.
  * ``ip_hash`` / ``user_agent_hash`` length cap (64 chars / SHA256 hex).
  * Forbidden columns absent from the ORM table.
  * Cascade delete from OrderCandidate drops audit rows.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
    ApprovalAuditLogValidationError,
    VALID_EVENT_TYPES,
)
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.models import ApprovalAuditLog
from app.db.session import create_session_factory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
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
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _seed_candidate(session) -> int:
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("1000000"))
    session.commit()

    cand = OrderCandidateRepository(session).create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("100"),
    )
    session.commit()
    return cand.id


# ---------------------------------------------------------------------------
# Append happy paths
# ---------------------------------------------------------------------------


def test_append_creates_audit_row(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    row = repo.append(
        candidate_id=candidate_id,
        event_type="CREATED",
        user_id=None,
        reason="seed",
        details={"source": "MANUAL"},
        ip_hash="a" * 64,
        user_agent_hash="b" * 64,
    )
    session.commit()
    assert row.id is not None
    assert row.event_type == "CREATED"
    assert row.reason == "seed"
    assert row.details_json == {"source": "MANUAL"}
    assert row.ip_hash == "a" * 64
    assert row.user_agent_hash == "b" * 64


def test_append_truncates_long_reason(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    long_reason = "x" * 500
    row = repo.append(
        candidate_id=candidate_id,
        event_type="REJECTED",
        reason=long_reason,
    )
    session.commit()
    assert row.reason is not None
    assert len(row.reason) == 256


@pytest.mark.parametrize("event_type", sorted(VALID_EVENT_TYPES))
def test_append_accepts_all_valid_event_types(session, event_type):
    candidate_id = _seed_candidate(session)
    row = ApprovalAuditLogRepository(session).append(
        candidate_id=candidate_id,
        event_type=event_type,
    )
    session.commit()
    assert row.event_type == event_type


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_append_rejects_unknown_event_type(session):
    candidate_id = _seed_candidate(session)
    with pytest.raises(ApprovalAuditLogValidationError, match="event_type must be"):
        ApprovalAuditLogRepository(session).append(
            candidate_id=candidate_id,
            event_type="UNKNOWN",
        )


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "api_key",
        "token",
        "secret",
        "access_token",
        "jwt_secret",
        "broker_order_id",
        "kis_order_id",
        "real_account",
        "real_order_id",
        "account_number",
        "raw_text",
        "body",
        "full_text",
        "source_file_path",
    ],
)
def test_append_rejects_forbidden_details_keys(session, forbidden_key):
    candidate_id = _seed_candidate(session)
    with pytest.raises(ApprovalAuditLogValidationError, match="forbidden"):
        ApprovalAuditLogRepository(session).append(
            candidate_id=candidate_id,
            event_type="CREATED",
            details={forbidden_key: "leaky"},
        )


def test_append_rejects_non_dict_details(session):
    candidate_id = _seed_candidate(session)
    with pytest.raises(ApprovalAuditLogValidationError, match="must be a dict"):
        ApprovalAuditLogRepository(session).append(
            candidate_id=candidate_id,
            event_type="CREATED",
            details=["not", "a", "dict"],  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("kwarg", ["ip_hash", "user_agent_hash"])
def test_append_rejects_oversized_hash_inputs(session, kwarg):
    candidate_id = _seed_candidate(session)
    too_long = "a" * 65
    with pytest.raises(
        ApprovalAuditLogValidationError, match="64 chars"
    ):
        ApprovalAuditLogRepository(session).append(
            candidate_id=candidate_id,
            event_type="CREATED",
            **{kwarg: too_long},
        )


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def test_list_by_candidate_returns_ascending_id(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    repo.append(candidate_id=candidate_id, event_type="CREATED")
    repo.append(candidate_id=candidate_id, event_type="RISK_CHECKED")
    repo.append(candidate_id=candidate_id, event_type="APPROVED")
    session.commit()

    rows = repo.list_by_candidate(candidate_id)
    assert [r.event_type for r in rows] == [
        "CREATED",
        "RISK_CHECKED",
        "APPROVED",
    ]


def test_list_recent_returns_descending_id(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    repo.append(candidate_id=candidate_id, event_type="CREATED")
    repo.append(candidate_id=candidate_id, event_type="REJECTED")
    session.commit()
    rows = repo.list_recent()
    assert [r.event_type for r in rows] == ["REJECTED", "CREATED"]


def test_list_recent_event_type_filter(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    repo.append(candidate_id=candidate_id, event_type="CREATED")
    repo.append(candidate_id=candidate_id, event_type="APPROVED")
    repo.append(candidate_id=candidate_id, event_type="EXECUTED_PAPER")
    session.commit()
    rows = repo.list_recent(event_type="APPROVED")
    assert len(rows) == 1
    assert rows[0].event_type == "APPROVED"


def test_list_recent_rejects_unknown_event_type(session):
    repo = ApprovalAuditLogRepository(session)
    with pytest.raises(ApprovalAuditLogValidationError):
        repo.list_recent(event_type="UNKNOWN")


# ---------------------------------------------------------------------------
# Append-only contract (no update / delete API)
# ---------------------------------------------------------------------------


def test_repository_has_no_mutation_methods_beyond_append():
    """Repository must NOT expose ``update`` / ``delete`` / similar."""
    forbidden_substrings = (
        "update",
        "delete",
        "remove",
        "set_event",
        "edit",
        "patch",
        "mutate",
    )
    public_methods = [
        name
        for name, _ in inspect.getmembers(
            ApprovalAuditLogRepository, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    ]
    leaks = [
        m
        for m in public_methods
        if any(s in m.lower() for s in forbidden_substrings)
    ]
    assert leaks == [], (
        f"ApprovalAuditLogRepository must be append-only; mutation-like "
        f"methods found: {leaks!r}"
    )


# ---------------------------------------------------------------------------
# Forbidden columns + cascade
# ---------------------------------------------------------------------------


_FORBIDDEN_COLUMNS = (
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "real_order_id",
    "api_key",
    "token",
    "secret",
)


def test_orm_has_no_forbidden_columns():
    column_names = {col.key for col in ApprovalAuditLog.__table__.columns}
    leaked = column_names & set(_FORBIDDEN_COLUMNS)
    assert leaked == set()


def test_cascade_delete_from_candidate_removes_audit_rows(session):
    candidate_id = _seed_candidate(session)
    repo = ApprovalAuditLogRepository(session)
    repo.append(candidate_id=candidate_id, event_type="CREATED")
    repo.append(candidate_id=candidate_id, event_type="APPROVED")
    session.commit()

    cand = OrderCandidateRepository(session).get_by_id(candidate_id)
    session.delete(cand)
    session.commit()

    assert repo.list_by_candidate(candidate_id) == []
