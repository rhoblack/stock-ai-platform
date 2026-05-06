# Stock AI Platform

[![CI](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml)

한국투자증권 API 기반 AI 주식 분석·추천·보유점검 플랫폼입니다.

> **v0.6 Fundamental & Earnings Intelligence — 마감 완료.**
> 현재 누적 인수 태그는 `v0.6-frontend-fundamentals`이며, 최종 마감 태그는
> `v0.6-final` 예정이다. v0.6은 운영자 수동 CSV import 기반의 재무 / 실적 데이터
> 라인 (`fundamental_snapshots` 24번째 + `earnings_events` 25번째 테이블) 첫
> 도입, `fundamental_score` (가중치 15%) + HoldingCheckEngine 의 `earnings_score`
> placeholder 의 첫 real 화 (`RealFundamentalScoreProducer` +
> `RealEarningsScoreProducer`), 백엔드 read-only API 3종 (`/api/stocks/{symbol}/fundamentals`
> + `/api/stocks/{symbol}/earnings` + `/api/calendar/earnings`), StockDetail 의
> 재무 / 실적 두 카드 + Today 의 다가오는 실적 카드 + Recommendations / Holdings
> evidence cell 추가를 진행한 사이클이다. 추천 / 보유 응답에는 `fundamental_evidence` /
> `earnings_evidence` 가 명시 nullable 필드로 노출된다 (라우터 단계 화이트리스트
> 통과, 본문 / `source_file_path` 0건).
>
> 최신 통과 회귀 게이트 — **백엔드 pytest 558 / frontend vitest 77 / Playwright e2e 13 /
> build 통과**. 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST
> 트리거 UI 는 모든 사이클에서 코드 일체 포함하지 않습니다 (`BrokerInterface`
> 는 ABC placeholder 만 유지). 자세한 정책은 [`AGENTS.md`](./AGENTS.md) /
> [`ROADMAP.md`](./ROADMAP.md) 참조.
>
> **저작권 / 데이터 정책 (v0.4 + v0.5 + v0.6 누적)**: 리포트·뉴스·공시·재무·실적
> 원문 본문 (paragraph) 저장 0건, PDF / Excel BLOB 저장 0건, 자동 크롤링 0건,
> `source_file_path` 외부 노출 0건. 모든 DTO·ORM 어디에도 body / content /
> full_text / paragraph_text / raw_text / 본문 / 원문 / 전문 13종 forbidden
> 컬럼 없음 (단위 테스트가 명시 단언 + CSV importer 가 forbidden header 즉시
> 거부). 수집 잡 (`collect_news` 19:00 KST / `collect_disclosures` 20:00 KST) +
> 재무 / 실적 자동 fetch (`fundamental_collection_enabled` /
> `earnings_collection_enabled`) 모두 default OFF — 운영자가 `.env` 에 명시
> 설정 시에만 동작. v0.6 시점에서는 재무 / 실적 scheduler job 자체를 추가하지
> 않았으므로 운영 default 영향 0건. DART API 자동 호출 0건 (1단계는 운영자
> 수동 CSV 만, 실 provider 는 v0.7+ 후보). evidence 응답은 라우터 단계
> 화이트리스트로 defense-in-depth 2단 검증 — `fundamental_evidence` 는 10 키 +
> reason / `earnings_evidence` 는 8 키 + reason 만 노출.
>
> **누적 인수 태그**: `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
> → `v0.2-frontend-final` → `v0.3-phase-a-ci` → `v0.3-backend-analysis` →
> `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final` →
> `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` →
> `v0.4-frontend-reports` → `v0.4-final` →
> `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` →
> `v0.5-frontend-themes` → `v0.5-final` →
> (v0.6 Phase A 별도 태그 부재, 커밋 `0d3dba5` + `da3567f` 로 추적) →
> `v0.6-earnings-event-pipeline` → `v0.6-fundamental-score` →
> **`v0.6-frontend-fundamentals`** → `v0.6-final` (예정).
>
> 이전 사이클 마감 사유: [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md)
> (백엔드, 296 passed) / [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md)
> (PC 대시보드 8 화면, vitest 36 / e2e 6) / [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md)
> (v0.3 분석·운영, 319 / 59 / 8) / [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md)
> (v0.4 Analyst & Theme Intelligence, 382 / 60 / 9) /
> [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md) (v0.5 News·공시·테마 랭킹, 481 / 68 / 11) /
> [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md) (v0.6 Fundamental & Earnings,
> **558 / 77 / 13**). 다음 사이클 후보는 [`ROADMAP.md`](./ROADMAP.md) v0.7 참조.

## 1. 프로젝트 목표

본 프로젝트는 **실거래 자동매매가 아닌 read-only 분석 / 추천 / 보유점검 +
증권사 리포트·테마 인텔리전스 + News·공시 데이터 라인 + 재무·실적 인텔리전스 +
대시보드** 플랫폼입니다.

현재까지 마감된 사이클 (v0.1 ~ v0.6) 의 누적 기능:

- 한국투자증권 API 기반 read-only 데이터 수집
- 시가총액 TOP 500 종목 유니버스 관리
- 관심종목 / 보유종목 관리
- 일봉 / 현재가 저장
- 기술적 지표 (MA / RSI / MACD / breakout / ma_alignment) + **캔들 5종 / Wilder ATR(14) / 4단계 변동성** (v0.3)
- 보유 종목 장전 / 장후 점검
- 신규 추천 TOP 5 + 1/3/5/20일 후 성과 검증
- 텔레그램 알림 (DRY_RUN 기본)
- FastAPI **read-only** 대시보드 API (17+ GET, **POST 0건**)
- **PC 대시보드 SPA** (9 화면, Vite + React + TypeScript) — v0.2 → v0.5
- **KRX 휴장일 정적 캘린더 + MarketStatusBanner** — v0.3
- **StockDetail 일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자** — v0.3
- **GitHub Actions CI** (3 잡: backend pytest / frontend vitest+build / Playwright e2e) — v0.3
- **증권사 애널리스트 리포트 인텔리전스 DB 기반** (6 ORM + 6 Repository) — v0.4
- **CSV import pipeline + 일별 컨센서스 스냅샷 잡** — v0.4
- **`report_score` / `theme_signal_score` 추천 보조 통합** — v0.4
- **StockDetail 리포트/컨센서스/테마/시그널 카드 + Recommendations score 컬럼** — v0.4
- **News / 공시 데이터 라인** — `NewsProviderInterface` / `DisclosureProviderInterface` ABC + `NewsCollector` / `DisclosureCollector` + `news_items.category` + 공시 5 카테고리 keyword 분류 + `collect_news` (19:00) / `collect_disclosures` (20:00) 잡 (모두 default OFF) — v0.5
- **`news_score` 첫 real 화 + RiskEngine 보강** — `RealNewsScoreProducer` (composition 패턴) + `DisclosureRiskProducer` (`RISK_DISCLOSURE` flag + cap +10 penalty) + `ScoreProducerInterface` ABC — v0.5
- **테마 랭킹 / 상세 화면** — `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` + 프런트 9번째 화면 `/themes` + `/themes/:theme_id` + Sidebar `테마 (β)` 메뉴 — v0.5
- **추천 응답 evidence 노출** — `RecommendationItemSchema.news_evidence` + `disclosure_risk_evidence` (whitelist 안전 필드만) + `RelatedThemesCard` 테마 링크 + `RecommendationsTable` evidence 컬럼 — v0.5
- **재무 / 실적 데이터 라인** — `FundamentalProviderInterface` / `EarningsProviderInterface` ABC + `FundamentalSnapshot` (24번째) + `EarningsEvent` (25번째) ORM + `scripts/import_fundamentals.py` / `scripts/import_earnings.py` argparse CLI (default dry-run) + BEAT/MEET/MISS 분류 + `FakeFundamentalProvider` / `FakeEarningsProvider` (실 DART 호출 0건) — v0.6
- **`fundamental_score` + `earnings_score` 첫 real 화** — `RealFundamentalScoreProducer` (composition 패턴, recommendation 가중치 15%) + `RealEarningsScoreProducer` (HoldingCheckEngine). 산식 모두 룰 기반, snapshot/event 부재 시 50 fallback. 본 weight 변경 0건 — v0.6
- **재무 / 실적 read-only API 3종** — `GET /api/stocks/{symbol}/fundamentals` + `GET /api/stocks/{symbol}/earnings` + `GET /api/calendar/earnings` (모두 read-only, source_file_path 0건) — v0.6
- **StockDetail 두 카드 + Today 한 카드 + Recommendations / Holdings evidence** — `FundamentalsCard` (PER/PBR/ROE/부채/배당/성장률 + history) + `EarningsCard` (BEAT/MEET/MISS tone-color badge + actual vs consensus + history) + `UpcomingEarningsCard` (limit 5) + `RecommendationsTable` 의 fund/earnings evidence cell + `RecentHoldingChecksCard` 의 earnings evidence 컬럼 + `HoldingCheckSchema` 의 evidence 3종 (v0.5 이연분 흡수) — v0.6
- data_snapshots / decision_logs / job_runs / notification_logs persistence
- 테스트 가능한 구조 (backend pytest **558**, vitest **77**, e2e **13**, build)

## 2. 전체 사이클 제외 범위 (v0.1 ~ v0.6 일관 정책)

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
- **(v0.5)** News / 공시 자동 크롤링 / 스크레이핑 (FakeProvider 만, 실 RSS / DART API 호출 0건)
- **(v0.5)** News / 공시 본문 paragraph 저장 — 메타데이터 (title / url / provider / category / sentiment / 짧은 summary) 만
- **(v0.5)** 자동 fetch default ON — `news_collection_enabled` / `disclosure_collection_enabled` 기본 false
- **(v0.5)** 추천 산식 본 weight 변경 — `news_score` 만 50 → real, 가중치 25% 그대로
- **(v0.6)** DART API 자동 호출 / 자동 크롤링 (1단계는 운영자 수동 CSV 만, 실 provider 는 v0.7+ 후보)
- **(v0.6)** 재무 / 실적 본문 paragraph 저장 — 정량 지표 + 짧은 메모 (≤500자) + URL / source 메타데이터만
- **(v0.6)** 재무제표 PDF / Excel BLOB DB 저장
- **(v0.6)** 재무 / 실적 자동 fetch default ON — `fundamental_collection_enabled` / `earnings_collection_enabled` 기본 false (v0.6 시점에서는 scheduler job 자체 미추가)
- **(v0.6)** 추천 / 보유 산식 본 weight 변경 — `fundamental_score` 만 50 → real (가중치 15%), `earnings_score` 만 50 → real (가중치 그대로)

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
| [`AGENTS.md`](./AGENTS.md) | Codex 가 매번 따라야 하는 핵심 지침 — 프로젝트 전체 (v0.1~v0.6) 규칙, 13 코딩 에이전트 역할 |
| [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) | 현재 사이클 상태 / 시작·마감 선언 / Phase 결과 요약. 새 세션이 가장 먼저 읽어야 할 파일 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 시스템 구조 — 10 layer (Data / Repository / Analysis / Report Intelligence / Scoring / Notification / API / Frontend / Scheduler / Ops·CI) |
| [`ROADMAP.md`](./ROADMAP.md) | v0.1 ~ v0.6 진행 이력 + v0.7 후보 + Future Backlog (자동매매) |
| [`TASKS.md`](./TASKS.md) | 사이클별 phase 체크리스트 |
| [`PLANS.md`](./PLANS.md) | Codex 실행 계획 (PLAN-0001 ~ PLAN-0006) |
| [`API_SPEC.md`](./API_SPEC.md) | FastAPI read-only GET API 명세 (20+ GET, POST 0건, v0.5 §14 테마 + v0.6 §15 재무·실적 포함) |
| [`DB_SCHEMA.md`](./DB_SCHEMA.md) | 25 테이블 (v0.1 17 + v0.4 6 + v0.6 2) 명세 + 저작권 정책 + v0.5 `news_items.category` |
| [`TESTING.md`](./TESTING.md) | 테스트 전략 + 게이트 baseline (558 / 77 / 13 / build) |
| [`SECURITY.md`](./SECURITY.md) | 보안 원칙 (KIS / Telegram / source_file_path 마스킹 + News·공시·재무·실적 본문 미저장) |
| [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) | mock seed 통합 시나리오 + KIS 모의투자 검증 + News·공시·테마·재무·실적 운영 절차 (v0.5 §10~§12 + v0.6 §13~§15) |
| [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) | 운영 KIS 키 사전 검증 체크리스트 |
| [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) | v0.1 백엔드 마감 선언 |
| [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) | v0.2 프런트 MVP 마감 선언 |
| [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) | v0.3 분석·운영 마감 선언 |
| [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md) | v0.4 Analyst & Theme Intelligence 마감 선언 |
| [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md) | v0.5 News·공시·테마 랭킹 마감 선언 |
| [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md) | v0.6 Fundamental & Earnings Intelligence 마감 선언 |
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

## 6. 누적 사이클 상태 (v0.1 ~ v0.6)

| 사이클 | 상태 | 회귀 게이트 | 최종 태그 |
|---|---|---|---|
| v0.1 Backend | ✅ 마감 | pytest 296 | `v0.1-backend-kis-paper-verified` |
| v0.2 Frontend MVP | ✅ 마감 | pytest 296 / vitest 36 / e2e 6 | `v0.2-frontend-final` |
| v0.3 Analysis & Ops | ✅ 마감 | pytest 319 / vitest 59 / e2e 8 | `v0.3-final` |
| v0.4 Analyst & Theme Intelligence | ✅ 마감 | pytest 382 / vitest 60 / e2e 9 / build | `v0.4-final` |
| v0.5 News, Disclosure & Theme Ranking | ✅ 마감 | pytest 481 / vitest 68 / e2e 11 / build | `v0.5-final` |
| v0.6 Phase A — Fundamental data layer + CSV import | ✅ 인수 | pytest 부분 통과 (커밋 추적) | (별도 태그 부재 — `0d3dba5` + `da3567f`) |
| v0.6 Phase B — Earnings event layer + CSV import | ✅ 인수 | pytest 부분 통과 | `v0.6-earnings-event-pipeline` |
| v0.6 Phase C — `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + evidence 통합 | ✅ 인수 | pytest 544 | `v0.6-fundamental-score` |
| v0.6 Phase D — read-only API 3종 + StockDetail 카드 + Today 카드 + evidence cell | ✅ 인수 | pytest 558 / vitest 77 / e2e 13 | `v0.6-frontend-fundamentals` |
| v0.6 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 558 / vitest 77 / e2e 13 / build | `v0.6-final` (예정) |

### 영역별 상태

| 영역 | 상태 |
|---|---|
| DB 모델 / Repository | 17 + 6 + 2 = **25 테이블 ORM**, 16 + 6 + 2 = **24 Repository**. v0.5 는 `news_items.category` ALTER ADD COLUMN, v0.6 은 `fundamental_snapshots` + `earnings_events` 신규 |
| KIS 데이터 수집 | `KisClient` + 정규화 / 품질 검사 / `DailyPriceCollector` / `MarketCapRankingCollector` (mock-injectable) |
| **News / 공시 데이터 라인 (v0.5)** | `NewsProviderInterface` / `DisclosureProviderInterface` ABC + `NewsCollector` / `DisclosureCollector` + 9 필드 DTO (본문 0건) + `news_items.category` 6 enum + 공시 5 카테고리 keyword 분류 + `collect_news` (19:00) / `collect_disclosures` (20:00) 잡 (모두 default OFF) |
| **재무 / 실적 데이터 라인 (v0.6)** | `FundamentalProviderInterface` / `EarningsProviderInterface` ABC + `FundamentalSnapshot` (24번째, 8 정량 지표) + `EarningsEvent` (25번째, BEAT/MEET/MISS) + `scripts/import_fundamentals.py` / `scripts/import_earnings.py` argparse CLI (default dry-run) + `FakeFundamentalProvider` / `FakeEarningsProvider` (실 DART 호출 0건) |
| 분석 / 점수 | `TechnicalAnalyzer` (MA/RSI/MACD/breakout/ma_alignment + 캔들 5종 / ATR / 변동성), `ScoringEngine`, `RiskEngine`, `ScoreProducerInterface` ABC + `DummyScoreProducer` + `RealNewsScoreProducer` + `DisclosureRiskProducer` (v0.5) + **`RealFundamentalScoreProducer` + `RealEarningsScoreProducer`** (v0.6) |
| 추천 / 보유 점검 | `RecommendationEngine`, `HoldingCheckEngine` (PRE/POST), `RecommendationResultService` (1/3/5/20일 성과). v0.5 의 evidence 4종 + **v0.6 의 `fundamental_evidence` (recommendation) + `earnings_evidence` (holding)** 모두 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 에 기록 |
| 알림 / 리포트 | `ReportGenerator` + `TelegramNotifier` (DRY_RUN 기본) + `NotificationService` + 3 dispatcher |
| Backend API | read-only GET API **20+ 라우터**. v0.5 `/api/themes/ranking` + `/api/themes/{theme_id}` + **v0.6 `/api/stocks/{symbol}/fundamentals` + `/api/stocks/{symbol}/earnings` + `/api/calendar/earnings`**. POST 0건. RecommendationItemSchema / HoldingCheckSchema 에 evidence 4종 nullable 필드 (라우터 단계 화이트리스트) |
| Scheduler | APScheduler + `run_job` 래퍼 + **9개 잡** (v0.4 Phase B `update_report_consensus_snapshots` 06:30 + v0.5 `collect_news` 19:00 + `collect_disclosures` 20:00, 두 v0.5 잡은 default OFF). v0.6 에서는 scheduler job 추가 0건 (수동 CSV import 만) |
| Import Pipeline | v0.4 `scripts/import_analyst_reports.py` + **v0.6 `scripts/import_fundamentals.py` + `scripts/import_earnings.py`** (모두 argparse CLI, default dry-run, `--commit` 시 DB 적재). Forbidden body column 13종 거부, `summary` / `memo` 500자 truncate, `source_file_path` 마스킹. pandas / openpyxl 의존성 0건 |
| Frontend | Vite + React + TS, **9 화면** (v0.5 `테마 (β)` 추가), 코드 스플릿, KRX 휴장 배너, StockDetail 일봉 차트 + 리포트 카드 + 테마 링크 + impact_path badge + **Fundamentals + Earnings 카드 (v0.6)** + Today **UpcomingEarnings 카드 (v0.6)** + Recommendations evidence 4종 cell + Holdings/HoldingChecks earnings evidence cell, msw + Playwright |
| **Report Intelligence (v0.4)** | 6 ORM + 6 Repository + CSV import + consensus snapshot job + report/theme score + dashboard 표시 |
| **News·Disclosure Intelligence (v0.5)** | `news_items` 통합 저장 (뉴스 + 공시) + `RealNewsScoreProducer` 가 `news_score` 25% 첫 real 화 + `DisclosureRiskProducer` 가 `RISK_DISCLOSURE` flag + cap +10 penalty + 추천·보유 evidence 노출 |
| **Fundamental·Earnings Intelligence (v0.6)** | 2 ORM + 2 Repository + 2 CSV import + RealFundamentalScoreProducer 가 `fundamental_score` 15% 첫 real 화 + RealEarningsScoreProducer 가 holding `earnings_score` 첫 real 화 + 3 read-only API + StockDetail 2 카드 + Today 1 카드 + Recommendations / Holdings evidence cell |
| Ops / CI | GitHub Actions 3 잡 (backend pytest / vitest+build / Playwright e2e), main + PR 자동 검증, mock 환경 변수 |
| 통합 검증 | `scripts/seed_mock_data.py` (멱등) + `INTEGRATION_RUNBOOK.md` (§10 News / §11 Disclosure / §12 테마 / **§13 Fundamental CSV / §14 Earnings CSV / §15 read-only API 운영 절차 포함**) |

세부 산출물 / 테스트 카운트 / 변경 이력은 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
와 [`TASKS.md`](./TASKS.md) 참고. v0.7 후보는 [`ROADMAP.md`](./ROADMAP.md) §7 참조.

## 7. 실행 순서 (권장)

새 세션 / 인수자 / QA 가 한 번에 따라가야 할 표준 순서. 각 단계는 모두 dry-run
/ mock-only — 실 KIS 호출, 실 텔레그램 발송, 자동매매 코드는 이 순서 안에서
절대 동작하지 않는다.

| 단계 | 명령 | 출력 / 검증 |
|---|---|---|
| 7.1 의존성 | `.\.venv\bin\python.exe -m pip install -e ".[dev]"` | 정상 설치 |
| 7.2 Docker (권장) 또는 로컬 uvicorn | §8 또는 §9 | `/health` 200 |
| 7.3 Mock seed | `.\.venv\bin\python.exe -m scripts.seed_mock_data --reset` | stocks 5 / daily_prices 150 등 (§10) |
| 7.4 통합 시나리오 (9잡 + 20+ API) | [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §3 ~ §5 / §10 ~ §15 따라감 | 모든 잡 SUCCESS (collect_news / collect_disclosures 는 default SKIPPED), API 200, notification_logs DRY_RUN |
| 7.5 회귀 게이트 | `.\.venv\bin\python.exe -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults` | 558 passed (v0.6 마감 시점) — 로컬 `.env` dev override 가 있으면 `test_settings_defaults` 1건은 deselect, CI clean env 에서는 자동 통과 |
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

현재 회귀 기준선 (v0.6 마감 시점):

- backend pytest **558 passed** (v0.1 296 → v0.3 319 → v0.4 final 382 → v0.5 final 481 → v0.6 Phase C 544 → Phase D 558). 로컬 `.env` 의 dev override (`MARKET_CAP_LIMIT=5` 등) 가 있으면 `tests/unit/test_project_structure.py::test_settings_defaults` 1건은 환경 의존으로 실패하므로 `--deselect` 또는 명시 env override 필요. CI clean env 에서는 자동 통과
- frontend vitest **77 passed** (13 파일)
- Playwright e2e **13 passed** (chromium + page.route mock)
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
먼저 읽고, 현재 사이클 (v0.6 마감 — v0.7 후보 검토 대기) 범위를 벗어나지
않는 개발 계획을 작성해줘.
아직 코드는 수정하지 말고 TASKS.md 업데이트 계획만 제안해줘.
```

## 15. 주의

이 프로젝트는 **투자 판단 보조 도구** 입니다. v0.1 ~ v0.6 어디에도 실제 주문 /
자동매매 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드를 구현하지 않습니다.

자동매매 진입은 별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실
제한 사이클이 선행되어야 검토할 수 있습니다 ([`ROADMAP.md`](./ROADMAP.md) 의
Future Backlog 참조).
