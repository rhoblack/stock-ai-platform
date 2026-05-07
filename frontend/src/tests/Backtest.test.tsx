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
      evidence_json: { grade: 'A', data_source: 'PROVIDER' },
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
      evidence_json: { data_source: 'FAKE' },
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

const FOLDS_42 = {
  run_id: 42,
  mode: 'walk_forward',
  total_folds: 2,
  avg_oos_win_rate_5d: '0.6000',
  avg_oos_avg_return_5d: '0.0200',
  folds: [
    {
      fold_index: 0,
      train_start: '2026-01-01',
      train_end: '2026-01-30',
      validate_start: '2026-01-31',
      validate_end: '2026-03-01',
      is_oos_gap: 0,
      is_signal_count: 5,
      is_buy_count: 2,
      is_win_rate_5d: '0.5000',
      is_avg_return_5d: '0.0100',
      oos_signal_count: 5,
      oos_buy_count: 2,
      oos_win_rate_5d: '0.5000',
      oos_avg_return_5d: '0.0100',
    },
    {
      fold_index: 1,
      train_start: '2026-03-02',
      train_end: '2026-03-31',
      validate_start: '2026-04-01',
      validate_end: '2026-04-30',
      is_oos_gap: 0,
      is_signal_count: 5,
      is_buy_count: 3,
      is_win_rate_5d: '0.6667',
      is_avg_return_5d: '0.0300',
      oos_signal_count: 5,
      oos_buy_count: 3,
      oos_win_rate_5d: '0.6667',
      oos_avg_return_5d: '0.0300',
    },
  ],
}

const COMPARISON_42 = {
  run_id: 42,
  mode: 'multi_strategy_comparison',
  total_strategies: 2,
  best_strategy_by_win_rate_5d: 'TopGradeStrategy',
  best_strategy_by_avg_return_5d: 'TopGradeStrategy',
  strategies: [
    {
      strategy_name: 'TopGradeStrategy',
      strategy_version: 'v1.0.0',
      signal_count: 2,
      buy_count: 1,
      pass_count: 1,
      avoid_count: 0,
      win_rate_5d: '1.0000',
      avg_return_5d: '0.0500',
      cost_adjusted_avg_return_5d: null,
      max_drawdown: null,
      regime_breakdown: [],
      sector_breakdown: [
        { sector: 'IT', signal_count: 1, buy_count: 1, win_rate_5d: '1.0000', avg_return_5d: '0.0500' },
        { sector: 'Semiconductor', signal_count: 1, buy_count: 0, win_rate_5d: null, avg_return_5d: null },
      ],
    },
    {
      strategy_name: 'HighScoreStrategy',
      strategy_version: 'v1.0.0',
      signal_count: 2,
      buy_count: 1,
      pass_count: 1,
      avoid_count: 0,
      win_rate_5d: '0.0000',
      avg_return_5d: '-0.0300',
      cost_adjusted_avg_return_5d: null,
      max_drawdown: null,
      regime_breakdown: [],
      sector_breakdown: [],
    },
  ],
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

// ---------------------------------------------------------------------------
// Phase D — walk-forward folds
// ---------------------------------------------------------------------------

describe('BacktestPage — walk-forward folds (v0.12 Phase D)', () => {
  it('renders fold table when folds endpoint returns data', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
      http.get('*/api/backtest/runs/42/folds', () => HttpResponse.json(FOLDS_42)),
      http.get('*/api/backtest/runs/42/comparison', () =>
        HttpResponse.json({ run_id: 42, mode: 'multi_strategy_comparison', total_strategies: 0, best_strategy_by_win_rate_5d: null, best_strategy_by_avg_return_5d: null, strategies: [] }),
      ),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-folds')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('backtest-folds-table')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-fold-0')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-fold-1')).toBeInTheDocument()
  })

  it('shows empty placeholder when no fold data', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
      // default empty handlers for folds/comparison already in mswServer
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-folds-empty')).toBeInTheDocument(),
    )
  })
})

// ---------------------------------------------------------------------------
// Phase D — multi-strategy comparison
// ---------------------------------------------------------------------------

describe('BacktestPage — multi-strategy comparison (v0.12 Phase D)', () => {
  it('renders comparison table with best strategy highlight', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
      http.get('*/api/backtest/runs/42/folds', () =>
        HttpResponse.json({ run_id: 42, mode: 'walk_forward', total_folds: 0, avg_oos_win_rate_5d: null, avg_oos_avg_return_5d: null, folds: [] }),
      ),
      http.get('*/api/backtest/runs/42/comparison', () => HttpResponse.json(COMPARISON_42)),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-comparison')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('backtest-comparison-table')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-comparison-row-TopGradeStrategy')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-comparison-row-HighScoreStrategy')).toBeInTheDocument()
    // Best strategy highlight
    expect(screen.getByTestId('backtest-comparison-best')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-comparison-best-TopGradeStrategy')).toBeInTheDocument()
    // Sector breakdown appears
    expect(screen.getByTestId('backtest-sector-breakdown')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-sector-TopGradeStrategy-IT')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-sector-TopGradeStrategy-Semiconductor')).toBeInTheDocument()
  })

  it('shows empty placeholder when no comparison data', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
      // default empty handlers already in mswServer
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-comparison-empty')).toBeInTheDocument(),
    )
  })
})

// ---------------------------------------------------------------------------
// Phase D — data_source chip
// ---------------------------------------------------------------------------

describe('BacktestPage — data_source chip (v0.12 Phase D)', () => {
  it('renders PROVIDER and FAKE chips from evidence_json.data_source', async () => {
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
    // RUN_DETAIL_42 has evidence_json: { data_source: 'PROVIDER' } on result 1001
    // and { data_source: 'FAKE' } on 1002
    expect(screen.getByTestId('backtest-data-source-PROVIDER')).toBeInTheDocument()
    expect(screen.getByTestId('backtest-data-source-FAKE')).toBeInTheDocument()
  })

  it('does not render data_source chip when evidence_json is null', async () => {
    const detailNoSource = {
      ...RUN_DETAIL_42,
      results: RUN_DETAIL_42.results.map(r => ({ ...r, evidence_json: null })),
    }
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(detailNoSource)),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-detail')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('backtest-data-source-PROVIDER')).not.toBeInTheDocument()
    expect(screen.queryByTestId('backtest-data-source-FAKE')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Phase D — forbidden field / automation guard
// ---------------------------------------------------------------------------

describe('BacktestPage — forbidden field guard (v0.12 Phase D)', () => {
  it('does not render raw_text / 본문 / 원문 / source_file_path anywhere', async () => {
    server.use(
      http.get('*/api/strategies', () => HttpResponse.json(STRATEGIES)),
      http.get('*/api/backtest/runs', () => HttpResponse.json(RUNS)),
      http.get('*/api/backtest/runs/42', () => HttpResponse.json(RUN_DETAIL_42)),
      http.get('*/api/backtest/runs/42/comparison', () => HttpResponse.json(COMPARISON_42)),
    )
    renderWithProviders(<BacktestPage />, { initialEntries: ['/backtest'] })
    await waitFor(() =>
      expect(screen.getByTestId('backtest-run-row-42')).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByTestId('backtest-run-row-42'))
    await waitFor(() =>
      expect(screen.getByTestId('backtest-detail')).toBeInTheDocument(),
    )
    for (const forbidden of ['source_file_path', 'raw_text', 'full_text', '본문', '원문', '전문']) {
      expect(screen.queryByText(new RegExp(forbidden, 'i'))).not.toBeInTheDocument()
    }
  })
})
