from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.data.dtos import KisDailyPrice, KisMarketCapRanking


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    message: str
    symbol: str | None = None
    target_date: date | None = None


class DataQualityChecker:
    def check_daily_prices(self, prices: list[KisDailyPrice]) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        seen: set[tuple[str, date]] = set()

        for price in prices:
            key = (price.symbol, price.date)
            if key in seen:
                issues.append(
                    DataQualityIssue(
                        code="DUPLICATE_DAILY_PRICE",
                        message="Duplicate daily price row.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )
            seen.add(key)

            if price.open <= 0 or price.high <= 0 or price.low <= 0 or price.close <= 0:
                issues.append(
                    DataQualityIssue(
                        code="INVALID_PRICE",
                        message="OHLC prices must be positive.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )

            if price.high < max(price.open, price.close, price.low):
                issues.append(
                    DataQualityIssue(
                        code="INVALID_HIGH_LOW_RANGE",
                        message="High price is lower than one of OHLC values.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )

            if price.low > min(price.open, price.close, price.high):
                issues.append(
                    DataQualityIssue(
                        code="INVALID_HIGH_LOW_RANGE",
                        message="Low price is higher than one of OHLC values.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )

            if price.volume < 0:
                issues.append(
                    DataQualityIssue(
                        code="INVALID_VOLUME",
                        message="Volume cannot be negative.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )

            if price.volume == 0:
                issues.append(
                    DataQualityIssue(
                        code="ZERO_VOLUME",
                        message="Volume is zero.",
                        symbol=price.symbol,
                        target_date=price.date,
                    ),
                )

        return issues

    def check_market_cap_rankings(
        self,
        rankings: list[KisMarketCapRanking],
        expected_limit: int | None = None,
    ) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        seen_symbols: set[str] = set()
        seen_ranks: set[int] = set()

        if expected_limit is not None and len(rankings) < expected_limit:
            issues.append(
                DataQualityIssue(
                    code="RANKING_COUNT_SHORT",
                    message="Market cap ranking count is below expected limit.",
                ),
            )

        for ranking in rankings:
            if ranking.symbol in seen_symbols:
                issues.append(
                    DataQualityIssue(
                        code="DUPLICATE_RANKING_SYMBOL",
                        message="Duplicate symbol in market cap rankings.",
                        symbol=ranking.symbol,
                        target_date=ranking.rank_date,
                    ),
                )
            seen_symbols.add(ranking.symbol)

            if ranking.rank in seen_ranks:
                issues.append(
                    DataQualityIssue(
                        code="DUPLICATE_RANK",
                        message="Duplicate rank in market cap rankings.",
                        symbol=ranking.symbol,
                        target_date=ranking.rank_date,
                    ),
                )
            seen_ranks.add(ranking.rank)

            if ranking.rank <= 0:
                issues.append(
                    DataQualityIssue(
                        code="INVALID_RANK",
                        message="Rank must be positive.",
                        symbol=ranking.symbol,
                        target_date=ranking.rank_date,
                    ),
                )

            if ranking.market_cap is not None and ranking.market_cap < Decimal("0"):
                issues.append(
                    DataQualityIssue(
                        code="INVALID_MARKET_CAP",
                        message="Market cap cannot be negative.",
                        symbol=ranking.symbol,
                        target_date=ranking.rank_date,
                    ),
                )

        return issues

