"""Unit tests for ProviderScorePolicy — v0.13 Phase A.

Invariants verified:
  - DATA_SOURCE_RELIABILITY: PROVIDER=1.00, CSV=0.90, MANUAL=0.80
  - FAKE is always bypassed (score returned unchanged), policy ON or OFF
  - Policy disabled → score returned unchanged for ALL data_source values
  - Unknown / None / blank data_source → factor 1.00 fallback (no attenuation)
  - Boundary scores: zero, maximum, negative
  - float and Decimal input conversion
  - ROUND_HALF_UP quantization to 4 decimal places
  - ScoringEngine weights unchanged assertion
  - No external network calls
  - Default policy is disabled (PROVIDER_SCORE_POLICY_ENABLED=False)
"""

import socket
from decimal import Decimal

from app.scoring.provider_policy import DATA_SOURCE_RELIABILITY, ProviderScorePolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _policy(enabled: bool = True) -> ProviderScorePolicy:
    return ProviderScorePolicy(enabled=enabled)


# ---------------------------------------------------------------------------
# DATA_SOURCE_RELIABILITY constants
# ---------------------------------------------------------------------------


def test_provider_factor_is_1_00():
    assert DATA_SOURCE_RELIABILITY["PROVIDER"] == Decimal("1.00")


def test_csv_factor_is_0_90():
    assert DATA_SOURCE_RELIABILITY["CSV"] == Decimal("0.90")


def test_manual_factor_is_0_80():
    assert DATA_SOURCE_RELIABILITY["MANUAL"] == Decimal("0.80")


def test_fake_absent_from_reliability_map():
    assert "FAKE" not in DATA_SOURCE_RELIABILITY


# ---------------------------------------------------------------------------
# Policy enabled — known sources
# ---------------------------------------------------------------------------


def test_provider_no_attenuation():
    result = _policy().apply_policy(Decimal("80"), "PROVIDER")
    assert result == Decimal("80.0000")  # 80 * 1.00


def test_csv_attenuates_10_percent():
    result = _policy().apply_policy(Decimal("80"), "CSV")
    assert result == Decimal("72.0000")  # 80 * 0.90


def test_manual_attenuates_20_percent():
    result = _policy().apply_policy(Decimal("80"), "MANUAL")
    assert result == Decimal("64.0000")  # 80 * 0.80


def test_csv_non_round_score():
    # 77 * 0.9 = 69.3 → 69.3000
    result = _policy().apply_policy(Decimal("77"), "CSV")
    assert result == Decimal("69.3000")


# ---------------------------------------------------------------------------
# FAKE bypass — score returned unchanged regardless of policy state
# ---------------------------------------------------------------------------


def test_fake_bypass_when_policy_enabled():
    result = _policy(enabled=True).apply_policy(Decimal("70.1234"), "FAKE")
    assert result == Decimal("70.1234")


def test_fake_bypass_when_policy_disabled():
    result = _policy(enabled=False).apply_policy(Decimal("70.1234"), "FAKE")
    assert result == Decimal("70.1234")


# ---------------------------------------------------------------------------
# Policy disabled — all sources return score unchanged
# ---------------------------------------------------------------------------


def test_disabled_provider_unchanged():
    result = _policy(enabled=False).apply_policy(Decimal("60.5"), "PROVIDER")
    assert result == Decimal("60.5")


def test_disabled_csv_unchanged():
    result = _policy(enabled=False).apply_policy(Decimal("60.5"), "CSV")
    assert result == Decimal("60.5")


def test_disabled_manual_unchanged():
    result = _policy(enabled=False).apply_policy(Decimal("60.5"), "MANUAL")
    assert result == Decimal("60.5")


def test_disabled_unknown_unchanged():
    result = _policy(enabled=False).apply_policy(Decimal("55"), "NONEXISTENT")
    assert result == Decimal("55")


# ---------------------------------------------------------------------------
# Unknown / None / blank data_source → factor 1.00 fallback
# ---------------------------------------------------------------------------


def test_unknown_source_factor_1_fallback():
    result = _policy().apply_policy(Decimal("50"), "UNKNOWN_SOURCE")
    assert result == Decimal("50.0000")


def test_none_source_factor_1_fallback():
    result = _policy().apply_policy(Decimal("50"), None)
    assert result == Decimal("50.0000")


def test_empty_string_source_factor_1_fallback():
    result = _policy().apply_policy(Decimal("50"), "")
    assert result == Decimal("50.0000")


# ---------------------------------------------------------------------------
# Boundary and edge scores
# ---------------------------------------------------------------------------


def test_zero_score_csv():
    result = _policy().apply_policy(Decimal("0"), "CSV")
    assert result == Decimal("0.0000")


def test_max_score_100_provider():
    result = _policy().apply_policy(Decimal("100"), "PROVIDER")
    assert result == Decimal("100.0000")


def test_negative_score_manual():
    result = _policy().apply_policy(Decimal("-10"), "MANUAL")
    assert result == Decimal("-8.0000")  # -10 * 0.80


# ---------------------------------------------------------------------------
# Input type handling
# ---------------------------------------------------------------------------


def test_float_input_csv():
    result = _policy().apply_policy(80.0, "CSV")
    assert result == Decimal("72.0000")


def test_decimal_input_exact_preservation_provider():
    score = Decimal("75.1234")
    result = _policy().apply_policy(score, "PROVIDER")
    assert result == Decimal("75.1234")


# ---------------------------------------------------------------------------
# Rounding: ROUND_HALF_UP to 4 decimal places
# ---------------------------------------------------------------------------


def test_rounding_half_up_at_boundary():
    # 0.55555 * 0.9 = 0.499995 → ROUND_HALF_UP → 0.5000
    result = _policy().apply_policy(Decimal("0.55555"), "CSV")
    assert result == Decimal("0.5000")


# ---------------------------------------------------------------------------
# Default state and property
# ---------------------------------------------------------------------------


def test_default_policy_is_disabled():
    p = ProviderScorePolicy()
    assert p.enabled is False


def test_enabled_property_reflects_constructor_arg():
    assert ProviderScorePolicy(enabled=False).enabled is False
    assert ProviderScorePolicy(enabled=True).enabled is True


# ---------------------------------------------------------------------------
# ScoringEngine weight unchanged assertion
# ---------------------------------------------------------------------------


def test_scoring_engine_new_recommendation_weights_unchanged():
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
# No external I/O
# ---------------------------------------------------------------------------


def test_no_external_network_calls(monkeypatch):
    def _block(*args, **kwargs):
        raise AssertionError("apply_policy must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", _block)
    monkeypatch.setattr(socket, "create_connection", _block)

    p = _policy(enabled=True)
    for src in ("PROVIDER", "CSV", "MANUAL", "FAKE", None, "", "UNKNOWN"):
        p.apply_policy(Decimal("60"), src)
