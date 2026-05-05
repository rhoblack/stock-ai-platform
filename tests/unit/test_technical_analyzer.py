from datetime import date, timedelta
from decimal import Decimal

from app.analysis.technical_analyzer import (
    MA_ALIGNMENT_BEAR,
    MA_ALIGNMENT_BULL,
    MA_ALIGNMENT_MIXED,
    MA_ALIGNMENT_PERFECT_BEAR,
    MA_ALIGNMENT_PERFECT_BULL,
    MA_ALIGNMENT_RECOVER,
    TechnicalAnalyzer,
    calculate_technical_score,
    classify_ma_alignment,
    compute_breakout,
    compute_macd,
    compute_volume_ratio_20d,
    relative_strength_index,
    simple_moving_average,
)
from app.data.dtos import KisDailyPrice


def _bars(
    closes: list[Decimal],
    *,
    highs: list[Decimal] | None = None,
    volumes: list[int] | None = None,
    symbol: str = "005930",
    start: date = date(2026, 1, 1),
) -> list[KisDailyPrice]:
    n = len(closes)
    highs = highs if highs is not None else closes
    volumes = volumes if volumes is not None else [1_000_000] * n
    return [
        KisDailyPrice(
            symbol=symbol,
            date=start + timedelta(days=i),
            open=closes[i],
            high=highs[i],
            low=closes[i],
            close=closes[i],
            volume=volumes[i],
        )
        for i in range(n)
    ]


# ---------- moving averages ----------

def test_simple_moving_average_returns_none_when_below_period():
    closes = [Decimal("100")] * 4
    assert simple_moving_average(closes, 5) is None


def test_simple_moving_average_uses_only_last_period_values():
    closes = [Decimal(str(v)) for v in [10, 20, 30, 1, 2, 3, 4, 5]]
    # last 5 = [2, 3, 4, 5] wait, only 4. actually last 5 of 8-element list = [1,2,3,4,5]
    assert simple_moving_average(closes, 5) == Decimal("3")


# ---------- RSI ----------

def test_rsi_returns_none_below_period_plus_one():
    closes = [Decimal("100")] * 5
    assert relative_strength_index(closes, 14) is None


def test_rsi_strong_uptrend_above_70():
    closes = [Decimal(str(100 + i)) for i in range(20)]
    rsi = relative_strength_index(closes, 14)
    assert rsi is not None
    assert rsi > Decimal("70")


def test_rsi_strong_downtrend_below_30():
    closes = [Decimal(str(100 - i)) for i in range(20)]
    rsi = relative_strength_index(closes, 14)
    assert rsi is not None
    assert rsi < Decimal("30")


def test_rsi_flat_series_returns_50():
    closes = [Decimal("100")] * 20
    assert relative_strength_index(closes, 14) == Decimal("50")


# ---------- MACD ----------

def test_macd_returns_none_below_slow_period():
    closes = [Decimal("100")] * 20
    macd_v, signal = compute_macd(closes)
    assert macd_v is None
    assert signal is None


def test_macd_uptrend_macd_and_signal_positive():
    # Linear growth converges MACD and signal both to a positive constant (~7),
    # so don't assert macd > signal here.
    closes = [Decimal(str(100 + i)) for i in range(40)]
    macd_v, signal = compute_macd(closes)
    assert macd_v is not None and signal is not None
    assert macd_v > Decimal("0")
    assert signal > Decimal("0")
    assert macd_v >= signal


def test_macd_signal_lags_macd_during_recent_acceleration():
    # Flat phase then steep rise: MACD jumps up while EMA9(MACD) signal still trails.
    closes = [Decimal("100")] * 26 + [Decimal(str(100 + (i + 1) * 5)) for i in range(15)]
    macd_v, signal = compute_macd(closes)
    assert macd_v is not None and signal is not None
    assert macd_v > signal


def test_macd_returns_value_but_no_signal_when_macd_series_short():
    # 26 closes -> macd_series length = 1, signal needs 9 -> signal None
    closes = [Decimal(str(100 + i)) for i in range(26)]
    macd_v, signal = compute_macd(closes)
    assert macd_v is not None
    assert signal is None


# ---------- volume ratio ----------

def test_volume_ratio_returns_none_when_only_period_bars():
    volumes = [1_000_000] * 20
    assert compute_volume_ratio_20d(volumes, 20) is None


def test_volume_ratio_today_double_prior_average():
    volumes = [1_000_000] * 20 + [2_000_000]
    assert compute_volume_ratio_20d(volumes, 20) == Decimal("2")


def test_volume_ratio_returns_none_when_prior_average_is_zero():
    volumes = [0] * 20 + [1_000_000]
    assert compute_volume_ratio_20d(volumes, 20) is None


# ---------- breakout ----------

def test_breakout_true_when_close_exceeds_prior_max():
    highs = [Decimal("100")] * 20 + [Decimal("110")]
    assert compute_breakout(highs, 20, Decimal("105")) is True


def test_breakout_false_when_close_at_or_below_prior_max():
    highs = [Decimal("100")] * 20 + [Decimal("90")]
    assert compute_breakout(highs, 20, Decimal("100")) is False
    assert compute_breakout(highs, 20, Decimal("90")) is False


def test_breakout_returns_none_when_not_enough_history():
    highs = [Decimal("100")] * 19
    assert compute_breakout(highs, 20, Decimal("110")) is None


# ---------- ma alignment ----------

def test_ma_alignment_perfect_bull_requires_ma120():
    assert classify_ma_alignment(
        close=Decimal("110"),
        ma5=Decimal("105"),
        ma20=Decimal("100"),
        ma60=Decimal("95"),
        ma120=Decimal("90"),
    ) == MA_ALIGNMENT_PERFECT_BULL


def test_ma_alignment_bull_when_ma120_missing():
    assert classify_ma_alignment(
        close=Decimal("110"),
        ma5=Decimal("105"),
        ma20=Decimal("100"),
        ma60=Decimal("95"),
        ma120=None,
    ) == MA_ALIGNMENT_BULL


def test_ma_alignment_perfect_bear():
    assert classify_ma_alignment(
        close=Decimal("90"),
        ma5=Decimal("90"),
        ma20=Decimal("95"),
        ma60=Decimal("100"),
        ma120=Decimal("105"),
    ) == MA_ALIGNMENT_PERFECT_BEAR


def test_ma_alignment_bear_when_ma120_missing():
    assert classify_ma_alignment(
        close=Decimal("90"),
        ma5=Decimal("90"),
        ma20=Decimal("95"),
        ma60=Decimal("100"),
        ma120=None,
    ) == MA_ALIGNMENT_BEAR


def test_ma_alignment_recover_when_close_above_ma20_but_ma20_below_ma60():
    assert classify_ma_alignment(
        close=Decimal("105"),
        ma5=Decimal("100"),
        ma20=Decimal("100"),
        ma60=Decimal("110"),
        ma120=None,
    ) == MA_ALIGNMENT_RECOVER


def test_ma_alignment_mixed_when_no_clear_pattern():
    assert classify_ma_alignment(
        close=Decimal("95"),
        ma5=Decimal("100"),
        ma20=Decimal("100"),
        ma60=Decimal("100"),
        ma120=None,
    ) == MA_ALIGNMENT_MIXED


def test_ma_alignment_none_when_required_ma_missing():
    assert classify_ma_alignment(
        close=Decimal("110"),
        ma5=Decimal("100"),
        ma20=None,
        ma60=Decimal("100"),
        ma120=None,
    ) is None


# ---------- technical_score ----------

def test_calculate_technical_score_perfect_setup_hits_100():
    score = calculate_technical_score(
        ma_alignment=MA_ALIGNMENT_PERFECT_BULL,
        volume_ratio_20d=Decimal("3.5"),
        breakout_20d=True,
        breakout_60d=True,
        rsi14=Decimal("60"),
        macd_value=Decimal("1.5"),
        macd_signal=Decimal("0.5"),
    )
    # 30 + 25 + 25 (60d wins over 20d) + 10 (RSI sweet) + 10 (MACD>signal)
    assert score == Decimal("100")


def test_calculate_technical_score_zero_when_all_inputs_none():
    score = calculate_technical_score(
        ma_alignment=None,
        volume_ratio_20d=None,
        breakout_20d=None,
        breakout_60d=None,
        rsi14=None,
        macd_value=None,
        macd_signal=None,
    )
    assert score == Decimal("0")


def test_calculate_technical_score_perfect_bear_breakout_fail():
    score = calculate_technical_score(
        ma_alignment=MA_ALIGNMENT_PERFECT_BEAR,
        volume_ratio_20d=Decimal("0.5"),
        breakout_20d=False,
        breakout_60d=False,
        rsi14=Decimal("20"),
        macd_value=Decimal("-1.0"),
        macd_signal=Decimal("-0.5"),
    )
    # 0 (MA) + 0 (volume<1) + 0 (no breakout) + 0 (RSI<30) + 0 (MACD<signal)
    assert score == Decimal("0")


def test_calculate_technical_score_breakout60_supersedes_breakout20():
    base = dict(
        ma_alignment=MA_ALIGNMENT_BULL,
        volume_ratio_20d=Decimal("1.0"),
        rsi14=Decimal("55"),
        macd_value=Decimal("1.0"),
        macd_signal=Decimal("0.5"),
    )
    only20 = calculate_technical_score(breakout_20d=True, breakout_60d=False, **base)
    both = calculate_technical_score(breakout_20d=True, breakout_60d=True, **base)
    assert both - only20 == Decimal("10")  # 25 - 15 = 10


# ---------- TechnicalAnalyzer integration ----------

def test_technical_analyzer_returns_none_for_empty_bars():
    assert TechnicalAnalyzer().analyze_latest([]) is None


def test_technical_analyzer_short_history_returns_safe_nones():
    snapshot = TechnicalAnalyzer().analyze_latest(_bars([Decimal("100")] * 4))
    assert snapshot is not None
    assert snapshot.ma5 is None
    assert snapshot.ma20 is None
    assert snapshot.ma60 is None
    assert snapshot.ma120 is None
    assert snapshot.rsi14 is None
    assert snapshot.macd is None
    assert snapshot.macd_signal is None
    assert snapshot.volume_ratio_20d is None
    assert snapshot.breakout_20d is None
    assert snapshot.breakout_60d is None
    assert snapshot.ma_alignment is None
    assert snapshot.technical_score == Decimal("0.0000")


def test_technical_analyzer_full_history_perfect_bull_uptrend():
    closes = [Decimal(str(100 + i)) for i in range(130)]
    volumes = [1_000_000] * 129 + [3_500_000]
    snapshot = TechnicalAnalyzer().analyze_latest(_bars(closes, volumes=volumes))

    assert snapshot is not None
    assert snapshot.symbol == "005930"
    assert snapshot.date == date(2026, 1, 1) + timedelta(days=129)
    assert snapshot.ma5 is not None
    assert snapshot.ma20 is not None
    assert snapshot.ma60 is not None
    assert snapshot.ma120 is not None
    assert snapshot.rsi14 is not None
    assert snapshot.macd is not None
    assert snapshot.macd_signal is not None
    assert snapshot.volume_ratio_20d is not None
    assert snapshot.volume_ratio_20d >= Decimal("3.0")
    assert snapshot.breakout_20d is True
    assert snapshot.breakout_60d is True
    assert snapshot.ma_alignment == MA_ALIGNMENT_PERFECT_BULL
    # MA(30) + Volume(25) + Breakout60(25) + MACD>signal(10) = 90; RSI saturates at 100 => no points
    assert snapshot.technical_score >= Decimal("80")


def test_technical_analyzer_sorts_unordered_bars_by_date():
    closes = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"), Decimal("140")]
    bars = _bars(closes)
    shuffled = [bars[2], bars[0], bars[4], bars[1], bars[3]]

    snapshot = TechnicalAnalyzer().analyze_latest(shuffled)

    assert snapshot is not None
    assert snapshot.date == bars[-1].date
    assert snapshot.ma5 == Decimal("120.0000")  # mean(100, 110, 120, 130, 140)


def test_technical_analyzer_indicator_snapshot_quantizes_to_four_decimals():
    closes = [Decimal(str(100 + i)) for i in range(30)]
    snapshot = TechnicalAnalyzer().analyze_latest(_bars(closes))
    assert snapshot is not None
    assert snapshot.ma20 is not None
    # last 20 closes are 110..129, mean = (110 + 129) / 2 = 119.5
    assert snapshot.ma20 == Decimal("119.5000")


# ---------- v0.3 Phase B: ATR(14) + candle patterns + volatility ----------

from app.analysis.technical_analyzer import (  # noqa: E402  (intentional grouping)
    CANDLE_BEARISH_ENGULFING,
    CANDLE_BULLISH_ENGULFING,
    CANDLE_DOJI,
    CANDLE_HAMMER,
    CANDLE_SHOOTING_STAR,
    VOLATILITY_EXTREME,
    VOLATILITY_HIGH,
    VOLATILITY_LOW,
    VOLATILITY_NORMAL,
    classify_volatility,
    compute_atr14,
    detect_bearish_engulfing,
    detect_bullish_engulfing,
    detect_candle_patterns,
    detect_doji,
    detect_hammer,
    detect_shooting_star,
)


def _ohlc_bar(
    *,
    open_: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    bar_date: date = date(2026, 1, 1),
    symbol: str = "005930",
    volume: int = 1_000_000,
) -> KisDailyPrice:
    return KisDailyPrice(
        symbol=symbol,
        date=bar_date,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_compute_atr14_returns_none_when_too_short():
    assert compute_atr14(_bars([Decimal("100")] * 14)) is None  # 14 bars → only 13 TRs
    assert compute_atr14([]) is None


def test_compute_atr14_constant_step_uptrend():
    # All bars: open=high=low=close=100+i. TR_i = |close_i - close_{i-1}| = 1.
    # ATR(14) = 1.
    closes = [Decimal(str(100 + i)) for i in range(20)]
    bars = _bars(closes)
    atr = compute_atr14(bars, period=14)
    assert atr == Decimal("1")


def test_detect_doji_flat_bar_qualifies():
    bar = _ohlc_bar(open_=Decimal("100"), high=Decimal("100"), low=Decimal("100"), close=Decimal("100"))
    assert detect_doji(bar) is True


def test_detect_doji_large_body_does_not_qualify():
    # body = 2 (2% of 100) > threshold 0.1%
    bar = _ohlc_bar(open_=Decimal("100"), high=Decimal("103"), low=Decimal("99"), close=Decimal("102"))
    assert detect_doji(bar) is False


def test_detect_hammer_long_lower_shadow_small_body():
    # body=0.5 (close-open), lower shadow=4 (>=2*body), upper shadow≈0
    bar = _ohlc_bar(open_=Decimal("100"), high=Decimal("100.5"), low=Decimal("96"), close=Decimal("100.5"))
    assert detect_hammer(bar) is True
    assert detect_shooting_star(bar) is False


def test_detect_shooting_star_long_upper_shadow_small_body():
    bar = _ohlc_bar(open_=Decimal("100"), high=Decimal("104"), low=Decimal("99.5"), close=Decimal("99.5"))
    assert detect_shooting_star(bar) is True
    assert detect_hammer(bar) is False


def test_detect_bullish_engulfing_pair():
    prev = _ohlc_bar(open_=Decimal("105"), high=Decimal("105"), low=Decimal("100"), close=Decimal("100"))  # bearish
    curr = _ohlc_bar(open_=Decimal("99"), high=Decimal("108"), low=Decimal("99"), close=Decimal("107"))  # bullish, engulfs
    assert detect_bullish_engulfing(prev, curr) is True
    assert detect_bearish_engulfing(prev, curr) is False


def test_detect_bearish_engulfing_pair():
    prev = _ohlc_bar(open_=Decimal("100"), high=Decimal("105"), low=Decimal("100"), close=Decimal("105"))  # bullish
    curr = _ohlc_bar(open_=Decimal("106"), high=Decimal("106"), low=Decimal("98"), close=Decimal("99"))  # bearish, engulfs
    assert detect_bearish_engulfing(prev, curr) is True
    assert detect_bullish_engulfing(prev, curr) is False


def test_detect_candle_patterns_aggregates_doji_only_when_flat():
    flat = [_ohlc_bar(open_=Decimal("100"), high=Decimal("100"), low=Decimal("100"), close=Decimal("100"))]
    patterns = detect_candle_patterns(flat)
    assert patterns == [CANDLE_DOJI]


def test_detect_candle_patterns_engulfing_uses_prior_bar():
    prev = _ohlc_bar(
        open_=Decimal("105"), high=Decimal("105"), low=Decimal("100"), close=Decimal("100"),
        bar_date=date(2026, 1, 1),
    )
    curr = _ohlc_bar(
        open_=Decimal("99"), high=Decimal("108"), low=Decimal("99"), close=Decimal("107"),
        bar_date=date(2026, 1, 2),
    )
    patterns = detect_candle_patterns([prev, curr])
    assert CANDLE_BULLISH_ENGULFING in patterns


def test_classify_volatility_bands():
    close = Decimal("100")
    assert classify_volatility(Decimal("0.5"), close) == VOLATILITY_LOW
    assert classify_volatility(Decimal("2"), close) == VOLATILITY_NORMAL
    assert classify_volatility(Decimal("4"), close) == VOLATILITY_HIGH
    assert classify_volatility(Decimal("6"), close) == VOLATILITY_EXTREME
    assert classify_volatility(None, close) is None
    assert classify_volatility(Decimal("1"), None) is None
    assert classify_volatility(Decimal("1"), Decimal("0")) is None


def test_calculate_technical_score_clamps_above_100_with_bullish_booster():
    """Perfect setup (100점) + BULLISH_ENGULFING (+5) + LOW vol (+2) → clamp 100."""
    score = calculate_technical_score(
        ma_alignment=MA_ALIGNMENT_PERFECT_BULL,
        volume_ratio_20d=Decimal("3.5"),
        breakout_20d=True,
        breakout_60d=True,
        rsi14=Decimal("60"),
        macd_value=Decimal("1.5"),
        macd_signal=Decimal("0.5"),
        candle_patterns=[CANDLE_BULLISH_ENGULFING],
        volatility_band=VOLATILITY_LOW,
    )
    assert score == Decimal("100")


def test_calculate_technical_score_floor_zero_with_bearish_setup():
    score = calculate_technical_score(
        ma_alignment=MA_ALIGNMENT_PERFECT_BEAR,
        volume_ratio_20d=Decimal("0.5"),
        breakout_20d=False,
        breakout_60d=False,
        rsi14=Decimal("20"),
        macd_value=Decimal("-1.0"),
        macd_signal=Decimal("-0.5"),
        candle_patterns=[CANDLE_SHOOTING_STAR, CANDLE_BEARISH_ENGULFING],
        volatility_band=VOLATILITY_EXTREME,
    )
    assert score == Decimal("0")


def test_calculate_technical_score_mid_range_picks_up_hammer_bonus():
    """Mid setup (BULL + 1.0 vol + breakout20 + RSI 55 + MACD>signal) = 22+5+15+10+10 = 62.
    + HAMMER (+3) → 65."""
    score = calculate_technical_score(
        ma_alignment=MA_ALIGNMENT_BULL,
        volume_ratio_20d=Decimal("1.0"),
        breakout_20d=True,
        breakout_60d=False,
        rsi14=Decimal("55"),
        macd_value=Decimal("1.0"),
        macd_signal=Decimal("0.5"),
        candle_patterns=[CANDLE_HAMMER],
        volatility_band=VOLATILITY_NORMAL,
    )
    assert score == Decimal("65")


def test_technical_analyzer_persists_atr_and_volatility_band_on_long_history():
    closes = [Decimal(str(100 + i)) for i in range(130)]
    snapshot = TechnicalAnalyzer().analyze_latest(_bars(closes, volumes=[1_000_000] * 130))
    assert snapshot is not None
    # 입력 OHLC 가 모두 동일 close (high=low=close) 이므로 TR=|Δclose|=1 → ATR=1.
    assert snapshot.atr14 == Decimal("1.0000")
    # close 가 229, ATR/close ≈ 0.44% → LOW band
    assert snapshot.volatility_band == VOLATILITY_LOW
    # 모든 OHLC 가 동일하므로 doji 만 트리거 (다른 패턴은 body=0 가드에 막힘)
    assert snapshot.candle_patterns == [CANDLE_DOJI]


def test_technical_analyzer_short_history_keeps_atr_and_patterns_safe():
    snapshot = TechnicalAnalyzer().analyze_latest(_bars([Decimal("100")] * 4))
    assert snapshot is not None
    assert snapshot.atr14 is None
    assert snapshot.volatility_band is None
    # 4개 bar 가 모두 OHLC 동일 → doji 만 트리거
    assert snapshot.candle_patterns == [CANDLE_DOJI]
    # 짧은 히스토리이므로 base 컴포넌트는 모두 None / 0. doji bonus = 0, vol_band=None.
    # → 최종 0
    assert snapshot.technical_score == Decimal("0.0000")
