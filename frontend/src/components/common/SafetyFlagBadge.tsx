import { cn } from '@/lib/utils'

interface SafetyFlagBadgeProps {
  /** v0.1 안전 플래그 — `true` 면 위험 상태 (실주문/자동매매 활성). v0.1 backend 동결 정책 상 항상 `false` 여야 한다. */
  enabled: boolean
  /** 의미 있는 플래그 이름 (예: feature_real_order_execution) */
  flag: string
  /** `true` 자체가 위험인 플래그 (대부분 v0.1 안전 플래그) vs `false` 가 위험인 플래그 (예: kis_use_paper) */
  dangerWhen?: 'true' | 'false'
  className?: string
}

export function SafetyFlagBadge({
  enabled,
  flag,
  dangerWhen = 'true',
  className,
}: SafetyFlagBadgeProps) {
  const isDanger =
    (dangerWhen === 'true' && enabled) || (dangerWhen === 'false' && !enabled)
  return (
    <span
      data-testid={`safety-${flag}`}
      data-danger={isDanger ? 'true' : 'false'}
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-mono font-medium',
        isDanger
          ? 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200'
          : 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
        className,
      )}
    >
      {enabled ? 'true' : 'false'}
      {isDanger ? <span className="ml-1">⚠</span> : null}
    </span>
  )
}
