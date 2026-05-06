"""v0.9 Phase A -- Security Hardening middleware package."""

from app.middleware.security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
