"""PnLTracker -- v0.14 Phase C bookkeeping for paper trading fills.

Responsibilities
----------------

* Apply a single fill (BUY or SELL) to the (account, position, cash) tuple,
  computing the four cost components from
  :class:`~app.backtest.cost_model.PaperTradingCostModel` and writing a
  matching :class:`~app.db.models.VirtualFill` row.
* Raise :class:`InsufficientCashError` for BUY fills that would drive the
  account's ``cash_balance`` below 0.
* Raise :class:`~app.data.repositories.virtual_position.InsufficientPositionError`
  via the position repository for SELL fills that exceed the held quantity.
* Build a per-account daily PnL snapshot from the current open positions
  and the latest daily_prices on / before the snapshot date.

Hard constraints (regression-tested):

* No KIS / DART / RSS / requests / httpx import is allowed in this module.
* No outbound HTTP / network call is performed. Pricing is read from the
  local ``daily_prices`` table only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.backtest.cost_model import PaperFillCosts, PaperTradingCostModel
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_fill import VirtualFillRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import (
    InsufficientPositionError,
    VirtualPositionRepository,
)
from app.db.models import (
    VirtualAccount,
    VirtualFill,
    VirtualPnLSnapshot,
    VirtualPosition,
)


_ZERO = Decimal("0")


class InsufficientCashError(ValueError):
    """Raised when a BUY fill would drive ``cash_balance`` below 0."""


@dataclass(frozen=True)
class FillResult:
    """Outcome of a single :meth:`PnLTracker.apply_fill` call."""

    fill: VirtualFill
    position: VirtualPosition
    account: VirtualAccount
    costs: PaperFillCosts
    realized_pnl_delta: Decimal


class PnLTracker:
    """Apply paper-trading fills and build per-day account snapshots."""

    def __init__(
        self, cost_model: PaperTradingCostModel | None = None
    ) -> None:
        self._cost_model = cost_model or PaperTradingCostModel()

    # ------------------------------------------------------------------
    # Single-fill application
    # ------------------------------------------------------------------

    def apply_fill(
        self,
        session: Session,
        *,
        order_id: int,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        fill_price: Decimal,
        filled_at: datetime | None = None,
    ) -> FillResult:
        """Persist a fill, mutate cash + position, and return the result.

        BUY: cash_balance decreases by ``net_amount`` (gross + fee + slippage),
        position quantity increases, ``avg_cost`` is rebased.

        SELL: cash_balance increases by ``net_amount`` (gross - fee -
        stamp_tax - slippage), position quantity decreases, ``realized_pnl``
        accumulates ``cash_received - cost_basis``.
        """
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if fill_price <= _ZERO:
            raise ValueError("fill_price must be > 0")

        accounts = VirtualAccountRepository(session)
        positions = VirtualPositionRepository(session)
        fills = VirtualFillRepository(session)

        account = accounts.get_by_id(account_id)
        if account is None:
            raise ValueError(f"VirtualAccount id={account_id} not found")

        costs = self._cost_model.compute(
            side=side, fill_price=fill_price, quantity=quantity
        )

        realized_pnl_delta = _ZERO
        if side == "BUY":
            if account.cash_balance < costs.net_amount:
                raise InsufficientCashError(
                    f"BUY of {quantity} {symbol} requires "
                    f"{costs.net_amount} cash; account has "
                    f"{account.cash_balance}"
                )
            new_balance = Decimal(account.cash_balance) - costs.net_amount
            accounts.update_cash_balance(account, new_balance=new_balance)
            position = positions.apply_buy(
                account_id=account_id,
                symbol=symbol,
                fill_quantity=quantity,
                fill_price=fill_price,
                cash_spent=costs.net_amount,
            )
        else:  # SELL
            position, realized_pnl_delta = positions.apply_sell(
                account_id=account_id,
                symbol=symbol,
                fill_quantity=quantity,
                cash_received=costs.net_amount,
            )
            new_balance = Decimal(account.cash_balance) + costs.net_amount
            accounts.update_cash_balance(account, new_balance=new_balance)

        fill = fills.create(
            order_id=order_id,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            fill_price=fill_price,
            fee=costs.fee,
            stamp_tax=costs.stamp_tax,
            slippage=costs.slippage,
            gross_amount=costs.gross_amount,
            net_amount=costs.net_amount,
            filled_at=filled_at,
        )

        return FillResult(
            fill=fill,
            position=position,
            account=account,
            costs=costs,
            realized_pnl_delta=realized_pnl_delta,
        )

    # ------------------------------------------------------------------
    # Daily snapshot
    # ------------------------------------------------------------------

    def create_daily_pnl_snapshot(
        self,
        session: Session,
        *,
        account_id: int,
        snapshot_date: date,
        price_lookback_days: int = 14,
    ) -> VirtualPnLSnapshot:
        """Compute and persist the (account_id, snapshot_date) snapshot.

        ``market_value`` and ``unrealized_pnl`` are calculated from open
        positions priced at the most recent daily_prices.close on or before
        ``snapshot_date`` (within ``price_lookback_days`` calendar days).
        Positions whose symbol has no usable price contribute 0 to
        ``market_value`` -- the snapshot job stays graceful when prices are
        late or missing.
        """
        accounts = VirtualAccountRepository(session)
        positions = VirtualPositionRepository(session)
        prices = DailyPriceRepository(session)
        snapshots = VirtualPnLSnapshotRepository(session)

        account = accounts.get_by_id(account_id)
        if account is None:
            raise ValueError(f"VirtualAccount id={account_id} not found")

        market_value = _ZERO
        unrealized_pnl = _ZERO
        realized_total = _ZERO

        for pos in positions.list_by_account(account_id):
            realized_total += Decimal(pos.realized_pnl)
            if pos.quantity <= 0:
                continue
            bar = prices.get_latest_on_or_before(
                symbol=pos.symbol,
                target_date=snapshot_date,
                lookback_days=price_lookback_days,
            )
            if bar is None or bar.close is None:
                # Graceful: open position with no price contributes 0 to
                # market_value AND 0 to unrealized_pnl rather than failing
                # the whole snapshot.
                continue
            symbol_market_value = Decimal(bar.close) * Decimal(pos.quantity)
            symbol_cost_basis = (
                Decimal(pos.avg_cost) * Decimal(pos.quantity)
            )
            market_value += symbol_market_value
            unrealized_pnl += symbol_market_value - symbol_cost_basis

        return snapshots.create_or_replace_snapshot(
            account_id=account_id,
            snapshot_date=snapshot_date,
            cash_balance=Decimal(account.cash_balance),
            market_value=market_value,
            realized_pnl=realized_total,
            unrealized_pnl=unrealized_pnl,
        )


__all__ = [
    "FillResult",
    "InsufficientCashError",
    "InsufficientPositionError",
    "PnLTracker",
]
