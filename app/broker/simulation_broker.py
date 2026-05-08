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
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_order import (
    CANCELABLE_STATUSES,
    TERMINAL_STATUSES,
    VALID_ORDER_TYPES,
    VALID_SIDES,
    VirtualOrderRepository,
)
from app.data.repositories.virtual_position import (
    InsufficientPositionError,
)
from app.db.models import VirtualAccount, VirtualFill, VirtualOrder
from app.paper.pnl_tracker import InsufficientCashError, PnLTracker


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

    # -------- v0.14 Phase C: matching engine --------

    def execute_pending_orders(
        self,
        session: Session,
        *,
        as_of_date: date,
        account_id: int | None = None,
        pnl_tracker: PnLTracker | None = None,
        price_lookback_days: int = 0,
    ) -> "ExecutePendingResult":
        """Match CREATED / SUBMITTED orders against ``daily_prices``.

        Pricing rule
        ------------
        For each pending order the engine looks up
        ``daily_prices.close`` for ``(symbol, as_of_date)`` (or, when
        ``price_lookback_days > 0``, the most recent close on or before
        ``as_of_date`` within that lookback window). When no price is
        available the order is left untouched so the next run can retry.

        Matching rule
        -------------
        * **MARKET**: always fills at ``close_price`` if the symbol has a
          price for the day.
        * **LIMIT BUY**: fills at ``close_price`` only if
          ``close_price <= limit_price``; otherwise the order is left in
          its current state (no status change).
        * **LIMIT SELL**: fills at ``close_price`` only if
          ``close_price >= limit_price``; otherwise the order is left in
          its current state.

        Failure rule
        ------------
        Cash / position constraints surface as a state transition:

        * ``InsufficientCashError`` -> order REJECTED with reason.
        * ``InsufficientPositionError`` -> order REJECTED with reason.

        The engine never raises -- it returns a structured summary so the
        caller can persist a job_run row and react.

        Side-effects
        ------------
        On a successful fill the engine mutates: ``cash_balance``,
        ``virtual_positions`` row, writes a ``virtual_fills`` row, and
        flips the order status to ``FILLED``. ``ExecutePendingResult``
        accumulates the (order, fill) pairs.

        ``PAPER_TRADING_ENABLED`` is NOT required for execute_pending_orders
        because the orders themselves were already created under that gate.
        Re-executing terminal orders is forbidden -- the SQL filter
        excludes them.
        """
        tracker = pnl_tracker or PnLTracker()
        orders_repo = VirtualOrderRepository(session)
        prices_repo = DailyPriceRepository(session)

        candidates: list[VirtualOrder] = []
        for status in ("CREATED", "SUBMITTED"):
            if account_id is None:
                candidates.extend(self._list_pending_global(session, status))
            else:
                candidates.extend(
                    orders_repo.list_by_account(
                        account_id, status=status, limit=10_000
                    )
                )
        # Stable order: account, then id ascending (FIFO within account).
        candidates.sort(key=lambda o: (o.account_id, o.id))

        result = ExecutePendingResult()

        for order in candidates:
            # Defensive recheck -- terminal states must NEVER re-execute
            # even if the loader hands us one. Indexing the SQL filter does
            # the heavy lifting; this guards against caller-supplied
            # candidate lists in tests.
            if order.status in TERMINAL_STATUSES:
                result.skipped_terminal += 1
                continue

            bar = self._lookup_close_price(
                prices_repo,
                symbol=order.symbol,
                as_of_date=as_of_date,
                price_lookback_days=price_lookback_days,
            )
            if bar is None:
                result.skipped_no_price += 1
                continue

            close_price = Decimal(bar.close)

            # LIMIT crossing check.
            if order.order_type == "LIMIT":
                limit = Decimal(order.limit_price)
                if order.side == "BUY" and close_price > limit:
                    result.skipped_limit_unmet += 1
                    continue
                if order.side == "SELL" and close_price < limit:
                    result.skipped_limit_unmet += 1
                    continue

            try:
                fill_result = tracker.apply_fill(
                    session,
                    order_id=order.id,
                    account_id=order.account_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    fill_price=close_price,
                )
            except InsufficientCashError as exc:
                orders_repo.update_status(
                    order, new_status="REJECTED", reason=str(exc)[:256]
                )
                result.rejected.append(order)
                continue
            except InsufficientPositionError as exc:
                orders_repo.update_status(
                    order, new_status="REJECTED", reason=str(exc)[:256]
                )
                result.rejected.append(order)
                continue

            orders_repo.update_status(order, new_status="FILLED")
            result.filled.append((order, fill_result.fill))

        return result

    @staticmethod
    def _list_pending_global(
        session: Session, status: str
    ) -> list[VirtualOrder]:
        from sqlalchemy import select

        statement = (
            select(VirtualOrder)
            .where(VirtualOrder.status == status)
            .order_by(VirtualOrder.id.asc())
        )
        return list(session.execute(statement).scalars().all())

    @staticmethod
    def _lookup_close_price(
        repo: DailyPriceRepository,
        *,
        symbol: str,
        as_of_date: date,
        price_lookback_days: int,
    ):
        if price_lookback_days <= 0:
            return repo.get_by_symbol_date(symbol, as_of_date)
        return repo.get_latest_on_or_before(
            symbol=symbol,
            target_date=as_of_date,
            lookback_days=price_lookback_days,
        )


@dataclass
class ExecutePendingResult:
    """Structured summary of one ``execute_pending_orders`` invocation."""

    filled: list[tuple[VirtualOrder, VirtualFill]]
    rejected: list[VirtualOrder]
    skipped_no_price: int
    skipped_limit_unmet: int
    skipped_terminal: int

    def __init__(self) -> None:
        self.filled = []
        self.rejected = []
        self.skipped_no_price = 0
        self.skipped_limit_unmet = 0
        self.skipped_terminal = 0

    @property
    def filled_count(self) -> int:
        return len(self.filled)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)
