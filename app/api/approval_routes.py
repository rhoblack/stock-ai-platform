"""v0.15 Phase D -- Approval Workflow API.

Endpoints (all under ``/api/approvals``):

  * ``GET    /api/approvals/candidates?status=&account_id=&limit=``
  * ``GET    /api/approvals/candidates/{id}``
  * ``POST   /api/approvals/candidates``                  (3-gate mutation)
  * ``POST   /api/approvals/{id}/approve``                (3-gate mutation)
  * ``POST   /api/approvals/{id}/reject``                 (3-gate mutation)
  * ``POST   /api/approvals/{id}/expire``                 (3-gate mutation)
  * ``GET    /api/approvals/audit?candidate_id=&limit=``

Mutation gating order (matches PLAN-0015 §3):
  1. ``trading_safety_enabled`` must be True       -> else 503
  2. ``kill_switch_enabled`` must be False         -> else 503 + audit
  3. ``require_auth`` (Phase B convention)         -> else 401

Hard policies (regression-tested):
  * The router NEVER imports KIS / DART / RSS / requests / httpx.
  * Approved candidates are forwarded to ``SimulationBroker.submit_order``
    via :class:`ApprovalService` -- no real-broker / KIS path.
  * Forbidden response field guard (12 substrings + KIS variants) is
    enforced by the schemas + e2e payload assertions.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.api.schemas import (
    ApprovalAuditLogSchema,
    ApprovalAuditResponse,
    ApprovalCandidateStatusResponse,
    ApproveCandidateResponse,
    CreateOrderCandidateRequest,
    CreateOrderCandidateResponse,
    ExpireCandidateRequest,
    OrderCandidateDetailResponse,
    OrderCandidateSchema,
    OrderCandidatesResponse,
    RejectCandidateRequest,
    RiskCheckResultSchema,
    RiskViolationSchema,
)
from app.approval.approval_service import (
    ApprovalActor,
    ApprovalDeniedError,
    ApprovalService,
    ApprovalServiceError,
    KillSwitchBlockedError,
    TradingSafetyDisabledError,
)
from app.auth.dependencies import extract_client_ip, require_auth
from app.auth.security import AuthenticatedUser, hash_for_audit
from app.config.settings import Settings, get_settings
from app.data.repositories.approval_audit_log import (
    ApprovalAuditLogRepository,
    ApprovalAuditLogValidationError,
    VALID_EVENT_TYPES,
)
from app.data.repositories.order_candidate import (
    OrderCandidateRepository,
    OrderCandidateValidationError,
    VALID_STATUSES,
)
from app.data.repositories.virtual_account import VirtualAccountRepository
from app.db.models import ApprovalAuditLog, OrderCandidate
from app.db.session import get_session


router = APIRouter(prefix="/api/approvals", tags=["approval-trading"])


# ---------------------------------------------------------------------------
# Mutation gating
# ---------------------------------------------------------------------------


def _require_trading_safety_enabled(settings: Settings) -> None:
    if not settings.trading_safety_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "approval workflow is disabled — set TRADING_SAFETY_ENABLED=true "
                "in operator-private .env to opt in"
            ),
        )


def _require_kill_switch_off(settings: Settings) -> None:
    if settings.kill_switch_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "kill switch is ON — set KILL_SWITCH_ENABLED=false in "
                "operator-private .env to opt out of the paranoid default"
            ),
        )


def _build_actor(request: Request, current: AuthenticatedUser) -> ApprovalActor:
    raw_ip = extract_client_ip(request)
    raw_ua = request.headers.get("user-agent")
    return ApprovalActor(
        user_id=current.user_id,
        ip_hash=hash_for_audit(raw_ip),
        user_agent_hash=hash_for_audit(raw_ua),
    )


def _resolve_account_id(
    session: Session,
    *,
    requested: int | None,
    user_id: int | None,
) -> int:
    accounts = VirtualAccountRepository(session)
    if requested is not None:
        acc = accounts.get_by_id(requested)
        if acc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="virtual account not found",
            )
        return acc.id
    candidates = accounts.list_by_user(user_id) or accounts.list_by_user(None)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no virtual account exists for this user",
        )
    return candidates[0].id


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _to_candidate_schema(candidate: OrderCandidate) -> OrderCandidateSchema:
    return OrderCandidateSchema(
        id=candidate.id,
        account_id=candidate.account_id,
        source=candidate.source,
        source_ref_id=candidate.source_ref_id,
        symbol=candidate.symbol,
        side=candidate.side,
        quantity=candidate.quantity,
        order_type=candidate.order_type,
        limit_price=(
            str(candidate.limit_price)
            if candidate.limit_price is not None
            else None
        ),
        estimated_amount=str(candidate.estimated_amount),
        status=candidate.status,
        rejection_reason=candidate.rejection_reason,
        expires_at=candidate.expires_at,
        virtual_order_id=candidate.virtual_order_id,
        approver_user_id=candidate.approver_user_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def _to_risk_schema(payload: dict | None) -> RiskCheckResultSchema | None:
    if payload is None:
        return None
    violations = [
        RiskViolationSchema(
            rule_id=v.get("rule_id", ""),
            severity=v.get("severity", "HARD"),
            message=v.get("message", ""),
            details=v.get("details"),
        )
        for v in payload.get("violations", [])
        if isinstance(v, dict)
    ]
    return RiskCheckResultSchema(
        policy_version=payload.get("policy_version"),
        passed=payload.get("passed"),
        violations=violations,
        checked_at=payload.get("checked_at"),
    )


def _to_audit_schema(row: ApprovalAuditLog) -> ApprovalAuditLogSchema:
    return ApprovalAuditLogSchema(
        id=row.id,
        candidate_id=row.candidate_id,
        event_type=row.event_type,
        user_id=row.user_id,
        reason=row.reason,
        details=row.details_json,
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# GET /api/approvals/candidates
# ---------------------------------------------------------------------------


@router.get("/candidates", response_model=OrderCandidatesResponse)
def list_candidates(
    status_filter: str | None = Query(None, alias="status"),
    account_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> OrderCandidatesResponse:
    if status_filter is not None and status_filter not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )
    repo = OrderCandidateRepository(session)
    if account_id is not None:
        rows = repo.list_by_account(
            account_id, status=status_filter, limit=limit
        )
    elif status_filter is not None:
        rows = repo.list_by_status(status_filter, limit=limit)
    else:
        rows = repo.list_pending(limit=limit)
    return OrderCandidatesResponse(
        candidates=[_to_candidate_schema(r) for r in rows],
        total=len(rows),
        limit=limit,
    )


# ---------------------------------------------------------------------------
# GET /api/approvals/candidates/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/candidates/{candidate_id}",
    response_model=OrderCandidateDetailResponse,
)
def get_candidate_detail(
    candidate_id: int = Path(..., ge=1),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> OrderCandidateDetailResponse:
    repo = OrderCandidateRepository(session)
    candidate = repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order candidate not found",
        )
    return OrderCandidateDetailResponse(
        candidate=_to_candidate_schema(candidate),
        risk_check_result=_to_risk_schema(candidate.risk_check_result_json),
    )


# ---------------------------------------------------------------------------
# POST /api/approvals/candidates
# ---------------------------------------------------------------------------


@router.post(
    "/candidates",
    response_model=CreateOrderCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    payload: CreateOrderCandidateRequest = Body(...),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> CreateOrderCandidateResponse:
    _require_trading_safety_enabled(settings)
    _require_kill_switch_off(settings)

    account_id = _resolve_account_id(
        session,
        requested=payload.account_id,
        user_id=current.user_id,
    )
    actor = _build_actor(request, current)
    service = ApprovalService(settings=settings)
    ttl = (
        timedelta(minutes=payload.ttl_minutes)
        if payload.ttl_minutes is not None
        else None
    )
    try:
        result = service.create_candidate(
            session,
            account_id=account_id,
            source=payload.source,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            order_type=payload.order_type,
            limit_price=payload.limit_price,
            estimated_amount=(payload.estimated_amount or "0"),
            source_ref_id=payload.source_ref_id,
            ttl=ttl,
            actor=actor,
        )
    except KillSwitchBlockedError as exc:
        # Defense-in-depth: only fires if settings flipped between gate and call.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except TradingSafetyDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except OrderCandidateValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    session.commit()

    return CreateOrderCandidateResponse(
        candidate=_to_candidate_schema(result.candidate),
        risk_check_result=_to_risk_schema(result.risk_result.to_dict()),
        risk_passed=result.risk_passed,
    )


# ---------------------------------------------------------------------------
# POST /api/approvals/{id}/approve
# ---------------------------------------------------------------------------


@router.post(
    "/{candidate_id}/approve",
    response_model=ApproveCandidateResponse,
)
def approve_candidate(
    candidate_id: int = Path(..., ge=1),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> ApproveCandidateResponse:
    _require_trading_safety_enabled(settings)
    _require_kill_switch_off(settings)
    actor = _build_actor(request, current)
    service = ApprovalService(settings=settings)
    try:
        result = service.approve(
            session, candidate_id=candidate_id, actor=actor
        )
    except ApprovalServiceError as exc:
        if isinstance(exc, KillSwitchBlockedError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            )
        if isinstance(exc, ApprovalDeniedError):
            # Distinguish "not found" from semantic denial.
            if "not found" in str(exc):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )
        if "not found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
    session.commit()

    return ApproveCandidateResponse(
        candidate=_to_candidate_schema(result.candidate),
        virtual_order_id=result.virtual_order_id,
    )


# ---------------------------------------------------------------------------
# POST /api/approvals/{id}/reject
# ---------------------------------------------------------------------------


@router.post(
    "/{candidate_id}/reject",
    response_model=ApprovalCandidateStatusResponse,
)
def reject_candidate(
    candidate_id: int = Path(..., ge=1),
    payload: RejectCandidateRequest = Body(...),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> ApprovalCandidateStatusResponse:
    _require_trading_safety_enabled(settings)
    _require_kill_switch_off(settings)
    actor = _build_actor(request, current)
    service = ApprovalService(settings=settings)
    try:
        candidate = service.reject(
            session,
            candidate_id=candidate_id,
            actor=actor,
            reason=payload.reason,
        )
    except KillSwitchBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except ApprovalDeniedError as exc:
        if "not found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    except ApprovalServiceError as exc:
        if "not found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        raise
    session.commit()
    return ApprovalCandidateStatusResponse(
        candidate_id=candidate.id, new_status=candidate.status
    )


# ---------------------------------------------------------------------------
# POST /api/approvals/{id}/expire
# ---------------------------------------------------------------------------


@router.post(
    "/{candidate_id}/expire",
    response_model=ApprovalCandidateStatusResponse,
)
def expire_candidate(
    candidate_id: int = Path(..., ge=1),
    payload: ExpireCandidateRequest = Body(default=None),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(require_auth),
) -> ApprovalCandidateStatusResponse:
    _require_trading_safety_enabled(settings)
    # Note: expiration is allowed even when kill_switch is ON to avoid
    # candidates accumulating indefinitely; but the route still enforces
    # the explicit operator gate via _require_trading_safety_enabled.
    actor = _build_actor(request, current)
    service = ApprovalService(settings=settings)
    try:
        candidate = service.expire(
            session, candidate_id=candidate_id, actor=actor
        )
    except ApprovalDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    except ApprovalServiceError as exc:
        if "not found" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            )
        raise
    session.commit()
    return ApprovalCandidateStatusResponse(
        candidate_id=candidate.id, new_status=candidate.status
    )


# ---------------------------------------------------------------------------
# GET /api/approvals/audit
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=ApprovalAuditResponse)
def list_audit_logs(
    candidate_id: int | None = Query(None, ge=1),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    current: AuthenticatedUser = Depends(require_auth),
) -> ApprovalAuditResponse:
    if event_type is not None and event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"event_type must be one of {sorted(VALID_EVENT_TYPES)}",
        )
    repo = ApprovalAuditLogRepository(session)
    try:
        if candidate_id is not None:
            rows = repo.list_by_candidate(candidate_id, limit=limit)
        else:
            rows = repo.list_recent(event_type=event_type, limit=limit)
    except ApprovalAuditLogValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return ApprovalAuditResponse(
        items=[_to_audit_schema(r) for r in rows],
        total=len(rows),
        limit=limit,
    )
