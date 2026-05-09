"""Unit tests for v0.16 Phase D + v1.0 Phase D — FillSyncService.

All tests use an in-memory SQLite DB (fast, isolated).

v1.0 Phase D semantic changes vs v0.16:
  * DRY_RUN orders → skipped (no transport call). v0.16 mock fill creation
    on dry-run is intentionally dropped; the new tests assert the skip.
  * Delta-based idempotent RealFill writes — repeat sync never duplicates.
  * 6-class outcome (FULL / PARTIAL / NONE / REJECTED / CANCELED / FAILED).
  * ApprovalAuditLog REAL_ORDER_FILL_SYNCED / REAL_ORDER_FILL_FAILED /
    FILL_SYNC_NEGATIVE_DELTA event types.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.broker.fill_sync_service import FillSyncResult, FillSyncService
from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisFillStatusResult,
)
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import RealOrderRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.base import Base, utc_now
from app.db.session import create_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Custom transport stubs
# ---------------------------------------------------------------------------


class _PartialTransport(FakeKisOrderTransport):
    """Always returns PARTIALLY_FILLED with filled_quantity=3."""

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        return KisFillStatusResult(
            success=True,
            order_no=order_no,
            status="PARTIALLY_FILLED",
            filled_quantity=3,
            remaining_quantity=7,
            message="partial",
        )


class _PendingTransport(FakeKisOrderTransport):
    """Always returns PENDING (no fill yet)."""

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        return KisFillStatusResult(
            success=True,
            order_no=order_no,
            status="PENDING",
            filled_quantity=0,
            remaining_quantity=10,
            message="pending",
        )


class _CanceledTransport(FakeKisOrderTransport):
    """Always returns CANCELED from the broker side."""

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        return KisFillStatusResult(
            success=True,
            order_no=order_no,
            status="CANCELED",
            filled_quantity=0,
            remaining_quantity=0,
            message="canceled",
        )


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


def _seed_real_order(
    session,
    *,
    status: str = "SUBMITTED",
    estimated_amount: Decimal = Decimal("750_000"),
    quantity: int = 10,
    fake_order_no: str | None = "FAKE-TEST-001",
    dry_run: bool | None = None,
) -> int:
    """Create VirtualAccount → APPROVED OrderCandidate → RealOrder.
    Returns real_order.id.

    Default seed is now ``status="SUBMITTED", dry_run=False`` — v1.0 Phase D
    skips DRY_RUN orders at the FillSyncService transport boundary, so most
    fill-flow tests need a non-DRY_RUN seed. Override either field explicitly
    when exercising dry-run-specific paths.
    """
    acc_repo = VirtualAccountRepository(session)
    acc = acc_repo.create(name="fill-test", initial_cash=Decimal("10_000_000"))
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

    order_repo = RealOrderRepository(session)
    # If the caller did not specify dry_run, default to True for DRY_RUN
    # status only and False for everything else (including SUBMITTED).
    effective_dry_run = (
        dry_run if dry_run is not None else (status == "DRY_RUN")
    )
    order = order_repo.create(
        candidate_id=cand.id,
        symbol="005930",
        side="BUY",
        quantity=quantity,
        order_type="MARKET",
        estimated_amount=estimated_amount,
        status=status,
        dry_run=effective_dry_run,
        fake_order_no=fake_order_no,
    )
    session.commit()
    return order.id


# ---------------------------------------------------------------------------
# 1. FillSyncResult dataclass
# ---------------------------------------------------------------------------


def test_fill_sync_result_as_dict_completeness():
    r = FillSyncResult(
        real_order_id=7,
        fill_status="FULL",
        created_fill_count=1,
        skipped_reason=None,
    )
    d = r.as_dict()
    assert d["real_order_id"] == 7
    assert d["fill_status"] == "FULL"
    assert d["created_fill_count"] == 1
    assert d["skipped_reason"] is None


def test_fill_sync_result_is_frozen():
    r = FillSyncResult(
        real_order_id=1, fill_status="NONE", created_fill_count=0,
        skipped_reason="TEST",
    )
    with pytest.raises((AttributeError, TypeError)):
        r.fill_status = "FULL"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. FULL fill (default FakeKisOrderTransport → FILLED)
# ---------------------------------------------------------------------------


def test_full_fill_creates_real_fill_row(session):
    oid = _seed_real_order(session, quantity=10,
                           estimated_amount=Decimal("750_000"))
    svc = FillSyncService()  # default FakeKisOrderTransport returns FILLED
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FULL"
    assert result.created_fill_count == 1
    assert result.skipped_reason is None

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert len(fills) == 1
    assert fills[0].fill_status == "FULL"
    assert fills[0].quantity == 10
    assert fills[0].symbol == "005930"


def test_full_fill_updates_order_status_to_filled(session):
    """For a non-terminal SUBMITTED order, status must become FILLED."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=5,
                           estimated_amount=Decimal("500_000"))

    svc = FillSyncService()
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FULL"
    from app.db.models import RealOrder
    refreshed = session.get(RealOrder, oid)
    assert refreshed.status == "FILLED"


def test_dry_run_order_is_skipped_no_transport_call(session):
    """v1.0 Phase D: DRY_RUN orders short-circuit with a NONE result and
    skipped_reason='DRY_RUN_ORDER_SKIPPED'. The transport is NEVER called."""
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))

    class _BoomTransport(FakeKisOrderTransport):
        def query_fill_status(self, order_no):  # noqa: D401
            raise AssertionError(
                "transport.query_fill_status MUST NOT be called for DRY_RUN orders"
            )

    svc = FillSyncService(transport=_BoomTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0
    assert result.skipped_reason == "DRY_RUN_ORDER_SKIPPED"

    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    assert order.status == "DRY_RUN"

    fill_repo = RealFillRepository(session)
    assert fill_repo.list_by_order(oid) == []


# ---------------------------------------------------------------------------
# 3. PARTIAL fill (custom stub transport)
# ---------------------------------------------------------------------------


def test_partial_fill_creates_partial_real_fill(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    svc = FillSyncService(transport=_PartialTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "PARTIAL"
    assert result.created_fill_count == 1
    assert result.skipped_reason is None

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert len(fills) == 1
    assert fills[0].fill_status == "PARTIAL"
    assert fills[0].quantity == 3  # _PartialTransport returns filled_quantity=3


# ---------------------------------------------------------------------------
# 4. PENDING / unknown → NONE result, no fill
# ---------------------------------------------------------------------------


def test_pending_status_returns_none_result(session):
    """v1.0: PENDING is now NONE classification (no skipped_reason — sync was successful, just no fill yet)."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=5,
                           estimated_amount=Decimal("500_000"))
    svc = FillSyncService(transport=_PendingTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0
    # v1.0 Phase D: PENDING is a successful sync (not a skip). delta == 0.
    assert result.delta == 0

    fill_repo = RealFillRepository(session)
    assert fill_repo.list_by_order(oid) == []


def test_canceled_broker_status_transitions_order_status(session):
    """v1.0: A broker-side CANCELED on a non-DRY_RUN order transitions
    RealOrder.status → CANCELED and reports fill_status="CANCELED"."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=5,
                           estimated_amount=Decimal("500_000"))
    svc = FillSyncService(transport=_CanceledTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "CANCELED"
    assert result.created_fill_count == 0

    fill_repo = RealFillRepository(session)
    assert fill_repo.list_by_order(oid) == []

    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    assert order.status == "CANCELED"


# ---------------------------------------------------------------------------
# 5. Terminal order states → skipped
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("terminal_status", ["FILLED", "CANCELED", "REJECTED", "FAILED"])
def test_terminal_order_skipped(session, terminal_status):
    """Non-DRY_RUN terminal orders are skipped at the order-status guard."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=5,
                           estimated_amount=Decimal("500_000"))
    # Force terminal status (skipping repository transition guard for test isolation)
    from app.db.models import RealOrder
    raw_order = session.get(RealOrder, oid)
    raw_order.status = terminal_status
    session.commit()

    svc = FillSyncService()
    result = svc.sync_fills(session, oid)

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0
    assert result.skipped_reason == f"ORDER_ALREADY_TERMINAL_{terminal_status}"

    fill_repo = RealFillRepository(session)
    assert fill_repo.list_by_order(oid) == []


# ---------------------------------------------------------------------------
# 6. REAL_ORDER_NOT_FOUND
# ---------------------------------------------------------------------------


def test_nonexistent_order_returns_not_found(session):
    svc = FillSyncService()
    result = svc.sync_fills(session, real_order_id=99999)

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0
    assert result.skipped_reason == "REAL_ORDER_NOT_FOUND"
    assert result.real_order_id == 99999


# ---------------------------------------------------------------------------
# 7. Transport injection
# ---------------------------------------------------------------------------


def test_fill_sync_service_uses_fake_transport_by_default():
    svc = FillSyncService()
    assert isinstance(svc._transport, FakeKisOrderTransport)


def test_fill_sync_service_accepts_custom_transport():
    custom = _PartialTransport()
    svc = FillSyncService(transport=custom)
    assert svc._transport is custom


# ---------------------------------------------------------------------------
# 8. AST guard — no forbidden imports in fill_sync_service.py
# ---------------------------------------------------------------------------


def _service_source() -> str:
    return (PROJECT_ROOT / "app" / "broker" / "fill_sync_service.py").read_text(
        encoding="utf-8"
    )


def test_fill_sync_service_has_no_httpx_import():
    src = _service_source()
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


def test_fill_sync_service_has_no_requests_import():
    src = _service_source()
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


def test_fill_sync_service_has_no_urllib_import():
    src = _service_source()
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


def test_fill_sync_service_has_no_kis_http_transport():
    src = _service_source()
    assert "KisHttpOrderTransport" not in src, (
        "KisHttpOrderTransport must not be referenced in Phase D FillSyncService"
    )


# ---------------------------------------------------------------------------
# 9. No raw-response storage method
# ---------------------------------------------------------------------------


def test_fill_sync_service_has_no_raw_response_method():
    methods = [m for m in dir(FillSyncService) if not m.startswith("_")]
    raw_methods = [m for m in methods if "raw" in m.lower()]
    assert raw_methods == [], f"Must not expose raw methods: {raw_methods}"


# ---------------------------------------------------------------------------
# 10. fill_price and gross_amount are positive
# ---------------------------------------------------------------------------


def test_full_fill_amounts_are_positive(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("750_000"))
    svc = FillSyncService()
    svc.sync_fills(session, oid)
    session.commit()

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.fill_price > 0
    assert fill.gross_amount > 0
    assert fill.net_amount > 0


# ===========================================================================
# v1.0 Phase D — delta-based idempotency + audit + new classifications
# ===========================================================================


from app.broker.kis_order_client import (  # noqa: E402
    KisCancelResult,
    KisOrderResult,
)
from app.data.repositories.approval_audit_log import (  # noqa: E402
    ApprovalAuditLogRepository,
    VALID_EVENT_TYPES,
)


# ---------------------------------------------------------------------------
# Phase D transport stubs (programmable per call)
# ---------------------------------------------------------------------------


class _ScriptedTransport:
    """Programmable KisOrderClientInterface for Phase D unit tests.

    Each call to query_fill_status() pops the next response from
    ``responses`` (or returns the last one indefinitely if exhausted).
    Place / cancel raise to flag accidental misuse.
    """

    def __init__(self, responses: list[KisFillStatusResult]) -> None:
        self.responses = responses
        self.calls = 0

    def place_order(self, request):  # pragma: no cover
        raise AssertionError("place_order must not be called by FillSyncService")

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        self.calls += 1
        idx = min(self.calls - 1, len(self.responses) - 1)
        return self.responses[idx]

    def cancel_order(self, order_no: str) -> KisCancelResult:  # pragma: no cover
        raise AssertionError("cancel_order must not be called by FillSyncService")


def _full_response(qty: int, *, success: bool = True) -> KisFillStatusResult:
    return KisFillStatusResult(
        success=success, order_no="ord-X", filled_quantity=qty,
        remaining_quantity=0, status="FILLED", message="full",
    )


def _partial_response(filled: int, total: int) -> KisFillStatusResult:
    return KisFillStatusResult(
        success=True, order_no="ord-X", filled_quantity=filled,
        remaining_quantity=max(total - filled, 0),
        status="PARTIALLY_FILLED", message="partial",
    )


def _pending_response(total: int) -> KisFillStatusResult:
    return KisFillStatusResult(
        success=True, order_no="ord-X", filled_quantity=0,
        remaining_quantity=total, status="PENDING", message="pending",
    )


def _rejected_response() -> KisFillStatusResult:
    return KisFillStatusResult(
        success=False, order_no="ord-X", filled_quantity=0,
        remaining_quantity=0, status="REJECTED", message="REJECTED",
    )


def _canceled_response() -> KisFillStatusResult:
    return KisFillStatusResult(
        success=True, order_no="ord-X", filled_quantity=0,
        remaining_quantity=0, status="CANCELED", message="canceled",
    )


def _failed_response() -> KisFillStatusResult:
    return KisFillStatusResult(
        success=False, order_no="ord-X", filled_quantity=0,
        remaining_quantity=0, status="PENDING",
        message="UNKNOWN: KIS HTTP 503 (server error)",
    )


# ---------------------------------------------------------------------------
# 11. v1.0 Phase D — audit event_type whitelist
# ---------------------------------------------------------------------------


def test_phase_d_audit_event_types_extended():
    assert "REAL_ORDER_FILL_SYNCED" in VALID_EVENT_TYPES
    assert "REAL_ORDER_FILL_FAILED" in VALID_EVENT_TYPES
    assert "FILL_SYNC_NEGATIVE_DELTA" in VALID_EVENT_TYPES


# ---------------------------------------------------------------------------
# 12. Delta-based idempotency
# ---------------------------------------------------------------------------


def test_phase_d_full_fill_delta_first_call(session):
    oid = _seed_real_order(session, quantity=10,
                           estimated_amount=Decimal("750_000"))
    svc = FillSyncService(transport=_ScriptedTransport([_full_response(10)]))
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FULL"
    assert result.created_fill_count == 1
    assert result.delta == 10
    assert result.fills_total == 10


def test_phase_d_repeated_full_sync_is_idempotent(session):
    oid = _seed_real_order(session, quantity=10,
                           estimated_amount=Decimal("750_000"))
    transport = _ScriptedTransport([_full_response(10), _full_response(10)])
    svc = FillSyncService(transport=transport)

    # First call creates 1 fill (delta=10)
    r1 = svc.sync_fills(session, oid)
    session.commit()
    # Second call: delta = 10 - 10 = 0 → no new row
    r2 = svc.sync_fills(session, oid)
    session.commit()

    assert r1.created_fill_count == 1
    assert r2.created_fill_count == 0
    assert r2.delta == 0

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert len(fills) == 1, (
        "Repeated sync must NOT duplicate the fill row"
    )


def test_phase_d_partial_then_full_appends_only_delta(session):
    """First sync sees partial fill of 4, second sync sees full fill of 10.
    Two RealFill rows are created with quantities [4, 6]."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))

    transport = _ScriptedTransport([
        _partial_response(4, 10),
        _full_response(10),
    ])
    svc = FillSyncService(transport=transport)
    r1 = svc.sync_fills(session, oid)
    session.commit()
    r2 = svc.sync_fills(session, oid)
    session.commit()

    assert r1.fill_status == "PARTIAL"
    assert r1.delta == 4
    assert r2.fill_status == "FULL"
    assert r2.delta == 6

    fill_repo = RealFillRepository(session)
    quantities = sorted(f.quantity for f in fill_repo.list_by_order(oid))
    assert quantities == [4, 6]


def test_phase_d_partial_idempotent_when_filled_quantity_unchanged(session):
    """Two PARTIAL responses with the same filled_quantity → only first creates a fill."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))

    transport = _ScriptedTransport([
        _partial_response(3, 10),
        _partial_response(3, 10),
    ])
    svc = FillSyncService(transport=transport)
    svc.sync_fills(session, oid)
    session.commit()
    r2 = svc.sync_fills(session, oid)
    session.commit()

    assert r2.created_fill_count == 0
    assert r2.delta == 0
    fill_repo = RealFillRepository(session)
    assert len(fill_repo.list_by_order(oid)) == 1


def test_phase_d_pending_does_not_change_status(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    svc = FillSyncService(transport=_ScriptedTransport([_pending_response(10)]))
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "NONE"
    assert result.delta == 0
    assert result.created_fill_count == 0
    from app.db.models import RealOrder
    refreshed = session.get(RealOrder, oid)
    assert refreshed.status == "SUBMITTED"


# ---------------------------------------------------------------------------
# 13. Negative delta (KIS reduction below internal record)
# ---------------------------------------------------------------------------


def test_phase_d_negative_delta_writes_audit_and_returns_failed(session):
    """KIS reports a smaller filled_quantity than our internal record →
    audit row + FAILED result. We use PARTIAL→PARTIAL to keep the order
    in PARTIALLY_FILLED (non-terminal) for the second sync."""
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    transport = _ScriptedTransport([
        _partial_response(8, 10),  # first sync -> creates 8
        _partial_response(3, 10),  # second sync -> KIS shows 3 (delta = -5)
    ])
    svc = FillSyncService(transport=transport)

    svc.sync_fills(session, oid)
    session.commit()

    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FAILED"
    assert result.delta == -5
    assert result.skipped_reason == "NEGATIVE_DELTA"

    fill_repo = RealFillRepository(session)
    # No new RealFill row created on negative delta — only the original 8.
    assert len(fill_repo.list_by_order(oid)) == 1

    # Audit row written
    audit_repo = ApprovalAuditLogRepository(session)
    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    rows = [
        r for r in audit_repo.list_by_candidate(order.candidate_id)
        if r.event_type == "FILL_SYNC_NEGATIVE_DELTA"
    ]
    assert len(rows) == 1
    assert rows[0].details_json["delta"] == -5


# ---------------------------------------------------------------------------
# 14. REJECTED / CANCELED transitions (no fills written)
# ---------------------------------------------------------------------------


def test_phase_d_rejected_transitions_status(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    svc = FillSyncService(transport=_ScriptedTransport([_rejected_response()]))
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "REJECTED"
    assert result.created_fill_count == 0

    from app.db.models import RealOrder
    refreshed = session.get(RealOrder, oid)
    assert refreshed.status == "REJECTED"


def test_phase_d_canceled_transitions_status(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    svc = FillSyncService(transport=_ScriptedTransport([_canceled_response()]))
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "CANCELED"
    from app.db.models import RealOrder
    refreshed = session.get(RealOrder, oid)
    assert refreshed.status == "CANCELED"


# ---------------------------------------------------------------------------
# 15. FAILED — transport-level / unrecognised
# ---------------------------------------------------------------------------


def test_phase_d_transport_failure_marks_failed_and_audits(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    svc = FillSyncService(transport=_ScriptedTransport([_failed_response()]))
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FAILED"
    assert result.delta == 0
    assert result.created_fill_count == 0

    audit_repo = ApprovalAuditLogRepository(session)
    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    rows = [
        r for r in audit_repo.list_by_candidate(order.candidate_id)
        if r.event_type == "REAL_ORDER_FILL_FAILED"
    ]
    assert len(rows) == 1


def test_phase_d_transport_raised_marks_failed_and_audits(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))

    class _RaisingTransport:
        def place_order(self, request):  # pragma: no cover
            raise AssertionError("must not be called")

        def query_fill_status(self, order_no):
            raise RuntimeError("simulated network outage")

        def cancel_order(self, order_no):  # pragma: no cover
            raise AssertionError("must not be called")

    svc = FillSyncService(transport=_RaisingTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FAILED"
    assert result.skipped_reason == "TRANSPORT_RAISED"

    audit_repo = ApprovalAuditLogRepository(session)
    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    rows = [
        r for r in audit_repo.list_by_candidate(order.candidate_id)
        if r.event_type == "REAL_ORDER_FILL_FAILED"
    ]
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 16. Audit details — forbidden keys never present
# ---------------------------------------------------------------------------


def test_phase_d_audit_details_have_no_forbidden_keys(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"))
    transport = _ScriptedTransport([
        _full_response(10),       # SYNCED
        _partial_response(4, 10), # NEGATIVE_DELTA
    ])
    svc = FillSyncService(transport=transport)
    svc.sync_fills(session, oid)
    session.commit()
    svc.sync_fills(session, oid)
    session.commit()

    audit_repo = ApprovalAuditLogRepository(session)
    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    rows = audit_repo.list_by_candidate(order.candidate_id)

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
# 17. plaintext order_no never persisted by FillSyncService
# ---------------------------------------------------------------------------


def test_phase_d_plaintext_order_no_never_persisted(session):
    oid = _seed_real_order(session, status="SUBMITTED", quantity=10,
                           estimated_amount=Decimal("1_000_000"),
                           fake_order_no=None)
    plaintext = "PLAINTEXT-ORD-NO-77777"

    captured = {"refs": []}

    class _CapturingTransport(_ScriptedTransport):
        def query_fill_status(self, order_no):
            captured["refs"].append(order_no)
            return super().query_fill_status(order_no)

    transport = _CapturingTransport([_full_response(10)])
    svc = FillSyncService(transport=transport)
    svc.sync_fills(session, oid, kis_order_no_plaintext=plaintext)
    session.commit()

    # Transport saw the plaintext (in-memory only)
    assert captured["refs"] == [plaintext]

    # Plaintext NEVER appears in any persisted column
    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    for f in fills:
        for col in (f.symbol, f.side, f.fill_status):
            assert plaintext not in str(col)

    audit_repo = ApprovalAuditLogRepository(session)
    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    for row in audit_repo.list_by_candidate(order.candidate_id):
        assert plaintext not in str(row.reason or "")
        assert plaintext not in str(row.details_json or {})


# ---------------------------------------------------------------------------
# 18. Phase D scope guard — Reconciliation / auto-polling NOT introduced
# ---------------------------------------------------------------------------


def test_phase_d_no_reconciliation_module():
    """Phase D explicitly defers Reconciliation to v1.1 — module must NOT exist."""
    from pathlib import Path

    candidates = [
        PROJECT_ROOT / "app" / "broker" / "reconciliation_service.py",
        PROJECT_ROOT / "app" / "broker" / "reconciliation.py",
        PROJECT_ROOT / "app" / "reconciliation" / "__init__.py",
    ]
    for path in candidates:
        assert not path.exists(), (
            f"v1.0 Phase D must not introduce reconciliation module {path}"
        )


def test_phase_d_no_auto_fill_sync_polling_job():
    """Phase D defers auto-polling jobs to v1.1 — none must be registered."""
    from app.scheduler import jobs as job_module

    forbidden_names = (
        "auto_sync_real_order_fills",
        "poll_real_order_fills",
        "fill_sync_polling",
    )
    for name in forbidden_names:
        assert not hasattr(job_module, name), (
            f"v1.0 Phase D must not introduce {name} — auto-polling is v1.1"
        )
