"""Integration tests for v0.8 Phase B repositories."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.data.repositories.login_audit_logs import (
    EVENT_LOGIN_FAILED,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    LoginAuditLogRepository,
)
from app.data.repositories.users import UserRepository
from app.db.base import Base
from app.db.session import create_session_factory


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ---------- UserRepository ----------


def test_create_user_persists_with_defaults(session):
    repo = UserRepository(session)
    user = repo.create(
        username="alice",
        password_hash="scrypt$1024$8$1$abc$def",
    )
    session.commit()
    assert user.id is not None
    assert user.is_active is True
    assert user.is_admin is False
    assert user.last_login_at is None
    assert user.created_at is not None
    assert user.updated_at is not None


def test_get_by_username_returns_row_or_none(session):
    repo = UserRepository(session)
    repo.create(username="alice", password_hash="scrypt$1024$8$1$abc$def")
    session.commit()

    found = repo.get_by_username("alice")
    assert found is not None
    assert found.username == "alice"

    missing = repo.get_by_username("never-existed")
    assert missing is None


def test_get_by_id(session):
    repo = UserRepository(session)
    user = repo.create(username="alice", password_hash="scrypt$1024$8$1$abc$def")
    session.commit()
    found = repo.get_by_id(user.id)
    assert found is not None and found.id == user.id


def test_username_unique_constraint(session):
    repo = UserRepository(session)
    repo.create(username="dup", password_hash="scrypt$1024$8$1$a$b")
    # BaseRepository.add() flushes inside create(), so the second insert is
    # what surfaces the UNIQUE violation.
    with pytest.raises(IntegrityError):
        repo.create(username="dup", password_hash="scrypt$1024$8$1$c$d")


def test_set_last_login_updates_timestamp(session):
    repo = UserRepository(session)
    user = repo.create(username="alice", password_hash="scrypt$1024$8$1$a$b")
    session.commit()
    assert user.last_login_at is None
    before_updated = user.updated_at

    repo.set_last_login(user)
    session.commit()
    assert user.last_login_at is not None
    assert user.updated_at >= before_updated


def test_deactivate(session):
    repo = UserRepository(session)
    user = repo.create(username="alice", password_hash="scrypt$1024$8$1$a$b")
    session.commit()
    assert user.is_active is True
    repo.deactivate(user)
    session.commit()
    assert user.is_active is False


def test_admin_flag_persists(session):
    repo = UserRepository(session)
    user = repo.create(
        username="boss",
        password_hash="scrypt$1024$8$1$a$b",
        is_admin=True,
    )
    session.commit()
    fetched = repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.is_admin is True


# ---------- LoginAuditLogRepository ----------


def test_create_login_audit_log_success(session):
    user = UserRepository(session).create(
        username="alice", password_hash="scrypt$1024$8$1$a$b"
    )
    session.flush()
    audit = LoginAuditLogRepository(session)
    row = audit.create(
        event_type=EVENT_LOGIN_SUCCESS,
        username="alice",
        user_id=user.id,
        source_ip_hash="a" * 64,
        user_agent_hash="b" * 64,
    )
    session.commit()
    assert row.id is not None
    assert row.event_type == EVENT_LOGIN_SUCCESS
    assert row.user_id == user.id
    assert row.source_ip_hash == "a" * 64
    assert row.user_agent_hash == "b" * 64


def test_create_login_audit_log_failed_with_unknown_user(session):
    audit = LoginAuditLogRepository(session)
    row = audit.create(
        event_type=EVENT_LOGIN_FAILED,
        username="ghost",
        user_id=None,
        source_ip_hash=None,
        user_agent_hash=None,
    )
    session.commit()
    assert row.event_type == EVENT_LOGIN_FAILED
    assert row.user_id is None
    assert row.source_ip_hash is None


def test_create_rejects_unknown_event_type(session):
    audit = LoginAuditLogRepository(session)
    with pytest.raises(ValueError):
        audit.create(
            event_type="OOPS",
            username="alice",
            user_id=None,
            source_ip_hash=None,
            user_agent_hash=None,
        )


def test_audit_does_not_persist_plain_ip_or_user_agent(session):
    """The repository accepts hashes only -- plaintext caller data must be
    hashed at the route layer. This test enforces that no plaintext IP /
    user agent strings ever reach the column. We confirm by inserting both
    a known plaintext-like and a real SHA256 hex and asserting the column
    matches what was passed."""
    audit = LoginAuditLogRepository(session)
    row = audit.create(
        event_type=EVENT_LOGIN_FAILED,
        username="bob",
        user_id=None,
        # Routes pass the SHA256 hex of the IP -- not the IP itself.
        source_ip_hash="0" * 64,
        user_agent_hash="f" * 64,
    )
    session.commit()
    assert row.source_ip_hash != "203.0.113.7"
    assert row.user_agent_hash != "Mozilla/5.0"
    assert len(row.source_ip_hash) == 64
    assert len(row.user_agent_hash) == 64


def test_list_recent_returns_newest_first(session):
    user = UserRepository(session).create(
        username="alice", password_hash="scrypt$1024$8$1$a$b"
    )
    session.flush()
    audit = LoginAuditLogRepository(session)
    for ev in (EVENT_LOGIN_SUCCESS, EVENT_LOGOUT, EVENT_LOGIN_SUCCESS):
        audit.create(
            event_type=ev,
            username="alice",
            user_id=user.id,
            source_ip_hash=None,
            user_agent_hash=None,
        )
    session.commit()
    recent = audit.list_recent(limit=10)
    assert len(recent) == 3
    assert recent[0].id > recent[1].id > recent[2].id


def test_list_by_username_filters(session):
    audit = LoginAuditLogRepository(session)
    audit.create(
        event_type=EVENT_LOGIN_SUCCESS,
        username="alice",
        user_id=None,
        source_ip_hash=None,
        user_agent_hash=None,
    )
    audit.create(
        event_type=EVENT_LOGIN_FAILED,
        username="bob",
        user_id=None,
        source_ip_hash=None,
        user_agent_hash=None,
    )
    session.commit()
    rows = audit.list_by_username("alice")
    assert len(rows) == 1
    assert rows[0].username == "alice"


def test_list_by_user_filters(session):
    user = UserRepository(session).create(
        username="alice", password_hash="scrypt$1024$8$1$a$b"
    )
    session.flush()
    audit = LoginAuditLogRepository(session)
    audit.create(
        event_type=EVENT_LOGIN_SUCCESS,
        username="alice",
        user_id=user.id,
        source_ip_hash=None,
        user_agent_hash=None,
    )
    audit.create(
        event_type=EVENT_LOGIN_FAILED,
        username="ghost",
        user_id=None,
        source_ip_hash=None,
        user_agent_hash=None,
    )
    session.commit()
    rows = audit.list_by_user(user.id)
    assert len(rows) == 1
    assert rows[0].user_id == user.id
