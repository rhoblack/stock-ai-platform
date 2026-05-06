"""v0.9 Phase A -- slowapi Limiter instance shared across the application.

The ``limiter`` object is imported by ``app/main.py`` (to set up the
SlowAPIMiddleware and exception handler) and by route modules that apply
``@limiter.limit(...)`` decorators.

Key-function design
-------------------
When ``request.app.state.rate_limit_enabled`` is ``False`` (the default in
test environments set by ``tests/conftest.py``), the key function returns a
unique UUID string so the counter for that key is always 0 and the limit is
never triggered.  In production (``rate_limit_enabled=True``) the real
client IP is used as the key.

This avoids the need for a separate ``exempt_when`` hook and works with all
slowapi 0.1.x versions.
"""

from __future__ import annotations

from uuid import uuid4

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _limiter_key(request: Request) -> str:
    if not getattr(request.app.state, "rate_limit_enabled", True):
        # Unique key per request -- counter never fills, effectively bypasses.
        return f"__exempt_{uuid4().hex}"
    return get_remote_address(request)


limiter = Limiter(key_func=_limiter_key)
