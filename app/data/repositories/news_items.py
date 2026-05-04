from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import NewsItem


class NewsItemRepository(BaseRepository[NewsItem]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, NewsItem)

    def list_by_time_range(self, start_time: datetime, end_time: datetime) -> list[NewsItem]:
        statement = (
            select(NewsItem)
            .where(NewsItem.published_at >= start_time, NewsItem.published_at <= end_time)
            .order_by(NewsItem.published_at.desc())
        )
        return list(self.session.execute(statement).scalars().all())

