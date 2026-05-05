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

## v0.2 Phase A 범위 (현재)

- [x] 프로젝트 초기화, Tailwind, Router, QueryClientProvider
- [x] Sidebar (8 메뉴) + Header (페이지 제목 / health badge / 다크모드 토글)
- [x] 8 페이지 placeholder
- [x] `/health` hook + 테스트 (vitest + msw)
- [ ] (Phase B) Today Report + Jobs 실 데이터 연동
- [ ] (Phase C) Recommendations + History
- [ ] (Phase D) Holdings + Stock Detail
- [ ] (Phase E) MarketCap Top + Settings
- [ ] (Phase F) Playwright e2e + Docker 배포 + `RELEASE_NOTES_v0.2_FRONTEND.md`

## 보안 / 보안 정책

- KIS 키 / 시크릿 / 계좌번호 / 텔레그램 토큰은 **백엔드의 마스킹된 응답** 그대로 표시. 프론트가 평문을 다루지 않는다.
- `frontend/.env` 는 `.gitignore` 등록. `.env.example` 만 커밋.
- 자동매매 / 실 주문 / POST 라우터 호출 UI 미포함 (`v0.1-backend-final` 동결).
- Test 가 실 KIS / 실 텔레그램 / 실 백엔드 호출하지 않음 (msw + jsdom).
