"""v0.8 Phase B -- single-user authentication foundation.
v0.9 Phase A -- brute force guard added (BruteForceGuard / BruteForceLockedError).

Public surface:

  * ``PasswordHasher`` -- scrypt-based password hashing (no bcrypt dependency).
  * ``JwtIssuer`` -- HS256 JWT create / decode with TTL.
  * ``hash_for_audit`` -- SHA256 hash for IP / user-agent before persistence.
  * ``AuthService`` -- composes hasher + issuer + repositories for login flow.
  * ``InvalidTokenError`` / ``ExpiredTokenError`` / ``MissingSecretError`` --
    typed exceptions consumed by FastAPI dependencies.
  * ``BruteForceGuard`` / ``BruteForceLockedError`` -- in-memory failure
    tracking and lockout for POST /api/auth/login (v0.9 Phase A).
  * Dependencies: ``get_current_user`` / ``require_auth`` (in
    ``app.auth.dependencies``).

Multi-user / RBAC / OAuth / SSO / refresh tokens are intentionally out of
scope. See PLAN-0008 for the policy.
"""

from app.auth.brute_force import BruteForceGuard, BruteForceLockedError
from app.auth.security import (
    AuthService,
    AuthenticatedUser,
    DecodedToken,
    ExpiredTokenError,
    InvalidTokenError,
    JwtIssuer,
    LoginResult,
    MissingSecretError,
    PasswordHasher,
    hash_for_audit,
    validate_auth_settings,
)


__all__ = [
    "AuthenticatedUser",
    "AuthService",
    "BruteForceGuard",
    "BruteForceLockedError",
    "DecodedToken",
    "ExpiredTokenError",
    "InvalidTokenError",
    "JwtIssuer",
    "LoginResult",
    "MissingSecretError",
    "PasswordHasher",
    "hash_for_audit",
    "validate_auth_settings",
]
