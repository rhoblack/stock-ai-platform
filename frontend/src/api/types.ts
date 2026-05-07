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

// ----- v0.6 Phase D — fundamental / earnings evidence -----

export interface FundamentalEvidence {
  snapshot_date?: string
  fiscal_year?: number
  fiscal_quarter?: number | null
  per?: string | null
  pbr?: string | null
  roe?: string | null
  debt_ratio?: string | null
  revenue_growth_yoy?: string | null
  operating_income_growth_yoy?: string | null
  dividend_yield?: string | null
  reason?: string
}

export interface EarningsEvidence {
  latest_event_date?: string
  fiscal_year?: number
  fiscal_quarter?: number | null
  event_type?: string
  surprise_type?: string | null
  surprise_pct?: string | null
  operating_income_actual?: string | null
  operating_income_consensus?: string | null
  reason?: string
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
  report_score?: string | null
  theme_signal_score?: string | null
  report_evidence?: Record<string, unknown> | null
  // v0.5 Phase D — optional, only set when RealNewsScoreProducer /
  // DisclosureRiskProducer ran for this run. Older snapshots → null.
  news_evidence?: NewsEvidence | null
  disclosure_risk_evidence?: DisclosureRiskEvidence | null
  // v0.6 Phase D — set by RealFundamentalScoreProducer; null for older runs.
  fundamental_evidence?: FundamentalEvidence | null
  // Always null on the recommendation flow today (only HoldingCheckEngine
  // wires earnings_evidence). Kept for symmetry with HoldingCheck.
  earnings_evidence?: EarningsEvidence | null
  results?: RecommendationResult[]
}

export interface NewsEvidenceTopItem {
  title: string
  url: string | null
  provider: string | null
  published_at: string
  sentiment: string | null
}

export interface NewsEvidence {
  news_count: number
  positive_count: number
  neutral_count: number
  negative_count: number
  latest_news_at: string | null
  top_news: NewsEvidenceTopItem[]
}

export interface DisclosureRiskItem {
  title: string
  url: string | null
  provider: string | null
  published_at: string
}

export interface DisclosureRiskEvidence {
  risk_disclosure_count: number
  recent_risk_disclosures: DisclosureRiskItem[]
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
  // v0.6 Phase D — surfaced from holding-check DataSnapshot.market_context_json.
  news_evidence?: NewsEvidence | null
  disclosure_risk_evidence?: DisclosureRiskEvidence | null
  earnings_evidence?: EarningsEvidence | null
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

export interface ReportConsensus {
  symbol: string
  snapshot_date: string
  window_days: number
  report_count: number
  avg_target_price: string | null
  min_target_price: string | null
  max_target_price: string | null
  strong_buy_count: number
  buy_count: number
  hold_count: number
  sell_count: number
  strong_sell_count: number
  latest_published_at: string | null
}

export interface AnalystReport {
  id: number
  symbol: string | null
  company_name: string | null
  market: string | null
  report_type: string
  broker_name: string
  analyst_name: string | null
  published_at: string
  title: string
  rating: string | null
  normalized_rating: string | null
  target_price: string | null
  currency: string | null
  summary: string | null
  source_url: string | null
}

export interface RelatedTheme {
  theme_id: number
  theme_name: string
  theme_category: string
  direction: string
  time_horizon: string
  summary: string | null
  mapping_id: number
  impact_direction: string
  impact_strength: string | null
  impact_path: string | null
  relation_type: string | null
  benefit_type: string | null
  time_lag: string | null
  reason: string | null
}

export interface ReportSignalEvent {
  id: number
  report_id: number
  symbol: string | null
  theme_id: number | null
  event_type: string
  direction: string
  strength: string | null
  time_horizon: string
  summary: string | null
  evidence_json: Record<string, unknown> | null
}

export interface StockReportsResponse {
  symbol: string
  latest_consensus: ReportConsensus | null
  recent_reports: AnalystReport[]
  related_themes: RelatedTheme[]
  recent_signal_events: ReportSignalEvent[]
}

export interface StockDetailResponse {
  stock: StockBrief
  latest_price: DailyPriceRow | null
  latest_indicator: StockIndicatorRow | null
  recent_recommendations: RecommendationItem[]
  recent_holding_checks: HoldingCheck[]
  analyst_reports?: StockReportsResponse | null
}

export interface StockPriceSeriesResponse {
  symbol: string
  days: number
  count: number
  prices: DailyPriceRow[]
}

// ----- v0.6 Phase D — fundamentals / earnings / earnings calendar -----

export interface FundamentalSnapshot {
  snapshot_date: string
  fiscal_year: number
  fiscal_quarter: number | null
  revenue: string | null
  operating_income: string | null
  net_income: string | null
  total_assets: string | null
  total_liabilities: string | null
  total_equity: string | null
  eps: string | null
  bps: string | null
  per: string | null
  pbr: string | null
  roe: string | null
  debt_ratio: string | null
  dividend_yield: string | null
  revenue_growth_yoy: string | null
  operating_income_growth_yoy: string | null
  source: string | null
}

export interface StockFundamentalsResponse {
  symbol: string
  latest: FundamentalSnapshot | null
  history: FundamentalSnapshot[]
  count: number
}

export interface EarningsEvent {
  event_date: string
  fiscal_year: number
  fiscal_quarter: number | null
  event_type: string
  company_name: string | null
  revenue_actual: string | null
  revenue_consensus: string | null
  operating_income_actual: string | null
  operating_income_consensus: string | null
  net_income_actual: string | null
  net_income_consensus: string | null
  eps_actual: string | null
  eps_consensus: string | null
  surprise_type: string | null
  surprise_pct: string | null
  source: string | null
  memo: string | null
}

export interface StockEarningsResponse {
  symbol: string
  latest: EarningsEvent | null
  events: EarningsEvent[]
  count: number
}

export interface EarningsCalendarItem {
  symbol: string
  company_name: string | null
  event_date: string
  fiscal_year: number
  fiscal_quarter: number | null
  event_type: string
  surprise_type: string | null
  surprise_pct: string | null
}

export interface EarningsCalendarResponse {
  items: EarningsCalendarItem[]
  count: number
  from_date: string | null
  to_date: string | null
  surprise_type: string | null
  limit: number
}

// ----- /api/themes/* (v0.5 Phase D) -----

export interface ThemeRankingItem {
  theme_id: number
  theme_name: string
  theme_category: string
  direction: string
  time_horizon: string
  summary: string | null
  confidence: string | null
  source_report_id: number
  mapping_count: number
  signal_event_count: number
}

export interface ThemeRankingResponse {
  items: ThemeRankingItem[]
  category: string | null
  direction: string | null
  limit: number
}

export interface ThemeStockMapping {
  mapping_id: number
  theme_id: number
  symbol: string
  company_name: string | null
  market: string | null
  relation_type: string | null
  impact_direction: string
  impact_strength: string | null
  impact_path: string | null
  benefit_type: string | null
  time_lag: string | null
  reason: string | null
}

export interface ThemeDetailResponse {
  theme: ThemeRankingItem
  stock_mappings: ThemeStockMapping[]
  signal_events: ReportSignalEvent[]
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

// ----- v0.7 Phase D — Strategy / Backtest read-only API -----

export interface StrategyItem {
  name: string
  version: string
  description: string | null
}

export interface StrategiesResponse {
  items: StrategyItem[]
  count: number
}

export interface BacktestRunItem {
  id: number
  strategy_name: string
  strategy_version: string
  run_date: string
  start_date: string | null
  end_date: string | null
  signal_count: number
  buy_count: number
  pass_count: number
  avoid_count: number
  win_rate_1d: string | null
  win_rate_3d: string | null
  win_rate_5d: string | null
  win_rate_20d: string | null
  avg_return_1d: string | null
  avg_return_3d: string | null
  avg_return_5d: string | null
  avg_return_20d: string | null
  cost_adjusted_avg_return_5d: string | null
  max_drawdown: string | null
  status: string
  cost_model_version: string | null
  total_cost: string | null
}

export interface BacktestRunsResponse {
  items: BacktestRunItem[]
  count: number
  strategy: string | null
  limit: number
}

export interface BacktestResultItem {
  id: number
  symbol: string
  recommendation_id: number | null
  signal_action: 'BUY' | 'PASS' | 'AVOID' | string
  confidence: string | null
  reason: string | null
  grade: string | null
  total_score: string | null
  return_1d: string | null
  return_3d: string | null
  return_5d: string | null
  return_20d: string | null
  cost_adjusted_return_5d: string | null
  max_drawdown: string | null
  result_status: string | null
  regime: string | null
  evidence_json: Record<string, unknown> | null
}

export interface RegimeBreakdownItem {
  regime: string
  buy_count: number
  win_rate_5d: string | null
  avg_return_5d: string | null
  cost_adjusted_avg_return_5d: string | null
}

export interface BacktestRunDetailResponse {
  run: BacktestRunItem
  results: BacktestResultItem[]
  regime_breakdown: RegimeBreakdownItem[]
  cost_model_version: string | null
  total_cost: string | null
  summary_json: Record<string, unknown> | null
  notes: string | null
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

// ----- v0.8 Phase D — Auth -----

export interface LoginUser {
  id: number
  username: string
  is_admin: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  issued_at: string
  expires_at: string
  user: LoginUser
}

export interface MeResponse {
  auth_enabled: boolean
  via: string
  user: LoginUser | null
}

// ----- v0.8 Phase D — Watchlist -----

export interface WatchlistItem {
  id: number
  symbol: string
  memo: string | null
  created_at: string
  updated_at: string
}

export interface Watchlist {
  id: number
  name: string
  is_default: boolean
  item_count: number
  created_at: string
  updated_at: string
}

export interface WatchlistDetail extends Watchlist {
  items: WatchlistItem[]
}

export interface WatchlistsResponse {
  watchlists: Watchlist[]
}

export interface WatchlistStatusResponse {
  status: string
}

// ----- v0.9 Phase C — WatchlistItemsResponse (paginated) -----

export interface WatchlistItemsResponse {
  items: WatchlistItem[]
  total: number
  limit: number
  offset: number
}

// ----- v0.9 Phase D — UserPreference -----

export interface UserPreference {
  user_id: number
  default_watchlist_id: number | null
  default_market: string | null
  default_strategy: string | null
  dashboard_layout_json: unknown | null
  notification_preferences_json: unknown | null
  created_at: string
  updated_at: string
}

export interface UserPreferenceUpdateRequest {
  default_watchlist_id?: number | null
  default_market?: string | null
  default_strategy?: string | null
  dashboard_layout_json?: unknown | null
  notification_preferences_json?: unknown | null
}

// ----- v0.10 Phase D — Provider Health -----

export type ProviderCircuitState =
  | 'CLOSED'
  | 'OPEN'
  | 'HALF_OPEN'
  | 'UNREGISTERED'

export interface ProviderHealthItem {
  provider_name: string
  enabled: boolean
  configured: boolean
  circuit_state: ProviderCircuitState
  call_count: number
  success_count: number
  failure_count: number
  last_error_kind: string | null
  last_called_at: string | null
}

export interface ProviderHealthResponse {
  items: ProviderHealthItem[]
  count: number
}
