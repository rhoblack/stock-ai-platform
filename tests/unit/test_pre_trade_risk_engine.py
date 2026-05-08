"""Unit tests for v0.15 Phase C ``PreTradeRiskEngine``.

Scope:
  * 7 hard rules (account_paper_enabled / kill_switch_off / per_symbol_limit /
    daily_total_limit / position_ratio_limit / daily_loss_limit /
    duplicate_recent) -- happy path + boundary + violation each.
  * Boundary correctness:
      - per_symbol_limit ``cap`` exact / cap+0.0001 over
      - daily_total_limit cap exact / over
      - position_ratio_limit 0.20 exact (passes, ratio == cap allowed)
        / 0.20 + ε (rejects)
      - daily_loss_limit ``-cap`` exact (passes) / ``-cap-1`` (rejects)
      - duplicate_recent 4m59s under window (rejects) / 5m00s on window
        edge (passes -- strict ">" semantics)
  * Multiple violations accumulate (no short-circuit).
  * ``RiskCheckResult.to_dict()`` is JSON-safe (Decimal / datetime
    rendered as str).
  * ``POLICY_VERSION == "pre-trade-v1"`` and survives the round-trip.

These tests use an in-memory SQLite session per test. No external network.
Settings is constructed inline per test so each rule can be exercised in
isolation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.data.repositories.virtual_pnl_snapshot import (
    VirtualPnLSnapshotRepository,
)
from app.data.repositories.virtual_position import VirtualPositionRepository
from app.db.base import Base
from app.db.models import OrderCandidate
from app.db.session import create_session_factory
from app.risk.pre_trade_risk_engine import (
    ACTIVE_CANDIDATE_STATUSES,
    DUPLICATE_RECENT_WINDOW,
    POLICY_VERSION,
    PreTradeRiskEngine,
    RiskCheckResult,
    RiskViolation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _):  # noqa: ANN001 - SQLA event signature
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _enabled_settings(**overrides) -> Settings:
    """Default 'safe to evaluate' settings for the engine.

    kill_switch_enabled is flipped OFF here so most tests can pass through
    rule 2; the dedicated kill-switch test re-enables it explicitly.
    """
    base = dict(
        kill_switch_enabled=False,
        trading_safety_enabled=True,
        approval_required=True,
        max_order_amount=100_000,
        max_daily_order_amount=1_000_000,
        max_position_ratio=0.20,
        max_daily_loss_amount=500_000,
    )
    base.update(overrides)
    return Settings(**base)


def _seed_account(
    session,
    *,
    name: str = "paper",
    initial_cash: Decimal = Decimal("1000000"),
    paper_trading_enabled: bool = True,
) -> int:
    repo = VirtualAccountRepository(session)
    acc = repo.create(
        name=name,
        initial_cash=initial_cash,
        paper_trading_enabled=paper_trading_enabled,
    )
    session.commit()
    return acc.id


def _make_candidate(
    session,
    *,
    account_id: int,
    symbol: str = "005930",
    side: str = "BUY",
    quantity: int = 1,
    estimated_amount: Decimal = Decimal("10000"),
    status: str = "DRAFT",
) -> OrderCandidate:
    """Create + commit, then return the row."""
    repo = OrderCandidateRepository(session)
    cand = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol=symbol,
        side=side,
        quantity=quantity,
        estimated_amount=estimated_amount,
        status=status,
    )
    session.commit()
    return cand


# ---------------------------------------------------------------------------
# 0. Result shape + JSON safety + policy version
# ---------------------------------------------------------------------------


def test_policy_version_is_pre_trade_v1():
    assert POLICY_VERSION == "pre-trade-v1"


def test_active_candidate_statuses_excludes_terminal_and_executed():
    assert ACTIVE_CANDIDATE_STATUSES == frozenset(
        {"DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "APPROVED"}
    )
    for terminal in ("RISK_REJECTED", "REJECTED", "EXPIRED", "EXECUTED_PAPER"):
        assert terminal not in ACTIVE_CANDIDATE_STATUSES


def test_duplicate_window_is_five_minutes():
    assert DUPLICATE_RECENT_WINDOW == timedelta(minutes=5)


def test_to_dict_is_json_safe(session):
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(_enabled_settings())
    result = engine.evaluate(session, cand)

    payload = result.to_dict()
    # round-trips through json.dumps (no Decimal / datetime leaks)
    encoded = json.dumps(payload)
    assert isinstance(encoded, str)
    assert payload["policy_version"] == "pre-trade-v1"
    assert isinstance(payload["passed"], bool)
    assert isinstance(payload["violations"], list)
    assert payload["checked_at"].endswith("+00:00") or "T" in payload["checked_at"]


def test_to_dict_alias_as_dict_works(session):
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(_enabled_settings())
    result = engine.evaluate(session, cand)
    assert result.as_dict() == result.to_dict()


def test_riskviolation_details_decimal_serialisation():
    v = RiskViolation(
        rule_id="x",
        message="m",
        details={"amount": Decimal("100.5")},
    )
    payload = v.to_dict()
    assert payload["details"]["amount"] == "100.5"
    assert payload["severity"] == "HARD"


# ---------------------------------------------------------------------------
# Rule 1. account_paper_enabled
# ---------------------------------------------------------------------------


def test_account_paper_enabled_passes_when_account_active(session):
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(_enabled_settings())

    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "account_paper_enabled" not in rule_ids


def test_account_paper_enabled_blocks_when_account_disabled(session):
    account_id = _seed_account(session, paper_trading_enabled=False)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(_enabled_settings())

    result = engine.evaluate(session, cand)
    assert result.passed is False
    rule_ids = {v.rule_id for v in result.violations}
    assert "account_paper_enabled" in rule_ids


# ---------------------------------------------------------------------------
# Rule 2. kill_switch_off
# ---------------------------------------------------------------------------


def test_kill_switch_blocks_by_default(session):
    """Settings() default kill_switch_enabled=True must produce a violation."""
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)

    # Don't use _enabled_settings -- exercise the documented paranoid default.
    settings = Settings()  # kill_switch_enabled=True
    engine = PreTradeRiskEngine(settings)

    result = engine.evaluate(session, cand)
    assert result.passed is False
    rule_ids = {v.rule_id for v in result.violations}
    assert "kill_switch_off" in rule_ids


def test_kill_switch_off_passes_when_operator_opted_out(session):
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(_enabled_settings())  # kill_switch=False

    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "kill_switch_off" not in rule_ids


# ---------------------------------------------------------------------------
# Rule 3. per_symbol_limit
# ---------------------------------------------------------------------------


def test_per_symbol_limit_passes_at_cap_exact(session):
    account_id = _seed_account(session)
    settings = _enabled_settings(max_order_amount=100_000)
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("100000"),  # exactly at the cap
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "per_symbol_limit" not in rule_ids


def test_per_symbol_limit_rejects_just_over_cap(session):
    account_id = _seed_account(session)
    settings = _enabled_settings(max_order_amount=100_000)
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("100000.0001"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "per_symbol_limit" in rule_ids


def test_per_symbol_limit_aggregates_active_existing(session):
    """Existing active candidate on same symbol counts toward the cap."""
    account_id = _seed_account(session)
    settings = _enabled_settings(max_order_amount=100_000)
    # Existing active (status=PENDING_APPROVAL) candidate already at 90,000.
    repo = OrderCandidateRepository(session)
    other = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("90000"),
    )
    repo.update_status(other, new_status="RISK_CHECKING")
    repo.update_status(other, new_status="PENDING_APPROVAL")
    session.commit()

    # New 11,000 -> 101,000 total -> exceeds 100,000.
    new_cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("11000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, new_cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "per_symbol_limit" in rule_ids


def test_per_symbol_limit_ignores_terminal_candidates(session):
    """Terminal (REJECTED) historical candidate should NOT count."""
    account_id = _seed_account(session)
    settings = _enabled_settings(max_order_amount=100_000)
    repo = OrderCandidateRepository(session)
    historical = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("99000"),
    )
    # Drive it to REJECTED.
    repo.update_status(historical, new_status="RISK_CHECKING")
    repo.update_status(historical, new_status="PENDING_APPROVAL")
    repo.update_status(historical, new_status="REJECTED")
    session.commit()

    # Now a new 99,000 should pass even though the historical was 99,000.
    new_cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("99000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, new_cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "per_symbol_limit" not in rule_ids


# ---------------------------------------------------------------------------
# Rule 4. daily_total_limit
# ---------------------------------------------------------------------------


def test_daily_total_limit_passes_at_cap(session):
    account_id = _seed_account(session)
    settings = _enabled_settings(max_daily_order_amount=1_000_000)
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("1000000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_total_limit" not in rule_ids


def test_daily_total_limit_rejects_when_aggregate_exceeds(session):
    account_id = _seed_account(session)
    settings = _enabled_settings(max_daily_order_amount=1_000_000)

    # 3 existing active candidates totaling 900,000 today.
    repo = OrderCandidateRepository(session)
    for sym in ("005930", "000660", "035420"):
        c = repo.create(
            account_id=account_id,
            source="MANUAL",
            symbol=sym,
            side="BUY",
            quantity=1,
            estimated_amount=Decimal("300000"),
        )
        repo.update_status(c, new_status="RISK_CHECKING")
        repo.update_status(c, new_status="PENDING_APPROVAL")
    session.commit()

    new_cand = _make_candidate(
        session,
        account_id=account_id,
        symbol="207940",
        estimated_amount=Decimal("200000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, new_cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_total_limit" in rule_ids


# ---------------------------------------------------------------------------
# Rule 5. position_ratio_limit
# ---------------------------------------------------------------------------


def test_position_ratio_limit_passes_at_exact_cap(session):
    """ratio == max_position_ratio is allowed (<=, not <)."""
    account_id = _seed_account(
        session, initial_cash=Decimal("1000000")
    )
    settings = _enabled_settings(max_position_ratio=0.20)
    # No existing position. estimate = 200,000 / total 1,000,000 = 0.20
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("200000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "position_ratio_limit" not in rule_ids


def test_position_ratio_limit_rejects_just_over_cap(session):
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    settings = _enabled_settings(max_position_ratio=0.20)
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("200001"),  # ratio > 0.20
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "position_ratio_limit" in rule_ids


def test_position_ratio_limit_skipped_for_sell(session):
    """SELL reduces exposure -- ratio cap is not enforced."""
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    settings = _enabled_settings(max_position_ratio=0.20)
    cand = _make_candidate(
        session,
        account_id=account_id,
        side="SELL",
        estimated_amount=Decimal("999999"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "position_ratio_limit" not in rule_ids


def test_position_ratio_limit_uses_pnl_snapshot_total_value(session):
    """When a snapshot exists, total_value comes from it (not cash_balance)."""
    account_id = _seed_account(session, initial_cash=Decimal("100000"))
    # Snapshot says total_value = 1,000,000 (cash 100k + market value 900k).
    VirtualPnLSnapshotRepository(session).create_or_replace_snapshot(
        account_id=account_id,
        snapshot_date=datetime.now(timezone.utc).date(),
        cash_balance=Decimal("100000"),
        market_value=Decimal("900000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    settings = _enabled_settings(max_position_ratio=0.20)
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("199000"),  # 199k / 1M = 0.199 < 0.20
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "position_ratio_limit" not in rule_ids


def test_position_ratio_includes_existing_position_market_value(session):
    """Existing 005930 position counts toward the projected ratio."""
    account_id = _seed_account(session, initial_cash=Decimal("1000000"))
    # Existing position 10 @ avg_cost 9,000 (cost basis 90,000).
    VirtualPositionRepository(session).apply_buy(
        account_id=account_id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("9000"),
        cash_spent=Decimal("90000"),
    )
    # Latest close 10,000 → market value 100,000.
    DailyPriceRepository(session).upsert(
        symbol="005930",
        price_date=datetime(2026, 5, 8).date(),
        open_price=Decimal("10000"),
        high_price=Decimal("10000"),
        low_price=Decimal("10000"),
        close_price=Decimal("10000"),
        volume=1000,
    )
    session.commit()

    settings = _enabled_settings(max_position_ratio=0.20)
    # Total cash 1M; with 100k existing market value (100k + new) > 200k cap.
    cand = _make_candidate(
        session,
        account_id=account_id,
        estimated_amount=Decimal("110000"),
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "position_ratio_limit" in rule_ids


# ---------------------------------------------------------------------------
# Rule 6. daily_loss_limit
# ---------------------------------------------------------------------------


def test_daily_loss_limit_no_snapshot_passes(session):
    """No PnL snapshot yet -> rule passes (snapshot job will fill in)."""
    account_id = _seed_account(session)
    cand = _make_candidate(session, account_id=account_id)
    settings = _enabled_settings(max_daily_loss_amount=500_000)
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_loss_limit" not in rule_ids


def test_daily_loss_limit_at_floor_passes(session):
    """realized_pnl == -cap is the boundary; rule uses '<' not '<='."""
    account_id = _seed_account(session)
    VirtualPnLSnapshotRepository(session).create_or_replace_snapshot(
        account_id=account_id,
        snapshot_date=datetime.now(timezone.utc).date(),
        cash_balance=Decimal("500000"),
        market_value=Decimal("0"),
        realized_pnl=Decimal("-500000"),  # exactly at -cap
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    settings = _enabled_settings(max_daily_loss_amount=500_000)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_loss_limit" not in rule_ids


def test_daily_loss_limit_below_floor_rejects(session):
    account_id = _seed_account(session)
    VirtualPnLSnapshotRepository(session).create_or_replace_snapshot(
        account_id=account_id,
        snapshot_date=datetime.now(timezone.utc).date(),
        cash_balance=Decimal("499999"),
        market_value=Decimal("0"),
        realized_pnl=Decimal("-500001"),  # below floor
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    settings = _enabled_settings(max_daily_loss_amount=500_000)
    cand = _make_candidate(session, account_id=account_id)
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_loss_limit" in rule_ids


# ---------------------------------------------------------------------------
# Rule 7. duplicate_recent
# ---------------------------------------------------------------------------


def test_duplicate_recent_blocks_within_window(session):
    """4m59s under the window -> blocked."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    earlier = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    repo.update_status(earlier, new_status="RISK_CHECKING")
    repo.update_status(earlier, new_status="PENDING_APPROVAL")
    session.commit()

    new_cand = _make_candidate(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    settings = _enabled_settings()
    engine = PreTradeRiskEngine(settings)
    # 4m59s after the earlier candidate's created_at.
    now = earlier.created_at + timedelta(minutes=4, seconds=59)
    result = engine.evaluate(session, new_cand, now=now)
    rule_ids = {v.rule_id for v in result.violations}
    assert "duplicate_recent" in rule_ids


def test_duplicate_recent_passes_at_window_boundary(session):
    """5m00s exactly -> passes (strict '>' semantics)."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    earlier = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    repo.update_status(earlier, new_status="RISK_CHECKING")
    repo.update_status(earlier, new_status="PENDING_APPROVAL")
    session.commit()

    new_cand = _make_candidate(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    settings = _enabled_settings()
    engine = PreTradeRiskEngine(settings)
    now = earlier.created_at + timedelta(minutes=5)
    result = engine.evaluate(session, new_cand, now=now)
    rule_ids = {v.rule_id for v in result.violations}
    assert "duplicate_recent" not in rule_ids


def test_duplicate_recent_ignores_terminal_candidates(session):
    """A REJECTED earlier candidate should NOT trigger the duplicate rule."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    earlier = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    repo.update_status(earlier, new_status="RISK_CHECKING")
    repo.update_status(earlier, new_status="PENDING_APPROVAL")
    repo.update_status(earlier, new_status="REJECTED")
    session.commit()

    new_cand = _make_candidate(
        session,
        account_id=account_id,
        symbol="005930",
        side="BUY",
        quantity=10,
    )
    settings = _enabled_settings()
    engine = PreTradeRiskEngine(settings)
    now = earlier.created_at + timedelta(minutes=1)
    result = engine.evaluate(session, new_cand, now=now)
    rule_ids = {v.rule_id for v in result.violations}
    assert "duplicate_recent" not in rule_ids


def test_duplicate_recent_distinguishes_side(session):
    """Same symbol/quantity but different side -> not a duplicate."""
    account_id = _seed_account(session)
    repo = OrderCandidateRepository(session)
    earlier = repo.create(
        account_id=account_id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    repo.update_status(earlier, new_status="RISK_CHECKING")
    repo.update_status(earlier, new_status="PENDING_APPROVAL")
    session.commit()

    new_cand = _make_candidate(
        session,
        account_id=account_id,
        symbol="005930",
        side="SELL",
        quantity=10,
    )
    settings = _enabled_settings()
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, new_cand)
    rule_ids = {v.rule_id for v in result.violations}
    assert "duplicate_recent" not in rule_ids


# ---------------------------------------------------------------------------
# Multiple violations accumulate (no short-circuit)
# ---------------------------------------------------------------------------


def test_multiple_violations_accumulate(session):
    """When account is disabled AND kill switch is ON, both violations
    appear -- the engine never short-circuits."""
    account_id = _seed_account(session, paper_trading_enabled=False)
    cand = _make_candidate(session, account_id=account_id)

    # Default settings have kill_switch_enabled=True.
    settings = Settings()
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)

    rule_ids = {v.rule_id for v in result.violations}
    assert "account_paper_enabled" in rule_ids
    assert "kill_switch_off" in rule_ids
    assert result.passed is False


# ---------------------------------------------------------------------------
# RiskCheckResult / RiskViolation immutability
# ---------------------------------------------------------------------------


def test_riskcheckresult_is_frozen():
    r = RiskCheckResult(
        policy_version="x",
        passed=True,
        violations=(),
        checked_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )
    with pytest.raises(Exception):  # FrozenInstanceError subclasses Exception
        r.passed = False  # type: ignore[misc]


def test_riskviolation_is_frozen():
    v = RiskViolation(rule_id="x", message="m")
    with pytest.raises(Exception):
        v.rule_id = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AST guard
# ---------------------------------------------------------------------------


def test_pre_trade_risk_engine_module_has_no_forbidden_imports():
    import ast
    from pathlib import Path

    src_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "risk"
        / "pre_trade_risk_engine.py"
    )
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    forbidden_modules = {"requests", "httpx", "urllib", "urllib3"}
    forbidden_prefixes = (
        "app.kis",
        "app.data.dart_provider",
        "app.data.rss_provider",
        "app.data.collectors.kis_client",
    )
    leaks: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in forbidden_modules or any(
                    a.name == p or a.name.startswith(p + ".")
                    for p in forbidden_prefixes
                ):
                    leaks.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in forbidden_modules or any(
                module == p or module.startswith(p + ".")
                for p in forbidden_prefixes
            ):
                leaks.append(f"from {module}")
    assert leaks == [], (
        f"pre_trade_risk_engine.py unexpectedly imports forbidden modules: "
        f"{leaks!r}"
    )
