# Stock AI Platform

[![CI](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml)

한국투자증권 API 기반 AI 주식 분석·추천·보유점검 플랫폼입니다.

> **v0.4 Analyst & Theme Intelligence — 마감 완료.**
> 현재 인수 태그는 `v0.4-frontend-reports`이며, 최종 마감 태그는
> `v0.4-final` 예정이다. v0.4는 증권사 리포트 메타데이터, 테마/종목 매핑,
> 변화 시그널, 컨센서스 스냅샷, `report_score` / `theme_signal_score`, 그리고
> StockDetail / Recommendations 대시보드 표시까지 마감했다.
>
> 최신 통과 회귀 게이트 — **백엔드 pytest 382 / frontend vitest 60 / Playwright e2e 9 /
> build 통과**. 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST
> 트리거 UI 는 모든 사이클에서 코드 일체 포함하지 않습니다 (`BrokerInterface`
> 는 ABC placeholder 만 유지). 자세한 정책은 [`AGENTS.md`](./AGENTS.md) /
> [`ROADMAP.md`](./ROADMAP.md) 참조.
>
> **저작권 정책 (v0.4)**: 리포트 원문 본문 / paragraph 저장 0건, PDF BLOB
> 저장 0건, 자동 크롤링 0건, `source_file_path` 외부 노출 0건. 운영자가 직접
> 작성한 짧은 요약 (≤ 500자) 만 저장. CSV importer 는 헤더에 `body /
> content / paragraph_text / 본문 / 원문 / 전문` 등 13종 column 이 포함되면
> 파일을 즉시 거부.
>
> **누적 인수 태그**: `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
> → `v0.2-frontend-final` → `v0.3-phase-a-ci` → `v0.3-backend-analysis` →
> `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final` →
> `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` →
> **`v0.4-frontend-reports`** → `v0.4-final` (예정).
>
> 이전 사이클 마감 사유: [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md)
> (백엔드, 296 passed) / [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md)
> (PC 대시보드 8 화면, vitest 36 / e2e 6) / [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md)
> (v0.3 분석·운영, 319 / 59 / 8). v0.4 진행 상태는 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
> §0 참조.

## 1. 프로젝트 목표

본 프로젝트는 **실거래 자동매매가 아닌 read-only 분석 / 추천 / 보유점검 +
증권사 리포트·테마 인텔리전스 + 대시보드** 플랫폼입니다.

현재까지 마감된 사이클 (v0.1 ~ v0.4) 의 누적 기능:

- 한국투자증권 API 기반 read-only 데이터 수집
- 시가총액 TOP 500 종목 유니버스 관리
- 관심종목 / 보유종목 관리
- 일봉 / 현재가 저장
- 기술적 지표 (MA / RSI / MACD / breakout / ma_alignment) + **캔들 5종 / Wilder ATR(14) / 4단계 변동성** (v0.3)
- 보유 종목 장전 / 장후 점검
- 신규 추천 TOP 5 + 1/3/5/20일 후 성과 검증
- 텔레그램 알림 (DRY_RUN 기본)
- FastAPI **read-only** 대시보드 API (15+ GET, **POST 0건**)
- **PC 대시보드 SPA** (8 화면, Vite + React + TypeScript) — v0.2
- **KRX 휴장일 정적 캘린더 + MarketStatusBanner** — v0.3
- **StockDetail 일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자** — v0.3
- **GitHub Actions CI** (3 잡: backend pytest / frontend vitest+build / Playwright e2e) — v0.3
- **증권사 애널리스트 리포트 인텔리전스 DB 기반** (6 ORM + 6 Repository) — v0.4
- **CSV import pipeline + 일별 컨센서스 스냅샷 잡** — v0.4
- **`report_score` / `theme_signal_score` 추천 보조 통합** — v0.4
- **StockDetail 리포트/컨센서스/테마/시그널 카드 + Recommendations score 컬럼** — v0.4
- data_snapshots / decision_logs / job_runs / notification_logs persistence
- 테스트 가능한 구조 (backend pytest 382, vitest 60, e2e 9)

## 2. 전체 사이클 제외 범위 (v0.1 ~ v0.4 일관 정책)

다음 기능은 **모든 사이클에서 코드 일체 포함하지 않습니다.** 자동매매 진입은
별도 보안 / 컴플라이언스 사이클이 선행되어야 가능합니다.

- 실거래 자동매매 (FULL_AUTO / APPROVAL / SMALL_AUTO 모드)
- 실제 주문 API 실행 (`BrokerInterface` 는 ABC placeholder 만 유지)
- POST / PUT / DELETE 라우터 (read-only API 만)
- 가상 증권사 서버 / MockBroker / ReplayBroker / SimulationBroker
- 전략 자동 튜닝 / Strategy 모듈
- 전용 AI 모델 학습 / Custom AI training
- 대량 가상 데이터 생성
- 완전한 백테스트 시스템
- **(v0.4)** 증권사 리포트 자동 크롤링 / 스크레이핑 (수동 CSV 만)
- **(v0.4)** 리포트 원문 본문 / PDF BLOB 저장
- **(v0.4)** `source_file_path` API / 프런트 / e2e 노출

위 항목은 모두 [`ROADMAP.md`](./ROADMAP.md) 의 Future Backlog 로 분류되어 있고,
각 항목은 진입 전제 조건 (예: 인증 / 컴플라이언스 / 자본 한도) 이 명시되어
있습니다.

## 3. 권장 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python, FastAPI |
| DB | PostgreSQL, SQLite 초기 허용 |
| ORM | SQLAlchemy |
| Scheduler | APScheduler |
| Analysis | pandas, numpy |
| Test | pytest |
| Notification | Telegram Bot API |
| Frontend | React 또는 Next.js |
| Config | .env |

## 4. 프로젝트 문서

| 파일 | 설명 |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | Codex 가 매번 따라야 하는 핵심 지침 — 프로젝트 전체 (v0.1~v0.4) 규칙, 13 코딩 에이전트 역할 |
| [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) | 현재 사이클 상태 / 시작·마감 선언 / Phase 결과 요약. 새 세션이 가장 먼저 읽어야 할 파일 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 시스템 구조 — 10 layer (Data / Repository / Analysis / Report Intelligence / Scoring / Notification / API / Frontend / Scheduler / Ops·CI) |
| [`ROADMAP.md`](./ROADMAP.md) | v0.1 ~ v0.4 진행 이력 + v0.5 후보 + Future Backlog (자동매매) |
| [`TASKS.md`](./TASKS.md) | 사이클별 phase 체크리스트 |
| [`PLANS.md`](./PLANS.md) | Codex 실행 계획 (PLAN-0001 ~ PLAN-0004) |
| [`API_SPEC.md`](./API_SPEC.md) | FastAPI read-only GET API 명세 |
| [`DB_SCHEMA.md`](./DB_SCHEMA.md) | 23 테이블 (v0.1 17 + v0.4 6) 명세 + 저작권 정책 |
| [`TESTING.md`](./TESTING.md) | 테스트 전략 + 게이트 baseline (335 / 59 / 8) |
| [`SECURITY.md`](./SECURITY.md) | 보안 원칙 (KIS / Telegram / source_file_path 마스킹) |
| [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) | mock seed 통합 시나리오 + KIS 모의투자 검증 절차 |
| [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) | 운영 KIS 키 사전 검증 체크리스트 |
| [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) | v0.1 백엔드 마감 선언 |
| [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) | v0.2 프런트 MVP 마감 선언 |
| [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) | v0.3 분석·운영 마감 선언 |
| [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md) | v0.4 Analyst & Theme Intelligence 마감 선언 |
| `stock_ai_project_codex_brief.md` | 초기 프로젝트 브리프 (역사적 — 실제 진행은 ROADMAP 참조) |
| `stock_ai_detailed_spec.md` | 초기 상세 기능 명세 (역사적) |
| `codex_agent_creation_spec.md` | 초기 코딩 에이전트 생성 명세 (역사적) |
| `.env.example` | 환경변수 예시 |

## 5. 권장 개발 순서

1. 아키텍처와 인터페이스
2. DB 모델과 Repository
3. 최소 실행환경
4. 한국투자증권 API 클라이언트
5. 데이터 수집/정제
6. 기술적 분석과 점수 계산
7. 추천/보유 점검 서비스
8. 텔레그램 리포트
9. FastAPI 대시보드 API
10. 테스트와 문서화

## 6. 누적 사이클 상태 (v0.1 ~ v0.4)

| 사이클 | 상태 | 회귀 게이트 | 최종 태그 |
|---|---|---|---|
| v0.1 Backend | ✅ 마감 | pytest 296 | `v0.1-backend-kis-paper-verified` |
| v0.2 Frontend MVP | ✅ 마감 | pytest 296 / vitest 36 / e2e 6 | `v0.2-frontend-final` |
| v0.3 Analysis & Ops | ✅ 마감 | pytest 319 / vitest 59 / e2e 8 | `v0.3-final` |
| v0.4 Phase A — Analyst & Theme Intelligence DB | ✅ 인수 | pytest 335 / vitest 59 / e2e 8 | `v0.4-backend-reports` |
| v0.4 Phase B — CSV import CLI + consensus snapshot job | ✅ 인수 | pytest 362 / vitest 59 / e2e 8 | `v0.4-import-pipeline` |
| v0.4 Phase C — `report_score` + `theme_signal_score` 계산기 | ✅ 인수 | pytest 379 / vitest 59 / e2e 8 | `v0.4-report-score` |
| v0.4 Phase D — 프런트 (StockDetail 리포트·테마·시그널 카드 + Recommendations score 컬럼) | ✅ 인수 | pytest 382 / vitest 60 / e2e 9 | `v0.4-frontend-reports` |
| v0.4 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 382 / vitest 60 / e2e 9 / build | `v0.4-final` (예정) |

### 영역별 상태

| 영역 | 상태 |
|---|---|
| DB 모델 / Repository | 17 + 6 = **23 테이블 ORM**, 16 + 6 = **22 Repository** |
| KIS 데이터 수집 | `KisClient` + 정규화 / 품질 검사 / `DailyPriceCollector` / `MarketCapRankingCollector` (mock-injectable) |
| 분석 / 점수 | `TechnicalAnalyzer` (MA/RSI/MACD/breakout/ma_alignment + 캔들 5종 / ATR / 변동성), `ScoringEngine`, `RiskEngine`, `DummyScoreProducer` |
| 추천 / 보유 점검 | `RecommendationEngine`, `HoldingCheckEngine` (PRE/POST), `RecommendationResultService` (1/3/5/20일 성과) |
| 알림 / 리포트 | `ReportGenerator` + `TelegramNotifier` (DRY_RUN 기본) + `NotificationService` + 3 dispatcher |
| Backend API | read-only GET API. `/api/stocks/{symbol}/prices`, `/api/stocks/{symbol}/reports`, `analyst_reports` 응답 포함. POST 0건 |
| Scheduler | APScheduler + `run_job` 래퍼 + **7개 잡** (v0.4 Phase B 의 `update_report_consensus_snapshots` 06:30 KST 추가됨) |
| Import Pipeline (v0.4 Phase B) | `scripts/import_analyst_reports.py` argparse CLI (default dry-run, `--commit` 시 DB 적재) + `app/data/importers/analyst_reports.py` (35 컬럼 CSV → 4 entity 분해 + 검증 + 멱등 upsert). Forbidden body column 13종 거부, `summary` 500자 truncate, `source_file_path` 마스킹. pandas / openpyxl 의존성 0건 |
| Frontend | Vite + React + TS, 8 화면, 코드 스플릿, KRX 휴장 배너, StockDetail 일봉 차트 + 리포트 카드, msw + Playwright |
| **Report Intelligence (v0.4)** | 6 ORM + 6 Repository + CSV import + consensus snapshot job + report/theme score + dashboard 표시 |
| Ops / CI | GitHub Actions 3 잡 (backend pytest / vitest+build / Playwright e2e), main + PR 자동 검증, mock 환경 변수 |
| 통합 검증 | `scripts/seed_mock_data.py` (멱등) + `INTEGRATION_RUNBOOK.md` |

세부 산출물 / 테스트 카운트 / 변경 이력은 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
와 [`TASKS.md`](./TASKS.md) 참고. v0.5 후보는 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
§0의 후속 후보를 참조.

## 7. 실행 순서 (권장)

새 세션 / 인수자 / QA 가 한 번에 따라가야 할 표준 순서. 각 단계는 모두 dry-run
/ mock-only — 실 KIS 호출, 실 텔레그램 발송, 자동매매 코드는 이 순서 안에서
절대 동작하지 않는다.

| 단계 | 명령 | 출력 / 검증 |
|---|---|---|
| 7.1 의존성 | `.\.venv\bin\python.exe -m pip install -e ".[dev]"` | 정상 설치 |
| 7.2 Docker (권장) 또는 로컬 uvicorn | §8 또는 §9 | `/health` 200 |
| 7.3 Mock seed | `.\.venv\bin\python.exe -m scripts.seed_mock_data --reset` | stocks 5 / daily_prices 150 등 (§10) |
| 7.4 통합 시나리오 (6잡 + 13API) | [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §3 ~ §5 그대로 따라감 | 모든 잡 SUCCESS, 13/13 API 200, notification_logs DRY_RUN |
| 7.5 회귀 게이트 | `.\.venv\bin\python.exe -m pytest -q` | 382 passed (v0.4 마감 시점) |
| 7.6 (운영 전) 실 KIS 키 사전 검증 | [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) | 체크리스트 항목별 통과 — 코드 변경 없음 |

## 8. Docker 로컬 실행

Docker Compose는 v0.1 로컬 검증용으로 PostgreSQL과 FastAPI backend를 함께 실행한다.
기본 설정은 안전하게 `SCHEDULER_ENABLED=false`, `TELEGRAM_ENABLED=false`,
`FEATURE_REAL_ORDER_EXECUTION=false`, `FEATURE_FULL_AUTO=false`로 고정되어 실제 KIS 주문,
자동매매, 텔레그램 발송을 하지 않는다.

```powershell
docker compose up --build
Invoke-RestMethod http://127.0.0.1:8000/health
```

Compose 기본 DB URL:

```text
postgresql+psycopg2://stock_user:stock_password@db:5432/stock_db
```

종료 / 볼륨 정리:

```powershell
docker compose down       # 컨테이너만 종료
docker compose down -v    # DB 볼륨까지 삭제 (필요 시에만)
```

로그 파일을 남기고 싶으면 `.env` 또는 Compose 환경변수에서 `LOG_TO_FILE=true`로 설정한다.
로그 디렉터리는 기본적으로 `logs/`이며, Git에는 `.gitkeep`만 유지된다.

## 9. 로컬 uvicorn 실행 (대안)

Docker 를 쓰지 않을 때.

```powershell
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\bin\python.exe -m pip install -e ".[dev]"
.\.venv\bin\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
```

MSYS2 Python에서 `greenlet` 빌드 오류로 SQLAlchemy 설치가 실패하면 현재 동기식 DB
테스트 범위에서는 다음 명령으로 로컬 검증이 가능하다.

```powershell
.\.venv\bin\python.exe -m pip install "fastapi>=0.99,<0.100" "pydantic>=1.10,<2.0" "uvicorn>=0.30,<1.0" "pytest>=8.0,<9.0" "httpx>=0.24,<0.27" "python-dotenv>=1.0,<2.0"
.\.venv\bin\python.exe -m pip install "SQLAlchemy>=2.0,<3.0" --no-deps
.\.venv\bin\python.exe -m pip install -e . --no-deps
```

## 10. Mock Seed 데이터 / 통합 실행 시나리오

실 KIS 키 / 실 텔레그램 없이 백엔드 전체 흐름 (v0.1 베이스 + v0.3 분석 보강)
을 로컬에서 검증하려면 `scripts/seed_mock_data.py` 로 결정론적 mock 데이터를
적재한 뒤, [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) 에 정리된 6개 잡
+ 14+ GET API 시나리오를 따라간다.

```powershell
# 1) Mock 시드 적재 (로컬 SQLite, 멱등 — `--reset`은 destructive)
.\.venv\bin\python.exe -m scripts.seed_mock_data --reset

# 2) 시나리오는 INTEGRATION_RUNBOOK.md §3 (잡), §4 (API) 참조
```

시드 범위: stocks, market_cap_rankings, stock_universes/members, daily_prices,
stock_indicators, holdings, recommendation_runs, recommendations, data_snapshots,
holding_checks. 자세한 건수와 종목 / 점검 데이터 구성은
[INTEGRATION_RUNBOOK.md §1.2](./INTEGRATION_RUNBOOK.md) 참고.

가장 최근 통합 실행 결과(6잡 SUCCESS, 13/13 API 200, notification_logs 7건 등)는
[`PROJECT_STATUS.md` §2 "v0.1 통합 실행 결과"](./PROJECT_STATUS.md) 에 인수
스냅샷으로 보관되어 있다.

## 11. 테스트

```powershell
.\.venv\bin\python.exe -m pytest
```

외부 API, 텔레그램, 주문 기능은 테스트에서 실제로 호출하지 않습니다 (mock /
`httpx.MockTransport` / `FakeKisDataProvider`).

현재 회귀 기준선 (v0.4 Phase B 시점):

- backend pytest **362 passed** (v0.1 296 → v0.3 319 → v0.4 Phase A 335 → v0.4 Phase B 362)
- frontend vitest **59 passed** (12 파일)
- Playwright e2e **8 passed** (chromium + page.route mock)
- frontend build (`tsc --noEmit && vite build`) 그린

자세한 테스트 정책 / 카테고리는 [`TESTING.md`](./TESTING.md) 참조.

## 12. CI (GitHub Actions)

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) 이 push / pull_request 이벤트 (대상: `main`) 마다 다음 3 잡을 자동 실행합니다.

| 잡 | 단계 |
|---|---|
| `backend / pytest` | Python 3.12 + pip cache → `pip install -e ".[dev]"` → `pytest -q` |
| `frontend / vitest + build` | Node 20 + npm cache → `npm ci` → `npm run test` → `npm run build` |
| `frontend / playwright e2e` | Node 20 + npm cache + Playwright 브라우저 캐시 → `npm ci` → `npx playwright install --with-deps chromium` → `npm run build` → `npm run e2e` (`vite preview` + `page.route` mock — 실 백엔드 / KIS / Telegram 호출 0건). 실패 시 `playwright-report/` artifact 업로드 |

CI 환경 변수는 모두 mock / dry-run 값으로 강제됩니다 (`KIS_USE_PAPER=true`, `TELEGRAM_ENABLED=false`, `FEATURE_REAL_ORDER_EXECUTION=false`, `FEATURE_FULL_AUTO=false`, fake KIS / Telegram 키). 실 자격증명 / 실 KIS API / 실 텔레그램 봇 사용 0건.

로컬에서 동일 게이트를 돌릴 때:

```powershell
# 백엔드
.\.venv\bin\python.exe -m pytest -q

# 프런트
cd frontend
npm run test
npm run build
npm run e2e
```

## 13. 운영 전 KIS 실 키 검증

운영 환경에서 실 KIS 키 + 실 텔레그램으로 한 번 검증하기 전에는
[`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 의 체크리스트를 항목 단위로
확인한다. 코드 변경 없이 `.env` / 운영 SOP 만으로 통과해야 한다.

## 14. Codex 첫 실행 프롬프트 예시

```text
AGENTS.md, PROJECT_STATUS.md (§0), ARCHITECTURE.md, TASKS.md, ROADMAP.md 를
먼저 읽고, 현재 사이클 (v0.4 Phase A+B 인수 / Phase C 진입 대기) 범위를
벗어나지 않는 개발 계획을 작성해줘.
아직 코드는 수정하지 말고 TASKS.md 업데이트 계획만 제안해줘.
```

## 15. 주의

이 프로젝트는 **투자 판단 보조 도구** 입니다. v0.1 ~ v0.4 어디에도 실제 주문 /
자동매매 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드를 구현하지 않습니다.

자동매매 진입은 별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실
제한 사이클이 선행되어야 검토할 수 있습니다 ([`ROADMAP.md`](./ROADMAP.md) 의
Future Backlog 참조).
