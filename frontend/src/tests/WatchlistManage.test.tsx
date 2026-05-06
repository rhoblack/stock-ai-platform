// v0.9 Phase D — Watchlist management UI tests.
// Covers: rename success/409, set-default, delete (incl. default list),
//         memo edit success/422, item filter/search, forbidden field check.

import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { WatchlistPage } from '@/pages/Watchlist'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const WL1 = {
  id: 1,
  name: '관심종목',
  is_default: true,
  item_count: 2,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const WL2 = {
  id: 2,
  name: '테스트목록',
  is_default: false,
  item_count: 0,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const WL1_DETAIL = {
  ...WL1,
  items: [
    { id: 1, symbol: '005930', memo: '삼성전자', created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
    { id: 2, symbol: '000660', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
  ],
}

function withWatchlistList() {
  server.use(
    http.get('*/api/watchlists', () =>
      HttpResponse.json({ watchlists: [WL1, WL2] }),
    ),
    http.get('*/api/watchlists/1', () => HttpResponse.json(WL1_DETAIL)),
    http.get('*/api/watchlists/2', () =>
      HttpResponse.json({ ...WL2, items: [] }),
    ),
  )
}

// ---------------------------------------------------------------------------
// Rename
// ---------------------------------------------------------------------------

describe('WatchlistListItem — rename', () => {
  it('renames a watchlist successfully', async () => {
    withWatchlistList()
    let patchCalled = false
    server.use(
      http.patch('*/api/watchlists/1', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        patchCalled = true
        return HttpResponse.json({ ...WL1, name: String(body.name) })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-1')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-1'))
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-rename-btn-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-rename-btn-1'))

    const input = await screen.findByTestId('watchlist-rename-input-1')
    await userEvent.clear(input)
    await userEvent.type(input, '새이름')
    await userEvent.click(screen.getByTestId('watchlist-rename-confirm-1'))

    await waitFor(() => expect(patchCalled).toBe(true))
  })

  it('shows 409 error when rename conflicts with existing name', async () => {
    withWatchlistList()
    server.use(
      http.patch('*/api/watchlists/2', () =>
        HttpResponse.json({ detail: 'already exists' }, { status: 409 }),
      ),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-2'))
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-rename-btn-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-rename-btn-2'))

    const input = await screen.findByTestId('watchlist-rename-input-2')
    await userEvent.clear(input)
    await userEvent.type(input, '관심종목')
    await userEvent.click(screen.getByTestId('watchlist-rename-confirm-2'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-rename-error-2')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-rename-error-2')).toHaveTextContent(
      '같은 이름이 이미 있습니다.',
    )
  })

  it('cancels rename without calling API', async () => {
    withWatchlistList()
    let patchCalled = false
    server.use(
      http.patch('*/api/watchlists/1', () => {
        patchCalled = true
        return HttpResponse.json(WL1)
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-1'))
    await userEvent.click(screen.getByTestId('watchlist-rename-btn-1'))

    await screen.findByTestId('watchlist-rename-cancel-1')
    await userEvent.click(screen.getByTestId('watchlist-rename-cancel-1'))

    expect(patchCalled).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Set default
// ---------------------------------------------------------------------------

describe('WatchlistListItem — set default', () => {
  it('sets a non-default watchlist as default', async () => {
    withWatchlistList()
    let patchCalled = false
    server.use(
      http.patch('*/api/watchlists/2', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        patchCalled = true
        return HttpResponse.json({ ...WL2, is_default: Boolean(body.is_default) })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-2'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-set-default-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-set-default-2'))

    await waitFor(() => expect(patchCalled).toBe(true))
  })

  it('does not show set-default button for the already-default watchlist', async () => {
    withWatchlistList()

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-1'))

    // WL1 is_default=true so the button should NOT render
    expect(screen.queryByTestId('watchlist-set-default-1')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------

describe('WatchlistListItem — delete', () => {
  it('deletes a non-default watchlist', async () => {
    let deleteCalled = false
    let listCallCount = 0
    server.use(
      http.get('*/api/watchlists', () => {
        listCallCount++
        if (listCallCount === 1) return HttpResponse.json({ watchlists: [WL1, WL2] })
        return HttpResponse.json({ watchlists: [WL1] })
      }),
      http.get('*/api/watchlists/1', () => HttpResponse.json(WL1_DETAIL)),
      http.get('*/api/watchlists/2', () =>
        HttpResponse.json({ ...WL2, items: [] }),
      ),
      http.delete('*/api/watchlists/2', () => {
        deleteCalled = true
        return HttpResponse.json({ status: 'ok' })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-2'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-delete-btn-2')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-delete-btn-2'))

    await waitFor(() => expect(deleteCalled).toBe(true))
  })

  it('deletes the default watchlist (API allows it)', async () => {
    let deleteCalled = false
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/watchlists/1', () => HttpResponse.json(WL1_DETAIL)),
      http.delete('*/api/watchlists/1', () => {
        deleteCalled = true
        return HttpResponse.json({ status: 'ok' })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-1'))
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-delete-btn-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-delete-btn-1'))

    await waitFor(() => expect(deleteCalled).toBe(true))
  })

  it('shows error when delete returns 404', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WL1] }),
      ),
      http.get('*/api/watchlists/1', () => HttpResponse.json(WL1_DETAIL)),
      http.delete('*/api/watchlists/1', () =>
        HttpResponse.json({ detail: 'not found' }, { status: 404 }),
      ),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-menu-toggle-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-menu-toggle-1'))
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-delete-btn-1')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-delete-btn-1'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-action-error-1')).toBeInTheDocument(),
    )
  })
})

// ---------------------------------------------------------------------------
// Memo edit
// ---------------------------------------------------------------------------

describe('WatchlistItemRow — memo edit', () => {
  it('edits a memo successfully', async () => {
    withWatchlistList()
    let patchCalled = false
    server.use(
      http.patch('*/api/watchlists/1/items/005930', async ({ request }) => {
        const body = await request.json() as Record<string, unknown>
        patchCalled = true
        return HttpResponse.json({
          id: 1,
          symbol: '005930',
          memo: body.memo,
          created_at: '2026-05-06T00:00:00',
          updated_at: '2026-05-07T00:00:00',
        })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('watchlist-item-memo-edit-005930'))

    const memoInput = await screen.findByTestId('watchlist-memo-input-005930')
    await userEvent.clear(memoInput)
    await userEvent.type(memoInput, '수정된 메모')
    await userEvent.click(screen.getByTestId('watchlist-memo-confirm-005930'))

    await waitFor(() => expect(patchCalled).toBe(true))
  })

  it('shows 422 error when memo exceeds limit', async () => {
    withWatchlistList()
    server.use(
      http.patch('*/api/watchlists/1/items/005930', () =>
        HttpResponse.json({ detail: 'memo too long' }, { status: 422 }),
      ),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('watchlist-item-memo-edit-005930'))
    const memoInput = await screen.findByTestId('watchlist-memo-input-005930')
    await userEvent.type(memoInput, '초과 메모')
    await userEvent.click(screen.getByTestId('watchlist-memo-confirm-005930'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-memo-error-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-memo-error-005930')).toHaveTextContent(
      '메모는 최대 500자입니다.',
    )
  })

  it('cancels memo edit without calling API', async () => {
    withWatchlistList()
    let patchCalled = false
    server.use(
      http.patch('*/api/watchlists/1/items/005930', () => {
        patchCalled = true
        return HttpResponse.json({ id: 1, symbol: '005930', memo: null, created_at: '', updated_at: '' })
      }),
    )

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('watchlist-item-memo-edit-005930'))
    await screen.findByTestId('watchlist-memo-cancel-005930')
    await userEvent.click(screen.getByTestId('watchlist-memo-cancel-005930'))

    expect(patchCalled).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Item filter/search
// ---------------------------------------------------------------------------

describe('WatchlistDetailPanel — item filter', () => {
  it('filters items by symbol prefix', async () => {
    withWatchlistList()

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-item-000660')).toBeInTheDocument()

    const filter = screen.getByTestId('watchlist-item-filter')
    await userEvent.type(filter, '005')

    // Only 005930 should remain
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('watchlist-item-000660')).not.toBeInTheDocument()
  })

  it('shows empty message when filter has no match', async () => {
    withWatchlistList()

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-filter')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-item-filter'), 'ZZZZZ')

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-items-filter-empty')).toBeInTheDocument(),
    )
  })
})

// ---------------------------------------------------------------------------
// Forbidden fields
// ---------------------------------------------------------------------------

describe('WatchlistPage — forbidden fields', () => {
  it('never renders broker/account/quantity/password/token/order/주문/매수/매도', async () => {
    withWatchlistList()

    renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-detail')).toBeInTheDocument(),
    )

    expect(screen.queryByText(/broker/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/account/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/quantity/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/access_token/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/order_price/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/order_type/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/주문/)).not.toBeInTheDocument()
    expect(screen.queryByText(/매수/)).not.toBeInTheDocument()
    expect(screen.queryByText(/매도/)).not.toBeInTheDocument()
    expect(screen.queryByText(/자동매매/)).not.toBeInTheDocument()
  })
})
