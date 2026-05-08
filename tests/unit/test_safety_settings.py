"""Unit tests for v0.15 Phase A — Approval Trading Safety Layer settings.

Scope:
  * Paranoid defaults for the 7 new fields:
      - trading_safety_enabled = False
      - kill_switch_enabled    = True
      - approval_required      = True
      - max_order_amount       = 100,000
      - max_daily_order_amount = 1,000,000
      - max_position_ratio     = 0.20
      - max_daily_loss_amount  = 500,000
  * Env overrides via the documented variable names.
  * ``_as_strict_bool`` semantics: invalid token falls back to the default
    so a typo in .env does NOT silently flip kill_switch off.
  * ``__post_init__`` boundary validation rejects:
      - max_order_amount <= 0
      - max_daily_order_amount <= 0
      - max_position_ratio outside (0, 1]
      - max_daily_loss_amount < 0
  * Pre-existing v0.1 ~ v0.14 settings remain untouched (regression check).
  * No DB / Alembic / API / frontend / pip dependency changes.

These tests instantiate ``Settings`` directly with kwargs (frozen dataclass
constructor). They do NOT exercise ``get_settings()`` because that function
is ``lru_cache``-d and would carry process-level state; the env-override
tests use ``monkeypatch`` against ``os.environ`` and construct a fresh
``Settings()`` per assertion.
"""

from __future__ import annotations

import pytest

from app.config.settings import (
    Settings,
    _as_strict_bool,
)


# ---------------------------------------------------------------------------
# 1. Paranoid defaults
# ---------------------------------------------------------------------------


def test_safety_defaults_are_paranoid(monkeypatch: pytest.MonkeyPatch) -> None:
    """All 7 safety fields default to the documented paranoid values when
    no env override is present."""
    for var in (
        "TRADING_SAFETY_ENABLED",
        "KILL_SWITCH_ENABLED",
        "APPROVAL_REQUIRED",
        "MAX_ORDER_AMOUNT",
        "MAX_DAILY_ORDER_AMOUNT",
        "MAX_POSITION_RATIO",
        "MAX_DAILY_LOSS_AMOUNT",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings()

    assert settings.trading_safety_enabled is False
    assert settings.kill_switch_enabled is True
    assert settings.approval_required is True
    assert settings.max_order_amount == 100_000
    assert settings.max_daily_order_amount == 1_000_000
    assert settings.max_position_ratio == 0.20
    assert settings.max_daily_loss_amount == 500_000


def test_kill_switch_enabled_by_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    assert Settings().kill_switch_enabled is True


def test_trading_safety_disabled_by_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRADING_SAFETY_ENABLED", raising=False)
    assert Settings().trading_safety_enabled is False


def test_approval_required_true_by_default_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPROVAL_REQUIRED", raising=False)
    assert Settings().approval_required is True


# ---------------------------------------------------------------------------
# 2. Env override -- happy paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("on", True),
        ("YES", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("off", False),
        ("NO", False),
    ],
)
def test_trading_safety_enabled_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("TRADING_SAFETY_ENABLED", env_value)
    assert Settings().trading_safety_enabled is expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        ("0", False),
        ("1", True),
        ("on", True),
        ("off", False),
    ],
)
def test_kill_switch_enabled_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("KILL_SWITCH_ENABLED", env_value)
    assert Settings().kill_switch_enabled is expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        ("0", False),
        ("1", True),
    ],
)
def test_approval_required_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("APPROVAL_REQUIRED", env_value)
    assert Settings().approval_required is expected


def test_numeric_env_overrides_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_ORDER_AMOUNT", "250000")
    monkeypatch.setenv("MAX_DAILY_ORDER_AMOUNT", "5000000")
    monkeypatch.setenv("MAX_POSITION_RATIO", "0.35")
    monkeypatch.setenv("MAX_DAILY_LOSS_AMOUNT", "1000000")

    settings = Settings()

    assert settings.max_order_amount == 250_000
    assert settings.max_daily_order_amount == 5_000_000
    assert settings.max_position_ratio == 0.35
    assert settings.max_daily_loss_amount == 1_000_000


# ---------------------------------------------------------------------------
# 3. Strict-bool helper -- typo in .env keeps the safety guard ON
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("typo", ["", "maybe", "garbage", "truthy", "0.0", "  "])
def test_kill_switch_enabled_paranoid_on_typo(
    monkeypatch: pytest.MonkeyPatch, typo: str
) -> None:
    """A garbage / typo'd KILL_SWITCH_ENABLED must NOT silently flip the
    switch off. The paranoid default (True) must hold."""
    monkeypatch.setenv("KILL_SWITCH_ENABLED", typo)
    assert Settings().kill_switch_enabled is True


@pytest.mark.parametrize("typo", ["maybe", "garbage", "truthy"])
def test_approval_required_paranoid_on_typo(
    monkeypatch: pytest.MonkeyPatch, typo: str
) -> None:
    monkeypatch.setenv("APPROVAL_REQUIRED", typo)
    assert Settings().approval_required is True


def test_as_strict_bool_returns_default_for_unknown_token() -> None:
    assert _as_strict_bool("maybe", default=True) is True
    assert _as_strict_bool("maybe", default=False) is False
    assert _as_strict_bool(None, default=True) is True
    assert _as_strict_bool("", default=True) is True


def test_as_strict_bool_recognises_canonical_tokens() -> None:
    for tok in ("1", "true", "True", "YES", "on", " on "):
        assert _as_strict_bool(tok, default=False) is True
    for tok in ("0", "false", "False", "NO", "off", " off "):
        assert _as_strict_bool(tok, default=True) is False


# ---------------------------------------------------------------------------
# 4. Boundary validation in __post_init__
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -100_000])
def test_max_order_amount_must_be_positive(bad_value: int) -> None:
    with pytest.raises(ValueError, match="max_order_amount must be > 0"):
        Settings(max_order_amount=bad_value)


@pytest.mark.parametrize("bad_value", [0, -1, -1_000_000])
def test_max_daily_order_amount_must_be_positive(bad_value: int) -> None:
    with pytest.raises(ValueError, match="max_daily_order_amount must be > 0"):
        Settings(max_daily_order_amount=bad_value)


@pytest.mark.parametrize("bad_value", [-0.1, 0.0, 1.01, 2.0, -1.0])
def test_max_position_ratio_must_be_in_open_zero_to_one(bad_value: float) -> None:
    with pytest.raises(ValueError, match=r"max_position_ratio must be in \(0, 1\]"):
        Settings(max_position_ratio=bad_value)


@pytest.mark.parametrize("good_value", [0.0001, 0.05, 0.20, 0.50, 1.0])
def test_max_position_ratio_accepts_in_range_values(good_value: float) -> None:
    s = Settings(max_position_ratio=good_value)
    assert s.max_position_ratio == good_value


def test_max_daily_loss_amount_rejects_negative() -> None:
    with pytest.raises(ValueError, match="max_daily_loss_amount must be >= 0"):
        Settings(max_daily_loss_amount=-1)


def test_max_daily_loss_amount_zero_is_allowed() -> None:
    """0 means 'no loss tolerated' — a valid (if extreme) operator policy."""
    assert Settings(max_daily_loss_amount=0).max_daily_loss_amount == 0


# ---------------------------------------------------------------------------
# 5. Frozen dataclass — fields cannot be mutated after construction
# ---------------------------------------------------------------------------


def test_settings_is_frozen_for_safety_fields() -> None:
    s = Settings()
    with pytest.raises(Exception):  # FrozenInstanceError subclasses Exception
        s.kill_switch_enabled = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6. Regression: pre-existing settings unchanged
# ---------------------------------------------------------------------------


def test_v014_paper_trading_default_still_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase A must NOT regress paper_trading_enabled default."""
    monkeypatch.delenv("PAPER_TRADING_ENABLED", raising=False)
    assert Settings().paper_trading_enabled is False


def test_v01_feature_real_order_execution_default_still_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase A must NOT regress the v0.1 real-order kill flag."""
    monkeypatch.delenv("FEATURE_REAL_ORDER_EXECUTION", raising=False)
    assert Settings().feature_real_order_execution is False


def test_v01_feature_full_auto_default_still_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FEATURE_FULL_AUTO", raising=False)
    assert Settings().feature_full_auto is False


# ---------------------------------------------------------------------------
# 7. Phase A scope — nothing outside settings/tests should change.
# ---------------------------------------------------------------------------


def test_phase_a_does_not_introduce_new_alembic_revisions() -> None:
    """Phase A must not change the head Alembic revision."""
    from pathlib import Path

    versions_dir = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions"
    )
    revisions = sorted(p.name for p in versions_dir.glob("0*.py"))
    # v0.14 closed at 0006_virtual_positions; Phase A must not touch this.
    assert revisions == [
        "0001_baseline_v0_7.py",
        "0002_auth_foundation.py",
        "0003_watchlist.py",
        "0004_user_preferences.py",
        "0005_virtual_trading_core.py",
        "0006_virtual_positions.py",
    ]


def test_phase_a_does_not_add_paper_or_approval_routes_module() -> None:
    """Phase A must not create the v0.15 Phase D Approval routes module yet."""
    from pathlib import Path

    api_dir = (
        Path(__file__).resolve().parents[2] / "app" / "api"
    )
    assert not (api_dir / "approval_routes.py").exists(), (
        "Phase A must not introduce app/api/approval_routes.py — that is "
        "Phase D scope."
    )
