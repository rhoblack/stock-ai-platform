# Stock AI Frontend (v0.2)

PC 대시보드. v0.1 백엔드 (`v0.1-backend-final`) 의 13개 GET API 만 소비하는
read-only SPA. 자동매매 / 실 주문 UI 미포함.

## 기술 스택

- Vite + React 18 + TypeScript
- Tailwind CSS + shadcn/ui 스타일 (CSS variable 기반 테마)
- TanStack Query v5 (`useQuery` 캐시)
- React Router v6
- TanStack Table (Phase B 부터 사용 예정)
- Recharts (차트, Phase B+)
- vitest + @testing-library/react + msw (테스트)
- openapi-typescript (Phase B 에서 백엔드 schema 자동 생성)

## 실행 방법

### 1. 의존성 설치

```powershell
cd "d:\dev\AI\codex\3.AI주식 자동매매 대시보드\frontend"
npm install
```

### 2. 백엔드 (별도 터미널)

```powershell
cd "d:\dev\AI\codex\3.AI주식 자동매매 대시보드"
.\.venv\bin\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`SCHEDULER_ENABLED=false`, `TELEGRAM_ENABLED=false` 권장 (DRY_RUN).

### 3. 프론트 dev 서버

```powershell
cd frontend
npm run dev
```

기본 포트 `5173`. `http://127.0.0.1:5173` 에서 사이드바 8 메뉴 + 헤더 + 빈
페이지가 보이면 정상. 우측 상단의 health badge 가 녹색 OK 면 백엔드 proxy 정상.

### 4. 테스트

```powershell
npm run test       # vitest run (단일 실행, CI 용)
npm run test:watch # 개발 중 watch 모드
```

`msw/node` 가 `/health` 등 외부 호출을 가로채므로 테스트 중 실 백엔드는
필요 없음.

### 5. 프로덕션 빌드

```powershell
npm run build     # tsc --noEmit + vite build → dist/
npm run preview   # 빌드 결과 로컬 미리보기 (포트 4173)
```

배포는 별도 web 컨테이너 (nginx 등) 로. **FastAPI 가 정적 파일을 서빙하지
않는다** (v0.1 백엔드 동결).

## 디렉터리

```
frontend/
├── index.html
├── package.json
├── tailwind.config.ts / postcss.config.js / tsconfig.json
├── vite.config.ts          # /api, /health → :8000 proxy + vitest 설정
└── src/
    ├── main.tsx
    ├── App.tsx              # QueryClientProvider + ThemeProvider + RouterProvider
    ├── router.tsx           # 8 page routes
    ├── index.css            # Tailwind base + shadcn CSS variables
    ├── api/
    │   ├── client.ts        # GET-only fetch wrapper, ApiError
    │   └── types.ts         # 손글씨 타입 (Phase B 에서 openapi 생성으로 교체)
    ├── hooks/
    │   └── useHealth.ts
    ├── lib/
    │   └── utils.ts         # cn() (clsx + tailwind-merge)
    ├── components/
    │   ├── PagePlaceholder.tsx
    │   ├── theme/ThemeProvider.tsx
    │   └── layout/{AppLayout, Sidebar, Header}.tsx
    ├── pages/
    │   ├── TodayReport/
    │   ├── Recommendations/
    │   ├── RecommendationHistory/
    │   ├── Holdings/
    │   ├── StockDetail/
    │   ├── MarketCapTop/
    │   ├── Jobs/
    │   └── Settings/
    ├── tests/
    │   ├── mswServer.ts
    │   ├── App.test.tsx
    │   └── useHealth.test.tsx
    └── setupTests.ts
```

## 8 화면 / 사용 API 매핑

| 메뉴 | 경로 | 사용 GET API (Phase B+ 에서 연결) |
|---|---|---|
| 오늘의 리포트 | `/today` | `/api/reports/today` |
| 추천 종목 | `/recommendations` | `/api/recommendations/latest`, `/api/recommendations/runs/{run_id}` |
| 추천 이력 | `/recommendations/history` | `/api/recommendations/history` |
| 보유 종목 점검 | `/holdings` | `/api/holdings`, `/api/holdings/checks/latest`, `/api/holdings/{symbol}/checks` |
| 종목 상세 | `/stocks/:symbol` | `/api/stocks/{symbol}` |
| 시가총액 TOP | `/universe/market-cap-top` | `/api/universe/market-cap-top` |
| 시스템 로그 / 잡 | `/jobs`, `/jobs/:jobId` | `/api/jobs`, `/api/jobs/{job_id}` |
| 설정 | `/settings` | `/api/settings` |

## v0.2 진행 상태

- [x] **Phase A** — 프로젝트 초기화, Tailwind, Router, QueryClientProvider, Sidebar (8 메뉴), Header (페이지 제목 / health badge / 다크모드 토글), 8 페이지 placeholder, `/health` hook + 테스트
- [x] **Phase B** — Today Report 화면 + 시스템 로그/잡 화면 실 데이터 연동
  - hooks: `useJobs`, `useJobDetail`, `useTodayReport`
  - shared components: `DataStatusBadge`, `RiskBadge`, `GradePill`, `DecisionPill`, `ReturnRate`, `JsonViewer`
  - Jobs: TanStack Table 기반 list + 우측 패널 detail (`result_summary` JSON 뷰), 30초 자동 새로고침, 행 클릭 → `/jobs/:jobId`
  - Today Report: 추천 TOP / 보유 점검 알림 / HIGH risk / 마지막 run 4 카드, 60초 자동 새로고침
  - 테스트: Jobs + Today 각각 happy / empty / error 3종
- [x] **Phase C** — 추천 종목 + 추천 이력 화면 실 데이터 연동
  - hooks: `useLatestRecommendationRun`, `useRecommendationRunDetail`, `useRecommendationHistory`
  - shared components 추가: `MetricCard`, `TrendLineChart` (Recharts wrapper)
  - Recommendations: rank / 등급 / 시장 / 종목 / total_score / 5컴포넌트 점수 / risk / 1·3·5·20일 close_return / 사유 / risk_note. 5분 자동 새로고침. `/recommendations/runs/:runId` 로 특정 run 상세 보기 지원.
  - Recommendation History: 4 metric card (run 수 / 총 추천 / avg success_rate / avg close_return 5d) + 2 Recharts 추세 라인 (success_rate, avg_close_return_5d) + run 별 표 (run_date 클릭 → 해당 run 상세). 5분 자동 새로고침.
  - 테스트: Recommendations 4건 (happy / empty / error 404 / `:runId` 라우팅) + History 3건 (happy / empty / error 500). jsdom ResizeObserver mock 추가 (Recharts ResponsiveContainer 의존).
- [x] **Phase D** — 보유 종목 점검 + 종목 상세 화면 실 데이터 연동
  - hooks: `useHoldings`, `useLatestHoldingChecks`, `useHoldingChecksForSymbol`, `useStockDetail`
  - shared components 추가: `KeyValueGrid`
  - Holdings: 좌측 보유 list (symbol/qty/avg_buy/strategy/decision/risk/return/alert) + 우측 선택 종목 패널 (4 metric card + KeyValueGrid + total_score/return_rate 추세 라인 2개 + 최근 점검 펼침 표). 행 클릭 → `/holdings/:symbol`. "종목 상세 →" 링크 → `/stocks/:symbol`. 60초 자동 새로고침.
  - Stock Detail: 헤더 (name/symbol/market/sector) + 최신 가격 (open/high/low/close/volume/trading_value) + 최신 지표 (MA5/20/60/120 / RSI14 / MACD / volume_ratio_20d / breakout / ma_alignment / technical_score) + 최근 추천 이력 표 (rank/grade/total/risk + 1·3·5·20일 close_return + 사유) + 최근 보유 점검 표.
  - 테스트: Holdings 4건 (happy with checks merge / row-click → trend panel + 4 metrics / empty / error 500) + StockDetail 3건 (happy 5 sections / empty placeholders / error 404).
- [x] **Phase E** — 시가총액 TOP + 설정 화면 실 데이터 연동
  - hooks: `useMarketCapTop`, `useSettings`
  - shared components 추가: `SafetyFlagBadge`
  - MarketCap TOP: rank 정렬 가능 TanStack Table + 시장 필터 (KOSPI/KOSDAQ/ALL — ALL 은 두 시장 병합) + symbol/name 검색. 종목 클릭 → `/stocks/:symbol`. 1시간 자동 새로고침.
  - Settings: 4 KeyValueGrid 섹션 (앱·환경 / KIS / Telegram / v0.1 안전 플래그) + freeze 배너 ("v0.1 백엔드 동결 / 변경은 .env + 재시작") + `MaskedSecret` 비밀값 평문 노출 자동 감지 (⚠ unmasked 표시). 안전 플래그 5개가 모두 false 인지 색상으로 한눈 확인.
  - 테스트: MarketCap 5건 (happy / market 필터 KOSPI→KOSDAQ→ALL / symbol·name 검색 / empty / 500) + Settings 5건 (happy + 4 sections / 모든 비밀 마스킹 검증 / 평문 누출 시 unmasked 마커 / 안전 플래그 위반 시 빨강 + 헤더 카운트 / 500 에러).
- [x] **Phase F** — v0.2 MVP 마감 (`v0.2-frontend-final`)
  - 코드 스플릿: 모든 페이지 `React.lazy` + `<Suspense>`, `manualChunks` 로 react/query/table/charts 분리. 첫 진입 (Today) gzip ≈ 80 kB, Recharts 청크 (gzip 105 kB) 는 추세 화면 진입 시에만 로드.
  - Playwright e2e (`npm run e2e`): 8 화면 sidebar 순회 / Jobs JSON 패널 / MarketCap 필터+검색 / Settings 마스킹 가드 / 자동매매 UI 부재 검증 — 6 tests passed (5.5s). `vite preview` 자동 기동 + `page.route` mock — 실 백엔드 / KIS / Telegram 호출 0건.
  - Docker 프런트 서비스: [`Dockerfile`](./Dockerfile) (Node 20 build → nginx 1.27 serve) + [`nginx.conf`](./nginx.conf) (`/api`, `/health` → `backend:8000` proxy) + 루트 [`../docker-compose.yml`](../docker-compose.yml) `web` 서비스 (port 8080). FastAPI 정적 서빙 미사용.
  - 릴리스 문서: [`../RELEASE_NOTES_v0.2_FRONTEND.md`](../RELEASE_NOTES_v0.2_FRONTEND.md), 루트 README + PROJECT_STATUS 마감 선언.

### Phase F — Docker 한 줄 실행

```powershell
docker compose up --build
# 프런트: http://127.0.0.1:8080  (nginx 가 /api 와 /health 를 backend 로 proxy)
# 백엔드: http://127.0.0.1:8000  (직접 접근도 가능, FastAPI 정적 서빙 미사용)
```

### Phase F — e2e 한 줄 실행

```powershell
cd frontend
npm install
npx playwright install chromium    # 1회 (~110 MiB)
npm run e2e
```

### Phase B 실행 빠른 가이드

1. 백엔드 + mock seed 적재 (별도 터미널, 프로젝트 루트):
   ```powershell
   .\.venv\bin\python.exe -m scripts.seed_mock_data --reset
   .\.venv\bin\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
2. 프런트 dev:
   ```powershell
   cd frontend
   npm run dev
   ```
3. 브라우저에서 `http://127.0.0.1:5173/today` (Today Report) 와 `http://127.0.0.1:5173/jobs` (Jobs) 확인.
4. `/jobs` 에서 행 클릭 → URL 이 `/jobs/:jobId` 로 변하고 우측 패널에 `result_summary` JSON 노출.
5. 회귀: `npm run test` (vitest) + `npm run build` (tsc + vite build).

## 보안 / 보안 정책

- KIS 키 / 시크릿 / 계좌번호 / 텔레그램 토큰은 **백엔드의 마스킹된 응답** 그대로 표시. 프론트가 평문을 다루지 않는다.
- `frontend/.env` 는 `.gitignore` 등록. `.env.example` 만 커밋.
- 자동매매 / 실 주문 / POST 라우터 호출 UI 미포함 (`v0.1-backend-final` 동결).
- Test 가 실 KIS / 실 텔레그램 / 실 백엔드 호출하지 않음 (msw + jsdom).
