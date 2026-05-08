"""Repository for v0.15 Phase B OrderCandidate rows.

OrderCandidate is the staging row for the Approval Trading Safety Layer.
Phase B introduces ORM + repository + state machine; the
PreTradeRiskEngine (Phase C), Approval API + AuditLog (Phase D), and
Approval UI (Phase E) consume the persisted rows afterwards.

State machine
-------------

::

    DRAFT
      └─> RISK_CHECKING
            ├─> RISK_REJECTED        (terminal)
            └─> PENDING_APPROVAL
                  ├─> APPROVED
                  │     └─> EXECUTED_PAPER  (terminal)
                  ├─> REJECTED            (terminal)
                  └─> EXPIRED             (terminal)

Repository / state-machine guarantees
-------------------------------------

* Only paper execution is allowed downstream -- ``attach_virtual_order``
  links to ``virtual_orders.id`` only. There is NO real-broker / KIS path.
* Forbidden columns are absent from the ORM by construction. The
  integration test suite re-asserts this on the live SQLAlchemy table.
* ``update_status`` raises :class:`InvalidOrderCandidateTransition` on any
  edge not present in :data:`_ALLOWED_TRANSITIONS`. Terminal states refuse
  every further transition.
* Pure SQLAlchemy: no HTTP, no KIS / DART / RSS imports, no secret
  material.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import OrderCandidate


# ---------------------------------------------------------------------------
# Constants -- exposed for downstream consumers (PreTradeRiskEngine,
# ApprovalService, API schemas).
# ---------------------------------------------------------------------------


VALID_SOURCES: frozenset[str] = frozenset(
    {"RECOMMENDATION", "STRATEGY", "PAPER", "MANUAL"}
)
VALID_SIDES: frozenset[str] = frozenset({"BUY", "SELL"})
VALID_ORDER_TYPES: frozenset[str] = frozenset({"MARKET", "LIMIT"})

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "DRAFT",
        "RISK_CHECKING",
        "RISK_REJECTED",
        "PENDING_APPROVAL",
        "APPROVED",
        "EXECUTED_PAPER",
        "REJECTED",
        "EXPIRED",
    }
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"RISK_REJECTED", "EXECUTED_PAPER", "REJECTED", "EXPIRED"}
)


# Edges of the state machine. Read as: from_status -> {allowed next states}.
# Anything not in the value set raises InvalidOrderCandidateTransition.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"RISK_CHECKING"}),
    "RISK_CHECKING": frozenset({"RISK_REJECTED", "PENDING_APPROVAL"}),
    "PENDING_APPROVAL": frozenset({"APPROVED", "REJECTED", "EXPIRED"}),
    "APPROVED": frozenset({"EXECUTED_PAPER"}),
    # Terminal states -- no outgoing edges.
    "RISK_REJECTED": frozenset(),
    "EXECUTED_PAPER": frozenset(),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
}


_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InvalidOrderCandidateTransition(ValueError):
    """Raised when a state transition violates the documented machine."""


class OrderCandidateValidationError(ValueError):
    """Raised when create() is called with malformed inputs."""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class OrderCandidateRepository(BaseRepository[OrderCandidate]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, OrderCandidate)

    # -------- create --------

    def create(
        self,
        *,
        account_id: int,
        source: str,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Decimal | int | float | str | None = None,
        estimated_amount: Decimal | int | float | str = _ZERO,
        source_ref_id: int | None = None,
        expires_at: datetime | None = None,
        status: str = "DRAFT",
    ) -> OrderCandidate:
        """Insert a new candidate. Defaults to ``DRAFT``.

        Validation here is intentionally minimal -- the repository is the
        last line of defence against malformed rows hitting the DB. Higher
        layers (PreTradeRiskEngine in Phase C) own the business rules.
        """
        if source not in VALID_SOURCES:
            raise OrderCandidateValidationError(
                f"source must be one of {sorted(VALID_SOURCES)} (got {source!r})"
            )
        if side not in VALID_SIDES:
            raise OrderCandidateValidationError(
                f"side must be one of {sorted(VALID_SIDES)} (got {side!r})"
            )
        if order_type not in VALID_ORDER_TYPES:
            raise OrderCandidateValidationError(
                f"order_type must be one of {sorted(VALID_ORDER_TYPES)} "
                f"(got {order_type!r})"
            )
        if status not in VALID_STATUSES:
            raise OrderCandidateValidationError(
                f"status must be one of {sorted(VALID_STATUSES)} "
                f"(got {status!r})"
            )
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise OrderCandidateValidationError(
                "quantity must be a positive integer"
            )
        if quantity <= 0:
            raise OrderCandidateValidationError("quantity must be > 0")
        if not symbol or not symbol.strip():
            raise OrderCandidateValidationError("symbol must be non-empty")

        normalized_limit: Decimal | None
        if order_type == "LIMIT":
            if limit_price is None:
                raise OrderCandidateValidationError(
                    "LIMIT order requires limit_price"
                )
            normalized_limit = Decimal(str(limit_price))
            if normalized_limit <= _ZERO:
                raise OrderCandidateValidationError(
                    "limit_price must be > 0"
                )
        else:  # MARKET
            normalized_limit = None  # ignore limit_price even if supplied

        amount = Decimal(str(estimated_amount))
        if amount < _ZERO:
            raise OrderCandidateValidationError(
                "estimated_amount must be >= 0"
            )

        return self.add(
            OrderCandidate(
                account_id=account_id,
                source=source,
                source_ref_id=source_ref_id,
                symbol=symbol.strip().upper(),
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=normalized_limit,
                estimated_amount=amount,
                status=status,
                expires_at=expires_at,
            )
        )

    # -------- read --------

    def get_by_id(self, candidate_id: int) -> OrderCandidate | None:
        return self.session.get(OrderCandidate, candidate_id)

    def list_by_account(
        self,
        account_id: int,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[OrderCandidate]:
        statement = select(OrderCandidate).where(
            OrderCandidate.account_id == account_id
        )
        if status is not None:
            statement = statement.where(OrderCandidate.status == status)
        statement = statement.order_by(OrderCandidate.id.desc()).limit(limit)
        return list(self.session.execute(statement).scalars().all())

    def list_by_status(
        self, status: str, *, limit: int = 100
    ) -> list[OrderCandidate]:
        if status not in VALID_STATUSES:
            raise OrderCandidateValidationError(
                f"status must be one of {sorted(VALID_STATUSES)}"
            )
        statement = (
            select(OrderCandidate)
            .where(OrderCandidate.status == status)
            .order_by(OrderCandidate.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_pending(self, *, limit: int = 200) -> list[OrderCandidate]:
        return self.list_by_status("PENDING_APPROVAL", limit=limit)

    def list_expired_pending(
        self, *, now: datetime | None = None, limit: int = 200
    ) -> list[OrderCandidate]:
        """Return PENDING_APPROVAL candidates whose ``expires_at`` <= now."""
        threshold = now or utc_now()
        statement = (
            select(OrderCandidate)
            .where(
                OrderCandidate.status == "PENDING_APPROVAL",
                OrderCandidate.expires_at.is_not(None),
                OrderCandidate.expires_at <= threshold,
            )
            .order_by(OrderCandidate.id.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    # -------- write -- state machine --------

    def update_status(
        self,
        candidate: OrderCandidate,
        *,
        new_status: str,
        rejection_reason: str | None = None,
        approver_user_id: int | None = None,
    ) -> OrderCandidate:
        """Transition ``candidate`` to ``new_status`` if allowed.

        Raises :class:`InvalidOrderCandidateTransition` for any edge that is
        not present in the documented state machine. Terminal states
        (RISK_REJECTED / EXECUTED_PAPER / REJECTED / EXPIRED) refuse every
        further transition.
        """
        if new_status not in VALID_STATUSES:
            raise OrderCandidateValidationError(
                f"status must be one of {sorted(VALID_STATUSES)} "
                f"(got {new_status!r})"
            )
        prev = candidate.status
        allowed = _ALLOWED_TRANSITIONS.get(prev, frozenset())
        if new_status not in allowed:
            raise InvalidOrderCandidateTransition(
                f"cannot transition OrderCandidate id={candidate.id} from "
                f"{prev!r} to {new_status!r}; allowed next: {sorted(allowed)}"
            )

        candidate.status = new_status
        if rejection_reason is not None:
            candidate.rejection_reason = rejection_reason
        if approver_user_id is not None:
            candidate.approver_user_id = approver_user_id
        candidate.updated_at = utc_now()
        self.session.flush()
        return candidate

    # -------- domain-specific helpers --------

    def attach_risk_result(
        self,
        candidate: OrderCandidate,
        *,
        result: dict,
    ) -> OrderCandidate:
        """Persist the PreTradeRiskEngine output on ``candidate``.

        The repository does NOT itself decide PENDING_APPROVAL vs
        RISK_REJECTED -- that is ApprovalService's job in Phase D. We just
        store the JSON document.
        """
        if not isinstance(result, dict):
            raise OrderCandidateValidationError(
                "risk_check_result must be a dict (JSON-serialisable)"
            )
        candidate.risk_check_result_json = result
        candidate.updated_at = utc_now()
        self.session.flush()
        return candidate

    def attach_virtual_order(
        self,
        candidate: OrderCandidate,
        *,
        virtual_order_id: int,
    ) -> OrderCandidate:
        """Link ``candidate`` to its paper-trading VirtualOrder row.

        Idempotent guard: if already linked to a different virtual_order_id,
        raises rather than silently overwriting (paper rerun semantics).
        """
        if (
            candidate.virtual_order_id is not None
            and candidate.virtual_order_id != virtual_order_id
        ):
            raise InvalidOrderCandidateTransition(
                f"OrderCandidate id={candidate.id} already linked to "
                f"virtual_order_id={candidate.virtual_order_id}; refusing to "
                f"overwrite with {virtual_order_id}"
            )
        candidate.virtual_order_id = virtual_order_id
        candidate.updated_at = utc_now()
        self.session.flush()
        return candidate

    def approve(
        self,
        candidate: OrderCandidate,
        *,
        approver_user_id: int,
    ) -> OrderCandidate:
        """PENDING_APPROVAL -> APPROVED with approver tracking."""
        return self.update_status(
            candidate,
            new_status="APPROVED",
            approver_user_id=approver_user_id,
        )

    def reject(
        self,
        candidate: OrderCandidate,
        *,
        approver_user_id: int,
        reason: str,
    ) -> OrderCandidate:
        """PENDING_APPROVAL -> REJECTED with reason + approver tracking."""
        return self.update_status(
            candidate,
            new_status="REJECTED",
            approver_user_id=approver_user_id,
            rejection_reason=reason[:256] if reason else None,
        )

    def expire(self, candidate: OrderCandidate) -> OrderCandidate:
        """PENDING_APPROVAL -> EXPIRED. System-driven (no approver)."""
        return self.update_status(
            candidate,
            new_status="EXPIRED",
            rejection_reason="ttl_expired",
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = [
    "InvalidOrderCandidateTransition",
    "OrderCandidateRepository",
    "OrderCandidateValidationError",
    "TERMINAL_STATUSES",
    "VALID_ORDER_TYPES",
    "VALID_SIDES",
    "VALID_SOURCES",
    "VALID_STATUSES",
]
