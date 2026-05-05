from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ReportTheme


class ReportThemeRepository(BaseRepository[ReportTheme]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReportTheme)

    def create(
        self,
        *,
        theme_name: str,
        theme_category: str,
        direction: str,
        time_horizon: str,
        source_report_id: int,
        extraction_method: str,
        confidence: Decimal | None = None,
        summary: str | None = None,
        extraction_confidence: Decimal | None = None,
    ) -> ReportTheme:
        return self.add(
            ReportTheme(
                theme_name=theme_name,
                theme_category=theme_category,
                direction=direction,
                time_horizon=time_horizon,
                source_report_id=source_report_id,
                extraction_method=extraction_method,
                confidence=confidence,
                summary=summary,
                extraction_confidence=extraction_confidence,
            ),
        )

    def get_by_report_and_name(
        self,
        *,
        source_report_id: int,
        theme_name: str,
    ) -> ReportTheme | None:
        statement = select(ReportTheme).where(
            ReportTheme.source_report_id == source_report_id,
            ReportTheme.theme_name == theme_name,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_report_and_theme(
        self,
        *,
        source_report_id: int,
        theme_name: str,
        theme_category: str,
        direction: str,
        time_horizon: str,
        extraction_method: str,
        **fields,
    ) -> ReportTheme:
        existing = self.get_by_report_and_name(
            source_report_id=source_report_id,
            theme_name=theme_name,
        )
        if existing is not None:
            return existing
        return self.create(
            source_report_id=source_report_id,
            theme_name=theme_name,
            theme_category=theme_category,
            direction=direction,
            time_horizon=time_horizon,
            extraction_method=extraction_method,
            **fields,
        )

    def list_recent(self, *, limit: int = 50) -> list[ReportTheme]:
        statement = (
            select(ReportTheme)
            .order_by(ReportTheme.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_category(
        self,
        category: str,
        *,
        limit: int = 50,
    ) -> list[ReportTheme]:
        statement = (
            select(ReportTheme)
            .where(ReportTheme.theme_category == category)
            .order_by(ReportTheme.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_direction(
        self,
        direction: str,
        *,
        limit: int = 50,
    ) -> list[ReportTheme]:
        statement = (
            select(ReportTheme)
            .where(ReportTheme.direction == direction)
            .order_by(ReportTheme.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_source_report(self, source_report_id: int) -> list[ReportTheme]:
        statement = (
            select(ReportTheme)
            .where(ReportTheme.source_report_id == source_report_id)
            .order_by(ReportTheme.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())
