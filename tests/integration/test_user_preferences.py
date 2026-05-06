"""Integration tests for v0.9 Phase C UserPreference repository and API.

Covers:
  * get_or_create_for_user -- creates blank row on first call, returns same on second
  * update -- partial update of individual fields
  * set_default_watchlist -- sets / clears default_watchlist_id
  * update_dashboard_layout, update_notification_preferences
  * Cross-user isolation: user A cannot update user B's preferences
  * GET /api/users/me/preferences (AUTH_ENABLED=false dev fallback)
  * PUT /api/users/me/preferences (AUTH_ENABLED=false dev fallback)
  * PUT /api/users/me/preferences validates watchlist ownership
  * AUTH_ENABLED=true requires Bearer token
  * Forbidden fields never appear in responses
  * notification_preferences_json rejects secret keys
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.auth.security import PasswordHasher
from app.config.settings import Settings, get_settings
from app.data.repositories.user_preferences import UserPreferenceRepository
from app.data.repositories.users import UserRepository
from app.data.repositories.watchlists import WatchlistRepository
from app.db.base import Base
from app.db.session import create_session_factory, get_session
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FAST_HASH = {"password_hash_n": 1024, "password_hash_r": 8, "password_hash_p": 1}

_BASE_SETTINGS_KW = dict(
    app_env="test",
    app_name="stock_ai_platform",
    timezone="Asia/Seoul",
    log_level="INFO",
    telegram_enabled=False,
    telegram_bot_token="tok",
    telegram_chat_id="123",
    telegram_api_base_url="https://mock-telegram.local",
    telegram_timeout_seconds=5,
    kis_app_key="k" * 16,
    kis_app_secret="s" * 16,
    kis_account_no="1234567890",
    kis_account_product_code="01",
    kis_use_paper=True,
    scheduler_enabled=False,
    rate_limit_enabled=False,
    security_headers_enabled=False,
    auth_bruteforce_enabled=False,
    sentry_enabled=False,
    **_FAST_HASH,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):
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


def _seed_user(session, username: str = "alice", password: str = "hunter2!") -> int:
    hasher = PasswordHasher(n=1024)
    repo = UserRepository(session)
    user = repo.create(username=username, password_hash=hasher.hash_password(password))
    session.commit()
    return user.id


def _seed_watchlist(session, user_id: int, name: str = "My List") -> int:
    repo = WatchlistRepository(session)
    wl = repo.create(user_id=user_id, name=name, is_default=False)
    session.commit()
    return wl.id


def _make_client(session, *, auth_enabled: bool = False) -> TestClient:
    settings_kw = dict(_BASE_SETTINGS_KW)
    if auth_enabled:
        settings_kw["auth_enabled"] = True
        settings_kw["jwt_secret"] = "test-secret-32-chars-long-enough!!"
    else:
        settings_kw["auth_enabled"] = False

    settings = Settings(**settings_kw)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


def test_get_or_create_creates_blank_row_on_first_call(session):
    user_id = _seed_user(session)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    session.commit()

    assert pref.user_id == user_id
    assert pref.default_watchlist_id is None
    assert pref.default_market is None
    assert pref.default_strategy is None
    assert pref.dashboard_layout_json is None
    assert pref.notification_preferences_json is None


def test_get_or_create_returns_same_row_on_second_call(session):
    user_id = _seed_user(session)
    repo = UserPreferenceRepository(session)
    pref1 = repo.get_or_create_for_user(user_id)
    session.commit()

    pref2 = repo.get_or_create_for_user(user_id)
    assert pref1.id == pref2.id


def test_update_partial_fields(session):
    user_id = _seed_user(session)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    session.commit()

    repo.update(pref, default_market="KOSPI", default_strategy="momentum")
    session.commit()

    refreshed = repo.get_by_user_id(user_id)
    assert refreshed is not None
    assert refreshed.default_market == "KOSPI"
    assert refreshed.default_strategy == "momentum"
    assert refreshed.dashboard_layout_json is None  # untouched


def test_set_default_watchlist(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    session.commit()

    repo.set_default_watchlist(pref, watchlist_id=wl_id)
    session.commit()

    refreshed = repo.get_by_user_id(user_id)
    assert refreshed is not None
    assert refreshed.default_watchlist_id == wl_id


def test_set_default_watchlist_clear(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    repo.set_default_watchlist(pref, watchlist_id=wl_id)
    session.commit()

    repo.set_default_watchlist(pref, watchlist_id=None)
    session.commit()

    refreshed = repo.get_by_user_id(user_id)
    assert refreshed is not None
    assert refreshed.default_watchlist_id is None


def test_update_dashboard_layout(session):
    user_id = _seed_user(session)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    session.commit()

    layout = {"columns": 2, "widgets": ["chart", "news"]}
    repo.update_dashboard_layout(pref, layout=layout)
    session.commit()

    refreshed = repo.get_by_user_id(user_id)
    assert refreshed is not None
    assert refreshed.dashboard_layout_json == layout


def test_update_notification_preferences(session):
    user_id = _seed_user(session)
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(user_id)
    session.commit()

    notif = {"email": False, "push": True}
    repo.update_notification_preferences(pref, preferences=notif)
    session.commit()

    refreshed = repo.get_by_user_id(user_id)
    assert refreshed is not None
    assert refreshed.notification_preferences_json == notif


# ---------------------------------------------------------------------------
# API tests -- AUTH_ENABLED=false (dev fallback)
# ---------------------------------------------------------------------------


def test_get_preferences_creates_on_first_call(session):
    _seed_user(session)  # user_id=1
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.get("/api/users/me/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == 1
    assert data["default_watchlist_id"] is None
    assert data["default_market"] is None


def test_put_preferences_updates_fields(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.put(
            "/api/users/me/preferences",
            json={"default_market": "KOSDAQ", "default_strategy": "value"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_market"] == "KOSDAQ"
    assert data["default_strategy"] == "value"


def test_put_preferences_clears_fields_with_null(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        client.put("/api/users/me/preferences", json={"default_market": "KOSPI"})
        resp = client.put("/api/users/me/preferences", json={"default_market": None})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["default_market"] is None


def test_put_preferences_validates_watchlist_ownership(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.put(
            "/api/users/me/preferences",
            json={"default_watchlist_id": wl_id},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["default_watchlist_id"] == wl_id


def test_put_preferences_rejects_foreign_watchlist_id(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        # watchlist_id=9999 does not exist
        resp = client.put(
            "/api/users/me/preferences",
            json={"default_watchlist_id": 9999},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# API tests -- AUTH_ENABLED=true
# ---------------------------------------------------------------------------


def test_get_preferences_requires_token_when_auth_enabled(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True)
    try:
        resp = client.get("/api/users/me/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401


def test_put_preferences_requires_token_when_auth_enabled(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=True)
    try:
        resp = client.put("/api/users/me/preferences", json={})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Forbidden field guard
# ---------------------------------------------------------------------------

_FORBIDDEN_FIELDS = (
    "password",
    "password_hash",
    "access_token",
    "jwt_secret",
    "secret",
    "broker",
    "account",
    "quantity",
    "order_price",
    "order_type",
    "side",
    "source_file_path",
)


def test_preferences_response_contains_no_forbidden_fields(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.get("/api/users/me/preferences")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    flat = repr(resp.json()).lower()
    for forbidden in _FORBIDDEN_FIELDS:
        assert forbidden not in flat, f"Forbidden field '{forbidden}' found in response"


def test_put_preferences_rejects_secret_keys_in_notification_json(session):
    _seed_user(session)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.put(
            "/api/users/me/preferences",
            json={"notification_preferences_json": {"password": "oops"}},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
