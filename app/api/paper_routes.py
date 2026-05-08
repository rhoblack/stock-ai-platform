"""v0.14 Phase D -- Paper / Simulation Trading API.

Endpoints (all under ``/api/paper``):

  * ``GET    /api/paper/account``       -- VirtualAccount + latest PnL totals
  * ``GET    /api/paper/orders``        -- order history (status / symbol / limit filters)
  * ``GET    /api/paper/positions``     -- current positions + unrealized PnL
  * ``GET    /api/paper/pnl``           -- daily PnL snapshot timeseries
  * ``POST   /api/paper/orders``        -- create a paper order (PAPER_TRADING_ENABLED + AUTH)
  * ``DELETE /api/paper/orders/{id}``   -- cancel a paper order (PAPER_TRADING_ENABLED + AUTH)

Hard guarantees (regression-tested in tests/integration/test_paper_api.py):

* The router NEVER imports KIS / DART / RSS / requests / httpx (AST + grep).
* Mutation endpoints return ``503 Service Unavailable`` when
  ``Settings.paper_trading_enabled`` is False -- they do not silently 404.
* Forbidden response fields (``api_key``, ``token``, ``secret``,
  ``source_file_path``, ``broker_order_id``, ``kis_order_id``,
  ``real_account``, ``broker``, ``account_number``, ``raw_text``, ``body``,
  ``full_text``) NEVER appear in any response body.
* SimulationBroker.submit_order / cancel_order are the ONLY mutation
  paths -- the route layer never writes VirtualOrder directly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreatePaperOrderRequest,
    PaperAccountSchema,
    PaperOrderResponse,
    PaperOrderSchema,
    PaperOrdersResponse,
    PaperPnLResponse,
    PaperPnLSnapshotSchema,
    PaperPositionSchema,
    PaperPositionsResponse,
    PaperStatusResponse,
)
from app.auth.dependencies import require_auth
from app.auth.security import AuthenticatedUser
from app.broker.simulation_broker import (
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
)
from app.config.settings import Settings, get_settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import VirtualPositionRepository
from app.db.models import VirtualAccount, VirtualOrder, VirtualPosition
from app.db.session import get_session


router = APIRouter(prefix="/api/paper", tags=["paper-trading"])


# ---------------------------------------------------------------------------
# Mutation gating
# ---------------------------------------------------------------------------


def _require_paper_trading_enabled(settings: Settings) -> None:
    if not settings.paper_trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "paper trading is disabled — set PAPER_TRADING_ENABLED=true "
                "in operator-private .env to opt in"
            ),
        )


# ---------------------------------------------------------------------------
# Account resolution
# ---------------------------------------------------------------------------


def _resolve_account(
    session: Session,
    *,
    requested_account_id: int | None,
    user_id: int | None,
) -> VirtualAccount:
    accounts = VirtualAccountRepository(session)
    if requested_account_id is not None:
        acc = accounts.get_by_id(requested_account_id)
        if acc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="paper trading account not found",
            )
        return acc

    # No explicit id: pick the first account for this user (or NULL-user).
    candidates = accounts.list_by_user(user_id) or accounts.list_by_user(None)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no paper trading account exists for this user",
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _to_order_schema(order: VirtualOrder) -> PaperOrderSchema:
    return PaperOrderSchema(
        id=order.id,
        account_id=order.account_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        order_type=order.order_type,
        limit_price=str(order.limit_price) if order.limit_price is not None else None,
        status=order.status,
        idempotency_key=order.idempotency_key,
        reason=order.reason,
        note=order.note,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _to_position_schema(
    pos: VirtualPosition,
    *,
    last_close: Optional[Decimal],
) -> PaperPositionSchema:
    market_value: Optional[Decimal] = None
    unrealized: Optional[Decimal] = None
    if last_close is not None and pos.quantity > 0:
        market_value = Decimal(last_close) * Decimal(pos.quantity)
        unrealized = market_value - Decimal(pos.avg_cost) * Decimal(pos.quantity)
    return PaperPositionSchema(
        id=pos.id,
        account_id=pos.account_id,
        symbol=pos.symbol,
        quantity=pos.quantity,
        avg_cost=str(pos.avg_cost) if pos.avg_cost is not None else None,
        realized_pnl=str(pos.realized_pnl) if pos.realized_pnl is not None else None,
        last_close=str(last_close) if last_close is not None else None,
        market_value=str(market_value) if market_value is not None else None,
        unrealized_pnl=str(unrealized) if unrealized is not None else None,
        updated_at=pos.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /api/paper/account
# ---------------------------------------------------------------------------


@router.get("/account", response_model=PaperAccountSchema)
def get_paper_account(
    account_id: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperAccountSchema:
    account = _resolve_account(
        session, requested_account_id=account_id, user_id=current.user_id
    )

    snapshots = VirtualPnLSnapshotRepository(session).list_by_account(
        account.id, limit=1
    )
    latest = snapshots[-1] if snapshots else None

    return PaperAccountSchema(
        id=account.id,
        name=account.name,
        currency=account.currency,
        paper_trading_enabled=account.paper_trading_enabled,
        initial_cash=str(account.initial_cash),
        cash_balance=str(account.cash_balance),
        market_value=str(latest.market_value) if latest else None,
        total_value=str(latest.total_value) if latest else None,
        realized_pnl=str(latest.realized_pnl) if latest else None,
        unrealized_pnl=str(latest.unrealized_pnl) if latest else None,
        snapshot_date=latest.snapshot_date if latest else None,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /api/paper/orders
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=PaperOrdersResponse)
def list_paper_orders(
    account_id: int | None = Query(None, ge=1),
    status_filter: str | None = Query(None, alias="status"),
    symbol: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperOrdersResponse:
    account = _resolve_account(
        session, requested_account_id=account_id, user_id=current.user_id
    )
    orders_repo = VirtualOrderRepository(session)
    rows = orders_repo.list_by_account(
        account.id, status=status_filter, limit=limit
    )
    if symbol is not None:
        target = symbol.strip().upper()
        rows = [o for o in rows if o.symbol == target]
    return PaperOrdersResponse(
        orders=[_to_order_schema(o) for o in rows],
        total=len(rows),
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /api/paper/positions
# ---------------------------------------------------------------------------


_POSITION_PRICE_LOOKBACK_DAYS = 14


@router.get("/positions", response_model=PaperPositionsResponse)
def list_paper_positions(
    account_id: int | None = Query(None, ge=1),
    include_closed: bool = Query(False),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperPositionsResponse:
    account = _resolve_account(
        session, requested_account_id=account_id, user_id=current.user_id
    )
    positions_repo = VirtualPositionRepository(session)
    if include_closed:
        rows = positions_repo.list_by_account(account.id)
    else:
        rows = positions_repo.list_open_by_account(account.id)

    today = date.today()
    prices_repo = DailyPriceRepository(session)
    schemas = []
    for pos in rows:
        bar = prices_repo.get_latest_on_or_before(
            symbol=pos.symbol,
            target_date=today,
            lookback_days=_POSITION_PRICE_LOOKBACK_DAYS,
        )
        last_close = (
            Decimal(bar.close) if (bar is not None and bar.close is not None) else None
        )
        schemas.append(_to_position_schema(pos, last_close=last_close))

    return PaperPositionsResponse(positions=schemas, total=len(schemas))


# ---------------------------------------------------------------------------
# GET /api/paper/pnl
# ---------------------------------------------------------------------------


@router.get("/pnl", response_model=PaperPnLResponse)
def list_paper_pnl(
    account_id: int | None = Query(None, ge=1),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    limit: int = Query(365, ge=1, le=3650),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperPnLResponse:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date must be <= to_date",
        )
    account = _resolve_account(
        session, requested_account_id=account_id, user_id=current.user_id
    )
    snapshots_repo = VirtualPnLSnapshotRepository(session)
    rows = snapshots_repo.list_by_account(
        account.id, from_date=from_date, to_date=to_date, limit=limit
    )
    return PaperPnLResponse(
        snapshots=[
            PaperPnLSnapshotSchema(
                snapshot_date=s.snapshot_date,
                cash_balance=str(s.cash_balance),
                market_value=str(s.market_value),
                total_value=str(s.total_value),
                realized_pnl=str(s.realized_pnl),
                unrealized_pnl=str(s.unrealized_pnl),
            )
            for s in rows
        ],
        total=len(rows),
    )


# ---------------------------------------------------------------------------
# POST /api/paper/orders
# ---------------------------------------------------------------------------


@router.post(
    "/orders",
    response_model=PaperOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper_order(
    payload: CreatePaperOrderRequest = Body(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperOrderResponse:
    _require_paper_trading_enabled(settings)
    account = _resolve_account(
        session,
        requested_account_id=payload.account_id,
        user_id=current.user_id,
    )

    broker = SimulationBroker(settings=settings)
    try:
        result = broker.submit_order(
            session,
            account_id=account.id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            order_type=payload.order_type,
            limit_price=(
                Decimal(payload.limit_price)
                if payload.limit_price is not None
                else None
            ),
            idempotency_key=payload.idempotency_key,
            note=payload.note,
        )
    except PaperTradingDisabledError as exc:
        # Account-level switch off (global is gated above).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except SimulationBrokerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    session.commit()
    return PaperOrderResponse(
        order=_to_order_schema(result.order),
        deduplicated=result.deduplicated,
    )


# ---------------------------------------------------------------------------
# DELETE /api/paper/orders/{id}
# ---------------------------------------------------------------------------


@router.delete("/orders/{order_id}", response_model=PaperStatusResponse)
def cancel_paper_order(
    order_id: int = Path(..., ge=1),
    reason: str | None = Query(None, max_length=256),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> PaperStatusResponse:
    _require_paper_trading_enabled(settings)
    broker = SimulationBroker(settings=settings)
    try:
        broker.cancel_order(session, order_id=order_id, reason=reason)
    except SimulationBrokerError as exc:
        message = str(exc)
        # "not found" surfaces as 404, terminal-state refusals as 422.
        if "not found" in message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=message
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message
        )
    session.commit()
    return PaperStatusResponse(order_id=order_id)
