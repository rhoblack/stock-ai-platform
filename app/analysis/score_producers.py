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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.data.repositories.earnings_events import EarningsEventRepository
from app.data.repositories.fundamental_snapshots import FundamentalSnapshotRepository
from app.data.repositories.news_items import NewsItemRepository
from app.db.models import (
    EarningsEvent,
    FundamentalSnapshot,
    Holding,
    NewsItem,
    Stock,
    StockIndicator,
)


NEUTRAL_SCORE = Decimal("50")
LOW_RULE_SCORE = Decimal("45")
HIGH_RULE_SCORE = Decimal("55")
_SCORE_MIN = Decimal("0")
_SCORE_MAX = Decimal("100")


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


def _clip_score(value: Decimal) -> Decimal:
    return max(min(value, _SCORE_MAX), _SCORE_MIN)


def _decimal_evidence(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _safe_fundamental_evidence(snapshot: FundamentalSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {"reason": "no_fundamental_snapshot"}
    return {
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "fiscal_year": snapshot.fiscal_year,
        "fiscal_quarter": snapshot.fiscal_quarter,
        "per": _decimal_evidence(snapshot.per),
        "pbr": _decimal_evidence(snapshot.pbr),
        "roe": _decimal_evidence(snapshot.roe),
        "debt_ratio": _decimal_evidence(snapshot.debt_ratio),
        "revenue_growth_yoy": _decimal_evidence(snapshot.revenue_growth_yoy),
        "operating_income_growth_yoy": _decimal_evidence(snapshot.operating_income_growth_yoy),
        "dividend_yield": _decimal_evidence(snapshot.dividend_yield),
    }


def _score_fundamental_snapshot(snapshot: FundamentalSnapshot | None) -> tuple[Decimal, dict[str, Any]]:
    evidence = _safe_fundamental_evidence(snapshot)
    if snapshot is None:
        return NEUTRAL_SCORE, evidence
    score = NEUTRAL_SCORE
    if snapshot.roe is not None:
        score += min(max(snapshot.roe, Decimal("-10")), Decimal("25")) * Decimal("0.6")
    if snapshot.per is not None:
        if snapshot.per <= Decimal("8"):
            score += Decimal("8")
        elif snapshot.per <= Decimal("15"):
            score += Decimal("4")
        elif snapshot.per <= Decimal("25"):
            score += Decimal("0")
        elif snapshot.per <= Decimal("40"):
            score -= Decimal("6")
        else:
            score -= Decimal("12")
    if snapshot.pbr is not None:
        if snapshot.pbr <= Decimal("1.0"):
            score += Decimal("4")
        elif snapshot.pbr >= Decimal("4.0"):
            score -= Decimal("8")
        elif snapshot.pbr >= Decimal("2.5"):
            score -= Decimal("4")
    if snapshot.revenue_growth_yoy is not None:
        score += min(max(snapshot.revenue_growth_yoy, Decimal("-20")), Decimal("30")) * Decimal("0.25")
    if snapshot.operating_income_growth_yoy is not None:
        score += min(max(snapshot.operating_income_growth_yoy, Decimal("-30")), Decimal("50")) * Decimal("0.25")
    if snapshot.debt_ratio is not None:
        if snapshot.debt_ratio >= Decimal("200"):
            score -= Decimal("15")
        elif snapshot.debt_ratio >= Decimal("100"):
            score -= Decimal("8")
        elif snapshot.debt_ratio <= Decimal("50"):
            score += Decimal("3")
    if snapshot.dividend_yield is not None and snapshot.dividend_yield > 0:
        score += min(snapshot.dividend_yield, Decimal("5")) * Decimal("0.8")
    return _clip_score(score), evidence


class RealFundamentalScoreProducer(ScoreProducerInterface):
    """Repository-backed replacement for recommendation fundamental_score only."""

    def __init__(
        self,
        fundamental_repository: FundamentalSnapshotRepository,
        *,
        fallback: ScoreProducerInterface | None = None,
    ) -> None:
        self._repo = fundamental_repository
        self._fallback = fallback or DummyScoreProducer()

    def score_recommendation(
        self,
        *,
        stock: Stock,
        indicator: StockIndicator,
    ) -> RecommendationComponentScores:
        base = self._fallback.score_recommendation(stock=stock, indicator=indicator)
        snapshot = self._repo.get_latest_by_symbol(stock.symbol)
        score, evidence = _score_fundamental_snapshot(snapshot)
        return RecommendationComponentScores(
            news_score=base.news_score,
            supply_score=base.supply_score,
            fundamental_score=score,
            ai_score=base.ai_score,
            metadata={
                **(base.metadata or {}),
                "fundamental_producer": "RealFundamentalScoreProducer",
                "fundamental_evidence": evidence,
            },
        )

    def score_holding(
        self,
        *,
        holding: Holding,
        indicator: StockIndicator,
    ) -> HoldingComponentScores:
        return self._fallback.score_holding(holding=holding, indicator=indicator)


def _safe_earnings_evidence(event: EarningsEvent | None) -> dict[str, Any]:
    if event is None:
        return {"reason": "no_earnings_event"}
    return {
        "latest_event_date": event.event_date.isoformat(),
        "fiscal_year": event.fiscal_year,
        "fiscal_quarter": event.fiscal_quarter,
        "event_type": event.event_type,
        "surprise_type": event.surprise_type,
        "surprise_pct": _decimal_evidence(event.surprise_pct),
        "operating_income_actual": _decimal_evidence(event.operating_income_actual),
        "operating_income_consensus": _decimal_evidence(event.operating_income_consensus),
    }


def _recency_multiplier(event_date: date, as_of: date) -> Decimal:
    age_days = (as_of - event_date).days
    if age_days < 0:
        return Decimal("0.5")
    if age_days <= 30:
        return Decimal("1.0")
    if age_days <= 90:
        return Decimal("0.6")
    return Decimal("0.3")


def _score_earnings_event(
    event: EarningsEvent | None,
    *,
    as_of: date,
) -> tuple[Decimal, dict[str, Any]]:
    evidence = _safe_earnings_evidence(event)
    if event is None:
        return NEUTRAL_SCORE, evidence
    if event.surprise_type == "BEAT":
        base_delta = Decimal("10")
    elif event.surprise_type == "MISS":
        base_delta = Decimal("-10")
    else:
        base_delta = Decimal("0")
    surprise_delta = Decimal("0")
    if event.surprise_pct is not None:
        surprise_delta = max(min(event.surprise_pct * Decimal("0.5"), Decimal("10")), Decimal("-10"))
    multiplier = _recency_multiplier(event.event_date, as_of)
    return _clip_score(NEUTRAL_SCORE + (base_delta + surprise_delta) * multiplier), evidence


class RealEarningsScoreProducer(ScoreProducerInterface):
    """Repository-backed replacement for holding earnings_score only."""

    def __init__(
        self,
        earnings_repository: EarningsEventRepository,
        *,
        fallback: ScoreProducerInterface | None = None,
        as_of: date | None = None,
    ) -> None:
        self._repo = earnings_repository
        self._fallback = fallback or DummyScoreProducer()
        self._as_of = as_of

    def _today(self) -> date:
        return self._as_of or datetime.now(UTC).date()

    def score_recommendation(
        self,
        *,
        stock: Stock,
        indicator: StockIndicator,
    ) -> RecommendationComponentScores:
        return self._fallback.score_recommendation(stock=stock, indicator=indicator)

    def score_holding(
        self,
        *,
        holding: Holding,
        indicator: StockIndicator,
    ) -> HoldingComponentScores:
        base = self._fallback.score_holding(holding=holding, indicator=indicator)
        event = self._repo.get_latest_by_symbol(holding.symbol)
        score, evidence = _score_earnings_event(event, as_of=self._today())
        return HoldingComponentScores(
            news_score=base.news_score,
            earnings_score=score,
            ai_score=base.ai_score,
            metadata={
                **(base.metadata or {}),
                "earnings_producer": "RealEarningsScoreProducer",
                "earnings_evidence": evidence,
            },
        )


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
    "RealEarningsScoreProducer",
    "RealFundamentalScoreProducer",
    "RealNewsScoreProducer",
    "RecommendationComponentScores",
    "ScoreProducerInterface",
]
