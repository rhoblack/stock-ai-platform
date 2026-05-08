"""ApprovalService -- v0.15 Phase D workflow orchestrator.

Composes:
  * ``OrderCandidateRepository`` (8-state machine, Phase B)
  * ``PreTradeRiskEngine`` (7 HARD rules, Phase C)
  * ``ApprovalAuditLogRepository`` (append-only, Phase D)
  * ``SimulationBroker.submit_order`` (paper execution only, Phase B/C of v0.14)

Hard policies enforced here
---------------------------

* The route layer has primary AUTH / safety / kill-switch gates. This
  service performs *defense-in-depth* re-checks via
  :func:`_assert_workflow_active` and :func:`_assert_kill_switch_off` so
  unit / integration callers cannot bypass safety by skipping the route.
* ``approve()`` re-runs the PreTradeRiskEngine: a candidate that passed at
  creation time can still get rejected at approval time (state may have
  changed -- new fills, new positions, new daily totals).
* Approved candidates are forwarded to ``SimulationBroker.submit_order``
  ONLY. There is no real-broker / KIS code path. The audit log records
  ``EXECUTED_PAPER`` (never ``EXECUTED_REAL``).
* Every state transition / kill-switch block is recorded as one
  immutable :class:`~app.db.models.ApprovalAuditLog` row.

The service does NOT commit on its own; the caller (route handler /
scheduler job) commits after a successful return so the audit row +
candidate state + virtual-order link land atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.broker.simulation_broker import (
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
)
from app.config.settings import Settings
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
)
from app.data.repositories.order_candidate import (
    InvalidOrderCandidateTransition,
    OrderCandidateRepository,
    OrderCandidateValidationError,
)
from app.db.base import utc_now
from app.db.models import OrderCandidate
from app.risk.pre_trade_risk_engine import (
    POLICY_VERSION,
    PreTradeRiskEngine,
    RiskCheckResult,
)


DEFAULT_TTL = timedelta(minutes=30)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ApprovalServiceError(Exception):
    """Generic ApprovalService runtime error (e.g. candidate not found)."""


class TradingSafetyDisabledError(ApprovalServiceError):
    """Raised when ``Settings.trading_safety_enabled`` is False on a mutation."""


class KillSwitchBlockedError(ApprovalServiceError):
    """Raised when ``Settings.kill_switch_enabled`` is True on a mutation."""


class ApprovalDeniedError(ApprovalServiceError):
    """Raised when approval is requested on a candidate that cannot be approved.

    Concrete cases: status != PENDING_APPROVAL, risk re-check failure, or
    SimulationBroker rejection. The exception carries the most useful
    detail dict so the route layer can map it to a 422/409 response.
    """

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


# ---------------------------------------------------------------------------
# Audit context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalActor:
    """Caller identity captured for ``ApprovalAuditLog``.

    ``ip_hash`` and ``user_agent_hash`` MUST already be SHA256 hex (the
    route layer hashes via ``app.auth.security.hash_for_audit``). The
    service refuses to compute hashes itself -- centralising the hashing
    decision in one place.
    """

    user_id: int | None = None
    ip_hash: str | None = None
    user_agent_hash: str | None = None


@dataclass
class CreateCandidateResult:
    """Returned by ``ApprovalService.create_candidate``."""

    candidate: OrderCandidate
    risk_result: RiskCheckResult
    risk_passed: bool


@dataclass
class ApproveResult:
    """Returned by ``ApprovalService.approve``."""

    candidate: OrderCandidate
    virtual_order_id: int
    risk_result: RiskCheckResult


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ApprovalService:
    """Workflow orchestrator. Construct per request with current settings."""

    def __init__(
        self,
        *,
        settings: Settings,
        risk_engine: PreTradeRiskEngine | None = None,
        broker: SimulationBroker | None = None,
    ) -> None:
        self._settings = settings
        self._risk_engine = risk_engine or PreTradeRiskEngine(settings)
        self._broker = broker or SimulationBroker(settings=settings)

    # ------------------------------------------------------------------
    # Gating helpers (defense-in-depth; route layer is the primary gate)
    # ------------------------------------------------------------------

    def _assert_workflow_active(self) -> None:
        if not self._settings.trading_safety_enabled:
            raise TradingSafetyDisabledError(
                "TRADING_SAFETY_ENABLED is False -- Approval API is disabled "
                "(set TRADING_SAFETY_ENABLED=true in operator-private .env)."
            )

    def _assert_kill_switch_off(
        self,
        session: Session,
        *,
        candidate_id: int | None,
        actor: ApprovalActor,
    ) -> None:
        if self._settings.kill_switch_enabled:
            # If we already have a candidate row, append the audit row so
            # the operator can see the block in /api/approvals/audit.
            if candidate_id is not None:
                ApprovalAuditLogRepository(session).append(
                    candidate_id=candidate_id,
                    event_type="KILL_SWITCH_BLOCKED",
                    user_id=actor.user_id,
                    ip_hash=actor.ip_hash,
                    user_agent_hash=actor.user_agent_hash,
                    reason="kill_switch_enabled",
                )
            raise KillSwitchBlockedError(
                "kill switch is ON -- set KILL_SWITCH_ENABLED=false in "
                "operator-private .env to opt out of the paranoid default."
            )

    # ------------------------------------------------------------------
    # 1. create_candidate -- DRAFT -> RISK_CHECKING -> (PENDING_APPROVAL | RISK_REJECTED)
    # ------------------------------------------------------------------

    def create_candidate(
        self,
        session: Session,
        *,
        account_id: int,
        source: str,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        limit_price: Decimal | int | float | str | None = None,
        estimated_amount: Decimal | int | float | str = Decimal("0"),
        source_ref_id: int | None = None,
        ttl: timedelta | None = None,
        actor: ApprovalActor | None = None,
        now: datetime | None = None,
    ) -> CreateCandidateResult:
        """Create a candidate, run pre-trade risk, and route to the right state.

        Audit timeline written:
          * CREATED      -- candidate row inserted
          * RISK_CHECKED -- engine evaluated (always written)
          * RISK_REJECTED-- only when risk_result.passed is False

        The state transitions DRAFT -> RISK_CHECKING -> (PENDING_APPROVAL |
        RISK_REJECTED) are all performed in this single call so the caller
        sees the candidate already at its terminal pre-approval state.
        """
        self._assert_workflow_active()
        actor = actor or ApprovalActor()
        evaluated_at = now or utc_now()
        expires_at = evaluated_at + (ttl or DEFAULT_TTL)

        candidates = OrderCandidateRepository(session)
        audit = ApprovalAuditLogRepository(session)

        # Workflow start: defense-in-depth kill-switch check. We do NOT
        # write KILL_SWITCH_BLOCKED here because the candidate row does not
        # yet exist; the route layer is expected to short-circuit at 503
        # before reaching this method.
        if self._settings.kill_switch_enabled:
            raise KillSwitchBlockedError(
                "kill switch is ON -- candidate creation refused"
            )

        try:
            candidate = candidates.create(
                account_id=account_id,
                source=source,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                estimated_amount=estimated_amount,
                source_ref_id=source_ref_id,
                expires_at=expires_at,
            )
        except OrderCandidateValidationError:
            raise
        audit.append(
            candidate_id=candidate.id,
            event_type="CREATED",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            details={"source": source, "symbol": candidate.symbol},
        )

        # DRAFT -> RISK_CHECKING
        candidates.update_status(candidate, new_status="RISK_CHECKING")

        # Run the risk engine (read-only).
        risk_result = self._risk_engine.evaluate(
            session, candidate, now=evaluated_at
        )
        result_dict = risk_result.to_dict()
        candidates.attach_risk_result(candidate, result=result_dict)
        audit.append(
            candidate_id=candidate.id,
            event_type="RISK_CHECKED",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            details={
                "policy_version": risk_result.policy_version,
                "passed": risk_result.passed,
                "violation_rule_ids": [v.rule_id for v in risk_result.violations],
            },
        )

        if risk_result.passed:
            candidates.update_status(candidate, new_status="PENDING_APPROVAL")
        else:
            candidates.update_status(
                candidate,
                new_status="RISK_REJECTED",
                rejection_reason=_format_violations(risk_result),
            )
            audit.append(
                candidate_id=candidate.id,
                event_type="RISK_REJECTED",
                user_id=actor.user_id,
                ip_hash=actor.ip_hash,
                user_agent_hash=actor.user_agent_hash,
                reason=_format_violations(risk_result),
                details={
                    "policy_version": risk_result.policy_version,
                    "violation_rule_ids": [
                        v.rule_id for v in risk_result.violations
                    ],
                },
            )

        return CreateCandidateResult(
            candidate=candidate,
            risk_result=risk_result,
            risk_passed=risk_result.passed,
        )

    # ------------------------------------------------------------------
    # 2. approve -- PENDING_APPROVAL -> APPROVED -> EXECUTED_PAPER
    # ------------------------------------------------------------------

    def approve(
        self,
        session: Session,
        *,
        candidate_id: int,
        actor: ApprovalActor,
        now: datetime | None = None,
    ) -> ApproveResult:
        """Approve a PENDING_APPROVAL candidate and forward to SimulationBroker.

        Re-runs the risk engine before approval (the world has moved on
        since creation -- new fills / positions / daily totals may have
        appeared). On re-check failure, transitions to ``RISK_REJECTED``
        and raises :class:`ApprovalDeniedError`.

        On success: APPROVED -> SimulationBroker.submit_order -> EXECUTED_PAPER.
        Audit timeline: APPROVED then EXECUTED_PAPER (or KILL_SWITCH_BLOCKED
        / RISK_REJECTED on the failure paths).
        """
        self._assert_workflow_active()
        evaluated_at = now or utc_now()

        candidates = OrderCandidateRepository(session)
        audit = ApprovalAuditLogRepository(session)

        candidate = candidates.get_by_id(candidate_id)
        if candidate is None:
            raise ApprovalServiceError(
                f"OrderCandidate id={candidate_id} not found"
            )
        if candidate.status != "PENDING_APPROVAL":
            raise ApprovalDeniedError(
                f"candidate id={candidate_id} status is {candidate.status!r}; "
                f"only PENDING_APPROVAL candidates can be approved",
                details={"current_status": candidate.status},
            )

        self._assert_kill_switch_off(
            session, candidate_id=candidate.id, actor=actor
        )

        # Risk re-check.
        risk_result = self._risk_engine.evaluate(
            session, candidate, now=evaluated_at
        )
        if not risk_result.passed:
            candidates.attach_risk_result(
                candidate, result=risk_result.to_dict()
            )
            candidates.update_status(
                candidate,
                new_status="REJECTED",
                rejection_reason=_format_violations(risk_result),
                approver_user_id=actor.user_id,
            )
            audit.append(
                candidate_id=candidate.id,
                event_type="RISK_REJECTED",
                user_id=actor.user_id,
                ip_hash=actor.ip_hash,
                user_agent_hash=actor.user_agent_hash,
                reason=_format_violations(risk_result),
                details={
                    "policy_version": risk_result.policy_version,
                    "violation_rule_ids": [
                        v.rule_id for v in risk_result.violations
                    ],
                    "phase": "approve_recheck",
                },
            )
            raise ApprovalDeniedError(
                "risk re-check failed at approval time",
                details={
                    "violation_rule_ids": [
                        v.rule_id for v in risk_result.violations
                    ],
                },
            )

        # PENDING_APPROVAL -> APPROVED
        candidates.update_status(
            candidate,
            new_status="APPROVED",
            approver_user_id=actor.user_id,
        )
        audit.append(
            candidate_id=candidate.id,
            event_type="APPROVED",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            details={
                "policy_version": risk_result.policy_version,
            },
        )

        # APPROVED -> SimulationBroker.submit_order -> EXECUTED_PAPER.
        # NOTE: the broker is the ONLY downstream order path. There is no
        # real-broker fallback. Tests assert via AST that this module
        # imports nothing from app.kis / requests / httpx / etc.
        try:
            submit_result = self._broker.submit_order(
                session,
                account_id=candidate.account_id,
                symbol=candidate.symbol,
                side=candidate.side,
                quantity=candidate.quantity,
                order_type=candidate.order_type,
                limit_price=candidate.limit_price,
                idempotency_key=f"approval-{candidate.id}",
                note=f"approved candidate id={candidate.id}",
            )
        except (PaperTradingDisabledError, SimulationBrokerError) as exc:
            raise ApprovalDeniedError(
                f"paper execution failed: {exc}",
                details={"error_type": type(exc).__name__},
            ) from exc

        candidates.attach_virtual_order(
            candidate, virtual_order_id=submit_result.order.id
        )
        candidates.update_status(candidate, new_status="EXECUTED_PAPER")
        audit.append(
            candidate_id=candidate.id,
            event_type="EXECUTED_PAPER",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            details={
                "virtual_order_id": submit_result.order.id,
                "deduplicated": submit_result.deduplicated,
            },
        )

        return ApproveResult(
            candidate=candidate,
            virtual_order_id=submit_result.order.id,
            risk_result=risk_result,
        )

    # ------------------------------------------------------------------
    # 3. reject -- PENDING_APPROVAL -> REJECTED
    # ------------------------------------------------------------------

    def reject(
        self,
        session: Session,
        *,
        candidate_id: int,
        actor: ApprovalActor,
        reason: str,
    ) -> OrderCandidate:
        self._assert_workflow_active()

        candidates = OrderCandidateRepository(session)
        audit = ApprovalAuditLogRepository(session)
        candidate = candidates.get_by_id(candidate_id)
        if candidate is None:
            raise ApprovalServiceError(
                f"OrderCandidate id={candidate_id} not found"
            )
        if candidate.status != "PENDING_APPROVAL":
            raise ApprovalDeniedError(
                f"candidate id={candidate_id} status is {candidate.status!r}; "
                f"only PENDING_APPROVAL candidates can be rejected",
                details={"current_status": candidate.status},
            )
        self._assert_kill_switch_off(
            session, candidate_id=candidate.id, actor=actor
        )

        candidates.reject(
            candidate,
            approver_user_id=actor.user_id or 0,
            reason=reason,
        )
        audit.append(
            candidate_id=candidate.id,
            event_type="REJECTED",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            reason=reason[:256] if reason else None,
        )
        return candidate

    # ------------------------------------------------------------------
    # 4. expire -- PENDING_APPROVAL -> EXPIRED
    # ------------------------------------------------------------------

    def expire(
        self,
        session: Session,
        *,
        candidate_id: int,
        actor: ApprovalActor | None = None,
    ) -> OrderCandidate:
        """System-driven expiration. ``actor`` may be NULL (scheduler / TTL).

        Skips both safety / kill-switch gates -- expiration MUST work
        regardless of operator settings (otherwise expired candidates
        accumulate forever).
        """
        actor = actor or ApprovalActor()
        candidates = OrderCandidateRepository(session)
        audit = ApprovalAuditLogRepository(session)

        candidate = candidates.get_by_id(candidate_id)
        if candidate is None:
            raise ApprovalServiceError(
                f"OrderCandidate id={candidate_id} not found"
            )
        try:
            candidates.expire(candidate)
        except InvalidOrderCandidateTransition as exc:
            raise ApprovalDeniedError(
                f"candidate id={candidate_id} cannot be expired from "
                f"status {candidate.status!r}",
                details={"current_status": candidate.status},
            ) from exc
        audit.append(
            candidate_id=candidate.id,
            event_type="EXPIRED",
            user_id=actor.user_id,
            ip_hash=actor.ip_hash,
            user_agent_hash=actor.user_agent_hash,
            reason="ttl_expired",
        )
        return candidate


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_violations(risk_result: RiskCheckResult) -> str:
    if not risk_result.violations:
        return "risk passed"
    rules = ", ".join(v.rule_id for v in risk_result.violations)
    return f"risk:{POLICY_VERSION} violations=[{rules}]"
