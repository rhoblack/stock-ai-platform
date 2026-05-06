"""Unit tests for v0.9 Phase A SecurityHeadersMiddleware.

Uses FastAPI's TestClient on the shared ``app`` object. The conftest autouse
fixture disables rate limiting and brute force so these tests are not affected
by the other security layers.

Security headers are always injected by default
(``app.state.security_headers_enabled=True``). Tests that verify the disabled
path temporarily flip this flag and restore it in teardown.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


# ---------- Headers present by default ----------


def test_health_response_has_x_content_type_options(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_health_response_has_x_frame_options(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_health_response_has_referrer_policy(client):
    resp = client.get("/health")
    assert resp.headers.get("Referrer-Policy") == "no-referrer"


def test_health_response_has_permissions_policy(client):
    resp = client.get("/health")
    policy = resp.headers.get("Permissions-Policy", "")
    assert "camera=()" in policy
    assert "microphone=()" in policy
    assert "geolocation=()" in policy


def test_all_four_security_headers_present_in_single_request(client):
    resp = client.get("/health")
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Permissions-Policy"):
        assert header in resp.headers, f"Missing header: {header}"


# ---------- Headers absent when middleware disabled ----------


def test_security_headers_absent_when_disabled(client):
    original = getattr(app.state, "security_headers_enabled", True)
    app.state.security_headers_enabled = False
    try:
        resp = client.get("/health")
        for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Permissions-Policy"):
            assert header not in resp.headers, f"Header should be absent: {header}"
    finally:
        app.state.security_headers_enabled = original


def test_security_headers_restored_when_re_enabled(client):
    original = getattr(app.state, "security_headers_enabled", True)
    app.state.security_headers_enabled = False
    app.state.security_headers_enabled = True
    try:
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    finally:
        app.state.security_headers_enabled = original


# ---------- No CSP enforcement ----------


def test_no_content_security_policy_header_enforced(client):
    resp = client.get("/health")
    # CSP is deferred to Phase D+; must NOT be present as an enforcing header.
    assert "Content-Security-Policy" not in resp.headers


# ---------- Auth /me endpoint also gets headers (no DB needed in fallback mode) ----------


def test_security_headers_present_on_auth_me_endpoint(client):
    # GET /api/auth/me with AUTH_ENABLED=false (default) returns 200 without
    # any DB access (uses the dev fallback user_id=1). Security headers must
    # be present regardless of the endpoint.
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
