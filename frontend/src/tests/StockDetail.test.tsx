import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
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
  analyst_reports: {
    symbol: '005930',
    latest_consensus: {
      symbol: '005930',
      snapshot_date: '2026-05-04',
      window_days: 90,
      report_count: 2,
      avg_target_price: '82000',
      min_target_price: '78000',
      max_target_price: '86000',
      strong_buy_count: 0,
      buy_count: 2,
      hold_count: 0,
      sell_count: 0,
      strong_sell_count: 0,
      latest_published_at: '2026-05-02',
    },
    recent_reports: [
      {
        id: 31,
        symbol: '005930',
        company_name: '삼성전자',
        market: 'KOSPI',
        report_type: 'COMPANY',
        broker_name: '테스트증권',
        analyst_name: '홍길동',
        published_at: '2026-05-02',
        title: '삼성전자 HBM 수요 회복',
        rating: 'BUY',
        normalized_rating: 'BUY',
        target_price: '84000',
        currency: 'KRW',
        summary: 'HBM 수요 회복과 서버 메모리 가격 반등',
        source_url: 'https://example.com/reports/005930',
      },
    ],
    related_themes: [
      {
        theme_id: 41,
        theme_name: 'HBM',
        theme_category: 'SEMICONDUCTOR',
        direction: 'POSITIVE',
        time_horizon: 'MID',
        summary: 'AI 서버 메모리 수요',
        mapping_id: 51,
        impact_direction: 'POSITIVE',
        impact_strength: '0.800',
        impact_path: 'DEMAND_INCREASE',
        relation_type: 'SUPPLIER',
        benefit_type: 'PRICE_POWER',
        time_lag: 'MID',
        reason: 'HBM 공급사',
      },
    ],
    recent_signal_events: [
      {
        id: 61,
        report_id: 32,
        symbol: '005930',
        theme_id: 41,
        event_type: 'SUPPLY_SHORTAGE',
        direction: 'POSITIVE',
        strength: '0.700',
        time_horizon: 'MID',
        summary: 'HBM 공급 부족 지속',
        evidence_json: { source: 'fixture' },
      },
    ],
  },
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
    expect(
      screen.getByRole('heading', { name: /삼성전자 \(005930\)/ }),
    ).toBeInTheDocument()
    // KOSPI 가 헤더 메타에 노출
    expect(screen.getByText(/KOSPI/)).toBeInTheDocument()
    // indicator card
    expect(screen.getByTestId('stock-detail-indicator')).toBeInTheDocument()
    expect(screen.getByText('BULL')).toBeInTheDocument()
    // analyst report cards
    expect(screen.getByTestId('stock-detail-consensus')).toBeInTheDocument()
    expect(screen.getByText('Analyst Consensus')).toBeInTheDocument()
    expect(screen.getByText('삼성전자 HBM 수요 회복')).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-theme-51')).toHaveTextContent('HBM')
    expect(screen.getByTestId('stock-detail-signal-61')).toHaveTextContent(
      'SUPPLY_SHORTAGE',
    )
    expect(screen.queryByText(/source_file_path/)).not.toBeInTheDocument()
    expect(screen.queryByText(/D:\/private/)).not.toBeInTheDocument()
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
          analyst_reports: {
            symbol: '123456',
            latest_consensus: null,
            recent_reports: [],
            related_themes: [],
            recent_signal_events: [],
          },
        }),
      ),
    )

    renderStockAt('/stocks/123456')
    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-price-empty')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('stock-detail-indicator-empty')).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-consensus-empty')).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-analyst-reports-empty')).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-related-themes-empty')).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-signal-events-empty')).toBeInTheDocument()
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

  it('renders the price chart card with prices when /api/stocks/:symbol/prices succeeds', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/prices', () =>
        HttpResponse.json({
          symbol: '005930',
          days: 120,
          count: 3,
          prices: [
            {
              date: '2026-04-30',
              open: '69000',
              high: '70000',
              low: '68500',
              close: '69500',
              volume: 1200000,
              trading_value: null,
            },
            {
              date: '2026-05-01',
              open: '69500',
              high: '70500',
              low: '69000',
              close: '70000',
              volume: 1300000,
              trading_value: null,
            },
            {
              date: '2026-05-04',
              open: '70000',
              high: '71000',
              low: '69500',
              close: '70500',
              volume: 1500000,
              trading_value: null,
            },
          ],
        }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-price-chart')).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getByTestId('price-chart')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('price-chart-empty')).not.toBeInTheDocument()
    // 기본 days = 120 의 버튼이 active
    expect(screen.getByTestId('price-chart-days-120')).toHaveAttribute(
      'data-active',
      'true',
    )
    expect(screen.getByTestId('price-chart-days-30')).toHaveAttribute(
      'data-active',
      'false',
    )
  })

  it('shows the price chart empty placeholder when count=0', async () => {
    // /api/stocks/:symbol/prices 기본 핸들러는 count=0 반환.
    server.use(http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)))

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-price-chart')).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getByTestId('price-chart-empty')).toBeInTheDocument(),
    )
  })

  it('shows the price chart error state when /api/stocks/:symbol/prices returns 500', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/prices', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(
      () => expect(screen.getByTestId('price-chart-error')).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  it('switches days selection (120 → 30) and re-fetches the price series', async () => {
    let lastDays: string | null = null
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/prices', ({ request }) => {
        const url = new URL(request.url)
        lastDays = url.searchParams.get('days')
        return HttpResponse.json({
          symbol: '005930',
          days: Number(lastDays ?? 120),
          count: 1,
          prices: [
            {
              date: '2026-05-04',
              open: '70000',
              high: '70500',
              low: '69500',
              close: '70000',
              volume: 1000000,
              trading_value: null,
            },
          ],
        })
      }),
    )

    renderStockAt('/stocks/005930')
    await waitFor(() => expect(lastDays).toBe('120'))

    fireEvent.click(screen.getByTestId('price-chart-days-30'))

    await waitFor(() => expect(lastDays).toBe('30'))
    expect(screen.getByTestId('price-chart-days-30')).toHaveAttribute(
      'data-active',
      'true',
    )
  })
})
