from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import ThemeStockMapping


class ThemeStockMappingRepository(BaseRepository[ThemeStockMapping]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ThemeStockMapping)

    def create(
        self,
        *,
        theme_id: int,
        symbol: str,
        impact_direction: str,
        extraction_method: str,
        company_name: str | None = None,
        market: str | None = None,
        exchange: str | None = None,
        country: str | None = None,
        relation_type: str | None = None,
        impact_strength: Decimal | None = None,
        impact_path: str | None = None,
        benefit_type: str | None = None,
        time_lag: str | None = None,
        reason: str | None = None,
        source_sentence_summary: str | None = None,
        extraction_confidence: Decimal | None = None,
    ) -> ThemeStockMapping:
        return self.add(
            ThemeStockMapping(
                theme_id=theme_id,
                symbol=symbol,
                impact_direction=impact_direction,
                extraction_method=extraction_method,
                company_name=company_name,
                market=market,
                exchange=exchange,
                country=country,
                relation_type=relation_type,
                impact_strength=impact_strength,
                impact_path=impact_path,
                benefit_type=benefit_type,
                time_lag=time_lag,
                reason=reason,
                source_sentence_summary=source_sentence_summary,
                extraction_confidence=extraction_confidence,
            ),
        )

    def get_by_theme_and_symbol(
        self,
        *,
        theme_id: int,
        symbol: str,
    ) -> ThemeStockMapping | None:
        statement = select(ThemeStockMapping).where(
            ThemeStockMapping.theme_id == theme_id,
            ThemeStockMapping.symbol == symbol,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_theme_and_symbol(
        self,
        *,
        theme_id: int,
        symbol: str,
        impact_direction: str,
        extraction_method: str,
        **fields,
    ) -> ThemeStockMapping:
        existing = self.get_by_theme_and_symbol(theme_id=theme_id, symbol=symbol)
        if existing is not None:
            return existing
        return self.create(
            theme_id=theme_id,
            symbol=symbol,
            impact_direction=impact_direction,
            extraction_method=extraction_method,
            **fields,
        )

    def list_by_theme(self, theme_id: int) -> list[ThemeStockMapping]:
        statement = (
            select(ThemeStockMapping)
            .where(ThemeStockMapping.theme_id == theme_id)
            .order_by(ThemeStockMapping.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ThemeStockMapping]:
        statement = (
            select(ThemeStockMapping)
            .where(ThemeStockMapping.symbol == symbol)
            .order_by(ThemeStockMapping.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_positive_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ThemeStockMapping]:
        statement = (
            select(ThemeStockMapping)
            .where(
                ThemeStockMapping.symbol == symbol,
                ThemeStockMapping.impact_direction == "POSITIVE",
            )
            .order_by(ThemeStockMapping.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_negative_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[ThemeStockMapping]:
        statement = (
            select(ThemeStockMapping)
            .where(
                ThemeStockMapping.symbol == symbol,
                ThemeStockMapping.impact_direction == "NEGATIVE",
            )
            .order_by(ThemeStockMapping.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_impact_path(
        self,
        impact_path: str,
        *,
        limit: int = 50,
    ) -> list[ThemeStockMapping]:
        statement = (
            select(ThemeStockMapping)
            .where(ThemeStockMapping.impact_path == impact_path)
            .order_by(ThemeStockMapping.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
