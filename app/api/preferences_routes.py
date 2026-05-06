"""v0.9 Phase C UserPreference API.

Endpoints:

  * ``GET /api/users/me/preferences``  -- fetch (or lazily create) the
    preference row for the authenticated user.
  * ``PUT /api/users/me/preferences``  -- replace all preference fields.

Authentication
--------------

Both routes use ``require_auth``.  When ``AUTH_ENABLED=false`` the dev
fallback (``user_id=1``) is used so local iteration works without JWT.

Forbidden fields
----------------

Responses NEVER include ``password``, ``password_hash``, ``access_token``,
``jwt_secret``, ``secret``, ``broker``, ``account``, ``quantity``,
``order_price``, ``order_type``, or ``side``.

``notification_preferences_json`` is persisted as-is and intentionally
never routed to a live Telegram / Email sender in this module.

Ownership
---------

``user_id`` is taken from the authenticated token / dev fallback and is
NEVER accepted from the request body.  A caller cannot set another user's
preferences.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.auth.dependencies import require_auth
from app.auth.security import AuthenticatedUser
from app.data.repositories.user_preferences import UserPreferenceRepository
from app.data.repositories.watchlists import WatchlistRepository
from app.db.session import get_session


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_MARKET_MAX_LEN = 32
_STRATEGY_MAX_LEN = 64


class UserPreferenceSchema(BaseModel):
    user_id: int
    default_watchlist_id: Optional[int] = None
    default_market: Optional[str] = None
    default_strategy: Optional[str] = None
    dashboard_layout_json: Optional[Any] = None
    notification_preferences_json: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PutUserPreferenceRequest(BaseModel):
    default_watchlist_id: Optional[int] = None
    default_market: Optional[str] = None
    default_strategy: Optional[str] = None
    dashboard_layout_json: Optional[Any] = None
    notification_preferences_json: Optional[Any] = None

    @validator("default_market")
    def _market_len(cls, v: str | None) -> str | None:  # noqa: N805
        if v is not None and len(v) > _MARKET_MAX_LEN:
            raise ValueError(f"default_market must be at most {_MARKET_MAX_LEN} chars")
        return v

    @validator("default_strategy")
    def _strategy_len(cls, v: str | None) -> str | None:  # noqa: N805
        if v is not None and len(v) > _STRATEGY_MAX_LEN:
            raise ValueError(f"default_strategy must be at most {_STRATEGY_MAX_LEN} chars")
        return v

    @validator("notification_preferences_json")
    def _no_secrets_in_notification(cls, v: Any) -> Any:  # noqa: N805
        """Reject obvious secret keys in the notification blob."""
        _FORBIDDEN = {"password", "token", "secret", "jwt_secret", "access_token"}
        if isinstance(v, dict):
            bad = _FORBIDDEN & set(k.lower() for k in v)
            if bad:
                raise ValueError(f"notification_preferences_json must not contain: {bad}")
        return v


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/users/me", tags=["preferences"])


def _to_schema(pref) -> UserPreferenceSchema:
    return UserPreferenceSchema(
        user_id=pref.user_id,
        default_watchlist_id=pref.default_watchlist_id,
        default_market=pref.default_market,
        default_strategy=pref.default_strategy,
        dashboard_layout_json=pref.dashboard_layout_json,
        notification_preferences_json=pref.notification_preferences_json,
        created_at=pref.created_at,
        updated_at=pref.updated_at,
    )


@router.get("/preferences", response_model=UserPreferenceSchema)
def get_preferences(
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> UserPreferenceSchema:
    """Fetch (or lazily create) the authenticated user's preferences."""
    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(current.user_id)
    session.commit()
    return _to_schema(pref)


@router.put("/preferences", response_model=UserPreferenceSchema)
def put_preferences(
    payload: PutUserPreferenceRequest,
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> UserPreferenceSchema:
    """Replace all preference fields for the authenticated user.

    ``default_watchlist_id`` is validated to be owned by the current user.
    Pass ``null`` to clear a field.
    """
    # Validate watchlist ownership if provided.
    if payload.default_watchlist_id is not None:
        wl = WatchlistRepository(session).get_by_user_and_id(
            user_id=current.user_id,
            watchlist_id=payload.default_watchlist_id,
        )
        if wl is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="watchlist not found",
            )

    repo = UserPreferenceRepository(session)
    pref = repo.get_or_create_for_user(current.user_id)
    repo.update(
        pref,
        default_watchlist_id=payload.default_watchlist_id,
        default_market=payload.default_market,
        default_strategy=payload.default_strategy,
        dashboard_layout_json=payload.dashboard_layout_json,
        notification_preferences_json=payload.notification_preferences_json,
    )
    session.commit()
    return _to_schema(pref)
