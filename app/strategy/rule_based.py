"""Rule-based strategy implementations (v0.7 Phase A).

Three deterministic, pure-function strategies that consume a
:class:`ScoreSnapshot` and emit a :class:`StrategySignal`. They form the
v0.7 baseline against which the BacktestEngine (Phase B) measures real
``recommendation_results`` 1/3/5/20-day returns.

No DB / network / order side-effects — see :mod:`app.strategy.interfaces`
for the contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.strategy.interfaces import (
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
    ScoreSnapshot,
    StrategyInterface,
    StrategySignal,
)


_NEUTRAL_CONFIDENCE = Decimal("0.5")
_RISK_FLAG_DISCLOSURE = "RISK_DISCLOSURE"
_RISK_LEVEL_HIGH = "HIGH"


# ---------------------------------------------------------------------------
# TopGradeStrategy
# ---------------------------------------------------------------------------


_TOP_GRADE_CONFIDENCE: dict[str, Decimal] = {
    "S": Decimal("0.9"),
    "A": Decimal("0.75"),
    "D": Decimal("0.75"),
}


class TopGradeStrategy(StrategyInterface):
    """Trade on the recommendation grade alone.

    * grade ``S`` or ``A`` → BUY
    * grade ``D`` → AVOID
    * grade ``B`` / ``C`` / unknown / missing → PASS

    Confidence: 0.9 for ``S``, 0.75 for ``A`` and ``D``, 0.5 otherwise.
    """

    @property
    def name(self) -> str:
        return "TopGradeStrategy"

    @property
    def version(self) -> str:
        return "v1.0.0"

    def evaluate(self, snapshot: ScoreSnapshot) -> StrategySignal:
        grade = (snapshot.grade or "").upper()
        if grade in ("S", "A"):
            return StrategySignal(
                action=STRATEGY_ACTION_BUY,
                confidence=_TOP_GRADE_CONFIDENCE.get(grade, _NEUTRAL_CONFIDENCE),
                reason=f"grade={grade}",
                evidence={"grade": grade},
            )
        if grade == "D":
            return StrategySignal(
                action=STRATEGY_ACTION_AVOID,
                confidence=_TOP_GRADE_CONFIDENCE["D"],
                reason="grade=D",
                evidence={"grade": grade},
            )
        return StrategySignal(
            action=STRATEGY_ACTION_PASS,
            confidence=_NEUTRAL_CONFIDENCE,
            reason=f"grade={grade or 'unknown'}",
            evidence={"grade": grade or None},
        )


# ---------------------------------------------------------------------------
# HighScoreStrategy
# ---------------------------------------------------------------------------


_HIGH_SCORE_BUY_THRESHOLD = Decimal("75")
_HIGH_SCORE_AVOID_THRESHOLD = Decimal("35")


class HighScoreStrategy(StrategyInterface):
    """Trade on the recommendation's ``total_score`` alone.

    * ``total_score >= 75`` → BUY (confidence scales linearly 75→0.6 .. 100→1.0)
    * ``total_score <= 35`` → AVOID (confidence scales 35→0.6 .. 0→1.0)
    * 35 < total_score < 75 → PASS (confidence 0.5)
    * total_score is None → PASS (confidence 0.5)
    """

    @property
    def name(self) -> str:
        return "HighScoreStrategy"

    @property
    def version(self) -> str:
        return "v1.0.0"

    def evaluate(self, snapshot: ScoreSnapshot) -> StrategySignal:
        score = snapshot.total_score
        if score is None:
            return StrategySignal(
                action=STRATEGY_ACTION_PASS,
                confidence=_NEUTRAL_CONFIDENCE,
                reason="total_score=None",
                evidence={"total_score": None},
            )
        if score >= _HIGH_SCORE_BUY_THRESHOLD:
            # Linear ramp: 75 → 0.6, 100 → 1.0. Clamp by signal post-init.
            confidence = Decimal("0.6") + (score - _HIGH_SCORE_BUY_THRESHOLD) * Decimal("0.016")
            return StrategySignal(
                action=STRATEGY_ACTION_BUY,
                confidence=confidence,
                reason=f"total_score={score} >= {_HIGH_SCORE_BUY_THRESHOLD}",
                evidence={"total_score": str(score)},
            )
        if score <= _HIGH_SCORE_AVOID_THRESHOLD:
            confidence = Decimal("0.6") + (_HIGH_SCORE_AVOID_THRESHOLD - score) * Decimal("0.011")
            return StrategySignal(
                action=STRATEGY_ACTION_AVOID,
                confidence=confidence,
                reason=f"total_score={score} <= {_HIGH_SCORE_AVOID_THRESHOLD}",
                evidence={"total_score": str(score)},
            )
        return StrategySignal(
            action=STRATEGY_ACTION_PASS,
            confidence=_NEUTRAL_CONFIDENCE,
            reason=f"total_score={score} (mid-range)",
            evidence={"total_score": str(score)},
        )


# ---------------------------------------------------------------------------
# MultiSignalStrategy
# ---------------------------------------------------------------------------


_MULTI_SIGNAL_TOTAL_BUY = Decimal("65")
_MULTI_SIGNAL_TOTAL_AVOID = Decimal("35")
_MULTI_SIGNAL_FUNDAMENTAL_MIN = Decimal("60")
_MULTI_SIGNAL_NEWS_MIN = Decimal("50")
_MULTI_SIGNAL_EARNINGS_MIN = Decimal("50")

_MULTI_SIGNAL_BASE_CONFIDENCE = Decimal("0.7")
_MULTI_SIGNAL_BEAT_BOOST = Decimal("0.1")
_MULTI_SIGNAL_NEWS_POSITIVE_BOOST = Decimal("0.05")


def _has_risk_disclosure(snapshot: ScoreSnapshot) -> bool:
    return _RISK_FLAG_DISCLOSURE in (snapshot.risk_flags or [])


def _earnings_surprise_type(evidence: dict[str, Any] | None) -> str | None:
    if not evidence:
        return None
    earnings = evidence.get("earnings_evidence")
    if not isinstance(earnings, dict):
        return None
    return earnings.get("surprise_type")


def _news_sentiment_skew(evidence: dict[str, Any] | None) -> int:
    """Return positive_count - negative_count from news_evidence, or 0."""

    if not evidence:
        return 0
    news = evidence.get("news_evidence")
    if not isinstance(news, dict):
        return 0
    try:
        positive = int(news.get("positive_count", 0) or 0)
        negative = int(news.get("negative_count", 0) or 0)
    except (TypeError, ValueError):
        return 0
    return positive - negative


class MultiSignalStrategy(StrategyInterface):
    """Multi-factor rule combining v0.4~v0.6 signals.

    BUY when *all* of:
      * ``total_score >= 65``
      * ``fundamental_score >= 60``
      * ``news_score >= 50``
      * ``earnings_score >= 50`` *or* ``earnings_score is None`` (no event yet)
      * ``risk_level != HIGH``
      * ``RISK_DISCLOSURE`` not in ``risk_flags``

    AVOID when *any* of:
      * ``risk_level == HIGH``
      * ``RISK_DISCLOSURE`` in ``risk_flags``
      * ``total_score <= 35``

    Otherwise PASS.

    Evidence-driven confidence boost (BUY only):
      * ``earnings_evidence.surprise_type == "BEAT"`` → +0.10
      * ``news_evidence.positive_count > negative_count`` → +0.05

    All confidence values are clamped to ``[0, 1]`` by ``StrategySignal``.
    """

    @property
    def name(self) -> str:
        return "MultiSignalStrategy"

    @property
    def version(self) -> str:
        return "v1.0.0"

    def evaluate(self, snapshot: ScoreSnapshot) -> StrategySignal:
        # ---- AVOID gates (highest priority) -----------------------------
        if (snapshot.risk_level or "").upper() == _RISK_LEVEL_HIGH:
            return StrategySignal(
                action=STRATEGY_ACTION_AVOID,
                confidence=Decimal("0.85"),
                reason="risk_level=HIGH",
                evidence={"risk_level": snapshot.risk_level},
            )
        if _has_risk_disclosure(snapshot):
            return StrategySignal(
                action=STRATEGY_ACTION_AVOID,
                confidence=Decimal("0.85"),
                reason="RISK_DISCLOSURE flag",
                evidence={"risk_flags": list(snapshot.risk_flags or [])},
            )
        total_score = snapshot.total_score
        if total_score is not None and total_score <= _MULTI_SIGNAL_TOTAL_AVOID:
            return StrategySignal(
                action=STRATEGY_ACTION_AVOID,
                confidence=Decimal("0.7"),
                reason=f"total_score={total_score} <= {_MULTI_SIGNAL_TOTAL_AVOID}",
                evidence={"total_score": str(total_score)},
            )

        # ---- BUY gates --------------------------------------------------
        fundamental = snapshot.fundamental_score
        news = snapshot.news_score
        earnings = snapshot.earnings_score

        buy_conditions_met = (
            total_score is not None
            and total_score >= _MULTI_SIGNAL_TOTAL_BUY
            and fundamental is not None
            and fundamental >= _MULTI_SIGNAL_FUNDAMENTAL_MIN
            and news is not None
            and news >= _MULTI_SIGNAL_NEWS_MIN
            and (earnings is None or earnings >= _MULTI_SIGNAL_EARNINGS_MIN)
        )
        if buy_conditions_met:
            confidence = _MULTI_SIGNAL_BASE_CONFIDENCE
            reasons = [
                f"total={total_score}",
                f"fundamental={fundamental}",
                f"news={news}",
                f"earnings={earnings}" if earnings is not None else "earnings=N/A",
            ]
            if _earnings_surprise_type(snapshot.evidence) == "BEAT":
                confidence += _MULTI_SIGNAL_BEAT_BOOST
                reasons.append("earnings BEAT boost")
            if _news_sentiment_skew(snapshot.evidence) > 0:
                confidence += _MULTI_SIGNAL_NEWS_POSITIVE_BOOST
                reasons.append("news sentiment skew positive")
            return StrategySignal(
                action=STRATEGY_ACTION_BUY,
                confidence=confidence,
                reason="; ".join(reasons),
                evidence={
                    "total_score": str(total_score) if total_score is not None else None,
                    "fundamental_score": str(fundamental) if fundamental is not None else None,
                    "news_score": str(news) if news is not None else None,
                    "earnings_score": str(earnings) if earnings is not None else None,
                    "risk_level": snapshot.risk_level,
                },
            )

        # ---- PASS fallback ---------------------------------------------
        return StrategySignal(
            action=STRATEGY_ACTION_PASS,
            confidence=_NEUTRAL_CONFIDENCE,
            reason="conditions not met for BUY/AVOID",
            evidence={
                "total_score": str(total_score) if total_score is not None else None,
                "fundamental_score": str(fundamental) if fundamental is not None else None,
                "news_score": str(news) if news is not None else None,
                "earnings_score": str(earnings) if earnings is not None else None,
                "risk_level": snapshot.risk_level,
            },
        )


__all__ = [
    "HighScoreStrategy",
    "MultiSignalStrategy",
    "TopGradeStrategy",
]
