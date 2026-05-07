"""Unit tests for ScoreDeltaResult / compute_score_delta — v0.13 Phase B.

Invariants verified:
  - Policy OFF  → every component before==after, aggregate delta=="0.0000"
  - FAKE source → bypass; before==after for that component
  - PROVIDER    → factor 1.00; before==after
  - CSV         → factor 0.90; after = before * 0.90 (quantized)
  - MANUAL      → factor 0.80; after = before * 0.80 (quantized)
  - Multi-component sum matches individual deltas
  - Decimal rounding deterministic (ROUND_HALF_UP, 4 dp)
  - as_dict() is JSON-serialisable and contains only safe fields
  - Forbidden fields absent from as_dict()
  - None score treated as 0
  - ScoringEngine / HoldingCheckEngine weight unchanged
"""

import json
from decimal import Decimal

from app.scoring.provider_policy import ProviderScorePolicy
from app.scoring.score_delta import ComponentDelta, ScoreDeltaResult, compute_score_delta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _off() -> ProviderScorePolicy:
    return ProviderScorePolicy(enabled=False)


def _on() -> ProviderScorePolicy:
    return ProviderScorePolicy(enabled=True)


def _delta(components, *, enabled: bool = True) -> ScoreDeltaResult:
    return compute_score_delta(
        components=components,
        policy=ProviderScorePolicy(enabled=enabled),
    )


# ---------------------------------------------------------------------------
# Policy OFF — all deltas are zero
# ---------------------------------------------------------------------------


def test_policy_disabled_single_csv_delta_zero():
    result = _delta([("news", Decimal("60"), "CSV")], enabled=False)
    assert result.policy_enabled is False
    assert result.delta == Decimal("0.0000")
    assert result.score_before == result.score_after


def test_policy_disabled_all_components_delta_zero():
    result = _delta(
        [
            ("news", Decimal("60"), "CSV"),
            ("supply", Decimal("50"), "MANUAL"),
            ("fundamental", Decimal("70"), "PROVIDER"),
        ],
        enabled=False,
    )
    assert result.delta == Decimal("0.0000")
    for c in result.components:
        assert c.before == c.after


# ---------------------------------------------------------------------------
# FAKE bypass — before == after even when policy is ON
# ---------------------------------------------------------------------------


def test_fake_bypass_when_policy_enabled():
    result = _delta([("news", Decimal("70"), "FAKE")], enabled=True)
    assert result.delta == Decimal("0.0000")
    assert result.components[0].before == result.components[0].after
    assert result.components[0].factor == Decimal("1.00")


def test_fake_bypass_policy_disabled():
    result = _delta([("news", Decimal("70"), "FAKE")], enabled=False)
    assert result.delta == Decimal("0.0000")


# ---------------------------------------------------------------------------
# PROVIDER — factor 1.00, delta zero
# ---------------------------------------------------------------------------


def test_provider_factor_1_0_no_attenuation():
    result = _delta([("news", Decimal("80"), "PROVIDER")], enabled=True)
    assert result.components[0].factor == Decimal("1.00")
    assert result.components[0].before == Decimal("80.0000")
    assert result.components[0].after == Decimal("80.0000")
    assert result.delta == Decimal("0.0000")


# ---------------------------------------------------------------------------
# CSV attenuation
# ---------------------------------------------------------------------------


def test_csv_attenuates_by_10_percent():
    result = _delta([("news", Decimal("80"), "CSV")], enabled=True)
    c = result.components[0]
    assert c.factor == Decimal("0.90")
    assert c.before == Decimal("80.0000")
    assert c.after == Decimal("72.0000")  # 80 * 0.9
    assert result.delta == Decimal("-8.0000")


def test_csv_delta_sign_is_negative():
    result = _delta([("supply", Decimal("50"), "CSV")], enabled=True)
    assert result.delta < Decimal("0")


# ---------------------------------------------------------------------------
# MANUAL attenuation
# ---------------------------------------------------------------------------


def test_manual_attenuates_by_20_percent():
    result = _delta([("fundamental", Decimal("80"), "MANUAL")], enabled=True)
    c = result.components[0]
    assert c.factor == Decimal("0.80")
    assert c.before == Decimal("80.0000")
    assert c.after == Decimal("64.0000")  # 80 * 0.8
    assert result.delta == Decimal("-16.0000")


# ---------------------------------------------------------------------------
# Multi-component aggregate
# ---------------------------------------------------------------------------


def test_multi_component_total_delta():
    # CSV: 80 * 0.9 = 72  → delta -8
    # MANUAL: 60 * 0.8 = 48  → delta -12
    # PROVIDER: 70 * 1.0 = 70  → delta 0
    result = _delta(
        [
            ("news", Decimal("80"), "CSV"),
            ("earnings", Decimal("60"), "MANUAL"),
            ("ai", Decimal("70"), "PROVIDER"),
        ],
        enabled=True,
    )
    assert result.score_before == Decimal("210.0000")  # 80 + 60 + 70
    assert result.score_after == Decimal("190.0000")   # 72 + 48 + 70
    assert result.delta == Decimal("-20.0000")


def test_fake_and_csv_mixed():
    # FAKE: bypass → delta 0
    # CSV:  50 * 0.9 = 45 → delta -5
    result = _delta(
        [
            ("news", Decimal("50"), "FAKE"),
            ("supply", Decimal("50"), "CSV"),
        ],
        enabled=True,
    )
    assert result.delta == Decimal("-5.0000")


# ---------------------------------------------------------------------------
# None score treated as zero
# ---------------------------------------------------------------------------


def test_none_score_treated_as_zero_csv():
    result = _delta([("news", None, "CSV")], enabled=True)
    c = result.components[0]
    assert c.before == Decimal("0.0000")
    assert c.after == Decimal("0.0000")
    assert result.delta == Decimal("0.0000")


def test_empty_components_list_delta_zero():
    result = _delta([], enabled=True)
    assert result.delta == Decimal("0.0000")
    assert result.score_before == Decimal("0.0000")
    assert result.score_after == Decimal("0.0000")
    assert result.components == []


# ---------------------------------------------------------------------------
# Rounding determinism
# ---------------------------------------------------------------------------


def test_rounding_half_up_csv():
    # 77 * 0.9 = 69.3 → 69.3000
    result = _delta([("news", Decimal("77"), "CSV")], enabled=True)
    assert result.components[0].after == Decimal("69.3000")
    assert result.delta == Decimal("-7.7000")


def test_rounding_half_up_boundary():
    # 0.55555 * 0.9 = 0.499995 → ROUND_HALF_UP → 0.5000
    result = _delta([("news", Decimal("0.55555"), "CSV")], enabled=True)
    assert result.components[0].after == Decimal("0.5000")


# ---------------------------------------------------------------------------
# as_dict() — JSON-serialisable + safe fields only
# ---------------------------------------------------------------------------


def test_as_dict_json_serialisable():
    result = _delta(
        [("news", Decimal("60"), "CSV"), ("ai", Decimal("50"), "FAKE")],
        enabled=True,
    )
    d = result.as_dict()
    # Must round-trip through json.dumps without error
    serialised = json.dumps(d)
    parsed = json.loads(serialised)
    assert parsed["policy_enabled"] is True
    assert "delta" in parsed
    assert "components" in parsed
    assert len(parsed["components"]) == 2


def test_as_dict_forbidden_fields_absent():
    result = _delta([("news", Decimal("60"), "CSV")], enabled=True)
    d = result.as_dict()
    for bad_key in ("body", "full_text", "raw_text", "memo", "source_file_path", "secret"):
        assert bad_key not in d
        for c in d["components"]:
            assert bad_key not in c


def test_component_delta_as_dict_fields():
    result = _delta([("news", Decimal("80"), "CSV")], enabled=True)
    cd = result.components[0].as_dict()
    assert set(cd.keys()) == {"name", "data_source", "factor", "before", "after"}


# ---------------------------------------------------------------------------
# ScoringEngine weight unchanged assertion
# ---------------------------------------------------------------------------


def test_scoring_engine_weights_unchanged():
    from app.decision.scoring_engine import ScoringEngine

    w = ScoringEngine.NEW_RECOMMENDATION_WEIGHTS
    assert w["technical"] == Decimal("0.35")
    assert w["news"] == Decimal("0.25")
    assert w["supply"] == Decimal("0.15")
    assert w["fundamental"] == Decimal("0.15")
    assert w["ai"] == Decimal("0.10")
    assert sum(w.values()) == Decimal("1.00")

    hw = ScoringEngine.HOLDING_WEIGHTS
    assert hw["technical"] == Decimal("0.35")
    assert hw["news"] == Decimal("0.20")
    assert hw["earnings"] == Decimal("0.20")
    assert hw["ai"] == Decimal("0.15")
    assert hw["profit_management"] == Decimal("0.10")
    assert sum(hw.values()) == Decimal("1.00")
