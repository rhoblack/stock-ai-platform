from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import StockUniverse, StockUniverseMember


class StockUniverseRepository(BaseRepository[StockUniverse]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockUniverse)

    def get_by_name(self, name: str) -> StockUniverse | None:
        statement = select(StockUniverse).where(StockUniverse.name == name)
        return self.session.execute(statement).scalar_one_or_none()

    def get_or_create(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> tuple[StockUniverse, bool]:
        existing = self.get_by_name(name)
        if existing is not None:
            return existing, False
        created = self.add(StockUniverse(name=name, description=description))
        return created, True


class StockUniverseMemberRepository(BaseRepository[StockUniverseMember]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockUniverseMember)

    def list_by_universe(self, universe_id: int) -> list[StockUniverseMember]:
        statement = (
            select(StockUniverseMember)
            .where(StockUniverseMember.universe_id == universe_id)
            .order_by(StockUniverseMember.symbol)
        )
        return list(self.session.execute(statement).scalars().all())

    def find_by_universe_symbol(
        self,
        *,
        universe_id: int,
        symbol: str,
    ) -> StockUniverseMember | None:
        statement = select(StockUniverseMember).where(
            StockUniverseMember.universe_id == universe_id,
            StockUniverseMember.symbol == symbol,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def add_if_missing(
        self,
        *,
        universe_id: int,
        symbol: str,
        reason: str | None = None,
    ) -> tuple[StockUniverseMember, bool]:
        existing = self.find_by_universe_symbol(universe_id=universe_id, symbol=symbol)
        if existing is not None:
            return existing, False
        created = self.add(
            StockUniverseMember(universe_id=universe_id, symbol=symbol, reason=reason),
        )
        return created, True
