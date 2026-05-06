"""v0.9 Phase B — RequestIDMiddleware.

Assigns a unique request-id to every inbound HTTP request:

  * If the caller supplies ``X-Request-ID`` the value is reused as-is.
  * Otherwise a fresh UUID4 is generated.

The id is stored in two places:
  * ``request.state.request_id`` — accessible to route handlers and
    exception handlers via the ``Request`` object.
  * ``request_id_var`` (``contextvars.ContextVar``) — read by
    ``RequestIDFilter`` in the logging layer so every log line emitted
    during the request automatically carries the id.

The id is echoed back in the ``X-Request-ID`` response header so callers
can correlate client-side errors with server-side logs.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Module-level ContextVar consumed by RequestIDFilter in app/config/logging.py
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject and propagate X-Request-ID through the request lifecycle."""

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self._header_name) or str(uuid4())
        request.state.request_id = request_id

        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers[self._header_name] = request_id
        return response
