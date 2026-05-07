"""Unit tests for score producer implementations.

Covers DummyScoreProducer and ProviderScorePolicy integration in the three
real producers (RealNewsScoreProducer, RealFundamentalScoreProducer,
RealEarningsScoreProducer) — v0.14 Phase A.

Invariants verified:
  - DummyScoreProducer: neutral defaults and rule-based nudges (unchanged)
  - Policy disabled (default): producer output IDENTICAL to pre-policy behavior
  - Policy enabled + PROVIDER: no attenuation (factor 1.00)
  - Policy enabled + CSV: 10% attenuation (factor 0.90)
  - Policy enabled + MANUAL: 20% attenuation (factor 0.80)
  - Policy enabled + FAKE: bypass — score returned unchanged
  - Policy enabled + None data_source: factor 1.00 fallback
  - ScoringEngine weights unchanged (technical 35% / news 25% / supply 15% /
    fundamental 15% / ai 10% — holding weights also verified)
  - No external network calls
"""

from __future__ import annotations

import socket
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.analysis.score_producers import (
    NEUTRAL_SCORE,
    DummyScoreProducer,
    RealEarningsScoreProducer,
    RealFundamentalScoreProducer,
    RealNewsScoreProducer,
)
from app.db.models import Holding, Stock, StockIndicator
from app.scoring.provider_policy import ProviderScorePolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stock(symbol: str = "005930") -> Stock:
    return Stock(symbol=symbol, name="샘플", market="KOSPI")


def _indicator(symbol: str = "005930") -> StockIndicator:
    return StockIndicator(symbol=symbol)


def _holding(symbol: str = "005930") -> Holding:
    return Holding(symbol=symbol, quantity=Decimal("1"), avg_buy_price=Decimal("100"))


def _policy(enabled: bool = True) -> ProviderScorePolicy:
    return ProviderScorePolicy(enabled=enabled)


def _fake_news_repo(score: Decimal = Decimal("60")) -> MagicMock:
    """Mock news repository that returns a fixed score via the producer."""
    repo = MagicMock()
    repo.list_recent_by_symbol.return_value = []
    return repo


def _fake_fundamental_repo(snapshot_data_source: str | None = None) -> MagicMock:
    """Mock fundamental repository returning a snapshot with optional data_source."""
    repo = MagicMock()
    snapshot = MagicMock()
    snapshot.roe = Decimal("18")
    snapshot.per = Decimal("10")
    snapshot.pbr = Decimal("1.0")
    snapshot.debt_ratio = Decimal("40")
    snapshot.revenue_growth_yoy = Decimal("15")
    snapshot.operating_income_growth_yoy = Decimal("20")
    snapshot.dividend_yield = Decimal("2.0")
    snapshot.snapshot_date = date(2026, 5, 1)
    snapshot.fiscal_year = 2025
    snapshot.fiscal_quarter = 4
    if snapshot_data_source is not None:
        snapshot.data_source = snapshot_data_source
    else:
        # getattr fallback — do NOT set the attribute so getattr returns None
        del snapshot.data_source
    repo.get_latest_by_symbol.return_value = snapshot
    return repo


def _fake_earnings_repo(
    event_data_source: str | None = None,
    surprise_type: str = "BEAT",
    surprise_pct: Decimal = Decimal("10"),
) -> MagicMock:
    """Mock earnings repository returning an event with optional data_source."""
    repo = MagicMock()
    event = MagicMock()
    event.event_date = date(2026, 5, 1)
    event.fiscal_year = 2026
    event.fiscal_quarter = 1
    event.event_type = "FINAL"
    event.surprise_type = surprise_type
    event.surprise_pct = surprise_pct
    event.operating_income_actual = Decimal("110")
    event.operating_income_consensus = Decimal("100")
    if event_data_source is not None:
        event.data_source = event_data_source
    else:
        del event.data_source
    repo.get_latest_by_symbol.return_value = event
    return repo


# ---------------------------------------------------------------------------
# DummyScoreProducer — unchanged behavior
# ---------------------------------------------------------------------------


def test_recommendation_score_producer_defaults_to_neutral_scores():
    producer = DummyScoreProducer()
    scores = producer.score_recommendation(
        stock=Stock(symbol="005930", name="삼성전자", market="KOSPI"),
        indicator=StockIndicator(symbol="005930"),
    )

    assert scores.news_score == NEUTRAL_SCORE
    assert scores.supply_score == NEUTRAL_SCORE
    assert scores.fundamental_score == NEUTRAL_SCORE
    assert scores.ai_score == NEUTRAL_SCORE
    assert scores.metadata["mode"] == "rule_based_dummy"


def test_recommendation_score_producer_applies_available_indicator_rules():
    producer = DummyScoreProducer()
    scores = producer.score_recommendation(
        stock=Stock(symbol="005930", name="삼성전자", market="KOSPI"),
        indicator=StockIndicator(
            symbol="005930",
            volume_ratio_20d=Decimal("2.5"),
            ma_alignment="PERFECT_BULL",
        ),
    )

    assert scores.supply_score == Decimal("55")
    assert scores.ai_score == Decimal("55")
    assert scores.news_score == Decimal("50")
    assert scores.fundamental_score == Decimal("50")


def test_holding_score_producer_defaults_and_bearish_ai_rule():
    producer = DummyScoreProducer()
    scores = producer.score_holding(
        holding=Holding(symbol="005930", quantity=Decimal("1"), avg_buy_price=Decimal("100")),
        indicator=StockIndicator(symbol="005930", ma_alignment="BEAR"),
    )

    assert scores.news_score == Decimal("50")
    assert scores.earnings_score == Decimal("50")
    assert scores.ai_score == Decimal("45")


# ---------------------------------------------------------------------------
# RealNewsScoreProducer — policy integration
# ---------------------------------------------------------------------------


def test_real_news_producer_policy_disabled_by_default():
    """No policy kwarg → behavior identical to pre-policy code."""
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(repo)
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # No news rows → NEUTRAL_SCORE = 50 (unchanged)
    assert scores.news_score == NEUTRAL_SCORE


def test_real_news_producer_policy_disabled_explicitly():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(repo, policy=_policy(enabled=False))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.news_score == NEUTRAL_SCORE


def test_real_news_producer_policy_enabled_none_data_source_no_attenuation():
    """news_data_source=None → factor 1.00 → score unchanged."""
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source=None,
    )
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # NEUTRAL_SCORE * 1.00 = 50.0000 (quantized)
    assert scores.news_score == Decimal("50.0000")


def test_real_news_producer_policy_enabled_provider_no_attenuation():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source="PROVIDER",
    )
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.news_score == Decimal("50.0000")  # 50 * 1.00


def test_real_news_producer_policy_enabled_csv_attenuates():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source="CSV",
    )
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.news_score == Decimal("45.0000")  # 50 * 0.90


def test_real_news_producer_policy_enabled_manual_attenuates():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source="MANUAL",
    )
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    assert scores.news_score == Decimal("40.0000")  # 50 * 0.80


def test_real_news_producer_policy_enabled_fake_bypasses():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source="FAKE",
    )
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # FAKE bypass → score returned as-is (no quantization)
    assert scores.news_score == NEUTRAL_SCORE


def test_real_news_producer_policy_applies_to_score_holding_too():
    repo = _fake_news_repo()
    producer = RealNewsScoreProducer(
        repo,
        policy=_policy(enabled=True),
        news_data_source="CSV",
    )
    scores = producer.score_holding(holding=_holding(), indicator=_indicator())
    assert scores.news_score == Decimal("45.0000")  # 50 * 0.90


# ---------------------------------------------------------------------------
# RealFundamentalScoreProducer — policy integration
# ---------------------------------------------------------------------------


def test_real_fundamental_producer_policy_disabled_by_default():
    """No policy kwarg → score computed as before (no factor applied)."""
    repo = _fake_fundamental_repo(snapshot_data_source=None)
    producer = RealFundamentalScoreProducer(repo)
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # The mock snapshot returns roe=18, per=10, pbr=1.0, etc. → score > 50
    assert scores.fundamental_score > NEUTRAL_SCORE


def test_real_fundamental_producer_policy_disabled_explicitly_same_score():
    repo = _fake_fundamental_repo(snapshot_data_source="CSV")
    producer_no_policy = RealFundamentalScoreProducer(repo)
    producer_disabled = RealFundamentalScoreProducer(
        repo, policy=_policy(enabled=False)
    )
    s1 = producer_no_policy.score_recommendation(stock=_stock(), indicator=_indicator())
    s2 = producer_disabled.score_recommendation(stock=_stock(), indicator=_indicator())
    assert s1.fundamental_score == s2.fundamental_score


def test_real_fundamental_producer_policy_csv_attenuates():
    repo = _fake_fundamental_repo(snapshot_data_source="CSV")
    producer_base = RealFundamentalScoreProducer(repo)
    producer_policy = RealFundamentalScoreProducer(repo, policy=_policy(enabled=True))

    base_score = producer_base.score_recommendation(stock=_stock(), indicator=_indicator()).fundamental_score
    policy_score = producer_policy.score_recommendation(stock=_stock(), indicator=_indicator()).fundamental_score

    expected = (base_score * Decimal("0.90")).quantize(Decimal("0.0001"))
    assert policy_score == expected


def test_real_fundamental_producer_policy_provider_no_attenuation():
    repo = _fake_fundamental_repo(snapshot_data_source="PROVIDER")
    producer_base = RealFundamentalScoreProducer(repo)
    producer_policy = RealFundamentalScoreProducer(repo, policy=_policy(enabled=True))

    base_score = producer_base.score_recommendation(stock=_stock(), indicator=_indicator()).fundamental_score
    policy_score = producer_policy.score_recommendation(stock=_stock(), indicator=_indicator()).fundamental_score

    # PROVIDER factor = 1.00 → quantized but same value
    expected = (base_score * Decimal("1.00")).quantize(Decimal("0.0001"))
    assert policy_score == expected


def test_real_fundamental_producer_none_data_source_no_attenuation():
    repo = _fake_fundamental_repo(snapshot_data_source=None)
    producer = RealFundamentalScoreProducer(repo, policy=_policy(enabled=True))
    scores = producer.score_recommendation(stock=_stock(), indicator=_indicator())
    # None → fallback 1.00 → score quantized but not reduced
    base_producer = RealFundamentalScoreProducer(_fake_fundamental_repo(snapshot_data_source=None))
    base_score = base_producer.score_recommendation(stock=_stock(), indicator=_indicator()).fundamental_score
    expected = (base_score * Decimal("1.00")).quantize(Decimal("0.0001"))
    assert scores.fundamental_score == expected


# ---------------------------------------------------------------------------
# RealEarningsScoreProducer — policy integration
# ---------------------------------------------------------------------------


def test_real_earnings_producer_policy_disabled_by_default():
    """No policy kwarg → earnings_score unchanged from pre-policy behavior."""
    repo = _fake_earnings_repo(event_data_source=None)
    producer = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    scores = producer.score_holding(holding=_holding(), indicator=_indicator())
    # BEAT event with surprise_pct=10, age=0 → score > 50
    assert scores.earnings_score > NEUTRAL_SCORE


def test_real_earnings_producer_policy_disabled_explicitly_same_score():
    repo = _fake_earnings_repo(event_data_source="CSV")
    producer_no_policy = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    producer_disabled = RealEarningsScoreProducer(
        repo, as_of=date(2026, 5, 1), policy=_policy(enabled=False)
    )
    s1 = producer_no_policy.score_holding(holding=_holding(), indicator=_indicator())
    s2 = producer_disabled.score_holding(holding=_holding(), indicator=_indicator())
    assert s1.earnings_score == s2.earnings_score


def test_real_earnings_producer_policy_csv_attenuates():
    repo = _fake_earnings_repo(event_data_source="CSV")
    producer_base = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    producer_policy = RealEarningsScoreProducer(
        repo, as_of=date(2026, 5, 1), policy=_policy(enabled=True)
    )
    base_score = producer_base.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    policy_score = producer_policy.score_holding(holding=_holding(), indicator=_indicator()).earnings_score

    expected = (base_score * Decimal("0.90")).quantize(Decimal("0.0001"))
    assert policy_score == expected


def test_real_earnings_producer_policy_manual_attenuates():
    repo = _fake_earnings_repo(event_data_source="MANUAL")
    producer_base = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    producer_policy = RealEarningsScoreProducer(
        repo, as_of=date(2026, 5, 1), policy=_policy(enabled=True)
    )
    base_score = producer_base.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    policy_score = producer_policy.score_holding(holding=_holding(), indicator=_indicator()).earnings_score

    expected = (base_score * Decimal("0.80")).quantize(Decimal("0.0001"))
    assert policy_score == expected


def test_real_earnings_producer_policy_fake_bypasses():
    repo = _fake_earnings_repo(event_data_source="FAKE")
    producer_base = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    producer_policy = RealEarningsScoreProducer(
        repo, as_of=date(2026, 5, 1), policy=_policy(enabled=True)
    )
    base_score = producer_base.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    policy_score = producer_policy.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    # FAKE bypass → score returned as-is (no quantization)
    assert policy_score == base_score


def test_real_earnings_producer_none_data_source_no_attenuation():
    repo = _fake_earnings_repo(event_data_source=None)
    producer_base = RealEarningsScoreProducer(repo, as_of=date(2026, 5, 1))
    producer_policy = RealEarningsScoreProducer(
        repo, as_of=date(2026, 5, 1), policy=_policy(enabled=True)
    )
    base_score = producer_base.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    policy_score = producer_policy.score_holding(holding=_holding(), indicator=_indicator()).earnings_score
    expected = (base_score * Decimal("1.00")).quantize(Decimal("0.0001"))
    assert policy_score == expected


# ---------------------------------------------------------------------------
# ScoringEngine weight unchanged assertion
# ---------------------------------------------------------------------------


def test_scoring_engine_recommendation_weights_unchanged():
    from app.decision.scoring_engine import ScoringEngine
    w = ScoringEngine.NEW_RECOMMENDATION_WEIGHTS
    assert w["technical"] == Decimal("0.35")
    assert w["news"] == Decimal("0.25")
    assert w["supply"] == Decimal("0.15")
    assert w["fundamental"] == Decimal("0.15")
    assert w["ai"] == Decimal("0.10")
    assert sum(w.values()) == Decimal("1.00")


def test_scoring_engine_holding_weights_unchanged():
    from app.decision.scoring_engine import ScoringEngine
    w = ScoringEngine.HOLDING_WEIGHTS
    assert w["technical"] == Decimal("0.35")
    assert w["news"] == Decimal("0.20")
    assert w["earnings"] == Decimal("0.20")
    assert w["ai"] == Decimal("0.15")
    assert w["profit_management"] == Decimal("0.10")
    assert sum(w.values()) == Decimal("1.00")


# ---------------------------------------------------------------------------
# No external network calls
# ---------------------------------------------------------------------------


def test_no_network_calls_in_producers(monkeypatch):
    def _block(*args, **kwargs):
        raise AssertionError("producer must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", _block)
    monkeypatch.setattr(socket, "create_connection", _block)

    policy = _policy(enabled=True)

    # News producer
    news_producer = RealNewsScoreProducer(
        _fake_news_repo(), policy=policy, news_data_source="PROVIDER"
    )
    news_producer.score_recommendation(stock=_stock(), indicator=_indicator())

    # Fundamental producer
    fund_producer = RealFundamentalScoreProducer(
        _fake_fundamental_repo(snapshot_data_source="CSV"), policy=policy
    )
    fund_producer.score_recommendation(stock=_stock(), indicator=_indicator())

    # Earnings producer
    earn_producer = RealEarningsScoreProducer(
        _fake_earnings_repo(event_data_source="MANUAL"),
        as_of=date(2026, 5, 1),
        policy=policy,
    )
    earn_producer.score_holding(holding=_holding(), indicator=_indicator())
