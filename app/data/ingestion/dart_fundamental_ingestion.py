"""v0.12 Phase A -- DART fundamentals ingestion adapter.

Wires the v0.11 ``DartFundamentalProvider`` (transport-injected) through
``FundamentalSnapshotRepository.upsert_by_symbol_period`` into the
existing ``fundamental_snapshots`` table.  Default-OFF via
``Settings.provider_data_ingestion_enabled``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.data.dart_provider import (
    DartNotConfiguredError,
    DartTransport,
    create_dart_providers,
)
from app.data.provider_health_monitor import ProviderHealthMonitor
from app.data.repositories.fundamental_snapshots import (
    FundamentalSnapshotRepository,
)


@dataclass(frozen=True)
class DartFundamentalIngestionResult:
    """Outcome of one ``ingest_dart_fundamentals`` call."""

    skipped_disabled: bool = False
    fetched: int = 0
    upserted: int = 0

    @classmethod
    def disabled(cls) -> "DartFundamentalIngestionResult":
        return cls(skipped_disabled=True)


def ingest_dart_fundamentals(
    session: Session,
    *,
    symbols: Sequence[str],
    fiscal_year: int,
    fiscal_quarter: int | None = None,
    settings: Settings | None = None,
    transport: DartTransport | None = None,
    monitor: ProviderHealthMonitor | None = None,
) -> DartFundamentalIngestionResult:
    """Ingest DART fundamental snapshots into ``fundamental_snapshots``.

    Soft-skips when either ``provider_data_ingestion_enabled`` is False
    or DART is not enabled / configured.
    """
    settings = settings or get_settings()
    if not settings.provider_data_ingestion_enabled:
        return DartFundamentalIngestionResult.disabled()

    try:
        providers = create_dart_providers(
            settings=settings, transport=transport, monitor=monitor
        )
    except DartNotConfiguredError:
        return DartFundamentalIngestionResult.disabled()

    fundamentals_provider = providers["fundamentals"]
    repo = FundamentalSnapshotRepository(session)

    dtos = fundamentals_provider.fetch_fundamentals(
        list(symbols), fiscal_year, fiscal_quarter
    )

    upserted = 0
    for dto in dtos:
        # ``data_source`` is runtime-only (no DB column); strip before
        # forwarding to the repo upsert helper.
        payload = asdict(dto)
        payload.pop("data_source", None)
        repo.upsert_by_symbol_period(**payload)
        upserted += 1

    return DartFundamentalIngestionResult(
        skipped_disabled=False,
        fetched=len(dtos),
        upserted=upserted,
    )


__all__ = [
    "DartFundamentalIngestionResult",
    "ingest_dart_fundamentals",
]
