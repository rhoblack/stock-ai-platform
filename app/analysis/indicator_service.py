"""Service that pulls daily prices, runs the TechnicalAnalyzer, and persists results.

This service bridges the data layer (DailyPriceRepository / StockIndicatorRepository)
and the analysis layer (TechnicalAnalyzer). It does not call external APIs, does not
generate recommendations, and does not send notifications.

Typical batch usage (Phase 4-2 only — no scheduler wiring yet):

    service = TechnicalIndicatorService(daily_price_repo, indicator_repo)
    service.analyze_and_store_many(symbols=["005930", "000660", ...])
"""

from collections.abc import Iterable

from app.analysis.technical_analyzer import IndicatorSnapshot, TechnicalAnalyzer
from app.data.dtos import KisDailyPrice
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.db.models import DailyPrice


def _to_kis_daily_price(orm: DailyPrice) -> KisDailyPrice:
    return KisDailyPrice(
        symbol=orm.symbol,
        date=orm.date,
        open=orm.open,
        high=orm.high,
        low=orm.low,
        close=orm.close,
        volume=orm.volume,
        trading_value=orm.trading_value,
    )


class TechnicalIndicatorService:
    DEFAULT_LOOKBACK_DAYS = 250

    def __init__(
        self,
        daily_price_repository: DailyPriceRepository,
        indicator_repository: StockIndicatorRepository,
        analyzer: TechnicalAnalyzer | None = None,
    ) -> None:
        self._prices = daily_price_repository
        self._indicators = indicator_repository
        self._analyzer = analyzer or TechnicalAnalyzer()

    def analyze_and_store(
        self,
        symbol: str,
        *,
        lookback_days: int | None = None,
    ) -> IndicatorSnapshot | None:
        """Compute indicators for ``symbol`` and upsert into ``stock_indicators``.

        Returns the snapshot that was persisted, or ``None`` if there were no
        daily prices for the symbol. Insufficient history yields a snapshot
        with ``None`` for indicators that cannot be computed; the row is still
        upserted so that downstream consumers see a consistent (symbol, date)
        marker.
        """
        effective_lookback = (
            lookback_days if lookback_days is not None else self.DEFAULT_LOOKBACK_DAYS
        )
        bars = self._prices.list_by_symbol(symbol, limit=effective_lookback)
        if not bars:
            return None

        snapshot = self._analyzer.analyze_latest([_to_kis_daily_price(b) for b in bars])
        if snapshot is None:
            return None

        self._indicators.upsert(
            symbol=snapshot.symbol,
            indicator_date=snapshot.date,
            ma5=snapshot.ma5,
            ma20=snapshot.ma20,
            ma60=snapshot.ma60,
            ma120=snapshot.ma120,
            rsi14=snapshot.rsi14,
            macd=snapshot.macd,
            macd_signal=snapshot.macd_signal,
            volume_ratio_20d=snapshot.volume_ratio_20d,
            breakout_20d=snapshot.breakout_20d,
            breakout_60d=snapshot.breakout_60d,
            ma_alignment=snapshot.ma_alignment,
            technical_score=snapshot.technical_score,
            atr14=snapshot.atr14,
            candle_patterns=snapshot.candle_patterns,
            volatility_band=snapshot.volatility_band,
        )
        return snapshot

    def analyze_and_store_many(
        self,
        symbols: Iterable[str],
        *,
        lookback_days: int | None = None,
    ) -> list[IndicatorSnapshot]:
        results: list[IndicatorSnapshot] = []
        for symbol in symbols:
            snapshot = self.analyze_and_store(symbol, lookback_days=lookback_days)
            if snapshot is not None:
                results.append(snapshot)
        return results
