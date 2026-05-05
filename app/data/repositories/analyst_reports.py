from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import AnalystReport


class AnalystReportRepository(BaseRepository[AnalystReport]):
    """CRUD + read queries for `analyst_reports`.

    No score / consensus computation lives here — that is Phase B+. This
    repository is intentionally pure persistence: callers prepare values and
    the repository writes / reads. `source_file_path` is stored verbatim and
    is the responsibility of the API layer to mask before exposing it.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, AnalystReport)

    # ---------- create / upsert ----------

    def create(
        self,
        *,
        broker_name: str,
        published_at: date,
        title: str,
        report_type: str,
        extraction_method: str,
        symbol: str | None = None,
        company_name: str | None = None,
        market: str | None = None,
        exchange: str | None = None,
        country: str | None = None,
        broker_country: str | None = None,
        analyst_name: str | None = None,
        rating: str | None = None,
        normalized_rating: str | None = None,
        target_price: Decimal | None = None,
        previous_target_price: Decimal | None = None,
        current_price_at_report: Decimal | None = None,
        currency: str | None = None,
        summary: str | None = None,
        positive_points: str | None = None,
        risk_points: str | None = None,
        source_url: str | None = None,
        source_file_path: str | None = None,
        language: str | None = None,
        source_reliability_score: Decimal | None = None,
        extraction_confidence: Decimal | None = None,
        duplicate_group_key: str | None = None,
    ) -> AnalystReport:
        return self.add(
            AnalystReport(
                broker_name=broker_name,
                published_at=published_at,
                title=title,
                report_type=report_type,
                extraction_method=extraction_method,
                symbol=symbol,
                company_name=company_name,
                market=market,
                exchange=exchange,
                country=country,
                broker_country=broker_country,
                analyst_name=analyst_name,
                rating=rating,
                normalized_rating=normalized_rating,
                target_price=target_price,
                previous_target_price=previous_target_price,
                current_price_at_report=current_price_at_report,
                currency=currency,
                summary=summary,
                positive_points=positive_points,
                risk_points=risk_points,
                source_url=source_url,
                source_file_path=source_file_path,
                language=language,
                source_reliability_score=source_reliability_score,
                extraction_confidence=extraction_confidence,
                duplicate_group_key=duplicate_group_key,
            ),
        )

    def get_by_id(self, report_id: int) -> AnalystReport | None:
        return self.session.get(AnalystReport, report_id)

    def get_by_unique(
        self,
        *,
        broker_name: str,
        published_at: date,
        title: str,
    ) -> AnalystReport | None:
        statement = select(AnalystReport).where(
            AnalystReport.broker_name == broker_name,
            AnalystReport.published_at == published_at,
            AnalystReport.title == title,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_unique(
        self,
        *,
        broker_name: str,
        published_at: date,
        title: str,
        report_type: str,
        extraction_method: str,
        **fields,
    ) -> AnalystReport:
        """Idempotent create — returns existing row on unique conflict.

        Existing rows are NOT mutated by this call (use `update_*` helpers if
        editing is needed). This matches the CSV-import use-case where the
        operator imports the same file twice.
        """
        existing = self.get_by_unique(
            broker_name=broker_name,
            published_at=published_at,
            title=title,
        )
        if existing is not None:
            return existing
        return self.create(
            broker_name=broker_name,
            published_at=published_at,
            title=title,
            report_type=report_type,
            extraction_method=extraction_method,
            **fields,
        )

    # ---------- read ----------

    def list_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 50,
    ) -> list[AnalystReport]:
        statement = (
            select(AnalystReport)
            .where(AnalystReport.symbol == symbol)
            .order_by(AnalystReport.published_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_report_type(
        self,
        report_type: str,
        *,
        limit: int = 50,
    ) -> list[AnalystReport]:
        statement = (
            select(AnalystReport)
            .where(AnalystReport.report_type == report_type)
            .order_by(AnalystReport.published_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent(self, *, limit: int = 50) -> list[AnalystReport]:
        statement = (
            select(AnalystReport)
            .order_by(AnalystReport.published_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_recent_by_broker(
        self,
        broker_name: str,
        *,
        limit: int = 50,
    ) -> list[AnalystReport]:
        statement = (
            select(AnalystReport)
            .where(AnalystReport.broker_name == broker_name)
            .order_by(AnalystReport.published_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def search_text(
        self,
        keyword: str,
        *,
        limit: int = 50,
    ) -> list[AnalystReport]:
        """Case-sensitive substring match on title or summary.

        Phase A keeps it simple — full-text search / LIKE indexing is a v0.5
        concern. SQLite + Postgres both honor the `LIKE` operator unmodified.
        """
        pattern = f"%{keyword}%"
        statement = (
            select(AnalystReport)
            .where(
                or_(
                    AnalystReport.title.like(pattern),
                    AnalystReport.summary.like(pattern),
                )
            )
            .order_by(AnalystReport.published_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
