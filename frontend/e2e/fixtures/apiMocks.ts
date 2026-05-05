import { type Page, type Route } from '@playwright/test'

// v0.2 Phase F: e2e fixture. 각 테스트는 백엔드 없이 실행되며,
// Playwright 의 `page.route` 로 v0.1 백엔드의 13개 GET 라우터 응답을 mock 한다.
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

const HANDLERS: Array<{ pattern: RegExp; payload: unknown; status?: number }> = [
  { pattern: /\/health$/, payload: HEALTH },
  { pattern: /\/api\/reports\/today$/, payload: TODAY },
  { pattern: /\/api\/recommendations\/latest$/, payload: RECOMMENDATIONS_LATEST },
  { pattern: /\/api\/recommendations\/history(\?|$)/, payload: RECOMMENDATION_HISTORY },
  { pattern: /\/api\/recommendations\/\d+$/, payload: RECOMMENDATIONS_LATEST },
  { pattern: /\/api\/holdings\/checks\/latest(\?|$)/, payload: HOLDINGS_CHECKS_LATEST },
  { pattern: /\/api\/holdings\/005930\/checks(\?|$)/, payload: HOLDING_CHECKS_005930 },
  { pattern: /\/api\/holdings(\?|$)/, payload: HOLDINGS },
  { pattern: /\/api\/stocks\/005930\/prices(\?|$)/, payload: STOCK_PRICE_SERIES_005930 },
  { pattern: /\/api\/stocks\/005930(\?|$)/, payload: STOCK_DETAIL_005930 },
  { pattern: /\/api\/universe\/market-cap-top.*market=KOSDAQ/, payload: MARKET_CAP_KOSDAQ },
  { pattern: /\/api\/universe\/market-cap-top/, payload: MARKET_CAP_KOSPI },
  { pattern: /\/api\/jobs\/101$/, payload: JOB_DETAIL_101 },
  { pattern: /\/api\/jobs(\?|$)/, payload: JOBS_LIST },
  { pattern: /\/api\/market-regime\/latest/, payload: TODAY.market_regime },
  { pattern: /\/api\/news/, payload: { items: [], limit: 20, offset: 0 } },
  { pattern: /\/api\/settings$/, payload: SETTINGS_SAFE },
]

export async function installApiMocks(page: Page): Promise<void> {
  await page.route('**/api/**', handle)
  await page.route('**/health', handle)
}

async function handle(route: Route): Promise<void> {
  const url = route.request().url()
  for (const { pattern, payload, status = 200 } of HANDLERS) {
    if (pattern.test(url)) {
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
    body: JSON.stringify({ detail: `e2e mock missing for ${url}` }),
  })
}
