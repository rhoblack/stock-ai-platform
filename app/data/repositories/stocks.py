from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import Stock


class StockRepository(BaseRepository[Stock]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Stock)

    def get_by_symbol(self, symbol: str) -> Stock | None:
        statement = select(Stock).where(Stock.symbol == symbol)
        return self.session.execute(statement).scalar_one_or_none()

