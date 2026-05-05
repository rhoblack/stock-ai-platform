import { cn } from '@/lib/utils'

const LABEL: Record<string, string> = {
  HOLD: '보유 유지',
  WATCH: '관찰',
  REDUCE: '비중 축소',
  SELL_REVIEW: '매도 검토',
}

const TONE: Record<string, string> = {
  HOLD: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  WATCH: 'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  REDUCE: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  SELL_REVIEW: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
}

interface DecisionPillProps {
  decision: string | null | undefined
  className?: string
}

export function DecisionPill({ decision, className }: DecisionPillProps) {
  if (!decision) {
    return <span className={cn('text-xs text-muted-foreground', className)}>—</span>
  }
  const tone = TONE[decision] ?? 'bg-muted text-muted-foreground'
  const label = LABEL[decision] ?? decision
  return (
    <span
      data-testid={`decision-${decision}`}
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        tone,
        className,
      )}
      title={decision}
    >
      {label}
    </span>
  )
}
