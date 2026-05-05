import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './tests/mswServer'

// jsdom 은 ResizeObserver 를 제공하지 않는다 — Recharts 의
// ResponsiveContainer 가 의존하므로 테스트 환경에 가벼운 mock 을 주입한다.
class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (!('ResizeObserver' in globalThis)) {
  ;(globalThis as unknown as { ResizeObserver: typeof ResizeObserverMock }).ResizeObserver =
    ResizeObserverMock
}

// MSW intercepts fetch in jsdom. Real HTTP calls are forbidden in tests
// so any unhandled request fails fast — keeps the v0.1 boundary
// (no real KIS / Telegram during tests) on the frontend side too.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
