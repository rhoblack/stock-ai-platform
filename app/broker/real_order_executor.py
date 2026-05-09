"""RealOrderExecutor — v0.16 dry-run + v1.0 Phase C real path.

10-gate safety chain followed by a dry-run vs real-path branch.

Hard guarantees verified by the test suite
------------------------------------------
* No httpx / requests / urllib import at module load or runtime.
* No app.data.collectors.kis_client / app.providers.kis import.
* The dry-run branch keeps using FakeKisOrderTransport.
* The real branch is reached ONLY when ALL 10 gates pass AND the operator
  has explicitly injected a non-Fake transport (or a transport factory
  that builds one). The default constructor still produces a Fake-only
  executor — every existing v0.16 test continues to exercise the dry-run
  branch unchanged.
* RealOrder rows on the real branch carry ``dry_run=False``,
  ``status=SUBMITTED|FAILED``, and ``broker_order_no_hash`` = SHA-256 hex
  of the KIS plaintext order_no. The plaintext order_no is NEVER stored,
  logged, or returned to upstream callers.
* Raw KIS response payloads are never persisted (only whitelisted fields
  flow through the Phase B transport's :class:`KisOrderResult`).
* ApprovalAuditLog gets REAL_ORDER_SUBMITTED / REAL_ORDER_FAILED rows for
  every real-path attempt; whitelist-only details (forbidden keys are
  enforced by the audit repository).

Gate order (fast first, then DB reads, then network)
----------------------------------------------------
  1. CANDIDATE_NOT_FOUND / NOT_APPROVED — candidate exists and APPROVED.
  2. ALREADY_EXECUTED / DUPLICATE_REAL_ORDER — no non-failed RealOrder
     for this candidate yet (idempotent guard, see RealOrderRepository.
     :meth:`exists_non_failed_for_candidate`).
  3. KILL_SWITCH_ON — paranoid master block.
  4. TRADING_SAFETY_DISABLED — v0.15 Approval-layer kill switch.        [v1.0 NEW]
  5. REAL_TRADING_DISABLED — v0.16 real-trading master switch.
  6. KIS_ORDER_DISABLED — v0.16 KIS-order API switch.
  7. AMOUNT_EXCEEDS_PER_ORDER_CAP — Settings.max_real_order_amount.
  8. AMOUNT_EXCEEDS_DAILY_CAP — KST cumulative against
     Settings.max_real_daily_order_amount.
  9. RISK_REJECTED — PreTradeRiskEngine re-evaluation passes.
 10. TRANSPORT_UNAVAILABLE (real path only) — a non-Fake transport is    [v1.0 NEW]
     resolvable. For dry-run, gate 10 is a no-op (Fake is always present).

Execution branches
------------------
  * ``settings.real_order_dry_run=True`` → existing dry-run path
    (FakeKisOrderTransport, RealOrder.dry_run=True, status=DRY_RUN).
  * ``settings.real_order_dry_run=False`` → real path:
      1. RealOrder(dry_run=False, status=CREATED) is persisted FIRST so
         that an in-flight place_order whose response is lost still has a
         DB anchor for operator reconciliation (RUNBOOK §5).
      2. ``transport.place_order(KisOrderRequest)`` is called exactly
         once — Phase B transport's retry=0 policy on place_order is
         preserved end-to-end here.
      3. The result classification (parsed off the message prefix
         "SUBMITTED:" / "REJECTED:" / "TIMEOUT:" / "NETWORK_ERROR:" /
         "UNKNOWN:") drives:
            SUBMITTED → mark_submitted(broker_order_no_hash=...)
            REJECTED  → mark_failed(error_code="REJECTED", ...)
            TIMEOUT / NETWORK_ERROR / UNKNOWN → mark_failed(error_code=cls)
      4. ApprovalAuditLog gets exactly one
         REAL_ORDER_SUBMITTED or REAL_ORDER_FAILED row.
      5. ExecutorResult mirrors the RealOrder.status:
            SUBMITTED → ExecutorResult(success=True, status="SUBMITTED")
            FAILED    → ExecutorResult(success=False, status="FAILED")
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisOrderClientInterface,
    KisOrderRequest,
    KisOrderResult,
)
from app.config.settings import Settings, get_settings
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
)
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
    status: str                  # "DRY_RUN" | "BLOCKED" | "SUBMITTED" | "FAILED"
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


# Sensitive substrings that must never appear in an executor message,
# audit detail, or RealOrder.error_message. The repository's mark_failed
# enforces this on error_message via _check_error_message; we apply the
# same policy at the executor boundary as defense in depth before the
# message reaches the database.
_SENSITIVE_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "api_key",
        "appsecret",
        "secretkey",
        "access_token",
        "authorization",
        "account_no",
    }
)


def _scrub(text: str) -> str:
    """Return ``text`` with any sensitive substring replaced by ``***``.

    Case-insensitive; whole-word match is not required (the substrings
    above are themselves the leak fingerprints).
    """
    if not text:
        return text
    lowered = text.lower()
    redacted = text
    for substr in _SENSITIVE_SUBSTRINGS:
        if substr in lowered:
            pattern = re.compile(re.escape(substr), re.IGNORECASE)
            redacted = pattern.sub("***", redacted)
            lowered = redacted.lower()
    return redacted


def _today_real_order_total(session: Session, account_id: int) -> Decimal:
    """Sum estimated_amount for non-terminal RealOrders linked to account today.

    KST calendar day is used (Asia/Seoul, UTC+9). Non-failed statuses included:
    DRY_RUN / CREATED / SUBMITTED / PARTIALLY_FILLED / FILLED.
    """
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


# Map a KisOrderResult.message prefix back to the Phase B internal
# classification token. The transport always emits one of the 5 prefixes
# below for place_order — anything else collapses to UNKNOWN.
_PLACE_PREFIXES: tuple[str, ...] = (
    "SUBMITTED",
    "REJECTED",
    "TIMEOUT",
    "NETWORK_ERROR",
    "UNKNOWN",
)


def _classify_place_message(message: str) -> str:
    """Extract the Phase B classification token from a result.message string."""
    if not message:
        return "UNKNOWN"
    head = message.split(":", 1)[0].strip().upper()
    if head in _PLACE_PREFIXES:
        return head
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class RealOrderExecutor:
    """RealOrderExecutor — v0.16 dry-run + v1.0 Phase C real path.

    Real KIS HTTP calls are made ONLY through an explicitly-injected
    non-Fake transport (or a non-Fake transport returned by an
    operator-supplied factory). The default constructor produces a
    Fake-only executor — every existing v0.16 test path is preserved.

    Usage::

        # Dry-run (default — v0.16 behavior preserved)
        executor = RealOrderExecutor()
        result = executor.execute(session, candidate_id=123, settings=my_settings)

        # Real path (v1.0 Phase C — typically wired by Phase D ApprovalService)
        from app.broker.kis_order_transport_real import HttpxKisOrderTransport
        executor = RealOrderExecutor(transport=HttpxKisOrderTransport(...))
        result = executor.execute(session, candidate_id=123, settings=settings)
    """

    def __init__(
        self,
        *,
        transport: KisOrderClientInterface | None = None,
        real_transport_factory: (
            Callable[[Settings], KisOrderClientInterface] | None
        ) = None,
    ) -> None:
        self._transport: KisOrderClientInterface = (
            transport if transport is not None else FakeKisOrderTransport()
        )
        self._real_transport_factory = real_transport_factory

    # ------------------------------------------------------------------
    # public entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        session: Session,
        *,
        candidate_id: int,
        settings: Settings | None = None,
    ) -> ExecutorResult:
        """Run 10-gate check then dispatch to the dry-run or real branch.

        ``settings`` is injectable so tests can pass custom values without
        touching the lru_cached ``get_settings()`` singleton.
        """
        if settings is None:
            settings = get_settings()

        dry_run = settings.real_order_dry_run

        # ── Gate 1: candidate found + APPROVED ──────────────────────────
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

        # ── Gate 2: duplicate execution guard ───────────────────────────
        order_repo = RealOrderRepository(session)
        if order_repo.exists_non_failed_for_candidate(candidate_id):
            existing = order_repo.get_by_candidate_id(candidate_id)
            non_failed = next(
                (o for o in existing if o.status not in ("FAILED", "REJECTED", "CANCELED")),
                None,
            )
            return _blocked(
                reason=(
                    "DUPLICATE_REAL_ORDER" if not dry_run else "ALREADY_EXECUTED"
                ),
                message=(
                    f"candidate_id={candidate_id} already has an active "
                    f"RealOrder"
                    + (f" (id={non_failed.id}, status={non_failed.status!r})"
                       if non_failed is not None else "")
                ),
                dry_run=dry_run,
                real_order_id=non_failed.id if non_failed is not None else None,
            )

        # ── Gate 3: kill_switch must be OFF ─────────────────────────────
        if settings.kill_switch_enabled:
            return _blocked(
                reason="KILL_SWITCH_ON",
                message=(
                    "kill_switch_enabled=True blocks all real order attempts; "
                    "set KILL_SWITCH_ENABLED=false to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 4: trading_safety must be ON  (v1.0 NEW) ───────────────
        if not settings.trading_safety_enabled:
            return _blocked(
                reason="TRADING_SAFETY_DISABLED",
                message=(
                    "trading_safety_enabled=False; "
                    "set TRADING_SAFETY_ENABLED=true to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 5: real_trading_enabled must be True ───────────────────
        if not settings.real_trading_enabled:
            return _blocked(
                reason="REAL_TRADING_DISABLED",
                message=(
                    "real_trading_enabled=False; "
                    "set REAL_TRADING_ENABLED=true to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 6: kis_order_enabled must be True ──────────────────────
        if not settings.kis_order_enabled:
            return _blocked(
                reason="KIS_ORDER_DISABLED",
                message=(
                    "kis_order_enabled=False; "
                    "set KIS_ORDER_ENABLED=true to proceed"
                ),
                dry_run=dry_run,
            )

        # ── Gate 7: per-order amount cap ────────────────────────────────
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

        # ── Gate 8: daily cumulative real order cap ─────────────────────
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

        # ── Gate 9: PreTradeRiskEngine re-check ─────────────────────────
        risk_engine = PreTradeRiskEngine(settings)
        risk_result = risk_engine.evaluate(session, candidate)
        if not risk_result.passed:
            violation_ids = [v.rule_id for v in risk_result.violations]
            return _blocked(
                reason="RISK_REJECTED",
                message=f"PreTradeRiskEngine violations: {violation_ids}",
                dry_run=dry_run,
            )

        # ── Branch ──────────────────────────────────────────────────────
        if dry_run:
            return self._execute_dry_run(session, candidate, order_repo)

        # ── Gate 10: transport must be available for real path ──────────
        real_transport = self._resolve_real_transport(settings)
        if real_transport is None:
            return _blocked(
                reason="TRANSPORT_UNAVAILABLE",
                message=(
                    "Real-path transport is not configured. Inject a non-Fake "
                    "KisOrderClientInterface (or supply real_transport_factory) "
                    "before calling execute() with real_order_dry_run=False."
                ),
                dry_run=False,
            )
        return self._execute_real(
            session, candidate, order_repo, settings, real_transport
        )

    # ------------------------------------------------------------------
    # transport resolution (real path)
    # ------------------------------------------------------------------

    def _resolve_real_transport(
        self, settings: Settings
    ) -> KisOrderClientInterface | None:
        """Return a non-Fake transport for the real path, or ``None``.

        Resolution order:
          1. Operator-supplied factory (``real_transport_factory(settings)``).
             Any exception → unavailable.
          2. Explicitly-injected ``transport`` if it is NOT
             :class:`FakeKisOrderTransport`.
          3. Otherwise → ``None`` (gate 10 fails).

        Paranoid: a factory that returns a FakeKisOrderTransport is rejected;
        the real path must never be served by a fake.
        """
        if self._real_transport_factory is not None:
            try:
                t = self._real_transport_factory(settings)
            except Exception:  # noqa: BLE001 - factory init failure → unavailable
                return None
            if isinstance(t, FakeKisOrderTransport):
                return None
            return t
        if not isinstance(self._transport, FakeKisOrderTransport):
            return self._transport
        return None

    # ------------------------------------------------------------------
    # dry-run execution path (preserved from v0.16 Phase D)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # real-path execution (v1.0 Phase C — strict-gate-only)
    # ------------------------------------------------------------------

    def _execute_real(
        self,
        session: Session,
        candidate: OrderCandidate,
        order_repo: RealOrderRepository,
        settings: Settings,
        transport: KisOrderClientInterface,
    ) -> ExecutorResult:
        """Submit a real order via the injected transport and persist outcome.

        Order of operations is intentionally:
          (a) RealOrder(dry_run=False, status=CREATED) row is FLUSHED first,
              so an in-flight place_order whose response is lost still has
              a DB anchor for operator reconciliation.
          (b) ``transport.place_order`` is called exactly once. The Phase B
              transport's retry=0 policy on place_order is preserved.
          (c) Result classification drives mark_submitted / mark_failed.
          (d) ApprovalAuditLog gets exactly one REAL_ORDER_SUBMITTED or
              REAL_ORDER_FAILED row.
        """
        # (a) — RealOrder anchor row.
        order = order_repo.create(
            candidate_id=candidate.id,
            symbol=candidate.symbol,
            side=candidate.side,
            quantity=candidate.quantity,
            order_type=candidate.order_type,
            limit_price=candidate.limit_price,
            estimated_amount=candidate.estimated_amount,
            dry_run=False,
            status="CREATED",
        )
        session.flush()

        # (b) — transport.place_order (zero retries, see Phase B docstring).
        request = KisOrderRequest(
            symbol=candidate.symbol,
            side=candidate.side,
            order_type=candidate.order_type,
            quantity=candidate.quantity,
            price=int(candidate.limit_price or 0),
            account_no=settings.kis_account_no or "",
        )
        kis_result: KisOrderResult = transport.place_order(request)
        classification = _classify_place_message(kis_result.message)

        # (c)+(d) — branch on classification.
        audit_repo = ApprovalAuditLogRepository(session)
        if classification == "SUBMITTED":
            broker_hash = (
                hashlib.sha256(kis_result.order_no.encode()).hexdigest()
                if kis_result.order_no
                else None
            )
            order_repo.mark_submitted(order, broker_order_no_hash=broker_hash)
            session.flush()

            audit_repo.append(
                candidate_id=candidate.id,
                event_type="REAL_ORDER_SUBMITTED",
                reason="real-path place_order succeeded",
                details={
                    "classification": classification,
                    "dry_run": False,
                    "symbol": candidate.symbol,
                    "side": candidate.side,
                    "quantity": int(candidate.quantity),
                    # 16-char hex prefix of the SHA-256 hash — the full
                    # 64-char hash is on the RealOrder row itself.
                    "broker_order_no_hash_prefix": (
                        broker_hash[:16] if broker_hash else None
                    ),
                },
            )
            session.flush()

            return ExecutorResult(
                success=True,
                dry_run=False,
                blocked_reason=None,
                real_order_id=order.id,
                status="SUBMITTED",
                message="Real order submitted to KIS (broker_order_no_hash stored)",
            )

        # All non-SUBMITTED branches → mark_failed.
        sanitized = _scrub(kis_result.message or "")[:500]
        order_repo.mark_failed(
            order,
            error_code=classification,
            error_message=sanitized,
        )
        session.flush()

        audit_repo.append(
            candidate_id=candidate.id,
            event_type="REAL_ORDER_FAILED",
            reason=f"real-path place_order returned {classification}",
            details={
                "classification": classification,
                "dry_run": False,
                "symbol": candidate.symbol,
                "side": candidate.side,
                "quantity": int(candidate.quantity),
            },
        )
        session.flush()

        return ExecutorResult(
            success=False,
            dry_run=False,
            blocked_reason=classification,
            real_order_id=order.id,
            status="FAILED",
            message=(
                f"Real order rejected/failed at KIS: classification={classification}"
            ),
        )


__all__ = [
    "ExecutorResult",
    "RealOrderExecutor",
]
