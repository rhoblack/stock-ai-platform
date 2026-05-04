from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import DailyPrice


class DailyPriceRepository(BaseRepository[DailyPrice]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, DailyPrice)

    def get_by_symbol_date(self, symbol: str, price_date: date) -> DailyPrice | None:
        statement = select(DailyPrice).where(
            DailyPrice.symbol == symbol,
            DailyPrice.date == price_date,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest_by_symbol(self, symbol: str) -> DailyPrice | None:
        statement = (
            select(DailyPrice)
            .where(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_in_range(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[DailyPrice]:
        """Return bars for ``symbol`` in ``[start_date, end_date]`` ascending."""
        statement = (
            select(DailyPrice)
            .where(
                DailyPrice.symbol == symbol,
                DailyPrice.date >= start_date,
                DailyPrice.date <= end_date,
            )
            .order_by(DailyPrice.date.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def get_latest_on_or_before(
        self,
        *,
        symbol: str,
        target_date: date,
        lookback_days: int = 14,
    ) -> DailyPrice | None:
        """Return the most recent bar with date ≤ target_date (within lookback)."""
        statement = (
            select(DailyPrice)
            .where(
                DailyPrice.symbol == symbol,
                DailyPrice.date <= target_date,
                DailyPrice.date >= target_date - timedelta(days=lookback_days),
            )
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_symbol(
        self,
        symbol: str,
        *,
        limit: int | None = None,
    ) -> list[DailyPrice]:
        """Return bars for ``symbol`` ordered by date ascending.

        When ``limit`` is provided, returns only the most recent ``limit`` bars
        (still ordered ascending) using a SQL ORDER BY DESC + LIMIT under the hood.
        """
        if limit is not None:
            statement = (
                select(DailyPrice)
                .where(DailyPrice.symbol == symbol)
                .order_by(DailyPrice.date.desc())
                .limit(limit)
            )
            rows = list(self.session.execute(statement).scalars().all())
            rows.reverse()
            return rows

        statement = (
            select(DailyPrice)
            .where(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.date.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def upsert(
        self,
        *,
        symbol: str,
        price_date: date,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal,
        volume: int,
        trading_value: Decimal | None = None,
        adjusted_close: Decimal | None = None,
    ) -> DailyPrice:
        existing = self.get_by_symbol_date(symbol, price_date)
        if existing is None:
            return self.add(
                DailyPrice(
                    symbol=symbol,
                    date=price_date,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    trading_value=trading_value,
                    adjusted_close=adjusted_close,
                ),
            )

        existing.open = open_price
        existing.high = high_price
        existing.low = low_price
        existing.close = close_price
        existing.volume = volume
        existing.trading_value = trading_value
        existing.adjusted_close = adjusted_close
        self.session.flush()
        return existing

