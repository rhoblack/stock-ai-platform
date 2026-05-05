import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import type { RecommendationItem, RecommendationResult } from '@/api/types'
import { GradePill } from '@/components/common/GradePill'
import { RiskBadge } from '@/components/common/RiskBadge'
import { ReturnRate } from '@/components/common/ReturnRate'

interface RecommendationsTableProps {
  rows: RecommendationItem[]
}

const DAYS_AFTER: Array<1 | 3 | 5 | 20> = [1, 3, 5, 20]

function findResult(
  results: RecommendationResult[] | undefined,
  daysAfter: number,
): RecommendationResult | undefined {
  return results?.find(r => r.days_after === daysAfter)
}

function evidenceSummary(evidence: Record<string, unknown> | null | undefined) {
  if (!evidence) return '—'
  const reportAdj = evidence.report_score_adjustment
  const themeAdj = evidence.theme_signal_adjustment
  const topThemes = Array.isArray(evidence.top_themes)
    ? evidence.top_themes
        .map(item =>
          item && typeof item === 'object' && 'theme_name' in item
            ? String((item as { theme_name?: unknown }).theme_name ?? '')
            : '',
        )
        .filter(Boolean)
        .slice(0, 2)
    : []
  const parts = [
    reportAdj ? `report ${reportAdj}` : null,
    themeAdj ? `theme ${themeAdj}` : null,
    topThemes.length > 0 ? topThemes.join(', ') : null,
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : '—'
}

export function RecommendationsTable({ rows }: RecommendationsTableProps) {
  const columns = useMemo<ColumnDef<RecommendationItem>[]>(
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
        accessorKey: 'grade',
        header: '등급',
        cell: ({ row }) => <GradePill grade={row.original.grade} />,
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
            data-testid={`rec-row-${row.original.symbol}`}
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
        accessorKey: 'total_score',
        header: 'total',
        cell: ({ row }) => (
          <span className="font-mono text-sm font-semibold tabular-nums">
            {row.original.total_score ?? '—'}
          </span>
        ),
      },
      {
        id: 'report_scores',
        header: 'report / theme',
        cell: ({ row }) => (
          <div className="flex flex-col gap-0.5 font-mono text-xs tabular-nums">
            <span data-testid={`rec-report-score-${row.original.symbol}`}>
              {row.original.report_score ?? '—'}
            </span>
            <span data-testid={`rec-theme-score-${row.original.symbol}`}>
              {row.original.theme_signal_score ?? '—'}
            </span>
          </div>
        ),
      },
      {
        id: 'report_evidence',
        header: 'report evidence',
        cell: ({ row }) => (
          <span
            data-testid={`rec-report-evidence-${row.original.symbol}`}
            className="text-xs text-muted-foreground"
          >
            {evidenceSummary(row.original.report_evidence)}
          </span>
        ),
      },
      {
        id: 'components',
        header: 'tech / news / sup / fund / ai',
        cell: ({ row }) => {
          const r = row.original
          return (
            <span className="font-mono text-xs tabular-nums text-muted-foreground">
              {r.technical_score ?? '—'} / {r.news_score ?? '—'} /{' '}
              {r.supply_score ?? '—'} / {r.fundamental_score ?? '—'} /{' '}
              {r.ai_score ?? '—'}
            </span>
          )
        },
      },
      {
        id: 'risk',
        header: 'risk',
        cell: ({ row }) => (
          <RiskBadge level={row.original.risk_level} flags={row.original.risk_flags} />
        ),
      },
      ...DAYS_AFTER.map(
        (n): ColumnDef<RecommendationItem> => ({
          id: `result_${n}d`,
          header: `${n}d close`,
          cell: ({ row }) => {
            const result = findResult(row.original.results, n)
            return (
              <ReturnRate
                value={result?.close_return ?? null}
                precision={2}
                withSign={true}
              />
            )
          },
        }),
      ),
      {
        accessorKey: 'reason',
        header: '사유',
        cell: ({ row }) => (
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="text-muted-foreground line-clamp-2">
              {row.original.reason ?? '—'}
            </span>
            {row.original.risk_note ? (
              <span className="text-muted-foreground/80 italic">
                {row.original.risk_note}
              </span>
            ) : null}
          </div>
        ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (rows.length === 0) {
    return (
      <div
        data-testid="recs-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        이 run 에 추천이 없습니다.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          {table.getHeaderGroups().map(group => (
            <tr key={group.id}>
              {group.headers.map(header => (
                <th key={header.id} className="px-3 py-2 font-medium">
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody data-testid="recs-table-body">
          {table.getRowModel().rows.map(row => (
            <tr key={row.id} className="border-t border-border align-top">
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-3 py-3">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
