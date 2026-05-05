// 한국거래소 (KRX) 시장 운영 상태 판정 유틸. 정적 휴장일 데이터
// (`@/data/krxHolidays`) 와 KST(Asia/Seoul) 기준 요일 / 날짜 계산만 사용한다.
// 외부 API / 백엔드 호출 0건.
//
// 모든 함수는 ISO 날짜 문자열 (`YYYY-MM-DD`) 또는 `Date` 객체를 받고
// ISO 날짜 문자열 또는 `MarketStatus` 를 반환한다. UTC parse 후 일자
// 연산만 하므로 timezone 오프셋 누락 (e.g., `Date('2026-01-01')` 의 로컬
// 해석) 으로 인한 오프바이원이 발생하지 않는다.

import { KRX_HOLIDAYS, type KrxHoliday } from '@/data/krxHolidays'

const HOLIDAY_INDEX: ReadonlyMap<string, KrxHoliday> = new Map(
  KRX_HOLIDAYS.map(h => [h.date, h]),
)

/** Asia/Seoul 기준 오늘 (`YYYY-MM-DD`). 테스트는 `now` 를 주입해 결정론적. */
export function todayInSeoul(now: Date = new Date()): string {
  // `en-CA` 로케일은 ISO 형식 (YYYY-MM-DD) 을 그대로 출력한다.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
}

/** ISO 날짜 → UTC midnight Date (요일 / 일자 산술 전용). */
function parseIsoUtc(date: string): Date {
  const [y, m, d] = date.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

/** UTC midnight Date → ISO 날짜 문자열. */
function formatIso(date: Date): string {
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** ISO 날짜의 KST 요일 (0=일, 1=월, …, 6=토). UTC midnight 의 요일은 KST 와 같다. */
export function dayOfWeek(date: string): number {
  return parseIsoUtc(date).getUTCDay()
}

export function isWeekend(date: string): boolean {
  const dow = dayOfWeek(date)
  return dow === 0 || dow === 6
}

/** 해당 일자가 KRX 휴장일이면 메타를 반환, 아니면 undefined. */
export function getHoliday(date: string): KrxHoliday | undefined {
  return HOLIDAY_INDEX.get(date)
}

export function isHoliday(date: string): boolean {
  return HOLIDAY_INDEX.has(date)
}

export function isMarketClosed(date: string): boolean {
  return isWeekend(date) || isHoliday(date)
}

export function isMarketOpen(date: string): boolean {
  return !isMarketClosed(date)
}

/** ISO 날짜에 days 일을 더한 새 ISO 날짜 (UTC 기준). */
function addDays(date: string, days: number): string {
  const d = parseIsoUtc(date)
  d.setUTCDate(d.getUTCDate() + days)
  return formatIso(d)
}

/**
 * 다음 영업일을 반환한다 (`date` 다음 날부터 검색).
 *
 * 무한 루프 방지를 위해 최대 30일까지만 검색한다 — 한국 시장은 최장
 * 추석/설 + 주말이 겹쳐도 7~8일 휴장. 30일을 넘기면 데이터 갱신이
 * 누락되었다는 신호로 보고 throw 한다.
 */
export function nextOpenDay(date: string, maxScan: number = 30): string {
  let cursor = addDays(date, 1)
  for (let i = 0; i < maxScan; i++) {
    if (isMarketOpen(cursor)) return cursor
    cursor = addDays(cursor, 1)
  }
  throw new Error(
    `nextOpenDay: ${maxScan}일 내에 영업일을 찾지 못함 (${date}부터). KRX_HOLIDAYS 갱신을 확인하세요.`,
  )
}

/** 이전 영업일 (`date` 이전 날부터 검색). */
export function previousOpenDay(date: string, maxScan: number = 30): string {
  let cursor = addDays(date, -1)
  for (let i = 0; i < maxScan; i++) {
    if (isMarketOpen(cursor)) return cursor
    cursor = addDays(cursor, -1)
  }
  throw new Error(
    `previousOpenDay: ${maxScan}일 내에 영업일을 찾지 못함 (${date}부터).`,
  )
}

export type MarketStatus =
  | { open: true; date: string; nextClose: string | null }
  | {
      open: false
      date: string
      reason: 'WEEKEND' | 'HOLIDAY'
      holiday?: KrxHoliday
      nextOpen: string
    }

export function classifyMarketStatus(date: string): MarketStatus {
  const holiday = getHoliday(date)
  if (holiday) {
    return {
      open: false,
      date,
      reason: 'HOLIDAY',
      holiday,
      nextOpen: nextOpenDay(date),
    }
  }
  if (isWeekend(date)) {
    return {
      open: false,
      date,
      reason: 'WEEKEND',
      nextOpen: nextOpenDay(date),
    }
  }
  return { open: true, date, nextClose: null }
}
