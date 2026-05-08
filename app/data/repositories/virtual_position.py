"""Repository for v0.14 Phase C VirtualPosition rows.

VirtualPosition is the per-(account, symbol) holding state used by the
paper / simulation trading PnL engine. The repository is pure SQLAlchemy:
no HTTP, no KIS / DART / RSS imports, no secret material. Callers commit
or flush themselves.

Position lifecycle
------------------

  * BUY: ``apply_buy`` raises ``quantity`` and recomputes ``avg_cost`` using
    a cost-basis blend (cash spent on this fill, fees included, divided by
    the new total quantity).
  * SELL: ``apply_sell`` lowers ``quantity`` and accumulates ``realized_pnl``.
    When ``quantity`` reaches 0 the row is preserved (for history) but
    ``avg_cost`` is reset to 0 so a future re-entry starts clean.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import VirtualPosition


_ZERO = Decimal("0")


class VirtualPositionRepository(BaseRepository[VirtualPosition]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VirtualPosition)

    # -------- read --------

    def get_by_account_symbol(
        self, *, account_id: int, symbol: str
    ) -> VirtualPosition | None:
        statement = select(VirtualPosition).where(
            VirtualPosition.account_id == account_id,
            VirtualPosition.symbol == symbol,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_account(self, account_id: int) -> list[VirtualPosition]:
        statement = (
            select(VirtualPosition)
            .where(VirtualPosition.account_id == account_id)
            .order_by(VirtualPosition.symbol.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_open_by_account(self, account_id: int) -> list[VirtualPosition]:
        statement = (
            select(VirtualPosition)
            .where(
                VirtualPosition.account_id == account_id,
                VirtualPosition.quantity > 0,
            )
            .order_by(VirtualPosition.symbol.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    # -------- write --------

    def get_or_create(
        self, *, account_id: int, symbol: str
    ) -> VirtualPosition:
        existing = self.get_by_account_symbol(
            account_id=account_id, symbol=symbol
        )
        if existing is not None:
            return existing
        return self.add(
            VirtualPosition(
                account_id=account_id,
                symbol=symbol,
                quantity=0,
                avg_cost=_ZERO,
                realized_pnl=_ZERO,
            )
        )

    def upsert_position(
        self,
        *,
        account_id: int,
        symbol: str,
        quantity: int,
        avg_cost: Decimal,
        realized_pnl_delta: Decimal = _ZERO,
    ) -> VirtualPosition:
        """Set ``quantity`` and ``avg_cost`` directly; add ``realized_pnl_delta``.

        Lower-level helper used by tests / future reconciliation. PnLTracker
        normally calls :meth:`apply_buy` / :meth:`apply_sell` instead.
        """
        if quantity < 0:
            raise ValueError("quantity must be >= 0")
        position = self.get_or_create(account_id=account_id, symbol=symbol)
        position.quantity = quantity
        position.avg_cost = avg_cost if quantity > 0 else _ZERO
        position.realized_pnl = (
            Decimal(position.realized_pnl) + Decimal(realized_pnl_delta)
        )
        position.updated_at = utc_now()
        self.session.flush()
        return position

    def update_realized_pnl(
        self,
        position: VirtualPosition,
        *,
        delta: Decimal,
    ) -> VirtualPosition:
        position.realized_pnl = Decimal(position.realized_pnl) + Decimal(delta)
        position.updated_at = utc_now()
        self.session.flush()
        return position

    def apply_buy(
        self,
        *,
        account_id: int,
        symbol: str,
        fill_quantity: int,
        fill_price: Decimal,
        cash_spent: Decimal,
    ) -> VirtualPosition:
        """Add ``fill_quantity`` to the position and recompute ``avg_cost``.

        ``cash_spent`` is the actual cash outflow for this BUY fill (gross +
        fee + slippage). The new ``avg_cost`` is
        ``(prev_qty * prev_avg + cash_spent) / (prev_qty + fill_quantity)``
        so cost basis correctly absorbs the trading costs.
        """
        if fill_quantity <= 0:
            raise ValueError("fill_quantity must be > 0")
        if fill_price <= _ZERO:
            raise ValueError("fill_price must be > 0")
        if cash_spent < _ZERO:
            raise ValueError("cash_spent must be >= 0")

        position = self.get_or_create(account_id=account_id, symbol=symbol)
        prev_qty = position.quantity
        prev_avg = Decimal(position.avg_cost)
        new_qty = prev_qty + fill_quantity
        new_total_cost = prev_avg * Decimal(prev_qty) + Decimal(cash_spent)
        position.quantity = new_qty
        position.avg_cost = new_total_cost / Decimal(new_qty)
        position.updated_at = utc_now()
        self.session.flush()
        return position

    def apply_sell(
        self,
        *,
        account_id: int,
        symbol: str,
        fill_quantity: int,
        cash_received: Decimal,
    ) -> tuple[VirtualPosition, Decimal]:
        """Reduce the position by ``fill_quantity`` and accumulate realized PnL.

        Returns ``(position, realized_pnl_delta)``.

        Raises :class:`InsufficientPositionError` when the held quantity is
        less than the requested ``fill_quantity`` -- short-selling is NOT
        supported in Phase C.
        """
        if fill_quantity <= 0:
            raise ValueError("fill_quantity must be > 0")
        if cash_received < _ZERO:
            raise ValueError("cash_received must be >= 0")

        position = self.get_by_account_symbol(
            account_id=account_id, symbol=symbol
        )
        if position is None or position.quantity < fill_quantity:
            held = 0 if position is None else position.quantity
            raise InsufficientPositionError(
                f"cannot sell {fill_quantity} of {symbol!r} — held {held}"
            )

        cost_basis = Decimal(position.avg_cost) * Decimal(fill_quantity)
        realized_pnl_delta = Decimal(cash_received) - cost_basis

        position.quantity -= fill_quantity
        if position.quantity == 0:
            position.avg_cost = _ZERO
        position.realized_pnl = (
            Decimal(position.realized_pnl) + realized_pnl_delta
        )
        position.updated_at = utc_now()
        self.session.flush()
        return position, realized_pnl_delta


class InsufficientPositionError(ValueError):
    """Raised when a SELL would drive the position below 0."""
