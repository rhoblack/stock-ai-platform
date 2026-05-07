"""v0.10 Phase C -- RSS / News provider skeleton.

PURPOSE
-------
Implements :class:`~app.data.interfaces.NewsProviderInterface` on top of a
transport-injected RSS / Atom XML loader.  Tests pass mock XML strings; the
real httpx-backed transport is deferred to Phase D, mirroring the
Phase B DART pattern.

POLICY (v0.5 / v0.10 cycle-wide)
--------------------------------
* ``Settings.rss_news_enabled`` defaults to ``False``.  When false the
  factory raises :class:`RssNotConfiguredError` and any scheduler that
  would otherwise call :class:`RssNewsProvider` short-circuits with no
  HTTP fetch.
* ``Settings.rss_feed_urls`` is a comma-separated list of explicit feed
  URLs the operator has reviewed and approved.  No auto-discovery, no
  follow-up crawling, no body-paragraph fetching -- only metadata fields
  on the immediate item:

    title / url / provider / published_at / source / category / summary

  Body / paragraph / full_text / raw_text / html_body / 본문 / 원문 / 전문
  fields are stripped *before* the DTO is constructed.

* Duplicate URLs are deduplicated within a single ``fetch_recent_news``
  call.  Cross-call duplicates are blocked at the database boundary by
  the existing ``news_items.url`` UNIQUE constraint -- a callsite that
  ingests RSS items into ``NewsItemRepository`` performs upsert-ignore
  on conflict.

* Every transport call goes through
  :func:`app.data.provider_health_monitor.call_with_resilience` so the
  Phase A retry / circuit-breaker / failure-isolation primitives apply
  automatically.  ``call_with_resilience`` never raises -- network
  errors arrive as ``ProviderCallResult.fail(...)`` and are isolated to
  the affected feed without aborting the rest of the fetch.

ERROR TAXONOMY
--------------
The transport callable returns ``ProviderCallResult`` whose ``value`` is
the raw XML body (``str`` or ``bytes``).  Tests pass a closure over
fixture XML; the Phase D httpx transport will map HTTP / network errors
to ``ProviderErrorKind`` exactly like the DART transport.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from app.config.settings import Settings, get_settings
from app.data.dtos import NewsItemDTO
from app.data.interfaces import NewsProviderInterface
from app.data.provider_health_monitor import (
    ProviderHealthMonitor,
    call_with_resilience,
    get_health_monitor,
)
from app.data.provider_resilience import ProviderCallResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RssProviderError(RuntimeError):
    """Base class for RSS provider failures."""


class RssNotConfiguredError(RssProviderError):
    """Raised when ``rss_news_enabled=False`` or no feed URLs were configured.

    The factory inspects ``Settings.rss_news_enabled`` /
    ``Settings.rss_feed_urls`` *before* instantiating the provider; jobs
    catch this and skip without falling back to a fake.
    """


class RssParseError(RssProviderError):
    """Raised when the parser cannot interpret a feed payload."""


# ---------------------------------------------------------------------------
# Forbidden body fields (defence in depth)
# ---------------------------------------------------------------------------

# Mirrors the Phase B DART policy.  Any payload that includes one of these
# keys (case-insensitive on ASCII; Korean keys matched as-is) is dropped
# before the DTO is constructed.  The DTO itself never declares these
# fields, so the strip is a regression guard against future schema
# additions.
_FORBIDDEN_BODY_FIELDS: frozenset[str] = frozenset(
    {
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
)


def _strip_forbidden(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``payload`` without any forbidden body field."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _FORBIDDEN_BODY_FIELDS:
            logger.debug("dropping forbidden RSS field key=%s", key)
            continue
        out[key] = value
    return out


_SUMMARY_MAX_LEN = 500
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _safe_url_for_log(url: str) -> str:
    """Return ``url`` with query string + fragment stripped for logging.

    Some private RSS feeds embed an API key in the query string
    (``?api_key=...`` / ``?token=...``).  We never echo those into
    structured logs -- only the scheme + host + path survive.
    """
    try:
        parts = urlsplit(url)
    except (ValueError, TypeError):
        return "<unparseable-url>"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _short_summary(text: str | None) -> str | None:
    """Strip HTML tags and truncate to ``_SUMMARY_MAX_LEN`` characters.

    RSS ``<description>`` items frequently contain inline HTML.  We treat
    even the short description as untrusted and:

      1. Remove all ``<...>`` tags (no body / paragraph leak).
      2. Collapse whitespace.
      3. Truncate to the per-record max.
    """
    if text is None:
        return None
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = " ".join(cleaned.split()).strip()
    if not cleaned:
        return None
    if len(cleaned) > _SUMMARY_MAX_LEN:
        return cleaned[:_SUMMARY_MAX_LEN]
    return cleaned


def _parse_pub_date(raw: str | None) -> datetime | None:
    """Parse an RFC 822 (RSS ``pubDate``) or ISO 8601 (Atom ``updated``).

    Returns timezone-aware UTC ``datetime`` on success.  Returns ``None``
    when ``raw`` is missing or unparseable -- the caller decides whether
    that disqualifies the item (RSS items without a publish date are
    skipped).
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    # RFC 822 -- e.g. "Sat, 04 May 2026 09:30:00 GMT".
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        # ISO 8601 -- e.g. "2026-05-04T09:30:00Z".
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _atom_tag(name: str) -> str:
    return f"{_ATOM_NS}{name}"


# ---------------------------------------------------------------------------
# RSS 2.0 / Atom parsers
# ---------------------------------------------------------------------------


def _xml_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    text = element.text
    if text is None:
        return None
    text = text.strip()
    return text or None


def _parse_rss_item(
    item: ET.Element,
    *,
    feed_source: str | None,
    feed_category: str | None,
) -> NewsItemDTO | None:
    """Map a single ``<item>`` element to NewsItemDTO.

    Returns ``None`` when essential fields are missing rather than
    raising -- the caller filters the list and a malformed item should
    not abort the whole feed.
    """
    title = _xml_text(item.find("title"))
    url = _xml_text(item.find("link"))
    pub = _xml_text(item.find("pubDate"))

    if not (title and url):
        return None

    published_at = _parse_pub_date(pub)
    if published_at is None:
        return None

    # Defence in depth: capture only the description text (no full body).
    summary_raw = _xml_text(item.find("description"))
    summary = _short_summary(summary_raw)

    # Optional category override per item.
    cat_el = item.find("category")
    category = _xml_text(cat_el) or feed_category

    return NewsItemDTO(
        title=title,
        url=url,
        provider="rss",
        published_at=published_at,
        symbol=None,
        source=feed_source,
        category=category,
        sentiment_label=None,
        summary=summary,
    )


def _parse_atom_entry(
    entry: ET.Element,
    *,
    feed_source: str | None,
    feed_category: str | None,
) -> NewsItemDTO | None:
    title = _xml_text(entry.find(_atom_tag("title")))

    # Atom <link href="..."/>; the first rel="alternate" wins.
    url: str | None = None
    for link in entry.findall(_atom_tag("link")):
        href = link.attrib.get("href")
        if not href:
            continue
        rel = link.attrib.get("rel", "alternate")
        if rel == "alternate":
            url = href
            break
        if url is None:
            url = href

    pub = (
        _xml_text(entry.find(_atom_tag("updated")))
        or _xml_text(entry.find(_atom_tag("published")))
    )

    if not (title and url):
        return None

    published_at = _parse_pub_date(pub)
    if published_at is None:
        return None

    summary_raw = _xml_text(entry.find(_atom_tag("summary")))
    # Atom <content> is body-shaped -- never persist it.  We deliberately
    # do not even read it.
    summary = _short_summary(summary_raw)

    cat_el = entry.find(_atom_tag("category"))
    category = (cat_el.attrib.get("term") if cat_el is not None else None) or feed_category

    return NewsItemDTO(
        title=title,
        url=url,
        provider="rss",
        published_at=published_at,
        symbol=None,
        source=feed_source,
        category=category,
        sentiment_label=None,
        summary=summary,
    )


def parse_feed(
    payload: str | bytes,
    *,
    feed_source: str | None = None,
    feed_category: str | None = None,
) -> list[NewsItemDTO]:
    """Parse an RSS 2.0 or Atom XML payload into NewsItemDTOs.

    Format detection is structural -- the root element tag determines the
    branch (``rss`` → RSS 2.0, ``feed`` → Atom; namespace-aware on Atom).

    Malformed items are skipped individually; the rest of the feed is
    still returned.
    """
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RssParseError(f"invalid XML: {exc}") from exc

    items: list[NewsItemDTO] = []

    if root.tag.endswith("rss") or root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            return []
        if feed_source is None:
            feed_source = _xml_text(channel.find("title"))
        for item in channel.findall("item"):
            dto = _parse_rss_item(
                item,
                feed_source=feed_source,
                feed_category=feed_category,
            )
            if dto is not None:
                items.append(dto)
        return items

    if root.tag == _atom_tag("feed") or root.tag.endswith("}feed") or root.tag == "feed":
        if feed_source is None:
            feed_source = _xml_text(root.find(_atom_tag("title")))
        for entry in root.findall(_atom_tag("entry")):
            dto = _parse_atom_entry(
                entry,
                feed_source=feed_source,
                feed_category=feed_category,
            )
            if dto is not None:
                items.append(dto)
        return items

    raise RssParseError(f"unrecognised feed root: {root.tag!r}")


def dedup_items(items: Iterable[NewsItemDTO]) -> list[NewsItemDTO]:
    """Return ``items`` with duplicate URLs removed (first wins).

    Mirrors ``news_items.url`` UNIQUE so the in-memory dedup matches the
    DB-side upsert-ignore behaviour at the collector boundary.
    """
    seen: set[str] = set()
    out: list[NewsItemDTO] = []
    for item in items:
        if not item.url or item.url in seen:
            continue
        seen.add(item.url)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Transport contract
# ---------------------------------------------------------------------------

# A transport is a callable ``(feed_url) -> ProviderCallResult`` whose
# ``value`` (on success) is the raw XML body as ``str`` or ``bytes``.
# Tests pass a closure over fixture data; the real httpx transport is
# Phase D.
RssTransport = Callable[[str], ProviderCallResult]


# ---------------------------------------------------------------------------
# Provider config + factory
# ---------------------------------------------------------------------------


@dataclass
class _RssConfig:
    feed_urls: tuple[str, ...]
    timeout_s: float
    max_attempts: int
    provider_name: str

    @classmethod
    def from_settings(cls, settings: Settings) -> "_RssConfig":
        urls = tuple(
            url.strip()
            for url in (settings.rss_feed_urls or "").split(",")
            if url.strip()
        )
        return cls(
            feed_urls=urls,
            timeout_s=settings.rss_timeout_s,
            max_attempts=settings.rss_max_attempts,
            provider_name=settings.rss_provider_name,
        )


def _check_enabled(settings: Settings) -> None:
    if not settings.rss_news_enabled:
        raise RssNotConfiguredError(
            "RSS_NEWS_ENABLED is false; refusing to instantiate RssNewsProvider"
        )
    if not (settings.rss_feed_urls or "").strip():
        raise RssNotConfiguredError(
            "RSS_FEED_URLS is empty; operator must list reviewed feed URLs"
        )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class RssNewsProvider(NewsProviderInterface):
    """RSS / Atom news provider skeleton.

    Each registered feed URL is fetched through ``call_with_resilience``.
    Per-feed failures are isolated; the rest of the feeds still produce
    items.  Dedup runs across the merged result (URL-based, first wins).
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: RssTransport | None = None,
        monitor: ProviderHealthMonitor | None = None,
        feed_categories: Mapping[str, str] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        _check_enabled(self._settings)
        self._config = _RssConfig.from_settings(self._settings)
        if transport is None:
            raise RssNotConfiguredError(
                "RSS transport is required -- the real httpx transport is "
                "deferred to Phase D; tests must inject a fixture transport."
            )
        self._transport = transport
        self._monitor = monitor or get_health_monitor()
        self._monitor.register(self._config.provider_name)
        self._feed_categories = dict(feed_categories or {})

    # ------------------------------------------------------------------

    def _fetch_one(self, feed_url: str) -> list[NewsItemDTO]:
        """Fetch + parse a single feed.  Failures return an empty list."""
        result = call_with_resilience(
            self._config.provider_name,
            lambda: self._transport(feed_url),
            monitor=self._monitor,
            max_attempts=self._config.max_attempts,
        )
        if not result.success or result.value is None:
            logger.warning(
                "RSS feed fetch failed url=%s kind=%s",
                _safe_url_for_log(feed_url),
                result.error_kind,
            )
            return []
        try:
            return parse_feed(
                result.value,
                feed_category=self._feed_categories.get(feed_url),
            )
        except RssParseError as exc:
            logger.warning(
                "RSS feed parse error url=%s error=%s",
                _safe_url_for_log(feed_url),
                exc,
            )
            return []

    # ------------------------------------------------------------------

    def fetch_recent_news(
        self,
        *,
        symbols: list[str] | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItemDTO]:
        """Fetch + parse + dedup all configured feeds.

        ``symbols`` is accepted for interface compatibility but RSS feeds
        rarely tag items with stock symbols -- it is applied as a
        post-filter only when an item's ``symbol`` field is populated by
        a downstream enrichment step.

        ``since`` filters out items older than the cutoff before dedup.
        ``limit`` caps the merged result.
        """
        merged: list[NewsItemDTO] = []
        for feed_url in self._config.feed_urls:
            merged.extend(self._fetch_one(feed_url))

        merged = dedup_items(merged)

        if since is not None:
            merged = [m for m in merged if m.published_at >= since]

        if symbols:
            symbol_set = set(symbols)
            merged = [m for m in merged if m.symbol is None or m.symbol in symbol_set]

        if limit and len(merged) > limit:
            merged = merged[:limit]
        return merged


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_rss_provider(
    *,
    settings: Settings | None = None,
    transport: RssTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    feed_categories: Mapping[str, str] | None = None,
) -> RssNewsProvider:
    """Construct a RssNewsProvider after verifying the operator opted in."""
    settings = settings or get_settings()
    _check_enabled(settings)
    return RssNewsProvider(
        settings=settings,
        transport=transport,
        monitor=monitor,
        feed_categories=feed_categories,
    )


__all__ = [
    "RssProviderError",
    "RssNotConfiguredError",
    "RssParseError",
    "RssNewsProvider",
    "RssTransport",
    "create_rss_provider",
    "dedup_items",
    "parse_feed",
]
