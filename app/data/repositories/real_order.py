"""Repository for v0.16 Phase C RealOrder rows.

RealOrder rows are the persistent execution records for every order attempt
that exits the Approval Workflow. The repository is pure SQLAlchemy -- no HTTP,
no KIS, no auth. Callers commit / flush themselves.

Status machine (subset for Phase C -- Phase D will add SUBMITTED transitions):

  DRY_RUN  (terminal)   -- order recorded by FakeKisOrderTransport; no real submission.
  CREATED  → SUBMITTED  -- Phase D: order forwarded to KIS.
  SUBMITTED → PARTIALLY_FILLED / FILLED  -- Phase D: KIS fill confirmed.
  SUBMITTED / PARTIALLY_FILLED → CANCELED / REJECTED / FAILED  -- Phase D.

TERMINAL_STATUSES are write-once after reaching that state: no further
transition is permitted to prevent double-accounting.

Hard safety constraints:
  * error_message must not contain sensitive substrings (api_key, secret, token,
    account). mark_failed() raises if the message fails the check.
  * dry_run defaults to True in create(); callers must opt out explicitly.
  * No raw KIS response storage -- no such method exists on this repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import RealOrder


VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})
VALID_ORDER_TYPES: frozenset[str] = frozenset({"MARKET", "LIMIT"})
VALID_STATUSES: frozenset[str] = frozenset(
    {
        "DRY_RUN",
        "CREATED",
        "SUBMITTED",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCELED",
        "REJECTED",
        "FAILED",
    }
)
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"DRY_RUN", "FILLED", "CANCELED", "REJECTED", "FAILED"}
)
VALID_FILL_STATUSES: frozenset[str] = frozenset({"FULL", "PARTIAL"})

# Substrings that must never appear in error_message.
_SENSITIVE_SUBSTRINGS: frozenset[str] = frozenset(
    {"api_key", "appsecret", "secretkey", "access_token", "authorization", "account_no"}
)


def _check_error_message(message: str) -> None:
    lower = message.lower()
    for substr in _SENSITIVE_SUBSTRINGS:
        if substr in lower:
            raise ValueError(
                f"error_message must not contain sensitive substring {substr!r}"
            )


class RealOrderRepository(BaseRepository[RealOrder]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RealOrder)

    # -------- create --------

    def create(
        self,
        *,
        candidate_id: int,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: object = None,
        estimated_amount: object = 0,
        dry_run: bool = True,
        fake_order_no: str | None = None,
        request_id: str | None = None,
        status: str = "DRY_RUN",
    ) -> RealOrder:
        if side not in VALID_SIDES:
            raise ValueError(f"side must be one of {sorted(VALID_SIDES)}")
        if order_type not in VALID_ORDER_TYPES:
            raise ValueError(f"order_type must be one of {sorted(VALID_ORDER_TYPES)}")
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if order_type == "LIMIT" and limit_price is None:
            raise ValueError("LIMIT order requires limit_price")
        if order_type == "MARKET" and limit_price is not None:
            raise ValueError("MARKET order must not have limit_price")

        return self.add(
            RealOrder(
                candidate_id=candidate_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                estimated_amount=estimated_amount,
                status=status,
                dry_run=dry_run,
                fake_order_no=fake_order_no,
                request_id=request_id,
            )
        )

    # -------- read --------

    def get_by_id(self, order_id: int) -> RealOrder | None:
        return self.session.get(RealOrder, order_id)

    def get_by_candidate_id(self, candidate_id: int) -> list[RealOrder]:
        stmt = (
            select(RealOrder)
            .where(RealOrder.candidate_id == candidate_id)
            .order_by(RealOrder.id.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_recent(self, *, limit: int = 100) -> list[RealOrder]:
        stmt = select(RealOrder).order_by(RealOrder.id.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def list_by_status(self, status: str, *, limit: int = 100) -> list[RealOrder]:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        stmt = (
            select(RealOrder)
            .where(RealOrder.status == status)
            .order_by(RealOrder.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    # -------- state transitions --------

    def update_status(self, order: RealOrder, *, new_status: str) -> RealOrder:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        if order.status in TERMINAL_STATUSES:
            raise ValueError(
                f"cannot transition RealOrder id={order.id} from terminal "
                f"status={order.status!r} to {new_status!r}"
            )
        order.status = new_status
        order.updated_at = utc_now()
        self.session.flush()
        return order

    def mark_submitted(
        self,
        order: RealOrder,
        *,
        broker_order_no_hash: str | None = None,
        submitted_at: datetime | None = None,
    ) -> RealOrder:
        self.update_status(order, new_status="SUBMITTED")
        order.broker_order_no_hash = broker_order_no_hash
        order.submitted_at = submitted_at or utc_now()
        self.session.flush()
        return order

    def mark_failed(
        self,
        order: RealOrder,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> RealOrder:
        if error_message is not None:
            if len(error_message) > 500:
                error_message = error_message[:500]
            _check_error_message(error_message)
        self.update_status(order, new_status="FAILED")
        order.error_code = error_code
        order.error_message = error_message
        self.session.flush()
        return order

    def mark_dry_run(self, order: RealOrder, *, fake_order_no: str | None = None) -> RealOrder:
        if order.status != "CREATED":
            raise ValueError(
                f"mark_dry_run requires status=CREATED (got {order.status!r})"
            )
        order.status = "DRY_RUN"
        order.fake_order_no = fake_order_no
        order.updated_at = utc_now()
        self.session.flush()
        return order
