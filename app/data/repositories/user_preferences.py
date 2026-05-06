"""Repository for v0.9 Phase C UserPreference rows.

One row per user (UNIQUE user_id). The canonical access pattern is
:meth:`get_or_create_for_user` -- the API layer never creates rows explicitly,
it always upserts via this helper so the user always has a valid preference row
after the first GET /api/users/me/preferences call.

Secrets policy
--------------

This repository MUST NOT accept or store password / token / secret /
jwt_secret / broker / account / quantity / order_price fields. The only JSON
blobs stored are ``dashboard_layout_json`` and ``notification_preferences_json``
which are opaque UI blobs. ``notification_preferences_json`` is never connected
to a live Telegram / Email sender -- it is stored only.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import UserPreference


_UNSET = object()


class UserPreferenceRepository(BaseRepository[UserPreference]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, UserPreference)

    # -------- read --------

    def get_by_user_id(self, user_id: int) -> UserPreference | None:
        statement = select(UserPreference).where(UserPreference.user_id == user_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_or_create_for_user(self, user_id: int) -> UserPreference:
        """Return the preference row for ``user_id``, creating a blank one if absent."""
        existing = self.get_by_user_id(user_id)
        if existing is not None:
            return existing
        return self.add(UserPreference(user_id=user_id))

    # -------- write --------

    def update(
        self,
        pref: UserPreference,
        *,
        default_watchlist_id: object = _UNSET,
        default_market: object = _UNSET,
        default_strategy: object = _UNSET,
        dashboard_layout_json: object = _UNSET,
        notification_preferences_json: object = _UNSET,
    ) -> UserPreference:
        """Partial-update the preference row. Only provided kwargs are changed."""
        if default_watchlist_id is not _UNSET:
            pref.default_watchlist_id = default_watchlist_id  # type: ignore[assignment]
        if default_market is not _UNSET:
            pref.default_market = default_market  # type: ignore[assignment]
        if default_strategy is not _UNSET:
            pref.default_strategy = default_strategy  # type: ignore[assignment]
        if dashboard_layout_json is not _UNSET:
            pref.dashboard_layout_json = dashboard_layout_json  # type: ignore[assignment]
        if notification_preferences_json is not _UNSET:
            pref.notification_preferences_json = notification_preferences_json  # type: ignore[assignment]
        pref.updated_at = utc_now()
        self.session.flush()
        return pref

    def set_default_watchlist(
        self, pref: UserPreference, *, watchlist_id: int | None
    ) -> UserPreference:
        pref.default_watchlist_id = watchlist_id
        pref.updated_at = utc_now()
        self.session.flush()
        return pref

    def update_dashboard_layout(
        self, pref: UserPreference, *, layout: dict | None
    ) -> UserPreference:
        pref.dashboard_layout_json = layout
        pref.updated_at = utc_now()
        self.session.flush()
        return pref

    def update_notification_preferences(
        self, pref: UserPreference, *, preferences: dict | None
    ) -> UserPreference:
        pref.notification_preferences_json = preferences
        pref.updated_at = utc_now()
        self.session.flush()
        return pref
