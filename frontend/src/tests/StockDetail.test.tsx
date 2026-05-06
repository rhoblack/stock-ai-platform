import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    // v0.5 Phase D — theme name is a clickable Link to /themes/:theme_id
    const themeLink = screen.getByTestId('stock-detail-theme-link-41')
    expect(themeLink).toHaveAttribute('href', '/themes/41')
    // impact_path renders as a dedicated badge
    expect(screen.getByTestId('stock-detail-theme-impact-51')).toHaveTextContent(
      'DEMAND_INCREASE',
    )
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

  // -------- v0.6 Phase D — Fundamentals card --------
  it('renders FundamentalsCard latest + history when /fundamentals returns rows', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/fundamentals', () =>
        HttpResponse.json({
          symbol: '005930',
          latest: {
            snapshot_date: '2026-05-01',
            fiscal_year: 2025,
            fiscal_quarter: 4,
            revenue: '100000',
            operating_income: '20000',
            net_income: '15000',
            total_assets: '500000',
            total_liabilities: '200000',
            total_equity: '300000',
            eps: '3500',
            bps: '60000',
            per: '12.0000',
            pbr: '1.2000',
            roe: '18.0000',
            debt_ratio: '40.0000',
            dividend_yield: '2.5000',
            revenue_growth_yoy: '12.0000',
            operating_income_growth_yoy: '18.0000',
            source: 'MANUAL',
          },
          history: [
            {
              snapshot_date: '2026-05-01',
              fiscal_year: 2025,
              fiscal_quarter: 4,
              revenue: '100000',
              operating_income: '20000',
              net_income: '15000',
              total_assets: '500000',
              total_liabilities: '200000',
              total_equity: '300000',
              eps: '3500',
              bps: '60000',
              per: '12.0000',
              pbr: '1.2000',
              roe: '18.0000',
              debt_ratio: '40.0000',
              dividend_yield: '2.5000',
              revenue_growth_yoy: '12.0000',
              operating_income_growth_yoy: '18.0000',
              source: 'MANUAL',
            },
            {
              snapshot_date: '2025-11-14',
              fiscal_year: 2025,
              fiscal_quarter: 3,
              revenue: null,
              operating_income: null,
              net_income: null,
              total_assets: null,
              total_liabilities: null,
              total_equity: null,
              eps: null,
              bps: null,
              per: '13.0000',
              pbr: null,
              roe: null,
              debt_ratio: null,
              dividend_yield: null,
              revenue_growth_yoy: null,
              operating_income_growth_yoy: null,
              source: 'MANUAL',
            },
          ],
          count: 2,
        }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-fundamentals')).toBeInTheDocument(),
    )
    expect(
      screen.getByTestId('stock-detail-fundamentals-latest'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('stock-detail-fundamentals-history')).toBeInTheDocument()
    expect(screen.getByTestId('fund-row-2025-4')).toBeInTheDocument()
    expect(screen.getByTestId('fund-row-2025-3')).toBeInTheDocument()
    // forbidden / source_file_path 미노출
    expect(screen.queryByText(/source_file_path/)).not.toBeInTheDocument()
    expect(screen.queryByText(/D:\/private/)).not.toBeInTheDocument()
    expect(screen.queryByText(/원문/)).not.toBeInTheDocument()
    expect(screen.queryByText(/본문/)).not.toBeInTheDocument()
  })

  it('shows the FundamentalsCard empty placeholder when /fundamentals returns count=0', async () => {
    // default handler in mswServer returns count=0 for fundamentals.
    server.use(http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)))
    renderStockAt('/stocks/005930')
    await waitFor(() =>
      expect(
        screen.getByTestId('stock-detail-fundamentals-empty'),
      ).toBeInTheDocument(),
    )
  })

  it('shows the FundamentalsCard error state when /fundamentals returns 500', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/fundamentals', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderStockAt('/stocks/005930')
    await waitFor(
      () =>
        expect(
          screen.getByTestId('stock-detail-fundamentals-error'),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  // -------- v0.6 Phase D — Earnings card --------
  it('renders EarningsCard latest + history with surprise badge when events exist', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/earnings', () =>
        HttpResponse.json({
          symbol: '005930',
          latest: {
            event_date: '2026-05-01',
            fiscal_year: 2026,
            fiscal_quarter: 1,
            event_type: 'REPORT',
            company_name: '삼성전자',
            revenue_actual: null,
            revenue_consensus: null,
            operating_income_actual: '110.0000',
            operating_income_consensus: '100.0000',
            net_income_actual: null,
            net_income_consensus: null,
            eps_actual: '3500.0000',
            eps_consensus: '3300.0000',
            surprise_type: 'BEAT',
            surprise_pct: '10.0000',
            source: 'MANUAL',
            memo: null,
          },
          events: [
            {
              event_date: '2026-05-01',
              fiscal_year: 2026,
              fiscal_quarter: 1,
              event_type: 'REPORT',
              company_name: '삼성전자',
              revenue_actual: null,
              revenue_consensus: null,
              operating_income_actual: '110.0000',
              operating_income_consensus: '100.0000',
              net_income_actual: null,
              net_income_consensus: null,
              eps_actual: '3500.0000',
              eps_consensus: '3300.0000',
              surprise_type: 'BEAT',
              surprise_pct: '10.0000',
              source: 'MANUAL',
              memo: null,
            },
            {
              event_date: '2025-11-01',
              fiscal_year: 2025,
              fiscal_quarter: 3,
              event_type: 'REPORT',
              company_name: '삼성전자',
              revenue_actual: null,
              revenue_consensus: null,
              operating_income_actual: '90.0000',
              operating_income_consensus: '95.0000',
              net_income_actual: null,
              net_income_consensus: null,
              eps_actual: null,
              eps_consensus: null,
              surprise_type: 'MISS',
              surprise_pct: '-5.2632',
              source: 'MANUAL',
              memo: null,
            },
          ],
          count: 2,
        }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-earnings')).toBeInTheDocument(),
    )
    // BEAT badge for latest, MISS badge in history
    expect(screen.getAllByTestId('earnings-surprise-BEAT').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('earnings-surprise-MISS').length).toBeGreaterThan(0)
    expect(screen.getByTestId('earnings-row-2026-1')).toBeInTheDocument()
    expect(screen.getByTestId('earnings-row-2025-3')).toBeInTheDocument()
    expect(screen.queryByText(/source_file_path/)).not.toBeInTheDocument()
    expect(screen.queryByText(/원문/)).not.toBeInTheDocument()
    expect(screen.queryByText(/본문/)).not.toBeInTheDocument()
  })

  it('shows the EarningsCard empty placeholder when /earnings returns count=0', async () => {
    server.use(http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)))
    renderStockAt('/stocks/005930')
    await waitFor(() =>
      expect(
        screen.getByTestId('stock-detail-earnings-empty'),
      ).toBeInTheDocument(),
    )
  })

  it('shows the EarningsCard error state when /earnings returns 500', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/stocks/005930/earnings', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )
    renderStockAt('/stocks/005930')
    await waitFor(
      () =>
        expect(
          screen.getByTestId('stock-detail-earnings-error'),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    )
  })

  // -------- v0.8 Phase D — FavoriteButton (star toggle) --------
  it('renders FavoriteButton inactive when symbol is not in the default watchlist', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({
          watchlists: [
            {
              id: 1,
              name: '관심종목',
              is_default: true,
              item_count: 0,
              created_at: '2026-05-06T00:00:00',
              updated_at: '2026-05-06T00:00:00',
            },
          ],
        }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          id: 1,
          name: '관심종목',
          is_default: true,
          item_count: 0,
          created_at: '2026-05-06T00:00:00',
          updated_at: '2026-05-06T00:00:00',
          items: [],
        }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )
    const btn = screen.getByTestId('favorite-toggle')
    expect(btn).toHaveAttribute('data-active', 'false')
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    expect(btn).toHaveAttribute('aria-label', '관심종목에 추가')
  })

  it('renders FavoriteButton active when symbol is in the default watchlist', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({
          watchlists: [
            {
              id: 1,
              name: '관심종목',
              is_default: true,
              item_count: 1,
              created_at: '2026-05-06T00:00:00',
              updated_at: '2026-05-06T00:00:00',
            },
          ],
        }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          id: 1,
          name: '관심종목',
          is_default: true,
          item_count: 1,
          created_at: '2026-05-06T00:00:00',
          updated_at: '2026-05-06T00:00:00',
          items: [
            { id: 1, symbol: '005930', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() => {
      const btn = screen.getByTestId('favorite-toggle')
      expect(btn).toHaveAttribute('data-active', 'true')
    })
    const btn = screen.getByTestId('favorite-toggle')
    expect(btn).toHaveAttribute('aria-pressed', 'true')
    expect(btn).toHaveAttribute('aria-label', '관심종목에서 제거')
  })

  it('calls add mutation when clicking inactive FavoriteButton', async () => {
    let addCalled = false
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({
          watchlists: [
            { id: 1, name: '관심종목', is_default: true, item_count: 0, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          id: 1, name: '관심종목', is_default: true, item_count: 0,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
          items: [],
        }),
      ),
      http.post('*/api/watchlists/1/items', () => {
        addCalled = true
        return HttpResponse.json({
          id: 1, symbol: '005930', memo: null,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
        })
      }),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('favorite-toggle'))

    await waitFor(() => expect(addCalled).toBe(true))
  })

  it('calls remove mutation when clicking active FavoriteButton', async () => {
    let removeCalled = false
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({
          watchlists: [
            { id: 1, name: '관심종목', is_default: true, item_count: 1, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          id: 1, name: '관심종목', is_default: true, item_count: 1,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
          items: [{ id: 1, symbol: '005930', memo: null, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' }],
        }),
      ),
      http.delete('*/api/watchlists/1/items/005930', () => {
        removeCalled = true
        return HttpResponse.json({ status: 'removed' })
      }),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('favorite-toggle'))

    await waitFor(() => expect(removeCalled).toBe(true))
  })

  it('auto-creates watchlist and adds item when no watchlist exists (first-time click)', async () => {
    let createCalled = false
    let addCalled = false
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({ watchlists: [] }),
      ),
      http.post('*/api/watchlists', () => {
        createCalled = true
        return HttpResponse.json({
          id: 1, name: '관심종목', is_default: true, item_count: 0,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
        })
      }),
      http.post('*/api/watchlists/1/items', () => {
        addCalled = true
        return HttpResponse.json({
          id: 1, symbol: '005930', memo: null,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
        })
      }),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('favorite-toggle'))

    await waitFor(() => expect(createCalled).toBe(true))
    await waitFor(() => expect(addCalled).toBe(true))
  })

  it('shows favorite error on 500 when toggling', async () => {
    server.use(
      http.get('*/api/stocks/005930', () => HttpResponse.json(HAPPY)),
      http.get('*/api/watchlists', () =>
        HttpResponse.json({
          watchlists: [
            { id: 1, name: '관심종목', is_default: true, item_count: 0, created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00' },
          ],
        }),
      ),
      http.get('*/api/watchlists/1', () =>
        HttpResponse.json({
          id: 1, name: '관심종목', is_default: true, item_count: 0,
          created_at: '2026-05-06T00:00:00', updated_at: '2026-05-06T00:00:00',
          items: [],
        }),
      ),
      http.post('*/api/watchlists/1/items', () =>
        HttpResponse.json({ detail: 'server error' }, { status: 500 }),
      ),
    )

    renderStockAt('/stocks/005930')

    await waitFor(() =>
      expect(screen.getByTestId('favorite-toggle')).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByTestId('favorite-toggle'))

    await waitFor(() =>
      expect(screen.getByTestId('favorite-error')).toBeInTheDocument(),
    )
  })

  // -------- v0.6 Phase D — earnings_evidence in recent holding checks --------
  it('renders earnings_evidence cell on recent holding checks (whitelist only)', async () => {
    const happyWithEarningsEvidence = {
      ...HAPPY,
      recent_holding_checks: [
        {
          ...HAPPY.recent_holding_checks[0],
          earnings_evidence: {
            latest_event_date: '2026-05-01',
            fiscal_year: 2026,
            fiscal_quarter: 1,
            event_type: 'REPORT',
            surprise_type: 'BEAT',
            surprise_pct: '10.0000',
            operating_income_actual: '110.0000',
            operating_income_consensus: '100.0000',
          },
        },
      ],
    }
    server.use(
      http.get('*/api/stocks/005930', () =>
        HttpResponse.json(happyWithEarningsEvidence),
      ),
    )
    renderStockAt('/stocks/005930')
    await waitFor(() =>
      expect(screen.getByTestId('stock-detail-check-21')).toBeInTheDocument(),
    )
    const cell = screen.getByTestId('stock-detail-check-earnings-21')
    expect(cell).toHaveTextContent('BEAT')
    expect(cell).toHaveTextContent('10.0000')
  })
})
