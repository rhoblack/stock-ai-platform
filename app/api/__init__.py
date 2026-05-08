"""FastAPI routers for dashboard read APIs."""

from app.api.approval_routes import router as approval_router
from app.api.auth_routes import router as auth_router
from app.api.health_routes import router as health_router
from app.api.metrics_routes import router as metrics_router
from app.api.paper_routes import router as paper_router
from app.api.preferences_routes import router as preferences_router
from app.api.real_order_routes import router as real_order_router
from app.api.routes import router
from app.api.validation_routes import router as validation_router
from app.api.watchlist_routes import router as watchlist_router

__all__ = [
    "approval_router",
    "auth_router",
    "health_router",
    "metrics_router",
    "paper_router",
    "preferences_router",
    "real_order_router",
    "router",
    "validation_router",
    "watchlist_router",
]
