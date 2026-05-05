"""Deterministic EarningsProviderInterface for v0.6 Phase B tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.data.dtos import EarningsEventDTO
from app.data.interfaces import EarningsProviderInterface


_DETERMINISTIC_SAMPLE: tuple[EarningsEventDTO, ...] = (
    EarningsEventDTO(
        symbol="005930",
        company_name="Samsung Electronics",
        event_date=date(2026, 4, 30),
        fiscal_year=2026,
        fiscal_quarter=1,
        event_type="FINAL",
        operating_income_actual=Decimal("7100000.0000"),
        operating_income_consensus=Decimal("6500000.0000"),
        surprise_type="BEAT",
        surprise_pct=Decimal("9.2308"),
        source="FAKE_PROVIDER",
    ),
    EarningsEventDTO(
        symbol="000660",
        company_name="SK Hynix",
        event_date=date(2026, 4, 25),
        fiscal_year=2026,
        fiscal_quarter=1,
        event_type="FINAL",
        operating_income_actual=Decimal("5000000.0000"),
        operating_income_consensus=Decimal("4900000.0000"),
        surprise_type="MEET",
        surprise_pct=Decimal("2.0408"),
        source="FAKE_PROVIDER",
    ),
    EarningsEventDTO(
        symbol="035420",
        company_name="NAVER",
        event_date=date(2026, 4, 20),
        fiscal_year=2026,
        fiscal_quarter=1,
        event_type="FINAL",
        operating_income_actual=Decimal("350000.0000"),
        operating_income_consensus=Decimal("400000.0000"),
        surprise_type="MISS",
        surprise_pct=Decimal("-12.5000"),
        source="FAKE_PROVIDER",
    ),
    EarningsEventDTO(
        symbol="005380",
        company_name="Hyundai Motor",
        event_date=date(2026, 5, 20),
        fiscal_year=2026,
        fiscal_quarter=2,
        event_type="CONSENSUS",
        surprise_type="UNKNOWN",
        source="FAKE_PROVIDER",
        memo="upcoming sample",
    ),
)


class FakeEarningsProvider(EarningsProviderInterface):
    def __init__(self, items: tuple[EarningsEventDTO, ...] | None = None) -> None:
        self._items = items if items is not None else _DETERMINISTIC_SAMPLE
        self.calls: list[tuple[list[str], date | None, date | None, int]] = []

    def fetch_earnings_events(
        self,
        symbols: list[str],
        since: date | None = None,
        until: date | None = None,
        limit: int = 100,
    ) -> list[EarningsEventDTO]:
        self.calls.append((list(symbols), since, until, limit))
        symbol_set = set(symbols)
        results: list[EarningsEventDTO] = []
        for item in self._items:
            if item.symbol not in symbol_set:
                continue
            if since is not None and item.event_date < since:
                continue
            if until is not None and item.event_date > until:
                continue
            results.append(item)
            if len(results) >= limit:
                break
        return results


__all__ = ["FakeEarningsProvider"]
