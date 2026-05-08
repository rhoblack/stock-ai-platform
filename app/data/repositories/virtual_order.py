"""Repository for v0.14 Phase B VirtualOrder rows.

VirtualOrder rows are the persisted form of a paper-trading order. The
repository is pure SQLAlchemy -- no HTTP, no KIS, no auth. Callers (notably
``app.broker.simulation_broker.SimulationBroker``) commit / flush themselves.

State machine handled here (subset for Phase B):

  CREATED ---> SUBMITTED       (acknowledged by simulator, no fill yet)
  CREATED ---> CANCELED        (caller cancel)
  CREATED ---> REJECTED        (validation failure recorded)
  SUBMITTED ---> CANCELED      (caller cancel)
  SUBMITTED ---> PARTIALLY_FILLED / FILLED   (Phase C only -- not written here)

PARTIALLY_FILLED / FILLED / CANCELED / REJECTED are TERMINAL or
fill-progressed states; ``cancel`` rejects them.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import VirtualOrder


VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})
VALID_ORDER_TYPES: frozenset[str] = frozenset({"MARKET", "LIMIT"})
VALID_STATUSES: frozenset[str] = frozenset(
    {"CREATED", "SUBMITTED", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED"}
)
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"FILLED", "PARTIALLY_FILLED", "CANCELED", "REJECTED"}
)
CANCELABLE_STATUSES: frozenset[str] = frozenset({"CREATED", "SUBMITTED"})


class VirtualOrderRepository(BaseRepository[VirtualOrder]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VirtualOrder)

    # -------- create --------

    def create(
        self,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: object = None,
        idempotency_key: str | None = None,
        reason: str | None = None,
        note: str | None = None,
        status: str = "CREATED",
    ) -> VirtualOrder:
        if side not in VALID_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_SIDES)}")
        if order_type not in VALID_ORDER_TYPES:
            raise ValueError(
                f"order_type must be one of {sorted(VALID_ORDER_TYPES)}"
            )
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if order_type == "LIMIT" and limit_price is None:
            raise ValueError("LIMIT order requires limit_price")
        if order_type == "MARKET" and limit_price is not None:
            raise ValueError("MARKET order must not have limit_price")

        return self.add(
            VirtualOrder(
                account_id=account_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                status=status,
                idempotency_key=idempotency_key,
                reason=reason,
                note=note,
            )
        )

    # -------- read --------

    def get_by_id(self, order_id: int) -> VirtualOrder | None:
        return self.session.get(VirtualOrder, order_id)

    def list_by_account(
        self,
        account_id: int,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[VirtualOrder]:
        statement = select(VirtualOrder).where(VirtualOrder.account_id == account_id)
        if status is not None:
            statement = statement.where(VirtualOrder.status == status)
        statement = statement.order_by(VirtualOrder.id.desc()).limit(limit)
        return list(self.session.execute(statement).scalars().all())

    def get_by_idempotency_key(
        self,
        *,
        account_id: int,
        idempotency_key: str,
    ) -> VirtualOrder | None:
        statement = select(VirtualOrder).where(
            VirtualOrder.account_id == account_id,
            VirtualOrder.idempotency_key == idempotency_key,
        )
        return self.session.execute(statement).scalar_one_or_none()

    # -------- write --------

    def update_status(
        self,
        order: VirtualOrder,
        *,
        new_status: str,
        reason: str | None = None,
    ) -> VirtualOrder:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        order.status = new_status
        if reason is not None:
            order.reason = reason
        order.updated_at = utc_now()
        self.session.flush()
        return order

    def cancel(self, order: VirtualOrder, *, reason: str | None = None) -> VirtualOrder:
        """Move a non-terminal order to CANCELED.

        Raises ``ValueError`` for terminal / fill-progressed states
        (FILLED / PARTIALLY_FILLED / CANCELED / REJECTED).
        """
        if order.status not in CANCELABLE_STATUSES:
            raise ValueError(
                f"cannot cancel VirtualOrder in status={order.status!r}; "
                f"only {sorted(CANCELABLE_STATUSES)} are cancelable"
            )
        return self.update_status(order, new_status="CANCELED", reason=reason)
