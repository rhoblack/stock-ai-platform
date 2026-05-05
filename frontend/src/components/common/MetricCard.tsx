import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'neutral' | 'positive' | 'negative' | 'warning'
  className?: string
  testid?: string
}

const TONE_BORDER: Record<NonNullable<MetricCardProps['tone']>, string> = {
  neutral: 'border-border',
  positive: 'border-emerald-200 dark:border-emerald-900/40',
  negative: 'border-red-200 dark:border-red-900/40',
  warning: 'border-amber-200 dark:border-amber-900/40',
}

export function MetricCard({
  label,
  value,
  hint,
  tone = 'neutral',
  className,
  testid,
}: MetricCardProps) {
  return (
    <div
      data-testid={testid}
      className={cn(
        'flex flex-col gap-1 rounded-lg border bg-card p-4',
        TONE_BORDER[tone],
        className,
      )}
    >
      <span className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-xl font-semibold tabular-nums">{value}</span>
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </div>
  )
}
