import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useHoldings } from '@/hooks/useHoldings'
import { useLatestHoldingChecks } from '@/hooks/useLatestHoldingChecks'
import { MarketStatusBanner } from '@/components/common/MarketStatusBanner'
import { HoldingsList } from './HoldingsList'
import { HoldingTrendPanel } from './HoldingTrendPanel'
import type { HoldingCheck } from '@/api/types'

function buildLatestChecksBySymbol(items: HoldingCheck[]): Map<string, HoldingCheck> {
  const map = new Map<string, HoldingCheck>()
  for (const check of items) {
    const existing = map.get(check.symbol)
    if (!existing) {
      map.set(check.symbol, check)
      continue
    }
    // Pick the more recent one (by date, with POST_MARKET ranked after PRE_MARKET on same day).
    if (isLater(check, existing)) map.set(check.symbol, check)
  }
  return map
}

function isLater(a: HoldingCheck, b: HoldingCheck): boolean {
  if (a.check_date > b.check_date) return true
  if (a.check_date < b.check_date) return false
  const order = (t: string) => (t === 'POST_MARKET' ? 1 : 0)
  return order(a.check_type) > order(b.check_type)
}

export function HoldingsPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const holdings = useHoldings()
  const latestChecks = useLatestHoldingChecks()

  const checksMap = useMemo(
    () => buildLatestChecksBySymbol(latestChecks.data?.items ?? []),
    [latestChecks.data],
  )

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 className="text-2xl font-semibold">보유 종목 점검</h2>
        <p className="text-sm text-muted-foreground">
          활성 보유 종목 + 최신 점검(PRE/POST) 결합. 60초마다 자동 새로고침.
          {holdings.dataUpdatedAt > 0 && (
            <>
              {' '}
              <span className="font-mono text-xs">
                (last fetch{' '}
                {new Date(holdings.dataUpdatedAt).toLocaleTimeString('ko-KR')})
              </span>
            </>
          )}
        </p>
      </header>
      <MarketStatusBanner />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div data-testid="holdings-list-region">
          {holdings.isLoading && (
            <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
              보유 목록 로딩 중…
            </div>
          )}
          {holdings.isError && (
            <div
              data-testid="holdings-error"
              className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300"
            >
              보유 종목을 불러오지 못했습니다.
            </div>
          )}
          {holdings.isSuccess && (
            <HoldingsList
              holdings={holdings.data.items}
              latestChecksBySymbol={checksMap}
            />
          )}
          {latestChecks.isError && (
            <div
              data-testid="holdings-checks-warn"
              className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200"
            >
              최신 점검 정보를 불러오지 못했습니다 — 행에는 보유 정보만 노출됩니다.
            </div>
          )}
        </div>
        <HoldingTrendPanel symbol={symbol ?? null} />
      </div>
    </section>
  )
}
