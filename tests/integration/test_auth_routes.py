"""End-to-end tests for v0.8 Phase B auth API routes.

Covers two operating modes:

  * AUTH_ENABLED=false (dev / CI default) -- /login still works (so existing
    operators can sanity-check the flow), /me reports auth_enabled=False,
    /logout records an audit row with username=None.
  * AUTH_ENABLED=true (prod-like) -- /login issues a real JWT, missing /
    invalid / expired Bearer tokens are rejected by /me, deactivated users
    are rejected by /me even with a still-valid token.

Each test uses an in-memory SQLite seeded via Base.metadata.create_all() and
overrides FastAPI's get_session and get_settings dependencies. No external
APIs (KIS / DART / Telegram) are involved.
"""

from __future__ import annotations

import re
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.auth.security import PasswordHasher
from app.config.settings import Settings, get_settings
from app.data.repositories.login_audit_logs import (
    EVENT_LOGIN_FAILED,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    LoginAuditLogRepository,
)
from app.data.repositories.users import UserRepository
from app.db import Base
from app.db.session import create_session_factory, get_session


_FAST_HASH = {
    "password_hash_n": 1024,
    "password_hash_r": 8,
    "password_hash_p": 1,
}

_BASE_SETTINGS_KW = dict(
    app_env="test",
    app_name="stock_ai_platform",
    timezone="Asia/Seoul",
    log_level="INFO",
    telegram_enabled=False,
    telegram_bot_token="abcd1234efgh5678",
    telegram_chat_id="123456789012",
    telegram_api_base_url="https://mock-telegram.local",
    telegram_timeout_seconds=5,
    kis_app_key="kkkk1111kkkk2222",
    kis_app_secret="ssss3333ssss4444",
    kis_account_no="9876543210",
    kis_account_product_code="01",
    kis_use_paper=True,
    scheduler_enabled=False,
    feature_real_order_execution=False,
    feature_full_auto=False,
    feature_paper_trading=False,
    feature_backtest=False,
    feature_custom_ai_training=False,
)


@pytest.fixture()
def session() -> Iterator:
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


def _make_client(session, *, auth_enabled: bool, jwt_secret: str | None = None):
    from app.main import app

    settings = Settings(
        auth_enabled=auth_enabled,
        jwt_secret=jwt_secret,
        jwt_algorithm="HS256",
        jwt_expires_minutes=60,
        **_FAST_HASH,
        **_BASE_SETTINGS_KW,
    )

    def override_session():
        yield session

    def override_settings():
        return settings

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app)


def _seed_user(
    session,
    *,
    username: str = "alice",
    password: str = "hunter2!",
    is_admin: bool = True,
    is_active: bool = True,
):
    hasher = PasswordHasher(n=1024, r=8, p=1)
    user = UserRepository(session).create(
        username=username,
        password_hash=hasher.hash_password(password),
        is_admin=is_admin,
        is_active=is_active,
    )
    session.commit()
    return user


def _audit_events(session) -> list[str]:
    rows = LoginAuditLogRepository(session).list_recent(limit=50)
    return [r.event_type for r in rows]


def _flatten_response_text(payload) -> str:
    """Recursive json -> string for forbidden-token assertions."""
    return repr(payload).lower()


# ---------- AUTH_ENABLED=false (dev / CI fallback) ----------


def test_login_success_returns_token_and_does_not_leak_password(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "hunter2!"},
            headers={"User-Agent": "pytest"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["username"] == "alice"
    assert body["user"]["is_admin"] is True
    flat = _flatten_response_text(body)
    assert "password" not in flat  # neither plaintext nor hash leaks
    assert "scrypt$" not in flat
    # Audit log records LOGIN_SUCCESS.
    events = _audit_events(session)
    assert events == [EVENT_LOGIN_SUCCESS]


def test_login_failure_returns_generic_401(session):
    _seed_user(session, username="alice", password="correct")
    client = _make_client(session, auth_enabled=False)
    try:
        resp_wrong_pw = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "wrong"},
        )
        resp_unknown = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
    finally:
        client.app.dependency_overrides.clear()

    assert resp_wrong_pw.status_code == 401
    assert resp_unknown.status_code == 401
    # The error message must NOT distinguish the two cases.
    assert resp_wrong_pw.json()["detail"] == resp_unknown.json()["detail"]
    # Both produce LOGIN_FAILED audit rows.
    events = _audit_events(session)
    assert events.count(EVENT_LOGIN_FAILED) == 2


def test_login_failure_for_deactivated_user(session):
    _seed_user(session, username="alice", password="hunter2!", is_active=False)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "hunter2!"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 401
    assert _audit_events(session) == [EVENT_LOGIN_FAILED]


def test_me_when_auth_disabled_returns_fallback(session):
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.get("/api/auth/me")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_enabled"] is False
    assert body["via"] == "auth_disabled_fallback"
    assert body["user"] is None


def test_logout_records_audit_when_disabled(session):
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.post("/api/auth/logout")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    events = _audit_events(session)
    assert events == [EVENT_LOGOUT]


# ---------- AUTH_ENABLED=true (prod-like) ----------


def _login(client, username: str, password: str):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def test_me_when_auth_enabled_requires_token(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        resp_no_header = client.get("/api/auth/me")
        resp_bad_scheme = client.get(
            "/api/auth/me",
            headers={"Authorization": "Basic abcdef"},
        )
        resp_bad_token = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not.a.jwt"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp_no_header.status_code == 401
    assert resp_bad_scheme.status_code == 401
    assert resp_bad_token.status_code == 401
    for resp in (resp_no_header, resp_bad_scheme, resp_bad_token):
        assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_me_with_valid_token_returns_user(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        login = _login(client, "alice", "hunter2!")
        token = login.json()["access_token"]
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_enabled"] is True
    assert body["via"] == "token"
    assert body["user"]["username"] == "alice"


def test_me_rejects_token_when_user_deactivated(session):
    user = _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        login = _login(client, "alice", "hunter2!")
        token = login.json()["access_token"]
        # Deactivate AFTER issuing the token.
        UserRepository(session).deactivate(user)
        session.commit()
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 401


def test_login_success_audit_includes_username_and_user_id(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        _login(client, "alice", "hunter2!")
    finally:
        client.app.dependency_overrides.clear()
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == EVENT_LOGIN_SUCCESS
    assert row.username == "alice"
    assert row.user_id is not None


def test_login_failure_records_audit_with_no_user_id_when_unknown(session):
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        _login(client, "ghost", "anything")
    finally:
        client.app.dependency_overrides.clear()
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0].event_type == EVENT_LOGIN_FAILED
    assert rows[0].username == "ghost"
    assert rows[0].user_id is None


def test_audit_persists_only_hashed_ip_and_user_agent(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "hunter2!"},
            headers={
                "User-Agent": "Mozilla/5.0 SecretClient/1.0",
                "X-Forwarded-For": "203.0.113.7",
            },
        )
    finally:
        client.app.dependency_overrides.clear()
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    assert len(rows) == 1
    row = rows[0]
    # Plaintext NEVER appears in the persisted columns.
    assert row.source_ip_hash != "203.0.113.7"
    assert row.user_agent_hash != "Mozilla/5.0 SecretClient/1.0"
    # Both are 64-char hex digests.
    assert row.source_ip_hash is not None and len(row.source_ip_hash) == 64
    assert row.user_agent_hash is not None and len(row.user_agent_hash) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", row.source_ip_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", row.user_agent_hash)


def test_logout_with_token_records_audit_username(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        login = _login(client, "alice", "hunter2!")
        token = login.json()["access_token"]
        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    assert rows[0].event_type == EVENT_LOGOUT
    assert rows[0].username == "alice"


def test_login_responses_never_leak_password_hash(session):
    user = _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        login = _login(client, "alice", "hunter2!")
        token = login.json()["access_token"]
        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.app.dependency_overrides.clear()
    for body in (login.json(), me.json()):
        flat = _flatten_response_text(body)
        assert "password_hash" not in flat
        assert "scrypt$" not in flat
    # Sanity: the actual hash is in the DB.
    assert user.password_hash.startswith("scrypt$")


def test_existing_read_only_routes_remain_open_when_auth_enabled(session):
    """v0.8 Phase B does NOT retrofit existing GET routers behind auth.

    A protected stance for read-only endpoints would break v0.7 baselines and
    is explicitly out of scope. The Watchlist Phase C will introduce the
    first protected (POST/DELETE) endpoints.
    """
    _seed_user(session)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        resp = client.get("/health")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
