from fastapi import FastAPI

from app.config.logging import configure_logging
from app.config.settings import get_settings


def create_app() -> FastAPI:
    """Create the FastAPI application without starting background jobs."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    return app


app = create_app()

