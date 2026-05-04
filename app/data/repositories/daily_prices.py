from datetime import date
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

