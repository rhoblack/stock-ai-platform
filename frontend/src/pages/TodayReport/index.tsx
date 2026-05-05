import { Link } from 'react-router-dom'
import { useTodayReport } from '@/hooks/useTodayReport'
import { GradePill } from '@/components/common/GradePill'
import { RiskBadge } from '@/components/common/RiskBadge'
import { DecisionPill } from '@/components/common/DecisionPill'
import { ReturnRate } from '@/components/common/ReturnRate'
import { DataStatusBadge } from '@/components/common/DataStatusBadge'
import { MarketStatusBanner } from '@/components/common/MarketStatusBanner'
import type { HoldingCheck, RecommendationItem } from '@/api/types'

export function TodayReportPage() {
  const today = useTodayReport()

  if (today.isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
        오늘의 리포트 로딩 중…
      </div>
    )
  }

  if (today.isError) {
    return (
      <div
        data-testid="today-error"
        className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
      >
        오늘의 리포트를 불러오지 못했습니다.
      </div>
    )
  }

  if (!today.data) return null
  const { date, market_regime, latest_run, top_recommendations, holding_alerts } = today.data
  const highRiskAlerts = holding_alerts.filter(c => c.risk_level === 'HIGH' || c.alert)

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">오늘의 리포트</h2>
          <p className="text-sm text-muted-foreground">
            기준일 <span className="font-mono">{date}</span> · 60초마다 자동 새로고침
            {today.dataUpdatedAt > 0 && (
              <>
                {' '}
                <span className="font-mono text-xs">
                  (last fetch {new Date(today.dataUpdatedAt).toLocaleTimeString('ko-KR')})
                </span>
              </>
            )}
          </p>
        </div>
        {market_regime && (
          <div className="rounded-md border border-border bg-card px-3 py-2 text-xs">
            <div className="text-muted-foreground">시장 레짐 ({market_regime.market})</div>
            <div className="font-semibold">{market_regime.regime}</div>
          </div>
        )}
      </header>
      <MarketStatusBanner />


      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <RecommendationsCard items={top_recommendations} runDate={latest_run?.run_date} />
        <LatestRunCard latestRunStatus={latest_run?.status} telegramSent={latest_run?.telegram_sent} />
        <HoldingAlertsCard items={holding_alerts} />
        <HighRiskCard items={highRiskAlerts} />
      </div>
    </section>
  )
}

function RecommendationsCard({
  items,
  runDate,
}: {
  items: RecommendationItem[]
  runDate?: string | null
}) {
  return (
    <section
      data-testid="today-top-recs"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">추천 TOP {items.length}</h3>
        <Link to="/recommendations" className="text-xs text-muted-foreground hover:text-foreground">
          전체 →
        </Link>
      </header>
      {runDate && (
        <p className="text-xs text-muted-foreground">최근 run · {runDate}</p>
      )}
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">표시할 추천이 없습니다.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.map(rec => (
            <li
              key={`${rec.run_id}-${rec.symbol}`}
              data-testid={`today-rec-${rec.symbol}`}
              className="flex items-center gap-3 py-2"
            >
              <span className="w-6 text-center text-xs font-mono text-muted-foreground">
                #{rec.rank}
              </span>
              <GradePill grade={rec.grade} />
              <Link
                to={`/stocks/${rec.symbol}`}
                className="flex-1 truncate text-sm hover:underline"
              >
                <span className="font-medium">{rec.name}</span>{' '}
                <span className="text-muted-foreground">({rec.symbol})</span>
              </Link>
              <RiskBadge level={rec.risk_level} flags={rec.risk_flags} />
              <span className="w-16 text-right font-mono text-xs">
                {rec.total_score ?? '—'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function LatestRunCard({
  latestRunStatus,
  telegramSent,
}: {
  latestRunStatus?: string | null
  telegramSent?: boolean | null
}) {
  return (
    <section
      data-testid="today-latest-run"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">마지막 추천 run / 잡 상태</h3>
        <Link to="/jobs" className="text-xs text-muted-foreground hover:text-foreground">
          잡 보기 →
        </Link>
      </header>
      {latestRunStatus ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">run.status</dt>
          <dd>
            <DataStatusBadge status={latestRunStatus} variant="job" />
          </dd>
          <dt className="text-muted-foreground">telegram_sent</dt>
          <dd className="font-mono text-xs">
            {telegramSent === undefined || telegramSent === null
              ? '—'
              : telegramSent
                ? 'true'
                : 'false'}
          </dd>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">최근 run 정보가 없습니다.</p>
      )}
    </section>
  )
}

function HoldingAlertsCard({ items }: { items: HoldingCheck[] }) {
  return (
    <section
      data-testid="today-holding-alerts"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">보유 점검 알림 ({items.length})</h3>
        <Link to="/holdings" className="text-xs text-muted-foreground hover:text-foreground">
          전체 →
        </Link>
      </header>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">표시할 보유 점검이 없습니다.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.slice(0, 5).map(check => (
            <li
              key={check.id}
              data-testid={`today-holding-${check.symbol}`}
              className="flex items-center gap-3 py-2"
            >
              <span className="w-12 font-mono text-xs text-muted-foreground">
                {check.check_type}
              </span>
              <Link
                to={`/stocks/${check.symbol}`}
                className="flex-1 truncate text-sm hover:underline"
              >
                {check.symbol}
              </Link>
              <DecisionPill decision={check.decision} />
              <RiskBadge level={check.risk_level} />
              <ReturnRate value={check.return_rate} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function HighRiskCard({ items }: { items: HoldingCheck[] }) {
  return (
    <section
      data-testid="today-high-risk"
      className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">HIGH risk / 알림 강조 ({items.length})</h3>
      </header>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">HIGH risk 종목이 없습니다.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.slice(0, 5).map(check => (
            <li
              key={`hr-${check.id}`}
              data-testid={`today-high-risk-${check.symbol}`}
              className="flex flex-col gap-1 py-2"
            >
              <div className="flex items-center gap-2">
                <Link
                  to={`/stocks/${check.symbol}`}
                  className="text-sm font-medium hover:underline"
                >
                  {check.symbol}
                </Link>
                <RiskBadge level={check.risk_level} flags={check.risk_flags} showFlags />
              </div>
              {check.reason && (
                <p className="text-xs text-muted-foreground">{check.reason}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
