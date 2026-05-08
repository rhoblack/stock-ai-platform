"""Unit tests for v0.16 Phase D — FillSyncService.

All tests use an in-memory SQLite DB (fast, isolated).

Scope:
  * FillSyncResult dataclass: as_dict / frozen.
  * FULL fill: FakeKisOrderTransport (default) → RealFill created, order → FILLED.
  * PARTIAL fill: custom stub transport → RealFill(PARTIAL) created.
  * PENDING / unknown status → no fill, NONE result.
  * Order already in terminal fill state (FILLED/CANCELED/REJECTED/FAILED) → skipped.
  * DRY_RUN order: fill IS created but order status NOT updated.
  * REAL_ORDER_NOT_FOUND: nonexistent order id → NONE result.
  * Transport injection verified (FakeKisOrderTransport default).
  * AST guard: no httpx / requests / urllib in fill_sync_service.py.
  * No raw-response storage method on FillSyncService.
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
    status: str = "DRY_RUN",
    estimated_amount: Decimal = Decimal("750_000"),
    quantity: int = 10,
    fake_order_no: str | None = "FAKE-TEST-001",
) -> int:
    """Create VirtualAccount → APPROVED OrderCandidate → RealOrder.
    Returns real_order.id.
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
    order = order_repo.create(
        candidate_id=cand.id,
        symbol="005930",
        side="BUY",
        quantity=quantity,
        order_type="MARKET",
        estimated_amount=estimated_amount,
        status=status,
        dry_run=(status == "DRY_RUN"),
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
    oid = _seed_real_order(session, status="DRY_RUN", quantity=10,
                           estimated_amount=Decimal("750_000"))
    svc = FillSyncService()  # default FakeKisOrderTransport
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
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))
    # Manually move to SUBMITTED (non-terminal, non-DRY_RUN)
    order_repo = RealOrderRepository(session)
    order = order_repo.get_by_id(oid)
    # Patch status directly for test isolation (skip normal transition guard)
    from app.db.models import RealOrder
    raw_order = session.get(RealOrder, oid)
    raw_order.status = "SUBMITTED"
    session.commit()

    svc = FillSyncService()
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FULL"
    refreshed = session.get(RealOrder, oid)
    assert refreshed.status == "FILLED"


def test_full_fill_dry_run_order_status_not_changed(session):
    """DRY_RUN orders: fill IS created but order status stays DRY_RUN."""
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))
    svc = FillSyncService()
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "FULL"
    assert result.created_fill_count == 1

    from app.db.models import RealOrder
    order = session.get(RealOrder, oid)
    assert order.status == "DRY_RUN", (
        "DRY_RUN is terminal — status must not change after fill sync"
    )

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert len(fills) == 1


# ---------------------------------------------------------------------------
# 3. PARTIAL fill (custom stub transport)
# ---------------------------------------------------------------------------


def test_partial_fill_creates_partial_real_fill(session):
    oid = _seed_real_order(session, status="DRY_RUN", quantity=10,
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
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))
    svc = FillSyncService(transport=_PendingTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0
    assert result.skipped_reason == "FILL_STATUS_PENDING"

    fill_repo = RealFillRepository(session)
    fills = fill_repo.list_by_order(oid)
    assert fills == []


def test_canceled_broker_status_returns_none_result(session):
    """A CANCELED status from broker (not terminal order) → NONE result."""
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))
    svc = FillSyncService(transport=_CanceledTransport())
    result = svc.sync_fills(session, oid)
    session.commit()

    assert result.fill_status == "NONE"
    assert result.created_fill_count == 0

    fill_repo = RealFillRepository(session)
    assert fill_repo.list_by_order(oid) == []


# ---------------------------------------------------------------------------
# 5. Terminal order states → skipped
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("terminal_status", ["FILLED", "CANCELED", "REJECTED", "FAILED"])
def test_terminal_order_skipped(session, terminal_status):
    oid = _seed_real_order(session, status="DRY_RUN", quantity=5,
                           estimated_amount=Decimal("500_000"))
    # Force terminal status
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
    oid = _seed_real_order(session, status="DRY_RUN", quantity=10,
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
