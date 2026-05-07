"""v0.12 Phase A -- Provider data ingestion adapters.

These adapters wire the v0.11 HTTP transports
(:class:`app.data.dart_provider.HttpxDartTransport`,
:class:`app.data.rss_provider.HttpxRssTransport`) through their respective
provider classes into the existing v0.5/v0.6 collectors / importers /
repositories.  No new DB schema is introduced -- existing tables
(``news_items``, ``fundamental_snapshots``, ``earnings_events``) are
reused, and ``ProviderHealthMonitor`` ring buffer / call_with_resilience
infrastructure is inherited from v0.10/v0.11.

Default-OFF policy
------------------
Every adapter checks ``Settings.provider_data_ingestion_enabled`` first.
When the flag is False (the default), the adapter returns immediately
with an empty result; no provider is constructed, no httpx.Client is
instantiated, no DB row is written.  This preserves the v0.10/v0.11
zero-network guard for the entire test suite.

Secret discipline
-----------------
The adapters never log feed URLs / API keys.  Any provenance information
attached to DTOs survives only as the categorical ``data_source`` field
(``"PROVIDER"`` / ``"FAKE"`` / ``"CSV"`` / ``"MANUAL"``); message text
and URL query strings are dropped at the transport layer (v0.11
``SensitiveQueryStringFilter`` + ``_safe_url_for_log``).
"""

from app.data.ingestion.dart_disclosure_ingestion import (
    DartDisclosureIngestionResult,
    ingest_dart_disclosures,
)
from app.data.ingestion.dart_earnings_ingestion import (
    DartEarningsIngestionResult,
    ingest_dart_earnings,
)
from app.data.ingestion.dart_fundamental_ingestion import (
    DartFundamentalIngestionResult,
    ingest_dart_fundamentals,
)
from app.data.ingestion.rss_news_ingestion import (
    RssNewsIngestionResult,
    ingest_rss_news,
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
