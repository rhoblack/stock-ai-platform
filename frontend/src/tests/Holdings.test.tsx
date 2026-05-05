import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { HoldingsPage } from '@/pages/Holdings'

const HOLDINGS_BODY = {
  items: [
    {
      id: 1,
      symbol: '005930',
      quantity: '20',
      avg_buy_price: '66000',
      strategy_type: 'LONG',
      target_price: null,
      stop_loss_price: null,
      memo: null,
      is_active: true,
    },
    {
      id: 2,
      symbol: '000660',
      quantity: '5',
      avg_buy_price: '190000',
      strategy_type: 'MID',
      target_price: null,
      stop_loss_price: null,
      memo: null,
      is_active: true,
    },
  ],
}

const LATEST_CHECKS_BODY = {
  items: [
    {
      id: 11,
      check_date: '2026-05-05',
      check_type: 'POST_MARKET',
      symbol: '005930',
      current_price: '70000',
      avg_buy_price: '66000',
      return_rate: '6.0606',
      technical_score: '60',
      news_score: '50',
      earnings_score: '50',
      ai_score: '50',
      risk_score: '0',
      total_score: '60',
      grade: 'B',
      decision: 'WATCH',
      reason: 'mock',
      alert: false,
      snapshot_id: 1,
      risk_level: 'LOW',
      risk_flags: [],
    },
    {
      id: 12,
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
      reason: 'MA20 이탈',
      alert: true,
      snapshot_id: 2,
      risk_level: 'HIGH',
      risk_flags: ['MA20_BREAKDOWN'],
    },
  ],
}

const SYMBOL_CHECKS_BODY_005930 = {
  items: [
    {
      id: 21,
      check_date: '2026-05-05',
      check_type: 'POST_MARKET',
      symbol: '005930',
      current_price: '70000',
      avg_buy_price: '66000',
      return_rate: '6.0606',
      technical_score: '60',
      news_score: null,
      earnings_score: null,
      ai_score: null,
      risk_score: null,
      total_score: '60',
      grade: 'B',
      decision: 'WATCH',
      reason: 'mock',
      alert: false,
      snapshot_id: 1,
      risk_level: 'LOW',
      risk_flags: [],
    },
    {
      id: 22,
      check_date: '2026-05-04',
      check_type: 'POST_MARKET',
      symbol: '005930',
      current_price: '69000',
      avg_buy_price: '66000',
      return_rate: '4.5455',
      technical_score: null,
      news_score: null,
      earnings_score: null,
      ai_score: null,
      risk_score: null,
      total_score: '70',
      grade: 'A',
      decision: 'HOLD',
      reason: 'mock',
      alert: false,
      snapshot_id: 1,
      risk_level: 'LOW',
      risk_flags: [],
    },
  ],
  summary: {
    total_check_count: 2,
    alert_count: 0,
    high_risk_count: 0,
    latest_check_date: '2026-05-05',
    latest_total_score: '60',
    previous_total_score: '70',
    total_score_change: '-10',
    latest_return_rate: '6.0606',
    best_return_rate: '6.0606',
    worst_return_rate: '4.5455',
    latest_decision: 'WATCH',
    latest_risk_level: 'LOW',
  },
}

function renderHoldingsAt(path = '/holdings') {
  return renderWithProviders(
    <Routes>
      <Route path="/holdings" element={<HoldingsPage />} />
      <Route path="/holdings/:symbol" element={<HoldingsPage />} />
    </Routes>,
    { initialEntries: [path] },
  )
}

describe('HoldingsPage', () => {
  it('renders holdings list with latest check decision/risk/alert (happy)', async () => {
    server.use(
      http.get('*/api/holdings', () => HttpResponse.json(HOLDINGS_BODY)),
      http.get('*/api/holdings/checks/latest', () =>
        HttpResponse.json(LATEST_CHECKS_BODY),
      ),
    )

    renderHoldingsAt('/holdings')
    await waitFor(() =>
      expect(screen.getByTestId('holding-row-005930')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('holding-row-000660')).toBeInTheDocument()
    expect(screen.getByTestId('decision-WATCH')).toBeInTheDocument()
    expect(screen.getByTestId('decision-SELL_REVIEW')).toBeInTheDocument()
    expect(screen.getByTestId('risk-LOW')).toBeInTheDocument()
    expect(screen.getByTestId('risk-HIGH')).toBeInTheDocument()
    expect(screen.getByTestId('holding-alert-000660')).toHaveTextContent('alert')
  })

  it('opens trend panel for selected symbol with all 4 metric cards (click)', async () => {
    server.use(
      http.get('*/api/holdings', () => HttpResponse.json(HOLDINGS_BODY)),
      http.get('*/api/holdings/checks/latest', () =>
        HttpResponse.json(LATEST_CHECKS_BODY),
      ),
      http.get('*/api/holdings/005930/checks', () =>
        HttpResponse.json(SYMBOL_CHECKS_BODY_005930),
      ),
    )

    renderHoldingsAt('/holdings')
    const row = await screen.findByTestId('holding-row-005930')
    await userEvent.click(row)

    await waitFor(() =>
      expect(screen.getByTestId('holding-panel')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('holding-metric-latest-score')).toHaveTextContent('60')
    expect(screen.getByTestId('holding-metric-score-change')).toHaveTextContent('-10') // total_score_change
    expect(screen.getByTestId('holding-metric-latest-return')).toBeInTheDocument()
    expect(screen.getByTestId('holding-metric-alert')).toHaveTextContent('0 / 0')
    // 두 개의 trend chart 가 모두 렌더 (Recharts container or empty placeholder)
    expect(screen.getByTestId('holding-trend-score')).toBeInTheDocument()
    expect(screen.getByTestId('holding-trend-return')).toBeInTheDocument()
  })

  it('shows empty state when no holdings', async () => {
    // Default handlers already return empty.
    renderHoldingsAt('/holdings')
    await waitFor(() => expect(screen.getByTestId('holdings-empty')).toBeInTheDocument())
  })

  it('shows error state when /api/holdings is 500', async () => {
    server.use(
      http.get('*/api/holdings', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )

    renderHoldingsAt('/holdings')
    await waitFor(() => expect(screen.getByTestId('holdings-error')).toBeInTheDocument())
  })
})
