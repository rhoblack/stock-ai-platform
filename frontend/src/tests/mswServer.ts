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
  http.get('*/api/stocks/:symbol', () =>
    HttpResponse.json({ detail: 'not found' }, { status: 404 }),
  ),
]

export const server = setupServer(...handlers)
