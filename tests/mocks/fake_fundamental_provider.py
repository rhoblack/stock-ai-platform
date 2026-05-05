"""Deterministic FundamentalProviderInterface for v0.6 tests.

No DART/KIS/HTTP calls are made. The provider returns normalized sample
metrics only; it has no body/full_text/blob fields.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.data.dtos import FundamentalSnapshotDTO
from app.data.interfaces import FundamentalProviderInterface


_DETERMINISTIC_SAMPLE: tuple[FundamentalSnapshotDTO, ...] = (
    FundamentalSnapshotDTO(
        symbol="005930",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
        revenue=Decimal("258935500.0000"),
        operating_income=Decimal("32726000.0000"),
        net_income=Decimal("34451000.0000"),
        total_assets=Decimal("455905000.0000"),
        total_liabilities=Decimal("112334000.0000"),
        total_equity=Decimal("343571000.0000"),
        eps=Decimal("5200.0000"),
        bps=Decimal("56000.0000"),
        per=Decimal("12.3000"),
        pbr=Decimal("1.2000"),
        roe=Decimal("9.8000"),
        debt_ratio=Decimal("32.7000"),
        dividend_yield=Decimal("2.1000"),
        revenue_growth_yoy=Decimal("14.2000"),
        operating_income_growth_yoy=Decimal("30.5000"),
        source="FAKE_PROVIDER",
    ),
    FundamentalSnapshotDTO(
        symbol="000660",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
        revenue=Decimal("86120000.0000"),
        operating_income=Decimal("23500000.0000"),
        net_income=Decimal("19200000.0000"),
        total_assets=Decimal("142000000.0000"),
        total_liabilities=Decimal("51200000.0000"),
        total_equity=Decimal("90800000.0000"),
        eps=Decimal("24100.0000"),
        bps=Decimal("124000.0000"),
        per=Decimal("9.1000"),
        pbr=Decimal("1.7500"),
        roe=Decimal("21.3000"),
        debt_ratio=Decimal("56.4000"),
        dividend_yield=Decimal("1.4000"),
        revenue_growth_yoy=Decimal("44.0000"),
        operating_income_growth_yoy=Decimal("110.0000"),
        source="FAKE_PROVIDER",
    ),
    FundamentalSnapshotDTO(
        symbol="035420",
        snapshot_date=date(2026, 5, 1),
        fiscal_year=2025,
        fiscal_quarter=4,
        revenue=Decimal("10120000.0000"),
        operating_income=Decimal("1420000.0000"),
        net_income=Decimal("980000.0000"),
        total_assets=Decimal("36000000.0000"),
        total_liabilities=Decimal("11800000.0000"),
        total_equity=Decimal("24200000.0000"),
        eps=Decimal("6200.0000"),
        bps=Decimal("148000.0000"),
        per=Decimal("28.5000"),
        pbr=Decimal("1.1000"),
        roe=Decimal("7.9000"),
        debt_ratio=Decimal("48.8000"),
        dividend_yield=Decimal("0.6000"),
        revenue_growth_yoy=Decimal("8.5000"),
        operating_income_growth_yoy=Decimal("11.2000"),
        source="FAKE_PROVIDER",
    ),
)


class FakeFundamentalProvider(FundamentalProviderInterface):
    def __init__(self, items: tuple[FundamentalSnapshotDTO, ...] | None = None) -> None:
        self._items = items if items is not None else _DETERMINISTIC_SAMPLE
        self.calls: list[tuple[list[str], int, int | None]] = []

    def fetch_fundamentals(
        self,
        symbols: list[str],
        fiscal_year: int,
        fiscal_quarter: int | None = None,
    ) -> list[FundamentalSnapshotDTO]:
        self.calls.append((list(symbols), fiscal_year, fiscal_quarter))
        symbol_set = set(symbols)
        return [
            item
            for item in self._items
            if item.symbol in symbol_set
            and item.fiscal_year == fiscal_year
            and (fiscal_quarter is None or item.fiscal_quarter == fiscal_quarter)
        ]


__all__ = ["FakeFundamentalProvider"]
