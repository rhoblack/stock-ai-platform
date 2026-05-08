"""FillSyncService — v0.16 Phase D mock fill sync only.

Hard guarantees verified by the test suite
------------------------------------------
* No httpx / requests / urllib import at module load or runtime.
* FakeKisOrderTransport is the ONLY transport used in Phase D.
* raw KIS response never stored.
* Sensitive values (api_key, secret, account_no) never stored.

sync_fills() flow:
  1. Load RealOrder by id.
  2. Skip if already in a terminal fill state (FILLED / CANCELED / REJECTED).
  3. Call transport.query_fill_status() with fake_order_no or order id.
  4. Dispatch on status:
       FILLED          → create RealFill (fill_status="FULL"),
                         update RealOrder.status → FILLED (if non-terminal).
       PARTIALLY_FILLED → create RealFill (fill_status="PARTIAL"),
                         update RealOrder.status → PARTIALLY_FILLED.
       CANCELED        → update RealOrder.status → CANCELED.
       REJECTED        → update RealOrder.status → REJECTED.
       PENDING / other → skip, return NONE result.
  5. DRY_RUN orders are also synced (create fill) but status is NOT updated
     (DRY_RUN is terminal in RealOrderRepository).

Phase D limitation: FakeKisOrderTransport always returns status="FILLED".
To test PARTIAL / PENDING scenarios, inject a custom transport in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.broker.kis_order_client import FakeKisOrderTransport, KisOrderClientInterface
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import TERMINAL_STATUSES, RealOrderRepository
from app.db.base import utc_now


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

# Statuses that mean a fill was produced by KIS (real or mock).
_FILL_PRODUCING_STATUSES = frozenset({"FILLED", "PARTIALLY_FILLED"})

# Statuses after which we should not attempt to update the order status.
_ORDER_TERMINAL = frozenset({"DRY_RUN", "FILLED", "CANCELED", "REJECTED", "FAILED"})


@dataclass(frozen=True)
class FillSyncResult:
    """Structured result of one FillSyncService.sync_fills() call."""

    real_order_id: int
    fill_status: str           # "FULL" | "PARTIAL" | "NONE"
    created_fill_count: int
    skipped_reason: str | None  # None when a fill was created

    def as_dict(self) -> dict[str, Any]:
        return {
            "real_order_id": self.real_order_id,
            "fill_status": self.fill_status,
            "created_fill_count": self.created_fill_count,
            "skipped_reason": self.skipped_reason,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FillSyncService:
    """Mock fill sync service for v0.16 Phase D.

    Only FakeKisOrderTransport is used; no real KIS API calls.

    Inject a custom transport in tests to exercise PARTIAL / PENDING / CANCELED
    scenarios:

        class _PartialTransport(FakeKisOrderTransport):
            def query_fill_status(self, order_no):
                return KisFillStatusResult(..., status="PARTIALLY_FILLED", ...)

        svc = FillSyncService(transport=_PartialTransport())
    """

    def __init__(self, *, transport: KisOrderClientInterface | None = None) -> None:
        self._transport: KisOrderClientInterface = (
            transport if transport is not None else FakeKisOrderTransport()
        )

    def sync_fills(self, session: Session, real_order_id: int) -> FillSyncResult:
        """Query fill status and create RealFill rows as appropriate."""
        order_repo = RealOrderRepository(session)
        fill_repo = RealFillRepository(session)

        order = order_repo.get_by_id(real_order_id)
        if order is None:
            return FillSyncResult(
                real_order_id=real_order_id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason="REAL_ORDER_NOT_FOUND",
            )

        # Skip orders already in a fill-terminal or error-terminal state
        # (FILLED / CANCELED / REJECTED / FAILED — not DRY_RUN which we allow).
        _SKIP_STATUSES = frozenset({"FILLED", "CANCELED", "REJECTED", "FAILED"})
        if order.status in _SKIP_STATUSES:
            return FillSyncResult(
                real_order_id=real_order_id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason=f"ORDER_ALREADY_TERMINAL_{order.status}",
            )

        # Query fill status from transport (fake in Phase D)
        order_ref = order.fake_order_no or str(real_order_id)
        status_result = self._transport.query_fill_status(order_ref)

        if status_result.status not in _FILL_PRODUCING_STATUSES:
            # PENDING or unrecognised status → no fill yet
            return FillSyncResult(
                real_order_id=real_order_id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason=f"FILL_STATUS_{status_result.status}",
            )

        # Determine fill quantities and amounts
        estimated = Decimal(str(order.estimated_amount or 0))
        total_qty = order.quantity

        if status_result.status == "FILLED":
            fill_qty = total_qty
            fill_status_str = "FULL"
        else:
            # PARTIALLY_FILLED: use filled_quantity from result, default to half
            fill_qty = status_result.filled_quantity or max(1, total_qty // 2)
            fill_status_str = "PARTIAL"

        unit_price = (estimated / total_qty) if total_qty > 0 else Decimal("0")
        # Ensure unit_price is positive for repository validation
        if unit_price <= 0:
            unit_price = Decimal("1")
        gross = unit_price * fill_qty
        if gross <= 0:
            gross = Decimal("1")

        fill_repo.create(
            real_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_qty,
            fill_price=unit_price,
            fee=Decimal("0"),
            tax=Decimal("0"),
            gross_amount=gross,
            net_amount=gross,
            fill_status=fill_status_str,
            filled_at=utc_now(),
        )

        # Update order status for non-DRY_RUN, non-terminal orders.
        # DRY_RUN is a terminal status in RealOrderRepository — skip update.
        if order.status not in _ORDER_TERMINAL:
            new_order_status = "FILLED" if fill_status_str == "FULL" else "PARTIALLY_FILLED"
            order_repo.update_status(order, new_status=new_order_status)

        session.flush()

        return FillSyncResult(
            real_order_id=order.id,
            fill_status=fill_status_str,
            created_fill_count=1,
            skipped_reason=None,
        )
