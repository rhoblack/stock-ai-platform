"""Pull daily price rows from a DataProviderInterface and persist them via repository upsert.

Boundary rules: collectors do not compute indicators, scores, recommendations, or send
notifications. They only translate raw vendor responses into normalized DTOs and write
them through the repository layer.
"""

from dataclasses import dataclass
from datetime import date

from app.data.interfaces import DataProviderInterface
from app.data.normalizers import normalize_daily_prices
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.validators import DataQualityChecker, DataQualityIssue


@dataclass(frozen=True)
class DailyPriceCollectorResult:
    symbol: str
    saved_count: int
    quality_issues: list[DataQualityIssue]


class DailyPriceCollector:
    def __init__(
        self,
        client: DataProviderInterface,
        repository: DailyPriceRepository,
        checker: DataQualityChecker | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._checker = checker or DataQualityChecker()

    def collect(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> DailyPriceCollectorResult:
        rows = self._client.fetch_daily_prices(symbol, start_date, end_date)
        normalized = normalize_daily_prices({"output2": rows}, symbol=symbol)
        issues = self._checker.check_daily_prices(normalized)

        for price in normalized:
            self._repository.upsert(
                symbol=price.symbol,
                price_date=price.date,
                open_price=price.open,
                high_price=price.high,
                low_price=price.low,
                close_price=price.close,
                volume=price.volume,
                trading_value=price.trading_value,
            )

        return DailyPriceCollectorResult(
            symbol=symbol,
            saved_count=len(normalized),
            quality_issues=list(issues),
        )
