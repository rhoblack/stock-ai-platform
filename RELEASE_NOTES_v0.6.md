# RELEASE_NOTES_v0.6

## v0.6 Fundamental & Earnings Intelligence 마감

v0.6 은 v0.1 부터 placeholder 50 으로 비어 있던 `DummyScoreProducer.fundamental_score`
(가중치 15%) 와 `HoldingCheckEngine` 의 `earnings_score` 를 **처음으로 real 값으로
교체**하고, 운영자 수동 CSV import 기반의 `fundamental_snapshots` (24번째 테이블) +
`earnings_events` (25번째 테이블) 데이터 라인을 도입하며, StockDetail 화면에 재무
스냅샷 / 실적 이벤트 두 카드와 Today 화면에 다가오는 실적 캘린더 카드를 추가한
사이클이다. v0.1 ~ v0.5 의 read-only 원칙, 비밀값 마스킹, mock·DRY_RUN 정책,
v0.4 의 저작권 정책 (본문 paragraph 미저장 / 자동 fetch default OFF /
`source_file_path` 미노출) 은 모두 그대로 유지했다.

자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST 라우터 / DART 자동
호출은 이번 사이클에도 코드 일체 추가하지 않았다.

- 최종 태그 예정: `v0.6-final`
- 인수 일자: 2026-05-06 (Asia/Seoul)
- 직전 누적 태그: `v0.6-frontend-fundamentals` (Phase D)
- 기준선: `v0.5-final` (HEAD `9ccf0f8`) — 백엔드 pytest 481 / vitest 68 / build / e2e 11
- 마감 기준선: 백엔드 pytest **558** / vitest **77** / build / e2e **13**

## 핵심 변화 한 줄 요약

- **재무 데이터 라인 첫 도입** — `FundamentalProviderInterface` + `FundamentalSnapshotRepository` + `fundamental_snapshots` 테이블 (24번째, 8 정량 지표) + `scripts/import_fundamentals.py` argparse CLI (default dry-run)
- **실적 이벤트 데이터 라인 첫 도입** — `EarningsProviderInterface` + `EarningsEventRepository` + `earnings_events` 테이블 (25번째) + BEAT/MEET/MISS 분류 룰 + `scripts/import_earnings.py`
- **`fundamental_score` 첫 real 화** — `RealFundamentalScoreProducer` (composition 패턴, fallback 으로 news/supply/earnings/ai 위임). 산식 `clip(50 + ROE/PER/PBR/growth/debt/dividend rule adjustment, 0, 100)`. snapshot 없음 → 50
- **`earnings_score` 첫 real 화 (HoldingCheckEngine)** — `RealEarningsScoreProducer` (composition 패턴). 산식 `clip(50 + (base_delta + surprise_delta) * recency_multiplier, 0, 100)`. BEAT +10 / MISS -10 / MEET·UNKNOWN 0, surprise_pct cap ±10, recency 1.0 (≤30d) / 0.6 (≤90d) / 0.3 (>90d) / 0.5 (future)
- **백엔드 read-only API 3종** — `GET /api/stocks/{symbol}/fundamentals` + `GET /api/stocks/{symbol}/earnings` + `GET /api/calendar/earnings` (모두 read-only, source_file_path 0건 노출)
- **추천 / 보유 evidence 노출 강화** — `RecommendationItemSchema.fundamental_evidence` + `earnings_evidence` (현재는 항상 null, 미래 호환), `HoldingCheckSchema.earnings_evidence` + `news_evidence` + `disclosure_risk_evidence` (v0.5 Phase D 에서 이연된 holding evidence 노출 작업 흡수). 모두 라우터 단계 화이트리스트 통과
- **StockDetail 두 카드 + Today 한 카드 + Recommendations 두 cell + Holdings cell 추가** — `FundamentalsCard` (PER/PBR/ROE/부채/배당/성장률 + history 시계열) + `EarningsCard` (BEAT/MEET/MISS tone-color badge + actual vs consensus + history) + `UpcomingEarningsCard` (`useEarningsCalendar` limit=5) + `RecommendationsTable` 의 `fund evidence` / `earnings evidence` 두 cell + `RecentHoldingChecksCard` 의 earnings evidence 컬럼

## Phase A — Fundamental data layer + CSV import

> 두 PR 로 분리. PR1 = `FundamentalSnapshot` ORM + Repository 만, PR2 = CSV
> import pipeline. Phase A 인수 시점에 별도 태그를 부여하지 못해 **`v0.6-fundamental-data-layer`
> 태그는 부재**. Phase A 는 커밋 (`0d3dba5` Add fundamental snapshot data model
> and repository, `da3567f` Add fundamental snapshot import pipeline) 으로
> 추적한다.

### PR1 — Data model + Repository

- `app/db/models.py` — `FundamentalSnapshot` 신규 (24번째 테이블). 컬럼: `symbol` / `snapshot_date` / `fiscal_year` / `fiscal_quarter` (nullable, 연간 데이터 호환) / 8 정량 지표 (revenue / operating_income / net_income / total_assets / total_liabilities / total_equity / eps / bps / per / pbr / roe / debt_ratio / dividend_yield / revenue_growth_yoy / operating_income_growth_yoy) + `source` (String 64). UniqueConstraint `(symbol, snapshot_date, fiscal_year, fiscal_quarter)`. 본문 / 원문 / paragraph / source_file_path / PDF BLOB 컬럼 0건
- `app/data/repositories/fundamental_snapshots.py` — `FundamentalSnapshotRepository` 신규: `create` / `get_by_symbol_period` / `upsert_by_symbol_period` (멱등) / `get_latest_by_symbol` / `list_recent_by_symbol` / `list_by_fiscal_year`
- `app/data/repositories/__init__.py` — `FundamentalSnapshotRepository` export
- 테스트: `tests/integration/test_fundamental_repository.py` 신규 (ORM metadata / CRUD / upsert 멱등 / latest / recent 정렬 / fiscal_year 조회 / nullable quarter / Decimal round-trip / 본문 컬럼 0 가드)

### PR2 — CSV import pipeline

- `app/data/dtos.py` — `FundamentalSnapshotDTO` 신규. 정규화 수치 지표 + `source` 만 포함. body / content / full_text / paragraph_text / raw_text / source_file_path / 본문 / 원문 / 전문 등 13종 forbidden 필드 0건 (단위 테스트가 명시 단언)
- `app/data/interfaces.py` — `FundamentalProviderInterface` ABC 신규 (`fetch_fundamentals(symbols, fiscal_year, fiscal_quarter=None)`). 실 DART 구현체는 추가하지 않았음
- `tests/mocks/fake_fundamental_provider.py` — `FakeFundamentalProvider` 결정론적 3-row 샘플. 외부 API 호출 0건
- `app/data/importers/fundamentals.py` — CSV header validation + row validation + `FundamentalSnapshotRepository.upsert_by_symbol_period` 기반 import. 재import 시 값이 같으면 `unchanged`, 다르면 `updated` 로 집계
- `scripts/import_fundamentals.py` — argparse CLI. `--file` 필수, `--encoding` 기본 `utf-8-sig`, `--db-url` override, `--commit` 없는 기본 dry-run
- 테스트: `tests/integration/test_fundamental_import.py` (DTO forbidden guard / FakeProvider / dry-run / commit / reimport idempotency / forbidden column / required columns / date-year-quarter validation / Decimal / negative policy / CLI run_import)

## Phase B — Earnings event layer + CSV import

> 태그 `v0.6-earnings-event-pipeline`. Phase A 의 패턴을 그대로 복제 + BEAT/MEET/MISS
> 분류 룰 + 어닝 캘린더 import.

- `app/db/models.py` — `EarningsEvent` 신규 (25번째 테이블). 컬럼: `symbol` / `company_name` / `event_date` / `fiscal_year` / `fiscal_quarter` / `event_type` (REPORT / ANNOUNCEMENT) / 4 항목의 actual+consensus pair (revenue / operating_income / net_income / eps) / `surprise_type` (BEAT/MEET/MISS/UNKNOWN) / `surprise_pct` / `source` / `memo` (≤500자). UniqueConstraint `(symbol, event_date, fiscal_year, fiscal_quarter, event_type)`. 본문 / paragraph / source_file_path / PDF 컬럼 0건
- `app/data/repositories/earnings_events.py` — `EarningsEventRepository` 신규: `create` / `get_by_symbol_event` / `upsert_by_symbol_event` / `get_latest_by_symbol` / `list_recent_by_symbol` / `list_upcoming(since, until)` / `list_by_surprise_type`
- `app/data/dtos.py` / `app/data/interfaces.py` — `EarningsEventDTO` + `EarningsProviderInterface.fetch_earnings_events(...)` 추가. 실 구현체는 없음
- `tests/mocks/fake_earnings_provider.py` — BEAT / MEET / MISS / upcoming UNKNOWN 결정론 샘플. 외부 API 호출 0건
- `app/data/importers/earnings.py` / `scripts/import_earnings.py` — 기본 dry-run, `--commit` 저장, `--file`, `--encoding`, `--db-url` 지원
- surprise 계산 룰: CSV `surprise_type` 우선. 없으면 `operating_income_actual / operating_income_consensus` 로 `(actual - consensus) / abs(consensus) * 100` 계산. `>=5` BEAT, `<=-5` MISS, 그 사이 MEET, consensus 0/NULL → UNKNOWN
- 테스트: `tests/fixtures/earnings_events_sample.csv`, `tests/integration/test_earnings_repository.py`, `tests/integration/test_earnings_import.py` 신규
- 회귀: backend pytest **481 → ~530 (+~50)** (Phase A + B 누적). KIS / DART / Telegram / scheduler / API 라우터 / frontend 0건 변경

## Phase C — RealFundamentalScoreProducer + RealEarningsScoreProducer

> 태그 `v0.6-fundamental-score`. v0.1 의 `DummyScoreProducer.fundamental_score = 50`
> placeholder 와 HoldingCheckEngine 의 `earnings_score = 50` placeholder 가
> **처음으로 real 값으로 교체**. **추천·보유 본 weight 산식은 0건 변경**.

- `app/analysis/score_producers.py` — `RealFundamentalScoreProducer` 신규. 기존 `ScoreProducerInterface` composition 패턴 유지. fallback (default `DummyScoreProducer`) 가 news / supply / earnings / ai 처리, `fundamental_score` 만 `FundamentalSnapshotRepository.get_latest_by_symbol` 기반 real 화. 산식:
  ```
  score = 50
  score += clip(roe, -10, 25) * 0.6
  score += per_bucket          # ≤8:+8 / ≤15:+4 / ≤25:0 / ≤40:-6 / >40:-12
  score += pbr_bucket          # ≤1.0:+4 / ≥2.5:-4 / ≥4.0:-8
  score += clip(revenue_growth_yoy, -20, 30) * 0.25
  score += clip(operating_income_growth_yoy, -30, 50) * 0.25
  score += debt_ratio_bucket   # ≤50:+3 / ≥100:-8 / ≥200:-15
  score += min(dividend_yield, 5) * 0.8
  fundamental_score = clip(score, 0, 100)
  # snapshot None → 50 (Dummy fallback 호환)
  ```
- `app/analysis/score_producers.py` — `RealEarningsScoreProducer` 신규. holding 의 `earnings_score` 만 `EarningsEventRepository.get_latest_by_symbol` 기반 real 화. 산식:
  ```
  base_delta = +10(BEAT) / 0(MEET·UNKNOWN) / -10(MISS)
  surprise_delta = clip(surprise_pct * 0.5, -10, +10)
  recency_multiplier = 0.5(future) / 1.0(≤30d) / 0.6(≤90d) / 0.3(>90d)
  earnings_score = clip(50 + (base_delta + surprise_delta) * multiplier, 0, 100)
  # event None → 50
  ```
- `app/decision/recommendation_engine.py` — `_persist_candidate` 가 `data_snapshots.market_context_json["fundamental_evidence"]` + `decision_logs.rule_result_json["fundamental_evidence"]` 양쪽에 evidence 기록. 본 weight 산식 변경 0건
- `app/decision/holding_check_engine.py` — 동일 방식으로 `earnings_evidence` 기록
- `fundamental_evidence` safe-fields whitelist: `snapshot_date / fiscal_year / fiscal_quarter / per / pbr / roe / debt_ratio / revenue_growth_yoy / operating_income_growth_yoy / dividend_yield`. snapshot 없으면 `{"reason": "no_fundamental_snapshot"}`
- `earnings_evidence` safe-fields whitelist: `latest_event_date / fiscal_year / fiscal_quarter / event_type / surprise_type / surprise_pct / operating_income_actual / operating_income_consensus`. event 없으면 `{"reason": "no_earnings_event"}`
- 테스트: `tests/unit/test_real_fundamental_earnings_score_producers.py` 신규 (8 케이스: 데이터 없음 50 / 좋은 재무 50 초과 / 나쁜 재무 50 미만 / debt_ratio 감점 / growth 가산 / 0~100 clamp / BEAT/MISS/MEET/UNKNOWN / surprise_pct cap / old event 영향 감소 / upcoming UNKNOWN 중립 / evidence whitelist 단언) + `test_recommendation_engine.py` / `test_holding_check_engine.py` 보강 (real fundamental_score / earnings_score 반영 + decision_log + data_snapshot evidence 저장 + ScoringEngine 본 weight 변경 0건 회귀)
- 회귀: backend pytest **544 passed**. ScoringEngine 본 weight (recommendation: technical 35% / news 25% / supply 15% / **fundamental 15%** / ai 10%, holding: technical 35% / news 20% / **earnings 20%** / ai 15% / profit 10%) 산식 0건 변경

## Phase D — read-only API + StockDetail / Today 카드 + evidence cell

> 태그 `v0.6-frontend-fundamentals`. Phase A/B/C 의 데이터·점수 layer 위에
> read-only API 3종 + 프런트 카드 / cell 만 추가. POST / scheduler job /
> 자동매매 / DART 자동 호출 / Telegram 발송 0건.

### 백엔드

- `app/api/routes.py` — 3 신규 GET 라우터:
  - `GET /api/stocks/{symbol}/fundamentals?limit=` (기본 8, max 40). FundamentalSnapshot 시계열. Stock 없으면 404
  - `GET /api/stocks/{symbol}/earnings?limit=` (기본 8, max 40). EarningsEvent 이력 + memo 500자 cap. Stock 없으면 404
  - `GET /api/calendar/earnings?from_date=&to_date=&surprise_type=&limit=` (기본 20, max 100). `from_date` 미지정 시 오늘 이후 default
- `app/api/schemas.py` — 6 신규 schema (`FundamentalSnapshotSchema` / `StockFundamentalsResponse` / `EarningsEventSchema` / `StockEarningsResponse` / `EarningsCalendarItemSchema` / `EarningsCalendarResponse`). 모든 numeric 은 Decimal-as-string (`_BaseSchema._decimal_to_str` validator)
- `app/api/schemas.py` — `RecommendationItemSchema` 에 `fundamental_evidence` + `earnings_evidence` 추가, `HoldingCheckSchema` 에 `news_evidence` + `disclosure_risk_evidence` + `earnings_evidence` 3 추가 (v0.5 Phase D 에서 이연된 holding evidence 노출 작업 흡수)
- `app/api/routes.py` — `_whitelist_evidence(snapshot, key, allowed)` helper + `_FUNDAMENTAL_EVIDENCE_FIELDS` / `_EARNINGS_EVIDENCE_FIELDS` set 신규. **Phase C 의 score producer 단계 + Phase D 의 라우터 단계로 defense-in-depth 2 단 화이트리스트** — 향후 producer 변경에도 forbidden 키 누설 0건. 빈 dict 로 화이트리스트 후 떨어지면 None 으로 강등 (프런트 placeholder 일관)
- 테스트: `tests/integration/test_api_routes.py` 14 신규 케이스 (fundamentals happy / empty / 404 / limit clamp, earnings happy / empty / 404, calendar happy + from/to + surprise_type 필터, calendar default = 오늘 이후, calendar limit clamp, recommendation `fundamental_evidence` whitelist + pre-v0.6 → null, holding `earnings_evidence` whitelist + pre-v0.6 → null)

### 프런트

- `frontend/src/api/types.ts` — 6 response 타입 + `FundamentalEvidence` / `EarningsEvidence` 신규. `RecommendationItem` / `HoldingCheck` 에 evidence optional 필드 추가
- `frontend/src/hooks/useStockFundamentals.ts` / `useStockEarnings.ts` / `useEarningsCalendar.ts` 신규 (TanStack Query, staleTime 60초 — StockDetail 계열과 동일)
- `frontend/src/pages/StockDetail/FundamentalsCard.tsx` 신규 — 최근 fiscal period KeyValueGrid (PER / PBR / ROE / 부채비율 / 배당수익률 / 매출 성장률 / 영업이익 성장률 / EPS / BPS) + history 시계열 테이블 (count > 1 시)
- `frontend/src/pages/StockDetail/EarningsCard.tsx` 신규 — 최근 이벤트 + BEAT/MEET/MISS/UNKNOWN tone-color SurpriseBadge + surprise_pct + actual vs consensus 3-tile + history
- `frontend/src/pages/StockDetail/index.tsx` — Fundamentals + Earnings 카드 `lg:grid-cols-2` 한 행 추가. `RecentHoldingChecksCard` 에 `earnings evidence` 컬럼 추가
- `frontend/src/pages/TodayReport/index.tsx` — `UpcomingEarningsCard` 인라인 (가까운 5건, symbol/company/event_date/fiscal/event_type 또는 surprise_type)
- `frontend/src/pages/Recommendations/RecommendationsTable.tsx` — `fund evidence` + `earnings evidence` 두 compact summary cell 추가 (null/reason sentinel → "—")
- `frontend/src/tests/mswServer.ts` — 3 default 핸들러 추가, `/api/stocks/:symbol` catch-all 404 보다 앞에 배치
- `frontend/e2e/fixtures/apiMocks.ts` — `STOCK_FUNDAMENTALS_005930` / `STOCK_EARNINGS_005930` / `EARNINGS_CALENDAR` fixture + 라우터 패턴 추가

### 테스트

- backend pytest **544 → 558 (+14)**
- frontend vitest **68 → 77 (+9)** — StockDetail Fundamentals/Earnings 카드 happy/empty/error 6건 + recent holding check earnings_evidence cell 1건 + Recommendations evidence cell 보강 + TodayReport UpcomingEarnings 2건
- Playwright e2e **11 → 13 (+2)** — Recommendations evidence cell 보강 + StockDetail Fundamentals + Earnings 카드 + Today UpcomingEarnings
- frontend build 그린

## Phase E — 마감 문서 / 회귀 게이트 재확인

이 단계. `RELEASE_NOTES_v0.6.md` 신규 + `README.md` 마감 배너 +
`PROJECT_STATUS.md` §0 마감 선언 + `TASKS.md` 체크박스 + `ROADMAP.md` v0.6 마감 +
4 게이트 재확인. **코드 / 라우터 / DB 모델 / 프런트 화면 변경 0건**.

## 테스트 결과 (v0.6 마감 시점)

Phase D 인수 시점 + Phase E 마감 직전 재확인 모두 동일한 4 게이트 baseline:

- backend pytest: **558 passed** (v0.1 296 → v0.3 319 → v0.4 final 382 → v0.5 final 481 → v0.6 Phase C 544 → Phase D 558)
- frontend vitest: **77 passed** (13 파일, jsdom + msw v2)
- frontend build: **그린** (`tsc --noEmit && vite build`, vendor-charts 청크 383 kB / gzip 105 kB)
- Playwright e2e: **13 passed** (chromium + page.route mock)

테스트는 모두 mock / fixture 기반이다. KIS API 실제 호출, 텔레그램 실제 발송,
외부 RSS / DART API 실제 호출, 주문 실행은 0건이다.

운영자 로컬 `.env` 의 dev override (`MARKET_CAP_LIMIT=5`, `DAILY_PRICE_LOOKBACK_DAYS=7`
등) 와 충돌하는 단일 케이스 `tests/unit/test_project_structure.py::test_settings_defaults`
는 v0.3 부터 알려진 환경 의존성이며, `--deselect tests/unit/test_project_structure.py::test_settings_defaults`
또는 명시적 env override (`MARKET_CAP_LIMIT=500 ...`) 로 우회한다. 실제 default
검증은 GitHub Actions CI 환경 (clean env) 에서 자동 통과한다.

## 안전 정책 (cycle-wide)

v0.4 의 저작권 정책 + v0.1 ~ v0.5 의 자동매매 부재 정책을 그대로 누적:

- **재무 / 실적 본문 paragraph 저장 금지** — `FundamentalSnapshot` / `FundamentalSnapshotDTO` / `EarningsEvent` / `EarningsEventDTO` 어디에도 body / content / full_text / paragraph_text / raw_text / 본문 / 원문 / 전문 컬럼 없음. 정량 지표 + 짧은 메모 (`memo` ≤500자) + URL / source 메타데이터만 저장. 단위 테스트가 13종 forbidden 필드 부재 명시 단언 + CSV importer 가 forbidden header 검출 시 즉시 거부
- **재무제표 PDF / Excel BLOB 저장 금지** — DB 컬럼 0건. CSV 정량 지표만 적재
- **`source_file_path` 미노출** — 신규 `/api/stocks/{symbol}/fundamentals` / `/api/stocks/{symbol}/earnings` / `/api/calendar/earnings` 응답 + Recommendation `fundamental_evidence` + HoldingCheck `earnings_evidence` 모두 `_assert_no_source_file_path` recursive helper 로 0건 노출 검증. v0.4 / v0.5 의 정책 그대로 유지
- **DART API 자동 호출 금지** — `FundamentalProviderInterface` / `EarningsProviderInterface` ABC + `FakeFundamentalProvider` / `FakeEarningsProvider` 결정론적 sample 만 제공. 실 DART subset 구현체는 v0.7+ 후보 (라이선스 / 스로틀링 검토 동반)
- **자동 fetch default OFF** — `Settings.fundamental_collection_enabled` / `earnings_collection_enabled` 기본 false (v0.5 의 `news_collection_enabled` / `disclosure_collection_enabled` 패턴 재사용). 실제 v0.6 에서는 scheduler job 자체를 추가하지 않았으므로 운영 default 동작 영향 0건
- **외부 네트워크 테스트 금지** — `FakeFundamentalProvider` / `FakeEarningsProvider` 결정론적 sample 만 사용. 실 DART 호출 0건. CI 환경에서도 외부 트래픽 0건
- **자동매매 / 실주문 / POST 트리거 0건** — v0.6 에서도 POST / PUT / DELETE 라우터 추가 0건. `BrokerInterface` ABC placeholder 그대로. 자동매매 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드 0건
- **Evidence whitelist (defense-in-depth 2단)** — Phase C score producer 단계 + Phase D 라우터 단계 두 번 검증. `fundamental_evidence` 키 집합은 `{snapshot_date, fiscal_year, fiscal_quarter, per, pbr, roe, debt_ratio, revenue_growth_yoy, operating_income_growth_yoy, dividend_yield, reason}` 의 부분집합 / `earnings_evidence` 는 `{latest_event_date, fiscal_year, fiscal_quarter, event_type, surprise_type, surprise_pct, operating_income_actual, operating_income_consensus, reason}` 의 부분집합. 본문 / 내부 경로 / memo / source_file_path 절대 미포함
- **추천 산식 본 weight 변경 0건** — ScoringEngine (technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%) 그대로. `fundamental_score` 가 placeholder 50 → real 로 교체될 뿐 가중치 15% 유지
- **HoldingCheckEngine 산식 변경 0건** — 보유 점검 본 weight 그대로. `earnings_score` 가 placeholder 50 → real 로 교체될 뿐
- **KIS API / Telegram 실제 호출 0건** — v0.1~v0.5 정책 그대로
- **비밀값 마스킹 유지** — KIS 키 / Telegram 토큰 / 계좌번호 마스킹 정책, settings 응답 마스킹 검증 e2e 그대로 통과

## 알려진 한계

- **실 DART provider 미구현** — `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 와 `FakeFundamentalProvider` / `FakeEarningsProvider` 결정론적 샘플만 제공. 실 DART subset 구현체는 v0.7+ 후보 (라이선스 / 스로틀링 / 정책 검토 동반)
- **CSV 기반 수동 import 만** — 운영자가 `scripts/import_fundamentals.py` / `scripts/import_earnings.py` 를 수동 실행. scheduler job 미추가. 자동 수집 자동화는 v0.7+ 에 실 provider 도입과 동시 진행
- **재무 score 룰 기반** — 절댓값 buckets 기반 (PER ≤8:+8 / ≤15:+4 / ... / debt_ratio ≥200:-15 등). 시장 percentile / 섹터 평균 기반 정규화는 v0.7+ 후보. 시장 환경 변화 (금리 / 섹터 재편) 시 재조정 필요할 수 있음
- **earnings surprise 분류 기준 단순화** — operating income 만 사용한 ±5% 임계값. EPS / 매출 / 순이익 surprise 가중 평균은 v0.7+ 후보
- **운영 DB 마이그레이션 자동화 부재** — `fundamental_snapshots` + `earnings_events` 두 신규 테이블은 별도 절차로 적용 (Alembic 미사용). v0.5 `news_items.category` ALTER ADD COLUMN 까지 누적 4건 시점에 도입 검토
- **`.env` 의 dev override 로 인한 `test_settings_defaults` 환경 의존** — v0.3 부터 알려진 한계. CI clean env 에서는 통과하지만 로컬에서 `MARKET_CAP_LIMIT=5` 등을 설정한 경우 `--deselect` 또는 명시 env override 필요. v0.7+ 에서 settings test 격리 (예: `monkeypatch.setenv` + `Settings()` 직접 인스턴스화) 검토
- **인증 / 관심종목 / Watchlist** — 미구현. POST 라우터 도입은 인증 사이클과 묶음 (v0.7 후보)
- **earnings calendar 기본 limit 5 vs 추천 / 보유 union 미구현** — Today 화면의 `UpcomingEarningsCard` 는 단순히 가장 가까운 5건을 노출. "보유 + 추천 종목 union" 필터링은 v0.7+ 후보

## 제외 범위

다음은 모든 사이클 (v0.1 ~ v0.6) 과 동일하게 코드 일체 포함하지 않는다:

- 실거래 자동매매 (FULL_AUTO / APPROVAL / SMALL_AUTO)
- 실 KIS 주문 / `BrokerInterface` 구현체
- POST / PUT / DELETE 라우터 (read-only API 만)
- News / Disclosure / Fundamental / Earnings 자동 크롤링 / 스크레이핑 (FakeProvider 만, 실 RSS / DART 호출 0건)
- 가상 증권사 (MockBroker / ReplayBroker / SimulationBroker)
- 전략 모듈 / Strategy / Backtest / 전용 ML 학습
- 인증 / 권한 / 사용자별 관심종목
- 뉴스 / 공시 / 리포트 / 재무 / 실적 본문 (paragraph) DB 저장
- 재무제표 PDF / Excel BLOB 저장
- LLM 기반 자동 sentiment / 자동 분류 / 자동 재무 분석
- 추천 산식 본 weight 변경
- HoldingCheckEngine 본 weight 변경

## v0.7 후보

v0.6 마감 후 검토 가능한 후보들. 각 항목은 명시적 진입 요청 전까지 손대지 않는다.

### 데이터 / 분석 실제화

- **실 DART API 구현체** — v0.6 의 `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 위에 `DartFundamentalProvider` / `DartEarningsProvider` 추가. 라이선스 / 스로틀링 / 정책 검토 동반
- **실 RSS / News API 구현체** — v0.5 의 `NewsProviderInterface` 위에 `RssNewsProvider` / `NaverNewsProvider` 등
- **재무 score 산식 고도화** — v0.6 의 절댓값 기반 산식을 시장 percentile / 섹터 평균 기반으로 확장
- **earnings surprise 다지표 가중** — operating income 단일 → EPS / 매출 / 순이익 가중 평균
- **LLM 보강** — News / Disclosure 룰 sentiment + 재무 / 어닝 LLM 분석 (룰 기반 검증 후)

### 인증 / 관심종목

- **인증 / 권한** — 단일 토큰 / API key 헤더부터. POST 라우터 도입 전제
- **즐겨찾기 / 관심종목** — Watchlist 테이블 신규 + POST `/api/watchlist`. 인증 동반 필수
- **글로벌 검색** (cmd+k), 사이드바 collapse, breadcrumb, loading skeleton 통일
- **audit log** — POST 도입과 함께

### 운영 / UX

- **운영 모니터링** — Sentry / Prometheus / Grafana
- **모바일 / 태블릿 레이아웃** — 현재는 PC 1280px+ 우선
- **StockDetail 캔들 차트 + 거래량 BarChart + 이동평균 오버레이** — `lightweight-charts` 마이그레이션 검토
- **운영 DB migration / Alembic 도입** — 누적 ALTER 가 v0.5 `news_items.category` + v0.6 `fundamental_snapshots` + `earnings_events` 시점에 도입 검토

### 백엔드 인프라

- **POST 트리거** (잡 수동 실행 / 추천 즉시 생성) — 인증 동반 필수
- **WebSocket / SSE 실시간 잡 상태** — 현재 polling
- **`.github/dependabot.yml`** — v0.3 Phase A 보류 항목

### Future Backlog (자동매매)

⚠ **별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실 제한 사이클이
선행되어야 진입 가능.** v0.7 도 자동매매 부재 정책을 유지한다.

| 단계 | 진입 전제 |
|---|---|
| Strategy & Signal | 실 News (v0.5) + 실 재무 (v0.6) + 인증 (v0.7) 후행 |
| Backtest 엔진 | Strategy 모듈 선행 |
| MockBroker / ReplayBroker / SimulationBroker | BrokerInterface 구현 진입 |
| 전용 ML 모델 | Backtest 데이터 누적 후행 |
| APPROVAL 모드 | 컴플라이언스 검토 + MockBroker 검증 |
| SMALL_AUTO | APPROVAL 안정 운영 후 |
| FULL_AUTO | 본 프로젝트 범위 외 |

## 운영 가이드 요약

자세한 절차는 [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §13 ~ §15 참조.

### 재무 CSV 수동 import

```powershell
# dry-run (default)
.\.venv\bin\python.exe -m scripts.import_fundamentals --file tests/fixtures/fundamentals_sample.csv

# 실 적재
.\.venv\bin\python.exe -m scripts.import_fundamentals --file <path> --commit
```

CSV 헤더에 forbidden body column 13종 (body / content / full_text / paragraph_text /
raw_text / 본문 / 원문 / 전문 / disclosure_text / report_text / news_body /
article_body / pdf_text) 이 포함되면 즉시 거부. `summary` 컬럼이 있으면 500자
초과 시 truncate 후 `truncated_notes` 카운트 증가. 자세한 컬럼 / 검증 정책은
INTEGRATION_RUNBOOK §13 참조.

### 실적 CSV 수동 import

```powershell
.\.venv\bin\python.exe -m scripts.import_earnings --file tests/fixtures/earnings_events_sample.csv --commit
```

`memo` 컬럼은 ≤500자만 저장. `surprise_type` 미지정 시 operating_income actual /
consensus 로 자동 계산 (≥+5% BEAT / ≤-5% MISS / 그 사이 MEET / consensus 0/NULL
UNKNOWN).

### 신규 read-only API 수동 확인

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/stocks/005930/fundamentals?limit=4 |
  Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:8000/api/stocks/005930/earnings?limit=4 |
  Select-Object -ExpandProperty Content
Invoke-WebRequest "http://127.0.0.1:8000/api/calendar/earnings?from_date=2026-05-01&to_date=2026-05-31&limit=10" |
  Select-Object -ExpandProperty Content
```

응답 트리에 `source_file_path / body / content / full_text / raw_text / paragraph
/ html_body / 본문 / 원문 / 전문` 13종 forbidden 키워드는 0건이어야 한다 (backend
pytest 가 자동 검증).

### 4 게이트 재실행 명령

```powershell
# 백엔드 — 로컬 .env override 가 있으면 settings test 1건 deselect
.\.venv\bin\python.exe -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults

# 프런트
cd frontend
npm run test
npm run build
npm run e2e
```

## 누적 인수 태그 (v0.1 ~ v0.6)

- `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
- `v0.2-frontend-final`
- `v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final`
- `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` → `v0.4-frontend-reports` → `v0.4-final`
- `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` → `v0.5-frontend-themes` → `v0.5-final`
- v0.6 Phase A: 별도 태그 부재 (커밋 `0d3dba5` + `da3567f` 으로 추적, `v0.6-fundamental-data-layer` 태그는 부여하지 못함)
- `v0.6-earnings-event-pipeline` → `v0.6-fundamental-score` → `v0.6-frontend-fundamentals` → **`v0.6-final`** (예정)
