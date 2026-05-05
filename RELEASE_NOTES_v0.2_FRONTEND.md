# RELEASE_NOTES_v0.2_FRONTEND.md

**v0.2 PC 대시보드 프론트엔드 마감 선언**

- 최종 태그: `v0.2-frontend-final`
- 인수 일자: 2026-05-05 (Asia/Seoul)
- 회귀 게이트
  - **vitest 36 passed** (frontend 단위/통합)
  - **Playwright e2e 6 passed** (8 화면 happy + Jobs 상세 + MarketCap 필터/검색 + Settings 마스킹 + 자동매매 UI 부재 검증)
  - **백엔드 pytest 296 passed 유지** (v0.1 backend 동결, 코드 변경 0건)
- 누적 인수 태그
  - `v0.2-frontend-phase-a` — 골격 (Vite/React/Tailwind/QueryClient/Router, 8 메뉴 placeholder, /health hook)
  - `v0.2-frontend-phase-b` — Today Report + Jobs 실 데이터
  - `v0.2-frontend-phase-c` — Recommendations + Recommendation History (Recharts)
  - `v0.2-frontend-phase-d` — Holdings + Stock Detail
  - `v0.2-frontend-phase-e` — MarketCap TOP + Settings (마스킹 가드)
  - `v0.2-frontend-final` — Phase F 마감 (코드 스플릿 + e2e + Docker + 릴리스 문서)

본 릴리스는 `v0.1-backend-final` 백엔드의 13개 read-only GET API 만 소비하는
SPA 의 v0.2 MVP 마감을 선언한다. **자동매매 / 실 주문 / FULL_AUTO 모드 / POST
트리거 UI 는 v0.2 범위 밖** 이며 코드 / 인터페이스 일체 포함하지 않는다.

---

## 1. 산출물 한 줄 요약

| 영역 | 산출물 |
|---|---|
| 프레임워크 | Vite 5 + React 18 + TypeScript 5.5 |
| 스타일 | Tailwind CSS 3.4 + shadcn/ui 스타일 (CSS variable 테마, 다크/라이트 토글) |
| 데이터 | TanStack Query v5 (페이지별 staleTime / refetchInterval), TanStack Table v8 |
| 차트 | Recharts (RecommendationHistory + Holdings 추세 라인) |
| 라우팅 | React Router v6 legacy (`<Routes>`, lazy loaded) |
| API 타입 | hand-written `src/api/types.ts` (Phase G+ 에서 `openapi-typescript` 자동 생성으로 전환 예정) |
| 화면 | 8개 (오늘의 리포트 / 추천 종목 / 추천 이력 / 보유 종목 점검 / 종목 상세 / 시가총액 TOP / 시스템 로그·잡 / 설정) |
| 공통 컴포넌트 | `DataStatusBadge`, `RiskBadge`, `GradePill`, `DecisionPill`, `ReturnRate`, `JsonViewer`, `MetricCard`, `TrendLineChart`, `KeyValueGrid`, `SafetyFlagBadge`, `PagePlaceholder` |
| 단위/통합 테스트 | vitest 36 (10 파일) — happy / empty / error 트리플 + 마스킹 가드 + 필터/검색 |
| E2E | Playwright 6 — 8 화면 sidebar 순회 / Jobs JSON 패널 / MarketCap 필터+검색 / Settings 마스킹 / 자동매매 UI 부재 |
| 빌드 | `npm run build` — entry 36 kB + react vendor 157 kB + query 47 kB + table 51 kB + charts 383 kB + 페이지별 청크 5–10 kB. 첫 진입 (Today, no-charts) ≈ 297 kB / gzip ~80 kB |
| 배포 | `frontend/Dockerfile` (multi-stage Node 20 build → nginx 1.27 serve) + `nginx.conf` (`/api`, `/health` → `backend:8000` proxy) + `docker-compose.yml` `web` 서비스 (port 8080) |
| Mock 통합 검증 자산 | mock seed (`scripts/seed_mock_data.py` v0.1) → 백엔드 → Vite proxy → Today + Jobs 자동 새로고침 / 비밀 마스킹 / DRY_RUN dispatcher 흐름이 그대로 시각화 |

---

## 2. 검증 요약

### 2.1 vitest (단위/통합, jsdom + msw)

```
Test Files  10 passed (10)
     Tests  36 passed (36)
```

- App routes shell 3 / useHealth 2 / Jobs 4 / TodayReport 3 / Recommendations 4 / RecommendationHistory 3 / Holdings 4 / StockDetail 3 / MarketCapTop 5 / Settings 5
- 외부 호출 0건 (msw 가 fetch 가로채기). jsdom + Recharts 위해 ResizeObserver mock 주입.
- 비밀 평문 누출 가드: `secret-*` 노드 `data-masked="true"` + `⚠ unmasked` 마커 부재 단언.

### 2.2 Playwright e2e (chromium, vite preview + page.route 모킹)

```
Running 6 tests using 6 workers
  ok 1 — all 8 sidebar menus are reachable and render their main content
  ok 2 — Jobs row click reveals result_summary JSON in detail panel
  ok 3 — MarketCap TOP filter switches from KOSPI to KOSDAQ to ALL
  ok 4 — MarketCap TOP search filters by name/symbol
  ok 5 — Settings shows masked secrets only — no plaintext leak
  ok 6 — no automation / order UI is exposed anywhere in v0.2 frontend
  6 passed (5.5s)
```

- `npm run e2e` — `vite preview` 자동 기동 + `page.route('**/api/**', ...)` 로 백엔드
  응답 mock. 실 백엔드 / 실 KIS / 실 텔레그램 호출 0건.
- 자동매매 / 실 주문 UI 부재 검증: 8 페이지 모두 `<button type="submit">` / `<form>`
  요소 0건, "실거래 시작 / 자동매매 시작 / 주문 실행 / place order / submit order"
  CTA 라벨 부재 단언.

### 2.3 백엔드 회귀

```
296 passed in 5.80s
```

- v0.1 backend 동결 정책 그대로. `app/` 디렉터리 변경 0건. 본 릴리스는 백엔드 코드 / 라우터 / 잡 / 엔진을 한 줄도 수정하지 않는다.

---

## 3. 번들 최적화 결과 (Phase E → Phase F)

| 항목 | Phase E (단일 청크) | Phase F (lazy + manualChunks) |
|---|---|---|
| 단일 main JS | 733 kB / gzip 210 kB | — |
| entry / router | — | 36 kB / gzip 12 kB |
| vendor-react | — | 157 kB / gzip 51 kB |
| vendor-query | — | 47 kB / gzip 15 kB |
| vendor-table | — | 51 kB / gzip 14 kB |
| **vendor-charts** (Recharts) | (포함) | **383 kB / gzip 105 kB — 추세 화면 진입 시에만 로드** |
| 페이지 청크 (8) | (포함) | 6–10 kB / gzip 2–3 kB 각각 |
| 공통 component 청크 | (포함) | 0.7–1.4 kB / gzip 0.4–0.8 kB 각각 |
| **첫 진입 (Today)** 합산 | **733 kB / gzip 210 kB** | **≈ 297 kB / gzip ~80 kB** |
| Vite 500 kB 경고 | ⚠ | ✅ 사라짐 |

가장 큰 효과: **Recharts 105 kB(gzip) 가 첫 진입에서 분리** — 사용자가 추천 이력 / 보유 점검에 진입할 때만 로드. 그 외 페이지는 Recharts 의존을 받지 않는다.

---

## 4. v0.2 제외 범위 (재확인)

- ❌ 실거래 자동매매 / 실 KIS 주문 API 실행 — `BrokerInterface` ABC placeholder (백엔드 v0.1)
- ❌ FULL_AUTO / APPROVAL / SMALL_AUTO 모드
- ❌ POST 트리거 / 잡 수동 실행 / 보유 추가·삭제 / 설정 변경 폼 — frontend 0건
- ❌ 백엔드 schema 변경 — `app/` 코드 변경 0건
- ❌ 실 News / Supply / Fundamental / Earnings 데이터 — `DummyScoreProducer` placeholder
- ❌ React 외 다른 프레임워크 / SSR / 모바일 레이아웃 (PC 1280px+ 우선)

---

## 5. 알려진 한계 (코드 변경 없는 후속 가능)

| 항목 | 설명 |
|---|---|
| Recharts 번들 크기 | `vendor-charts` 청크가 여전히 gzip 105 kB. v0.3 에서 `lightweight-charts` 또는 SVG 직접 작성으로 교체 검토 가능. 첫 진입에는 영향 없음. |
| 한국 시장 휴장일 안내 | Today / Holdings 페이지에 휴장일 배너 없음 — 사용자가 잡 미실행 원인을 추측해야 함. v0.3 에 한국거래소 휴장 캘린더 통합 가능. |
| StockDetail 차트 부재 | 종목 상세에서 일봉 차트가 텍스트 키-값 테이블만. `latest_price` 외 시계열을 백엔드가 노출하면 추세 라인 추가 가능 (v0.2 backend 수정 필요). |
| 다국어 / 번역 | 한국어 single-locale. i18n 도입은 v0.3+ |
| 모바일 / 태블릿 | xl 이상에서만 2-column. 모바일 레이아웃 정렬은 후속 작업. |
| openapi-typescript | hand-written `types.ts` 사용 중. 백엔드 schema 변경이 잦아지면 `npm run openapi` 로 자동 생성 전환. |
| MSW v2 + happy-dom 호환성 | jsdom 으로 픽스됨 (MSW node 가 happy-dom fetch 를 가로채지 못하는 이슈). v0.3 에서 happy-dom 재시도 가능 (속도 이점). |

---

## 6. v0.3 후보 (Backlog)

본 마감 시점에 합의된 v0.3 후보. 명시적 진입 요청 전까지 손대지 않는다.

### 6.1 운영 / UX

- 한국거래소 휴장일 캘린더 통합 (Today / Jobs 화면 안내 배너)
- sidebar collapse, breadcrumb, loading skeleton 통일
- 종목 검색 글로벌 단축키 (cmd+k 등)
- 즐겨찾기 (관심 종목) 화면 — backend POST 가 필요해 v0.2 backend 변경 동반

### 6.2 데이터 / 차트

- StockDetail 일봉 차트 — backend 가 시계열 endpoint 노출 시 활성화
- Recharts → lightweight-charts (금융 캔들 렌더 최적화) 마이그레이션 검토
- 추천 이력의 success_rate 계산을 N=5 외 다른 기간으로 토글

### 6.3 백엔드 v0.2 (별도 cycle)

- 캔들 패턴 / ATR 변동성 컴포넌트
- 실 News / Supply / Fundamental / Earnings 파이프라인
- POST 트리거 (잡 수동 실행, 추천 즉시 생성)
- WebSocket / SSE 실시간 잡 상태 (현재 polling)

### 6.4 보안 / 인증

- 로컬 / 사내망 외 노출 시 인증 추가 (현재 단일 사용자 가정)
- KIS 키 회전 자동화 / Vault 통합

---

## 7. 운영 / 인수자 가이드

### 7.1 로컬 개발

```powershell
# 백엔드 (별도 터미널)
cd "d:\dev\AI\codex\3.AI주식 자동매매 대시보드"
.\.venv\bin\python.exe -m scripts.seed_mock_data --reset
.\.venv\bin\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 프런트 (별도 터미널)
cd frontend
npm install
npm run dev   # http://127.0.0.1:5173

# 회귀
npm run test  # vitest 36
npm run e2e   # Playwright 6 (vite preview 자동 기동)
npm run build # 코드 스플릿 + 검증

# 백엔드 회귀
cd ..
.\.venv\bin\python.exe -m pytest -q   # 296 passed
```

### 7.2 Docker 배포

```powershell
docker compose up --build
# 접속: http://127.0.0.1:8080  (frontend, nginx)
# 백엔드: http://127.0.0.1:8000 (FastAPI, 정적 서빙 안 함)
# DB:    postgres  (compose volume)
```

`web` 컨테이너 nginx 가 `/api/*` 와 `/health` 를 `backend:8000` 으로 proxy 한다. **FastAPI 정적 서빙 미사용** — v0.1 backend 동결 정책 그대로 유지.

### 7.3 비밀 / 보안

- 본 릴리스 노트와 frontend 코드 어디에도 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 평문이 기록되지 않았다. 백엔드 `/api/settings` 응답이 마스킹 (`5015****1-01`) 한 값을 그대로 표시.
- `frontend/.env` 는 `.gitignore` 등록, `.env.example` 만 커밋.
- e2e 는 `page.route` mock 으로 동작 — 실 자격증명을 절대 사용하지 않는다.

---

**이 문서로 v0.2 frontend MVP 마감을 선언한다.** v0.3 진입은 사용자의 명시적 요청이 있을 때 시작한다.
