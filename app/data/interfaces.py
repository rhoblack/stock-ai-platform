from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any


class DataProviderInterface(ABC):
    """Read-only external data provider contract for v0.1 collection flows."""

    @abstractmethod
    def fetch_current_price(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_market_cap_rankings(
        self,
        market: str,
        ranking_date: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_news(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def fetch_disclosures(
        self,
        symbols: list[str],
        target_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

