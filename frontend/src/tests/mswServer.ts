import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

// Default handlers shared across tests. Per-test overrides go through
// `server.use(...)` inside individual test files. Wildcard host pattern
// keeps tests stable regardless of the jsdom default base URL.
//
// 기본 응답은 의도적으로 "데이터 없음" 형태 — 화면 placeholder / empty
// state 가 자연스럽게 노출되도록 하고, 실제 데이터 검증이 필요한 테스트는
// `server.use(...)` 로 재정의한다.
export const handlers = [
  http.get('*/health', () =>
    HttpResponse.json({ status: 'ok', app: 'stock_ai_platform', env: 'test' }),
  ),
  http.get('*/api/jobs', () =>
    HttpResponse.json({ items: [], limit: 50, offset: 0 }),
  ),
  http.get('*/api/jobs/:jobId', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
  http.get('*/api/reports/today', () =>
    HttpResponse.json({
      date: '2026-05-05',
      market_regime: null,
      latest_run: null,
      top_recommendations: [],
      holding_alerts: [],
    }),
  ),
  http.get('*/api/recommendations/latest', () =>
    HttpResponse.json({ detail: 'No recommendation runs found' }, { status: 404 }),
  ),
  http.get('*/api/recommendations/history', () =>
    HttpResponse.json({ items: [], limit: 20, offset: 0 }),
  ),
  http.get('*/api/recommendations/:runId', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
  http.get('*/api/holdings', () => HttpResponse.json({ items: [] })),
  http.get('*/api/holdings/checks/latest', () => HttpResponse.json({ items: [] })),
  http.get('*/api/holdings/:symbol/checks', () =>
    HttpResponse.json({
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
    }),
  ),
  http.get('*/api/stocks/:symbol/prices', ({ params }) =>
    HttpResponse.json({
      symbol: String(params.symbol ?? ''),
      days: 120,
      count: 0,
      prices: [],
    }),
  ),
  http.get('*/api/stocks/:symbol/fundamentals', ({ params }) =>
    HttpResponse.json({
      symbol: String(params.symbol ?? ''),
      latest: null,
      history: [],
      count: 0,
    }),
  ),
  http.get('*/api/stocks/:symbol/earnings', ({ params }) =>
    HttpResponse.json({
      symbol: String(params.symbol ?? ''),
      latest: null,
      events: [],
      count: 0,
    }),
  ),
  http.get('*/api/calendar/earnings', () =>
    HttpResponse.json({
      items: [],
      count: 0,
      from_date: null,
      to_date: null,
      surprise_type: null,
      limit: 20,
    }),
  ),
  http.get('*/api/stocks/:symbol', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
  http.get('*/api/universe/market-cap-top', () =>
    HttpResponse.json({ rank_date: null, market: 'KOSPI', items: [] }),
  ),
  http.get('*/api/themes/ranking', () =>
    HttpResponse.json({ items: [], category: null, direction: null, limit: 50 }),
  ),
  http.get('*/api/themes/:themeId', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
  http.get('*/api/strategies', () =>
    HttpResponse.json({ items: [], count: 0 }),
  ),
  http.get('*/api/backtest/runs/:runId', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
  http.get('*/api/backtest/runs', () =>
    HttpResponse.json({ items: [], count: 0, strategy: null, limit: 20 }),
  ),
  http.get('*/api/settings', () =>
    HttpResponse.json({
      app_env: 'test',
      app_name: 'stock_ai_platform',
      timezone: 'Asia/Seoul',
      log_level: 'INFO',
      telegram_enabled: false,
      telegram_bot_token: 'fake****test',
      telegram_chat_id: '12****90',
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
    }),
  ),

  // v0.8 Phase D — Auth
  http.get('*/api/auth/me', () =>
    HttpResponse.json({ auth_enabled: false, via: 'dev_fallback', user: null }),
  ),
  http.post('*/api/auth/login', () =>
    HttpResponse.json({
      access_token: 'test-token',
      token_type: 'bearer',
      expires_in: 3600,
      issued_at: '2026-05-06T00:00:00',
      expires_at: '2026-05-06T01:00:00',
      user: { id: 1, username: 'testuser', is_admin: false },
    }),
  ),
  http.post('*/api/auth/logout', () => HttpResponse.json({ status: 'ok' })),

  // v0.8 Phase D — Watchlists
  http.get('*/api/watchlists', () =>
    HttpResponse.json({ watchlists: [] }),
  ),
  http.get('*/api/watchlists/:id', ({ params }) =>
    HttpResponse.json({
      id: Number(params.id),
      name: '관심종목',
      is_default: true,
      item_count: 0,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
      items: [],
    }),
  ),
  http.post('*/api/watchlists', () =>
    HttpResponse.json({
      id: 1,
      name: '관심종목',
      is_default: true,
      item_count: 0,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
    }),
  ),
  http.post('*/api/watchlists/:id/items', () =>
    HttpResponse.json({
      id: 1,
      symbol: 'AAPL',
      memo: null,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
    }),
  ),
  http.delete('*/api/watchlists/:id/items/:symbol', () =>
    HttpResponse.json({ status: 'removed' }),
  ),

  // v0.9 Phase C/D — Watchlist PATCH / DELETE / items list / item PATCH
  http.patch('*/api/watchlists/:id', ({ params }) =>
    HttpResponse.json({
      id: Number(params.id),
      name: '관심종목',
      is_default: true,
      item_count: 0,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-07T00:00:00',
    }),
  ),
  http.delete('*/api/watchlists/:id', () =>
    HttpResponse.json({ status: 'ok' }),
  ),
  http.get('*/api/watchlists/:id/items', () =>
    HttpResponse.json({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    }),
  ),
  http.patch('*/api/watchlists/:id/items/:symbol', ({ params }) =>
    HttpResponse.json({
      id: 1,
      symbol: String(params.symbol ?? ''),
      memo: null,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-07T00:00:00',
    }),
  ),

  // v0.9 Phase D — UserPreference
  http.get('*/api/users/me/preferences', () =>
    HttpResponse.json({
      user_id: 1,
      default_watchlist_id: null,
      default_market: null,
      default_strategy: null,
      dashboard_layout_json: null,
      notification_preferences_json: null,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-06T00:00:00',
    }),
  ),
  http.put('*/api/users/me/preferences', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      user_id: 1,
      default_watchlist_id: body.default_watchlist_id ?? null,
      default_market: body.default_market ?? null,
      default_strategy: body.default_strategy ?? null,
      dashboard_layout_json: body.dashboard_layout_json ?? null,
      notification_preferences_json: body.notification_preferences_json ?? null,
      created_at: '2026-05-06T00:00:00',
      updated_at: '2026-05-07T00:00:00',
    })
  }),
]

export const server = setupServer(...handlers)
