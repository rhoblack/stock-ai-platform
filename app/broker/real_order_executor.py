"""RealOrderExecutor — v0.16 Phase D dry-run execution only.

8-gate safety check followed by dry-run via FakeKisOrderTransport.

Hard guarantees verified by the test suite
------------------------------------------
* No httpx / requests / urllib import at module load or runtime.
* No app.data.collectors.kis_client import.
* FakeKisOrderTransport is the ONLY transport used in this module;
  KisHttpOrderTransport is Phase E+ scope.
* RealOrder rows are always written with dry_run=True in this phase.
* Sensitive values (api_key, secret, account_no) never stored.
* raw KIS response never stored.

Gate order (fast first, then DB reads):
  1. candidate found + status == APPROVED
  2. duplicate execution guard (DB: existing non-failed RealOrder for candidate)
  3. kill_switch_enabled == False  (Settings — fast)
  4. real_trading_enabled == True  (Settings — fast)
  5. kis_order_enabled == True     (Settings — fast)
  6. estimated_amount <= max_real_order_amount  (Settings — fast)
  7. today's cumulative real order total <= max_real_daily_order_amount  (DB)
  8. PreTradeRiskEngine.evaluate() passes  (DB — most expensive last)

Execution modes:
  * real_order_dry_run=True  (default) → FakeKisOrderTransport → DRY_RUN RealOrder.
  * real_order_dry_run=False → REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D result
    (Phase D does NOT implement real KIS HTTP calls).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisOrderClientInterface,
    KisOrderRequest,
)
from app.config.settings import Settings, get_settings
from app.data.repositories.order_candidate import OrderCandidateRepository
from app.data.repositories.real_order import RealOrderRepository
from app.db.models import OrderCandidate, RealOrder
from app.risk.pre_trade_risk_engine import PreTradeRiskEngine


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutorResult:
    """Structured result of one RealOrderExecutor.execute() call."""

    success: bool
    dry_run: bool
    blocked_reason: str | None   # None when success=True
    real_order_id: int | None    # None when blocked before RealOrder creation
    status: str                  # "DRY_RUN" | "BLOCKED" | "FAILED"
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "dry_run": self.dry_run,
            "blocked_reason": self.blocked_reason,
            "real_order_id": self.real_order_id,
            "status": self.status,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _today_real_order_total(session: Session, account_id: int) -> Decimal:
    """Sum estimated_amount for non-terminal RealOrders linked to account today.

    KST calendar day is used (Asia/Seoul, UTC+9). Non-failed statuses included:
    DRY_RUN / CREATED / SUBMITTED / PARTIALLY_FILLED / FILLED.
    """
    from datetime import date as _date
    from zoneinfo import ZoneInfo

    _KST = ZoneInfo("Asia/Seoul")
    kst_now = datetime.now(timezone.utc).astimezone(_KST)
    kst_today = kst_now.date()
    # Convert KST midnight to UTC range
    day_start_kst = datetime(
        kst_today.year, kst_today.month, kst_today.day, tzinfo=_KST
    )
    day_start_utc = day_start_kst.astimezone(timezone.utc)
    day_end_utc = day_start_utc + timedelta(days=1)

    _EXCLUDED = ("FAILED", "REJECTED", "CANCELED")

    result = session.execute(
        select(func.coalesce(func.sum(RealOrder.estimated_amount), 0))
        .join(OrderCandidate, RealOrder.candidate_id == OrderCandidate.id)
        .where(
            OrderCandidate.account_id == account_id,
            RealOrder.created_at >= day_start_utc,
            RealOrder.created_at < day_end_utc,
            RealOrder.status.notin_(_EXCLUDED),
        )
    ).scalar()

    return Decimal(str(result or 0))


def _blocked(
    *,
    reason: str,
    message: str,
    dry_run: bool,
    real_order_id: int | None = None,
) -> ExecutorResult:
    return ExecutorResult(
        success=False,
        dry_run=dry_run,
        blocked_reason=reason,
        real_order_id=real_order_id,
        status="BLOCKED",
        message=message,
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class RealOrderExecutor:
    """Dry-run-only order executor for v0.16.

    Real KIS HTTP calls: 0.  Only FakeKisOrderTransport is used.

    Usage::

        executor = RealOrderExecutor()
        result = executor.execute(session, candidate_id=123, settings=my_settings)
    """

    def __init__(self, *, transport: KisOrderClientInterface | None = None) -> None:
        self._transport: KisOrderClientInterface = (
            transport if transport is not None else FakeKisOrderTransport()
        )

    # -------- public entry point --------

    def execute(
        self,
        session: Session,
        *,
        candidate_id: int,
        settings: Settings | None = None,
    ) -> ExecutorResult:
        """Run 8-gate check then execute in dry-run mode.

        ``settings`` is injectable so tests can pass custom values without
        touching the lru_cached ``get_settings()`` singleton.
        """
        if settings is None:
            settings = get_settings()

        dry_run = settings.real_order_dry_run

        # ── Gate 1: candidate found + APPROVED ──────────────────────────────
        candidate_repo = OrderCandidateRepository(session)
        candidate = candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            return _blocked(
                reason="CANDIDATE_NOT_FOUND",
                message=f"OrderCandidate id={candidate_id} not found",
                dry_run=dry_run,
            )
        if candidate.status != "APPROVED":
            return _blocked(
                reason="NOT_APPROVED",
                message=(
                    f"candidate.status={candidate.status!r}; "
                    "must be APPROVED before execution"
                ),
                dry_run=dry_run,
            )

        # ── Gate 2: duplicate execution guard ───────────────────────────────
        order_repo = RealOrderRepository(session)
        existing_orders = order_repo.get_by_candidate_id(candidate_id)
        _NON_FAILED = frozenset({"DRY_RUN", "CREATED", "SUBMITTED", "PARTIALLY_FILLED", "FILLED"})
        active = [o for o in existing_orders if o.status in _NON_FAILED]
        if active:
            return _blocked(
                reason="ALREADY_EXECUTED",
                message=(
                    f"candidate_id={candidate_id} already has an active "
                    f"RealOrder (id={active[0].id}, status={active[0].status!r})"
                ),
                dry_run=dry_run,
                real_order_id=active[0].id,
            )

        # ── Gate 3: kill_switch must be OFF ─────────────────────────────────
        if settings.kill_switch_enabled:
            return _blocked(
                reason="KILL_SWITCH_ON",
                message=(
                    "kill_switch_enabled=True blocks all real order attempts; "
                    "set KILL_SWITCH_ENABLED=false to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 4: real_trading_enabled must be True ────────────────────────
        if not settings.real_trading_enabled:
            return _blocked(
                reason="REAL_TRADING_DISABLED",
                message=(
                    "real_trading_enabled=False; "
                    "set REAL_TRADING_ENABLED=true to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 5: kis_order_enabled must be True ───────────────────────────
        if not settings.kis_order_enabled:
            return _blocked(
                reason="KIS_ORDER_DISABLED",
                message=(
                    "kis_order_enabled=False; "
                    "set KIS_ORDER_ENABLED=true to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 6: per-order amount cap ─────────────────────────────────────
        estimated = Decimal(str(candidate.estimated_amount))
        cap = Decimal(str(settings.max_real_order_amount))
        if estimated > cap:
            return _blocked(
                reason="AMOUNT_EXCEEDS_PER_ORDER_CAP",
                message=(
                    f"estimated_amount={estimated} > "
                    f"max_real_order_amount={cap}"
                ),
                dry_run=dry_run,
            )

        # ── Gate 7: daily cumulative real order cap ──────────────────────────
        today_total = _today_real_order_total(session, candidate.account_id)
        daily_cap = Decimal(str(settings.max_real_daily_order_amount))
        if today_total + estimated > daily_cap:
            return _blocked(
                reason="AMOUNT_EXCEEDS_DAILY_CAP",
                message=(
                    f"today_total={today_total} + estimated={estimated} "
                    f"> max_real_daily_order_amount={daily_cap}"
                ),
                dry_run=dry_run,
            )

        # ── Gate 8: PreTradeRiskEngine re-check ─────────────────────────────
        risk_engine = PreTradeRiskEngine(settings)
        risk_result = risk_engine.evaluate(session, candidate)
        if not risk_result.passed:
            violation_ids = [v.rule_id for v in risk_result.violations]
            return _blocked(
                reason="RISK_REJECTED",
                message=f"PreTradeRiskEngine violations: {violation_ids}",
                dry_run=dry_run,
            )

        # ── Execution ────────────────────────────────────────────────────────
        if dry_run:
            return self._execute_dry_run(session, candidate, order_repo)

        # Phase D does not implement real KIS HTTP calls.
        return _blocked(
            reason="REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D",
            message=(
                "real_order_dry_run=False path is not implemented in v0.16 "
                "Phase D. KisHttpOrderTransport will be introduced in a future "
                "phase after compliance / security review."
            ),
            dry_run=False,
        )

    # -------- dry-run execution path --------

    def _execute_dry_run(
        self,
        session: Session,
        candidate: OrderCandidate,
        order_repo: RealOrderRepository,
    ) -> ExecutorResult:
        """Place a fake order via FakeKisOrderTransport and persist DRY_RUN row."""
        request = KisOrderRequest(
            symbol=candidate.symbol,
            side=candidate.side,
            order_type=candidate.order_type,
            quantity=candidate.quantity,
            price=int(candidate.limit_price or 0),
            account_no="DRY_RUN",
        )
        fake_result = self._transport.place_order(request)

        # Hash the fake order_no for consistent storage convention.
        fake_hash_prefix = hashlib.sha256(
            fake_result.order_no.encode()
        ).hexdigest()[:16]

        order = order_repo.create(
            candidate_id=candidate.id,
            symbol=candidate.symbol,
            side=candidate.side,
            quantity=candidate.quantity,
            order_type=candidate.order_type,
            limit_price=candidate.limit_price,
            estimated_amount=candidate.estimated_amount,
            dry_run=True,
            fake_order_no=fake_result.order_no,
            request_id=fake_hash_prefix,
            status="DRY_RUN",
        )
        session.flush()

        return ExecutorResult(
            success=True,
            dry_run=True,
            blocked_reason=None,
            real_order_id=order.id,
            status="DRY_RUN",
            message=f"Dry-run order recorded: fake_order_no={fake_result.order_no!r}",
        )
