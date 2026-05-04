from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import MarketRegime


class MarketRegimeRepository(BaseRepository[MarketRegime]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MarketRegime)

    def get_by_date_market(self, regime_date: date, market: str) -> MarketRegime | None:
        statement = select(MarketRegime).where(
            MarketRegime.date == regime_date,
            MarketRegime.market == market,
        )
        return self.session.execute(statement).scalar_one_or_none()

