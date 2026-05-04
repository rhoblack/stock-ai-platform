"""Pydantic v1 response schemas for the v0.1 dashboard API.

Conventions:
    * Decimal-valued model fields are typed as ``Optional[str]`` and converted
      via a wildcard pre-validator so JSON output is lossless and stable.
    * ORM rows are read via ``orm_mode = True`` (Pydantic v1 syntax).
    * No request bodies in v0.1 — only GET responses.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, validator


class _BaseSchema(BaseModel):
    class Config:
        orm_mode = True

    @validator("*", pre=True, allow_reuse=True)
    def _decimal_to_str(cls, value):  # noqa: N805 - Pydantic validator signature
        if isinstance(value, Decimal):
            return str(value)
        return value


class RiskSummarySchema(_BaseSchema):
    level: str
    flags: List[str]
    penalty: Optional[str] = None


class StockBriefSchema(_BaseSchema):
    symbol: str
    name: str
    market: str
    sector: Optional[str] = None
    is_active: bool


class DailyPriceSchema(_BaseSchema):
    date: date_type
    open: Optional[str]
    high: Optional[str]
    low: Optional[str]
    close: Optional[str]
    volume: int
    trading_value: Optional[str] = None


class StockIndicatorSchema(_BaseSchema):
    date: date_type
    ma5: Optional[str]
    ma20: Optional[str]
    ma60: Optional[str]
    ma120: Optional[str]
    rsi14: Optional[str]
    macd: Optional[str]
    macd_signal: Optional[str]
    volume_ratio_20d: Optional[str]
    breakout_20d: Optional[bool]
    breakout_60d: Optional[bool]
    ma_alignment: Optional[str]
    technical_score: Optional[str]


class RecommendationResultSchema(_BaseSchema):
    days_after: int
    result_date: date_type
    open_return: Optional[str]
    high_return: Optional[str]
    low_return: Optional[str]
    close_return: Optional[str]
    max_return: Optional[str]
    max_drawdown: Optional[str]
    result_status: Optional[str]


class RecommendationItemSchema(_BaseSchema):
    recommendation_id: Optional[int] = None
    run_id: Optional[int] = None
    run_date: Optional[date_type] = None
    telegram_sent: Optional[bool] = None
    rank: int
    market: str
    symbol: str
    name: str
    grade: Optional[str]
    total_score: Optional[str]
    technical_score: Optional[str]
    news_score: Optional[str]
    supply_score: Optional[str]
    fundamental_score: Optional[str]
    ai_score: Optional[str]
    risk_score: Optional[str]
    reason: Optional[str]
    risk_note: Optional[str]
    snapshot_id: Optional[int]
    risk_level: Optional[str] = None
    risk_flags: List[str] = []
    risk_summary: Optional[RiskSummarySchema] = None
    results: List[RecommendationResultSchema] = []


class RecommendationRunSchema(_BaseSchema):
    run_id: int
    run_date: date_type
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    market_summary: Optional[Dict[str, Any]]
    telegram_sent: bool


class RecommendationRunDetailResponse(_BaseSchema):
    run: RecommendationRunSchema
    recommendations: List[RecommendationItemSchema]


class RecommendationHistoryItem(_BaseSchema):
    run: RecommendationRunSchema
    recommendation_count: int
    success_rate: Optional[str] = None
    avg_close_return_1d: Optional[str] = None
    avg_close_return_3d: Optional[str] = None
    avg_close_return_5d: Optional[str] = None
    avg_close_return_20d: Optional[str] = None


class RecommendationHistoryResponse(_BaseSchema):
    items: List[RecommendationHistoryItem]
    limit: int
    offset: int


class HoldingSchema(_BaseSchema):
    id: int
    symbol: str
    quantity: Optional[str]
    avg_buy_price: Optional[str]
    strategy_type: Optional[str]
    target_price: Optional[str]
    stop_loss_price: Optional[str]
    memo: Optional[str]
    is_active: bool


class HoldingsResponse(_BaseSchema):
    items: List[HoldingSchema]


class HoldingCheckSchema(_BaseSchema):
    id: int
    check_date: date_type
    check_type: str
    symbol: str
    current_price: Optional[str]
    avg_buy_price: Optional[str]
    return_rate: Optional[str]
    technical_score: Optional[str]
    news_score: Optional[str]
    earnings_score: Optional[str]
    ai_score: Optional[str]
    risk_score: Optional[str]
    total_score: Optional[str]
    grade: Optional[str]
    decision: Optional[str]
    reason: Optional[str]
    alert: bool
    snapshot_id: Optional[int]
    risk_level: Optional[str] = None
    risk_flags: List[str] = []
    risk_summary: Optional[RiskSummarySchema] = None


class HoldingChecksResponse(_BaseSchema):
    items: List[HoldingCheckSchema]


class StockDetailResponse(_BaseSchema):
    stock: StockBriefSchema
    latest_price: Optional[DailyPriceSchema] = None
    latest_indicator: Optional[StockIndicatorSchema] = None
    recent_recommendations: List[RecommendationItemSchema] = []
    recent_holding_checks: List[HoldingCheckSchema] = []


class MarketCapRankingSchema(_BaseSchema):
    rank_date: date_type
    market: str
    rank: int
    symbol: str
    name: str
    market_cap: Optional[str]
    close_price: Optional[str]
    listed_shares: Optional[int]
    sector: Optional[str]
    trading_value: Optional[str]
    is_analysis_target: bool


class MarketCapRankingResponse(_BaseSchema):
    rank_date: Optional[date_type] = None
    market: Optional[str] = None
    items: List[MarketCapRankingSchema]


class MarketRegimeSchema(_BaseSchema):
    id: int
    date: date_type
    market: str
    regime: str
    market_score: Optional[str]
    risk_level: Optional[str]
    reason: Optional[str]


class NewsItemSchema(_BaseSchema):
    id: int
    published_at: datetime
    available_at: Optional[datetime]
    source: str
    title: str
    url: Optional[str]
    related_symbols: Optional[List[str]]
    sentiment: Optional[str]
    importance: Optional[str]
    theme: Optional[str]


class NewsResponse(_BaseSchema):
    items: List[NewsItemSchema]
    limit: int
    offset: int


class JobRunSchema(_BaseSchema):
    job_id: int
    job_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    result_summary: Optional[Dict[str, Any]]
    success_count: Optional[int] = None
    failed_count: Optional[int] = None
    skipped_count: Optional[int] = None
    partial_count: Optional[int] = None
    total_count: Optional[int] = None
    provider_type: Optional[str] = None
    universe_name: Optional[str] = None
    batch_size: Optional[int] = None


class JobsResponse(_BaseSchema):
    items: List[JobRunSchema]
    limit: int
    offset: int


class TodayReportResponse(_BaseSchema):
    date: date_type
    market_regime: Optional[MarketRegimeSchema] = None
    latest_run: Optional[RecommendationRunSchema] = None
    top_recommendations: List[RecommendationItemSchema]
    holding_alerts: List[HoldingCheckSchema]


class SettingsResponse(_BaseSchema):
    app_env: str
    app_name: str
    timezone: str
    log_level: str
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    kis_app_key: str
    kis_app_secret: str
    kis_account_no: str
    kis_use_paper: bool
    scheduler_enabled: bool
    feature_real_order_execution: bool
    feature_full_auto: bool
    feature_paper_trading: bool
    feature_backtest: bool
    feature_custom_ai_training: bool
