// Hand-written API shapes for v0.2 Phase A/B. Replace / augment via
// `npm run openapi` (writes to src/api/types.gen.ts) starting Phase C
// once the schema set stabilises.
//
// All Decimal-ish fields are serialised as strings on the wire (the
// FastAPI Pydantic `_decimal_to_str` validator). Use `Number(value)`
// at the very edge of rendering (Number.isFinite check first).

export interface HealthResponse {
  status: string
  app: string
  env: string
}

// ----- shared sub-shapes -----

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface RiskSummary {
  level: string
  flags: string[]
  penalty?: string | null
}

export interface RecommendationResult {
  days_after: number
  result_date: string
  open_return: string | null
  high_return: string | null
  low_return: string | null
  close_return: string | null
  max_return: string | null
  max_drawdown: string | null
  result_status: string | null
}

export interface RecommendationItem {
  recommendation_id?: number | null
  run_id?: number | null
  run_date?: string | null
  telegram_sent?: boolean | null
  rank: number
  market: string
  symbol: string
  name: string
  grade: string | null
  total_score: string | null
  technical_score: string | null
  news_score: string | null
  supply_score: string | null
  fundamental_score: string | null
  ai_score: string | null
  risk_score: string | null
  reason: string | null
  risk_note: string | null
  snapshot_id: number | null
  risk_level?: string | null
  risk_flags?: string[]
  risk_summary?: RiskSummary | null
  results?: RecommendationResult[]
}

export interface HoldingCheck {
  id: number
  check_date: string
  check_type: 'PRE_MARKET' | 'POST_MARKET' | string
  symbol: string
  current_price: string | null
  avg_buy_price: string | null
  return_rate: string | null
  technical_score: string | null
  news_score: string | null
  earnings_score: string | null
  ai_score: string | null
  risk_score: string | null
  total_score: string | null
  grade: string | null
  decision: string | null
  reason: string | null
  alert: boolean
  snapshot_id: number | null
  risk_level?: string | null
  risk_flags?: string[]
  risk_summary?: RiskSummary | null
}

export interface MarketRegime {
  id: number
  date: string
  market: string
  regime: string
  market_score: string | null
  risk_level: string | null
  reason: string | null
}

export interface RecommendationRun {
  run_id: number
  run_date: string
  started_at: string
  finished_at: string | null
  status: string
  market_summary: Record<string, unknown> | null
  telegram_sent: boolean
}

// ----- /api/reports/today -----

export interface TodayReportResponse {
  date: string
  market_regime: MarketRegime | null
  latest_run: RecommendationRun | null
  top_recommendations: RecommendationItem[]
  holding_alerts: HoldingCheck[]
}

// ----- /api/universe/market-cap-top -----

export interface MarketCapRanking {
  rank_date: string
  market: string
  rank: number
  symbol: string
  name: string
  market_cap: string | null
  close_price: string | null
  listed_shares: number | null
  sector: string | null
  trading_value: string | null
  is_analysis_target: boolean
}

export interface MarketCapRankingResponse {
  rank_date: string | null
  market: string | null
  items: MarketCapRanking[]
}

// ----- /api/settings -----

export interface SettingsResponse {
  app_env: string
  app_name: string
  timezone: string
  log_level: string
  telegram_enabled: boolean
  telegram_bot_token: string
  telegram_chat_id: string
  kis_app_key: string
  kis_app_secret: string
  kis_account_no: string
  kis_use_paper: boolean
  scheduler_enabled: boolean
  feature_real_order_execution: boolean
  feature_full_auto: boolean
  feature_paper_trading: boolean
  feature_backtest: boolean
  feature_custom_ai_training: boolean
}

// ----- /api/holdings -----

export interface Holding {
  id: number
  symbol: string
  quantity: string | null
  avg_buy_price: string | null
  strategy_type: string | null
  target_price: string | null
  stop_loss_price: string | null
  memo: string | null
  is_active: boolean
}

export interface HoldingsResponse {
  items: Holding[]
}

export interface HoldingChecksResponse {
  items: HoldingCheck[]
}

export interface HoldingCheckSymbolMetrics {
  total_check_count: number
  alert_count: number
  high_risk_count: number
  latest_check_date: string | null
  latest_total_score: string | null
  previous_total_score: string | null
  total_score_change: string | null
  latest_return_rate: string | null
  best_return_rate: string | null
  worst_return_rate: string | null
  latest_decision: string | null
  latest_risk_level: string | null
}

export interface HoldingCheckSymbolResponse {
  items: HoldingCheck[]
  summary: HoldingCheckSymbolMetrics
}

// ----- /api/stocks/{symbol} -----

export interface StockBrief {
  symbol: string
  name: string
  market: string
  sector: string | null
  is_active: boolean
}

export interface DailyPriceRow {
  date: string
  open: string | null
  high: string | null
  low: string | null
  close: string | null
  volume: number
  trading_value: string | null
}

export interface StockIndicatorRow {
  date: string
  ma5: string | null
  ma20: string | null
  ma60: string | null
  ma120: string | null
  rsi14: string | null
  macd: string | null
  macd_signal: string | null
  volume_ratio_20d: string | null
  breakout_20d: boolean | null
  breakout_60d: boolean | null
  ma_alignment: string | null
  technical_score: string | null
}

export interface StockDetailResponse {
  stock: StockBrief
  latest_price: DailyPriceRow | null
  latest_indicator: StockIndicatorRow | null
  recent_recommendations: RecommendationItem[]
  recent_holding_checks: HoldingCheck[]
}

export interface StockPriceSeriesResponse {
  symbol: string
  days: number
  count: number
  prices: DailyPriceRow[]
}

// ----- /api/recommendations -----

export interface RecommendationRunDetailResponse {
  run: RecommendationRun
  recommendations: RecommendationItem[]
}

export interface RecommendationHistoryItem {
  run: RecommendationRun
  recommendation_count: number
  success_rate: string | null
  avg_close_return_1d: string | null
  avg_close_return_3d: string | null
  avg_close_return_5d: string | null
  avg_close_return_20d: string | null
}

export interface RecommendationHistoryResponse {
  items: RecommendationHistoryItem[]
  limit: number
  offset: number
}

// ----- /api/jobs -----

export type JobStatus = 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'FAILED' | string

export interface JobRun {
  job_id: number
  job_name: string
  started_at: string
  finished_at: string | null
  status: JobStatus
  error_message: string | null
  result_summary: Record<string, unknown> | null
  success_count?: number | null
  failed_count?: number | null
  skipped_count?: number | null
  partial_count?: number | null
  total_count?: number | null
  provider_type?: string | null
  universe_name?: string | null
  batch_size?: number | null
}

export interface JobRunDetail extends JobRun {
  successes: Array<Record<string, unknown>>
  skipped: Array<Record<string, unknown>>
  failures: Array<Record<string, unknown>>
  batches: Array<Record<string, unknown>>
}

export interface JobsResponse {
  items: JobRun[]
  limit: number
  offset: number
}

// Convenience: keys we expect inside result_summary (rendered by the
// JobsTable + TodayReport summaries). All optional — different jobs
// surface different subsets.
export interface JobResultSummaryKeys {
  data_status?: string
  notification_status?: string
  dry_run?: boolean
  check_type?: string
  notification_log_id?: number | null
  recommendation_count?: number
  holding_check_count?: number
  alert_sent_count?: number
  saved_count?: number
  market_cap_status?: string
  daily_price_status?: string
}
