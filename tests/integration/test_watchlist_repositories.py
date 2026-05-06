"""Integration tests for v0.8 Phase C Watchlist + WatchlistItem repositories.

Covers:
  * Watchlist create / list_by_user / get_default_for_user / get_or_create_default
  * Unique(user_id, name) collision raises IntegrityError
  * set_default demotes the previous default; only one default per user
  * Cross-user isolation (get_by_user_and_id returns None for foreign rows)
  * WatchlistItem add_item / list_items / remove_item / exists / get_item
  * Unique(watchlist_id, symbol) collision
  * Symbol normalisation (whitespace + case)
  * memo length validation
  * Cascade delete from Watchlist removes items
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.auth.security import PasswordHasher
from app.data.repositories.users import UserRepository
from app.data.repositories.watchlist_items import (
    MAX_MEMO_LENGTH,
    WatchlistItemRepository,
    normalize_symbol,
)
from app.data.repositories.watchlists import (
    DEFAULT_WATCHLIST_NAME,
    WatchlistRepository,
)
from app.db.base import Base
from app.db.session import create_session_factory


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # SQLite ignores ON DELETE CASCADE unless foreign_keys pragma is on.
    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _seed_user(session, *, username: str = "alice") -> int:
    hasher = PasswordHasher(n=1024, r=8, p=1)
    user = UserRepository(session).create(
        username=username,
        password_hash=hasher.hash_password("hunter2!"),
        is_admin=True,
    )
    session.commit()
    return user.id


# ---------- normalize_symbol ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("005930", "005930"),
        ("  005930 ", "005930"),
        ("aapl", "AAPL"),
        ("\tNVDA\n", "NVDA"),
    ],
)
def test_normalize_symbol_trims_and_uppercases(raw, expected):
    assert normalize_symbol(raw) == expected


def test_normalize_symbol_rejects_empty():
    with pytest.raises(ValueError):
        normalize_symbol("   ")


def test_normalize_symbol_rejects_none():
    with pytest.raises(ValueError):
        normalize_symbol(None)  # type: ignore[arg-type]


# ---------- WatchlistRepository ----------


def test_create_watchlist_persists(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    wl = repo.create(user_id=user_id, name="단기")
    session.commit()
    assert wl.id is not None
    assert wl.user_id == user_id
    assert wl.is_default is False
    assert wl.created_at is not None


def test_list_by_user_orders_default_first_then_id(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    repo.create(user_id=user_id, name="A")
    repo.create(user_id=user_id, name="기본", is_default=True)
    repo.create(user_id=user_id, name="B")
    session.commit()
    rows = repo.list_by_user(user_id)
    assert [w.name for w in rows] == ["기본", "A", "B"]
    assert rows[0].is_default is True
    assert all(w.is_default is False for w in rows[1:])


def test_get_default_for_user_returns_default_or_none(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    assert repo.get_default_for_user(user_id) is None
    repo.create(user_id=user_id, name="기본", is_default=True)
    session.commit()
    default = repo.get_default_for_user(user_id)
    assert default is not None and default.name == "기본"


def test_get_or_create_default_idempotent(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    first = repo.get_or_create_default(user_id)
    session.commit()
    assert first.is_default is True
    assert first.name == DEFAULT_WATCHLIST_NAME
    second = repo.get_or_create_default(user_id)
    assert second.id == first.id


def test_unique_user_id_name_constraint(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    repo.create(user_id=user_id, name="dup")
    with pytest.raises(IntegrityError):
        repo.create(user_id=user_id, name="dup")


def test_set_default_demotes_previous_default(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    a = repo.create(user_id=user_id, name="A", is_default=True)
    b = repo.create(user_id=user_id, name="B")
    session.commit()
    repo.set_default(b)
    session.commit()
    refreshed_a = repo.get_by_user_and_id(user_id=user_id, watchlist_id=a.id)
    refreshed_b = repo.get_by_user_and_id(user_id=user_id, watchlist_id=b.id)
    assert refreshed_a is not None and refreshed_a.is_default is False
    assert refreshed_b is not None and refreshed_b.is_default is True


def test_create_with_is_default_demotes_previous(session):
    user_id = _seed_user(session)
    repo = WatchlistRepository(session)
    a = repo.create(user_id=user_id, name="A", is_default=True)
    session.commit()
    repo.create(user_id=user_id, name="B", is_default=True)
    session.commit()
    refreshed_a = repo.get_by_user_and_id(user_id=user_id, watchlist_id=a.id)
    assert refreshed_a is not None and refreshed_a.is_default is False
    defaults = [w for w in repo.list_by_user(user_id) if w.is_default]
    assert len(defaults) == 1
    assert defaults[0].name == "B"


def test_get_by_user_and_id_returns_none_for_foreign_user(session):
    alice = _seed_user(session, username="alice")
    bob = _seed_user(session, username="bob")
    repo = WatchlistRepository(session)
    bob_wl = repo.create(user_id=bob, name="bob-list")
    session.commit()
    # Alice cannot read Bob's list -- collapsed to None for the API to render 404.
    assert repo.get_by_user_and_id(user_id=alice, watchlist_id=bob_wl.id) is None
    # Bob still can.
    assert repo.get_by_user_and_id(user_id=bob, watchlist_id=bob_wl.id) is not None


def test_list_by_user_isolates_foreign_data(session):
    alice = _seed_user(session, username="alice")
    bob = _seed_user(session, username="bob")
    repo = WatchlistRepository(session)
    repo.create(user_id=alice, name="alice-list")
    repo.create(user_id=bob, name="bob-list")
    session.commit()
    assert [w.name for w in repo.list_by_user(alice)] == ["alice-list"]
    assert [w.name for w in repo.list_by_user(bob)] == ["bob-list"]


def test_delete_watchlist_cascades_items(session):
    user_id = _seed_user(session)
    wl_repo = WatchlistRepository(session)
    item_repo = WatchlistItemRepository(session)
    wl = wl_repo.create(user_id=user_id, name="L")
    item_repo.add_item(watchlist_id=wl.id, symbol="005930")
    item_repo.add_item(watchlist_id=wl.id, symbol="000660")
    session.commit()
    assert len(item_repo.list_items(wl.id)) == 2
    wl_repo.delete(wl)
    session.commit()
    assert item_repo.list_items(wl.id) == []


# ---------- WatchlistItemRepository ----------


def test_add_item_normalizes_symbol(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    item = WatchlistItemRepository(session).add_item(
        watchlist_id=wl.id, symbol="  aapl "
    )
    session.commit()
    assert item.symbol == "AAPL"


def test_add_item_unique_per_watchlist_and_symbol(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    repo.add_item(watchlist_id=wl.id, symbol="005930")
    with pytest.raises(IntegrityError):
        # Even with normalisation differences, the canonical form collides.
        repo.add_item(watchlist_id=wl.id, symbol=" 005930 ")


def test_add_item_same_symbol_in_different_watchlists_ok(session):
    user_id = _seed_user(session)
    wl_repo = WatchlistRepository(session)
    a = wl_repo.create(user_id=user_id, name="A")
    b = wl_repo.create(user_id=user_id, name="B")
    session.commit()
    items = WatchlistItemRepository(session)
    items.add_item(watchlist_id=a.id, symbol="005930")
    items.add_item(watchlist_id=b.id, symbol="005930")
    session.commit()
    assert items.exists(watchlist_id=a.id, symbol="005930")
    assert items.exists(watchlist_id=b.id, symbol="005930")


def test_memo_length_at_limit_accepted(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    long_memo = "x" * MAX_MEMO_LENGTH
    item = WatchlistItemRepository(session).add_item(
        watchlist_id=wl.id, symbol="005930", memo=long_memo
    )
    session.commit()
    assert item.memo == long_memo


def test_memo_too_long_rejected(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    too_long = "x" * (MAX_MEMO_LENGTH + 1)
    with pytest.raises(ValueError):
        WatchlistItemRepository(session).add_item(
            watchlist_id=wl.id, symbol="005930", memo=too_long
        )


def test_remove_item_returns_true_on_success(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    repo.add_item(watchlist_id=wl.id, symbol="005930")
    session.commit()
    assert repo.remove_item(watchlist_id=wl.id, symbol="005930") is True
    # Idempotent re-call returns False (nothing left to remove).
    assert repo.remove_item(watchlist_id=wl.id, symbol="005930") is False
    assert repo.exists(watchlist_id=wl.id, symbol="005930") is False


def test_remove_item_normalizes_symbol(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    repo.add_item(watchlist_id=wl.id, symbol="aapl")
    session.commit()
    assert repo.remove_item(watchlist_id=wl.id, symbol="  AAPL ") is True


def test_list_items_orders_by_id(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    for sym in ("005930", "000660", "035720"):
        repo.add_item(watchlist_id=wl.id, symbol=sym)
    session.commit()
    rows = repo.list_items(wl.id)
    assert [r.symbol for r in rows] == ["005930", "000660", "035720"]


def test_list_symbols_orders_alphabetically(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    for sym in ("ZZZ", "AAA", "MMM"):
        repo.add_item(watchlist_id=wl.id, symbol=sym)
    session.commit()
    assert repo.list_symbols(wl.id) == ["AAA", "MMM", "ZZZ"]


def test_update_memo_replaces_value(session):
    user_id = _seed_user(session)
    wl = WatchlistRepository(session).create(user_id=user_id, name="L")
    session.commit()
    repo = WatchlistItemRepository(session)
    item = repo.add_item(watchlist_id=wl.id, symbol="005930", memo="initial")
    session.commit()
    repo.update_memo(item, memo="updated")
    session.commit()
    refreshed = repo.get_item(watchlist_id=wl.id, symbol="005930")
    assert refreshed is not None and refreshed.memo == "updated"
    repo.update_memo(item, memo=None)
    session.commit()
    refreshed_again = repo.get_item(watchlist_id=wl.id, symbol="005930")
    assert refreshed_again is not None and refreshed_again.memo is None


def test_no_order_or_quantity_columns_on_watchlist_item():
    """WatchlistItem must NOT carry trade-direction, quantity, or broker fields."""
    from app.db.models import WatchlistItem

    forbidden = {
        "broker",
        "account",
        "quantity",
        "order_price",
        "order_type",
        "side",
        "buy_price",
        "sell_price",
    }
    columns = set(WatchlistItem.__table__.columns.keys())
    leaked = forbidden & columns
    assert not leaked, f"forbidden columns leaked into WatchlistItem: {leaked}"
