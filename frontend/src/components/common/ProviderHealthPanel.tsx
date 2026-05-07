// v0.10 Phase D — Provider Health read-only panel.
//
// Renders the GET /api/health/providers snapshot inside the Settings
// page (or wherever it is mounted).  Read-only — no enable/disable
// toggle, no API-key field.  All secret discipline is upstream: the
// backend never echoes API keys / URL query secrets / last_error_message,
// so this component just displays what arrives.

import { useProviderHealth } from '@/hooks/useProviderHealth'
import { cn } from '@/lib/utils'
import type {
  ProviderCircuitState,
  ProviderHealthItem,
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
    </section>
  )
}
