import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from './renderWithProviders'
import { server } from './mswServer'
import { ThemesPage } from '@/pages/Themes'
import { ThemeDetailPage } from '@/pages/ThemeDetail'

const RANKING_PAYLOAD = {
  items: [
    {
      theme_id: 41,
      theme_name: 'HBM',
      theme_category: 'SEMICONDUCTOR',
      direction: 'POSITIVE',
      time_horizon: 'MID',
      summary: 'AI 서버 메모리 수요',
      confidence: '0.800',
      source_report_id: 12,
      mapping_count: 2,
      signal_event_count: 1,
    },
    {
      theme_id: 42,
      theme_name: '거래정지',
      theme_category: 'RISK',
      direction: 'NEGATIVE',
      time_horizon: 'SHORT',
      summary: '거래정지 위험',
      confidence: null,
      source_report_id: 12,
      mapping_count: 0,
      signal_event_count: 1,
    },
  ],
  category: null,
  direction: null,
  limit: 50,
}

const HBM_DETAIL = {
  theme: {
    theme_id: 41,
    theme_name: 'HBM',
    theme_category: 'SEMICONDUCTOR',
    direction: 'POSITIVE',
    time_horizon: 'MID',
    summary: 'AI 서버 메모리 수요',
    confidence: '0.800',
    source_report_id: 12,
    mapping_count: 2,
    signal_event_count: 1,
  },
  stock_mappings: [
    {
      mapping_id: 51,
      theme_id: 41,
      symbol: '005930',
      company_name: '삼성전자',
      market: 'KOSPI',
      relation_type: 'SUPPLIER',
      impact_direction: 'POSITIVE',
      impact_strength: '0.800',
      impact_path: 'DEMAND_INCREASE',
      benefit_type: 'PRICE_POWER',
      time_lag: 'MID',
      reason: 'HBM 공급사',
    },
    {
      mapping_id: 52,
      theme_id: 41,
      symbol: '000660',
      company_name: 'SK하이닉스',
      market: 'KOSPI',
      relation_type: null,
      impact_direction: 'POSITIVE',
      impact_strength: '0.900',
      impact_path: 'MARKET_SHARE_GAIN',
      benefit_type: null,
      time_lag: null,
      reason: null,
    },
  ],
  signal_events: [
    {
      id: 71,
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
}

describe('ThemesPage', () => {
  it('renders the ranking table with mapping/signal counts (happy)', async () => {
    server.use(
      http.get('*/api/themes/ranking', () => HttpResponse.json(RANKING_PAYLOAD)),
    )
    renderWithProviders(<ThemesPage />, { initialEntries: ['/themes'] })

    await waitFor(() =>
      expect(screen.getByTestId('theme-row-41')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('theme-row-42')).toBeInTheDocument()
    expect(screen.getByTestId('theme-mapping-count-41')).toHaveTextContent('2')
    expect(screen.getByTestId('theme-signal-count-41')).toHaveTextContent('1')
    expect(screen.getByTestId('theme-direction-42')).toHaveTextContent('NEGATIVE')
    expect(screen.getByText('2건 표시')).toBeInTheDocument()
  })

  it('filters by direction via the radio group', async () => {
    server.use(
      http.get('*/api/themes/ranking', ({ request }) => {
        const url = new URL(request.url)
        const dir = url.searchParams.get('direction')
        if (dir === 'NEGATIVE') {
          return HttpResponse.json({
            ...RANKING_PAYLOAD,
            items: [RANKING_PAYLOAD.items[1]],
            direction: 'NEGATIVE',
          })
        }
        return HttpResponse.json(RANKING_PAYLOAD)
      }),
    )
    renderWithProviders(<ThemesPage />, { initialEntries: ['/themes'] })
    await waitFor(() =>
      expect(screen.getByTestId('theme-row-41')).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId('theme-filter-NEGATIVE'))
    await waitFor(() =>
      expect(screen.queryByTestId('theme-row-41')).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId('theme-row-42')).toBeInTheDocument()
  })

  it('filters by search input (theme_name / category)', async () => {
    server.use(
      http.get('*/api/themes/ranking', () => HttpResponse.json(RANKING_PAYLOAD)),
    )
    renderWithProviders(<ThemesPage />, { initialEntries: ['/themes'] })
    await waitFor(() =>
      expect(screen.getByTestId('theme-row-41')).toBeInTheDocument(),
    )
    await userEvent.type(screen.getByTestId('theme-search'), 'RISK')
    await waitFor(() =>
      expect(screen.queryByTestId('theme-row-41')).not.toBeInTheDocument(),
    )
    expect(screen.getByTestId('theme-row-42')).toBeInTheDocument()
  })

  it('shows empty state when API returns []', async () => {
    server.use(
      http.get('*/api/themes/ranking', () =>
        HttpResponse.json({
          items: [],
          category: null,
          direction: null,
          limit: 50,
        }),
      ),
    )
    renderWithProviders(<ThemesPage />, { initialEntries: ['/themes'] })
    await waitFor(() =>
      expect(screen.getByTestId('themes-empty')).toBeInTheDocument(),
    )
  })

  it('shows error state on 500', async () => {
    server.use(
      http.get('*/api/themes/ranking', () =>
        HttpResponse.json({ detail: 'simulated outage' }, { status: 500 }),
      ),
    )
    renderWithProviders(<ThemesPage />, { initialEntries: ['/themes'] })
    await waitFor(() =>
      expect(screen.getByTestId('themes-error')).toBeInTheDocument(),
    )
  })
})

describe('ThemeDetailPage', () => {
  it('renders theme + mappings + signal events (happy)', async () => {
    server.use(
      http.get('*/api/themes/41', () => HttpResponse.json(HBM_DETAIL)),
    )
    renderWithProviders(
      <Routes>
        <Route path="/themes/:themeId" element={<ThemeDetailPage />} />
      </Routes>,
      { initialEntries: ['/themes/41'] },
    )
    await waitFor(() =>
      expect(screen.getByTestId('theme-detail')).toBeInTheDocument(),
    )
    expect(screen.getByTestId('theme-mapping-51')).toHaveTextContent('삼성전자')
    expect(screen.getByTestId('theme-mapping-52')).toHaveTextContent('SK하이닉스')
    expect(screen.getByTestId('theme-detail-signal-71')).toHaveTextContent(
      'SUPPLY_SHORTAGE',
    )
    // impact_path badge surface
    expect(screen.getByText('DEMAND_INCREASE')).toBeInTheDocument()
  })

  it('shows error state on 404', async () => {
    server.use(
      http.get('*/api/themes/9999', () =>
        HttpResponse.json({ detail: 'not found' }, { status: 404 }),
      ),
    )
    renderWithProviders(
      <Routes>
        <Route path="/themes/:themeId" element={<ThemeDetailPage />} />
      </Routes>,
      { initialEntries: ['/themes/9999'] },
    )
    await waitFor(() =>
      expect(screen.getByTestId('theme-detail-error')).toBeInTheDocument(),
    )
  })

  it('shows empty signals state when theme has no signal_events', async () => {
    server.use(
      http.get('*/api/themes/41', () =>
        HttpResponse.json({ ...HBM_DETAIL, signal_events: [] }),
      ),
    )
    renderWithProviders(
      <Routes>
        <Route path="/themes/:themeId" element={<ThemeDetailPage />} />
      </Routes>,
      { initialEntries: ['/themes/41'] },
    )
    await waitFor(() =>
      expect(screen.getByTestId('theme-detail-signals-empty')).toBeInTheDocument(),
    )
  })
})
