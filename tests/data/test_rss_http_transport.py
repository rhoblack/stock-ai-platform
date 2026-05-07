"""v0.11 Phase B -- HttpxRssTransport tests.

The RSS skeleton (v0.10 Phase C) accepted any ``RssTransport`` callable
so tests injected closures over fixture XML.  Phase B adds the real
httpx-backed transport.  These tests verify:

* Mapping of HTTP responses to ``ProviderCallResult``:
    - HTTP 200 → ok(response.content)  (RSS 2.0 + Atom both work)
    - HTTP 4xx → CLIENT_ERROR
    - HTTP 5xx → SERVER_ERROR
    - httpx.TimeoutException → TIMEOUT
    - httpx.ConnectError / TLS error → UNKNOWN (class name only)
    - Non-XML 200 body → transport returns ok(bytes); parser layer
      isolates the failure as RssParseError
* Default-OFF guard: ``RSS_NEWS_ENABLED=false`` and missing
  ``RSS_FEED_URLS`` both prevent ``httpx.Client`` instantiation.
* Factory auto-injection: ``create_rss_provider(transport=None)`` with
  RSS opted in injects an ``HttpxRssTransport``; caller-supplied
  transport short-circuits and keeps the v0.10 ``httpx.Client``
  monkeypatch guard valid.
* Resilience integration: per-feed timeout / failure isolated; circuit
  breaker fast-fails after threshold; multi-feed fetch survives single
  feed failure.
* Secret discipline: feed URLs containing ``?api_key=...`` /
  ``?token=...`` never appear with their values in caplog or in
  ``ProviderCallResult.error_message`` -- the shared
  :class:`SensitiveQueryStringFilter` masks them in httpx INFO logs.

External network: 0 calls.  Every test uses respx to intercept httpx
requests at the transport layer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from app.config.settings import Settings
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import (
    CircuitBreakerState,
    ProviderCallResult,
    ProviderErrorKind,
)
from app.data.rss_provider import (
    HttpxRssTransport,
    RssNewsProvider,
    RssNotConfiguredError,
    create_rss_provider,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


_FEED_URL = "https://example.com/feed.xml"
_FEED_URL_2 = "https://example.com/another/feed.atom"
_FEED_URL_WITH_SECRET = (
    "https://private.example.com/feed?api_key=PRIVATE-FEED-SECRET-XYZ"
)
_PRIVATE_SECRET = "PRIVATE-FEED-SECRET-XYZ"


def _enabled_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    feed_urls: str = _FEED_URL,
    timeout_s: float | None = None,
    max_attempts: int | None = None,
) -> Settings:
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv("RSS_FEED_URLS", feed_urls)
    if timeout_s is not None:
        monkeypatch.setenv("RSS_TIMEOUT_S", str(timeout_s))
    if max_attempts is not None:
        monkeypatch.setenv("RSS_MAX_ATTEMPTS", str(max_attempts))
    return Settings()


def _disabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("RSS_NEWS_ENABLED", raising=False)
    monkeypatch.delenv("RSS_FEED_URLS", raising=False)
    return Settings()


_RSS_2_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Wire</title>
    <link>https://example.com/</link>
    <item>
      <title>HBM 공급 확대</title>
      <link>https://example.com/news/005930-hbm</link>
      <pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>
      <description>HBM 매출 가시성 개선</description>
    </item>
    <item>
      <title>SK하이닉스 1분기 실적</title>
      <link>https://example.com/news/000660-q1</link>
      <pubDate>Wed, 30 Apr 2026 16:00:00 GMT</pubDate>
      <description>1분기 영업이익 컨센서스 부합</description>
    </item>
  </channel>
</rss>
""".encode("utf-8")

_ATOM_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Sample Atom</title>
  <updated>2026-05-04T09:30:00Z</updated>
  <entry>
    <title>NAVER 1분기 매출 발표</title>
    <link href="https://example.com/atom/035420-q1" rel="alternate"/>
    <updated>2026-05-04T09:30:00Z</updated>
    <summary>NAVER Q1 매출 (sample)</summary>
  </entry>
</feed>
""".encode("utf-8")


# ---------------------------------------------------------------------------
# HTTP status → ProviderCallResult
# ---------------------------------------------------------------------------


@respx.mock
def test_transport_http_200_rss2_returns_ok_bytes(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(
        return_value=httpx.Response(200, content=_RSS_2_FIXTURE_XML)
    )
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL)
    finally:
        transport.close()

    assert result.success is True
    assert isinstance(result.value, (bytes, bytearray))
    assert b"HBM" in result.value


@respx.mock
def test_transport_http_200_atom_returns_ok_bytes(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch, feed_urls=_FEED_URL_2)
    respx.get(_FEED_URL_2).mock(
        return_value=httpx.Response(200, content=_ATOM_FIXTURE_XML)
    )
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL_2)
    finally:
        transport.close()

    assert result.success is True
    assert b"NAVER" in result.value


@respx.mock
def test_transport_http_4xx_returns_client_error(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(return_value=httpx.Response(404, text="not found"))
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.CLIENT_ERROR
    assert "404" in (result.error_message or "")


@respx.mock
def test_transport_http_5xx_returns_server_error(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(return_value=httpx.Response(503))
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.SERVER_ERROR
    assert "503" in (result.error_message or "")


@respx.mock
def test_transport_timeout_returns_timeout(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch, timeout_s=0.5)
    respx.get(_FEED_URL).mock(side_effect=httpx.ReadTimeout("simulated"))
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.TIMEOUT


@respx.mock
def test_transport_connect_error_returns_unknown_class_only(
    monkeypatch: pytest.MonkeyPatch,
):
    """httpx.ConnectError carries the request URL in its repr -- the
    transport must echo only the exception class name so the URL
    (which may contain ?api_key=...) cannot leak via error_message.
    """
    settings = _enabled_settings(monkeypatch, feed_urls=_FEED_URL_WITH_SECRET)
    respx.get(_FEED_URL_WITH_SECRET).mock(
        side_effect=httpx.ConnectError(
            f"Failed to connect to {_FEED_URL_WITH_SECRET}"
        )
    )
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL_WITH_SECRET)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN
    assert _PRIVATE_SECRET not in (result.error_message or "")
    # Class name only -- not str(exc).
    assert "ConnectError" in (result.error_message or "")


@respx.mock
def test_transport_unexpected_status_returns_unknown(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(return_value=httpx.Response(304))
    transport = HttpxRssTransport(settings=settings)
    try:
        result = transport(_FEED_URL)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN


@respx.mock
def test_transport_non_xml_200_isolates_at_parser_layer(
    monkeypatch: pytest.MonkeyPatch,
):
    """HTTP 200 + non-XML body: the transport returns ok(bytes); the
    provider's parse_feed raises RssParseError, which is isolated by
    RssNewsProvider._fetch_one (returns []).
    """
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(
        return_value=httpx.Response(200, text="<html><body>not a feed</body></html>")
    )
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(settings=settings, monitor=monitor)
    out = provider.fetch_recent_news()
    assert out == []
    # Transport call itself succeeded (HTTP 200) -- the failure is at
    # parser level, not transport level.  Monitor records success.
    status = monitor.get_status("rss")
    assert status["success_count"] == 1
    assert status["failure_count"] == 0


# ---------------------------------------------------------------------------
# Factory auto-injection
# ---------------------------------------------------------------------------


@respx.mock
def test_factory_auto_injects_httpx_transport_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch)
    respx.get(_FEED_URL).mock(
        return_value=httpx.Response(200, content=_RSS_2_FIXTURE_XML)
    )
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(
        settings=settings, transport=None, monitor=monitor
    )
    assert isinstance(provider, RssNewsProvider)

    out = provider.fetch_recent_news(limit=10)
    assert len(out) == 2
    assert {item.title for item in out} == {
        "HBM 공급 확대",
        "SK하이닉스 1분기 실적",
    }
    assert monitor.get_status("rss")["success_count"] == 1


def test_factory_disabled_rss_does_not_instantiate_transport(
    monkeypatch: pytest.MonkeyPatch,
):
    """v0.10 zero-network guard preserved: RSS_NEWS_ENABLED=false
    short-circuits in ``_check_enabled`` before the factory ever asks
    for a transport.
    """
    settings = _disabled_settings(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("RSS_NEWS_ENABLED=false but Client was instantiated")
        ),
    )
    with pytest.raises(RssNotConfiguredError):
        create_rss_provider(settings=settings, transport=None)


def test_factory_enabled_but_no_urls_does_not_instantiate(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv("RSS_FEED_URLS", "")
    settings = Settings()
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Empty RSS_FEED_URLS but Client was instantiated")
        ),
    )
    with pytest.raises(RssNotConfiguredError):
        create_rss_provider(settings=settings, transport=None)


def test_factory_caller_supplied_transport_skips_httpx_construction(
    monkeypatch: pytest.MonkeyPatch,
):
    """When the caller passes a transport, the factory must NOT touch
    ``httpx.Client`` -- the v0.10 ``test_no_httpx_client_constructed``
    guard remains valid for the test-injected path.
    """
    settings = _enabled_settings(monkeypatch)
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("Caller-supplied transport must skip httpx.Client")
        ),
    )

    def fake_transport(_url: str) -> ProviderCallResult:
        return ProviderCallResult.ok(_RSS_2_FIXTURE_XML)

    provider = create_rss_provider(
        settings=settings, transport=fake_transport
    )
    assert isinstance(provider, RssNewsProvider)


# ---------------------------------------------------------------------------
# Resilience integration -- timeout / circuit breaker / multi-feed isolation
# ---------------------------------------------------------------------------


@respx.mock
def test_provider_timeout_isolated_through_call_with_resilience(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _enabled_settings(monkeypatch, timeout_s=0.2, max_attempts=1)
    respx.get(_FEED_URL).mock(side_effect=httpx.ReadTimeout("simulated"))
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(
        settings=settings, transport=None, monitor=monitor
    )
    out = provider.fetch_recent_news()
    assert out == []
    status = monitor.get_status("rss")
    assert status["failure_count"] == 1
    assert status["last_error_kind"] == "TIMEOUT"


@respx.mock
def test_provider_multi_feed_isolation_one_fails_others_continue(
    monkeypatch: pytest.MonkeyPatch,
):
    feed_urls = f"{_FEED_URL},{_FEED_URL_2}"
    settings = _enabled_settings(
        monkeypatch, feed_urls=feed_urls, max_attempts=1
    )
    respx.get(_FEED_URL).mock(return_value=httpx.Response(503))
    respx.get(_FEED_URL_2).mock(
        return_value=httpx.Response(200, content=_RSS_2_FIXTURE_XML)
    )
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(
        settings=settings, transport=None, monitor=monitor
    )
    out = provider.fetch_recent_news()
    # First feed contributed 0; second feed contributed 2 items.
    assert len(out) == 2
    status = monitor.get_status("rss")
    assert status["call_count"] == 2
    assert status["success_count"] == 1
    assert status["failure_count"] == 1


@respx.mock
def test_provider_circuit_breaker_fast_fails_after_threshold(
    monkeypatch: pytest.MonkeyPatch,
):
    feeds = ",".join(
        f"https://example.com/feed{i}.xml" for i in range(1, 5)
    )
    settings = _enabled_settings(
        monkeypatch, feed_urls=feeds, max_attempts=1
    )
    routes = []
    for i in range(1, 5):
        url = f"https://example.com/feed{i}.xml"
        routes.append(respx.get(url).mock(return_value=httpx.Response(503)))

    monitor = ProviderHealthMonitor()
    monitor.register("rss", failure_threshold=2)
    provider = create_rss_provider(
        settings=settings, transport=None, monitor=monitor
    )
    out = provider.fetch_recent_news()
    assert out == []
    # First two feeds reach the transport; remaining two fast-fail.
    actual_calls = [r.call_count for r in routes]
    assert sum(actual_calls) == 2
    assert (
        monitor.get_status("rss")["status"] == CircuitBreakerState.OPEN.value
    )


# ---------------------------------------------------------------------------
# Secret discipline -- ?api_key=... never logged in plaintext
# ---------------------------------------------------------------------------


@respx.mock
def test_transport_does_not_log_query_secret_on_success(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    settings = _enabled_settings(monkeypatch, feed_urls=_FEED_URL_WITH_SECRET)
    respx.get(_FEED_URL_WITH_SECRET).mock(
        return_value=httpx.Response(200, content=_RSS_2_FIXTURE_XML)
    )
    transport = HttpxRssTransport(settings=settings)
    try:
        with caplog.at_level(logging.DEBUG):
            transport(_FEED_URL_WITH_SECRET)
    finally:
        transport.close()

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _PRIVATE_SECRET not in joined
    # If httpx logged the URL, the key NAME may appear but the value
    # MUST be masked by SensitiveQueryStringFilter.
    if "api_key=" in joined:
        assert "api_key=***" in joined


@respx.mock
def test_provider_failure_log_does_not_leak_query_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    settings = _enabled_settings(
        monkeypatch, feed_urls=_FEED_URL_WITH_SECRET, max_attempts=1
    )
    respx.get(_FEED_URL_WITH_SECRET).mock(return_value=httpx.Response(500))
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(
        settings=settings, transport=None, monitor=monitor
    )
    with caplog.at_level(logging.DEBUG):
        provider.fetch_recent_news()

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _PRIVATE_SECRET not in joined
    # Provider WARNING uses _safe_url_for_log → host + path only.
    status = monitor.get_status("rss")
    assert _PRIVATE_SECRET not in (status["last_error_message"] or "")


@respx.mock
def test_transport_connect_error_does_not_leak_query_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """ConnectError carries URL in __str__; transport stores only class
    name in error_message and caplog stays clean.
    """
    settings = _enabled_settings(
        monkeypatch, feed_urls=_FEED_URL_WITH_SECRET, max_attempts=1
    )
    respx.get(_FEED_URL_WITH_SECRET).mock(
        side_effect=httpx.ConnectError(
            f"Failed to connect to {_FEED_URL_WITH_SECRET}"
        )
    )
    transport = HttpxRssTransport(settings=settings)
    try:
        with caplog.at_level(logging.DEBUG):
            result = transport(_FEED_URL_WITH_SECRET)
    finally:
        transport.close()

    assert result.success is False
    assert result.error_kind == ProviderErrorKind.UNKNOWN
    assert _PRIVATE_SECRET not in (result.error_message or "")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert _PRIVATE_SECRET not in joined


# ---------------------------------------------------------------------------
# Real-network guard
# ---------------------------------------------------------------------------


@respx.mock(assert_all_called=False)
def test_no_unmocked_request_escapes_during_construction(
    monkeypatch: pytest.MonkeyPatch,
):
    """Constructing HttpxRssTransport must perform 0 outbound HTTP."""
    settings = _enabled_settings(monkeypatch)
    transport = HttpxRssTransport(settings=settings)
    transport.close()
