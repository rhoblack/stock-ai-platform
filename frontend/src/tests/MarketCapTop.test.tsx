import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { MarketCapTopPage } from '@/pages/MarketCapTop'

function row(rank: number, symbol: string, name: string, opts: { market?: string; mcap?: string; sector?: string } = {}) {
  return {
    rank_date: '2026-05-04',
    market: opts.market ?? 'KOSPI',
    rank,
    symbol,
    name,
    market_cap: opts.mcap ?? '450000000000000',
    close_price: '70000',
    listed_shares: 5_969_782_550,
    sector: opts.sector ?? '반도체',
    trading_value: '105000000000',
    is_analysis_target: true,
  }
}

describe('MarketCapTopPage', () => {
  it('renders rows for the default KOSPI market (happy)', async () => {
    server.use(
      http.get('*/api/universe/market-cap-top', ({ request }) => {
        const url = new URL(request.url)
        const market = url.searchParams.get('market') ?? 'KOSPI'
        if (market !== 'KOSPI') return HttpResponse.json({ rank_date: null, market, items: [] })
        return HttpResponse.json({
          rank_date: '2026-05-04',
          market: 'KOSPI',
          items: [
            row(1, '005930', '삼성전자'),
            row(2, '000660', 'SK하이닉스', { mcap: '150000000000000' }),
          ],
        })
      }),
    )

    renderWithProviders(<MarketCapTopPage />, {
      initialEntries: ['/universe/market-cap-top'],
    })

    await waitFor(() =>
      expect(screen.getByTestId('mcap-row-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('mcap-row-000660')).toBeInTheDocument()
    expect(screen.getByTestId('mcap-table')).toBeInTheDocument()
    expect(screen.getByText('2건 표시')).toBeInTheDocument()
  })

  it('switches to KOSDAQ when filter clicked, then to ALL merging both', async () => {
    server.use(
      http.get('*/api/universe/market-cap-top', ({ request }) => {
        const url = new URL(request.url)
        const market = url.searchParams.get('market') ?? 'KOSPI'
        if (market === 'KOSPI') {
          return HttpResponse.json({
            rank_date: '2026-05-04',
            market: 'KOSPI',
            items: [row(1, '005930', '삼성전자', { market: 'KOSPI' })],
          })
        }
        return HttpResponse.json({
          rank_date: '2026-05-04',
          market: 'KOSDAQ',
          items: [row(1, '247540', '에코프로비엠', { market: 'KOSDAQ' })],
        })
      }),
    )

    renderWithProviders(<MarketCapTopPage />, {
      initialEntries: ['/universe/market-cap-top'],
    })

    await waitFor(() =>
      expect(screen.getByTestId('mcap-row-005930')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('mcap-row-247540')).not.toBeInTheDocument()

    // Switch to KOSDAQ
    await userEvent.click(screen.getByTestId('mcap-filter-KOSDAQ'))
    await waitFor(() =>
      expect(screen.getByTestId('mcap-row-247540')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('mcap-row-005930')).not.toBeInTheDocument()

    // Switch to ALL — both visible
    await userEvent.click(screen.getByTestId('mcap-filter-ALL'))
    await waitFor(() => {
      expect(screen.getByTestId('mcap-row-005930')).toBeInTheDocument()
      expect(screen.getByTestId('mcap-row-247540')).toBeInTheDocument()
    })
  })

  it('filters by symbol/name search input', async () => {
    server.use(
      http.get('*/api/universe/market-cap-top', () =>
        HttpResponse.json({
          rank_date: '2026-05-04',
          market: 'KOSPI',
          items: [
            row(1, '005930', '삼성전자'),
            row(2, '000660', 'SK하이닉스'),
            row(3, '035420', 'NAVER', { sector: '인터넷' }),
          ],
        }),
      ),
    )

    renderWithProviders(<MarketCapTopPage />, {
      initialEntries: ['/universe/market-cap-top'],
    })

    await waitFor(() =>
      expect(screen.getByTestId('mcap-row-005930')).toBeInTheDocument(),
    )

    const search = screen.getByTestId('mcap-search')
    await userEvent.type(search, 'NAV')
    await waitFor(() =>
      expect(screen.getByTestId('mcap-row-035420')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('mcap-row-005930')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mcap-row-000660')).not.toBeInTheDocument()
  })

  it('shows empty state when items=[] (default handler)', async () => {
    renderWithProviders(<MarketCapTopPage />, {
      initialEntries: ['/universe/market-cap-top'],
    })
    await waitFor(() => expect(screen.getByTestId('mcap-empty')).toBeInTheDocument())
  })

  it('shows error state on 500', async () => {
    server.use(
      http.get('*/api/universe/market-cap-top', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderWithProviders(<MarketCapTopPage />, {
      initialEntries: ['/universe/market-cap-top'],
    })
    await waitFor(() => expect(screen.getByTestId('mcap-error')).toBeInTheDocument())
  })
})
