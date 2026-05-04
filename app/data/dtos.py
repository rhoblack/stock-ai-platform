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

