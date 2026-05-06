import { useStockEarnings } from '@/hooks/useStockEarnings'
import { cn } from '@/lib/utils'
import type { EarningsEvent } from '@/api/types'

interface EarningsCardProps {
  symbol: string
}

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', { maximumFractionDigits: 4 })
}

function periodLabel(event: EarningsEvent): string {
  const q = event.fiscal_quarter ?? null
  return q === null
    ? `${event.fiscal_year} 연간`
    : `${event.fiscal_year} Q${q}`
}

const SURPRISE_TONE: Record<string, string> = {
  BEAT: 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/30 dark:text-emerald-200',
  MEET: 'border-border bg-muted text-muted-foreground',
  MISS: 'border-red-300 bg-red-50 text-red-700 dark:border-red-900/40 dark:bg-red-900/30 dark:text-red-200',
  UNKNOWN: 'border-border bg-muted text-muted-foreground',
}

function SurpriseBadge({ value }: { value: string | null }) {
  const label = value ?? '—'
  const tone = SURPRISE_TONE[label] ?? 'border-border bg-muted text-muted-foreground'
  return (
    <span
      data-testid={`earnings-surprise-${label}`}
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        tone,
      )}
    >
      {label}
    </span>
  )
}

export function EarningsCard({ symbol }: EarningsCardProps) {
  const query = useStockEarnings(symbol)

  if (query.isLoading) {
    return (
      <section
        data-testid="stock-detail-earnings-loading"
        className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
      >
        실적 이벤트 로딩 중…
      </section>
    )
  }

  if (query.isError) {
    return (
      <section
        data-testid="stock-detail-earnings-error"
        className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        실적 이벤트를 불러오지 못했습니다.
      </section>
    )
  }

  const data = query.data
  const latest = data?.latest
  if (!latest) {
    return (
      <section
        data-testid="stock-detail-earnings-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        실적 이벤트가 없습니다.
      </section>
    )
  }

  return (
    <section
      data-testid="stock-detail-earnings"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-col">
          <h3 className="text-sm font-semibold">실적 이벤트</h3>
          <p className="text-xs text-muted-foreground">
            최근 {periodLabel(latest)} · {latest.event_date} ·{' '}
            <span className="font-mono">{latest.event_type}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <SurpriseBadge value={latest.surprise_type} />
          <span
            data-testid="stock-detail-earnings-latest-surprise-pct"
            className="font-mono text-xs tabular-nums"
          >
            {fmt(latest.surprise_pct)}%
          </span>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <div data-testid="stock-detail-earnings-op-actual" className="rounded-md border border-border bg-muted/30 p-2">
          <div className="text-muted-foreground">영업이익 (actual)</div>
          <div className="font-mono tabular-nums">{fmt(latest.operating_income_actual)}</div>
        </div>
        <div data-testid="stock-detail-earnings-op-consensus" className="rounded-md border border-border bg-muted/30 p-2">
          <div className="text-muted-foreground">영업이익 (consensus)</div>
          <div className="font-mono tabular-nums">{fmt(latest.operating_income_consensus)}</div>
        </div>
        <div className="rounded-md border border-border bg-muted/30 p-2">
          <div className="text-muted-foreground">EPS actual / consensus</div>
          <div className="font-mono tabular-nums">
            {fmt(latest.eps_actual)} / {fmt(latest.eps_consensus)}
          </div>
        </div>
      </div>

      {data && data.events.length > 1 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table
            className="w-full text-xs"
            data-testid="stock-detail-earnings-history"
          >
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">period</th>
                <th className="px-2 py-1 font-medium">date</th>
                <th className="px-2 py-1 font-medium">type</th>
                <th className="px-2 py-1 font-medium">surprise</th>
                <th className="px-2 py-1 font-medium">surprise %</th>
                <th className="px-2 py-1 font-medium">actual / cons</th>
              </tr>
            </thead>
            <tbody>
              {data.events.map(row => (
                <tr
                  key={`${row.event_date}-${row.fiscal_year}-${row.fiscal_quarter ?? 'A'}-${row.event_type}`}
                  data-testid={`earnings-row-${row.fiscal_year}-${row.fiscal_quarter ?? 'A'}`}
                  className="border-t border-border align-top"
                >
                  <td className="px-2 py-1 font-mono">{periodLabel(row)}</td>
                  <td className="px-2 py-1 font-mono">{row.event_date}</td>
                  <td className="px-2 py-1 text-muted-foreground">{row.event_type}</td>
                  <td className="px-2 py-1">
                    <SurpriseBadge value={row.surprise_type} />
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.surprise_pct)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.operating_income_actual)} / {fmt(row.operating_income_consensus)}
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
