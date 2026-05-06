"""v0.9 Phase A -- Security response headers middleware.

Adds security-related HTTP response headers to every response served by the
application. The middleware is always mounted; it reads
``request.app.state.security_headers_enabled`` at request time so the
behaviour can be toggled without restarting the process (used by tests).

Headers applied:
  * X-Content-Type-Options: nosniff  -- prevents MIME-sniffing attacks
  * X-Frame-Options: DENY            -- blocks clickjacking via iframes
  * Referrer-Policy: no-referrer     -- suppresses Referer header leakage
  * Permissions-Policy: ...          -- disables camera / mic / geolocation

CSP is intentionally NOT enforced here. A strict Content-Security-Policy
can conflict with Vite dev-server / nginx inline scripts / React hydration.
Add Content-Security-Policy-Report-Only after verifying the frontend asset
inventory (Phase D or later cycle).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into every HTTP response.

    Skips header injection when ``request.app.state.security_headers_enabled``
    is ``False`` (default: ``True``). Tests that need to verify the disabled
    path set this flag on the app state before making requests.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if getattr(request.app.state, "security_headers_enabled", True):
            for header, value in _SECURITY_HEADERS.items():
                response.headers[header] = value
        return response
