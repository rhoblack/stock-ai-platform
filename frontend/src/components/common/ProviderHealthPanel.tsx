// v0.10 Phase D / v0.11 Phase D — Provider Health read-only panel.
//
// Renders the GET /api/health/providers snapshot inside the Settings
// page (or wherever it is mounted).  Read-only — no enable/disable
// toggle, no API-key field.  All secret discipline is upstream: the
// backend never echoes API keys / URL query secrets / last_error_message,
// so this component just displays what arrives.
//
// v0.11 Phase D: surfaces rolling-24h aggregates (success rate +
// avg attempts) and the most recent five failure entries per provider.

import { useProviderHealth } from '@/hooks/useProviderHealth'
import { cn } from '@/lib/utils'
import type {
  ProviderCircuitState,
  ProviderHealthItem,
  RecentFailureSummary,
} from '@/api/types'

const STATE_BADGE: Record<
  ProviderCircuitState,
  { label: string; className: string }
> = {
  CLOSED: {
    label: 'CLOSED',
    className:
      'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  },
  HALF_OPEN: {
    label: 'HALF_OPEN',
    className:
      'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  },
  OPEN: {
    label: 'OPEN',
    className: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  },
  UNREGISTERED: {
    label: 'UNREGISTERED',
    className:
      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  },
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return '—'
  return `${(rate * 100).toFixed(1)}%`
}

function formatAvgAttempts(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(2)
}

/**
 * success_rate_24h colour band:
 *   ≥ 99%   emerald (healthy)
 *   ≥ 95%   amber   (degraded)
 *   < 95%   red     (alert)
 *   null    slate   (no data in window)
 */
function successRateClass(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) {
    return 'bg-slate-200 dark:bg-slate-700'
  }
  if (rate >= 0.99) return 'bg-emerald-500'
  if (rate >= 0.95) return 'bg-amber-500'
  return 'bg-red-500'
}

function SuccessRateBar({
  item,
}: {
  item: ProviderHealthItem
}) {
  const rate = item.success_rate_24h
  const widthPct =
    rate === null || rate === undefined ? 0 : Math.max(0, Math.min(1, rate)) * 100
  return (
    <div
      data-testid={`provider-success-rate-${item.provider_name}`}
      data-rate={rate ?? ''}
      className="flex flex-col gap-1"
    >
      <span className="font-mono text-xs tabular-nums">
        {formatPercent(rate)}
      </span>
      <div
        aria-hidden
        className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700"
      >
        <div
          className={cn('h-full transition-all', successRateClass(rate))}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  )
}

function RecentFailuresList({
  item,
}: {
  item: ProviderHealthItem
}) {
  const failures: RecentFailureSummary[] = item.recent_failures ?? []
  if (failures.length === 0) {
    return (
      <div
        data-testid={`provider-recent-failures-${item.provider_name}-empty`}
        className="text-xs text-muted-foreground"
      >
        최근 24시간 동안 실패 기록 없음
      </div>
    )
  }
  return (
    <ul
      data-testid={`provider-recent-failures-${item.provider_name}`}
      className="flex flex-col gap-1"
    >
      {failures.map((failure, idx) => (
        <li
          key={`${failure.timestamp}-${idx}`}
          data-testid={`provider-recent-failure-${item.provider_name}-${idx}`}
          className="flex items-center gap-2 text-xs"
        >
          <span className="inline-flex items-center rounded-md bg-red-50 px-2 py-0.5 font-mono font-medium text-red-900 dark:bg-red-900/20 dark:text-red-200">
            {failure.error_kind}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
            {formatTimestamp(failure.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  )
}

function ProviderRecentFailuresSection({
  items,
}: {
  items: ProviderHealthItem[]
}) {
  // Render a per-provider mini-card only for providers that have at
  // least one recorded failure -- the table itself already shows zero-
  // failure providers via the fail counter.
  const withFailures = items.filter(
    (item) => (item.recent_failures ?? []).length > 0,
  )
  if (withFailures.length === 0) {
    return null
  }
  return (
    <section
      data-testid="provider-recent-failures-section"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <header className="flex items-baseline justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          최근 실패 (last 5)
        </h4>
        <span className="text-[11px] text-muted-foreground">
          timestamp + error_kind 만 노출 — message text 0건
        </span>
      </header>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {withFailures.map((item) => (
          <div
            key={item.provider_name}
            data-testid={`provider-recent-failures-card-${item.provider_name}`}
            className="flex flex-col gap-2"
          >
            <span className="text-xs font-medium uppercase tracking-wide">
              {item.provider_name}
            </span>
            <RecentFailuresList item={item} />
          </div>
        ))}
      </div>
    </section>
  )
}

function ProviderRow({ item }: { item: ProviderHealthItem }) {
  const state = STATE_BADGE[item.circuit_state] ?? STATE_BADGE.UNREGISTERED
  const enabledLabel = item.enabled ? 'enabled' : 'disabled'
  const configuredLabel = item.configured ? 'configured' : 'not_configured'
  return (
    <tr
      data-testid={`provider-row-${item.provider_name}`}
      data-enabled={item.enabled ? 'true' : 'false'}
      data-configured={item.configured ? 'true' : 'false'}
      data-state={item.circuit_state}
      className="border-b border-border last:border-b-0"
    >
      <td className="px-3 py-2 text-sm font-medium uppercase tracking-wide">
        {item.provider_name}
      </td>
      <td className="px-3 py-2 text-xs">
        <span
          data-testid={`provider-enabled-${item.provider_name}`}
          className={cn(
            'inline-flex items-center rounded-md px-2 py-0.5 font-mono font-medium',
            item.enabled
              ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200'
              : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
          )}
        >
          {enabledLabel}
        </span>
      </td>
      <td className="px-3 py-2 text-xs">
        <span
          data-testid={`provider-configured-${item.provider_name}`}
          className={cn(
            'inline-flex items-center rounded-md px-2 py-0.5 font-mono font-medium',
            item.configured
              ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200'
              : item.enabled
                ? 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200'
                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
          )}
        >
          {configuredLabel}
        </span>
      </td>
      <td className="px-3 py-2 text-xs">
        <span
          data-testid={`provider-state-${item.provider_name}`}
          className={cn(
            'inline-flex items-center rounded-md px-2 py-0.5 font-mono font-medium',
            state.className,
          )}
        >
          {state.label}
        </span>
      </td>
      <td className="px-3 py-2 text-right text-sm font-mono tabular-nums">
        {item.call_count}
      </td>
      <td className="px-3 py-2 text-right text-sm font-mono tabular-nums text-emerald-700 dark:text-emerald-300">
        {item.success_count}
      </td>
      <td className="px-3 py-2 text-right text-sm font-mono tabular-nums text-red-700 dark:text-red-300">
        {item.failure_count}
      </td>
      <td className="px-3 py-2">
        <SuccessRateBar item={item} />
      </td>
      <td
        data-testid={`provider-avg-attempts-${item.provider_name}`}
        className="px-3 py-2 text-right text-xs font-mono tabular-nums text-muted-foreground"
      >
        {formatAvgAttempts(item.avg_attempts_24h)}
      </td>
      <td className="px-3 py-2 text-xs">
        {item.last_error_kind ? (
          <span
            data-testid={`provider-last-error-${item.provider_name}`}
            className="inline-flex items-center rounded-md bg-red-50 px-2 py-0.5 font-mono font-medium text-red-900 dark:bg-red-900/20 dark:text-red-200"
          >
            {item.last_error_kind}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground">
        {formatTimestamp(item.last_called_at)}
      </td>
    </tr>
  )
}

export function ProviderHealthPanel() {
  const { data, isLoading, isError } = useProviderHealth()

  return (
    <section
      data-testid="provider-health-panel"
      className="flex flex-col gap-2"
    >
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Provider Health (read-only)
        </h3>
        <span className="text-xs text-muted-foreground">
          GET /api/health/providers — in-memory, 프로세스 재시작 시 초기화
        </span>
      </header>
      <p className="text-xs text-muted-foreground">
        provider 상태는 read-only 입니다. enable / disable 은 .env 수정 후
        백엔드 재시작으로만 변경됩니다. API key / token / feed URL query
        secret 은 응답에 포함되지 않습니다.
      </p>

      {isLoading && (
        <div
          data-testid="provider-health-loading"
          className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
        >
          provider 상태 로딩 중…
        </div>
      )}

      {isError && (
        <div
          data-testid="provider-health-error"
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          provider 상태를 불러오지 못했습니다.
        </div>
      )}

      {data && data.items.length === 0 && (
        <div
          data-testid="provider-health-empty"
          className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
        >
          등록된 provider 가 없습니다.
        </div>
      )}

      {data && data.items.length > 0 && (
        <div
          data-testid="provider-health-table-wrap"
          className="overflow-hidden rounded-lg border border-border bg-card"
        >
          <table
            data-testid="provider-health-table"
            className="w-full text-left"
          >
            <thead className="bg-muted/40">
              <tr className="text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2">provider</th>
                <th className="px-3 py-2">enabled</th>
                <th className="px-3 py-2">configured</th>
                <th className="px-3 py-2">circuit</th>
                <th className="px-3 py-2 text-right">calls</th>
                <th className="px-3 py-2 text-right">ok</th>
                <th className="px-3 py-2 text-right">fail</th>
                <th className="px-3 py-2">success_24h</th>
                <th className="px-3 py-2 text-right">avg_attempts</th>
                <th className="px-3 py-2">last_error</th>
                <th className="px-3 py-2">last_called_at</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <ProviderRow key={item.provider_name} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.items.length > 0 && (
        <ProviderRecentFailuresSection items={data.items} />
      )}
    </section>
  )
}
