"""Unit tests for v0.7 Phase A — StrategyInterface + 3 rule-based strategies.

Pure-function tests. No DB / network / Telegram / order side-effects.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.strategy.interfaces import (
    SCORE_SNAPSHOT_FIELDS,
    STRATEGY_ACTIONS,
    STRATEGY_ACTION_AVOID,
    STRATEGY_ACTION_BUY,
    STRATEGY_ACTION_PASS,
    ScoreSnapshot,
    StrategyInterface,
    StrategySignal,
)
from app.strategy.rule_based import (
    HighScoreStrategy,
    MultiSignalStrategy,
    TopGradeStrategy,
)


# ---------------------------------------------------------------------------
# StrategySignal — action validation + confidence clamp
# ---------------------------------------------------------------------------


def test_strategy_signal_rejects_invalid_action():
    with pytest.raises(ValueError):
        StrategySignal(action="SELL")


@pytest.mark.parametrize("action", sorted(STRATEGY_ACTIONS))
def test_strategy_signal_accepts_known_actions(action):
    sig = StrategySignal(action=action)
    assert sig.action == action
    # default confidence stays neutral
    assert sig.confidence == Decimal("0.5")


@pytest.mark.parametrize(
    "raw,expected",
    [
        (Decimal("-1.0"), Decimal("0")),
        (Decimal("0"), Decimal("0")),
        (Decimal("0.5"), Decimal("0.5")),
        (Decimal("1.0"), Decimal("1")),
        (Decimal("2.0"), Decimal("1")),
        (Decimal("1.5"), Decimal("1")),
        (Decimal("-0.001"), Decimal("0")),
    ],
)
def test_strategy_signal_clamps_confidence(raw, expected):
    sig = StrategySignal(action=STRATEGY_ACTION_PASS, confidence=raw)
    assert sig.confidence == expected


def test_strategy_signal_coerces_non_decimal_confidence():
    sig = StrategySignal(action=STRATEGY_ACTION_BUY, confidence=0.85)
    assert isinstance(sig.confidence, Decimal)
    assert sig.confidence == Decimal("0.85")


# ---------------------------------------------------------------------------
# ScoreSnapshot — null-safe + no order fields
# ---------------------------------------------------------------------------


def test_score_snapshot_minimal_construction_only_requires_symbol():
    snap = ScoreSnapshot(symbol="005930")
    assert snap.symbol == "005930"
    assert snap.total_score is None
    assert snap.grade is None
    assert snap.risk_flags == []
    assert snap.evidence is None


def test_score_snapshot_does_not_carry_order_fields():
    """Strategy signals are not orders. Verify the dataclass blocks any
    accidental field that looks like one (quantity / price / account / broker /
    order_type)."""

    # Accept only the documented fields. If the dataclass grows order-side
    # fields by accident this asserts loudly.
    snap = ScoreSnapshot(symbol="005930")
    actual = set(snap.__dataclass_fields__.keys())
    assert actual == set(SCORE_SNAPSHOT_FIELDS)
    forbidden = {"quantity", "price", "account", "broker", "order_type", "side"}
    assert actual.isdisjoint(forbidden)


def test_score_snapshot_independent_risk_flags_per_instance():
    a = ScoreSnapshot(symbol="A")
    b = ScoreSnapshot(symbol="B")
    a.risk_flags.append("STOP_LOSS_NEAR")
    assert b.risk_flags == [], "default_factory should produce independent lists"


# ---------------------------------------------------------------------------
# StrategyInterface ABC
# ---------------------------------------------------------------------------


def test_strategy_interface_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        StrategyInterface()  # type: ignore[abstract]


def test_concrete_strategy_implements_interface():
    for cls in (TopGradeStrategy, HighScoreStrategy, MultiSignalStrategy):
        instance = cls()
        assert isinstance(instance, StrategyInterface)
        assert isinstance(instance.name, str) and instance.name
        assert isinstance(instance.version, str) and instance.version


# ---------------------------------------------------------------------------
# TopGradeStrategy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("grade", ["S", "A"])
def test_top_grade_strategy_buys_on_S_or_A(grade):
    strategy = TopGradeStrategy()
    sig = strategy.evaluate(ScoreSnapshot(symbol="005930", grade=grade))
    assert sig.action == STRATEGY_ACTION_BUY
    if grade == "S":
        assert sig.confidence == Decimal("0.9")
    else:
        assert sig.confidence == Decimal("0.75")
    assert sig.evidence == {"grade": grade}


def test_top_grade_strategy_avoids_on_D():
    sig = TopGradeStrategy().evaluate(ScoreSnapshot(symbol="005930", grade="D"))
    assert sig.action == STRATEGY_ACTION_AVOID
    assert sig.confidence == Decimal("0.75")


@pytest.mark.parametrize("grade", ["B", "C", "Z", "", None])
def test_top_grade_strategy_passes_on_other_grades(grade):
    sig = TopGradeStrategy().evaluate(ScoreSnapshot(symbol="005930", grade=grade))
    assert sig.action == STRATEGY_ACTION_PASS
    assert sig.confidence == Decimal("0.5")


def test_top_grade_strategy_handles_lowercase_grade():
    sig = TopGradeStrategy().evaluate(ScoreSnapshot(symbol="005930", grade="a"))
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.evidence == {"grade": "A"}


# ---------------------------------------------------------------------------
# HighScoreStrategy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score,expected_action",
    [
        (Decimal("100"), STRATEGY_ACTION_BUY),
        (Decimal("80"), STRATEGY_ACTION_BUY),
        (Decimal("75"), STRATEGY_ACTION_BUY),
        (Decimal("74.99"), STRATEGY_ACTION_PASS),
        (Decimal("60"), STRATEGY_ACTION_PASS),
        (Decimal("50"), STRATEGY_ACTION_PASS),
        (Decimal("36"), STRATEGY_ACTION_PASS),
        (Decimal("35"), STRATEGY_ACTION_AVOID),
        (Decimal("20"), STRATEGY_ACTION_AVOID),
        (Decimal("0"), STRATEGY_ACTION_AVOID),
    ],
)
def test_high_score_strategy_action_thresholds(score, expected_action):
    sig = HighScoreStrategy().evaluate(
        ScoreSnapshot(symbol="005930", total_score=score),
    )
    assert sig.action == expected_action


def test_high_score_strategy_passes_when_score_missing():
    sig = HighScoreStrategy().evaluate(ScoreSnapshot(symbol="005930"))
    assert sig.action == STRATEGY_ACTION_PASS
    assert sig.confidence == Decimal("0.5")
    assert sig.evidence == {"total_score": None}


def test_high_score_strategy_confidence_in_range():
    """Confidence is clamped to [0, 1] regardless of input score range."""

    for score in (Decimal("75"), Decimal("100"), Decimal("999"), Decimal("0"), Decimal("-50")):
        sig = HighScoreStrategy().evaluate(
            ScoreSnapshot(symbol="005930", total_score=score),
        )
        assert Decimal("0") <= sig.confidence <= Decimal("1")


# ---------------------------------------------------------------------------
# MultiSignalStrategy
# ---------------------------------------------------------------------------


def _good_buy_snapshot(**overrides):
    base = {
        "symbol": "005930",
        "total_score": Decimal("70"),
        "fundamental_score": Decimal("65"),
        "news_score": Decimal("55"),
        "earnings_score": Decimal("60"),
        "risk_level": "LOW",
        "risk_flags": [],
    }
    base.update(overrides)
    return ScoreSnapshot(**base)


def test_multi_signal_buys_when_all_conditions_met():
    sig = MultiSignalStrategy().evaluate(_good_buy_snapshot())
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.7")


def test_multi_signal_buys_with_no_earnings_score_yet():
    sig = MultiSignalStrategy().evaluate(_good_buy_snapshot(earnings_score=None))
    assert sig.action == STRATEGY_ACTION_BUY


def test_multi_signal_avoids_on_high_risk_level():
    snap = _good_buy_snapshot(risk_level="HIGH")
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_AVOID
    assert "risk_level" in sig.reason.lower() or "HIGH" in sig.reason


def test_multi_signal_avoids_on_risk_disclosure_flag():
    snap = _good_buy_snapshot(
        risk_level="LOW",
        risk_flags=["RISK_DISCLOSURE", "OTHER"],
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_AVOID
    assert "RISK_DISCLOSURE" in sig.reason


def test_multi_signal_avoids_when_total_score_low_even_without_other_risks():
    snap = _good_buy_snapshot(total_score=Decimal("30"))
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_AVOID


def test_multi_signal_passes_when_score_mid_range_and_no_risk():
    snap = _good_buy_snapshot(total_score=Decimal("50"))
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_PASS


def test_multi_signal_passes_when_fundamental_below_threshold():
    snap = _good_buy_snapshot(fundamental_score=Decimal("55"))
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_PASS


def test_multi_signal_passes_when_news_below_threshold():
    snap = _good_buy_snapshot(news_score=Decimal("45"))
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_PASS


def test_multi_signal_passes_when_earnings_below_threshold():
    snap = _good_buy_snapshot(earnings_score=Decimal("40"))
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_PASS


def test_multi_signal_confidence_boost_from_earnings_beat_evidence():
    snap = _good_buy_snapshot(
        evidence={"earnings_evidence": {"surprise_type": "BEAT"}},
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.8")  # 0.7 base + 0.1 BEAT boost


def test_multi_signal_confidence_boost_from_positive_news_skew():
    snap = _good_buy_snapshot(
        evidence={
            "news_evidence": {
                "positive_count": 3,
                "negative_count": 1,
            },
        },
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.75")  # 0.7 + 0.05


def test_multi_signal_combined_evidence_boosts_clamp_to_one():
    snap = _good_buy_snapshot(
        evidence={
            "earnings_evidence": {"surprise_type": "BEAT"},
            "news_evidence": {"positive_count": 5, "negative_count": 0},
        },
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.85")  # 0.7 + 0.1 + 0.05
    assert sig.confidence <= Decimal("1")


def test_multi_signal_no_boost_when_news_skew_non_positive():
    snap = _good_buy_snapshot(
        evidence={
            "news_evidence": {"positive_count": 1, "negative_count": 1},
        },
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.7")


def test_multi_signal_handles_missing_evidence_dict_gracefully():
    snap = _good_buy_snapshot(evidence=None)
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.7")


def test_multi_signal_handles_malformed_news_evidence_gracefully():
    """Strings where ints expected, or non-dict shapes, should not raise."""

    snap = _good_buy_snapshot(
        evidence={"news_evidence": "not-a-dict"},
    )
    sig = MultiSignalStrategy().evaluate(snap)
    assert sig.action == STRATEGY_ACTION_BUY
    assert sig.confidence == Decimal("0.7")

    snap2 = _good_buy_snapshot(
        evidence={"news_evidence": {"positive_count": "abc", "negative_count": None}},
    )
    sig2 = MultiSignalStrategy().evaluate(snap2)
    assert sig2.action == STRATEGY_ACTION_BUY
    assert sig2.confidence == Decimal("0.7")


# ---------------------------------------------------------------------------
# Cross-strategy guard: empty / null snapshot must never raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy_cls", [TopGradeStrategy, HighScoreStrategy, MultiSignalStrategy],
)
def test_strategies_return_pass_on_completely_empty_snapshot(strategy_cls):
    sig = strategy_cls().evaluate(ScoreSnapshot(symbol="005930"))
    # Defensive default: PASS for missing data on every strategy.
    assert sig.action == STRATEGY_ACTION_PASS
    assert Decimal("0") <= sig.confidence <= Decimal("1")
