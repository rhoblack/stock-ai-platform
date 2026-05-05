import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { RecommendationHistoryPage } from '@/pages/RecommendationHistory'

function makeRun(runId: number, runDate: string, opts: {
  status?: string
  recCount?: number
  successRate?: string | null
  avg5d?: string | null
}) {
  const { status = 'SUCCESS', recCount = 5, successRate = null, avg5d = null } = opts
  return {
    run: {
      run_id: runId,
      run_date: runDate,
      started_at: `${runDate}T06:00:00Z`,
      finished_at: `${runDate}T06:00:30Z`,
      status,
      market_summary: null,
      telegram_sent: false,
    },
    recommendation_count: recCount,
    success_rate: successRate,
    avg_close_return_1d: null,
    avg_close_return_3d: null,
    avg_close_return_5d: avg5d,
    avg_close_return_20d: null,
  }
}

const HAPPY_BODY = {
  items: [
    makeRun(9, '2026-05-04', { successRate: '60', avg5d: '2.5' }),
    makeRun(8, '2026-05-03', { successRate: '40', avg5d: '-0.5' }),
    makeRun(7, '2026-05-02', { successRate: '80', avg5d: '3.0' }),
  ],
  limit: 20,
  offset: 0,
}

describe('RecommendationHistoryPage', () => {
  it('renders metric cards, trend charts, and table rows (happy)', async () => {
    server.use(
      http.get('*/api/recommendations/history', () => HttpResponse.json(HAPPY_BODY)),
    )

    renderWithProviders(<RecommendationHistoryPage />, {
      initialEntries: ['/recommendations/history'],
    })

    await waitFor(() =>
      expect(screen.getByTestId('history-table')).toBeInTheDocument(),
    )

    // Metric cards
    expect(screen.getByTestId('history-metric-runs')).toHaveTextContent('3')
    expect(screen.getByTestId('history-metric-total')).toHaveTextContent('15')
    expect(screen.getByTestId('history-metric-success')).toHaveTextContent('60.00%') // (60+40+80)/3
    // avg close 5d = (2.5 + (-0.5) + 3.0) / 3 = 1.6666... → +1.67%
    expect(screen.getByTestId('history-metric-avg-5d')).toHaveTextContent('+1.67%')

    // Trend charts (Recharts containers)
    expect(screen.getByTestId('history-trend-success')).toBeInTheDocument()
    expect(screen.getByTestId('history-trend-close5d')).toBeInTheDocument()

    // Table rows clickable as links to /recommendations/runs/:id
    const row9 = screen.getByTestId('history-row-9')
    expect(row9).toHaveAttribute('href', '/recommendations/runs/9')
  })

  it('shows empty placeholders when items=[]', async () => {
    // Default handler already returns empty.
    renderWithProviders(<RecommendationHistoryPage />, {
      initialEntries: ['/recommendations/history'],
    })

    await waitFor(() => expect(screen.getByTestId('history-empty')).toBeInTheDocument())
    // Empty trend charts still render with empty-state container
    expect(screen.getByTestId('history-trend-success-empty')).toBeInTheDocument()
    expect(screen.getByTestId('history-trend-close5d-empty')).toBeInTheDocument()
    // No metric cards because stats() returns null on empty list
    expect(screen.queryByTestId('history-metric-runs')).not.toBeInTheDocument()
  })

  it('shows error state on /api/recommendations/history 500', async () => {
    server.use(
      http.get('*/api/recommendations/history', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderWithProviders(<RecommendationHistoryPage />, {
      initialEntries: ['/recommendations/history'],
    })

    await waitFor(() => expect(screen.getByTestId('history-error')).toBeInTheDocument())
  })
})
