import { describe, expect, it } from 'vitest'
import {
  classifyMarketStatus,
  dayOfWeek,
  getHoliday,
  isHoliday,
  isMarketClosed,
  isMarketOpen,
  isWeekend,
  nextOpenDay,
  previousOpenDay,
  todayInSeoul,
} from '@/lib/marketCalendar'

// 모든 날짜 reference: KST.

describe('marketCalendar — weekend / holiday / business day', () => {
  it('식별 — 주말 (토/일)', () => {
    // 2026-01-03 (Sat), 2026-01-04 (Sun)
    expect(dayOfWeek('2026-01-03')).toBe(6)
    expect(dayOfWeek('2026-01-04')).toBe(0)
    expect(isWeekend('2026-01-03')).toBe(true)
    expect(isWeekend('2026-01-04')).toBe(true)
    expect(isMarketClosed('2026-01-03')).toBe(true)
    expect(isMarketClosed('2026-01-04')).toBe(true)
  })

  it('식별 — 평일 영업일 (KRX 정규장)', () => {
    // 2026-06-15 Monday, no holiday near
    expect(isWeekend('2026-06-15')).toBe(false)
    expect(isHoliday('2026-06-15')).toBe(false)
    expect(isMarketOpen('2026-06-15')).toBe(true)
  })

  it('식별 — 한국거래소 휴장일 (신정)', () => {
    expect(isHoliday('2026-01-01')).toBe(true)
    expect(getHoliday('2026-01-01')?.name).toContain('신정')
    expect(isMarketClosed('2026-01-01')).toBe(true)
  })

  it('식별 — 한국거래소 휴장일 (어린이날)', () => {
    // 2026-05-05 Tue 어린이날
    expect(getHoliday('2026-05-05')?.category).toBe('fixed')
    expect(isMarketClosed('2026-05-05')).toBe(true)
  })

  it('식별 — 연말 폐장 (year-end)', () => {
    expect(getHoliday('2026-12-31')?.category).toBe('year-end')
    expect(isMarketClosed('2026-12-31')).toBe(true)
  })
})

describe('marketCalendar — nextOpenDay / previousOpenDay', () => {
  it('금요일 → 다음 영업일은 주말 건너뛰고 월요일', () => {
    // 2026-06-19 Fri → 2026-06-22 Mon
    expect(nextOpenDay('2026-06-19')).toBe('2026-06-22')
  })

  it('휴장일 (신정) → 다음 영업일', () => {
    // 2026-01-01 Thu 신정 → 2026-01-02 Fri
    expect(nextOpenDay('2026-01-01')).toBe('2026-01-02')
  })

  it('연말 폐장 + 신정 + 주말 모두 건너뛰기', () => {
    // 2026-12-30 Wed (영업일 가정) → 2026-12-31 Thu 폐장
    // → 2027-01-01 Fri 신정 → 2027-01-02 Sat → 2027-01-03 Sun → 2027-01-04 Mon
    expect(nextOpenDay('2026-12-30')).toBe('2027-01-04')
  })

  it('월요일 → 이전 영업일은 주말 건너뛰고 금요일', () => {
    // 2026-06-22 Mon → 2026-06-19 Fri
    expect(previousOpenDay('2026-06-22')).toBe('2026-06-19')
  })

  it('지방선거일 (2026-06-03) 직후 다음 영업일', () => {
    // 2026-06-03 Wed 선거 → 2026-06-04 Thu (영업일)
    expect(isHoliday('2026-06-03')).toBe(true)
    expect(nextOpenDay('2026-06-03')).toBe('2026-06-04')
  })
})

describe('marketCalendar — classifyMarketStatus', () => {
  it('영업일은 open=true, nextClose=null', () => {
    const status = classifyMarketStatus('2026-06-15')
    expect(status.open).toBe(true)
    if (status.open) {
      expect(status.date).toBe('2026-06-15')
      expect(status.nextClose).toBeNull()
    }
  })

  it('휴장일은 open=false, reason=HOLIDAY, holiday meta + nextOpen', () => {
    const status = classifyMarketStatus('2026-01-01')
    expect(status.open).toBe(false)
    if (!status.open) {
      expect(status.reason).toBe('HOLIDAY')
      expect(status.holiday?.name).toContain('신정')
      expect(status.nextOpen).toBe('2026-01-02')
    }
  })

  it('주말은 open=false, reason=WEEKEND, holiday undefined', () => {
    const status = classifyMarketStatus('2026-01-03') // Sat
    expect(status.open).toBe(false)
    if (!status.open) {
      expect(status.reason).toBe('WEEKEND')
      expect(status.holiday).toBeUndefined()
      expect(status.nextOpen).toBe('2026-01-05') // Mon
    }
  })
})

describe('marketCalendar — todayInSeoul', () => {
  it('UTC 시간대를 KST(YYYY-MM-DD) 로 변환', () => {
    // UTC 2026-01-01 00:00 == KST 2026-01-01 09:00
    const utcMidnight = new Date(Date.UTC(2026, 0, 1, 0, 0, 0))
    expect(todayInSeoul(utcMidnight)).toBe('2026-01-01')
  })

  it('UTC 23:00 → KST 다음 날 08:00', () => {
    // UTC 2026-01-01 23:00 == KST 2026-01-02 08:00
    const utcLate = new Date(Date.UTC(2026, 0, 1, 23, 0, 0))
    expect(todayInSeoul(utcLate)).toBe('2026-01-02')
  })
})
