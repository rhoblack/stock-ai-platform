"""Repository for v0.8 Phase C WatchlistItem rows.

Symbol normalization
--------------------

All write helpers (``add_item`` / ``update_memo``) and lookup helpers
(``get_item`` / ``remove_item`` / ``exists``) normalize the symbol via
:func:`normalize_symbol` -- ``str.strip().upper()`` -- so that ``"  005930 "``
and ``"005930"`` collide on the Unique(watchlist_id, symbol) constraint.
This matches the project's existing convention of upper-case canonical
symbols.

Memo length
-----------

``MAX_MEMO_LENGTH`` is enforced here as a defensive measure even though the
API layer rejects 422 first. Repositories raise :class:`ValueError`, which
the API can either let bubble (FastAPI -> 500) or pre-validate. The current
API path validates before calling, so the raise is purely a safety net.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import WatchlistItem


MAX_MEMO_LENGTH = 500


def normalize_symbol(symbol: str) -> str:
    """Return the canonical (trimmed + upper-cased) form of ``symbol``."""
    if symbol is None:
        raise ValueError("symbol must not be None")
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("symbol must not be empty")
    return cleaned


def _validate_memo(memo: str | None) -> None:
    if memo is None:
        return
    if len(memo) > MAX_MEMO_LENGTH:
        raise ValueError(
            f"memo must be at most {MAX_MEMO_LENGTH} chars (got {len(memo)})"
        )


class WatchlistItemRepository(BaseRepository[WatchlistItem]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, WatchlistItem)

    # -------- create / mutate --------

    def add_item(
        self,
        *,
        watchlist_id: int,
        symbol: str,
        memo: str | None = None,
    ) -> WatchlistItem:
        """Insert a new item. Caller handles IntegrityError on duplicate."""
        canonical = normalize_symbol(symbol)
        _validate_memo(memo)
        return self.add(
            WatchlistItem(
                watchlist_id=watchlist_id,
                symbol=canonical,
                memo=memo,
            ),
        )

    def update_memo(
        self,
        item: WatchlistItem,
        *,
        memo: str | None,
    ) -> WatchlistItem:
        _validate_memo(memo)
        item.memo = memo
        item.updated_at = utc_now()
        self.session.flush()
        return item

    def remove_item(self, *, watchlist_id: int, symbol: str) -> bool:
        """Delete an item. Returns True iff a row was removed."""
        canonical = normalize_symbol(symbol)
        item = self.get_item(watchlist_id=watchlist_id, symbol=canonical)
        if item is None:
            return False
        self.session.delete(item)
        self.session.flush()
        return True

    # -------- read --------

    def get_item(
        self,
        *,
        watchlist_id: int,
        symbol: str,
    ) -> WatchlistItem | None:
        canonical = normalize_symbol(symbol)
        statement = select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.symbol == canonical,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_items(self, watchlist_id: int) -> list[WatchlistItem]:
        statement = (
            select(WatchlistItem)
            .where(WatchlistItem.watchlist_id == watchlist_id)
            .order_by(WatchlistItem.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_symbols(self, watchlist_id: int) -> list[str]:
        statement = (
            select(WatchlistItem.symbol)
            .where(WatchlistItem.watchlist_id == watchlist_id)
            .order_by(WatchlistItem.symbol.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def exists(self, *, watchlist_id: int, symbol: str) -> bool:
        return self.get_item(watchlist_id=watchlist_id, symbol=symbol) is not None
