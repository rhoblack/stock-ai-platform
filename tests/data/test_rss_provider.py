"""v0.10 Phase C -- RssNewsProvider tests.

Coverage:

* Settings defaults: ``rss_news_enabled=False``, ``rss_feed_urls=""``,
  ``rss_timeout_s=10.0``, ``rss_max_attempts=3``,
  ``rss_provider_name="rss"``.
* Disabled / not-configured guard: provider construction blocks before
  any transport call.
* RSS 2.0 fixture: title / link / pubDate / description → NewsItemDTO.
* Atom fixture: title / link[@rel=alternate] / updated / summary →
  NewsItemDTO.
* Malformed item skip: missing title / link / pubDate items are skipped
  individually; the rest of the feed survives.
* Forbidden body fields (body / content / full_text / paragraph /
  raw_text / html / 본문 / 원문 / 전문) are stripped *before* the DTO is
  built; the DTO itself never declares them (parametrize assert).
* HTML inside ``<description>`` is tag-stripped.
* Summary truncation enforced at 500 chars.
* Duplicate URLs deduplicated within a single fetch (first wins).
* ``call_with_resilience`` wraps every transport call -- monitor counters
  reflect success / failure; exceptions in the transport are isolated
  to ``ProviderCallResult.fail(UNKNOWN)``.
* Per-feed failure isolation: one feed timing out does not abort the
  others.
* Circuit breaker fast-fails subsequent feeds after the failure
  threshold is reached.
* No real httpx.Client is constructed by any RSS code path
  (monkeypatch guard).
"""

from __future__ import annotations

import logging
from dataclasses import fields as dc_fields
from datetime import datetime, timezone
from typing import Any, Iterable

import pytest

from app.config.settings import Settings
from app.data.dtos import NewsItemDTO
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.provider_resilience import ProviderCallResult, ProviderErrorKind
from app.data.rss_provider import (
    RssNewsProvider,
    RssNotConfiguredError,
    RssParseError,
    create_rss_provider,
    dedup_items,
    parse_feed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enabled_settings(monkeypatch: pytest.MonkeyPatch, *, urls: str | None = None) -> Settings:
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv(
        "RSS_FEED_URLS",
        urls if urls is not None else "https://example.com/feed.xml",
    )
    return Settings()


def _disabled_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("RSS_NEWS_ENABLED", raising=False)
    monkeypatch.delenv("RSS_FEED_URLS", raising=False)
    return Settings()


def _queued_transport(responses: Iterable[ProviderCallResult]):
    queue = list(responses)
    calls: list[str] = []

    def transport(feed_url: str) -> ProviderCallResult:
        calls.append(feed_url)
        if not queue:
            raise RuntimeError("no more queued responses")
        return queue.pop(0)

    return transport, calls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_RSS_2_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Wire</title>
    <link>https://example.com/</link>
    <description>Sample news feed for tests</description>
    <item>
      <title>삼성전자, HBM 공급 확대 발표</title>
      <link>https://example.com/news/005930-hbm-2026-05-04</link>
      <pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>
      <description>HBM &lt;b&gt;공급&lt;/b&gt; 확대로 매출 가시성 개선</description>
      <category>EARNINGS_REPORT</category>
    </item>
    <item>
      <title>SK하이닉스 1분기 실적 발표</title>
      <link>https://example.com/news/000660-earnings-2026-04-30</link>
      <pubDate>Wed, 30 Apr 2026 16:00:00 GMT</pubDate>
      <description>2026년 1분기 영업이익 컨센서스 부합</description>
    </item>
    <!-- malformed: missing link -->
    <item>
      <title>Item without link</title>
      <pubDate>Wed, 30 Apr 2026 16:00:00 GMT</pubDate>
    </item>
    <!-- malformed: missing pubDate -->
    <item>
      <title>No date</title>
      <link>https://example.com/news/no-date</link>
    </item>
  </channel>
</rss>
"""


_ATOM_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Sample Atom Feed</title>
  <link href="https://example.com/atom" rel="self"/>
  <updated>2026-05-04T09:30:00Z</updated>
  <entry>
    <title>NAVER 1분기 매출 발표</title>
    <link href="https://example.com/atom/035420-q1" rel="alternate"/>
    <updated>2026-05-04T09:30:00Z</updated>
    <summary>매출 분기별 흐름 (sample)</summary>
    <category term="NEWS"/>
  </entry>
  <entry>
    <title>두 번째 atom 항목</title>
    <link href="https://example.com/atom/second" rel="alternate"/>
    <published>2026-05-03T10:00:00Z</published>
    <summary>두 번째 요약</summary>
  </entry>
</feed>
"""


_FORBIDDEN_FIXTURE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Forbidden Test</title>
    <item>
      <title>Item with forbidden fields</title>
      <link>https://example.com/forbidden/1</link>
      <pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>
      <description>safe summary &lt;p&gt;tag stripped&lt;/p&gt;</description>
      <body>full body content that should never reach DTO</body>
      <content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/">html_body</content:encoded>
      <full_text>full text dump</full_text>
    </item>
  </channel>
</rss>
"""


_DUP_URL_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Dup Test</title>
    <item>
      <title>First copy</title>
      <link>https://example.com/dup/1</link>
      <pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>
    </item>
    <item>
      <title>Second copy (same URL)</title>
      <link>https://example.com/dup/1</link>
      <pubDate>Mon, 04 May 2026 10:30:00 GMT</pubDate>
    </item>
    <item>
      <title>Third (different URL)</title>
      <link>https://example.com/dup/2</link>
      <pubDate>Mon, 04 May 2026 11:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


def test_settings_rss_news_enabled_default_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RSS_NEWS_ENABLED", raising=False)
    assert Settings().rss_news_enabled is False


def test_settings_rss_feed_urls_default_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RSS_FEED_URLS", raising=False)
    assert Settings().rss_feed_urls == ""


def test_settings_rss_runtime_defaults(monkeypatch: pytest.MonkeyPatch):
    for var in ("RSS_TIMEOUT_S", "RSS_MAX_ATTEMPTS", "RSS_PROVIDER_NAME"):
        monkeypatch.delenv(var, raising=False)
    s = Settings()
    assert s.rss_timeout_s == 10.0
    assert s.rss_max_attempts == 3
    assert s.rss_provider_name == "rss"


# ---------------------------------------------------------------------------
# Disabled guard
# ---------------------------------------------------------------------------


def test_disabled_rss_raises_not_configured(monkeypatch: pytest.MonkeyPatch):
    settings = _disabled_settings(monkeypatch)
    transport, calls = _queued_transport([])
    with pytest.raises(RssNotConfiguredError):
        RssNewsProvider(settings=settings, transport=transport)
    assert calls == []


def test_disabled_rss_factory_raises(monkeypatch: pytest.MonkeyPatch):
    settings = _disabled_settings(monkeypatch)
    transport, _ = _queued_transport([])
    with pytest.raises(RssNotConfiguredError):
        create_rss_provider(settings=settings, transport=transport)


def test_enabled_but_no_urls_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv("RSS_FEED_URLS", "")
    settings = Settings()
    transport, _ = _queued_transport([])
    with pytest.raises(RssNotConfiguredError):
        RssNewsProvider(settings=settings, transport=transport)


def test_enabled_without_transport_raises(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    with pytest.raises(RssNotConfiguredError):
        RssNewsProvider(settings=settings, transport=None)


# ---------------------------------------------------------------------------
# RSS 2.0 parser
# ---------------------------------------------------------------------------


def test_parse_rss_2_basic():
    items = parse_feed(_RSS_2_FIXTURE)
    # 4 raw items, 2 valid (other 2 missing link / pubDate respectively)
    assert len(items) == 2
    titles = [i.title for i in items]
    assert "삼성전자, HBM 공급 확대 발표" in titles
    assert "SK하이닉스 1분기 실적 발표" in titles
    for item in items:
        assert isinstance(item, NewsItemDTO)
        assert item.provider == "rss"
        assert item.url.startswith("https://")
        assert item.published_at.tzinfo is timezone.utc
        assert item.source == "Sample Wire"


def test_parse_rss_2_strips_html_in_summary():
    items = parse_feed(_RSS_2_FIXTURE)
    samsung = [i for i in items if "삼성전자" in i.title][0]
    assert samsung.summary == "HBM 공급 확대로 매출 가시성 개선"
    assert "<b>" not in (samsung.summary or "")
    assert "</b>" not in (samsung.summary or "")


def test_parse_rss_2_category_per_item_overrides_default():
    items = parse_feed(_RSS_2_FIXTURE, feed_category="DEFAULT_CAT")
    samsung = [i for i in items if "삼성전자" in i.title][0]
    sk = [i for i in items if "SK하이닉스" in i.title][0]
    assert samsung.category == "EARNINGS_REPORT"  # per-item wins
    assert sk.category == "DEFAULT_CAT"  # falls back to feed default


def test_parse_rss_2_explicit_feed_source_overrides_channel_title():
    items = parse_feed(_RSS_2_FIXTURE, feed_source="OverrideSource")
    assert all(i.source == "OverrideSource" for i in items)


# ---------------------------------------------------------------------------
# Atom parser
# ---------------------------------------------------------------------------


def test_parse_atom_basic():
    items = parse_feed(_ATOM_FIXTURE)
    assert len(items) == 2
    naver = items[0]
    assert naver.title == "NAVER 1분기 매출 발표"
    assert naver.url == "https://example.com/atom/035420-q1"
    assert naver.published_at == datetime(2026, 5, 4, 9, 30, tzinfo=timezone.utc)
    assert naver.category == "NEWS"
    assert naver.source == "Sample Atom Feed"
    second = items[1]
    assert second.published_at == datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc)


def test_parse_atom_uses_published_when_updated_missing():
    payload = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>only-published</title>
  <entry>
    <title>Only published</title>
    <link href="https://example.com/only-pub" rel="alternate"/>
    <published>2026-01-02T03:04:05Z</published>
  </entry>
</feed>
"""
    items = parse_feed(payload)
    assert len(items) == 1
    assert items[0].published_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Malformed / unknown root
# ---------------------------------------------------------------------------


def test_parse_invalid_xml_raises():
    with pytest.raises(RssParseError):
        parse_feed("<<not xml>>")


def test_parse_unknown_root_raises():
    with pytest.raises(RssParseError):
        parse_feed("<unknown><item/></unknown>")


def test_parse_rss_missing_channel_returns_empty():
    payload = "<?xml version='1.0'?><rss version='2.0'></rss>"
    assert parse_feed(payload) == []


def test_parse_atom_empty_returns_empty():
    payload = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"/>"""
    assert parse_feed(payload) == []


# ---------------------------------------------------------------------------
# Forbidden body fields are stripped
# ---------------------------------------------------------------------------


def test_parse_forbidden_body_fields_dropped_from_dto_shape():
    items = parse_feed(_FORBIDDEN_FIXTURE_RSS)
    assert len(items) == 1
    item = items[0]
    # Sanity: summary kept, HTML stripped
    assert item.summary == "safe summary tag stripped"
    # The DTO simply has no body / full_text / paragraph fields:
    field_names = {f.name for f in dc_fields(item)}
    assert {"body", "full_text", "fulltext", "paragraph", "raw_text", "html_body", "html", "본문", "원문", "전문"}.isdisjoint(
        field_names
    )


_BODY_FIELD_NAMES = {
    "body",
    "content",
    "content_encoded",
    "full_text",
    "fulltext",
    "paragraph",
    "raw_text",
    "rawtext",
    "html",
    "html_body",
    "description_full",
    "본문",
    "원문",
    "전문",
}


def test_news_item_dto_has_no_body_fields():
    names = {f.name for f in dc_fields(NewsItemDTO)}
    overlap = names & _BODY_FIELD_NAMES
    assert not overlap, f"NewsItemDTO carries forbidden body field(s): {overlap}"


def test_summary_truncated_to_500_chars():
    long_text = "A" * 1200
    payload = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item><title>long</title>
<link>https://example.com/long</link>
<pubDate>Mon, 04 May 2026 09:30:00 GMT</pubDate>
<description>{long_text}</description>
</item></channel></rss>"""
    items = parse_feed(payload)
    assert len(items) == 1
    assert items[0].summary is not None
    assert len(items[0].summary) == 500


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def test_dedup_items_first_wins():
    items = parse_feed(_DUP_URL_FIXTURE)
    # 3 raw items, 2 unique URLs
    deduped = dedup_items(items)
    assert len(deduped) == 2
    titles = [d.title for d in deduped]
    assert "First copy" in titles  # first wins
    assert "Second copy (same URL)" not in titles
    assert "Third (different URL)" in titles


# ---------------------------------------------------------------------------
# Provider integration -- transport injection + monitor wiring
# ---------------------------------------------------------------------------


def test_provider_fetches_single_feed(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, calls = _queued_transport([ProviderCallResult.ok(_RSS_2_FIXTURE)])
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_news(limit=10)
    assert len(out) == 2
    assert calls == ["https://example.com/feed.xml"]
    assert monitor.get_status("rss")["success_count"] == 1


def test_provider_dedup_across_feeds(monkeypatch: pytest.MonkeyPatch):
    """Two feeds returning overlapping URLs -- dedup is global."""
    settings = _enabled_settings(
        monkeypatch,
        urls="https://example.com/feed1.xml,https://example.com/feed2.xml",
    )
    transport, _ = _queued_transport(
        [
            ProviderCallResult.ok(_DUP_URL_FIXTURE),
            ProviderCallResult.ok(_DUP_URL_FIXTURE),
        ]
    )
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_news(limit=100)
    # Each feed yields 3 items / 2 unique URLs -- merged set still has 2.
    assert len(out) == 2
    assert {item.url for item in out} == {
        "https://example.com/dup/1",
        "https://example.com/dup/2",
    }


def test_provider_isolates_failed_feed(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(
        monkeypatch,
        urls="https://example.com/bad.xml,https://example.com/good.xml",
    )
    monkeypatch.setenv("RSS_MAX_ATTEMPTS", "1")
    settings = Settings()
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv(
        "RSS_FEED_URLS", "https://example.com/bad.xml,https://example.com/good.xml"
    )
    settings = Settings()

    transport, _ = _queued_transport(
        [
            ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "503"),
            ProviderCallResult.ok(_RSS_2_FIXTURE),
        ]
    )
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_news(limit=10)
    # Bad feed contributed 0; good feed contributed 2.
    assert len(out) == 2
    status = monitor.get_status("rss")
    assert status["call_count"] == 2
    assert status["failure_count"] == 1
    assert status["success_count"] == 1


def test_provider_timeout_isolated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv("RSS_FEED_URLS", "https://example.com/feed.xml")
    monkeypatch.setenv("RSS_MAX_ATTEMPTS", "1")
    settings = Settings()
    transport, _ = _queued_transport(
        [ProviderCallResult.fail(ProviderErrorKind.TIMEOUT, "timed out")]
    )
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_news()
    assert out == []
    status = monitor.get_status("rss")
    assert status["last_error_kind"] == "TIMEOUT"


def test_provider_exception_in_transport_isolated(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv("RSS_FEED_URLS", "https://example.com/feed.xml")
    monkeypatch.setenv("RSS_MAX_ATTEMPTS", "1")
    settings = Settings()

    def boom(_url: str) -> ProviderCallResult:
        raise RuntimeError("connection reset by peer")

    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(settings=settings, transport=boom, monitor=monitor)
    out = provider.fetch_recent_news()
    assert out == []  # never raises
    status = monitor.get_status("rss")
    assert status["last_error_kind"] == "UNKNOWN"


def test_provider_circuit_breaker_trips(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv(
        "RSS_FEED_URLS",
        "https://example.com/a.xml,https://example.com/b.xml,"
        "https://example.com/c.xml,https://example.com/d.xml",
    )
    monkeypatch.setenv("RSS_MAX_ATTEMPTS", "1")
    settings = Settings()

    transport_calls: list[str] = []

    def fail_transport(url: str) -> ProviderCallResult:
        transport_calls.append(url)
        return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "down")

    monitor = ProviderHealthMonitor()
    monitor.register("rss", failure_threshold=2)
    provider = RssNewsProvider(
        settings=settings, transport=fail_transport, monitor=monitor
    )
    out = provider.fetch_recent_news()
    assert out == []
    # Breaker tripped after the second failure -- feeds c / d never reach
    # the transport.
    assert transport_calls == [
        "https://example.com/a.xml",
        "https://example.com/b.xml",
    ]
    assert monitor.get_status("rss")["status"] == "OPEN"


def test_provider_since_filter(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, _ = _queued_transport([ProviderCallResult.ok(_RSS_2_FIXTURE)])
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    cutoff = datetime(2026, 5, 1, tzinfo=timezone.utc)
    out = provider.fetch_recent_news(since=cutoff)
    # Only the May 4 item passes the cutoff (Apr 30 is filtered out).
    assert len(out) == 1
    assert "삼성전자" in out[0].title


def test_provider_limit_caps_result(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, _ = _queued_transport([ProviderCallResult.ok(_RSS_2_FIXTURE)])
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    out = provider.fetch_recent_news(limit=1)
    assert len(out) == 1


def test_factory_creates_provider(monkeypatch: pytest.MonkeyPatch):
    settings = _enabled_settings(monkeypatch)
    transport, _ = _queued_transport([])
    monitor = ProviderHealthMonitor()
    provider = create_rss_provider(
        settings=settings, transport=transport, monitor=monitor
    )
    assert isinstance(provider, RssNewsProvider)


# ---------------------------------------------------------------------------
# No-network guard
# ---------------------------------------------------------------------------


def test_no_httpx_client_constructed(monkeypatch: pytest.MonkeyPatch):
    """Constructing / using an RSS provider must never instantiate httpx.Client.

    The Phase D httpx-backed transport is deliberately out of scope -- tests
    use a fixture transport, and we monkeypatch httpx.Client to raise on
    construction to enforce the boundary.
    """
    settings = _enabled_settings(monkeypatch)

    import httpx as _httpx  # noqa: PLC0415

    def boom(*_a: Any, **_kw: Any):
        raise AssertionError("RSS provider must not construct httpx.Client")

    monkeypatch.setattr(_httpx, "Client", boom)
    transport, _ = _queued_transport([ProviderCallResult.ok(_RSS_2_FIXTURE)])
    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(
        settings=settings, transport=transport, monitor=monitor
    )
    provider.fetch_recent_news(limit=10)


# ---------------------------------------------------------------------------
# Logging discipline -- secrets must never leak via the RSS provider logs
# ---------------------------------------------------------------------------


def test_provider_log_strips_url_query_secrets(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """A feed URL that embeds an API-key query parameter must NOT leak the
    secret into the WARN log on fetch failure -- only the scheme + host +
    path survive ``_safe_url_for_log``.
    """
    monkeypatch.setenv("RSS_NEWS_ENABLED", "true")
    monkeypatch.setenv(
        "RSS_FEED_URLS", "https://example.com/feed.xml?api_key=SECRETXYZ"
    )
    monkeypatch.setenv("RSS_MAX_ATTEMPTS", "1")
    settings = Settings()

    def fail(_url: str) -> ProviderCallResult:
        return ProviderCallResult.fail(ProviderErrorKind.SERVER_ERROR, "boom")

    monitor = ProviderHealthMonitor()
    provider = RssNewsProvider(settings=settings, transport=fail, monitor=monitor)
    with caplog.at_level(logging.WARNING):
        provider.fetch_recent_news()
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "SECRETXYZ" not in joined
    assert "api_key" not in joined
    # The host + path remain visible so the operator can still locate the
    # failing feed.
    assert "example.com/feed.xml" in joined


def test_safe_url_for_log_drops_query_and_fragment():
    from app.data.rss_provider import _safe_url_for_log

    assert (
        _safe_url_for_log("https://example.com/feed.xml?token=abc#frag")
        == "https://example.com/feed.xml"
    )
    assert (
        _safe_url_for_log("https://user:pass@example.com/path")
        == "https://user:pass@example.com/path"
        # netloc-embedded credentials remain (they are not query-string
        # leakage and are part of RFC 3986 authority).  Operators must
        # not put secrets in netloc.
    )
