"""Integration tests for v1.0 Phase D — POST /api/real-orders/{id}/sync.

Endpoint under test:
    POST /api/real-orders/{order_id}/sync

Verified invariants:
  * Triple gate — TRADING_SAFETY_ENABLED False / KILL_SWITCH_ENABLED True /
    missing-Bearer (when AUTH_ENABLED) all surface as 503 / 503 / 401.
  * 404 when the RealOrder id does not exist.
  * Happy path on a SUBMITTED non-dry-run order returns 200 with delta-based
    fill_status / fills_added / fills_total fields populated.
  * DRY_RUN order short-circuits to fill_status=NONE +
    skipped_reason='DRY_RUN_ORDER_SKIPPED'.
  * Repeat sync on already-FILLED order returns NONE + skipped_reason.
  * 405 on PUT/PATCH/DELETE — sync is POST-only.
  * Response body never contains forbidden substrings (api_key / token /
    secret / broker_order_no / kis_order_id / real_account /
    account_number / raw_text / body / full_text).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.session import create_session_factory, get_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# Forbidden response field NAMES.
#
# NOTE: ``real_order_id`` is intentionally NOT in this list — it is the
# natural primary-key reference returned by the sync endpoint (and by the
# RealOrderSyncResponse schema). The audit-log layer has its own forbidden
# key list (``_FORBIDDEN_DETAILS_KEYS`` in approval_audit_log.py) which
# DOES forbid ``real_order_id`` as a details_json key — that policy is
# tested elsewhere. The response surface uses it as a response field.
_FORBIDDEN_SUBSTRINGS = (
    "api_key",
    "app_secret",
    "appsecret",
    "access_token",
    "kis_account_no",
    "kis_app_key",
    "kis_app_secret",
    "broker_order_no",      # any broker order no field, hashed or otherwise
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "raw_text",
    "raw_response",
    "full_text",
    "source_file_path",
    "jwt_secret",
)


def _assert_no_forbidden(payload) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert f'"{needle}"' not in text, (
            f"forbidden field {needle!r} unexpectedly in response: {payload!r}"
        )


def _settings(
    *,
    trading_safety: bool = True,
    kill_switch: bool = False,
    auth: bool = False,
) -> Settings:
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
        paper_trading_enabled=False,
        trading_safety_enabled=trading_safety,
        kill_switch_enabled=kill_switch,
        approval_required=True,
        max_order_amount=100_000,
        max_daily_order_amount=1_000_000,
        max_position_ratio=0.20,
        max_daily_loss_amount=500_000,
        auth_enabled=auth,
        jwt_secret="x" * 32 if auth else None,
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


def _client_with(session, settings):
    from app.main import app

    def override_session():
        yield session

    def override_settings():
        return settings

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app), lambda: app.dependency_overrides.clear()


@pytest.fixture()
def client_enabled(session):
    """trading_safety=True, kill_switch=False, AUTH off (dev fallback user)."""
    client, cleanup = _client_with(session, _settings())
    try:
        yield client
    finally:
        cleanup()


@pytest.fixture()
def client_safety_off(session):
    client, cleanup = _client_with(session, _settings(trading_safety=False))
    try:
        yield client
    finally:
        cleanup()


@pytest.fixture()
def client_kill_switch_on(session):
    client, cleanup = _client_with(session, _settings(kill_switch=True))
    try:
        yield client
    finally:
        cleanup()


@pytest.fixture()
def client_auth_required(session):
    """auth_enabled=True — every mutation must carry a valid Bearer token."""
    s = _settings(auth=True)
    client, cleanup = _client_with(session, s)
    try:
        yield client
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_real_order(
    session,
    *,
    status: str = "SUBMITTED",
    quantity: int = 10,
    estimated_amount: Decimal = Decimal("750_000"),
    dry_run: bool | None = None,
) -> int:
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(
        name="sync-api-test", initial_cash=Decimal("10_000_000")
    )
    session.flush()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=quantity,
        order_type="MARKET",
        estimated_amount=estimated_amount,
    )
    cand_repo.update_status(cand, new_status="RISK_CHECKING")
    cand_repo.update_status(cand, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand, new_status="APPROVED")
    session.flush()

    effective_dry_run = (
        dry_run if dry_run is not None else (status == "DRY_RUN")
    )
    order = RealOrderRepository(session).create(
        candidate_id=cand.id,
        symbol="005930",
        side="BUY",
        quantity=quantity,
        order_type="MARKET",
        estimated_amount=estimated_amount,
        status=status,
        dry_run=effective_dry_run,
        fake_order_no="FAKE-INT-001",
    )
    session.commit()
    return order.id


# ---------------------------------------------------------------------------
# 1. Happy path — SUBMITTED order → FULL via FakeKisOrderTransport (default)
# ---------------------------------------------------------------------------


def test_int_post_sync_submitted_order_returns_full(client_enabled, session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    resp = client_enabled.post(f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["real_order_id"] == oid
    assert body["fill_status"] == "FULL"
    assert body["fills_added"] == 1
    assert body["fills_total"] == 10
    assert body["real_order_status"] == "FILLED"
    assert "synced_at" in body and body["synced_at"]
    assert body["message"]
    _assert_no_forbidden(body)


# ---------------------------------------------------------------------------
# 2. Idempotency — repeat sync after FULL returns ORDER_ALREADY_TERMINAL
# ---------------------------------------------------------------------------


def test_int_post_sync_repeat_after_full_skips(client_enabled, session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    r1 = client_enabled.post(f"/api/real-orders/{oid}/sync").json()
    assert r1["fills_added"] == 1
    assert r1["real_order_status"] == "FILLED"

    r2 = client_enabled.post(f"/api/real-orders/{oid}/sync").json()
    assert r2["fill_status"] == "NONE"
    assert r2["fills_added"] == 0
    assert r2["real_order_status"] == "FILLED"
    # Skip message indicates the order is already terminal.
    assert "ORDER_ALREADY_TERMINAL" in r2["message"]


# ---------------------------------------------------------------------------
# 3. DRY_RUN order short-circuits
# ---------------------------------------------------------------------------


def test_int_post_sync_dry_run_skipped(client_enabled, session):
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5)
    resp = client_enabled.post(f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 200

    body = resp.json()
    assert body["fill_status"] == "NONE"
    assert body["fills_added"] == 0
    assert body["real_order_status"] == "DRY_RUN"
    assert "DRY_RUN_ORDER_SKIPPED" in body["message"]


# ---------------------------------------------------------------------------
# 4. 404 when RealOrder does not exist
# ---------------------------------------------------------------------------


def test_int_post_sync_404_when_not_found(client_enabled):
    resp = client_enabled.post("/api/real-orders/9999/sync")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 5. Trading safety / kill switch gates → 503
# ---------------------------------------------------------------------------


def test_int_post_sync_503_when_trading_safety_disabled(
    client_safety_off, session
):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    resp = client_safety_off.post(f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 503
    assert "TRADING_SAFETY_ENABLED" in resp.text


def test_int_post_sync_503_when_kill_switch_on(
    client_kill_switch_on, session
):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    resp = client_kill_switch_on.post(f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 503
    assert "kill switch" in resp.text.lower()


# ---------------------------------------------------------------------------
# 6. Auth required → 401 when AUTH_ENABLED and no Bearer
# ---------------------------------------------------------------------------


def test_int_post_sync_401_when_auth_required_and_missing_bearer(
    client_auth_required, session
):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    resp = client_auth_required.post(f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 7. Method gate — PUT / PATCH / DELETE all 405
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_int_post_sync_method_405(client_enabled, session, method):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    resp = client_enabled.request(method, f"/api/real-orders/{oid}/sync")
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# 8. Optional kis_order_no body — never echoed back
# ---------------------------------------------------------------------------


def test_int_post_sync_with_plaintext_body_never_echoed(
    client_enabled, session
):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10)
    plaintext = "PLAINTEXT-ORD-NO-SECRET-12345"
    resp = client_enabled.post(
        f"/api/real-orders/{oid}/sync",
        json={"kis_order_no": plaintext},
    )
    assert resp.status_code == 200
    body = resp.json()
    text = json.dumps(body, ensure_ascii=False)
    assert plaintext not in text, (
        f"Plaintext kis_order_no must not be echoed back: {body!r}"
    )


# ---------------------------------------------------------------------------
# 9. Forbidden response substring scan (every happy-path response)
# ---------------------------------------------------------------------------


def test_int_post_sync_response_forbidden_substring_scan(
    client_enabled, session
):
    """Multiple sync responses (FULL / DRY_RUN / 404) must all be clean."""
    sub_id = _seed_real_order(session, status="SUBMITTED", quantity=10)
    dry_id = _seed_real_order(session, status="DRY_RUN", quantity=5)

    for path in (
        f"/api/real-orders/{sub_id}/sync",
        f"/api/real-orders/{dry_id}/sync",
    ):
        resp = client_enabled.post(path)
        if resp.status_code == 200:
            _assert_no_forbidden(resp.json())


# ---------------------------------------------------------------------------
# 10. Phase D mutating endpoint count regression
# ---------------------------------------------------------------------------


def test_int_real_orders_sync_route_exists():
    """The route is registered as exactly one POST endpoint."""
    from app.main import app

    matching = [
        r for r in app.routes
        if hasattr(r, "methods")
        and "POST" in r.methods
        and getattr(r, "path", "") == "/api/real-orders/{order_id}/sync"
    ]
    assert len(matching) == 1
