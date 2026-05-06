import { useStockFundamentals } from '@/hooks/useStockFundamentals'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import type { FundamentalSnapshot } from '@/api/types'

interface FundamentalsCardProps {
  symbol: string
}

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  // Strip trailing zeros after the decimal for display readability while
  // preserving the source string's precision when needed.
  const num = Number(value)
  if (!Number.isFinite(num)) return value
  return num.toLocaleString('ko-KR', { maximumFractionDigits: 4 })
}

function periodLabel(row: FundamentalSnapshot): string {
  const q = row.fiscal_quarter ?? null
  return q === null ? `${row.fiscal_year} 연간` : `${row.fiscal_year} Q${q}`
}

export function FundamentalsCard({ symbol }: FundamentalsCardProps) {
  const query = useStockFundamentals(symbol)

  if (query.isLoading) {
    return (
      <section
        data-testid="stock-detail-fundamentals-loading"
        className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
      >
        재무 스냅샷 로딩 중…
      </section>
    )
  }

  if (query.isError) {
    return (
      <section
        data-testid="stock-detail-fundamentals-error"
        className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        재무 스냅샷을 불러오지 못했습니다.
      </section>
    )
  }

  const data = query.data
  const latest = data?.latest
  if (!latest) {
    return (
      <section
        data-testid="stock-detail-fundamentals-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        재무 데이터가 없습니다.
      </section>
    )
  }

  return (
    <section
      data-testid="stock-detail-fundamentals"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div className="flex flex-col">
          <h3 className="text-sm font-semibold">재무 스냅샷</h3>
          <p className="text-xs text-muted-foreground">
            {periodLabel(latest)} · 기준일{' '}
            <span className="font-mono">{latest.snapshot_date}</span>
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          history{' '}
          <span className="font-mono">{data?.count ?? 0}</span>
        </span>
      </header>

      <KeyValueGrid
        columns={3}
        testid="stock-detail-fundamentals-latest"
        rows={[
          { label: 'PER', value: fmt(latest.per) },
          { label: 'PBR', value: fmt(latest.pbr) },
          { label: 'ROE %', value: fmt(latest.roe) },
          { label: '부채비율 %', value: fmt(latest.debt_ratio) },
          { label: '배당수익률 %', value: fmt(latest.dividend_yield) },
          { label: '매출 성장률 %', value: fmt(latest.revenue_growth_yoy) },
          {
            label: '영업이익 성장률 %',
            value: fmt(latest.operating_income_growth_yoy),
          },
          { label: 'EPS', value: fmt(latest.eps) },
          { label: 'BPS', value: fmt(latest.bps) },
        ]}
      />

      {data && data.history.length > 1 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table
            className="w-full text-xs"
            data-testid="stock-detail-fundamentals-history"
          >
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">period</th>
                <th className="px-2 py-1 font-medium">PER</th>
                <th className="px-2 py-1 font-medium">PBR</th>
                <th className="px-2 py-1 font-medium">ROE</th>
                <th className="px-2 py-1 font-medium">매출↑</th>
                <th className="px-2 py-1 font-medium">영익↑</th>
                <th className="px-2 py-1 font-medium">부채</th>
              </tr>
            </thead>
            <tbody>
              {data.history.map(row => (
                <tr
                  key={`${row.snapshot_date}-${row.fiscal_year}-${row.fiscal_quarter ?? 'A'}`}
                  data-testid={`fund-row-${row.fiscal_year}-${row.fiscal_quarter ?? 'A'}`}
                  className="border-t border-border align-top"
                >
                  <td className="px-2 py-1 font-mono">{periodLabel(row)}</td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.per)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.pbr)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.roe)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.revenue_growth_yoy)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.operating_income_growth_yoy)}
                  </td>
                  <td className="px-2 py-1 font-mono tabular-nums">
                    {fmt(row.debt_ratio)}
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
