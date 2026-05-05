import { Link, useNavigate, useParams } from 'react-router-dom'
import { useThemeDetail } from '@/hooks/useThemeDetail'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { cn } from '@/lib/utils'
import type {
  ReportSignalEvent,
  ThemeDetailResponse,
  ThemeStockMapping,
} from '@/api/types'

function dash(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function ImpactBadge({
  direction,
  impactPath,
}: {
  direction: string
  impactPath: string | null | undefined
}) {
  return (
    <span className="flex flex-wrap items-center gap-1">
      <span
        className={cn(
          'rounded-md px-2 py-0.5 text-[11px]',
          direction === 'POSITIVE' &&
            'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
          direction === 'NEGATIVE' &&
            'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
          direction === 'NEUTRAL' && 'bg-muted text-muted-foreground',
        )}
      >
        {direction}
      </span>
      {impactPath ? (
        <span className="rounded-md border border-border bg-muted/30 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
          {impactPath}
        </span>
      ) : null}
    </span>
  )
}

export function ThemeDetailPage() {
  const navigate = useNavigate()
  const { themeId } = useParams<{ themeId: string }>()
  const numeric = themeId ? Number(themeId) : null
  const idValid = numeric !== null && Number.isFinite(numeric) && numeric > 0

  const detail = useThemeDetail(idValid ? numeric : null)

  if (!idValid) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">테마 상세</h2>
        <div className="rounded-lg border border-dashed border-border bg-card p-6 text-sm text-muted-foreground">
          테마 ID 가 지정되지 않았습니다. <code>/themes</code> 에서 테마를 선택하세요.
        </div>
      </section>
    )
  }

  if (detail.isLoading) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">테마 상세 — #{themeId}</h2>
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          테마 상세 로딩 중…
        </div>
      </section>
    )
  }

  if (detail.isError) {
    return (
      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">테마 상세 — #{themeId}</h2>
        <div
          data-testid="theme-detail-error"
          className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
        >
          테마를 찾을 수 없거나 응답에 실패했습니다.
        </div>
        <button
          type="button"
          className="self-start rounded-md border border-border bg-card px-3 py-1.5 text-xs hover:bg-accent"
          onClick={() => navigate('/themes')}
        >
          테마 목록으로 돌아가기
        </button>
      </section>
    )
  }

  return <ThemeDetailContent data={detail.data!} />
}

function ThemeDetailContent({ data }: { data: ThemeDetailResponse }) {
  const { theme, stock_mappings, signal_events } = data
  return (
    <section className="flex flex-col gap-4" data-testid="theme-detail">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">
            {theme.theme_name}{' '}
            <span className="text-muted-foreground">#{theme.theme_id}</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            {theme.theme_category} · {theme.direction} / {theme.time_horizon}
          </p>
        </div>
        <Link
          to="/themes"
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          ← 테마 목록
        </Link>
      </header>

      <section
        data-testid="theme-detail-summary"
        className="rounded-lg border border-border bg-card p-4"
      >
        <h3 className="mb-2 text-sm font-semibold">개요</h3>
        <KeyValueGrid
          columns={3}
          rows={[
            { label: 'theme_id', value: theme.theme_id },
            { label: 'category', value: theme.theme_category },
            { label: 'direction', value: theme.direction },
            { label: 'time_horizon', value: theme.time_horizon },
            { label: 'confidence', value: dash(theme.confidence) },
            { label: 'source_report_id', value: theme.source_report_id },
            { label: 'mapping_count', value: theme.mapping_count },
            { label: 'signal_event_count', value: theme.signal_event_count },
          ]}
        />
        {theme.summary ? (
          <p className="mt-3 text-sm text-muted-foreground">{theme.summary}</p>
        ) : null}
      </section>

      <StockMappingsCard mappings={stock_mappings} />
      <SignalEventsCard events={signal_events} />
    </section>
  )
}

function StockMappingsCard({ mappings }: { mappings: ThemeStockMapping[] }) {
  return (
    <section
      data-testid="theme-detail-mappings"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">
          영향 종목 ({mappings.length})
        </h3>
      </header>
      {mappings.length === 0 ? (
        <p
          data-testid="theme-detail-mappings-empty"
          className="text-sm text-muted-foreground"
        >
          연결된 종목이 없습니다.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {mappings.map(m => (
            <article
              key={m.mapping_id}
              data-testid={`theme-mapping-${m.mapping_id}`}
              className="rounded-md border border-border bg-muted/20 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/stocks/${m.symbol}`}
                  className="text-sm font-medium hover:underline"
                >
                  {m.company_name ?? m.symbol}
                </Link>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {m.symbol}
                </span>
                {m.market ? (
                  <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    {m.market}
                  </span>
                ) : null}
                <ImpactBadge
                  direction={m.impact_direction}
                  impactPath={m.impact_path}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                strength {dash(m.impact_strength)} · benefit {dash(m.benefit_type)}
                {' · '}
                lag {dash(m.time_lag)}
                {' · '}
                relation {dash(m.relation_type)}
              </p>
              {m.reason ? (
                <p className="mt-1 text-xs text-muted-foreground">{m.reason}</p>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function SignalEventsCard({ events }: { events: ReportSignalEvent[] }) {
  return (
    <section
      data-testid="theme-detail-signals"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">시그널 이벤트 ({events.length})</h3>
      </header>
      {events.length === 0 ? (
        <p
          data-testid="theme-detail-signals-empty"
          className="text-sm text-muted-foreground"
        >
          연결된 시그널 이벤트가 없습니다.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">event</th>
                <th className="px-2 py-1 font-medium">direction</th>
                <th className="px-2 py-1 font-medium">strength</th>
                <th className="px-2 py-1 font-medium">symbol</th>
                <th className="px-2 py-1 font-medium">summary</th>
              </tr>
            </thead>
            <tbody>
              {events.map(event => (
                <tr
                  key={event.id}
                  data-testid={`theme-detail-signal-${event.id}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-mono">{event.event_type}</td>
                  <td className="px-2 py-1">{event.direction}</td>
                  <td className="px-2 py-1 font-mono">{dash(event.strength)}</td>
                  <td className="px-2 py-1 font-mono">
                    {event.symbol ? (
                      <Link
                        to={`/stocks/${event.symbol}`}
                        className="hover:underline"
                      >
                        {event.symbol}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-2 py-1 text-muted-foreground">
                    {dash(event.summary)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
