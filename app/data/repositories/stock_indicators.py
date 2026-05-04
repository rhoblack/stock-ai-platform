from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.models import StockIndicator


class StockIndicatorRepository(BaseRepository[StockIndicator]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StockIndicator)

    def get_by_symbol_date(self, symbol: str, indicator_date: date) -> StockIndicator | None:
        statement = select(StockIndicator).where(
            StockIndicator.symbol == symbol,
            StockIndicator.date == indicator_date,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest_by_symbol(self, symbol: str) -> StockIndicator | None:
        statement = (
            select(StockIndicator)
            .where(StockIndicator.symbol == symbol)
            .order_by(StockIndicator.date.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def upsert(
        self,
        *,
        symbol: str,
        indicator_date: date,
        ma5: Decimal | None = None,
        ma20: Decimal | None = None,
        ma60: Decimal | None = None,
        ma120: Decimal | None = None,
        rsi14: Decimal | None = None,
        macd: Decimal | None = None,
        macd_signal: Decimal | None = None,
        volume_ratio_20d: Decimal | None = None,
        breakout_20d: bool | None = None,
        breakout_60d: bool | None = None,
        ma_alignment: str | None = None,
        technical_score: Decimal | None = None,
    ) -> StockIndicator:
        existing = self.get_by_symbol_date(symbol, indicator_date)
        if existing is None:
            return self.add(
                StockIndicator(
                    symbol=symbol,
                    date=indicator_date,
                    ma5=ma5,
                    ma20=ma20,
                    ma60=ma60,
                    ma120=ma120,
                    rsi14=rsi14,
                    macd=macd,
                    macd_signal=macd_signal,
                    volume_ratio_20d=volume_ratio_20d,
                    breakout_20d=breakout_20d,
                    breakout_60d=breakout_60d,
                    ma_alignment=ma_alignment,
                    technical_score=technical_score,
                ),
            )

        existing.ma5 = ma5
        existing.ma20 = ma20
        existing.ma60 = ma60
        existing.ma120 = ma120
        existing.rsi14 = rsi14
        existing.macd = macd
        existing.macd_signal = macd_signal
        existing.volume_ratio_20d = volume_ratio_20d
        existing.breakout_20d = breakout_20d
        existing.breakout_60d = breakout_60d
        existing.ma_alignment = ma_alignment
        existing.technical_score = technical_score
        self.session.flush()
        return existing
