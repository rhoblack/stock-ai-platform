import { Link } from 'react-router-dom'
import { KeyValueGrid } from '@/components/common/KeyValueGrid'
import { cn } from '@/lib/utils'
import type {
  AnalystReport,
  RelatedTheme,
  ReportConsensus,
  ReportSignalEvent,
  StockReportsResponse,
} from '@/api/types'

function dash(value: string | number | null | undefined) {
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function RatingDistribution({ consensus }: { consensus: ReportConsensus }) {
  const items = [
    ['Strong Buy', consensus.strong_buy_count],
    ['Buy', consensus.buy_count],
    ['Hold', consensus.hold_count],
    ['Sell', consensus.sell_count],
    ['Strong Sell', consensus.strong_sell_count],
  ]
  return (
    <div className="flex flex-wrap gap-1">
      {items.map(([label, value]) => (
        <span
          key={label}
          className="rounded-md border border-border bg-muted/30 px-2 py-1 font-mono text-[11px] text-muted-foreground"
        >
          {label}:{value}
        </span>
      ))}
    </div>
  )
}

function ConsensusCard({ consensus }: { consensus: ReportConsensus | null }) {
  if (!consensus) {
    return (
      <section
        data-testid="stock-detail-consensus-empty"
        className="rounded-lg border border-dashed border-border bg-card p-4 text-sm text-muted-foreground"
      >
        analyst consensus 데이터가 없습니다.
      </section>
    )
  }

  return (
    <section
      data-testid="stock-detail-consensus"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
    >
      <header>
        <h3 className="text-sm font-semibold">Analyst Consensus</h3>
        <p className="text-xs text-muted-foreground">
          snapshot {consensus.snapshot_date} · {consensus.window_days}d window
        </p>
      </header>
      <KeyValueGrid
        columns={3}
        rows={[
          { label: 'report_count', value: consensus.report_count },
          { label: 'avg_target_price', value: consensus.avg_target_price ?? '—' },
          { label: 'min_target_price', value: consensus.min_target_price ?? '—' },
          { label: 'max_target_price', value: consensus.max_target_price ?? '—' },
          {
            label: 'latest_published_at',
            value: consensus.latest_published_at ?? '—',
          },
        ]}
      />
      <RatingDistribution consensus={consensus} />
    </section>
  )
}

function RecentReportsCard({ reports }: { reports: AnalystReport[] }) {
  return (
    <section
      data-testid="stock-detail-analyst-reports"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Recent Reports ({reports.length})</h3>
      </header>
      {reports.length === 0 ? (
        <p
          data-testid="stock-detail-analyst-reports-empty"
          className="text-sm text-muted-foreground"
        >
          표시할 리포트가 없습니다.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">published</th>
                <th className="px-2 py-1 font-medium">broker</th>
                <th className="px-2 py-1 font-medium">title</th>
                <th className="px-2 py-1 font-medium">rating</th>
                <th className="px-2 py-1 font-medium">target</th>
                <th className="px-2 py-1 font-medium">summary</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(report => (
                <tr
                  key={report.id}
                  data-testid={`stock-detail-report-${report.id}`}
                  className="border-t border-border align-top"
                >
                  <td className="px-2 py-1 font-mono">{report.published_at}</td>
                  <td className="px-2 py-1">{report.broker_name}</td>
                  <td className="px-2 py-1 font-medium">
                    {report.source_url ? (
                      <a
                        href={report.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:underline"
                      >
                        {report.title}
                      </a>
                    ) : (
                      report.title
                    )}
                  </td>
                  <td className="px-2 py-1">{dash(report.rating)}</td>
                  <td className="px-2 py-1 font-mono">{dash(report.target_price)}</td>
                  <td className="px-2 py-1 text-muted-foreground">
                    {dash(report.summary)}
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

function RelatedThemesCard({ themes }: { themes: RelatedTheme[] }) {
  return (
    <section
      data-testid="stock-detail-related-themes"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Related Themes ({themes.length})</h3>
      </header>
      {themes.length === 0 ? (
        <p
          data-testid="stock-detail-related-themes-empty"
          className="text-sm text-muted-foreground"
        >
          연결된 테마가 없습니다.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          {themes.map(theme => (
            <article
              key={theme.mapping_id}
              data-testid={`stock-detail-theme-${theme.mapping_id}`}
              className="rounded-md border border-border bg-muted/20 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/themes/${theme.theme_id}`}
                  data-testid={`stock-detail-theme-link-${theme.theme_id}`}
                  className="text-sm font-medium hover:underline"
                >
                  {theme.theme_name}
                </Link>
                <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                  {theme.theme_category}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {theme.direction}/{theme.time_horizon}
                </span>
                <span
                  className={cn(
                    'rounded-md px-2 py-0.5 text-[11px]',
                    theme.impact_direction === 'POSITIVE' &&
                      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
                    theme.impact_direction === 'NEGATIVE' &&
                      'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
                    !['POSITIVE', 'NEGATIVE'].includes(theme.impact_direction) &&
                      'bg-muted text-muted-foreground',
                  )}
                >
                  {theme.impact_direction}
                </span>
                {theme.impact_path ? (
                  <span
                    data-testid={`stock-detail-theme-impact-${theme.mapping_id}`}
                    className="rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                  >
                    {theme.impact_path}
                  </span>
                ) : null}
              </div>
              {theme.reason ? (
                <p className="mt-1 text-xs text-muted-foreground">{theme.reason}</p>
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
      data-testid="stock-detail-signal-events"
      className="rounded-lg border border-border bg-card p-4"
    >
      <header className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Signal Events ({events.length})</h3>
      </header>
      {events.length === 0 ? (
        <p
          data-testid="stock-detail-signal-events-empty"
          className="text-sm text-muted-foreground"
        >
          표시할 시그널 이벤트가 없습니다.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-left uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-1 font-medium">event</th>
                <th className="px-2 py-1 font-medium">direction</th>
                <th className="px-2 py-1 font-medium">strength</th>
                <th className="px-2 py-1 font-medium">summary</th>
              </tr>
            </thead>
            <tbody>
              {events.map(event => (
                <tr
                  key={event.id}
                  data-testid={`stock-detail-signal-${event.id}`}
                  className="border-t border-border"
                >
                  <td className="px-2 py-1 font-mono">{event.event_type}</td>
                  <td className="px-2 py-1">{event.direction}</td>
                  <td className="px-2 py-1 font-mono">{dash(event.strength)}</td>
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

export function AnalystReportsCard({
  data,
}: {
  data: StockReportsResponse | null | undefined
}) {
  const safe = data ?? {
    symbol: '',
    latest_consensus: null,
    recent_reports: [],
    related_themes: [],
    recent_signal_events: [],
  }

  return (
    <section data-testid="stock-detail-analyst-section" className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ConsensusCard consensus={safe.latest_consensus} />
        <RecentReportsCard reports={safe.recent_reports} />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <RelatedThemesCard themes={safe.related_themes} />
        <SignalEventsCard events={safe.recent_signal_events} />
      </div>
    </section>
  )
}
