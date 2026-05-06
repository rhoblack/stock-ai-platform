"""v0.9 Phase B — optional Sentry SDK integration.

Usage (in app/main.py)::

    from app.monitoring.sentry import init_sentry
    init_sentry(settings)

Design decisions:
  * ``sentry_enabled=False`` (default) — zero SDK overhead; no network call.
  * ``sentry_enabled=True`` + missing DSN → WARNING logged, Sentry disabled.
    Application continues normally (no crash-at-startup).
  * ``before_send`` hook scrubs sensitive fields from every event *before* it
    leaves the process so passwords / tokens never reach Sentry servers.
  * ``send_default_pii=False`` — SDK-level PII guard (IP, user-agent, cookies).
  * Stack traces are preserved in Sentry events (they are not in API responses).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- #
# Sensitive-field masking for Sentry events                              #
# --------------------------------------------------------------------- #

_SENSITIVE_RE = re.compile(
    r"\b(password|password_hash|access_token|jwt_secret|"
    r"authorization|api_key|apikey|token|secret)\b",
    re.IGNORECASE,
)

_MASK = "***"


def _is_sensitive(name: str) -> bool:
    return bool(_SENSITIVE_RE.search(name))


def _scrub_dict(d: dict) -> None:
    """Redact sensitive values in-place (shallow scan, non-recursive)."""
    for key in list(d.keys()):
        if _is_sensitive(str(key)):
            d[key] = _MASK


def _before_send(event: dict, hint: dict) -> dict:
    """Strip sensitive values from a Sentry event before transmission.

    Scans:
      * ``event["extra"]``              — custom extra context
      * ``event["request"]["data"]``    — parsed POST body
      * ``event["request"]["headers"]`` — HTTP headers (Authorization, etc.)

    Stack traces are left intact (essential for debugging).
    """
    extra = event.get("extra")
    if isinstance(extra, dict):
        _scrub_dict(extra)

    request = event.get("request")
    if isinstance(request, dict):
        data = request.get("data")
        if isinstance(data, dict):
            _scrub_dict(data)

        headers = request.get("headers")
        if isinstance(headers, dict):
            _scrub_dict(headers)

    return event


# --------------------------------------------------------------------- #
# Initialiser                                                             #
# --------------------------------------------------------------------- #


def init_sentry(settings) -> bool:
    """Initialise Sentry SDK if enabled and configured.

    Returns True when the SDK is successfully initialised, False otherwise.
    Never raises — the app must start regardless of Sentry availability.
    """
    if not settings.sentry_enabled:
        return False

    if not settings.sentry_dsn:
        logger.warning(
            "SENTRY_ENABLED=true but SENTRY_DSN is not configured; "
            "Sentry integration disabled"
        )
        return False

    try:
        import sentry_sdk  # noqa: PLC0415

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment or settings.app_env,
            before_send=_before_send,
            send_default_pii=False,
        )
        logger.info(
            "Sentry initialised (environment=%s)",
            settings.sentry_environment or settings.app_env,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Sentry initialisation failed; continuing without it")
        return False
