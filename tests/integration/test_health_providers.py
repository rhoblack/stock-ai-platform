"""v0.10 Phase D -- GET /api/health/providers integration tests.

Covers:

* Default (kis/dart/rss) providers always appear in the response, even
  with no recorded calls -- in fixed order: kis, dart, rss.
* DART_ENABLED=false → ``enabled=False`` / ``configured=False``;
  RSS_NEWS_ENABLED=false → ``enabled=False`` / ``configured=False``.
* DART_ENABLED=true + DART_API_KEY="..." → ``enabled=True`` /
  ``configured=True``.
* RSS_NEWS_ENABLED=true + RSS_FEED_URLS="..." → enabled+configured.
* Enabled-but-not-configured (key missing) shows ``enabled=True`` /
  ``configured=False`` -- the UI can warn explicitly.
* Provider with recorded successes/failures has matching counters and
  ``circuit_state`` / ``last_error_kind``.
* Circuit breaker OPEN state propagates to ``circuit_state``.
* Response NEVER includes ``last_error_message`` (a transport detail
  that may carry URL query secrets / partial body).
* Response NEVER includes ``dart_api_key`` / ``crtfc_key`` /
  ``rss_feed_urls`` / ``kis_app_key`` / ``kis_app_secret`` /
  ``access_token`` / ``password`` / etc. (whitelist + grep guard).
* No real DART / RSS / KIS HTTP call happens during the request --
  ``httpx.Client`` instantiation is monkeypatched to fail.
* Additional providers registered in the monitor (future-proof) are
  appended after the canonical 3 in monitor-iteration order.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings, get_settings
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_settings(**overrides) -> Settings:
    """Default-OFF settings; overrides flip individual flags on."""
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
        dart_api_key="",
        rss_news_enabled=False,
        rss_feed_urls="",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def fresh_monitor(monkeypatch: pytest.MonkeyPatch) -> Iterator[ProviderHealthMonitor]:
    """Replace the global health monitor with a fresh instance per test.

    Without this each test would inherit registrations + counter state
    from earlier tests, causing flaky assertions on call_count etc.
    """
    monitor = ProviderHealthMonitor()
    import app.data.provider_health_monitor as phm

    monkeypatch.setattr(phm, "_default_monitor", monitor)
    yield monitor


def _make_client(settings: Settings) -> TestClient:
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Default providers always surface
# ---------------------------------------------------------------------------


def test_health_providers_returns_three_canonical_rows_when_disabled(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    r = client.get("/api/health/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    names = [item["provider_name"] for item in body["items"]]
    assert names == ["kis", "dart", "rss"]


def test_health_providers_disabled_state(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    items_by_name = {it["provider_name"]: it for it in body["items"]}

    # DART
    assert items_by_name["dart"]["enabled"] is False
    assert items_by_name["dart"]["configured"] is False
    # RSS
    assert items_by_name["rss"]["enabled"] is False
    assert items_by_name["rss"]["configured"] is False
    # KIS — empty key in our test settings → not enabled / not configured
    assert items_by_name["kis"]["enabled"] is False
    assert items_by_name["kis"]["configured"] is False


def test_health_providers_circuit_state_unregistered_when_no_calls(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    for item in body["items"]:
        assert item["circuit_state"] == "UNREGISTERED"
        assert item["call_count"] == 0
        assert item["success_count"] == 0
        assert item["failure_count"] == 0
        assert item["last_error_kind"] is None
        assert item["last_called_at"] is None


# ---------------------------------------------------------------------------
# Enabled / configured branches
# ---------------------------------------------------------------------------


def test_health_providers_dart_enabled_and_configured(fresh_monitor):
    settings = _build_settings(dart_enabled=True, dart_api_key="testkey-XYZ")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    assert dart["enabled"] is True
    assert dart["configured"] is True


def test_health_providers_rss_enabled_and_configured(fresh_monitor):
    settings = _build_settings(
        rss_news_enabled=True, rss_feed_urls="https://example.com/feed.xml"
    )
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    rss = next(it for it in body["items"] if it["provider_name"] == "rss")
    assert rss["enabled"] is True
    assert rss["configured"] is True


def test_health_providers_dart_enabled_but_unconfigured(fresh_monitor):
    """DART_ENABLED=true but DART_API_KEY missing -- enabled True / configured False."""
    settings = _build_settings(dart_enabled=True, dart_api_key="")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    assert dart["enabled"] is True
    assert dart["configured"] is False


def test_health_providers_rss_enabled_but_no_feed_urls(fresh_monitor):
    settings = _build_settings(rss_news_enabled=True, rss_feed_urls="")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    rss = next(it for it in body["items"] if it["provider_name"] == "rss")
    assert rss["enabled"] is True
    assert rss["configured"] is False


def test_health_providers_kis_configured_when_key_and_secret_set(fresh_monitor):
    settings = _build_settings(
        kis_app_key="kkkk1111kkkk2222", kis_app_secret="ssss3333ssss4444"
    )
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    kis = next(it for it in body["items"] if it["provider_name"] == "kis")
    assert kis["enabled"] is True
    assert kis["configured"] is True


# ---------------------------------------------------------------------------
# Counters + circuit state from monitor
# ---------------------------------------------------------------------------


def test_health_providers_reflects_recorded_calls(fresh_monitor: ProviderHealthMonitor):
    fresh_monitor.register("dart")
    fresh_monitor.record_result("dart", ProviderCallResult.ok("ok"))
    fresh_monitor.record_result("dart", ProviderCallResult.ok("ok"))
    fresh_monitor.record_result(
        "dart", ProviderCallResult.fail(ProviderErrorKind.TIMEOUT, "timed out")
    )

    settings = _build_settings(dart_enabled=True, dart_api_key="K")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    assert dart["call_count"] == 3
    assert dart["success_count"] == 2
    assert dart["failure_count"] == 1
    assert dart["last_error_kind"] == "TIMEOUT"
    assert dart["last_called_at"] is not None
    assert dart["circuit_state"] == "CLOSED"


def test_health_providers_open_circuit_state_propagates(
    fresh_monitor: ProviderHealthMonitor,
):
    fresh_monitor.register("rss", failure_threshold=2)
    stats = fresh_monitor._providers["rss"]
    # Force OPEN.
    stats.circuit_breaker._state = CircuitBreakerState.OPEN
    stats.circuit_breaker._failure_count = 2

    settings = _build_settings(
        rss_news_enabled=True, rss_feed_urls="https://example.com/feed.xml"
    )
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    rss = next(it for it in body["items"] if it["provider_name"] == "rss")
    assert rss["circuit_state"] == "OPEN"


# ---------------------------------------------------------------------------
# Secret discipline
# ---------------------------------------------------------------------------


def test_health_providers_response_never_includes_secrets(fresh_monitor):
    """Even with credentials populated, the response body must not echo any.

    Validates against a paranoid forbidden-substring set drawn from
    the v0.5 / v0.10 secret-leak gates.
    """
    settings = _build_settings(
        dart_enabled=True,
        dart_api_key="DART-CRTFC-SUPERSECRET",
        rss_news_enabled=True,
        rss_feed_urls="https://example.com/feed.xml?api_key=URLSECRETXYZ",
        kis_app_key="KIS-APP-KEY-PLAINTEXT",
        kis_app_secret="KIS-APP-SECRET-PLAINTEXT",
    )
    client = _make_client(settings)
    raw = client.get("/api/health/providers").text

    forbidden_substrings = [
        "DART-CRTFC-SUPERSECRET",
        "URLSECRETXYZ",
        "KIS-APP-KEY-PLAINTEXT",
        "KIS-APP-SECRET-PLAINTEXT",
        "crtfc_key",
        "dart_api_key",
        "DART_API_KEY",
        "rss_feed_urls",
        "kis_app_key",
        "kis_app_secret",
        "access_token",
        "password",
        "jwt_secret",
        "?api_key=",
    ]
    for s in forbidden_substrings:
        assert s not in raw, f"response body leaks {s!r}"


def test_health_providers_omits_last_error_message(
    fresh_monitor: ProviderHealthMonitor,
):
    """``last_error_message`` may carry URL query strings / partial body --
    must never appear in the response.
    """
    fresh_monitor.register("rss")
    fresh_monitor.record_result(
        "rss",
        ProviderCallResult.fail(
            ProviderErrorKind.TIMEOUT,
            # An error message that contains a fake secret -- the
            # monitor stores it for log correlation but the API must
            # not echo it.
            "GET https://example.com/feed.xml?api_key=LEAKMEXYZ failed",
        ),
    )

    settings = _build_settings(
        rss_news_enabled=True, rss_feed_urls="https://example.com/feed.xml"
    )
    client = _make_client(settings)
    raw = client.get("/api/health/providers").text
    body = client.get("/api/health/providers").json()
    rss = next(it for it in body["items"] if it["provider_name"] == "rss")
    # The kind survives, the message does not.
    assert rss["last_error_kind"] == "TIMEOUT"
    assert "last_error_message" not in rss
    assert "LEAKMEXYZ" not in raw


# ---------------------------------------------------------------------------
# No external HTTP call
# ---------------------------------------------------------------------------


def test_health_providers_does_not_construct_httpx_client(
    fresh_monitor, monkeypatch: pytest.MonkeyPatch
):
    """A GET /api/health/providers request must build the response from
    in-memory state only -- the route must NEVER instantiate httpx.Client
    or otherwise reach a provider.
    """
    import httpx as _httpx

    def boom(*_a, **_kw):
        raise AssertionError(
            "GET /api/health/providers must not construct httpx.Client"
        )

    monkeypatch.setattr(_httpx, "Client", boom)

    settings = _build_settings(
        dart_enabled=True,
        dart_api_key="K",
        rss_news_enabled=True,
        rss_feed_urls="https://example.com/feed.xml",
    )
    client = _make_client(settings)
    r = client.get("/api/health/providers")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Future-proof: experimental provider beyond the canonical 3
# ---------------------------------------------------------------------------


def test_health_providers_surfaces_extra_registered_providers(
    fresh_monitor: ProviderHealthMonitor,
):
    fresh_monitor.register("experimental")
    fresh_monitor.record_result(
        "experimental", ProviderCallResult.ok("ok")
    )

    settings = _build_settings()
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    names = [it["provider_name"] for it in body["items"]]
    # Canonical 3 first, experimental appended.
    assert names[:3] == ["kis", "dart", "rss"]
    assert "experimental" in names[3:]
    extra = next(it for it in body["items"] if it["provider_name"] == "experimental")
    assert extra["call_count"] == 1
    assert extra["success_count"] == 1


# ---------------------------------------------------------------------------
# No POST / PUT / DELETE on the health route (read-only policy)
# ---------------------------------------------------------------------------


def test_health_providers_rejects_post(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    r = client.post("/api/health/providers")
    assert r.status_code == 405


def test_health_providers_rejects_put(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    r = client.put("/api/health/providers", json={})
    assert r.status_code == 405


def test_health_providers_rejects_delete(fresh_monitor):
    settings = _build_settings()
    client = _make_client(settings)
    r = client.delete("/api/health/providers")
    assert r.status_code == 405


# ---------------------------------------------------------------------------
# v0.11 Phase D additions -- 24h aggregates + recent_failures
# ---------------------------------------------------------------------------


def test_health_providers_unregistered_phase_d_fields_have_safe_defaults(
    fresh_monitor,
):
    """Default-OFF / never-registered providers must surface the new
    Phase D fields with neutral defaults (zero / None / empty list).
    """
    settings = _build_settings()
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    for item in body["items"]:
        assert item["call_count_24h"] == 0
        assert item["success_count_24h"] == 0
        assert item["failure_count_24h"] == 0
        assert item["success_rate_24h"] is None
        assert item["avg_attempts_24h"] is None
        assert item["recent_failures"] == []


def test_health_providers_24h_aggregates_reflect_recorded_calls(
    fresh_monitor: ProviderHealthMonitor,
):
    fresh_monitor.register("dart")
    fresh_monitor.record_result(
        "dart", ProviderCallResult.ok("ok", attempts=1)
    )
    fresh_monitor.record_result(
        "dart", ProviderCallResult.ok("ok", attempts=2)
    )
    fresh_monitor.record_result(
        "dart",
        ProviderCallResult.fail(
            ProviderErrorKind.TIMEOUT, "msg", attempts=3
        ),
    )

    settings = _build_settings(dart_enabled=True, dart_api_key="K")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    assert dart["call_count_24h"] == 3
    assert dart["success_count_24h"] == 2
    assert dart["failure_count_24h"] == 1
    assert dart["success_rate_24h"] == pytest.approx(2 / 3)
    assert dart["avg_attempts_24h"] == pytest.approx((1 + 2 + 3) / 3)


def test_health_providers_recent_failures_capped_at_five_newest_first(
    fresh_monitor: ProviderHealthMonitor,
):
    """recent_failures must surface at most the five newest failure
    records; the route reverses the deque so newest entries appear
    first.
    """
    fresh_monitor.register("dart")
    # Inject failure records directly with distinct timestamps so we
    # can verify the reverse-newest-first ordering deterministically.
    from app.data.provider_health_monitor import (  # noqa: PLC0415
        FailureRecord,
    )

    base = datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc)
    stats = fresh_monitor._providers["dart"]
    for i in range(8):
        stats.recent_failures.append(
            FailureRecord(
                timestamp=base + timedelta(minutes=i),
                error_kind=ProviderErrorKind.SERVER_ERROR,
                attempts=i + 1,
            )
        )

    settings = _build_settings(dart_enabled=True, dart_api_key="K")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    failures = dart["recent_failures"]
    # Exactly 5 surfaced (capped by _RECENT_FAILURE_LIMIT).
    assert len(failures) == 5
    # Each entry carries only timestamp + error_kind -- no message text.
    for entry in failures:
        assert set(entry.keys()) == {"timestamp", "error_kind"}
        assert entry["error_kind"] == "SERVER_ERROR"
    # Newest first: entry 0 must be the latest record (i=7), entry 4
    # must correspond to i=3.
    assert failures[0]["timestamp"] == (base + timedelta(minutes=7)).isoformat()
    assert failures[-1]["timestamp"] == (base + timedelta(minutes=3)).isoformat()


def test_health_providers_recent_failures_omits_message_text(
    fresh_monitor: ProviderHealthMonitor,
):
    """Even though monitor.last_error_message stores transport detail,
    recent_failures items must not include a message field.
    """
    fresh_monitor.register("rss")
    fresh_monitor.record_result(
        "rss",
        ProviderCallResult.fail(
            ProviderErrorKind.TIMEOUT,
            # Canary string -- must never appear in /api/health/providers.
            "GET https://example.com/feed.xml?api_key=LEAKMEXYZ failed",
            attempts=2,
        ),
    )

    settings = _build_settings(
        rss_news_enabled=True, rss_feed_urls="https://example.com/feed.xml"
    )
    client = _make_client(settings)
    raw = client.get("/api/health/providers").text
    body = client.get("/api/health/providers").json()
    rss = next(it for it in body["items"] if it["provider_name"] == "rss")
    # recent_failures has 1 entry without message text.
    assert len(rss["recent_failures"]) == 1
    assert "message" not in rss["recent_failures"][0]
    assert "error_message" not in rss["recent_failures"][0]
    assert "LEAKMEXYZ" not in raw


def test_health_providers_phase_d_response_secret_paranoid(
    fresh_monitor: ProviderHealthMonitor,
):
    """Combined Phase D paranoid check: even with credentials populated
    AND failures recorded, the response body must not echo any secret.
    Extends the v0.10 secret discipline test with the new fields.
    """
    fresh_monitor.register("dart")
    fresh_monitor.record_result(
        "dart",
        ProviderCallResult.fail(
            ProviderErrorKind.SERVER_ERROR,
            "GET https://opendart.fss.or.kr/api/x?crtfc_key=LEAKDART failed",
            attempts=4,
        ),
    )
    fresh_monitor.register("rss")
    fresh_monitor.record_result(
        "rss",
        ProviderCallResult.fail(
            ProviderErrorKind.CLIENT_ERROR,
            "GET https://private.example.com/feed?api_key=LEAKRSS failed",
            attempts=1,
        ),
    )

    settings = _build_settings(
        dart_enabled=True,
        dart_api_key="DART-CRTFC-SUPERSECRET",
        rss_news_enabled=True,
        rss_feed_urls="https://private.example.com/feed?api_key=URLSECRETXYZ",
        kis_app_key="KIS-APP-KEY-PLAINTEXT",
        kis_app_secret="KIS-APP-SECRET-PLAINTEXT",
    )
    client = _make_client(settings)
    raw = client.get("/api/health/providers").text

    forbidden = [
        "DART-CRTFC-SUPERSECRET",
        "URLSECRETXYZ",
        "LEAKDART",
        "LEAKRSS",
        "KIS-APP-KEY-PLAINTEXT",
        "KIS-APP-SECRET-PLAINTEXT",
        "crtfc_key",
        "dart_api_key",
        "DART_API_KEY",
        "rss_feed_urls",
        "kis_app_key",
        "kis_app_secret",
        "access_token",
        "password",
        "?api_key=",
        "last_error_message",
    ]
    for s in forbidden:
        assert s not in raw, f"Phase D response leaks {s!r}"


def test_health_providers_summary_24h_handles_zero_call_window_safely(
    fresh_monitor: ProviderHealthMonitor,
):
    """A provider that was registered but never produced a 24h call
    (e.g. reset() called recently) must surface success_rate_24h=None
    rather than crashing the route.
    """
    fresh_monitor.register("dart")
    settings = _build_settings(dart_enabled=True, dart_api_key="K")
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    dart = next(it for it in body["items"] if it["provider_name"] == "dart")
    assert dart["call_count_24h"] == 0
    assert dart["success_rate_24h"] is None
    assert dart["avg_attempts_24h"] is None
    assert dart["recent_failures"] == []


def test_health_providers_phase_d_fields_present_in_extra_provider(
    fresh_monitor: ProviderHealthMonitor,
):
    """Experimental providers appended after the canonical 3 must also
    carry Phase D fields with sensible defaults.
    """
    fresh_monitor.register("experimental")
    fresh_monitor.record_result(
        "experimental", ProviderCallResult.ok("ok", attempts=1)
    )
    settings = _build_settings()
    client = _make_client(settings)
    body = client.get("/api/health/providers").json()
    extra = next(
        it for it in body["items"] if it["provider_name"] == "experimental"
    )
    assert extra["call_count_24h"] == 1
    assert extra["success_count_24h"] == 1
    assert extra["success_rate_24h"] == 1.0
    assert extra["avg_attempts_24h"] == 1.0
    assert extra["recent_failures"] == []
