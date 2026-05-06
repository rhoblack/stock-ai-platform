# TESTING.md

> 본 문서는 **v0.10 Phase A 시점** 기준으로 갱신된다 (`v0.10-provider-resilience`
> 태그 포함). 누적 cycle 의 게이트 baseline 과 v0.4–v0.10 신규 테스트 카테고리를
> 반영한다.

## 1. 현재 회귀 게이트 (v0.10 Phase A 시점)

모든 사이클에서 4 게이트가 그린 상태로 유지된다. 외부 API / 텔레그램 / 주문은
어떤 테스트에서도 실제로 호출되지 않는다.

| 게이트 | 명령 | 현재 baseline |
|---|---|---|
| backend pytest | `.\.venv\Scripts\python.exe -m pytest -q` | **947 passed** (v0.10 Phase A: 916 → 947, +31 신규) |
| frontend vitest | `cd frontend && npm run test -- --run` | **146 passed** (19 파일, jsdom + msw v2; Phase C 117 → Phase D 146; +29 신규) |
| frontend build | `cd frontend && npm run build` | 그린 (`tsc --noEmit && vite build`) |
| Playwright e2e | `cd frontend && npm run e2e` | **19 passed** (chromium + page.route mock) |

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
│  ├─ WatchlistManage.test.tsx                # v0.9 Phase D — 21 케이스 (rename/delete/set-default/memo/filter/forbidden fields)
│  ├─ UserPreferences.test.tsx                # v0.9 Phase D — 15 케이스 (Settings 섹션/TodayReport/FavoriteButton preference)
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

## 6.12 v0.7 Phase A — Strategy interface + 룰 기반 전략 단위 테스트

v0.7 Phase A 는 **순수 함수 backend 로직** 만 추가한다. DB 모델 / API 라우터 /
프런트 / scheduler / 외부 호출 / 자동매매 / 주문 0건. 테스트도 모두 단위
테스트만 — DB / network / Telegram / fixture seed 의존성 0건.

- `tests/unit/test_rule_based_strategies.py` 신규 — **56 케이스**:
  - StrategySignal action 검증 (1) + 정상 액션 parametrize (3) + confidence
    `[0, 1]` 자동 clamp parametrize (7) + non-Decimal coerce (1) = **12**
  - ScoreSnapshot 최소 생성 (1) + **order field 부재 가드 (1)** (`quantity`,
    `price`, `account`, `broker`, `order_type`, `side` 모두 필드에 없음 +
    `SCORE_SNAPSHOT_FIELDS` frozenset 과 `__dataclass_fields__` 동치 단언) +
    risk_flags 인스턴스 격리 (1) = **3**
  - StrategyInterface ABC 직접 인스턴스화 차단 (1) + 3 구현체 호환 + name /
    version 검증 (1) = **2**
  - TopGradeStrategy parametrize 액션 (8) + lowercase normalize (1) = **9**
  - HighScoreStrategy threshold parametrize (10) + None → PASS (1) + confidence
    범위 가드 (1) = **12**
  - MultiSignalStrategy AVOID 우선 (3) + BUY happy + earnings None (2) + 3
    component threshold PASS (3) + low total AVOID (1) + mid PASS (1) + BEAT
    boost (1) + news skew boost (1) + combined clamp (1) + non-positive skew
    no boost (1) + missing evidence (1) + malformed evidence raise 0건 (1) = **15**
  - 3 전략 × 빈 snapshot → PASS 가드 parametrize (3) = **3**

핵심 안전 가드:

- `StrategySignal` 은 분석용 신호이지 매매 주문이 아니다. `action` 은
  `STRATEGY_ACTIONS = {BUY, PASS, AVOID}` 외 값이면 `ValueError`. `confidence`
  는 `__post_init__` 에서 `[0, 1]` 자동 clamp 되므로 호출자가 음수 / 1.0+ 을
  넘겨도 panic 없음.
- `ScoreSnapshot` 에 quantity / price / account / broker / order_type / side
  필드가 추가되면 단위 테스트가 즉시 깨진다 (`SCORE_SNAPSHOT_FIELDS` frozenset
  단언). 이는 v0.7+ 에서 strategy 레이어가 broker 레이어와 코드 단위로 격리
  유지되도록 강제하는 가드.
- 모든 룰 기반 전략은 빈 / null / malformed `evidence` 입력에 대해 raise 0건 —
  최소 PASS 로 fallback. 이 보장은 BacktestEngine (Phase B) 이 결정론적으로
  과거 snapshot 을 replay 할 수 있게 하는 전제.
- `app/strategy/` 패키지는 `requests` / `httpx` / `aiohttp` / `urllib` /
  `app.db.session` / `app.data.repositories` / KIS / DART / Telegram /
  BrokerInterface 를 import 하지 않는다 — 단위 테스트 환경에서 외부 자원
  접근 0건이 보장된다.

## 6.13 v0.7 Phase B — Backtest engine + 신규 테이블 2개 + CLI

v0.7 Phase B 는 backend ORM / Repository / engine / CLI 만 추가한다. API 라우터 /
프런트 / 비용 모델 / 시장 국면 분리는 Phase C·D 로 이연. 외부 호출 / 자동매매 /
주문 0건.

- `tests/integration/test_backtest_repositories.py` 신규 — **20 케이스**:
  - ORM metadata (2): `backtest_runs` + `backtest_results` 두 테이블 모두 expected
    컬럼 set 포함
  - `BacktestRunRepository` (7): create defaults / get_by_id 존재 / get_by_id 부재 /
    list_recent run_date desc 정렬 / list_by_strategy 필터 / mark_finished metric
    일괄 update + status SUCCESS / mark_failed status FAILED + error_message
  - `BacktestResultRepository` (7): create / bulk_insert N행 / 빈 bulk_insert
    no-op / list_by_run id asc 정렬 / list_by_symbol 필터 / aggregate_by_run
    `{action: count}` GROUP BY / aggregate_by_signal_action
  - Unique constraint (2): `(backtest_run_id, recommendation_id)` 중복 IntegrityError +
    `recommendation_id=NULL` 중복 허용
  - cascade delete: BacktestRun 삭제 → BacktestResult 자동 삭제 (sqlite `PRAGMA
    foreign_keys = ON` 활성화)
  - relationship: `BacktestRun.results` 자식 로드
- `tests/integration/test_backtest_engine.py` 신규 — **18 케이스**:
  - `build_score_snapshot` (3): 정상 (Recommendation + DataSnapshot 결합) / snapshot
    None / malformed market_context (str / 비-dict 도 raise 0건)
  - dry-run vs commit (2): dry-run 시 BacktestRun / BacktestResult 0건 / commit
    시 적재
  - 3 strategies × happy (3): TopGrade BUY/PASS/AVOID 분포 / HighScore action split
    / MultiSignal evidence 기반 BUY + win_rate 계산
  - metrics (4): BUY-only 산식 (PASS row 가 win_rate / avg_return 에 영향 0건) /
    horizon 별 missing_result_count 가산 / BUY 0건 → win_rate / avg_return /
    max_drawdown None / max_drawdown 은 BUY rows 의 최솟값 (가장 깊은 excursion)
  - buy-only 노트: `BacktestRunSummary.notes` 가 `BUY_ONLY_METRICS_NOTE` 와 일치
  - date filter (1): start_date / end_date 가 `RecommendationRun.run_date` 외부
    배제
  - CLI (4): dry-run DB 0건 / commit BacktestRun + Result 적재 /
    `UnknownStrategyError` 강제 / `main()` smoke (`--db-url` + `--strategy
    top_grade` exit 0)

핵심 안전 가드:

- `app/backtest/` + `app/strategy/` 어디에도 `requests` / `httpx` / `aiohttp` /
  `urllib` / KIS 클라이언트 / DART 클라이언트 / Telegram / `BrokerInterface`
  import 0건 (grep 검증). 외부 자원 호출 0건 보장.
- `BacktestEngine` 은 read-only — 입력 테이블은 `recommendations` /
  `recommendation_results` / `data_snapshots` / `recommendation_runs` 만 SELECT,
  쓰기 대상은 `backtest_runs` / `backtest_results` 두 신규 테이블만.
- `BacktestResult` 컬럼에 broker / 주문 / 계좌 / 가격 / 수량 컬럼 부재 — Phase A
  의 `SCORE_SNAPSHOT_FIELDS` 가드 + Phase B 의 ORM 컬럼 set 가드 양쪽으로
  강제된다.
- BUY-only 산식은 `_aggregate(rows)` 헬퍼가 `signal_action == BUY` 만 필터한
  뒤 win_rate / avg_return 계산. PASS / AVOID 는 `*_count` 에는 잡히고 수익률
  통계에는 미반영. horizon 별 NULL `close_return` 은 그 horizon 의 평균에서
  제외되고 `missing_result_count_per_horizon[h]` 에 카운트만 가산.
- `dry_run=True` (default) 에서 `session.commit()` 호출 0건이고 모든 ORM 객체는
  rollback 으로 사라진다. CLI 는 `--commit` 명시 없으면 자동 rollback.

## 6.14 v0.7 Phase C — CostModel + 시장 국면별 분리

v0.7 Phase C 는 backend 분석 layer 만 보강한다. API 라우터 / 프런트 / scheduler /
외부 호출 / 자동매매 / 주문 0건. CostModel 은 placeholder constant 만 사용 — 실
broker fee schedule fetch / 종목별 stamp duty / tick-size 슬리피지 모델링은
v0.8+ 후보.

- `tests/unit/test_cost_model.py` 신규 — **9 케이스**:
  - `version` 상수가 `"constant-v1"` 이고 `COST_MODEL_VERSION` 과 일치 (1)
  - `total_cost` = 0.00015 + 0.00015 + 0.0020 + 0.0010 = **0.0033** (0.33%) (1)
  - `apply()`: 양수 (1.5% → 1.17%) / 음수 (-2.0% → -2.33%) / zero (0 → -0.33) /
    None → None (4)
  - custom 비율 합산 (1)
  - custom version 전파 (1)
  - frozen dataclass (`buy_fee` 변경 거부) (1)
- `tests/integration/test_backtest_regime.py` 신규 — **12 케이스**:
  - `assign_regime` 4: 같은 날짜 exact match / `date <= signal_date` 가운데 가장
    최근 fallback / signal_date 가 모든 regime 데이터보다 앞이면 None / market
    필터 (KOSPI vs KOSDAQ)
  - engine summary 8:
    - dry-run summary 가 `cost_model_version` / `total_cost` /
      `cost_adjusted_avg_return_5d` / `regime_breakdown` 필드 노출
    - regime 데이터 없으면 BUY 신호가 `UNCLASSIFIED` bucket 으로 폴딩
    - commit 시 `BacktestResult.cost_adjusted_return_5d` + `regime` 컬럼 영속 +
      `BacktestRun.summary_json` 에 cost/regime 메타 carry
    - PASS / AVOID 신호는 `cost_adjusted_return_5d=NULL` 이지만 regime 은 그대로
      할당 (분석 breakdown 용)
    - regime_breakdown 이 BUY rows GROUP BY regime + `buy_count desc` 정렬로
      결정성 보장 (UPTREND_EARLY 2건이 DOWNTREND 1건보다 앞)
    - `BacktestResultRepository.aggregate_by_regime` 가 `{regime: count}` 반환
    - aggregate_by_regime 이 NULL regime 을 `UNCLASSIFIED_BUCKET` 으로 폴딩
    - custom CostModel 주입 시 `BacktestEngine` 가 그대로 전파
      (`cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d`
      모두 custom 값)

핵심 안전 가드:

- `CostModel.apply()` 단위 변환: `total_cost` 는 fraction (0.0033 = 0.33%) 이고
  `recommendation_results.close_return` 은 percent (1.5 = 1.5%) — `apply()` 가
  `total_cost × 100` 후 빼므로 단위가 일관된다. 단위 테스트가 명시 단언.
- BUY-only 정책 유지: `cost_adjusted_return_5d` 는 BUY 신호만 채워지고 PASS /
  AVOID 는 NULL — 분석 시 "fee 를 내지 않은 신호에 fee 를 차감하지 않는다" 보장.
  반면 `regime` 은 모든 신호에 할당되어 미래 분석 breakdown 에 활용 가능.
- regime DB 컬럼은 NULL 그대로 저장하고 display 단계에서만 `UNCLASSIFIED` 로
  매핑 — regime 데이터 후행 적재 후 재계산 가능 (`BacktestEngine.run()` 다시 돌리면
  같은 recommendation 에 다른 regime 부여).
- Phase B 의 `BUY_ONLY_METRICS_NOTE` + dry_run/commit 정책 그대로 계승. 기존 38
  Phase B 테스트가 회귀 0건으로 통과.
- `app/backtest/cost_model.py` + `regime_split.py` 어디에도 외부 HTTP / KIS / DART /
  Telegram / `BrokerInterface` import 0건 (grep 검증).

## 6.15 v0.7 Phase D — Backtest read-only API + 10번째 화면

v0.7 Phase D 는 read-only API 3종 + 프런트 10번째 화면만 추가한다. BacktestEngine
산식 / CostModel / regime_split / DB 모델 변경 0건. POST 라우터 / 자동매매 /
외부 호출 / Telegram 0건.

- `tests/integration/test_api_routes.py` 보강 — **9 신규 케이스**:
  - `_BACKTEST_FORBIDDEN_FIELDS` (16종): `source_file_path` / `body` /
    `content` / `full_text` / `raw_text` / `paragraph` / `html_body` / `본문` /
    `원문` / `전문` + 주문 계열 `broker` / `account` / `quantity` /
    `order_price` / `order_type` / `side`
  - `/api/strategies` 가 3 룰 기반 전략 (TopGradeStrategy / HighScoreStrategy /
    MultiSignalStrategy) 노출 + `version` + 비어 있지 않은 `description`
  - `/api/backtest/runs` empty (모든 필드 default) / happy 정렬 (run_date desc) +
    `cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` 응답
    최상위 노출 / strategy filter 정확성 / `limit=999` → 422 clamp
  - `/api/backtest/runs/{run_id}` happy + regime_breakdown + cost_adjusted +
    BUY-only notes / 9999 → 404 / forbidden tokens 16종 미노출 가드 (raw JSON
    substring 검사) / `_assert_no_source_file_path` recursive 가드
- `frontend/src/tests/Backtest.test.tsx` 신규 — **7 케이스**:
  - happy: 3 strategy 카드 + run row 표시
  - empty: msw default 가 빈 응답이라 `backtest-strategies-empty` /
    `backtest-runs-empty` placeholder 노출
  - error: `/api/backtest/runs` 500 → `backtest-runs-error`
  - detail 클릭: row 클릭 → detail 패널 로드 + cost_model badge + regime_breakdown
    + BUY-only note + BUY/PASS 양쪽 ActionBadge
  - detail 500: `backtest-detail-error` 노출
  - strategy filter URL 변경: 필터 클릭 → `/api/backtest/runs?strategy=...` 호출
  - 자동매매 / order UI 부재: form / submit / "실거래" / "자동매매" / "주문 실행" /
    `source_file_path` / `원문` / `본문` 모두 0건 단언
- `frontend/e2e/dashboard.spec.ts` 보강:
  - sidebar nav 테스트에 `백테스트 (β)` 메뉴 클릭 + `backtest-strategies` visible
    (Sidebar 9 → 10 메뉴)
  - 신규 `Backtest screen surfaces strategies + runs + detail (read-only)` 테스트:
    3 strategy + run row + 클릭 시 detail + regime + cost_model + raw JSON
    payload (`/api/backtest/runs` + `/api/backtest/runs/42`) 에 `source_file_path` /
    `order_type` / `quantity` 0건 단언
  - `no automation / order UI` targets 에 `/backtest` 추가 (form / submit / CTA
    label 0건 가드)

핵심 안전 가드:

- `BacktestRunSchema` / `BacktestResultSchema` / `BacktestRunDetailResponse` /
  `RegimeBreakdownSchema` / `StrategySchema` 어디에도 broker / account /
  quantity / order_price / order_type / side 필드 0건. e2e + backend 통합 양쪽
  에서 forbidden 토큰 16종 미노출 단언.
- `GET /api/strategies` 는 DB 접근 0건 — `KNOWN_STRATEGIES` 순회 + 인스턴스화
  후 `name` / `version` / docstring 첫 줄을 응답. 외부 API 호출 0건.
- `GET /api/backtest/runs` 의 limit Query 는 1~100 으로 FastAPI 자동 검증
  (limit=999 → 422). strategy filter 는 partial match 가 아니라 exact equality
  (`BacktestRunRepository.list_by_strategy`).
- BacktestPage UI 에 form / submit / 주문 실행 / 자동매매 시작 같은 CTA 라벨
  0건 — `no automation / order UI` e2e 가 `/backtest` targets 에 포함되어 가드.
- 새로 추가된 evidence_json 등 dict 응답에서도 `_assert_no_source_file_path`
  recursive 가드가 그대로 작동.

## 6.16 v0.8 Phase A — Alembic baseline migration 테스트

`tests/integration/test_alembic_migration.py` (16 케이스). v0.7-final 시점의
27 테이블을 baseline 으로 등록한 Alembic 도입을 검증한다. 모든 테스트는
`tmp_path` 의 임시 SQLite 만 사용 — 운영 / 개발 DB 0건 접근.

검증 항목:

- **`test_baseline_revision_exists_and_is_head`** — `0001_baseline_v0_7` 가
  `ScriptDirectory.get_heads()` 의 단일 head. `down_revision` 은 `None`. 후속
  Phase B/C 에서 head 가 `0002_user_audit` / `0003_watchlist` 로 바뀔 때마다
  본 단언이 명시적으로 갱신되어야 한다 (회귀 신호).
- **`test_upgrade_head_creates_all_27_tables`** — 빈 SQLite 에 
  `command.upgrade(cfg, "head")` → `inspect(engine).get_table_names()` 가
  `alembic_version` + 27 ORM 테이블 정확히 28개. 카운트 + 핵심 spot-check
  9 테이블 (stocks / recommendations / recommendation_results / analyst_reports /
  news_items / fundamental_snapshots / earnings_events / backtest_runs /
  backtest_results) 명시 단언.
- **`test_alembic_version_table_stamped_at_baseline`** — upgrade 후
  `MigrationContext.get_current_revision()` == `0001_baseline_v0_7`.
- **`test_compare_metadata_after_upgrade_is_empty`** (load-bearing) —
  `compare_metadata(ctx, Base.metadata)` 결과가 빈 list. ORM 변경이 revision
  없이 머지되면 본 테스트가 즉시 실패. `compare_type=True` /
  `compare_server_default=True` 로 type 차이도 잡는다.
- **`test_stamp_marks_existing_db_at_baseline_without_running_ddl`** —
  운영 DB stamp 시나리오: `Base.metadata.create_all()` 로 기존 27 테이블 적재
  → `command.stamp(cfg, "0001_baseline_v0_7")` → 기존 테이블 모두 보존 +
  `alembic_version` 신규 + revision = baseline. INTEGRATION_RUNBOOK §17.3 의
  실제 운영 절차를 그대로 검증.
- **`test_downgrade_base_cleanly_drops_all_baseline_tables`** — upgrade →
  downgrade base 후 27 테이블 전부 drop. `alembic_version` 만 남음 (alembic
  설계상 정상). 운영 환경에서는 사용 금지지만 dev / 검증용 round-trip 보장.
- **`test_offline_mode_emits_sql_without_connecting`** — 
  `command.upgrade(cfg, "head", sql=True)` 가 `CREATE TABLE stocks` /
  `backtest_runs` 등 SQL 을 stdout 출력 + DB 파일 생성 0건. 
  INTEGRATION_RUNBOOK §17.5 의 "운영 적용 전 SQL 미리 검토" 패턴 보장.
- **`test_spot_check_each_required_table_present`** (parametrize 9) —
  spot-check 9 테이블 각각 개별 케이스로 분리. baseline 누락 시 어떤 테이블이
  빠졌는지 focused 메시지로 즉시 파악 가능.

안전 가드:

- 모든 케이스가 `tmp_path` 의 임시 SQLite 사용 — `stock_ai_kis_check.db` /
  `stock_ai.db` / 운영 DB 접근 0건.
- 외부 API / KIS / DART / Telegram 호출 0건.
- POST 라우터 / 자동매매 / Broker / Watchlist 코드 호출 0건 — Phase A 는
  인프라 (Alembic) 만 도입.
- `app.db.models.Base.metadata` 만 import — 다른 cycle 의 ORM 모델 변경 시에도
  자동 추적 (compare_metadata 가 잡는다).

회귀 기준:

- backend pytest **682 → 698 passed (+16)** (1 deselected 그대로).
- 신규 alembic verification step (`alembic upgrade head` against ephemeral
  SQLite) 도 CI backend 잡에 추가 — 본 pytest 16 케이스 외에 별도 fast
  signal.

## 6.17 v0.8 Phase B — 단일 사용자 인증 foundation 테스트

총 **62 케이스**. v0.7-final 위에 추가된 인증 도메인 (`User` /
`LoginAuditLog` / JWT / scrypt / `POST /api/auth/login` / `/logout` / `/me` /
admin CLI) 을 다층 검증한다.

### 6.17.1 Unit — `tests/unit/test_auth_security.py` (26 케이스)

`app.auth.security` 의 순수 함수 / 클래스만 검증 — DB / FastAPI 호출 0건,
외부 호출 0건.

- **PasswordHasher (scrypt)** — hash 형식 (`scrypt$<n>$<r>$<p>$<salt>$<derived>`)
  단언 / salt 가 매번 다름 / verify 성공·실패 / 평문 hash 미포함 / malformed
  hash 입력 (5 parametrize) 은 raise 없이 False / 빈 password 거부
- **JwtIssuer (HS256)** — issue → decode round-trip / 다른 secret 으로 decode
  실패 (InvalidTokenError) / 만료 token (ExpiredTokenError) / garbage token
  (InvalidTokenError) / secret 없는 issuer 사용 시 MissingSecretError
- **hash_for_audit** — SHA256 hex (64자) / 결정적 / 다른 입력은 다른 출력 /
  None / 빈 / 공백 입력은 None 반환 (3 parametrize)
- **validate_auth_settings** — disabled 시 통과 / enabled + secret 시 통과 /
  enabled + None secret 거부 / enabled + 빈 secret 거부

### 6.17.2 Integration — `tests/integration/test_auth_repositories.py` (15 케이스)

in-memory SQLite + `Base.metadata.create_all`.

- **UserRepository** — create with defaults / get_by_username / get_by_id /
  username UNIQUE 위반 (`BaseRepository.add()` 가 즉시 flush 하므로 두 번째
  create 에서 IntegrityError) / set_last_login 이 timestamp 갱신 / deactivate /
  is_admin flag 영속
- **LoginAuditLogRepository** — LOGIN_SUCCESS / LOGIN_FAILED with unknown user
  (user_id NULL) / event_type validation (raise on `OOPS`) / **평문 IP /
  user agent 저장 0건 가드** (column 에 ≠ "203.0.113.7" + len == 64 단언) /
  list_recent newest-first / list_by_username / list_by_user

### 6.17.3 API — `tests/integration/test_auth_routes.py` (14 케이스)

FastAPI TestClient + dependency override (`get_session` + `get_settings`) +
in-memory SQLite. 두 운영 모드 모두 커버.

**AUTH_ENABLED=false (dev / CI)**:
- /login 성공 → access_token 반환 + LOGIN_SUCCESS audit + body 에 `password` /
  `scrypt$` 0건
- /login 실패 (wrong password vs unknown user) → 동일 generic 401 메시지 /
  LOGIN_FAILED audit 2건
- /login 실패 (deactivated user) → 401 / LOGIN_FAILED
- /me → `auth_enabled=false`, `via=auth_disabled_fallback`, `user=null`
- /logout → 200 / LOGOUT audit (username=None)

**AUTH_ENABLED=true + JWT_SECRET**:
- /me 토큰 없음 / Basic scheme / garbage Bearer 모두 401 + `WWW-Authenticate: Bearer`
- /me 유효 토큰 → `auth_enabled=true`, `via=token`, user 정보
- /me 유효 토큰이지만 user deactivate 후 → 401
- LOGIN_SUCCESS audit 에 username + user_id 기록
- unknown user 의 LOGIN_FAILED 에는 user_id NULL + username 보존
- /login 시 `User-Agent` + `X-Forwarded-For` 헤더 → audit row 의
  `source_ip_hash` / `user_agent_hash` 가 SHA256 hex (`re.fullmatch(r"[0-9a-f]{64}")`),
  평문 ("203.0.113.7" / "Mozilla/...") 미저장
- /logout (with token) → audit row 의 username 보존
- 모든 응답 (login + me) 에 `password_hash` / `scrypt$` 0건
- `AUTH_ENABLED=true` 모드에서도 `/health` 등 기존 read-only GET 라우터는
  그대로 OPEN — Watchlist (Phase C) 가 첫 보호 라우터 후보임을 단언

### 6.17.4 CLI — `tests/integration/test_create_admin_cli.py` (5 케이스)

`scripts.create_admin.main()` 직접 호출 + `monkeypatch` 로 env var 주입 +
`tmp_path` 의 SQLite. `Base.metadata.create_all()` 로 임시 DB 부트스트랩.

- 정상 생성 → user 행이 scrypt 해시 + admin / active / verify 가능 / stdout
  에 password / hash 0건
- 중복 username + `--update-if-exists` 없음 → exit 1 + stderr "already exists" +
  hash / password 0건
- 중복 username + `--update-if-exists` → password 갱신 (이전 password 더 이상
  검증 안 됨, 새 password 검증 OK)
- `--no-admin` flag → is_admin=False
- ADMIN_PASSWORD="" → exit 1 + stderr "password must not be empty"

### 6.17.5 Alembic head 갱신 — `tests/integration/test_alembic_migration.py`

Phase B 가 새 head 를 layering 했으므로 Phase A 의 single-head 단언이 갱신되었다:

- `BASELINE_REVISION = "0001_baseline_v0_7"` 그대로 (down_revision=None 단언)
- 신규 `HEAD_REVISION = "0002_auth_foundation"` 단언
- `EXPECTED_TABLE_COUNT = 29` (27 → 29)
- spot-check parametrize 에 `users` + `login_audit_logs` 2건 추가
- `compare_metadata` diff 0건 단언 그대로 (load-bearing 가드)

회귀 기준:

- backend pytest **698 → 760 passed (+62)** (1 deselected 그대로).
- 신규 alembic head = `0002_auth_foundation` — CI 의 `alembic upgrade head`
  step 이 자동 검증.
- frontend / build / e2e 변경 0건 (Phase B 는 백엔드 + CLI 만; 프런트 로그인
  화면은 Phase D 후보).

## 6.18 v0.8 Phase C — Watchlist DB/API 테스트

총 **48 케이스 (+ alembic spot-check 2 추가)**. v0.8 Phase B 위에 도입된 Watchlist
도메인 (`Watchlist` 30번째 + `WatchlistItem` 31번째 + GET/POST/DELETE 5 라우터 +
require_auth 가드 + symbol normalize + cross-user isolation) 을 다층 검증.

### 6.18.1 Repository — `tests/integration/test_watchlist_repositories.py` (27 케이스)

in-memory SQLite + `PRAGMA foreign_keys=ON` + `Base.metadata.create_all`.

- **normalize_symbol** (4 parametrize + 2 edge): trim + UPPER, 빈 / None 거부
- **WatchlistRepository** (10): create / list_by_user (default 우선 정렬) /
  get_default_for_user / get_or_create_default 멱등 / Unique(user_id, name)
  IntegrityError / set_default 가 이전 default demote / create with
  is_default 도 demote / **다른 user 의 watchlist 격리** (get_by_user_and_id 가
  None) / list_by_user 격리 / cascade delete 가 items 모두 제거
- **WatchlistItemRepository** (12): symbol normalize 적용 / Unique(watchlist_id,
  symbol) (normalize 후 collide) / 다른 watchlist 에 같은 symbol OK / memo 길이
  500 (limit / over) / remove_item True/False / remove_item 도 normalize /
  list_items id 정렬 / list_symbols 알파벳 정렬 / update_memo / **broker /
  account / quantity / order_* / 가격 컬럼 0건 단언** (회귀 가드)

### 6.18.2 API — `tests/integration/test_watchlist_routes.py` (19 케이스)

FastAPI TestClient + dependency override + in-memory SQLite +
`PRAGMA foreign_keys=ON`. 두 운영 모드 + cross-user + spoofing 모두 커버.

**AUTH_ENABLED=false (dev / CI)** (12):

- 빈 목록 / create + list / 중복 name 409 / 빈 name 422 /
  is_default=true 두 번 → 단일 default invariant / 상세 + items / 404 missing /
  POST item with normalize ("aapl" → "AAPL") / 중복 symbol 409 / unknown symbol
  404 / memo 500자 초과 422 / DELETE item 성공 / DELETE path symbol normalize /
  DELETE missing 404

**AUTH_ENABLED=true** (4):

- list 토큰 없음 / 무효 토큰 → 401 + `WWW-Authenticate: Bearer`
- 유효 토큰 → 200
- **cross-user 404**: bob 의 watchlist 에 alice 토큰으로 접근 시도 (GET / POST
  item / DELETE item) 모두 404 — 403 아님, ownership 노출 0건
- **request body user_id 무시**: `{"name":"spoof", "user_id": <bob_id>}` 페이로드
  를 alice 토큰으로 보내도 alice 가 owner

**보안 가드** (3):

- `test_response_never_leaks_password_hash_or_token` — 모든 응답 (list / create
  / detail / item create) 을 recursive 로 스캔, forbidden 토큰 (broker / account
  / quantity / order_* / source_file_path / password_hash / token / secret /
  jwt_secret) 0건 + scrypt$ string 0건
- `test_request_body_user_id_is_ignored` (spoofing 가드)

### 6.18.3 Alembic head 갱신 — `tests/integration/test_alembic_migration.py`

Phase C 가 새 head 를 layering 했으므로:

- `HEAD_REVISION = "0003_watchlist"` (0002 → 0003)
- `EXPECTED_TABLE_COUNT = 31` (29 → 31)
- spot-check parametrize 에 `watchlists` + `watchlist_items` 2건 추가 (11 → 13)
- `compare_metadata` diff 0건 단언 그대로 (load-bearing 가드)

### 6.18.4 회귀 기준

- backend pytest **760 → 808 passed (+48)** (1 deselected 그대로)
- 신규 alembic head = `0003_watchlist` — CI 의 `alembic upgrade head` step 자동 검증
- frontend / build / e2e 변경 0건 (Phase C 는 백엔드만; 프런트 Watchlist 화면 / Login
  화면 / StockDetail 별 토글은 Phase D 후보)

## 6.19 v0.9 Phase A — Security Hardening 테스트

총 **37 케이스 신규** (unit 26 + integration 11). slowapi rate limit / SecurityHeadersMiddleware /
BruteForceGuard / auth_routes 강화를 다층 검증.

### 6.19.1 Unit — `tests/unit/test_security_headers.py` (8 케이스)

FastAPI TestClient + `app/main.app` 공유 객체. autouse conftest fixture 로 rate limit /
brute force 비활성화 상태에서 실행.

- `/health` 응답에 4개 헤더 각각 존재: `X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: no-referrer` / `Permissions-Policy`
- 단일 요청에서 4개 헤더 동시 존재
- `app.state.security_headers_enabled = False` 시 4개 헤더 모두 부재
- `False → True` 재활성화 시 헤더 복원
- `Content-Security-Policy` 헤더 **미존재** 단언 (Phase D+ 예정)
- GET `/api/auth/me` 엔드포인트에도 보안 헤더 존재 (DB 접근 0건 fallback 경로 사용)

### 6.19.2 Unit — `tests/unit/test_brute_force.py` (12 케이스)

순수 인메모리 단위 테스트 — DB / FastAPI / 네트워크 호출 0건.

- `check_allowed` 실패 없을 때 / max_failures 미만일 때 pass
- `max_failures` 도달 시 `BruteForceLockedError` raise
- `is_locked` True/False
- `record_success` 가 실패 카운터 초기화 (2회 실패 후 성공 → 2회 추가 실패도 잠금 미발생)
- 다른 IP 같은 user / 같은 IP 다른 user 가 독립적으로 카운트 (composite key 격리)
- `reset()` 으로 모든 잠금 해제
- `None` IP 허용 (None 도 복합 키 구성 요소로 허용)

### 6.19.3 Unit — `tests/unit/test_rate_limit.py` (6 케이스)

- `limiter` 가 `slowapi.Limiter` 인스턴스
- `rate_limit_enabled=False` 시 `_limiter_key` 가 `__exempt_` 접두어 UUID 반환
- `rate_limit_enabled=False` 시 10회 호출에서 서로 다른 고유 키 반환 (카운터 공유 방지)
- `rate_limit_enabled=True` 시 `_limiter_key` 가 클라이언트 IP 반환
- Settings 기본값 단언: `rate_limit_enabled=True`, `rate_limit_auth="5/minute"`, `rate_limit_default="100/minute"`
- HTTP 레벨 트리거: 5회 로그인 후 6번째 요청이 429 (실제 default `5/minute` 기준)

### 6.19.4 Integration — `tests/integration/test_auth_security.py` (11 케이스)

in-memory SQLite + StaticPool + TestClient + `app.dependency_overrides`. autouse conftest
fixture 로 기본 비활성화, 개별 테스트가 상태 직접 제어.

- 보안 헤더 — `/health` 4개 / `/api/auth/login` 에도 `X-Content-Type-Options` 존재
- brute force 잠금 — 3회 실패 후 4번째 요청이 generic 401 (`"invalid username or password"`)
- 잠금 응답 == 틀린 비밀번호 응답 (status_code + body.detail 동일 — user-existence leak 방지)
- 성공 로그인 시 실패 카운터 초기화 (2회 실패 → 올바른 로그인 → 2회 추가 실패 후 잠금 미발생)
- `LOCKOUT_REJECTED` 이벤트가 감사 로그에 기록
- `source_ip` → 64자 SHA256 hex 저장 (`203.0.113.42` 원문 미저장)
- `user_agent` → 64자 SHA256 hex 저장 (원문 미저장)
- 로그인 성공 응답에 `password` / `scrypt$` / `password_hash` / `jwt_secret` 포함 0건
- 변경(POST/PUT/DELETE) 엔드포인트 수 == 5 고정 (Phase A 신규 라우터 0건 단언)
- 라우트 경로에 `order|broker|auto_trade|full_auto|approval|small_auto` 패턴 0건

### 6.19.5 회귀 기준

- backend pytest **808 → 845 passed (+37)** — 회귀 0건
- frontend / build / e2e 변경 0건 (Phase A 는 백엔드 미들웨어 전용)
- autouse conftest 로 기존 808 테스트 모두 rate limit / brute force 영향 없이 통과

## 6.20 v0.9 Phase B — Structured Logging & Monitoring 테스트

총 **28 케이스 신규** (backend unit 24 + frontend vitest 4). RequestIDMiddleware /
구조화 로깅 / optional Sentry / frontend ErrorBoundary를 다층 검증.

### 6.20.1 Unit — `tests/unit/test_logging_config.py` (12 케이스)

순수 단위 — DB / 네트워크 / FastAPI 호출 0건. root logger 상태를 autouse fixture로 격리.

- `SensitiveFilter` 가 `password` / `password_hash` / `jwt_secret` / `access_token` extra 필드 `***` 치환
- `SensitiveFilter` 가 `username` / `user_id` 같은 안전한 필드 유지
- `SensitiveFilter` 가 표준 LogRecord 속성(`name`, `lineno` 등) 수정 않음
- `RequestIDFilter` 가 request 컨텍스트 밖에서 `record.request_id = "-"` fallback
- `configure_logging` 이 `SensitiveFilter` 를 최소 1개 핸들러에 설치
- `configure_logging` 이 `log_request_id_enabled=True` (기본) 시 `RequestIDFilter` 설치
- `configure_logging` 이 `log_request_id_enabled=False` 시 `RequestIDFilter` 미설치
- `configure_logging` 이 idempotent (중복 핸들러 누적 없음)
- `configure_logging` + `structured_logging_enabled=True` → `JsonFormatter` 계열 포매터 설치

### 6.20.2 Unit — `tests/unit/test_request_id.py` (5 케이스)

FastAPI TestClient + `/health` / `/api/auth/me` 엔드포인트 사용.

- `X-Request-ID` 헤더 없음 → UUID4 형식 생성 후 응답 헤더 포함
- `X-Request-ID` 헤더 있음 → 동일 값 응답 헤더에 보존
- 연속 5회 요청 → 모두 서로 다른 id (고유성)
- `/api/auth/me` 에도 `X-Request-ID` 존재
- rate limit 429 응답에도 `X-Request-ID` 포함 (RequestIDMiddleware가 SlowAPI보다 외부에서 wrapping)

### 6.20.3 Unit — `tests/unit/test_sentry.py` (7 케이스)

순수 단위 — 실제 Sentry 서버 호출 0건 (patch 사용).

- `sentry_enabled=False` → `init_sentry` 가 `False` 반환
- `sentry_enabled=True` + `sentry_dsn=None` → WARNING 로그 + `False` 반환
- `sentry_enabled=True` + dummy DSN → `sentry_sdk.init` 1회 호출 / `send_default_pii=False` 확인
- `_before_send` — `event["extra"]["password"]` 마스킹
- `_before_send` — `event["request"]["data"]["password_hash"]` / `access_token` 마스킹, 안전 필드 유지
- `_before_send` — `Authorization` 헤더 마스킹, `Content-Type` 유지
- `_before_send` — 민감 키 없는 이벤트 통과 (무손실)

### 6.20.4 Frontend — `src/tests/ErrorBoundary.test.tsx` (4 케이스)

jsdom + React Testing Library. console.error mock으로 테스트 출력 억제.

- 자식 정상 렌더 → fallback UI 없음
- 자식 throw → `role="alert"` fallback UI + 다시 시도 버튼 노출
- `fallback` prop 제공 시 커스텀 fallback 렌더 (기본 UI 미노출)
- 다시 시도 버튼 클릭 → 오류 상태 초기화 → non-throwing 자식 복구 렌더

### 6.20.5 회귀 기준

- backend pytest **845 → 869 passed (+24)** — 회귀 0건
- frontend vitest **113 → 117 passed (+4)** — 회귀 0건
- frontend build 그린
- 기존 808 테스트 모두 configure_logging 변경(handlers.clear) 영향 없이 통과
  (autouse conftest fixture가 root logger 상태를 각 test_logging_config.py 테스트에서 격리)

## 6.21 v0.9 Phase C — Watchlist 고도화 + UserPreference + Provider 회복성 테스트

총 **47 케이스 신규** (integration 37 + unit 10). 새 PATCH/DELETE watchlist 엔드포인트 /
UserPreference CRUD / CircuitBreaker 흐름을 다층 검증. 프론트엔드 변경 없음.

### 6.21.1 Integration — `tests/integration/test_watchlist_phase_c.py` (20 케이스)

TestClient + StaticPool SQLite. AUTH_ENABLED=false dev fallback 사용.

- `PATCH /api/watchlists/{id}` rename 성공 → 200 + 새 name
- `PATCH /api/watchlists/{id}` set_default → 200 + 이전 default 자동 해제
- `PATCH /api/watchlists/{id}` 필드 미제공 → 422
- `PATCH /api/watchlists/{id}` 타인 watchlist → 404 (ownership 비노출)
- `DELETE /api/watchlists/{id}` → 200 + DB 행 삭제 확인
- default watchlist DELETE 허용
- DELETE cascade → WatchlistItem 행 함께 삭제
- `GET /api/watchlists/{id}/items` → total / items 반환
- limit/offset pagination 동작
- symbol_prefix 필터 동작
- `PATCH /api/watchlists/{id}/items/{symbol}` memo 업데이트
- memo null 초기화
- 미존재 symbol → 404
- 응답에 forbidden field (password / broker / account 등) 0건

### 6.21.2 Integration — `tests/integration/test_user_preferences.py` (17 케이스)

Repository 단위 + API 통합 혼합. StaticPool SQLite.

- `get_or_create_for_user` — 최초 blank row 생성
- `get_or_create_for_user` — 2회 호출 시 동일 row id
- `update` partial fields
- `set_default_watchlist` / clear to None
- `update_dashboard_layout`, `update_notification_preferences`
- `GET /api/users/me/preferences` → 200 (dev fallback)
- `PUT /api/users/me/preferences` → 필드 업데이트
- null 전송 시 필드 초기화
- watchlist 소유권 검증 (존재하는 것 / 없는 것)
- AUTH_ENABLED=true → 토큰 없으면 401 (GET / PUT 각 1건)
- 응답에 forbidden field 0건
- notification_preferences_json에 secret 키 포함 → 422

### 6.21.3 Unit — `tests/unit/test_provider_resilience.py` (19 케이스)

순수 단위 — 실제 외부 API 호출 0건 (fn은 항상 로컬 callable).

- `ProviderCallResult.ok` / `.fail` factory
- `retry_with_backoff` 1회 성공 / 3회 째 성공 / 최대 시도 소진
- `CLIENT_ERROR` 비재시도 (결정적)
- `TIMEOUT` / `RATE_LIMIT` 재시도
- `CircuitBreaker` CLOSED 시작 / 정상 통과
- threshold 초과 → OPEN
- OPEN fast-fail (fn 미호출 확인)
- OPEN → HALF_OPEN (timeout 경과, monkeypatch)
- HALF_OPEN probe 성공 → CLOSED
- HALF_OPEN probe 실패 → OPEN
- `reset()` CLOSED 강제 전환

### 6.21.4 회귀 기준

- backend pytest **869 → 916 passed (+47)** — 회귀 0건
- frontend vitest **117 passed** — 변경 없음
- frontend build 그린
- alembic upgrade head + compare_metadata diff 0건 (0004_user_preferences 통과)

## 6.22 v0.9 Phase D — Frontend 관리 UI + UserPreference 테스트

총 **36 케이스 신규** (vitest). 백엔드 변경 0건. Watchlist 관리 UI /
UserPreference 설정 / TodayReport + StockDetail preference 연동을 다층 검증.

### 6.22.1 `tests/WatchlistManage.test.tsx` (21 케이스)

MSW v2 + TanStack Query + renderWithProviders. 새 watchlist 관리 기능을 컴포넌트
단위로 검증.

**WatchlistListItem — rename (3)**
- 인라인 rename → PATCH 호출 → 이름 업데이트 성공
- 409 충돌 → "같은 이름이 이미 있습니다" 오류 표시
- cancel (X 버튼) → 원래 이름 복원

**WatchlistListItem — set default (2)**
- set-default 버튼 클릭 → PATCH 호출 → 기본 목록 변경
- 이미 기본 목록인 경우 set-default 버튼 미노출

**WatchlistListItem — delete (3)**
- 비기본 목록 삭제 → DELETE 호출 → 목록에서 제거
- 기본 목록도 삭제 허용
- 404 응답 → "목록을 찾을 수 없습니다" 오류 표시

**WatchlistItemRow — memo edit (3)**
- Pencil 버튼 → 인라인 form → memo 업데이트 성공
- 422 서버 오류 → 오류 메시지 표시
- cancel → 원래 memo 복원

**WatchlistDetailPanel — item filter (2)**
- symbol prefix 입력 → 일치 항목만 표시
- 일치 항목 없음 → empty placeholder 표시

**WatchlistPage — forbidden fields (8)**
- broker / account / quantity / password / token / order / 주문 / 매수 / 매도 / 자동매매
  0건 단언 (innerHTML 스캔)

### 6.22.2 `tests/UserPreferences.test.tsx` (15 케이스)

MSW v2 + TanStack Query + renderWithProviders + renderStockDetail() 헬퍼.

**SettingsPage — UserPreference section (8)**
- GET /api/users/me/preferences → 폼 렌더링 (default_watchlist_id / default_market /
  default_strategy 셀렉트 + notification 체크박스)
- 500 오류 → `pref-load-error` 노출
- watchlist_id 변경 → PUT 호출 → `pref-save-success` 노출
- market 변경 → 업데이트 성공
- strategy 변경 → 업데이트 성공
- notification toggle → `notification_preferences_json: {enabled: true}` 전송
- 401 저장 실패 → `pref-save-error` 노출
- user-preference-form innerHTML 에 forbidden 필드 0건 (broker / account / quantity /
  password / token / 자동매매 / 주문)

**TodayReport — WatchlistCard with preference (3)**
- preference.default_watchlist_id 가 설정된 경우 해당 watchlist 아이템 표시
- preference 미설정 시 watchlist is_default fallback 동작
- preference API 500 오류 시 fallback 유지 (폼 자체 오류 아님)

**StockDetailPage — FavoriteButton with preference (4)**
- preference default watchlist 에 포함된 종목 → `data-active="true"`
- 미포함 종목 → `data-active="false"`
- 409 응답 → 오류 없이 idempotent 처리 (에러 미노출)
- 500 응답 → 오류 표시

### 6.22.3 회귀 기준

- backend pytest **916 passed** — Phase D 는 프런트 전용, 백엔드 변경 0건
- frontend vitest **117 → 146 passed (+29)** — 19 파일
- frontend build 그린 (`tsc --noEmit && vite build`)
- Playwright e2e **19 passed** — 변경 없음
- `v0.9-frontend` 태그 생성 후 push

핵심 안전 가드:
- `user-preference-form` innerHTML 에 broker / account / quantity / password /
  token / 자동매매 / 주문 0건 (컴포넌트 레벨 whitelist 가드)
- FavoriteButton 409 → idempotent — 이미 목록에 있음 = silent success, 에러 0건
- notification 설정은 UI 저장 전용 (`notification_preferences_json.enabled`) — 실
  Telegram 발송 0건 (e2e + unit 모두 외부 호출 0건 확인)
- `useUserPreferences` 는 `retry: false` 상속 (test QueryClient 의 `retry: false`
  와 충돌 없음) — per-query retry override 없음

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
