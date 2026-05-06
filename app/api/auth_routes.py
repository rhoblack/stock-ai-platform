"""v0.8 Phase B authentication endpoints.

Three endpoints, all under ``/api/auth/*``:

  * ``POST /api/auth/login`` -- exchange ``{username, password}`` for a JWT
    Bearer token. Failures collapse to a single generic 401 so the response
    does not reveal whether the username exists.
  * ``POST /api/auth/logout`` -- best-effort audit log entry. JWTs are
    stateless; this is a logging hook, not a token revocation.
  * ``GET /api/auth/me`` -- introspection. Always succeeds when AUTH is
    disabled (returns the dev fallback identity); when enabled requires a
    valid Bearer token.

This is the **only** module in v0.8 Phase B that exposes POST endpoints.
Watchlist (Phase C) will follow the same pattern but live in a separate
router.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

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
)
from app.config.settings import Settings, get_settings


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


@router.post("/login", response_model=LoginResponse)
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

    try:
        result: LoginResult | None = service.login(
            username=payload.username,
            password=payload.password,
            source_ip=extract_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
    except MissingSecretError as exc:
        # Issuer was invoked without a secret -- AUTH_ENABLED=true but secret
        # got cleared mid-process. Treat as service-unavailable, don't leak
        # the auth-related error to the client.
        logger.error("login failed: missing JWT secret")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth is unavailable",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_GENERIC_LOGIN_ERROR,
        )

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
