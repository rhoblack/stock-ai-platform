from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import DecisionLog


class DecisionLogRepository(BaseRepository[DecisionLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DecisionLog)

    def list_by_symbol(self, symbol: str) -> list[DecisionLog]:
        statement = (
            select(DecisionLog)
            .where(DecisionLog.symbol == symbol)
            .order_by(DecisionLog.created_at.desc())
        )
        return list(self.session.execute(statement).scalars().all())

