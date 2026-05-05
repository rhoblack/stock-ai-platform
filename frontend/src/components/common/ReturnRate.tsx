import { cn } from '@/lib/utils'

interface ReturnRateProps {
  // 백엔드는 Decimal 을 문자열로 직렬화한다 (예: "-7.1429"). 여기서 Number()
  // 변환 + 4 자리 절단. 입력이 null / undefined / 빈 문자열이면 placeholder.
  value: string | number | null | undefined
  className?: string
  precision?: number
  withSign?: boolean
  unit?: string
}

export function ReturnRate({
  value,
  className,
  precision = 2,
  withSign = true,
  unit = '%',
}: ReturnRateProps) {
  if (value === null || value === undefined || value === '') {
    return <span className={cn('text-muted-foreground tabular-nums', className)}>—</span>
  }
  const num = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(num)) {
    return <span className={cn('text-muted-foreground tabular-nums', className)}>—</span>
  }
  const formatted = num.toFixed(precision)
  const tone =
    num > 0
      ? 'text-emerald-600 dark:text-emerald-400'
      : num < 0
        ? 'text-red-600 dark:text-red-400'
        : 'text-muted-foreground'
  const sign = withSign && num > 0 ? '+' : ''
  return (
    <span
      data-testid="return-rate"
      className={cn('tabular-nums font-medium', tone, className)}
    >
      {sign}
      {formatted}
      {unit}
    </span>
  )
}
