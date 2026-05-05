import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import type { JobRun, JobResultSummaryKeys } from '@/api/types'
import { DataStatusBadge } from '@/components/common/DataStatusBadge'
import { cn } from '@/lib/utils'

interface JobsTableProps {
  rows: JobRun[]
}

function readSummaryKeys(row: JobRun): JobResultSummaryKeys {
  return (row.result_summary ?? {}) as JobResultSummaryKeys
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return value
    return d.toLocaleString('ko-KR', { hour12: false })
  } catch {
    return value
  }
}

export function JobsTable({ rows }: JobsTableProps) {
  const navigate = useNavigate()
  const { jobId } = useParams<{ jobId: string }>()
  const selectedJobId = jobId ? Number(jobId) : null

  const columns = useMemo<ColumnDef<JobRun>[]>(
    () => [
      {
        accessorKey: 'job_id',
        header: '#',
        cell: ({ row }) => <span className="font-mono">{row.original.job_id}</span>,
      },
      {
        accessorKey: 'job_name',
        header: '잡 이름',
        cell: ({ row }) => (
          <span className="font-mono text-xs">{row.original.job_name}</span>
        ),
      },
      {
        id: 'status',
        header: 'status',
        cell: ({ row }) => (
          <DataStatusBadge status={row.original.status} variant="job" />
        ),
      },
      {
        id: 'data_status',
        header: 'data_status',
        cell: ({ row }) => {
          const s = readSummaryKeys(row.original).data_status
          return s ? <DataStatusBadge status={s} variant="data" /> : <span className="text-xs text-muted-foreground">—</span>
        },
      },
      {
        id: 'notification_status',
        header: 'notif',
        cell: ({ row }) => {
          const s = readSummaryKeys(row.original).notification_status
          return s ? (
            <DataStatusBadge status={s} variant="notification" />
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )
        },
      },
      {
        id: 'dry_run',
        header: 'dry_run',
        cell: ({ row }) => {
          const s = readSummaryKeys(row.original)
          if (s.dry_run === undefined) {
            return <span className="text-xs text-muted-foreground">—</span>
          }
          return (
            <span
              data-testid={`dry-run-${row.original.job_id}`}
              className={cn(
                'text-xs',
                s.dry_run ? 'text-violet-600 dark:text-violet-300' : 'text-muted-foreground',
              )}
            >
              {s.dry_run ? '✓ DRY' : '—'}
            </span>
          )
        },
      },
      {
        accessorKey: 'started_at',
        header: '시작',
        cell: ({ row }) => (
          <span className="font-mono text-xs">{formatTime(row.original.started_at)}</span>
        ),
      },
      {
        accessorKey: 'finished_at',
        header: '종료',
        cell: ({ row }) => (
          <span className="font-mono text-xs">{formatTime(row.original.finished_at)}</span>
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
        data-testid="jobs-empty"
        className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground"
      >
        조회된 잡이 없습니다.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
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
        <tbody data-testid="jobs-table-body">
          {table.getRowModel().rows.map(row => {
            const isActive = row.original.job_id === selectedJobId
            return (
              <tr
                key={row.id}
                data-testid={`job-row-${row.original.job_id}`}
                className={cn(
                  'cursor-pointer border-t border-border transition-colors hover:bg-accent',
                  isActive && 'bg-accent',
                )}
                onClick={() => navigate(`/jobs/${row.original.job_id}`)}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2 align-middle">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
