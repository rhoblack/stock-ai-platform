from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import EarningsEvent


class EarningsEventRepository(BaseRepository[EarningsEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, EarningsEvent)

    def create(
        self,
        *,
        symbol: str,
        event_date: date,
        fiscal_year: int,
        event_type: str,
        company_name: str | None = None,
        fiscal_quarter: int | None = None,
        revenue_actual: Decimal | None = None,
        revenue_consensus: Decimal | None = None,
        operating_income_actual: Decimal | None = None,
        operating_income_consensus: Decimal | None = None,
        net_income_actual: Decimal | None = None,
        net_income_consensus: Decimal | None = None,
        eps_actual: Decimal | None = None,
        eps_consensus: Decimal | None = None,
        surprise_type: str | None = None,
        surprise_pct: Decimal | None = None,
        source: str | None = None,
        memo: str | None = None,
    ) -> EarningsEvent:
        return self.add(
            EarningsEvent(
                symbol=symbol,
                company_name=company_name,
                event_date=event_date,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                event_type=event_type,
                revenue_actual=revenue_actual,
                revenue_consensus=revenue_consensus,
                operating_income_actual=operating_income_actual,
                operating_income_consensus=operating_income_consensus,
                net_income_actual=net_income_actual,
                net_income_consensus=net_income_consensus,
                eps_actual=eps_actual,
                eps_consensus=eps_consensus,
                surprise_type=surprise_type,
                surprise_pct=surprise_pct,
                source=source,
                memo=memo,
            ),
        )

    def get_by_symbol_event(
        self,
        *,
        symbol: str,
        event_date: date,
        fiscal_year: int,
        fiscal_quarter: int | None,
        event_type: str,
    ) -> EarningsEvent | None:
        statement = select(EarningsEvent).where(
            EarningsEvent.symbol == symbol,
            EarningsEvent.event_date == event_date,
            EarningsEvent.fiscal_year == fiscal_year,
            EarningsEvent.event_type == event_type,
        )
        if fiscal_quarter is None:
            statement = statement.where(EarningsEvent.fiscal_quarter.is_(None))
        else:
            statement = statement.where(EarningsEvent.fiscal_quarter == fiscal_quarter)
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_symbol_event(
        self,
        *,
        symbol: str,
        event_date: date,
        fiscal_year: int,
        event_type: str,
        company_name: str | None = None,
        fiscal_quarter: int | None = None,
        revenue_actual: Decimal | None = None,
        revenue_consensus: Decimal | None = None,
        operating_income_actual: Decimal | None = None,
        operating_income_consensus: Decimal | None = None,
        net_income_actual: Decimal | None = None,
        net_income_consensus: Decimal | None = None,
        eps_actual: Decimal | None = None,
        eps_consensus: Decimal | None = None,
        surprise_type: str | None = None,
        surprise_pct: Decimal | None = None,
        source: str | None = None,
        memo: str | None = None,
    ) -> EarningsEvent:
        existing = self.get_by_symbol_event(
            symbol=symbol,
            event_date=event_date,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            event_type=event_type,
        )
        if existing is None:
            return self.create(
                symbol=symbol,
                event_date=event_date,
                fiscal_year=fiscal_year,
                event_type=event_type,
                company_name=company_name,
                fiscal_quarter=fiscal_quarter,
                revenue_actual=revenue_actual,
                revenue_consensus=revenue_consensus,
                operating_income_actual=operating_income_actual,
                operating_income_consensus=operating_income_consensus,
                net_income_actual=net_income_actual,
                net_income_consensus=net_income_consensus,
                eps_actual=eps_actual,
                eps_consensus=eps_consensus,
                surprise_type=surprise_type,
                surprise_pct=surprise_pct,
                source=source,
                memo=memo,
            )

        existing.company_name = company_name
        existing.revenue_actual = revenue_actual
        existing.revenue_consensus = revenue_consensus
        existing.operating_income_actual = operating_income_actual
        existing.operating_income_consensus = operating_income_consensus
        existing.net_income_actual = net_income_actual
        existing.net_income_consensus = net_income_consensus
        existing.eps_actual = eps_actual
        existing.eps_consensus = eps_consensus
        existing.surprise_type = surprise_type
        existing.surprise_pct = surprise_pct
        existing.source = source
        existing.memo = memo
        self.session.flush()
        return existing

    def get_latest_by_symbol(self, symbol: str) -> EarningsEvent | None:
        statement = (
            select(EarningsEvent)
            .where(EarningsEvent.symbol == symbol)
            .order_by(EarningsEvent.event_date.desc(), EarningsEvent.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_recent_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 20,
    ) -> list[EarningsEvent]:
        statement = (
            select(EarningsEvent)
            .where(EarningsEvent.symbol == symbol)
            .order_by(EarningsEvent.event_date.desc(), EarningsEvent.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_upcoming(
        self,
        *,
        since: date,
        until: date | None = None,
        limit: int = 100,
    ) -> list[EarningsEvent]:
        statement = select(EarningsEvent).where(EarningsEvent.event_date >= since)
        if until is not None:
            statement = statement.where(EarningsEvent.event_date <= until)
        statement = statement.order_by(EarningsEvent.event_date.asc(), EarningsEvent.symbol.asc()).limit(limit)
        return list(self.session.execute(statement).scalars().all())

    def list_by_surprise_type(
        self,
        surprise_type: str,
        *,
        limit: int = 100,
    ) -> list[EarningsEvent]:
        statement = (
            select(EarningsEvent)
            .where(EarningsEvent.surprise_type == surprise_type)
            .order_by(EarningsEvent.event_date.desc(), EarningsEvent.symbol.asc())
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
