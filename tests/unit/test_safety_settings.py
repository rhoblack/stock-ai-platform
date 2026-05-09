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
    can_attempt_real_order_settings,
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


def test_phase_d_alembic_head_advanced_to_0008() -> None:
    """v0.15 Phase D introduced ``0008_approval_audit_logs``; v0.16 Phase C
    subsequently added 0009_real_orders and 0010_real_fills.
    This test verifies the full revision chain through 0010."""
    from pathlib import Path

    versions_dir = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions"
    )
    revisions = sorted(p.name for p in versions_dir.glob("0*.py"))
    assert revisions == [
        "0001_baseline_v0_7.py",
        "0002_auth_foundation.py",
        "0003_watchlist.py",
        "0004_user_preferences.py",
        "0005_virtual_trading_core.py",
        "0006_virtual_positions.py",
        "0007_order_candidates.py",
        "0008_approval_audit_logs.py",
        "0009_real_orders.py",
        "0010_real_fills.py",
    ]


def test_phase_d_approval_modules_exist() -> None:
    """v0.15 Phase D introduces approval_routes / approval_service /
    approval_audit_log."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert (root / "app" / "api" / "approval_routes.py").exists()
    assert (root / "app" / "approval" / "__init__.py").exists()
    assert (root / "app" / "approval" / "approval_service.py").exists()
    assert (
        root / "app" / "data" / "repositories" / "approval_audit_log.py"
    ).exists()


def test_phase_c_pre_trade_risk_engine_module_exists() -> None:
    """v0.15 Phase C introduces ``app/risk/pre_trade_risk_engine.py``.

    Phase D's ApprovalService imports :class:`PreTradeRiskEngine`; this
    guard catches accidental deletion.
    """
    from pathlib import Path

    risk_dir = (
        Path(__file__).resolve().parents[2] / "app" / "risk"
    )
    assert (risk_dir / "__init__.py").exists()
    assert (risk_dir / "pre_trade_risk_engine.py").exists()


# ---------------------------------------------------------------------------
# 8. v0.16 Phase A — Real Order Integration Skeleton settings
# ---------------------------------------------------------------------------


def test_v016_real_trading_defaults_are_paranoid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All 5 v0.16 real-trading fields default to the documented paranoid
    values when no env override is present."""
    for var in (
        "REAL_TRADING_ENABLED",
        "KIS_ORDER_ENABLED",
        "REAL_ORDER_DRY_RUN",
        "MAX_REAL_ORDER_AMOUNT",
        "MAX_REAL_DAILY_ORDER_AMOUNT",
    ):
        monkeypatch.delenv(var, raising=False)

    s = Settings()

    assert s.real_trading_enabled is False
    assert s.kis_order_enabled is False
    assert s.real_order_dry_run is True
    assert s.max_real_order_amount == 100_000
    assert s.max_real_daily_order_amount == 1_000_000


def test_real_trading_enabled_false_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REAL_TRADING_ENABLED", raising=False)
    assert Settings().real_trading_enabled is False


def test_kis_order_enabled_false_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KIS_ORDER_ENABLED", raising=False)
    assert Settings().kis_order_enabled is False


def test_real_order_dry_run_true_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REAL_ORDER_DRY_RUN", raising=False)
    assert Settings().real_order_dry_run is True


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
def test_real_trading_enabled_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("REAL_TRADING_ENABLED", env_value)
    assert Settings().real_trading_enabled is expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("on", True),
        ("off", False),
    ],
)
def test_kis_order_enabled_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("KIS_ORDER_ENABLED", env_value)
    assert Settings().kis_order_enabled is expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
    ],
)
def test_real_order_dry_run_env_override(
    monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
) -> None:
    monkeypatch.setenv("REAL_ORDER_DRY_RUN", env_value)
    assert Settings().real_order_dry_run is expected


def test_max_real_order_amount_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_REAL_ORDER_AMOUNT", "50000")
    monkeypatch.setenv("MAX_REAL_DAILY_ORDER_AMOUNT", "500000")
    s = Settings()
    assert s.max_real_order_amount == 50_000
    assert s.max_real_daily_order_amount == 500_000


# ---------------------------------------------------------------------------
# 9. v0.16 — strict-bool: typo in .env keeps paranoid defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("typo", ["", "maybe", "garbage", "truthy", "0.0", "  "])
def test_real_trading_enabled_typo_keeps_false(
    monkeypatch: pytest.MonkeyPatch, typo: str
) -> None:
    """A garbage REAL_TRADING_ENABLED must NOT silently flip the switch on."""
    monkeypatch.setenv("REAL_TRADING_ENABLED", typo)
    assert Settings().real_trading_enabled is False


@pytest.mark.parametrize("typo", ["", "maybe", "garbage"])
def test_kis_order_enabled_typo_keeps_false(
    monkeypatch: pytest.MonkeyPatch, typo: str
) -> None:
    monkeypatch.setenv("KIS_ORDER_ENABLED", typo)
    assert Settings().kis_order_enabled is False


@pytest.mark.parametrize("typo", ["", "maybe", "garbage"])
def test_real_order_dry_run_typo_keeps_true(
    monkeypatch: pytest.MonkeyPatch, typo: str
) -> None:
    """A garbage REAL_ORDER_DRY_RUN must NOT silently flip dry-run off."""
    monkeypatch.setenv("REAL_ORDER_DRY_RUN", typo)
    assert Settings().real_order_dry_run is True


# ---------------------------------------------------------------------------
# 10. v0.16 — boundary validation for real-order amount caps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -100_000])
def test_max_real_order_amount_must_be_positive(bad_value: int) -> None:
    with pytest.raises(ValueError, match="max_real_order_amount must be > 0"):
        Settings(max_real_order_amount=bad_value)


@pytest.mark.parametrize("bad_value", [0, -1, -1_000_000])
def test_max_real_daily_order_amount_must_be_positive(bad_value: int) -> None:
    with pytest.raises(ValueError, match="max_real_daily_order_amount must be > 0"):
        Settings(max_real_daily_order_amount=bad_value)


def test_max_real_order_amount_cannot_exceed_daily() -> None:
    """Single order cap must not exceed the daily cumulative cap."""
    with pytest.raises(ValueError, match="max_real_order_amount.*must be.*<=.*max_real_daily"):
        Settings(max_real_order_amount=500_000, max_real_daily_order_amount=100_000)


def test_max_real_order_amount_equal_to_daily_is_allowed() -> None:
    """Edge case: single order cap == daily cap is valid."""
    s = Settings(max_real_order_amount=100_000, max_real_daily_order_amount=100_000)
    assert s.max_real_order_amount == 100_000
    assert s.max_real_daily_order_amount == 100_000


# ---------------------------------------------------------------------------
# 11. v0.16 — can_attempt_real_order_settings() helper
# ---------------------------------------------------------------------------


def test_can_attempt_real_order_settings_false_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With all paranoid defaults, real-order execution is structurally impossible."""
    for var in (
        "REAL_TRADING_ENABLED",
        "KIS_ORDER_ENABLED",
        "REAL_ORDER_DRY_RUN",
        "TRADING_SAFETY_ENABLED",
        "KILL_SWITCH_ENABLED",
        "APPROVAL_REQUIRED",
    ):
        monkeypatch.delenv(var, raising=False)
    assert can_attempt_real_order_settings(Settings()) is False


def test_can_attempt_real_order_settings_true_when_all_gates_open() -> None:
    """Returns True only when every required gate is in the active state."""
    s = Settings(
        trading_safety_enabled=True,
        kill_switch_enabled=False,
        approval_required=True,
        real_trading_enabled=True,
        kis_order_enabled=True,
        real_order_dry_run=False,
    )
    assert can_attempt_real_order_settings(s) is True


@pytest.mark.parametrize(
    "closed_gate,kwargs",
    [
        ("trading_safety_enabled=False",  {"trading_safety_enabled": False}),
        ("kill_switch_enabled=True",      {"kill_switch_enabled": True}),
        ("approval_required=False",       {"approval_required": False}),
        ("real_trading_enabled=False",    {"real_trading_enabled": False}),
        ("kis_order_enabled=False",       {"kis_order_enabled": False}),
        ("real_order_dry_run=True",       {"real_order_dry_run": True}),
    ],
)
def test_can_attempt_real_order_settings_one_closed_gate_blocks(
    closed_gate: str, kwargs: dict
) -> None:
    """Closing any single gate must make the helper return False."""
    base = dict(
        trading_safety_enabled=True,
        kill_switch_enabled=False,
        approval_required=True,
        real_trading_enabled=True,
        kis_order_enabled=True,
        real_order_dry_run=False,
    )
    base.update(kwargs)
    assert can_attempt_real_order_settings(Settings(**base)) is False, (
        f"Expected False when {closed_gate}"
    )


# ---------------------------------------------------------------------------
# 12. v0.16 Phase A scope — Alembic / modules unchanged
# ---------------------------------------------------------------------------


def test_v016_phase_a_alembic_head_through_0010(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase A added no Alembic revision (head was 0008). Phase C subsequently
    added 0009_real_orders and 0010_real_fills. Verify the full chain."""
    from pathlib import Path

    versions_dir = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions"
    )
    revisions = sorted(p.name for p in versions_dir.glob("0*.py"))
    assert revisions == [
        "0001_baseline_v0_7.py",
        "0002_auth_foundation.py",
        "0003_watchlist.py",
        "0004_user_preferences.py",
        "0005_virtual_trading_core.py",
        "0006_virtual_positions.py",
        "0007_order_candidates.py",
        "0008_approval_audit_logs.py",
        "0009_real_orders.py",
        "0010_real_fills.py",
    ], f"Unexpected revisions: {revisions}"


def test_v016_phase_c_real_order_orm_exists() -> None:
    """Phase C creates real_order.py and real_fill.py — verify both are present."""
    from pathlib import Path

    repo_dir = Path(__file__).resolve().parents[2] / "app" / "data" / "repositories"
    assert (repo_dir / "real_order.py").exists(), (
        "real_order.py must exist after Phase C"
    )
    assert (repo_dir / "real_fill.py").exists(), (
        "real_fill.py must exist after Phase C"
    )


# ---------------------------------------------------------------------------
# 13. v0.16 regression — v0.15 safety defaults still intact
# ---------------------------------------------------------------------------


def test_v016_does_not_regress_v015_kill_switch_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    assert Settings().kill_switch_enabled is True


def test_v016_does_not_regress_v015_trading_safety_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRADING_SAFETY_ENABLED", raising=False)
    assert Settings().trading_safety_enabled is False


def test_v016_does_not_regress_v014_paper_trading_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PAPER_TRADING_ENABLED", raising=False)
    assert Settings().paper_trading_enabled is False


# ---------------------------------------------------------------------------
# 14. v1.0 Phase A — RUNBOOK_REAL_TRADING.md presence + required keywords
# ---------------------------------------------------------------------------


def _runbook_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[2] / "RUNBOOK_REAL_TRADING.md"


def test_v10_phase_a_runbook_exists() -> None:
    """Phase A produces RUNBOOK_REAL_TRADING.md at repo root."""
    assert _runbook_path().exists(), (
        "RUNBOOK_REAL_TRADING.md must exist at repo root after v1.0 Phase A"
    )


@pytest.mark.parametrize(
    "keyword",
    [
        # Mandatory env-var names — runbook must show operators what to set
        "REAL_TRADING_ENABLED",
        "KIS_ORDER_ENABLED",
        "REAL_ORDER_DRY_RUN",
        "KILL_SWITCH_ENABLED",
        "APPROVAL_REQUIRED",
        "TRADING_SAFETY_ENABLED",
        "MAX_REAL_ORDER_AMOUNT",
        "MAX_REAL_DAILY_ORDER_AMOUNT",
        # Mandatory section anchors — runbook must contain §1~§9
        "§1",
        "§2",
        "§3",
        "§4",
        "§5",
        "§6",
        "§7",
        "§8",
        "§9",
        # Mandatory policy lockdowns — both autotrade modes named explicitly
        "FULL_AUTO",
        "SMALL_AUTO",
    ],
)
def test_v10_phase_a_runbook_contains_required_keywords(keyword: str) -> None:
    """Runbook must surface every safety knob and forbidden mode by name."""
    text = _runbook_path().read_text(encoding="utf-8")
    assert keyword in text, (
        f"RUNBOOK_REAL_TRADING.md must contain {keyword!r}"
    )


def test_v10_phase_a_runbook_forbids_full_auto_and_small_auto() -> None:
    """Runbook §9 must explicitly mark FULL_AUTO + SMALL_AUTO as forbidden."""
    text = _runbook_path().read_text(encoding="utf-8")
    # The §9 lockdown lines start with the no-entry symbol ❌.
    assert "❌ **FULL_AUTO" in text, (
        "Runbook §9 must explicitly forbid FULL_AUTO autotrade"
    )
    assert "❌ **SMALL_AUTO" in text, (
        "Runbook §9 must explicitly forbid SMALL_AUTO autotrade"
    )


def test_v10_phase_a_runbook_forbids_user_approval_bypass() -> None:
    """Runbook §9 must explicitly forbid user-approval-less orders."""
    text = _runbook_path().read_text(encoding="utf-8")
    assert "❌ **사용자 승인 없는 주문**" in text, (
        "Runbook §9 must forbid user-approval-less orders"
    )


def test_v10_phase_a_runbook_forbids_real_default_on() -> None:
    """Runbook §9 must lock REAL_TRADING_ENABLED / KIS_ORDER_ENABLED /
    REAL_ORDER_DRY_RUN paranoid defaults — no default-ON real trading."""
    text = _runbook_path().read_text(encoding="utf-8")
    assert "❌ **실거래 default ON**" in text, (
        "Runbook §9 must forbid default-ON real trading"
    )


# ---------------------------------------------------------------------------
# 15. v1.0 Phase A — paranoid default re-verification (ALL safety gates)
# ---------------------------------------------------------------------------


def test_v10_phase_a_all_paranoid_defaults_intact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-verification of every safety/real-trading default at the start of v1.0.

    No env override, no Settings kwarg — purely the .env-less default state.
    Any drift here is a regression in the safety baseline.
    """
    for var in (
        # v0.15 layer
        "TRADING_SAFETY_ENABLED",
        "KILL_SWITCH_ENABLED",
        "APPROVAL_REQUIRED",
        "MAX_ORDER_AMOUNT",
        "MAX_DAILY_ORDER_AMOUNT",
        # v0.16 layer
        "REAL_TRADING_ENABLED",
        "KIS_ORDER_ENABLED",
        "REAL_ORDER_DRY_RUN",
        "MAX_REAL_ORDER_AMOUNT",
        "MAX_REAL_DAILY_ORDER_AMOUNT",
        # adjacent gates
        "PAPER_TRADING_ENABLED",
        "AUTH_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)

    s = Settings()

    # v0.15 — paranoid Approval layer
    assert s.trading_safety_enabled is False
    assert s.kill_switch_enabled is True
    assert s.approval_required is True

    # v0.16 — paranoid Real Order layer
    assert s.real_trading_enabled is False
    assert s.kis_order_enabled is False
    assert s.real_order_dry_run is True

    # v0.14 — paranoid Paper layer (still off)
    assert s.paper_trading_enabled is False

    # v0.8 — auth default off (matches dev/CI baseline)
    assert s.auth_enabled is False

    # Real-order execution gate is structurally False under defaults
    assert can_attempt_real_order_settings(s) is False


def test_v10_phase_a_all_real_trading_settings_default_to_paranoid_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare assertions of the 5 v0.16 real-trading defaults at the start of v1.0."""
    for var in (
        "REAL_TRADING_ENABLED",
        "KIS_ORDER_ENABLED",
        "REAL_ORDER_DRY_RUN",
        "MAX_REAL_ORDER_AMOUNT",
        "MAX_REAL_DAILY_ORDER_AMOUNT",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings()
    assert s.real_trading_enabled is False
    assert s.kis_order_enabled is False
    assert s.real_order_dry_run is True
    assert s.max_real_order_amount == 100_000
    assert s.max_real_daily_order_amount == 1_000_000


# ---------------------------------------------------------------------------
# 16. v1.0 Phase A — validate_real_trading_operating_limits() advisory helper
# ---------------------------------------------------------------------------


def test_v10_validate_operating_limits_empty_for_paranoid_defaults() -> None:
    """Default 100k / 1M caps are well within recommended thresholds."""
    from app.config.settings import validate_real_trading_operating_limits

    warnings = validate_real_trading_operating_limits(Settings())
    assert warnings == [], (
        f"Paranoid defaults must produce zero advisories, got {warnings!r}"
    )


def test_v10_validate_operating_limits_warns_on_per_order_above_threshold() -> None:
    """Per-order cap above the v1.0 threshold (1,000,000 KRW) must surface."""
    from app.config.settings import (
        RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW,
        validate_real_trading_operating_limits,
    )

    s = Settings(
        max_real_order_amount=RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW + 1,
        max_real_daily_order_amount=RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW + 1,
    )
    warnings = validate_real_trading_operating_limits(s)
    assert any("MAX_REAL_ORDER_AMOUNT" in w for w in warnings), (
        f"Expected MAX_REAL_ORDER_AMOUNT advisory, got {warnings!r}"
    )


def test_v10_validate_operating_limits_warns_on_daily_above_threshold() -> None:
    """Daily cumulative cap above the v1.0 threshold (10,000,000 KRW) must surface."""
    from app.config.settings import (
        RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW,
        validate_real_trading_operating_limits,
    )

    s = Settings(
        max_real_order_amount=100_000,
        max_real_daily_order_amount=RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW + 1,
    )
    warnings = validate_real_trading_operating_limits(s)
    assert any("MAX_REAL_DAILY_ORDER_AMOUNT" in w for w in warnings), (
        f"Expected MAX_REAL_DAILY_ORDER_AMOUNT advisory, got {warnings!r}"
    )


def test_v10_validate_operating_limits_returns_two_when_both_exceed() -> None:
    """Both caps over threshold → both advisories returned (in stable order)."""
    from app.config.settings import (
        RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW,
        RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW,
        validate_real_trading_operating_limits,
    )

    s = Settings(
        max_real_order_amount=RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW + 1,
        max_real_daily_order_amount=RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW + 1,
    )
    warnings = validate_real_trading_operating_limits(s)
    assert len(warnings) == 2
    assert "MAX_REAL_ORDER_AMOUNT" in warnings[0]
    assert "MAX_REAL_DAILY_ORDER_AMOUNT" in warnings[1]


def test_v10_validate_operating_limits_pure_returns_no_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helper must be pure — no logging, no external calls. Calling twice on
    the same Settings yields the same list (no side effect)."""
    from app.config.settings import validate_real_trading_operating_limits

    s = Settings()
    a = validate_real_trading_operating_limits(s)
    b = validate_real_trading_operating_limits(s)
    assert a == b == []


def test_v10_validate_operating_limits_at_exact_threshold_no_warning() -> None:
    """Exactly at the recommended cap is acceptable (boundary inclusive)."""
    from app.config.settings import (
        RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW,
        RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW,
        validate_real_trading_operating_limits,
    )

    s = Settings(
        max_real_order_amount=RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW,
        max_real_daily_order_amount=RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW,
    )
    assert validate_real_trading_operating_limits(s) == []


# ---------------------------------------------------------------------------
# 17. v1.0 Phase A — can_attempt_real_order_settings(): full operating gate
#     re-verification across the 9 .env keys from RUNBOOK §2
# ---------------------------------------------------------------------------


def test_v10_can_attempt_only_with_all_runbook_section_2_keys_open() -> None:
    """The 6-gate AND helper agrees with the RUNBOOK §2 activation keys.

    All 6 simultaneously-open gates → True. Closing any one → False.
    (auth_enabled + max_real_*_amount are checked at HTTP / Executor layer,
    not the can_attempt helper — the helper covers settings-level gating only.)
    """
    open_kwargs = dict(
        trading_safety_enabled=True,
        kill_switch_enabled=False,
        approval_required=True,
        real_trading_enabled=True,
        kis_order_enabled=True,
        real_order_dry_run=False,
    )
    assert can_attempt_real_order_settings(Settings(**open_kwargs)) is True

    # Each of the 6 gates, when flipped to its closed state in isolation,
    # must independently block.
    for closed_field, closed_value in [
        ("trading_safety_enabled", False),
        ("kill_switch_enabled", True),
        ("approval_required", False),
        ("real_trading_enabled", False),
        ("kis_order_enabled", False),
        ("real_order_dry_run", True),
    ]:
        kwargs = dict(open_kwargs)
        kwargs[closed_field] = closed_value
        assert can_attempt_real_order_settings(Settings(**kwargs)) is False, (
            f"{closed_field}={closed_value} must block real-order execution"
        )


# ---------------------------------------------------------------------------
# 18. v1.0 Phase A — Phase B scope guard:
#     HttpxKisOrderTransport + KIS real transport must NOT yet exist.
# ---------------------------------------------------------------------------


def test_v10_phase_a_httpx_kis_order_transport_module_absent() -> None:
    """Phase B (KIS real transport) is not yet implemented in Phase A."""
    from pathlib import Path

    broker_dir = Path(__file__).resolve().parents[2] / "app" / "broker"
    real_transport = broker_dir / "kis_order_transport_real.py"
    assert not real_transport.exists(), (
        "kis_order_transport_real.py must be deferred to v1.0 Phase B "
        f"(found at {real_transport})"
    )


def test_v10_phase_a_kis_order_client_does_not_define_httpx_transport() -> None:
    """Even within the existing kis_order_client.py, HttpxKisOrderTransport
    is not yet a concrete class — Phase A only adds runbook + settings
    helpers."""
    import importlib

    module = importlib.import_module("app.broker.kis_order_client")
    assert not hasattr(module, "HttpxKisOrderTransport"), (
        "HttpxKisOrderTransport must not exist before v1.0 Phase B"
    )


def test_v10_phase_a_no_real_order_executor_real_path() -> None:
    """RealOrderExecutor real path (Phase C) is not yet implemented.

    The Phase D / v0.16 dry-run executor exists, but it must not yet expose
    a method or branch named ``real_path`` / ``execute_real`` etc. We assert
    that the executor module — which already exists — does NOT export an
    HttpxKisOrderTransport-bound symbol.
    """
    import importlib

    module = importlib.import_module("app.broker.real_order_executor")
    # Phase A scope guard: no public symbol named after the real transport
    forbidden = ("HttpxKisOrderTransport", "execute_real", "real_path_execute")
    for name in forbidden:
        assert not hasattr(module, name), (
            f"v1.0 Phase A must not introduce {name} on RealOrderExecutor; "
            f"that belongs to Phase C"
        )


def test_v10_phase_a_no_fill_sync_real_transport_helper() -> None:
    """FillSyncService real-transport helper (Phase D) is not yet present."""
    import importlib

    module = importlib.import_module("app.broker.fill_sync_service")
    forbidden = ("sync_fills_real", "HttpxKisOrderTransport")
    for name in forbidden:
        assert not hasattr(module, name), (
            f"v1.0 Phase A must not introduce {name} on FillSyncService; "
            f"that belongs to Phase D"
        )


# ---------------------------------------------------------------------------
# 19. v1.0 Phase A — Alembic head + DB / API / frontend scope unchanged
# ---------------------------------------------------------------------------


def test_v10_phase_a_alembic_head_is_unchanged_at_0010_real_fills() -> None:
    """Phase A adds zero Alembic revisions — head stays at 0010_real_fills."""
    from pathlib import Path

    versions_dir = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions"
    )
    revisions = sorted(p.name for p in versions_dir.glob("0*.py"))
    assert revisions == [
        "0001_baseline_v0_7.py",
        "0002_auth_foundation.py",
        "0003_watchlist.py",
        "0004_user_preferences.py",
        "0005_virtual_trading_core.py",
        "0006_virtual_positions.py",
        "0007_order_candidates.py",
        "0008_approval_audit_logs.py",
        "0009_real_orders.py",
        "0010_real_fills.py",
    ], f"v1.0 Phase A must not add Alembic revisions, got {revisions}"


def test_v10_phase_a_no_new_pip_dependency() -> None:
    """Phase A introduces zero new pip dependencies. The pyproject.toml's
    declared distribution dependencies must remain a subset of those that
    were present at v0.16-final.

    We sanity-check that no new top-level package name is added — we don't
    pin exact versions because dev tooling (respx/prometheus-client/sqlalchemy)
    can surface as a shared lockfile. We only assert that:
      * httpx (used by Phase B later) was already a dependency
      * respx (Phase B/D test mock) was already a dev dependency
      * no exotic 'real trading' SDK has been silently added
    """
    from pathlib import Path

    pyproject = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "httpx" in pyproject
    assert "respx" in pyproject
    # Forbidden / suspicious additions
    forbidden_pkgs = (
        "ccxt",  # crypto exchange SDK
        "broker-sdk",
        "kis-sdk",
        "openapi-kis",
    )
    for pkg in forbidden_pkgs:
        assert pkg not in pyproject, (
            f"v1.0 Phase A must not add {pkg!r} to pyproject.toml"
        )
