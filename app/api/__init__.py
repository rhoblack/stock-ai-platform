"""FastAPI routers for dashboard read APIs."""

from app.api.auth_routes import router as auth_router
from app.api.routes import router

__all__ = ["auth_router", "router"]
