import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { BacktestPage } from '@/pages/Backtest'

const STRATEGIES = {
  count: 3,
  items: [
    {
      name: 'TopGradeStrategy',
      version: 'v1.0.0',
      description: 'Trade on the recommendation grade alone.',
    },
    {
      name: 'HighScoreStrategy',
      version: 'v1.0.0',
      description: "Trade on the recommendation's total_score alone.",
    },
    {
      name: 'MultiSignalStrategy',
      version: 'v1.0.0',
      description: 'Multi-factor rule combining v0.4~v0.6 signals.',
    },
  ],
}

const RUNS = {
  count: 2,
  strategy: null,
  limit: 20,
  items: [
    {
      id: 42,
      strategy_name: 'top_grade',
      strategy_version: 'v1.0.0',
      run_date: '2026-05-06',
      start_date: '2026-04-01',
      end_date: '2026-05-04',
      signal_count: 5,
      buy_count: 2,
      pass_count: 2,
      avoid_count: 1,
      win_rate_1d: '0.5000',
      win_rate_3d: null,
      win_rate_5d: '0.5000',
      win_rate_20d: null,
      avg_return_1d: '1.0000',
      avg_return_3d: null,
      avg_return_5d: '1.5000',
      avg_return_20d: null,
      cost_adjusted_avg_return_5d: '1.1700',
      max_drawdown: '-2.5000',
      status: 'SUCCESS',
      cost_model_version: 'constant-v1',
      total_cost: '0.00330',
    },
    {
      id: 41,
      strategy_name: 'high_score',
      strategy_version: 'v1.0.0',
      run_date: '2026-05-05',
      start_date: null,
      end_date: null,
      signal_count: 3,
      buy_count: 1,
      pass_count: 2,
      avoid_count: 0,
      win_rate_1d: null,
      win_rate_3d: null,
      win_rate_5d: '1.0000',
      win_rate_20d: null,
      avg_return_1d: null,
      avg_return_3d: null,
      avg_return_5d: '3.0000',
      avg_return_20d: null,
      cost_adjusted_avg_return_5d: '2.6700',
      max_drawdown: '-1.0000',
      status: 'SUCCESS',
      cost_model_version: 'constant-v1',
      total_cost: '0.00330',
    },
  ],
}

const RUN_DETAIL_42 = {
  run: RUNS.items[0],
  results: [
    {
      id: 1001,
      symbol: '005930',
      recommendation_id: 71,
      signal_action: 'BUY',
      confidence: '0.7500',
      reason: 'grade=A',
      grade: 'A',
      total_score: '80.0000',
      return_1d: '1.0000',
      return_3d: null,
      return_5d: '1.5000',
      return_20d: null,
      cost_adjusted_return_5d: '1.1700',
      max_drawdown: '-2.5000',
      result_status: 'SUCCESS',
      regime: 'UPTREND_EARLY',
      evidence_json: { grade: 'A' },
    },
    {
      id: 1002,
      symbol: '000660',
      recommendation_id: 72,
      signal_action: 'PASS',
      confidence: '0.5000',
      reason: 'grade=C',
      grade: 'C',
      total_score: '50.0000',
      return_1d: null,
      return_3d: null,
      return_5d: '0.5000',
      return_20d: null,
      cost_adjusted_return_5d: null,
      max_drawdown: null,
      result_status: null,
      regime: 'UPTREND_EARLY',
      evidence_json: null,
    },
  ],
  regime_breakdown: [
    {
      regime: 'UPTREND_EARLY',
      buy_count: 2,
      win_rate_5d: '0.5000',
      avg_return_5d: '1.5000',
      cost_adjusted_avg_return_5d: '1.1700',
    },
  ],
  cost_model_version: 'constant-v1',
  total_cost: '0.00330',
  summary_json: { notes: 'BUY signals only' },
  notes: 'win_rate / avg_return / max_drawdown are computed over BUY signals only.',
}

describe('BacktestPage', () => {
  it('renders strategies + runs table happy path', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
    )

    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })

    await waitFor(() =>
      expect(
        screen.getByTestId('backtest-strategy-TopGradeStrategy'),
      ).toBeInTheDocument(),
    )
    expect(screen.getByTestId('backtest-strategy-HighScoreStrategy')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-strategy-MultiSignalStrategy')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-runs-table')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-run-row-41')).toBeInTheDocument()
  })

  it('shows empty placeholders when both endpoints are empty', async () => {
    // mswServer defaults already return empty
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-strategies-empty')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('backtest-runs-empty')).toBeInTheDocument()
  })

  it('shows error state when /api/backtest/runs returns 500', async () => {
    server.use(
      http.get('*/api/backtest/runs', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(
      () => expect(screen.getByTestId('backtest-runs-error')).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  it('loads detail panel when a run row is clicked', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })

    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))

    await waitFor(() =>
      expect(screen.getByTestId('backtest-detail')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('backtest-detail-cost-model')).toHaveTextContent(
      'constant-v1',
    )
    expect(screen.getByTestId('backtest-regime-UPTREND_EARLY')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-result-1001')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-result-1002')).toBeInTheDocument()
    // BUY badge present
    expect(screen.getAllByTestId('backtest-action-BUY').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('backtest-action-PASS').length).toBeGreaterThan(0)
    // BUY-only note rendered
    expect(screen.getByTestId('backtest-detail-notes')).toHaveTextContent(
      'BUY signals only',
    )
  })

  it('shows detail error state when run detail returns 500', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(
      () =>
        expect(screen.getByTestId('backtest-detail-error')).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  it('strategy filter switches the runs query', async () => {
    let lastUrl = ''
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', ({ request }) => {
        lastUrl = request.url
        return HttpResponse.json(RUNS)
      }),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })

    await waitFor(() => expect(lastUrl).toContain('/api/backtest/runs'))
    fireEvent.click(screen.getByTestId('backtest-strategy-filter-TopGradeStrategy'))
    await waitFor(() => expect(lastUrl).toContain('strategy=TopGradeStrategy'))
  })

  it('does not expose any automation / order UI', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-detail')).toBeInTheDocument(),
    )

    // No <form> / submit buttons / order CTA labels
    expect(document.querySelectorAll('form').length).toBe(0)
    expect(document.querySelectorAll('button[type="submit"]').length).toBe(0)
    for (const forbidden of ['실거래', '자동매매', '주문 실행', 'place order']) {
      expect(screen.queryByText(new RegExp(forbidden, 'i'))).not.toBeInTheDocument()
    }
    // Forbidden / source_file_path 미노출
    expect(screen.queryByText(/source_file_path/)).not.toBeInTheDocument()
    expect(screen.queryByText(/원문/)).not.toBeInTheDocument()
    expect(screen.queryByText(/본문/)).not.toBeInTheDocument()
  })
})
