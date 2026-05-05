import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface KeyValueRow {
  label: string
  value: ReactNode
  hint?: ReactNode
}

interface KeyValueGridProps {
  rows: KeyValueRow[]
  columns?: 1 | 2 | 3
  className?: string
  testid?: string
}

const COL_CLASS: Record<NonNullable<KeyValueGridProps['columns']>, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3',
}

export function KeyValueGrid({
  rows,
  columns = 2,
  className,
  testid,
}: KeyValueGridProps) {
  if (rows.length === 0) {
    return (
      <p data-testid={testid} className={cn('text-sm text-muted-foreground', className)}>
        표시할 항목이 없습니다.
      </p>
    )
  }
  return (
    <dl
      data-testid={testid}
      className={cn(
        'grid gap-x-6 gap-y-2 rounded-md border border-border bg-card p-4',
        COL_CLASS[columns],
        className,
      )}
    >
      {rows.map(row => (
        <div key={row.label} className="flex flex-col gap-0.5">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {row.label}
          </dt>
          <dd className="text-sm font-medium tabular-nums">{row.value}</dd>
          {row.hint ? (
            <dd className="text-xs text-muted-foreground">{row.hint}</dd>
          ) : null}
        </div>
      ))}
    </dl>
  )
}
