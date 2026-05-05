import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { TodayReportPage } from '@/pages/TodayReport'

const HAPPY_BODY = {
  date: '2026-05-05',
  market_regime: {
    id: 1,
    date: '2026-05-05',
    market: 'KOSPI',
    regime: 'NEUTRAL',
    market_score: '50',
    risk_level: 'LOW',
    reason: '시드 데이터',
  },
  latest_run: {
    run_id: 7,
    run_date: '2026-05-04',
    started_at: '2026-05-04T06:00:00Z',
    finished_at: '2026-05-04T06:00:30Z',
    status: 'SUCCESS',
    market_summary: { phase: 'seed_mock_data' },
    telegram_sent: false,
  },
  top_recommendations: [
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
      reason: '관찰 후보',
      risk_note: null,
      snapshot_id: 11,
      risk_level: 'LOW',
      risk_flags: [],
      results: [],
    },
  ],
  holding_alerts: [
    {
      id: 21,
      check_date: '2026-05-05',
      check_type: 'POST_MARKET',
      symbol: '000660',
      current_price: '170000',
      avg_buy_price: '190000',
      return_rate: '-10.5263',
      technical_score: '40',
      news_score: '50',
      earnings_score: '50',
      ai_score: '45',
      risk_score: '23',
      total_score: '20',
      grade: 'D',
      decision: 'SELL_REVIEW',
      reason: '20일선 이탈, 손절 근접',
      alert: true,
      snapshot_id: 33,
      risk_level: 'HIGH',
      risk_flags: ['MA20_BREAKDOWN', 'STOP_LOSS_NEAR'],
    },
  ],
}

const EMPTY_BODY = {
  date: '2026-05-05',
  market_regime: null,
  latest_run: null,
  top_recommendations: [],
  holding_alerts: [],
}

describe('TodayReportPage', () => {
  it('renders all 4 sections with happy data', async () => {
    server.use(http.get('*/api/reports/today', () => HttpResponse.json(HAPPY_BODY)))

    renderWithProviders(<TodayReportPage />, { initialEntries: ['/today'] })

    await waitFor(() =>
      expect(screen.getByTestId('today-top-recs')).toBeInTheDocument(),
    )
    // 추천 TOP
    expect(screen.getByTestId('today-rec-005930')).toHaveTextContent('삼성전자')
    expect(screen.getByTestId('grade-A')).toBeInTheDocument()
    // 보유 점검 알림
    expect(screen.getByTestId('today-holding-000660')).toBeInTheDocument()
    expect(screen.getByTestId('decision-SELL_REVIEW')).toBeInTheDocument()
    expect(screen.getAllByTestId('return-rate').length).toBeGreaterThan(0)
    // HIGH risk 강조
    expect(screen.getByTestId('today-high-risk-000660')).toBeInTheDocument()
    expect(screen.getByText(/MA20_BREAKDOWN/)).toBeInTheDocument()
    // latest run status
    expect(screen.getByTestId('today-latest-run')).toHaveTextContent('SUCCESS')
  })

  it('shows empty placeholders when arrays are empty', async () => {
    server.use(http.get('*/api/reports/today', () => HttpResponse.json(EMPTY_BODY)))

    renderWithProviders(<TodayReportPage />, { initialEntries: ['/today'] })

    await waitFor(() =>
      expect(screen.getByTestId('today-top-recs')).toBeInTheDocument(),
    )
    expect(screen.getByText('표시할 추천이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('표시할 보유 점검이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('HIGH risk 종목이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('최근 run 정보가 없습니다.')).toBeInTheDocument()
  })

  it('shows the error state on /api/reports/today 500', async () => {
    server.use(
      http.get('*/api/reports/today', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderWithProviders(<TodayReportPage />, { initialEntries: ['/today'] })

    await waitFor(() =>
      expect(screen.getByTestId('today-error')).toBeInTheDocument(),
    )
  })
})
