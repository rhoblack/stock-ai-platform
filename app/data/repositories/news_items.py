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

    # -- v0.5 Phase A additions ----------------------------------------------

    def get_by_url(self, url: str) -> NewsItem | None:
        """Return the first row whose ``url`` exactly matches.

        v0.5 Phase A 의 NewsCollector 는 url 을 글로벌 dedup 키로 사용한다.
        기존 unique 제약 ``(source, url)`` 은 그대로 유지하되, 본 collector
        흐름에서는 동일 url 이 여러 source 로 들어오는 케이스가 사실상 없다고
        가정한다 (v0.6+ 에서 실 RSS 출처 다중화 시 재검토).
        """
        statement = select(NewsItem).where(NewsItem.url == url)
        return self.session.execute(statement).scalars().first()

    def upsert_by_url(
        self,
        *,
        url: str,
        published_at: datetime,
        source: str,
        title: str,
        related_symbols: list[str] | None = None,
        sentiment: str | None = None,
        importance: str | None = None,
        theme: str | None = None,
        category: str | None = None,
        available_at: datetime | None = None,
    ) -> tuple[NewsItem, bool]:
        """Idempotent insert keyed by ``url``.

        Returns ``(news_item, inserted)``. ``inserted=False`` means the row
        already existed and the caller should treat the call as a duplicate
        skip — fields are NOT overwritten.
        """
        if not url:
            raise ValueError("upsert_by_url requires a non-empty url")
        existing = self.get_by_url(url)
        if existing is not None:
            return existing, False
        news = self.add(
            NewsItem(
                published_at=published_at,
                available_at=available_at,
                source=source,
                title=title,
                url=url,
                related_symbols=related_symbols,
                sentiment=sentiment,
                importance=importance,
                theme=theme,
                category=category,
            ),
        )
        return news, True

    def list_recent_by_symbol(
        self,
        symbol: str,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItem]:
        """Return news rows whose ``related_symbols`` JSON array contains ``symbol``.

        SQLite has no portable JSON-containment operator, so we fetch recent
        rows ordered by ``published_at desc`` and filter in Python. Volume
        is low enough (news_items is bounded by collector cadence) that this
        is acceptable — Postgres-native containment is a v0.6+ optimization
        candidate.
        """
        statement = select(NewsItem).order_by(NewsItem.published_at.desc())
        if since is not None:
            statement = statement.where(NewsItem.published_at >= since)
        rows = list(self.session.execute(statement).scalars().all())
        matches: list[NewsItem] = []
        for row in rows:
            related = row.related_symbols or []
            if symbol in related:
                matches.append(row)
                if len(matches) >= limit:
                    break
        return matches

    def list_recent_by_category(
        self,
        category: str,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItem]:
        statement = select(NewsItem).where(NewsItem.category == category)
        if since is not None:
            statement = statement.where(NewsItem.published_at >= since)
        statement = statement.order_by(NewsItem.published_at.desc()).limit(limit)
        return list(self.session.execute(statement).scalars().all())
