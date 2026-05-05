import { Link, useParams } from 'react-router-dom'
import { useLatestRecommendationRun } from '@/hooks/useLatestRecommendationRun'
import { useRecommendationRunDetail } from '@/hooks/useRecommendationRunDetail'
import { DataStatusBadge } from '@/components/common/DataStatusBadge'
import { MetricCard } from '@/components/common/MetricCard'
import { RecommendationsTable } from './RecommendationsTable'
import type { RecommendationRunDetailResponse } from '@/api/types'

function summarize(payload: RecommendationRunDetailResponse) {
  const grades = payload.recommendations.reduce<Record<string, number>>((acc, rec) => {
    if (!rec.grade) return acc
    acc[rec.grade] = (acc[rec.grade] ?? 0) + 1
    return acc
  }, {})
  const order = ['S', 'A', 'B', 'C', 'D']
  const distribution = order
    .filter(g => grades[g] && grades[g] > 0)
    .map(g => `${g}:${grades[g]}`)
    .join(' · ')
  return distribution || '—'
}

export function RecommendationsPage() {
  const { runId } = useParams<{ runId: string }>()
  const numericRunId = runId ? Number(runId) : null
  const isHistoricalView = Number.isFinite(numericRunId) && numericRunId !== null

  const latest = useLatestRecommendationRun()
  const detail = useRecommendationRunDetail(isHistoricalView ? numericRunId : null)
  const query = isHistoricalView ? detail : latest

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">
            {isHistoricalView ? `추천 종목 — run #${numericRunId}` : '추천 종목 (최신)'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {isHistoricalView
              ? '추천 이력에서 선택한 run 의 상세.'
              : '최신 recommendation_run 의 TOP-N 관찰 후보. 5분마다 자동 새로고침.'}
            {query.dataUpdatedAt > 0 && (
              <>
                {' '}
                <span className="font-mono text-xs">
                  (last fetch{' '}
                  {new Date(query.dataUpdatedAt).toLocaleTimeString('ko-KR')})
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Link to="/recommendations/history" className="text-muted-foreground hover:text-foreground">
            추천 이력 →
          </Link>
        </div>
      </header>

      {query.isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          추천 데이터 로딩 중…
        </div>
      )}

      {query.isError && (
        <div
          data-testid="recs-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          추천 데이터를 불러오지 못했습니다.{' '}
          {!isHistoricalView ? '아직 recommendation_run 이 없을 수 있습니다 (404).' : ''}
        </div>
      )}

      {query.isSuccess && query.data && (
        <RecommendationsContent data={query.data} runDistribution={summarize(query.data)} />
      )}
    </section>
  )
}

function RecommendationsContent({
  data,
  runDistribution,
}: {
  data: RecommendationRunDetailResponse
  runDistribution: string
}) {
  const { run, recommendations } = data
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard
          label="run_date"
          value={run.run_date}
          hint={run.status}
          testid="rec-metric-run-date"
        />
        <MetricCard
          label="status"
          value={<DataStatusBadge status={run.status} variant="job" />}
          hint={run.telegram_sent ? 'telegram sent' : 'telegram not sent'}
          tone={run.status === 'SUCCESS' ? 'positive' : 'warning'}
          testid="rec-metric-status"
        />
        <MetricCard
          label="추천 수"
          value={recommendations.length}
          hint={`run_id #${run.run_id}`}
          testid="rec-metric-count"
        />
        <MetricCard
          label="등급 분포"
          value={runDistribution}
          testid="rec-metric-grade-dist"
        />
      </div>
      <RecommendationsTable rows={recommendations} />
    </div>
  )
}
