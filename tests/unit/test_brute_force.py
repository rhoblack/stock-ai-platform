"""Unit tests for v0.9 Phase A BruteForceGuard.

Pure in-memory unit tests -- no DB, no FastAPI, no network.
Tests the guard's failure counting, window reset, lockout, and success reset.
"""

from __future__ import annotations

import time

import pytest

from app.auth.brute_force import BruteForceGuard, BruteForceLockedError


def _guard(max_failures: int = 3, window: int = 60, lockout: int = 300) -> BruteForceGuard:
    return BruteForceGuard(
        max_failures=max_failures,
        window_seconds=window,
        lockout_seconds=lockout,
    )


_IP_HASH = "a" * 64  # dummy 64-char SHA256 hex string
_USER = "alice"


# ---------- check_allowed before any failure ----------


def test_check_allowed_passes_with_no_failures():
    g = _guard()
    g.check_allowed(_USER, _IP_HASH)  # must not raise


def test_check_allowed_passes_below_max_failures():
    g = _guard(max_failures=3)
    g.record_failure(_USER, _IP_HASH)
    g.record_failure(_USER, _IP_HASH)
    g.check_allowed(_USER, _IP_HASH)  # 2 failures, threshold is 3 -- still allowed


# ---------- lockout after max_failures ----------


def test_lockout_after_max_failures():
    g = _guard(max_failures=3)
    for _ in range(3):
        g.record_failure(_USER, _IP_HASH)
    with pytest.raises(BruteForceLockedError):
        g.check_allowed(_USER, _IP_HASH)


def test_is_locked_true_after_lockout():
    g = _guard(max_failures=2)
    g.record_failure(_USER, _IP_HASH)
    g.record_failure(_USER, _IP_HASH)
    assert g.is_locked(_USER, _IP_HASH) is True


def test_is_locked_false_before_lockout():
    g = _guard(max_failures=5)
    g.record_failure(_USER, _IP_HASH)
    assert g.is_locked(_USER, _IP_HASH) is False


# ---------- success resets counter ----------


def test_record_success_clears_failure_count():
    g = _guard(max_failures=3)
    g.record_failure(_USER, _IP_HASH)
    g.record_failure(_USER, _IP_HASH)
    g.record_success(_USER, _IP_HASH)
    # After success reset, 2 more failures should not lock (threshold is 3).
    g.record_failure(_USER, _IP_HASH)
    g.record_failure(_USER, _IP_HASH)
    g.check_allowed(_USER, _IP_HASH)  # must not raise


# ---------- composite key isolation ----------


def test_different_ip_same_user_independent():
    g = _guard(max_failures=2)
    ip_a = "a" * 64
    ip_b = "b" * 64
    g.record_failure(_USER, ip_a)
    g.record_failure(_USER, ip_a)
    # ip_a is locked, ip_b is not
    with pytest.raises(BruteForceLockedError):
        g.check_allowed(_USER, ip_a)
    g.check_allowed(_USER, ip_b)  # must not raise


def test_different_user_same_ip_independent():
    g = _guard(max_failures=2)
    g.record_failure("alice", _IP_HASH)
    g.record_failure("alice", _IP_HASH)
    with pytest.raises(BruteForceLockedError):
        g.check_allowed("alice", _IP_HASH)
    g.check_allowed("bob", _IP_HASH)  # must not raise


# ---------- reset() clears all records ----------


def test_reset_clears_all_locked_keys():
    g = _guard(max_failures=2)
    g.record_failure(_USER, _IP_HASH)
    g.record_failure(_USER, _IP_HASH)
    g.reset()
    g.check_allowed(_USER, _IP_HASH)  # must not raise after reset


# ---------- None IP is handled gracefully ----------


def test_none_ip_hash_is_accepted():
    g = _guard(max_failures=2)
    g.record_failure(_USER, None)
    g.record_failure(_USER, None)
    with pytest.raises(BruteForceLockedError):
        g.check_allowed(_USER, None)
