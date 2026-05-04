from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import MarketCapRanking


class MarketCapRankingRepository(BaseRepository[MarketCapRanking]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MarketCapRanking)

    def list_by_date_market(self, rank_date: date, market: str) -> list[MarketCapRanking]:
        statement = (
            select(MarketCapRanking)
            .where(MarketCapRanking.rank_date == rank_date, MarketCapRanking.market == market)
            .order_by(MarketCapRanking.rank)
        )
        return list(self.session.execute(statement).scalars().all())

    def latest_rank_date(self, market: str | None = None) -> date | None:
        statement = select(MarketCapRanking.rank_date).order_by(
            MarketCapRanking.rank_date.desc(),
        )
        if market is not None:
            statement = statement.where(MarketCapRanking.market == market)
        return self.session.execute(statement.limit(1)).scalar_one_or_none()

    def replace_for_date_market(
        self,
        *,
        rank_date: date,
        market: str,
        rankings: list[MarketCapRanking],
    ) -> int:
        """Snapshot replace: drop existing rows for (rank_date, market), insert fresh rankings.

        Used by collectors so a re-fetched ranking snapshot can shuffle ranks without
        violating the (rank_date, market, rank) and (rank_date, market, symbol) constraints.
        """
        self.session.execute(
            delete(MarketCapRanking).where(
                MarketCapRanking.rank_date == rank_date,
                MarketCapRanking.market == market,
            )
        )
        self.session.flush()
        for ranking in rankings:
            self.session.add(ranking)
        self.session.flush()
        return len(rankings)
