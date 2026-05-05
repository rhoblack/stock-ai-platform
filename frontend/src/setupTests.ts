import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './tests/mswServer'

// MSW intercepts fetch in jsdom. Real HTTP calls are forbidden in tests
// so any unhandled request fails fast — keeps the v0.1 boundary
// (no real KIS / Telegram during tests) on the frontend side too.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
