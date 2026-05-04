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

