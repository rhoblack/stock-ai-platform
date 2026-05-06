"""v0.8 Phase B authentication endpoints.
v0.9 Phase A -- rate limit + brute force protection added to POST /login.

Three endpoints, all under ``/api/auth/*``:

  * ``POST /api/auth/login`` -- exchange ``{username, password}`` for a JWT
    Bearer token. Failures collapse to a single generic 401 so the response
    does not reveal whether the username exists, is locked out, or has a wrong
    password. Rate limited (Settings.rate_limit_auth, default 5/minute per IP).
    Brute force protection: after Settings.auth_bruteforce_max_failures failures
    within the window the key is locked for Settings.auth_bruteforce_lockout_seconds.
  * ``POST /api/auth/logout`` -- best-effort audit log entry. JWTs are
    stateless; this is a logging hook, not a token revocation.
  * ``GET /api/auth/me`` -- introspection. Always succeeds when AUTH is
    disabled (returns the dev fallback identity); when enabled requires a
    valid Bearer token.
"""

import logging
from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.brute_force import BruteForceGuard, BruteForceLockedError
from app.auth.dependencies import (
    extract_client_ip,
    get_auth_service,
    get_current_user,
    get_jwt_issuer,
)
from app.auth.security import (
    AuthenticatedUser,
    AuthService,
    JwtIssuer,
    LoginResult,
    MissingSecretError,
    hash_for_audit,
)
from app.config.settings import Settings, get_settings
from app.data.repositories.login_audit_logs import EVENT_LOCKOUT_REJECTED
from app.middleware.rate_limit import limiter


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas (kept local to the auth surface area)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginUser(BaseModel):
    id: int
    username: str
    is_admin: bool

    class Config:
        orm_mode = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    issued_at: datetime
    expires_at: datetime
    user: LoginUser


class LogoutResponse(BaseModel):
    status: str = "ok"


class MeResponse(BaseModel):
    auth_enabled: bool
    via: str
    user: Optional[LoginUser] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/api/auth", tags=["auth"])


_GENERIC_LOGIN_ERROR = "invalid username or password"


def _get_auth_rate_limit() -> str:
    return get_settings().rate_limit_auth


@router.post("/login", response_model=LoginResponse)
@limiter.limit(_get_auth_rate_limit)
def login(
    payload: LoginRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    if settings.auth_enabled and not settings.jwt_secret:
        # Should be caught at startup, but keep as belt-and-braces.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth is enabled but JWT_SECRET is not configured",
        )

    source_ip = extract_client_ip(request)
    ip_hash = hash_for_audit(source_ip)
    ua_hash = hash_for_audit(request.headers.get("User-Agent"))

    # ------------------------------------------------------------------
    # v0.9 Phase A -- Brute force pre-check.
    # Performed before any DB lookup so locked requests never reach the DB.
    # The generic error keeps the response identical to a wrong-password 401.
    # Lockout is recorded in audit as LOCKOUT_REJECTED (no timing hint exposed).
    # ------------------------------------------------------------------
    guard: Optional[BruteForceGuard] = getattr(request.app.state, "bruteforce_guard", None)
    bruteforce_active = getattr(request.app.state, "bruteforce_enabled", False)

    if bruteforce_active and guard is not None:
        try:
            guard.check_allowed(payload.username, ip_hash)
        except BruteForceLockedError:
            service.audit_logs.create(
                event_type=EVENT_LOCKOUT_REJECTED,
                username=payload.username,
                user_id=None,
                source_ip_hash=ip_hash,
                user_agent_hash=ua_hash,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_GENERIC_LOGIN_ERROR,
            )

    try:
        result: Union[LoginResult, None] = service.login(
            username=payload.username,
            password=payload.password,
            source_ip=source_ip,
            user_agent=request.headers.get("User-Agent"),
        )
    except MissingSecretError as exc:
        logger.error("login failed: missing JWT secret")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth is unavailable",
        ) from exc

    if result is None:
        # Record failure in brute force guard so the counter advances.
        if bruteforce_active and guard is not None:
            guard.record_failure(payload.username, ip_hash)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_GENERIC_LOGIN_ERROR,
        )

    # Success -- clear the failure counter so a legitimate user is not locked
    # out after a previous series of mistakes followed by a correct login.
    if bruteforce_active and guard is not None:
        guard.record_success(payload.username, ip_hash)

    expires_in = max(0, int((result.expires_at - result.issued_at).total_seconds()))
    return LoginResponse(
        access_token=result.token,
        token_type="bearer",
        expires_in=expires_in,
        issued_at=result.issued_at,
        expires_at=result.expires_at,
        user=LoginUser(
            id=result.user.id,
            username=result.user.username,
            is_admin=result.user.is_admin,
        ),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    current: AuthenticatedUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> LogoutResponse:
    service.record_logout(
        user=current,
        source_ip=extract_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    return LogoutResponse()


@router.get("/me", response_model=MeResponse)
def me(
    settings: Settings = Depends(get_settings),
    issuer: JwtIssuer = Depends(get_jwt_issuer),
    current: AuthenticatedUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    if not settings.auth_enabled:
        return MeResponse(
            auth_enabled=False,
            via=current.via,
            user=None,
        )

    # AUTH_ENABLED=true: get_current_user has either raised 401 or returned a
    # token-bearing identity. Look up the row to surface the live username /
    # is_admin (token claim alone may be stale if the user was deactivated).
    user_row = service.users.get_by_id(current.user_id)
    if user_row is None or not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists or is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return MeResponse(
        auth_enabled=True,
        via=current.via,
        user=LoginUser(
            id=user_row.id,
            username=user_row.username,
            is_admin=user_row.is_admin,
        ),
    )
