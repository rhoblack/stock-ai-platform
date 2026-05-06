"""End-to-end tests for v0.8 Phase C Watchlist API routes.

Operating modes covered:
  * AUTH_ENABLED=false (dev / CI default) -- routes resolve to user_id=1 via
    require_auth's dev fallback.
  * AUTH_ENABLED=true (prod-like) -- a Bearer token from POST /api/auth/login
    is required. Cross-user requests collapse to 404 to avoid leaking
    ownership.

Forbidden field hygiene: every response body is recursively scanned for
`broker`, `account`, `quantity`, `order_*`, `source_file_path`,
`password_hash`, `token`, `secret`, `jwt_secret`. Any leak fails the test.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.auth.security import PasswordHasher
from app.config.settings import Settings, get_settings
from app.data.repositories.stocks import StockRepository
from app.data.repositories.users import UserRepository
from app.data.repositories.watchlists import WatchlistRepository
from app.db import Base
from app.db.models import Stock
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


_FORBIDDEN_FIELDS = {
    "broker",
    "account",
    "quantity",
    "order_price",
    "order_type",
    "side",
    "buy_price",
    "sell_price",
    "source_file_path",
    "password_hash",
    "password",
    "token",
    "secret",
    "jwt_secret",
}


def _assert_no_forbidden_fields(value, *, where: str = "<root>") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert key not in _FORBIDDEN_FIELDS, (
                f"forbidden field {key!r} present at {where}.{key}"
            )
            _assert_no_forbidden_fields(child, where=f"{where}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            _assert_no_forbidden_fields(child, where=f"{where}[{idx}]")
    elif isinstance(value, str):
        # access_token from a different endpoint should never appear here.
        # Guard against accidentally serialising hashes / scrypt blocks.
        assert "scrypt$" not in value, f"scrypt$ leaked into {where}"


@pytest.fixture()
def session() -> Iterator:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
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
    session, *, username: str = "alice", user_id: int | None = None
):
    """Insert a user; if ``user_id`` is given, use it (so dev fallback id=1
    matches an existing row)."""
    hasher = PasswordHasher(n=1024, r=8, p=1)
    repo = UserRepository(session)
    user = repo.create(
        username=username,
        password_hash=hasher.hash_password("hunter2!"),
        is_admin=True,
    )
    if user_id is not None and user.id != user_id:
        # Force a specific id (only useful when the table is empty).
        user.id = user_id
        session.flush()
    session.commit()
    return user


def _seed_stock(session, *, symbol: str, name: str = "삼성전자") -> Stock:
    stock = StockRepository(session).add(
        Stock(symbol=symbol, name=name, market="KOSPI", sector="전기전자"),
    )
    session.commit()
    return stock


def _login_token(client, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# AUTH_ENABLED=false (dev / CI fallback)
# ---------------------------------------------------------------------------


def test_list_watchlists_empty_when_auth_disabled(session):
    _seed_user(session, user_id=1)  # dev fallback uses id=1
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.get("/api/watchlists")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"watchlists": []}
    _assert_no_forbidden_fields(body, where="GET /api/watchlists")


def test_create_watchlist_then_list_includes_it(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        create = client.post(
            "/api/watchlists", json={"name": "단기", "is_default": True}
        )
        listed = client.get("/api/watchlists")
    finally:
        client.app.dependency_overrides.clear()
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "단기"
    assert body["is_default"] is True
    assert body["item_count"] == 0
    _assert_no_forbidden_fields(body, where="POST /api/watchlists")

    assert listed.status_code == 200
    listed_body = listed.json()
    assert len(listed_body["watchlists"]) == 1
    assert listed_body["watchlists"][0]["name"] == "단기"


def test_create_watchlist_duplicate_name_409(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        client.post("/api/watchlists", json={"name": "dup"})
        dup = client.post("/api/watchlists", json={"name": "dup"})
    finally:
        client.app.dependency_overrides.clear()
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]


def test_create_watchlist_empty_name_422(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.post("/api/watchlists", json={"name": "   "})
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_create_second_default_demotes_first(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        a = client.post(
            "/api/watchlists", json={"name": "A", "is_default": True}
        ).json()
        b = client.post(
            "/api/watchlists", json={"name": "B", "is_default": True}
        ).json()
        listed = client.get("/api/watchlists").json()
    finally:
        client.app.dependency_overrides.clear()
    assert a["is_default"] is True
    assert b["is_default"] is True
    defaults = [w for w in listed["watchlists"] if w["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "B"


def test_get_watchlist_detail_contains_items(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="005930")
    _seed_stock(session, symbol="000660", name="SK하이닉스")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        wl_id = wl["id"]
        client.post(
            f"/api/watchlists/{wl_id}/items",
            json={"symbol": "005930", "memo": "삼전 메모"},
        )
        client.post(
            f"/api/watchlists/{wl_id}/items", json={"symbol": "000660"}
        )
        detail = client.get(f"/api/watchlists/{wl_id}")
    finally:
        client.app.dependency_overrides.clear()
    assert detail.status_code == 200
    body = detail.json()
    assert body["item_count"] == 2
    symbols = sorted(item["symbol"] for item in body["items"])
    assert symbols == ["000660", "005930"]
    _assert_no_forbidden_fields(body, where=f"GET /api/watchlists/{wl_id}")


def test_get_watchlist_404_for_missing_id(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        resp = client.get("/api/watchlists/999")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404


def test_add_item_normalizes_symbol(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="AAPL", name="Apple")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        resp = client.post(
            f"/api/watchlists/{wl['id']}/items",
            json={"symbol": "  aapl ", "memo": "tech"},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "AAPL"


def test_add_item_duplicate_returns_409(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="005930")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        client.post(
            f"/api/watchlists/{wl['id']}/items", json={"symbol": "005930"}
        )
        dup = client.post(
            f"/api/watchlists/{wl['id']}/items", json={"symbol": "005930"}
        )
    finally:
        client.app.dependency_overrides.clear()
    assert dup.status_code == 409


def test_add_item_unknown_symbol_returns_404(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        resp = client.post(
            f"/api/watchlists/{wl['id']}/items", json={"symbol": "999999"}
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404
    assert "stocks" in resp.json()["detail"]


def test_add_item_memo_too_long_returns_422(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="005930")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        resp = client.post(
            f"/api/watchlists/{wl['id']}/items",
            json={"symbol": "005930", "memo": "x" * 501},
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 422


def test_remove_item_success(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="005930")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        client.post(
            f"/api/watchlists/{wl['id']}/items", json={"symbol": "005930"}
        )
        resp = client.delete(f"/api/watchlists/{wl['id']}/items/005930")
        listed = client.get(f"/api/watchlists/{wl['id']}").json()
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert listed["items"] == []


def test_remove_item_normalizes_path_symbol(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="AAPL", name="Apple")
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        client.post(
            f"/api/watchlists/{wl['id']}/items", json={"symbol": "AAPL"}
        )
        # FastAPI strips trailing whitespace/slashes; lowercase is normalised
        # by the repository before deletion.
        resp = client.delete(f"/api/watchlists/{wl['id']}/items/aapl")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200


def test_remove_item_missing_returns_404(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=False)
    try:
        wl = client.post("/api/watchlists", json={"name": "L"}).json()
        resp = client.delete(f"/api/watchlists/{wl['id']}/items/999999")
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AUTH_ENABLED=true
# ---------------------------------------------------------------------------


def test_list_watchlists_requires_token_when_auth_enabled(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        no_header = client.get("/api/watchlists")
        bad_token = client.get(
            "/api/watchlists", headers={"Authorization": "Bearer not.a.jwt"}
        )
    finally:
        client.app.dependency_overrides.clear()
    assert no_header.status_code == 401
    assert bad_token.status_code == 401
    for resp in (no_header, bad_token):
        assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_list_watchlists_with_token(session):
    _seed_user(session, user_id=1)
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        token = _login_token(client, "alice", "hunter2!")
        resp = client.get("/api/watchlists", headers=_bearer(token))
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"watchlists": []}
    _assert_no_forbidden_fields(body, where="GET /api/watchlists (auth=true)")


def test_cross_user_watchlist_returns_404(session):
    alice = _seed_user(session, username="alice", user_id=1)
    bob = _seed_user(session, username="bob")
    bob_wl = WatchlistRepository(session).create(
        user_id=bob.id, name="bob-list"
    )
    session.commit()
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        token = _login_token(client, "alice", "hunter2!")
        resp = client.get(
            f"/api/watchlists/{bob_wl.id}", headers=_bearer(token)
        )
        # Adding to Bob's list also collapses to 404.
        add = client.post(
            f"/api/watchlists/{bob_wl.id}/items",
            json={"symbol": "005930"},
            headers=_bearer(token),
        )
        # As does deletion attempts.
        delete = client.delete(
            f"/api/watchlists/{bob_wl.id}/items/005930",
            headers=_bearer(token),
        )
    finally:
        client.app.dependency_overrides.clear()
    assert resp.status_code == 404
    assert add.status_code == 404
    assert delete.status_code == 404


def test_request_body_user_id_is_ignored(session):
    """A malicious client cannot impersonate another user via request body.

    Pydantic models for create / add-item have NO user_id field, so any
    extra key is silently dropped. We confirm by sending a spoofed payload
    and asserting the row was assigned to the authenticated user, not the
    spoofed value."""
    _seed_user(session, user_id=1)  # alice
    bob = _seed_user(session, username="bob")
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        token = _login_token(client, "alice", "hunter2!")
        created = client.post(
            "/api/watchlists",
            # Try to spoof bob's user_id; the schema must drop it.
            json={"name": "spoof", "user_id": bob.id, "owner_id": bob.id},
            headers=_bearer(token),
        )
    finally:
        client.app.dependency_overrides.clear()
    assert created.status_code == 201
    # Confirm via DB that the row is owned by alice (id=1).
    rows = WatchlistRepository(session).list_by_user(1)
    assert any(w.name == "spoof" for w in rows)
    bob_rows = WatchlistRepository(session).list_by_user(bob.id)
    assert all(w.name != "spoof" for w in bob_rows)


def test_response_never_leaks_password_hash_or_token(session):
    _seed_user(session, user_id=1)
    _seed_stock(session, symbol="005930")
    client = _make_client(session, auth_enabled=True, jwt_secret="x" * 32)
    try:
        token = _login_token(client, "alice", "hunter2!")
        wl = client.post(
            "/api/watchlists", json={"name": "L"}, headers=_bearer(token)
        ).json()
        item = client.post(
            f"/api/watchlists/{wl['id']}/items",
            json={"symbol": "005930", "memo": "memo"},
            headers=_bearer(token),
        ).json()
        detail = client.get(
            f"/api/watchlists/{wl['id']}", headers=_bearer(token)
        ).json()
        listed = client.get("/api/watchlists", headers=_bearer(token)).json()
    finally:
        client.app.dependency_overrides.clear()
    for body, where in (
        (wl, "POST /api/watchlists"),
        (item, "POST /items"),
        (detail, "GET /api/watchlists/{id}"),
        (listed, "GET /api/watchlists"),
    ):
        _assert_no_forbidden_fields(body, where=where)
