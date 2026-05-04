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
