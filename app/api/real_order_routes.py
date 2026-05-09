"""v0.16 Phase E — Real Order read-only API.
v1.0 Phase D — adds POST /sync (the SOLE mutation route on this prefix).

Endpoints:
  * ``GET  /api/real-orders``                 list real orders (filter + paginate)
  * ``GET  /api/real-orders/{id}``            order detail with fills
  * ``POST /api/real-orders/{id}/sync``       manual fill-status sync (v1.0 Phase D)

Hard policies (regression-tested):
  * Router NEVER imports httpx / requests / urllib.
  * Router NEVER imports HttpxKisOrderTransport / KisOrderClientInterface
    directly — FillSyncService is constructed with the default Fake
    transport. Production wiring (real transport injection) is the
    operator's responsibility outside this module.
  * Response schema excludes forbidden fields:
      broker_order_no_hash / api_key / app_secret / access_token /
      token / secret / raw_response / account_number / real_account.
  * error_message is passed through as-is (already sanitised at write time
    by RealOrderRepository.mark_failed(); max 500 chars, no secrets).
  * POST /sync gates: AUTH + TRADING_SAFETY_ENABLED + KILL_SWITCH_OFF.
    REAL_TRADING_ENABLED / KIS_ORDER_ENABLED are NOT required — operators
    must be able to query fill status post-incident even after disabling
    new order placement. PUT / PATCH / DELETE return 405.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    RealFillSchema,
    RealOrderDetailResponse,
    RealOrderSchema,
    RealOrderSyncRequest,
    RealOrderSyncResponse,
    RealOrdersResponse,
)
from app.auth.dependencies import require_auth
from app.auth.security import AuthenticatedUser
from app.broker.fill_sync_service import FillSyncService
from app.config.settings import Settings, get_settings
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import VALID_STATUSES, RealOrderRepository
from app.db.base import utc_now
from app.db.models import RealFill, RealOrder
from app.db.session import get_session


router = APIRouter(prefix="/api/real-orders", tags=["real-orders"])


# ---------------------------------------------------------------------------
# Mutation gating (mirrors approval_routes pattern)
# ---------------------------------------------------------------------------


def _require_trading_safety_enabled(settings: Settings) -> None:
    if not settings.trading_safety_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "real-order sync is disabled — set TRADING_SAFETY_ENABLED=true "
                "in operator-private .env to opt in"
            ),
        )


def _require_kill_switch_off(settings: Settings) -> None:
    if settings.kill_switch_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "kill switch is ON — set KILL_SWITCH_ENABLED=false in "
                "operator-private .env to opt out of the paranoid default"
            ),
        )


# ---------------------------------------------------------------------------
# Conversion helpers (safe fields only)
# ---------------------------------------------------------------------------


def _order_to_schema(order: RealOrder) -> RealOrderSchema:
    return RealOrderSchema(
        id=order.id,
        candidate_id=order.candidate_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        order_type=order.order_type,
        limit_price=str(order.limit_price) if order.limit_price is not None else None,
        estimated_amount=(
            str(order.estimated_amount) if order.estimated_amount is not None else None
        ),
        status=order.status,
        dry_run=order.dry_run,
        fake_order_no=order.fake_order_no,
        request_id=order.request_id,
        error_code=order.error_code,
        error_message=order.error_message,
        submitted_at=order.submitted_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _fill_to_schema(fill: RealFill) -> RealFillSchema:
    return RealFillSchema(
        id=fill.id,
        real_order_id=fill.real_order_id,
        symbol=fill.symbol,
        side=fill.side,
        quantity=fill.quantity,
        fill_price=str(fill.fill_price) if fill.fill_price is not None else None,
        fee=str(fill.fee) if fill.fee is not None else None,
        tax=str(fill.tax) if fill.tax is not None else None,
        gross_amount=str(fill.gross_amount) if fill.gross_amount is not None else None,
        net_amount=str(fill.net_amount) if fill.net_amount is not None else None,
        fill_status=fill.fill_status,
        filled_at=fill.filled_at,
        created_at=fill.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=RealOrdersResponse, tags=["real-orders"])
def list_real_orders(
    status: Optional[str] = Query(None, description="Filter by order status"),
    candidate_id: Optional[int] = Query(None, description="Filter by candidate_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> RealOrdersResponse:
    """List RealOrder rows (read-only). No sensitive fields exposed.

    ``status`` must be one of the valid statuses (VALID_STATUSES) when provided.
    Returns an empty list (not 404) when no orders match.
    """
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status {status!r}. Must be one of {sorted(VALID_STATUSES)}",
        )

    repo = RealOrderRepository(session)
    if status is not None:
        rows = repo.list_by_status(status, limit=limit + offset)
    elif candidate_id is not None:
        rows = repo.get_by_candidate_id(candidate_id)
    else:
        rows = repo.list_recent(limit=limit + offset)

    # Apply candidate_id filter if also provided with status filter
    if candidate_id is not None and status is not None:
        rows = [r for r in rows if r.candidate_id == candidate_id]

    total = len(rows)
    page = rows[offset: offset + limit]

    return RealOrdersResponse(
        items=[_order_to_schema(r) for r in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=RealOrderDetailResponse, tags=["real-orders"])
def get_real_order(
    order_id: int,
    session: Session = Depends(get_session),
) -> RealOrderDetailResponse:
    """Return one RealOrder with its RealFill rows. No sensitive fields exposed."""
    order = RealOrderRepository(session).get_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"real order {order_id} not found")

    fills = RealFillRepository(session).list_by_order(order_id)
    return RealOrderDetailResponse(
        order=_order_to_schema(order),
        fills=[_fill_to_schema(f) for f in fills],
    )


# ---------------------------------------------------------------------------
# v1.0 Phase D — POST /api/real-orders/{order_id}/sync
# ---------------------------------------------------------------------------


@router.post(
    "/{order_id}/sync",
    response_model=RealOrderSyncResponse,
    tags=["real-orders"],
)
def sync_real_order_fill(
    order_id: int = Path(..., ge=1),
    payload: RealOrderSyncRequest = Body(default=RealOrderSyncRequest()),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> RealOrderSyncResponse:
    """Manually trigger fill-status sync for a single RealOrder.

    Auth + safety gates:
      * AUTH (401 if not authenticated)
      * TRADING_SAFETY_ENABLED=true (503 otherwise)
      * KILL_SWITCH_ENABLED=false (503 otherwise)

    REAL_TRADING_ENABLED / KIS_ORDER_ENABLED are intentionally NOT required —
    the operator may need to query fill status for already-submitted orders
    after disabling new placement.

    The optional ``kis_order_no`` field in the request body is the plaintext
    KIS order number. It flows through the FillSyncService transport
    in-memory only and is NEVER persisted or logged.
    """
    _require_trading_safety_enabled(settings)
    _require_kill_switch_off(settings)

    order = RealOrderRepository(session).get_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"real order {order_id} not found",
        )

    service = FillSyncService()
    result = service.sync_fills(
        session,
        real_order_id=order_id,
        kis_order_no_plaintext=payload.kis_order_no,
    )
    session.commit()

    # Refresh the order to pick up any status transition.
    refreshed = RealOrderRepository(session).get_by_id(order_id)
    refreshed_status = refreshed.status if refreshed is not None else order.status

    if result.fill_status == "FAILED":
        message = (
            f"sync failed: {result.skipped_reason or 'transport error'}"
        )
    elif result.skipped_reason:
        message = f"sync skipped: {result.skipped_reason}"
    elif result.created_fill_count > 0:
        message = (
            f"sync ok: {result.fill_status} (delta={result.delta}, "
            f"new fill recorded)"
        )
    else:
        message = (
            f"sync ok: {result.fill_status} (idempotent — no new fill, "
            f"delta={result.delta})"
        )

    return RealOrderSyncResponse(
        real_order_id=result.real_order_id,
        real_order_status=refreshed_status,
        fill_status=result.fill_status,
        fills_added=result.created_fill_count,
        fills_total=result.fills_total,
        synced_at=utc_now(),
        message=message,
    )
