"""Pure technical indicator calculator over a sequence of daily price bars.

Analysis-layer boundary: no external API calls, no DB writes, no recommendation
or holding-check logic, no AI/broker/notification dependencies. Inputs are
normalized daily price DTOs; outputs are ``IndicatorSnapshot`` instances shaped
to be persisted into the ``stock_indicators`` table by a future Phase 4-2 service.

Indicators implemented:
    MA5 / MA20 / MA60 / MA120 (simple moving average of close)
    RSI14 (Wilder smoothing)
    MACD = EMA12(close) - EMA26(close), signal = EMA9(MACD)
    volume_ratio_20d = volume[t] / mean(volume[t-20..t-1])
    breakout_20d / breakout_60d = close[t] > max(high[t-N..t-1])
    ma_alignment ∈ {PERFECT_BULL, BULL, RECOVER, MIXED, BEAR, PERFECT_BEAR}
    technical_score (0..100) aggregating the indicators above

When the input series is too short to compute an indicator, that indicator is
returned as ``None``. ``technical_score`` defaults to ``Decimal("0")`` and
accumulates whatever components are available.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from decimal import ROUND_HALF_UP, Decimal

from app.data.dtos import KisDailyPrice


_PRICE_QUANT = Decimal("0.0001")
_RATIO_QUANT = Decimal("0.0001")
_SCORE_QUANT = Decimal("0.0001")

MA_ALIGNMENT_PERFECT_BULL = "PERFECT_BULL"
MA_ALIGNMENT_BULL = "BULL"
MA_ALIGNMENT_RECOVER = "RECOVER"
MA_ALIGNMENT_MIXED = "MIXED"
MA_ALIGNMENT_BEAR = "BEAR"
MA_ALIGNMENT_PERFECT_BEAR = "PERFECT_BEAR"

# v0.3 Phase B: candle patterns + ATR-derived volatility band.
# Patterns are detected on the most recent bar (engulfing also needs the prior
# bar). ATR(14) uses Wilder smoothing of true range; volatility band is
# computed against the latest close so the scoring layer never deals with raw
# price units.
CANDLE_DOJI = "DOJI"
CANDLE_HAMMER = "HAMMER"
CANDLE_SHOOTING_STAR = "SHOOTING_STAR"
CANDLE_BULLISH_ENGULFING = "BULLISH_ENGULFING"
CANDLE_BEARISH_ENGULFING = "BEARISH_ENGULFING"

VOLATILITY_LOW = "LOW"
VOLATILITY_NORMAL = "NORMAL"
VOLATILITY_HIGH = "HIGH"
VOLATILITY_EXTREME = "EXTREME"


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Indicator values for a single (symbol, date) ready to persist."""

    symbol: str
    date: date_type
    ma5: Decimal | None
    ma20: Decimal | None
    ma60: Decimal | None
    ma120: Decimal | None
    rsi14: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    volume_ratio_20d: Decimal | None
    breakout_20d: bool | None
    breakout_60d: bool | None
    ma_alignment: str | None
    technical_score: Decimal | None
    # v0.3 Phase B — defaulted so the existing positional / keyword tests
    # constructing IndicatorSnapshot keep working.
    atr14: Decimal | None = None
    candle_patterns: list[str] | None = None
    volatility_band: str | None = None


def _quantize(value: Decimal | None, quant: Decimal) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def simple_moving_average(closes: Sequence[Decimal], period: int) -> Decimal | None:
    if period <= 0 or len(closes) < period:
        return None
    window = closes[-period:]
    total = sum(window, Decimal("0"))
    return total / Decimal(period)


def exponential_moving_average(
    values: Sequence[Decimal],
    period: int,
) -> list[Decimal] | None:
    """EMA series bootstrapped with SMA of the first ``period`` values.

    The returned list has length ``len(values) - period + 1`` and aligns with
    the suffix of ``values`` starting at index ``period - 1``.
    """
    if period <= 0 or len(values) < period:
        return None
    seed = sum(values[:period], Decimal("0")) / Decimal(period)
    alpha = Decimal("2") / Decimal(period + 1)
    one_minus_alpha = Decimal("1") - alpha
    series = [seed]
    for i in range(period, len(values)):
        prev = series[-1]
        current = values[i]
        series.append(current * alpha + prev * one_minus_alpha)
    return series


def relative_strength_index(closes: Sequence[Decimal], period: int = 14) -> Decimal | None:
    """Wilder's RSI for the most recent bar."""
    if period <= 0 or len(closes) < period + 1:
        return None

    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(Decimal("0"))
        else:
            gains.append(Decimal("0"))
            losses.append(-diff)

    avg_gain = sum(gains[:period], Decimal("0")) / Decimal(period)
    avg_loss = sum(losses[:period], Decimal("0")) / Decimal(period)

    period_minus_one = Decimal(period - 1)
    period_dec = Decimal(period)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * period_minus_one + gains[i]) / period_dec
        avg_loss = (avg_loss * period_minus_one + losses[i]) / period_dec

    if avg_loss == 0:
        if avg_gain == 0:
            return Decimal("50")
        return Decimal("100")

    rs = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))


def compute_macd(
    closes: Sequence[Decimal],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[Decimal | None, Decimal | None]:
    """Return (macd, macd_signal) for the most recent bar.

    ``(None, None)`` if there are fewer than ``slow_period`` closes.
    ``(macd, None)`` if the MACD series is shorter than ``signal_period``.
    """
    if len(closes) < slow_period:
        return None, None

    fast_series = exponential_moving_average(closes, fast_period)
    slow_series = exponential_moving_average(closes, slow_period)
    if fast_series is None or slow_series is None:
        return None, None

    aligned_fast = fast_series[-len(slow_series):]
    macd_series = [f - s for f, s in zip(aligned_fast, slow_series)]
    macd_value = macd_series[-1]

    if len(macd_series) < signal_period:
        return macd_value, None

    signal_series = exponential_moving_average(macd_series, signal_period)
    if signal_series is None:
        return macd_value, None
    return macd_value, signal_series[-1]


def compute_volume_ratio_20d(volumes: Sequence[int], period: int = 20) -> Decimal | None:
    """today's volume / mean(prior ``period`` volumes, excluding today)."""
    if period <= 0 or len(volumes) < period + 1:
        return None
    prior_window = volumes[-(period + 1):-1]
    avg = Decimal(sum(prior_window)) / Decimal(period)
    if avg == 0:
        return None
    return Decimal(volumes[-1]) / avg


def compute_breakout(
    highs: Sequence[Decimal],
    period: int,
    today_close: Decimal,
) -> bool | None:
    """True if ``today_close`` exceeds max of prior ``period`` highs (excluding today)."""
    if period <= 0 or len(highs) < period + 1:
        return None
    prior_window = highs[-(period + 1):-1]
    return today_close > max(prior_window)


def classify_ma_alignment(
    *,
    close: Decimal | None,
    ma5: Decimal | None,
    ma20: Decimal | None,
    ma60: Decimal | None,
    ma120: Decimal | None,
) -> str | None:
    if ma5 is None or ma20 is None or ma60 is None:
        return None

    if ma5 > ma20 > ma60:
        if ma120 is not None and ma60 > ma120:
            return MA_ALIGNMENT_PERFECT_BULL
        return MA_ALIGNMENT_BULL

    if ma5 < ma20 < ma60:
        if ma120 is not None and ma60 < ma120:
            return MA_ALIGNMENT_PERFECT_BEAR
        return MA_ALIGNMENT_BEAR

    if close is not None and close > ma20 and ma20 < ma60:
        return MA_ALIGNMENT_RECOVER

    return MA_ALIGNMENT_MIXED


def compute_atr14(
    bars: Sequence[KisDailyPrice],
    period: int = 14,
) -> Decimal | None:
    """Wilder's ATR over the last ``period`` bars.

    Needs ``period + 1`` bars (period TR values + the prior close used by the
    first TR). Returns ``None`` if too short. Unsorted input is sorted by date.
    """
    if period <= 0 or len(bars) < period + 1:
        return None
    ordered = sorted(bars, key=lambda b: b.date)

    trs: list[Decimal] = []
    for i in range(1, len(ordered)):
        bar = ordered[i]
        prev_close = ordered[i - 1].close
        tr = max(
            bar.high - bar.low,
            abs(bar.high - prev_close),
            abs(bar.low - prev_close),
        )
        trs.append(tr)

    if len(trs) < period:
        return None

    initial = sum(trs[:period], Decimal("0")) / Decimal(period)
    atr = initial
    period_minus_one = Decimal(period - 1)
    period_dec = Decimal(period)
    for i in range(period, len(trs)):
        atr = (atr * period_minus_one + trs[i]) / period_dec
    return atr


def _body(bar: KisDailyPrice) -> Decimal:
    return abs(bar.close - bar.open)


def _range(bar: KisDailyPrice) -> Decimal:
    return bar.high - bar.low


def _upper_shadow(bar: KisDailyPrice) -> Decimal:
    return bar.high - max(bar.open, bar.close)


def _lower_shadow(bar: KisDailyPrice) -> Decimal:
    return min(bar.open, bar.close) - bar.low


def detect_doji(
    bar: KisDailyPrice,
    body_pct_of_close: Decimal = Decimal("0.1"),
) -> bool:
    """True when the body is at most ``body_pct_of_close`` % of the close.

    A flat bar (open==close) qualifies as DOJI; downstream scoring treats DOJI
    as 0-bonus so it is informational only.
    """
    if bar.close <= 0:
        return False
    return _body(bar) <= bar.close * body_pct_of_close / Decimal("100")


def detect_hammer(bar: KisDailyPrice) -> bool:
    """Small body near the top of the range, lower shadow >= 2 * body.

    Requires a non-zero body and range so flat bars never trigger.
    """
    rng = _range(bar)
    body = _body(bar)
    if rng == 0 or body == 0:
        return False
    upper = _upper_shadow(bar)
    lower = _lower_shadow(bar)
    return (
        body / rng <= Decimal("0.34")
        and lower >= body * Decimal("2")
        and upper <= body
    )


def detect_shooting_star(bar: KisDailyPrice) -> bool:
    """Mirror of hammer: small body near the bottom, upper shadow >= 2 * body."""
    rng = _range(bar)
    body = _body(bar)
    if rng == 0 or body == 0:
        return False
    upper = _upper_shadow(bar)
    lower = _lower_shadow(bar)
    return (
        body / rng <= Decimal("0.34")
        and upper >= body * Decimal("2")
        and lower <= body
    )


def detect_bullish_engulfing(prev: KisDailyPrice, curr: KisDailyPrice) -> bool:
    """Prev bar is bearish (close < open), current bar is bullish (close > open),
    and the current body engulfs the prior body (open <= prev.close and
    close >= prev.open).
    """
    if prev.close >= prev.open:
        return False
    if curr.close <= curr.open:
        return False
    return curr.open <= prev.close and curr.close >= prev.open


def detect_bearish_engulfing(prev: KisDailyPrice, curr: KisDailyPrice) -> bool:
    if prev.close <= prev.open:
        return False
    if curr.close >= curr.open:
        return False
    return curr.open >= prev.close and curr.close <= prev.open


def detect_candle_patterns(bars: Sequence[KisDailyPrice]) -> list[str]:
    """Return all candle patterns triggered on the most recent bar.

    Engulfing patterns also use the prior bar; if only one bar is available,
    only single-bar patterns can fire. Empty input → empty list.
    """
    if not bars:
        return []
    ordered = sorted(bars, key=lambda b: b.date)
    last = ordered[-1]
    patterns: list[str] = []

    if detect_doji(last):
        patterns.append(CANDLE_DOJI)
    if detect_hammer(last):
        patterns.append(CANDLE_HAMMER)
    if detect_shooting_star(last):
        patterns.append(CANDLE_SHOOTING_STAR)
    if len(ordered) >= 2:
        prev = ordered[-2]
        if detect_bullish_engulfing(prev, last):
            patterns.append(CANDLE_BULLISH_ENGULFING)
        if detect_bearish_engulfing(prev, last):
            patterns.append(CANDLE_BEARISH_ENGULFING)
    return patterns


def classify_volatility(
    atr14: Decimal | None,
    latest_close: Decimal | None,
) -> str | None:
    """Map ATR(14) / close ratio into a 4-step volatility band.

    LOW < 1% < NORMAL < 3% < HIGH < 5% <= EXTREME. Returns ``None`` when ATR
    or close is unavailable so the scoring layer contributes 0.
    """
    if atr14 is None or latest_close is None or latest_close <= 0:
        return None
    pct = atr14 / latest_close * Decimal("100")
    if pct < Decimal("1"):
        return VOLATILITY_LOW
    if pct < Decimal("3"):
        return VOLATILITY_NORMAL
    if pct < Decimal("5"):
        return VOLATILITY_HIGH
    return VOLATILITY_EXTREME


_CANDLE_BONUS: dict[str, Decimal] = {
    CANDLE_BULLISH_ENGULFING: Decimal("5"),
    CANDLE_HAMMER: Decimal("3"),
    CANDLE_DOJI: Decimal("0"),
    CANDLE_SHOOTING_STAR: Decimal("-3"),
    CANDLE_BEARISH_ENGULFING: Decimal("-5"),
}

_VOLATILITY_BONUS: dict[str, Decimal] = {
    VOLATILITY_LOW: Decimal("2"),
    VOLATILITY_NORMAL: Decimal("0"),
    VOLATILITY_HIGH: Decimal("-3"),
    VOLATILITY_EXTREME: Decimal("-5"),
}


def _candle_bonus(patterns: list[str] | None) -> Decimal:
    if not patterns:
        return Decimal("0")
    bonus = sum((_CANDLE_BONUS.get(p, Decimal("0")) for p in patterns), Decimal("0"))
    # 보수적 cap — 다중 패턴이 동시에 잡혀도 영향이 ±5 점 이내로 제한
    if bonus > Decimal("5"):
        return Decimal("5")
    if bonus < Decimal("-5"):
        return Decimal("-5")
    return bonus


def _volatility_bonus(band: str | None) -> Decimal:
    return _VOLATILITY_BONUS.get(band or "", Decimal("0"))


def calculate_technical_score(
    *,
    ma_alignment: str | None,
    volume_ratio_20d: Decimal | None,
    breakout_20d: bool | None,
    breakout_60d: bool | None,
    rsi14: Decimal | None,
    macd_value: Decimal | None,
    macd_signal: Decimal | None,
    candle_patterns: list[str] | None = None,
    volatility_band: str | None = None,
) -> Decimal:
    """Aggregate available indicators into a 0..100 technical score.

    Base components (sum to 100 when all components score top):
        MA trend ......... 30
        Volume ratio ..... 25
        Breakout ......... 25
        Momentum ......... 20  (RSI sweet spot 10 + MACD positive cross 10)

    v0.3 Phase B booster/penalty (clamped to 0..100 after addition):
        Candle patterns .. ±5  (BULLISH_ENGULFING +5, HAMMER +3, DOJI 0,
                                SHOOTING_STAR -3, BEARISH_ENGULFING -5; sum
                                capped at ±5)
        Volatility band .. +2 / 0 / -3 / -5  (LOW / NORMAL / HIGH / EXTREME)

    Both Phase B components default to 0 when input is None so existing call
    sites remain numerically unchanged.
    """
    score = Decimal("0")

    score += {
        MA_ALIGNMENT_PERFECT_BULL: Decimal("30"),
        MA_ALIGNMENT_BULL: Decimal("22"),
        MA_ALIGNMENT_RECOVER: Decimal("15"),
        MA_ALIGNMENT_MIXED: Decimal("10"),
        MA_ALIGNMENT_BEAR: Decimal("5"),
        MA_ALIGNMENT_PERFECT_BEAR: Decimal("0"),
    }.get(ma_alignment or "", Decimal("0"))

    if volume_ratio_20d is not None:
        if volume_ratio_20d >= Decimal("3.0"):
            score += Decimal("25")
        elif volume_ratio_20d >= Decimal("2.0"):
            score += Decimal("20")
        elif volume_ratio_20d >= Decimal("1.5"):
            score += Decimal("15")
        elif volume_ratio_20d >= Decimal("1.2"):
            score += Decimal("10")
        elif volume_ratio_20d >= Decimal("1.0"):
            score += Decimal("5")

    if breakout_60d:
        score += Decimal("25")
    elif breakout_20d:
        score += Decimal("15")

    if rsi14 is not None:
        if Decimal("50") <= rsi14 <= Decimal("70"):
            score += Decimal("10")
        elif Decimal("40") <= rsi14 < Decimal("50"):
            score += Decimal("5")
        elif Decimal("30") <= rsi14 < Decimal("40"):
            score += Decimal("2")

    if macd_value is not None and macd_signal is not None and macd_value > macd_signal:
        score += Decimal("10")

    # v0.3 Phase B booster/penalty layer
    score += _candle_bonus(candle_patterns)
    score += _volatility_bonus(volatility_band)

    if score < Decimal("0"):
        return Decimal("0")
    if score > Decimal("100"):
        return Decimal("100")
    return score


class TechnicalAnalyzer:
    """Turn a sequence of daily price bars into one IndicatorSnapshot.

    The analyzer is a pure function holder: no DB session, no HTTP client, no
    side effects. Bars are sorted by date internally; the snapshot is computed
    against the most recent bar.
    """

    def analyze_latest(self, bars: Sequence[KisDailyPrice]) -> IndicatorSnapshot | None:
        if not bars:
            return None

        ordered = sorted(bars, key=lambda b: b.date)
        last = ordered[-1]

        closes = [b.close for b in ordered]
        highs = [b.high for b in ordered]
        volumes = [b.volume for b in ordered]

        ma5 = simple_moving_average(closes, 5)
        ma20 = simple_moving_average(closes, 20)
        ma60 = simple_moving_average(closes, 60)
        ma120 = simple_moving_average(closes, 120)

        rsi14 = relative_strength_index(closes, 14)
        macd_value, macd_signal_value = compute_macd(closes)

        volume_ratio = compute_volume_ratio_20d(volumes, 20)

        breakout20 = compute_breakout(highs, 20, last.close)
        breakout60 = compute_breakout(highs, 60, last.close)

        ma_alignment = classify_ma_alignment(
            close=last.close,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            ma120=ma120,
        )

        # v0.3 Phase B: candle patterns + ATR(14) + volatility band
        atr14_value = compute_atr14(ordered, period=14)
        candle_patterns = detect_candle_patterns(ordered)
        volatility_band = classify_volatility(atr14_value, last.close)

        score = calculate_technical_score(
            ma_alignment=ma_alignment,
            volume_ratio_20d=volume_ratio,
            breakout_20d=breakout20,
            breakout_60d=breakout60,
            rsi14=rsi14,
            macd_value=macd_value,
            macd_signal=macd_signal_value,
            candle_patterns=candle_patterns or None,
            volatility_band=volatility_band,
        )

        return IndicatorSnapshot(
            symbol=last.symbol,
            date=last.date,
            ma5=_quantize(ma5, _PRICE_QUANT),
            ma20=_quantize(ma20, _PRICE_QUANT),
            ma60=_quantize(ma60, _PRICE_QUANT),
            ma120=_quantize(ma120, _PRICE_QUANT),
            rsi14=_quantize(rsi14, _RATIO_QUANT),
            macd=_quantize(macd_value, _PRICE_QUANT),
            macd_signal=_quantize(macd_signal_value, _PRICE_QUANT),
            volume_ratio_20d=_quantize(volume_ratio, _RATIO_QUANT),
            breakout_20d=breakout20,
            breakout_60d=breakout60,
            ma_alignment=ma_alignment,
            technical_score=_quantize(score, _SCORE_QUANT),
            atr14=_quantize(atr14_value, _PRICE_QUANT),
            candle_patterns=(candle_patterns or None),
            volatility_band=volatility_band,
        )
