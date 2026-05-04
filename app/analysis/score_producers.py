"""Rule-based dummy score producers for v0.1 component scores.

The real news, supply/demand, fundamentals, earnings, and AI analysis
pipelines are intentionally out of scope for v0.1. This module provides
deterministic neutral defaults so recommendation and holding-check flows can
exercise the final scoring inputs without calling external APIs or LLMs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.db.models import Holding, Stock, StockIndicator


NEUTRAL_SCORE = Decimal("50")
LOW_RULE_SCORE = Decimal("45")
HIGH_RULE_SCORE = Decimal("55")


@dataclass(frozen=True)
class RecommendationComponentScores:
    news_score: Decimal = NEUTRAL_SCORE
    supply_score: Decimal = NEUTRAL_SCORE
    fundamental_score: Decimal = NEUTRAL_SCORE
    ai_score: Decimal = NEUTRAL_SCORE
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class HoldingComponentScores:
    news_score: Decimal = NEUTRAL_SCORE
    earnings_score: Decimal = NEUTRAL_SCORE
    ai_score: Decimal = NEUTRAL_SCORE
    metadata: dict[str, Any] | None = None


class DummyScoreProducer:
    """Small deterministic producer for missing v0.1 score components.

    All components default to 50. When already-available indicator data is
    present, conservative rule-based nudges are applied:
    * supply: volume_ratio_20d >= 2.0 -> 55, <= 0.7 -> 45
    * ai: bullish MA alignment -> 55, bearish MA alignment -> 45

    The "ai" score here is not an LLM result; it is a deterministic placeholder
    occupying the existing scoring input until a future AI provider is added.
    """

    def score_recommendation(
        self,
        *,
        stock: Stock,
        indicator: StockIndicator,
    ) -> RecommendationComponentScores:
        supply_score, supply_rule = _score_supply(indicator.volume_ratio_20d)
        ai_score, ai_rule = _score_ai_placeholder(indicator.ma_alignment)
        return RecommendationComponentScores(
            news_score=NEUTRAL_SCORE,
            supply_score=supply_score,
            fundamental_score=NEUTRAL_SCORE,
            ai_score=ai_score,
            metadata={
                "producer": "DummyScoreProducer",
                "mode": "rule_based_dummy",
                "symbol": stock.symbol,
                "rules": {
                    "news": "neutral_no_news_pipeline",
                    "supply": supply_rule,
                    "fundamental": "neutral_no_fundamental_pipeline",
                    "ai": ai_rule,
                },
            },
        )

    def score_holding(
        self,
        *,
        holding: Holding,
        indicator: StockIndicator,
    ) -> HoldingComponentScores:
        ai_score, ai_rule = _score_ai_placeholder(indicator.ma_alignment)
        return HoldingComponentScores(
            news_score=NEUTRAL_SCORE,
            earnings_score=NEUTRAL_SCORE,
            ai_score=ai_score,
            metadata={
                "producer": "DummyScoreProducer",
                "mode": "rule_based_dummy",
                "symbol": holding.symbol,
                "rules": {
                    "news": "neutral_no_news_pipeline",
                    "earnings": "neutral_no_earnings_pipeline",
                    "ai": ai_rule,
                },
            },
        )


def _score_supply(volume_ratio_20d: Decimal | None) -> tuple[Decimal, str]:
    if volume_ratio_20d is None:
        return NEUTRAL_SCORE, "neutral_missing_volume_ratio"
    if volume_ratio_20d >= Decimal("2.0"):
        return HIGH_RULE_SCORE, "positive_volume_ratio_20d_gte_2"
    if volume_ratio_20d <= Decimal("0.7"):
        return LOW_RULE_SCORE, "negative_volume_ratio_20d_lte_0_7"
    return NEUTRAL_SCORE, "neutral_volume_ratio_20d"


def _score_ai_placeholder(ma_alignment: str | None) -> tuple[Decimal, str]:
    normalized = (ma_alignment or "").upper()
    if "BULL" in normalized:
        return HIGH_RULE_SCORE, "positive_bullish_ma_alignment"
    if "BEAR" in normalized:
        return LOW_RULE_SCORE, "negative_bearish_ma_alignment"
    return NEUTRAL_SCORE, "neutral_ma_alignment"
