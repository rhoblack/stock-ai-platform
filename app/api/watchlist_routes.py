"""v0.8 Phase C / v0.9 Phase C Watchlist API.

Endpoints (all under ``/api/watchlists``):

  * ``GET    /api/watchlists``                               -- list user's watchlists
  * ``GET    /api/watchlists/{watchlist_id}``                -- detail + items
  * ``POST   /api/watchlists``                               -- create a new watchlist
  * ``PATCH  /api/watchlists/{watchlist_id}``                -- rename / set_default (v0.9 C)
  * ``DELETE /api/watchlists/{watchlist_id}``                -- delete watchlist (v0.9 C)
  * ``GET    /api/watchlists/{watchlist_id}/items``          -- list items w/ pagination (v0.9 C)
  * ``POST   /api/watchlists/{watchlist_id}/items``          -- add a symbol
  * ``PATCH  /api/watchlists/{watchlist_id}/items/{symbol}`` -- update memo (v0.9 C)
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

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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


# v0.9 Phase C schemas

class PatchWatchlistRequest(BaseModel):
    name: str | None = None
    is_default: bool | None = None

    @validator("name")
    def _name_valid(cls, value: str | None) -> str | None:  # noqa: N805
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        if len(cleaned) > 64:
            raise ValueError("name must be at most 64 chars")
        return cleaned


class PatchWatchlistItemRequest(BaseModel):
    memo: str | None = None

    @validator("memo")
    def _memo_length(cls, value: str | None) -> str | None:  # noqa: N805
        if value is None:
            return None
        if len(value) > MAX_MEMO_LENGTH:
            raise ValueError(f"memo must be at most {MAX_MEMO_LENGTH} chars")
        return value


class WatchlistItemsResponse(BaseModel):
    items: List[WatchlistItemSchema]
    total: int
    limit: int
    offset: int


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


# ---------------------------------------------------------------------------
# v0.9 Phase C additions
# ---------------------------------------------------------------------------


# -------- patch watchlist --------


@router.patch("/{watchlist_id}", response_model=WatchlistSchema)
def patch_watchlist(
    payload: PatchWatchlistRequest,
    watchlist_id: int = Path(..., ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistSchema:
    """Rename a watchlist and / or toggle its default flag."""
    if payload.name is None and payload.is_default is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="at least one of name or is_default must be provided",
        )
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    repo = WatchlistRepository(session)
    try:
        if payload.name is not None:
            repo.rename(watchlist, new_name=payload.name)
        if payload.is_default is True:
            repo.set_default(watchlist)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="watchlist name already exists for this user",
        )
    refreshed = repo.get_by_user_and_id(
        user_id=current.user_id, watchlist_id=watchlist_id
    )
    assert refreshed is not None
    return _to_summary(refreshed, item_count=len(refreshed.items))


# -------- delete watchlist --------


@router.delete("/{watchlist_id}", response_model=StatusResponse)
def delete_watchlist(
    watchlist_id: int = Path(..., ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> StatusResponse:
    """Delete a watchlist and all its items (cascade).

    Policy: deleting the default watchlist is allowed; the user's
    ``UserPreference.default_watchlist_id`` is cleared to NULL via the FK
    ON DELETE SET NULL rule. After deletion there is no automatic promotion
    of another watchlist to default -- the caller decides.
    """
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    WatchlistRepository(session).delete(watchlist)
    session.commit()
    return StatusResponse()


# -------- list items (paginated) --------


@router.get("/{watchlist_id}/items", response_model=WatchlistItemsResponse)
def list_watchlist_items(
    watchlist_id: int = Path(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    symbol_prefix: str | None = Query(None, max_length=32),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistItemsResponse:
    """List items in a watchlist with optional filtering and pagination."""
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    all_items = WatchlistItemRepository(session).list_items(watchlist.id)
    if symbol_prefix:
        prefix = symbol_prefix.strip().upper()
        all_items = [i for i in all_items if i.symbol.startswith(prefix)]
    total = len(all_items)
    page = all_items[offset: offset + limit]
    return WatchlistItemsResponse(
        items=[
            WatchlistItemSchema(
                id=item.id,
                symbol=item.symbol,
                memo=item.memo,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in page
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# -------- patch item memo --------


@router.patch(
    "/{watchlist_id}/items/{symbol}",
    response_model=WatchlistItemSchema,
)
def patch_watchlist_item(
    payload: PatchWatchlistItemRequest,
    watchlist_id: int = Path(..., ge=1),
    symbol: str = Path(..., min_length=1, max_length=32),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> WatchlistItemSchema:
    """Update the memo on a watchlist item."""
    watchlist = _load_owned_watchlist(
        session, user_id=current.user_id, watchlist_id=watchlist_id
    )
    items_repo = WatchlistItemRepository(session)
    try:
        canonical = normalize_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    item = items_repo.get_item(watchlist_id=watchlist.id, symbol=canonical)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="symbol not in this watchlist",
        )
    try:
        updated = items_repo.update_memo(item, memo=payload.memo)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    return WatchlistItemSchema(
        id=updated.id,
        symbol=updated.symbol,
        memo=updated.memo,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
