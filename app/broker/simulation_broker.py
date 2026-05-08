"""SimulationBroker -- v0.14 Phase B in-process paper trading core.

The simulator is the FIRST concrete implementation backing the long-standing
``BrokerInterface`` placeholder. It is intentionally MINIMAL in Phase B:

  * ``submit_order()`` writes a CREATED-state ``VirtualOrder`` row when the
    paper-trading switch is on and refuses cleanly when it is off.
  * ``cancel_order()`` moves CREATED / SUBMITTED rows to CANCELED. Terminal
    or fill-progressed states (FILLED / PARTIALLY_FILLED / CANCELED /
    REJECTED) are rejected.
  * ``execute_pending_orders()`` is a Phase C / D responsibility -- here it
    is a documented skeleton that raises ``NotImplementedError``.

Hard guarantees verified by the test suite
------------------------------------------

* No KIS / DART / RSS / external HTTP client is imported here.
* No ``requests`` / ``httpx`` / ``urllib`` import is performed at module load
  or at runtime.
* The default ``Settings.paper_trading_enabled`` is ``False``; the broker
  refuses to write any VirtualOrder until an operator explicitly opts in.
* Real-order / real-broker / autotrade / KIS order-placement code is OUT OF
  SCOPE for this entire module.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import (
    CANCELABLE_STATUSES,
    TERMINAL_STATUSES,
    VALID_ORDER_TYPES,
    VALID_SIDES,
    VirtualOrderRepository,
)
from app.db.models import VirtualAccount, VirtualOrder


class PaperTradingDisabledError(RuntimeError):
    """Raised when SimulationBroker.submit_order() is called while the
    PAPER_TRADING_ENABLED switch (global or per-account) is off."""


class SimulationBrokerError(RuntimeError):
    """Generic SimulationBroker validation / state-machine error."""


@dataclass(frozen=True)
class SubmitResult:
    """Return value of :meth:`SimulationBroker.submit_order`.

    ``order`` is the persisted VirtualOrder. ``deduplicated`` is True when an
    existing order with the same ``(account_id, idempotency_key)`` was found
    and returned unchanged -- the broker never writes a second row for the
    same idempotency key.
    """

    order: VirtualOrder
    deduplicated: bool


class SimulationBroker:
    """Paper-trading order book backed by ``virtual_orders``.

    The broker is stateless; the session is passed per call. This mirrors
    the existing repository pattern in this project (see
    ``app.data.repositories.base``). Callers are expected to call
    ``session.commit()`` themselves.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    # -------- public surface --------

    def submit_order(
        self,
        session: Session,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Decimal | int | float | str | None = None,
        idempotency_key: str | None = None,
        note: str | None = None,
    ) -> SubmitResult:
        """Validate and persist a new VirtualOrder in CREATED state.

        Raises :class:`PaperTradingDisabledError` when the global setting or
        the account's per-row flag is False. Raises :class:`SimulationBrokerError`
        on validation failure (unknown side / order_type / non-positive
        quantity / unknown account / LIMIT-without-price etc.).

        On duplicate ``idempotency_key`` for the same account, the existing
        order row is returned with ``deduplicated=True`` and NO new row is
        written.
        """
        if not self._settings.paper_trading_enabled:
            raise PaperTradingDisabledError(
                "PAPER_TRADING_ENABLED is False; SimulationBroker.submit_order "
                "refuses to write any VirtualOrder. Set PAPER_TRADING_ENABLED=true "
                "in operator-private .env to opt in."
            )

        accounts = VirtualAccountRepository(session)
        account = accounts.get_by_id(account_id)
        if account is None:
            raise SimulationBrokerError(
                f"VirtualAccount id={account_id} not found"
            )
        if not account.paper_trading_enabled:
            raise PaperTradingDisabledError(
                f"VirtualAccount id={account_id} has paper_trading_enabled=False"
            )

        if side not in VALID_SIDES:
            raise SimulationBrokerError(
                f"side must be one of {sorted(VALID_SIDES)} (got {side!r})"
            )
        if order_type not in VALID_ORDER_TYPES:
            raise SimulationBrokerError(
                f"order_type must be one of {sorted(VALID_ORDER_TYPES)} "
                f"(got {order_type!r})"
            )
        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise SimulationBrokerError("quantity must be a positive integer")
        if quantity <= 0:
            raise SimulationBrokerError("quantity must be > 0")
        if not symbol or not symbol.strip():
            raise SimulationBrokerError("symbol must be non-empty")

        normalized_limit: Decimal | None
        if order_type == "LIMIT":
            if limit_price is None:
                raise SimulationBrokerError("LIMIT order requires limit_price")
            normalized_limit = Decimal(str(limit_price))
            if normalized_limit <= 0:
                raise SimulationBrokerError("limit_price must be > 0")
        else:
            if limit_price is not None:
                raise SimulationBrokerError(
                    "MARKET order must not have limit_price"
                )
            normalized_limit = None

        orders = VirtualOrderRepository(session)
        if idempotency_key is not None:
            existing = orders.get_by_idempotency_key(
                account_id=account_id, idempotency_key=idempotency_key
            )
            if existing is not None:
                return SubmitResult(order=existing, deduplicated=True)

        order = orders.create(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=normalized_limit,
            idempotency_key=idempotency_key,
            note=note,
            status="CREATED",
        )
        return SubmitResult(order=order, deduplicated=False)

    def cancel_order(
        self,
        session: Session,
        *,
        order_id: int,
        reason: str | None = None,
    ) -> VirtualOrder:
        """Cancel a non-terminal VirtualOrder.

        Allowed source states: CREATED, SUBMITTED. Terminal /
        fill-progressed states (FILLED / PARTIALLY_FILLED / CANCELED /
        REJECTED) raise :class:`SimulationBrokerError`.

        Cancellation does NOT require ``paper_trading_enabled``: an operator
        who flips the master switch off must still be able to cancel
        previously-created orders cleanly.
        """
        orders = VirtualOrderRepository(session)
        order = orders.get_by_id(order_id)
        if order is None:
            raise SimulationBrokerError(f"VirtualOrder id={order_id} not found")
        if order.status not in CANCELABLE_STATUSES:
            raise SimulationBrokerError(
                f"VirtualOrder id={order_id} is in status={order.status!r}; "
                f"only {sorted(CANCELABLE_STATUSES)} are cancelable "
                f"(terminal: {sorted(TERMINAL_STATUSES)})"
            )
        return orders.cancel(order, reason=reason)

    def get_order(self, session: Session, order_id: int) -> VirtualOrder | None:
        return VirtualOrderRepository(session).get_by_id(order_id)

    def list_orders(
        self,
        session: Session,
        *,
        account_id: int,
        status: str | None = None,
        limit: int = 100,
    ) -> list[VirtualOrder]:
        return VirtualOrderRepository(session).list_by_account(
            account_id, status=status, limit=limit
        )

    # -------- Phase C / D placeholder --------

    def execute_pending_orders(self, *args: Any, **kwargs: Any) -> None:
        """Placeholder for Phase C/D. NEVER fills orders in Phase B.

        Phase C will implement matching against ``daily_prices``. Until then
        callers must not rely on this method -- it raises a clear error so
        accidental invocation in tests / scripts surfaces immediately.
        """
        raise NotImplementedError(
            "execute_pending_orders is a Phase C responsibility -- "
            "VirtualPosition / VirtualFill / cost model are not yet wired."
        )
