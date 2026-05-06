"""Repository for v0.8 Phase C Watchlist rows.

Ownership policy
----------------

Every read / write helper accepts a ``user_id`` argument and joins on it so
that a caller cannot accidentally fetch or mutate another user's data. The
only helper that returns a row "by id" is :meth:`get_by_user_and_id` -- there
is no ``get_by_id`` that ignores ownership, because the API layer always
knows the authenticated user.

Default-watchlist invariant
---------------------------

At most one watchlist per user has ``is_default=True``. ``set_default`` clears
the previous default in a single transaction; ``create`` accepts ``is_default``
and likewise demotes the previous default if so. Both rely on the API layer
calling ``session.commit()`` or ``session.flush()`` -- consistent with the
rest of the project, repositories never commit on their own.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import Watchlist


DEFAULT_WATCHLIST_NAME = "기본"


class WatchlistRepository(BaseRepository[Watchlist]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Watchlist)

    # -------- create / mutate --------

    def create(
        self,
        *,
        user_id: int,
        name: str,
        is_default: bool = False,
    ) -> Watchlist:
        """Insert a new watchlist for ``user_id``.

        If ``is_default`` is True, demotes any existing default for the same
        user (single-default invariant). Caller is expected to handle the
        ``IntegrityError`` raised by the Unique(user_id, name) constraint.
        """
        if is_default:
            self._clear_default_for_user(user_id)
        return self.add(
            Watchlist(user_id=user_id, name=name, is_default=is_default),
        )

    def get_or_create_default(self, user_id: int) -> Watchlist:
        """Return the user's default watchlist, creating one if needed."""
        existing = self.get_default_for_user(user_id)
        if existing is not None:
            return existing
        return self.create(
            user_id=user_id,
            name=DEFAULT_WATCHLIST_NAME,
            is_default=True,
        )

    def rename(self, watchlist: Watchlist, *, new_name: str) -> Watchlist:
        watchlist.name = new_name
        watchlist.updated_at = utc_now()
        self.session.flush()
        return watchlist

    def set_default(self, watchlist: Watchlist) -> Watchlist:
        """Make ``watchlist`` the default for its owner. Demotes the previous one."""
        if watchlist.is_default:
            return watchlist
        self._clear_default_for_user(watchlist.user_id)
        watchlist.is_default = True
        watchlist.updated_at = utc_now()
        self.session.flush()
        return watchlist

    def delete(self, watchlist: Watchlist) -> None:
        """Delete a watchlist (cascade-deletes its items)."""
        self.session.delete(watchlist)
        self.session.flush()

    # -------- read (ownership-scoped) --------

    def get_by_user_and_id(
        self,
        *,
        user_id: int,
        watchlist_id: int,
    ) -> Watchlist | None:
        """Fetch a watchlist by id, but only if the user owns it.

        Returns ``None`` for non-existent ids AND for ids owned by a different
        user, so the API layer can collapse both cases into a single 404 and
        avoid leaking ownership.
        """
        statement = (
            select(Watchlist)
            .where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
            .options(selectinload(Watchlist.items))
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_default_for_user(self, user_id: int) -> Watchlist | None:
        statement = (
            select(Watchlist)
            .where(
                Watchlist.user_id == user_id,
                Watchlist.is_default.is_(True),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_user(self, user_id: int) -> list[Watchlist]:
        statement = (
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.is_default.desc(), Watchlist.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    # -------- internal --------

    def _clear_default_for_user(self, user_id: int) -> None:
        """Set all watchlists for ``user_id`` to is_default=False."""
        statement = (
            update(Watchlist)
            .where(Watchlist.user_id == user_id, Watchlist.is_default.is_(True))
            .values(is_default=False, updated_at=utc_now())
        )
        self.session.execute(statement)
