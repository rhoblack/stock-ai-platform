import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useMarketCapTop } from '@/hooks/useMarketCapTop'
import type { MarketCapRanking } from '@/api/types'
import { cn } from '@/lib/utils'

type MarketFilter = 'KOSPI' | 'KOSDAQ' | 'ALL'

const MARKET_OPTIONS: MarketFilter[] = ['KOSPI', 'KOSDAQ', 'ALL']

function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(num)) return String(value)
  return new Intl.NumberFormat('ko-KR').format(num)
}

export function MarketCapTopPage() {
  const [market, setMarket] = useState<MarketFilter>('KOSPI')
  const [search, setSearch] = useState('')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'rank', desc: false }])

  // Backend exposes single market per call; for ALL we fetch KOSPI + KOSDAQ in
  // parallel and merge client-side.
  const kospi = useMarketCapTop({
    market: 'KOSPI',
    enabled: market !== 'KOSDAQ',
  })
  const kosdaq = useMarketCapTop({
    market: 'KOSDAQ',
    enabled: market !== 'KOSPI',
  })

  const rows: MarketCapRanking[] = useMemo(() => {
    const collected: MarketCapRanking[] = []
    if (market !== 'KOSDAQ' && kospi.data) collected.push(...kospi.data.items)
    if (market !== 'KOSPI' && kosdaq.data) collected.push(...kosdaq.data.items)
    if (!search.trim()) return collected
    const needle = search.trim().toLowerCase()
    return collected.filter(
      r =>
        r.symbol.toLowerCase().includes(needle) ||
        r.name.toLowerCase().includes(needle),
    )
  }, [market, kospi.data, kosdaq.data, search])

  const isLoading =
    (market !== 'KOSDAQ' && kospi.isLoading) || (market !== 'KOSPI' && kosdaq.isLoading)
  const isError =
    (market !== 'KOSDAQ' && kospi.isError) || (market !== 'KOSPI' && kosdaq.isError)

  const columns = useMemo<ColumnDef<MarketCapRanking>[]>(
    () => [
      {
        accessorKey: 'rank',
        header: '#',
        cell: ({ row }) => (
          <span className="font-mono text-xs text-muted-foreground">
            {row.original.rank}
          </span>
        ),
      },
      {
        accessorKey: 'market',
        header: '시장',
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">{row.original.market}</span>
        ),
      },
      {
        accessorKey: 'symbol',
        header: '종목',
        cell: ({ row }) => (
          <Link
            to={`/stocks/${row.original.symbol}`}
            data-testid={`mcap-row-${row.original.symbol}`}
            className="flex flex-col leading-tight hover:underline"
          >
            <span className="text-sm font-medium">{row.original.name}</span>
            <span className="font-mono text-xs text-muted-foreground">
              {row.original.symbol}
            </span>
          </Link>
        ),
      },
      {
        accessorKey: 'sector',
        header: '섹터',
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {row.original.sector ?? '—'}
          </span>
        ),
      },
      {
        accessorKey: 'market_cap',
        header: 'market_cap',
        cell: ({ row }) => (
          <span className="font-mono text-xs tabular-nums">
            {formatNumber(row.original.market_cap)}
          </span>
        ),
        sortingFn: (a, b) =>
          Number(a.original.market_cap ?? 0) - Number(b.original.market_cap ?? 0),
      },
      {
        accessorKey: 'close_price',
        header: 'close',
        cell: ({ row }) => (
          <span className="font-mono text-xs tabular-nums">
            {formatNumber(row.original.close_price)}
          </span>
        ),
      },
      {
        accessorKey: 'listed_shares',
        header: '발행주식',
        cell: ({ row }) => (
          <span className="font-mono text-xs tabular-nums">
            {formatNumber(row.original.listed_shares)}
          </span>
        ),
      },
      {
        accessorKey: 'trading_value',
        header: 'trading_value',
        cell: ({ row }) => (
          <span className="font-mono text-xs tabular-nums">
            {formatNumber(row.original.trading_value)}
          </span>
        ),
      },
      {
        accessorKey: 'is_analysis_target',
        header: '분석',
        cell: ({ row }) => (
          <span
            className={cn(
              'text-xs',
              row.original.is_analysis_target
                ? 'text-emerald-600 dark:text-emerald-300'
                : 'text-muted-foreground',
            )}
          >
            {row.original.is_analysis_target ? '✓' : '—'}
          </span>
        ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const lastFetch =
    market === 'KOSDAQ'
      ? kosdaq.dataUpdatedAt
      : market === 'KOSPI'
        ? kospi.dataUpdatedAt
        : Math.max(kospi.dataUpdatedAt, kosdaq.dataUpdatedAt)

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">시가총액 TOP</h2>
          <p className="text-sm text-muted-foreground">
            18:00 collect_market_close_data 잡으로 갱신. 1시간마다 자동 새로고침.
            {lastFetch > 0 && (
              <>
                {' '}
                <span className="font-mono text-xs">
                  (last fetch {new Date(lastFetch).toLocaleTimeString('ko-KR')})
                </span>
              </>
            )}
          </p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div
          role="radiogroup"
          aria-label="market filter"
          className="inline-flex overflow-hidden rounded-md border border-border bg-card text-sm"
        >
          {MARKET_OPTIONS.map(opt => (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={market === opt}
              data-testid={`mcap-filter-${opt}`}
              onClick={() => setMarket(opt)}
              className={cn(
                'px-3 py-1.5 transition-colors',
                market === opt
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-accent/60',
              )}
            >
              {opt}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="symbol 또는 종목명 검색"
          aria-label="symbol 또는 종목명 검색"
          data-testid="mcap-search"
          className="w-72 rounded-md border border-border bg-card px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <span className="ml-auto text-xs text-muted-foreground">
          {rows.length}건 표시
        </span>
      </div>

      {isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          시총 상위 로딩 중…
        </div>
      )}

      {isError && (
        <div
          data-testid="mcap-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          시가총액 데이터를 불러오지 못했습니다.
        </div>
      )}

      {!isLoading && !isError && rows.length === 0 && (
        <div
          data-testid="mcap-empty"
          className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
        >
          {search.trim()
            ? `"${search}" 와 일치하는 종목이 없습니다.`
            : '아직 시가총액 데이터가 없습니다 (collect_market_close_data 잡 미실행).'}
        </div>
      )}

      {!isLoading && !isError && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm" data-testid="mcap-table">
            <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              {table.getHeaderGroups().map(group => (
                <tr key={group.id}>
                  {group.headers.map(header => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={cn(
                        'cursor-pointer px-3 py-2 font-medium select-none',
                        header.column.getIsSorted() && 'text-foreground',
                      )}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {header.column.getIsSorted() === 'asc' && ' ▲'}
                      {header.column.getIsSorted() === 'desc' && ' ▼'}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map(row => (
                <tr key={row.id} className="border-t border-border align-middle">
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
