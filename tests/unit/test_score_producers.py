from decimal import Decimal

from app.analysis.score_producers import DummyScoreProducer, NEUTRAL_SCORE
from app.db.models import Holding, Stock, StockIndicator


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
