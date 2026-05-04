"""RiskEngine v0.1 — Phase 5-3 risk_penalty / risk_level / risk_flags producer.

Pure-function module: no DB writes, no external API calls, no order placement.
Two evaluation entry points share a common ``RiskAssessment`` shape so callers
can store risk results in ``data_snapshots`` and ``decision_logs`` uniformly.

* ``evaluate_recommendation`` — for new-watch-candidate generation. Inspects
  technical_score, ma_alignment, and volume_ratio_20d from a stock_indicators
  row and returns an assessment.
* ``evaluate_holding`` — for pre-/post-market holding checks. Inspects
  technical_score, the current vs. previous weighted total score, current
  price vs. ma20, and return_rate.

Risk levels (LOW / MEDIUM / HIGH) are derived from ``risk_penalty`` thresholds
so callers can rank, group, or display by level. ``risk_penalty`` itself feeds
back into ``ScoringEngine.score_*`` to subtract from the weighted total.

This module is the foundation for future risk gating (Phase 6+ block / approve
flow). v0.1 RiskEngine is observational only — it never executes orders or
mutates portfolio state.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


RISK_FLAG_LOW_TECHNICAL_SCORE = "LOW_TECHNICAL_SCORE"
RISK_FLAG_BEARISH_MA_ALIGNMENT = "BEARISH_MA_ALIGNMENT"
RISK_FLAG_VOLUME_RATIO_MISSING = "VOLUME_RATIO_MISSING"
RISK_FLAG_VOLUME_RATIO_EXTREME = "VOLUME_RATIO_EXTREME"
RISK_FLAG_SCORE_DROP = "SCORE_DROP"
RISK_FLAG_MA20_BREAKDOWN = "MA20_BREAKDOWN"
RISK_FLAG_STOP_LOSS_NEAR = "STOP_LOSS_NEAR"

RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_HIGH = "HIGH"


_PENALTY_QUANT = Decimal("0.0001")
_BEARISH_MA_ALIGNMENTS = frozenset({"BEAR", "PERFECT_BEAR"})


@dataclass(frozen=True)
class RiskAssessment:
    risk_penalty: Decimal
    risk_level: str
    risk_flags: list[str]
    details: dict[str, Any]


def _decimal_to_str(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _quantize_penalty(value: Decimal) -> Decimal:
    return value.quantize(_PENALTY_QUANT, rounding=ROUND_HALF_UP)


class RiskEngine:
    LOW_TECHNICAL_SCORE_THRESHOLD = Decimal("20")
    VOLUME_RATIO_EXTREME_THRESHOLD = Decimal("5")
    SCORE_DROP_THRESHOLD = Decimal("15")
    STOP_LOSS_RETURN_THRESHOLD = Decimal("-5")

    PENALTY_LOW_TECH_REC = Decimal("10")
    PENALTY_BEARISH_MA = Decimal("8")
    PENALTY_VOLUME_MISSING = Decimal("3")
    PENALTY_VOLUME_EXTREME = Decimal("5")

    PENALTY_SCORE_DROP = Decimal("12")
    PENALTY_MA20_BREAKDOWN = Decimal("8")
    PENALTY_STOP_LOSS = Decimal("15")
    PENALTY_LOW_TECH_HOLD = Decimal("5")

    PENALTY_CAP = Decimal("50")
    LEVEL_HIGH_THRESHOLD = Decimal("15")
    LEVEL_MEDIUM_THRESHOLD = Decimal("5")

    def evaluate_recommendation(
        self,
        *,
        technical_score: Decimal | None,
        ma_alignment: str | None,
        volume_ratio_20d: Decimal | None,
    ) -> RiskAssessment:
        flags: list[str] = []
        penalty = Decimal("0")

        if (
            technical_score is not None
            and technical_score < self.LOW_TECHNICAL_SCORE_THRESHOLD
        ):
            flags.append(RISK_FLAG_LOW_TECHNICAL_SCORE)
            penalty += self.PENALTY_LOW_TECH_REC

        if ma_alignment in _BEARISH_MA_ALIGNMENTS:
            flags.append(RISK_FLAG_BEARISH_MA_ALIGNMENT)
            penalty += self.PENALTY_BEARISH_MA

        if volume_ratio_20d is None:
            flags.append(RISK_FLAG_VOLUME_RATIO_MISSING)
            penalty += self.PENALTY_VOLUME_MISSING
        elif volume_ratio_20d >= self.VOLUME_RATIO_EXTREME_THRESHOLD:
            flags.append(RISK_FLAG_VOLUME_RATIO_EXTREME)
            penalty += self.PENALTY_VOLUME_EXTREME

        capped = _quantize_penalty(min(penalty, self.PENALTY_CAP))
        level = self._classify_risk_level(capped)
        details = {
            "technical_score": _decimal_to_str(technical_score),
            "ma_alignment": ma_alignment,
            "volume_ratio_20d": _decimal_to_str(volume_ratio_20d),
            "low_technical_score_threshold": str(self.LOW_TECHNICAL_SCORE_THRESHOLD),
            "volume_ratio_extreme_threshold": str(self.VOLUME_RATIO_EXTREME_THRESHOLD),
        }
        return RiskAssessment(
            risk_penalty=capped,
            risk_level=level,
            risk_flags=flags,
            details=details,
        )

    def evaluate_holding(
        self,
        *,
        technical_score: Decimal | None,
        current_total_score: Decimal,
        previous_total_score: Decimal | None,
        current_price: Decimal,
        ma20: Decimal | None,
        return_rate: Decimal | None,
    ) -> RiskAssessment:
        """Evaluate holding-check risk.

        ``current_total_score`` should be the weighted total before risk_penalty
        is applied. ``previous_total_score`` is the prior holding_check's stored
        ``total_score`` (post-penalty). The asymmetry is acceptable for v0.1
        because the SCORE_DROP threshold (15 points) is wide enough that the
        small mismatch from a prior penalty does not change the alert outcome.
        """
        flags: list[str] = []
        penalty = Decimal("0")

        if (
            previous_total_score is not None
            and previous_total_score - current_total_score >= self.SCORE_DROP_THRESHOLD
        ):
            flags.append(RISK_FLAG_SCORE_DROP)
            penalty += self.PENALTY_SCORE_DROP

        if ma20 is not None and current_price < ma20:
            flags.append(RISK_FLAG_MA20_BREAKDOWN)
            penalty += self.PENALTY_MA20_BREAKDOWN

        if (
            return_rate is not None
            and return_rate <= self.STOP_LOSS_RETURN_THRESHOLD
        ):
            flags.append(RISK_FLAG_STOP_LOSS_NEAR)
            penalty += self.PENALTY_STOP_LOSS

        if (
            technical_score is not None
            and technical_score < self.LOW_TECHNICAL_SCORE_THRESHOLD
        ):
            flags.append(RISK_FLAG_LOW_TECHNICAL_SCORE)
            penalty += self.PENALTY_LOW_TECH_HOLD

        capped = _quantize_penalty(min(penalty, self.PENALTY_CAP))
        level = self._classify_risk_level(capped)
        details = {
            "previous_total_score": _decimal_to_str(previous_total_score),
            "current_total_score": _decimal_to_str(current_total_score),
            "ma20": _decimal_to_str(ma20),
            "current_price": _decimal_to_str(current_price),
            "return_rate": _decimal_to_str(return_rate),
            "technical_score": _decimal_to_str(technical_score),
            "score_drop_threshold": str(self.SCORE_DROP_THRESHOLD),
            "stop_loss_return_threshold": str(self.STOP_LOSS_RETURN_THRESHOLD),
            "low_technical_score_threshold": str(self.LOW_TECHNICAL_SCORE_THRESHOLD),
        }
        return RiskAssessment(
            risk_penalty=capped,
            risk_level=level,
            risk_flags=flags,
            details=details,
        )

    @classmethod
    def _classify_risk_level(cls, penalty: Decimal) -> str:
        if penalty >= cls.LEVEL_HIGH_THRESHOLD:
            return RISK_LEVEL_HIGH
        if penalty >= cls.LEVEL_MEDIUM_THRESHOLD:
            return RISK_LEVEL_MEDIUM
        return RISK_LEVEL_LOW
