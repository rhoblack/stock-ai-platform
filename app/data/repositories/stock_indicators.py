from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import StockIndicator


class StockIndicatorRepository(BaseRepository[StockIndicator]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockIndicator)

    def get_by_symbol_date(self, symbol: str, indicator_date: date) -> StockIndicator | None:
        statement = select(StockIndicator).where(
            StockIndicator.symbol == symbol,
            StockIndicator.date == indicator_date,
        )
        return self.session.execute(statement).scalar_one_or_none()

