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
    # v0.3 Phase B — defaulted None so older callers / fixtures stay valid.
    atr14: Optional[str] = None
    candle_patterns: Optional[List[str]] = None
    volatility_band: Optional[str] = None


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
    report_score: Optional[str] = None
    theme_signal_score: Optional[str] = None
    report_evidence: Optional[Dict[str, Any]] = None
    # v0.5 Phase D — surface news_evidence (set by RealNewsScoreProducer) and
    # disclosure_risk_evidence (set by DisclosureRiskProducer) that are stored
    # inside the run's DataSnapshot.market_context_json. Both are optional;
    # absent for v0.4 / pre-v0.5 runs that did not wire those producers.
    news_evidence: Optional[Dict[str, Any]] = None
    disclosure_risk_evidence: Optional[Dict[str, Any]] = None
    # v0.6 Phase D — fundamental_evidence (RealFundamentalScoreProducer) and
    # earnings_evidence (placeholder — always null on recommendation flow in
    # Phase C, but kept for symmetry with HoldingCheckSchema and to stay
    # forward-compatible if a future producer wires it on recommendations).
    # Both whitelisted at the API layer; absent for pre-v0.6 runs.
    fundamental_evidence: Optional[Dict[str, Any]] = None
    earnings_evidence: Optional[Dict[str, Any]] = None
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
    # v0.6 Phase D — surface news/disclosure/earnings evidence stored inside
    # the holding-check DataSnapshot.market_context_json. Whitelisted at the
    # API layer; absent for pre-v0.5/v0.6 holding checks.
    news_evidence: Optional[Dict[str, Any]] = None
    disclosure_risk_evidence: Optional[Dict[str, Any]] = None
    earnings_evidence: Optional[Dict[str, Any]] = None


class HoldingChecksResponse(_BaseSchema):
    items: List[HoldingCheckSchema]


class HoldingCheckSymbolMetrics(_BaseSchema):
    total_check_count: int = 0
    alert_count: int = 0
    high_risk_count: int = 0
    latest_check_date: Optional[date_type] = None
    latest_total_score: Optional[str] = None
    previous_total_score: Optional[str] = None
    total_score_change: Optional[str] = None
    latest_return_rate: Optional[str] = None
    best_return_rate: Optional[str] = None
    worst_return_rate: Optional[str] = None
    latest_decision: Optional[str] = None
    latest_risk_level: Optional[str] = None


class HoldingCheckSymbolResponse(_BaseSchema):
    items: List[HoldingCheckSchema]
    summary: HoldingCheckSymbolMetrics


class ReportConsensusSchema(_BaseSchema):
    symbol: str
    snapshot_date: date_type
    window_days: int
    report_count: int
    avg_target_price: Optional[str] = None
    min_target_price: Optional[str] = None
    max_target_price: Optional[str] = None
    strong_buy_count: int = 0
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    strong_sell_count: int = 0
    latest_published_at: Optional[date_type] = None


class AnalystReportSchema(_BaseSchema):
    id: int
    symbol: Optional[str] = None
    company_name: Optional[str] = None
    market: Optional[str] = None
    report_type: str
    broker_name: str
    analyst_name: Optional[str] = None
    published_at: date_type
    title: str
    rating: Optional[str] = None
    normalized_rating: Optional[str] = None
    target_price: Optional[str] = None
    currency: Optional[str] = None
    summary: Optional[str] = None
    source_url: Optional[str] = None


class RelatedThemeSchema(_BaseSchema):
    theme_id: int
    theme_name: str
    theme_category: str
    direction: str
    time_horizon: str
    summary: Optional[str] = None
    mapping_id: int
    impact_direction: str
    impact_strength: Optional[str] = None
    impact_path: Optional[str] = None
    relation_type: Optional[str] = None
    benefit_type: Optional[str] = None
    time_lag: Optional[str] = None
    reason: Optional[str] = None


class ReportSignalEventSchema(_BaseSchema):
    id: int
    report_id: int
    symbol: Optional[str] = None
    theme_id: Optional[int] = None
    event_type: str
    direction: str
    strength: Optional[str] = None
    time_horizon: str
    summary: Optional[str] = None
    evidence_json: Optional[Dict[str, Any]] = None


class StockReportsResponse(_BaseSchema):
    symbol: str
    latest_consensus: Optional[ReportConsensusSchema] = None
    recent_reports: List[AnalystReportSchema] = []
    related_themes: List[RelatedThemeSchema] = []
    recent_signal_events: List[ReportSignalEventSchema] = []


# ----- v0.5 Phase D — themes API -----


class ThemeStockMappingSchema(_BaseSchema):
    """Theme → stock mapping (theme is the parent context).

    Distinct from :class:`RelatedThemeSchema`, which embeds theme + mapping
    fields together for the *stock* side. This schema is returned by the
    theme detail endpoint and intentionally omits ``theme_*`` fields since
    callers already know which theme they queried.
    """

    mapping_id: int
    theme_id: int
    symbol: str
    company_name: Optional[str] = None
    market: Optional[str] = None
    relation_type: Optional[str] = None
    impact_direction: str
    impact_strength: Optional[str] = None
    impact_path: Optional[str] = None
    benefit_type: Optional[str] = None
    time_lag: Optional[str] = None
    reason: Optional[str] = None


class ThemeRankingItemSchema(_BaseSchema):
    theme_id: int
    theme_name: str
    theme_category: str
    direction: str
    time_horizon: str
    summary: Optional[str] = None
    confidence: Optional[str] = None
    source_report_id: int
    mapping_count: int = 0
    signal_event_count: int = 0


class ThemeRankingResponse(_BaseSchema):
    items: List[ThemeRankingItemSchema]
    category: Optional[str] = None
    direction: Optional[str] = None
    limit: int


class ThemeDetailResponse(_BaseSchema):
    theme: ThemeRankingItemSchema
    stock_mappings: List[ThemeStockMappingSchema] = []
    signal_events: List[ReportSignalEventSchema] = []


class StockDetailResponse(_BaseSchema):
    stock: StockBriefSchema
    latest_price: Optional[DailyPriceSchema] = None
    latest_indicator: Optional[StockIndicatorSchema] = None
    recent_recommendations: List[RecommendationItemSchema] = []
    recent_holding_checks: List[HoldingCheckSchema] = []
    analyst_reports: Optional[StockReportsResponse] = None


class StockPriceSeriesResponse(_BaseSchema):
    symbol: str
    days: int
    count: int
    prices: List[DailyPriceSchema] = []


# ----- v0.6 Phase D — fundamentals / earnings / earnings calendar -----


class FundamentalSnapshotSchema(_BaseSchema):
    """One fundamental_snapshots row, safe numeric fields only.

    Excludes: source_file_path, body / content / full_text / raw_text /
    paragraph / 본문 / 원문 / 전문 (the model does not declare these — this is
    additionally enforced by `_assert_no_source_file_path` API tests).
    """

    snapshot_date: date_type
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    revenue: Optional[str] = None
    operating_income: Optional[str] = None
    net_income: Optional[str] = None
    total_assets: Optional[str] = None
    total_liabilities: Optional[str] = None
    total_equity: Optional[str] = None
    eps: Optional[str] = None
    bps: Optional[str] = None
    per: Optional[str] = None
    pbr: Optional[str] = None
    roe: Optional[str] = None
    debt_ratio: Optional[str] = None
    dividend_yield: Optional[str] = None
    revenue_growth_yoy: Optional[str] = None
    operating_income_growth_yoy: Optional[str] = None
    source: Optional[str] = None


class StockFundamentalsResponse(_BaseSchema):
    symbol: str
    latest: Optional[FundamentalSnapshotSchema] = None
    history: List[FundamentalSnapshotSchema] = []
    count: int


class EarningsEventSchema(_BaseSchema):
    """One earnings_events row, safe numeric fields only.

    `memo` is allowed but capped to 500 chars by the model. `source_file_path`
    / body / paragraph / 본문 are not stored on the model.
    """

    event_date: date_type
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    event_type: str
    company_name: Optional[str] = None
    revenue_actual: Optional[str] = None
    revenue_consensus: Optional[str] = None
    operating_income_actual: Optional[str] = None
    operating_income_consensus: Optional[str] = None
    net_income_actual: Optional[str] = None
    net_income_consensus: Optional[str] = None
    eps_actual: Optional[str] = None
    eps_consensus: Optional[str] = None
    surprise_type: Optional[str] = None
    surprise_pct: Optional[str] = None
    source: Optional[str] = None
    memo: Optional[str] = None


class StockEarningsResponse(_BaseSchema):
    symbol: str
    latest: Optional[EarningsEventSchema] = None
    events: List[EarningsEventSchema] = []
    count: int


class EarningsCalendarItemSchema(_BaseSchema):
    symbol: str
    company_name: Optional[str] = None
    event_date: date_type
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    event_type: str
    surprise_type: Optional[str] = None
    surprise_pct: Optional[str] = None


class EarningsCalendarResponse(_BaseSchema):
    items: List[EarningsCalendarItemSchema]
    count: int
    from_date: Optional[date_type] = None
    to_date: Optional[date_type] = None
    surprise_type: Optional[str] = None
    limit: int


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


class JobRunDetailSchema(JobRunSchema):
    successes: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    batches: List[Dict[str, Any]] = []


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
