"""Integration tests for v0.14 Phase C virtual trading PnL & fill engine.

Covers:
  * VirtualPosition / VirtualFill / VirtualPnLSnapshot repositories
  * PnLTracker.apply_fill BUY / SELL / insufficient cash / insufficient
    position semantics
  * PnLTracker.create_daily_pnl_snapshot — open positions priced at
    daily_prices.close, missing prices handled gracefully
  * SimulationBroker.execute_pending_orders — MARKET / LIMIT crossing /
    no-price skip / terminal-state skip / insufficient-cash REJECT path /
    insufficient-position REJECT path
  * Forbidden columns on the three new tables
  * Alembic upgrade head / downgrade restores 0005 baseline
"""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.broker.simulation_broker import (
    ExecutePendingResult,
    SimulationBroker,
)
from app.config.settings import Settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_fill import VirtualFillRepository
from app.data.repositories.virtual_order import VirtualOrderRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import (
    InsufficientPositionError,
    VirtualPositionRepository,
)
from app.db.base import Base
from app.db.models import (
    VirtualAccount,
    VirtualFill,
    VirtualPnLSnapshot,
    VirtualPosition,
)
from app.db.session import create_session_factory
from app.paper.pnl_tracker import InsufficientCashError, PnLTracker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_conn.cursor()
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


def _make_alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.cmd_opts = type("Args", (), {"x": [f"url={database_url}"]})()  # type: ignore[attr-defined]
    return cfg


def _seed_account(
    session, *, name: str = "paper", initial_cash: Decimal = Decimal("1000000")
) -> int:
    repo = VirtualAccountRepository(session)
    acc = repo.create(name=name, initial_cash=initial_cash)
    session.commit()
    return acc.id


def _seed_order(
    session,
    *,
    account_id: int,
    symbol: str = "005930",
    side: str = "BUY",
    quantity: int = 10,
    order_type: str = "MARKET",
    limit_price=None,
) -> int:
    """Insert a CREATED-state VirtualOrder so VirtualFill.order_id FKs are valid."""
    order = VirtualOrderRepository(session).create(
        account_id=account_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
    )
    session.commit()
    return order.id


def _seed_price(
    session,
    *,
    symbol: str,
    price_date: date,
    close: Decimal,
):
    DailyPriceRepository(session).upsert(
        symbol=symbol,
        price_date=price_date,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1_000,
    )
    session.commit()


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


def test_position_unique_account_symbol(session):
    account_id = _seed_account(session)
    repo = VirtualPositionRepository(session)
    repo.get_or_create(account_id=account_id, symbol="005930")
    session.commit()
    repo.get_or_create(account_id=account_id, symbol="005930")  # idempotent
    session.commit()
    # Manually try to insert duplicate -> IntegrityError on flush.
    with pytest.raises(IntegrityError):
        session.add(
            VirtualPosition(
                account_id=account_id,
                symbol="005930",
                quantity=0,
                avg_cost=Decimal("0"),
                realized_pnl=Decimal("0"),
            )
        )
        session.flush()


def test_position_apply_buy_blends_avg_cost(session):
    account_id = _seed_account(session)
    repo = VirtualPositionRepository(session)
    pos = repo.apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("100"),
        cash_spent=Decimal("1015"),  # gross 1000 + fee 15
    )
    session.commit()
    assert pos.quantity == 10
    # avg_cost = 1015 / 10 = 101.5
    assert pos.avg_cost == Decimal("101.5")

    pos2 = repo.apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("200"),
        cash_spent=Decimal("2030"),  # gross 2000 + fee 30
    )
    session.commit()
    # new total cost = 1015 + 2030 = 3045 over 20 -> 152.25
    assert pos2.quantity == 20
    assert pos2.avg_cost == Decimal("152.25")


def test_position_apply_sell_realized_pnl_and_zero_resets_avg(session):
    account_id = _seed_account(session)
    repo = VirtualPositionRepository(session)
    repo.apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("100"),
        cash_spent=Decimal("1000"),
    )
    session.commit()

    pos, delta = repo.apply_sell(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        cash_received=Decimal("1500"),
    )
    session.commit()

    assert pos.quantity == 0
    assert pos.avg_cost == Decimal("0")
    # cost_basis = 100 * 10 = 1000; delta = 1500 - 1000 = 500
    assert delta == Decimal("500")
    assert pos.realized_pnl == Decimal("500")


def test_position_apply_sell_more_than_held_raises(session):
    account_id = _seed_account(session)
    repo = VirtualPositionRepository(session)
    repo.apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=5,
        fill_price=Decimal("100"),
        cash_spent=Decimal("500"),
    )
    session.commit()
    with pytest.raises(InsufficientPositionError):
        repo.apply_sell(
            account_id=account_id,
            symbol="005930",
            fill_quantity=10,
            cash_received=Decimal("1000"),
        )


def test_fill_repo_create_and_list(session):
    account_id = _seed_account(session)
    orders_repo = VirtualOrderRepository(session)
    order = orders_repo.create(
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    session.commit()

    fills = VirtualFillRepository(session)
    f = fills.create(
        order_id=order.id,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        fill_price=Decimal("100"),
        fee=Decimal("1.5"),
        stamp_tax=Decimal("0"),
        slippage=Decimal("0.5"),
        gross_amount=Decimal("1000"),
        net_amount=Decimal("1002"),
    )
    session.commit()
    assert f.id is not None
    assert fills.list_by_order(order.id) == [f]
    assert fills.list_by_account(account_id)[0].id == f.id


def test_pnl_snapshot_unique_per_date_replaces_in_place(session):
    account_id = _seed_account(session)
    snaps = VirtualPnLSnapshotRepository(session)
    s1 = snaps.create_or_replace_snapshot(
        account_id=account_id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("1000"),
        market_value=Decimal("0"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    s2 = snaps.create_or_replace_snapshot(
        account_id=account_id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("900"),
        market_value=Decimal("100"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("-10"),
    )
    session.commit()

    assert s1.id == s2.id
    assert s2.total_value == Decimal("1000")  # 900 + 100
    assert s2.unrealized_pnl == Decimal("-10")


# ---------------------------------------------------------------------------
# PnLTracker.apply_fill
# ---------------------------------------------------------------------------


def test_apply_fill_buy_decreases_cash_increases_position(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    order_id = _seed_order(session, account_id=account_id, symbol="005930", quantity=10)
    tracker = PnLTracker()
    result = tracker.apply_fill(
        session,
        order_id=order_id,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        fill_price=Decimal("10000"),
    )
    session.commit()

    # gross 100,000; fee 15; slippage 50; tax 0; net 100,065
    assert result.costs.net_amount == Decimal("100065.0000")
    assert result.position.quantity == 10
    assert result.position.avg_cost == Decimal("10006.5000")  # 100065 / 10

    fresh = VirtualAccountRepository(session).get_by_id(account_id)
    assert fresh.cash_balance == Decimal("899935.0000")  # 1,000,000 - 100,065


def test_apply_fill_sell_increases_cash_realizes_pnl(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    buy_id = _seed_order(session, account_id=account_id, side="BUY")
    sell_id = _seed_order(
        session, account_id=account_id, side="SELL"
    )
    tracker = PnLTracker()
    tracker.apply_fill(
        session,
        order_id=buy_id,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        fill_price=Decimal("10000"),
    )
    session.commit()

    sell = tracker.apply_fill(
        session,
        order_id=sell_id,
        account_id=account_id,
        symbol="005930",
        side="SELL",
        quantity=10,
        fill_price=Decimal("11000"),
    )
    session.commit()

    # SELL gross 110,000; fee 16.5; tax 198; slip 55; net 109,730.5
    assert sell.costs.net_amount == Decimal("109730.5000")
    assert sell.position.quantity == 0
    assert sell.position.avg_cost == Decimal("0")

    # realized = cash_received(109,730.5) - cost_basis(100,065) = 9,665.5
    assert sell.realized_pnl_delta == Decimal("9665.5000")
    assert sell.position.realized_pnl == Decimal("9665.5000")

    fresh = VirtualAccountRepository(session).get_by_id(account_id)
    # 1,000,000 - 100,065 + 109,730.5 = 1,009,665.5
    assert fresh.cash_balance == Decimal("1009665.5000")


def test_apply_fill_buy_insufficient_cash_raises(session):
    account_id = _seed_account(session, initial_cash=Decimal("100"))
    order_id = _seed_order(session, account_id=account_id)
    tracker = PnLTracker()
    with pytest.raises(InsufficientCashError):
        tracker.apply_fill(
            session,
            order_id=order_id,
            account_id=account_id,
            symbol="005930",
            side="BUY",
            quantity=10,
            fill_price=Decimal("10000"),
        )


def test_apply_fill_sell_more_than_held_raises(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    order_id = _seed_order(session, account_id=account_id, side="SELL", quantity=5)
    tracker = PnLTracker()
    with pytest.raises(InsufficientPositionError):
        tracker.apply_fill(
            session,
            order_id=order_id,
            account_id=account_id,
            symbol="005930",
            side="SELL",
            quantity=5,
            fill_price=Decimal("10000"),
        )


# ---------------------------------------------------------------------------
# PnLTracker.create_daily_pnl_snapshot
# ---------------------------------------------------------------------------


def test_daily_snapshot_uses_close_price_for_market_value(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    order_id = _seed_order(session, account_id=account_id)
    tracker = PnLTracker()
    tracker.apply_fill(
        session,
        order_id=order_id,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        fill_price=Decimal("10000"),
    )
    session.commit()

    # Cash now: 1,000,000 - 100,065 = 899,935
    # Position: qty 10 at avg_cost 10006.5
    # Today's close: 11,000 -> market_value = 110,000
    # unrealized = 110,000 - 10006.5*10 = 110,000 - 100,065 = 9,935
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("11000"),
    )

    snap = tracker.create_daily_pnl_snapshot(
        session, account_id=account_id, snapshot_date=date(2026, 5, 8)
    )
    session.commit()

    assert snap.cash_balance == Decimal("899935.0000")
    assert snap.market_value == Decimal("110000.0000")
    assert snap.total_value == Decimal("1009935.0000")
    assert snap.unrealized_pnl == Decimal("9935.0000")
    assert snap.realized_pnl == Decimal("0")


def test_daily_snapshot_graceful_when_price_missing(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    order_id = _seed_order(session, account_id=account_id, symbol="UNKNOWN", quantity=1)
    tracker = PnLTracker()
    tracker.apply_fill(
        session,
        order_id=order_id,
        account_id=account_id,
        symbol="UNKNOWN",
        side="BUY",
        quantity=1,
        fill_price=Decimal("100"),
    )
    session.commit()

    snap = tracker.create_daily_pnl_snapshot(
        session, account_id=account_id, snapshot_date=date(2026, 5, 8)
    )
    session.commit()

    # No daily_prices row -> market_value contribution is 0,
    # unrealized_pnl contribution is 0 (NOT negative cost basis).
    assert snap.market_value == Decimal("0")
    assert snap.unrealized_pnl == Decimal("0")


# ---------------------------------------------------------------------------
# SimulationBroker.execute_pending_orders
# ---------------------------------------------------------------------------


def _settings(*, enabled: bool) -> Settings:
    return Settings(paper_trading_enabled=enabled)


def _create_order(session, *, account_id, **kwargs) -> int:
    broker = SimulationBroker(settings=_settings(enabled=True))
    order = broker.submit_order(session, account_id=account_id, **kwargs).order
    session.commit()
    return order.id


def test_execute_market_buy_fills_and_writes_fill_row(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("10000"),
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )

    broker = SimulationBroker(settings=_settings(enabled=True))
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()

    assert isinstance(result, ExecutePendingResult)
    assert result.filled_count == 1
    assert result.rejected_count == 0
    assert result.skipped_no_price == 0

    order = VirtualOrderRepository(session).get_by_id(order_id)
    assert order.status == "FILLED"

    fills = VirtualFillRepository(session).list_by_order(order_id)
    assert len(fills) == 1
    assert fills[0].fill_price == Decimal("10000")
    assert fills[0].side == "BUY"


def test_execute_skips_when_no_daily_price(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )

    broker = SimulationBroker(settings=_settings(enabled=True))
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()

    assert result.filled_count == 0
    assert result.skipped_no_price == 1
    order = VirtualOrderRepository(session).get_by_id(order_id)
    # Order kept CREATED so a future run can retry.
    assert order.status == "CREATED"


def test_execute_limit_buy_fills_only_when_close_below_limit(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    # close > limit -> no fill
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("11000"),
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
        order_type="LIMIT",
        limit_price=Decimal("10000"),
    )

    broker = SimulationBroker(settings=_settings(enabled=True))
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()

    assert result.filled_count == 0
    assert result.skipped_limit_unmet == 1
    assert (
        VirtualOrderRepository(session).get_by_id(order_id).status == "CREATED"
    )

    # Drop close to the limit -> fills.
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 9),
        close=Decimal("9000"),
    )
    result2 = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 9)
    )
    session.commit()
    assert result2.filled_count == 1


def test_execute_limit_sell_requires_close_at_or_above_limit(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    # Seed an existing position so we have something to sell.
    VirtualPositionRepository(session).apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("8000"),
        cash_spent=Decimal("80000"),
    )
    session.commit()

    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("9000"),  # below limit
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="SELL",
        quantity=10,
        order_type="LIMIT",
        limit_price=Decimal("10000"),
    )
    broker = SimulationBroker(settings=_settings(enabled=True))
    res = broker.execute_pending_orders(session, as_of_date=date(2026, 5, 8))
    session.commit()
    assert res.filled_count == 0
    assert res.skipped_limit_unmet == 1
    assert (
        VirtualOrderRepository(session).get_by_id(order_id).status == "CREATED"
    )


def test_execute_rejects_buy_when_cash_insufficient(session):
    account_id = _seed_account(session, initial_cash=Decimal("100"))
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("10000"),
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    broker = SimulationBroker(settings=_settings(enabled=True))
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()

    assert result.filled_count == 0
    assert result.rejected_count == 1
    rejected = VirtualOrderRepository(session).get_by_id(order_id)
    assert rejected.status == "REJECTED"
    assert rejected.reason and "cash" in rejected.reason.lower()


def test_execute_rejects_sell_when_position_insufficient(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("10000"),
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="SELL",
        quantity=10,
    )
    broker = SimulationBroker(settings=_settings(enabled=True))
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()

    assert result.rejected_count == 1
    rejected = VirtualOrderRepository(session).get_by_id(order_id)
    assert rejected.status == "REJECTED"


def test_execute_does_not_replay_terminal_orders(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("10000"),
    )
    order_id = _create_order(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    broker = SimulationBroker(settings=_settings(enabled=True))
    broker.execute_pending_orders(session, as_of_date=date(2026, 5, 8))
    session.commit()
    # Now the order is FILLED. A second invocation must NOT produce a
    # second VirtualFill row.
    result = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8)
    )
    session.commit()
    assert result.filled_count == 0
    fills = VirtualFillRepository(session).list_by_order(order_id)
    assert len(fills) == 1


def test_execute_account_filter_only_fills_target_account(session):
    a1 = _seed_account(session, name="acct-1", initial_cash=Decimal("1000000"))
    a2 = _seed_account(session, name="acct-2", initial_cash=Decimal("1000000"))
    _seed_price(
        session,
        symbol="005930",
        price_date=date(2026, 5, 8),
        close=Decimal("10000"),
    )
    o1 = _create_order(
        session,
        account_id=a1,
        symbol="005930",
        side="BUY",
        quantity=1,
    )
    o2 = _create_order(
        session,
        account_id=a2,
        symbol="005930",
        side="BUY",
        quantity=1,
    )
    broker = SimulationBroker(settings=_settings(enabled=True))
    res = broker.execute_pending_orders(
        session, as_of_date=date(2026, 5, 8), account_id=a1
    )
    session.commit()
    assert res.filled_count == 1
    assert (
        VirtualOrderRepository(session).get_by_id(o1).status == "FILLED"
    )
    assert (
        VirtualOrderRepository(session).get_by_id(o2).status == "CREATED"
    )


# ---------------------------------------------------------------------------
# Forbidden columns
# ---------------------------------------------------------------------------


_FORBIDDEN_COLUMNS = (
    "broker_order_id",
    "kis_order_id",
    "real_account",
    "api_key",
    "token",
    "secret",
)


@pytest.mark.parametrize(
    "model", [VirtualPosition, VirtualFill, VirtualPnLSnapshot]
)
def test_phase_c_models_have_no_forbidden_columns(model):
    column_names = {col.key for col in model.__table__.columns}
    leaked = column_names & set(_FORBIDDEN_COLUMNS)
    assert leaked == set()


# ---------------------------------------------------------------------------
# Alembic upgrade head / downgrade
# ---------------------------------------------------------------------------


def test_alembic_upgrade_head_creates_phase_c_tables(tmp_path):
    db_file = tmp_path / "v014_phase_c.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    for required in (
        "virtual_positions",
        "virtual_fills",
        "virtual_pnl_snapshots",
    ):
        assert required in names


def test_alembic_downgrade_phase_c_drops_only_three_tables(tmp_path):
    db_file = tmp_path / "v014_phase_c_dn.db"
    url = f"sqlite:///{db_file.as_posix()}"
    cfg = _make_alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0005_virtual_trading_core")

    engine = create_engine(url)
    try:
        names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "virtual_positions" not in names
    assert "virtual_fills" not in names
    assert "virtual_pnl_snapshots" not in names
    # Phase B tables remain.
    assert "virtual_accounts" in names
    assert "virtual_orders" in names


# ---------------------------------------------------------------------------
# Hard guarantees: NO KIS / external HTTP imports in Phase C modules
# ---------------------------------------------------------------------------


_FORBIDDEN_MODULES = {"requests", "httpx", "urllib", "urllib3"}
_FORBIDDEN_PREFIXES = (
    "app.kis",
    "app.data.dart_provider",
    "app.data.rss_provider",
)


def _ast_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return imports


def _assert_no_forbidden(path: Path) -> None:
    leaks = []
    for name in _ast_imports(path):
        if name in _FORBIDDEN_MODULES or any(
            name == p or name.startswith(p + ".") for p in _FORBIDDEN_PREFIXES
        ):
            leaks.append(name)
    assert leaks == [], (
        f"{path.name} unexpectedly imports forbidden modules: {leaks!r}"
    )


def test_pnl_tracker_has_no_forbidden_imports():
    _assert_no_forbidden(PROJECT_ROOT / "app" / "paper" / "pnl_tracker.py")


def test_simulation_broker_phase_c_has_no_forbidden_imports():
    _assert_no_forbidden(
        PROJECT_ROOT / "app" / "broker" / "simulation_broker.py"
    )


def test_paper_repositories_have_no_forbidden_imports():
    repo_dir = PROJECT_ROOT / "app" / "data" / "repositories"
    for name in (
        "virtual_position.py",
        "virtual_fill.py",
        "virtual_pnl_snapshot.py",
    ):
        _assert_no_forbidden(repo_dir / name)
