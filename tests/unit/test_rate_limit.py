"""Unit tests for v0.9 Phase A rate limit infrastructure.

Tests:
  * The limiter key-function returns a UUID-format string when disabled,
    ensuring requests never share a counter and the limit is never hit.
  * The limiter key-function returns the client IP when enabled.
  * The module-level ``limiter`` is a properly configured slowapi Limiter.
  * Settings defaults for rate_limit_enabled / rate_limit_auth are correct.
  * Rate limit triggering via HTTP (integration-style, app.state controlled).
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from slowapi import Limiter
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings, get_settings
from app.db import Base
from app.db.session import create_session_factory, get_session
from app.main import app
from app.middleware.rate_limit import _limiter_key, limiter


# ---------- limiter object ----------


def test_limiter_is_slowapi_limiter_instance():
    assert isinstance(limiter, Limiter)


# ---------- key function when disabled ----------


def test_limiter_key_returns_exempt_prefix_when_disabled():
    class _FakeState:
        rate_limit_enabled = False

    class _FakeApp:
        state = _FakeState()

    class _FakeRequest:
        app = _FakeApp()
        client = None
        headers = {}

    key = _limiter_key(_FakeRequest())
    assert key.startswith("__exempt_")


def test_limiter_key_returns_unique_values_when_disabled():
    class _FakeState:
        rate_limit_enabled = False

    class _FakeApp:
        state = _FakeState()

    class _FakeRequest:
        app = _FakeApp()
        client = None
        headers = {}

    keys = {_limiter_key(_FakeRequest()) for _ in range(10)}
    assert len(keys) == 10, "Each exempt key must be unique to avoid counter accumulation"


# ---------- key function when enabled ----------


def test_limiter_key_returns_remote_address_when_enabled():
    class _FakeState:
        rate_limit_enabled = True

    class _FakeApp:
        state = _FakeState()

    class _FakeClient:
        host = "1.2.3.4"

    class _FakeRequest:
        app = _FakeApp()
        client = _FakeClient()
        headers = {}

    key = _limiter_key(_FakeRequest())
    assert key == "1.2.3.4"


# ---------- Settings defaults ----------


def test_settings_rate_limit_enabled_default_is_true():
    s = Settings(
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
    assert s.rate_limit_enabled is True
    assert s.rate_limit_auth == "5/minute"
    assert s.rate_limit_default == "100/minute"


# ---------- session fixture for rate-limit HTTP test ----------


@pytest.fixture()
def _rl_session() -> Iterator:
    """In-memory SQLite session for rate limit HTTP tests (mirrors integration fixture)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ---------- rate limit trigger via HTTP (integration-style) ----------


def test_rate_limit_triggers_after_threshold(_rl_session):
    """Send 5+1 login requests with rate limiting enabled and expect 429 on the 6th.

    _get_auth_rate_limit() calls get_settings() via lru_cache (not FastAPI DI),
    so the effective limit is always the real default "5/minute".  We send 5
    requests (expect 401 for bad creds) then 1 more that must be 429.
    """
    def override_session():
        yield _rl_session

    app.dependency_overrides[get_session] = override_session
    app.state.rate_limit_enabled = True

    client = TestClient(app)
    try:
        # First 5 requests: should NOT be 429 (401 for wrong credentials)
        for i in range(5):
            r = client.post("/api/auth/login", json={"username": "x", "password": "y"})
            assert r.status_code != 429, (
                f"Got unexpected 429 on request {i+1}; headers: {dict(r.headers)}"
            )
        # 6th request: must be 429 (rate limit = 5/minute)
        r6 = client.post("/api/auth/login", json={"username": "x", "password": "y"})
        assert r6.status_code == 429
    finally:
        app.dependency_overrides.clear()
        app.state.rate_limit_enabled = False
        try:
            limiter._storage.reset()
        except Exception:
            pass
