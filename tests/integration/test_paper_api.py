"""Integration tests for v0.14 Phase D Paper Trading API.

Endpoints under test:

    GET    /api/paper/account
    GET    /api/paper/orders
    GET    /api/paper/positions
    GET    /api/paper/pnl
    POST   /api/paper/orders
    DELETE /api/paper/orders/{id}

Invariants verified:
  * GET endpoints work whether ``paper_trading_enabled`` is True or False.
  * Mutation endpoints return 503 when ``paper_trading_enabled`` is False.
  * Mutation endpoints write through SimulationBroker (status=CREATED for
    POST, status=CANCELED for DELETE) and never touch KIS.
  * Idempotency: POST with the same idempotency_key returns the existing
    order with ``deduplicated=True`` and writes no extra row.
  * Cancel of a terminal-state order returns 422.
  * AUTH gate: when ``auth_enabled=True``, mutations require Bearer.
  * Forbidden response fields (api_key / token / secret / source_file_path /
    broker_order_id / kis_order_id / real_account / broker / account_number /
    raw_text / body / full_text) NEVER appear in any response body.
  * Source-AST guard: ``app/api/paper_routes.py`` imports nothing from
    KIS / DART / RSS / requests / httpx / urllib.
"""

from __future__ import annotations

import ast
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import VirtualPositionRepository
from app.db.base import Base
from app.db.session import create_session_factory, get_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Forbidden fields
# ---------------------------------------------------------------------------


_FORBIDDEN_FIELDS = (
    "api_key",
    "token",
    "secret",
    "source_file_path",
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "broker",
    "account_number",
    "raw_text",
    "body",
    "full_text",
)


def _assert_no_forbidden_fields(payload) -> None:
    """Recursive walk over a JSON-decoded response asserting no banned key."""
    text = json.dumps(payload, ensure_ascii=False)
    for needle in _FORBIDDEN_FIELDS:
        assert f'"{needle}"' not in text, (
            f"forbidden field {needle!r} unexpectedly present in response: "
            f"{payload!r}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_settings(*, paper_trading_enabled: bool, auth_enabled: bool = False):
    return Settings(
        app_env="test",
        app_name="stock_ai_platform",
        timezone="Asia/Seoul",
        log_level="INFO",
        telegram_enabled=False,
        scheduler_enabled=False,
        rate_limit_enabled=False,
        security_headers_enabled=False,
        auth_bruteforce_enabled=False,
        sentry_enabled=False,
        paper_trading_enabled=paper_trading_enabled,
        auth_enabled=auth_enabled,
        jwt_secret="x" * 32 if auth_enabled else None,
        password_hash_n=1024,
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


def _client_with(session, settings):
    """Return a (TestClient, cleanup) pair sharing the given session/settings."""
    from app.main import app

    def override_session():
        yield session

    def override_settings():
        return settings

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    client = TestClient(app)
    return client, lambda: app.dependency_overrides.clear()


@pytest.fixture()
def client_disabled(session):
    client, cleanup = _client_with(
        session, _build_settings(paper_trading_enabled=False)
    )
    try:
        yield client
    finally:
        cleanup()


@pytest.fixture()
def client_enabled(session):
    client, cleanup = _client_with(
        session, _build_settings(paper_trading_enabled=True)
    )
    try:
        yield client
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_account(session, *, name="paper", initial_cash=Decimal("1000000")):
    repo = VirtualAccountRepository(session)
    acc = repo.create(name=name, initial_cash=initial_cash)
    session.commit()
    return acc


def _seed_close(session, *, symbol, price_date, close):
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1000,
    )
    session.commit()


# ---------------------------------------------------------------------------
# GET /api/paper/account
# ---------------------------------------------------------------------------


def test_get_account_returns_404_when_no_account(client_disabled):
    resp = client_disabled.get("/api/paper/account")
    assert resp.status_code == 404


def test_get_account_returns_aggregate_with_latest_snapshot(client_disabled, session):
    acc = _seed_account(session)
    snaps = VirtualPnLSnapshotRepository(session)
    snaps.create_or_replace_snapshot(
        account_id=acc.id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("900000"),
        market_value=Decimal("150000"),
        realized_pnl=Decimal("100"),
        unrealized_pnl=Decimal("-200"),
    )
    session.commit()

    resp = client_disabled.get("/api/paper/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == acc.id
    # Numeric(18,4) → preserves trailing zeros in str(Decimal)
    assert Decimal(body["cash_balance"]) == Decimal("1000000")
    assert Decimal(body["market_value"]) == Decimal("150000")
    assert Decimal(body["total_value"]) == Decimal("1050000")
    assert Decimal(body["realized_pnl"]) == Decimal("100")
    assert Decimal(body["unrealized_pnl"]) == Decimal("-200")
    assert body["snapshot_date"] == "2026-05-08"
    _assert_no_forbidden_fields(body)


# ---------------------------------------------------------------------------
# GET /api/paper/orders
# ---------------------------------------------------------------------------


def test_get_orders_returns_paginated_list_with_filters(client_disabled, session):
    acc = _seed_account(session)
    orders = VirtualOrderRepository(session)
    orders.create(account_id=acc.id, symbol="005930", side="BUY", quantity=1)
    orders.create(account_id=acc.id, symbol="000660", side="BUY", quantity=2)
    o3 = orders.create(account_id=acc.id, symbol="005930", side="SELL", quantity=1)
    orders.update_status(o3, new_status="CANCELED")
    session.commit()

    # No filter: 3 rows.
    resp = client_disabled.get("/api/paper/orders")
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 3
    _assert_no_forbidden_fields(body)

    # status filter.
    resp = client_disabled.get("/api/paper/orders?status=CANCELED")
    assert resp.json()["total"] == 1

    # symbol filter (case-insensitive).
    resp = client_disabled.get("/api/paper/orders?symbol=005930")
    assert resp.json()["total"] == 2

    # limit.
    resp = client_disabled.get("/api/paper/orders?limit=1")
    assert len(resp.json()["orders"]) == 1


# ---------------------------------------------------------------------------
# GET /api/paper/positions
# ---------------------------------------------------------------------------


def test_get_positions_includes_market_value_when_price_present(
    client_disabled, session
):
    acc = _seed_account(session)
    VirtualPositionRepository(session).apply_buy(
        account_id=acc.id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("10000"),
        cash_spent=Decimal("100000"),
    )
    session.commit()
    _seed_close(
        session,
        symbol="005930",
        price_date=date.today(),
        close=Decimal("11000"),
    )

    resp = client_disabled.get("/api/paper/positions")
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 1
    pos = body["positions"][0]
    assert pos["symbol"] == "005930"
    assert pos["quantity"] == 10
    assert Decimal(pos["last_close"]) == Decimal("11000")
    assert Decimal(pos["market_value"]) == Decimal("110000")
    # avg_cost = 100,000 / 10 = 10,000; unrealized = 110,000 - 10,000*10 = 10,000
    assert Decimal(pos["unrealized_pnl"]) == Decimal("10000")
    _assert_no_forbidden_fields(body)


def test_get_positions_excludes_closed_unless_include_closed(client_disabled, session):
    acc = _seed_account(session)
    repo = VirtualPositionRepository(session)
    repo.apply_buy(
        account_id=acc.id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("10000"),
        cash_spent=Decimal("100000"),
    )
    repo.apply_sell(
        account_id=acc.id,
        symbol="005930",
        fill_quantity=10,
        cash_received=Decimal("110000"),
    )
    session.commit()

    resp = client_disabled.get("/api/paper/positions")
    assert resp.json()["total"] == 0  # quantity is 0 → excluded by default

    resp = client_disabled.get("/api/paper/positions?include_closed=true")
    body = resp.json()
    assert body["total"] == 1
    assert body["positions"][0]["quantity"] == 0


# ---------------------------------------------------------------------------
# GET /api/paper/pnl
# ---------------------------------------------------------------------------


def test_get_pnl_returns_snapshot_timeseries_with_date_range(client_disabled, session):
    acc = _seed_account(session)
    snaps = VirtualPnLSnapshotRepository(session)
    for d in (date(2026, 5, 6), date(2026, 5, 7), date(2026, 5, 8)):
        snaps.create_or_replace_snapshot(
            account_id=acc.id,
            snapshot_date=d,
            cash_balance=Decimal("1000000"),
            market_value=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
    session.commit()

    resp = client_disabled.get(
        "/api/paper/pnl?from_date=2026-05-07&to_date=2026-05-08"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [s["snapshot_date"] for s in body["snapshots"]] == [
        "2026-05-07",
        "2026-05-08",
    ]
    _assert_no_forbidden_fields(body)


def test_get_pnl_rejects_inverted_date_range(client_disabled, session):
    _seed_account(session)
    resp = client_disabled.get(
        "/api/paper/pnl?from_date=2026-05-09&to_date=2026-05-08"
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/paper/orders
# ---------------------------------------------------------------------------


def test_post_order_returns_503_when_paper_trading_disabled(client_disabled, session):
    _seed_account(session)
    resp = client_disabled.post(
        "/api/paper/orders",
        json={"symbol": "005930", "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"].lower()
    assert "paper trading" in detail and "disabled" in detail
    # No order was written.
    assert VirtualOrderRepository(session).list_by_account(1) == []


def test_post_order_creates_virtual_order_when_enabled(client_enabled, session):
    acc = _seed_account(session)
    resp = client_enabled.post(
        "/api/paper/orders",
        json={"symbol": "005930", "side": "BUY", "quantity": 5},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["deduplicated"] is False
    assert body["order"]["symbol"] == "005930"
    assert body["order"]["status"] == "CREATED"
    _assert_no_forbidden_fields(body)

    persisted = VirtualOrderRepository(session).list_by_account(acc.id)
    assert len(persisted) == 1
    assert persisted[0].quantity == 5


def test_post_order_idempotency_key_returns_existing(client_enabled, session):
    _seed_account(session)
    payload = {
        "symbol": "005930",
        "side": "BUY",
        "quantity": 5,
        "idempotency_key": "abc",
    }
    first = client_enabled.post("/api/paper/orders", json=payload)
    second = client_enabled.post("/api/paper/orders", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["order"]["id"] == second.json()["order"]["id"]
    assert first.json()["deduplicated"] is False
    assert second.json()["deduplicated"] is True


def test_post_order_validates_invalid_quantity(client_enabled, session):
    _seed_account(session)
    resp = client_enabled.post(
        "/api/paper/orders",
        json={"symbol": "005930", "side": "BUY", "quantity": 0},
    )
    assert resp.status_code == 422


def test_post_limit_order_requires_limit_price(client_enabled, session):
    _seed_account(session)
    resp = client_enabled.post(
        "/api/paper/orders",
        json={
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1,
            "order_type": "LIMIT",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/paper/orders/{id}
# ---------------------------------------------------------------------------


def test_delete_order_cancels_pending_order(client_enabled, session):
    acc = _seed_account(session)
    order = VirtualOrderRepository(session).create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    session.commit()

    resp = client_enabled.delete(
        f"/api/paper/orders/{order.id}?reason=ops"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    fresh = VirtualOrderRepository(session).get_by_id(order.id)
    assert fresh.status == "CANCELED"
    assert fresh.reason == "ops"


def test_delete_order_returns_503_when_disabled(client_disabled, session):
    acc = _seed_account(session)
    order = VirtualOrderRepository(session).create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    session.commit()
    resp = client_disabled.delete(f"/api/paper/orders/{order.id}")
    assert resp.status_code == 503


def test_delete_terminal_order_returns_422(client_enabled, session):
    acc = _seed_account(session)
    order = VirtualOrderRepository(session).create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    VirtualOrderRepository(session).update_status(order, new_status="FILLED")
    session.commit()
    resp = client_enabled.delete(f"/api/paper/orders/{order.id}")
    assert resp.status_code == 422


def test_delete_unknown_order_returns_404(client_enabled, session):
    resp = client_enabled.delete("/api/paper/orders/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AUTH gate
# ---------------------------------------------------------------------------


def test_post_order_requires_bearer_when_auth_enabled(session):
    _seed_account(session)
    settings = _build_settings(paper_trading_enabled=True, auth_enabled=True)
    client, cleanup = _client_with(session, settings)
    try:
        resp = client.post(
            "/api/paper/orders",
            json={"symbol": "005930", "side": "BUY", "quantity": 1},
        )
        assert resp.status_code == 401
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# Forbidden imports in the route module
# ---------------------------------------------------------------------------


_FORBIDDEN_MODULES = {"requests", "httpx", "urllib", "urllib3"}
_FORBIDDEN_PREFIXES = (
    "app.kis",
    "app.data.dart_provider",
    "app.data.rss_provider",
    "app.data.collectors.kis_client",
)


def test_paper_routes_module_has_no_forbidden_imports():
    src = (PROJECT_ROOT / "app" / "api" / "paper_routes.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in _FORBIDDEN_MODULES or any(
                    a.name == p or a.name.startswith(p + ".")
                    for p in _FORBIDDEN_PREFIXES
                ):
                    leaks.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _FORBIDDEN_MODULES or any(
                module == p or module.startswith(p + ".")
                for p in _FORBIDDEN_PREFIXES
            ):
                leaks.append(f"from {module}")
    assert leaks == [], (
        f"paper_routes.py unexpectedly imports forbidden modules: {leaks!r}"
    )


# ---------------------------------------------------------------------------
# Mutation methods 405-out for read-only paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("post", "/api/paper/account"),
        ("delete", "/api/paper/account"),
        ("post", "/api/paper/positions"),
        ("delete", "/api/paper/positions"),
        ("post", "/api/paper/pnl"),
        ("delete", "/api/paper/pnl"),
    ],
)
def test_read_only_endpoints_reject_mutation_methods(
    client_enabled, session, method, endpoint
):
    _seed_account(session)
    resp = getattr(client_enabled, method)(endpoint)
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Forbidden fields never appear on a populated response
# ---------------------------------------------------------------------------


def test_forbidden_fields_absent_from_full_response_set(client_enabled, session):
    acc = _seed_account(session)
    # Seed: order, position, snapshot, daily price.
    order = VirtualOrderRepository(session).create(
        account_id=acc.id, symbol="005930", side="BUY", quantity=1
    )
    VirtualPositionRepository(session).apply_buy(
        account_id=acc.id,
        symbol="005930",
        fill_quantity=1,
        fill_price=Decimal("10000"),
        cash_spent=Decimal("10000"),
    )
    VirtualPnLSnapshotRepository(session).create_or_replace_snapshot(
        account_id=acc.id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("990000"),
        market_value=Decimal("11000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("1000"),
    )
    _seed_close(
        session, symbol="005930", price_date=date.today(), close=Decimal("11000")
    )
    session.commit()

    for path in (
        "/api/paper/account",
        "/api/paper/orders",
        "/api/paper/positions",
        "/api/paper/pnl",
    ):
        resp = client_enabled.get(path)
        assert resp.status_code == 200
        _assert_no_forbidden_fields(resp.json())
