import { cn } from '@/lib/utils'

const TONE: Record<string, string> = {
  S: 'bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200',
  A: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  B: 'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  C: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  D: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
}

interface GradePillProps {
  grade: string | null | undefined
  className?: string
}

export function GradePill({ grade, className }: GradePillProps) {
  if (!grade) {
    return <span className={cn('text-xs text-muted-foreground', className)}>—</span>
  }
  const tone = TONE[grade] ?? 'bg-muted text-muted-foreground'
  return (
    <span
      data-testid={`grade-${grade}`}
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded-md text-xs font-bold',
        tone,
        className,
      )}
    >
      {grade}
    </span>
  )
}
