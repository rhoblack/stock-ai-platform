"""Cryptographic primitives + auth orchestration for v0.8 Phase B.

Design notes:

* **scrypt over bcrypt.** Python's stdlib ``hashlib.scrypt`` provides a
  memory-hard password-hashing algorithm with no native-extension build
  dependency, so it works on every supported Python install (CPython,
  MSYS2 UCRT64, Alpine, etc.) without compilation. bcrypt would also be
  acceptable but lacks PyPI wheels for some platforms; scrypt removes
  that operational risk while keeping security guarantees.
* **JWT (HS256).** Symmetric signing with a single shared secret loaded
  from ``Settings.jwt_secret``. Asymmetric / OAuth flows are out of scope
  for v0.8.
* **Append-only audit logging.** Source IP and user agent are SHA256-hashed
  at the route layer before being handed to the repository. Raw values are
  never persisted.
* **Constant-time comparison.** Both password verification (``hashlib.scrypt``
  output compared via ``hmac.compare_digest``) and the audit-hash helper rely
  on constant-time digests to avoid timing oracles.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt

from app.config.settings import Settings, get_settings
from app.data.repositories.login_audit_logs import (
    EVENT_LOGIN_FAILED,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    LoginAuditLogRepository,
)
from app.data.repositories.users import UserRepository
from app.db.models import User


SCRYPT_PREFIX = "scrypt"
SALT_BYTES = 16
DERIVED_KEY_BYTES = 32
# RFC 7914 maxmem default for `hashlib.scrypt` (~32 MiB at n=2^14, r=8, p=1)
# with headroom for future cost increases. Fixed here so test cost overrides
# don't trip the default ceiling.
SCRYPT_MAXMEM = 64 * 1024 * 1024


class MissingSecretError(RuntimeError):
    """Raised when AUTH_ENABLED=true but JWT_SECRET is unset."""


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or fails signature verification."""


class ExpiredTokenError(InvalidTokenError):
    """Raised specifically when the JWT has passed its ``exp`` claim."""


@dataclass(frozen=True)
class DecodedToken:
    user_id: int
    username: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class AuthenticatedUser:
    """A user resolved by ``get_current_user`` for downstream dependencies.

    ``via`` is one of:
      * ``"token"`` -- AUTH_ENABLED=true and a valid Bearer token was supplied.
      * ``"auth_disabled_fallback"`` -- AUTH_ENABLED=false; the dependency
        returned the dev fallback user id (``1``). Such requests are not
        authenticated and ``user_id`` may not exist in the DB.
    """

    user_id: int
    username: str | None
    via: str
    token: DecodedToken | None = None


# ---------------------------------------------------------------------------
# Password hashing -- scrypt
# ---------------------------------------------------------------------------


class PasswordHasher:
    """Wraps ``hashlib.scrypt`` for password hashing and verification.

    Hash format: ``scrypt$<n>$<r>$<p>$<salt_b64>$<derived_b64>``.

    Cost parameters are read from ``Settings`` at construction time and may
    be overridden in tests via the ``n`` / ``r`` / ``p`` constructor args.
    """

    def __init__(
        self,
        *,
        n: int | None = None,
        r: int | None = None,
        p: int | None = None,
    ) -> None:
        s = get_settings()
        self.n = n if n is not None else s.password_hash_n
        self.r = r if r is not None else s.password_hash_r
        self.p = p if p is not None else s.password_hash_p

    @staticmethod
    def _b64encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    def hash_password(self, password: str) -> str:
        if not password:
            raise ValueError("password must not be empty")
        salt = secrets.token_bytes(SALT_BYTES)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=self.n,
            r=self.r,
            p=self.p,
            dklen=DERIVED_KEY_BYTES,
            maxmem=SCRYPT_MAXMEM,
        )
        return (
            f"{SCRYPT_PREFIX}${self.n}${self.r}${self.p}"
            f"${self._b64encode(salt)}${self._b64encode(derived)}"
        )

    @staticmethod
    def _b64decode(raw: str) -> bytes:
        padding = 4 - (len(raw) % 4)
        if padding and padding < 4:
            raw = raw + ("=" * padding)
        return base64.urlsafe_b64decode(raw.encode("ascii"))

    def verify_password(self, password: str, stored: str) -> bool:
        """Return True iff ``password`` matches the previously hashed ``stored``.

        Returns False on any malformed hash rather than raising -- callers
        should treat verification as a boolean and not leak format details to
        end users (the auth route returns a generic error on failure).
        """
        if not stored:
            return False
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != SCRYPT_PREFIX:
            return False
        try:
            n = int(parts[1])
            r = int(parts[2])
            p = int(parts[3])
            salt = self._b64decode(parts[4])
            expected = self._b64decode(parts[5])
        except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
            return False
        try:
            derived = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                dklen=len(expected),
                maxmem=SCRYPT_MAXMEM,
            )
        except (ValueError, OverflowError):
            return False
        return hmac.compare_digest(derived, expected)


# ---------------------------------------------------------------------------
# JWT issuance + validation
# ---------------------------------------------------------------------------


class JwtIssuer:
    """Issues + validates HS256 (or configured algorithm) JWTs.

    The constructor reads from ``Settings`` if not given an explicit secret /
    algorithm / TTL -- production-time injection. Tests pass values directly
    to keep the Settings cache untouched.
    """

    def __init__(
        self,
        *,
        secret: str | None = None,
        algorithm: str | None = None,
        expires_minutes: int | None = None,
    ) -> None:
        s = get_settings()
        self._secret = secret if secret is not None else s.jwt_secret
        self.algorithm = algorithm or s.jwt_algorithm
        self.expires_minutes = (
            expires_minutes if expires_minutes is not None else s.jwt_expires_minutes
        )

    @property
    def secret(self) -> str:
        if not self._secret:
            raise MissingSecretError(
                "JWT_SECRET is not configured. Set the JWT_SECRET environment "
                "variable when AUTH_ENABLED=true."
            )
        return self._secret

    def issue(self, *, user_id: int, username: str) -> tuple[str, datetime, datetime]:
        """Return ``(token, issued_at, expires_at)``."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.expires_minutes)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }
        token = pyjwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token, now, expires

    def decode(self, token: str) -> DecodedToken:
        try:
            payload = pyjwt.decode(token, self.secret, algorithms=[self.algorithm])
        except pyjwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError("token expired") from exc
        except pyjwt.InvalidTokenError as exc:
            raise InvalidTokenError(f"invalid token: {exc}") from exc

        try:
            user_id = int(payload["sub"])
            username = str(payload["username"])
            issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
            expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError(f"malformed token payload: {exc}") from exc

        return DecodedToken(
            user_id=user_id,
            username=username,
            issued_at=issued_at,
            expires_at=expires_at,
        )


# ---------------------------------------------------------------------------
# Audit-hash helper
# ---------------------------------------------------------------------------


def hash_for_audit(value: str | None) -> str | None:
    """Return SHA256 hex of ``value`` or ``None`` if empty/None.

    Used by the auth route to convert raw client IPs and user-agent strings
    into one-way digests before persistence in ``login_audit_logs``. Storing
    the raw values would constitute PII retention with no operational benefit
    -- a hash supports correlation across events without persisting the
    underlying string.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def validate_auth_settings(settings: Settings | None = None) -> None:
    """Raise ``MissingSecretError`` when AUTH_ENABLED=true but JWT_SECRET unset.

    Called from FastAPI startup (``create_app``) so misconfiguration fails
    immediately rather than at the first login attempt.
    """
    s = settings or get_settings()
    if s.auth_enabled and not s.jwt_secret:
        raise MissingSecretError(
            "AUTH_ENABLED=true but JWT_SECRET is empty. Set JWT_SECRET in the "
            "environment (e.g. via .env) before starting the application."
        )


# ---------------------------------------------------------------------------
# AuthService -- orchestrates hasher + issuer + repositories
# ---------------------------------------------------------------------------


@dataclass
class LoginResult:
    user: User
    token: str
    issued_at: datetime
    expires_at: datetime


class AuthService:
    """Orchestrates the LOGIN_SUCCESS / LOGIN_FAILED audit flow.

    Created per-request so that the underlying SQLAlchemy ``Session`` stays
    scoped to the request lifecycle.
    """

    def __init__(
        self,
        *,
        users: UserRepository,
        audit_logs: LoginAuditLogRepository,
        hasher: PasswordHasher,
        issuer: JwtIssuer,
    ) -> None:
        self.users = users
        self.audit_logs = audit_logs
        self.hasher = hasher
        self.issuer = issuer

    def login(
        self,
        *,
        username: str,
        password: str,
        source_ip: str | None,
        user_agent: str | None,
    ) -> LoginResult | None:
        """Return ``LoginResult`` on success, ``None`` on any failure.

        On failure the route layer must return a generic error -- this method
        intentionally collapses "unknown user", "wrong password", and
        "deactivated account" into a single ``None`` return so the response
        does not reveal which case occurred.
        """
        ip_hash = hash_for_audit(source_ip)
        ua_hash = hash_for_audit(user_agent)
        user = self.users.get_by_username(username)

        if user is None or not user.is_active:
            self.audit_logs.create(
                event_type=EVENT_LOGIN_FAILED,
                username=username,
                user_id=user.id if user is not None else None,
                source_ip_hash=ip_hash,
                user_agent_hash=ua_hash,
            )
            return None

        if not self.hasher.verify_password(password, user.password_hash):
            self.audit_logs.create(
                event_type=EVENT_LOGIN_FAILED,
                username=username,
                user_id=user.id,
                source_ip_hash=ip_hash,
                user_agent_hash=ua_hash,
            )
            return None

        token, issued_at, expires_at = self.issuer.issue(
            user_id=user.id, username=user.username
        )
        self.users.set_last_login(user)
        self.audit_logs.create(
            event_type=EVENT_LOGIN_SUCCESS,
            username=user.username,
            user_id=user.id,
            source_ip_hash=ip_hash,
            user_agent_hash=ua_hash,
        )
        return LoginResult(
            user=user, token=token, issued_at=issued_at, expires_at=expires_at
        )

    def record_logout(
        self,
        *,
        user: AuthenticatedUser,
        source_ip: str | None,
        user_agent: str | None,
    ) -> None:
        """Append a LOGOUT audit row. JWTs are stateless -- no revocation.

        For ``via == "auth_disabled_fallback"`` the row is still written with
        ``username = None`` so operators can still see logout requests during
        ``AUTH_ENABLED=false`` development sessions.
        """
        self.audit_logs.create(
            event_type=EVENT_LOGOUT,
            username=user.username,
            user_id=user.user_id,
            source_ip_hash=hash_for_audit(source_ip),
            user_agent_hash=hash_for_audit(user_agent),
        )
