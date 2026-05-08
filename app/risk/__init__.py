"""v0.15 Phase C -- PreTradeRiskEngine and supporting dataclasses.

This package owns the **read-only** risk evaluation that runs before an
``OrderCandidate`` is moved to ``PENDING_APPROVAL``. The engine never
mutates the DB on its own; it returns a :class:`RiskCheckResult` whose
``to_dict()`` is JSON-safe and goes straight into
``OrderCandidateRepository.attach_risk_result(result=...)``.

Forbidden imports across this package (regression-tested):
``requests / httpx / urllib / urllib3 / app.kis / app.data.dart_provider /
app.data.rss_provider / app.data.collectors.kis_client``. Everything is
local DB reads + ``Settings`` snapshots.
"""

from app.risk.pre_trade_risk_engine import (
    ACTIVE_CANDIDATE_STATUSES,
    POLICY_VERSION,
    DUPLICATE_RECENT_WINDOW,
    PreTradeRiskEngine,
    RiskCheckResult,
    RiskViolation,
)


__all__ = [
    "ACTIVE_CANDIDATE_STATUSES",
    "DUPLICATE_RECENT_WINDOW",
    "POLICY_VERSION",
    "PreTradeRiskEngine",
    "RiskCheckResult",
    "RiskViolation",
]
