"""In-memory fake DataProviderInterface for collector tests.

Tests must never reach the real KIS service. This fake records calls and replays
canned raw rows shaped like KIS responses (already extracted from output/output2).
"""

from datetime import date, datetime
from typing import Any

from app.data.interfaces import DataProviderInterface


class FakeKisDataProvider(DataProviderInterface):
    def __init__(
        self,
        *,
        daily_price_responses: dict[str, list[dict[str, Any]]] | None = None,
        market_cap_responses: dict[tuple[str, date], list[dict[str, Any]]] | None = None,
        current_price_responses: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._daily_price_responses = daily_price_responses or {}
        self._market_cap_responses = market_cap_responses or {}
        self._current_price_responses = current_price_responses or {}
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def fetch_current_price(self, symbol: str) -> dict[str, Any]:
        self.calls.append(("fetch_current_price", (symbol,)))
        if symbol not in self._current_price_responses:
            raise KeyError(f"No fake current price set for symbol={symbol}")
        return self._current_price_responses[symbol]

    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        self.calls.append(("fetch_daily_prices", (symbol, start_date, end_date)))
        return list(self._daily_price_responses.get(symbol, []))

    def fetch_market_cap_rankings(
        self,
        market: str,
        ranking_date: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(("fetch_market_cap_rankings", (market, ranking_date, limit)))
        rows = self._market_cap_responses.get((market, ranking_date), [])
        return list(rows[:limit])

    def fetch_news(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("News collection is outside Phase 3-3.")

    def fetch_disclosures(
        self,
        symbols: list[str],
        target_date: date,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Disclosure collection is outside Phase 3-3.")
