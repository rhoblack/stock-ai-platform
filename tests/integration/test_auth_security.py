"""Integration tests for v0.9 Phase A auth security hardening.

Covers:
  * Security headers present on /health and /api/auth/login
  * Brute force lockout via POST /api/auth/login (with fresh in-memory guard)
  * Lockout response is identical to wrong-password 401 (no user-existence leak)
  * Successful login resets the brute force failure counter
  * LOCKOUT_REJECTED audit row is recorded (no sensitive data)
  * source_ip and user_agent are stored only as hashes (not plaintext)
  * password / password_hash / access_token / jwt_secret not in response bodies
  * POST/PUT/DELETE endpoint count guard (Watchlist + Auth = 5, no extras)
  * No auto-trade / order / broker strings in route paths or schemas

The conftest autouse fixture disables rate limiting and brute force globally.
Tests that need them active manage app.state themselves.
"""

from __future__ import annotations

import re
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.auth.brute_force import BruteForceGuard
from app.auth.security import PasswordHasher
from app.config.settings import Settings, get_settings
from app.data.repositories.login_audit_logs import (
    EVENT_LOCKOUT_REJECTED,
    EVENT_LOGIN_FAILED,
    EVENT_LOGIN_SUCCESS,
    LoginAuditLogRepository,
)
from app.data.repositories.users import UserRepository
from app.db import Base
from app.db.session import create_session_factory, get_session
from app.main import app
from app.middleware.rate_limit import limiter


_FAST_HASH = {"password_hash_n": 1024, "password_hash_r": 8, "password_hash_p": 1}

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


def _make_client(session, *, auth_enabled: bool = False, jwt_secret: str | None = None):
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


def _seed_user(session, *, username: str = "alice", password: str = "hunter2!"):
    hasher = PasswordHasher(n=1024, r=8, p=1)
    user = UserRepository(session).create(
        username=username,
        password_hash=hasher.hash_password(password),
    )
    session.commit()
    return user


def _audit_events(session) -> list[str]:
    rows = LoginAuditLogRepository(session).list_recent(limit=50)
    return [r.event_type for r in rows]


# ---------- security headers present on key endpoints ----------


def test_security_headers_on_health(session):
    client = _make_client(session)
    try:
        resp = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert "camera=()" in resp.headers.get("Permissions-Policy", "")


def test_security_headers_on_login_endpoint(session):
    client = _make_client(session)
    try:
        resp = client.post("/api/auth/login", json={"username": "x", "password": "y"})
    finally:
        app.dependency_overrides.clear()
    # 401 or 200 -- headers must be present regardless of status
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ---------- brute force lockout ----------


def _make_bf_client(session, *, guard: BruteForceGuard):
    """Create a client with brute force enabled and a custom guard."""
    client = _make_client(session)
    app.state.bruteforce_guard = guard
    app.state.bruteforce_enabled = True
    return client


def test_bruteforce_lockout_returns_generic_401(session):
    guard = BruteForceGuard(max_failures=3, window_seconds=60, lockout_seconds=300)
    _seed_user(session)
    client = _make_bf_client(session, guard=guard)
    try:
        # 3 wrong-password failures to trigger lockout
        for _ in range(3):
            r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
            assert r.status_code == 401
        # 4th request: locked out
        r_locked = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        assert r_locked.status_code == 401
        # Response body must be generic -- same detail as wrong-password
        assert r_locked.json()["detail"] == "invalid username or password"
    finally:
        app.dependency_overrides.clear()
        app.state.bruteforce_enabled = False
        guard.reset()


def test_bruteforce_lockout_same_error_as_wrong_password(session):
    """Lockout response must be indistinguishable from a wrong-password 401."""
    guard = BruteForceGuard(max_failures=2, window_seconds=60, lockout_seconds=300)
    _seed_user(session)
    client = _make_bf_client(session, guard=guard)
    try:
        # Fill up to lockout
        for _ in range(2):
            client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        locked_resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        # Compare with a fresh client (rate limiting disabled) wrong-password response
        app.state.bruteforce_enabled = False
        wrong_pw_resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})

        assert locked_resp.status_code == wrong_pw_resp.status_code
        assert locked_resp.json()["detail"] == wrong_pw_resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        app.state.bruteforce_enabled = False
        guard.reset()


def test_bruteforce_success_resets_counter(session):
    guard = BruteForceGuard(max_failures=3, window_seconds=60, lockout_seconds=300)
    _seed_user(session)
    client = _make_bf_client(session, guard=guard)
    try:
        # 2 failures
        for _ in range(2):
            client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        # Correct login -- resets counter
        ok = client.post("/api/auth/login", json={"username": "alice", "password": "hunter2!"})
        assert ok.status_code == 200
        # 2 more failures: should NOT lock (counter was reset)
        for _ in range(2):
            r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
            assert r.status_code == 401
            assert not guard.is_locked("alice", None)
    finally:
        app.dependency_overrides.clear()
        app.state.bruteforce_enabled = False
        guard.reset()


def test_lockout_audit_recorded_as_lockout_rejected(session):
    guard = BruteForceGuard(max_failures=2, window_seconds=60, lockout_seconds=300)
    _seed_user(session)
    client = _make_bf_client(session, guard=guard)
    try:
        for _ in range(2):
            client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        # Trigger lockout
        client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    finally:
        app.dependency_overrides.clear()
        app.state.bruteforce_enabled = False
        guard.reset()

    events = _audit_events(session)
    assert EVENT_LOCKOUT_REJECTED in events


# ---------- PII / sensitive data guards ----------


def test_source_ip_not_stored_as_plaintext(session):
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "hunter2!"},
            headers={"X-Forwarded-For": "203.0.113.42"},
        )
    finally:
        app.dependency_overrides.clear()
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    assert rows, "Expected at least one audit row"
    for row in rows:
        if row.source_ip_hash is not None:
            assert row.source_ip_hash != "203.0.113.42"
            assert len(row.source_ip_hash) == 64
            assert re.fullmatch(r"[0-9a-f]{64}", row.source_ip_hash)


def test_user_agent_not_stored_as_plaintext(session):
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    ua = "Mozilla/5.0 TestBrowser/9"
    try:
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "anything"},
            headers={"User-Agent": ua},
        )
    finally:
        app.dependency_overrides.clear()
    rows = LoginAuditLogRepository(session).list_recent(limit=10)
    for row in rows:
        if row.user_agent_hash is not None:
            assert row.user_agent_hash != ua
            assert re.fullmatch(r"[0-9a-f]{64}", row.user_agent_hash)


def test_login_response_does_not_leak_sensitive_fields(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "hunter2!"},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    flat = repr(resp.json()).lower()
    for forbidden in ("password", "scrypt$", "password_hash", "jwt_secret"):
        assert forbidden not in flat, f"Forbidden field '{forbidden}' found in response"


# ---------- endpoint count guard ----------


def test_mutating_endpoint_count_unchanged(session):
    """Verify POST/PUT/PATCH/DELETE count matches the known set.

    v0.9 Phase C adds:
      PATCH  /api/watchlists/{id}              (rename / set_default)
      DELETE /api/watchlists/{id}              (delete watchlist)
      GET    /api/watchlists/{id}/items        (paginated -- NOT mutating, skipped)
      PATCH  /api/watchlists/{id}/items/{sym}  (memo update)
      PUT    /api/users/me/preferences         (replace preferences)

    v0.14 Phase D adds (paper / simulation trading only -- KIS / real
    broker / autotrade still 0 routes):
      POST   /api/paper/orders                 (SimulationBroker.submit_order)
      DELETE /api/paper/orders/{id}            (SimulationBroker.cancel_order)

    v0.15 Phase D adds (Approval Workflow only -- still 0 KIS / real
    broker; approved candidates are forwarded to SimulationBroker only):
      POST   /api/approvals/candidates         (create + risk-check)
      POST   /api/approvals/{id}/approve       (paper execution only)
      POST   /api/approvals/{id}/reject
      POST   /api/approvals/{id}/expire

    Total mutating: auth(2) + watchlist(6) + preferences(1) + paper(2) + approvals(4) = 15.
    POST /api/auth/register is not present (single-user, no self-registration).
    """
    from app.main import app as _app

    mutating = [
        (r.methods, r.path)
        for r in _app.routes
        if hasattr(r, "methods") and r.methods & {"POST", "PUT", "PATCH", "DELETE"}
    ]
    assert len(mutating) == 15, (
        f"Expected 15 mutating endpoints (auth 2 + watchlist 6 + preferences 1 "
        f"+ paper 2 + approvals 4), found {len(mutating)}: {mutating}"
    )


# ---------- auto-trade guard ----------


def test_no_auto_trade_strings_in_routes(session):
    """Reject KIS / real-broker / autotrade keywords in route paths.

    v0.14 Phase D legitimately introduces ``/api/paper/orders`` for
    in-process simulation. v0.15 Phase D introduces ``/api/approvals/...``
    for the safety / approval workflow whose mutations forward only to
    ``SimulationBroker.submit_order`` (paper execution). v0.16 Phase E
    introduces ``/api/real-orders`` as a read-only (GET only) view of
    DRY_RUN records — no real KIS calls; no mutations.
    The guard still rejects ``broker / auto_trade / full_auto / small_auto``
    outright, plus any ``order`` path NOT under ``/api/paper/`` or
    ``/api/real-orders``, and any ``approval`` path NOT under
    ``/api/approvals/``.
    """
    from app.main import app as _app

    forbidden_patterns = re.compile(
        r"broker|auto_trade|full_auto|small_auto", re.IGNORECASE
    )
    order_pattern = re.compile(r"order", re.IGNORECASE)
    approval_pattern = re.compile(r"approval", re.IGNORECASE)
    # Allowlisted order paths: paper simulation + v0.16 dry-run read-only view.
    _ALLOWED_ORDER_PREFIXES = ("/api/paper/", "/api/real-orders")
    for route in _app.routes:
        path = getattr(route, "path", "")
        assert not forbidden_patterns.search(path), (
            f"Forbidden pattern found in route path: {path}"
        )
        if approval_pattern.search(path):
            assert path.startswith("/api/approvals/") or path == "/api/approvals", (
                f"Route {path!r} contains 'approval' but is NOT under "
                f"/api/approvals/. Real-broker / KIS approval endpoints are "
                f"forbidden; only the v0.15 paper-execution Approval "
                f"Workflow is allowed."
            )
        if order_pattern.search(path):
            assert any(path.startswith(p) for p in _ALLOWED_ORDER_PREFIXES), (
                f"Route {path!r} contains 'order' but is NOT under an allowed "
                f"prefix {_ALLOWED_ORDER_PREFIXES}. Real broker / KIS order "
                f"endpoints are forbidden; only paper simulation or the v0.16 "
                f"dry-run read-only endpoint is allowed."
            )
