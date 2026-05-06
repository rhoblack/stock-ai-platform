import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { WatchlistPage } from '@/pages/Watchlist'

const WATCHLIST_1 = {
  id: 1,
  name: '관심종목',
  is_default: true,
  item_count: 2,
  created_at: '2026-05-06T00:00:00',
  updated_at: '2026-05-06T00:00:00',
}

const WATCHLIST_DETAIL_1 = {
  ...WATCHLIST_1,
  items: [
    { id: 1, symbol: '005930', memo: '삼성전자', created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
    { id: 2, symbol: '000660', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
  ],
}

function renderWatchlist() {
  return renderWithProviders(<WatchlistPage />, { initialEntries: ['/watchlist'] })
}

describe('WatchlistPage', () => {
  it('shows empty placeholder when no watchlists exist', async () => {
    // default MSW handler returns { watchlists: [] }
    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-list-empty')).toBeInTheDocument(),
    )
    expect(screen.getByText('관심목록이 없습니다.')).toBeInTheDocument()
  })

  it('shows error state when /api/watchlists returns 500', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-error')).toBeInTheDocument(),
    )
  })

  it('renders watchlist list and selects first watchlist on load', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json(WATCHLIST_DETAIL_1),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-row-1')).toBeInTheDocument(),
    )
    // Detail panel should load automatically
    await waitFor(() =>
      expect(screen.getByTestId('watchlist-detail')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-item-005930')).toBeInTheDocument()
    expect(screen.getByTestId('watchlist-item-000660')).toBeInTheDocument()
    // item links navigate to stock detail
    expect(screen.getByTestId('watchlist-item-link-005930')).toHaveAttribute(
      'href',
      '/stocks/005930',
    )
    // memo renders
    expect(screen.getByTestId('watchlist-item-memo-005930')).toHaveTextContent('삼성전자')
  })

  it('shows empty items placeholder when watchlist has no items', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [{ ...WATCHLIST_1, item_count: 0 }] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WATCHLIST_DETAIL_1, items: [], item_count: 0 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-items-empty')).toBeInTheDocument(),
    )
  })

  it('can create a new watchlist successfully', async () => {
    let callCount = 0
    server.use(
      http.get('*/api/watchlists', () => {
        // First call: empty; second call (after invalidation): has the new list
        callCount++
        if (callCount === 1) return HttpResponse.json({ watchlists: [] })
        return HttpResponse.json({ watchlists: [{ ...WATCHLIST_1, name: '테스트목록' }] })
      }),
      http.post('*/api/watchlists', () =>
        HttpResponse.json({ ...WATCHLIST_1, name: '테스트목록' }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WATCHLIST_DETAIL_1, name: '테스트목록', items: [] }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-create-form')).toBeInTheDocument(),
    )

    const nameInput = screen.getByTestId('watchlist-create-name')
    await userEvent.type(nameInput, '테스트목록')
    await userEvent.click(screen.getByTestId('watchlist-create-submit'))

    await waitFor(() => expect(callCount).toBeGreaterThan(1))
  })

  it('shows 409 error when creating a duplicate watchlist name', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.post('*/api/watchlists', () =>
        HttpResponse.json({ detail: 'already exists' }, { status: 409 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-create-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-create-name'), '관심종목')
    await userEvent.click(screen.getByTestId('watchlist-create-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-create-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-create-error')).toHaveTextContent(
      '같은 이름의 관심목록이 이미 있습니다.',
    )
  })

  it('can add an item to a watchlist', async () => {
    let detailCallCount = 0
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () => {
        detailCallCount++
        if (detailCallCount === 1) {
          return HttpResponse.json({ ...WATCHLIST_DETAIL_1, items: [], item_count: 0 })
        }
        return HttpResponse.json(WATCHLIST_DETAIL_1)
      }),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({
          id: 1,
          symbol: '005930',
          memo: null,
          created_at: '2026-05-06T00:00:00',
          updated_at: '2026-05-06T00:00:00',
        }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-item-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-add-symbol'), '005930')
    await userEvent.click(screen.getByTestId('watchlist-add-submit'))

    await waitFor(() => expect(detailCallCount).toBeGreaterThan(1))
  })

  it('shows 404 error when adding an unknown symbol', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WATCHLIST_DETAIL_1, items: [], item_count: 0 }),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'symbol not found' }, { status: 404 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-item-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-add-symbol'), 'INVALID')
    await userEvent.click(screen.getByTestId('watchlist-add-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-add-error')).toHaveTextContent(
      '존재하지 않는 종목 코드입니다.',
    )
  })

  it('shows 409 error when adding a duplicate symbol', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json(WATCHLIST_DETAIL_1),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'already exists' }, { status: 409 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-item-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-add-symbol'), '005930')
    await userEvent.click(screen.getByTestId('watchlist-add-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-add-error')).toHaveTextContent(
      '이미 관심목록에 있는 종목입니다.',
    )
  })

  it('shows 401 error when adding an item without auth', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({ ...WATCHLIST_DETAIL_1, items: [] }),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'unauthorized' }, { status: 401 }),
      ),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-item-form')).toBeInTheDocument(),
    )

    await userEvent.type(screen.getByTestId('watchlist-add-symbol'), '005930')
    await userEvent.click(screen.getByTestId('watchlist-add-submit'))

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-add-error')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('watchlist-add-error')).toHaveTextContent(
      '로그인이 필요합니다.',
    )
  })

  it('can remove an item from a watchlist', async () => {
    let deleteCount = 0
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json(WATCHLIST_DETAIL_1),
      ),
      http.delete('*/api/watchlists/1/items/005930', () => {
        deleteCount++
        return HttpResponse.json({ status: 'removed' })
      }),
    )

    renderWatchlist()

    await waitFor(() =>
      expect(screen.getByTestId('watchlist-item-remove-005930')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('watchlist-item-remove-005930'))

    await waitFor(() => expect(deleteCount).toBe(1))
  })

  it('never renders forbidden fields (broker, account, quantity, password, token)', async () => {
    server.use(
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [WATCHLIST_1] }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json(WATCHLIST_DETAIL_1),
      ),
    )

    renderWatchlist()

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
  })
})
