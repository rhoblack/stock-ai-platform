from abc import ABC, abstractmethod
from datetime import date
from typing import Any


class BrokerInterface(ABC):
    """Broker boundary for future market data and trading integrations.

    v0.1 must not provide any implementation that executes real orders.
    """

    @abstractmethod
    def get_current_price(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_orderbook(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_balance(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Future-only order boundary. No v0.1 implementation may execute this."""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Future-only order boundary. No v0.1 implementation may execute this."""
        raise NotImplementedError

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

