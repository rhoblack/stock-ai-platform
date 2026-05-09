// v0.16 Phase E — RealOrders page vitest suite.
// v1.0 Phase E — adds RealTradingModeBanner + Sync Fill button tests.
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

  // 2. Safety banner text — v1.0 Phase E uses uppercase "DRY-RUN" mode label.
  it('safety banner contains required dry-run notice', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      const text = screen.getByTestId('real-orders-safety-banner').textContent ?? ''
      // The new banner copies "DRY-RUN 모드에서는 실제 KIS 주문이 실행되지 않습니다".
      expect(text.toLowerCase()).toContain('dry-run')
    })
    expect(
      screen.getByTestId('real-orders-safety-banner').textContent,
    ).toContain('실제 KIS 주문이 실행되지 않습니다')
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

  // 13. v1.0 Phase D — only the SOLE mutation hook (useSyncRealOrder) is exported.
  it('useRealOrders module exposes ONLY useSyncRealOrder as a mutation', async () => {
    const hooks = await import('@/hooks/useRealOrders')
    const exportedKeys = Object.keys(hooks)
    expect(exportedKeys).toContain('useRealOrders')
    expect(exportedKeys).toContain('useRealOrderDetail')
    expect(exportedKeys).toContain('useSyncRealOrder')
    // Forbidden mutation hooks — would indicate accidental "create real order"
    // / "delete real order" surface that v1.0 must not expose.
    const forbiddenMutationPrefixes = ['useCreate', 'useUpdate', 'useDelete']
    for (const key of exportedKeys) {
      for (const prefix of forbiddenMutationPrefixes) {
        expect(key.startsWith(prefix)).toBe(false)
      }
    }
  })

  // ===========================================================================
  // v1.0 Phase E — RealTradingModeBanner + Sync Fill button
  // ===========================================================================

  // Build a canonical settings response used by every Phase E banner test.
  const PARANOID_SETTINGS = {
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
    trading_safety_enabled: false,
    kill_switch_enabled: true,
    real_trading_enabled: false,
    kis_order_enabled: false,
    real_order_dry_run: true,
  }

  // 14. Banner renders with all 5 safety bool flags as labelled badges.
  it('RealTradingModeBanner renders all 5 safety flag badges', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-trading-flags')).toBeDefined()
    })
    // Each flag badge surfaces its env-var name as readable text.
    expect(
      screen.getByTestId('real-trading-flag-TRADING_SAFETY_ENABLED'),
    ).toBeDefined()
    expect(
      screen.getByTestId('real-trading-flag-KILL_SWITCH_ENABLED'),
    ).toBeDefined()
    expect(
      screen.getByTestId('real-trading-flag-REAL_TRADING_ENABLED'),
    ).toBeDefined()
    expect(
      screen.getByTestId('real-trading-flag-KIS_ORDER_ENABLED'),
    ).toBeDefined()
    expect(
      screen.getByTestId('real-trading-flag-REAL_ORDER_DRY_RUN'),
    ).toBeDefined()
  })

  // 15. Paranoid defaults → mode = "KILL SWITCH ON" (kill_switch=true).
  it('mode badge shows KILL SWITCH ON under paranoid defaults', async () => {
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      const badge = screen.getByTestId('real-trading-mode-badge')
      expect(badge.textContent).toContain('KILL SWITCH ON')
    })
  })

  // 16. DRY-RUN mode (kill_switch=false, safety=true, dry_run=true).
  it('mode badge shows DRY-RUN when kill switch off + dry_run on', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          ...PARANOID_SETTINGS,
          kill_switch_enabled: false,
          trading_safety_enabled: true,
          real_trading_enabled: false,
          kis_order_enabled: false,
          real_order_dry_run: true,
        }),
      ),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      const badge = screen.getByTestId('real-trading-mode-badge')
      expect(badge.textContent).toContain('DRY-RUN')
    })
  })

  // 17. REAL TRADING ENABLED mode (every gate open).
  it('mode badge shows REAL TRADING ENABLED when all gates open', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          ...PARANOID_SETTINGS,
          kill_switch_enabled: false,
          trading_safety_enabled: true,
          real_trading_enabled: true,
          kis_order_enabled: true,
          real_order_dry_run: false,
        }),
      ),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      const badge = screen.getByTestId('real-trading-mode-badge')
      expect(badge.textContent).toContain('REAL TRADING ENABLED')
    })
  })

  // 18. Sync Fill button visible inside detail panel.
  const SUBMITTED_ORDER = {
    ...DRY_RUN_ORDER,
    id: 42,
    status: 'SUBMITTED' as const,
    dry_run: false,
    fake_order_no: null,
  }

  it('Sync Fill button is visible in the order detail panel', async () => {
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: SUBMITTED_ORDER, fills: [] }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-42')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-42'))
    await waitFor(() => {
      expect(screen.getByTestId('real-order-sync-button')).toBeDefined()
    })
    expect(
      screen.getByTestId('real-order-sync-button').textContent,
    ).toContain('체결 동기화')
  })

  // 19. Sync Fill disabled for DRY_RUN order.
  it('Sync Fill button is disabled for DRY_RUN order', async () => {
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [DRY_RUN_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
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
      const btn = screen.getByTestId('real-order-sync-button') as HTMLButtonElement
      expect(btn.disabled).toBe(true)
    })
    expect(
      screen.getByTestId('real-order-sync-disabled-reason').textContent,
    ).toContain('DRY_RUN')
  })

  // 20. Sync Fill disabled when KILL_SWITCH_ENABLED=true.
  it('Sync Fill button is disabled when kill switch is ON', async () => {
    // Default settings already have kill_switch=true → confirm SUBMITTED order is blocked.
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: SUBMITTED_ORDER, fills: [] }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-42')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-42'))
    await waitFor(() => {
      const btn = screen.getByTestId('real-order-sync-button') as HTMLButtonElement
      expect(btn.disabled).toBe(true)
    })
    expect(
      screen.getByTestId('real-order-sync-disabled-reason').textContent,
    ).toContain('KILL_SWITCH_ENABLED')
  })

  // 21. Sync Fill happy path → success message rendered.
  it('Sync Fill happy path shows success message', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          ...PARANOID_SETTINGS,
          kill_switch_enabled: false,
          trading_safety_enabled: true,
          real_trading_enabled: false,  // intentionally off — sync API does NOT require it
          kis_order_enabled: false,
          real_order_dry_run: false,
        }),
      ),
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: SUBMITTED_ORDER, fills: [] }),
      ),
      http.post('*/api/real-orders/:orderId/sync', () =>
        HttpResponse.json({
          real_order_id: 42,
          real_order_status: 'FILLED',
          fill_status: 'FULL',
          fills_added: 1,
          fills_total: 10,
          synced_at: '2026-05-09T01:00:00Z',
          message: 'sync ok: FULL (delta=10, new fill recorded)',
        }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-42')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-42'))
    const btn = await waitFor(() => {
      const b = screen.getByTestId('real-order-sync-button') as HTMLButtonElement
      expect(b.disabled).toBe(false)
      return b
    })
    await user.click(btn)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-sync-success')).toBeDefined()
    })
    expect(
      screen.getByTestId('real-order-sync-success').textContent,
    ).toContain('FULL')
  })

  // 22. Sync Fill 503 (mutation rejected) shows error message.
  it('Sync Fill 503 disabled response shows error message', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          ...PARANOID_SETTINGS,
          kill_switch_enabled: false,
          trading_safety_enabled: true,
          real_order_dry_run: false,
        }),
      ),
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: SUBMITTED_ORDER, fills: [] }),
      ),
      // Default mswServer already returns 503; explicit override here for clarity.
      http.post('*/api/real-orders/:orderId/sync', () =>
        HttpResponse.json({ detail: 'safety disabled' }, { status: 503 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-42')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-42'))
    const btn = await waitFor(() =>
      screen.getByTestId('real-order-sync-button') as HTMLButtonElement,
    )
    await user.click(btn)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-sync-error')).toBeDefined()
    })
  })

  // 23. Phase E forbidden CTA scan — verify no automation/order labels appear.
  it('Phase E renders the safe-only Sync Fill label and no forbidden CTA', async () => {
    server.use(
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
      http.get('*/api/real-orders/:id', () =>
        HttpResponse.json({ order: SUBMITTED_ORDER, fills: [] }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-order-row-42')).toBeDefined()
    })
    await user.click(screen.getByTestId('real-order-row-42'))
    await waitFor(() => {
      expect(screen.getByTestId('real-order-sync-button')).toBeDefined()
    })
    const buttons = document.querySelectorAll('button, [role="button"], a')
    const forbiddenCtas = [
      '실주문 실행',
      '주문 전송',
      'place real order',
      '자동매매',
      'FULL_AUTO',
      'SMALL_AUTO',
    ]
    for (const btn of Array.from(buttons)) {
      const text = btn.textContent ?? ''
      for (const phrase of forbiddenCtas) {
        expect(text).not.toContain(phrase)
      }
    }
  })

  // 24. Settings response forbidden substring scan — extended for v1.0.
  it('Phase E does not surface KIS app key / secret / account_no plaintext', async () => {
    server.use(
      http.get('*/api/settings', () =>
        HttpResponse.json({
          ...PARANOID_SETTINGS,
          // Even if backend leaks plaintext, frontend must not surface it.
          kis_app_key: 'PLAINTEXT-APP-KEY-99999',
          kis_app_secret: 'PLAINTEXT-APP-SECRET-99999',
          kis_account_no: 'PLAINTEXT-ACCOUNT-NO-99999',
        }),
      ),
      http.get('*/api/real-orders', () =>
        HttpResponse.json({ items: [SUBMITTED_ORDER], total: 1, limit: 100, offset: 0 }),
      ),
    )
    renderWithProviders(<RealOrdersPage />)
    await waitFor(() => {
      expect(screen.getByTestId('real-orders-page')).toBeDefined()
    })
    const pageText = document.body.textContent ?? ''
    for (const forbidden of [
      'PLAINTEXT-APP-KEY-99999',
      'PLAINTEXT-APP-SECRET-99999',
      'PLAINTEXT-ACCOUNT-NO-99999',
    ]) {
      expect(pageText).not.toContain(forbidden)
    }
  })
})
