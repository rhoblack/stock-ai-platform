"""Analysis layer. This package must not call external APIs or place orders."""

from app.analysis.indicator_service import TechnicalIndicatorService
from app.analysis.technical_analyzer import (
    MA_ALIGNMENT_BEAR,
    MA_ALIGNMENT_BULL,
    MA_ALIGNMENT_MIXED,
    MA_ALIGNMENT_PERFECT_BEAR,
    MA_ALIGNMENT_PERFECT_BULL,
    MA_ALIGNMENT_RECOVER,
    IndicatorSnapshot,
    TechnicalAnalyzer,
    calculate_technical_score,
    classify_ma_alignment,
    compute_breakout,
    compute_macd,
    compute_volume_ratio_20d,
    exponential_moving_average,
    relative_strength_index,
    simple_moving_average,
)

__all__ = [
    "IndicatorSnapshot",
    "MA_ALIGNMENT_BEAR",
    "MA_ALIGNMENT_BULL",
    "MA_ALIGNMENT_MIXED",
    "MA_ALIGNMENT_PERFECT_BEAR",
    "MA_ALIGNMENT_PERFECT_BULL",
    "MA_ALIGNMENT_RECOVER",
    "TechnicalAnalyzer",
    "TechnicalIndicatorService",
    "calculate_technical_score",
    "classify_ma_alignment",
    "compute_breakout",
    "compute_macd",
    "compute_volume_ratio_20d",
    "exponential_moving_average",
    "relative_strength_index",
    "simple_moving_average",
]
