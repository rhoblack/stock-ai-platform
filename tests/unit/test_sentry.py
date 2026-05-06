"""Unit tests for v0.9 Phase B optional Sentry integration.

Tests:
  * init_sentry returns False when sentry_enabled=False (default).
  * init_sentry returns False + logs WARNING when enabled but DSN is absent.
  * init_sentry calls sentry_sdk.init exactly once with a dummy DSN.
  * _before_send masks sensitive fields in event["extra"].
  * _before_send masks sensitive fields in event["request"]["data"].
  * _before_send masks Authorization-style headers.
  * _before_send does not alter non-sensitive fields.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from app.config.settings import Settings

_BASE_KW = dict(
    app_env="test",
    app_name="stock_ai_platform",
    timezone="Asia/Seoul",
    log_level="INFO",
    telegram_enabled=False,
    telegram_bot_token="x" * 16,
    telegram_chat_id="123",
    telegram_api_base_url="https://mock.local",
    telegram_timeout_seconds=5,
    kis_app_key="k" * 16,
    kis_app_secret="s" * 16,
    kis_account_no="0" * 10,
    kis_account_product_code="01",
    kis_use_paper=True,
    scheduler_enabled=False,
    feature_real_order_execution=False,
    feature_full_auto=False,
    feature_paper_trading=False,
    feature_backtest=False,
    feature_custom_ai_training=False,
)


def _settings(**kw) -> Settings:
    return Settings(**{**_BASE_KW, **kw})


# ---- init_sentry ----


def test_init_sentry_disabled_by_default():
    from app.monitoring.sentry import init_sentry

    result = init_sentry(_settings(sentry_enabled=False))
    assert result is False


def test_init_sentry_skips_and_warns_when_dsn_missing(caplog):
    from app.monitoring.sentry import init_sentry

    with caplog.at_level(logging.WARNING, logger="app.monitoring.sentry"):
        result = init_sentry(_settings(sentry_enabled=True, sentry_dsn=None))

    assert result is False
    assert any("SENTRY_DSN" in r.message for r in caplog.records), (
        "A WARNING mentioning SENTRY_DSN must be logged when DSN is absent"
    )


def test_init_sentry_calls_sdk_init_with_dummy_dsn():
    from app.monitoring.sentry import init_sentry

    settings = _settings(
        sentry_enabled=True,
        sentry_dsn="https://fake_key@o0.ingest.sentry.io/0",
        sentry_environment="test",
    )
    with patch("sentry_sdk.init") as mock_init:
        result = init_sentry(settings)

    assert result is True
    mock_init.assert_called_once()
    call_kwargs = mock_init.call_args.kwargs
    assert call_kwargs["dsn"] == "https://fake_key@o0.ingest.sentry.io/0"
    assert call_kwargs["send_default_pii"] is False


# ---- _before_send masking ----


def test_before_send_masks_password_in_extra():
    from app.monitoring.sentry import _before_send, _MASK

    event = {"extra": {"password": "hunter2", "user_id": 1}}
    result = _before_send(event, {})
    assert result["extra"]["password"] == _MASK
    assert result["extra"]["user_id"] == 1


def test_before_send_masks_sensitive_fields_in_request_data():
    from app.monitoring.sentry import _before_send, _MASK

    event = {
        "request": {
            "data": {
                "password_hash": "scrypt$...",
                "access_token": "Bearer xyz",
                "username": "alice",
            }
        }
    }
    result = _before_send(event, {})
    data = result["request"]["data"]
    assert data["password_hash"] == _MASK
    assert data["access_token"] == _MASK
    assert data["username"] == "alice"  # non-sensitive — must not be masked


def test_before_send_masks_authorization_header():
    from app.monitoring.sentry import _before_send, _MASK

    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer eyJhb...",
                "Content-Type": "application/json",
            }
        }
    }
    result = _before_send(event, {})
    headers = result["request"]["headers"]
    assert headers["Authorization"] == _MASK
    assert headers["Content-Type"] == "application/json"


def test_before_send_passes_through_event_without_sensitive_keys():
    from app.monitoring.sentry import _before_send

    event = {
        "extra": {"request_id": "abc-123", "path": "/health"},
        "request": {"method": "GET"},
    }
    result = _before_send(event, {})
    assert result["extra"]["request_id"] == "abc-123"
    assert result["extra"]["path"] == "/health"
    assert result["request"]["method"] == "GET"
