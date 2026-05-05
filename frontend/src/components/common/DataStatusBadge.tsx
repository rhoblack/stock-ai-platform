import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  SUCCESS: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  PARTIAL: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  RUNNING: 'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  FAILED: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  NO_DATA: 'bg-muted text-muted-foreground',
  DRY_RUN: 'bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200',
  DISABLED: 'bg-muted text-muted-foreground',
}

interface DataStatusBadgeProps {
  status: string | null | undefined
  variant?: 'job' | 'data' | 'notification'
  className?: string
}

export function DataStatusBadge({ status, variant = 'job', className }: DataStatusBadgeProps) {
  const value = status ?? 'UNKNOWN'
  const tone = TONE[value] ?? 'bg-muted text-muted-foreground'
  return (
    <span
      data-testid={`status-${variant}-${value}`}
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        tone,
        className,
      )}
    >
      {value}
    </span>
  )
}
