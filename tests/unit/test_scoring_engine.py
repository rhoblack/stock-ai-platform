from decimal import Decimal

from app.decision.scoring_engine import (
    HoldingScoreInputs,
    NewRecommendationScoreInputs,
    ScoreBreakdown,
    ScoringEngine,
)


# ---------- weight invariants ----------

def test_new_recommendation_weights_sum_to_one():
    total = sum(ScoringEngine.NEW_RECOMMENDATION_WEIGHTS.values(), Decimal("0"))
    assert total == Decimal("1.00")


def test_holding_weights_sum_to_one():
    total = sum(ScoringEngine.HOLDING_WEIGHTS.values(), Decimal("0"))
    assert total == Decimal("1.00")


# ---------- new recommendation ----------

def test_score_new_recommendation_perfect_inputs_yield_100():
    engine = ScoringEngine()
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("100"),
            news_score=Decimal("100"),
            supply_score=Decimal("100"),
            fundamental_score=Decimal("100"),
            ai_score=Decimal("100"),
        )
    )
    assert isinstance(result, ScoreBreakdown)
    assert result.total_score == Decimal("100.0000")
    assert result.raw_total == Decimal("100.0000")
    assert result.risk_penalty == Decimal("0.0000")


def test_score_new_recommendation_matches_brief_formula():
    engine = ScoringEngine()
    # 80*0.35 + 60*0.25 + 70*0.15 + 50*0.15 + 90*0.10
    # = 28 + 15 + 10.5 + 7.5 + 9 = 70.0
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("80"),
            news_score=Decimal("60"),
            supply_score=Decimal("70"),
            fundamental_score=Decimal("50"),
            ai_score=Decimal("90"),
        )
    )
    assert result.total_score == Decimal("70.0000")
    assert result.weighted_components["technical"] == Decimal("28.0000")
    assert result.weighted_components["news"] == Decimal("15.0000")
    assert result.weighted_components["supply"] == Decimal("10.5000")
    assert result.weighted_components["fundamental"] == Decimal("7.5000")
    assert result.weighted_components["ai"] == Decimal("9.0000")


def test_score_new_recommendation_none_components_treated_as_zero():
    engine = ScoringEngine()
    # only technical present: 100*0.35 = 35
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(technical_score=Decimal("100"))
    )
    assert result.total_score == Decimal("35.0000")
    assert result.weighted_components["news"] == Decimal("0.0000")
    assert result.weighted_components["supply"] == Decimal("0.0000")
    assert result.weighted_components["fundamental"] == Decimal("0.0000")
    assert result.weighted_components["ai"] == Decimal("0.0000")


def test_score_new_recommendation_risk_penalty_subtracts():
    engine = ScoringEngine()
    # weighted = 80, penalty = 20 -> 60
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("80"),
            news_score=Decimal("80"),
            supply_score=Decimal("80"),
            fundamental_score=Decimal("80"),
            ai_score=Decimal("80"),
            risk_penalty=Decimal("20"),
        )
    )
    assert result.total_score == Decimal("60.0000")
    assert result.risk_penalty == Decimal("20.0000")
    assert result.raw_total == Decimal("60.0000")


def test_score_new_recommendation_negative_penalty_floored_to_zero():
    engine = ScoringEngine()
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("100"),
            news_score=Decimal("100"),
            supply_score=Decimal("100"),
            fundamental_score=Decimal("100"),
            ai_score=Decimal("100"),
            risk_penalty=Decimal("-50"),
        )
    )
    assert result.total_score == Decimal("100.0000")
    assert result.risk_penalty == Decimal("0.0000")


def test_score_new_recommendation_clamps_below_zero_when_penalty_overweighs():
    engine = ScoringEngine()
    # weighted = 10, penalty = 50, raw = -40 -> clamped 0
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("10"),
            news_score=Decimal("10"),
            supply_score=Decimal("10"),
            fundamental_score=Decimal("10"),
            ai_score=Decimal("10"),
            risk_penalty=Decimal("50"),
        )
    )
    assert result.raw_total == Decimal("-40.0000")
    assert result.total_score == Decimal("0.0000")


def test_score_new_recommendation_input_above_100_clamped_before_weighting():
    engine = ScoringEngine()
    # absurd 150 should be clamped to 100 before weight
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("150"),
            news_score=Decimal("100"),
            supply_score=Decimal("100"),
            fundamental_score=Decimal("100"),
            ai_score=Decimal("100"),
        )
    )
    assert result.total_score == Decimal("100.0000")


def test_score_new_recommendation_negative_input_clamped_to_zero():
    engine = ScoringEngine()
    # technical = -10 -> clamped 0; weighted = 0*.35 + 100*0.65 = 65
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("-10"),
            news_score=Decimal("100"),
            supply_score=Decimal("100"),
            fundamental_score=Decimal("100"),
            ai_score=Decimal("100"),
        )
    )
    assert result.total_score == Decimal("65.0000")
    assert result.weighted_components["technical"] == Decimal("0.0000")


def test_score_new_recommendation_breakdown_sum_minus_penalty_equals_raw():
    engine = ScoringEngine()
    result = engine.score_new_recommendation(
        NewRecommendationScoreInputs(
            technical_score=Decimal("80"),
            news_score=Decimal("60"),
            supply_score=Decimal("70"),
            fundamental_score=Decimal("50"),
            ai_score=Decimal("90"),
            risk_penalty=Decimal("5"),
        )
    )
    contrib_sum = sum(result.weighted_components.values(), Decimal("0"))
    assert contrib_sum - result.risk_penalty == result.raw_total


# ---------- holding ----------

def test_score_holding_perfect_inputs_yield_100():
    engine = ScoringEngine()
    result = engine.score_holding(
        HoldingScoreInputs(
            technical_score=Decimal("100"),
            news_score=Decimal("100"),
            earnings_score=Decimal("100"),
            ai_score=Decimal("100"),
            profit_management_score=Decimal("100"),
        )
    )
    assert result.total_score == Decimal("100.0000")


def test_score_holding_matches_brief_formula():
    engine = ScoringEngine()
    # 80*0.35 + 60*0.20 + 70*0.20 + 50*0.15 + 90*0.10
    # = 28 + 12 + 14 + 7.5 + 9 = 70.5
    result = engine.score_holding(
        HoldingScoreInputs(
            technical_score=Decimal("80"),
            news_score=Decimal("60"),
            earnings_score=Decimal("70"),
            ai_score=Decimal("50"),
            profit_management_score=Decimal("90"),
        )
    )
    assert result.total_score == Decimal("70.5000")
    assert result.weighted_components["technical"] == Decimal("28.0000")
    assert result.weighted_components["news"] == Decimal("12.0000")
    assert result.weighted_components["earnings"] == Decimal("14.0000")
    assert result.weighted_components["ai"] == Decimal("7.5000")
    assert result.weighted_components["profit_management"] == Decimal("9.0000")


def test_score_holding_risk_penalty_subtracts():
    engine = ScoringEngine()
    # weighted = 80, penalty = 15 -> 65
    result = engine.score_holding(
        HoldingScoreInputs(
            technical_score=Decimal("80"),
            news_score=Decimal("80"),
            earnings_score=Decimal("80"),
            ai_score=Decimal("80"),
            profit_management_score=Decimal("80"),
            risk_penalty=Decimal("15"),
        )
    )
    assert result.total_score == Decimal("65.0000")
    assert result.risk_penalty == Decimal("15.0000")


def test_score_holding_all_none_inputs_yield_zero():
    engine = ScoringEngine()
    result = engine.score_holding(HoldingScoreInputs())
    assert result.total_score == Decimal("0.0000")
    assert result.raw_total == Decimal("0.0000")
    assert result.risk_penalty == Decimal("0.0000")


def test_score_holding_extreme_penalty_clamps_to_zero():
    engine = ScoringEngine()
    result = engine.score_holding(
        HoldingScoreInputs(
            technical_score=Decimal("50"),
            news_score=Decimal("50"),
            earnings_score=Decimal("50"),
            ai_score=Decimal("50"),
            profit_management_score=Decimal("50"),
            risk_penalty=Decimal("200"),
        )
    )
    assert result.raw_total == Decimal("-150.0000")
    assert result.total_score == Decimal("0.0000")
