import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router as api_router
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the APScheduler when ``settings.scheduler_enabled`` is True.

    The ``apscheduler`` import is lazy so test environments / CLIs that don't
    need scheduling never pay the import cost. Tests that don't enter a
    ``with TestClient(app)`` block skip lifespan entirely (Starlette behavior).
    """
    settings = get_settings()
    scheduler = None
    if settings.scheduler_enabled:
        try:
            from app.scheduler.scheduler import build_scheduler

            scheduler = build_scheduler(
                session_factory=SessionLocal,
                timezone=settings.timezone,
            )
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("scheduler started (timezone=%s)", settings.timezone)
        except Exception:  # noqa: BLE001 - never block app startup on scheduler
            logger.exception("scheduler failed to start; continuing without it")
    try:
        yield
    finally:
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("scheduler stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application without starting background jobs eagerly."""
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_dir=settings.log_dir,
        log_to_file=settings.log_to_file,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    app.include_router(api_router)
    return app


app = create_app()
