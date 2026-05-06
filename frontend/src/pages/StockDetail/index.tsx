import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useStockDetail } from '@/hooks/useStockDetail'
import { useStockPriceSeries } from '@/hooks/useStockPriceSeries'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { GradePill } from '@/components/common/GradePill'
import { RiskBadge } from '@/components/common/RiskBadge'
import { DecisionPill } from '@/components/common/DecisionPill'
import { ReturnRate } from '@/components/common/ReturnRate'
import { cn } from '@/lib/utils'
import { PriceChart } from './PriceChart'
import { AnalystReportsCard } from './AnalystReportsCard'
import { FundamentalsCard } from './FundamentalsCard'
import { EarningsCard } from './EarningsCard'
import type {
  HoldingCheck,
  RecommendationItem,
  RecommendationResult,
  StockDetailResponse,
} from '@/api/types'

const PRICE_CHART_DAYS_OPTIONS: ReadonlyArray<30 | 60 | 120 | 250> = [
  30, 60, 120, 250,
]
type PriceChartDays = (typeof PRICE_CHART_DAYS_OPTIONS)[number]

const DAYS_AFTER: Array<1 | 3 | 5 | 20> = [1, 3, 5, 20]

function findResult(
  results: RecommendationResult[] | undefined,
  daysAfter: number,
): RecommendationResult | undefined {
  return results?.find(r => r.days_after === daysAfter)
}

export function StockDetailPage() {
  const navigate = useNavigate()
  const { symbol } = useParams<{ symbol: string }>()
  const detail = useStockDetail(symbol)

  if (!symbol) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">종목 상세</h2>
        <div className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground">
          종목 코드가 지정되지 않았습니다. 사이드바의 다른 화면에서 종목을 클릭하면
          이 페이지로 이동합니다 (예: <code>/stocks/005930</code>).
        </div>
      </section>
    )
  }

  if (detail.isLoading) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">종목 상세 — {symbol}</h2>
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          {symbol} 상세 로딩 중…
        </div>
      </section>
    )
  }

  if (detail.isError) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">종목 상세 — {symbol}</h2>
        <div
          data-testid="stock-detail-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          {symbol} 종목을 찾을 수 없거나 응답에 실패했습니다.
        </div>
        <button
          type="button"
          className="self-start rounded-md border border-border bg-card px-3 py-1.5 text-xs hover:bg-accent"
          onClick={() => navigate('/today')}
        >
          오늘의 리포트로 돌아가기
        </button>
      </section>
    )
  }

  return <StockDetailContent data={detail.data!} />
}

function StockDetailContent({ data }: { data: StockDetailResponse }) {
  const {
    stock,
    latest_price,
    latest_indicator,
    recent_recommendations,
    recent_holding_checks,
    analyst_reports,
  } = data

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">
            {stock.name}{' '}
            <span className="text-muted-foreground">({stock.symbol})</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            {stock.market} · {stock.sector ?? '섹터 미지정'} ·{' '}
            {stock.is_active ? 'active' : 'inactive'}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PriceCard latest_price={latest_price} />
        <IndicatorCard indicator={latest_indicator} />
      </div>

      <PriceChartCard symbol={stock.symbol} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FundamentalsCard symbol={stock.symbol} />
        <EarningsCard symbol={stock.symbol} />
      </div>

      <AnalystReportsCard data={analyst_reports} />

      <RecentRecommendationsCard items={recent_recommendations} />
      <RecentHoldingChecksCard items={recent_holding_checks} />
    </section>
  )
}

function PriceChartCard({ symbol }: { symbol: string }) {
  const [days, setDays] = useState<PriceChartDays>(120)
  const series = useStockPriceSeries(symbol, { days })

  return (
    <section
      data-testid="stock-detail-price-chart"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col">
          <h3 className="text-sm font-semibold">일봉 close 추세</h3>
          <p className="text-xs text-muted-foreground">
            기간: {days}일 · count{' '}
            <span className="font-mono">{series.data?.count ?? '—'}</span>
          </p>
        </div>
        <div className="flex gap-1" role="tablist" aria-label="기간 선택">
          {PRICE_CHART_DAYS_OPTIONS.map(option => {
            const active = option === days
            return (
              <button
                key={option}
                type="button"
                role="tab"
                aria-selected={active}
                data-testid={`price-chart-days-${option}`}
                data-active={active}
                onClick={() => setDays(option)}
                className={cn(
                  'rounded-md border px-2 py-1 text-xs transition-colors',
                  active
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-muted-foreground hover:bg-accent',
                )}
              >
                {option}d
              </button>
            )
          })}
        </div>
      </header>

      {series.isLoading && (
        <div
          data-testid="price-chart-loading"
          className="rounded-md border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
        >
          가격 시계열 로딩 중…
        </div>
      )}
      {series.isError && (
        <div
          data-testid="price-chart-error"
          className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          가격 시계열을 불러오지 못했습니다.
        </div>
      )}
      {series.isSuccess && <PriceChart prices={series.data.prices} />}
    </section>
  )
}

function PriceCard({
  latest_price,
}: {
  latest_price: StockDetailResponse['latest_price']
}) {
  if (!latest_price) {
    return (
      <div
        data-testid="stock-detail-price-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        최신 가격 데이터가 없습니다.
      </div>
    )
  }
  return (
    <div data-testid="stock-detail-price" className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">최신 가격 ({latest_price.date})</h3>
      <KeyValueGrid
        columns={3}
        rows={[
          { label: 'open', value: latest_price.open ?? '—' },
          { label: 'high', value: latest_price.high ?? '—' },
          { label: 'low', value: latest_price.low ?? '—' },
          { label: 'close', value: latest_price.close ?? '—' },
          { label: 'volume', value: latest_price.volume.toLocaleString('ko-KR') },
          {
            label: 'trading_value',
            value: latest_price.trading_value ?? '—',
          },
        ]}
      />
    </div>
  )
}

function IndicatorCard({
  indicator,
}: {
  indicator: StockDetailResponse['latest_indicator']
}) {
  if (!indicator) {
    return (
      <div
        data-testid="stock-detail-indicator-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        최신 기술 지표가 없습니다.
      </div>
    )
  }
  return (
    <div data-testid="stock-detail-indicator" className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">최신 기술 지표 ({indicator.date})</h3>
      <KeyValueGrid
        columns={3}
        rows={[
          { label: 'MA5', value: indicator.ma5 ?? '—' },
          { label: 'MA20', value: indicator.ma20 ?? '—' },
          { label: 'MA60', value: indicator.ma60 ?? '—' },
          { label: 'MA120', value: indicator.ma120 ?? '—' },
          { label: 'RSI14', value: indicator.rsi14 ?? '—' },
          {
            label: 'MACD / signal',
            value: `${indicator.macd ?? '—'} / ${indicator.macd_signal ?? '—'}`,
          },
          {
            label: 'volume_ratio_20d',
            value: indicator.volume_ratio_20d ?? '—',
          },
          {
            label: 'breakout 20d/60d',
            value: `${indicator.breakout_20d ? '✓' : '—'} / ${indicator.breakout_60d ? '✓' : '—'}`,
          },
          {
            label: 'ma_alignment',
            value: indicator.ma_alignment ?? '—',
            hint: indicator.technical_score
              ? `tech_score ${indicator.technical_score}`
              : null,
          },
        ]}
      />
    </div>
  )
}

function RecentRecommendationsCard({ items }: { items: RecommendationItem[] }) {
  return (
    <section
      data-testid="stock-detail-recs"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">최근 추천 이력 ({items.length})</h3>
      </header>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">표시할 추천 이력이 없습니다.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">run_date</th>
                <th className="px-2 py-1 font-medium">rank</th>
                <th className="px-2 py-1 font-medium">grade</th>
                <th className="px-2 py-1 font-medium">total</th>
                <th className="px-2 py-1 font-medium">risk</th>
                {DAYS_AFTER.map(n => (
                  <th key={n} className="px-2 py-1 font-medium">
                    {n}d
                  </th>
                ))}
                <th className="px-2 py-1 font-medium">사유</th>
              </tr>
            </thead>
            <tbody>
              {items.map(rec => (
                <tr
                  key={`${rec.run_id}-${rec.recommendation_id}`}
                  data-testid={`stock-detail-rec-${rec.run_id}`}
                  className="border-t border-border align-top"
                >
                  <td className="px-2 py-1 font-mono">{rec.run_date ?? '—'}</td>
                  <td className="px-2 py-1 font-mono">{rec.rank}</td>
                  <td className="px-2 py-1">
                    <GradePill grade={rec.grade} />
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {rec.total_score ?? '—'}
                  </td>
                  <td className="px-2 py-1">
                    <RiskBadge level={rec.risk_level} flags={rec.risk_flags} />
                  </td>
                  {DAYS_AFTER.map(n => {
                    const result = findResult(rec.results, n)
                    return (
                      <td key={n} className="px-2 py-1">
                        <ReturnRate value={result?.close_return ?? null} />
                      </td>
                    )
                  })}
                  <td className="px-2 py-1 text-muted-foreground">
                    {rec.reason ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function summarizeEarningsEvidence(check: HoldingCheck): string {
  const e = check.earnings_evidence
  if (!e) return '—'
  if (e.reason === 'no_earnings_event') return '—'
  const parts: string[] = []
  if (e.surprise_type) parts.push(e.surprise_type)
  if (e.surprise_pct !== null && e.surprise_pct !== undefined)
    parts.push(`${e.surprise_pct}%`)
  if (e.latest_event_date) parts.push(e.latest_event_date)
  return parts.length > 0 ? parts.join(' · ') : '—'
}

function RecentHoldingChecksCard({ items }: { items: HoldingCheck[] }) {
  return (
    <section
      data-testid="stock-detail-checks"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">최근 보유 점검 ({items.length})</h3>
      </header>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">표시할 점검 이력이 없습니다.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">date</th>
                <th className="px-2 py-1 font-medium">type</th>
                <th className="px-2 py-1 font-medium">decision</th>
                <th className="px-2 py-1 font-medium">risk</th>
                <th className="px-2 py-1 font-medium">return</th>
                <th className="px-2 py-1 font-medium">total_score</th>
                <th className="px-2 py-1 font-medium">earnings evidence</th>
                <th className="px-2 py-1 font-medium">alert</th>
              </tr>
            </thead>
            <tbody>
              {items.map(check => (
                <tr
                  key={check.id}
                  data-testid={`stock-detail-check-${check.id}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-mono">{check.check_date}</td>
                  <td className="px-2 py-1 text-muted-foreground">
                    {check.check_type === 'POST_MARKET' ? 'POST' : 'PRE'}
                  </td>
                  <td className="px-2 py-1">
                    <DecisionPill decision={check.decision} />
                  </td>
                  <td className="px-2 py-1">
                    <RiskBadge level={check.risk_level} />
                  </td>
                  <td className="px-2 py-1">
                    <ReturnRate value={check.return_rate} />
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {check.total_score ?? '—'}
                  </td>
                  <td
                    data-testid={`stock-detail-check-earnings-${check.id}`}
                    className="px-2 py-1 text-muted-foreground"
                  >
                    {summarizeEarningsEvidence(check)}
                  </td>
                  <td className="px-2 py-1">
                    {check.alert ? (
                      <span className="text-red-600 dark:text-red-300">⚠</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
