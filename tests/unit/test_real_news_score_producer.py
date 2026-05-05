"""Unit tests for v0.5 Phase C scoring producers.

Covers:
  * RealNewsScoreProducer — recency + sentiment formula, evidence top-3,
    fallback delegation to DummyScoreProducer for non-news scores.
  * DisclosureRiskProducer — 14-day window, 3 per disclosure, cap +10,
    flag toggle, evidence top-3.

All tests use deterministic ``now`` injection so recency thresholds are exact.
News rows are produced via NewsItemRepository directly (in-memory SQLite).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.analysis.score_producers import (
    NEUTRAL_SCORE,
    DisclosureRiskProducer,
    DummyScoreProducer,
    RealNewsScoreProducer,
    RISK_DISCLOSURE_FLAG,
)
from app.data.repositories import NewsItemRepository
from app.db import Base
from app.db.models import Stock, StockIndicator
from app.db.session import create_db_engine, create_session_factory


_NOW = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session():
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def _seed_news(
    session: Session,
    *,
    url: str,
    symbol: str,
    sentiment: str | None,
    age: timedelta,
    title: str = "sample",
    category: str = "NEWS",
):
    repo = NewsItemRepository(session)
    repo.upsert_by_url(
        url=url,
        published_at=_NOW - age,
        source="UnitTest",
        title=title,
        related_symbols=[symbol],
        sentiment=sentiment,
        category=category,
    )


def _stock(symbol: str = "005930") -> Stock:
    return Stock(id=1, symbol=symbol, name="Sample", market="KOSPI")


def _indicator(symbol: str = "005930") -> StockIndicator:
    return StockIndicator(symbol=symbol, date=_NOW.date())


# ---------- RealNewsScoreProducer ----------


def test_real_news_score_news_count_zero_returns_neutral(session):
    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert result.news_score == NEUTRAL_SCORE
    ev = result.metadata["news_evidence"]
    assert ev["news_count"] == 0
    assert ev["top_news"] == []
    assert ev["latest_news_at"] is None


def test_real_news_score_recent_positive_news_raises_score(session):
    _seed_news(session, url="u1", symbol="005930", sentiment="POSITIVE",
               age=timedelta(hours=12))
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # 50 + (1 * 1.0) * 5 / 1 = 55
    assert result.news_score == Decimal("55")
    assert result.metadata["news_evidence"]["news_count"] == 1
    assert result.metadata["news_evidence"]["positive_count"] == 1


def test_real_news_score_recent_negative_news_lowers_score(session):
    _seed_news(session, url="u1", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(hours=12))
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # 50 + (-1 * 1.0) * 5 / 1 = 45
    assert result.news_score == Decimal("45")
    assert result.metadata["news_evidence"]["negative_count"] == 1


def test_real_news_score_older_news_has_smaller_recency_weight(session):
    # 6일 (≤7d 윈도우 내, recency 0.3) POSITIVE
    _seed_news(session, url="u1", symbol="005930", sentiment="POSITIVE",
               age=timedelta(days=6))
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # 50 + (1 * 0.3) * 5 / 1 = 51.5
    assert result.news_score == Decimal("51.5")


def test_real_news_score_news_outside_7d_window_excluded(session):
    # 10일 전 news → 7일 윈도우 외 — 조회되지 않으므로 영향 0
    _seed_news(session, url="u1", symbol="005930", sentiment="POSITIVE",
               age=timedelta(days=10))
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert result.news_score == NEUTRAL_SCORE
    assert result.metadata["news_evidence"]["news_count"] == 0


def test_real_news_score_mixed_sentiment(session):
    # 1 positive (recent, w=1.0, +1) + 1 negative (3d, w=0.7, -1)
    _seed_news(session, url="u1", symbol="005930", sentiment="POSITIVE",
               age=timedelta(hours=2))
    _seed_news(session, url="u2", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(days=3))
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # weighted = 1.0 - 0.7 = 0.3 ; score = 50 + 0.3 * 5 / 2 = 50.75
    assert result.news_score == Decimal("50.75")
    ev = result.metadata["news_evidence"]
    assert ev["positive_count"] == 1 and ev["negative_count"] == 1
    assert ev["news_count"] == 2


def test_real_news_score_evidence_top_news_capped_at_three(session):
    for i in range(5):
        _seed_news(
            session,
            url=f"u{i}",
            symbol="005930",
            sentiment="POSITIVE",
            age=timedelta(hours=i + 1),
            title=f"news-{i}",
        )
    session.commit()

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    ev = result.metadata["news_evidence"]
    assert ev["news_count"] == 5
    assert len(ev["top_news"]) == 3  # top 3 only
    # Sorted by published_at desc → most recent first
    titles = [n["title"] for n in ev["top_news"]]
    assert titles == ["news-0", "news-1", "news-2"]
    # Safe fields only — no body/content/full_text
    for n in ev["top_news"]:
        assert set(n.keys()) == {"title", "url", "provider", "published_at", "sentiment"}


def test_real_news_score_delegates_other_components_to_fallback(session):
    """non-news scores (supply / fundamental / ai) come from the fallback (Dummy)."""
    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    indicator = _indicator()
    indicator.volume_ratio_20d = Decimal("2.5")  # → supply 55 from Dummy
    indicator.ma_alignment = "BULL"  # → ai 55 from Dummy

    result = producer.score_recommendation(stock=_stock(), indicator=indicator)
    assert result.supply_score == Decimal("55")
    assert result.ai_score == Decimal("55")
    assert result.fundamental_score == NEUTRAL_SCORE
    assert result.metadata["producer"] == "DummyScoreProducer"  # from fallback metadata
    assert result.metadata["news_producer"] == "RealNewsScoreProducer"


def test_real_news_score_holding_pattern(session):
    """score_holding 도 동일 패턴 — earnings/ai 는 dummy fallback."""
    from app.db.models import Holding

    _seed_news(session, url="u1", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(hours=2))
    session.commit()
    holding = Holding(symbol="005930", quantity=10, avg_buy_price=Decimal("70000"))

    producer = RealNewsScoreProducer(NewsItemRepository(session), now=_NOW)
    result = producer.score_holding(holding=holding, indicator=_indicator())
    assert result.news_score == Decimal("45")
    assert result.earnings_score == NEUTRAL_SCORE  # from Dummy
    assert "news_evidence" in result.metadata


# ---------- DisclosureRiskProducer ----------


def test_disclosure_risk_no_disclosures_returns_zero(session):
    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 0
    assert result.penalty_addition == Decimal("0")
    assert result.flag is None
    assert result.evidence["recent_risk_disclosures"] == []


def test_disclosure_risk_one_disclosure_yields_penalty_3(session):
    _seed_news(
        session,
        url="r1",
        symbol="005930",
        sentiment="NEGATIVE",
        age=timedelta(days=2),
        title="거래정지",
        category="RISK_DISCLOSURE",
    )
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 1
    assert result.penalty_addition == Decimal("3")
    assert result.flag == RISK_DISCLOSURE_FLAG


def test_disclosure_risk_three_disclosures_yields_penalty_9(session):
    for i in range(3):
        _seed_news(
            session,
            url=f"r{i}",
            symbol="005930",
            sentiment="NEGATIVE",
            age=timedelta(days=i + 1),
            title=f"disclosure-{i}",
            category="RISK_DISCLOSURE",
        )
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 3
    assert result.penalty_addition == Decimal("9")  # 3 * 3 = 9, < cap


def test_disclosure_risk_penalty_capped_at_ten(session):
    for i in range(10):  # 10 disclosures × 3 = 30 → cap 10
        _seed_news(
            session,
            url=f"r{i}",
            symbol="005930",
            sentiment="NEGATIVE",
            age=timedelta(days=i % 14),
            title=f"d-{i}",
            category="RISK_DISCLOSURE",
        )
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 10
    assert result.penalty_addition == Decimal("10")  # capped


def test_disclosure_risk_only_within_14d_window(session):
    # In window
    _seed_news(session, url="r1", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(days=10), title="recent", category="RISK_DISCLOSURE")
    # Out of window
    _seed_news(session, url="r2", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(days=20), title="old", category="RISK_DISCLOSURE")
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 1


def test_disclosure_risk_only_for_target_symbol(session):
    _seed_news(session, url="r1", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(days=2), title="our", category="RISK_DISCLOSURE")
    _seed_news(session, url="r2", symbol="000660", sentiment="NEGATIVE",
               age=timedelta(days=2), title="other", category="RISK_DISCLOSURE")
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 1
    assert result.evidence["recent_risk_disclosures"][0]["title"] == "our"


def test_disclosure_risk_ignores_non_risk_categories(session):
    # NEWS category — not risk
    _seed_news(session, url="n1", symbol="005930", sentiment="NEGATIVE",
               age=timedelta(days=2), title="NEWS only", category="NEWS")
    # EARNINGS_REPORT — not risk
    _seed_news(session, url="e1", symbol="005930", sentiment="NEUTRAL",
               age=timedelta(days=2), title="실적", category="EARNINGS_REPORT")
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 0
    assert result.flag is None


def test_disclosure_risk_evidence_top_three(session):
    for i in range(5):
        _seed_news(
            session,
            url=f"r{i}",
            symbol="005930",
            sentiment="NEGATIVE",
            age=timedelta(hours=i + 1),
            title=f"disclosure-{i}",
            category="RISK_DISCLOSURE",
        )
    session.commit()

    producer = DisclosureRiskProducer(NewsItemRepository(session), now=_NOW)
    result = producer.evaluate("005930")
    assert result.risk_disclosure_count == 5
    assert len(result.evidence["recent_risk_disclosures"]) == 3
    # Top 3 by recency desc
    titles = [d["title"] for d in result.evidence["recent_risk_disclosures"]]
    assert titles == ["disclosure-0", "disclosure-1", "disclosure-2"]
    # Safe fields only (no source_file_path / body)
    for d in result.evidence["recent_risk_disclosures"]:
        assert set(d.keys()) == {"title", "url", "provider", "published_at"}
