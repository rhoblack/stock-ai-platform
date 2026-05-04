from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import NotificationLog


class NotificationLogRepository(BaseRepository[NotificationLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, NotificationLog)

    def list_by_status(self, status: str) -> list[NotificationLog]:
        statement = select(NotificationLog).where(NotificationLog.status == status)
        return list(self.session.execute(statement).scalars().all())

