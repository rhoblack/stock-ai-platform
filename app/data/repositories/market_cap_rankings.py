from datetime import date

from sqlalchemy import select
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

