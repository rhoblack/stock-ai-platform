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
