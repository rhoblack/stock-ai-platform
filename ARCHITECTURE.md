# Architecture

> 본 문서는 **v0.8 마감 시점** 기준으로 갱신된다 (`v0.8-frontend-watchlist` 태그
> 누적, `v0.8-final` 마감). v0.1 Backend → v0.2 Frontend → v0.3
> Analysis/Ops → v0.4 Analyst & Theme Intelligence → v0.5 News·공시·테마 랭킹 →
> v0.6 Fundamental & Earnings Intelligence → v0.7 Strategy & Backtest Foundation →
> v0.8 User & Migration Foundation 이 모두 누적된 상태의 시스템 구조를 반영한다.
> **v0.8 의 Auth / Watchlist layer 는 신규 `app/auth/` 패키지 + `app/api/auth_routes.py` +
> `app/api/watchlist_routes.py` 로 분리** (Watchlist write 라우터 첫 도입 — 5건 한정,
> cross-user 404 격리 + spoofing 가드 + broker/주문 필드 0건 격리). Alembic baseline
> 은 `alembic/versions/` 3 revision 으로 관리된다.

## 1. 핵심 흐름

이 프로젝트는 **read-only 분석·추천·보유점검 + 외부 신호 (휴장 캘린더 / 증권사
리포트 / 테마 매핑) 통합 + read-only 대시보드** 구조다. 자동매매 / 실 주문 /
POST 트리거 / FULL_AUTO / APPROVAL / SMALL_AUTO 는 **모든 사이클에서 코드
일체 포함하지 않는다** (`BrokerInterface` 는 ABC placeholder 만 유지).

```text
External Inputs                    Read-only Pipelines                Surfaces
─────────────────                  ───────────────────                ────────
KIS API (read)        ┐
                      ├─→ Data Collection ─→ Repository ─→ Analysis ─→ Scoring ─→ Recommendation / Holding Check ─→ Risk Gate ─→ Notification (DRY_RUN) + Dashboard API + PC Dashboard SPA
KRX 휴장일 (정적 JSON) ┘
                                              ↑
                              ┌───────────────┴────────────┐
Operator CSV (manual) ─→ Report Intelligence Layer ─→ Consensus Snapshot ─→ (Phase C+) Recommendation 보조 점수 ±5
```

향후 자동매매 흐름 (현재 어떤 사이클에도 미구현):

```text
Strategy Signal → AI Judgement → RiskEngine → BrokerInterface → TradeLogger
```

이 흐름은 v0.5+ 의 별도 보안 / 컴플라이언스 사이클이 선행되어야 진입 가능하다.
v0.1~v0.4 어디에도 활성화된 코드가 없다.

## 2. 레이어 구조 (v0.4 Phase A 기준)

```text
app/
├─ config/                  # Settings, .env 매핑, KIS / Telegram 마스킹
├─ db/                      # SQLAlchemy 2.0 Base / 23 ORM 모델 (v0.1 17 + v0.3 +0/3컬럼 + v0.4 +6)
├─ data/
│  ├─ collectors/           # KIS read-only HTTP / DailyPriceCollector / MarketCapCollector / Fake provider
│  ├─ importers/            # v0.4 — operator CSV / Excel import (analyst reports, themes, mappings, signal events)
│  ├─ normalizers/          # KIS raw → DTO
│  ├─ validators/           # DataQualityChecker
│  └─ repositories/         # 22 Repository (v0.1 16 + v0.4 +6)
├─ analysis/                # TechnicalAnalyzer, IndicatorService, candle/ATR/volatility (v0.3 Phase B)
├─ decision/                # ScoringEngine, RecommendationEngine, HoldingCheckEngine, RiskEngine, score producers
├─ notification/            # ReportGenerator, TelegramNotifier (DRY_RUN), Dispatchers
├─ api/                     # FastAPI read-only routers (15+ GET endpoints, 0 POST)
├─ scheduler/               # APScheduler + run_job wrapper + 6 jobs (v0.4 Phase B 진입 시 7번째 추가 예정)
└─ broker/                  # placeholder only (ABC) — 자동매매 진입 전까지 비어 있음

frontend/                   # v0.2 Vite/React/TS PC 대시보드 + v0.3 휴장 배너·일봉 차트
├─ src/
│  ├─ pages/                # 8 화면 (Today / Recommendations / History / Holdings / StockDetail / MarketCap / Jobs / Settings)
│  ├─ components/common/    # MarketStatusBanner, TrendLineChart, RiskBadge, GradePill, …
│  ├─ data/                 # KRX 휴장일 정적 JSON (2025–2027)
│  ├─ lib/                  # marketCalendar 등 read-only 유틸
│  ├─ hooks/                # useStockDetail, useStockPriceSeries, …
│  ├─ api/                  # apiFetch + 타입 (hand-written)
│  └─ tests/                # vitest + msw
├─ e2e/                     # Playwright + page.route mock

scripts/                    # 운영자 CLI
├─ seed_mock_data.py        # v0.1 — mock seed 적재
└─ (v0.4 Phase B) import_analyst_reports.py — CSV/Excel 수동 import (예정)

.github/workflows/          # v0.3 Phase A — CI 3 job (backend pytest / frontend vitest+build / e2e)
```

## 3. 계층별 책임

### 3.1 Data Layer

외부 read-only 입력의 정규화 + 저장. KIS API, KRX 휴장일 정적 JSON, 운영자 CSV
import 가 모두 여기를 통과한다. **추천 판단을 하지 않는다.**

- `data/collectors/` — KIS HTTP 클라이언트 + 일봉 / 시총 collector + Fake provider
- `data/importers/` (v0.4) — 운영자 CSV → analyst_reports / report_themes /
  theme_stock_mappings / report_signal_events. **자동 크롤링 / 스크레이핑 0건**.
  PDF 본문 / paragraph 저장 금지. `source_file_path` 는 DB 에 저장되지만 API 응답
  / 프런트 어디에도 노출되지 않는다.
- `data/normalizers/`, `data/validators/` — KIS raw → DTO 변환 + 품질 검사

### 3.2 Repository Layer

ORM 모델 + 단순 CRUD / upsert. 로직 0. 22 Repository 가 단일 export 면 (`app.data.repositories`)
에서 노출된다.

### 3.3 Analysis Layer

저장된 데이터를 지표 / 패턴 / 변동성 분류로 변환.

- v0.1 — MA5/20/60/120, RSI14, MACD, 거래량 비율, breakout, ma_alignment, technical_score
- v0.3 Phase B — 캔들 패턴 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING /
  BEARISH_ENGULFING), Wilder ATR(14), 4단계 변동성 분류 (LOW / NORMAL / HIGH /
  EXTREME). `technical_score` 에 ±5점 cap 보조 가산.
- v0.4 Phase C (예정) — `report_score_calculator` (기업 리포트 + 테마·시그널
  기반 보조 점수)

**외부 API 호출 / 주문 0건.**

### 3.4 Report Intelligence Layer (v0.4)

증권사 애널리스트 리포트 메타데이터 + 추출된 투자 테마 + 테마→종목 매핑 +
변화 시그널 이벤트를 통합. 6 ORM + 6 Repository 가 핵심.

```text
analyst_reports (1) ──┬── (N) report_themes ──┬── (N) theme_stock_mappings
                      │                       │
                      └── (N) report_signal_events ──── (theme_id nullable FK)

report_consensus_snapshots          (per-symbol per-window 일별 집계)
report_score_logs                   (report_score + theme_signal_score 계산 이력)
```

- 7 report_type (COMPANY / SECTOR / INDUSTRY / THEME / COMMODITY / MACRO / STRATEGY)
  을 단일 테이블로 통합 — `symbol` nullable 로 매크로·테마·원자재 리포트 지원.
- 글로벌 종목 (US / NASDAQ / USD) 동일 테이블 저장 (market / exchange / country
  / currency / broker_country 컬럼).
- `extraction_method` (MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED) 로 데이터
  출처를 태깅 — 미래에 LLM 자동 요약을 붙일 수 있도록 설계되었으나 v0.4 Phase
  A 에서는 미구현.
- **저작권 정책**: 원문 본문 / paragraph 저장 0건, PDF BLOB 0건, 자동 크롤링 0건,
  외부 공유 / 공개 API 0건.

### 3.5 Scoring / Decision Layer

- `ScoringEngine` — 신규 추천 (technical 35% + news 25% + supply 15% + fundamental
  15% + ai 10% - risk_penalty) / 보유 (technical 35% + news 20% + earnings 20% +
  ai 15% + profit_management 10% - risk_penalty)
- `RecommendationEngine`, `HoldingCheckEngine` — 후보 생성 + risk gate +
  snapshot/log 저장. 외부 API 호출 0건.
- `RiskEngine` — risk_penalty / risk_level / risk_flags. **모든 미래 자동매매의
  최종 게이트** (현재는 추천·보유 점검의 risk 라벨만 채움).
- v0.4 Phase C (예정): `report_score` + `theme_signal_score` 를 각 ±5점 cap 보조
  가산 (총 ±10점). **본 weight 산식은 손대지 않는다.**

### 3.6 Notification Layer

리포트 텍스트 생성 + 텔레그램 발송 + 알림 로그.

- 기본 `DRY_RUN` (`TELEGRAM_ENABLED=false`).
- 3 dispatcher (`RecommendationReportDispatcher`, `HoldingCheckReportDispatcher`,
  `HoldingRiskAlertDispatcher`) 가 잡과 연결되어 `notification_logs.related_job_id`
  를 자동 채운다.
- **추천 로직 / 점수 산식을 변경하지 않는다.**

### 3.7 API Layer (Backend, v0.1 ~ v0.3)

PC 대시보드용 read-only GET 라우터만 제공. **POST / PUT / DELETE 0건** —
v0.1~v0.4 일관 정책.

- v0.1: 13개 read-only GET (`/api/reports/today`, `/api/recommendations`, `/api/holdings/checks/latest`, `/api/stocks/{symbol}`, `/api/jobs`, `/api/settings`, …)
- v0.3 Phase D: `GET /api/stocks/{symbol}/prices?days=120` 추가 (일봉 차트 시계열)
- v0.4 Phase D (예정): `GET /api/stocks/{symbol}/reports` 신규 — 리포트 / 컨센서스 /
  최근 시그널 (read-only). `source_file_path` 는 schema 에서 마스킹.

라우터는 collector / 지표 계산 / 추천 생성을 직접 하지 않는다 — Repository 와
Pydantic schema 만 사용한다.

### 3.8 Frontend Layer (v0.2 ~ v0.3)

Vite + React + TypeScript 5.5 + Tailwind + TanStack Query/Table + Recharts. 8 화면
모두 backend read-only API 만 소비. **POST / form / submit 0건** — e2e 가
명시적으로 검증.

- v0.2 — 8 화면 MVP + 코드 스플릿 + Docker
- v0.3 Phase C — KRX 휴장일 정적 JSON + `MarketStatusBanner` (Today / Jobs /
  Holdings 헤더)
- v0.3 Phase D — StockDetail 일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자
- v0.4 Phase D (예정) — StockDetail 리포트·테마·시그널 카드 + Recommendations 의
  `report_score` / `theme_signal_score` 컬럼

### 3.9 Scheduler Layer

APScheduler + `run_job` wrapper. 6 개 잡이 매일 자동 실행되며 모두 `job_runs`
테이블에 audit 기록을 남긴다.

| 잡 | 시간 (KST) | 역할 |
|---|---|---|
| `collect_market_close_data` | 18:00 | 시총 + 일봉 수집 |
| `calculate_technical_indicators` | 18:30 | 지표 일괄 계산 (캔들 / ATR 포함, v0.3 Phase B+) |
| `send_recommendation_report` | 06:00 | 텔레그램 추천 발송 (DRY_RUN 기본) |
| `run_pre_market_holding_check` | 08:30 | 장전 보유 점검 |
| `run_post_market_holding_check` | 16:30 | 장후 보유 점검 |
| `update_recommendation_results` | 17:00 | 1/3/5/20일 후 성과 갱신 |
| `update_report_consensus_snapshots` (예정, v0.4 Phase B) | 06:30 | 리포트 컨센서스 일별 집계 |

부분 실패가 전체 시스템을 멈추지 않는다 (PARTIAL / NO_DATA 분기).

### 3.10 Ops / CI Layer (v0.3 Phase A)

`.github/workflows/ci.yml` — main / PR 양쪽에서 자동 실행되는 3 잡:

- `backend / pytest` — Python 3.12 + `pip install -e ".[dev]"` + `pytest -q`
- `frontend / vitest + build` — Node 20 + `npm ci` + `npm run test` + `npm run build`
- `frontend / playwright e2e` — `playwright install chromium` + `npm run e2e`,
  실패 시 `playwright-report/` artifact 업로드

CI 환경 변수는 모두 mock / dry-run (KIS_USE_PAPER=true, TELEGRAM_ENABLED=false,
FEATURE_REAL_ORDER_EXECUTION=false 등). 실 자격증명 / 실 KIS / 실 Telegram 호출
0건.

`Docker` (v0.2): backend (`uvicorn`) + nginx (frontend SPA + `/api` proxy) +
postgres compose. `web` 컨테이너가 `/api` / `/health` 를 `backend:8000` 으로
proxy.

## 4. Import Pipeline (v0.4)

운영자가 직접 작성한 메타데이터 CSV 를 시스템에 적재하는 read-only 파이프라인.
v0.4 Phase B 에서 `scripts/import_analyst_reports.py` (argparse CLI, default
dry-run, `--commit` 시 DB 적재) + 입력 검증 + 멱등 upsert 로 구체화될 예정.

```text
operator CSV / Excel
   │  (manual run only — no auto-crawler)
   ▼
data/importers/  (Phase B 신규)
   │  validation: enum / date / number / 본문 column 거부
   │  truncation: summary > 500자 → truncate + count
   │  idempotency: get_by_unique → skip / create
   ▼
analyst_reports + report_themes + theme_stock_mappings + report_signal_events
   │
   ▼
update_report_consensus_snapshots (Phase B 신규 잡, 06:30 KST)
   │
   ▼
report_consensus_snapshots
```

`source_file_path` 는 운영자 로컬 PDF 경로 — DB 저장 후 어떤 출력에도 노출되지
않는다 (CLI summary / API 응답 / 프런트 / e2e 모두 마스킹). 자동 크롤링 /
스크레이핑은 v0.5+ 별도 저작권 검토 후 검토 가능.

## 5. 핵심 인터페이스

### DataProviderInterface

외부 데이터 공급자 교체용 ABC. v0.1 의 `KisDataProvider` (실 KIS) /
`FakeKisDataProvider` (테스트) 가 동일 인터페이스 구현. v0.5+ 에 News / 공시 /
재무 공급자가 같은 패턴으로 추가될 수 있다.

### AIProviderInterface / DummyScoreProducer

Dummy / Local LLM / Cloud LLM / Custom Model 을 교체 가능하게 만든다. v0.1 ~
v0.4 는 `DummyScoreProducer` (neutral 50 + rule 기반 ±5 보정) 만 사용. v0.5+ 에
실 News / Supply / Fundamental / Earnings 파이프라인이 도입되면 producer 가
교체된다.

### BrokerInterface

미래 확장용 ABC. **v0.1 ~ v0.4 어디에도 구현체가 없다.**

- KisBroker (실거래) — v1.0+
- MockBroker / ReplayBroker / SimulationBroker — v0.5+ 가상매매 사이클

### StrategyInterface

미래 전략 / 백테스트 확장용 placeholder. 현재 코드 미존재.

## 6. v0.1 ~ v0.4 일관 안전 규칙

- 모든 사이클에서 **자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드
  0건**.
- 모든 사이클에서 **POST / PUT / DELETE 라우터 0건** (read-only API 만).
- AI / Scoring / Notification 모듈은 직접 주문하지 않는다.
- Recommendation / Holding 은 외부 API 를 직접 호출하지 않는다.
- API 라우터는 collector / 지표 계산 / 추천 생성을 직접 하지 않는다.
- 모든 판단은 `data_snapshots` + `decision_logs` + `job_runs` + `notification_logs`
  로 추적 가능하다.
- v0.4 의 리포트 본문 / PDF BLOB 저장 0건 — 운영자 작성 짧은 요약만.
- 모든 비밀값 (KIS 키 / 텔레그램 토큰 / 계좌번호) 은 마스킹 (`5015****1-01`)
  되며 API 응답 / 프런트 / e2e 어디에도 평문 노출 0건.
- 모든 외부 호출 (KIS / Telegram) 은 테스트에서 mock 으로 대체 — `pytest -q`
  실행 시 외부 네트워크 0건.
