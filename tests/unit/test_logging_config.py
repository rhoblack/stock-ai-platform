"""Unit tests for v0.9 Phase B structured logging configuration.

Tests:
  * SensitiveFilter redacts extra fields whose names match the sensitive pattern.
  * SensitiveFilter leaves non-sensitive fields intact.
  * configure_logging installs SensitiveFilter on handlers.
  * configure_logging with structured_logging_enabled=True installs a JSON formatter.
  * configure_logging is idempotent (clearing handlers on each call).
  * RequestIDFilter falls back to "-" outside a request context.
"""

from __future__ import annotations

import logging

import pytest

from app.config.logging import (
    RequestIDFilter,
    SensitiveFilter,
    _MASK,
    configure_logging,
)


# ---- Fixture: isolate root logger state between tests ----


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)


# ---- SensitiveFilter unit tests ----


def _make_record(extra: dict | None = None) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, "", 0, "test msg", (), None)
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


def test_sensitive_filter_masks_password():
    f = SensitiveFilter()
    rec = _make_record({"password": "hunter2"})
    f.filter(rec)
    assert rec.password == _MASK


def test_sensitive_filter_masks_password_hash():
    f = SensitiveFilter()
    rec = _make_record({"password_hash": "scrypt$N=1024..."})
    f.filter(rec)
    assert rec.password_hash == _MASK


def test_sensitive_filter_masks_jwt_secret():
    f = SensitiveFilter()
    rec = _make_record({"jwt_secret": "supersecret"})
    f.filter(rec)
    assert rec.jwt_secret == _MASK


def test_sensitive_filter_masks_access_token():
    f = SensitiveFilter()
    rec = _make_record({"access_token": "Bearer eyJhb..."})
    f.filter(rec)
    assert rec.access_token == _MASK


def test_sensitive_filter_leaves_safe_fields_intact():
    f = SensitiveFilter()
    rec = _make_record({"username": "alice", "user_id": 42})
    f.filter(rec)
    assert rec.username == "alice"
    assert rec.user_id == 42


def test_sensitive_filter_does_not_mask_standard_log_attrs():
    f = SensitiveFilter()
    rec = _make_record()
    original_name = rec.name
    f.filter(rec)
    assert rec.name == original_name


# ---- RequestIDFilter unit tests ----


def test_request_id_filter_fallback_outside_request():
    f = RequestIDFilter()
    rec = _make_record()
    f.filter(rec)
    # Outside a request context the var is None → fallback to "-"
    assert hasattr(rec, "request_id")
    assert rec.request_id == "-"


# ---- configure_logging integration tests ----


def test_configure_logging_installs_sensitive_filter(tmp_path):
    configure_logging("DEBUG", log_dir=str(tmp_path))
    root = logging.getLogger()
    all_filters = [f for h in root.handlers for f in h.filters]
    assert any(isinstance(f, SensitiveFilter) for f in all_filters), (
        "SensitiveFilter must be installed on at least one handler"
    )


def test_configure_logging_installs_request_id_filter_by_default(tmp_path):
    configure_logging("DEBUG", log_dir=str(tmp_path), log_request_id_enabled=True)
    root = logging.getLogger()
    all_filters = [f for h in root.handlers for f in h.filters]
    assert any(isinstance(f, RequestIDFilter) for f in all_filters)


def test_configure_logging_omits_request_id_filter_when_disabled(tmp_path):
    configure_logging("DEBUG", log_dir=str(tmp_path), log_request_id_enabled=False)
    root = logging.getLogger()
    all_filters = [f for h in root.handlers for f in h.filters]
    assert not any(isinstance(f, RequestIDFilter) for f in all_filters)


def test_configure_logging_is_idempotent(tmp_path):
    configure_logging("INFO", log_dir=str(tmp_path))
    first_count = len(logging.getLogger().handlers)
    configure_logging("INFO", log_dir=str(tmp_path))
    second_count = len(logging.getLogger().handlers)
    assert first_count == second_count, (
        "configure_logging must not accumulate duplicate handlers"
    )


def test_configure_logging_json_format(tmp_path):
    pytest.importorskip("pythonjsonlogger", reason="python-json-logger not installed")
    configure_logging("INFO", log_dir=str(tmp_path), structured_logging_enabled=True)
    root = logging.getLogger()
    formatter_types = [type(h.formatter).__name__ for h in root.handlers if h.formatter]
    assert any("Json" in t for t in formatter_types), (
        f"Expected a JSON formatter; got {formatter_types}"
    )
