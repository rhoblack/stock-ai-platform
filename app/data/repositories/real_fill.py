"""Repository for v0.16 Phase C RealFill rows.

RealFill rows record individual fill events against a RealOrder. Phase C
defines the ORM skeleton only; no fills are ever written in this phase because
no KIS HTTP calls exist yet.

v0.16 Phase D's FillSyncService writes mock fill rows (FakeKisOrderTransport
always returns FILLED). v1.0 Phase D adds delta-based idempotent updates so
repeat sync calls never duplicate fill rows — see ``total_filled_quantity``.

Hard safety constraints:
  * No raw KIS response storage -- no such parameter or method exists here.
  * No sensitive values (api_key, secret, account_no) stored in any column.
  * fill_status must be "FULL" or "PARTIAL".
  * fill_price and quantity must be strictly positive.
  * gross_amount and net_amount must be non-negative.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import RealFill


VALID_FILL_STATUSES: frozenset[str] = frozenset({"FULL", "PARTIAL"})
VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})


class RealFillRepository(BaseRepository[RealFill]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RealFill)

    # -------- create --------

    def create(
        self,
        *,
        real_order_id: int,
        symbol: str,
        side: str,
        quantity: int,
        fill_price: object,
        fee: object = 0,
        tax: object = 0,
        gross_amount: object,
        net_amount: object,
        fill_status: str,
        filled_at: object = None,
    ) -> RealFill:
        from app.db.base import utc_now
        from decimal import Decimal

        if side not in VALID_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_SIDES)}")
        if fill_status not in VALID_FILL_STATUSES:
            raise ValueError(f"fill_status must be one of {sorted(VALID_FILL_STATUSES)}")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if Decimal(str(fill_price)) <= 0:
            raise ValueError("fill_price must be > 0")
        if Decimal(str(gross_amount)) < 0:
            raise ValueError("gross_amount must be >= 0")
        if Decimal(str(net_amount)) < 0:
            raise ValueError("net_amount must be >= 0")

        return self.add(
            RealFill(
                real_order_id=real_order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                fill_price=fill_price,
                fee=fee,
                tax=tax,
                gross_amount=gross_amount,
                net_amount=net_amount,
                fill_status=fill_status,
                filled_at=filled_at or utc_now(),
            )
        )

    # -------- read --------

    def list_by_order(self, real_order_id: int, *, limit: int = 100) -> list[RealFill]:
        stmt = (
            select(RealFill)
            .where(RealFill.real_order_id == real_order_id)
            .order_by(RealFill.filled_at.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_recent(self, *, limit: int = 100) -> list[RealFill]:
        stmt = select(RealFill).order_by(RealFill.id.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    # v1.0 Phase D — delta-based idempotency helper.
    #
    # FillSyncService computes ``delta = kis_total - existing_total`` and
    # creates a single RealFill row with ``quantity=delta`` only when
    # ``delta > 0``. Repeated sync calls with the same upstream KIS state
    # therefore yield ``delta == 0`` and zero new rows. ``delta < 0`` is
    # treated as a data anomaly (KIS-side reduction below internal record).
    def total_filled_quantity(self, real_order_id: int) -> int:
        """Return the sum of ``quantity`` across all RealFill rows for the order.

        Returns 0 when no fills exist. The DB-level ``SUM`` keeps this
        constant-time regardless of fill row count.
        """
        stmt = select(
            func.coalesce(func.sum(RealFill.quantity), 0)
        ).where(RealFill.real_order_id == real_order_id)
        result = self.session.execute(stmt).scalar()
        return int(result or 0)
