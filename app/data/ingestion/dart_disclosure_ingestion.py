"""v0.12 Phase A -- DART disclosure ingestion adapter.

Wires the v0.11 ``DartDisclosureProvider`` (httpx-backed in production,
respx-mock-backed in tests) through the existing v0.5 ``DisclosureCollector``
into the existing ``news_items`` table.

Default-OFF
-----------
``Settings.provider_data_ingestion_enabled`` defaults to ``False``.  The
adapter short-circuits on the *very first* line; no provider is built,
no httpx.Client is instantiated, no DB row is written.

Boundary rules preserved
------------------------
* ``DisclosureCollector`` already classifies each DTO into the canonical
  5-category taxonomy and applies the v0.5 forbidden-body-field policy.
  This adapter does not re-implement any of that -- it only orchestrates
  ``create_dart_providers(...)`` → ``DisclosureCollector.collect_recent(...)``.
* Errors from the provider layer arrive as ``ProviderCallResult.fail``
  via ``call_with_resilience`` (v0.10).  The collector swallows the empty
  result list naturally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.collectors.disclosure_collector import (
    DisclosureCollector,
    DisclosureCollectorResult,
)
from app.data.dart_provider import (
    DartNotConfiguredError,
    DartTransport,
    create_dart_providers,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.repositories.news_items import NewsItemRepository


@dataclass(frozen=True)
class DartDisclosureIngestionResult:
    """Outcome of one ``ingest_dart_disclosures`` call."""

    skipped_disabled: bool = False
    fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0
    truncated_summaries: int = 0
    classified_counts: dict[str, int] | None = None

    @classmethod
    def disabled(cls) -> "DartDisclosureIngestionResult":
        return cls(skipped_disabled=True)

    @classmethod
    def from_collector(
        cls, result: DisclosureCollectorResult
    ) -> "DartDisclosureIngestionResult":
        return cls(
            skipped_disabled=False,
            fetched=result.fetched,
            inserted=result.inserted,
            skipped_duplicates=result.skipped_duplicates,
            truncated_summaries=result.truncated_summaries,
            classified_counts=dict(result.classified_counts or {}),
        )


def ingest_dart_disclosures(
    session: Session,
    *,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
    symbols: Sequence[str] | None = None,
    since: datetime | None = None,
    limit: int = 50,
) -> DartDisclosureIngestionResult:
    """Ingest DART disclosures into ``news_items``.

    Returns a result whose ``skipped_disabled`` is True when
    ``provider_data_ingestion_enabled`` is False *or* DART is not
    enabled / configured.  No exception is raised in those cases --
    the caller (scheduler / CLI) should treat the call as a no-op.

    ``transport`` accepts an injected mock for tests; when ``None`` the
    factory builds the production ``HttpxDartTransport`` (only reached
    after both ``provider_data_ingestion_enabled`` and ``dart_enabled``
    are True).
    """
    settings = settings or get_settings()
    if not settings.provider_data_ingestion_enabled:
        return DartDisclosureIngestionResult.disabled()

    try:
        providers = create_dart_providers(
            settings=settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError:
        # DART_ENABLED=false / DART_API_KEY missing.  This is a soft skip
        # so operators can flip the master flag without DART simultaneously.
        return DartDisclosureIngestionResult.disabled()

    collector = DisclosureCollector(
        providers["disclosures"], NewsItemRepository(session)
    )
    result = collector.collect_recent(
        symbols=list(symbols) if symbols is not None else None,
        since=since,
        limit=limit,
    )
    return DartDisclosureIngestionResult.from_collector(result)


__all__ = [
    "DartDisclosureIngestionResult",
    "ingest_dart_disclosures",
]
