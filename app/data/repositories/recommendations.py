from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import Recommendation, RecommendationResult, RecommendationRun


class RecommendationRunRepository(BaseRepository[RecommendationRun]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RecommendationRun)

    def latest(self) -> RecommendationRun | None:
        statement = select(RecommendationRun).order_by(
            RecommendationRun.run_date.desc(),
            RecommendationRun.started_at.desc(),
            RecommendationRun.run_id.desc(),
        )
        return self.session.execute(statement).scalars().first()

    def list_by_date_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[RecommendationRun]:
        statement = (
            select(RecommendationRun)
            .where(
                RecommendationRun.run_date >= start_date,
                RecommendationRun.run_date <= end_date,
            )
            .order_by(RecommendationRun.run_date.asc())
        )
        return list(self.session.execute(statement).scalars().all())


class RecommendationRepository(BaseRepository[Recommendation]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Recommendation)

    def list_by_run_id(self, run_id: int) -> list[Recommendation]:
        statement = (
            select(Recommendation)
            .where(Recommendation.run_id == run_id)
            .order_by(Recommendation.rank)
        )
        return list(self.session.execute(statement).scalars().all())


class RecommendationResultRepository(BaseRepository[RecommendationResult]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RecommendationResult)

    def list_by_recommendation_id(self, recommendation_id: int) -> list[RecommendationResult]:
        statement = (
            select(RecommendationResult)
            .where(RecommendationResult.recommendation_id == recommendation_id)
            .order_by(RecommendationResult.days_after)
        )
        return list(self.session.execute(statement).scalars().all())

    def get_by_recommendation_days(
        self,
        *,
        recommendation_id: int,
        days_after: int,
    ) -> RecommendationResult | None:
        statement = select(RecommendationResult).where(
            RecommendationResult.recommendation_id == recommendation_id,
            RecommendationResult.days_after == days_after,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert(
        self,
        *,
        recommendation_id: int,
        days_after: int,
        result_date: date,
        open_return: Decimal | None = None,
        high_return: Decimal | None = None,
        low_return: Decimal | None = None,
        close_return: Decimal | None = None,
        max_return: Decimal | None = None,
        max_drawdown: Decimal | None = None,
        result_status: str | None = None,
    ) -> RecommendationResult:
        existing = self.get_by_recommendation_days(
            recommendation_id=recommendation_id,
            days_after=days_after,
        )
        if existing is None:
            return self.add(
                RecommendationResult(
                    recommendation_id=recommendation_id,
                    days_after=days_after,
                    result_date=result_date,
                    open_return=open_return,
                    high_return=high_return,
                    low_return=low_return,
                    close_return=close_return,
                    max_return=max_return,
                    max_drawdown=max_drawdown,
                    result_status=result_status,
                ),
            )

        existing.result_date = result_date
        existing.open_return = open_return
        existing.high_return = high_return
        existing.low_return = low_return
        existing.close_return = close_return
        existing.max_return = max_return
        existing.max_drawdown = max_drawdown
        existing.result_status = result_status
        self.session.flush()
        return existing
