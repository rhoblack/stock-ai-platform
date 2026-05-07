"""v0.11 Phase C -- Provider observability tests.

Three concerns are covered:

1. ProviderHealthMonitor ring-buffer + summary_24h semantics
   - bounded `recent_calls` (maxlen=200) / `recent_failures` (maxlen=50)
   - 24h window boundary in `summary_24h(now=...)`
   - reset() clears the ring buffers

2. PrometheusMetrics bundle + record_call helper
   - Counter / Gauge / Histogram lines appear in render_metrics output
   - Per-provider labels segregate counts
   - failures_by_kind labels by ProviderErrorKind value
   - circuit_state gauge encoding (CLOSED=0 / OPEN=1 / HALF_OPEN=2 /
     UNREGISTERED=3)
   - Tests own a fresh CollectorRegistry via set_metrics(), so the
     global prometheus_client.REGISTRY stays clean across the suite

3. GET /metrics route policy
   - 404 when PROMETHEUS_ENABLED=false (operator opt-out)
   - 200 + text/plain when enabled
   - POST/PUT/DELETE /metrics return 405
   - Response body never contains DART_API_KEY / crtfc_key /
     ?api_key=... -- only counter / gauge labels with provider names

External network calls: 0 (Prometheus is purely in-memory; no HTTP
fanout happens during /metrics rendering).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from app.config.settings import Settings, get_settings
from app.data.provider_health_monitor import (
    CALL_HISTORY_MAXLEN,
    FAILURE_HISTORY_MAXLEN,
    ProviderHealthMonitor,
)
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)
from app.monitoring import prometheus as prom


# ---------------------------------------------------------------------------
# Fixtures -- isolated metrics bundle per test
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_metrics() -> Iterator[prom.PrometheusMetrics]:
    """Inject a fresh CollectorRegistry-backed metrics bundle.

    Restores the previous bundle (or None) on teardown so the global
    prometheus_client.REGISTRY is never polluted by tests.
    """
    previous = prom.get_metrics()
    registry = CollectorRegistry()
    metrics = prom.PrometheusMetrics.build(registry)
    prom.set_metrics(metrics)
    try:
        yield metrics
    finally:
        prom.set_metrics(previous)


@pytest.fixture()
def disabled_metrics() -> Iterator[None]:
    """Disable the Prometheus side-channel for this test (None bundle)."""
    previous = prom.get_metrics()
    prom.set_metrics(None)
    try:
        yield
    finally:
        prom.set_metrics(previous)


# ===========================================================================
# 1. Ring buffer + summary_24h
# ===========================================================================


def _ok(attempts: int = 1) -> ProviderCallResult:
    return ProviderCallResult.ok("data", attempts=attempts)


def _fail(
    kind: ProviderErrorKind = ProviderErrorKind.SERVER_ERROR,
    attempts: int = 1,
) -> ProviderCallResult:
    return ProviderCallResult.fail(kind, "msg", attempts=attempts)


def test_recent_calls_bounded_by_maxlen(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    for _ in range(CALL_HISTORY_MAXLEN + 50):
        monitor.record_result("dart", _ok())
    stats = monitor._providers["dart"]
    assert len(stats.recent_calls) == CALL_HISTORY_MAXLEN


def test_recent_failures_bounded_by_maxlen(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    for _ in range(FAILURE_HISTORY_MAXLEN + 25):
        monitor.record_result("dart", _fail())
    stats = monitor._providers["dart"]
    assert len(stats.recent_failures) == FAILURE_HISTORY_MAXLEN
    # recent_calls is also bounded but at a larger maxlen
    assert len(stats.recent_calls) <= CALL_HISTORY_MAXLEN


def test_recent_calls_records_success_and_attempts(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok(attempts=2))
    monitor.record_result("dart", _fail(ProviderErrorKind.TIMEOUT, attempts=3))
    stats = monitor._providers["dart"]
    assert len(stats.recent_calls) == 2
    assert stats.recent_calls[0].success is True
    assert stats.recent_calls[0].attempts == 2
    assert stats.recent_calls[1].success is False
    assert stats.recent_calls[1].error_kind == ProviderErrorKind.TIMEOUT
    assert stats.recent_calls[1].attempts == 3
    assert len(stats.recent_failures) == 1
    assert stats.recent_failures[0].error_kind == ProviderErrorKind.TIMEOUT
    assert stats.recent_failures[0].attempts == 3


def test_summary_24h_empty_when_no_calls(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    stats = monitor._providers["dart"]
    summary = stats.summary_24h()
    assert summary.call_count_24h == 0
    assert summary.success_count_24h == 0
    assert summary.failure_count_24h == 0
    assert summary.success_rate_24h is None
    assert summary.avg_attempts is None


def test_summary_24h_aggregates_within_window(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok(attempts=1))
    monitor.record_result("dart", _ok(attempts=2))
    monitor.record_result("dart", _fail(attempts=3))
    summary = monitor._providers["dart"].summary_24h()
    assert summary.call_count_24h == 3
    assert summary.success_count_24h == 2
    assert summary.failure_count_24h == 1
    assert summary.success_rate_24h == pytest.approx(2 / 3)
    assert summary.avg_attempts == pytest.approx((1 + 2 + 3) / 3)


def test_summary_24h_excludes_records_outside_window(disabled_metrics):
    """Records older than 24h should drop out of the summary even if
    they still sit in the ring buffer (the buffer is bounded by count,
    not by time)."""
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    stats = monitor._providers["dart"]
    # Inject an old record by hand to avoid having to monkeypatch
    # datetime.now.
    from app.data.provider_health_monitor import CallRecord  # noqa: PLC0415

    old_ts = datetime.now(tz=timezone.utc) - timedelta(hours=30)
    stats.recent_calls.append(
        CallRecord(timestamp=old_ts, success=True, error_kind=None, attempts=1)
    )
    # Plus a fresh successful record via the public path.
    monitor.record_result("dart", _ok())
    # ``now`` injection demonstrates: only the fresh record counts.
    summary = stats.summary_24h(now=datetime.now(tz=timezone.utc))
    assert summary.call_count_24h == 1
    assert summary.success_count_24h == 1


def test_reset_clears_ring_buffers(disabled_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok())
    monitor.record_result("dart", _fail())
    stats = monitor._providers["dart"]
    assert len(stats.recent_calls) == 2
    assert len(stats.recent_failures) == 1

    monitor.reset("dart")
    assert len(stats.recent_calls) == 0
    assert len(stats.recent_failures) == 0


# ===========================================================================
# 2. Prometheus metrics bundle
# ===========================================================================


def test_record_call_increments_counters(isolated_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok(attempts=1))
    monitor.record_result("dart", _ok(attempts=2))
    monitor.record_result("dart", _fail(ProviderErrorKind.TIMEOUT, attempts=3))

    payload, content_type = prom.render_metrics()
    body = payload.decode("utf-8")
    assert "text/plain" in content_type
    # Counters carry the provider label
    assert 'provider_calls_total{provider="dart"} 3.0' in body
    assert 'provider_call_successes_total{provider="dart"} 2.0' in body
    assert 'provider_call_failures_total{provider="dart"} 1.0' in body
    assert (
        'provider_call_failures_by_kind_total'
        '{error_kind="TIMEOUT",provider="dart"} 1.0'
    ) in body


def test_record_call_circuit_state_gauge(isolated_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart", failure_threshold=2)
    monitor.record_result("dart", _ok())
    body = prom.render_metrics()[0].decode("utf-8")
    # CLOSED → 0
    assert 'provider_circuit_state{provider="dart"} 0.0' in body

    # Trip via two failures
    stats = monitor._providers["dart"]
    stats.circuit_breaker._state = CircuitBreakerState.OPEN
    monitor.record_result("dart", _fail())
    body = prom.render_metrics()[0].decode("utf-8")
    assert 'provider_circuit_state{provider="dart"} 1.0' in body


def test_record_call_attempts_histogram(isolated_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok(attempts=1))
    monitor.record_result("dart", _ok(attempts=4))
    body = prom.render_metrics()[0].decode("utf-8")
    assert 'provider_call_attempts_count{provider="dart"} 2.0' in body
    # Sum of attempts across observations.
    assert 'provider_call_attempts_sum{provider="dart"} 5.0' in body


def test_record_call_segregates_by_provider(isolated_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.register("rss")
    monitor.record_result("dart", _ok())
    monitor.record_result("rss", _fail())
    monitor.record_result("rss", _fail())
    body = prom.render_metrics()[0].decode("utf-8")
    assert 'provider_calls_total{provider="dart"} 1.0' in body
    assert 'provider_calls_total{provider="rss"} 2.0' in body


def test_record_call_no_op_when_metrics_disabled(disabled_metrics):
    """With set_metrics(None), record_call must silently no-op so the
    monitor path stays cheap when PROMETHEUS_ENABLED=false."""
    # Just verify no exception escapes -- the behavioural assertion is
    # that monitor.record_result does not raise even without a bundle.
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok())
    # render_metrics returns empty bytes when the bundle is None.
    payload, _ = prom.render_metrics()
    assert payload == b""


def test_isolated_registry_does_not_pollute_global(isolated_metrics):
    """Each test bundle owns its own CollectorRegistry; building a
    second isolated bundle in the same process must not raise the
    'collector already registered' error.
    """
    second_registry = CollectorRegistry()
    second_bundle = prom.PrometheusMetrics.build(second_registry)
    # Both bundles can independently observe and render.
    second_bundle.calls.labels(provider="kis").inc()
    body = prom.generate_latest(second_registry).decode("utf-8")
    assert 'provider_calls_total{provider="kis"} 1.0' in body


def test_prometheus_emit_failure_does_not_break_monitor(monkeypatch):
    """If the Prometheus hook raises, the provider call path must
    continue: the monitor swallows the exception via try/except
    around _emit_prometheus.
    """
    monitor = ProviderHealthMonitor()
    monitor.register("dart")

    def boom(*_a, **_kw):
        raise RuntimeError("simulated prometheus crash")

    monkeypatch.setattr(prom, "record_call", boom)
    # Must NOT raise.
    monitor.record_result("dart", _ok())
    assert monitor._providers["dart"].call_count == 1


# ===========================================================================
# 3. GET /metrics route
# ===========================================================================


def _make_client_with_settings(**overrides) -> TestClient:
    base = dict(
        app_env="test",
        app_name="stock_ai_platform",
        timezone="Asia/Seoul",
        log_level="INFO",
        kis_app_key="",
        kis_app_secret="",
        kis_account_no="",
        kis_account_product_code="01",
        kis_use_paper=True,
        scheduler_enabled=False,
        rate_limit_enabled=False,
        security_headers_enabled=False,
        auth_bruteforce_enabled=False,
        sentry_enabled=False,
        dart_enabled=False,
        rss_news_enabled=False,
        prometheus_enabled=False,
    )
    base.update(overrides)
    settings = Settings(**base)
    from app.main import app  # noqa: PLC0415

    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, raise_server_exceptions=False)


def test_metrics_returns_404_when_prometheus_disabled():
    client = _make_client_with_settings(prometheus_enabled=False)
    r = client.get("/metrics")
    assert r.status_code == 404


def test_metrics_returns_200_with_text_plain_when_enabled(isolated_metrics):
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result("dart", _ok())
    client = _make_client_with_settings(prometheus_enabled=True)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert 'provider_calls_total{provider="dart"} 1.0' in r.text


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_metrics_rejects_mutations_with_405(method: str):
    client = _make_client_with_settings(prometheus_enabled=True)
    r = getattr(client, method)("/metrics")
    assert r.status_code == 405


def test_metrics_response_never_contains_provider_secrets(isolated_metrics):
    """Even with credentials populated in Settings, the /metrics body
    must not echo any secret -- only counter / gauge labels.
    """
    # Populate the monitor with calls that simulate real provider use.
    monitor = ProviderHealthMonitor()
    monitor.register("dart")
    monitor.record_result(
        "dart",
        ProviderCallResult.fail(
            ProviderErrorKind.TIMEOUT,
            # An error message that contains a fake secret -- the
            # monitor stores it for log correlation but Prometheus
            # records carry only the enum.
            "GET https://opendart.fss.or.kr/api/x?crtfc_key=LEAKMEXYZ failed",
            attempts=2,
        ),
    )
    client = _make_client_with_settings(
        prometheus_enabled=True,
        dart_enabled=True,
        dart_api_key="DART-CRTFC-SUPERSECRET",
        rss_news_enabled=True,
        rss_feed_urls="https://example.com/feed.xml?api_key=URLSECRETXYZ",
    )
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    forbidden = [
        "DART-CRTFC-SUPERSECRET",
        "URLSECRETXYZ",
        "LEAKMEXYZ",
        "crtfc_key",
        "dart_api_key",
        "rss_feed_urls",
        "kis_app_key",
        "?api_key=",
        "access_token",
        "password",
    ]
    for s in forbidden:
        assert s not in body, f"/metrics body leaks {s!r}"


def test_metrics_endpoint_does_not_construct_httpx_client(monkeypatch):
    """GET /metrics must build the response from in-memory state only;
    the route must NEVER trigger a provider HTTP call.
    """
    import httpx  # noqa: PLC0415

    def boom(*_a, **_kw):
        raise AssertionError("/metrics must not construct httpx.Client")

    monkeypatch.setattr(httpx, "Client", boom)
    client = _make_client_with_settings(prometheus_enabled=True)
    r = client.get("/metrics")
    assert r.status_code in (200, 404)  # depending on bundle init order
