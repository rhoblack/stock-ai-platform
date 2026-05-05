from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class KisCurrentPrice:
    symbol: str
    name: str | None
    market: str | None
    current_price: Decimal
    change_rate: Decimal | None = None
    volume: int | None = None
    trading_value: Decimal | None = None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class KisDailyPrice:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trading_value: Decimal | None = None


@dataclass(frozen=True)
class KisMarketCapRanking:
    rank_date: date
    market: str
    rank: int
    symbol: str
    name: str
    market_cap: Decimal | None = None
    close_price: Decimal | None = None
    listed_shares: int | None = None
    sector: str | None = None
    trading_value: Decimal | None = None
    is_analysis_target: bool = True


# ---------------------------------------------------------------------------
# v0.5 — News collection (Phase A)
#
# NewsItemDTO is the typed payload every NewsProviderInterface returns. It
# carries metadata only — original article body / paragraph / full text MUST
# NOT be added to this dataclass. The integration test in
# ``tests/integration/test_news_collector.py`` enforces this guard.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NewsItemDTO:
    title: str
    url: str
    provider: str
    published_at: datetime
    symbol: str | None = None
    source: str | None = None
    category: str | None = None
    sentiment_label: str | None = None
    summary: str | None = None

