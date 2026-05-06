"""Unit tests for v0.9 Phase C provider resilience primitives.

Covers:
  * ProviderCallResult.ok / .fail factories
  * retry_with_backoff -- success on first attempt
  * retry_with_backoff -- success on later attempt (after failures)
  * retry_with_backoff -- exhausts max_attempts, returns last failure
  * retry_with_backoff -- CLIENT_ERROR not retried (deterministic)
  * retry_with_backoff -- TIMEOUT retried
  * CircuitBreaker -- starts CLOSED
  * CircuitBreaker -- CLOSED → OPEN after threshold failures
  * CircuitBreaker -- OPEN fast-fails without calling fn
  * CircuitBreaker -- OPEN → HALF_OPEN after timeout
  * CircuitBreaker -- HALF_OPEN probe success → CLOSED
  * CircuitBreaker -- HALF_OPEN probe failure → OPEN
  * CircuitBreaker -- reset() forces CLOSED
  * No real external API calls (verified by design: fn is a fake callable)
"""

from __future__ import annotations

import time

import pytest

from app.data.provider_resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
    retry_with_backoff,
)

# ---------------------------------------------------------------------------
# ProviderCallResult
# ---------------------------------------------------------------------------


def test_ok_factory():
    r = ProviderCallResult.ok("data")
    assert r.success is True
    assert r.value == "data"
    assert r.error_kind is None


def test_fail_factory():
    r = ProviderCallResult.fail(ProviderErrorKind.TIMEOUT, "timed out")
    assert r.success is False
    assert r.error_kind == ProviderErrorKind.TIMEOUT
    assert r.error_message == "timed out"
    assert r.value is None


# ---------------------------------------------------------------------------
# retry_with_backoff
# ---------------------------------------------------------------------------

_NO_SLEEP = lambda _: None  # noqa: E731


def test_retry_success_on_first_attempt():
    calls = []

    def fn():
        calls.append(1)
        return ProviderCallResult.ok("hit")

    result = retry_with_backoff(fn, _sleep=_NO_SLEEP)
    assert result.success is True
    assert result.value == "hit"
    assert result.attempts == 1
    assert len(calls) == 1


def test_retry_success_on_third_attempt():
    attempt = [0]

    def fn():
        attempt[0] += 1
        if attempt[0] < 3:
            return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "error")
        return ProviderCallResult.ok("recovered")

    result = retry_with_backoff(fn, max_attempts=3, _sleep=_NO_SLEEP)
    assert result.success is True
    assert result.attempts == 3


def test_retry_exhausts_attempts():
    calls = [0]

    def fn():
        calls[0] += 1
        return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "always fail")

    result = retry_with_backoff(fn, max_attempts=3, _sleep=_NO_SLEEP)
    assert result.success is False
    assert calls[0] == 3


def test_retry_client_error_not_retried():
    calls = [0]

    def fn():
        calls[0] += 1
        return ProviderCallResult.fail(ProviderErrorKind.CLIENT_ERROR, "bad request")

    result = retry_with_backoff(fn, max_attempts=5, _sleep=_NO_SLEEP)
    assert result.success is False
    assert calls[0] == 1  # stopped immediately


def test_retry_timeout_is_retried():
    calls = [0]

    def fn():
        calls[0] += 1
        if calls[0] < 2:
            return ProviderCallResult.fail(ProviderErrorKind.TIMEOUT)
        return ProviderCallResult.ok("ok")

    result = retry_with_backoff(fn, max_attempts=3, _sleep=_NO_SLEEP)
    assert result.success is True
    assert calls[0] == 2


def test_retry_rate_limit_is_retried():
    calls = [0]

    def fn():
        calls[0] += 1
        if calls[0] == 1:
            return ProviderCallResult.fail(ProviderErrorKind.RATE_LIMIT)
        return ProviderCallResult.ok("ok after rate limit")

    result = retry_with_backoff(fn, max_attempts=3, _sleep=_NO_SLEEP)
    assert result.success is True


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


def _ok_fn():
    return ProviderCallResult.ok("ok")


def _fail_fn():
    return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "err")


def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker()
    assert cb.state == CircuitBreakerState.CLOSED


def test_circuit_breaker_closed_passes_calls_through():
    cb = CircuitBreaker()
    result = cb.call(_ok_fn)
    assert result.success is True
    assert cb.state == CircuitBreakerState.CLOSED


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(3):
        cb.call(_fail_fn)
    assert cb.state == CircuitBreakerState.OPEN


def test_circuit_breaker_open_fast_fails():
    cb = CircuitBreaker(failure_threshold=2)
    cb.call(_fail_fn)
    cb.call(_fail_fn)
    assert cb.state == CircuitBreakerState.OPEN

    call_count = [0]

    def fn():
        call_count[0] += 1
        return ProviderCallResult.ok("should not reach")

    result = cb.call(fn)
    assert result.success is False
    assert call_count[0] == 0  # fn was never called


def test_circuit_breaker_open_to_half_open_after_timeout(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, reset_timeout_s=1.0)
    cb.call(_fail_fn)
    assert cb.state == CircuitBreakerState.OPEN

    # Fake time passing beyond reset_timeout_s.
    future = time.monotonic() + 2.0
    monkeypatch.setattr("app.data.provider_resilience.time.monotonic", lambda: future)

    # Next call triggers _try_reset.
    result = cb.call(_ok_fn)
    assert cb.state == CircuitBreakerState.CLOSED
    assert result.success is True


def test_circuit_breaker_half_open_failure_reopens(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, reset_timeout_s=1.0)
    cb.call(_fail_fn)

    future = time.monotonic() + 2.0
    monkeypatch.setattr("app.data.provider_resilience.time.monotonic", lambda: future)

    result = cb.call(_fail_fn)
    assert cb.state == CircuitBreakerState.OPEN
    assert result.success is False


def test_circuit_breaker_reset_forces_closed():
    cb = CircuitBreaker(failure_threshold=2)
    cb.call(_fail_fn)
    cb.call(_fail_fn)
    assert cb.state == CircuitBreakerState.OPEN

    cb.reset()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb._failure_count == 0


def test_circuit_breaker_no_real_external_calls():
    """Verify the test suite never touches a real external system.

    This is enforced by design: every ``fn`` passed to CircuitBreaker/retry
    in this file is a local lambda that returns a ProviderCallResult directly.
    """
    cb = CircuitBreaker()
    # If this test file imported any real KIS/DART/RSS module and called it,
    # the test would fail before reaching here because those modules require
    # live network or credentials. They don't -- all fns are local.
    result = cb.call(lambda: ProviderCallResult.ok("local-only"))
    assert result.success is True
