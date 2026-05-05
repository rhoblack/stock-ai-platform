import { Calendar, CheckCircle2, MinusCircle } from 'lucide-react'
import { useMemo } from 'react'
import {
  classifyMarketStatus,
  todayInSeoul,
  type MarketStatus,
} from '@/lib/marketCalendar'
import { cn } from '@/lib/utils'

interface MarketStatusBannerProps {
  /** 테스트 / 시점 freeze 용. 미지정 시 KST 기준 오늘. */
  date?: string
  className?: string
  testid?: string
}

/**
 * Today / Jobs / Holdings 화면 헤더 옆에 노출되는 시장 운영 상태 배너.
 * KRX 정적 휴장일 + 주말 판정 만으로 동작 — 외부 API 호출 0건.
 */
export function MarketStatusBanner({
  date,
  className,
  testid = 'market-status-banner',
}: MarketStatusBannerProps) {
  const today = date ?? todayInSeoul()
  const status = useMemo(() => classifyMarketStatus(today), [today])

  return (
    <div
      data-testid={testid}
      data-state={status.open ? 'open' : status.reason.toLowerCase()}
      className={cn(
        'flex items-start gap-2 rounded-md border px-3 py-2 text-xs',
        status.open
          ? 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-200'
          : status.reason === 'HOLIDAY'
            ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-200'
            : 'border-border bg-muted/50 text-muted-foreground',
        className,
      )}
    >
      <span aria-hidden className="mt-0.5">
        {status.open ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : status.reason === 'HOLIDAY' ? (
          <Calendar className="h-4 w-4" />
        ) : (
          <MinusCircle className="h-4 w-4" />
        )}
      </span>
      <div className="flex flex-col gap-0.5 leading-tight">
        <span className="font-semibold">{summaryHeadline(status)}</span>
        <span className="text-[11px] opacity-80">{summaryDetail(status)}</span>
      </div>
    </div>
  )
}

function summaryHeadline(status: MarketStatus): string {
  if (status.open) return `오늘은 영업일 (${status.date})`
  if (status.reason === 'HOLIDAY') {
    return `오늘은 한국 주식시장 휴장일 — ${status.holiday?.name ?? '휴장'}`
  }
  return `오늘은 주말 — 한국 주식시장 휴장`
}

function summaryDetail(status: MarketStatus): string {
  if (status.open) {
    return 'KRX 정규장 운영 중. 잡 / 추천 / 보유 점검이 정상적으로 자동 갱신됩니다.'
  }
  return `다음 영업일: ${status.nextOpen} · 잡 미실행은 휴장 때문일 수 있습니다.`
}
