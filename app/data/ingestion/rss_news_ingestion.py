"""v0.12 Phase A -- RSS news ingestion adapter.

Wires the v0.11 ``RssNewsProvider`` (httpx-backed in production,
respx-mock-backed in tests) through the existing v0.5 ``NewsCollector``
into ``news_items``.  Default-OFF via
``Settings.provider_data_ingestion_enabled``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.collectors.news_collector import NewsCollector, NewsCollectorResult
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.repositories.news_items import NewsItemRepository
from app.data.rss_provider import (
    RssNotConfiguredError,
    RssTransport,
    create_rss_provider,
)


@dataclass(frozen=True)
class RssNewsIngestionResult:
    """Outcome of one ``ingest_rss_news`` call."""

    skipped_disabled: bool = False
    fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0
    truncated_summaries: int = 0

    @classmethod
    def disabled(cls) -> "RssNewsIngestionResult":
        return cls(skipped_disabled=True)

    @classmethod
    def from_collector(cls, result: NewsCollectorResult) -> "RssNewsIngestionResult":
        return cls(
            skipped_disabled=False,
            fetched=result.fetched,
            inserted=result.inserted,
            skipped_duplicates=result.skipped_duplicates,
            truncated_summaries=result.truncated_summaries,
        )


def ingest_rss_news(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: RssTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: Sequence[str] | None = None,
    since: datetime | None = None,
    limit: int = 50,
) -> RssNewsIngestionResult:
    """Ingest RSS / Atom news metadata into ``news_items``.

    Soft-skips when either ``provider_data_ingestion_enabled`` is False
    or RSS is not enabled / configured (``RssNotConfiguredError``).
    """
    settings = settings or get_settings()
    if not settings.provider_data_ingestion_enabled:
        return RssNewsIngestionResult.disabled()

    try:
        provider = create_rss_provider(
            settings=settings, transport=transport, monitor=monitor
        )
    except RssNotConfiguredError:
        return RssNewsIngestionResult.disabled()

    collector = NewsCollector(provider, NewsItemRepository(session))
    result = collector.collect_recent(
        symbols=list(symbols) if symbols is not None else None,
        since=since,
        limit=limit,
    )
    return RssNewsIngestionResult.from_collector(result)


__all__ = [
    "RssNewsIngestionResult",
    "ingest_rss_news",
]
