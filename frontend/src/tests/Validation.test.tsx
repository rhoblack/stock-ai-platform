import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { ValidationPage } from '@/pages/Validation'

const EMPTY_SCORE_DELTA = {
  total_scored: 0,
  policy_enabled_count: 0,
  avg_delta: null,
  positive_delta_count: 0,
  negative_delta_count: 0,
  neutral_delta_count: 0,
  data_source_counts: {},
}

const REPORT_EMPTY = {
  generated_at: '2026-05-08T00:00:00',
  run_count: 0,
  signal_count: 0,
  buy_count: 0,
  win_rate_5d: null,
  avg_return_5d: null,
  score_delta: EMPTY_SCORE_DELTA,
}

const REPORT_HAPPY = {
  generated_at: '2026-05-08T09:00:00',
  run_count: 5,
  signal_count: 100,
  buy_count: 40,
  win_rate_5d: '0.6000',
  avg_return_5d: '0.0250',
  score_delta: {
    total_scored: 30,
    policy_enabled_count: 25,
    avg_delta: '0.0120',
    positive_delta_count: 18,
    negative_delta_count: 7,
    neutral_delta_count: 5,
    data_source_counts: { PROVIDER: 20, FAKE: 5, CSV: 5 },
  },
}

const STRATEGIES_HAPPY = {
  count: 2,
  items: [
    {
      strategy_name: 'TopGradeStrategy',
      run_count: 3,
      signal_count: 60,
      buy_count: 25,
      win_rate_5d: '0.6400',
      avg_return_5d: '0.0280',
      cost_adjusted_avg_return_5d: '0.0250',
      max_drawdown: '-0.0500',
    },
    {
      strategy_name: 'HighScoreStrategy',
      run_count: 2,
      signal_count: 40,
      buy_count: 15,
      win_rate_5d: '0.5333',
      avg_return_5d: '0.0200',
      cost_adjusted_avg_return_5d: null,
      max_drawdown: null,
    },
  ],
}

const REGIMES_HAPPY = {
  count: 2,
  items: [
    { regime: 'UPTREND_EARLY', buy_count: 20, win_rate_5d: '0.7000', avg_return_5d: '0.0350' },
    { regime: 'UNCLASSIFIED', buy_count: 10, win_rate_5d: '0.5000', avg_return_5d: '0.0100' },
  ],
}

const SECTORS_HAPPY = {
  count: 2,
  items: [
    { sector: '반도체', buy_count: 15, win_rate_5d: '0.7333', avg_return_5d: '0.0400' },
    { sector: 'UNKNOWN', buy_count: 5, win_rate_5d: null, avg_return_5d: null },
  ],
}

describe('ValidationPage', () => {
  it('renders validation-page wrapper', async () => {
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    expect(screen.getByTestId('validation-page')).toBeInTheDocument()
    expect(screen.getByTestId('validation-report-card')).toBeInTheDocument()
  })

  it('shows empty state when report returns zero data', async () => {
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.queryByTestId('validation-report-loading')).not.toBeInTheDocument(),
    )
    // Default MSW returns 0 run_count — score_delta card still renders since data is present
    expect(screen.getByTestId('validation-score-delta-card')).toBeInTheDocument()
    expect(screen.getByTestId('validation-strategy-empty')).toBeInTheDocument()
    expect(screen.getByTestId('validation-regime-empty')).toBeInTheDocument()
    expect(screen.getByTestId('validation-sector-empty')).toBeInTheDocument()
  })

  it('renders happy-path overall summary stats', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.queryByTestId('validation-report-loading')).not.toBeInTheDocument(),
    )
    // signal_count=100, buy_count=40 are unique in the fixture
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('40')).toBeInTheDocument()
    // score_delta card shows totals
    expect(screen.getByTestId('validation-score-delta-card')).toBeInTheDocument()
    expect(screen.getByTestId('validation-data-source-PROVIDER')).toBeInTheDocument()
    expect(screen.getByTestId('validation-data-source-FAKE')).toBeInTheDocument()
    expect(screen.getByTestId('validation-data-source-CSV')).toBeInTheDocument()
  })

  it('renders strategy table with rows', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_EMPTY)),
      http.get('*/api/validation/report/by-strategy', () => HttpResponse.json(STRATEGIES_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-strategy-table')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('validation-strategy-row-TopGradeStrategy')).toBeInTheDocument()
    expect(screen.getByTestId('validation-strategy-row-HighScoreStrategy')).toBeInTheDocument()
  })

  it('renders regime rows including UNCLASSIFIED', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_EMPTY)),
      http.get('*/api/validation/report/by-regime', () => HttpResponse.json(REGIMES_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-regime-row-UPTREND_EARLY')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('validation-regime-row-UNCLASSIFIED')).toBeInTheDocument()
  })

  it('renders sector rows including UNKNOWN', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_EMPTY)),
      http.get('*/api/validation/report/by-sector', () => HttpResponse.json(SECTORS_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-sector-row-반도체')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('validation-sector-row-UNKNOWN')).toBeInTheDocument()
  })

  it('shows report error state when endpoint returns 500', async () => {
    server.use(
      http.get('*/api/validation/report', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(
      () => expect(screen.getByTestId('validation-report-error')).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  it('does not expose automation or forbidden fields', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_HAPPY)),
      http.get('*/api/validation/report/by-strategy', () => HttpResponse.json(STRATEGIES_HAPPY)),
      http.get('*/api/validation/report/by-regime', () => HttpResponse.json(REGIMES_HAPPY)),
      http.get('*/api/validation/report/by-sector', () => HttpResponse.json(SECTORS_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-strategy-table')).toBeInTheDocument(),
    )
    // No forms or submit buttons
    expect(document.querySelectorAll('form').length).toBe(0)
    expect(document.querySelectorAll('button[type="submit"]').length).toBe(0)
    // No forbidden text
    for (const forbidden of [
      'source_file_path',
      'raw_text',
      'evidence_json',
      '본문',
      '원문',
      '실거래',
      '자동매매',
    ]) {
      expect(screen.queryByText(new RegExp(forbidden, 'i'))).not.toBeInTheDocument()
    }
  })

  it('data_source chips not rendered when data_source_counts is empty', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_EMPTY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-score-delta-card')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('validation-data-source-PROVIDER')).not.toBeInTheDocument()
    expect(screen.queryByTestId('validation-data-source-FAKE')).not.toBeInTheDocument()
  })

  it('cost_adjusted and max_drawdown show dash when null', async () => {
    server.use(
      http.get('*/api/validation/report', () => HttpResponse.json(REPORT_EMPTY)),
      http.get('*/api/validation/report/by-strategy', () => HttpResponse.json(STRATEGIES_HAPPY)),
    )
    renderWithProviders(<ValidationPage />, { initialEntries: ['/validation'] })
    await waitFor(() =>
      expect(screen.getByTestId('validation-strategy-row-HighScoreStrategy')).toBeInTheDocument(),
    )
    // HighScoreStrategy has null cost_adjusted and max_drawdown → shown as "—"
    const row = screen.getByTestId('validation-strategy-row-HighScoreStrategy')
    expect(row.textContent).toContain('—')
  })
})
