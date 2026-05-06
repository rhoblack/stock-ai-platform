"""v0.9 Phase B — structured logging with optional JSON format and secret masking.

Two formatter modes:
  * text (default, structured_logging_enabled=False):
      ``%(asctime)s %(levelname)s [%(name)s] %(message)s``
  * json (structured_logging_enabled=True):
      pythonjsonlogger.JsonFormatter — falls back to text if not installed.

Two filters applied to every handler:
  * SensitiveFilter  — redacts log record *extra* fields whose names match
    the OWASP-aligned sensitive-field pattern (password, token, secret, …).
  * RequestIDFilter  — injects the current request-id (from contextvars)
    as ``record.request_id`` so JSON and text formatters can emit it.

The filters are a defence-in-depth safety net; callers should never embed
raw secrets in the log message or extra kwargs.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

# --------------------------------------------------------------------- #
# Sensitive field detection                                              #
# --------------------------------------------------------------------- #

_SENSITIVE_FIELD_RE = re.compile(
    r"\b(password|password_hash|access_token|jwt_secret|"
    r"authorization|api_key|apikey|token|secret)\b",
    re.IGNORECASE,
)

_MASK = "***"


def _is_sensitive(name: str) -> bool:
    return bool(_SENSITIVE_FIELD_RE.search(name))


# --------------------------------------------------------------------- #
# Filters                                                                #
# --------------------------------------------------------------------- #


class SensitiveFilter(logging.Filter):
    """Redact *extra* fields whose names match the sensitive-field pattern.

    Only attributes that were explicitly injected via ``extra={}`` in the
    logging call are scanned.  Standard LogRecord attributes (funcName,
    lineno, …) are skipped to avoid false positives.
    """

    _STANDARD_ATTRS: frozenset[str] = frozenset(logging.LogRecord(
        "", 0, "", 0, "", (), None
    ).__dict__.keys()) | {"message", "asctime"}

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in list(vars(record)):
            if attr in self._STANDARD_ATTRS:
                continue
            if _is_sensitive(attr):
                setattr(record, attr, _MASK)
        return True


class RequestIDFilter(logging.Filter):
    """Inject ``record.request_id`` from the active request context.

    Falls back to ``"-"`` when called outside a request (scheduler jobs,
    startup, CLI).  Import is deferred to avoid a circular-import between
    ``app.config.logging`` and ``app.middleware.request_id``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.middleware.request_id import request_id_var  # noqa: PLC0415
            record.request_id = request_id_var.get() or "-"
        except Exception:  # noqa: BLE001
            record.request_id = "-"
        return True


# --------------------------------------------------------------------- #
# Formatter factory                                                       #
# --------------------------------------------------------------------- #


def _make_formatter(structured: bool) -> logging.Formatter:
    if structured:
        try:
            from pythonjsonlogger import jsonlogger  # noqa: PLC0415
            return jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"levelname": "level", "asctime": "ts"},
            )
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "python-json-logger not available; falling back to text format"
            )
    return logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")


# --------------------------------------------------------------------- #
# Public API                                                              #
# --------------------------------------------------------------------- #


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: str = "logs",
    log_to_file: bool = False,
    structured_logging_enabled: bool = False,
    log_request_id_enabled: bool = True,
) -> None:
    """Configure process-wide logging.

    Clears existing root-logger handlers so the function is idempotent and
    can be called again in tests without accumulating duplicate handlers.
    """
    root = logging.getLogger()
    root.handlers.clear()

    level_int = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(level_int)

    formatter = _make_formatter(structured_logging_enabled)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path / "app.log", encoding="utf-8"))

    sensitive_filter = SensitiveFilter()
    request_id_filter = RequestIDFilter() if log_request_id_enabled else None

    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(sensitive_filter)
        if request_id_filter is not None:
            handler.addFilter(request_id_filter)
        root.addHandler(handler)
