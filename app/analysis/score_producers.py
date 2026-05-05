"""Component score producers for v0.1 ~ v0.5 scoring inputs.

v0.1 ~ v0.4 had only :class:`DummyScoreProducer` — a deterministic neutral
producer that returned 50 for every component score (news / supply /
fundamental / earnings / ai). v0.5 Phase C introduces real news scoring on
top of the v0.5 Phase A/B News+Disclosure data layer.

* :class:`ScoreProducerInterface` — abstract base that
  ``RecommendationEngine`` / ``HoldingCheckEngine`` accept via injection.
* :class:`DummyScoreProducer` — unchanged behavior, now declares the ABC.
* :class:`RealNewsScoreProducer` — wraps a fallback (dummy) for
  supply/fundamental/earnings/ai but overrides ``news_score`` using
  ``NewsItemRepository``-backed rule-based scoring of recent news rows.
* :class:`DisclosureRiskProducer` — separate producer that consults
  ``news_items.category=RISK_DISCLOSURE`` rows and feeds the result into
  ``RiskEngine`` (penalty + RISK_DISCLOSURE flag).

All score formulas keep within v0.5 scope: News / Disclosure data layers were
opt-in (default OFF in production) so downstream behavior remains unchanged
unless an operator enables collection AND injects the real producers. v0.6+
will replace the fallback for fundamental / earnings / supply.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.data.repositories.news_items import NewsItemRepository
from app.db.models import Holding, NewsItem, Stock, StockIndicator


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


class ScoreProducerInterface(ABC):
    """Contract for component-score producers consumed by recommendation /
    holding engines.

    Implementations may be deterministic (DummyScoreProducer) or backed by
    real data (RealNewsScoreProducer wrapping a NewsItemRepository). Engines
    do not branch on the concrete type — they always call the two methods
    below and merge the result into their respective scoring inputs.
    """

    @abstractmethod
    def score_recommendation(
        self,
        *,
        stock: Stock,
        indicator: StockIndicator,
    ) -> RecommendationComponentScores:
        raise NotImplementedError

    @abstractmethod
    def score_holding(
        self,
        *,
        holding: Holding,
        indicator: StockIndicator,
    ) -> HoldingComponentScores:
        raise NotImplementedError


class DummyScoreProducer(ScoreProducerInterface):
    """Deterministic producer for missing v0.1 score components.

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


# ---------------------------------------------------------------------------
# v0.5 Phase C — RealNewsScoreProducer
# ---------------------------------------------------------------------------

_NEWS_LOOKBACK_DAYS = 7
_NEWS_LOOKBACK_LIMIT = 50

_RECENCY_CUTOFFS = (
    (timedelta(hours=24), Decimal("1.0")),
    (timedelta(days=3), Decimal("0.7")),
    (timedelta(days=7), Decimal("0.3")),
)

_SENTIMENT_VALUE = {
    "POSITIVE": 1,
    "NEUTRAL": 0,
    "UNKNOWN": 0,
    "NEGATIVE": -1,
}


def _to_naive_utc(value: datetime) -> datetime:
    """Normalize aware/naive datetimes to a comparable naive-UTC form.

    SQLite roundtrips ``DateTime(timezone=True)`` columns as naive even though
    the ORM column declared timezone=True. Postgres preserves tz. To make the
    calculator portable across both, we strip tz on both sides before doing
    arithmetic.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _recency_factor(now: datetime, published_at: datetime) -> Decimal:
    delta = _to_naive_utc(now) - _to_naive_utc(published_at)
    if delta < timedelta(0):
        # Future-stamped news — treat as fresh (≤24h bucket).
        return Decimal("1.0")
    for cutoff, factor in _RECENCY_CUTOFFS:
        if delta <= cutoff:
            return factor
    return Decimal("0")


def _safe_news_evidence(news: NewsItem) -> dict[str, Any]:
    """Produce evidence dict carrying *only safe* news fields.

    Per v0.5 정책: source_file_path 등 운영자 로컬 경로 / 본문 paragraph 는
    응답·로그에 절대 노출하지 않는다. NewsItem 자체에 그런 필드는 없지만,
    evidence 빌더에서도 명시적으로 안전한 4 필드만 화이트리스트로 노출한다.
    """
    return {
        "title": news.title,
        "url": news.url,
        "provider": news.source,
        "published_at": news.published_at.isoformat(),
        "sentiment": news.sentiment,
    }


@dataclass(frozen=True)
class _NewsScoreCalculation:
    score: Decimal
    evidence: dict[str, Any]


def _calculate_news_score(
    rows: list[NewsItem],
    *,
    now: datetime,
) -> _NewsScoreCalculation:
    if not rows:
        return _NewsScoreCalculation(
            score=NEUTRAL_SCORE,
            evidence={
                "news_count": 0,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
                "latest_news_at": None,
                "top_news": [],
            },
        )

    weighted = Decimal("0")
    pos = neu = neg = 0
    for row in rows:
        sentiment_value = _SENTIMENT_VALUE.get(row.sentiment or "UNKNOWN", 0)
        recency = _recency_factor(now, row.published_at)
        weighted += Decimal(sentiment_value) * recency
        if sentiment_value > 0:
            pos += 1
        elif sentiment_value < 0:
            neg += 1
        else:
            neu += 1

    raw = NEUTRAL_SCORE + weighted * Decimal("5") / Decimal(max(len(rows), 1))
    score = max(min(raw, Decimal("100")), Decimal("0"))

    # Sort by published_at desc to make "latest" + "top_news" deterministic
    # even when the repository ordering changes.
    ordered = sorted(rows, key=lambda r: r.published_at, reverse=True)
    return _NewsScoreCalculation(
        score=score,
        evidence={
            "news_count": len(rows),
            "positive_count": pos,
            "neutral_count": neu,
            "negative_count": neg,
            "latest_news_at": ordered[0].published_at.isoformat(),
            "top_news": [_safe_news_evidence(n) for n in ordered[:3]],
        },
    )


class RealNewsScoreProducer(ScoreProducerInterface):
    """News-backed score producer.

    Composition pattern: delegates supply / fundamental / earnings / ai to a
    fallback (default :class:`DummyScoreProducer`) and overrides only
    ``news_score`` based on the last 7 days of NewsItem rows for the symbol.

    Recipe (v0.5 Phase C):
      * Pull last 7 days news_items rows for the symbol via
        ``NewsItemRepository.list_recent_by_symbol``.
      * For each row, weight ``sentiment_value`` (POSITIVE=+1, NEGATIVE=-1,
        else 0) by recency (≤24h: 1.0 / ≤3d: 0.7 / ≤7d: 0.3).
      * ``news_score = clip( 50 + weighted_sentiment * 5 / max(news_count, 1),
        0, 100 )``. ``news_count = 0`` → 50 (Dummy fallback compatibility).
    """

    def __init__(
        self,
        news_repository: NewsItemRepository,
        *,
        fallback: ScoreProducerInterface | None = None,
        now: datetime | None = None,
    ) -> None:
        self._news_repo = news_repository
        self._fallback = fallback or DummyScoreProducer()
        # Tests inject a fixed ``now`` so recency thresholds become deterministic.
        self._now_override = now

    def _now(self) -> datetime:
        return self._now_override or datetime.now(UTC)

    def _compute(self, symbol: str) -> _NewsScoreCalculation:
        now = self._now()
        cutoff = now - timedelta(days=_NEWS_LOOKBACK_DAYS)
        rows = self._news_repo.list_recent_by_symbol(
            symbol,
            since=cutoff,
            limit=_NEWS_LOOKBACK_LIMIT,
        )
        return _calculate_news_score(rows, now=now)

    def score_recommendation(
        self,
        *,
        stock: Stock,
        indicator: StockIndicator,
    ) -> RecommendationComponentScores:
        base = self._fallback.score_recommendation(stock=stock, indicator=indicator)
        result = self._compute(stock.symbol)
        merged_metadata = {
            **(base.metadata or {}),
            "news_producer": "RealNewsScoreProducer",
            "news_evidence": result.evidence,
        }
        return RecommendationComponentScores(
            news_score=result.score,
            supply_score=base.supply_score,
            fundamental_score=base.fundamental_score,
            ai_score=base.ai_score,
            metadata=merged_metadata,
        )

    def score_holding(
        self,
        *,
        holding: Holding,
        indicator: StockIndicator,
    ) -> HoldingComponentScores:
        base = self._fallback.score_holding(holding=holding, indicator=indicator)
        result = self._compute(holding.symbol)
        merged_metadata = {
            **(base.metadata or {}),
            "news_producer": "RealNewsScoreProducer",
            "news_evidence": result.evidence,
        }
        return HoldingComponentScores(
            news_score=result.score,
            earnings_score=base.earnings_score,
            ai_score=base.ai_score,
            metadata=merged_metadata,
        )


# ---------------------------------------------------------------------------
# v0.5 Phase C — DisclosureRiskProducer
# ---------------------------------------------------------------------------

_DISCLOSURE_LOOKBACK_DAYS = 14
_DISCLOSURE_LOOKBACK_LIMIT = 50
_RISK_CATEGORY = "RISK_DISCLOSURE"
_PENALTY_PER_DISCLOSURE = Decimal("3")
_PENALTY_CAP = Decimal("10")
RISK_DISCLOSURE_FLAG = "RISK_DISCLOSURE"


@dataclass(frozen=True)
class DisclosureRiskResult:
    risk_disclosure_count: int
    penalty_addition: Decimal
    flag: str | None
    evidence: dict[str, Any]


def _safe_disclosure_evidence(news: NewsItem) -> dict[str, Any]:
    return {
        "title": news.title,
        "url": news.url,
        "provider": news.source,
        "published_at": news.published_at.isoformat(),
    }


class DisclosureRiskProducer:
    """Inspect last 14 days of RISK_DISCLOSURE news_items for a symbol.

    Returns :class:`DisclosureRiskResult` with the count + capped penalty
    addition + the RISK_DISCLOSURE flag when count > 0. Engines pass the
    result's ``risk_disclosure_count`` into ``RiskEngine`` so the existing
    risk_penalty / risk_flags / risk_level pipeline absorbs the new signal
    without changing the ScoringEngine base weights.
    """

    LOOKBACK_DAYS = _DISCLOSURE_LOOKBACK_DAYS
    PENALTY_PER_DISCLOSURE = _PENALTY_PER_DISCLOSURE
    PENALTY_CAP = _PENALTY_CAP

    def __init__(
        self,
        news_repository: NewsItemRepository,
        *,
        now: datetime | None = None,
    ) -> None:
        self._news_repo = news_repository
        self._now_override = now

    def _now(self) -> datetime:
        return self._now_override or datetime.now(UTC)

    def evaluate(self, symbol: str) -> DisclosureRiskResult:
        now = self._now()
        cutoff = now - timedelta(days=self.LOOKBACK_DAYS)
        # Symbol-first filter (Python-side related_symbols match) then narrow
        # by category to RISK_DISCLOSURE.
        recent = self._news_repo.list_recent_by_symbol(
            symbol,
            since=cutoff,
            limit=_DISCLOSURE_LOOKBACK_LIMIT,
        )
        risk_rows = [r for r in recent if r.category == _RISK_CATEGORY]
        count = len(risk_rows)
        if count == 0:
            return DisclosureRiskResult(
                risk_disclosure_count=0,
                penalty_addition=Decimal("0"),
                flag=None,
                evidence={
                    "risk_disclosure_count": 0,
                    "recent_risk_disclosures": [],
                },
            )
        penalty = min(
            Decimal(count) * self.PENALTY_PER_DISCLOSURE,
            self.PENALTY_CAP,
        )
        ordered = sorted(risk_rows, key=lambda r: r.published_at, reverse=True)
        return DisclosureRiskResult(
            risk_disclosure_count=count,
            penalty_addition=penalty,
            flag=RISK_DISCLOSURE_FLAG,
            evidence={
                "risk_disclosure_count": count,
                "recent_risk_disclosures": [
                    _safe_disclosure_evidence(r) for r in ordered[:3]
                ],
            },
        )


# ---------------------------------------------------------------------------
# Helpers (unchanged from v0.1)
# ---------------------------------------------------------------------------


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


__all__ = [
    "DisclosureRiskProducer",
    "DisclosureRiskResult",
    "DummyScoreProducer",
    "HIGH_RULE_SCORE",
    "HoldingComponentScores",
    "LOW_RULE_SCORE",
    "NEUTRAL_SCORE",
    "RISK_DISCLOSURE_FLAG",
    "RealNewsScoreProducer",
    "RecommendationComponentScores",
    "ScoreProducerInterface",
]
