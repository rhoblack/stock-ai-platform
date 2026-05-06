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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

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
        """
        stats = self._providers.get(name)
        if stats is None:
            return
        stats.call_count += 1
        stats.last_called_at = datetime.now(tz=timezone.utc)
        if result.success:
            stats.success_count += 1
            stats.last_error_kind = None
            stats.last_error_message = None
        else:
            stats.failure_count += 1
            stats.last_error_kind = result.error_kind
            stats.last_error_message = result.error_message

    def get_status(self, name: str) -> dict[str, Any] | None:
        """Return serialised status dict for ``name``, or ``None`` if not registered."""
        stats = self._providers.get(name)
        return stats.to_dict() if stats else None

    def get_all_status(self) -> list[dict[str, Any]]:
        """Return serialised status dicts for all registered providers."""
        return [s.to_dict() for s in self._providers.values()]

    def reset(self, name: str) -> None:
        """Reset circuit breaker and all counters for a single provider."""
        stats = self._providers.get(name)
        if stats is not None:
            stats.circuit_breaker.reset()
            stats.call_count = 0
            stats.success_count = 0
            stats.failure_count = 0
            stats.last_error_kind = None
            stats.last_error_message = None
            stats.last_called_at = None

    def reset_all(self) -> None:
        """Reset all registered providers."""
        for name in list(self._providers):
            self.reset(name)


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
