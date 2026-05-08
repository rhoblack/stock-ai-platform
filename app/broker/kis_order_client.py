"""KIS Order Client interface and fake transport — v0.16 Phase B.

Hard guarantees verified by the test suite
------------------------------------------
* No httpx / requests / urllib import is performed at module load or at runtime.
* No app.data.collectors.kis_client import.
* Sensitive fields (api_key, api_secret, account_no) NEVER appear in
  repr / str / log output — ``__repr__`` is explicitly defined to mask them.
* No raw KIS response fields are exposed.
* FakeKisOrderTransport performs zero real HTTP calls.

Phase D will introduce KisHttpOrderTransport that actually calls the KIS
Open API. Until then FakeKisOrderTransport is the only concrete transport.
"""

from __future__ import annotations

import abc
from typing import Any


# ---------------------------------------------------------------------------
# Request / Result dataclasses
# ---------------------------------------------------------------------------


class KisOrderRequest:
    """Minimal order-placement request payload.

    account_no is masked in all repr / str / as_dict output.
    Phase D will extend fields as the real KIS API signature becomes clear.
    """

    __slots__ = ("symbol", "side", "order_type", "quantity", "price", "account_no")

    def __init__(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: int,
        account_no: str,
    ) -> None:
        if side not in ("BUY", "SELL"):
            raise ValueError(f"side must be BUY or SELL (got {side!r})")
        if order_type not in ("LIMIT", "MARKET"):
            raise ValueError(f"order_type must be LIMIT or MARKET (got {order_type!r})")
        if quantity <= 0:
            raise ValueError(f"quantity must be > 0 (got {quantity!r})")
        if price < 0:
            raise ValueError(f"price must be >= 0 (got {price!r})")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "order_type", order_type)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "account_no", account_no)

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError("KisOrderRequest is immutable")

    def __repr__(self) -> str:
        masked = _mask_account_no(self.account_no)
        return (
            f"KisOrderRequest(symbol={self.symbol!r}, side={self.side!r}, "
            f"order_type={self.order_type!r}, quantity={self.quantity!r}, "
            f"price={self.price!r}, account_no={masked!r})"
        )

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe dict — account_no is masked."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "account_no": _mask_account_no(self.account_no),
        }


class KisOrderResult:
    """Result of a place_order call."""

    __slots__ = ("success", "order_no", "message")

    def __init__(self, *, success: bool, order_no: str, message: str) -> None:
        object.__setattr__(self, "success", success)
        object.__setattr__(self, "order_no", order_no)
        object.__setattr__(self, "message", message)

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError("KisOrderResult is immutable")

    def __repr__(self) -> str:
        return (
            f"KisOrderResult(success={self.success!r}, "
            f"order_no={self.order_no!r}, message={self.message!r})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_no": self.order_no,
            "message": self.message,
        }


class KisFillStatusResult:
    """Result of a query_fill_status call."""

    VALID_STATUSES = frozenset(
        {"PENDING", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED"}
    )

    __slots__ = (
        "success",
        "order_no",
        "filled_quantity",
        "remaining_quantity",
        "status",
        "message",
    )

    def __init__(
        self,
        *,
        success: bool,
        order_no: str,
        filled_quantity: int,
        remaining_quantity: int,
        status: str,
        message: str,
    ) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(self.VALID_STATUSES)} (got {status!r})")
        object.__setattr__(self, "success", success)
        object.__setattr__(self, "order_no", order_no)
        object.__setattr__(self, "filled_quantity", filled_quantity)
        object.__setattr__(self, "remaining_quantity", remaining_quantity)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "message", message)

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError("KisFillStatusResult is immutable")

    def __repr__(self) -> str:
        return (
            f"KisFillStatusResult(success={self.success!r}, order_no={self.order_no!r}, "
            f"filled_quantity={self.filled_quantity!r}, remaining_quantity={self.remaining_quantity!r}, "
            f"status={self.status!r}, message={self.message!r})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_no": self.order_no,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "status": self.status,
            "message": self.message,
        }


class KisCancelResult:
    """Result of a cancel_order call."""

    __slots__ = ("success", "order_no", "message")

    def __init__(self, *, success: bool, order_no: str, message: str) -> None:
        object.__setattr__(self, "success", success)
        object.__setattr__(self, "order_no", order_no)
        object.__setattr__(self, "message", message)

    def __setattr__(self, name: str, value: object) -> None:  # type: ignore[override]
        raise AttributeError("KisCancelResult is immutable")

    def __repr__(self) -> str:
        return (
            f"KisCancelResult(success={self.success!r}, "
            f"order_no={self.order_no!r}, message={self.message!r})"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_no": self.order_no,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# ABC Interface
# ---------------------------------------------------------------------------


class KisOrderClientInterface(abc.ABC):
    """Abstract interface for KIS order placement.

    Concrete implementations:
      * FakeKisOrderTransport — tests / dry-run (zero real HTTP calls).
      * KisHttpOrderTransport — Phase D, real HTTP calls via KIS Open API.
    """

    @abc.abstractmethod
    def place_order(self, request: KisOrderRequest) -> KisOrderResult:
        """Submit a new order to KIS. Returns KisOrderResult."""

    @abc.abstractmethod
    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        """Query fill status for an existing order."""

    @abc.abstractmethod
    def cancel_order(self, order_no: str) -> KisCancelResult:
        """Request cancellation of an existing order."""


# ---------------------------------------------------------------------------
# Fake Transport (zero real HTTP calls)
# ---------------------------------------------------------------------------

_fake_order_counter: list[int] = [0]


def _next_fake_order_no() -> str:
    _fake_order_counter[0] += 1
    return f"FAKE-{_fake_order_counter[0]:06d}"


class FakeKisOrderTransport(KisOrderClientInterface):
    """Deterministic fake implementation — zero real HTTP calls.

    Used in tests, dry-run mode, and local development.

    * place_order: always succeeds, returns a deterministic fake order_no.
    * query_fill_status: always returns FILLED with filled_quantity=0,
      remaining_quantity=0 (representing an instantly-filled fake order).
    * cancel_order: always succeeds.
    """

    def place_order(self, request: KisOrderRequest) -> KisOrderResult:
        order_no = _next_fake_order_no()
        return KisOrderResult(
            success=True,
            order_no=order_no,
            message="fake order accepted",
        )

    def query_fill_status(self, order_no: str) -> KisFillStatusResult:
        return KisFillStatusResult(
            success=True,
            order_no=order_no,
            filled_quantity=0,
            remaining_quantity=0,
            status="FILLED",
            message="fake fill complete",
        )

    def cancel_order(self, order_no: str) -> KisCancelResult:
        return KisCancelResult(
            success=True,
            order_no=order_no,
            message="fake cancel accepted",
        )


# ---------------------------------------------------------------------------
# Masking helpers
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"api_key", "api_secret", "account_no", "authorization", "token", "access_token"}
)


def _mask_account_no(account_no: str) -> str:
    if len(account_no) >= 4:
        return "****" + account_no[-4:]
    return "****"


def mask_sensitive_order_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with known sensitive keys masked.

    Sensitive keys: api_key, api_secret, account_no, authorization, token,
    access_token. Key matching is case-insensitive.
    """
    result: dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in _SENSITIVE_KEYS:
            result[k] = "***MASKED***"
        else:
            result[k] = v
    return result
