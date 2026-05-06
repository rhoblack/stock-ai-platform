"""v0.9 Phase C -- Provider resilience primitives.

PURPOSE
-------
Provides a thin layer of retry / circuit-breaker machinery that can be
wrapped around any external data-provider call (KIS, DART, RSS, etc.)
without touching the existing provider implementations.

SCOPE
-----
* No real external API calls are made here.
* Existing providers (KIS / DART / RSS) are NOT forcibly wrapped -- callers
  opt in by using :func:`retry_with_backoff` or :class:`CircuitBreaker`.
* ``PROVIDER_RESILIENCE_ENABLED`` feature flag guards accidental activation
  in production before the providers have been hardened (default: OFF).

DESIGN
------
CircuitBreaker states (see Fowler 2014):

  CLOSED  → normal operation; failures are counted.
  OPEN    → fast-fail mode; no calls go through until ``reset_timeout_s``
            has elapsed.
  HALF_OPEN → one probe call is allowed through; success → CLOSED,
              failure → OPEN.

retry_with_backoff retries a callable up to ``max_attempts`` times with
exponential back-off (base * 2^attempt), capped at ``max_delay_s``.
Retries are skipped for CLIENT_ERROR (4xx) -- those are deterministic.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class ProviderErrorKind(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_ERROR = "SERVER_ERROR"
    CLIENT_ERROR = "CLIENT_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class ProviderCallResult:
    """Wraps the outcome of a provider call."""

    success: bool
    value: Any = None
    error_kind: ProviderErrorKind | None = None
    error_message: str | None = None
    attempts: int = 1

    @classmethod
    def ok(cls, value: Any, *, attempts: int = 1) -> "ProviderCallResult":
        return cls(success=True, value=value, attempts=attempts)

    @classmethod
    def fail(
        cls,
        kind: ProviderErrorKind,
        message: str = "",
        *,
        attempts: int = 1,
    ) -> "ProviderCallResult":
        return cls(
            success=False,
            error_kind=kind,
            error_message=message,
            attempts=attempts,
        )


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_NON_RETRYABLE = {ProviderErrorKind.CLIENT_ERROR}


def retry_with_backoff(
    fn: Callable[[], ProviderCallResult],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 0.5,
    max_delay_s: float = 10.0,
    _sleep: Callable[[float], None] = time.sleep,
) -> ProviderCallResult:
    """Call ``fn`` up to ``max_attempts`` times with exponential back-off.

    ``fn`` must return a :class:`ProviderCallResult`.  CLIENT_ERROR results
    are not retried (they are deterministic).

    Args:
        fn: zero-argument callable that performs one provider call.
        max_attempts: total number of attempts (not retries).
        base_delay_s: initial sleep before the second attempt.
        max_delay_s: upper cap on the sleep between attempts.
        _sleep: injectable sleep function (use ``lambda _: None`` in tests).
    """
    last: ProviderCallResult | None = None
    for attempt in range(1, max_attempts + 1):
        result = fn()
        result.attempts = attempt
        if result.success:
            return result
        last = result
        if result.error_kind in _NON_RETRYABLE:
            logger.debug(
                "provider call non-retryable error=%s; stopping after attempt %d",
                result.error_kind,
                attempt,
            )
            break
        if attempt < max_attempts:
            delay = min(base_delay_s * (2 ** (attempt - 1)), max_delay_s)
            logger.debug(
                "provider call failed error=%s attempt=%d/%d; retrying in %.2fs",
                result.error_kind,
                attempt,
                max_attempts,
                delay,
            )
            _sleep(delay)

    assert last is not None
    return last


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    """Simple in-process circuit breaker.

    Not thread-safe by default.  For multi-threaded use, wrap ``call`` with
    an external lock.

    Args:
        failure_threshold: consecutive failures before OPEN.
        reset_timeout_s: seconds before moving OPEN → HALF_OPEN.
        name: human-readable label for log messages.
    """

    failure_threshold: int = 5
    reset_timeout_s: float = 60.0
    name: str = "provider"

    _state: CircuitBreakerState = field(
        default=CircuitBreakerState.CLOSED, init=False, repr=False
    )
    _failure_count: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    def _try_reset(self) -> None:
        """Transition OPEN → HALF_OPEN if the reset timeout has elapsed."""
        if (
            self._state is CircuitBreakerState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.reset_timeout_s
        ):
            self._state = CircuitBreakerState.HALF_OPEN
            logger.info("circuit breaker '%s' → HALF_OPEN", self.name)

    def call(
        self,
        fn: Callable[[], ProviderCallResult],
    ) -> ProviderCallResult:
        """Execute ``fn`` through the circuit breaker.

        OPEN  → immediately returns a fast-fail UNKNOWN result.
        HALF_OPEN → allows one probe call; success → CLOSED, failure → OPEN.
        CLOSED → normal operation; failures increment the counter.
        """
        self._try_reset()

        if self._state is CircuitBreakerState.OPEN:
            return ProviderCallResult.fail(
                ProviderErrorKind.UNKNOWN,
                f"circuit breaker '{self.name}' is OPEN",
            )

        result = fn()

        if result.success:
            if self._state is CircuitBreakerState.HALF_OPEN:
                logger.info("circuit breaker '%s' → CLOSED (probe succeeded)", self.name)
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._opened_at = None
        else:
            self._failure_count += 1
            if (
                self._state is CircuitBreakerState.HALF_OPEN
                or self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitBreakerState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "circuit breaker '%s' → OPEN (failures=%d)",
                    self.name,
                    self._failure_count,
                )

        return result

    def reset(self) -> None:
        """Manually reset to CLOSED state (for testing / ops)."""
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._opened_at = None
