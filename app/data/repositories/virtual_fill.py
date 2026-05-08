"""Repository for v0.14 Phase C VirtualFill rows.

VirtualFill rows are the immutable record of every fill produced by
``SimulationBroker.execute_pending_orders()``. Pure SQLAlchemy: no HTTP,
no KIS / DART / RSS imports, no secret material.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import VirtualFill


_ZERO = Decimal("0")


class VirtualFillRepository(BaseRepository[VirtualFill]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VirtualFill)

    # -------- create --------

    def create(
        self,
        *,
        order_id: int,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        fill_price: Decimal,
        fee: Decimal,
        stamp_tax: Decimal,
        slippage: Decimal,
        gross_amount: Decimal,
        net_amount: Decimal,
        filled_at: datetime | None = None,
    ) -> VirtualFill:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if fill_price <= _ZERO:
            raise ValueError("fill_price must be > 0")
        for amount in (fee, stamp_tax, slippage, gross_amount, net_amount):
            if Decimal(amount) < _ZERO:
                raise ValueError("cost / amount fields must be >= 0")
        kwargs = dict(
            order_id=order_id,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            fill_price=fill_price,
            fee=fee,
            stamp_tax=stamp_tax,
            slippage=slippage,
            gross_amount=gross_amount,
            net_amount=net_amount,
        )
        if filled_at is not None:
            kwargs["filled_at"] = filled_at
        return self.add(VirtualFill(**kwargs))

    # -------- read --------

    def list_by_order(self, order_id: int) -> list[VirtualFill]:
        statement = (
            select(VirtualFill)
            .where(VirtualFill.order_id == order_id)
            .order_by(VirtualFill.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_account(
        self, account_id: int, *, limit: int = 200
    ) -> list[VirtualFill]:
        statement = (
            select(VirtualFill)
            .where(VirtualFill.account_id == account_id)
            .order_by(VirtualFill.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
