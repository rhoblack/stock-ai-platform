from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import FundamentalSnapshot


class FundamentalSnapshotRepository(BaseRepository[FundamentalSnapshot]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, FundamentalSnapshot)

    def create(
        self,
        *,
        symbol: str,
        snapshot_date: date,
        fiscal_year: int,
        fiscal_quarter: int | None = None,
        revenue: Decimal | None = None,
        operating_income: Decimal | None = None,
        net_income: Decimal | None = None,
        total_assets: Decimal | None = None,
        total_liabilities: Decimal | None = None,
        total_equity: Decimal | None = None,
        eps: Decimal | None = None,
        bps: Decimal | None = None,
        per: Decimal | None = None,
        pbr: Decimal | None = None,
        roe: Decimal | None = None,
        debt_ratio: Decimal | None = None,
        dividend_yield: Decimal | None = None,
        revenue_growth_yoy: Decimal | None = None,
        operating_income_growth_yoy: Decimal | None = None,
        source: str | None = None,
    ) -> FundamentalSnapshot:
        return self.add(
            FundamentalSnapshot(
                symbol=symbol,
                snapshot_date=snapshot_date,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                revenue=revenue,
                operating_income=operating_income,
                net_income=net_income,
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
                eps=eps,
                bps=bps,
                per=per,
                pbr=pbr,
                roe=roe,
                debt_ratio=debt_ratio,
                dividend_yield=dividend_yield,
                revenue_growth_yoy=revenue_growth_yoy,
                operating_income_growth_yoy=operating_income_growth_yoy,
                source=source,
            ),
        )

    def get_by_symbol_period(
        self,
        *,
        symbol: str,
        snapshot_date: date,
        fiscal_year: int,
        fiscal_quarter: int | None,
    ) -> FundamentalSnapshot | None:
        statement = select(FundamentalSnapshot).where(
            FundamentalSnapshot.symbol == symbol,
            FundamentalSnapshot.snapshot_date == snapshot_date,
            FundamentalSnapshot.fiscal_year == fiscal_year,
        )
        if fiscal_quarter is None:
            statement = statement.where(FundamentalSnapshot.fiscal_quarter.is_(None))
        else:
            statement = statement.where(FundamentalSnapshot.fiscal_quarter == fiscal_quarter)
        return self.session.execute(statement).scalar_one_or_none()

    def upsert_by_symbol_period(
        self,
        *,
        symbol: str,
        snapshot_date: date,
        fiscal_year: int,
        fiscal_quarter: int | None = None,
        revenue: Decimal | None = None,
        operating_income: Decimal | None = None,
        net_income: Decimal | None = None,
        total_assets: Decimal | None = None,
        total_liabilities: Decimal | None = None,
        total_equity: Decimal | None = None,
        eps: Decimal | None = None,
        bps: Decimal | None = None,
        per: Decimal | None = None,
        pbr: Decimal | None = None,
        roe: Decimal | None = None,
        debt_ratio: Decimal | None = None,
        dividend_yield: Decimal | None = None,
        revenue_growth_yoy: Decimal | None = None,
        operating_income_growth_yoy: Decimal | None = None,
        source: str | None = None,
    ) -> FundamentalSnapshot:
        """Insert or update one symbol/period row.

        Policy: when the unique period already exists, overwrite the normalized
        metric columns with the supplied values and return the same row. This
        keeps manual CSV corrections idempotent without preserving stale metrics.
        """
        existing = self.get_by_symbol_period(
            symbol=symbol,
            snapshot_date=snapshot_date,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
        )
        if existing is None:
            return self.create(
                symbol=symbol,
                snapshot_date=snapshot_date,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
                revenue=revenue,
                operating_income=operating_income,
                net_income=net_income,
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
                eps=eps,
                bps=bps,
                per=per,
                pbr=pbr,
                roe=roe,
                debt_ratio=debt_ratio,
                dividend_yield=dividend_yield,
                revenue_growth_yoy=revenue_growth_yoy,
                operating_income_growth_yoy=operating_income_growth_yoy,
                source=source,
            )

        existing.revenue = revenue
        existing.operating_income = operating_income
        existing.net_income = net_income
        existing.total_assets = total_assets
        existing.total_liabilities = total_liabilities
        existing.total_equity = total_equity
        existing.eps = eps
        existing.bps = bps
        existing.per = per
        existing.pbr = pbr
        existing.roe = roe
        existing.debt_ratio = debt_ratio
        existing.dividend_yield = dividend_yield
        existing.revenue_growth_yoy = revenue_growth_yoy
        existing.operating_income_growth_yoy = operating_income_growth_yoy
        existing.source = source
        self.session.flush()
        return existing

    def get_latest_by_symbol(self, symbol: str) -> FundamentalSnapshot | None:
        statement = (
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.symbol == symbol)
            .order_by(
                FundamentalSnapshot.snapshot_date.desc(),
                FundamentalSnapshot.fiscal_year.desc(),
                FundamentalSnapshot.fiscal_quarter.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_recent_by_symbol(
        self,
        symbol: str,
        *,
        limit: int = 20,
    ) -> list[FundamentalSnapshot]:
        statement = (
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.symbol == symbol)
            .order_by(
                FundamentalSnapshot.snapshot_date.desc(),
                FundamentalSnapshot.fiscal_year.desc(),
                FundamentalSnapshot.fiscal_quarter.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_fiscal_year(
        self,
        fiscal_year: int,
        *,
        limit: int = 200,
    ) -> list[FundamentalSnapshot]:
        statement = (
            select(FundamentalSnapshot)
            .where(FundamentalSnapshot.fiscal_year == fiscal_year)
            .order_by(
                FundamentalSnapshot.symbol.asc(),
                FundamentalSnapshot.snapshot_date.desc(),
                FundamentalSnapshot.fiscal_quarter.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
