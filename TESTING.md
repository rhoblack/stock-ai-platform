# TESTING.md

> 본 문서는 **v0.6 마감 시점** 기준으로 갱신된다 (`v0.6-frontend-fundamentals` 누적,
> `v0.6-final` 마감 예정). 누적 cycle 의 게이트 baseline 과 v0.4 / v0.5 / v0.6
> 신규 테스트 카테고리를 반영한다.

## 1. 현재 회귀 게이트 (v0.6 마감 시점)

모든 사이클에서 4 게이트가 그린 상태로 유지된다. 외부 API / 텔레그램 / 주문은
어떤 테스트에서도 실제로 호출되지 않는다.

| 게이트 | 명령 | 현재 baseline |
|---|---|---|
| backend pytest | `.\.venv\bin\python.exe -m pytest -q` | **558 passed** (v0.1 296 → v0.3 319 → v0.4 final 382 → v0.5 final 481 → v0.6 Phase C 544 → Phase D 558) |
| frontend vitest | `cd frontend && npm run test -- --run` | **77 passed** (13 파일, jsdom + msw v2) |
| frontend build | `cd frontend && npm run build` | 그린 (`tsc --noEmit && vite build`, vendor-charts 청크 383 kB / gzip 105 kB) |
| Playwright e2e | `cd frontend && npm run e2e` | **13 passed** (chromium + page.route mock) |

GitHub Actions CI 가 main / PR 양쪽에서 위 4 게이트를 자동 검증한다 (실 KIS /
Telegram 호출 0건). 자세한 CI 정의는 [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

## 2. 테스트 목표 (cycle-wide)

본 프로젝트는 실거래 없는 read-only 분석 / 추천 / 보유점검 + 증권사 리포트
인텔리전스 + 대시보드 시스템이다. 테스트의 핵심:

- 지표 / 점수 계산 정확성 (캔들·ATR·변동성 포함)
- 추천 / 보유 판단 저장 + 1/3/5/20일 후 성과 검증
- snapshot / log 저장 (`data_snapshots`, `decision_logs`, `job_runs`, `notification_logs`)
- 외부 API mock 처리 (KIS / Telegram)
- 텔레그램 메시지 포맷 (DRY_RUN 기본)
- FastAPI 조회 API (15+ GET, **POST 0건**)
- 자동매매 / 실 주문 / FULL_AUTO / POST 트리거 부재 가드 (e2e)
- 비밀값 마스킹 가드 (KIS 키 / Telegram 토큰 / `source_file_path`)
- **(v0.4)** 리포트 / 테마 / 매핑 / 시그널 이벤트 CRUD + idempotency + 저작권
  정책 (원문 본문 거부 / source_file_path 미노출)

## 3. 테스트 도구

- **pytest** (backend, 8.4.x)
- **httpx.MockTransport** — KIS HTTP 클라이언트 / Telegram BOT API mock
- **FakeKisDataProvider** — `DataProviderInterface` 대체
- **SQLite in-memory** — backend 통합 테스트 DB
- **vitest 2.x** + **@testing-library/react** + **msw v2** + **jsdom** — frontend 단위/통합
- **Playwright** (chromium) + `page.route` mock — frontend e2e
- **csv (stdlib)** — v0.4 import 테스트 입력 (pandas / openpyxl 의존성 미사용)

## 4. 테스트 폴더 구조

```text
tests/
├─ unit/
│  ├─ test_technical_analyzer.py        # MA / RSI / MACD / breakout / 캔들 / ATR / 변동성
│  ├─ test_scoring_engine.py
│  ├─ test_recommendation_engine.py
│  ├─ test_holding_check_engine.py
│  ├─ test_report_generator.py
│  ├─ test_score_producers.py
│  └─ test_project_structure.py
├─ integration/
│  ├─ test_repositories.py
│  ├─ test_api_routes.py
│  ├─ test_scheduler_jobs.py
│  ├─ test_indicator_service.py
│  ├─ test_recommendation_engine.py
│  ├─ test_holding_check_engine.py
│  ├─ test_recommendation_result_service.py
│  └─ test_analyst_report_repositories.py     # v0.4 Phase A 신규 — 16 케이스
├─ fixtures/                                  # v0.4 Phase B 진입 시 추가 예정
│  └─ analyst_reports_sample.csv              # (예정)
└─ mocks/
   ├─ kis_responses.py
   ├─ fake_kis_client.py
   └─ sample_market_data.py

frontend/
├─ src/tests/
│  ├─ App.test.tsx
│  ├─ useHealth.test.tsx
│  ├─ TodayReport.test.tsx
│  ├─ Recommendations.test.tsx
│  ├─ RecommendationHistory.test.tsx
│  ├─ Holdings.test.tsx
│  ├─ StockDetail.test.tsx                    # v0.3 Phase D — 일봉 차트 테스트 포함
│  ├─ MarketCapTop.test.tsx
│  ├─ Jobs.test.tsx
│  ├─ Settings.test.tsx
│  ├─ marketCalendar.test.tsx                 # v0.3 Phase C — 15 케이스
│  ├─ MarketStatusBanner.test.tsx             # v0.3 Phase C — 4 케이스
│  ├─ mswServer.ts
│  └─ renderWithProviders.tsx
└─ e2e/
   ├─ dashboard.spec.ts                       # 8 케이스 (sidebar / Jobs JSON / MarketCap 필터/검색 / 마스킹 / 자동매매 부재 / Banner / 일봉 차트)
   └─ fixtures/apiMocks.ts
```

## 5. 필수 테스트

### TechnicalAnalyzer

- MA 계산 (5/20/60/120)
- RSI 계산 (14)
- MACD 계산
- volume_ratio_20d 계산
- breakout 계산 (20d / 60d)
- ma_alignment 분류
- 데이터 부족 시 None / safe fallback
- **(v0.3 Phase B)** Wilder ATR(14) 계산
- **(v0.3 Phase B)** 캔들 패턴 5종 detector (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING / BEARISH_ENGULFING)
- **(v0.3 Phase B)** 4단계 변동성 분류 (LOW / NORMAL / HIGH / EXTREME)
- **(v0.3 Phase B)** `calculate_technical_score` 의 `candle_bonus` ±5 cap + `volatility_bonus` -5~+2 + 0~100 clamp

### ScoringEngine

- 신규 추천 점수 공식
- 보유 종목 점수 공식
- risk_penalty 반영
- AI 점수 비중 제한

### DummyScoreProducer

- 뉴스/수급/재무/실적/AI placeholder 기본 50점
- 사용 가능한 지표 기반 rule 보정
- 외부 뉴스/API/LLM 호출 없음

### RecommendationEngine

- 시총 TOP 500 필터링
- 위험 종목 제외
- TOP 5 생성
- recommendations 저장
- data_snapshots 생성
- decision_logs 생성

### HoldingCheckEngine

- 수익률 계산
- 장전/장후 점검 생성
- 점수 급락 경고
- 20일선 이탈 경고
- holding_checks 저장

### ReportGenerator

- 추천 리포트 포맷
- 장전 점검 포맷
- 장후 점검 포맷
- 위험 경고 포맷

### KIS Client

- 외부 API mock
- 인증 실패 처리
- 재시도 처리
- 응답 정규화

### Backend API

- 주요 GET API 응답
- schema 검증
- 없는 데이터 처리
- 페이지네이션/필터 기초

## 6. v0.4 신규 — Analyst & Theme Intelligence 테스트

v0.4 Phase A 에서 **통합 테스트 16건** 신규 (`tests/integration/test_analyst_report_repositories.py`).
모두 SQLite in-memory + 6 신규 Repository 직접 호출. 외부 API 호출 0건.

### 6.1 AnalystReport (6 케이스)

- COMPANY 리포트 CRUD + `target_price` Decimal 정밀도
- `(broker_name, published_at, title)` unique 충돌 시 `upsert_unique` → 기존 행 반환 (extraction_method 미덮어씀)
- THEME / MACRO / COMMODITY 리포트의 `symbol = null` 허용
- 글로벌 리포트 (US / NASDAQ / USD / Goldman Sachs / English) 동일 테이블 저장
- `list_by_symbol` / `list_by_report_type` 쿼리
- `search_text` 가 title + summary 양쪽 LIKE 매칭

### 6.2 ReportTheme (2 케이스)

- `upsert_by_report_and_theme` 멱등 (extraction_method 미덮어씀)
- `list_by_category` / `list_by_direction` / `list_by_source_report`

### 6.3 ThemeStockMapping (2 케이스)

- `upsert_by_theme_and_symbol` 멱등
- 5 list 변형 (theme / symbol / positive / negative / impact_path) — "구리 부족" 테마 → 풍산 (NEGATIVE / COST_PRESSURE) + LS (POSITIVE / MARGIN_IMPROVEMENT) 동시 매핑 시나리오

### 6.4 ReportSignalEvent (2 케이스)

- `upsert_by_report_event_symbol_theme` (NULL-aware) — evidence_json 보존
- 6 list 변형 (symbol / theme / event_type / positive / negative / recent)

### 6.5 ReportConsensusSnapshot (1 케이스)

- `upsert_by_symbol_date_window` 갱신 (window_days 30 vs 90 분리 저장)
- `get_latest_by_symbol(window_days=…)` 필터

### 6.6 ReportScoreLog (2 케이스)

- 정렬 (`score_date desc, id desc`)
- NULL `recommendation_run_id` 다중 행 허용 (SQLite/PG NULL distinct 정책)

### 6.7 메타 (1 케이스)

- 6 신규 테이블이 `Base.metadata` 에 등록되었는지 검증

### 6.8 Phase B 진입 시 추가 예정 (현재 미구현)

- `tests/integration/test_analyst_report_import.py` — CSV dry-run / commit /
  멱등 / 필수 컬럼 누락 / 본문 컬럼 거부 (영문·한글) / enum / date / number /
  500자 truncate / signal_strength 범위 / theme·mapping·signal 추출 분기 /
  `source_file_path` 마스킹 검증 / programmatic entry
- `tests/integration/test_consensus_snapshot_job.py` — NO_DATA / 다종목 산정 /
  90일 윈도우 외 제외 / non-COMPANY 제외 / 멱등 upsert / job_runs 기록

## 6.9 v0.5 Phase A/B/C — News, Disclosure, RealNewsScoreProducer 테스트

v0.5 cycle 의 News + Disclosure + 점수 실제화 테스트 카운트:

- Phase A PR1 (data layer skeleton) — `tests/integration/test_news_collector.py` 신규 19 케이스 (DTO 본문 필드 0 가드 / FakeNewsProvider determinism / collector 멱등 / category persist / repository 메서드)
- Phase A PR2 (scheduler integration) — `tests/integration/test_scheduler_jobs.py` 보강 5 케이스 (registry 7→8 jobs / 19:00 schedule / collect_news 3-way branch / 멱등) + `test_settings_defaults` 의 `news_collection_enabled is False` 단언
- Phase B (Disclosure subset) — `tests/integration/test_disclosure_collector.py` 신규 24 케이스 (DTO 가드 / classify_disclosure 18 (parametrized Korean keywords + priority RISK > EARNINGS > GOVERNANCE / OTHER fallback) / FakeDisclosureProvider 4 / collector flow 7) + scheduler 보강 5 케이스 (registry 8→9 / 20:00 / collect_disclosures 분기 / 멱등) + `test_settings_defaults` 의 `disclosure_collection_enabled is False`
- Phase C (RealNewsScoreProducer + DisclosureRiskProducer) — `tests/unit/test_real_news_score_producer.py` 신규 17 케이스 (RealNews 9: news_count=0 / 양수·음수 recent / 6일·7일 윈도우 / mixed sentiment / evidence top 3 / fallback delegation / score_holding 패턴 + Disclosure 8: no risk / penalty 3·9·cap10 / 14일 윈도우 / symbol 필터 / non-risk 제외 / evidence top 3) + RecommendationEngine 보강 5 케이스 + HoldingCheckEngine 보강 3 케이스 + RiskEngine 보강 5 케이스
- Phase D (테마 API + Recommendation evidence surfacing + 프론트 9th 메뉴) — `tests/integration/test_api_routes.py` 보강 11 케이스: 테마 ranking 6 (전체 + category/direction 필터 / invalid direction 422 / 빈 결과 / limit / source_file_path 가드) + 테마 detail 4 (mappings + signal_events 노출 / 404 / 빈 매핑 / source_file_path 가드 통합) + recommendation 2 (snapshot.market_context_json → news_evidence + disclosure_risk_evidence whitelist 노출 / pre-v0.5 snapshot 의 두 필드 None 단언). 프론트 vitest +8 케이스 (Themes 5 + ThemeDetail 3) + 기존 Recommendations / StockDetail / App 테스트 보강. e2e 9 → 11 (Themes 랭킹/상세 + StockDetail → Theme link 네비 + Recommendations evidence cells)

핵심 안전 가드:
- DTO 본문 필드 0 — `dataclass.fields(NewsItemDTO)` / `DisclosureItemDTO` 명시 단언
- Evidence safe-fields whitelist — top_news / recent_risk_disclosures 의 dict key 가 정확히 `{title, url, provider, published_at, sentiment}` (또는 sentiment 제외 disclosure 세트) 인지 단언. body / content / full_text / source_file_path 0건
- collect_news / collect_disclosures default OFF — disabled spy provider 의 `calls == []` 명시 검증 (외부 호출 0건 가드)
- ScoringEngine 본 weight (technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%) 산식 변경 0건 — Phase C 가 news_score 만 50 → real 로 교체, 기존 추천 / 보유 회귀 테스트 그대로 통과

## 6.10 v0.6 Phase C — Fundamental / Earnings score producer 테스트

v0.6 Phase C 는 CSV 로 적재된 정량 데이터만 사용한다. DART / KIS / Telegram /
LLM / 주문 API 는 어떤 테스트에서도 호출하지 않는다.

- `tests/unit/test_real_fundamental_earnings_score_producers.py` 신규 — 데이터 없음 50 fallback, 좋은 재무 가산, 나쁜 재무 감산, debt ratio 감점, growth 가산, 0~100 clamp, BEAT/MISS/MEET/UNKNOWN, surprise_pct cap, old event 영향 감소, upcoming UNKNOWN 중립, evidence whitelist 를 검증한다.
- `tests/integration/test_recommendation_engine.py` 보강 — `RealFundamentalScoreProducer` 가 추천 `fundamental_score` 에 반영되고, `decision_logs.rule_result_json["fundamental_evidence"]` 와 `data_snapshots.market_context_json["fundamental_evidence"]` 에 동일 safe evidence 가 저장되는지 확인한다.
- `tests/integration/test_holding_check_engine.py` 보강 — `RealEarningsScoreProducer` 가 보유점검 `earnings_score` 에 반영되고, `decision_logs.rule_result_json["earnings_evidence"]` 와 `data_snapshots.market_context_json["earnings_evidence"]` 에 동일 safe evidence 가 저장되는지 확인한다.

핵심 안전 가드:
- `fundamental_evidence` 는 `snapshot_date`, `fiscal_year`, `fiscal_quarter`, `per`, `pbr`, `roe`, `debt_ratio`, `revenue_growth_yoy`, `operating_income_growth_yoy`, `dividend_yield` 만 허용한다.
- `earnings_evidence` 는 `latest_event_date`, `fiscal_year`, `fiscal_quarter`, `event_type`, `surprise_type`, `surprise_pct`, `operating_income_actual`, `operating_income_consensus` 만 허용한다.
- `source`, `source_file_path`, `memo`, `summary`, `body`, `content`, `full_text`, `paragraph`, `raw_text`, `html_body`, `본문`, `원문`, `전문` 계열은 evidence 에 포함하지 않는다.
- ScoringEngine 본 weight 변경 0건 — recommendation 35/25/15/15/10, holding 35/20/20/15/10 회귀 테스트로 고정한다.

## 6.11 v0.6 Phase D — 재무 / 실적 read-only API + 프런트 카드 + evidence 노출

v0.6 Phase D 는 신규 read-only API 3종 (`/api/stocks/{symbol}/fundamentals`,
`/api/stocks/{symbol}/earnings`, `/api/calendar/earnings`) + 기존 추천 / 보유
점검 응답에 `fundamental_evidence` / `earnings_evidence` 필드를 추가한다. 본
weight 산식 변경 0건, 신규 POST 0건, KIS / DART / Telegram 호출 0건.

- `tests/integration/test_api_routes.py` 보강 — 신규 9 백엔드 케이스:
  fundamentals happy / empty / 404 / limit clamp, earnings happy / empty / 404,
  calendar happy + from/to 필터 + surprise_type 필터, calendar default 가
  "오늘 이후" 만 반환, calendar limit clamp, recommendation `fundamental_evidence`
  whitelist (forbidden 13종 strip 검증), recommendation pre-v0.6 → null,
  holding check `earnings_evidence` whitelist + pre-v0.6 → null.
- `frontend/src/tests/StockDetail.test.tsx` 보강 — Fundamentals 카드 happy /
  empty / error 3건 + Earnings 카드 happy / empty / error 3건 + recent holding
  check 의 earnings_evidence cell 1건. 모든 케이스에서 `source_file_path` /
  `원문` / `본문` 미노출 단언.
- `frontend/src/tests/Recommendations.test.tsx` 보강 — happy 시나리오에
  `rec-fund-evidence-{symbol}` / `rec-earnings-evidence-{symbol}` 셀 단언 +
  null fallback 시나리오에 두 cell 모두 "—" 단언 + forbidden 필드 미노출 단언.
- `frontend/src/tests/TodayReport.test.tsx` 보강 — UpcomingEarnings 카드 happy
  (calendar items 표시) + empty placeholder 케이스.
- `frontend/src/tests/mswServer.ts` — 3 신규 default 핸들러 (fundamentals /
  earnings / calendar) 모두 빈 응답 + Stock-NotFound 흐름 fallback.
- `frontend/e2e/dashboard.spec.ts` 보강 — Recommendations evidence cell 셀에
  fund / earnings 두 cell 추가 단언, StockDetail Fundamentals + Earnings 카드
  visible + 원문 / 본문 / source_file_path 0건 단언, Today UpcomingEarnings 카드
  visible 단언 (e2e fixture 의 calendar mock 사용).
- `frontend/e2e/fixtures/apiMocks.ts` — `STOCK_FUNDAMENTALS_005930`,
  `STOCK_EARNINGS_005930`, `EARNINGS_CALENDAR` 신규 + 라우터 패턴 추가.

핵심 안전 가드:

- API 라우터 레벨에서 `_whitelist_evidence(snapshot, key, allowed)` helper 가
  `fundamental_evidence` / `earnings_evidence` dict 의 모든 키를 화이트리스트
  검증 후 응답한다 — Phase C 의 score producer 단계 + Phase D 의 라우터 단계로
  defense-in-depth 2 단 방어.
- 모든 신규 API 케이스가 `_assert_no_source_file_path(body)` 로 `source_file_path`
  문자열의 응답 트리 0건을 재귀 검증.
- `body / content / full_text / raw_text / paragraph / html_body / 본문 / 원문 /
  전문` 13종 forbidden 키워드는 응답 텍스트 변환 후 substring 검사로 0건 보장.
- `RecommendationItemSchema.fundamental_evidence` / `earnings_evidence`,
  `HoldingCheckSchema.fundamental_evidence` / `earnings_evidence` /
  `news_evidence` / `disclosure_risk_evidence` 모두 nullable — pre-v0.6 snapshot
  은 null 반환으로 호환성 유지.
- 프런트 evidence cell 은 `reason: "no_fundamental_snapshot"` /
  `"no_earnings_event"` 시그널을 명시적으로 검사해서 placeholder "—" 로 렌더 —
  데이터 부족 시 빈 문자열 / 잘못된 숫자가 노출되지 않는다.

## 7. 금지 사항

테스트에서 절대 금지:

- 실제 KIS API 호출
- 실제 텔레그램 발송
- 실제 계좌번호 사용
- 실제 주문 API 호출
- 실거래 관련 테스트 구현
- **(v0.4)** 리포트 자동 크롤링 / 스크레이핑 mock — manual CSV import 만 검증
- **(v0.4)** `source_file_path` 가 출력 / 에러 메시지 / 응답에 노출되는 테스트
  (오히려 부재를 명시적으로 단언해야 함)

## 8. 테스트 실행 명령 예시

```powershell
.\.venv\bin\python.exe -m pytest                      # 전체 backend (335 passed)
.\.venv\bin\python.exe -m pytest tests/unit
.\.venv\bin\python.exe -m pytest tests/integration
.\.venv\bin\python.exe -m pytest tests/integration/test_analyst_report_repositories.py  # v0.4 Phase A

cd frontend
npm run test -- --run                                 # vitest (59 passed)
npm run build                                         # tsc + vite build
npx playwright test                                   # e2e (8 passed)
```

DB/Repository 테스트는 SQLite 메모리 DB를 사용한다. 실제 KIS API, 텔레그램,
주문 API는 호출하지 않는다.

Phase 2 DB 테스트는 다음을 확인한다.

- v0.1 필수 테이블 생성
- Repository 저장/조회
- `daily_prices`의 `symbol + date` upsert
- `stock_universe_members`의 `universe_id + symbol` 중복 방지
- recommendation run/result/snapshot 관계
- holding check/decision log/snapshot 관계
- notification log/job run 관계

Phase 3-1 KIS/Data 테스트는 실제 KIS API를 호출하지 않고 mock 응답만 사용한다.

- KIS 현재가/일봉/시가총액 응답 normalizer
- DataQualityChecker의 중복/누락/이상값 감지
- 실제 API 키, 계좌번호, 토큰 사용 금지

Phase 3-2 KIS HTTP 구조 테스트도 실제 KIS API를 호출하지 않고 `httpx.MockTransport`
기반 mock 응답만 사용한다.

- `KisClient` 토큰 발급, 현재가, 일봉, 시가총액 상위 조회 request shape
- KIS API 오류 코드, HTTP 오류, timeout, JSON/응답 형식 오류 처리
- app key, app secret, bearer token 로그 마스킹
- 주문 API, 자동매매, 추천 로직, 기술 지표 계산, 텔레그램 발송 테스트 금지

Phase 3-3 Collector 통합 테스트는 `tests/mocks/fake_kis_client.py`의 `FakeKisDataProvider`로
`DataProviderInterface`를 대체하고 SQLite in-memory DB만 사용한다.

- `DailyPriceCollector` raw → normalize → `daily_prices` upsert 흐름
- 동일 `symbol+date` 재수집 시 중복 없이 갱신되는지
- `DataQualityChecker` 결과가 collector 결과에 그대로 노출되는지
- `MarketCapRankingCollector`가 `market_cap_rankings` 스냅샷을 교체하면서 순위 재배치 시
  unique 제약을 위반하지 않는지
- `stocks`, `stock_universes`, `stock_universe_members`까지 함께 동기화되는지
- 실제 KIS API/주문 API/텔레그램 호출 금지

Phase 4-1 `TechnicalAnalyzer` 단위 테스트는 외부 의존성 없이 `KisDailyPrice` DTO 시퀀스만
입력으로 받아 순수 계산을 검증한다.

- `simple_moving_average`, `relative_strength_index`, `compute_macd`,
  `compute_volume_ratio_20d`, `compute_breakout`, `classify_ma_alignment`,
  `calculate_technical_score`의 입력별 동작
- 데이터 부족 시 None 반환 및 안전한 fallback
- `TechnicalAnalyzer.analyze_latest`가 정렬되지 않은 bar를 정렬해 처리
- `IndicatorSnapshot` 필드가 `Numeric(20,4)` / `Numeric(10,4)` 컬럼에 맞게 4자리로
  quantize되는지
- DB, 외부 API, 추천/보유점검/텔레그램 호출 일체 없음

Phase 4-2 통합 테스트는 SQLite in-memory DB와 `TechnicalIndicatorService`로
`daily_prices` → `TechnicalAnalyzer` → `stock_indicators` 흐름 끝단을 검증한다.

- 가격이 없는 종목은 `stock_indicators` 행을 생성하지 않음
- 130봉 이상이면 13개 필드를 모두 채워 upsert
- 같은 (symbol, date) 재실행 시 행이 중복되지 않고 갱신만 발생
- 가격 정정 후 재실행하면 `technical_score`가 새 값으로 덮어씌워짐
- `lookback_days` 제한으로 입력 윈도우 축소 (MA60 None 등)
- `analyze_and_store_many`가 가격 없는 종목은 결과에서 제외
- 외부 API/주문/텔레그램/추천 후보 선정 호출 없음

Phase 4-2 `ScoringEngine` 단위 테스트는 순수 계산 검증이며 외부 의존성 없음.

- 가중치 합 = 1.00 (신규 추천 / 보유 모두)
- 만점 입력 → 100, None 입력 → 0
- `risk_penalty` 차감 / 음수 penalty floor 0 / penalty 과다 시 0 clamp
- 입력 100 초과/음수는 weighting 전 clamp
- `ScoreBreakdown` 컴포넌트 합계 - penalty == raw_total 일치
- 추천 후보 선정/보유 판단/텔레그램/AI 호출 없음

`DummyScoreProducer` 단위 테스트는 실제 뉴스/재무/AI 파이프라인이 없는 v0.1에서
중립 component score를 안정적으로 제공하는지 검증한다.

- recommendation: news/supply/fundamental/ai 기본 50점
- holding: news/earnings/ai 기본 50점
- `volume_ratio_20d`, `ma_alignment`가 있으면 보수적 rule 보정
- KIS/뉴스/텔레그램/AI 호출 없음

Phase 5-1 `RecommendationEngine` 통합 테스트는 SQLite in-memory DB와 Repository 9종을
연결해 추천 흐름 전체를 검증한다.

- 유니버스 미존재 / 멤버 0 → status="EMPTY" run 생성, recommendations 0건
- 지표 없는 종목 자동 skip + `skipped_no_indicator` 카운트
- TOP N 정렬 (`total_score desc`, 동점 시 `symbol asc`)
- `recommendation_runs` `started_at`/`finished_at`/`status`/`market_summary` 기록
- `recommendations` 행이 `data_snapshots`와 `decision_logs`에 같은 `snapshot_id`로 연결
- `news_score`/`supply_score`/`fundamental_score`/`ai_score`가 dummy/rule 기반으로 저장
- `risk_score`는 `RiskEngine` penalty로 저장
- `reason` = "관찰 후보 …" / `risk_note` = dummy score producer + risk level
- `decision_logs.final_decision` = `"WATCH_CANDIDATE_RANK_{n}"`
- 등급 `_grade_for_score` 임계값 (S≥85, A≥70, B≥55, C≥40, D<40)
- 같은 날짜에 두 번 호출하면 별도 run_id 생성
- 사용자 지정 universe_name 동작 / `top_n=0` 시 EMPTY
- KIS API/지표 재계산/텔레그램/AI 호출 일체 없음

Phase 6 `ReportGenerator` 단위 테스트는 ORM 모델 + risk metadata만 입력으로
받아 텔레그램 텍스트 포맷을 검증한다 (DB / 외부 호출 없음).

- `extract_risk_summary`: 스냅샷의 `market_context_json.risk_summary`에서 level/flags 추출, None / 빈 dict 시 LOW 기본값
- 추천 리포트: 제목 / 시장 요약 / 빈 리스트 안내 / TOP 후보 라인 / rank 정렬
- 보유 리포트: HIGH risk_level이 상단에 별도 섹션, 일반 종목은 그 아래
- 단일 위험 경고 포맷
- HIGH가 없으면 `⚠ 위험 경고 종목` 섹션 자체가 없음

Phase 6 `TelegramNotifier` 단위 테스트는 `httpx.MockTransport`로 BOT API를
대체해 실제 telegram.org와 통신하지 않는다.

- chat_id 마스킹 (`12****90`), bot token은 절대 결과/에러 메시지에 노출 금지
- `TELEGRAM_ENABLED=false` → DRY_RUN, HTTP 호출 일체 없음
- 자격증명 누락 → DISABLED
- 200 + ok=true → SUCCESS
- HTTP ≥ 400 → FAILED (코드 포함)
- 200 + ok=false → FAILED (description 포함)
- timeout / RequestError → FAILED
- non-JSON 응답 → FAILED

Phase 5 후속 `RecommendationResultService` 통합 테스트는 SQLite in-memory DB만
사용해 추천 행을 1/3/5/20일 후 daily_prices 기준으로 평가하는 것을 검증한다.

`tests/integration/test_recommendation_result_service.py`:
- 임계값 분류: close_return≥+1% → SUCCESS, high_return≥+3% → SUCCESS,
  low_return≤-5% → FAILED (우선순위), 그 외 → PENDING
- 1/3/5/20 days_after 모두 한 번에 처리 (4행 업서트)
- 데이터 부족 → PENDING + 모든 return None 저장 (`skipped_no_reference` 카운트)
- 기준 가격 fallback: run_date에 daily_prices 없으면 14일 lookback 안에서
  가장 최근의 (≤ run_date) 종가 사용 (주말/휴일 보정)
- max_drawdown은 (window 내 최저저가 - peak) / peak * 100 (peak는 reference와
  window 내 최고가 중 큰 값)
- 동일 (recommendation_id, days_after) 재실행 시 upsert로 행 1개 유지
- PENDING 상태가 데이터 보강 후 SUCCESS로 갱신됨 (id는 동일)
- `lookback_days`로 범위 밖 옛 추천 제외
- 빈 DB → 0건 처리

`update_recommendation_results` 잡 통합 테스트:
- 추천 0건일 때도 SUCCESS 종료, summary에 0 카운트
- 시드 1건 + 가격 데이터 → 4행 (days_after 1/3/5/20) 업서트, 잡 결과
  summary에 `processed_recommendations`, `upserted_results` 등 노출

Phase 8 follow-up `Dispatcher` 통합 테스트는 ORM → `ReportGenerator` →
`NotificationService` 경로를 검증한다 (실제 텔레그램 발송 없음).

`tests/integration/test_dispatchers.py`:
- `RecommendationReportDispatcher`:
  - DRY_RUN(`telegram_enabled=False`): `notification_logs` 행 생성, sent=False,
    `recommendation_runs.telegram_sent`는 False 유지, 메시지 본문에
    "[AI 주식 리포트]" / 후보 라인 / 리스크 텍스트 포함
  - SUCCESS (`httpx.MockTransport`로 ok=true 응답): `telegram_sent=True`로 갱신
  - FAILED (api ok=false): `telegram_sent`는 False 유지
  - 알 수 없는 run_id → `ValueError`
  - `related_job_id`로 `JobRun` 연결
  - 추천이 0건인 EMPTY run도 "관찰 후보가 없습니다" 메시지 dispatch
- `HoldingCheckReportDispatcher`:
  - DRY_RUN: HIGH 위험 보유에 대해 "⚠ 위험 경고 종목" 섹션 + 한국어 라벨 출력
  - POST_MARKET 호출 시 "[보유 종목 장후 점검]" 제목 사용
  - 보유 점검 0건 → "점검 대상 보유 종목이 없습니다" 메시지 dispatch
  - 잘못된 `check_type` → `ValueError`
  - SUCCESS 경로 (`httpx.MockTransport`): `notification_logs.sent_at` 채워짐
  
- `HoldingRiskAlertDispatcher`:
  - `holding_checks` 중 `alert=True` 또는 `risk_level=HIGH` 인 항목에 대해
    `risk_alert` 포맷터로 알림 생성
  - `notification_logs.message_type = "ALERT"` 로 저장
  - 동일한 `symbol + check_date + check_type + alert_type` 대상은 재실행 시
    중복 발송 방지 (Skip)
  - DRY_RUN: `settings.telegram_enabled=False`일 경우 HTTP 호출 없이 DB에만 로깅됨
  - `related_job_id` 연결 확인

Phase 8 follow-up `scheduler jobs` 추가 통합 테스트:
- `run_job` 래퍼가 `session.info["job_run_id"]`를 fn에 노출 → 잡 함수가
  `NotificationService.send_telegram(related_job_id=...)`로 전달 가능
- `send_recommendation_report` 잡을 `run_job`을 거쳐 실행하면
  `notification_logs.related_job_id`가 해당 `job_run_id`와 일치
- `session.info["settings"]`로 dry-run 설정을 결정적으로 주입 (env / lru_cache
  영향 받지 않음)
- Job summary의 새 필드: `notification_status`, `telegram_sent`,
  `telegram_sent_flag_updated`, `notification_log_id`, `recommendation_count`
  / `holding_check_count`, `message_length`
- `send_recommendation_report`는 새 추천을 생성하지 않고 최신
  `recommendation_runs`를 조회해 `RecommendationReportDispatcher`로 전달한다.
  최신 run이 없으면 `notification_status="NO_DATA"`, `run_id=None`,
  `recommendation_count=0`으로 안전 종료하며 `notification_logs`는 생성하지 않는다.
  DRY_RUN 발송 시 `dry_run=True`, `telegram_sent=False`,
  `notification_log_id`가 summary에 기록된다.

Phase 8 `Scheduler / Jobs` 테스트는 `BackgroundScheduler`를 실제로 시작하지
않고 잡 함수와 `run_job` 래퍼를 직접 호출해 검증한다 (시간 대기 / 실제
트리거 발화는 사용하지 않음).

`tests/integration/test_scheduler_jobs.py`:
- `run_job` 래퍼: SUCCESS / PARTIAL / FAILED(예외) / 예외 시 작업 세션 롤백 /
  성공 시 작업 세션 commit / 호출마다 별도 `job_run_id` / 등록된 잡 함수와
  연결
- `collect_market_close_data`: `FakeKisDataProvider`로
  `MarketCapRankingCollector` → `DailyPriceCollector` 배선 검증, 전체 성공 /
  일부 종목 실패(PARTIAL) / 전체 종목 실패(FAILED), 실패 사유 summary 저장,
  `Settings` 기반 수집 시장/시총 limit/universe/lookback/batch override 검증
- `calculate_technical_indicators`: 설정 universe 멤버 기준으로
  `TechnicalIndicatorService` 호출, 전체 성공 / daily_prices 없음 스킵(PARTIAL) /
  일부 분석 실패(PARTIAL), `Settings` 기반 universe/lookback/batch override 검증
- 나머지 잡 함수: 빈 DB → skipped, 시드 후 실제 service/engine 호출 검증
  (`TechnicalIndicatorService`, `RecommendationEngine`, `HoldingCheckEngine`)
- 모든 잡 결과의 `telegram_sent`는 False, 테스트에서 실제 KIS API 호출 없음

`tests/unit/test_scheduler_module.py`:
- `build_scheduler`가 6개 잡을 등록하고 cron 시간이 `DEFAULT_SCHEDULE`과 일치
- 빌드 후 `scheduler.running is False` (자동 시작 안 함)
- 사용자 지정 schedule override 동작
- 잡 함수가 실제로 호출되면 `run_job`을 거쳐 `session_factory`/`job_name` 전달
  (monkeypatch로 `run_job` 가로채 검증)

Phase 6 `NotificationService` 통합 테스트는 SQLite in-memory DB와 mock
Telegram transport로 send + `notification_logs` 기록을 검증한다.

- DRY_RUN: log 행 생성, `sent_at=None`, `error_message=None`
- SUCCESS: `sent_at` 채워짐
- FAILED (api ok=false): `error_message`에 description 포함
- DISABLED: 자격증명 부재 시 HTTP 호출 없이 log만 기록
- `related_job_id`로 `job_runs` 행과 연결
- 여러 번 호출 시 log 행 누적, 상태 다양화 가능
- 실제 Telegram 발송 / KIS API / AI / 주문 호출 일체 없음

Phase 5-3 `RiskEngine` 단위 테스트는 외부 의존성 없이 추천/보유 평가 함수의
입력별 동작을 검증한다.

- `evaluate_recommendation`: technical_score 임계값 (<20),
  bearish ma_alignment ({BEAR, PERFECT_BEAR}), volume_ratio_20d None / 과도(>=5)
  플래그와 penalty 점수
- `evaluate_holding`: SCORE_DROP (직전 대비 ≥15 하락), MA20_BREAKDOWN
  (close < ma20), STOP_LOSS_NEAR (return ≤ -5), LOW_TECHNICAL_SCORE (<20)
- 다중 플래그 합산 후 PENALTY_CAP=50 캡, risk_level 분류 (LOW <5, MEDIUM 5~14.99,
  HIGH ≥15)
- `details` dict에 thresholds와 입력값 포함 (snapshot/decision_log 저장용)
- DB / 외부 API / 텔레그램 / AI / broker 호출 일체 없음

Phase 5-3에서 `RecommendationEngine`과 `HoldingCheckEngine`이 RiskEngine을
사용하도록 확장되어, 통합 테스트도 다음을 추가 검증한다.

- `recommendations.risk_score` = `RiskAssessment.risk_penalty` (이전 None →
  실제 값)
- `holding_checks.risk_score` = penalty (이전 None → 실제 값)
- `data_snapshots.market_context_json.risk_summary` = `{level, flags, penalty}`
- `decision_logs.risk_result_json` = `{...details, alerts, risk_penalty,
  risk_level}` (recommendation/holding 양쪽 모두)
- HoldingCheckEngine은 두-패스 점수 (1: 가중합, 2: risk evaluate, 3: 패널티 적용)
  로 final total_score를 계산
- `LOW_TECHNICAL_SCORE` 플래그가 holding 다중-경고 케이스에 포함됨

Phase 5-2 `HoldingCheckEngine` 통합 테스트는 `holdings` → `daily_prices` 최신가 +
`stock_indicators` 최신 지표 → `ScoringEngine.score_holding` → `holding_checks`
upsert + `data_snapshots`/`decision_logs` 기록 경로를 검증한다.

- `check_type`이 PRE_MARKET / POST_MARKET 외이면 `ValueError`
- 활성 holdings 없음 / 가격 누락 / 지표 누락 → 각각 카운트만 증가, 행 미생성
- 비활성 holding (`is_active=False`)는 분석 대상 제외
- 정상 경로: `holding_checks` 한 행 + `data_snapshots`(`HOLDING_CHECK`) +
  `decision_logs`(`HOLDING`) 가 동일 `snapshot_id`로 연결
- `news_score`/`earnings_score`/`ai_score`가 dummy/rule 기반으로 저장
- `risk_score`는 `RiskEngine` penalty로 저장,
  `decision_logs.ai_result_json` = None, component score metadata 기록
- 같은 (date, type, symbol) 재실행 시 행이 1개로 유지 (upsert)
- 같은 날 PRE_MARKET / POST_MARKET 두 번 실행 시 별도 행 2개
- 위험 경고:
  - `MA20_BREAKDOWN` (close < ma20)
  - `STOP_LOSS_NEAR` (return_rate ≤ -5%)
  - `SCORE_DROP` (직전 holding_check 대비 total_score 15점 이상 하락)
  - 첫 점검에서는 SCORE_DROP 미발생
  - 세 경고 동시 트리거 시 `decision_logs.risk_result_json.alerts`에 모두 기록
- `ma20`이 None이면 MA20_BREAKDOWN 평가 자체를 건너뜀
- 등급 임계값 (S≥85, A≥70, B≥55, C≥40, D<40)에 따른 decision 매핑
  (S/A → HOLD, B → WATCH, C → REDUCE, D → SELL_REVIEW)
- KIS API/지표 재계산/추천 로직/텔레그램/AI 호출 일체 없음

## 9. 코드 리뷰 체크리스트

- Data 모듈이 추천 판단을 하지 않는가?
- Analysis 모듈이 외부 API를 호출하지 않는가?
- Recommendation 모듈이 KIS API를 직접 호출하지 않는가?
- Notification 모듈이 점수 계산을 하지 않는가?
- API 라우터가 추천 생성을 직접 하지 않는가?
- 실거래 주문 코드가 없는가?
- API 키/토큰이 노출되지 않는가?
- snapshot/log 저장이 보장되는가?
