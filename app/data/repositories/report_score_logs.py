from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ReportScoreLog


class ReportScoreLogRepository(BaseRepository[ReportScoreLog]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReportScoreLog)

    def create(
        self,
        *,
        symbol: str,
        score_date: date,
        report_count: int,
        evidence_json: dict | None = None,
        report_score: Decimal | None = None,
        theme_signal_score: Decimal | None = None,
        theme_count: int | None = None,
        signal_event_count: int | None = None,
        target_upside_pct: Decimal | None = None,
        rating_score_avg: Decimal | None = None,
        recency_bonus: Decimal | None = None,
        theme_signal_bonus: Decimal | None = None,
        event_signal_bonus: Decimal | None = None,
        risk_penalty: Decimal | None = None,
        recommendation_run_id: int | None = None,
    ) -> ReportScoreLog:
        return self.add(
            ReportScoreLog(
                symbol=symbol,
                score_date=score_date,
                report_count=report_count,
                evidence_json=evidence_json,
                report_score=report_score,
                theme_signal_score=theme_signal_score,
                theme_count=theme_count,
                signal_event_count=signal_event_count,
                target_upside_pct=target_upside_pct,
                rating_score_avg=rating_score_avg,
                recency_bonus=recency_bonus,
                theme_signal_bonus=theme_signal_bonus,
                event_signal_bonus=event_signal_bonus,
                risk_penalty=risk_penalty,
                recommendation_run_id=recommendation_run_id,
            ),
        )

    def get_latest_by_symbol(self, symbol: str) -> ReportScoreLog | None:
        statement = (
            select(ReportScoreLog)
            .where(ReportScoreLog.symbol == symbol)
            .order_by(ReportScoreLog.score_date.desc(), ReportScoreLog.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_recommendation_run_symbol(
        self,
        *,
        run_id: int,
        symbol: str,
    ) -> ReportScoreLog | None:
        statement = (
            select(ReportScoreLog)
            .where(
                ReportScoreLog.recommendation_run_id == run_id,
                ReportScoreLog.symbol == symbol,
            )
            .order_by(ReportScoreLog.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_recent_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 30,
    ) -> list[ReportScoreLog]:
        statement = (
            select(ReportScoreLog)
            .where(ReportScoreLog.symbol == symbol)
            .order_by(ReportScoreLog.score_date.desc(), ReportScoreLog.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_recommendation_run(self, run_id: int) -> list[ReportScoreLog]:
        statement = (
            select(ReportScoreLog)
            .where(ReportScoreLog.recommendation_run_id == run_id)
            .order_by(ReportScoreLog.symbol.asc())
        )
        return list(self.session.execute(statement).scalars().all())
