"""Unit tests for v0.16 Phase D — RealOrderExecutor.

All tests use an in-memory SQLite DB (fast, isolated). The executor is tested
via direct DB interactions so each gate can be verified in isolation.

Scope:
  * ExecutorResult dataclass: as_dict / frozen.
  * Gate 1 — NOT_APPROVED: missing candidate / wrong status.
  * Gate 2 — ALREADY_EXECUTED: active RealOrder for same candidate.
  * Gate 3 — KILL_SWITCH_ON.
  * Gate 4 — REAL_TRADING_DISABLED.
  * Gate 5 — KIS_ORDER_DISABLED.
  * Gate 6 — AMOUNT_EXCEEDS_PER_ORDER_CAP.
  * Gate 7 — AMOUNT_EXCEEDS_DAILY_CAP.
  * Gate 8 — RISK_REJECTED (PreTradeRiskEngine).
  * Dry-run success: RealOrder created with dry_run=True, status=DRY_RUN.
  * Non-dry-run: REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D result.
  * FakeKisOrderTransport only — no real HTTP.
  * AST guard: no httpx/requests/urllib in real_order_executor.py.
  * No raw-response storage method on RealOrderExecutor.
  * Phase E scope guard: frontend real-orders page not yet created.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.broker.real_order_executor import ExecutorResult, RealOrderExecutor
from app.config.settings import Settings
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base
from app.db.models import RealOrder
from app.db.session import create_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    def _fk(dbapi_conn, _):
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


def _make_settings(
    *,
    kill_switch_enabled: bool = False,
    real_trading_enabled: bool = True,
    kis_order_enabled: bool = True,
    real_order_dry_run: bool = True,
    max_real_order_amount: int = 5_000_000,
    max_real_daily_order_amount: int = 50_000_000,
    trading_safety_enabled: bool = True,
    approval_required: bool = True,
    max_order_amount: int = 5_000_000,
    max_daily_order_amount: int = 50_000_000,
    max_position_ratio: float = 0.80,
    max_daily_loss_amount: int = 5_000_000,
) -> Settings:
    """Return a Settings instance with the given overrides."""
    return Settings(
        kill_switch_enabled=kill_switch_enabled,
        real_trading_enabled=real_trading_enabled,
        kis_order_enabled=kis_order_enabled,
        real_order_dry_run=real_order_dry_run,
        max_real_order_amount=max_real_order_amount,
        max_real_daily_order_amount=max_real_daily_order_amount,
        trading_safety_enabled=trading_safety_enabled,
        approval_required=approval_required,
        max_order_amount=max_order_amount,
        max_daily_order_amount=max_daily_order_amount,
        max_position_ratio=max_position_ratio,
        max_daily_loss_amount=max_daily_loss_amount,
    )


def _seed_approved_candidate(session) -> tuple[int, int]:
    """Create VirtualAccount + APPROVED OrderCandidate.
    Returns (account_id, candidate_id).
    """
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(name="exec-test", initial_cash=Decimal("10_000_000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        estimated_amount=Decimal("750_000"),
    )
    # Manually advance to APPROVED status via allowed transitions
    cand_repo.update_status(cand, new_status="RISK_CHECKING")
    cand_repo.update_status(cand, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand, new_status="APPROVED")
    session.commit()
    return acc.id, cand.id


# ---------------------------------------------------------------------------
# 1. ExecutorResult dataclass
# ---------------------------------------------------------------------------


def test_executor_result_as_dict_completeness():
    r = ExecutorResult(
        success=True,
        dry_run=True,
        blocked_reason=None,
        real_order_id=42,
        status="DRY_RUN",
        message="ok",
    )
    d = r.as_dict()
    assert d["success"] is True
    assert d["dry_run"] is True
    assert d["blocked_reason"] is None
    assert d["real_order_id"] == 42
    assert d["status"] == "DRY_RUN"
    assert d["message"] == "ok"


def test_executor_result_is_frozen():
    r = ExecutorResult(
        success=False, dry_run=True, blocked_reason="X",
        real_order_id=None, status="BLOCKED", message="m"
    )
    with pytest.raises((AttributeError, TypeError)):
        r.success = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Gate 1 — NOT_APPROVED
# ---------------------------------------------------------------------------


def test_gate1_missing_candidate_returns_candidate_not_found(session):
    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=9999, settings=_make_settings())
    assert result.success is False
    assert result.blocked_reason == "CANDIDATE_NOT_FOUND"


@pytest.mark.parametrize("status", ["DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "REJECTED", "EXPIRED"])
def test_gate1_non_approved_status_blocks(session, status):
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(name="g1test", initial_cash=Decimal("1_000_000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id, source="MANUAL", symbol="005930",
        side="BUY", quantity=1, order_type="MARKET",
        estimated_amount=Decimal("10_000"),
    )
    # Advance to target status
    _TRANSITIONS = {
        "RISK_CHECKING": ["RISK_CHECKING"],
        "PENDING_APPROVAL": ["RISK_CHECKING", "PENDING_APPROVAL"],
        "APPROVED": ["RISK_CHECKING", "PENDING_APPROVAL", "APPROVED"],
        "REJECTED": ["RISK_CHECKING", "PENDING_APPROVAL", "REJECTED"],
        "EXPIRED": ["RISK_CHECKING", "PENDING_APPROVAL", "EXPIRED"],
    }
    for t in _TRANSITIONS.get(status, []):
        cand_repo.update_status(cand, new_status=t)
    session.commit()

    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=cand.id, settings=_make_settings())
    assert result.success is False
    assert result.blocked_reason == "NOT_APPROVED"


# ---------------------------------------------------------------------------
# 3. Gate 2 — ALREADY_EXECUTED
# ---------------------------------------------------------------------------


def test_gate2_active_real_order_blocks(session):
    _, cid = _seed_approved_candidate(session)
    order_repo = RealOrderRepository(session)
    # Create an existing DRY_RUN RealOrder for this candidate
    order_repo.create(
        candidate_id=cid, symbol="005930", side="BUY",
        quantity=10, order_type="MARKET", status="DRY_RUN",
    )
    session.commit()

    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=cid, settings=_make_settings())
    assert result.success is False
    assert result.blocked_reason == "ALREADY_EXECUTED"


def test_gate2_failed_real_order_does_not_block(session):
    _, cid = _seed_approved_candidate(session)
    order_repo = RealOrderRepository(session)
    # A FAILED order does NOT count as "active" → should not block
    order_repo.create(
        candidate_id=cid, symbol="005930", side="BUY",
        quantity=10, order_type="MARKET", status="FAILED",
    )
    session.commit()

    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=cid, settings=_make_settings())
    # Should proceed past gate 2 (will be blocked by risk engine or succeed)
    assert result.blocked_reason != "ALREADY_EXECUTED"


# ---------------------------------------------------------------------------
# 4. Gate 3 — KILL_SWITCH_ON
# ---------------------------------------------------------------------------


def test_gate3_kill_switch_on_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(kill_switch_enabled=True)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "KILL_SWITCH_ON"


# ---------------------------------------------------------------------------
# 5. Gate 4 — REAL_TRADING_DISABLED
# ---------------------------------------------------------------------------


def test_gate4_real_trading_disabled_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(real_trading_enabled=False)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "REAL_TRADING_DISABLED"


# ---------------------------------------------------------------------------
# 6. Gate 5 — KIS_ORDER_DISABLED
# ---------------------------------------------------------------------------


def test_gate5_kis_order_disabled_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(kis_order_enabled=False)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "KIS_ORDER_DISABLED"


# ---------------------------------------------------------------------------
# 7. Gate 6 — per-order amount cap
# ---------------------------------------------------------------------------


def test_gate6_per_order_amount_exceeded_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    # estimated_amount=750_000 > max_real_order_amount=100_000
    settings = _make_settings(max_real_order_amount=100_000, max_real_daily_order_amount=1_000_000)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "AMOUNT_EXCEEDS_PER_ORDER_CAP"


# ---------------------------------------------------------------------------
# 8. Gate 7 — daily real order cap
# ---------------------------------------------------------------------------


def test_gate7_daily_cap_exceeded_blocks(session):
    acc_id, cid = _seed_approved_candidate(session)
    # Seed an existing DRY_RUN RealOrder that is counted toward today's total
    order_repo = RealOrderRepository(session)
    order_repo.create(
        candidate_id=cid,
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="MARKET",
        estimated_amount=Decimal("900_000"),
        status="FAILED",  # excluded from sum
    )
    # Create a second APPROVED candidate with the same account
    cand_repo = OrderCandidateRepository(session)
    acc_repo = VirtualAccountRepository(session)
    # Reuse existing account — create a second candidate
    cand2 = cand_repo.create(
        account_id=acc_id,
        source="MANUAL",
        symbol="000660",
        side="BUY",
        quantity=5,
        order_type="MARKET",
        estimated_amount=Decimal("600_000"),
    )
    cand_repo.update_status(cand2, new_status="RISK_CHECKING")
    cand_repo.update_status(cand2, new_status="PENDING_APPROVAL")
    cand_repo.update_status(cand2, new_status="APPROVED")
    session.commit()

    # Now first execute cid1 → creates a DRY_RUN RealOrder (750_000)
    executor = RealOrderExecutor()
    # Allow 1_000_000 daily cap; 750_000 passes; then 600_000 → 1_350_000 > 1_000_000
    settings = _make_settings(
        max_real_order_amount=1_000_000,
        max_real_daily_order_amount=1_000_000,
    )
    r1 = executor.execute(session, candidate_id=cid, settings=settings)
    session.commit()
    assert r1.success is True  # first order succeeds

    r2 = executor.execute(session, candidate_id=cand2.id, settings=settings)
    assert r2.success is False
    assert r2.blocked_reason == "AMOUNT_EXCEEDS_DAILY_CAP"


# ---------------------------------------------------------------------------
# 9. Gate 8 — RISK_REJECTED (PreTradeRiskEngine)
# ---------------------------------------------------------------------------


def test_gate8_risk_engine_rejection_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    # Set max_order_amount=1 → per_symbol_limit violation (estimated=750_000 > 1)
    settings = _make_settings(
        max_order_amount=1,
        max_daily_order_amount=50_000_000,
    )
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "RISK_REJECTED"
    assert "per_symbol_limit" in result.message


# ---------------------------------------------------------------------------
# 10. Dry-run success
# ---------------------------------------------------------------------------


def test_dry_run_success_creates_real_order(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=cid, settings=_make_settings())
    session.commit()

    assert result.success is True
    assert result.dry_run is True
    assert result.blocked_reason is None
    assert result.status == "DRY_RUN"
    assert result.real_order_id is not None

    order = session.get(RealOrder, result.real_order_id)
    assert order is not None
    assert order.dry_run is True
    assert order.status == "DRY_RUN"
    assert order.fake_order_no is not None
    assert order.fake_order_no.startswith("FAKE-")
    assert order.symbol == "005930"
    assert order.candidate_id == cid


def test_dry_run_order_has_no_sensitive_fields(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    result = executor.execute(session, candidate_id=cid, settings=_make_settings())
    session.commit()

    order = session.get(RealOrder, result.real_order_id)
    assert order is not None
    # These attributes must not exist on the model at all
    assert not hasattr(order, "api_key")
    assert not hasattr(order, "access_token")
    assert not hasattr(order, "account_number")
    assert not hasattr(order, "raw_response")


# ---------------------------------------------------------------------------
# 11. Non-dry-run blocked in Phase D
# ---------------------------------------------------------------------------


def test_non_dry_run_blocked_in_phase_d(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(real_order_dry_run=False)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D"
    assert result.dry_run is False


# ---------------------------------------------------------------------------
# 12. FakeKisOrderTransport only
# ---------------------------------------------------------------------------


def test_executor_uses_only_fake_transport_by_default():
    from app.broker.kis_order_client import FakeKisOrderTransport
    executor = RealOrderExecutor()
    assert isinstance(executor._transport, FakeKisOrderTransport)


# ---------------------------------------------------------------------------
# 13. AST guard — no forbidden imports in real_order_executor.py
# ---------------------------------------------------------------------------


def _executor_source() -> str:
    return (PROJECT_ROOT / "app" / "broker" / "real_order_executor.py").read_text(
        encoding="utf-8"
    )


def test_real_order_executor_has_no_httpx_import():
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "httpx" not in (name or ""), "httpx must not be imported"


def test_real_order_executor_has_no_requests_import():
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "requests" not in (name or ""), "requests must not be imported"


def test_real_order_executor_has_no_urllib_import():
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else ([node.module] if node.module else [])
            )
            for name in names:
                assert "urllib" not in (name or ""), "urllib must not be imported"


def test_real_order_executor_has_no_kis_http_transport():
    """KisHttpOrderTransport must not be imported (docstring mentions are fine)."""
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [alias.name for alias in node.names]
            )
            for name in names:
                assert "KisHttpOrderTransport" not in (name or ""), (
                    "KisHttpOrderTransport must not be imported in Phase D executor"
                )


# ---------------------------------------------------------------------------
# 14. No raw-response storage method
# ---------------------------------------------------------------------------


def test_real_order_executor_has_no_raw_response_method():
    methods = [m for m in dir(RealOrderExecutor) if not m.startswith("_")]
    raw_methods = [m for m in methods if "raw" in m.lower()]
    assert raw_methods == [], f"Must not expose raw methods: {raw_methods}"


# ---------------------------------------------------------------------------
# 15. Phase E scope guard
# ---------------------------------------------------------------------------


def test_phase_e_real_orders_frontend_not_yet_created():
    frontend_dir = PROJECT_ROOT / "frontend" / "src" / "pages"
    real_orders_pages = list(frontend_dir.glob("*[Rr]eal*[Oo]rder*"))
    assert real_orders_pages == [], (
        f"RealOrders frontend page must not exist in Phase D: {real_orders_pages}"
    )
