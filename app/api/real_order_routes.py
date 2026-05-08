"""v0.16 Phase E — Real Order read-only API.

Endpoints (all GET — no mutation):
  * ``GET /api/real-orders``          list real orders (filter + paginate)
  * ``GET /api/real-orders/{id}``     order detail with fills

Hard policies (regression-tested):
  * Router NEVER imports httpx / requests / urllib.
  * Router NEVER imports KisHttpOrderTransport / KisOrderClientInterface.
  * Response schema excludes forbidden fields:
      broker_order_no_hash / api_key / app_secret / access_token /
      token / secret / raw_response / account_number / real_account.
  * error_message is passed through as-is (already sanitised at write time
    by RealOrderRepository.mark_failed(); max 500 chars, no secrets).
  * No POST / PUT / DELETE endpoints — dry-run execution happens via CLI or
    future API in Phase E+; the UI is read-only in v0.16.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    RealFillSchema,
    RealOrderDetailResponse,
    RealOrderSchema,
    RealOrdersResponse,
)
from app.data.repositories.real_fill import RealFillRepository
from app.data.repositories.real_order import VALID_STATUSES, RealOrderRepository
from app.db.models import RealFill, RealOrder
from app.db.session import get_session


router = APIRouter(prefix="/api/real-orders", tags=["real-orders"])


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
