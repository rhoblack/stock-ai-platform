import { type Page, type Route } from '@playwright/test'

// v0.2 Phase F / v0.8 Phase D: e2e fixture.
// Playwright 의 `page.route` 로 백엔드 응답을 mock 한다.
// 실 KIS / 실 텔레그램 / 실 백엔드 호출은 절대 발생하지 않아야 한다.

const HEALTH = { status: 'ok', app: 'stock_ai_platform', env: 'e2e' }

const TODAY = {
  date: '2026-05-05',
  market_regime: {
    id: 1,
    date: '2026-05-05',
    market: 'KOSPI',
    regime: 'NEUTRAL',
    market_score: '50',
    risk_level: 'LOW',
    reason: 'e2e fixture',
  },
  latest_run: {
    run_id: 7,
    run_date: '2026-05-04',
    started_at: '2026-05-04T06:00:00Z',
    finished_at: '2026-05-04T06:00:30Z',
    status: 'SUCCESS',
    market_summary: { phase: 'e2e' },
    telegram_sent: false,
  },
  top_recommendations: [
    {
      recommendation_id: 1,
      run_id: 7,
      run_date: '2026-05-04',
      telegram_sent: false,
      rank: 1,
      market: 'KOSPI',
      symbol: '005930',
      name: '삼성전자',
      grade: 'A',
      total_score: '82',
      technical_score: '80',
      news_score: '50',
      supply_score: '55',
      fundamental_score: '50',
      ai_score: '55',
      risk_score: '0',
      reason: '관찰 후보',
      risk_note: null,
      snapshot_id: 11,
      risk_level: 'LOW',
      risk_flags: [],
      report_score: '75.00',
      theme_signal_score: '60.00',
      report_evidence: {
        report_score_adjustment: '2.50',
        theme_signal_adjustment: '1.00',
        top_themes: [{ theme_name: 'HBM' }],
      },
      results: [],
    },
  ],
  holding_alerts: [
    {
      id: 21,
      check_date: '2026-05-05',
      check_type: 'POST_MARKET',
      symbol: '000660',
      current_price: '170000',
      avg_buy_price: '190000',
      return_rate: '-10.5263',
      technical_score: '40',
      news_score: '50',
      earnings_score: '50',
      ai_score: '45',
      risk_score: '23',
      total_score: '20',
      grade: 'D',
      decision: 'SELL_REVIEW',
      reason: '20일선 이탈',
      alert: true,
      snapshot_id: 33,
      risk_level: 'HIGH',
      risk_flags: ['MA20_BREAKDOWN'],
    },
  ],
}

const JOBS_LIST = {
  items: [
    {
      job_id: 101,
      job_name: 'send_recommendation_report',
      started_at: '2026-05-04T22:52:00Z',
      finished_at: '2026-05-04T22:52:01Z',
      status: 'SUCCESS',
      error_message: null,
      result_summary: { notification_status: 'DRY_RUN', dry_run: true, run_id: 7 },
    },
    {
      job_id: 102,
      job_name: 'update_recommendation_results',
      started_at: '2026-05-04T22:53:00Z',
      finished_at: '2026-05-04T22:53:02Z',
      status: 'PARTIAL',
      error_message: '1 recommendations had no reference price',
      result_summary: { data_status: 'PARTIAL' },
    },
  ],
  limit: 50,
  offset: 0,
}

const JOB_DETAIL_101 = {
  ...JOBS_LIST.items[0],
  successes: [],
  skipped: [],
  failures: [],
  batches: [],
}

const RECOMMENDATIONS_LATEST = {
  run: TODAY.latest_run,
  recommendations: TODAY.top_recommendations,
}

const RECOMMENDATION_HISTORY = {
  items: [
    {
      run: TODAY.latest_run,
      recommendation_count: 1,
      success_rate: '60',
      avg_close_return_1d: '1.5',
      avg_close_return_3d: '2.0',
      avg_close_return_5d: '3.0',
      avg_close_return_20d: null,
    },
  ],
  limit: 20,
  offset: 0,
}

const HOLDINGS = {
  items: [
    {
      id: 1,
      symbol: '005930',
      quantity: '20',
      avg_buy_price: '66000',
      strategy_type: 'LONG',
      target_price: null,
      stop_loss_price: null,
      memo: null,
      is_active: true,
    },
  ],
}

const HOLDINGS_CHECKS_LATEST = { items: [] }

const HOLDING_CHECKS_005930 = {
  items: [],
  summary: {
    total_check_count: 0,
    alert_count: 0,
    high_risk_count: 0,
    latest_check_date: null,
    latest_total_score: null,
    previous_total_score: null,
    total_score_change: null,
    latest_return_rate: null,
    best_return_rate: null,
    worst_return_rate: null,
    latest_decision: null,
    latest_risk_level: null,
  },
}

const STOCK_DETAIL_005930 = {
  stock: {
    symbol: '005930',
    name: '삼성전자',
    market: 'KOSPI',
    sector: '반도체',
    is_active: true,
  },
  latest_price: {
    date: '2026-05-04',
    open: '69500',
    high: '70500',
    low: '69000',
    close: '70000',
    volume: 1500000,
    trading_value: '105000000000',
  },
  latest_indicator: {
    date: '2026-05-04',
    ma5: '70200',
    ma20: '69300',
    ma60: '68500',
    ma120: null,
    rsi14: '55',
    macd: '120',
    macd_signal: '110',
    volume_ratio_20d: '1.4',
    breakout_20d: true,
    breakout_60d: false,
    ma_alignment: 'BULL',
    technical_score: '78',
  },
  recent_recommendations: TODAY.top_recommendations,
  analyst_reports: {
    symbol: '005930',
    latest_consensus: {
      symbol: '005930',
      snapshot_date: '2026-05-04',
      window_days: 90,
      report_count: 2,
      avg_target_price: '82000',
      min_target_price: '78000',
      max_target_price: '86000',
      strong_buy_count: 0,
      buy_count: 2,
      hold_count: 0,
      sell_count: 0,
      strong_sell_count: 0,
      latest_published_at: '2026-05-02',
    },
    recent_reports: [
      {
        id: 31,
        symbol: '005930',
        company_name: '삼성전자',
        market: 'KOSPI',
        report_type: 'COMPANY',
        broker_name: '테스트증권',
        analyst_name: '홍길동',
        published_at: '2026-05-02',
        title: '삼성전자 HBM 수요 회복',
        rating: 'BUY',
        normalized_rating: 'BUY',
        target_price: '84000',
        currency: 'KRW',
        summary: 'HBM 수요 회복과 서버 메모리 가격 반등',
        source_url: 'https://example.com/reports/005930',
      },
    ],
    related_themes: [
      {
        theme_id: 41,
        theme_name: 'HBM',
        theme_category: 'SEMICONDUCTOR',
        direction: 'POSITIVE',
        time_horizon: 'MID',
        summary: 'AI 서버 메모리 수요',
        mapping_id: 51,
        impact_direction: 'POSITIVE',
        impact_strength: '0.800',
        impact_path: 'DEMAND_INCREASE',
        relation_type: 'SUPPLIER',
        benefit_type: 'PRICE_POWER',
        time_lag: 'MID',
        reason: 'HBM 공급사',
      },
    ],
    recent_signal_events: [
      {
        id: 61,
        report_id: 32,
        symbol: '005930',
        theme_id: 41,
        event_type: 'SUPPLY_SHORTAGE',
        direction: 'POSITIVE',
        strength: '0.700',
        time_horizon: 'MID',
        summary: 'HBM 공급 부족 지속',
        evidence_json: { source: 'fixture' },
      },
    ],
  },
  recent_holding_checks: [],
}

const STOCK_FUNDAMENTALS_005930 = {
  symbol: '005930',
  latest: {
    snapshot_date: '2026-05-01',
    fiscal_year: 2025,
    fiscal_quarter: 4,
    revenue: '100000',
    operating_income: '20000',
    net_income: '15000',
    total_assets: '500000',
    total_liabilities: '200000',
    total_equity: '300000',
    eps: '3500',
    bps: '60000',
    per: '12.0000',
    pbr: '1.2000',
    roe: '18.0000',
    debt_ratio: '40.0000',
    dividend_yield: '2.5000',
    revenue_growth_yoy: '12.0000',
    operating_income_growth_yoy: '18.0000',
    source: 'MANUAL',
  },
  history: [
    {
      snapshot_date: '2026-05-01',
      fiscal_year: 2025,
      fiscal_quarter: 4,
      revenue: '100000',
      operating_income: '20000',
      net_income: '15000',
      total_assets: '500000',
      total_liabilities: '200000',
      total_equity: '300000',
      eps: '3500',
      bps: '60000',
      per: '12.0000',
      pbr: '1.2000',
      roe: '18.0000',
      debt_ratio: '40.0000',
      dividend_yield: '2.5000',
      revenue_growth_yoy: '12.0000',
      operating_income_growth_yoy: '18.0000',
      source: 'MANUAL',
    },
  ],
  count: 1,
}

const STOCK_EARNINGS_005930 = {
  symbol: '005930',
  latest: {
    event_date: '2026-05-01',
    fiscal_year: 2026,
    fiscal_quarter: 1,
    event_type: 'REPORT',
    company_name: '삼성전자',
    revenue_actual: null,
    revenue_consensus: null,
    operating_income_actual: '110.0000',
    operating_income_consensus: '100.0000',
    net_income_actual: null,
    net_income_consensus: null,
    eps_actual: '3500.0000',
    eps_consensus: '3300.0000',
    surprise_type: 'BEAT',
    surprise_pct: '10.0000',
    source: 'MANUAL',
    memo: null,
  },
  events: [
    {
      event_date: '2026-05-01',
      fiscal_year: 2026,
      fiscal_quarter: 1,
      event_type: 'REPORT',
      company_name: '삼성전자',
      revenue_actual: null,
      revenue_consensus: null,
      operating_income_actual: '110.0000',
      operating_income_consensus: '100.0000',
      net_income_actual: null,
      net_income_consensus: null,
      eps_actual: '3500.0000',
      eps_consensus: '3300.0000',
      surprise_type: 'BEAT',
      surprise_pct: '10.0000',
      source: 'MANUAL',
      memo: null,
    },
  ],
  count: 1,
}

const EARNINGS_CALENDAR = {
  items: [
    {
      symbol: '005930',
      company_name: '삼성전자',
      event_date: '2099-05-08',
      fiscal_year: 2099,
      fiscal_quarter: 1,
      event_type: 'ANNOUNCEMENT',
      surprise_type: null,
      surprise_pct: null,
    },
    {
      symbol: '000660',
      company_name: 'SK하이닉스',
      event_date: '2099-05-10',
      fiscal_year: 2099,
      fiscal_quarter: 1,
      event_type: 'ANNOUNCEMENT',
      surprise_type: null,
      surprise_pct: null,
    },
  ],
  count: 2,
  from_date: null,
  to_date: null,
  surprise_type: null,
  limit: 5,
}

const STOCK_PRICE_SERIES_005930 = {
  symbol: '005930',
  days: 120,
  count: 5,
  prices: [
    {
      date: '2026-04-28',
      open: '69000',
      high: '69800',
      low: '68500',
      close: '69500',
      volume: 1_100_000,
      trading_value: '76450000000',
    },
    {
      date: '2026-04-29',
      open: '69500',
      high: '70200',
      low: '69300',
      close: '70000',
      volume: 1_250_000,
      trading_value: '87500000000',
    },
    {
      date: '2026-04-30',
      open: '70000',
      high: '70500',
      low: '69700',
      close: '70200',
      volume: 1_320_000,
      trading_value: '92664000000',
    },
    {
      date: '2026-05-03',
      open: '70200',
      high: '70800',
      low: '69900',
      close: '70300',
      volume: 1_400_000,
      trading_value: '98420000000',
    },
    {
      date: '2026-05-04',
      open: '70300',
      high: '71000',
      low: '70000',
      close: '70500',
      volume: 1_500_000,
      trading_value: '105750000000',
    },
  ],
}

const MARKET_CAP_KOSPI = {
  rank_date: '2026-05-04',
  market: 'KOSPI',
  items: [
    {
      rank_date: '2026-05-04',
      market: 'KOSPI',
      rank: 1,
      symbol: '005930',
      name: '삼성전자',
      market_cap: '450000000000000',
      close_price: '70000',
      listed_shares: 5_969_782_550,
      sector: '반도체',
      trading_value: '105000000000',
      is_analysis_target: true,
    },
    {
      rank_date: '2026-05-04',
      market: 'KOSPI',
      rank: 2,
      symbol: '000660',
      name: 'SK하이닉스',
      market_cap: '150000000000000',
      close_price: '180000',
      listed_shares: 728_002_365,
      sector: '반도체',
      trading_value: '90000000000',
      is_analysis_target: true,
    },
  ],
}

const MARKET_CAP_KOSDAQ = {
  rank_date: '2026-05-04',
  market: 'KOSDAQ',
  items: [
    {
      rank_date: '2026-05-04',
      market: 'KOSDAQ',
      rank: 1,
      symbol: '247540',
      name: '에코프로비엠',
      market_cap: '20000000000000',
      close_price: '230000',
      listed_shares: 97_802_000,
      sector: '2차전지',
      trading_value: '5000000000',
      is_analysis_target: true,
    },
  ],
}

const THEME_RANKING = {
  items: [
    {
      theme_id: 41,
      theme_name: 'HBM',
      theme_category: 'SEMICONDUCTOR',
      direction: 'POSITIVE',
      time_horizon: 'MID',
      summary: 'AI 서버 메모리 수요',
      confidence: '0.800',
      source_report_id: 12,
      mapping_count: 2,
      signal_event_count: 1,
    },
    {
      theme_id: 42,
      theme_name: '거래정지',
      theme_category: 'RISK',
      direction: 'NEGATIVE',
      time_horizon: 'SHORT',
      summary: '거래정지 위험',
      confidence: null,
      source_report_id: 12,
      mapping_count: 0,
      signal_event_count: 1,
    },
  ],
  category: null,
  direction: null,
  limit: 50,
}

const THEME_DETAIL_41 = {
  theme: THEME_RANKING.items[0],
  stock_mappings: [
    {
      mapping_id: 51,
      theme_id: 41,
      symbol: '005930',
      company_name: '삼성전자',
      market: 'KOSPI',
      relation_type: 'SUPPLIER',
      impact_direction: 'POSITIVE',
      impact_strength: '0.800',
      impact_path: 'DEMAND_INCREASE',
      benefit_type: 'PRICE_POWER',
      time_lag: 'MID',
      reason: 'HBM 공급사',
    },
    {
      mapping_id: 52,
      theme_id: 41,
      symbol: '000660',
      company_name: 'SK하이닉스',
      market: 'KOSPI',
      relation_type: null,
      impact_direction: 'POSITIVE',
      impact_strength: '0.900',
      impact_path: 'MARKET_SHARE_GAIN',
      benefit_type: null,
      time_lag: null,
      reason: null,
    },
  ],
  signal_events: [
    {
      id: 71,
      report_id: 32,
      symbol: '005930',
      theme_id: 41,
      event_type: 'SUPPLY_SHORTAGE',
      direction: 'POSITIVE',
      strength: '0.700',
      time_horizon: 'MID',
      summary: 'HBM 공급 부족 지속',
      evidence_json: { source: 'fixture' },
    },
  ],
}

const STRATEGIES = {
  count: 3,
  items: [
    {
      name: 'TopGradeStrategy',
      version: 'v1.0.0',
      description: 'Trade on the recommendation grade alone.',
    },
    {
      name: 'HighScoreStrategy',
      version: 'v1.0.0',
      description: "Trade on the recommendation's total_score alone.",
    },
    {
      name: 'MultiSignalStrategy',
      version: 'v1.0.0',
      description: 'Multi-factor rule combining v0.4~v0.6 signals.',
    },
  ],
}

const BACKTEST_RUNS_LIST = {
  count: 1,
  strategy: null,
  limit: 20,
  items: [
    {
      id: 42,
      strategy_name: 'top_grade',
      strategy_version: 'v1.0.0',
      run_date: '2026-05-06',
      start_date: '2026-04-01',
      end_date: '2026-05-04',
      signal_count: 5,
      buy_count: 2,
      pass_count: 2,
      avoid_count: 1,
      win_rate_1d: '0.5000',
      win_rate_3d: null,
      win_rate_5d: '0.5000',
      win_rate_20d: null,
      avg_return_1d: '1.0000',
      avg_return_3d: null,
      avg_return_5d: '1.5000',
      avg_return_20d: null,
      cost_adjusted_avg_return_5d: '1.1700',
      max_drawdown: '-2.5000',
      status: 'SUCCESS',
      cost_model_version: 'constant-v1',
      total_cost: '0.00330',
    },
  ],
}

const BACKTEST_RUN_DETAIL_42 = {
  run: BACKTEST_RUNS_LIST.items[0],
  results: [
    {
      id: 1001,
      symbol: '005930',
      recommendation_id: 71,
      signal_action: 'BUY',
      confidence: '0.7500',
      reason: 'grade=A',
      grade: 'A',
      total_score: '80.0000',
      return_1d: '1.0000',
      return_3d: null,
      return_5d: '1.5000',
      return_20d: null,
      cost_adjusted_return_5d: '1.1700',
      max_drawdown: '-2.5000',
      result_status: 'SUCCESS',
      regime: 'UPTREND_EARLY',
      evidence_json: { grade: 'A' },
    },
  ],
  regime_breakdown: [
    {
      regime: 'UPTREND_EARLY',
      buy_count: 2,
      win_rate_5d: '0.5000',
      avg_return_5d: '1.5000',
      cost_adjusted_avg_return_5d: '1.1700',
    },
  ],
  cost_model_version: 'constant-v1',
  total_cost: '0.00330',
  summary_json: { notes: 'BUY signals only' },
  notes: 'win_rate / avg_return / max_drawdown are computed over BUY signals only.',
}

// v0.8 Phase D — Auth + Watchlist fixtures
const AUTH_ME = { auth_enabled: false, via: 'dev_fallback', user: null }

const WATCHLISTS_EMPTY = { watchlists: [] }

const WATCHLISTS_WITH_DEFAULT = {
  watchlists: [
    {
      id: 1,
      name: '관심종목',
      is_default: true,
      item_count: 1,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
    },
  ],
}

const WATCHLIST_DETAIL_1 = {
  id: 1,
  name: '관심종목',
  is_default: true,
  item_count: 1,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
  items: [
    {
      id: 1,
      symbol: '005930',
      memo: '삼성전자',
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
    },
  ],
}

const PROVIDER_HEALTH_DEFAULT_OFF = {
  // v0.10 / v0.11 Phase D — DART / RSS default-OFF; KIS configured but
  // unregistered (no calls flowed through call_with_resilience in the
  // e2e fixture).  Phase D adds the 24h aggregates + recent_failures
  // surface so the panel exercises the new cells.
  items: [
    {
      provider_name: 'kis',
      enabled: true,
      configured: true,
      circuit_state: 'CLOSED',
      call_count: 50,
      success_count: 49,
      failure_count: 1,
      last_error_kind: 'TIMEOUT',
      last_called_at: '2026-05-07T12:00:00Z',
      call_count_24h: 50,
      success_count_24h: 49,
      failure_count_24h: 1,
      success_rate_24h: 0.98,
      avg_attempts_24h: 1.05,
      recent_failures: [
        { timestamp: '2026-05-07T11:30:00Z', error_kind: 'TIMEOUT' },
      ],
    },
    {
      provider_name: 'dart',
      enabled: false,
      configured: false,
      circuit_state: 'UNREGISTERED',
      call_count: 0,
      success_count: 0,
      failure_count: 0,
      last_error_kind: null,
      last_called_at: null,
      call_count_24h: 0,
      success_count_24h: 0,
      failure_count_24h: 0,
      success_rate_24h: null,
      avg_attempts_24h: null,
      recent_failures: [],
    },
    {
      provider_name: 'rss',
      enabled: false,
      configured: false,
      circuit_state: 'UNREGISTERED',
      call_count: 0,
      success_count: 0,
      failure_count: 0,
      last_error_kind: null,
      last_called_at: null,
      call_count_24h: 0,
      success_count_24h: 0,
      failure_count_24h: 0,
      success_rate_24h: null,
      avg_attempts_24h: null,
      recent_failures: [],
    },
  ],
  count: 3,
}

const SETTINGS_SAFE = {
  app_env: 'e2e',
  app_name: 'stock_ai_platform',
  timezone: 'Asia/Seoul',
  log_level: 'INFO',
  telegram_enabled: false,
  telegram_bot_token: '7739****51ZI',
  telegram_chat_id: '82****08',
  kis_app_key: 'PSnm****Zqry',
  kis_app_secret: 'XxC8****4yc=',
  kis_account_no: '5015****1-01',
  kis_use_paper: true,
  scheduler_enabled: false,
  feature_real_order_execution: false,
  feature_full_auto: false,
  feature_paper_trading: false,
  feature_backtest: false,
  feature_custom_ai_training: false,
}

const VALIDATION_REPORT_EMPTY = {
  generated_at: '2026-05-08T00:00:00',
  run_count: 0,
  signal_count: 0,
  buy_count: 0,
  win_rate_5d: null,
  avg_return_5d: null,
  score_delta: {
    total_scored: 0,
    policy_enabled_count: 0,
    avg_delta: null,
    positive_delta_count: 0,
    negative_delta_count: 0,
    neutral_delta_count: 0,
    data_source_counts: {},
  },
}

// v0.14 Phase E — Paper / Simulation Trading e2e fixture.
// VirtualAccount with one open position and a recent fill so the page
// renders all of its sections (account / positions / pnl / orders).
const PAPER_ACCOUNT = {
  id: 1,
  name: 'paper',
  currency: 'KRW',
  paper_trading_enabled: true,
  initial_cash: '10000000',
  cash_balance: '9899935',
  market_value: '110000',
  total_value: '10009935',
  realized_pnl: '0',
  unrealized_pnl: '9935',
  snapshot_date: '2026-05-08',
  created_at: '2026-05-08T00:00:00',
  updated_at: '2026-05-08T16:30:00',
}

const PAPER_ORDERS = {
  orders: [
    {
      id: 101,
      account_id: 1,
      symbol: '005930',
      side: 'BUY',
      quantity: 10,
      order_type: 'MARKET',
      limit_price: null,
      status: 'FILLED',
      idempotency_key: null,
      reason: null,
      note: null,
      created_at: '2026-05-08T15:55:00',
      updated_at: '2026-05-08T16:00:00',
    },
    {
      id: 102,
      account_id: 1,
      symbol: '005930',
      side: 'SELL',
      quantity: 5,
      order_type: 'LIMIT',
      limit_price: '12000',
      status: 'CREATED',
      idempotency_key: 'manual-1',
      reason: null,
      note: null,
      created_at: '2026-05-08T15:58:00',
      updated_at: '2026-05-08T15:58:00',
    },
  ],
  total: 2,
  limit: 50,
}

const PAPER_POSITIONS = {
  positions: [
    {
      id: 1,
      account_id: 1,
      symbol: '005930',
      quantity: 10,
      avg_cost: '10006.5',
      realized_pnl: '0',
      last_close: '11000',
      market_value: '110000',
      unrealized_pnl: '9935',
      updated_at: '2026-05-08T16:00:00',
    },
  ],
  total: 1,
}

const PAPER_PNL = {
  snapshots: [
    {
      snapshot_date: '2026-05-07',
      cash_balance: '10000000',
      market_value: '0',
      total_value: '10000000',
      realized_pnl: '0',
      unrealized_pnl: '0',
    },
    {
      snapshot_date: '2026-05-08',
      cash_balance: '9899935',
      market_value: '110000',
      total_value: '10009935',
      realized_pnl: '0',
      unrealized_pnl: '9935',
    },
  ],
  total: 2,
}

const HANDLERS: Array<{ pattern: RegExp; payload: unknown; status?: number; method?: string }> = [
  { pattern: /\/health$/, payload: HEALTH },
  // v0.8 Phase D — auth + watchlist
  { pattern: /\/api\/auth\/me$/, payload: AUTH_ME },
  { pattern: /\/api\/auth\/login$/, payload: { access_token: 'test-token', token_type: 'bearer', expires_in: 3600, issued_at: '2026-05-06T00:00:00', expires_at: '2026-05-06T01:00:00', user: { id: 1, username: 'admin', is_admin: false } }, method: 'POST' },
  { pattern: /\/api\/auth\/logout$/, payload: { status: 'ok' }, method: 'POST' },
  { pattern: /\/api\/watchlists\/1\/items\/005930$/, payload: { status: 'removed' }, method: 'DELETE' },
  { pattern: /\/api\/watchlists\/1\/items(\?|$)/, payload: WATCHLIST_DETAIL_1.items[0], method: 'POST' },
  { pattern: /\/api\/watchlists\/1(\?|$)/, payload: WATCHLIST_DETAIL_1 },
  { pattern: /\/api\/watchlists(\?|$)/, payload: WATCHLISTS_EMPTY },
  { pattern: /\/api\/reports\/today$/, payload: TODAY },
  { pattern: /\/api\/recommendations\/latest$/, payload: RECOMMENDATIONS_LATEST },
  { pattern: /\/api\/recommendations\/history(\?|$)/, payload: RECOMMENDATION_HISTORY },
  { pattern: /\/api\/recommendations\/\d+$/, payload: RECOMMENDATIONS_LATEST },
  { pattern: /\/api\/holdings\/checks\/latest(\?|$)/, payload: HOLDINGS_CHECKS_LATEST },
  { pattern: /\/api\/holdings\/005930\/checks(\?|$)/, payload: HOLDING_CHECKS_005930 },
  { pattern: /\/api\/holdings(\?|$)/, payload: HOLDINGS },
  { pattern: /\/api\/stocks\/005930\/prices(\?|$)/, payload: STOCK_PRICE_SERIES_005930 },
  { pattern: /\/api\/stocks\/005930\/fundamentals(\?|$)/, payload: STOCK_FUNDAMENTALS_005930 },
  { pattern: /\/api\/stocks\/005930\/earnings(\?|$)/, payload: STOCK_EARNINGS_005930 },
  { pattern: /\/api\/stocks\/005930(\?|$)/, payload: STOCK_DETAIL_005930 },
  { pattern: /\/api\/calendar\/earnings(\?|$)/, payload: EARNINGS_CALENDAR },
  { pattern: /\/api\/universe\/market-cap-top.*market=KOSDAQ/, payload: MARKET_CAP_KOSDAQ },
  { pattern: /\/api\/universe\/market-cap-top/, payload: MARKET_CAP_KOSPI },
  { pattern: /\/api\/jobs\/101$/, payload: JOB_DETAIL_101 },
  { pattern: /\/api\/jobs(\?|$)/, payload: JOBS_LIST },
  { pattern: /\/api\/themes\/ranking(\?|$)/, payload: THEME_RANKING },
  { pattern: /\/api\/themes\/41(\?|$)/, payload: THEME_DETAIL_41 },
  { pattern: /\/api\/strategies(\?|$)/, payload: STRATEGIES },
  { pattern: /\/api\/backtest\/runs\/42(\?|$)/, payload: BACKTEST_RUN_DETAIL_42 },
  { pattern: /\/api\/backtest\/runs(\?|$)/, payload: BACKTEST_RUNS_LIST },
  { pattern: /\/api\/market-regime\/latest/, payload: TODAY.market_regime },
  { pattern: /\/api\/news/, payload: { items: [], limit: 20, offset: 0 } },
  { pattern: /\/api\/settings$/, payload: SETTINGS_SAFE },
  // v0.10 Phase D — read-only Provider Health snapshot.
  { pattern: /\/api\/health\/providers$/, payload: PROVIDER_HEALTH_DEFAULT_OFF },
  // v0.13 Phase D — Validation Report (read-only, default empty; more specific first)
  { pattern: /\/api\/validation\/report\/by-strategy(\?|$)/, payload: { count: 0, items: [] } },
  { pattern: /\/api\/validation\/report\/by-regime(\?|$)/, payload: { count: 0, items: [] } },
  { pattern: /\/api\/validation\/report\/by-sector(\?|$)/, payload: { count: 0, items: [] } },
  { pattern: /\/api\/validation\/report(\?|$)/, payload: VALIDATION_REPORT_EMPTY },
  // v0.14 Phase E — Paper / Simulation Trading (GET 4종).  POST/DELETE are
  // intentionally NOT mocked: the e2e fixture treats PAPER_TRADING_ENABLED
  // as false so the order form's mutation should land on the
  // bottom-of-the-list 404 fallback (acting like a 503-ish disabled response
  // for the dashboard) — preventing accidental "real order" code paths.
  { pattern: /\/api\/paper\/account(\?|$)/, payload: PAPER_ACCOUNT },
  { pattern: /\/api\/paper\/orders\/\d+$/, payload: { detail: 'paper trading disabled' }, status: 503, method: 'DELETE' },
  { pattern: /\/api\/paper\/orders$/, payload: { detail: 'paper trading disabled' }, status: 503, method: 'POST' },
  { pattern: /\/api\/paper\/orders(\?|$)/, payload: PAPER_ORDERS },
  { pattern: /\/api\/paper\/positions(\?|$)/, payload: PAPER_POSITIONS },
  { pattern: /\/api\/paper\/pnl(\?|$)/, payload: PAPER_PNL },
]

export async function installApiMocks(page: Page): Promise<void> {
  await page.route('**/api/**', handle)
  await page.route('**/health', handle)
}

async function handle(route: Route): Promise<void> {
  const url = route.request().url()
  const method = route.request().method().toUpperCase()
  for (const { pattern, payload, status = 200, method: handlerMethod } of HANDLERS) {
    if (pattern.test(url)) {
      // If handler specifies a method, only match that method.
      // GET handlers (no method) should only match GET requests.
      if (handlerMethod) {
        if (method !== handlerMethod) continue
      } else if (method !== 'GET') {
        continue
      }
      await route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(payload),
      })
      return
    }
  }
  await route.fulfill({
    status: 404,
    contentType: 'application/json',
    body: JSON.stringify({ detail: `e2e mock missing for ${url} [${method}]` }),
  })
}
