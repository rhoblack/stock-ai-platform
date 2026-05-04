"""ScoringEngine: pure-function score calculator for v0.1 recommendation/holding flows.

This module aggregates pre-computed component scores using fixed v0.1 weights,
applies ``risk_penalty``, and clamps the result to ``[0, 100]``.

Boundary rules:
    * No external API calls.
    * No DB writes.
    * No recommendation candidate selection (Phase 5).
    * No holding-check decisions (Phase 5).
    * No notifications, no broker, no AI calls.

Component scores must be pre-computed by the caller (technical from
``TechnicalAnalyzer``, news/supply/fundamental/earnings/profit_management/ai
from their respective producers in later phases). Each input is treated as
``0`` when ``None`` and clamped to ``[0, 100]`` defensively. ``risk_penalty``
is treated as ``0`` when ``None`` and floored at ``0``.

v0.1 formulas (from the project brief):

    new recommendation =
        technical * 0.35
      + news      * 0.25
      + supply    * 0.15
      + fundamental * 0.15
      + ai        * 0.10
      - risk_penalty

    holding =
        technical * 0.35
      + news      * 0.20
      + earnings  * 0.20
      + ai        * 0.15
      + profit_management * 0.10
      - risk_penalty
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


_SCORE_QUANT = Decimal("0.0001")
_MIN_SCORE = Decimal("0")
_MAX_SCORE = Decimal("100")


@dataclass(frozen=True)
class NewRecommendationScoreInputs:
    technical_score: Decimal | None = None
    news_score: Decimal | None = None
    supply_score: Decimal | None = None
    fundamental_score: Decimal | None = None
    ai_score: Decimal | None = None
    risk_penalty: Decimal | None = None


@dataclass(frozen=True)
class HoldingScoreInputs:
    technical_score: Decimal | None = None
    news_score: Decimal | None = None
    earnings_score: Decimal | None = None
    ai_score: Decimal | None = None
    profit_management_score: Decimal | None = None
    risk_penalty: Decimal | None = None


@dataclass(frozen=True)
class ScoreBreakdown:
    """Result of a score computation.

    ``total_score`` is the final value clamped to ``[0, 100]`` and quantized
    to 4 decimals. ``raw_total`` is the value before clamping (can be negative
    when penalty overweighs the weighted sum). ``weighted_components`` is the
    per-component contribution after the weight is applied.
    """

    total_score: Decimal
    raw_total: Decimal
    weighted_components: dict[str, Decimal]
    risk_penalty: Decimal


def _clamp_component(value: Decimal | None) -> Decimal:
    if value is None:
        return _MIN_SCORE
    if value < _MIN_SCORE:
        return _MIN_SCORE
    if value > _MAX_SCORE:
        return _MAX_SCORE
    return value


def _normalize_penalty(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if value < Decimal("0"):
        return Decimal("0")
    return value


def _clamp_total(value: Decimal) -> Decimal:
    if value < _MIN_SCORE:
        return _MIN_SCORE
    if value > _MAX_SCORE:
        return _MAX_SCORE
    return value


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_SCORE_QUANT, rounding=ROUND_HALF_UP)


class ScoringEngine:
    """Stateless v0.1 scoring engine."""

    NEW_RECOMMENDATION_WEIGHTS: dict[str, Decimal] = {
        "technical": Decimal("0.35"),
        "news": Decimal("0.25"),
        "supply": Decimal("0.15"),
        "fundamental": Decimal("0.15"),
        "ai": Decimal("0.10"),
    }

    HOLDING_WEIGHTS: dict[str, Decimal] = {
        "technical": Decimal("0.35"),
        "news": Decimal("0.20"),
        "earnings": Decimal("0.20"),
        "ai": Decimal("0.15"),
        "profit_management": Decimal("0.10"),
    }

    def score_new_recommendation(
        self,
        inputs: NewRecommendationScoreInputs,
    ) -> ScoreBreakdown:
        components = [
            ("technical", inputs.technical_score),
            ("news", inputs.news_score),
            ("supply", inputs.supply_score),
            ("fundamental", inputs.fundamental_score),
            ("ai", inputs.ai_score),
        ]
        return self._compose(
            components=components,
            weights=self.NEW_RECOMMENDATION_WEIGHTS,
            risk_penalty=inputs.risk_penalty,
        )

    def score_holding(self, inputs: HoldingScoreInputs) -> ScoreBreakdown:
        components = [
            ("technical", inputs.technical_score),
            ("news", inputs.news_score),
            ("earnings", inputs.earnings_score),
            ("ai", inputs.ai_score),
            ("profit_management", inputs.profit_management_score),
        ]
        return self._compose(
            components=components,
            weights=self.HOLDING_WEIGHTS,
            risk_penalty=inputs.risk_penalty,
        )

    @staticmethod
    def _compose(
        *,
        components: list[tuple[str, Decimal | None]],
        weights: dict[str, Decimal],
        risk_penalty: Decimal | None,
    ) -> ScoreBreakdown:
        weighted_total = Decimal("0")
        breakdown: dict[str, Decimal] = {}
        for name, raw_value in components:
            value = _clamp_component(raw_value)
            contribution = value * weights[name]
            weighted_total += contribution
            breakdown[name] = _quantize(contribution)

        penalty = _normalize_penalty(risk_penalty)
        raw_total = weighted_total - penalty
        final = _clamp_total(raw_total)
        return ScoreBreakdown(
            total_score=_quantize(final),
            raw_total=_quantize(raw_total),
            weighted_components=breakdown,
            risk_penalty=_quantize(penalty),
        )
