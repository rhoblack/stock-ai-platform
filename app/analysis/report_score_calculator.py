"""v0.4 analyst report and theme signal score helpers.

The functions in this module are pure calculation helpers. They do not read
from repositories, call external APIs, or mutate ORM rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


_SCORE_QUANT = Decimal("0.01")
_PCT_QUANT = Decimal("0.0001")
_RATING_QUANT = Decimal("0.0001")
_POINT_QUANT = Decimal("0.01")

_RATING_WEIGHTS = {
    "STRONG_BUY": Decimal("2"),
    "BUY": Decimal("1"),
    "HOLD": Decimal("0"),
    "SELL": Decimal("-1"),
    "STRONG_SELL": Decimal("-2"),
}

_DIRECTION_WEIGHTS = {
    "POSITIVE": Decimal("1"),
    "NEGATIVE": Decimal("-1"),
    "MIXED": Decimal("0"),
    "NEUTRAL": Decimal("0"),
}

_RISK_WARNING_TYPES = {"RISK_WARNING"}


@dataclass(frozen=True)
class ReportScoreResult:
    report_score: Decimal | None
    report_count: int
    target_upside_pct: Decimal | None
    rating_score_avg: Decimal | None
    recency_bonus: Decimal | None


@dataclass(frozen=True)
class ThemeSignalScoreResult:
    theme_signal_score: Decimal | None
    theme_count: int
    signal_event_count: int
    theme_signal_bonus: Decimal | None
    event_signal_bonus: Decimal | None
    risk_penalty: Decimal | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class ScoreAdjustmentResult:
    report_score_adjustment: Decimal
    theme_signal_adjustment: Decimal
    total_score_after: Decimal


def _clip(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


def _quantize(value: Decimal, quant: Decimal = _SCORE_QUANT) -> Decimal:
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def calculate_recency_bonus(
    *,
    as_of: date,
    latest_published_at: date | None,
) -> Decimal | None:
    if latest_published_at is None:
        return None
    age_days = (as_of - latest_published_at).days
    if age_days <= 14:
        return Decimal("5")
    if age_days <= 30:
        return Decimal("3")
    return Decimal("0")


def calculate_rating_score_avg(
    *,
    report_count: int,
    strong_buy_count: int = 0,
    buy_count: int = 0,
    hold_count: int = 0,
    sell_count: int = 0,
    strong_sell_count: int = 0,
) -> Decimal | None:
    if report_count <= 0:
        return None

    weighted = (
        Decimal(strong_buy_count) * _RATING_WEIGHTS["STRONG_BUY"]
        + Decimal(buy_count) * _RATING_WEIGHTS["BUY"]
        + Decimal(hold_count) * _RATING_WEIGHTS["HOLD"]
        + Decimal(sell_count) * _RATING_WEIGHTS["SELL"]
        + Decimal(strong_sell_count) * _RATING_WEIGHTS["STRONG_SELL"]
    )
    return _quantize(weighted / Decimal(report_count), _RATING_QUANT)


def calculate_target_upside_pct(
    *,
    avg_target_price: Decimal | None,
    latest_close: Decimal | None,
) -> Decimal | None:
    if avg_target_price is None or latest_close is None or latest_close <= 0:
        return None
    raw = (avg_target_price - latest_close) / latest_close * Decimal("100")
    return _quantize(_clip(raw, Decimal("-40"), Decimal("60")), _PCT_QUANT)


def calculate_report_score(
    *,
    as_of: date,
    report_count: int,
    avg_target_price: Decimal | None = None,
    latest_close: Decimal | None = None,
    strong_buy_count: int = 0,
    buy_count: int = 0,
    hold_count: int = 0,
    sell_count: int = 0,
    strong_sell_count: int = 0,
    latest_published_at: date | None = None,
) -> ReportScoreResult:
    if report_count <= 0:
        return ReportScoreResult(
            report_score=None,
            report_count=0,
            target_upside_pct=None,
            rating_score_avg=None,
            recency_bonus=None,
        )

    target_upside_pct = calculate_target_upside_pct(
        avg_target_price=avg_target_price,
        latest_close=latest_close,
    )
    rating_score_avg = calculate_rating_score_avg(
        report_count=report_count,
        strong_buy_count=strong_buy_count,
        buy_count=buy_count,
        hold_count=hold_count,
        sell_count=sell_count,
        strong_sell_count=strong_sell_count,
    )
    recency_bonus = calculate_recency_bonus(
        as_of=as_of,
        latest_published_at=latest_published_at,
    )

    score = Decimal("50")
    if target_upside_pct is not None:
        score += target_upside_pct * Decimal("0.5")
    if rating_score_avg is not None:
        score += rating_score_avg * Decimal("10")
    if recency_bonus is not None:
        score += recency_bonus

    return ReportScoreResult(
        report_score=_quantize(_clip(score, Decimal("0"), Decimal("100"))),
        report_count=report_count,
        target_upside_pct=target_upside_pct,
        rating_score_avg=rating_score_avg,
        recency_bonus=recency_bonus,
    )


def _direction_weight(direction: str | None) -> Decimal:
    if direction is None:
        return Decimal("0")
    return _DIRECTION_WEIGHTS.get(direction.upper(), Decimal("0"))


def _strength(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("1")
    return _clip(Decimal(value), Decimal("0"), Decimal("1"))


def _average_signal_points(values: Iterable[Decimal], count: int) -> Decimal | None:
    if count <= 0:
        return None
    return _quantize(sum(values, Decimal("0")) / Decimal(count) * Decimal("10"))


def calculate_theme_signal_score(
    *,
    theme_mappings: list[Any],
    signal_events: list[Any],
) -> ThemeSignalScoreResult:
    theme_count = len(theme_mappings)
    signal_event_count = len(signal_events)
    if theme_count == 0 and signal_event_count == 0:
        return ThemeSignalScoreResult(
            theme_signal_score=None,
            theme_count=0,
            signal_event_count=0,
            theme_signal_bonus=None,
            event_signal_bonus=None,
            risk_penalty=None,
            evidence={"top_themes": [], "top_events": []},
        )

    theme_points = [
        _direction_weight(getattr(mapping, "impact_direction", None))
        * _strength(getattr(mapping, "impact_strength", None))
        for mapping in theme_mappings
    ]
    event_points = [
        _direction_weight(getattr(event, "direction", None))
        * _strength(getattr(event, "strength", None))
        for event in signal_events
    ]
    risk_warning_count = sum(
        1
        for event in signal_events
        if str(getattr(event, "event_type", "")).upper() in _RISK_WARNING_TYPES
    )

    theme_signal_bonus = _average_signal_points(theme_points, theme_count)
    event_signal_bonus = _average_signal_points(event_points, signal_event_count)
    risk_penalty = _quantize(
        _clip(Decimal(risk_warning_count) * Decimal("2.5"), Decimal("0"), Decimal("10")),
    )

    score = Decimal("50")
    if theme_signal_bonus is not None:
        score += theme_signal_bonus
    if event_signal_bonus is not None:
        score += event_signal_bonus
    score -= risk_penalty

    evidence = {
        "top_themes": [_theme_mapping_evidence(m) for m in theme_mappings[:3]],
        "top_events": [_signal_event_evidence(e) for e in signal_events[:3]],
        "risk_warning_count": risk_warning_count,
    }
    return ThemeSignalScoreResult(
        theme_signal_score=_quantize(_clip(score, Decimal("0"), Decimal("100"))),
        theme_count=theme_count,
        signal_event_count=signal_event_count,
        theme_signal_bonus=theme_signal_bonus,
        event_signal_bonus=event_signal_bonus,
        risk_penalty=risk_penalty,
        evidence=evidence,
    )


def calculate_score_adjustment(
    *,
    base_total_score: Decimal,
    report_score: Decimal | None,
    theme_signal_score: Decimal | None,
) -> ScoreAdjustmentResult:
    report_adjustment = (
        _clip((report_score - Decimal("50")) * Decimal("0.1"), Decimal("-5"), Decimal("5"))
        if report_score is not None
        else Decimal("0")
    )
    theme_adjustment = (
        _clip(
            (theme_signal_score - Decimal("50")) * Decimal("0.1"),
            Decimal("-5"),
            Decimal("5"),
        )
        if theme_signal_score is not None
        else Decimal("0")
    )
    total = _clip(
        base_total_score + report_adjustment + theme_adjustment,
        Decimal("0"),
        Decimal("100"),
    )
    return ScoreAdjustmentResult(
        report_score_adjustment=_quantize(report_adjustment),
        theme_signal_adjustment=_quantize(theme_adjustment),
        total_score_after=_quantize(total, Decimal("0.0001")),
    )


def _theme_mapping_evidence(mapping: Any) -> dict[str, Any]:
    theme = getattr(mapping, "theme", None)
    return {
        "theme_name": getattr(theme, "theme_name", None),
        "theme_category": getattr(theme, "theme_category", None),
        "impact_direction": getattr(mapping, "impact_direction", None),
        "impact_strength": str(getattr(mapping, "impact_strength", None))
        if getattr(mapping, "impact_strength", None) is not None
        else None,
        "impact_path": getattr(mapping, "impact_path", None),
        "reason": getattr(mapping, "reason", None),
    }


def _signal_event_evidence(event: Any) -> dict[str, Any]:
    return {
        "event_type": getattr(event, "event_type", None),
        "direction": getattr(event, "direction", None),
        "strength": str(getattr(event, "strength", None))
        if getattr(event, "strength", None) is not None
        else None,
        "summary": getattr(event, "summary", None),
    }
