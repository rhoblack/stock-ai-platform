"""Collect market-cap top rankings, then populate Stock master and StockUniverse members.

A re-fetch for the same (rank_date, market) is treated as a snapshot replace so reordered
ranks do not violate the (rank_date, market, rank) unique constraint.

Boundary rules: collectors do not compute indicators, scores, recommendations, or send
notifications.
"""

from dataclasses import dataclass
from datetime import date

from app.data.interfaces import DataProviderInterface
from app.data.normalizers import normalize_market_cap_rankings
from app.data.repositories.market_cap_rankings import MarketCapRankingRepository
from app.data.repositories.stock_universes import (
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.data.repositories.stocks import StockRepository
from app.data.validators import DataQualityChecker, DataQualityIssue
from app.db.models import MarketCapRanking


@dataclass(frozen=True)
class MarketCapRankingCollectorResult:
    rank_date: date
    market: str
    universe_id: int
    saved_rankings: int
    new_stocks: int
    new_universe_members: int
    quality_issues: list[DataQualityIssue]


class MarketCapRankingCollector:
    DEFAULT_UNIVERSE_NAME = "MARKET_CAP_TOP_500"

    def __init__(
        self,
        client: DataProviderInterface,
        ranking_repository: MarketCapRankingRepository,
        stock_repository: StockRepository,
        universe_repository: StockUniverseRepository,
        member_repository: StockUniverseMemberRepository,
        checker: DataQualityChecker | None = None,
    ) -> None:
        self._client = client
        self._ranking_repository = ranking_repository
        self._stock_repository = stock_repository
        self._universe_repository = universe_repository
        self._member_repository = member_repository
        self._checker = checker or DataQualityChecker()

    def collect(
        self,
        *,
        market: str,
        ranking_date: date,
        limit: int,
        universe_name: str | None = None,
    ) -> MarketCapRankingCollectorResult:
        rows = self._client.fetch_market_cap_rankings(market, ranking_date, limit)
        normalized = normalize_market_cap_rankings(
            {"output": rows},
            ranking_date=ranking_date,
            market=market,
        )
        issues = self._checker.check_market_cap_rankings(normalized, expected_limit=limit)

        ranking_models = [
            MarketCapRanking(
                rank_date=item.rank_date,
                market=item.market,
                rank=item.rank,
                symbol=item.symbol,
                name=item.name,
                market_cap=item.market_cap,
                close_price=item.close_price,
                listed_shares=item.listed_shares,
                sector=item.sector,
                trading_value=item.trading_value,
                is_analysis_target=item.is_analysis_target,
            )
            for item in normalized
        ]
        saved_rankings = self._ranking_repository.replace_for_date_market(
            rank_date=ranking_date,
            market=market,
            rankings=ranking_models,
        )

        universe, _ = self._universe_repository.get_or_create(
            name=universe_name or self.DEFAULT_UNIVERSE_NAME,
        )

        new_stocks = 0
        new_universe_members = 0
        for item in normalized:
            _stock, stock_created = self._stock_repository.upsert(
                symbol=item.symbol,
                market=item.market,
                name=item.name,
                sector=item.sector,
            )
            if stock_created:
                new_stocks += 1

            _member, member_created = self._member_repository.add_if_missing(
                universe_id=universe.universe_id,
                symbol=item.symbol,
            )
            if member_created:
                new_universe_members += 1

        return MarketCapRankingCollectorResult(
            rank_date=ranking_date,
            market=market,
            universe_id=universe.universe_id,
            saved_rankings=saved_rankings,
            new_stocks=new_stocks,
            new_universe_members=new_universe_members,
            quality_issues=list(issues),
        )
