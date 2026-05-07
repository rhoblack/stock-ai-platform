"""v0.12 Phase A -- DART earnings ingestion adapter.

Wires the v0.11 ``DartEarningsProvider`` (transport-injected) through
``EarningsEventRepository.upsert_by_symbol_event`` into the existing
``earnings_events`` table.  Default-OFF via
``Settings.provider_data_ingestion_enabled``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.dart_provider import (
    DartNotConfiguredError,
    DartTransport,
    create_dart_providers,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.repositories.earnings_events import EarningsEventRepository


@dataclass(frozen=True)
class DartEarningsIngestionResult:
    """Outcome of one ``ingest_dart_earnings`` call."""

    skipped_disabled: bool = False
    fetched: int = 0
    upserted: int = 0

    @classmethod
    def disabled(cls) -> "DartEarningsIngestionResult":
        return cls(skipped_disabled=True)


def ingest_dart_earnings(
    session: Session,
    *,
    symbols: Sequence[str],
    since: date | None = None,
    until: date | None = None,
    limit: int = 100,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
) -> DartEarningsIngestionResult:
    """Ingest DART earnings events into ``earnings_events``."""
    settings = settings or get_settings()
    if not settings.provider_data_ingestion_enabled:
        return DartEarningsIngestionResult.disabled()

    try:
        providers = create_dart_providers(
            settings=settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError:
        return DartEarningsIngestionResult.disabled()

    earnings_provider = providers["earnings"]
    repo = EarningsEventRepository(session)

    dtos = earnings_provider.fetch_earnings_events(
        list(symbols), since=since, until=until, limit=limit
    )

    upserted = 0
    for dto in dtos:
        payload = asdict(dto)
        payload.pop("data_source", None)
        repo.upsert_by_symbol_event(**payload)
        upserted += 1

    return DartEarningsIngestionResult(
        skipped_disabled=False,
        fetched=len(dtos),
        upserted=upserted,
    )


__all__ = [
    "DartEarningsIngestionResult",
    "ingest_dart_earnings",
]
