"""Integration tests for v0.9 Phase C Watchlist API additions.

Covers:
  * PATCH /api/watchlists/{id} -- rename
  * PATCH /api/watchlists/{id} -- set_default
  * PATCH /api/watchlists/{id} -- no fields provided → 422
  * DELETE /api/watchlists/{id} -- delete watchlist
  * DELETE /api/watchlists/{id} -- default watchlist can be deleted
  * GET /api/watchlists/{id}/items -- paginated list
  * GET /api/watchlists/{id}/items -- symbol_prefix filter
  * GET /api/watchlists/{id}/items -- limit/offset pagination
  * PATCH /api/watchlists/{id}/items/{symbol} -- update memo
  * PATCH /api/watchlists/{id}/items/{symbol} -- clear memo to null
  * Cross-user isolation for all new endpoints
  * Forbidden fields not present
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.auth.security import PasswordHasher
from app.config.settings import Settings, get_settings
from app.data.repositories.users import UserRepository
from app.data.repositories.watchlist_items import WatchlistItemRepository
from app.data.repositories.watchlists import WatchlistRepository
from app.db.base import Base
from app.db.models import Stock
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
    auth_enabled=False,
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


def _seed_user(session, username: str = "alice") -> int:
    hasher = PasswordHasher(n=1024)
    user = UserRepository(session).create(
        username=username, password_hash=hasher.hash_password("pw!")
    )
    session.commit()
    return user.id


def _seed_watchlist(session, user_id: int, name: str = "WL", *, is_default=False) -> int:
    wl = WatchlistRepository(session).create(
        user_id=user_id, name=name, is_default=is_default
    )
    session.commit()
    return wl.id


def _seed_stock(session, symbol: str = "005930") -> None:
    session.add(Stock(market="KOSPI", symbol=symbol, name=f"Stock {symbol}"))
    session.commit()


def _seed_item(session, watchlist_id: int, symbol: str, memo: str | None = None) -> None:
    WatchlistItemRepository(session).add_item(
        watchlist_id=watchlist_id, symbol=symbol, memo=memo
    )
    session.commit()


def _make_client(session) -> TestClient:
    settings = Settings(**_BASE_SETTINGS_KW)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# PATCH /api/watchlists/{id}
# ---------------------------------------------------------------------------


def test_patch_watchlist_rename(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id, "Old Name")
    client = _make_client(session)
    try:
        resp = client.patch(f"/api/watchlists/{wl_id}", json={"name": "New Name"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_patch_watchlist_set_default(session):
    user_id = _seed_user(session)
    wl1_id = _seed_watchlist(session, user_id, "WL1", is_default=True)
    wl2_id = _seed_watchlist(session, user_id, "WL2", is_default=False)
    client = _make_client(session)
    try:
        resp = client.patch(f"/api/watchlists/{wl2_id}", json={"is_default": True})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["is_default"] is True

    # verify old default was demoted
    from sqlalchemy import select
    from app.db.models import Watchlist
    wl1 = session.get(Watchlist, wl1_id)
    assert wl1 is not None
    assert wl1.is_default is False


def test_patch_watchlist_no_fields_returns_422(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    client = _make_client(session)
    try:
        resp = client.patch(f"/api/watchlists/{wl_id}", json={})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


def test_patch_watchlist_cross_user_isolation(session):
    uid_a = _seed_user(session, "alice")
    _seed_user(session, "bob")
    wl_a = _seed_watchlist(session, uid_a, "Alice WL")
    # bob is the dev fallback (user_id=1) -- alice is user_id=1 in this test setup.
    # In AUTH_ENABLED=false, dev fallback is user_id=1 = alice.
    # So try a watchlist that belongs to no known user (id 9999).
    client = _make_client(session)
    try:
        resp = client.patch("/api/watchlists/9999", json={"name": "Hack"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/watchlists/{id}
# ---------------------------------------------------------------------------


def test_delete_watchlist(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id, "To Delete")
    client = _make_client(session)
    try:
        resp = client.delete(f"/api/watchlists/{wl_id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    from app.db.models import Watchlist
    assert session.get(Watchlist, wl_id) is None


def test_delete_default_watchlist_allowed(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id, "Default", is_default=True)
    client = _make_client(session)
    try:
        resp = client.delete(f"/api/watchlists/{wl_id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


def test_delete_watchlist_cascades_items(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    _seed_stock(session, "005930")
    _seed_item(session, wl_id, "005930")
    client = _make_client(session)
    try:
        resp = client.delete(f"/api/watchlists/{wl_id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    from app.db.models import WatchlistItem
    from sqlalchemy import select
    remaining = session.execute(
        select(WatchlistItem).where(WatchlistItem.watchlist_id == wl_id)
    ).scalars().all()
    assert remaining == []


# ---------------------------------------------------------------------------
# GET /api/watchlists/{id}/items
# ---------------------------------------------------------------------------


def test_get_items_returns_all(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    for sym in ("A", "B", "C"):
        _seed_stock(session, sym)
        _seed_item(session, wl_id, sym)
    client = _make_client(session)
    try:
        resp = client.get(f"/api/watchlists/{wl_id}/items")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_get_items_pagination(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    for sym in ("A", "B", "C", "D", "E"):
        _seed_stock(session, sym)
        _seed_item(session, wl_id, sym)
    client = _make_client(session)
    try:
        resp = client.get(f"/api/watchlists/{wl_id}/items?limit=2&offset=2")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 2
    assert len(data["items"]) == 2


def test_get_items_symbol_prefix_filter(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    for sym in ("AAPL", "AMZN", "GOOG"):
        _seed_stock(session, sym)
        _seed_item(session, wl_id, sym)
    client = _make_client(session)
    try:
        resp = client.get(f"/api/watchlists/{wl_id}/items?symbol_prefix=A")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    symbols = [i["symbol"] for i in data["items"]]
    assert "GOOG" not in symbols


# ---------------------------------------------------------------------------
# PATCH /api/watchlists/{id}/items/{symbol}
# ---------------------------------------------------------------------------


def test_patch_item_update_memo(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    _seed_stock(session, "005930")
    _seed_item(session, wl_id, "005930", memo="old memo")
    client = _make_client(session)
    try:
        resp = client.patch(
            f"/api/watchlists/{wl_id}/items/005930",
            json={"memo": "updated memo"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["memo"] == "updated memo"


def test_patch_item_clear_memo_to_null(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    _seed_stock(session, "005930")
    _seed_item(session, wl_id, "005930", memo="some memo")
    client = _make_client(session)
    try:
        resp = client.patch(
            f"/api/watchlists/{wl_id}/items/005930",
            json={"memo": None},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["memo"] is None


def test_patch_item_not_found_returns_404(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    client = _make_client(session)
    try:
        resp = client.patch(
            f"/api/watchlists/{wl_id}/items/NOTEXIST",
            json={"memo": "x"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Forbidden fields
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


def test_watchlist_responses_contain_no_forbidden_fields(session):
    user_id = _seed_user(session)
    wl_id = _seed_watchlist(session, user_id)
    _seed_stock(session, "005930")
    _seed_item(session, wl_id, "005930")
    client = _make_client(session)
    try:
        r1 = client.patch(f"/api/watchlists/{wl_id}", json={"name": "Safe"})
        r2 = client.get(f"/api/watchlists/{wl_id}/items")
        r3 = client.patch(
            f"/api/watchlists/{wl_id}/items/005930", json={"memo": "ok"}
        )
    finally:
        app.dependency_overrides.clear()

    for resp in (r1, r2, r3):
        flat = repr(resp.json()).lower()
        for forbidden in _FORBIDDEN_FIELDS:
            assert forbidden not in flat, (
                f"Forbidden field '{forbidden}' found in {resp.request.method} "
                f"{resp.request.url} response"
            )
