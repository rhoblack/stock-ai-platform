import { cn } from '@/lib/utils'
import {
  useValidationReport,
  useValidationByStrategy,
  useValidationByRegime,
  useValidationBySector,
} from '@/hooks/useValidationReport'
import type {
  ValidationStrategySummary,
  ValidationRegimeSummary,
  ValidationSectorSummary,
  ScoreDeltaSummary,
} from '@/api/types'

function fmtNum(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', { maximumFractionDigits: 4 })
}

function fmtPct(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return `${(num * 100).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}%`
}

const DATA_SOURCE_TONE: Record<string, string> = {
  PROVIDER:
    'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-900/40',
  FAKE: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-900/40',
  CSV: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-200 dark:border-purple-900/40',
  MANUAL:
    'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-900/30 dark:text-gray-200 dark:border-gray-900/40',
  UNKNOWN:
    'bg-muted text-muted-foreground border-border',
}

export function ValidationPage() {
  const report = useValidationReport()
  const strategies = useValidationByStrategy()
  const regimes = useValidationByRegime()
  const sectors = useValidationBySector()

  return (
    <section className="flex flex-col gap-4" data-testid="validation-page">
      <header>
        <h2 className="text-2xl font-semibold">검증 리포트</h2>
        <p className="text-sm text-muted-foreground">
          백테스트 run/result 집계 기반 read-only 검증 대시보드. 실 주문·Broker 호출 0건.
        </p>
      </header>

      <OverallReportCard
        loading={report.isLoading}
        error={report.isError}
        data={report.data}
      />

      {report.data && (
        <ScoreDeltaCard delta={report.data.score_delta} />
      )}

      <StrategyTableSection
        loading={strategies.isLoading}
        error={strategies.isError}
        items={strategies.data?.items ?? []}
      />

      <RegimeTableSection
        loading={regimes.isLoading}
        error={regimes.isError}
        items={regimes.data?.items ?? []}
      />

      <SectorTableSection
        loading={sectors.isLoading}
        error={sectors.isError}
        items={sectors.data?.items ?? []}
      />
    </section>
  )
}

// -----------------------------------------------------------------------
// Overall report card
// -----------------------------------------------------------------------

function OverallReportCard({
  loading,
  error,
  data,
}: {
  loading: boolean
  error: boolean
  data: { run_count: number; signal_count: number; buy_count: number; win_rate_5d: string | null; avg_return_5d: string | null } | undefined
}) {
  return (
    <section
      data-testid="validation-report-card"
      className="rounded-lg border border-border bg-card p-5"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        전체 요약
      </h3>
      {loading && (
        <p data-testid="validation-report-loading" className="text-sm text-muted-foreground">
          리포트 로딩 중…
        </p>
      )}
      {error && (
        <p data-testid="validation-report-error" className="text-sm text-red-700 dark:text-red-300">
          리포트를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && !data && (
        <p data-testid="validation-report-empty" className="text-sm text-muted-foreground">
          집계된 백테스트 데이터가 없습니다.
        </p>
      )}
      {!loading && !error && data && (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCell label="run 수" value={String(data.run_count)} />
          <StatCell label="신호 수" value={String(data.signal_count)} />
          <StatCell label="BUY 수" value={String(data.buy_count)} />
          <StatCell label="승률 5d" value={fmtPct(data.win_rate_5d)} />
          <StatCell label="평균 수익 5d" value={fmtNum(data.avg_return_5d)} />
        </dl>
      )}
    </section>
  )
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="font-mono text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

// -----------------------------------------------------------------------
// Score delta card
// -----------------------------------------------------------------------

function ScoreDeltaCard({ delta }: { delta: ScoreDeltaSummary }) {
  return (
    <section
      data-testid="validation-score-delta-card"
      className="rounded-lg border border-border bg-card p-5"
    >
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Score Delta 요약
      </h3>
      <div className="flex flex-wrap gap-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            scored 건수
          </span>
          <span className="font-mono text-lg font-semibold tabular-nums">
            {delta.total_scored}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            policy 활성
          </span>
          <span className="font-mono text-lg font-semibold tabular-nums">
            {delta.policy_enabled_count}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            avg delta
          </span>
          <span className="font-mono text-lg font-semibold tabular-nums">
            {fmtNum(delta.avg_delta)}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            +/0/−
          </span>
          <span className="font-mono text-lg font-semibold tabular-nums text-emerald-700 dark:text-emerald-300">
            {delta.positive_delta_count}
          </span>
          <span className="font-mono text-sm tabular-nums text-muted-foreground">
            / {delta.neutral_delta_count} /{' '}
            <span className="text-red-600 dark:text-red-400">
              {delta.negative_delta_count}
            </span>
          </span>
        </div>
      </div>

      {Object.keys(delta.data_source_counts).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Object.entries(delta.data_source_counts).map(([source, count]) => {
            const tone = DATA_SOURCE_TONE[source] ?? DATA_SOURCE_TONE.UNKNOWN
            return (
              <span
                key={source}
                data-testid={`validation-data-source-${source}`}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
                  tone,
                )}
              >
                {source}
                <span className="font-mono">{count}</span>
              </span>
            )
          })}
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Strategy table
// -----------------------------------------------------------------------

function StrategyTableSection({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: ValidationStrategySummary[]
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        전략별 성과
      </h3>
      {loading && (
        <p className="text-sm text-muted-foreground">전략별 데이터 로딩 중…</p>
      )}
      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">
          전략별 데이터를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="validation-strategy-empty" className="text-sm text-muted-foreground">
          전략 집계 데이터가 없습니다.
        </p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs" data-testid="validation-strategy-table">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">strategy</th>
                <th className="px-2 py-1 font-medium">run</th>
                <th className="px-2 py-1 font-medium">signal</th>
                <th className="px-2 py-1 font-medium">buy</th>
                <th className="px-2 py-1 font-medium">win_rate_5d</th>
                <th className="px-2 py-1 font-medium">avg_return_5d</th>
                <th className="px-2 py-1 font-medium">cost_adj_5d</th>
                <th className="px-2 py-1 font-medium">max_dd</th>
              </tr>
            </thead>
            <tbody>
              {items.map(row => (
                <tr
                  key={row.strategy_name}
                  data-testid={`validation-strategy-row-${row.strategy_name}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-semibold">{row.strategy_name}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.run_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.signal_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.buy_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtPct(row.win_rate_5d)}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtNum(row.avg_return_5d)}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmtNum(row.cost_adjusted_avg_return_5d)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtNum(row.max_drawdown)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Regime table
// -----------------------------------------------------------------------

function RegimeTableSection({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: ValidationRegimeSummary[]
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        시장 국면별 BUY 성과
      </h3>
      {loading && (
        <p className="text-sm text-muted-foreground">국면별 데이터 로딩 중…</p>
      )}
      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">
          국면별 데이터를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="validation-regime-empty" className="text-sm text-muted-foreground">
          국면별 집계 데이터가 없습니다.
        </p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">regime</th>
                <th className="px-2 py-1 font-medium">buy</th>
                <th className="px-2 py-1 font-medium">win_rate_5d</th>
                <th className="px-2 py-1 font-medium">avg_return_5d</th>
              </tr>
            </thead>
            <tbody>
              {items.map(row => (
                <tr
                  key={row.regime}
                  data-testid={`validation-regime-row-${row.regime}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-mono">{row.regime}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.buy_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtPct(row.win_rate_5d)}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtNum(row.avg_return_5d)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Sector table
// -----------------------------------------------------------------------

function SectorTableSection({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: ValidationSectorSummary[]
}) {
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        섹터별 BUY 성과
      </h3>
      {loading && (
        <p className="text-sm text-muted-foreground">섹터별 데이터 로딩 중…</p>
      )}
      {error && (
        <p className="text-sm text-red-700 dark:text-red-300">
          섹터별 데이터를 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p data-testid="validation-sector-empty" className="text-sm text-muted-foreground">
          섹터별 집계 데이터가 없습니다.
        </p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">sector</th>
                <th className="px-2 py-1 font-medium">buy</th>
                <th className="px-2 py-1 font-medium">win_rate_5d</th>
                <th className="px-2 py-1 font-medium">avg_return_5d</th>
              </tr>
            </thead>
            <tbody>
              {items.map(row => (
                <tr
                  key={row.sector}
                  data-testid={`validation-sector-row-${row.sector}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-mono">{row.sector}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.buy_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtPct(row.win_rate_5d)}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">{fmtNum(row.avg_return_5d)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
