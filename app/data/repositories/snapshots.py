from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import DataSnapshot


class DataSnapshotRepository(BaseRepository[DataSnapshot]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DataSnapshot)

    def list_by_symbol(self, symbol: str) -> list[DataSnapshot]:
        statement = (
            select(DataSnapshot)
            .where(DataSnapshot.symbol == symbol)
            .order_by(DataSnapshot.snapshot_time.desc())
        )
        return list(self.session.execute(statement).scalars().all())

