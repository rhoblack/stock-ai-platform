"""Unit tests for v0.8 Phase B auth primitives.

Scope:
  * PasswordHasher (scrypt) -- hash format, verify success/fail, malformed
    input is rejected without raising, never echoes plaintext.
  * JwtIssuer -- create/decode round trip, expiry, invalid signature, missing
    secret error path.
  * hash_for_audit -- SHA256 hex, empty/None handling.
  * validate_auth_settings -- AUTH_ENABLED=true requires JWT_SECRET.

No DB / FastAPI / network involvement.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.auth.security import (
    ExpiredTokenError,
    InvalidTokenError,
    JwtIssuer,
    MissingSecretError,
    PasswordHasher,
    SCRYPT_PREFIX,
    hash_for_audit,
    validate_auth_settings,
)
from app.config.settings import Settings


# Cheap scrypt cost for fast unit tests.
_FAST = {"n": 1024, "r": 8, "p": 1}


# ---------- PasswordHasher ----------


def test_hash_password_returns_scrypt_formatted_string() -> None:
    h = PasswordHasher(**_FAST).hash_password("hunter2")
    parts = h.split("$")
    assert parts[0] == SCRYPT_PREFIX
    assert parts[1] == "1024"
    assert parts[2] == "8"
    assert parts[3] == "1"
    assert len(parts) == 6  # prefix + n + r + p + salt + derived
    assert "hunter2" not in h  # plaintext never embedded


def test_hash_password_is_salted_so_repeated_calls_differ() -> None:
    hasher = PasswordHasher(**_FAST)
    a = hasher.hash_password("same-password")
    b = hasher.hash_password("same-password")
    assert a != b, "salt should make repeated hashes diverge"


def test_verify_password_success() -> None:
    hasher = PasswordHasher(**_FAST)
    h = hasher.hash_password("correct-horse-battery-staple")
    assert hasher.verify_password("correct-horse-battery-staple", h) is True


def test_verify_password_wrong_password() -> None:
    hasher = PasswordHasher(**_FAST)
    h = hasher.hash_password("hunter2")
    assert hasher.verify_password("wrong", h) is False


def test_verify_password_handles_empty_stored_hash() -> None:
    assert PasswordHasher(**_FAST).verify_password("anything", "") is False


@pytest.mark.parametrize(
    "malformed",
    [
        "not-a-hash",
        "scrypt$only$two",
        "argon2$1$8$1$abc$def",  # wrong prefix
        "scrypt$abc$8$1$abc$def",  # non-int n
        "scrypt$1024$8$1$!!!$###",  # invalid base64
    ],
)
def test_verify_password_malformed_hash_returns_false(malformed: str) -> None:
    assert PasswordHasher(**_FAST).verify_password("anything", malformed) is False


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError):
        PasswordHasher(**_FAST).hash_password("")


# ---------- JwtIssuer ----------


def test_jwt_issue_and_decode_round_trip() -> None:
    issuer = JwtIssuer(secret="x" * 32, algorithm="HS256", expires_minutes=5)
    token, issued, expires = issuer.issue(user_id=42, username="alice")
    decoded = issuer.decode(token)
    assert decoded.user_id == 42
    assert decoded.username == "alice"
    # Allow a +/- 1s drift between epoch-second rounding and the dataclass.
    assert abs((decoded.issued_at - issued).total_seconds()) < 2
    assert abs((decoded.expires_at - expires).total_seconds()) < 2


def test_jwt_decode_rejects_invalid_signature() -> None:
    issuer = JwtIssuer(secret="x" * 32, algorithm="HS256", expires_minutes=5)
    token, _, _ = issuer.issue(user_id=1, username="alice")
    other = JwtIssuer(secret="y" * 32, algorithm="HS256", expires_minutes=5)
    with pytest.raises(InvalidTokenError):
        other.decode(token)


def test_jwt_decode_rejects_expired_token() -> None:
    issuer = JwtIssuer(secret="x" * 32, algorithm="HS256", expires_minutes=1)
    # Forge an already-expired token.
    import jwt as pyjwt

    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    payload = {
        "sub": "1",
        "username": "alice",
        "iat": int(past.timestamp()),
        "exp": int((past + timedelta(seconds=30)).timestamp()),
    }
    token = pyjwt.encode(payload, "x" * 32, algorithm="HS256")
    with pytest.raises(ExpiredTokenError):
        issuer.decode(token)


def test_jwt_decode_rejects_garbage_token() -> None:
    issuer = JwtIssuer(secret="x" * 32, algorithm="HS256", expires_minutes=5)
    with pytest.raises(InvalidTokenError):
        issuer.decode("not.a.jwt")


def test_jwt_issuer_without_secret_raises_on_use() -> None:
    issuer = JwtIssuer(secret=None, algorithm="HS256", expires_minutes=5)
    with pytest.raises(MissingSecretError):
        issuer.issue(user_id=1, username="alice")
    with pytest.raises(MissingSecretError):
        issuer.decode("anything")


# ---------- hash_for_audit ----------


def test_hash_for_audit_produces_sha256_hex() -> None:
    out = hash_for_audit("203.0.113.7")
    assert isinstance(out, str)
    assert len(out) == 64  # sha256 hex digest length
    assert all(c in "0123456789abcdef" for c in out)


def test_hash_for_audit_is_deterministic() -> None:
    assert hash_for_audit("user-agent-string") == hash_for_audit("user-agent-string")


def test_hash_for_audit_differs_per_input() -> None:
    assert hash_for_audit("a") != hash_for_audit("b")


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_hash_for_audit_returns_none_for_empty_input(empty) -> None:
    assert hash_for_audit(empty) is None


# ---------- validate_auth_settings ----------


def _settings_with(**overrides) -> Settings:
    base = dict(
        auth_enabled=False,
        jwt_secret=None,
        jwt_algorithm="HS256",
        jwt_expires_minutes=1440,
        password_hash_n=1024,
        password_hash_r=8,
        password_hash_p=1,
    )
    base.update(overrides)
    return Settings(**base)


def test_validate_auth_settings_passes_when_disabled() -> None:
    validate_auth_settings(_settings_with(auth_enabled=False, jwt_secret=None))


def test_validate_auth_settings_passes_when_enabled_with_secret() -> None:
    validate_auth_settings(
        _settings_with(auth_enabled=True, jwt_secret="x" * 32),
    )


def test_validate_auth_settings_raises_when_enabled_without_secret() -> None:
    with pytest.raises(MissingSecretError):
        validate_auth_settings(
            _settings_with(auth_enabled=True, jwt_secret=None),
        )


def test_validate_auth_settings_raises_when_enabled_with_empty_secret() -> None:
    with pytest.raises(MissingSecretError):
        validate_auth_settings(
            _settings_with(auth_enabled=True, jwt_secret=""),
        )
