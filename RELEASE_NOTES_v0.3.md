# RELEASE_NOTES_v0.3.md

**v0.3 분석 보강 + 운영 정착 사이클 마감 선언**

- 최종 태그: `v0.3-final`
- 인수 일자: 2026-05-05 (Asia/Seoul)
- 회귀 게이트
  - **백엔드 pytest 319 passed** (+23 vs v0.2 의 296)
  - **frontend vitest 59 passed** (+23 vs v0.2 의 36)
  - **frontend build 통과** (vendor-charts 청크 383 kB / gzip 105 kB 동일, StockDetail 페이지 청크만 8.28 → 11.36 kB 증가)
  - **Playwright e2e 8 passed** (+2 vs v0.2 의 6)
- 누적 인수 태그 (시간순)
  - `v0.3-phase-a-ci` — GitHub Actions CI (3 job: backend pytest / frontend vitest+build / Playwright e2e)
  - `v0.3-backend-analysis` — 캔들 패턴 5종 + Wilder ATR(14) + 4단계 변동성 분류 + 점수 산식 보강 + DB 컬럼 3개
  - `v0.3-frontend-calendar` — 정적 KRX 휴장일 캘린더 (2025–2027) + Today/Jobs/Holdings MarketStatusBanner
  - `v0.3-frontend-stock-chart` — `GET /api/stocks/{symbol}/prices` read-only API + StockDetail 일봉 라인 차트 + 30/60/120/250 days 선택자
  - `v0.3-final` — 본 릴리스 마감 (코드 변경 없는 문서 마감)

본 릴리스는 `v0.1-backend-final` (백엔드 기준선) + `v0.2-frontend-final` (대시보드
기준선) 위에 분석 컴포넌트 + 운영 UX + CI 4 phase 를 추가하고, 현재까지의 전체
시스템을 한 번에 마감한다. **자동매매 / 실 주문 / FULL_AUTO / APPROVAL /
SMALL_AUTO / POST 트리거 UI 는 v0.3 범위 밖** 이며 코드 / 인터페이스 / UI 를
일체 포함하지 않는다 (`BrokerInterface` 는 ABC placeholder 만 유지).

---

## 1. 산출물 한 줄 요약

| Phase | 영역 | 산출물 |
|---|---|---|
| A | DevOps / CI | `.github/workflows/ci.yml` — backend pytest + frontend vitest+build + Playwright e2e 3 job. main / PR 양쪽 자동 검증. PR 1건 의도적 실패로 빨강 한 번 확인 후 픽스 |
| B | Backend Analysis | `app/analysis/technical_analyzer.py` 캔들 5종 detector (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING / BEARISH_ENGULFING) + Wilder ATR(14) + 4단계 변동성 분류 (LOW / NORMAL / HIGH / EXTREME). `calculate_technical_score` 가산/감산 (캔들 ±5 cap, 변동성 -5~+2) + 0~100 clamp |
| B | DB Schema | `StockIndicator` 에 nullable 3 컬럼 추가 (`atr14 Numeric(20,4)`, `candle_patterns JSON`, `volatility_band String(16)`). ALTER ADD only — 기존 데이터 무영향 |
| B | API 응답 | `StockIndicatorSchema` 에 3개 optional 필드 → `/api/stocks/{symbol}.latest_indicator` 응답에 자동 포함 |
| C | Frontend / 운영 UX | `frontend/src/data/krxHolidays.ts` 정적 JSON (2025–2027, 6 카테고리: fixed/lunar/substitute/election/temporary/year-end) + `frontend/src/lib/marketCalendar.ts` (KST 기준 영업일 / 휴장일 / 다음 영업일 산정) + `MarketStatusBanner` 컴포넌트 — Today / Jobs / Holdings 헤더에 통합. **외부 API 호출 0건** |
| D | Backend / Read-only API | `GET /api/stocks/{symbol}/prices?days=120` (default 120, min 1, max 500) — `daily_prices` 만 조회 (KIS 호출 0건). 응답 정렬 = 날짜 오름차순. 404 (종목 없음) / 200 + count=0 (일봉 없음) / 422 (days 범위 외) |
| D | Frontend / 차트 | `useStockPriceSeries` 훅 + `pages/StockDetail/PriceChart.tsx` (Recharts LineChart, close 추세) + 30/60/120/250 days 선택자. `vendor-charts` 청크는 동일 (383 kB / gzip 105 kB) — Recharts 신규 의존 0건 |
| E | Docs / 마감 | `RELEASE_NOTES_v0.3.md` (본 문서) + `README.md` v0.3 마감 배너 + `PROJECT_STATUS.md` §0 v0.3 마감 선언 + `TASKS.md` 모든 Phase [x] |

---

## 2. 검증 요약

### 2.1 백엔드 pytest (`pytest -q`)

```
319 passed in 5.53s
```

증분 분석:

| 누적 태그 | 통과 수 | 증분 |
|---|---|---|
| `v0.1-backend-final` | 296 | — |
| `v0.3-backend-analysis` (Phase B) | **314** | +18 (캔들/ATR/변동성 단위 16 + indicator persist 통합 2) |
| `v0.3-frontend-calendar` (Phase C) | 314 | 0 (백엔드 변경 없음) |
| `v0.3-frontend-stock-chart` (Phase D) | **319** | +5 (`/api/stocks/{symbol}/prices` happy / cap / empty / 404 / days bounds 422) |
| `v0.3-final` | 319 | 0 |

> 운영 환경에서 `.env` 의 `MARKET_CAP_LIMIT=5` 같은 dev override 가 있으면
> `tests/unit/test_project_structure.py::test_settings_defaults` 가 한 건
> 실패하지만, 이는 본 릴리스가 아닌 사용자 로컬 dev 설정 영향이다. CI 와
> 본 게이트 측정은 `.env` 를 옮긴 상태에서 수행한 결과를 기준으로 한다.

### 2.2 frontend vitest (`npm run test -- --run`)

```
Test Files  12 passed (12)
     Tests  59 passed (59)
```

증분:

| 누적 태그 | 통과 수 | 증분 신규 파일 / 테스트 |
|---|---|---|
| `v0.2-frontend-final` | 36 | — |
| `v0.3-frontend-calendar` | **55** | +19 (`marketCalendar.test.tsx` 15 + `MarketStatusBanner.test.tsx` 4) |
| `v0.3-frontend-stock-chart` | **59** | +4 (`StockDetail.test.tsx` chart success / empty / error / days 선택자 토글) |

- jsdom + msw v2 + ResizeObserver mock (`setupTests.ts`) 위에서 외부 호출 0건.
- 비밀 평문 누출 가드: `secret-*` 노드 `data-masked="true"` 단언 그대로 유지.

### 2.3 Playwright e2e (`npx playwright test`, chromium, vite preview + page.route 모킹)

```
Running 8 tests using 8 workers
  ok 1 — all 8 sidebar menus are reachable and render their main content
  ok 2 — Jobs row click reveals result_summary JSON in detail panel
  ok 3 — MarketCap TOP filter switches from KOSPI to KOSDAQ to ALL
  ok 4 — MarketCap TOP search filters by name/symbol
  ok 5 — Settings shows masked secrets only — no plaintext leak
  ok 6 — no automation / order UI is exposed anywhere in v0.2 frontend
  ok 7 — MarketStatusBanner is visible on Today / Jobs / Holdings pages   ← v0.3 Phase C
  ok 8 — StockDetail price chart card and days selector are visible       ← v0.3 Phase D
  8 passed (5.5s)
```

- 6 → 8 (+2). 추가된 두 건 모두 read-only — POST / form / submit 0건.
- 자동매매 UI 부재 검증 (`no automation / order UI ...`) 은 v0.3 신규 화면 (배너,
  차트 카드) 도 검사 범위에 포함되며 그대로 통과.

### 2.4 frontend build (`npm run build` = `tsc --noEmit && vite build`)

```
✓ 2468 modules transformed.
dist/assets/vendor-charts-DDZcf56L.js  383.32 kB │ gzip: 105.44 kB   ← 동일
dist/assets/vendor-react-BcDvhPSV.js   156.79 kB │ gzip:  51.34 kB
dist/assets/vendor-table-Cx-kCU2W.js    50.90 kB │ gzip:  13.62 kB
dist/assets/vendor-query-DAybuspA.js    46.94 kB │ gzip:  14.51 kB
dist/assets/MarketStatusBanner-*.js      5.77 kB │ gzip:   2.22 kB   ← Phase C 신규 청크
dist/assets/index-*.js (StockDetail)    11.36 kB │ gzip:   3.40 kB   ← Phase D 후 (8.28 → 11.36)
✓ built in 3.36s
```

- Recharts 의존 신규 0건 → `vendor-charts` 크기 변동 없음.
- StockDetail 페이지 청크 +3 kB ≈ PriceChart 컴포넌트.
- 첫 진입 (Today, no charts) 합산 ≈ 297 kB / gzip ~80 kB — v0.2 와 동일.

---

## 3. v0.3 누적 변경 (정책 / 코드 / 데이터)

### 3.1 백엔드 동결 정책 변경

`v0.1-backend-final` 동결을 v0.3 에서 일부 깬다. 변경 범위는 다음으로 한정:

| Phase | 변경 파일 | 종류 |
|---|---|---|
| B | `app/analysis/technical_analyzer.py` | 신규 함수 추가 (캔들 / ATR / 변동성), 기존 산식 시그니처는 default None 키워드만 추가 |
| B | `app/db/models.py` | `StockIndicator` ALTER ADD 3 컬럼 (모두 nullable) |
| B | `app/data/repositories/stock_indicators.py` | `upsert` 키워드 3개 추가 (default None) |
| B | `app/analysis/indicator_service.py` | snapshot 의 신규 필드 persist |
| B | `app/api/schemas.py` | `StockIndicatorSchema` 에 3 optional 필드 |
| D | `app/api/routes.py` | 신규 read-only `GET /api/stocks/{symbol}/prices` 1개 추가 |
| D | `app/api/schemas.py` | `StockPriceSeriesResponse` 신규 |
| D | `tests/integration/test_api_routes.py` | 5건 신규 |

**POST 라우터 / 잡 트리거 / 자동매매 코드 / KIS 호출 / 텔레그램 발송은 추가하지
않았다.** DB 컬럼 추가는 `ALTER TABLE ADD COLUMN` 만이라 destructive 하지 않으나,
운영 환경에는 마이그레이션 안내가 필요 — `daily_prices` 테이블 / 인덱스에는
변경이 없다. `StockIndicator` 의 신규 3 컬럼은 NULL 로 채워진 채 유지되며 다음
indicator 갱신 잡이 돌면 자동으로 채워진다.

### 3.2 프런트 변경 요약

| Phase | 신규 / 수정 |
|---|---|
| C | 신규 `data/krxHolidays.ts`, `lib/marketCalendar.ts`, `components/common/MarketStatusBanner.tsx`, `tests/marketCalendar.test.tsx`, `tests/MarketStatusBanner.test.tsx` |
| C | 수정 `pages/TodayReport/index.tsx`, `pages/Jobs/index.tsx`, `pages/Holdings/index.tsx` (각 +2 줄, 헤더 직후 `<MarketStatusBanner />`) |
| C | 수정 `e2e/dashboard.spec.ts` (Banner e2e 1건) |
| D | 신규 `hooks/useStockPriceSeries.ts`, `pages/StockDetail/PriceChart.tsx` |
| D | 수정 `api/types.ts`, `pages/StockDetail/index.tsx`, `tests/StockDetail.test.tsx`, `tests/mswServer.ts`, `e2e/fixtures/apiMocks.ts`, `e2e/dashboard.spec.ts` |

화면 레이아웃 / 라우팅 / 테마 / 사이드바는 변경하지 않았다. 8 화면 구조는 v0.2
와 동일.

---

## 4. v0.3 제외 범위 (재확인)

- ❌ 실거래 자동매매 / 실 KIS 주문 API 실행 — `BrokerInterface` ABC placeholder 그대로 유지
- ❌ FULL_AUTO / APPROVAL / SMALL_AUTO 모드
- ❌ POST 트리거 UI / API — frontend / backend 양쪽 0건 (read-only GET 만 추가)
- ❌ 실 News / Supply / Fundamental / Earnings 외부 데이터 파이프라인 — `DummyScoreProducer` placeholder 유지. v0.3 의 분석 보강은 캔들 / ATR / 변동성 (기존 일봉 + 거래량 데이터로 계산 가능) 한정
- ❌ 즐겨찾기 / 관심 종목 / 인증 / 권한 / 운영 모니터링 (Sentry / Prometheus / Grafana)
- ❌ Strategy / Backtest / MockBroker / SimulationBroker — 모두 v0.4+ 백로그
- ❌ 모바일 / 태블릿 레이아웃 — PC 1280px+ 우선 그대로

---

## 5. 알려진 한계 (v0.4 후속 가능)

| 항목 | 설명 |
|---|---|
| KRX 휴장일 데이터 갱신 | 정적 JSON 으로 매년 1회 수동 갱신 필요 (`frontend/src/data/krxHolidays.ts` 헤더 주석에 4단계 절차). 임시공휴일은 발표 직후 PR 로 추가. 자동 fetch 는 v0.4+ |
| 2027 캘린더 잠정 | 2027 항목은 KRX 공식 발표 (보통 전년 12월) 후 재확인이 필요. 일부 대체공휴일이 변경될 수 있음 |
| StockDetail 차트 = close 라인 1개 | 캔들 차트 / 거래량 BarChart / 이동평균 오버레이 미구현. Recharts 의 `ComposedChart` 또는 `lightweight-charts` 로 v0.4 에 확장 가능 |
| 차트 시계열 캐싱 정책 | `useStockPriceSeries` 의 `staleTime: 60_000` 만 적용. 종목 전환 시 매번 새 fetch — 마지막 5종목 LRU 캐시는 v0.4+ |
| Recharts 번들 크기 | `vendor-charts` 청크 gzip 105 kB. 현재는 추세 / 일봉 차트 진입 시에만 로드되므로 첫 진입에는 영향 없음. 금융 캔들 화면 추가 시 `lightweight-charts` 로 마이그레이션 검토 |
| 캔들 / ATR 의 score impact 가시화 | 백엔드는 score 에 반영하지만, 프런트 StockDetail 화면은 `atr14` / `candle_patterns` / `volatility_band` 를 명시적으로 표시하지 않음. v0.4 에서 IndicatorCard 확장 가능 |
| `daily_prices` 의 거래일 누락 | 휴장일 / 주말이 자동 누락된 형태로 응답 — 클라이언트는 `date` 가 연속 영업일이라는 점에 의존. 향후 백엔드가 거래일 캘린더와 join 하면 더 안전 |
| 차트 reset 시 days=120 fallback | URL state 미반영 — 페이지 새로고침 시 항상 120d 로 시작. v0.4 에서 `useSearchParams` 로 deep-link 가능 |

---

## 6. v0.4 후보 (Backlog)

본 마감 시점에 합의된 v0.4 후보. 명시적 진입 요청 전까지 손대지 않는다.

### 6.1 데이터 / 분석

- 실 News / Supply / Fundamental / Earnings 파이프라인 (`DummyScoreProducer` 교체)
- 캔들 차트 / 거래량 차트 (`lightweight-charts` 마이그레이션 검토)
- StockDetail 의 ATR / 캔들 / 변동성 점수 영향 가시화 (IndicatorCard 확장)
- `recommendation_results` 의 N=20 일 외 다른 기간 토글
- KRX 휴장일 캘린더 자동 fetch (한국거래소 공지 RSS / 공공 API)

### 6.2 운영 / UX

- StockDetail 차트 days deep-link (`/stocks/005930?days=60`)
- 종목 시계열의 LRU 캐시 (마지막 N 종목)
- 즐겨찾기 / 관심 종목 — POST 라우터 도입 필요
- 글로벌 검색 단축키 (cmd+k)
- sidebar collapse / breadcrumb / loading skeleton 통일
- 모바일 / 태블릿 레이아웃

### 6.3 백엔드 v0.4 (별도 cycle)

- POST 트리거 (잡 수동 실행 / 추천 즉시 생성) — 인증 동반 필수
- WebSocket / SSE 실시간 잡 상태 (현재 polling)
- Strategy 모듈 (장기/중기/단기, SIGNAL / PAPER 모드)
- Backtest 엔진 (walk-forward, 그리드 서치)
- MockBroker / ReplayBroker / SimulationBroker / 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래 — `BrokerInterface` 구현체 도입)

### 6.4 보안 / 인증 / 운영

- 인증 / 권한 (단일 사용자 / 사내망 외 노출 시)
- KIS 키 회전 자동화 / Vault 통합
- Sentry / Prometheus / Grafana 운영 모니터링

---

## 7. 운영 / 인수자 가이드

### 7.1 로컬 개발 (v0.3 기준)

```powershell
# 백엔드 (별도 터미널)
cd "d:\dev\AI\codex\3.AI주식 자동매매 대시보드"
.\.venv\bin\python.exe -m scripts.seed_mock_data --reset
.\.venv\bin\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 프런트 (별도 터미널)
cd frontend
npm install
npm run dev          # http://127.0.0.1:5173

# 회귀
npm run test -- --run     # vitest 59
npm run e2e               # Playwright 8 (vite preview 자동 기동)
npm run build             # tsc --noEmit + vite build

# 백엔드 회귀 (.env 의 dev override 가 있으면 잠시 옮긴 후)
cd ..
.\.venv\bin\python.exe -m pytest -q   # 319 passed
```

### 7.2 Docker 배포

```powershell
docker compose up --build
# 접속: http://127.0.0.1:8080  (frontend, nginx)
# 백엔드: http://127.0.0.1:8000 (FastAPI, 정적 서빙 안 함)
# DB:    postgres  (compose volume)
```

`web` 컨테이너 nginx 가 `/api/*` 와 `/health` 를 `backend:8000` 으로 proxy 한다.
v0.2 와 동일 — v0.3 에서 docker / nginx 설정은 변경 없음.

### 7.3 운영 환경 마이그레이션 (v0.2 → v0.3)

1. `git pull` 후 `v0.3-final` 태그 확인
2. 백엔드: `StockIndicator` 테이블에 `ALTER TABLE ADD COLUMN` 3개 — Alembic 미사용 시 SQL 직접 적용:
   ```sql
   ALTER TABLE stock_indicators ADD COLUMN atr14 NUMERIC(20, 4);
   ALTER TABLE stock_indicators ADD COLUMN candle_patterns JSON;
   ALTER TABLE stock_indicators ADD COLUMN volatility_band VARCHAR(16);
   ```
   기존 행은 NULL 로 채워지고, 다음 indicator 갱신 잡이 돌면 자동으로 값이 들어간다.
3. 프런트: nginx 컨테이너 재빌드 (`docker compose build web && docker compose up -d`).
4. KRX 휴장일 캘린더는 정적 JSON — 추가 마이그레이션 없음. 매년 12월 (KRX 공지 후) 다음 해 항목 추가 PR 1건.

### 7.4 비밀 / 보안

- 본 릴리스 노트와 frontend / backend 어디에도 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 평문이 기록되지 않았다. 백엔드 `/api/settings` 응답 마스킹 정책 그대로 유지.
- `.env` / `frontend/.env` 는 `.gitignore` 등록. `.env.example` 만 커밋.
- e2e 는 `page.route` mock 으로 동작 — 실 자격증명을 절대 사용하지 않는다.
- v0.3 추가 코드 (캘린더 / 차트 / 가격 시계열 API) 는 모두 read-only — 외부 호출 / 인증 정보 / 비밀값 0건.

---

**이 문서로 v0.3 분석 보강 + 운영 정착 사이클 마감을 선언한다.** v0.4 진입은
사용자의 명시적 요청이 있을 때 시작한다.
