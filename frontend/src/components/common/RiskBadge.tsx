import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  LOW: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  MEDIUM: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  HIGH: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
}

interface RiskBadgeProps {
  level?: string | null
  flags?: string[]
  className?: string
  showFlags?: boolean
}

export function RiskBadge({ level, flags, className, showFlags = false }: RiskBadgeProps) {
  if (!level) {
    return (
      <span className={cn('text-xs text-muted-foreground', className)}>
        — risk N/A
      </span>
    )
  }
  const tone = TONE[level] ?? 'bg-muted text-muted-foreground'
  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      <span
        data-testid={`risk-${level}`}
        className={cn(
          'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
          tone,
        )}
      >
        {level}
      </span>
      {showFlags && flags && flags.length > 0 ? (
        <span className="text-xs text-muted-foreground">{flags.join(', ')}</span>
      ) : null}
    </span>
  )
}
