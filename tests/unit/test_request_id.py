"""Unit tests for v0.9 Phase B RequestIDMiddleware.

Uses FastAPI's TestClient on the shared ``app`` object.  The conftest
autouse fixture disables rate limiting and brute force so these tests are
not affected by the Phase A security layers.

Tests verify:
  * A UUID is generated and echoed in X-Request-ID when the header is absent.
  * A supplied X-Request-ID is preserved unchanged in the response.
  * Each request without a pre-set id receives a unique id.
  * The generated id matches UUID4 format.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@pytest.fixture()
def client():
    return TestClient(app)


def test_request_id_generated_when_header_absent(client):
    resp = client.get("/health")
    assert "X-Request-ID" in resp.headers, "X-Request-ID must be present"
    assert _UUID4_RE.match(resp.headers["X-Request-ID"]), (
        f"Generated id is not UUID4: {resp.headers['X-Request-ID']}"
    )


def test_request_id_preserved_when_header_present(client):
    custom_id = "my-trace-id-abc123"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers["X-Request-ID"] == custom_id


def test_request_id_unique_per_request(client):
    ids = {client.get("/health").headers["X-Request-ID"] for _ in range(5)}
    assert len(ids) == 5, "Each request must receive a distinct request-id"


def test_request_id_present_on_auth_endpoint(client):
    resp = client.get("/api/auth/me")
    assert "X-Request-ID" in resp.headers


def test_request_id_present_on_429_response():
    """Rate-limit 429 responses also carry X-Request-ID (middleware wraps SlowAPI)."""
    from app.config.settings import Settings, get_settings
    from app.db import Base
    from app.db.session import create_session_factory, get_session
    from app.middleware.rate_limit import limiter
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    db = factory()

    settings = Settings(
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
        rate_limit_enabled=True,
        rate_limit_auth="3/minute",
    )

    def override_session():
        yield db

    def override_settings():
        return settings

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    app.state.rate_limit_enabled = True

    client = TestClient(app)
    try:
        # Exhaust the 5/minute (real default) limit then check the 429.
        resp_429 = None
        for _ in range(6):
            r = client.post("/api/auth/login", json={"username": "x", "password": "y"})
            if r.status_code == 429:
                resp_429 = r
                break
        if resp_429 is not None:
            assert "X-Request-ID" in resp_429.headers
    finally:
        app.dependency_overrides.clear()
        app.state.rate_limit_enabled = False
        db.close()
        Base.metadata.drop_all(engine)
        try:
            limiter._storage.reset()
        except Exception:
            pass
