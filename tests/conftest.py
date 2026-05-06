"""Shared pytest fixtures for v0.9 Phase A security hardening.

The autouse fixture ``_disable_security_guards`` runs before every test and:
  * Sets ``app.state.rate_limit_enabled = False`` so the slowapi key function
    returns a unique UUID per request and the counter never fills.
  * Sets ``app.state.bruteforce_enabled = False`` so auth_routes skips the
    brute force check entirely.

Tests that explicitly test rate limiting or brute force behaviour override
these flags themselves (see tests/integration/test_auth_security.py).

After each test:
  * Flags are restored to their pre-test values.
  * The brute force guard's in-memory counters are cleared.
  * The slowapi MemoryStorage counters are cleared.
"""

import pytest


@pytest.fixture(autouse=True)
def _disable_security_guards():
    from app.main import app
    from app.middleware.rate_limit import limiter

    rl_orig = getattr(app.state, "rate_limit_enabled", True)
    bf_orig = getattr(app.state, "bruteforce_enabled", True)

    app.state.rate_limit_enabled = False
    app.state.bruteforce_enabled = False

    yield

    app.state.rate_limit_enabled = rl_orig
    app.state.bruteforce_enabled = bf_orig

    guard = getattr(app.state, "bruteforce_guard", None)
    if guard is not None:
        guard.reset()

    try:
        limiter._storage.reset()
    except Exception:  # noqa: BLE001 - tolerate storage API differences
        pass
