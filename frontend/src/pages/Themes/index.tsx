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
import { useThemeRanking } from '@/hooks/useThemeRanking'
import type { ThemeRankingItem } from '@/api/types'
import { cn } from '@/lib/utils'

type DirectionFilter = 'ALL' | 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'

const DIRECTION_OPTIONS: DirectionFilter[] = [
  'ALL',
  'POSITIVE',
  'NEGATIVE',
  'NEUTRAL',
]

function dash(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

export function ThemesPage() {
  const [direction, setDirection] = useState<DirectionFilter>('ALL')
  const [search, setSearch] = useState('')
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'mapping_count', desc: true },
  ])

  const query = useThemeRanking({
    direction: direction === 'ALL' ? undefined : direction,
    limit: 100,
  })

  const rows: ThemeRankingItem[] = useMemo(() => {
    const items = query.data?.items ?? []
    if (!search.trim()) return items
    const needle = search.trim().toLowerCase()
    return items.filter(
      r =>
        r.theme_name.toLowerCase().includes(needle) ||
        r.theme_category.toLowerCase().includes(needle),
    )
  }, [query.data?.items, search])

  const columns = useMemo<ColumnDef<ThemeRankingItem>[]>(
    () => [
      {
        accessorKey: 'theme_name',
        header: '테마',
        cell: ({ row }) => (
          <Link
            to={`/themes/${row.original.theme_id}`}
            data-testid={`theme-row-${row.original.theme_id}`}
            className="flex flex-col leading-tight hover:underline"
          >
            <span className="text-sm font-medium">{row.original.theme_name}</span>
            <span className="font-mono text-[11px] text-muted-foreground">
              theme_id #{row.original.theme_id}
            </span>
          </Link>
        ),
      },
      {
        accessorKey: 'theme_category',
        header: '카테고리',
        cell: ({ row }) => (
          <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
            {row.original.theme_category}
          </span>
        ),
      },
      {
        accessorKey: 'direction',
        header: '방향',
        cell: ({ row }) => (
          <span
            className={cn(
              'rounded-md px-2 py-0.5 text-[11px]',
              row.original.direction === 'POSITIVE' &&
                'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
              row.original.direction === 'NEGATIVE' &&
                'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
              (row.original.direction === 'NEUTRAL' ||
                !['POSITIVE', 'NEGATIVE'].includes(row.original.direction)) &&
                'bg-muted text-muted-foreground',
            )}
            data-testid={`theme-direction-${row.original.theme_id}`}
          >
            {row.original.direction}
          </span>
        ),
      },
      {
        accessorKey: 'time_horizon',
        header: '기간',
        cell: ({ row }) => (
          <span className="font-mono text-[11px] text-muted-foreground">
            {row.original.time_horizon}
          </span>
        ),
      },
      {
        accessorKey: 'mapping_count',
        header: '연결 종목',
        cell: ({ row }) => (
          <span
            data-testid={`theme-mapping-count-${row.original.theme_id}`}
            className="font-mono text-xs tabular-nums"
          >
            {row.original.mapping_count}
          </span>
        ),
      },
      {
        accessorKey: 'signal_event_count',
        header: '시그널',
        cell: ({ row }) => (
          <span
            data-testid={`theme-signal-count-${row.original.theme_id}`}
            className="font-mono text-xs tabular-nums"
          >
            {row.original.signal_event_count}
          </span>
        ),
      },
      {
        accessorKey: 'summary',
        header: '요약',
        cell: ({ row }) => (
          <span className="line-clamp-2 text-xs text-muted-foreground">
            {dash(row.original.summary)}
          </span>
        ),
      },
      {
        accessorKey: 'confidence',
        header: 'confidence',
        cell: ({ row }) => (
          <span className="font-mono text-[11px] text-muted-foreground">
            {dash(row.original.confidence)}
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

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">
            테마 <span className="text-xs text-muted-foreground">(β)</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            증권사 리포트에서 추출된 테마와 영향 종목 연결.
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
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div
          role="radiogroup"
          aria-label="theme direction filter"
          className="inline-flex overflow-hidden rounded-md border border-border bg-card text-sm"
        >
          {DIRECTION_OPTIONS.map(opt => (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={direction === opt}
              data-testid={`theme-filter-${opt}`}
              onClick={() => setDirection(opt)}
              className={cn(
                'px-3 py-1.5 transition-colors',
                direction === opt
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
          placeholder="테마명 또는 카테고리 검색"
          aria-label="테마명 또는 카테고리 검색"
          data-testid="theme-search"
          className="w-72 rounded-md border border-border bg-card px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <span className="ml-auto text-xs text-muted-foreground">
          {rows.length}건 표시
        </span>
      </div>

      {query.isLoading && (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          테마 랭킹 로딩 중…
        </div>
      )}

      {query.isError && (
        <div
          data-testid="themes-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          테마 랭킹을 불러오지 못했습니다.
        </div>
      )}

      {!query.isLoading && !query.isError && rows.length === 0 && (
        <div
          data-testid="themes-empty"
          className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
        >
          {search.trim()
            ? `"${search}" 와 일치하는 테마가 없습니다.`
            : '아직 테마 데이터가 없습니다.'}
        </div>
      )}

      {!query.isLoading && !query.isError && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm" data-testid="themes-table">
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
