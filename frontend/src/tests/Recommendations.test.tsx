import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { RecommendationsPage } from '@/pages/Recommendations'

const HAPPY_LATEST = {
  run: {
    run_id: 7,
    run_date: '2026-05-04',
    started_at: '2026-05-04T06:00:00Z',
    finished_at: '2026-05-04T06:00:30Z',
    status: 'SUCCESS',
    market_summary: { phase: 'seed_mock_data' },
    telegram_sent: false,
  },
  recommendations: [
    {
      recommendation_id: 1,
      run_id: 7,
      run_date: '2026-05-04',
      telegram_sent: false,
      rank: 1,
      market: 'KOSPI',
      symbol: '005930',
      name: '삼성전자',
      grade: 'A',
      total_score: '82',
      technical_score: '80',
      news_score: '50',
      supply_score: '55',
      fundamental_score: '50',
      ai_score: '55',
      risk_score: '0',
      reason: '관찰 후보 · 기술점수 80',
      risk_note: null,
      snapshot_id: 11,
      risk_level: 'LOW',
      risk_flags: [],
      report_score: '75.00',
      theme_signal_score: '60.00',
      report_evidence: {
        report_score_adjustment: '2.50',
        theme_signal_adjustment: '1.00',
        top_themes: [{ theme_name: 'HBM' }],
      },
      news_evidence: {
        news_count: 3,
        positive_count: 2,
        neutral_count: 1,
        negative_count: 0,
        latest_news_at: '2026-05-04T07:00:00+00:00',
        top_news: [
          {
            title: 'HBM 공급 부족 지속',
            url: 'https://example.com/n/1',
            provider: '뉴스원',
            published_at: '2026-05-04T07:00:00+00:00',
            sentiment: 'POSITIVE',
          },
        ],
      },
      disclosure_risk_evidence: {
        risk_disclosure_count: 1,
        recent_risk_disclosures: [
          {
            title: '감사의견 비적정',
            url: 'https://example.com/d/1',
            provider: 'DART',
            published_at: '2026-05-03T09:00:00+00:00',
          },
        ],
      },
      fundamental_evidence: {
        snapshot_date: '2026-05-01',
        fiscal_year: 2025,
        fiscal_quarter: 4,
        per: '12.0000',
        pbr: '1.2000',
        roe: '18.0000',
        debt_ratio: '40.0000',
        revenue_growth_yoy: '12.0000',
        operating_income_growth_yoy: '18.0000',
        dividend_yield: '2.5000',
      },
      earnings_evidence: null,
      results: [
        {
          days_after: 1,
          result_date: '2026-05-05',
          open_return: '0.5',
          high_return: '2.0',
          low_return: '-0.5',
          close_return: '1.5',
          max_return: '2.0',
          max_drawdown: '-0.5',
          result_status: 'SUCCESS',
        },
        {
          days_after: 5,
          result_date: '2026-05-09',
          open_return: '1.5',
          high_return: '4.0',
          low_return: '-2.0',
          close_return: '3.0',
          max_return: '4.0',
          max_drawdown: '-2.0',
          result_status: 'SUCCESS',
        },
      ],
    },
  ],
}

function renderRecsAt(path = '/recommendations') {
  return renderWithProviders(
    <Routes>
      <Route path="/recommendations" element={<RecommendationsPage />} />
      <Route path="/recommendations/runs/:runId" element={<RecommendationsPage />} />
    </Routes>,
    { initialEntries: [path] },
  )
}

describe('RecommendationsPage', () => {
  it('renders the latest run with metric cards + table (happy)', async () => {
    server.use(
      http.get('*/api/recommendations/latest', () => HttpResponse.json(HAPPY_LATEST)),
    )

    renderRecsAt('/recommendations')

    await waitFor(() =>
      expect(screen.getByTestId('rec-row-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('rec-metric-run-date')).toHaveTextContent('2026-05-04')
    expect(screen.getByTestId('rec-metric-count')).toHaveTextContent('1')
    expect(screen.getByTestId('rec-metric-grade-dist')).toHaveTextContent('A:1')
    expect(screen.getByTestId('grade-A')).toBeInTheDocument()
    expect(screen.getByTestId('risk-LOW')).toBeInTheDocument()
    expect(screen.getByTestId('rec-report-score-005930')).toHaveTextContent('75.00')
    expect(screen.getByTestId('rec-theme-score-005930')).toHaveTextContent('60.00')
    expect(screen.getByTestId('rec-report-evidence-005930')).toHaveTextContent(
      'HBM',
    )
    // v0.5 Phase D — news_evidence + disclosure_risk_evidence cells
    expect(screen.getByTestId('rec-news-evidence-005930')).toHaveTextContent('n=3')
    expect(screen.getByTestId('rec-news-evidence-005930')).toHaveTextContent(
      'HBM 공급 부족',
    )
    expect(screen.getByTestId('rec-disclosure-evidence-005930')).toHaveTextContent(
      '감사의견 비적정',
    )
    // v0.6 Phase D — fundamental evidence cell
    expect(screen.getByTestId('rec-fund-evidence-005930')).toHaveTextContent(
      'PER 12.0000',
    )
    expect(screen.getByTestId('rec-fund-evidence-005930')).toHaveTextContent(
      'ROE 18.0000',
    )
    // earnings evidence — null on recommendation flow → "—"
    expect(screen.getByTestId('rec-earnings-evidence-005930')).toHaveTextContent('—')
    // forbidden fields must not leak into the rendered table
    expect(screen.queryByText(/source_file_path/)).not.toBeInTheDocument()
    expect(screen.queryByText(/원문/)).not.toBeInTheDocument()
    expect(screen.queryByText(/본문/)).not.toBeInTheDocument()
    // 1/3/5/20 day result columns: 1d → +1.50%, 5d → +3.00%, 3d/20d → "—"
    expect(screen.getAllByTestId('return-rate').length).toBeGreaterThanOrEqual(4)
  })

  it('renders report score null fallbacks as dashes', async () => {
    server.use(
      http.get('*/api/recommendations/latest', () =>
        HttpResponse.json({
          ...HAPPY_LATEST,
          recommendations: [
            {
              ...HAPPY_LATEST.recommendations[0],
              report_score: null,
              theme_signal_score: null,
              report_evidence: null,
              news_evidence: null,
              disclosure_risk_evidence: null,
              fundamental_evidence: null,
              earnings_evidence: null,
            },
          ],
        }),
      ),
    )

    renderRecsAt('/recommendations')
    await waitFor(() =>
      expect(screen.getByTestId('rec-row-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('rec-report-score-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-theme-score-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-report-evidence-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-news-evidence-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-disclosure-evidence-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-fund-evidence-005930')).toHaveTextContent('—')
    expect(screen.getByTestId('rec-earnings-evidence-005930')).toHaveTextContent('—')
  })

  it('shows empty table when run has no recommendations', async () => {
    server.use(
      http.get('*/api/recommendations/latest', () =>
        HttpResponse.json({
          run: HAPPY_LATEST.run,
          recommendations: [],
        }),
      ),
    )

    renderRecsAt('/recommendations')
    await waitFor(() => expect(screen.getByTestId('recs-empty')).toBeInTheDocument())
    expect(screen.queryByTestId('recs-table-body')).not.toBeInTheDocument()
  })

  it('shows error when /api/recommendations/latest is 404 (no runs yet)', async () => {
    // Default handler already returns 404 — explicit override not required.
    renderRecsAt('/recommendations')
    await waitFor(() => expect(screen.getByTestId('recs-error')).toBeInTheDocument())
  })

  it('loads a specific run via /recommendations/runs/:runId', async () => {
    server.use(
      http.get('*/api/recommendations/7', () => HttpResponse.json(HAPPY_LATEST)),
    )

    renderRecsAt('/recommendations/runs/7')
    await waitFor(() =>
      expect(screen.getByTestId('rec-row-005930')).toBeInTheDocument(),
    )
    expect(screen.getByText('추천 종목 — run #7')).toBeInTheDocument()
  })
})
