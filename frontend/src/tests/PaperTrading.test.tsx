import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { PaperTradingPage } from '@/pages/PaperTrading'

const ACCOUNT_HAPPY = {
  id: 1,
  name: 'paper',
  currency: 'KRW',
  paper_trading_enabled: true,
  initial_cash: '10000000',
  cash_balance: '9899935',
  market_value: '110000',
  total_value: '10009935',
  realized_pnl: '0',
  unrealized_pnl: '9935',
  snapshot_date: '2026-05-08',
  created_at: '2026-05-08T00:00:00',
  updated_at: '2026-05-08T16:30:00',
}

const ORDERS_WITH_OPEN = {
  orders: [
    {
      id: 101,
      account_id: 1,
      symbol: '005930',
      side: 'BUY',
      quantity: 10,
      order_type: 'MARKET',
      limit_price: null,
      status: 'CREATED',
      idempotency_key: null,
      reason: null,
      note: null,
      created_at: '2026-05-08T15:55:00',
      updated_at: '2026-05-08T15:55:00',
    },
    {
      id: 102,
      account_id: 1,
      symbol: '000660',
      side: 'SELL',
      quantity: 5,
      order_type: 'LIMIT',
      limit_price: '180000',
      status: 'FILLED',
      idempotency_key: null,
      reason: null,
      note: null,
      created_at: '2026-05-08T15:58:00',
      updated_at: '2026-05-08T16:01:00',
    },
  ],
  total: 2,
  limit: 50,
}

const POSITIONS_HAPPY = {
  positions: [
    {
      id: 1,
      account_id: 1,
      symbol: '005930',
      quantity: 10,
      avg_cost: '10006.5',
      realized_pnl: '0',
      last_close: '11000',
      market_value: '110000',
      unrealized_pnl: '9935',
      updated_at: '2026-05-08T16:00:00',
    },
  ],
  total: 1,
}

const PNL_HAPPY = {
  snapshots: [
    {
      snapshot_date: '2026-05-07',
      cash_balance: '10000000',
      market_value: '0',
      total_value: '10000000',
      realized_pnl: '0',
      unrealized_pnl: '0',
    },
    {
      snapshot_date: '2026-05-08',
      cash_balance: '9899935',
      market_value: '110000',
      total_value: '10009935',
      realized_pnl: '0',
      unrealized_pnl: '9935',
    },
  ],
  total: 2,
}

const FORBIDDEN_SUBSTRINGS = [
  'api_key',
  'access_token',
  'jwt_secret',
  'kis_app_secret',
  'kis_account_no',
  'source_file_path',
  'broker_order_id',
  'kis_order_id',
  'real_account',
  'account_number',
  'raw_text',
  'full_text',
  'broker_name',
]

const FORBIDDEN_AUTOMATION_PHRASES = [
  '자동매매 시작',
  '자동매매 모드',
  '실거래 시작',
  '실거래 모드',
  'FULL_AUTO',
  'SMALL_AUTO',
  'APPROVAL',
  'place real order',
]

describe('PaperTradingPage', () => {
  it('renders paper-page wrapper and policy banner', () => {
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    expect(screen.getByTestId('paper-page')).toBeInTheDocument()
    expect(screen.getByTestId('paper-policy-banner')).toBeInTheDocument()
    // The order form is always rendered; the disabled banner only surfaces
    // after a 503 mutation attempt.
    expect(screen.getByTestId('paper-order-form')).toBeInTheDocument()
  })

  it('shows the account card with happy-path stats', async () => {
    server.use(
      http.get('*/api/paper/account', () => HttpResponse.json(ACCOUNT_HAPPY)),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.queryByTestId('paper-account-loading')).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-account-card')).toBeInTheDocument()
    expect(screen.getByTestId('paper-account-name')).toHaveTextContent('paper')
    expect(screen.getByTestId('paper-account-cash')).toHaveTextContent('9,899,935')
    expect(screen.getByTestId('paper-account-total')).toHaveTextContent('10,009,935')
    expect(screen.getByTestId('paper-account-unrealized')).toHaveTextContent('9,935')
  })

  it('shows empty placeholders when account is missing (404)', async () => {
    server.use(
      http.get('*/api/paper/account', () =>
        HttpResponse.json({ detail: 'no paper trading account' }, { status: 404 }),
      ),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.getByTestId('paper-account-empty')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-positions-empty')).toBeInTheDocument()
    expect(screen.getByTestId('paper-pnl-empty')).toBeInTheDocument()
    expect(screen.getByTestId('paper-orders-empty')).toBeInTheDocument()
  })

  it('renders the positions table when at least one open position exists', async () => {
    server.use(
      http.get('*/api/paper/positions', () => HttpResponse.json(POSITIONS_HAPPY)),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.getByTestId('paper-positions-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-position-row-005930')).toBeInTheDocument()
  })

  it('renders the PnL timeseries table when snapshots exist', async () => {
    server.use(http.get('*/api/paper/pnl', () => HttpResponse.json(PNL_HAPPY)))
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.getByTestId('paper-pnl-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-pnl-row-2026-05-08')).toBeInTheDocument()
  })

  it('renders the orders table with both terminal and open rows', async () => {
    server.use(http.get('*/api/paper/orders', () => HttpResponse.json(ORDERS_WITH_OPEN)))
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.getByTestId('paper-orders-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-order-row-101')).toBeInTheDocument()
    expect(screen.getByTestId('paper-order-row-102')).toBeInTheDocument()
    // Open order has a cancel button; terminal (FILLED) does not.
    expect(screen.getByTestId('paper-order-cancel-101')).toBeInTheDocument()
    expect(screen.queryByTestId('paper-order-cancel-102')).not.toBeInTheDocument()
  })

  it('shows the disabled banner when POST returns 503', async () => {
    server.use(
      http.post('*/api/paper/orders', () =>
        HttpResponse.json(
          { detail: 'paper trading is disabled' },
          { status: 503 },
        ),
      ),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })

    fireEvent.change(screen.getByTestId('paper-order-symbol-input'), {
      target: { value: '005930' },
    })
    fireEvent.change(screen.getByTestId('paper-order-quantity-input'), {
      target: { value: '10' },
    })
    fireEvent.click(screen.getByTestId('paper-order-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('paper-order-disabled-banner')).toBeInTheDocument(),
    )
    // No success banner.
    expect(screen.queryByTestId('paper-order-submit-success')).not.toBeInTheDocument()
  })

  it('submits a paper order and shows the success banner', async () => {
    server.use(
      http.post('*/api/paper/orders', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        expect(body.symbol).toBe('005930')
        expect(body.side).toBe('BUY')
        expect(body.quantity).toBe(10)
        return HttpResponse.json({
          order: {
            id: 999,
            account_id: 1,
            symbol: '005930',
            side: 'BUY',
            quantity: 10,
            order_type: 'MARKET',
            limit_price: null,
            status: 'CREATED',
            idempotency_key: null,
            reason: null,
            note: null,
            created_at: '2026-05-08T16:10:00',
            updated_at: '2026-05-08T16:10:00',
          },
          deduplicated: false,
        })
      }),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })

    fireEvent.change(screen.getByTestId('paper-order-symbol-input'), {
      target: { value: '005930' },
    })
    fireEvent.change(screen.getByTestId('paper-order-quantity-input'), {
      target: { value: '10' },
    })
    fireEvent.click(screen.getByTestId('paper-order-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('paper-order-submit-success')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('paper-order-submit-success')).toHaveTextContent('999')
  })

  it('cancels a paper order via DELETE and surfaces no error banner on success', async () => {
    server.use(
      http.get('*/api/paper/orders', () => HttpResponse.json(ORDERS_WITH_OPEN)),
      http.delete('*/api/paper/orders/:id', () =>
        HttpResponse.json({ status: 'ok', order_id: 101 }),
      ),
    )
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    await waitFor(() =>
      expect(screen.getByTestId('paper-order-cancel-101')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('paper-order-cancel-101'))
    // The orders list re-fetches via invalidate; we just confirm no error banner was raised.
    await waitFor(() =>
      expect(screen.queryByTestId('paper-cancel-disabled-banner')).not.toBeInTheDocument(),
    )
  })

  it('does NOT render forbidden response field labels', async () => {
    server.use(
      http.get('*/api/paper/account', () => HttpResponse.json(ACCOUNT_HAPPY)),
      http.get('*/api/paper/orders', () => HttpResponse.json(ORDERS_WITH_OPEN)),
      http.get('*/api/paper/positions', () => HttpResponse.json(POSITIONS_HAPPY)),
      http.get('*/api/paper/pnl', () => HttpResponse.json(PNL_HAPPY)),
    )
    const { container } = renderWithProviders(<PaperTradingPage />, {
      initialEntries: ['/paper'],
    })
    await waitFor(() =>
      expect(screen.getByTestId('paper-orders-table')).toBeInTheDocument(),
    )
    const text = container.textContent ?? ''
    for (const needle of FORBIDDEN_SUBSTRINGS) {
      expect(text.toLowerCase()).not.toContain(needle.toLowerCase())
    }
  })

  it('does NOT render any automation / autotrade CTA copy', async () => {
    renderWithProviders(<PaperTradingPage />, { initialEntries: ['/paper'] })
    const root = screen.getByTestId('paper-page')
    for (const phrase of FORBIDDEN_AUTOMATION_PHRASES) {
      expect(root.textContent ?? '').not.toContain(phrase)
    }
    // The single submit button must be labelled "페이퍼 주문 만들기" — no
    // "주문 실행" / "place order" wording.
    expect(screen.getByTestId('paper-order-submit')).toHaveTextContent(
      '페이퍼 주문 만들기',
    )
  })
})
