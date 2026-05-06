"""v0.8 Phase C Watchlist API.

Endpoints (all under ``/api/watchlists``):

  * ``GET    /api/watchlists``                        -- list user's watchlists
  * ``GET    /api/watchlists/{watchlist_id}``         -- detail + items
  * ``POST   /api/watchlists``                        -- create a new watchlist
  * ``POST   /api/watchlists/{watchlist_id}/items``   -- add a symbol
  * ``DELETE /api/watchlists/{watchlist_id}/items/{symbol}`` -- remove a symbol

Authentication
--------------

All five routes go through ``require_auth``. When ``AUTH_ENABLED=false``
(dev / CI default), ``require_auth`` resolves to the dev fallback identity
(``user_id=1``) so existing local workflows keep working without configuring
JWT. When ``AUTH_ENABLED=true``, a valid Bearer token is required and
``user_id`` is taken from the token claim -- the request body NEVER carries
``user_id``, so a malicious client cannot impersonate another user.

Cross-user isolation
--------------------

Every read / write helper in :class:`WatchlistRepository` and
:class:`WatchlistItemRepository` is scoped by ``user_id`` or by a
``watchlist_id`` that the route layer first validates with
``get_by_user_and_id``. If the watchlist belongs to a different user we
return **404** (not 403) so the response does not leak ownership.

Forbidden fields
----------------

The Pydantic schemas only expose ``id`` / ``name`` / ``is_default`` /
``created_at`` / ``updated_at`` (watchlist) and ``id`` / ``symbol`` /
``memo`` / ``created_at`` / ``updated_at`` (item). Tests assert that
``broker``, ``account``, ``quantity``, ``order_*``, ``source_file_path``,
``password_hash``, ``token``, ``secret``, ``jwt_secret`` never appear in any
response body.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_auth
from app.auth.security import AuthenticatedUser
from app.data.repositories.stocks import StockRepository
from app.data.repositories.watchlist_items import (
    MAX_MEMO_LENGTH,
    WatchlistItemRepository,
    normalize_symbol,
)
from app.data.repositories.watchlists import WatchlistRepository
from app.db.session import get_session


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WatchlistItemSchema(BaseModel):
    id: int
    symbol: str
    memo: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class WatchlistSchema(BaseModel):
    id: int
    name: str
    is_default: bool
    item_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class WatchlistDetailSchema(WatchlistSchema):
    items: List[WatchlistItemSchema] = []


class WatchlistsResponse(BaseModel):
    watchlists: List[WatchlistSchema]


class CreateWatchlistRequest(BaseModel):
    name: str
    is_default: bool = False

    @validator("name")
    def _name_not_empty(cls, value: str) -> str:  # noqa: N805
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        if len(cleaned) > 64:
            raise ValueError("name must be at most 64 chars")
        return cleaned


class CreateWatchlistItemRequest(BaseModel):
    symbol: str
    memo: Optional[str] = None

    @validator("symbol")
    def _symbol_not_empty(cls, value: str) -> str:  # noqa: N805
        try:
            return normalize_symbol(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @validator("memo")
    def _memo_length(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is None:
            return None
        if len(value) > MAX_MEMO_LENGTH:
            raise ValueError(
                f"memo must be at most {MAX_MEMO_LENGTH} chars"
            )
        return value


class StatusResponse(BaseModel):
    status: str = "ok"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


def _to_summary(watchlist, item_count: int) -> WatchlistSchema:
    return WatchlistSchema(
        id=watchlist.id,
        name=watchlist.name,
        is_default=watchlist.is_default,
        item_count=item_count,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


def _load_owned_watchlist(
    session: Session,
    *,
    user_id: int,
    watchlist_id: int,
):
    watchlist = WatchlistRepository(session).get_by_user_and_id(
        user_id=user_id,
        watchlist_id=watchlist_id,
    )
    if watchlist is None:
        # 404 covers both "doesn't exist" and "belongs to another user" so the
        # response does not leak ownership of unrelated rows.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="watchlist not found",
        )
    return watchlist


# -------- list --------


@router.get("", response_model=WatchlistsResponse)
def list_watchlists(
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistsResponse:
    repo = WatchlistRepository(session)
    rows = repo.list_by_user(current.user_id)
    return WatchlistsResponse(
        watchlists=[
            _to_summary(w, item_count=len(w.items) if w.items is not None else 0)
            for w in rows
        ],
    )


# -------- detail --------


@router.get("/{watchlist_id}", response_model=WatchlistDetailSchema)
def get_watchlist(
    watchlist_id: int = Path(..., ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistDetailSchema:
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    return WatchlistDetailSchema(
        id=watchlist.id,
        name=watchlist.name,
        is_default=watchlist.is_default,
        item_count=len(watchlist.items),
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items=[
            WatchlistItemSchema(
                id=item.id,
                symbol=item.symbol,
                memo=item.memo,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in watchlist.items
        ],
    )


# -------- create --------


@router.post(
    "",
    response_model=WatchlistSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_watchlist(
    payload: CreateWatchlistRequest,
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistSchema:
    repo = WatchlistRepository(session)
    try:
        created = repo.create(
            user_id=current.user_id,
            name=payload.name,
            is_default=payload.is_default,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="watchlist name already exists for this user",
        )
    # Re-fetch via ownership-scoped path so the relationship is loaded for
    # the item_count calculation -- consistent with GET responses.
    refreshed = repo.get_by_user_and_id(
        user_id=current.user_id, watchlist_id=created.id
    )
    assert refreshed is not None  # we just created it
    return _to_summary(refreshed, item_count=len(refreshed.items))


# -------- add item --------


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistItemSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_watchlist_item(
    payload: CreateWatchlistItemRequest,
    watchlist_id: int = Path(..., ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistItemSchema:
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )

    # Symbol must exist in the canonical stocks table -- otherwise we'd accept
    # arbitrary client input as a "favourite". Symbol is already canonicalised
    # by the request validator.
    stock = StockRepository(session).get_by_symbol(payload.symbol)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="symbol not found in stocks",
        )

    items_repo = WatchlistItemRepository(session)
    try:
        item = items_repo.add_item(
            watchlist_id=watchlist.id,
            symbol=payload.symbol,
            memo=payload.memo,
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="symbol already in this watchlist",
        )

    return WatchlistItemSchema(
        id=item.id,
        symbol=item.symbol,
        memo=item.memo,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# -------- remove item --------


@router.delete(
    "/{watchlist_id}/items/{symbol}",
    response_model=StatusResponse,
)
def remove_watchlist_item(
    watchlist_id: int = Path(..., ge=1),
    symbol: str = Path(..., min_length=1, max_length=32),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> StatusResponse:
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    items_repo = WatchlistItemRepository(session)
    try:
        removed = items_repo.remove_item(
            watchlist_id=watchlist.id, symbol=symbol
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="symbol not in this watchlist",
        )
    session.commit()
    return StatusResponse()
