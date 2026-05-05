import { describe, expect, it } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { http, HttpResponse } from 'msw'
import { useHealth } from '@/hooks/useHealth'
import { server } from './mswServer'

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('useHealth', () => {
  it('returns mocked /health payload', async () => {
    const { result } = renderHook(() => useHealth(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({
      status: 'ok',
      app: 'stock_ai_platform',
      env: 'test',
    })
  })

  it('exposes an error state when /health fails', async () => {
    server.use(
      http.get('*/health', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 503 }),
      ),
    )
    const { result } = renderHook(() => useHealth(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeDefined()
  })
})
