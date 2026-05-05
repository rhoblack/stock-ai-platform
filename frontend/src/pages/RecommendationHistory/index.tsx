import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useRecommendationHistory } from '@/hooks/useRecommendationHistory'
import { DataStatusBadge } from '@/components/common/DataStatusBadge'
import { ReturnRate } from '@/components/common/ReturnRate'
import { TrendLineChart } from '@/components/common/TrendLineChart'
import { MetricCard } from '@/components/common/MetricCard'
import type { RecommendationHistoryItem } from '@/api/types'

interface TrendPoint {
  run_date: string
  success_rate: number | null
  avg_close_5d: number | null
}

function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function buildTrend(items: RecommendationHistoryItem[]): TrendPoint[] {
  // history 응답은 run_date desc 정렬 — 차트 X축은 시간 순 (asc) 으로 뒤집어 표시
  return [...items]
    .reverse()
    .map(item => ({
      run_date: item.run.run_date,
      success_rate: toNumber(item.success_rate),
      avg_close_5d: toNumber(item.avg_close_return_5d),
    }))
}

function summary(items: RecommendationHistoryItem[]) {
  if (items.length === 0) return null
  const successRates = items
    .map(i => toNumber(i.success_rate))
    .filter((v): v is number => v !== null)
  const avg5d = items
    .map(i => toNumber(i.avg_close_return_5d))
    .filter((v): v is number => v !== null)
  const avg = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null)
  return {
    runs: items.length,
    avgSuccess: avg(successRates),
    avgClose5d: avg(avg5d),
    totalRecommendations: items.reduce((acc, i) => acc + i.recommendation_count, 0),
  }
}

export function RecommendationHistoryPage() {
  const history = useRecommendationHistory({ limit: 20 })
  const items = history.data?.items ?? []
  const trend = useMemo(() => buildTrend(items), [items])
  const stats = useMemo(() => summary(items), [items])

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">추천 이력</h2>
          <p className="text-sm text-muted-foreground">
            최근 20건. 5분마다 자동 새로고침.
            {history.dataUpdatedAt > 0 && (
              <>
                {' '}
                <span className="font-mono text-xs">
                  (last fetch{' '}
                  {new Date(history.dataUpdatedAt).toLocaleTimeString('ko-KR')})
                </span>
              </>
            )}
          </p>
        </div>
        <Link
          to="/recommendations"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          최신 run →
        </Link>
      </header>

      {history.isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          이력 로딩 중…
        </div>
      )}

      {history.isError && (
        <div
          data-testid="history-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          추천 이력을 불러오지 못했습니다.
        </div>
      )}

      {history.isSuccess && (
        <>
          {stats ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricCard
                label="run 수"
                value={stats.runs}
                hint="최근 20건"
                testid="history-metric-runs"
              />
              <MetricCard
                label="총 추천 수"
                value={stats.totalRecommendations}
                testid="history-metric-total"
              />
              <MetricCard
                label="avg success_rate"
                value={
                  stats.avgSuccess === null ? '—' : `${stats.avgSuccess.toFixed(2)}%`
                }
                hint="5d 기준 SUCCESS/FAILED 가 finalized 된 run 만"
                tone={stats.avgSuccess && stats.avgSuccess >= 50 ? 'positive' : 'neutral'}
                testid="history-metric-success"
              />
              <MetricCard
                label="avg close_return 5d"
                value={
                  <ReturnRate value={stats.avgClose5d} precision={2} withSign={true} />
                }
                testid="history-metric-avg-5d"
              />
            </div>
          ) : null}

          <div className="rounded-lg border border-border bg-card p-4">
            <TrendLineChart
              data={trend}
              xKey="run_date"
              yKey="success_rate"
              label="success_rate (%) 추세 (run_date asc)"
              unit="%"
              testid="history-trend-success"
            />
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <TrendLineChart
              data={trend}
              xKey="run_date"
              yKey="avg_close_5d"
              label="avg_close_return_5d (%) 추세"
              unit="%"
              testid="history-trend-close5d"
              height={200}
            />
          </div>

          <HistoryTable items={items} />
        </>
      )}
    </section>
  )
}

function HistoryTable({ items }: { items: RecommendationHistoryItem[] }) {
  if (items.length === 0) {
    return (
      <div
        data-testid="history-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        조회된 run 이 없습니다.
      </div>
    )
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm" data-testid="history-table">
        <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">run_date</th>
            <th className="px-3 py-2 font-medium">status</th>
            <th className="px-3 py-2 font-medium">recs</th>
            <th className="px-3 py-2 font-medium">success_rate</th>
            <th className="px-3 py-2 font-medium">avg close 1d</th>
            <th className="px-3 py-2 font-medium">avg close 3d</th>
            <th className="px-3 py-2 font-medium">avg close 5d</th>
            <th className="px-3 py-2 font-medium">avg close 20d</th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.run.run_id} className="border-t border-border">
              <td className="px-3 py-2">
                <Link
                  to={`/recommendations/runs/${item.run.run_id}`}
                  data-testid={`history-row-${item.run.run_id}`}
                  className="font-mono text-sm hover:underline"
                >
                  {item.run.run_date}
                </Link>
              </td>
              <td className="px-3 py-2">
                <DataStatusBadge status={item.run.status} variant="job" />
              </td>
              <td className="px-3 py-2 font-mono text-sm tabular-nums">
                {item.recommendation_count}
              </td>
              <td className="px-3 py-2 font-mono text-sm tabular-nums">
                {item.success_rate ? `${Number(item.success_rate).toFixed(1)}%` : '—'}
              </td>
              <td className="px-3 py-2">
                <ReturnRate value={item.avg_close_return_1d} />
              </td>
              <td className="px-3 py-2">
                <ReturnRate value={item.avg_close_return_3d} />
              </td>
              <td className="px-3 py-2">
                <ReturnRate value={item.avg_close_return_5d} />
              </td>
              <td className="px-3 py-2">
                <ReturnRate value={item.avg_close_return_20d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
