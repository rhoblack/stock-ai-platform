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
# 11. Non-dry-run with default (Fake-only) executor → TRANSPORT_UNAVAILABLE
#     (was REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D before v1.0 Phase C; the
#     blocked_reason changed when the real path landed.)
# ---------------------------------------------------------------------------


def test_non_dry_run_with_fake_transport_blocks(session):
    """Default constructor produces a Fake-only executor. With real_order_dry_run=
    False, gates 1-9 still pass (settings allow it) but gate 10 (TRANSPORT_UNAVAILABLE)
    fires because the real path refuses to use a Fake transport."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()  # default → FakeKisOrderTransport only
    settings = _make_settings(real_order_dry_run=False)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "TRANSPORT_UNAVAILABLE"
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


def test_phase_e_real_orders_frontend_exists():
    """Phase E must have created the RealOrders frontend page."""
    frontend_dir = PROJECT_ROOT / "frontend" / "src" / "pages"
    real_orders_pages = list(frontend_dir.glob("*[Rr]eal*[Oo]rder*"))
    assert real_orders_pages != [], (
        "RealOrders frontend page must exist after Phase E"
    )


# ===========================================================================
# v1.0 Phase C — 10-gate executor + dry-run vs real path branch
# ===========================================================================


import hashlib  # noqa: E402

import httpx  # noqa: E402  -- mock-only via httpx.MockTransport

from app.broker.kis_order_client import (  # noqa: E402
    FakeKisOrderTransport,
    KisCancelResult,
    KisFillStatusResult,
    KisOrderClientInterface,
    KisOrderResult,
)
from app.data.repositories.approval_audit_log import (  # noqa: E402
    ApprovalAuditLogRepository,
    VALID_EVENT_TYPES,
)


# ---------------------------------------------------------------------------
# Phase C helpers
# ---------------------------------------------------------------------------


class _StubTransport(KisOrderClientInterface):
    """Programmable KisOrderClientInterface for unit-testing the real branch.

    Each call counter is incremented so we can assert place_order is invoked
    exactly once (Phase B retry=0 is preserved end-to-end). Callers set
    ``next_place_result`` to drive the executor branch.
    """

    def __init__(self, *, next_place_result: KisOrderResult) -> None:
        self.next_place_result = next_place_result
        self.place_calls = 0
        self.query_calls = 0
        self.cancel_calls = 0

    def place_order(self, request) -> KisOrderResult:
        self.place_calls += 1
        return self.next_place_result

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        self.query_calls += 1
        return KisFillStatusResult(
            success=True, order_no=order_no, filled_quantity=0,
            remaining_quantity=0, status="PENDING", message="stub",
        )

    def cancel_order(self, order_no: str) -> KisCancelResult:
        self.cancel_calls += 1
        return KisCancelResult(
            success=True, order_no=order_no, message="stub cancel",
        )


def _make_real_settings(**overrides) -> Settings:
    """Settings tuned for the real path: every gate set to allow execution.

    Overrides apply on top of the all-open base.
    """
    base = dict(
        kill_switch_enabled=False,
        trading_safety_enabled=True,
        real_trading_enabled=True,
        kis_order_enabled=True,
        real_order_dry_run=False,
        max_real_order_amount=5_000_000,
        max_real_daily_order_amount=50_000_000,
        approval_required=True,
        max_order_amount=5_000_000,
        max_daily_order_amount=50_000_000,
        max_position_ratio=0.80,
        max_daily_loss_amount=5_000_000,
        kis_account_no="TEST-ACCT-9012",
    )
    base.update(overrides)
    return Settings(**base)


def _kis_submitted(order_no: str = "0000123456") -> KisOrderResult:
    return KisOrderResult(
        success=True,
        order_no=order_no,
        message=f"SUBMITTED: 정상처리 order_no={order_no}",
    )


def _kis_rejected() -> KisOrderResult:
    return KisOrderResult(
        success=False,
        order_no="",
        message="REJECTED: rt_cd=1 주문 가능 수량 초과",
    )


def _kis_timeout() -> KisOrderResult:
    return KisOrderResult(
        success=False,
        order_no="",
        message="TIMEOUT: KIS place_order exceeded 5.0s",
    )


def _kis_network_error() -> KisOrderResult:
    return KisOrderResult(
        success=False,
        order_no="",
        message="NETWORK_ERROR: ConnectError",
    )


def _kis_unknown() -> KisOrderResult:
    return KisOrderResult(
        success=False,
        order_no="",
        message="UNKNOWN: KIS HTTP 503 (server error)",
    )


# ---------------------------------------------------------------------------
# 16. Gate 4 — TRADING_SAFETY_DISABLED (NEW in v1.0)
# ---------------------------------------------------------------------------


def test_phase_c_gate4_trading_safety_disabled_blocks(session):
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(trading_safety_enabled=False)
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.success is False
    assert result.blocked_reason == "TRADING_SAFETY_DISABLED"


def test_phase_c_gate_ordering_kill_switch_before_safety(session):
    """When BOTH kill_switch=True AND safety=False, kill_switch fires first."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    settings = _make_settings(
        kill_switch_enabled=True, trading_safety_enabled=False
    )
    result = executor.execute(session, candidate_id=cid, settings=settings)
    assert result.blocked_reason == "KILL_SWITCH_ON"


# ---------------------------------------------------------------------------
# 17. Gate 10 — TRANSPORT_UNAVAILABLE (NEW in v1.0)
# ---------------------------------------------------------------------------


def test_phase_c_gate10_real_path_no_transport_blocks(session):
    """Default executor + real_order_dry_run=False → TRANSPORT_UNAVAILABLE."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()  # FakeKisOrderTransport
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert result.success is False
    assert result.blocked_reason == "TRANSPORT_UNAVAILABLE"


def test_phase_c_gate10_factory_returning_fake_blocks(session):
    """Factory must NOT return a Fake transport for the real path."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor(
        real_transport_factory=lambda settings: FakeKisOrderTransport()
    )
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert result.blocked_reason == "TRANSPORT_UNAVAILABLE"


def test_phase_c_gate10_factory_raising_blocks(session):
    """A factory that raises is treated as TRANSPORT_UNAVAILABLE (not propagated)."""
    def boom(_):
        raise RuntimeError("simulated factory init failure")

    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor(real_transport_factory=boom)
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert result.blocked_reason == "TRANSPORT_UNAVAILABLE"


def test_phase_c_dry_run_does_not_check_gate10(session):
    """Dry-run path uses the FakeKisOrderTransport unconditionally."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()  # default Fake
    result = executor.execute(
        session, candidate_id=cid, settings=_make_settings(real_order_dry_run=True)
    )
    assert result.success is True
    assert result.dry_run is True


# ---------------------------------------------------------------------------
# 18. Real path — SUBMITTED outcome
# ---------------------------------------------------------------------------


def test_phase_c_real_path_submitted_creates_real_order(session):
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=_kis_submitted("REAL-ORDER-789"))
    executor = RealOrderExecutor(transport=transport)

    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()

    assert transport.place_calls == 1, "place_order must be invoked exactly once"
    assert result.success is True
    assert result.dry_run is False
    assert result.status == "SUBMITTED"
    assert result.real_order_id is not None

    order = session.get(RealOrder, result.real_order_id)
    assert order is not None
    assert order.dry_run is False
    assert order.status == "SUBMITTED"
    # broker_order_no_hash MUST be 64-char SHA-256 hex of the plaintext order_no.
    expected_hash = hashlib.sha256(b"REAL-ORDER-789").hexdigest()
    assert order.broker_order_no_hash == expected_hash
    assert len(order.broker_order_no_hash) == 64


def test_phase_c_real_path_does_not_store_plain_order_no(session):
    """The plaintext KIS order_no must NEVER be persisted on the RealOrder."""
    _, cid = _seed_approved_candidate(session)
    plaintext = "PLAINTEXT-ORDER-NO-99999"
    transport = _StubTransport(next_place_result=_kis_submitted(plaintext))
    executor = RealOrderExecutor(transport=transport)

    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()

    order = session.get(RealOrder, result.real_order_id)
    # No column on the model carries the plaintext.
    assert plaintext not in (order.broker_order_no_hash or "")
    assert plaintext not in (order.fake_order_no or "")
    assert plaintext not in (order.error_message or "")
    assert plaintext not in (order.error_code or "")
    # ExecutorResult message and as_dict must not surface the plaintext.
    text = repr(result) + " " + str(result.as_dict())
    assert plaintext not in text


def test_phase_c_real_path_executor_message_does_not_carry_plain_order_no(session):
    """Belt-and-braces: ExecutorResult.message is hash-only / status-only."""
    _, cid = _seed_approved_candidate(session)
    plaintext = "DO-NOT-LEAK-ORDER-77777"
    transport = _StubTransport(next_place_result=_kis_submitted(plaintext))
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert plaintext not in result.message


# ---------------------------------------------------------------------------
# 19. Real path — REJECTED / TIMEOUT / NETWORK_ERROR / UNKNOWN
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kis_factory,classification",
    [
        (_kis_rejected, "REJECTED"),
        (_kis_timeout, "TIMEOUT"),
        (_kis_network_error, "NETWORK_ERROR"),
        (_kis_unknown, "UNKNOWN"),
    ],
)
def test_phase_c_real_path_non_submitted_marks_failed(
    session, kis_factory, classification
):
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=kis_factory())
    executor = RealOrderExecutor(transport=transport)

    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()

    assert transport.place_calls == 1, "place_order retry MUST stay at 0"
    assert result.success is False
    assert result.dry_run is False
    assert result.status == "FAILED"
    assert result.blocked_reason == classification

    order = session.get(RealOrder, result.real_order_id)
    assert order.status == "FAILED"
    assert order.error_code == classification
    # broker_order_no_hash should NOT be populated for failed orders.
    assert order.broker_order_no_hash is None


# ---------------------------------------------------------------------------
# 20. Audit log — REAL_ORDER_SUBMITTED / REAL_ORDER_FAILED rows
# ---------------------------------------------------------------------------


def test_phase_c_audit_event_types_extended():
    """The repository's whitelist must include both new Phase C event types."""
    assert "REAL_ORDER_SUBMITTED" in VALID_EVENT_TYPES
    assert "REAL_ORDER_FAILED" in VALID_EVENT_TYPES


def test_phase_c_real_path_submitted_writes_audit(session):
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=_kis_submitted("REAL-AUDIT-001"))
    executor = RealOrderExecutor(transport=transport)
    executor.execute(session, candidate_id=cid, settings=_make_real_settings())
    session.commit()

    audit_repo = ApprovalAuditLogRepository(session)
    rows = audit_repo.list_by_candidate(cid)
    submitted = [r for r in rows if r.event_type == "REAL_ORDER_SUBMITTED"]
    assert len(submitted) == 1
    details = submitted[0].details_json
    assert details["classification"] == "SUBMITTED"
    assert details["dry_run"] is False
    assert details["symbol"] == "005930"
    assert details["side"] == "BUY"
    # 16-char hex prefix only — not the full hash, never the plaintext.
    assert isinstance(details.get("broker_order_no_hash_prefix"), str)
    assert len(details["broker_order_no_hash_prefix"]) == 16


def test_phase_c_real_path_failed_writes_audit(session):
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=_kis_rejected())
    executor = RealOrderExecutor(transport=transport)
    executor.execute(session, candidate_id=cid, settings=_make_real_settings())
    session.commit()

    audit_repo = ApprovalAuditLogRepository(session)
    rows = audit_repo.list_by_candidate(cid)
    failed = [r for r in rows if r.event_type == "REAL_ORDER_FAILED"]
    assert len(failed) == 1
    assert failed[0].details_json["classification"] == "REJECTED"


def test_phase_c_audit_details_have_no_forbidden_keys(session):
    """details_json must never contain real_order_id / kis_order_id / api_key etc."""
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=_kis_submitted("AUDIT-FORBID-77"))
    executor = RealOrderExecutor(transport=transport)
    executor.execute(session, candidate_id=cid, settings=_make_real_settings())
    session.commit()

    audit_repo = ApprovalAuditLogRepository(session)
    rows = audit_repo.list_by_candidate(cid)
    forbidden = {
        "api_key", "token", "secret", "access_token", "jwt_secret",
        "broker_order_id", "kis_order_id", "real_account", "real_order_id",
        "account_number", "raw_text", "body", "full_text", "source_file_path",
    }
    for row in rows:
        assert isinstance(row.details_json, dict)
        leaked = set(row.details_json.keys()) & forbidden
        assert leaked == set(), f"audit row {row.id} leaked {leaked}"


# ---------------------------------------------------------------------------
# 21. exists_non_failed_for_candidate helper
# ---------------------------------------------------------------------------


def test_phase_c_repo_helper_returns_false_when_no_orders(session):
    _, cid = _seed_approved_candidate(session)
    repo = RealOrderRepository(session)
    assert repo.exists_non_failed_for_candidate(cid) is False


@pytest.mark.parametrize(
    "status",
    ["DRY_RUN", "CREATED", "SUBMITTED", "PARTIALLY_FILLED", "FILLED"],
)
def test_phase_c_repo_helper_returns_true_for_non_failed(session, status):
    _, cid = _seed_approved_candidate(session)
    repo = RealOrderRepository(session)
    repo.create(
        candidate_id=cid, symbol="005930", side="BUY",
        quantity=1, order_type="MARKET", status=status,
    )
    session.flush()
    assert repo.exists_non_failed_for_candidate(cid) is True


@pytest.mark.parametrize("status", ["FAILED", "REJECTED", "CANCELED"])
def test_phase_c_repo_helper_returns_false_for_failed_terminals(session, status):
    _, cid = _seed_approved_candidate(session)
    repo = RealOrderRepository(session)
    repo.create(
        candidate_id=cid, symbol="005930", side="BUY",
        quantity=1, order_type="MARKET", status=status,
    )
    session.flush()
    assert repo.exists_non_failed_for_candidate(cid) is False


def test_phase_c_real_path_duplicate_blocks(session):
    """After a SUBMITTED real order, a second execute() must be DUPLICATE_REAL_ORDER."""
    _, cid = _seed_approved_candidate(session)
    transport = _StubTransport(next_place_result=_kis_submitted("DUP-ABC"))
    executor = RealOrderExecutor(transport=transport)
    first = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()
    assert first.success is True

    transport.next_place_result = _kis_submitted("DUP-XYZ")
    second = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert second.success is False
    assert second.blocked_reason == "DUPLICATE_REAL_ORDER"
    assert transport.place_calls == 1, "duplicate must NOT call place_order again"


def test_phase_c_real_path_failed_does_not_block_retry(session):
    """A FAILED real order leaves room for a retry attempt."""
    _, cid = _seed_approved_candidate(session)
    t1 = _StubTransport(next_place_result=_kis_timeout())
    executor = RealOrderExecutor(transport=t1)
    r1 = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()
    assert r1.status == "FAILED"

    # Retry with a fresh transport that succeeds.
    t2 = _StubTransport(next_place_result=_kis_submitted("RETRY-OK"))
    executor2 = RealOrderExecutor(transport=t2)
    r2 = executor2.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()
    assert r2.success is True
    assert r2.status == "SUBMITTED"


# ---------------------------------------------------------------------------
# 22. Sensitive substring scrubbing in error_message
# ---------------------------------------------------------------------------


def test_phase_c_real_path_error_message_scrubs_sensitive_substrings(session):
    """If KIS happens to return a message containing 'access_token' (e.g. a
    parser quirk), the executor must scrub before mark_failed (which would
    otherwise raise) and the persisted error_message must not contain the leak."""
    _, cid = _seed_approved_candidate(session)
    leaky = KisOrderResult(
        success=False, order_no="",
        message=(
            "REJECTED: KIS msg containing access_token=ABC123 should not "
            "leak — api_key=DEF456 either"
        ),
    )
    transport = _StubTransport(next_place_result=leaky)
    executor = RealOrderExecutor(transport=transport)
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()

    assert result.status == "FAILED"
    order = session.get(RealOrder, result.real_order_id)
    assert "access_token" not in (order.error_message or "").lower()
    assert "api_key" not in (order.error_message or "").lower()


# ---------------------------------------------------------------------------
# 23. RealOrder anchor row created BEFORE the KIS call
# ---------------------------------------------------------------------------


def test_phase_c_real_order_persisted_before_transport_call(session):
    """The DB anchor row must exist by the time transport.place_order is called.

    We assert by capturing how many RealOrder rows existed at the moment
    the transport sees the request. The stub records ``place_calls`` before
    returning — at that point the row must already be in the session.
    """
    _, cid = _seed_approved_candidate(session)

    rows_seen_inside_transport: list[int] = []
    real_result = _kis_submitted("ANCHOR-77")

    class _AnchorObservingTransport(KisOrderClientInterface):
        def place_order(self, request):
            rows_seen_inside_transport.append(
                session.query(RealOrder).filter_by(candidate_id=cid).count()
            )
            return real_result

        def query_fill_status(self, order_no):
            return KisFillStatusResult(
                success=True, order_no=order_no, filled_quantity=0,
                remaining_quantity=0, status="PENDING", message="",
            )

        def cancel_order(self, order_no):
            return KisCancelResult(
                success=True, order_no=order_no, message="",
            )

    executor = RealOrderExecutor(transport=_AnchorObservingTransport())
    executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    assert rows_seen_inside_transport == [1], (
        "RealOrder anchor row must be flushed BEFORE transport.place_order is called"
    )


# ---------------------------------------------------------------------------
# 24. AST guard — Phase C executor must remain free of httpx / real-transport
#     module imports. The transport is injected, never imported.
# ---------------------------------------------------------------------------


def test_phase_c_executor_does_not_import_kis_order_transport_real():
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "kis_order_transport_real" not in node.module, (
                "real-transport module must not be imported by the executor "
                "(transport is dependency-injected via the constructor)"
            )


def test_phase_c_executor_does_not_import_app_providers_kis():
    src = _executor_source()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "app.providers.kis" not in node.module, (
                "executor must not import the read-only KIS data layer"
            )


# ---------------------------------------------------------------------------
# 25. Constructor — real_transport_factory wiring
# ---------------------------------------------------------------------------


def test_phase_c_constructor_with_factory_uses_factory_for_real_path(session):
    """Factory takes precedence over an injected Fake transport for the real branch."""
    _, cid = _seed_approved_candidate(session)
    factory_calls: list[Settings] = []

    real_stub = _StubTransport(next_place_result=_kis_submitted("FAC-ABC"))

    def factory(settings):
        factory_calls.append(settings)
        return real_stub

    executor = RealOrderExecutor(real_transport_factory=factory)
    result = executor.execute(
        session, candidate_id=cid, settings=_make_real_settings()
    )
    session.commit()

    assert len(factory_calls) == 1
    assert real_stub.place_calls == 1
    assert result.success is True


def test_phase_c_constructor_default_uses_fake_only(session):
    """Default constructor still produces a Fake-only executor — v0.16 behavior."""
    _, cid = _seed_approved_candidate(session)
    executor = RealOrderExecutor()
    assert isinstance(executor._transport, FakeKisOrderTransport)

    result = executor.execute(
        session, candidate_id=cid, settings=_make_settings()
    )
    assert result.dry_run is True
    assert result.success is True


# ---------------------------------------------------------------------------
# 26. Phase C scope guard — Phase D (FillSync real) still pending
# ---------------------------------------------------------------------------


def test_phase_c_does_not_introduce_fill_sync_real_helper():
    import importlib

    module = importlib.import_module("app.broker.fill_sync_service")
    forbidden = ("sync_fills_real",)
    for name in forbidden:
        assert not hasattr(module, name), (
            f"Phase C must not introduce {name} on FillSyncService — that is Phase D scope"
        )
