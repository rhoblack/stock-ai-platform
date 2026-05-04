from abc import ABC, abstractmethod
from typing import Any


class StrategyInterface(ABC):
    """Future strategy contract.

    v0.1 may define this boundary, but strategy execution and trading flows stay
    disabled until later project phases.
    """

    @abstractmethod
    def generate_signal(
        self,
        market_context: dict[str, Any],
        stock_context: dict[str, Any],
        portfolio_context: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def risk_rules(self) -> list[dict[str, Any]]:
        raise NotImplementedError

