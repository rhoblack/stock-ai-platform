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
]

export const server = setupServer(...handlers)
