"""FastAPI dependencies for v0.8 Phase B auth.

Two key dependencies:

  * ``get_current_user`` -- resolves a Bearer token (when ``AUTH_ENABLED=true``)
    or returns the dev fallback user (``user_id=1``, ``via="auth_disabled_fallback"``)
    when ``AUTH_ENABLED=false``. This is the *non-enforcing* dependency: routers
    that wish to operate in both modes use it directly.
  * ``require_auth`` -- enforces a valid token even when ``AUTH_ENABLED=true``.
    Routers that protect mutating operations (Phase C Watchlist write
    endpoints) wire this in instead.

In the AUTH_ENABLED=false path the request is **not** authenticated -- it is
a developer convenience so existing read-only API surface keeps working.
Production deployments must set AUTH_ENABLED=true (and JWT_SECRET) to enable
real authentication.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import (
    AuthService,
    AuthenticatedUser,
    ExpiredTokenError,
    InvalidTokenError,
    JwtIssuer,
    PasswordHasher,
)
from app.config.settings import Settings, get_settings
from app.data.repositories.login_audit_logs import LoginAuditLogRepository
from app.data.repositories.users import UserRepository
from app.db.session import get_session


# auto_error=False so the dependency can short-circuit (return None) when
# AUTH_ENABLED=false and no header is supplied -- otherwise FastAPI would
# 403 every dev request.
_bearer_scheme = HTTPBearer(auto_error=False)

DEV_FALLBACK_USER_ID = 1

# Ephemeral per-process secret used for /api/auth/login when AUTH_ENABLED=false
# and no JWT_SECRET is configured. The token still works within the same
# process (so a dev / CI test can call /login then /me), but is invalidated on
# every restart -- which is appropriate because authentication is disabled.
# When AUTH_ENABLED=true, validate_auth_settings() at startup guarantees that
# the real Settings.jwt_secret is set, and this fallback is never used.
_DEV_EPHEMERAL_SECRET = secrets.token_hex(32)


def get_password_hasher() -> PasswordHasher:
    return PasswordHasher()


def get_jwt_issuer(settings: Settings = Depends(get_settings)) -> JwtIssuer:
    secret = settings.jwt_secret
    if not secret and not settings.auth_enabled:
        # AUTH_ENABLED=false dev fallback. Tokens still issue + decode within
        # this process, but restarts invalidate them and they cannot leak to
        # production (validate_auth_settings would reject AUTH_ENABLED=true
        # without a real secret).
        secret = _DEV_EPHEMERAL_SECRET
    return JwtIssuer(
        secret=secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expires_minutes,
    )


def get_auth_service(
    session: Session = Depends(get_session),
    hasher: PasswordHasher = Depends(get_password_hasher),
    issuer: JwtIssuer = Depends(get_jwt_issuer),
) -> AuthService:
    return AuthService(
        users=UserRepository(session),
        audit_logs=LoginAuditLogRepository(session),
        hasher=hasher,
        issuer=issuer,
    )


def get_current_user(
    settings: Settings = Depends(get_settings),
    issuer: JwtIssuer = Depends(get_jwt_issuer),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """Resolve the caller's authenticated identity, or dev fallback.

    * ``AUTH_ENABLED=false`` -> always returns the dev fallback (no check).
    * ``AUTH_ENABLED=true`` + missing / invalid / expired token -> 401.
    * ``AUTH_ENABLED=true`` + valid token -> the decoded identity.
    """
    if not settings.auth_enabled:
        return AuthenticatedUser(
            user_id=DEV_FALLBACK_USER_ID,
            username=None,
            via="auth_disabled_fallback",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded = issuer.decode(credentials.credentials)
    except ExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AuthenticatedUser(
        user_id=decoded.user_id,
        username=decoded.username,
        via="token",
        token=decoded,
    )


def require_auth(
    settings: Settings = Depends(get_settings),
    current: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Strict variant of ``get_current_user`` for protected mutating routes.

    * ``AUTH_ENABLED=true`` -> returns ``current`` (which is already a real
      user resolved via Bearer token, otherwise 401 was raised).
    * ``AUTH_ENABLED=false`` -> still returns the dev fallback so local
      Phase C / Phase D iteration is possible without configuring JWT, but
      logs a soft warning at the route layer (route-side responsibility).

    Phase C will use this for Watchlist POST / DELETE endpoints. Phase B
    introduces it but does NOT retrofit existing read-only routers.
    """
    return current


def extract_client_ip(request: Request) -> str | None:
    """Best-effort client IP extraction for audit hashing.

    Order: ``X-Forwarded-For`` first IP -> ``request.client.host`` ->
    ``None``. Both the raw header and ``request.client`` are passed to
    ``hash_for_audit`` and never stored verbatim.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        head = forwarded.split(",")[0].strip()
        if head:
            return head
    if request.client is not None:
        return request.client.host
    return None
