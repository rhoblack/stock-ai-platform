import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useHoldingChecksForSymbol } from '@/hooks/useHoldingChecksForSymbol'
import { MetricCard } from '@/components/common/MetricCard'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { TrendLineChart } from '@/components/common/TrendLineChart'
import { ReturnRate } from '@/components/common/ReturnRate'
import { DecisionPill } from '@/components/common/DecisionPill'
import { RiskBadge } from '@/components/common/RiskBadge'
import type { HoldingCheck } from '@/api/types'

interface TrendPoint {
  check_label: string
  total_score: number | null
  return_rate: number | null
}

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function buildTrend(items: HoldingCheck[]): TrendPoint[] {
  // Backend returns latest-first; reverse to chronological order for chart.
  return [...items]
    .reverse()
    .map(item => ({
      check_label: `${item.check_date}·${item.check_type === 'POST_MARKET' ? 'POST' : 'PRE'}`,
      total_score: toNumber(item.total_score),
      return_rate: toNumber(item.return_rate),
    }))
}

interface HoldingTrendPanelProps {
  symbol: string | null
}

export function HoldingTrendPanel({ symbol }: HoldingTrendPanelProps) {
  const query = useHoldingChecksForSymbol(symbol, { limit: 30 })
  const trend = useMemo(() => buildTrend(query.data?.items ?? []), [query.data])

  if (!symbol) {
    return (
      <aside
        data-testid="holding-panel-empty"
        className="flex h-full items-center justify-center rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        보유 종목 행을 선택하면 추세가 표시됩니다.
      </aside>
    )
  }

  if (query.isLoading) {
    return (
      <aside className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        {symbol} 점검 이력 로딩 중…
      </aside>
    )
  }

  if (query.isError) {
    return (
      <aside
        data-testid="holding-panel-error"
        className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        {symbol} 점검 이력 조회에 실패했습니다.
      </aside>
    )
  }

  const { items, summary } = query.data!

  return (
    <aside
      data-testid="holding-panel"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            선택 종목
          </span>
          <h3 className="font-mono text-lg font-semibold">{symbol}</h3>
        </div>
        <Link
          to={`/stocks/${symbol}`}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          종목 상세 →
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="latest total_score"
          value={summary.latest_total_score ?? '—'}
          hint={`prev ${summary.previous_total_score ?? '—'}`}
          testid="holding-metric-latest-score"
        />
        <MetricCard
          label="score 변화 Δ"
          value={
            <ReturnRate
              value={summary.total_score_change}
              precision={2}
              withSign
              unit=""
            />
          }
          tone={
            summary.total_score_change && Number(summary.total_score_change) < 0
              ? 'negative'
              : summary.total_score_change && Number(summary.total_score_change) > 0
                ? 'positive'
                : 'neutral'
          }
          testid="holding-metric-score-change"
        />
        <MetricCard
          label="latest return"
          value={<ReturnRate value={summary.latest_return_rate} />}
          hint={
            <>
              best <ReturnRate value={summary.best_return_rate} className="ml-1" /> /
              worst <ReturnRate value={summary.worst_return_rate} className="ml-1" />
            </>
          }
          testid="holding-metric-latest-return"
        />
        <MetricCard
          label="alert / high_risk"
          value={`${summary.alert_count} / ${summary.high_risk_count}`}
          hint={`총 점검 ${summary.total_check_count}건`}
          tone={summary.high_risk_count > 0 ? 'warning' : 'neutral'}
          testid="holding-metric-alert"
        />
      </div>

      <KeyValueGrid
        testid="holding-meta-grid"
        rows={[
          {
            label: 'latest_check_date',
            value: summary.latest_check_date ?? '—',
          },
          {
            label: 'latest_decision',
            value: <DecisionPill decision={summary.latest_decision} />,
          },
          {
            label: 'latest_risk_level',
            value: <RiskBadge level={summary.latest_risk_level} />,
          },
          {
            label: 'total_check_count',
            value: summary.total_check_count,
          },
        ]}
      />

      <div className="rounded-md border border-border bg-card p-3">
        <TrendLineChart
          data={trend}
          xKey="check_label"
          yKey="total_score"
          label="total_score 추세 (점검 시점 asc)"
          testid="holding-trend-score"
          height={200}
        />
      </div>

      <div className="rounded-md border border-border bg-card p-3">
        <TrendLineChart
          data={trend}
          xKey="check_label"
          yKey="return_rate"
          label="return_rate 추세 (%)"
          unit="%"
          testid="holding-trend-return"
          height={200}
        />
      </div>

      <details className="rounded-md border border-border bg-card p-3 text-xs">
        <summary className="cursor-pointer text-muted-foreground">
          최근 점검 행 ({items.length})
        </summary>
        <table
          data-testid="holding-recent-checks"
          className="mt-2 w-full text-left text-xs"
        >
          <thead>
            <tr className="text-muted-foreground">
              <th className="px-1 py-1 font-medium">date</th>
              <th className="px-1 py-1 font-medium">type</th>
              <th className="px-1 py-1 font-medium">decision</th>
              <th className="px-1 py-1 font-medium">risk</th>
              <th className="px-1 py-1 font-medium">return</th>
              <th className="px-1 py-1 font-medium">total_score</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} className="border-t border-border">
                <td className="px-1 py-1 font-mono">{item.check_date}</td>
                <td className="px-1 py-1 text-muted-foreground">
                  {item.check_type === 'POST_MARKET' ? 'POST' : 'PRE'}
                </td>
                <td className="px-1 py-1">
                  <DecisionPill decision={item.decision} />
                </td>
                <td className="px-1 py-1">
                  <RiskBadge level={item.risk_level} />
                </td>
                <td className="px-1 py-1">
                  <ReturnRate value={item.return_rate} />
                </td>
                <td className="px-1 py-1 font-mono tabular-nums">
                  {item.total_score ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </aside>
  )
}
