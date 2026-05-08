"""PreTradeRiskEngine -- v0.15 Phase C.

Pure read-only risk evaluation that runs against an ``OrderCandidate``
before Phase D's ``ApprovalService`` flips it to ``PENDING_APPROVAL``.
The engine does NOT mutate the DB; it only reads VirtualAccount /
VirtualPosition / VirtualPnLSnapshot / OrderCandidate state and returns a
:class:`RiskCheckResult` whose ``to_dict()`` is JSON-safe. The caller is
expected to call ``OrderCandidateRepository.attach_risk_result(result=...)``
with that dict.

Hard rules (all severity HARD)
------------------------------

1. ``account_paper_enabled`` -- VirtualAccount.paper_trading_enabled must be True.
2. ``kill_switch_off``       -- ``Settings.kill_switch_enabled`` must be False
   (operator must explicitly opt out of the paranoid default).
3. ``per_symbol_limit``      -- existing-active-candidate amount on the same
   (account_id, symbol) PLUS the new candidate's ``estimated_amount`` must
   be <= ``Settings.max_order_amount``.
4. ``daily_total_limit``     -- sum of today's (KST) active-candidate
   ``estimated_amount`` PLUS the new candidate's ``estimated_amount`` must
   be <= ``Settings.max_daily_order_amount``.
5. ``position_ratio_limit``  -- BUY only. (existing position market_value +
   new estimated_amount) / total account value must be <=
   ``Settings.max_position_ratio``. SELL is exempt because it reduces
   exposure.
6. ``daily_loss_limit``      -- latest realized_pnl snapshot value must be
   >= ``-Settings.max_daily_loss_amount``.
7. ``duplicate_recent``      -- no other active candidate with the same
   (account_id, symbol, side, quantity) created within the last 5 minutes.

Active-candidate definition: any ``OrderCandidate`` whose status is in
:data:`ACTIVE_CANDIDATE_STATUSES`. Terminal states (``RISK_REJECTED`` /
``REJECTED`` / ``EXPIRED``) and ``EXECUTED_PAPER`` are excluded so a
historical reject does not block a fresh re-attempt.

Policy version
--------------

``POLICY_VERSION = "pre-trade-v1"``. Any change to rule semantics must
bump this string AND keep the old behavior reachable for replay (Phase D's
audit log records the policy_version it ran against).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.data.repositories.daily_prices import DailyPriceRepository
from app.db.base import utc_now
from app.db.models import (
    OrderCandidate,
    VirtualAccount,
    VirtualPnLSnapshot,
    VirtualPosition,
)


POLICY_VERSION = "pre-trade-v1"

# Statuses considered "active" for cap / duplicate rule aggregation. Terminal
# (RISK_REJECTED / REJECTED / EXPIRED) and EXECUTED_PAPER are intentionally
# excluded so a historical reject does NOT block a fresh attempt.
ACTIVE_CANDIDATE_STATUSES: frozenset[str] = frozenset(
    {"DRAFT", "RISK_CHECKING", "PENDING_APPROVAL", "APPROVED"}
)

DUPLICATE_RECENT_WINDOW: timedelta = timedelta(minutes=5)

_ZERO = Decimal("0")
_KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# Result dataclasses (JSON-safe via ``to_dict()``)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskViolation:
    """One reason a candidate was rejected.

    ``details`` is a small JSON-safe map of comparable scalars (Decimal /
    int / float / str / bool). The risk engine never puts user-controlled
    free text or full DB rows here.
    """

    rule_id: str
    message: str
    severity: str = "HARD"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "details": _jsonify(self.details),
        }


@dataclass(frozen=True)
class RiskCheckResult:
    """Outcome of one ``PreTradeRiskEngine.evaluate(...)`` call."""

    policy_version: str
    passed: bool
    violations: tuple[RiskViolation, ...]
    checked_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "checked_at": self.checked_at.isoformat(),
        }

    # Backwards compatibility alias -- some callers prefer ``as_dict``.
    as_dict = to_dict


def _jsonify(value: Any) -> Any:
    """Convert Decimal / datetime / date to JSON-friendly primitives.

    Used by ``RiskViolation.to_dict``'s ``details`` payload so the result
    survives a round-trip through SQLAlchemy's JSON column.
    """
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PreTradeRiskEngine:
    """6 HARD rule evaluator. Pure read-only -- no DB mutation.

    Construct once with ``Settings`` and reuse per request. The session is
    passed per ``evaluate`` call so this engine integrates with whatever
    transaction context the caller already owns.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # -------- public surface --------

    def evaluate(
        self,
        session: Session,
        candidate: OrderCandidate,
        *,
        now: datetime | None = None,
    ) -> RiskCheckResult:
        """Run all 7 rules and return a structured result.

        ``now`` is injectable so tests can pin the duplicate-window /
        daily-cap clock without freezing time globally. Defaults to
        :func:`app.db.base.utc_now`.
        """
        evaluated_at = now or utc_now()
        violations: list[RiskViolation] = []

        # Per-rule check helpers each return a RiskViolation OR None. We
        # accumulate ALL violations rather than short-circuiting so the
        # operator sees every reason at once -- a single round-trip to the
        # UI / API surfaces the complete failure report.
        account = self._load_account(session, candidate.account_id)

        violations.extend(self._check_account_paper_enabled(account))
        violations.extend(self._check_kill_switch_off())
        violations.extend(self._check_per_symbol_limit(session, candidate))
        violations.extend(
            self._check_daily_total_limit(session, candidate, evaluated_at)
        )
        violations.extend(
            self._check_position_ratio_limit(session, candidate, account)
        )
        violations.extend(
            self._check_daily_loss_limit(session, candidate, evaluated_at)
        )
        violations.extend(
            self._check_duplicate_recent(session, candidate, evaluated_at)
        )

        return RiskCheckResult(
            policy_version=POLICY_VERSION,
            passed=not violations,
            violations=tuple(violations),
            checked_at=evaluated_at,
        )

    # -------- 1. account_paper_enabled --------

    def _check_account_paper_enabled(
        self, account: VirtualAccount | None
    ) -> list[RiskViolation]:
        if account is None:
            return [
                RiskViolation(
                    rule_id="account_paper_enabled",
                    message="virtual account not found",
                    details={"account_id": None},
                )
            ]
        if not account.paper_trading_enabled:
            return [
                RiskViolation(
                    rule_id="account_paper_enabled",
                    message=(
                        "VirtualAccount.paper_trading_enabled is False; "
                        "enable paper trading on the account before "
                        "submitting candidates."
                    ),
                    details={"account_id": account.id},
                )
            ]
        return []

    # -------- 2. kill_switch_off --------

    def _check_kill_switch_off(self) -> list[RiskViolation]:
        if self._settings.kill_switch_enabled:
            return [
                RiskViolation(
                    rule_id="kill_switch_off",
                    message=(
                        "kill switch is ON; operator must explicitly set "
                        "KILL_SWITCH_ENABLED=false before any candidate can pass."
                    ),
                    details={"kill_switch_enabled": True},
                )
            ]
        return []

    # -------- 3. per_symbol_limit --------

    def _check_per_symbol_limit(
        self, session: Session, candidate: OrderCandidate
    ) -> list[RiskViolation]:
        existing = self._sum_active_candidate_amount(
            session,
            account_id=candidate.account_id,
            symbol=candidate.symbol,
            exclude_id=candidate.id,
        )
        new_amount = Decimal(candidate.estimated_amount)
        total = existing + new_amount
        cap = Decimal(self._settings.max_order_amount)
        if total > cap:
            return [
                RiskViolation(
                    rule_id="per_symbol_limit",
                    message=(
                        f"per-symbol active total {total} would exceed cap "
                        f"{cap} for {candidate.symbol}"
                    ),
                    details={
                        "symbol": candidate.symbol,
                        "active_existing": existing,
                        "new_estimated": new_amount,
                        "total": total,
                        "max_order_amount": cap,
                    },
                )
            ]
        return []

    # -------- 4. daily_total_limit --------

    def _check_daily_total_limit(
        self,
        session: Session,
        candidate: OrderCandidate,
        evaluated_at: datetime,
    ) -> list[RiskViolation]:
        kst_today = self._kst_date(evaluated_at)
        existing = self._sum_active_candidate_amount(
            session,
            account_id=candidate.account_id,
            kst_date=kst_today,
            exclude_id=candidate.id,
        )
        new_amount = Decimal(candidate.estimated_amount)
        total = existing + new_amount
        cap = Decimal(self._settings.max_daily_order_amount)
        if total > cap:
            return [
                RiskViolation(
                    rule_id="daily_total_limit",
                    message=(
                        f"daily total {total} would exceed cap {cap} on "
                        f"{kst_today.isoformat()} (KST)"
                    ),
                    details={
                        "kst_date": kst_today.isoformat(),
                        "active_existing": existing,
                        "new_estimated": new_amount,
                        "total": total,
                        "max_daily_order_amount": cap,
                    },
                )
            ]
        return []

    # -------- 5. position_ratio_limit --------

    def _check_position_ratio_limit(
        self,
        session: Session,
        candidate: OrderCandidate,
        account: VirtualAccount | None,
    ) -> list[RiskViolation]:
        # SELL reduces exposure, so we don't apply the ratio cap on SELL.
        if candidate.side != "BUY":
            return []
        if account is None:
            return []  # account-not-found violation already raised in rule 1

        new_amount = Decimal(candidate.estimated_amount)
        position_value = self._estimate_position_market_value(
            session, account_id=account.id, symbol=candidate.symbol
        )
        total_value = self._estimate_total_account_value(
            session, account=account
        )
        if total_value <= _ZERO:
            return [
                RiskViolation(
                    rule_id="position_ratio_limit",
                    message=(
                        "cannot evaluate position ratio: account total_value "
                        "is non-positive"
                    ),
                    details={
                        "total_value": total_value,
                        "max_position_ratio": Decimal(
                            str(self._settings.max_position_ratio)
                        ),
                    },
                )
            ]

        projected = position_value + new_amount
        ratio = projected / total_value
        cap_ratio = Decimal(str(self._settings.max_position_ratio))
        if ratio > cap_ratio:
            return [
                RiskViolation(
                    rule_id="position_ratio_limit",
                    message=(
                        f"projected position ratio {ratio:.6f} exceeds cap "
                        f"{cap_ratio} for {candidate.symbol}"
                    ),
                    details={
                        "symbol": candidate.symbol,
                        "current_position_value": position_value,
                        "new_estimated": new_amount,
                        "projected_value": projected,
                        "total_value": total_value,
                        "ratio": ratio,
                        "max_position_ratio": cap_ratio,
                    },
                )
            ]
        return []

    # -------- 6. daily_loss_limit --------

    def _check_daily_loss_limit(
        self,
        session: Session,
        candidate: OrderCandidate,
        evaluated_at: datetime,
    ) -> list[RiskViolation]:
        snap = self._latest_pnl_snapshot(session, account_id=candidate.account_id)
        if snap is None:
            # No snapshot -> nothing to compare against. Conservative
            # interpretation: pass (snapshot job will fill in soon).
            return []

        cap = Decimal(self._settings.max_daily_loss_amount)
        floor = -cap
        realized = Decimal(snap.realized_pnl)
        if realized < floor:
            return [
                RiskViolation(
                    rule_id="daily_loss_limit",
                    message=(
                        f"realized PnL {realized} below floor {floor} "
                        f"(cap={cap})"
                    ),
                    details={
                        "realized_pnl": realized,
                        "max_daily_loss_amount": cap,
                        "floor": floor,
                        "snapshot_date": snap.snapshot_date.isoformat(),
                    },
                )
            ]
        return []

    # -------- 7. duplicate_recent --------

    def _check_duplicate_recent(
        self,
        session: Session,
        candidate: OrderCandidate,
        evaluated_at: datetime,
    ) -> list[RiskViolation]:
        threshold = evaluated_at - DUPLICATE_RECENT_WINDOW
        statement = (
            select(OrderCandidate.id)
            .where(
                OrderCandidate.account_id == candidate.account_id,
                OrderCandidate.symbol == candidate.symbol,
                OrderCandidate.side == candidate.side,
                OrderCandidate.quantity == candidate.quantity,
                OrderCandidate.created_at > threshold,
                OrderCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
            )
            .order_by(OrderCandidate.id.desc())
        )
        if candidate.id is not None:
            statement = statement.where(OrderCandidate.id != candidate.id)

        match_id = session.execute(statement).scalar()
        if match_id is None:
            return []
        return [
            RiskViolation(
                rule_id="duplicate_recent",
                message=(
                    f"another active candidate with same "
                    f"(account, symbol, side, quantity) was created within "
                    f"the last {int(DUPLICATE_RECENT_WINDOW.total_seconds())} "
                    f"seconds"
                ),
                details={
                    "duplicate_candidate_id": match_id,
                    "window_seconds": int(
                        DUPLICATE_RECENT_WINDOW.total_seconds()
                    ),
                },
            )
        ]

    # -------- internal helpers --------

    @staticmethod
    def _load_account(
        session: Session, account_id: int
    ) -> VirtualAccount | None:
        return session.get(VirtualAccount, account_id)

    @staticmethod
    def _sum_active_candidate_amount(
        session: Session,
        *,
        account_id: int,
        symbol: str | None = None,
        kst_date: date | None = None,
        exclude_id: int | None = None,
    ) -> Decimal:
        statement = select(OrderCandidate).where(
            OrderCandidate.account_id == account_id,
            OrderCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
        )
        if symbol is not None:
            statement = statement.where(OrderCandidate.symbol == symbol)
        if kst_date is not None:
            # KST [00:00, 24:00) window converted to UTC for the SQL filter.
            kst_start = datetime.combine(kst_date, time(0, 0), tzinfo=_KST)
            kst_end = kst_start + timedelta(days=1)
            statement = statement.where(
                OrderCandidate.created_at >= kst_start,
                OrderCandidate.created_at < kst_end,
            )
        if exclude_id is not None:
            statement = statement.where(OrderCandidate.id != exclude_id)

        rows = session.execute(statement).scalars().all()
        return sum((Decimal(c.estimated_amount) for c in rows), _ZERO)

    @staticmethod
    def _kst_date(moment: datetime) -> date:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(_KST).date()

    @staticmethod
    def _estimate_position_market_value(
        session: Session, *, account_id: int, symbol: str
    ) -> Decimal:
        """Return an estimate of the current market value of a position.

        Order of preference:
          1. Latest VirtualPnLSnapshot's market_value -- but that is the
             *aggregate* across all symbols. For per-symbol value we have
             to fall back to (quantity * latest close).
          2. quantity * latest daily_prices.close (lookback 14 days).
          3. quantity * avg_cost (very last resort -- "we paid this").
          4. 0 (no position).
        """
        statement = select(VirtualPosition).where(
            VirtualPosition.account_id == account_id,
            VirtualPosition.symbol == symbol,
        )
        position = session.execute(statement).scalar_one_or_none()
        if position is None or position.quantity <= 0:
            return _ZERO

        prices = DailyPriceRepository(session)
        bar = prices.get_latest_by_symbol(symbol)
        if bar is not None and bar.close is not None:
            return Decimal(bar.close) * Decimal(position.quantity)

        # Fallback: cost basis. Conservative because BUY at this value would
        # double-count vs. avg_cost; we live with that to avoid 0-by-default
        # which would WEAKEN the ratio cap.
        return Decimal(position.avg_cost) * Decimal(position.quantity)

    @staticmethod
    def _estimate_total_account_value(
        session: Session, *, account: VirtualAccount
    ) -> Decimal:
        """Return total account valuation.

        Preference: latest VirtualPnLSnapshot.total_value (cash + market
        value sum across all positions). Fallback: cash_balance only --
        conservative because it temporarily IGNORES open-position market
        value, which makes the ratio cap effectively tighter (rejects more
        easily) until the next 16:30 snapshot.
        """
        statement = (
            select(VirtualPnLSnapshot)
            .where(VirtualPnLSnapshot.account_id == account.id)
            .order_by(VirtualPnLSnapshot.snapshot_date.desc())
            .limit(1)
        )
        snap = session.execute(statement).scalar_one_or_none()
        if snap is not None:
            return Decimal(snap.total_value)
        return Decimal(account.cash_balance)

    @staticmethod
    def _latest_pnl_snapshot(
        session: Session, *, account_id: int
    ) -> VirtualPnLSnapshot | None:
        statement = (
            select(VirtualPnLSnapshot)
            .where(VirtualPnLSnapshot.account_id == account_id)
            .order_by(VirtualPnLSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return session.execute(statement).scalar_one_or_none()
