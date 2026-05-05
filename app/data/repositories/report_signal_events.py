from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ReportSignalEvent


class ReportSignalEventRepository(BaseRepository[ReportSignalEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReportSignalEvent)

    def create(
        self,
        *,
        report_id: int,
        event_type: str,
        direction: str,
        time_horizon: str,
        extraction_method: str,
        symbol: str | None = None,
        theme_id: int | None = None,
        strength: Decimal | None = None,
        summary: str | None = None,
        evidence_json: dict | None = None,
        extraction_confidence: Decimal | None = None,
    ) -> ReportSignalEvent:
        return self.add(
            ReportSignalEvent(
                report_id=report_id,
                event_type=event_type,
                direction=direction,
                time_horizon=time_horizon,
                extraction_method=extraction_method,
                symbol=symbol,
                theme_id=theme_id,
                strength=strength,
                summary=summary,
                evidence_json=evidence_json,
                extraction_confidence=extraction_confidence,
            ),
        )

    def get_by_unique(
        self,
        *,
        report_id: int,
        event_type: str,
        symbol: str | None,
        theme_id: int | None,
    ) -> ReportSignalEvent | None:
        statement = select(ReportSignalEvent).where(
            ReportSignalEvent.report_id == report_id,
            ReportSignalEvent.event_type == event_type,
            ReportSignalEvent.symbol.is_(None) if symbol is None else ReportSignalEvent.symbol == symbol,
            ReportSignalEvent.theme_id.is_(None) if theme_id is None else ReportSignalEvent.theme_id == theme_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_report_event_symbol_theme(
        self,
        *,
        report_id: int,
        event_type: str,
        direction: str,
        time_horizon: str,
        extraction_method: str,
        symbol: str | None = None,
        theme_id: int | None = None,
        **fields,
    ) -> ReportSignalEvent:
        existing = self.get_by_unique(
            report_id=report_id,
            event_type=event_type,
            symbol=symbol,
            theme_id=theme_id,
        )
        if existing is not None:
            return existing
        return self.create(
            report_id=report_id,
            event_type=event_type,
            direction=direction,
            time_horizon=time_horizon,
            extraction_method=extraction_method,
            symbol=symbol,
            theme_id=theme_id,
            **fields,
        )

    def list_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .where(ReportSignalEvent.symbol == symbol)
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_theme(
        self,
        theme_id: int,
        *,
        limit: int = 50,
    ) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .where(ReportSignalEvent.theme_id == theme_id)
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_event_type(
        self,
        event_type: str,
        *,
        limit: int = 50,
    ) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .where(ReportSignalEvent.event_type == event_type)
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent(self, *, limit: int = 50) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_positive_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .where(
                ReportSignalEvent.symbol == symbol,
                ReportSignalEvent.direction == "POSITIVE",
            )
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_negative_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ReportSignalEvent]:
        statement = (
            select(ReportSignalEvent)
            .where(
                ReportSignalEvent.symbol == symbol,
                ReportSignalEvent.direction == "NEGATIVE",
            )
            .order_by(ReportSignalEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
