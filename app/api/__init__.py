"""FastAPI routers for dashboard read APIs."""

from app.api.auth_routes import router as auth_router
from app.api.health_routes import router as health_router
from app.api.preferences_routes import router as preferences_router
from app.api.routes import router
from app.api.watchlist_routes import router as watchlist_router

__all__ = [
    "auth_router",
    "health_router",
    "preferences_router",
    "router",
    "watchlist_router",
]
