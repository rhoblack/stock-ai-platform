import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import (
    auth_router,
    health_router,
    metrics_router,
    paper_router,
    preferences_router,
    router as api_router,
    validation_router,
    watchlist_router,
)
from app.auth.brute_force import BruteForceGuard
from app.auth.security import validate_auth_settings
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.db.session import SessionLocal
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.monitoring.sentry import init_sentry


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
        structured_logging_enabled=settings.structured_logging_enabled,
        log_request_id_enabled=settings.log_request_id_enabled,
    )

    # v0.8 Phase B -- fail fast if AUTH_ENABLED=true is set without a secret.
    validate_auth_settings(settings)

    # v0.9 Phase B -- optional Sentry error monitoring.
    # init_sentry is a no-op when sentry_enabled=False (default).
    init_sentry(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # v0.9 Phase A -- Security Hardening
    # ------------------------------------------------------------------

    # Rate limiter (slowapi). The limiter key-func returns a unique UUID when
    # app.state.rate_limit_enabled is False so no request ever hits the limit.
    # The conftest autouse fixture sets this to False for the test suite.
    app.state.limiter = limiter
    app.state.rate_limit_enabled = settings.rate_limit_enabled
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Security response headers. The middleware checks app.state at request
    # time so tests can toggle it without restarting.
    app.state.security_headers_enabled = settings.security_headers_enabled

    # Brute force guard. When disabled, app.state.bruteforce_guard is None and
    # auth_routes skips the check entirely.
    if settings.auth_bruteforce_enabled:
        app.state.bruteforce_guard = BruteForceGuard(
            max_failures=settings.auth_bruteforce_max_failures,
            window_seconds=settings.auth_bruteforce_window_seconds,
            lockout_seconds=settings.auth_bruteforce_lockout_seconds,
        )
    else:
        app.state.bruteforce_guard = None
    app.state.bruteforce_enabled = settings.auth_bruteforce_enabled

    # ------------------------------------------------------------------
    # v0.9 Phase B -- Global exception handler
    # Returns generic 500; stack trace goes to logs only, never to response.
    # request_id is included in the body for client-side log correlation.
    # ------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "unhandled exception path=%s request_id=%s",
            request.url.path,
            request_id,
            exc_info=exc,
        )
        body: dict = {"detail": "internal server error"}
        if request_id:
            body["request_id"] = request_id
        return JSONResponse(status_code=500, content=body)

    # ------------------------------------------------------------------
    # Middleware registration — order matters (last added = outermost).
    #
    # Request flow:  SecurityHeaders → RequestID → SlowAPI → route handler
    # Response flow: route handler → SlowAPI → RequestID → SecurityHeaders
    #
    # SlowAPI (innermost): rate limiting; 429 responses also get X-Request-ID
    #   and security headers because they pass through the outer middlewares.
    # RequestID (middle): assigns / echoes X-Request-ID; sets request.state
    #   and the contextvars slot so loggers can include it automatically.
    # SecurityHeaders (outermost): injects 4 security headers on all responses.
    # ------------------------------------------------------------------
    app.add_middleware(SlowAPIMiddleware)       # innermost
    app.add_middleware(RequestIDMiddleware)     # middle  (v0.9 Phase B)
    app.add_middleware(SecurityHeadersMiddleware)  # outermost

    # ------------------------------------------------------------------

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    app.include_router(auth_router)
    app.include_router(watchlist_router)
    app.include_router(preferences_router)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(validation_router)
    app.include_router(paper_router)
    app.include_router(api_router)

    # v0.11 Phase C -- initialise Prometheus metrics bundle when the
    # operator opted in.  init_default_metrics is idempotent + a no-op
    # when PROMETHEUS_ENABLED=false.
    from app.monitoring.prometheus import init_default_metrics  # noqa: PLC0415

    init_default_metrics(settings)
    return app


app = create_app()
