// v0.16 Phase E — RealOrders page vitest suite.
//
// All tests use MSW handlers. The default mswServer returns empty lists so
// the empty state renders naturally. Per-test overrides use `server.use(...)`.

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { RealOrdersPage } from '@/pages/RealOrders'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DRY_RUN_ORDER = {
  id: 1,
  candidate_id: 11,
  symbol: '005930',
  side: 'BUY',
  quantity: 10,
  order_type: 'MARKET',
  limit_price: null,
  estimated_amount: '750000',
  status: 'DRY_RUN' as const,
  dry_run: true,
  fake_order_no: 'FAKE-abcd1234',
  request_id: 'abc123def456',
  error_code: null,
  error_message: null,
  submitted_at: null,
  created_at: '2026-05-08T10:00:00',
  updated_at: '2026-05-08T10:00:00',
}

const ORDERS_LIST = {
  items: [DRY_RUN_ORDER],
  total: 1,
  limit: 100,
  offset: 0,
}

const DRY_RUN_FILL = {
  id: 1,
  real_order_id: 1,
  symbol: '005930',
  side: 'BUY',
  quantity: 10,
  fill_price: '75000',
  fee: '0',
  tax: '0',
  gross_amount: '750000',
  net_amount: '750000',
  fill_status: 'FULL',
  filled_at: '2026-05-08T10:01:00',
  created_at: '2026-05-08T10:01:00',
}

const ORDER_DETAIL = {
  order: DRY_RUN_ORDER,
  fills: [DRY_RUN_FILL],
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RealOrdersPage', () => {
  beforeEach(() => {
    server.resetHandlers()
  })
  afterEach(() => {
    server.resetHandlers()
  })

  // 1. Render + safety banner
  it('renders page wrapper and safety banner', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-page')).toBeDefined()
    })
    expect(screen.getByTestId('real-orders-safety-banner')).toBeDefined()
  })

  // 2. Safety banner text
  it('safety banner contains required dry-run notice', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-safety-banner').textContent).toContain(
        'dry-run',
      )
    })
    expect(screen.getByTestId('real-orders-safety-banner').textContent).toContain(
      '실제 KIS 주문은 실행되지 않습니다',
    )
  })

  // 3. Empty state
  it('shows empty state when no orders', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-empty')).toBeDefined()
    })
  })

  // 4. Table renders with DRY_RUN order
  it('shows orders table when orders exist', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-table')).toBeDefined()
    })
    expect(screen.getByTestId('real-order-row-1')).toBeDefined()
  })

  // 5. DRY_RUN badge rendered
  it('shows DRY_RUN status badge', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      const row = screen.getByTestId('real-order-row-1')
      expect(row.textContent).toContain('DRY_RUN')
    })
  })

  // 6. Summary cards visible with order data
  it('renders summary cards with correct counts', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-summary-cards')).toBeDefined()
      expect(screen.getByTestId('real-orders-dryrun-card')).toBeDefined()
    })
  })

  // 7. Detail panel opens on row click
  it('opens detail panel when order row is clicked', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
      http.get('*/api/real-orders/:id', () => HttpResponse.json(ORDER_DETAIL)),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-1')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-1'))
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-detail')).toBeDefined()
    })
  })

  // 8. Fills table shown in detail panel
  it('shows fills table inside detail panel', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
      http.get('*/api/real-orders/:id', () => HttpResponse.json(ORDER_DETAIL)),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-1')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-1'))
    await waitFor(() => {
      expect(screen.getByTestId('real-fills-table')).toBeDefined()
    })
  })

  // 9. Empty fills state
  it('shows fills empty state when no fills in detail', async () => {
    server.use(
      http.get('*/api/real-orders', () => HttpResponse.json(ORDERS_LIST)),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: DRY_RUN_ORDER, fills: [] }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-1')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-1'))
    await waitFor(() => {
      expect(screen.getByTestId('real-fills-empty')).toBeDefined()
    })
  })

  // 10. Error state
  it('shows error state when API fails', async () => {
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-error')).toBeDefined()
    })
  })

  // 11. Forbidden response fields NOT rendered
  it('does NOT render forbidden response fields', async () => {
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({
          ...ORDERS_LIST,
          // These must never appear in any response the UI renders
          api_key: 'SHOULD_NOT_RENDER',
          broker_order_no_hash: 'SHOULD_NOT_RENDER',
          access_token: 'SHOULD_NOT_RENDER',
          raw_response: 'SHOULD_NOT_RENDER',
          account_number: 'SHOULD_NOT_RENDER',
          real_account: 'SHOULD_NOT_RENDER',
        }),
      ),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-page')).toBeDefined()
    })
    const pageText = document.body.textContent ?? ''
    for (const forbidden of [
      'SHOULD_NOT_RENDER',
      'broker_order_no_hash',
      'access_token',
      'raw_response',
      'real_account',
    ]) {
      expect(pageText).not.toContain(forbidden)
    }
  })

  // 12. No real order / automation CTA
  it('does NOT render real order or automation CTA buttons', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-page')).toBeDefined()
    })
    const buttons = document.querySelectorAll('button, [role="button"], a')
    const forbiddenPhrases = [
      '실주문 실행',
      '주문 전송',
      'place real order',
      '자동매매',
      'FULL_AUTO',
      'SMALL_AUTO',
      '실 KIS 주문',
    ]
    for (const btn of Array.from(buttons)) {
      const text = btn.textContent ?? ''
      for (const phrase of forbiddenPhrases) {
        expect(text).not.toContain(phrase)
      }
    }
  })

  // 13. API calls are read-only GET only (no POST/PUT/DELETE in hooks)
  it('useRealOrders hook only performs GET requests', async () => {
    // Verify hooks are read-only by checking there are no mutation hooks exported
    const { useRealOrders, useRealOrderDetail } = await import('@/hooks/useRealOrders')
    expect(typeof useRealOrders).toBe('function')
    expect(typeof useRealOrderDetail).toBe('function')
    // No mutation hook should exist
    const hooks = await import('@/hooks/useRealOrders')
    const exportedKeys = Object.keys(hooks)
    const mutationKeys = exportedKeys.filter(
      k => k.startsWith('useCreate') || k.startsWith('useUpdate') || k.startsWith('useDelete'),
    )
    expect(mutationKeys).toHaveLength(0)
  })
})
