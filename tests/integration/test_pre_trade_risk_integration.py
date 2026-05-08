"""Integration tests for v0.15 Phase C — PreTradeRiskEngine end-to-end.

These tests exercise the engine alongside the live Phase B / v0.14 repos
(VirtualAccount, VirtualPosition, VirtualPnLSnapshot, OrderCandidate). They
make sure the engine's read paths actually compose with the persisted
state, not just the in-memory dataclasses.

Verified invariants:
  * Engine never mutates DB state -- candidate.status stays the same after
    evaluate(). Caller is responsible for status transition + attach.
  * Result dict is accepted as-is by ``OrderCandidateRepository.attach_risk_result``.
  * Multi-rule fail surfaces the full violation set (not short-circuit).
  * Multi-rule pass produces ``passed=True`` and zero violations.
  * Engine cooperates with VirtualPnLSnapshot / VirtualPosition / DailyPrice
    fallback chains for the position_ratio and daily_loss rules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
from app.db.session import create_session_factory
from app.risk.pre_trade_risk_engine import (
    POLICY_VERSION,
    PreTradeRiskEngine,
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


# ---------------------------------------------------------------------------
# 1. End-to-end happy path
# ---------------------------------------------------------------------------


def test_happy_path_passes_all_seven_rules(session):
    """No existing positions / no snapshot / no duplicates -> all pass."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("10000000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100000"),
    )
    session.commit()

    engine = PreTradeRiskEngine(_enabled_settings())
    result = engine.evaluate(session, cand)

    assert result.passed is True
    assert result.violations == ()
    assert result.policy_version == POLICY_VERSION


# ---------------------------------------------------------------------------
# 2. Engine does not mutate candidate
# ---------------------------------------------------------------------------


def test_engine_does_not_mutate_candidate_status(session):
    """The engine is read-only -- candidate.status stays at DRAFT after evaluate."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("1000000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("100"),
    )
    session.commit()
    assert cand.status == "DRAFT"
    assert cand.risk_check_result_json is None

    engine = PreTradeRiskEngine(_enabled_settings())
    engine.evaluate(session, cand)

    # No status change, no risk_check_result attached automatically.
    fresh = cand_repo.get_by_id(cand.id)
    assert fresh is not None
    assert fresh.status == "DRAFT"
    assert fresh.risk_check_result_json is None


# ---------------------------------------------------------------------------
# 3. attach_risk_result(result.to_dict()) round-trip
# ---------------------------------------------------------------------------


def test_attach_risk_result_round_trip(session):
    """The result dict produced by the engine MUST be accepted as-is by
    ``OrderCandidateRepository.attach_risk_result``."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("1000000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("100"),
    )
    session.commit()

    engine = PreTradeRiskEngine(_enabled_settings())
    result = engine.evaluate(session, cand)
    cand_repo.attach_risk_result(cand, result=result.to_dict())
    session.commit()

    refreshed = cand_repo.get_by_id(cand.id)
    assert refreshed is not None
    assert refreshed.risk_check_result_json is not None
    assert refreshed.risk_check_result_json["policy_version"] == "pre-trade-v1"
    assert refreshed.risk_check_result_json["passed"] is True


def test_attach_risk_result_round_trip_with_violations(session):
    """A failing result also round-trips through JSON storage."""
    accounts = VirtualAccountRepository(session)
    # Disabled paper account triggers rule 1.
    acc = accounts.create(
        name="paper",
        initial_cash=Decimal("1000000"),
        paper_trading_enabled=False,
    )
    session.commit()
    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("100"),
    )
    session.commit()

    engine = PreTradeRiskEngine(_enabled_settings())
    result = engine.evaluate(session, cand)
    assert result.passed is False
    cand_repo.attach_risk_result(cand, result=result.to_dict())
    session.commit()

    refreshed = cand_repo.get_by_id(cand.id)
    assert refreshed is not None
    payload = refreshed.risk_check_result_json
    assert payload["passed"] is False
    rule_ids = {v["rule_id"] for v in payload["violations"]}
    assert "account_paper_enabled" in rule_ids


# ---------------------------------------------------------------------------
# 4. Multi-rule fail accumulates the full set
# ---------------------------------------------------------------------------


def test_multi_rule_fail_accumulates_full_violation_set(session):
    """Account disabled + kill switch ON + per_symbol_limit over + duplicate."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(
        name="paper",
        initial_cash=Decimal("1000000"),
        paper_trading_enabled=False,  # rule 1
    )
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    earlier = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("90000"),
    )
    cand_repo.update_status(earlier, new_status="RISK_CHECKING")
    cand_repo.update_status(earlier, new_status="PENDING_APPROVAL")
    session.commit()

    new_cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,  # duplicate of earlier
        estimated_amount=Decimal("80000"),  # 90 + 80 = 170k > 100k cap
    )
    session.commit()

    settings = Settings(  # explicit kill switch ON for rule 2
        kill_switch_enabled=True,
        trading_safety_enabled=True,
        max_order_amount=100_000,
    )
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, new_cand)

    rule_ids = {v.rule_id for v in result.violations}
    assert {
        "account_paper_enabled",
        "kill_switch_off",
        "per_symbol_limit",
        "duplicate_recent",
    }.issubset(rule_ids)
    assert result.passed is False


# ---------------------------------------------------------------------------
# 5. position_ratio uses VirtualPosition + DailyPrice + VirtualPnLSnapshot
# ---------------------------------------------------------------------------


def test_position_ratio_uses_full_state(session):
    """Existing position + snapshot total_value + new candidate combined."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("100000"))
    session.commit()

    # Existing 005930 position 10 @ avg_cost 9,000.
    VirtualPositionRepository(session).apply_buy(
        account_id=acc.id,
        symbol="005930",
        fill_quantity=10,
        fill_price=Decimal("9000"),
        cash_spent=Decimal("90000"),
    )
    # Latest close 10,000 -> position market value = 100,000.
    DailyPriceRepository(session).upsert(
        symbol="005930",
        price_date=date(2026, 5, 8),
        open_price=Decimal("10000"),
        high_price=Decimal("10000"),
        low_price=Decimal("10000"),
        close_price=Decimal("10000"),
        volume=1000,
    )
    # PnL snapshot says total_value = 1,000,000 (so cap of 0.20 -> 200,000).
    VirtualPnLSnapshotRepository(session).create_or_replace_snapshot(
        account_id=acc.id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("900000"),
        market_value=Decimal("100000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("10000"),
    )
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    # New BUY 99,000: projected (100,000 + 99,000) / 1,000,000 = 0.199 -> passes.
    ok_cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("99000"),
    )
    session.commit()

    engine = PreTradeRiskEngine(_enabled_settings())
    res_pass = engine.evaluate(session, ok_cand)
    rule_ids = {v.rule_id for v in res_pass.violations}
    assert "position_ratio_limit" not in rule_ids

    # New BUY 110,000: projected (100,000 + 110,000) / 1,000,000 = 0.21 -> fails.
    bad_cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=11,
        estimated_amount=Decimal("110000"),
    )
    session.commit()
    res_fail = engine.evaluate(session, bad_cand)
    rule_ids_fail = {v.rule_id for v in res_fail.violations}
    assert "position_ratio_limit" in rule_ids_fail


# ---------------------------------------------------------------------------
# 6. daily_loss rule reads latest VirtualPnLSnapshot
# ---------------------------------------------------------------------------


def test_daily_loss_reads_latest_snapshot(session):
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("1000000"))
    session.commit()

    snaps = VirtualPnLSnapshotRepository(session)
    # Two days of snapshots; the engine reads the LATEST.
    snaps.create_or_replace_snapshot(
        account_id=acc.id,
        snapshot_date=date(2026, 5, 7),
        cash_balance=Decimal("1000000"),
        market_value=Decimal("0"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    snaps.create_or_replace_snapshot(
        account_id=acc.id,
        snapshot_date=date(2026, 5, 8),
        cash_balance=Decimal("400000"),
        market_value=Decimal("0"),
        realized_pnl=Decimal("-600000"),  # below -500k cap
        unrealized_pnl=Decimal("0"),
    )
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=1,
        estimated_amount=Decimal("100"),
    )
    session.commit()

    settings = _enabled_settings(max_daily_loss_amount=500_000)
    engine = PreTradeRiskEngine(settings)
    result = engine.evaluate(session, cand)

    rule_ids = {v.rule_id for v in result.violations}
    assert "daily_loss_limit" in rule_ids


# ---------------------------------------------------------------------------
# 7. duplicate_recent ignores other accounts
# ---------------------------------------------------------------------------


def test_duplicate_recent_scoped_to_account(session):
    accounts = VirtualAccountRepository(session)
    a1 = accounts.create(name="acct-1")
    a2 = accounts.create(name="acct-2")
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    # Account 1 has a recent active candidate.
    earlier = cand_repo.create(
        account_id=a1.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    cand_repo.update_status(earlier, new_status="RISK_CHECKING")
    cand_repo.update_status(earlier, new_status="PENDING_APPROVAL")
    session.commit()

    # Account 2's identical candidate must NOT trigger duplicate_recent.
    new_cand = cand_repo.create(
        account_id=a2.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("100"),
    )
    session.commit()

    engine = PreTradeRiskEngine(_enabled_settings())
    now = earlier.created_at + timedelta(minutes=1)
    result = engine.evaluate(session, new_cand, now=now)

    rule_ids = {v.rule_id for v in result.violations}
    assert "duplicate_recent" not in rule_ids


# ---------------------------------------------------------------------------
# 8. KST day boundary for daily_total_limit
# ---------------------------------------------------------------------------


def test_daily_total_limit_kst_day_boundary(session):
    """Yesterday's KST candidates must NOT count toward today's cap."""
    accounts = VirtualAccountRepository(session)
    acc = accounts.create(name="paper", initial_cash=Decimal("10000000"))
    session.commit()

    cand_repo = OrderCandidateRepository(session)
    # Existing active candidate "yesterday" (KST). We reach into ORM to
    # backdate created_at since the repository commits at "now".
    earlier = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="005930",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("900000"),
    )
    cand_repo.update_status(earlier, new_status="RISK_CHECKING")
    cand_repo.update_status(earlier, new_status="PENDING_APPROVAL")
    # Backdate to 2026-05-07 18:00 KST (= 2026-05-07 09:00 UTC).
    earlier.created_at = datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc)
    session.flush()
    session.commit()

    new_cand = cand_repo.create(
        account_id=acc.id,
        source="MANUAL",
        symbol="000660",
        side="BUY",
        quantity=10,
        estimated_amount=Decimal("200000"),
    )
    session.commit()

    settings = _enabled_settings(max_daily_order_amount=1_000_000)
    engine = PreTradeRiskEngine(settings)
    # "Now" is 2026-05-08 09:00 UTC = 2026-05-08 18:00 KST.
    result = engine.evaluate(
        session,
        new_cand,
        now=datetime(2026, 5, 8, 9, 0, tzinfo=timezone.utc),
    )
    rule_ids = {v.rule_id for v in result.violations}
    # Only 200k counts toward today's KST window -> well under the 1M cap.
    assert "daily_total_limit" not in rule_ids
