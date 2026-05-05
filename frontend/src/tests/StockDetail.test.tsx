import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { StockDetailPage } from '@/pages/StockDetail'

const HAPPY = {
  stock: {
    symbol: '005930',
    name: '삼성전자',
    market: 'KOSPI',
    sector: '반도체',
    is_active: true,
  },
  latest_price: {
    date: '2026-05-04',
    open: '69500',
    high: '70500',
    low: '69000',
    close: '70000',
    volume: 1500000,
    trading_value: '105000000000',
  },
  latest_indicator: {
    date: '2026-05-04',
    ma5: '70200',
    ma20: '69300',
    ma60: '68500',
    ma120: null,
    rsi14: '55',
    macd: '120',
    macd_signal: '110',
    volume_ratio_20d: '1.4',
    breakout_20d: true,
    breakout_60d: false,
    ma_alignment: 'BULL',
    technical_score: '78',
  },
  recent_recommendations: [
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
      ],
    },
  ],
  recent_holding_checks: [
    {
      id: 21,
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
      reason: '관찰',
      alert: false,
      snapshot_id: 1,
      risk_level: 'LOW',
      risk_flags: [],
    },
  ],
}

function renderStockAt(path: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stocks/:symbol" element={<StockDetailPage />} />
      <Route path="/stocks" element={<StockDetailPage />} />
    </Routes>,
    { initialEntries: [path] },
  )
}

describe('StockDetailPage', () => {
  it('renders stock + price + indicator + recommendations + holding checks (happy)', async () => {
    server.use(http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)))

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-price')).toBeInTheDocument(),
    )
    expect(screen.getByText('삼성전자', { exact: false })).toBeInTheDocument()
    // KOSPI 가 헤더 메타에 노출
    expect(screen.getByText(/KOSPI/)).toBeInTheDocument()
    // indicator card
    expect(screen.getByTestId('stock-detail-indicator')).toBeInTheDocument()
    expect(screen.getByText('BULL')).toBeInTheDocument()
    // recommendations table — recommendation row
    expect(screen.getByTestId('stock-detail-rec-7')).toBeInTheDocument()
    expect(screen.getByTestId('grade-A')).toBeInTheDocument()
    // holding checks table
    expect(screen.getByTestId('stock-detail-check-21')).toBeInTheDocument()
    expect(screen.getByTestId('decision-WATCH')).toBeInTheDocument()
  })

  it('shows empty placeholders when stock has no price/indicator/recs/checks', async () => {
    server.use(
      http.get('*/api/stocks/123456', () =>
        HttpResponse.json({
          stock: {
            symbol: '123456',
            name: '테스트',
            market: 'KOSPI',
            sector: null,
            is_active: true,
          },
          latest_price: null,
          latest_indicator: null,
          recent_recommendations: [],
          recent_holding_checks: [],
        }),
      ),
    )

    renderStockAt('/stocks/123456')
    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-price-empty')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('stock-detail-indicator-empty')).toBeInTheDocument()
    expect(screen.getByText('표시할 추천 이력이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('표시할 점검 이력이 없습니다.')).toBeInTheDocument()
  })

  it('shows the error state when /api/stocks/:symbol returns 404', async () => {
    // Default handler returns 404 for any /api/stocks/:symbol unless overridden.
    renderStockAt('/stocks/UNKNOWN')
    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-error')).toBeInTheDocument(),
    )
  })
})
