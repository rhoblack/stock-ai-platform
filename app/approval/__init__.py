"""v0.15 Phase D -- Approval Workflow service layer.

Orchestrates OrderCandidate state machine + PreTradeRiskEngine +
SimulationBroker (paper execution only) + ApprovalAuditLog. NEVER calls
KIS / real broker -- the only downstream order path is
``SimulationBroker.submit_order``.
"""

from app.approval.approval_service import (
    ApprovalDeniedError,
    ApprovalService,
    ApprovalServiceError,
    KillSwitchBlockedError,
    TradingSafetyDisabledError,
)


__all__ = [
    "ApprovalDeniedError",
    "ApprovalService",
    "ApprovalServiceError",
    "KillSwitchBlockedError",
    "TradingSafetyDisabledError",
]
