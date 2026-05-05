import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

// Default handlers shared across tests. Per-test overrides go through
// `server.use(...)` inside individual test files. Wildcard host pattern
// keeps tests stable regardless of the jsdom default base URL.
export const handlers = [
  http.get('*/health', () =>
    HttpResponse.json({ status: 'ok', app: 'stock_ai_platform', env: 'test' }),
  ),
]

export const server = setupServer(...handlers)
