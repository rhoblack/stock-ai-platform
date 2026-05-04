from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import JobRun


class JobRunRepository(BaseRepository[JobRun]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, JobRun)

    def list_by_status(self, status: str) -> Sequence[JobRun]:
        statement = select(JobRun).where(JobRun.status == status)
        return self.session.execute(statement).scalars().all()

