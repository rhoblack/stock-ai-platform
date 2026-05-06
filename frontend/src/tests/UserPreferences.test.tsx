// v0.9 Phase D — UserPreference tests.
// Covers: Settings page (get/update preferences), TodayReport WatchlistCard
// with preference default_watchlist_id, FavoriteButton preference path,
// forbidden field check.

import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { SettingsPage } from '@/pages/Settings'
import { TodayReportPage } from '@/pages/TodayReport'
import { StockDetailPage } from '@/pages/StockDetail'

function renderStockDetail(symbol = '005930') {
  return renderWithProviders(
    <Routes>
      <Route path="/stocks/:symbol" element={<StockDetailPage />} />
    </Routes>,
    { initialEntries: [`/stocks/${symbol}`] },
  )
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_PREF = {
  user_id: 1,
  default_watchlist_id: null,
  default_market: null,
  default_strategy: null,
  dashboard_layout_json: null,
  notification_preferences_json: null,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const WL1 = {
  id: 1,
  name: '관심종목',
  is_default: true,
  item_count: 0,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const WL2 = {
  id: 2,
  name: '기술주',
  is_default: false,
  item_count: 1,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const EMPTY_TODAY = {
  date: '2026-05-07',
  market_regime: null,
  latest_run: null,
  top_recommendations: [],
  holding_alerts: [],
}

// ---------------------------------------------------------------------------
// Settings page — UserPreference section
// ---------------------------------------------------------------------------

describe('SettingsPage — UserPreference section', () => {
  it('renders the user preference form', async () => {
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('user-preference-form')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('pref-default-watchlist')).toBeInTheDocument()
    expect(screen.getByTestId('pref-default-market')).toBeInTheDocument()
    expect(screen.getByTestId('pref-default-strategy')).toBeInTheDocument()
    expect(screen.getByTestId('pref-notification-enabled')).toBeInTheDocument()
    expect(screen.getByTestId('pref-save-btn')).toBeInTheDocument()
  })

  it('shows error state when preferences API returns 500', async () => {
    server.use(
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('user-preference-error')).toBeInTheDocument(),
    )
  })

  it('updates default_watchlist_id successfully', async () => {
    let savedPayload: unknown = null
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1, WL2] }),
      ),
      http.put('*/api/users/me/preferences', async ({ request }) => {
        savedPayload = await request.json()
        return HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 2 })
      }),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-default-watchlist')).toBeInTheDocument(),
    )

    // Select WL2
    await userEvent.selectOptions(screen.getByTestId('pref-default-watchlist'), '2')
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-success')).toBeInTheDocument(),
    )
    expect(savedPayload).toMatchObject({ default_watchlist_id: 2 })
  })

  it('updates default_market', async () => {
    let savedPayload: unknown = null
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.put('*/api/users/me/preferences', async ({ request }) => {
        savedPayload = await request.json()
        return HttpResponse.json({ ...BASE_PREF, default_market: 'KOSPI' })
      }),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-default-market')).toBeInTheDocument(),
    )
    await userEvent.selectOptions(screen.getByTestId('pref-default-market'), 'KOSPI')
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-success')).toBeInTheDocument(),
    )
    expect(savedPayload).toMatchObject({ default_market: 'KOSPI' })
  })

  it('updates default_strategy', async () => {
    let savedPayload: unknown = null
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.put('*/api/users/me/preferences', async ({ request }) => {
        savedPayload = await request.json()
        return HttpResponse.json({ ...BASE_PREF, default_strategy: 'momentum' })
      }),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-default-strategy')).toBeInTheDocument(),
    )
    await userEvent.selectOptions(screen.getByTestId('pref-default-strategy'), 'momentum')
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-success')).toBeInTheDocument(),
    )
    expect(savedPayload).toMatchObject({ default_strategy: 'momentum' })
  })

  it('saves notification preference (UI toggle only, no live send)', async () => {
    let savedPayload: unknown = null
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.put('*/api/users/me/preferences', async ({ request }) => {
        savedPayload = await request.json()
        return HttpResponse.json({ ...BASE_PREF, notification_preferences_json: { enabled: true } })
      }),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-notification-enabled')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('pref-notification-enabled'))
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-success')).toBeInTheDocument(),
    )
    expect((savedPayload as Record<string, unknown>)?.notification_preferences_json).toMatchObject({
      enabled: true,
    })
  })

  it('shows 401 error when save fails', async () => {
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.put('*/api/users/me/preferences', () =>
        HttpResponse.json({ detail: 'unauthorized' }, { status: 401 }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-btn')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('pref-save-error')).toHaveTextContent('로그인이 필요합니다.')
  })

  it('shows 404 error when chosen watchlist is not found', async () => {
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.put('*/api/users/me/preferences', () =>
        HttpResponse.json({ detail: 'watchlist not found' }, { status: 404 }),
      ),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-btn')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('pref-save-btn'))

    await waitFor(() =>
      expect(screen.getByTestId('pref-save-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('pref-save-error')).toHaveTextContent(
      '선택한 관심목록을 찾을 수 없습니다.',
    )
  })

  it('never renders forbidden fields in user-preference-form (password/token/broker/quantity/order)', async () => {
    server.use(
      http.get('*/api/users/me/preferences', () => HttpResponse.json(BASE_PREF)),
    )

    renderWithProviders(<SettingsPage />, { initialEntries: ['/settings'] })

    const form = await screen.findByTestId('user-preference-form')

    // Check forbidden fields are absent from the writable UserPreference section
    expect(form.innerHTML).not.toMatch(/password/i)
    expect(form.innerHTML).not.toMatch(/access_token/i)
    expect(form.innerHTML).not.toMatch(/jwt_secret/i)
    expect(form.innerHTML).not.toMatch(/broker/i)
    expect(form.innerHTML).not.toMatch(/quantity/i)
    expect(form.innerHTML).not.toMatch(/order_price/i)
    // Automation/trading terms must not appear in the preference form
    expect(form.innerHTML).not.toMatch(/자동매매/)
    expect(form.innerHTML).not.toMatch(/매수/)
    expect(form.innerHTML).not.toMatch(/매도/)
  })
})

// ---------------------------------------------------------------------------
// TodayReport — WatchlistCard uses preference.default_watchlist_id
// ---------------------------------------------------------------------------

describe('TodayReport — WatchlistCard with preference', () => {
  it('shows items from preference default_watchlist_id (overrides watchlist default flag)', async () => {
    // WL1 is is_default=true, but preference points to WL2
    server.use(
      http.get('*/api/reports/today', () => HttpResponse.json(EMPTY_TODAY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1, WL2] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 2 }),
      ),
      http.get('*/api/watchlists/2', () =>
        HttpResponse.json({
          ...WL2,
          items: [
            { id: 10, symbol: 'TSLA', memo: '테슬라', created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
    )

    renderWithProviders(<TodayReportPage />, { initialEntries: ['/today'] })

    await waitFor(() =>
      expect(screen.getByTestId('today-watchlist-item-TSLA')).toBeInTheDocument(),
    )
  })

  it('falls back to watchlist default flag when preference has no default_watchlist_id', async () => {
    server.use(
      http.get('*/api/reports/today', () => HttpResponse.json(EMPTY_TODAY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: null }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          ...WL1,
          items: [
            { id: 1, symbol: '005930', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
    )

    renderWithProviders(<TodayReportPage />, { initialEntries: ['/today'] })

    await waitFor(() =>
      expect(screen.getByTestId('today-watchlist-item-005930')).toBeInTheDocument(),
    )
  })
})

// ---------------------------------------------------------------------------
// StockDetail — FavoriteButton uses preference default_watchlist_id
// ---------------------------------------------------------------------------

describe('StockDetailPage — FavoriteButton with preference', () => {
  const STOCK_RESPONSE = {
    stock: {
      symbol: '005930',
      name: '삼성전자',
      market: 'KOSPI',
      sector: '반도체',
      is_active: true,
    },
    latest_price: null,
    latest_indicator: null,
    recent_recommendations: [],
    recent_holding_checks: [],
    analyst_reports: null,
  }

  it('marks star active when symbol is in preference-default watchlist', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(STOCK_RESPONSE)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL2] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 2 }),
      ),
      http.get('*/api/watchlists/2', () =>
        HttpResponse.json({
          ...WL2,
          items: [
            { id: 10, symbol: '005930', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
    )

    renderStockDetail('005930')

    // Wait until both the button is visible AND data-active reflects loaded state
    await waitFor(() => {
      const btn = screen.getByTestId('favorite-toggle')
      expect(btn).toHaveAttribute('data-active', 'true')
    })
  })

  it('shows star inactive when symbol is not in preference-default watchlist', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(STOCK_RESPONSE)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 1 }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WL1, items: [] }),
      ),
    )

    renderStockDetail('005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('favorite-toggle')).toHaveAttribute('data-active', 'false')
  })

  it('treats 409 on add as idempotent (no error shown)', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(STOCK_RESPONSE)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 1 }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WL1, items: [] }),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'already exists' }, { status: 409 }),
      ),
    )

    renderStockDetail('005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('favorite-toggle'))

    // 409 should be silently ignored (no error message)
    await waitFor(() =>
      expect(screen.queryByTestId('favorite-error')).not.toBeInTheDocument(),
    )
  })

  it('shows mutation error on 500', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(STOCK_RESPONSE)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/users/me/preferences', () =>
        HttpResponse.json({ ...BASE_PREF, default_watchlist_id: 1 }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WL1, items: [] }),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )

    renderStockDetail('005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('favorite-toggle'))

    await waitFor(() =>
      expect(screen.getByTestId('favorite-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('favorite-error')).toHaveTextContent(
      '관심종목 변경에 실패했습니다.',
    )
  })
})
