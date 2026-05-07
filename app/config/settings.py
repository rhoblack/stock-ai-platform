import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv


load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "stock_ai_platform"))
    app_host: str = field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    app_port: int = field(default_factory=lambda: _as_int(os.getenv("APP_PORT"), 8000))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))
    log_to_file: bool = field(default_factory=lambda: _as_bool(os.getenv("LOG_TO_FILE"), False))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Seoul"))

    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    sqlite_database_url: str = field(
        default_factory=lambda: os.getenv("SQLITE_DATABASE_URL", "sqlite:///./stock_ai.db"),
    )

    kis_app_key: str = field(default_factory=lambda: os.getenv("KIS_APP_KEY", ""))
    kis_app_secret: str = field(default_factory=lambda: os.getenv("KIS_APP_SECRET", ""))
    kis_account_no: str = field(default_factory=lambda: os.getenv("KIS_ACCOUNT_NO", ""))
    kis_account_product_code: str = field(
        default_factory=lambda: os.getenv("KIS_ACCOUNT_PRODUCT_CODE", "01"),
    )
    kis_base_url: str = field(
        default_factory=lambda: os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443"),
    )
    kis_paper_base_url: str = field(
        default_factory=lambda: os.getenv(
            "KIS_PAPER_BASE_URL",
            "https://openapivts.koreainvestment.com:29443",
        ),
    )
    kis_use_paper: bool = field(default_factory=lambda: _as_bool(os.getenv("KIS_USE_PAPER"), True))
    kis_timeout_seconds: int = field(default_factory=lambda: _as_int(os.getenv("KIS_TIMEOUT_SECONDS"), 10))

    collect_market: str = field(default_factory=lambda: os.getenv("COLLECT_MARKET", "KOSPI"))
    market_cap_limit: int = field(default_factory=lambda: _as_int(os.getenv("MARKET_CAP_LIMIT"), 500))
    market_cap_universe_name: str = field(
        default_factory=lambda: os.getenv("MARKET_CAP_UNIVERSE_NAME", "MARKET_CAP_TOP_500"),
    )
    daily_price_lookback_days: int = field(
        default_factory=lambda: _as_int(os.getenv("DAILY_PRICE_LOOKBACK_DAYS"), 1),
    )
    daily_price_batch_size: int = field(
        default_factory=lambda: _as_int(os.getenv("DAILY_PRICE_BATCH_SIZE"), 100),
    )
    indicator_universe_name: str = field(
        default_factory=lambda: os.getenv("INDICATOR_UNIVERSE_NAME", "MARKET_CAP_TOP_500"),
    )
    indicator_lookback_days: int = field(
        default_factory=lambda: _as_int(os.getenv("INDICATOR_LOOKBACK_DAYS"), 250),
    )
    indicator_batch_size: int = field(
        default_factory=lambda: _as_int(os.getenv("INDICATOR_BATCH_SIZE"), 100),
    )

    telegram_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("TELEGRAM_ENABLED"), False),
    )
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""),
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""),
    )
    telegram_api_base_url: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org"),
    )
    telegram_timeout_seconds: int = field(
        default_factory=lambda: _as_int(os.getenv("TELEGRAM_TIMEOUT_SECONDS"), 10),
    )
    scheduler_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("SCHEDULER_ENABLED"), True),
    )

    # v0.5 Phase A — News collection opt-in.
    # 외부 뉴스 / RSS 호출은 default OFF. 운영자가 .env 에 NEWS_COLLECTION_ENABLED=true
    # 를 명시적으로 설정한 경우에만 collect_news 잡이 NewsCollector 를 실행한다.
    # disabled 상태에서는 잡이 SKIPPED 로 즉시 종료 (외부 호출 0건).
    news_collection_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("NEWS_COLLECTION_ENABLED"), False),
    )

    # v0.5 Phase B — Disclosure collection opt-in.
    # 외부 DART / KRX 호출은 default OFF. .env 의 DISCLOSURE_COLLECTION_ENABLED=true
    # 명시 시에만 collect_disclosures 잡이 DisclosureCollector 를 실행. 그 외엔
    # SKIPPED 로 즉시 종료 (외부 호출 0건).
    disclosure_collection_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("DISCLOSURE_COLLECTION_ENABLED"), False),
    )

    # v0.8 Phase B -- single-user authentication foundation.
    # Default OFF: dev / CI / local environments keep the existing read-only
    # API surface unchanged. When AUTH_ENABLED=true is exported (typically in
    # prod), routers using `require_auth` will reject unauthenticated requests.
    # JWT_SECRET MUST be set when AUTH_ENABLED=true -- startup rejects an
    # empty secret to prevent token forgery. See app/auth/security.py and
    # app/auth/dependencies.py.
    auth_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("AUTH_ENABLED"), False),
    )
    jwt_secret: str | None = field(
        default_factory=lambda: os.getenv("JWT_SECRET") or None,
    )
    jwt_algorithm: str = field(
        default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256"),
    )
    jwt_expires_minutes: int = field(
        default_factory=lambda: _as_int(os.getenv("JWT_EXPIRES_MINUTES"), 1440),
    )
    # scrypt cost parameters. Defaults match a >100ms hash on modern hardware
    # (RFC 7914 recommended floor: n=2^14, r=8, p=1). Tests inject lower n
    # (`password_hash_n = 2**10`) to keep the suite fast.
    password_hash_n: int = field(
        default_factory=lambda: _as_int(os.getenv("PASSWORD_HASH_N"), 1 << 14),
    )
    password_hash_r: int = field(
        default_factory=lambda: _as_int(os.getenv("PASSWORD_HASH_R"), 8),
    )
    password_hash_p: int = field(
        default_factory=lambda: _as_int(os.getenv("PASSWORD_HASH_P"), 1),
    )

    # v0.9 Phase A -- Security Hardening.
    # Rate limiting via slowapi. Default ON; set RATE_LIMIT_ENABLED=false in dev
    # to bypass without changing code. The conftest autouse fixture also disables
    # it for the test suite so existing tests are never affected.
    rate_limit_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("RATE_LIMIT_ENABLED"), True),
    )
    rate_limit_default: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_DEFAULT", "100/minute"),
    )
    rate_limit_auth: str = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_AUTH", "5/minute"),
    )

    # Security response headers middleware. Default ON.
    security_headers_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("SECURITY_HEADERS_ENABLED"), True),
    )

    # In-memory brute force protection for POST /api/auth/login.
    # Tracks failures per (username + source_ip_hash) composite key.
    # Plain IPs are NEVER stored -- only the SHA256 hash via hash_for_audit().
    auth_bruteforce_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("AUTH_BRUTEFORCE_ENABLED"), True),
    )
    auth_bruteforce_max_failures: int = field(
        default_factory=lambda: _as_int(os.getenv("AUTH_BRUTEFORCE_MAX_FAILURES"), 5),
    )
    auth_bruteforce_window_seconds: int = field(
        default_factory=lambda: _as_int(os.getenv("AUTH_BRUTEFORCE_WINDOW_SECONDS"), 300),
    )
    auth_bruteforce_lockout_seconds: int = field(
        default_factory=lambda: _as_int(os.getenv("AUTH_BRUTEFORCE_LOCKOUT_SECONDS"), 900),
    )

    # v0.9 Phase B -- Structured logging + Request ID + optional Sentry.
    # structured_logging_enabled=False keeps human-readable text format in dev.
    # Set STRUCTURED_LOGGING_ENABLED=true in production for JSON log ingestion.
    structured_logging_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("STRUCTURED_LOGGING_ENABLED"), False),
    )
    log_request_id_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("LOG_REQUEST_ID_ENABLED"), True),
    )

    # Optional Sentry integration. Disabled by default.
    # sentry_enabled=True + sentry_dsn=None → WARNING logged, Sentry skipped.
    sentry_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("SENTRY_ENABLED"), False),
    )
    sentry_dsn: str | None = field(
        default_factory=lambda: os.getenv("SENTRY_DSN") or None,
    )
    sentry_environment: str | None = field(
        default_factory=lambda: os.getenv("SENTRY_ENVIRONMENT") or None,
    )

    # v0.10 Phase A -- Provider resilience runtime settings.
    # PROVIDER_RESILIENCE_ENABLED=false (default) keeps all wrapper opt-in logic
    # inactive.  Set to true in production once providers are hardened.
    # Per-provider enable flags (DART_ENABLED, RSS_NEWS_ENABLED) are added in
    # Phase B and Phase C respectively.
    provider_resilience_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("PROVIDER_RESILIENCE_ENABLED"), False),
    )
    provider_default_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("PROVIDER_DEFAULT_TIMEOUT_S") or "10.0"),
    )
    provider_default_max_attempts: int = field(
        default_factory=lambda: _as_int(os.getenv("PROVIDER_DEFAULT_MAX_ATTEMPTS"), 3),
    )
    provider_default_base_delay_s: float = field(
        default_factory=lambda: float(os.getenv("PROVIDER_DEFAULT_BASE_DELAY_S") or "0.5"),
    )
    provider_default_max_delay_s: float = field(
        default_factory=lambda: float(os.getenv("PROVIDER_DEFAULT_MAX_DELAY_S") or "10.0"),
    )
    provider_circuit_breaker_failure_threshold: int = field(
        default_factory=lambda: _as_int(os.getenv("PROVIDER_CIRCUIT_BREAKER_FAILURE_THRESHOLD"), 5),
    )
    provider_circuit_breaker_reset_timeout_s: float = field(
        default_factory=lambda: float(
            os.getenv("PROVIDER_CIRCUIT_BREAKER_RESET_TIMEOUT_S") or "60.0"
        ),
    )

    # v0.10 Phase B -- DART OpenAPI provider runtime settings.
    # DART_ENABLED=false (default) keeps the DartFundamental/Earnings/Disclosure
    # providers inert -- they are never instantiated by the provider factory and
    # any direct call returns DartNotConfiguredError.  Set DART_ENABLED=true +
    # DART_API_KEY=<crtfc_key> in operator-private prod only.  Personal /
    # research / non-commercial use only -- see PLANS.md PLAN-0010 Phase B
    # license memo.
    dart_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("DART_ENABLED"), False),
    )
    dart_api_key: str = field(
        default_factory=lambda: os.getenv("DART_API_KEY", ""),
    )
    dart_base_url: str = field(
        default_factory=lambda: os.getenv("DART_BASE_URL", "https://opendart.fss.or.kr"),
    )
    dart_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("DART_TIMEOUT_S") or "10.0"),
    )
    dart_max_attempts: int = field(
        default_factory=lambda: _as_int(os.getenv("DART_MAX_ATTEMPTS"), 3),
    )
    dart_provider_name: str = field(
        default_factory=lambda: os.getenv("DART_PROVIDER_NAME", "dart"),
    )

    # v0.10 Phase C -- RSS / News provider runtime settings.
    # RSS_NEWS_ENABLED=false (default) keeps RssNewsProvider inert -- the
    # factory raises RssNotConfiguredError so any scheduler / collector that
    # would otherwise call it short-circuits with no HTTP fetch.  Operators
    # who opt in must also list explicit feed URLs in RSS_FEED_URLS (comma
    # separated); auto-crawling of unspecified URLs is forbidden.  Stored
    # rows are metadata only (title / url / published_at / source / category /
    # short summary) -- body / paragraph / full_text fields are stripped by
    # the parser.
    rss_news_enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("RSS_NEWS_ENABLED"), False),
    )
    rss_feed_urls: str = field(
        default_factory=lambda: os.getenv("RSS_FEED_URLS", ""),
    )
    rss_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("RSS_TIMEOUT_S") or "10.0"),
    )
    rss_max_attempts: int = field(
        default_factory=lambda: _as_int(os.getenv("RSS_MAX_ATTEMPTS"), 3),
    )
    rss_provider_name: str = field(
        default_factory=lambda: os.getenv("RSS_PROVIDER_NAME", "rss"),
    )

    feature_real_order_execution: bool = field(
        default_factory=lambda: _as_bool(os.getenv("FEATURE_REAL_ORDER_EXECUTION"), False),
    )
    feature_full_auto: bool = field(
        default_factory=lambda: _as_bool(os.getenv("FEATURE_FULL_AUTO"), False),
    )
    feature_paper_trading: bool = field(
        default_factory=lambda: _as_bool(os.getenv("FEATURE_PAPER_TRADING"), False),
    )
    feature_backtest: bool = field(
        default_factory=lambda: _as_bool(os.getenv("FEATURE_BACKTEST"), False),
    )
    feature_custom_ai_training: bool = field(
        default_factory=lambda: _as_bool(os.getenv("FEATURE_CUSTOM_AI_TRAINING"), False),
    )

    @property
    def effective_database_url(self) -> str:
        return self.database_url or self.sqlite_database_url

    @property
    def effective_kis_base_url(self) -> str:
        return self.kis_paper_base_url if self.kis_use_paper else self.kis_base_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
