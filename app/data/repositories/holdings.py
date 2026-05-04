from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import Holding


class HoldingRepository(BaseRepository[Holding]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Holding)

    def get_active_by_symbol(self, symbol: str) -> Holding | None:
        statement = select(Holding).where(
            Holding.symbol == symbol,
            Holding.is_active.is_(True),
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_active(self) -> Sequence[Holding]:
        statement = select(Holding).where(Holding.is_active.is_(True))
        return self.session.execute(statement).scalars().all()

