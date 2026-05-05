// 한국거래소 (KRX) 휴장일 정적 데이터.
//
// 출처:
//   * 고정일자 (신정 / 삼일절 / 어린이날 / 현충일 / 광복절 / 개천절 / 한글날 / 성탄절)
//     은 한국 법정공휴일로 매년 동일.
//   * 음력 기반 (설날 / 부처님오신날 / 추석) 은 한국천문연구원 음양력 변환 결과.
//   * 대체공휴일 (substitute) 은 「관공서의 공휴일에 관한 규정」 제3조 (일요일 또는 공휴일 중복 시).
//   * 연말 폐장 (year-end) 은 KRX 의 매년 12월 폐장 안내. 12/31 이 평일이면 그 날, 주말이면 그 직전
//     영업일을 폐장일로 한다 (현재 데이터는 12/31 평일 케이스만 포함).
//
// 갱신 절차 (운영자 1인 매년 1회):
//   1. 한국거래소 공지: https://open.krx.co.kr/contents/OPN/04/04020800/OPN04020800.jsp
//      → "휴장일 안내" 발표 (보통 전년 12월) 확인.
//   2. 다음 해 항목을 본 파일에 추가하거나, 기존 항목과 일치하지 않으면 수정.
//   3. `frontend/src/tests/marketCalendar.test.tsx` 에 해당 연도 케이스 1~2건 추가 권장.
//   4. PR / push → CI 가 회귀 자동 검증.
//
// 임시공휴일 (대선·총선·국가 임시 지정 등) 은 발표 직후 본 파일에 `temporary`
// 카테고리로 추가한다. 본 데이터에는 향후 확정되지 않은 임시공휴일은 포함되지 않는다.

export type KrxHolidayCategory =
  | 'fixed' // 고정일자 법정공휴일 (Jan 1, May 5 등)
  | 'lunar' // 음력 기반 (설/추석/부처님오신날)
  | 'substitute' // 대체공휴일 (일/공휴일 중복으로 인한 다음 평일 휴무)
  | 'election' // 임기제 선거일 (전국 단위)
  | 'temporary' // 정부 지정 임시공휴일
  | 'year-end' // KRX 연말 폐장

export interface KrxHoliday {
  /** ISO 날짜 YYYY-MM-DD (KST). */
  date: string
  /** 사유 (한국어). */
  name: string
  category: KrxHolidayCategory
}

// 2025-2027. 그 이후는 매년 KRX 공식 발표 후 추가.
export const KRX_HOLIDAYS: KrxHoliday[] = [
  // ----- 2025 -----
  { date: '2025-01-01', name: '신정', category: 'fixed' },
  { date: '2025-01-27', name: '설날 임시공휴일', category: 'temporary' },
  { date: '2025-01-28', name: '설날 연휴', category: 'lunar' },
  { date: '2025-01-29', name: '설날', category: 'lunar' },
  { date: '2025-01-30', name: '설날 연휴', category: 'lunar' },
  { date: '2025-03-03', name: '삼일절 대체공휴일', category: 'substitute' },
  { date: '2025-05-05', name: '어린이날·부처님오신날', category: 'fixed' },
  { date: '2025-05-06', name: '대체공휴일 (어린이날·부처님오신날 중복)', category: 'substitute' },
  { date: '2025-06-06', name: '현충일', category: 'fixed' },
  { date: '2025-08-15', name: '광복절', category: 'fixed' },
  { date: '2025-10-03', name: '개천절', category: 'fixed' },
  { date: '2025-10-06', name: '추석 연휴', category: 'lunar' },
  { date: '2025-10-07', name: '추석', category: 'lunar' },
  { date: '2025-10-08', name: '추석 연휴', category: 'lunar' },
  { date: '2025-10-09', name: '한글날', category: 'fixed' },
  { date: '2025-12-25', name: '성탄절', category: 'fixed' },
  { date: '2025-12-31', name: '연말 폐장', category: 'year-end' },

  // ----- 2026 -----
  { date: '2026-01-01', name: '신정', category: 'fixed' },
  { date: '2026-02-16', name: '설날 연휴', category: 'lunar' },
  { date: '2026-02-17', name: '설날', category: 'lunar' },
  { date: '2026-02-18', name: '설날 연휴', category: 'lunar' },
  { date: '2026-03-02', name: '삼일절 대체공휴일', category: 'substitute' },
  { date: '2026-05-05', name: '어린이날', category: 'fixed' },
  { date: '2026-05-25', name: '부처님오신날 대체공휴일', category: 'substitute' },
  { date: '2026-06-03', name: '8회 전국동시지방선거', category: 'election' },
  // 6월 6일 현충일은 토요일 → 시장 주말 휴장으로 흡수, 별도 항목 없음
  { date: '2026-08-17', name: '광복절 대체공휴일', category: 'substitute' },
  { date: '2026-09-24', name: '추석 연휴', category: 'lunar' },
  { date: '2026-09-25', name: '추석', category: 'lunar' },
  { date: '2026-09-28', name: '추석 대체공휴일', category: 'substitute' },
  { date: '2026-10-05', name: '개천절 대체공휴일', category: 'substitute' },
  { date: '2026-10-09', name: '한글날', category: 'fixed' },
  { date: '2026-12-25', name: '성탄절', category: 'fixed' },
  { date: '2026-12-31', name: '연말 폐장', category: 'year-end' },

  // ----- 2027 (잠정 — KRX 공식 발표 후 재확인 필요) -----
  { date: '2027-01-01', name: '신정', category: 'fixed' },
  { date: '2027-02-08', name: '설날 대체공휴일', category: 'substitute' },
  { date: '2027-03-01', name: '삼일절', category: 'fixed' },
  { date: '2027-05-05', name: '어린이날', category: 'fixed' },
  { date: '2027-05-13', name: '부처님오신날', category: 'lunar' },
  { date: '2027-06-07', name: '현충일 대체공휴일', category: 'substitute' },
  { date: '2027-08-16', name: '광복절 대체공휴일', category: 'substitute' },
  { date: '2027-09-14', name: '추석 연휴', category: 'lunar' },
  { date: '2027-09-15', name: '추석', category: 'lunar' },
  { date: '2027-09-16', name: '추석 연휴', category: 'lunar' },
  { date: '2027-10-04', name: '개천절 대체공휴일', category: 'substitute' },
  { date: '2027-10-11', name: '한글날 대체공휴일', category: 'substitute' },
  { date: '2027-12-31', name: '연말 폐장', category: 'year-end' },
]
