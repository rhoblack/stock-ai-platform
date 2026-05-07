"""v0.10 Phase A -- ProviderHealthMonitor: per-provider in-memory health tracking.

PURPOSE
-------
Tracks circuit-breaker state, call counts, and last error for every registered
provider name ("kis", "dart", "rss", ...).  The global singleton is exposed by
GET /api/health/providers in Phase D.

FAILURE ISOLATION
-----------------
``call_with_resilience`` NEVER raises.  If the underlying callable raises an
exception, it is caught and converted to
``ProviderCallResult.fail(ProviderErrorKind.UNKNOWN)``.  The caller always
receives a ``ProviderCallResult`` and decides whether to propagate.

LOGGING
-------
Every call logs ``provider`` + optional ``request_id`` so structured-log
pipelines can correlate provider errors back to an HTTP request
(v0.9 RequestIDMiddleware).

DESIGN NOTES
------------
* Not persistent -- state resets on server restart.
* Not thread-safe by default; external locking is required for truly concurrent
  use.  Single-threaded scheduler jobs do not need it.
* ``_default_monitor`` is a module-level singleton; tests should pass their own
  ``ProviderHealthMonitor()`` instance via the ``monitor=`` parameter.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Deque

from app.data.provider_resilience import (
    CircuitBreaker,
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
    retry_with_backoff,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-provider stats
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# v0.11 Phase C -- bounded ring buffers + 24h summary
# ---------------------------------------------------------------------------

# Per-provider ring buffer caps.  Both bounded so memory per provider is
# strictly ``CALL_HISTORY_MAXLEN * sizeof(CallRecord)`` ≈ a few KB.
CALL_HISTORY_MAXLEN = 200
FAILURE_HISTORY_MAXLEN = 50


@dataclass(frozen=True)
class CallRecord:
    """One entry in the per-provider call history ring buffer.

    Memory-conscious by design: only enum + ints + a single timestamp.
    Never carries ``error_message`` -- that field can hold transport
    detail (URL with query secret) and we never want it propagated
    through observability.
    """

    timestamp: datetime
    success: bool
    error_kind: ProviderErrorKind | None
    attempts: int


@dataclass(frozen=True)
class FailureRecord:
    """One entry in the per-provider failure-only ring buffer.

    Mirrors :class:`CallRecord` minus ``success`` (always False).  Same
    secret-discipline guarantee: no message text.
    """

    timestamp: datetime
    error_kind: ProviderErrorKind
    attempts: int


@dataclass
class Summary24h:
    """Snapshot of last-24-hours aggregates for a provider.

    All fields are nullable when ``call_count_24h == 0`` so the
    presentation layer can show "—" instead of dividing by zero.
    """

    call_count_24h: int
    success_count_24h: int
    failure_count_24h: int
    success_rate_24h: float | None
    avg_attempts: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_count_24h": self.call_count_24h,
            "success_count_24h": self.success_count_24h,
            "failure_count_24h": self.failure_count_24h,
            "success_rate_24h": self.success_rate_24h,
            "avg_attempts": self.avg_attempts,
        }


@dataclass
class ProviderStats:
    """Mutable per-provider statistics and circuit-breaker state."""

    name: str
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error_kind: ProviderErrorKind | None = None
    last_error_message: str | None = None
    last_called_at: datetime | None = None
    # v0.11 Phase C bounded ring buffers.  ``maxlen`` ensures memory is
    # capped regardless of how long the process runs.
    recent_calls: Deque[CallRecord] = field(
        default_factory=lambda: deque(maxlen=CALL_HISTORY_MAXLEN)
    )
    recent_failures: Deque[FailureRecord] = field(
        default_factory=lambda: deque(maxlen=FAILURE_HISTORY_MAXLEN)
    )

    @property
    def status(self) -> CircuitBreakerState:
        return self.circuit_breaker.state

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error_kind": (
                self.last_error_kind.value if self.last_error_kind else None
            ),
            "last_error_message": self.last_error_message,
            "last_called_at": (
                self.last_called_at.isoformat() if self.last_called_at else None
            ),
        }

    # -- summary helpers ----------------------------------------------------

    def summary_24h(self, *, now: datetime | None = None) -> Summary24h:
        """Compute the rolling 24-hour aggregate from ``recent_calls``.

        Records older than 24 hours are skipped.  ``now`` is injectable
        so tests can pin the wall clock without monkeypatching.

        ``success_rate_24h`` and ``avg_attempts`` are ``None`` when the
        window contains zero calls (no UI division-by-zero).
        """
        if now is None:
            now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(hours=24)

        call_count = 0
        success_count = 0
        failure_count = 0
        attempts_sum = 0
        for rec in self.recent_calls:
            if rec.timestamp < cutoff:
                continue
            call_count += 1
            attempts_sum += rec.attempts
            if rec.success:
                success_count += 1
            else:
                failure_count += 1

        success_rate = (
            success_count / call_count if call_count > 0 else None
        )
        avg_attempts = (
            attempts_sum / call_count if call_count > 0 else None
        )
        return Summary24h(
            call_count_24h=call_count,
            success_count_24h=success_count,
            failure_count_24h=failure_count,
            success_rate_24h=success_rate,
            avg_attempts=avg_attempts,
        )


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class ProviderHealthMonitor:
    """In-memory registry of provider health state.

    Each provider is identified by a string ``name`` (e.g. ``"kis"``,
    ``"dart"``, ``"rss"``).  Call :meth:`register` before any
    :func:`call_with_resilience` or :meth:`record_result` usage; it is
    idempotent and returns the existing entry if the provider was already
    registered.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderStats] = {}

    def register(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 60.0,
    ) -> ProviderStats:
        """Register a provider and return its :class:`ProviderStats`.

        Idempotent -- calling ``register`` on an already-registered name
        returns the existing entry without resetting any state.
        """
        if name not in self._providers:
            cb = CircuitBreaker(
                failure_threshold=failure_threshold,
                reset_timeout_s=reset_timeout_s,
                name=name,
            )
            self._providers[name] = ProviderStats(name=name, circuit_breaker=cb)
            logger.debug("provider registered name=%s", name)
        return self._providers[name]

    def record_result(self, name: str, result: ProviderCallResult) -> None:
        """Record the outcome of one provider call into the named stats.

        Silently ignores unregistered names so that callers do not need to
        guard against missing registrations.

        v0.11 Phase C: also appends to the bounded ``recent_calls`` /
        ``recent_failures`` ring buffers.  The records carry only enums
        + ints + a UTC timestamp -- no error_message text -- so the
        observability layer cannot leak transport detail (URL secrets,
        partial response bodies).
        """
        stats = self._providers.get(name)
        if stats is None:
            return
        now = datetime.now(tz=timezone.utc)
        stats.call_count += 1
        stats.last_called_at = now
        attempts = max(int(getattr(result, "attempts", 1) or 1), 1)
        if result.success:
            stats.success_count += 1
            stats.last_error_kind = None
            stats.last_error_message = None
        else:
            stats.failure_count += 1
            stats.last_error_kind = result.error_kind
            stats.last_error_message = result.error_message
            stats.recent_failures.append(
                FailureRecord(
                    timestamp=now,
                    error_kind=result.error_kind or ProviderErrorKind.UNKNOWN,
                    attempts=attempts,
                )
            )
        stats.recent_calls.append(
            CallRecord(
                timestamp=now,
                success=bool(result.success),
                error_kind=result.error_kind if not result.success else None,
                attempts=attempts,
            )
        )
        # v0.11 Phase C optional Prometheus hook.  Lazy import so the
        # monitor module never imports prometheus_client unless the
        # operator opted in (PROMETHEUS_ENABLED=true).  Failures inside
        # the hook are swallowed -- observability must never break a
        # provider call path.
        _emit_prometheus(name, stats, result, attempts)

    def get_status(self, name: str) -> dict[str, Any] | None:
        """Return serialised status dict for ``name``, or ``None`` if not registered."""
        stats = self._providers.get(name)
        return stats.to_dict() if stats else None

    def get_all_status(self) -> list[dict[str, Any]]:
        """Return serialised status dicts for all registered providers."""
        return [s.to_dict() for s in self._providers.values()]

    def reset(self, name: str) -> None:
        """Reset circuit breaker, counters, and ring buffers for one provider."""
        stats = self._providers.get(name)
        if stats is not None:
            stats.circuit_breaker.reset()
            stats.call_count = 0
            stats.success_count = 0
            stats.failure_count = 0
            stats.last_error_kind = None
            stats.last_error_message = None
            stats.last_called_at = None
            stats.recent_calls.clear()
            stats.recent_failures.clear()

    def reset_all(self) -> None:
        """Reset all registered providers."""
        for name in list(self._providers):
            self.reset(name)


# ---------------------------------------------------------------------------
# v0.11 Phase C -- Prometheus side-channel (lazy, optional)
# ---------------------------------------------------------------------------
#
# ``record_result`` calls ``_emit_prometheus`` for every provider call.
# The hook is a no-op unless ``app.monitoring.prometheus`` has been
# imported AND the operator has set PROMETHEUS_ENABLED=true (the
# helper module checks Settings on first use and silently skips
# otherwise).  Any exception inside the hook is swallowed so
# observability cannot break the provider call path.


def _emit_prometheus(
    name: str,
    stats: "ProviderStats",
    result: ProviderCallResult,
    attempts: int,
) -> None:
    """Forward a recorded call to the optional Prometheus collectors."""
    try:
        # Lazy import: keeps this module free of prometheus_client side
        # effects until the operator opts in.  The helper module is
        # responsible for the PROMETHEUS_ENABLED short-circuit.
        from app.monitoring.prometheus import record_call  # noqa: PLC0415

        record_call(name, stats.status, result, attempts)
    except Exception:  # noqa: BLE001 -- never break the provider path
        logger.debug(
            "prometheus emission failed provider=%s",
            name,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Global singleton (exposed to Phase D health API)
# ---------------------------------------------------------------------------

_default_monitor = ProviderHealthMonitor()


def get_health_monitor() -> ProviderHealthMonitor:
    """Return the module-level ``ProviderHealthMonitor`` singleton.

    Tests should NOT use this -- pass a fresh ``ProviderHealthMonitor()``
    instance via the ``monitor=`` parameter of :func:`call_with_resilience`
    to prevent cross-test state pollution.
    """
    return _default_monitor


# ---------------------------------------------------------------------------
# call_with_resilience -- main entry point for provider calls
# ---------------------------------------------------------------------------


def call_with_resilience(
    provider_name: str,
    fn: Callable[[], ProviderCallResult],
    *,
    monitor: ProviderHealthMonitor | None = None,
    max_attempts: int = 3,
    base_delay_s: float = 0.5,
    max_delay_s: float = 10.0,
    _sleep: Callable[[float], None] = time.sleep,
    request_id: str | None = None,
) -> ProviderCallResult:
    """Call ``fn`` through circuit-breaker + retry; record in health monitor.

    FAILURE ISOLATION
    -----------------
    This function **never raises**.  If ``fn`` raises an exception, the
    exception is caught and converted to
    ``ProviderCallResult.fail(ProviderErrorKind.UNKNOWN)``.  The job that
    called this function receives a ``ProviderCallResult`` and can log /
    skip gracefully instead of crashing.

    CIRCUIT BREAKER
    ---------------
    If the named provider has been registered with the monitor, its
    :class:`~app.data.provider_resilience.CircuitBreaker` guards the call.
    When the circuit is OPEN the function fast-fails immediately without
    invoking ``fn``.  Unregistered providers skip the circuit-breaker and
    proceed directly to retry.

    Args:
        provider_name: string key used to look up the provider in the monitor.
        fn: zero-argument callable returning :class:`~app.data.provider_resilience.ProviderCallResult`.
        monitor: override the global monitor (pass a fresh instance in tests).
        max_attempts: forwarded to :func:`~app.data.provider_resilience.retry_with_backoff`.
        base_delay_s: forwarded to :func:`~app.data.provider_resilience.retry_with_backoff`.
        max_delay_s: forwarded to :func:`~app.data.provider_resilience.retry_with_backoff`.
        _sleep: injectable sleep function (use ``lambda _: None`` in tests).
        request_id: optional request-ID for structured-log correlation.
    """
    if monitor is None:
        monitor = get_health_monitor()

    log_extra: dict[str, Any] = {"provider": provider_name}
    if request_id:
        log_extra["request_id"] = request_id

    def _safe_fn() -> ProviderCallResult:
        """Wrap fn; convert any exception to ProviderCallResult.fail."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "provider call raised exception provider=%s error=%r",
                provider_name,
                str(exc),
                extra=log_extra,
            )
            return ProviderCallResult.fail(ProviderErrorKind.UNKNOWN, str(exc))

    def _with_retry() -> ProviderCallResult:
        return retry_with_backoff(
            _safe_fn,
            max_attempts=max_attempts,
            base_delay_s=base_delay_s,
            max_delay_s=max_delay_s,
            _sleep=_sleep,
        )

    stats = monitor._providers.get(provider_name)
    if stats is not None:
        result = stats.circuit_breaker.call(_with_retry)
    else:
        result = _with_retry()

    monitor.record_result(provider_name, result)

    if result.success:
        logger.debug(
            "provider call ok provider=%s attempts=%d",
            provider_name,
            result.attempts,
            extra=log_extra,
        )
    else:
        logger.warning(
            "provider call failed provider=%s kind=%s attempts=%d message=%r",
            provider_name,
            result.error_kind,
            result.attempts,
            result.error_message,
            extra=log_extra,
        )

    return result
