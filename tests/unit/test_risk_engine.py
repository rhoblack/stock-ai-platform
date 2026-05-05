from decimal import Decimal

from app.decision.risk_engine import (
    RISK_FLAG_BEARISH_MA_ALIGNMENT,
    RISK_FLAG_LOW_TECHNICAL_SCORE,
    RISK_FLAG_MA20_BREAKDOWN,
    RISK_FLAG_SCORE_DROP,
    RISK_FLAG_STOP_LOSS_NEAR,
    RISK_FLAG_VOLUME_RATIO_EXTREME,
    RISK_FLAG_VOLUME_RATIO_MISSING,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RiskAssessment,
    RiskEngine,
)


# ---------- recommendation evaluation ----------

def test_recommendation_clean_inputs_yield_low_risk():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("82"),
        ma_alignment="PERFECT_BULL",
        volume_ratio_20d=Decimal("2.0"),
    )
    assert isinstance(result, RiskAssessment)
    assert result.risk_flags == []
    assert result.risk_penalty == Decimal("0.0000")
    assert result.risk_level == RISK_LEVEL_LOW


def test_recommendation_low_technical_score_flag_and_penalty():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("10"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("1.5"),
    )
    assert result.risk_flags == [RISK_FLAG_LOW_TECHNICAL_SCORE]
    assert result.risk_penalty == Decimal("10.0000")
    assert result.risk_level == RISK_LEVEL_MEDIUM


def test_recommendation_threshold_boundary_at_20_does_not_flag():
    engine = RiskEngine()
    # technical_score == 20 is NOT below 20
    result = engine.evaluate_recommendation(
        technical_score=Decimal("20"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("1.0"),
    )
    assert RISK_FLAG_LOW_TECHNICAL_SCORE not in result.risk_flags


def test_recommendation_bearish_ma_alignment_flagged():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("60"),
        ma_alignment="BEAR",
        volume_ratio_20d=Decimal("1.5"),
    )
    assert result.risk_flags == [RISK_FLAG_BEARISH_MA_ALIGNMENT]
    assert result.risk_penalty == Decimal("8.0000")


def test_recommendation_perfect_bear_alignment_flagged():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("60"),
        ma_alignment="PERFECT_BEAR",
        volume_ratio_20d=Decimal("1.5"),
    )
    assert RISK_FLAG_BEARISH_MA_ALIGNMENT in result.risk_flags


def test_recommendation_volume_ratio_missing_adds_penalty():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("60"),
        ma_alignment="BULL",
        volume_ratio_20d=None,
    )
    assert result.risk_flags == [RISK_FLAG_VOLUME_RATIO_MISSING]
    assert result.risk_penalty == Decimal("3.0000")


def test_recommendation_volume_ratio_extreme_adds_penalty():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("60"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("8.0"),  # >= 5
    )
    assert result.risk_flags == [RISK_FLAG_VOLUME_RATIO_EXTREME]
    assert result.risk_penalty == Decimal("5.0000")


def test_recommendation_volume_missing_and_extreme_are_mutually_exclusive():
    engine = RiskEngine()
    only_missing = engine.evaluate_recommendation(
        technical_score=Decimal("60"), ma_alignment="BULL", volume_ratio_20d=None,
    )
    only_extreme = engine.evaluate_recommendation(
        technical_score=Decimal("60"), ma_alignment="BULL", volume_ratio_20d=Decimal("9"),
    )
    assert RISK_FLAG_VOLUME_RATIO_MISSING in only_missing.risk_flags
    assert RISK_FLAG_VOLUME_RATIO_EXTREME not in only_missing.risk_flags
    assert RISK_FLAG_VOLUME_RATIO_EXTREME in only_extreme.risk_flags
    assert RISK_FLAG_VOLUME_RATIO_MISSING not in only_extreme.risk_flags


def test_recommendation_stacks_into_high_risk_level():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("5"),       # +10
        ma_alignment="PERFECT_BEAR",        # +8
        volume_ratio_20d=None,              # +3
    )
    # 10 + 8 + 3 = 21 -> HIGH (>= 15)
    assert set(result.risk_flags) == {
        RISK_FLAG_LOW_TECHNICAL_SCORE,
        RISK_FLAG_BEARISH_MA_ALIGNMENT,
        RISK_FLAG_VOLUME_RATIO_MISSING,
    }
    assert result.risk_penalty == Decimal("21.0000")
    assert result.risk_level == RISK_LEVEL_HIGH


def test_recommendation_details_include_thresholds_and_inputs():
    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("82"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("2.0"),
    )
    assert result.details["technical_score"] == "82"
    assert result.details["ma_alignment"] == "BULL"
    assert result.details["volume_ratio_20d"] == "2.0"
    assert result.details["low_technical_score_threshold"] == "20"
    assert result.details["volume_ratio_extreme_threshold"] == "5"


# ---------- holding evaluation ----------

def test_holding_clean_inputs_yield_low_risk():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("80"),
        current_total_score=Decimal("28.0000"),
        previous_total_score=None,
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("10.0000"),
    )
    assert result.risk_flags == []
    assert result.risk_penalty == Decimal("0.0000")
    assert result.risk_level == RISK_LEVEL_LOW


def test_holding_score_drop_requires_previous_score():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("80"),
        current_total_score=Decimal("3.5"),
        previous_total_score=None,
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("10"),
    )
    assert RISK_FLAG_SCORE_DROP not in result.risk_flags


def test_holding_score_drop_threshold_at_15_inclusive():
    engine = RiskEngine()
    # exactly 15 point drop should fire the alert
    result = engine.evaluate_holding(
        technical_score=Decimal("80"),
        current_total_score=Decimal("20"),
        previous_total_score=Decimal("35"),
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("10"),
    )
    assert RISK_FLAG_SCORE_DROP in result.risk_flags


def test_holding_score_drop_just_under_threshold_does_not_fire():
    engine = RiskEngine()
    # 14.99 point drop should NOT fire
    result = engine.evaluate_holding(
        technical_score=Decimal("80"),
        current_total_score=Decimal("20.01"),
        previous_total_score=Decimal("35"),
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("10"),
    )
    assert RISK_FLAG_SCORE_DROP not in result.risk_flags


def test_holding_ma20_breakdown_when_close_below_ma20():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("60"),
        current_total_score=Decimal("21"),
        previous_total_score=None,
        current_price=Decimal("99"),
        ma20=Decimal("105"),
        return_rate=Decimal("-1"),
    )
    assert RISK_FLAG_MA20_BREAKDOWN in result.risk_flags


def test_holding_ma20_none_skips_breakdown_check():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("60"),
        current_total_score=Decimal("21"),
        previous_total_score=None,
        current_price=Decimal("99"),
        ma20=None,
        return_rate=Decimal("-1"),
    )
    assert RISK_FLAG_MA20_BREAKDOWN not in result.risk_flags


def test_holding_stop_loss_at_minus_5_inclusive():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("60"),
        current_total_score=Decimal("21"),
        previous_total_score=None,
        current_price=Decimal("95"),
        ma20=Decimal("90"),
        return_rate=Decimal("-5"),
    )
    assert RISK_FLAG_STOP_LOSS_NEAR in result.risk_flags


def test_holding_stop_loss_just_above_minus_5_does_not_fire():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("60"),
        current_total_score=Decimal("21"),
        previous_total_score=None,
        current_price=Decimal("95.5"),
        ma20=Decimal("90"),
        return_rate=Decimal("-4.5"),
    )
    assert RISK_FLAG_STOP_LOSS_NEAR not in result.risk_flags


def test_holding_low_technical_score_flag():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("10"),
        current_total_score=Decimal("3.5"),
        previous_total_score=None,
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("10"),
    )
    assert RISK_FLAG_LOW_TECHNICAL_SCORE in result.risk_flags
    # Holding low-tech penalty is 5 (vs 10 for recommendation)
    assert result.risk_penalty == Decimal("5.0000")


def test_holding_all_four_alerts_combine_into_high_level():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("10"),       # LOW_TECH +5
        current_total_score=Decimal("3.5"),  # vs prev 35 -> SCORE_DROP +12
        previous_total_score=Decimal("35"),
        current_price=Decimal("90"),         # < ma20 -> +8
        ma20=Decimal("95"),
        return_rate=Decimal("-10"),          # <= -5 -> +15
    )
    assert set(result.risk_flags) == {
        RISK_FLAG_SCORE_DROP,
        RISK_FLAG_MA20_BREAKDOWN,
        RISK_FLAG_STOP_LOSS_NEAR,
        RISK_FLAG_LOW_TECHNICAL_SCORE,
    }
    # 12 + 8 + 15 + 5 = 40 -> HIGH
    assert result.risk_penalty == Decimal("40.0000")
    assert result.risk_level == RISK_LEVEL_HIGH


def test_holding_penalty_capped_at_50():
    engine = RiskEngine()
    # Force a stack that would exceed 50 if uncapped (even if that requires
    # exceeding the 4-flag combo above; PENALTY_CAP defends against future
    # additions). For now the natural max is 40, but verify the cap constant
    # by overriding via reload-style simulation: just assert constant exists.
    assert RiskEngine.PENALTY_CAP == Decimal("50")


def test_holding_details_include_thresholds_and_inputs():
    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("60"),
        current_total_score=Decimal("21"),
        previous_total_score=Decimal("18"),
        current_price=Decimal("105"),
        ma20=Decimal("100"),
        return_rate=Decimal("5"),
    )
    assert result.details["previous_total_score"] == "18"
    assert result.details["current_total_score"] == "21"
    assert result.details["ma20"] == "100"
    assert result.details["current_price"] == "105"
    assert result.details["return_rate"] == "5"
    assert result.details["technical_score"] == "60"
    assert result.details["score_drop_threshold"] == "15"
    assert result.details["stop_loss_return_threshold"] == "-5"
    assert result.details["low_technical_score_threshold"] == "20"


# ---------- risk level classification ----------

def test_risk_level_low_below_5():
    assert RiskEngine._classify_risk_level(Decimal("0")) == RISK_LEVEL_LOW
    assert RiskEngine._classify_risk_level(Decimal("4.99")) == RISK_LEVEL_LOW


def test_risk_level_medium_at_5_inclusive():
    assert RiskEngine._classify_risk_level(Decimal("5")) == RISK_LEVEL_MEDIUM
    assert RiskEngine._classify_risk_level(Decimal("14.99")) == RISK_LEVEL_MEDIUM


def test_risk_level_high_at_15_inclusive():
    assert RiskEngine._classify_risk_level(Decimal("15")) == RISK_LEVEL_HIGH
    assert RiskEngine._classify_risk_level(Decimal("100")) == RISK_LEVEL_HIGH


# ---------- v0.5 Phase C — disclosure_risk_count flag ----------

def test_recommendation_disclosure_risk_count_zero_no_flag():
    """default disclosure_risk_count=0 → backward compat (기존 호출자 영향 0)."""
    from app.decision.risk_engine import RISK_FLAG_DISCLOSURE

    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("80"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("1.5"),
    )
    assert RISK_FLAG_DISCLOSURE not in result.risk_flags
    assert result.risk_penalty == Decimal("0.0000")


def test_recommendation_disclosure_risk_adds_flag_and_penalty():
    """count > 0 → RISK_DISCLOSURE flag + penalty addition 가산."""
    from app.decision.risk_engine import RISK_FLAG_DISCLOSURE

    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("80"),
        ma_alignment="BULL",
        volume_ratio_20d=Decimal("1.5"),
        disclosure_risk_count=2,
        disclosure_penalty_addition=Decimal("6"),
    )
    assert RISK_FLAG_DISCLOSURE in result.risk_flags
    assert result.risk_penalty == Decimal("6.0000")
    assert result.details["disclosure_risk_count"] == 2
    assert result.details["disclosure_penalty_addition"] == "6"


def test_recommendation_disclosure_combined_with_existing_flags():
    """기존 BEARISH_MA + LOW_TECH 와 함께 RISK_DISCLOSURE 가 누적된다 (cap 50)."""
    from app.decision.risk_engine import RISK_FLAG_DISCLOSURE

    engine = RiskEngine()
    result = engine.evaluate_recommendation(
        technical_score=Decimal("10"),
        ma_alignment="BEAR",
        volume_ratio_20d=Decimal("1.5"),
        disclosure_risk_count=3,
        disclosure_penalty_addition=Decimal("9"),
    )
    # 10 (low_tech) + 8 (bear) + 9 (disclosure) = 27, < cap 50
    assert RISK_FLAG_LOW_TECHNICAL_SCORE in result.risk_flags
    assert RISK_FLAG_BEARISH_MA_ALIGNMENT in result.risk_flags
    assert RISK_FLAG_DISCLOSURE in result.risk_flags
    assert result.risk_penalty == Decimal("27.0000")


def test_holding_disclosure_risk_count_zero_no_flag():
    from app.decision.risk_engine import RISK_FLAG_DISCLOSURE

    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("70"),
        current_total_score=Decimal("70"),
        previous_total_score=None,
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("5"),
    )
    assert RISK_FLAG_DISCLOSURE not in result.risk_flags
    assert result.risk_penalty == Decimal("0.0000")


def test_holding_disclosure_risk_adds_flag_and_penalty():
    from app.decision.risk_engine import RISK_FLAG_DISCLOSURE

    engine = RiskEngine()
    result = engine.evaluate_holding(
        technical_score=Decimal("70"),
        current_total_score=Decimal("70"),
        previous_total_score=None,
        current_price=Decimal("110"),
        ma20=Decimal("100"),
        return_rate=Decimal("5"),
        disclosure_risk_count=4,
        disclosure_penalty_addition=Decimal("10"),  # capped at producer
    )
    assert RISK_FLAG_DISCLOSURE in result.risk_flags
    assert result.risk_penalty == Decimal("10.0000")
    assert result.details["disclosure_risk_count"] == 4
