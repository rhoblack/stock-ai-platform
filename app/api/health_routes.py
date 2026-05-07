"""v0.10 Phase D -- read-only provider health API.

Endpoint:

    GET /api/health/providers
        Returns an array of in-memory provider health snapshots from
        :class:`app.data.provider_health_monitor.ProviderHealthMonitor`,
        plus a configuration summary (``enabled`` / ``configured``) for
        every provider the platform knows about (kis, dart, rss).

Policy
------
* **No external HTTP call** is made.  The response is built solely from
  the in-memory monitor + the operator-supplied ``Settings`` flags.
* **No POST / PUT / DELETE** -- read only, mirrors the v0.1~v0.9 API
  policy.  Provider enable / disable toggling is intentionally out of
  scope (operator must edit ``.env`` and restart).
* **Secret discipline** -- the response NEVER includes ``dart_api_key``,
  ``crtfc_key``, raw KIS credentials, ``rss_feed_urls`` (URLs may embed
  ``?api_key=...``), or any ``last_error_message`` payload that could
  contain query-string secrets.  Only ``last_error_kind`` (the
  enumerated ``ProviderErrorKind`` label) survives.
* **Decimal / datetime serialisation** -- ``call_count`` /
  ``success_count`` / ``failure_count`` are plain ints; ``last_called_at``
  is the monitor's pre-formatted ISO-8601 string (or ``null``).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config.settings import Settings, get_settings
from app.data.provider_health_monitor import (
    ProviderHealthMonitor,
    get_health_monitor,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProviderHealthItem(BaseModel):
    """One row in the provider-health response.

    All fields are safe for public read-only exposure.  ``last_error_message``
    is intentionally **omitted** -- the monitor stores it for log
    correlation, but echoing it through HTTP risks leaking transport
    detail (e.g. URL query strings, partial response bodies).
    """

    provider_name: str
    enabled: bool
    configured: bool
    circuit_state: str
    call_count: int
    success_count: int
    failure_count: int
    last_error_kind: Optional[str] = None
    last_called_at: Optional[str] = None


class ProviderHealthResponse(BaseModel):
    items: list[ProviderHealthItem]
    count: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/health", tags=["health"])


# Provider names that are *always* surfaced even when the operator has not
# opted in -- so the operator can see at a glance that a provider is
# disabled / not configured.  The order is the display order in the UI.
_DEFAULT_PROVIDERS: tuple[str, ...] = ("kis", "dart", "rss")


def _is_enabled(provider: str, settings: Settings) -> bool:
    """Return True when the operator has flagged this provider as enabled."""
    if provider == "kis":
        # KIS has no boolean enabled flag in v0.10; presence of credentials
        # and absence of explicit disable signals "enabled".  Treat empty
        # app_key as not configured (handled separately by ``configured``).
        return bool(settings.kis_app_key)
    if provider == "dart":
        return bool(settings.dart_enabled)
    if provider == "rss":
        return bool(settings.rss_news_enabled)
    return False


def _is_configured(provider: str, settings: Settings) -> bool:
    """Return True when minimum credentials / config are present.

    A provider can be ``enabled=True`` but ``configured=False`` if the
    operator forgot a key.  In that case the factory raises and the
    monitor never sees a call -- the UI surfaces this as a warning.
    """
    if provider == "kis":
        return bool(settings.kis_app_key) and bool(settings.kis_app_secret)
    if provider == "dart":
        return bool(settings.dart_api_key)
    if provider == "rss":
        return bool((settings.rss_feed_urls or "").strip())
    return False


def _build_item(
    provider: str,
    settings: Settings,
    monitor: ProviderHealthMonitor,
) -> ProviderHealthItem:
    """Merge config flags with monitor stats into one row."""
    enabled = _is_enabled(provider, settings)
    configured = _is_configured(provider, settings)
    stats = monitor.get_status(provider)
    if stats is None:
        # Provider was never registered -- typical for default-OFF state.
        return ProviderHealthItem(
            provider_name=provider,
            enabled=enabled,
            configured=configured,
            circuit_state="UNREGISTERED",
            call_count=0,
            success_count=0,
            failure_count=0,
            last_error_kind=None,
            last_called_at=None,
        )
    return ProviderHealthItem(
        provider_name=provider,
        enabled=enabled,
        configured=configured,
        circuit_state=stats["status"],
        call_count=int(stats["call_count"]),
        success_count=int(stats["success_count"]),
        failure_count=int(stats["failure_count"]),
        last_error_kind=stats["last_error_kind"],
        last_called_at=stats["last_called_at"],
    )


@router.get(
    "/providers",
    response_model=ProviderHealthResponse,
    tags=["health"],
)
def get_provider_health(
    settings: Settings = Depends(get_settings),
) -> ProviderHealthResponse:
    """Return the current provider-health snapshot.

    Combines the in-memory ``ProviderHealthMonitor`` state with operator
    settings so the UI can show "kis / dart / rss" status even when the
    monitor has no recorded calls yet (e.g. fresh process, default-OFF).
    """
    monitor = get_health_monitor()

    # Always emit the canonical 3 providers in fixed order.
    items: list[ProviderHealthItem] = [
        _build_item(name, settings, monitor) for name in _DEFAULT_PROVIDERS
    ]

    # Surface any *additional* providers the monitor knows about (future-
    # proof: an experimental provider registered for a CLI run will still
    # appear in /api/health/providers).
    seen = set(_DEFAULT_PROVIDERS)
    for status in monitor.get_all_status():
        name = status["name"]
        if name in seen:
            continue
        seen.add(name)
        items.append(_build_item(name, settings, monitor))

    return ProviderHealthResponse(items=items, count=len(items))
