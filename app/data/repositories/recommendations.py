from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import Recommendation, RecommendationResult, RecommendationRun


class RecommendationRunRepository(BaseRepository[RecommendationRun]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, RecommendationRun)

    def latest(self) -> RecommendationRun | None:
        statement = select(RecommendationRun).order_by(RecommendationRun.run_date.desc())
        return self.session.execute(statement).scalars().first()


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

