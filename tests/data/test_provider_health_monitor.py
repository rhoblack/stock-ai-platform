"""Unit tests for v0.10 Phase A ProviderHealthMonitor and call_with_resilience.

Covers:
  * ProviderStats.to_dict structure and field types
  * ProviderHealthMonitor.register (fresh + idempotent)
  * ProviderHealthMonitor.get_status (registered + unregistered)
  * ProviderHealthMonitor.get_all_status (empty + populated)
  * ProviderHealthMonitor.record_result -- success and failure field updates
  * ProviderHealthMonitor.last_called_at set after record
  * ProviderHealthMonitor.reset -- counters and circuit breaker cleared
  * ProviderHealthMonitor.reset_all
  * CircuitBreaker state reflected in get_status after threshold failures
  * call_with_resilience -- success path, result recorded in monitor
  * call_with_resilience -- retry on SERVER_ERROR then success
  * call_with_resilience -- CLIENT_ERROR not retried
  * call_with_resilience -- exception in fn isolated to ProviderCallResult.fail
  * call_with_resilience -- never raises even on repeated exceptions
  * call_with_resilience -- circuit breaker OPEN triggers fast-fail
  * call_with_resilience -- unregistered provider still returns result (no crash)
  * call_with_resilience -- request_id appears in WARNING log
  * get_health_monitor returns the global singleton (same object)
  * Settings: provider_resilience_enabled defaults False
  * Settings: provider_default_timeout_s defaults 10.0
  * Settings: provider_default_max_attempts defaults 3
  * Settings: provider_default_base_delay_s defaults 0.5
  * Settings: provider_default_max_delay_s defaults 10.0
  * Settings: circuit breaker defaults (threshold 5, timeout 60s)
  * Stub provider wrapped with call_with_resilience -- job isolation demo
"""

from __future__ import annotations

import time

import pytest

from app.data.provider_health_monitor import (
    ProviderHealthMonitor,
    ProviderStats,
    call_with_resilience,
    get_health_monitor,
)
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)

_NO_SLEEP: object = lambda _: None  # noqa: E731  injected into call_with_resilience

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok() -> ProviderCallResult:
    return ProviderCallResult.ok("data")


def _fail_server() -> ProviderCallResult:
    return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "oops")


def _fail_client() -> ProviderCallResult:
    return ProviderCallResult.fail(ProviderErrorKind.CLIENT_ERROR, "bad req")


def _raise() -> ProviderCallResult:
    raise RuntimeError("kaboom")


def _fresh() -> ProviderHealthMonitor:
    """Return a fresh isolated monitor for each test."""
    return ProviderHealthMonitor()


# ---------------------------------------------------------------------------
# ProviderStats.to_dict
# ---------------------------------------------------------------------------


def test_to_dict_success_fields():
    monitor = _fresh()
    monitor.register("kis")
    monitor.record_result("kis", ProviderCallResult.ok("x"))
    d = monitor.get_status("kis")
    assert d is not None
    assert d["name"] == "kis"
    assert d["status"] == "CLOSED"
    assert d["call_count"] == 1
    assert d["success_count"] == 1
    assert d["failure_count"] == 0
    assert d["last_error_kind"] is None
    assert d["last_error_message"] is None
    assert d["last_called_at"] is not None  # ISO-8601 string


def test_to_dict_failure_fields():
    monitor = _fresh()
    monitor.register("dart")
    monitor.record_result(
        "dart", ProviderCallResult.fail(ProviderErrorKind.TIMEOUT, "timed out")
    )
    d = monitor.get_status("dart")
    assert d["failure_count"] == 1
    assert d["last_error_kind"] == "TIMEOUT"
    assert d["last_error_message"] == "timed out"


# ---------------------------------------------------------------------------
# ProviderHealthMonitor.register
# ---------------------------------------------------------------------------


def test_register_fresh():
    monitor = _fresh()
    stats = monitor.register("kis")
    assert stats.name == "kis"
    assert stats.call_count == 0
    assert stats.status == CircuitBreakerState.CLOSED


def test_register_idempotent():
    monitor = _fresh()
    s1 = monitor.register("kis")
    s1.call_count = 99  # mutate
    s2 = monitor.register("kis")  # should return same object
    assert s2 is s1
    assert s2.call_count == 99


# ---------------------------------------------------------------------------
# ProviderHealthMonitor.get_status
# ---------------------------------------------------------------------------


def test_get_status_unregistered_returns_none():
    monitor = _fresh()
    assert monitor.get_status("nonexistent") is None


def test_get_status_registered_returns_dict():
    monitor = _fresh()
    monitor.register("rss")
    d = monitor.get_status("rss")
    assert isinstance(d, dict)
    assert d["name"] == "rss"


# ---------------------------------------------------------------------------
# ProviderHealthMonitor.get_all_status
# ---------------------------------------------------------------------------


def test_get_all_status_empty():
    monitor = _fresh()
    assert monitor.get_all_status() == []


def test_get_all_status_multiple():
    monitor = _fresh()
    monitor.register("kis")
    monitor.register("dart")
    monitor.register("rss")
    all_status = monitor.get_all_status()
    assert len(all_status) == 3
    names = {d["name"] for d in all_status}
    assert names == {"kis", "dart", "rss"}


# ---------------------------------------------------------------------------
# ProviderHealthMonitor.record_result
# ---------------------------------------------------------------------------


def test_record_result_success_increments_success_count():
    monitor = _fresh()
    monitor.register("kis")
    monitor.record_result("kis", ProviderCallResult.ok("v"))
    monitor.record_result("kis", ProviderCallResult.ok("v"))
    d = monitor.get_status("kis")
    assert d["call_count"] == 2
    assert d["success_count"] == 2
    assert d["failure_count"] == 0


def test_record_result_failure_increments_failure_count():
    monitor = _fresh()
    monitor.register("kis")
    monitor.record_result("kis", ProviderCallResult.fail(ProviderErrorKind.TIMEOUT))
    d = monitor.get_status("kis")
    assert d["call_count"] == 1
    assert d["failure_count"] == 1
    assert d["success_count"] == 0


def test_record_result_last_called_at_is_set():
    monitor = _fresh()
    monitor.register("kis")
    before = time.time()
    monitor.record_result("kis", ProviderCallResult.ok("x"))
    d = monitor.get_status("kis")
    assert d["last_called_at"] is not None


def test_record_result_unregistered_is_silently_ignored():
    monitor = _fresh()
    monitor.record_result("ghost", ProviderCallResult.ok("x"))  # must not raise


# ---------------------------------------------------------------------------
# ProviderHealthMonitor.reset
# ---------------------------------------------------------------------------


def test_reset_clears_counters_and_circuit_breaker():
    monitor = _fresh()
    monitor.register("kis", failure_threshold=1)
    monitor.record_result("kis", ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR))
    # Manually trip via circuit breaker
    stats = monitor._providers["kis"]
    stats.circuit_breaker._failure_count = 1
    stats.circuit_breaker._state = CircuitBreakerState.OPEN

    monitor.reset("kis")
    d = monitor.get_status("kis")
    assert d["call_count"] == 0
    assert d["failure_count"] == 0
    assert d["success_count"] == 0
    assert d["last_error_kind"] is None
    assert d["status"] == "CLOSED"


def test_reset_all_clears_multiple_providers():
    monitor = _fresh()
    monitor.register("kis")
    monitor.register("dart")
    monitor.record_result("kis", ProviderCallResult.ok("x"))
    monitor.record_result("dart", ProviderCallResult.fail(ProviderErrorKind.TIMEOUT))

    monitor.reset_all()
    for name in ("kis", "dart"):
        d = monitor.get_status(name)
        assert d["call_count"] == 0


# ---------------------------------------------------------------------------
# CircuitBreaker state reflected in get_status
# ---------------------------------------------------------------------------


def test_circuit_breaker_open_reflected_in_status():
    monitor = _fresh()
    monitor.register("kis", failure_threshold=2)
    stats = monitor._providers["kis"]

    # Trip the circuit breaker by calling fail twice through it
    stats.circuit_breaker.call(_fail_server)
    stats.circuit_breaker.call(_fail_server)

    d = monitor.get_status("kis")
    assert d["status"] == "OPEN"


# ---------------------------------------------------------------------------
# call_with_resilience -- success path
# ---------------------------------------------------------------------------


def test_call_with_resilience_success():
    monitor = _fresh()
    monitor.register("kis")
    result = call_with_resilience("kis", _ok, monitor=monitor, _sleep=_NO_SLEEP)
    assert result.success is True
    assert result.value == "data"
    assert monitor.get_status("kis")["success_count"] == 1


def test_call_with_resilience_records_in_monitor():
    monitor = _fresh()
    monitor.register("dart")
    call_with_resilience("dart", _ok, monitor=monitor, _sleep=_NO_SLEEP)
    d = monitor.get_status("dart")
    assert d["call_count"] == 1
    assert d["success_count"] == 1


# ---------------------------------------------------------------------------
# call_with_resilience -- retry behaviour
# ---------------------------------------------------------------------------


def test_call_with_resilience_retries_server_error_then_succeeds():
    monitor = _fresh()
    monitor.register("kis")
    attempt = [0]

    def fn() -> ProviderCallResult:
        attempt[0] += 1
        if attempt[0] < 3:
            return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "temp")
        return ProviderCallResult.ok("recovered")

    result = call_with_resilience(
        "kis", fn, monitor=monitor, max_attempts=3, _sleep=_NO_SLEEP
    )
    assert result.success is True
    assert attempt[0] == 3


def test_call_with_resilience_client_error_not_retried():
    monitor = _fresh()
    monitor.register("kis")
    calls = [0]

    def fn() -> ProviderCallResult:
        calls[0] += 1
        return _fail_client()

    result = call_with_resilience(
        "kis", fn, monitor=monitor, max_attempts=5, _sleep=_NO_SLEEP
    )
    assert result.success is False
    assert calls[0] == 1  # stopped immediately


# ---------------------------------------------------------------------------
# call_with_resilience -- failure isolation
# ---------------------------------------------------------------------------


def test_call_with_resilience_exception_is_isolated():
    monitor = _fresh()
    monitor.register("kis")
    result = call_with_resilience("kis", _raise, monitor=monitor, _sleep=_NO_SLEEP)
    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN
    assert "kaboom" in (result.error_message or "")


def test_call_with_resilience_never_raises():
    monitor = _fresh()
    monitor.register("kis")
    # Even with max_attempts=5 of raises, must not propagate
    result = call_with_resilience(
        "kis", _raise, monitor=monitor, max_attempts=5, _sleep=_NO_SLEEP
    )
    assert result.success is False  # no exception was raised to here


# ---------------------------------------------------------------------------
# call_with_resilience -- circuit breaker open triggers fast-fail
# ---------------------------------------------------------------------------


def test_call_with_resilience_circuit_open_fast_fails():
    monitor = _fresh()
    monitor.register("kis", failure_threshold=2)
    # Trip breaker
    call_with_resilience("kis", _fail_server, monitor=monitor, _sleep=_NO_SLEEP)
    call_with_resilience("kis", _fail_server, monitor=monitor, _sleep=_NO_SLEEP)

    assert monitor.get_status("kis")["status"] == "OPEN"

    called = [0]

    def fn() -> ProviderCallResult:
        called[0] += 1
        return ProviderCallResult.ok("should not reach")

    result = call_with_resilience("kis", fn, monitor=monitor, _sleep=_NO_SLEEP)
    assert result.success is False
    assert called[0] == 0  # fn was never invoked


# ---------------------------------------------------------------------------
# call_with_resilience -- unregistered provider
# ---------------------------------------------------------------------------


def test_call_with_resilience_unregistered_provider_works():
    monitor = _fresh()
    # "anonymous" was never registered -- should still work without crash
    result = call_with_resilience(
        "anonymous", _ok, monitor=monitor, _sleep=_NO_SLEEP
    )
    assert result.success is True
    # Unregistered -- no stats entry created
    assert monitor.get_status("anonymous") is None


# ---------------------------------------------------------------------------
# call_with_resilience -- request_id in log
# ---------------------------------------------------------------------------


def test_call_with_resilience_warning_logged_on_exception(caplog):
    """Verify provider-level WARNING is emitted when fn raises.

    request_id is passed as ``extra=`` to the LogRecord so structured-log
    pipelines (v0.9 RequestIDMiddleware / LOG_FORMAT=json) can correlate
    provider errors back to the originating HTTP request.  Here we confirm
    the warning fires and the provider name appears in the message.
    """
    monitor = _fresh()
    monitor.register("dart")
    import logging

    with caplog.at_level(logging.WARNING, logger="app.data.provider_health_monitor"):
        call_with_resilience(
            "dart",
            _raise,
            monitor=monitor,
            max_attempts=1,
            _sleep=_NO_SLEEP,
            request_id="req-abc-123",
        )
    messages = [r.getMessage() for r in caplog.records]
    assert any("dart" in m for m in messages)
    assert any("kaboom" in m for m in messages)


# ---------------------------------------------------------------------------
# get_health_monitor singleton
# ---------------------------------------------------------------------------


def test_get_health_monitor_returns_same_object():
    m1 = get_health_monitor()
    m2 = get_health_monitor()
    assert m1 is m2


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


def test_settings_provider_resilience_enabled_default_false():
    from app.config.settings import Settings

    s = Settings()
    assert s.provider_resilience_enabled is False


def test_settings_provider_default_timeout():
    from app.config.settings import Settings

    s = Settings()
    assert s.provider_default_timeout_s == 10.0


def test_settings_provider_default_max_attempts():
    from app.config.settings import Settings

    s = Settings()
    assert s.provider_default_max_attempts == 3


def test_settings_provider_default_delays():
    from app.config.settings import Settings

    s = Settings()
    assert s.provider_default_base_delay_s == 0.5
    assert s.provider_default_max_delay_s == 10.0


def test_settings_circuit_breaker_defaults():
    from app.config.settings import Settings

    s = Settings()
    assert s.provider_circuit_breaker_failure_threshold == 5
    assert s.provider_circuit_breaker_reset_timeout_s == 60.0


# ---------------------------------------------------------------------------
# Stub provider wrapped with call_with_resilience -- job isolation demo
# ---------------------------------------------------------------------------


def test_stub_provider_job_isolation():
    """Simulate a scheduler job calling a stub provider.

    The stub fails on the first call.  The job should receive a
    ProviderCallResult.fail and continue -- not crash.
    """
    monitor = _fresh()
    monitor.register("stub", failure_threshold=10)

    job_errors: list[str] = []

    def run_job() -> str:
        result = call_with_resilience(
            "stub",
            lambda: ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "stub down"),
            monitor=monitor,
            max_attempts=1,
            _sleep=_NO_SLEEP,
        )
        if not result.success:
            job_errors.append(result.error_message or "")
            return "SKIPPED"
        return "OK"

    outcome = run_job()
    assert outcome == "SKIPPED"
    assert "stub down" in job_errors[0]
    # Job did not raise -- isolation confirmed
    d = monitor.get_status("stub")
    assert d["failure_count"] == 1
    assert d["status"] == "CLOSED"  # one failure, threshold=10
