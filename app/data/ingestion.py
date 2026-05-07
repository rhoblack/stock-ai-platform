"""v0.12 Phase A -- Provider data ingestion adapters.

Connects v0.11 DART / RSS transport results to the existing DB tables via the
v0.5/v0.6 collector / repository layer.  All four entry points check the
master switch (``Settings.provider_data_ingestion_enabled``, default False)
before touching any provider, repository, or HTTP client.

Design notes:
  * DART adapters delegate to :func:`~app.data.dart_provider.create_dart_providers`
    so the production httpx transport is auto-injected and
    ``DartNotConfiguredError`` from missing config is caught centrally.
  * RSS adapter delegates to :func:`~app.data.rss_provider.create_rss_provider`
    for the same reasons.
  * ``data_source`` on every DTO is a runtime-only provenance tag (no DB
    column in v0.12 Phase A); it is filtered out via ``asdict`` + ``pop``
    before the repository upsert sees it -- matching the pattern already
    established in FundamentalCsvImporter / EarningsCsvImporter.
  * ScoringEngine / HoldingCheckEngine weights are NOT touched here.  The
    scoring formulas are the v0.5/v0.6 originals; only the data inputs
    change (fake → real) once an operator opts in.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.collectors.disclosure_collector import DisclosureCollector
from app.data.collectors.news_collector import NewsCollector
from app.data.dart_provider import (
    DartNotConfiguredError,
    DartTransport,
    create_dart_providers,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.repositories.earnings_events import EarningsEventRepository
from app.data.repositories.fundamental_snapshots import FundamentalSnapshotRepository
from app.data.repositories.news_items import NewsItemRepository
from app.data.rss_provider import (
    RssNotConfiguredError,
    RssTransport,
    create_rss_provider,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DartDisclosureIngestionResult:
    """Result of one ingest_dart_disclosures() call."""

    skipped_disabled: bool
    fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0


@dataclass(frozen=True)
class RssNewsIngestionResult:
    """Result of one ingest_rss_news() call."""

    skipped_disabled: bool
    fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0


@dataclass(frozen=True)
class DartFundamentalIngestionResult:
    """Result of one ingest_dart_fundamentals() call."""

    skipped_disabled: bool
    fetched: int = 0
    upserted: int = 0


@dataclass(frozen=True)
class DartEarningsIngestionResult:
    """Result of one ingest_dart_earnings() call."""

    skipped_disabled: bool
    fetched: int = 0
    upserted: int = 0


# ---------------------------------------------------------------------------
# Internal helpers -- strip runtime-only data_source before repo upsert
# ---------------------------------------------------------------------------


def _fund_kwargs(dto: Any) -> dict[str, Any]:
    payload = asdict(dto)
    payload.pop("data_source", None)
    return payload


def _earn_kwargs(dto: Any) -> dict[str, Any]:
    payload = asdict(dto)
    payload.pop("data_source", None)
    return payload


# ---------------------------------------------------------------------------
# Public adapters
# ---------------------------------------------------------------------------


def ingest_dart_disclosures(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: list[str] | None = None,
    limit: int = 50,
) -> DartDisclosureIngestionResult:
    """Fetch DART disclosures and persist into ``news_items`` via DisclosureCollector.

    Short-circuits with ``skipped_disabled=True`` when:
    * ``settings.provider_data_ingestion_enabled=False`` (master switch, default)
    * DART not configured (``dart_enabled=False`` / ``dart_api_key`` empty)

    All DisclosureItemDTOs are tagged ``data_source="PROVIDER"`` by the DART
    parser; the collector classifies them with the existing keyword taxonomy
    and upserts into news_items keyed by URL.
    """
    _settings = settings or get_settings()
    if not _settings.provider_data_ingestion_enabled:
        return DartDisclosureIngestionResult(skipped_disabled=True)

    try:
        providers = create_dart_providers(
            settings=_settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError as exc:
        logger.debug("DART disclosures ingestion skipped: %s", exc)
        return DartDisclosureIngestionResult(skipped_disabled=True)

    repo = NewsItemRepository(session)
    collector = DisclosureCollector(provider=providers["disclosures"], repository=repo)
    result = collector.collect_recent(symbols=symbols, limit=limit)
    return DartDisclosureIngestionResult(
        skipped_disabled=False,
        fetched=result.fetched,
        inserted=result.inserted,
        skipped_duplicates=result.skipped_duplicates,
    )


def ingest_rss_news(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: RssTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: list[str] | None = None,
    limit: int = 50,
) -> RssNewsIngestionResult:
    """Fetch RSS news and persist into ``news_items`` via NewsCollector.

    Short-circuits with ``skipped_disabled=True`` when:
    * ``settings.provider_data_ingestion_enabled=False`` (master switch, default)
    * RSS not configured (``rss_news_enabled=False`` / ``rss_feed_urls`` empty)

    NewsItemDTOs arrive tagged ``data_source="PROVIDER"`` from the RSS parser.
    The collector upserts into news_items keyed by URL.
    """
    _settings = settings or get_settings()
    if not _settings.provider_data_ingestion_enabled:
        return RssNewsIngestionResult(skipped_disabled=True)

    try:
        provider = create_rss_provider(
            settings=_settings, transport=transport, monitor=monitor
        )
    except RssNotConfiguredError as exc:
        logger.debug("RSS news ingestion skipped: %s", exc)
        return RssNewsIngestionResult(skipped_disabled=True)

    repo = NewsItemRepository(session)
    collector = NewsCollector(provider=provider, repository=repo)
    result = collector.collect_recent(symbols=symbols, limit=limit)
    return RssNewsIngestionResult(
        skipped_disabled=False,
        fetched=result.fetched,
        inserted=result.inserted,
        skipped_duplicates=result.skipped_duplicates,
    )


def ingest_dart_fundamentals(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: list[str],
    fiscal_year: int,
    fiscal_quarter: int | None = None,
) -> DartFundamentalIngestionResult:
    """Fetch DART fundamental snapshots and upsert into ``fundamental_snapshots``.

    Each FundamentalSnapshotDTO arrives tagged ``data_source="PROVIDER"`` from
    the DART parser.  ``data_source`` is stripped before the repository upsert
    (runtime-only; no DB column in Phase A).
    """
    _settings = settings or get_settings()
    if not _settings.provider_data_ingestion_enabled:
        return DartFundamentalIngestionResult(skipped_disabled=True)

    try:
        providers = create_dart_providers(
            settings=_settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError as exc:
        logger.debug("DART fundamentals ingestion skipped: %s", exc)
        return DartFundamentalIngestionResult(skipped_disabled=True)

    dtos = providers["fundamentals"].fetch_fundamentals(
        symbols, fiscal_year, fiscal_quarter
    )
    repo = FundamentalSnapshotRepository(session)
    upserted = 0
    for dto in dtos:
        repo.upsert_by_symbol_period(**_fund_kwargs(dto))
        upserted += 1

    return DartFundamentalIngestionResult(
        skipped_disabled=False,
        fetched=len(dtos),
        upserted=upserted,
    )


def ingest_dart_earnings(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: list[str],
    since: date | None = None,
    until: date | None = None,
    limit: int = 100,
) -> DartEarningsIngestionResult:
    """Fetch DART earnings events and upsert into ``earnings_events``.

    Each EarningsEventDTO arrives tagged ``data_source="PROVIDER"`` from
    the DART parser.  ``data_source`` is stripped before the repository upsert
    (runtime-only; no DB column in Phase A).
    """
    _settings = settings or get_settings()
    if not _settings.provider_data_ingestion_enabled:
        return DartEarningsIngestionResult(skipped_disabled=True)

    try:
        providers = create_dart_providers(
            settings=_settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError as exc:
        logger.debug("DART earnings ingestion skipped: %s", exc)
        return DartEarningsIngestionResult(skipped_disabled=True)

    dtos = providers["earnings"].fetch_earnings_events(
        symbols, since=since, until=until, limit=limit
    )
    repo = EarningsEventRepository(session)
    upserted = 0
    for dto in dtos:
        repo.upsert_by_symbol_event(**_earn_kwargs(dto))
        upserted += 1

    return DartEarningsIngestionResult(
        skipped_disabled=False,
        fetched=len(dtos),
        upserted=upserted,
    )


__all__ = [
    "DartDisclosureIngestionResult",
    "DartEarningsIngestionResult",
    "DartFundamentalIngestionResult",
    "RssNewsIngestionResult",
    "ingest_dart_disclosures",
    "ingest_dart_earnings",
    "ingest_dart_fundamentals",
    "ingest_rss_news",
]
