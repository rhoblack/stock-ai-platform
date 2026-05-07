import { useMemo, useState } from 'react'
import { useStrategies } from '@/hooks/useStrategies'
import { useBacktestRuns } from '@/hooks/useBacktestRuns'
import { useBacktestRunDetail } from '@/hooks/useBacktestRunDetail'
import { useBacktestFolds } from '@/hooks/useBacktestFolds'
import { useBacktestComparison } from '@/hooks/useBacktestComparison'
import { cn } from '@/lib/utils'
import type {
  BacktestComparisonStrategyItem,
  BacktestFoldItem,
  BacktestResultItem,
  BacktestRunItem,
  RegimeBreakdownItem,
  SectorBreakdownItem,
  StrategyItem,
} from '@/api/types'

function fmtNum(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', { maximumFractionDigits: 4 })
}

const ACTION_TONE: Record<string, string> = {
  BUY: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-900/40',
  AVOID:
    'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-200 dark:border-red-900/40',
  PASS: 'bg-muted text-muted-foreground border-border',
}

const DATA_SOURCE_TONE: Record<string, string> = {
  PROVIDER: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-900/40',
  FAKE: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-900/40',
  CSV: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-200 dark:border-purple-900/40',
  MANUAL: 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-900/30 dark:text-gray-200 dark:border-gray-900/40',
}

function ActionBadge({ value }: { value: string | null }) {
  const label = value ?? '—'
  const tone = ACTION_TONE[label] ?? ACTION_TONE.PASS
  return (
    <span
      data-testid={`backtest-action-${label}`}
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        tone,
      )}
    >
      {label}
    </span>
  )
}

function DataSourceChip({ value }: { value: string | null | undefined }) {
  if (!value) return null
  const tone = DATA_SOURCE_TONE[value.toUpperCase()] ?? DATA_SOURCE_TONE.MANUAL
  return (
    <span
      data-testid={`backtest-data-source-${value}`}
      className={cn(
        'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium',
        tone,
      )}
    >
      {value}
    </span>
  )
}

export function BacktestPage() {
  const [strategyFilter, setStrategyFilter] = useState<string>('ALL')
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)

  const strategies = useStrategies()
  const runs = useBacktestRuns({
    strategy: strategyFilter === 'ALL' ? undefined : strategyFilter,
    limit: 20,
  })
  const detail = useBacktestRunDetail(selectedRunId)
  const folds = useBacktestFolds(selectedRunId)
  const comparison = useBacktestComparison(selectedRunId)

  const strategyOptions = useMemo<Array<'ALL' | string>>(
    () => ['ALL', ...(strategies.data?.items.map(s => s.name) ?? [])],
    [strategies.data?.items],
  )

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">
            백테스트 <span className="text-xs text-muted-foreground">(β)</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            과거 추천 + recommendation_results 위에 룰 기반 전략을 재실행한 read-only
            결과. 실제 매매 / 주문 / Broker 호출 0건.
            {runs.dataUpdatedAt > 0 && (
              <>
                {' '}
                <span className="font-mono text-xs">
                  (last fetch{' '}
                  {new Date(runs.dataUpdatedAt).toLocaleTimeString('ko-KR')})
                </span>
              </>
            )}
          </p>
        </div>
      </header>

      <StrategyListSection
        loading={strategies.isLoading}
        error={strategies.isError}
        items={strategies.data?.items ?? []}
      />

      <RunsTableSection
        loading={runs.isLoading}
        error={runs.isError}
        items={runs.data?.items ?? []}
        strategyOptions={strategyOptions}
        strategyFilter={strategyFilter}
        onStrategyChange={setStrategyFilter}
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
      />

      {selectedRunId !== null && (
        <RunDetailSection
          loading={detail.isLoading}
          error={detail.isError}
          data={detail.data}
          foldsLoading={folds.isLoading}
          foldsData={folds.data}
          comparisonLoading={comparison.isLoading}
          comparisonData={comparison.data}
        />
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Strategy list
// -----------------------------------------------------------------------

function StrategyListSection({
  loading,
  error,
  items,
}: {
  loading: boolean
  error: boolean
  items: StrategyItem[]
}) {
  return (
    <section
      data-testid="backtest-strategies"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">등록된 전략 ({items.length})</h3>
        <span className="text-xs text-muted-foreground">
          registry 기반 · 외부 호출 0건
        </span>
      </header>
      {loading && (
        <p
          data-testid="backtest-strategies-loading"
          className="text-sm text-muted-foreground"
        >
          전략 목록 로딩 중…
        </p>
      )}
      {error && (
        <p
          data-testid="backtest-strategies-error"
          className="text-sm text-red-700 dark:text-red-300"
        >
          전략 목록을 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p
          data-testid="backtest-strategies-empty"
          className="text-sm text-muted-foreground"
        >
          등록된 전략이 없습니다.
        </p>
      )}
      {!loading && !error && items.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {items.map(strategy => (
            <li
              key={strategy.name}
              data-testid={`backtest-strategy-${strategy.name}`}
              className="rounded-md border border-border bg-muted/30 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{strategy.name}</span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {strategy.version}
                </span>
              </div>
              {strategy.description && (
                <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">
                  {strategy.description}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Runs table
// -----------------------------------------------------------------------

function RunsTableSection({
  loading,
  error,
  items,
  strategyOptions,
  strategyFilter,
  onStrategyChange,
  selectedRunId,
  onSelectRun,
}: {
  loading: boolean
  error: boolean
  items: BacktestRunItem[]
  strategyOptions: Array<'ALL' | string>
  strategyFilter: string
  onStrategyChange: (value: string) => void
  selectedRunId: number | null
  onSelectRun: (id: number) => void
}) {
  return (
    <section
      data-testid="backtest-runs"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">최근 백테스트 run ({items.length})</h3>
        <div
          role="radiogroup"
          aria-label="strategy filter"
          className="inline-flex overflow-hidden rounded-md border border-border bg-card text-sm"
        >
          {strategyOptions.map(opt => (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={strategyFilter === opt}
              data-testid={`backtest-strategy-filter-${opt}`}
              onClick={() => onStrategyChange(opt)}
              className={cn(
                'px-3 py-1.5 transition-colors',
                strategyFilter === opt
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-accent/60',
              )}
            >
              {opt}
            </button>
          ))}
        </div>
      </header>

      {loading && (
        <p
          data-testid="backtest-runs-loading"
          className="text-sm text-muted-foreground"
        >
          백테스트 run 로딩 중…
        </p>
      )}
      {error && (
        <p
          data-testid="backtest-runs-error"
          className="text-sm text-red-700 dark:text-red-300"
        >
          백테스트 run 목록을 불러오지 못했습니다.
        </p>
      )}
      {!loading && !error && items.length === 0 && (
        <p
          data-testid="backtest-runs-empty"
          className="text-sm text-muted-foreground"
        >
          저장된 백테스트 run 이 없습니다. CLI{' '}
          <code className="rounded bg-muted px-1 py-0.5">
            scripts/run_backtest.py --commit
          </code>{' '}
          으로 적재하세요.
        </p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-xs" data-testid="backtest-runs-table">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">strategy</th>
                <th className="px-2 py-1 font-medium">run_date</th>
                <th className="px-2 py-1 font-medium">signals</th>
                <th className="px-2 py-1 font-medium">B / P / A</th>
                <th className="px-2 py-1 font-medium">win_rate_5d</th>
                <th className="px-2 py-1 font-medium">avg_return_5d</th>
                <th className="px-2 py-1 font-medium">cost_adj_5d</th>
                <th className="px-2 py-1 font-medium">max_dd</th>
                <th className="px-2 py-1 font-medium">status</th>
              </tr>
            </thead>
            <tbody>
              {items.map(run => {
                const active = run.id === selectedRunId
                return (
                  <tr
                    key={run.id}
                    data-testid={`backtest-run-row-${run.id}`}
                    onClick={() => onSelectRun(run.id)}
                    className={cn(
                      'cursor-pointer border-t border-border transition-colors hover:bg-accent',
                      active && 'bg-accent',
                    )}
                  >
                    <td className="px-2 py-1">
                      <div className="flex flex-col leading-tight">
                        <span className="font-semibold">{run.strategy_name}</span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {run.strategy_version}
                        </span>
                      </div>
                    </td>
                    <td className="px-2 py-1 font-mono">{run.run_date}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {run.signal_count}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums text-muted-foreground">
                      {run.buy_count}/{run.pass_count}/{run.avoid_count}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(run.win_rate_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(run.avg_return_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(run.cost_adjusted_avg_return_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(run.max_drawdown)}
                    </td>
                    <td className="px-2 py-1">
                      <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                        {run.status}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// -----------------------------------------------------------------------
// Run detail
// -----------------------------------------------------------------------

interface RunDetailData {
  run: BacktestRunItem
  results: BacktestResultItem[]
  regime_breakdown: RegimeBreakdownItem[]
  cost_model_version: string | null
  total_cost: string | null
  notes: string | null
}

function RunDetailSection({
  loading,
  error,
  data,
  foldsLoading,
  foldsData,
  comparisonLoading,
  comparisonData,
}: {
  loading: boolean
  error: boolean
  data: RunDetailData | undefined
  foldsLoading: boolean
  foldsData: { total_folds: number; folds: BacktestFoldItem[]; avg_oos_win_rate_5d: string | null; avg_oos_avg_return_5d: string | null } | undefined
  comparisonLoading: boolean
  comparisonData: { total_strategies: number; strategies: BacktestComparisonStrategyItem[]; best_strategy_by_win_rate_5d: string | null; best_strategy_by_avg_return_5d: string | null } | undefined
}) {
  if (loading) {
    return (
      <section
        data-testid="backtest-detail-loading"
        className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground"
      >
        백테스트 상세 로딩 중…
      </section>
    )
  }
  if (error) {
    return (
      <section
        data-testid="backtest-detail-error"
        className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        백테스트 상세를 불러오지 못했습니다.
      </section>
    )
  }
  if (!data) return null

  return (
    <section
      data-testid="backtest-detail"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">
            run #{data.run.id} · {data.run.strategy_name}{' '}
            <span className="font-mono text-[11px] text-muted-foreground">
              {data.run.strategy_version}
            </span>
          </h3>
          <p className="text-xs text-muted-foreground">
            {data.run.run_date} ·{' '}
            <span className="font-mono">{data.run.status}</span>
            {data.cost_model_version && (
              <>
                {' '}
                · cost_model{' '}
                <span data-testid="backtest-detail-cost-model" className="font-mono">
                  {data.cost_model_version}
                </span>{' '}
                (total_cost {data.total_cost ?? '—'})
              </>
            )}
          </p>
        </div>
      </header>

      {data.notes && (
        <p
          data-testid="backtest-detail-notes"
          className="rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
        >
          {data.notes}
        </p>
      )}

      {/* Walk-forward folds */}
      <WalkForwardFoldsSection loading={foldsLoading} data={foldsData} />

      {/* Multi-strategy comparison */}
      <MultiStrategyComparisonSection loading={comparisonLoading} data={comparisonData} />

      <div data-testid="backtest-detail-regime-breakdown">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          regime breakdown
        </h4>
        {data.regime_breakdown.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            regime 분리 데이터가 없습니다.
          </p>
        ) : (
          <div className="mt-1 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-2 py-1 font-medium">regime</th>
                  <th className="px-2 py-1 font-medium">buy</th>
                  <th className="px-2 py-1 font-medium">win_rate_5d</th>
                  <th className="px-2 py-1 font-medium">avg_return_5d</th>
                  <th className="px-2 py-1 font-medium">cost_adj_5d</th>
                </tr>
              </thead>
              <tbody>
                {data.regime_breakdown.map(entry => (
                  <tr
                    key={entry.regime}
                    data-testid={`backtest-regime-${entry.regime}`}
                    className="border-t border-border"
                  >
                    <td className="px-2 py-1 font-mono">{entry.regime}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {entry.buy_count}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(entry.win_rate_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(entry.avg_return_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(entry.cost_adjusted_avg_return_5d)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div data-testid="backtest-detail-results">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          신호 ({data.results.length})
        </h4>
        {data.results.length === 0 ? (
          <p className="text-xs text-muted-foreground">평가된 신호가 없습니다.</p>
        ) : (
          <div className="mt-1 overflow-x-auto rounded-md border border-border">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-2 py-1 font-medium">symbol</th>
                  <th className="px-2 py-1 font-medium">action</th>
                  <th className="px-2 py-1 font-medium">conf</th>
                  <th className="px-2 py-1 font-medium">grade</th>
                  <th className="px-2 py-1 font-medium">total</th>
                  <th className="px-2 py-1 font-medium">5d</th>
                  <th className="px-2 py-1 font-medium">cost_adj_5d</th>
                  <th className="px-2 py-1 font-medium">regime</th>
                  <th className="px-2 py-1 font-medium">source</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map(row => (
                  <tr
                    key={row.id}
                    data-testid={`backtest-result-${row.id}`}
                    className="border-t border-border"
                  >
                    <td className="px-2 py-1 font-mono">{row.symbol}</td>
                    <td className="px-2 py-1">
                      <ActionBadge value={row.signal_action} />
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(row.confidence)}
                    </td>
                    <td className="px-2 py-1">{row.grade ?? '—'}</td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(row.total_score)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(row.return_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono tabular-nums">
                      {fmtNum(row.cost_adjusted_return_5d)}
                    </td>
                    <td className="px-2 py-1 font-mono text-[11px] text-muted-foreground">
                      {row.regime ?? '—'}
                    </td>
                    <td className="px-2 py-1">
                      <DataSourceChip
                        value={
                          typeof row.evidence_json?.data_source === 'string'
                            ? row.evidence_json.data_source
                            : null
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

// -----------------------------------------------------------------------
// Walk-forward folds sub-section
// -----------------------------------------------------------------------

function WalkForwardFoldsSection({
  loading,
  data,
}: {
  loading: boolean
  data: { total_folds: number; folds: BacktestFoldItem[]; avg_oos_win_rate_5d: string | null; avg_oos_avg_return_5d: string | null } | undefined
}) {
  if (loading) return null
  if (!data || data.total_folds === 0) {
    return (
      <div data-testid="backtest-folds-empty">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          walk-forward folds
        </h4>
        <p className="text-xs text-muted-foreground">
          walk-forward 데이터가 없습니다.
        </p>
      </div>
    )
  }

  return (
    <div data-testid="backtest-folds">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        walk-forward folds ({data.total_folds}){' '}
        <span className="ml-2 font-normal text-muted-foreground">
          avg OOS win_rate_5d: {fmtNum(data.avg_oos_win_rate_5d)} · avg OOS avg_return_5d:{' '}
          {fmtNum(data.avg_oos_avg_return_5d)}
        </span>
      </h4>
      <div className="mt-1 overflow-x-auto rounded-md border border-border">
        <table className="w-full text-xs" data-testid="backtest-folds-table">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-2 py-1 font-medium">#</th>
              <th className="px-2 py-1 font-medium">IS 기간</th>
              <th className="px-2 py-1 font-medium">OOS 기간</th>
              <th className="px-2 py-1 font-medium">IS buy</th>
              <th className="px-2 py-1 font-medium">IS win_5d</th>
              <th className="px-2 py-1 font-medium">OOS buy</th>
              <th className="px-2 py-1 font-medium">OOS win_5d</th>
              <th className="px-2 py-1 font-medium">OOS avg_5d</th>
            </tr>
          </thead>
          <tbody>
            {data.folds.map(fold => (
              <tr
                key={fold.fold_index}
                data-testid={`backtest-fold-${fold.fold_index}`}
                className="border-t border-border"
              >
                <td className="px-2 py-1 font-mono tabular-nums">{fold.fold_index}</td>
                <td className="px-2 py-1 font-mono text-[11px]">
                  {fold.train_start} ~ {fold.train_end}
                </td>
                <td className="px-2 py-1 font-mono text-[11px]">
                  {fold.validate_start} ~ {fold.validate_end}
                </td>
                <td className="px-2 py-1 font-mono tabular-nums">{fold.is_buy_count}</td>
                <td className="px-2 py-1 font-mono tabular-nums">
                  {fmtNum(fold.is_win_rate_5d)}
                </td>
                <td className="px-2 py-1 font-mono tabular-nums">{fold.oos_buy_count}</td>
                <td className="px-2 py-1 font-mono tabular-nums">
                  {fmtNum(fold.oos_win_rate_5d)}
                </td>
                <td className="px-2 py-1 font-mono tabular-nums">
                  {fmtNum(fold.oos_avg_return_5d)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------
// Multi-strategy comparison sub-section
// -----------------------------------------------------------------------

function MultiStrategyComparisonSection({
  loading,
  data,
}: {
  loading: boolean
  data: { total_strategies: number; strategies: BacktestComparisonStrategyItem[]; best_strategy_by_win_rate_5d: string | null; best_strategy_by_avg_return_5d: string | null } | undefined
}) {
  if (loading) return null
  if (!data || data.total_strategies === 0) {
    return (
      <div data-testid="backtest-comparison-empty">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          multi-strategy comparison
        </h4>
        <p className="text-xs text-muted-foreground">
          다중 전략 비교 데이터가 없습니다.
        </p>
      </div>
    )
  }

  return (
    <div data-testid="backtest-comparison">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        multi-strategy comparison ({data.total_strategies})
      </h4>
      {(data.best_strategy_by_win_rate_5d || data.best_strategy_by_avg_return_5d) && (
        <p
          data-testid="backtest-comparison-best"
          className="mt-0.5 text-xs text-muted-foreground"
        >
          best win_rate_5d:{' '}
          <span className="font-semibold text-emerald-700 dark:text-emerald-300">
            {data.best_strategy_by_win_rate_5d ?? '—'}
          </span>{' '}
          · best avg_return_5d:{' '}
          <span className="font-semibold text-emerald-700 dark:text-emerald-300">
            {data.best_strategy_by_avg_return_5d ?? '—'}
          </span>
        </p>
      )}
      <div className="mt-1 overflow-x-auto rounded-md border border-border">
        <table className="w-full text-xs" data-testid="backtest-comparison-table">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-2 py-1 font-medium">strategy</th>
              <th className="px-2 py-1 font-medium">signals</th>
              <th className="px-2 py-1 font-medium">B / P / A</th>
              <th className="px-2 py-1 font-medium">win_rate_5d</th>
              <th className="px-2 py-1 font-medium">avg_return_5d</th>
              <th className="px-2 py-1 font-medium">cost_adj_5d</th>
              <th className="px-2 py-1 font-medium">max_dd</th>
            </tr>
          </thead>
          <tbody>
            {data.strategies.map(row => {
              const isBestWr = row.strategy_name === data.best_strategy_by_win_rate_5d
              const isBestAr = row.strategy_name === data.best_strategy_by_avg_return_5d
              return (
                <tr
                  key={row.strategy_name}
                  data-testid={`backtest-comparison-row-${row.strategy_name}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1">
                    <div className="flex flex-col leading-tight">
                      <span className={cn('font-semibold', (isBestWr || isBestAr) && 'text-emerald-700 dark:text-emerald-300')}>
                        {row.strategy_name}
                        {(isBestWr || isBestAr) && (
                          <span
                            data-testid={`backtest-comparison-best-${row.strategy_name}`}
                            className="ml-1 text-[10px]"
                          >
                            ★
                          </span>
                        )}
                      </span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {row.strategy_version}
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">{row.signal_count}</td>
                  <td className="px-2 py-1 font-mono tabular-nums text-muted-foreground">
                    {row.buy_count}/{row.pass_count}/{row.avoid_count}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmtNum(row.win_rate_5d)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmtNum(row.avg_return_5d)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmtNum(row.cost_adjusted_avg_return_5d)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmtNum(row.max_drawdown)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Sector breakdown for each strategy (compact) */}
      {data.strategies.some(s => s.sector_breakdown.length > 0) && (
        <SectorBreakdownSection strategies={data.strategies} />
      )}
    </div>
  )
}

// -----------------------------------------------------------------------
// Sector breakdown (compact, per-strategy)
// -----------------------------------------------------------------------

function SectorBreakdownSection({
  strategies,
}: {
  strategies: BacktestComparisonStrategyItem[]
}) {
  return (
    <div
      data-testid="backtest-sector-breakdown"
      className="mt-2 flex flex-col gap-2"
    >
      {strategies
        .filter(s => s.sector_breakdown.length > 0)
        .map(s => (
          <div key={s.strategy_name}>
            <p className="text-[11px] font-semibold text-muted-foreground">
              {s.strategy_name} — sector breakdown
            </p>
            <SectorTable items={s.sector_breakdown} strategyName={s.strategy_name} />
          </div>
        ))}
    </div>
  )
}

function SectorTable({
  items,
  strategyName,
}: {
  items: SectorBreakdownItem[]
  strategyName: string
}) {
  return (
    <div className="mt-0.5 overflow-x-auto rounded-md border border-border">
      <table className="w-full text-xs">
        <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-2 py-1 font-medium">sector</th>
            <th className="px-2 py-1 font-medium">signals</th>
            <th className="px-2 py-1 font-medium">buy</th>
            <th className="px-2 py-1 font-medium">win_5d</th>
            <th className="px-2 py-1 font-medium">avg_5d</th>
          </tr>
        </thead>
        <tbody>
          {items.map(entry => (
            <tr
              key={entry.sector}
              data-testid={`backtest-sector-${strategyName}-${entry.sector}`}
              className="border-t border-border"
            >
              <td className="px-2 py-1 font-mono">{entry.sector}</td>
              <td className="px-2 py-1 font-mono tabular-nums">{entry.signal_count}</td>
              <td className="px-2 py-1 font-mono tabular-nums">{entry.buy_count}</td>
              <td className="px-2 py-1 font-mono tabular-nums">
                {fmtNum(entry.win_rate_5d)}
              </td>
              <td className="px-2 py-1 font-mono tabular-nums">
                {fmtNum(entry.avg_return_5d)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
