"""v0.11 Phase C -- Prometheus exporter for provider observability.

Exposes per-provider counters / gauges / histograms via a single
:class:`PrometheusMetrics` bundle.  The module is **opt-in**:

* ``record_call`` is a no-op unless :func:`get_metrics` returns a
  bundle, which only happens when ``Settings.prometheus_enabled`` is
  ``True`` AND the bundle has been initialised.  Tests construct their
  own bundle with an isolated :class:`prometheus_client.CollectorRegistry`
  to avoid polluting the global registry across the test suite.

* ``GET /metrics`` (in :mod:`app.api.metrics_routes`) calls
  :func:`render_metrics` to produce the Prometheus text-format payload.
  When disabled the route returns 404; the payload itself contains
  only counter / gauge / histogram values + the provider name label --
  no API key / token / URL / message text appears in any sample.

CIRCUIT STATE ENCODING
----------------------
Prometheus scrapers prefer numeric gauges, so the circuit-breaker
state is encoded as an integer:

    CLOSED       = 0
    OPEN         = 1
    HALF_OPEN    = 2
    UNREGISTERED = 3

Operators can read the gauge alongside the counters to distinguish a
healthy quiet provider (CLOSED + zero recent calls) from a fast-failing
one (OPEN).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from app.config.settings import Settings, get_settings
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CIRCUIT_STATE_VALUES: dict[CircuitBreakerState, int] = {
    CircuitBreakerState.CLOSED: 0,
    CircuitBreakerState.OPEN: 1,
    CircuitBreakerState.HALF_OPEN: 2,
}

# Sentinel for circuit_state when a provider has never been registered
# (the monitor returns ``UNREGISTERED`` from the route handler).
_UNREGISTERED_VALUE = 3


# ---------------------------------------------------------------------------
# Metrics bundle
# ---------------------------------------------------------------------------


@dataclass
class PrometheusMetrics:
    """Bundle of provider observability metrics tied to one registry.

    Tests construct their own bundle with a fresh registry so they
    cannot collide with the global default-registry installed by the
    application bootstrap.
    """

    registry: CollectorRegistry
    calls: Counter
    successes: Counter
    failures: Counter
    failures_by_kind: Counter
    circuit_state: Gauge
    attempts: Histogram

    @classmethod
    def build(cls, registry: CollectorRegistry) -> "PrometheusMetrics":
        return cls(
            registry=registry,
            calls=Counter(
                "provider_calls_total",
                "Total provider calls observed by ProviderHealthMonitor.",
                labelnames=("provider",),
                registry=registry,
            ),
            successes=Counter(
                "provider_call_successes_total",
                "Provider calls that returned ProviderCallResult.success=True.",
                labelnames=("provider",),
                registry=registry,
            ),
            failures=Counter(
                "provider_call_failures_total",
                "Provider calls that returned ProviderCallResult.success=False.",
                labelnames=("provider",),
                registry=registry,
            ),
            failures_by_kind=Counter(
                "provider_call_failures_by_kind_total",
                "Provider call failures broken down by ProviderErrorKind.",
                labelnames=("provider", "error_kind"),
                registry=registry,
            ),
            circuit_state=Gauge(
                "provider_circuit_state",
                "Circuit breaker state per provider "
                "(0=CLOSED, 1=OPEN, 2=HALF_OPEN, 3=UNREGISTERED).",
                labelnames=("provider",),
                registry=registry,
            ),
            attempts=Histogram(
                "provider_call_attempts",
                "Number of attempts (retries+1) per provider call.",
                labelnames=("provider",),
                registry=registry,
                # Small integer-friendly buckets covering typical retry counts.
                buckets=(1, 2, 3, 4, 5, 7, 10),
            ),
        )


# ---------------------------------------------------------------------------
# Module-level singleton (opt-in)
# ---------------------------------------------------------------------------

# When ``_metrics`` is ``None`` every public helper is a no-op.  The
# bundle is initialised lazily by the app bootstrap (see
# :func:`init_default_metrics`) and overridden in tests via
# :func:`set_metrics` (or `with_metrics_for_test` context manager).
_metrics: PrometheusMetrics | None = None


def get_metrics() -> PrometheusMetrics | None:
    """Return the currently active metrics bundle, or ``None`` when off."""
    return _metrics


def set_metrics(metrics: PrometheusMetrics | None) -> None:
    """Inject a metrics bundle (tests use a fresh isolated registry).

    Pass ``None`` to disable the side channel between tests.
    """
    global _metrics
    _metrics = metrics


def init_default_metrics(settings: Settings | None = None) -> Optional[PrometheusMetrics]:
    """Initialise a metrics bundle on the prometheus_client global registry.

    Called by the app factory at startup when
    ``Settings.prometheus_enabled`` is ``True``.  Idempotent: if a
    bundle already exists it is returned unchanged so a hot-reload
    does not double-register collectors (which would raise).

    Returns ``None`` when Prometheus is disabled.
    """
    global _metrics
    settings = settings or get_settings()
    if not settings.prometheus_enabled:
        return None
    if _metrics is not None:
        return _metrics
    # Use prometheus_client's process-global registry by default; the
    # bundle still owns its own collectors so re-init in tests is
    # opt-in via :func:`set_metrics`.
    from prometheus_client import REGISTRY  # noqa: PLC0415

    try:
        _metrics = PrometheusMetrics.build(REGISTRY)
    except ValueError:
        # Collector with the same name already registered (test pollution
        # or hot-reload).  Skip silently -- observability must never
        # break startup.
        logger.warning(
            "prometheus collectors already registered; "
            "skipping init (likely a hot reload)"
        )
        return None
    return _metrics


# ---------------------------------------------------------------------------
# Recording API (called from ProviderHealthMonitor.record_result)
# ---------------------------------------------------------------------------


def record_call(
    provider_name: str,
    circuit_state: CircuitBreakerState,
    result: ProviderCallResult,
    attempts: int,
) -> None:
    """Forward one provider call outcome to the active metrics bundle.

    No-op when no bundle is set.  Never raises -- the monitor wraps
    this in its own try/except so a Prometheus issue cannot break a
    provider call.
    """
    metrics = _metrics
    if metrics is None:
        return
    metrics.calls.labels(provider=provider_name).inc()
    if result.success:
        metrics.successes.labels(provider=provider_name).inc()
    else:
        metrics.failures.labels(provider=provider_name).inc()
        kind = (
            result.error_kind.value
            if result.error_kind is not None
            else ProviderErrorKind.UNKNOWN.value
        )
        metrics.failures_by_kind.labels(
            provider=provider_name, error_kind=kind
        ).inc()
    metrics.attempts.labels(provider=provider_name).observe(attempts)
    metrics.circuit_state.labels(provider=provider_name).set(
        CIRCUIT_STATE_VALUES.get(circuit_state, _UNREGISTERED_VALUE)
    )


def mark_unregistered(provider_name: str) -> None:
    """Record a provider as ``UNREGISTERED`` in the gauge.

    Useful for the route handler so the gauge has a sample even for
    providers that have not yet emitted a call.
    """
    metrics = _metrics
    if metrics is None:
        return
    metrics.circuit_state.labels(provider=provider_name).set(_UNREGISTERED_VALUE)


# ---------------------------------------------------------------------------
# Rendering API (called from /metrics route)
# ---------------------------------------------------------------------------


def render_metrics() -> tuple[bytes, str]:
    """Return the Prometheus text-format payload + content-type header.

    The payload contains only counter / gauge / histogram lines with
    provider-name + error-kind labels -- no URL, no API key, no
    message text appears.

    Returns ``(b"", CONTENT_TYPE_LATEST)`` when Prometheus is disabled
    so the route handler can short-circuit to 404 without inspecting
    the bundle directly.
    """
    metrics = _metrics
    if metrics is None:
        return b"", CONTENT_TYPE_LATEST
    return generate_latest(metrics.registry), CONTENT_TYPE_LATEST


__all__ = [
    "CIRCUIT_STATE_VALUES",
    "PrometheusMetrics",
    "get_metrics",
    "set_metrics",
    "init_default_metrics",
    "record_call",
    "mark_unregistered",
    "render_metrics",
]
