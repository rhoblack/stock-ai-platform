"""FillSyncService — v0.16 Phase D mock + v1.0 Phase D delta-based idempotent sync.

v1.0 Phase D extends the v0.16 mock service with:
  * **Delta-based idempotency** — RealFill rows are written only when
    ``kis_total > existing_total``. Repeated sync calls on the same upstream
    KIS state produce zero new rows.
  * **6-class outcome** — FULL / PARTIAL / NONE / REJECTED / CANCELED / FAILED.
    The previous v0.16 mock returned only FULL / PARTIAL / NONE.
  * **DRY_RUN orders skip transport** — calling the sync on a dry-run RealOrder
    is a no-op (NONE result, ``DRY_RUN_ORDER_SKIPPED`` reason). With the v1.0
    real transport (``HttpxKisOrderTransport``), querying KIS for a fake
    order_no would either fail outright or, worse, hit a real broker order
    id collision. Dry-run skip prevents both.
  * **Audit logging** — every sync result writes one ApprovalAuditLog row:
        REAL_ORDER_FILL_SYNCED   (FULL / PARTIAL / NONE / REJECTED / CANCELED)
        REAL_ORDER_FILL_FAILED   (transport failure / UNKNOWN / unrecognised)
        FILL_SYNC_NEGATIVE_DELTA (KIS reduction below internal record)
    details_json carries whitelist fields only — no broker_order_no,
    no real_order_id, no raw response, no secrets.

Hard guarantees verified by the test suite
------------------------------------------
* No httpx / requests / urllib import at module load or runtime.
* Transport is dependency-injected — the service never instantiates a real
  HTTP client itself.
* raw KIS response NEVER stored.
* Sensitive values (api_key, secret, account_no) NEVER stored.
* Existing v0.16 dry-run "always FILLED" semantic is REPLACED by skip — any
  prior caller that depended on dry-run fill creation must update.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisFillStatusResult,
    KisOrderClientInterface,
)
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
)
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import RealOrderRepository
from app.db.base import utc_now
from app.db.models import RealOrder


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Statuses indicating a fill (full or partial) was confirmed at the broker.
_FILL_PRODUCING_STATUSES = frozenset({"FILLED", "PARTIALLY_FILLED"})

# Statuses indicating no upstream fill action remains (broker-side terminal).
_BROKER_TERMINAL_STATUSES = frozenset({"CANCELED", "REJECTED"})

# Order statuses that block any further sync (already terminal at our side).
_ORDER_SKIP_STATUSES = frozenset({"FILLED", "CANCELED", "REJECTED", "FAILED"})

# Order statuses where it is safe to issue an order-status transition via
# update_status() without re-creating a row. DRY_RUN is intentionally NOT in
# this set — DRY_RUN is a v0.16 terminal status in RealOrderRepository.
_ORDER_NON_TERMINAL = frozenset({"CREATED", "SUBMITTED", "PARTIALLY_FILLED"})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FillSyncResult:
    """Structured result of one FillSyncService.sync_fills() call.

    Field reference
    ---------------
    real_order_id        : the RealOrder.id targeted (regardless of outcome).
    fill_status          : one of FULL / PARTIAL / NONE / REJECTED / CANCELED / FAILED.
    created_fill_count   : number of NEW RealFill rows created. With delta-based
                           idempotency this is 0 or 1 — never higher per call.
    skipped_reason       : non-None only when the service short-circuited before
                           computing a fill (DRY_RUN_ORDER_SKIPPED /
                           ORDER_ALREADY_TERMINAL_<X> / REAL_ORDER_NOT_FOUND /
                           TRANSPORT_FAILURE / UNRECOGNISED_STATUS_<X> /
                           NEGATIVE_DELTA / ...).
    delta                : kis_total - existing_total. Zero on idempotent
                           re-call, positive when a new fill was minted, zero
                           also when the broker reports no fill yet.
    fills_total          : total internal RealFill quantity AFTER this sync.
    real_order_status    : RealOrder.status AFTER this sync (echo for the API).
    """

    real_order_id: int
    fill_status: str
    created_fill_count: int
    skipped_reason: str | None
    delta: int = 0
    fills_total: int = 0
    real_order_status: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "real_order_id": self.real_order_id,
            "fill_status": self.fill_status,
            "created_fill_count": self.created_fill_count,
            "skipped_reason": self.skipped_reason,
            "delta": self.delta,
            "fills_total": self.fills_total,
            "real_order_status": self.real_order_status,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_fill_response(
    response: KisFillStatusResult, total_qty: int
) -> str:
    """Map the v1.0 transport's KisFillStatusResult to the 6-class
    FillSyncResult.fill_status token.

    Phase B's HttpxKisOrderTransport produces — by status string:
        FILLED             → FULL    (success=True)
        PARTIALLY_FILLED   → PARTIAL (success=True)
        PENDING + success=True  → NONE   (legitimate "no fill yet")
        PENDING + success=False → FAILED (transport-mapped UNKNOWN)
        REJECTED           → REJECTED (success=False)
        CANCELED           → CANCELED (success=False)
        anything else      → FAILED
    """
    s = response.status
    if s == "FILLED":
        return "FULL"
    if s == "PARTIALLY_FILLED":
        return "PARTIAL"
    if s == "REJECTED":
        return "REJECTED"
    if s == "CANCELED":
        return "CANCELED"
    if s == "PENDING":
        return "NONE" if response.success else "FAILED"
    return "FAILED"


def _effective_kis_total(
    classification: str,
    response: KisFillStatusResult,
    total_qty: int,
) -> int:
    """Compute the authoritative cumulative filled quantity for delta.

    Policy:
      FULL    → max(filled_quantity, total_qty). Handles legacy
                 FakeKisOrderTransport which returns filled_quantity=0
                 for FILLED. Real KIS responses populate filled_quantity
                 and the max preserves the higher-of-two source-of-truth.
      PARTIAL → filled_quantity (must be reported by the broker).
      NONE / REJECTED / CANCELED / FAILED → 0.
    """
    raw = max(int(response.filled_quantity or 0), 0)
    if classification == "FULL":
        return max(raw, total_qty if total_qty > 0 else 0)
    if classification == "PARTIAL":
        return raw
    return 0


def _safe_unit_price(order: RealOrder, total_qty: int) -> Decimal:
    """Compute a unit price that is strictly positive (RealFill validation)."""
    estimated = Decimal(str(order.estimated_amount or 0))
    if total_qty > 0 and estimated > 0:
        unit = estimated / total_qty
    else:
        unit = Decimal("0")
    return unit if unit > 0 else Decimal("1")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class FillSyncService:
    """Fill sync service for v0.16 Phase D + v1.0 Phase D.

    Construction
    ------------
    ``transport`` is dependency-injected. The default is FakeKisOrderTransport
    so unit tests and dry-run paths run without real HTTP. Production callers
    inject ``HttpxKisOrderTransport`` (or any non-Fake KisOrderClientInterface).

    Public API
    ----------
    ``sync_fills(session, real_order_id, *, kis_order_no_plaintext=None)``.

    The optional ``kis_order_no_plaintext`` parameter is the resolution path
    for non-DRY_RUN orders: callers who still hold the plaintext order_no
    (e.g. immediately after a successful Phase C place_order) pass it in. The
    service NEVER persists or logs that plaintext — it flows through the
    transport in-memory only. When unset, the service falls back to
    ``order.fake_order_no`` (DRY_RUN orders only) or ``str(real_order_id)``
    (non-dry-run, non-resolvable — production transport will return UNKNOWN
    and the operator follows RUNBOOK §6).
    """

    def __init__(
        self, *, transport: KisOrderClientInterface | None = None
    ) -> None:
        self._transport: KisOrderClientInterface = (
            transport if transport is not None else FakeKisOrderTransport()
        )

    # -----------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------

    def sync_fills(
        self,
        session: Session,
        real_order_id: int,
        *,
        kis_order_no_plaintext: str | None = None,
    ) -> FillSyncResult:
        order_repo = RealOrderRepository(session)
        fill_repo = RealFillRepository(session)
        audit_repo = ApprovalAuditLogRepository(session)

        order = order_repo.get_by_id(real_order_id)
        if order is None:
            return FillSyncResult(
                real_order_id=real_order_id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason="REAL_ORDER_NOT_FOUND",
                delta=0,
                fills_total=0,
                real_order_status=None,
            )

        # ── DRY_RUN orders skip transport entirely ─────────────────────
        # v1.0 policy: a dry-run RealOrder has no real broker order_no, so
        # querying KIS for it is meaningless and dangerous (could collide
        # with another real broker order_no). The service short-circuits
        # before touching the transport. No audit row is written for skip
        # cases — the call had no effect.
        if order.dry_run is True or order.status == "DRY_RUN":
            return FillSyncResult(
                real_order_id=order.id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason="DRY_RUN_ORDER_SKIPPED",
                delta=0,
                fills_total=fill_repo.total_filled_quantity(order.id),
                real_order_status=order.status,
            )

        # ── Order already in a terminal state at our side ─────────────
        if order.status in _ORDER_SKIP_STATUSES:
            return FillSyncResult(
                real_order_id=order.id,
                fill_status="NONE",
                created_fill_count=0,
                skipped_reason=f"ORDER_ALREADY_TERMINAL_{order.status}",
                delta=0,
                fills_total=fill_repo.total_filled_quantity(order.id),
                real_order_status=order.status,
            )

        # ── Resolve the order ref to send to KIS ──────────────────────
        # Operator-supplied plaintext takes precedence. Fallback to
        # fake_order_no (only meaningful for DRY_RUN, already filtered out
        # above) or the DB primary key (KIS will return UNKNOWN — operator
        # follows RUNBOOK §6).
        order_ref = (
            kis_order_no_plaintext
            or order.fake_order_no
            or str(real_order_id)
        )

        try:
            status_result = self._transport.query_fill_status(order_ref)
        except Exception:  # noqa: BLE001 — transport must never raise to caller
            audit_repo.append(
                candidate_id=order.candidate_id,
                event_type="REAL_ORDER_FILL_FAILED",
                reason="transport.query_fill_status raised",
                details={
                    "classification": "FAILED",
                    "dry_run": False,
                    "symbol": order.symbol,
                    "side": order.side,
                },
            )
            session.flush()
            return FillSyncResult(
                real_order_id=order.id,
                fill_status="FAILED",
                created_fill_count=0,
                skipped_reason="TRANSPORT_RAISED",
                delta=0,
                fills_total=fill_repo.total_filled_quantity(order.id),
                real_order_status=order.status,
            )

        return self._dispatch_status(
            session=session,
            order=order,
            order_repo=order_repo,
            fill_repo=fill_repo,
            audit_repo=audit_repo,
            status_result=status_result,
        )

    # -----------------------------------------------------------------
    # Status dispatch + delta-based idempotency
    # -----------------------------------------------------------------

    def _dispatch_status(
        self,
        *,
        session: Session,
        order: RealOrder,
        order_repo: RealOrderRepository,
        fill_repo: RealFillRepository,
        audit_repo: ApprovalAuditLogRepository,
        status_result: KisFillStatusResult,
    ) -> FillSyncResult:
        total_qty = order.quantity
        classification = _classify_fill_response(status_result, total_qty)

        # ── FAILED (transport-level) ─────────────────────────────────
        if classification == "FAILED":
            audit_repo.append(
                candidate_id=order.candidate_id,
                event_type="REAL_ORDER_FILL_FAILED",
                reason=f"unrecognised KIS status: {status_result.status}",
                details={
                    "classification": "FAILED",
                    "dry_run": False,
                    "symbol": order.symbol,
                    "side": order.side,
                    "kis_status": status_result.status,
                },
            )
            session.flush()
            return FillSyncResult(
                real_order_id=order.id,
                fill_status="FAILED",
                created_fill_count=0,
                skipped_reason=f"UNRECOGNISED_STATUS_{status_result.status}",
                delta=0,
                fills_total=fill_repo.total_filled_quantity(order.id),
                real_order_status=order.status,
            )

        # ── REJECTED / CANCELED (no fill, transition order status) ───
        if classification in ("REJECTED", "CANCELED"):
            new_status = "REJECTED" if classification == "REJECTED" else "CANCELED"
            if order.status in _ORDER_NON_TERMINAL:
                order_repo.update_status(order, new_status=new_status)
            audit_repo.append(
                candidate_id=order.candidate_id,
                event_type="REAL_ORDER_FILL_SYNCED",
                reason=f"KIS reported {classification}",
                details={
                    "classification": classification,
                    "dry_run": False,
                    "symbol": order.symbol,
                    "side": order.side,
                    "delta": 0,
                },
            )
            session.flush()
            return FillSyncResult(
                real_order_id=order.id,
                fill_status=classification,
                created_fill_count=0,
                skipped_reason=None,
                delta=0,
                fills_total=fill_repo.total_filled_quantity(order.id),
                real_order_status=order.status,
            )

        # ── FULL / PARTIAL / NONE ────────────────────────────────────
        existing_total = fill_repo.total_filled_quantity(order.id)
        kis_total = _effective_kis_total(classification, status_result, total_qty)
        delta = kis_total - existing_total

        if delta < 0:
            audit_repo.append(
                candidate_id=order.candidate_id,
                event_type="FILL_SYNC_NEGATIVE_DELTA",
                reason="KIS reports filled_quantity below internal RealFill sum",
                details={
                    "classification": classification,
                    "dry_run": False,
                    "symbol": order.symbol,
                    "side": order.side,
                    "delta": int(delta),
                    "existing_total": int(existing_total),
                    "kis_total": int(kis_total),
                },
            )
            session.flush()
            return FillSyncResult(
                real_order_id=order.id,
                fill_status="FAILED",
                created_fill_count=0,
                skipped_reason="NEGATIVE_DELTA",
                delta=int(delta),
                fills_total=int(existing_total),
                real_order_status=order.status,
            )

        created_count = 0
        if delta > 0:
            unit_price = _safe_unit_price(order, total_qty)
            gross = unit_price * Decimal(delta)
            if gross <= 0:
                gross = Decimal("1")
            # FULL when this fill brings us to the ordered total; PARTIAL
            # otherwise.
            fill_status_str = (
                "FULL"
                if (existing_total + delta) >= total_qty and total_qty > 0
                else "PARTIAL"
            )
            fill_repo.create(
                real_order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=delta,
                fill_price=unit_price,
                fee=Decimal("0"),
                tax=Decimal("0"),
                gross_amount=gross,
                net_amount=gross,
                fill_status=fill_status_str,
                filled_at=utc_now(),
            )
            created_count = 1

        # Drive RealOrder status toward the broker's view, but only if our
        # current status allows the transition. We never demote out of a
        # terminal status, never write to DRY_RUN.
        if order.status in _ORDER_NON_TERMINAL:
            if classification == "FULL":
                order_repo.update_status(order, new_status="FILLED")
            elif classification == "PARTIAL":
                # Only step up SUBMITTED → PARTIALLY_FILLED; PARTIALLY_FILLED
                # stays as-is (no self-transition).
                if order.status != "PARTIALLY_FILLED":
                    order_repo.update_status(
                        order, new_status="PARTIALLY_FILLED"
                    )
            # NONE → no status change.

        # One audit row for the successful sync (idempotent re-call still
        # logs because the operator may have called explicitly).
        audit_repo.append(
            candidate_id=order.candidate_id,
            event_type="REAL_ORDER_FILL_SYNCED",
            reason=f"KIS reported {classification} (delta={delta})",
            details={
                "classification": classification,
                "dry_run": False,
                "symbol": order.symbol,
                "side": order.side,
                "delta": int(delta),
                "kis_total": int(kis_total),
            },
        )
        session.flush()

        return FillSyncResult(
            real_order_id=order.id,
            fill_status=classification,
            created_fill_count=created_count,
            skipped_reason=None,
            delta=int(delta),
            fills_total=int(existing_total + delta),
            real_order_status=order.status,
        )


__all__ = ["FillSyncResult", "FillSyncService"]
