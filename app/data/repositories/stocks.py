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

    def upsert(
        self,
        *,
        symbol: str,
        market: str,
        name: str,
        sector: str | None = None,
    ) -> tuple[Stock, bool]:
        existing = self.get_by_symbol(symbol)
        if existing is None:
            created = self.add(Stock(symbol=symbol, market=market, name=name, sector=sector))
            return created, True

        existing.market = market
        existing.name = name
        if sector is not None:
            existing.sector = sector
        self.session.flush()
        return existing, False

