from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.analysis.report_score_calculator import (
    calculate_report_score,
    calculate_score_adjustment,
    calculate_theme_signal_score,
)


def test_report_score_returns_none_when_report_count_zero():
    result = calculate_report_score(
        as_of=date(2026, 5, 5),
        report_count=0,
    )

    assert result.report_score is None
    assert result.target_upside_pct is None
    assert result.rating_score_avg is None
    assert result.recency_bonus is None


def test_report_score_clips_target_upside():
    result = calculate_report_score(
        as_of=date(2026, 5, 5),
        report_count=1,
        avg_target_price=Decimal("300"),
        latest_close=Decimal("100"),
        buy_count=1,
        latest_published_at=date(2026, 5, 1),
    )

    assert result.target_upside_pct == Decimal("60.0000")
    assert result.report_score == Decimal("95.00")


def test_report_score_calculates_rating_score_average():
    result = calculate_report_score(
        as_of=date(2026, 5, 5),
        report_count=4,
        latest_close=Decimal("100"),
        avg_target_price=Decimal("100"),
        strong_buy_count=1,
        buy_count=1,
        hold_count=1,
        sell_count=1,
        latest_published_at=date(2026, 5, 1),
    )

    assert result.rating_score_avg == Decimal("0.5000")
    assert result.report_score == Decimal("60.00")


def test_report_score_recency_bonus_buckets():
    fresh = calculate_report_score(
        as_of=date(2026, 5, 31),
        report_count=1,
        hold_count=1,
        latest_published_at=date(2026, 5, 17),
    )
    mid = calculate_report_score(
        as_of=date(2026, 5, 31),
        report_count=1,
        hold_count=1,
        latest_published_at=date(2026, 5, 16),
    )
    stale = calculate_report_score(
        as_of=date(2026, 5, 31),
        report_count=1,
        hold_count=1,
        latest_published_at=date(2026, 4, 30),
    )

    assert fresh.recency_bonus == Decimal("5")
    assert mid.recency_bonus == Decimal("3")
    assert stale.recency_bonus == Decimal("0")


def test_report_score_is_clamped_to_zero_to_hundred():
    result = calculate_report_score(
        as_of=date(2026, 5, 5),
        report_count=1,
        avg_target_price=Decimal("1000"),
        latest_close=Decimal("100"),
        strong_buy_count=1,
        latest_published_at=date(2026, 5, 1),
    )

    assert result.report_score == Decimal("100.00")


def test_score_adjustment_caps_each_component():
    result = calculate_score_adjustment(
        base_total_score=Decimal("80"),
        report_score=Decimal("100"),
        theme_signal_score=Decimal("0"),
    )

    assert result.report_score_adjustment == Decimal("5.00")
    assert result.theme_signal_adjustment == Decimal("-5.00")
    assert result.total_score_after == Decimal("80.0000")


def test_theme_signal_score_returns_none_without_themes_or_events():
    result = calculate_theme_signal_score(theme_mappings=[], signal_events=[])

    assert result.theme_signal_score is None
    assert result.evidence == {"top_themes": [], "top_events": []}


def test_theme_signal_score_adds_positive_theme():
    mapping = SimpleNamespace(
        impact_direction="POSITIVE",
        impact_strength=Decimal("1.0"),
        impact_path="DEMAND_RECOVERY",
        reason="HBM demand",
        theme=SimpleNamespace(theme_name="HBM", theme_category="SEMICONDUCTOR"),
    )

    result = calculate_theme_signal_score(theme_mappings=[mapping], signal_events=[])

    assert result.theme_signal_score == Decimal("60.00")
    assert result.theme_signal_bonus == Decimal("10.00")
    assert result.evidence["top_themes"][0]["theme_name"] == "HBM"


def test_theme_signal_score_subtracts_negative_theme():
    mapping = SimpleNamespace(
        impact_direction="NEGATIVE",
        impact_strength=Decimal("0.5"),
        impact_path="COST_PRESSURE",
        reason="cost pressure",
        theme=SimpleNamespace(theme_name="Copper", theme_category="COMMODITY"),
    )

    result = calculate_theme_signal_score(theme_mappings=[mapping], signal_events=[])

    assert result.theme_signal_score == Decimal("45.00")
    assert result.theme_signal_bonus == Decimal("-5.00")


def test_theme_signal_score_applies_risk_warning_penalty():
    event = SimpleNamespace(
        event_type="RISK_WARNING",
        direction="NEGATIVE",
        strength=Decimal("1.0"),
        summary="margin risk",
    )

    result = calculate_theme_signal_score(theme_mappings=[], signal_events=[event])

    assert result.event_signal_bonus == Decimal("-10.00")
    assert result.risk_penalty == Decimal("2.50")
    assert result.theme_signal_score == Decimal("37.50")


def test_theme_signal_score_treats_mixed_direction_as_neutral():
    mapping = SimpleNamespace(
        impact_direction="MIXED",
        impact_strength=Decimal("1.0"),
        impact_path="MIXED",
        reason=None,
        theme=SimpleNamespace(theme_name="AI", theme_category="AI"),
    )

    result = calculate_theme_signal_score(theme_mappings=[mapping], signal_events=[])

    assert result.theme_signal_score == Decimal("50.00")
    assert result.theme_signal_bonus == Decimal("0.00")


def test_theme_signal_score_returns_event_evidence():
    event = SimpleNamespace(
        event_type="TARGET_PRICE_UP",
        direction="POSITIVE",
        strength=Decimal("0.7"),
        summary="target raised",
    )

    result = calculate_theme_signal_score(theme_mappings=[], signal_events=[event])

    assert result.evidence["top_events"] == [
        {
            "event_type": "TARGET_PRICE_UP",
            "direction": "POSITIVE",
            "strength": "0.7",
            "summary": "target raised",
        },
    ]
