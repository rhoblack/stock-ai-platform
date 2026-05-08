"""Integration tests for v0.15 Phase D Approval Workflow API.

Endpoints under test:

    GET    /api/approvals/candidates
    GET    /api/approvals/candidates/{id}
    POST   /api/approvals/candidates              (3-gate mutation)
    POST   /api/approvals/{id}/approve            (3-gate mutation)
    POST   /api/approvals/{id}/reject             (3-gate mutation)
    POST   /api/approvals/{id}/expire             (gated)
    GET    /api/approvals/audit

Verified invariants:
  * Mutation triple gate -- TRADING_SAFETY_ENABLED False / KILL_SWITCH_ENABLED
    True / missing-Bearer (when AUTH_ENABLED) all surface as 503 / 503 / 401.
  * Risk-pass path lands the candidate in PENDING_APPROVAL with a
    non-empty risk_check_result_json.
  * Risk-fail path lands the candidate in RISK_REJECTED.
  * Approval flows the candidate through APPROVED -> EXECUTED_PAPER and
    attaches a virtual_order_id (paper). NO KIS / real broker call.
  * Forbidden response substrings (api_key / token / secret / source_file_path
    / broker_order_id / kis_order_id / real_account / real_order_id /
    account_number / raw_text / body / full_text) NEVER appear.
  * AST guard: the route module imports nothing from KIS / DART / RSS /
    requests / httpx / urllib.
"""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
)
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.db.base import Base
from app.db.session import create_session_factory, get_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Forbidden response substrings (raw JSON scan)
# ---------------------------------------------------------------------------


_FORBIDDEN_SUBSTRINGS = (
    "api_key",
    "token",
    "secret",
    "source_file_path",
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "real_order_id",
    "broker_name",
    "account_number",
    "raw_text",
    "body",
    "full_text",
    "access_token",
    "jwt_secret",
    "kis_app_secret",
    "kis_account_no",
)


def _assert_no_forbidden(payload) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert f'"{needle}"' not in text, (
            f"forbidden field {needle!r} unexpectedly in response: {payload!r}"
        )


# ---------------------------------------------------------------------------
# Settings + fixtures
# ---------------------------------------------------------------------------


def _settings(
    *,
    trading_safety: bool = True,
    kill_switch: bool = False,
    paper: bool = True,
    auth: bool = False,
) -> Settings:
    """Default 'enabled' settings for the workflow."""
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
        paper_trading_enabled=paper,
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
    """trading_safety=True, kill_switch=False, AUTH off."""
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


def _seed_dev_fallback_user(session) -> None:
    """The auth dev fallback resolves to ``user_id=1``. The audit log has a
    FK on ``users.id``, so the user row must exist or INSERTs fail.
    """
    from app.auth.security import PasswordHasher
    from app.data.repositories.users import UserRepository

    hasher = PasswordHasher(n=1024, r=8, p=1)
    repo = UserRepository(session)
    user = repo.create(
        username="dev-fallback",
        password_hash=hasher.hash_password("hunter2!"),
        is_admin=True,
    )
    if user.id != 1:
        user.id = 1
        session.flush()
    session.commit()


def _seed_account(session, *, name="paper", initial_cash=Decimal("1000000")):
    _seed_dev_fallback_user(session)
    repo = VirtualAccountRepository(session)
    acc = repo.create(name=name, initial_cash=initial_cash)
    session.commit()
    return acc


# ---------------------------------------------------------------------------
# 1. GET candidates / detail (read-only)
# ---------------------------------------------------------------------------


def test_get_candidates_default_returns_pending(client_enabled, session):
    acc = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
    )
    repo.update_status(cand, new_status="RISK_CHECKING")
    repo.update_status(cand, new_status="PENDING_APPROVAL")
    session.commit()

    resp = client_enabled.get("/api/approvals/candidates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["candidates"][0]["status"] == "PENDING_APPROVAL"
    _assert_no_forbidden(body)


def test_get_candidate_detail_includes_risk_check_result(client_enabled, session):
    acc = _seed_account(session)
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
    )
    repo.attach_risk_result(
        cand,
        result={
            "policy_version": "pre-trade-v1",
            "passed": True,
            "violations": [],
            "checked_at": "2026-05-08T16:30:00+00:00",
        },
    )
    session.commit()

    resp = client_enabled.get(f"/api/approvals/candidates/{cand.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate"]["id"] == cand.id
    assert body["risk_check_result"]["passed"] is True
    _assert_no_forbidden(body)


def test_get_candidate_detail_404_when_missing(client_enabled):
    resp = client_enabled.get("/api/approvals/candidates/9999")
    assert resp.status_code == 404


def test_get_candidates_status_filter_validation(client_enabled):
    resp = client_enabled.get("/api/approvals/candidates?status=UNKNOWN")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 2. POST candidate gating
# ---------------------------------------------------------------------------


def test_post_candidate_503_when_safety_disabled(client_safety_off, session):
    _seed_account(session)
    resp = client_safety_off.post(
        "/api/approvals/candidates",
        json={"symbol": "005930", "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"].lower()
    assert "approval workflow is disabled" in detail
    assert OrderCandidateRepository(session).list_pending() == []


def test_post_candidate_503_when_kill_switch_on(client_kill_switch_on, session):
    _seed_account(session)
    resp = client_kill_switch_on.post(
        "/api/approvals/candidates",
        json={"symbol": "005930", "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 503
    assert "kill switch" in resp.json()["detail"].lower()


def test_post_candidate_requires_bearer_when_auth_enabled(session):
    _seed_account(session)
    settings = _settings(auth=True)
    client, cleanup = _client_with(session, settings)
    try:
        resp = client.post(
            "/api/approvals/candidates",
            json={"symbol": "005930", "side": "BUY", "quantity": 1},
        )
        assert resp.status_code == 401
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# 3. POST candidate happy + risk-fail
# ---------------------------------------------------------------------------


def test_post_candidate_risk_pass_lands_in_pending_approval(client_enabled, session):
    _seed_account(session)
    resp = client_enabled.post(
        "/api/approvals/candidates",
        json={
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1,
            "estimated_amount": "100",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["risk_passed"] is True
    assert body["candidate"]["status"] == "PENDING_APPROVAL"
    assert body["risk_check_result"]["passed"] is True
    _assert_no_forbidden(body)


def test_post_candidate_risk_fail_lands_in_risk_rejected(session):
    """An over-cap order (estimated_amount > max_order_amount) fails risk
    rule 3 and lands in RISK_REJECTED."""
    _seed_account(session)
    settings = _settings()  # max_order_amount=100,000
    client, cleanup = _client_with(session, settings)
    try:
        resp = client.post(
            "/api/approvals/candidates",
            json={
                "symbol": "005930",
                "side": "BUY",
                "quantity": 1,
                "estimated_amount": "999999",  # > cap
            },
        )
    finally:
        cleanup()
    assert resp.status_code == 201
    body = resp.json()
    assert body["risk_passed"] is False
    assert body["candidate"]["status"] == "RISK_REJECTED"
    rule_ids = {v["rule_id"] for v in body["risk_check_result"]["violations"]}
    assert "per_symbol_limit" in rule_ids


def test_post_candidate_validation_error(client_enabled, session):
    _seed_account(session)
    resp = client_enabled.post(
        "/api/approvals/candidates",
        json={"symbol": "005930", "side": "HOLD", "quantity": 1},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. POST approve -- happy path produces VirtualOrder, EXECUTED_PAPER
# ---------------------------------------------------------------------------


def _create_pending(client) -> dict:
    resp = client.post(
        "/api/approvals/candidates",
        json={
            "symbol": "005930",
            "side": "BUY",
            "quantity": 1,
            "estimated_amount": "100",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["candidate"]["status"] == "PENDING_APPROVAL"
    return body["candidate"]


def test_approve_lands_in_executed_paper_with_virtual_order(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)

    resp = client_enabled.post(f"/api/approvals/{cand['id']}/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate"]["status"] == "EXECUTED_PAPER"
    virtual_order_id = body["virtual_order_id"]
    assert isinstance(virtual_order_id, int) and virtual_order_id > 0

    # The downstream VirtualOrder exists and was created by SimulationBroker
    # (status=CREATED, NOT a real KIS order).
    vo = VirtualOrderRepository(session).get_by_id(virtual_order_id)
    assert vo is not None
    assert vo.status == "CREATED"
    _assert_no_forbidden(body)


def test_approve_404_when_unknown(client_enabled):
    resp = client_enabled.post("/api/approvals/9999/approve")
    assert resp.status_code in (404, 409)


def test_approve_409_when_status_not_pending(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    # First approve -> EXECUTED_PAPER. Second approve must 409.
    client_enabled.post(f"/api/approvals/{cand['id']}/approve")
    resp = client_enabled.post(f"/api/approvals/{cand['id']}/approve")
    assert resp.status_code == 409


def test_approve_503_when_kill_switch_on(session):
    _seed_account(session)
    enabled = _settings()
    client, cleanup = _client_with(session, enabled)
    try:
        cand = _create_pending(client)
    finally:
        cleanup()

    blocked = _settings(kill_switch=True)
    client2, cleanup2 = _client_with(session, blocked)
    try:
        resp = client2.post(f"/api/approvals/{cand['id']}/approve")
    finally:
        cleanup2()
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 5. POST reject + expire
# ---------------------------------------------------------------------------


def test_reject_marks_candidate_rejected(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    resp = client_enabled.post(
        f"/api/approvals/{cand['id']}/reject",
        json={"reason": "operator chose to skip"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["new_status"] == "REJECTED"
    fresh = OrderCandidateRepository(session).get_by_id(cand["id"])
    assert fresh.status == "REJECTED"
    assert fresh.rejection_reason == "operator chose to skip"


def test_reject_validation_empty_reason(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    resp = client_enabled.post(
        f"/api/approvals/{cand['id']}/reject",
        json={"reason": "   "},
    )
    assert resp.status_code == 422


def test_expire_marks_candidate_expired(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    resp = client_enabled.post(f"/api/approvals/{cand['id']}/expire")
    assert resp.status_code == 200
    body = resp.json()
    assert body["new_status"] == "EXPIRED"


def test_expire_409_on_already_executed(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    client_enabled.post(f"/api/approvals/{cand['id']}/approve")
    resp = client_enabled.post(f"/api/approvals/{cand['id']}/expire")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 6. GET audit
# ---------------------------------------------------------------------------


def test_audit_log_appended_per_workflow_step(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    client_enabled.post(f"/api/approvals/{cand['id']}/approve")

    resp = client_enabled.get(f"/api/approvals/audit?candidate_id={cand['id']}")
    assert resp.status_code == 200
    body = resp.json()
    events = [item["event_type"] for item in body["items"]]
    # Order is ascending by id (list_by_candidate semantics).
    assert "CREATED" in events
    assert "RISK_CHECKED" in events
    assert "APPROVED" in events
    assert "EXECUTED_PAPER" in events
    _assert_no_forbidden(body)


def test_audit_log_event_filter(client_enabled, session):
    _seed_account(session)
    cand = _create_pending(client_enabled)
    client_enabled.post(
        f"/api/approvals/{cand['id']}/reject",
        json={"reason": "ops"},
    )
    resp = client_enabled.get("/api/approvals/audit?event_type=REJECTED")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["event_type"] == "REJECTED" for item in items)
    _assert_no_forbidden(resp.json())


def test_audit_log_invalid_event_type_422(client_enabled):
    resp = client_enabled.get("/api/approvals/audit?event_type=UNKNOWN")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. AST guard: route module imports nothing from KIS / external HTTP
# ---------------------------------------------------------------------------


def test_approval_routes_module_has_no_forbidden_imports():
    src = (PROJECT_ROOT / "app" / "api" / "approval_routes.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = (
        "app.kis",
        "app.data.dart_provider",
        "app.data.rss_provider",
        "app.data.collectors.kis_client",
    )
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in forbidden_modules or any(
                    a.name == p or a.name.startswith(p + ".")
                    for p in forbidden_prefixes
                ):
                    leaks.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module == p or module.startswith(p + ".")
                for p in forbidden_prefixes
            ):
                leaks.append(f"from {module}")
    assert leaks == [], (
        f"approval_routes.py unexpectedly imports forbidden modules: {leaks!r}"
    )


def test_approval_service_module_has_no_forbidden_imports():
    src = (PROJECT_ROOT / "app" / "approval" / "approval_service.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = (
        "app.kis",
        "app.data.dart_provider",
        "app.data.rss_provider",
        "app.data.collectors.kis_client",
    )
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in forbidden_modules or any(
                    a.name == p or a.name.startswith(p + ".")
                    for p in forbidden_prefixes
                ):
                    leaks.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module == p or module.startswith(p + ".")
                for p in forbidden_prefixes
            ):
                leaks.append(f"from {module}")
    assert leaks == [], (
        f"approval_service.py unexpectedly imports forbidden modules: {leaks!r}"
    )


# ---------------------------------------------------------------------------
# 8. Mutation methods 405 on read-only paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("put", "/api/approvals/candidates"),
        ("delete", "/api/approvals/candidates"),
        ("patch", "/api/approvals/candidates"),
        ("put", "/api/approvals/audit"),
        ("delete", "/api/approvals/audit"),
        ("patch", "/api/approvals/audit"),
    ],
)
def test_read_only_endpoints_reject_mutation_methods(
    client_enabled, method, endpoint
):
    resp = getattr(client_enabled, method)(endpoint)
    assert resp.status_code == 405
