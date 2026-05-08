# TASKS.md

이 파일은 Codex가 v0.1 개발 작업을 작게 나누어 진행하기 위한 태스크 목록이다.
체크박스 상태는 실제 코드/테스트 상태에 맞춰 동기화한다 (현재 스냅샷: **296 passed,
v0.1 백엔드 마감**).

## Phase 0 - 프로젝트 준비

- [x] `AGENTS.md` 읽기
- [x] 프로젝트 브리프/상세 명세/에이전트 명세 읽기
- [x] v0.1 범위 확인
- [x] v0.1 제외 범위 확인
- [x] 초기 Git 커밋 생성

## Phase 1 - 아키텍처/골격

- [x] FastAPI 프로젝트 기본 구조 생성
- [x] config 모듈 생성
- [x] logging 설정 생성
- [x] DataProviderInterface 생성
- [x] AIProviderInterface 생성
- [x] BrokerInterface placeholder 생성
- [x] StrategyInterface placeholder 생성
- [x] 기본 README 갱신

## Phase 2 - DB/Repository

- [x] SQLAlchemy 설정
- [x] DB 세션 관리
- [x] stocks 모델
- [x] holdings 모델
- [x] daily_prices 모델
- [x] stock_indicators 모델
- [x] market_cap_rankings 모델
- [x] stock_universes 모델
- [x] news_items 모델
- [x] market_regimes 모델
- [x] recommendation_runs 모델
- [x] recommendations 모델
- [x] recommendation_results 모델
- [x] holding_checks 모델
- [x] data_snapshots 모델
- [x] decision_logs 모델
- [x] job_runs 모델
- [x] notification_logs 모델
- [x] Repository 기본 구현 (16개 클래스)
- [x] DB 테스트 작성

## Phase 3 - KIS/Data

- [x] KisClient 생성
- [x] 인증 토큰 처리 placeholder
- [x] 현재가 조회 메서드
- [x] 일봉 조회 메서드
- [x] 시가총액 상위 조회 메서드
- [x] API 응답 정규화 DTO
- [x] DataQualityChecker
- [x] daily_prices 수집/저장 서비스 (`DailyPriceCollector`)
- [x] market_cap_rankings 수집/저장 서비스 (`MarketCapRankingCollector`)
- [x] Mock API 테스트 (`FakeKisDataProvider`, `httpx.MockTransport`)

## Phase 4 - Analysis/Scoring

- [x] MA 계산 (5/20/60/120)
- [x] RSI 계산 (14)
- [x] MACD 계산
- [x] volume_ratio_20d 계산
- [x] breakout_20d 계산
- [x] breakout_60d 계산
- [x] ma_alignment 계산
- [x] technical_score 계산
- [x] 신규 추천 점수 계산 (`ScoringEngine.score_recommendation`)
- [x] 보유 종목 점수 계산 (`ScoringEngine.score_holding`)
- [x] DummyScoreProducer (News/Supply/Fundamental/Earnings/AI placeholder, 룰베이스 ±5 nudge)
- [x] RiskEngine (`evaluate_recommendation` / `evaluate_holding`)
- [x] 지표/점수 테스트 (technical_analyzer 32, scoring_engine 16, risk_engine 25, score_producers 3)

## Phase 5 - Recommendation/Holding

- [x] RecommendationEngine 생성
- [x] 시총 TOP 500 기반 후보 필터링
- [x] 추천 TOP 5 생성
- [x] recommendation_runs 저장
- [x] recommendations 저장
- [x] data_snapshots 연결
- [x] decision_logs 저장
- [x] HoldingCheckEngine 생성
- [x] 보유 종목 수익률 계산
- [x] 장전/장후 점검 생성 (PRE_MARKET / POST_MARKET)
- [x] 위험 경고 조건 생성 (RiskEngine 연동, alert flag 저장)
- [x] RecommendationResultService (1/3/5/20일 성과 upsert)
- [x] 서비스 테스트 (recommendation_engine 13, holding_check_engine 17, recommendation_result_service 13)

## Phase 6 - Notification/Report

- [x] ReportGenerator 생성
- [x] 추천 리포트 포맷
- [x] 장전 점검 리포트 포맷
- [x] 장후 점검 리포트 포맷
- [x] 위험 경고 포맷
- [x] TelegramNotifier 생성 (DRY_RUN / DISABLED 분기)
- [x] NotificationService 생성 (notification_logs 자동 기록)
- [x] Dispatcher 글루 (Recommendation / HoldingCheck / HoldingRiskAlert)
- [x] notification_logs 저장
- [x] 메시지 포맷 테스트 (report_generator 12, telegram_notifier 14, notification_service 6, dispatchers 16)

## Phase 7 - Backend API

- [x] `/api/reports/today`
- [x] `/api/recommendations/latest`
- [x] `/api/recommendations/history` (success_rate / avg_close_return_{1,3,5,20}d 집계 포함)
- [x] `/api/holdings`
- [x] `/api/holdings/checks/latest`
- [x] `/api/holdings/{symbol}/checks` (items[] + summary metric: total/alert/high_risk count, latest/previous/change, best/worst return rate, latest decision/risk_level)
- [x] `/api/stocks/{symbol}` (recent_recommendations[*].results[] 1/3/5/20일 성과 join 포함)
- [x] `/api/universe/market-cap-top`
- [x] `/api/market-regime/latest`
- [x] `/api/news`
- [x] `/api/jobs` + `/api/jobs/{job_id}` (스케줄러 진단용)
- [x] API schema 작성 (Pydantic v1, Decimal → str 일관 직렬화)
- [x] API 테스트 (40 cases)

## Phase 8 - Scheduler

- [x] APScheduler 설정 (`BackgroundScheduler`, `SCHEDULER_ENABLED` 제어)
- [x] `run_job` 2-session 래퍼 (job_runs 항상 commit, work_session은 실패 시 rollback)
- [x] 18:00 장마감 데이터 수집 job (`collect_market_close_data`)
- [x] 18:30 지표 계산 job (`calculate_technical_indicators`)
- [x] 06:00 추천 리포트 job (`send_recommendation_report` — NO_DATA / DRY_RUN / dispatcher 연동)
- [x] 08:30 장전 점검 job (`run_pre_market_holding_check` — NO_DATA / dispatcher + alert 연동)
- [x] 16:30 장후 점검 job (`run_post_market_holding_check`)
- [x] 17:00 추천 성과 업데이트 job (`update_recommendation_results` — data_status SUCCESS/PARTIAL/NO_DATA)
- [x] job_runs 저장 (status / result_summary / error_message / finished_at)
- [x] 실패/재시도 처리 (run_job 래퍼가 예외 캐치 후 FAILED 기록 + work_session 롤백)
- [x] 잡 통합 테스트 (34 cases)

## Phase 9 - 테스트/문서 / 통합 시나리오

- [x] pytest 전체 실행 (296 passed)
- [x] 구조 경계 리뷰 (PROJECT_STATUS.md §6 금지사항 정리)
- [x] API 키 노출 여부 점검 (.env 미커밋, .env.example만, telegram chat_id 마스킹)
- [x] v0.1 범위 위반 점검 (자동매매/실주문/POST 라우터 없음)
- [x] README 갱신 (mock seed + runbook 진입점 추가)
- [x] TESTING.md 갱신 (잡 / dispatcher / NO_DATA·PARTIAL 케이스 반영)
- [x] SECURITY.md 갱신
- [x] PROJECT_STATUS.md 동기화
- [x] TASKS.md 동기화
- [x] Mock seed 스크립트 (`scripts/seed_mock_data.py`, 멱등 + `--reset`)
- [x] 통합 실행 시나리오 문서 (`INTEGRATION_RUNBOOK.md`: 사전준비 → 시드 → 6개 잡 수동 트리거 → 13개 GET API → 로그 검증 → 회귀 게이트)

## 남은 v0.1 작업

v0.1 백엔드 코드는 마감 상태 (tag `v0.1-backend-accepted`). 코드 변경이
필요한 v0.1 항목은 없다. 운영 단계 1건만 남아있다.

- [ ] (운영) 실 KIS 키 + 실 텔레그램으로 1회 운영 검증 —
  [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 항목별 통과 후
  결과를 PROJECT_STATUS.md §2에 기록. 코드 변경 없음.

## Backlog (v0.4 이후)

v0.1–v0.3 범위 외. v0.3 진입 시점에 일부 항목 (캔들 패턴 / ATR / 휴장일 캘린더 /
StockDetail 일봉 차트) 은 v0.3 phase 로 승격되었다.

**완료된 사이클**

- [x] **v0.2 PC 대시보드 프론트엔드** — `v0.2-frontend-final` 마감 ✅ (Vite + React, 8 화면)
- [→ v0.3 Phase B] 캔들 패턴 + ATR 변동성 컴포넌트 ✅ (`v0.3-backend-analysis`)
- [→ v0.3 Phase C] 한국거래소 휴장일 캘린더 ✅ (`v0.3-frontend-calendar`)
- [→ v0.3 Phase D] StockDetail 일봉 차트 ✅ (`v0.3-frontend-stock-chart`)

**v0.4 후보 (백엔드 / 데이터)**

- [ ] 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 `DummyScoreProducer` placeholder)
- [ ] Strategy 모듈 (장기/중기/단기 관리, SIGNAL / PAPER 모드)
- [ ] Backtest 엔진 (walk-forward 검증, 그리드 서치 튜닝)
- [ ] MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- [ ] 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- [ ] APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래 — `BrokerInterface` 구현체 도입, 인증 동반 필수)
- [ ] POST 트리거 (잡 수동 실행 / 추천 즉시 생성) — 인증 동반 필수
- [ ] WebSocket / SSE 실시간 잡 상태 (현재 polling)
- [ ] KRX 휴장일 자동 fetch (한국거래소 공지 / 공공 API)

**v0.4 후보 (프런트엔드 / UX)**

- [ ] StockDetail 캔들 차트 + 거래량 BarChart + 이동평균 오버레이 (`lightweight-charts` 마이그레이션 검토)
- [ ] StockDetail 의 ATR / 캔들 / 변동성 점수 영향 가시화 (IndicatorCard 확장)
- [ ] StockDetail 차트 days deep-link (`/stocks/005930?days=60`)
- [ ] 종목 시계열의 LRU 캐시 (마지막 N 종목)
- [ ] 즐겨찾기 / 관심 종목 (POST 라우터 도입 필요)
- [ ] 글로벌 검색 단축키 (cmd+k)
- [ ] sidebar collapse / breadcrumb / loading skeleton 통일
- [ ] 모바일 / 태블릿 레이아웃

**v0.4 후보 (보안 / 운영)**

- [ ] 인증 / 권한 (단일 사용자 / 사내망 외 노출 시)
- [ ] 운영 모니터링 (Sentry / Prometheus / Grafana)
- [ ] KIS 키 회전 자동화 / Vault 통합
- [ ] `.github/dependabot.yml` (v0.3 Phase A 에서 보류)

## v0.3 — 분석 보강 + 운영 정착

기준선: `v0.2-frontend-final`. 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0003` 참조.

**v0.3 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI (수동 잡 실행 / 추천 즉시 생성 / 보유 추가·삭제 폼)
- ❌ 실 News / Supply / Fundamental / Earnings 외부 파이프라인 (placeholder 유지, 캔들/ATR 만 추가)
- ❌ 즐겨찾기 / 관심 종목 (POST 필요)
- ❌ 인증 / 권한
- ❌ Sentry / Prometheus / 운영 모니터링
- ❌ Strategy / Backtest / MockBroker / SimulationBroker
- ❌ 모바일 / 태블릿 레이아웃

### Phase A — GitHub Actions CI

- [ ] `.github/workflows/ci.yml` 작성 (backend pytest + frontend vitest+build + e2e)
- [ ] backend job: python 3.12 + `pip install -e ".[dev]"` + `pytest -q`
- [ ] frontend job: node 20 + `npm ci` + `npm run lint && test && build`
- [ ] e2e job: `playwright install chromium` + `npm run e2e` + `playwright-report/` artifact
- [ ] PR 1건 의도적 실패 → CI 빨강 확인 1회
- [ ] (선택) `.github/dependabot.yml` 추가
- 완료 기준: main / PR 양쪽 모두 3 체크 그린, 회귀 0건. 태그 `v0.3-phase-a-ci`.

### Phase B — 캔들 패턴 + ATR 변동성 컴포넌트 ✅ 인수

- [x] `app/analysis/technical_analyzer.py` — `compute_atr14` (Wilder), 캔들 5종 detector (`detect_doji` / `detect_hammer` / `detect_shooting_star` / `detect_bullish_engulfing` / `detect_bearish_engulfing` + 통합 `detect_candle_patterns`), `classify_volatility` (LOW/NORMAL/HIGH/EXTREME)
- [x] `IndicatorSnapshot` 에 `atr14`, `candle_patterns`, `volatility_band` (default None)
- [x] `calculate_technical_score` 에 `candle_patterns` / `volatility_band` 보조 가산/감산 (캔들 ±5 cap, 변동성 -5~+2) + 0~100 clamp 명시
- [x] `app/db/models.py` `StockIndicator` 컬럼 추가: `atr14 Numeric(20,4)`, `candle_patterns JSON`, `volatility_band String(16)` — 모두 nullable, ALTER ADD only
- [x] `app/data/repositories/stock_indicators.py` `upsert` 시그니처에 신규 키워드 3개 (default None)
- [x] `app/analysis/indicator_service.py` 가 snapshot 의 신규 필드를 upsert
- [x] `app/api/schemas.py` `StockIndicatorSchema` 에 3개 optional 필드 추가
- [x] `tests/unit/test_technical_analyzer.py` 신규 16건 (ATR / 5 캔들 / 변동성 분류 / 신규 score 경로)
- [x] `tests/integration/test_indicator_service.py` 신규 2건 (Phase B 필드 persist 검증)
- [x] backend `pytest -q` **296 → 314 passed**, 회귀 0건
- [x] frontend `npm run test` 36 / `npm run e2e` 6 / `npm run build` 통과 — `vite.config.ts` 의 vitest include/exclude 보정 (e2e/** 제외)
- 완료 기준: 신규 필드가 응답에 흘러가고 점수 산식이 캔들/ATR 보강을 반영하면서 회귀 0건. 태그 `v0.3-backend-analysis`.

### Phase C — 한국거래소 휴장일 캘린더 ✅ 인수

- [x] `frontend/src/data/krxHolidays.ts` 정적 JSON (2025~2027) — 출처 / 갱신 절차 주석
- [x] `frontend/src/lib/marketCalendar.ts` — `isMarketClosed` / `nextOpenDay` / `previousOpenDay` / `classifyMarketStatus` / `todayInSeoul`
- [x] `frontend/src/components/common/MarketStatusBanner.tsx`
- [x] Today / Jobs / Holdings 헤더에 Banner 통합
- [x] `frontend/src/tests/marketCalendar.test.tsx` (신규, 15 케이스)
- [x] `frontend/src/tests/MarketStatusBanner.test.tsx` (신규, 4 케이스)
- [x] e2e: Banner 노출 검증 1건 추가 (6 → 7)
- 완료 기준: 휴장/평일/주말 분기 정확. vitest 36 → 55, e2e 6 → 7. 태그 `v0.3-frontend-calendar`.

### Phase D — StockDetail 일봉 차트 ✅ 인수

- [x] `app/api/routes.py` — `GET /api/stocks/{symbol}/prices?days=120` (max 500) 신규
- [x] `app/api/schemas.py` — `StockPriceSeriesResponse` 추가
- [x] `tests/integration/test_api_routes.py` — happy / empty / 404 / days cap / bounds 5건
- [x] `frontend/src/api/types.ts` — `StockPriceSeriesResponse` 추가
- [x] `frontend/src/hooks/useStockPriceSeries.ts` (신규)
- [x] `frontend/src/pages/StockDetail/PriceChart.tsx` (신규, Recharts LineChart)
- [x] `frontend/src/pages/StockDetail/index.tsx` 차트 카드 + days 선택자 (30/60/120/250) + empty / loading / error placeholder
- [x] `frontend/src/tests/StockDetail.test.tsx` 차트 happy / empty / error / days 선택자 4건 보강
- [x] `frontend/src/tests/mswServer.ts` + `frontend/e2e/fixtures/apiMocks.ts` handler 추가
- 완료 기준: backend pytest 314 → 319 (+5), frontend vitest 55 → 59 (+4), e2e 7 → 8 (+1). 차트가 종목 상세 화면에 노출. 태그 `v0.3-frontend-stock-chart`.

### Phase E — v0.3 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.3.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.4 후보 / 가이드 / 보안)
- [x] `README.md` 상단 마감 배너 갱신 + 누적 태그 라인
- [x] `PROJECT_STATUS.md` §0 v0.3 마감 선언, 기존 §0-1 / §0-2 그대로 보존
- [x] `TASKS.md` v0.3 phase 모두 [x] + v0.4 Backlog 갱신 (본 섹션)
- [x] backend pytest **319** + frontend vitest **59** + e2e **8** + build 4 게이트 그린
- [x] tag `v0.3-final` + push (commit `4dcef1e`)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES 붙여넣기 (UI 작업).

## v0.4 — Analyst & Theme Intelligence

기준선: `v0.3-final` (HEAD `f6b0ba5`). 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0004` 참조.

**v0.4 핵심 목표**

기업 / 산업 / 테마 / 원자재 / 매크로 / 전략 리포트 메타데이터를 CSV / Excel 로
import 하고, 리포트에서 추출한 **투자 테마** 와 **테마 → 종목 매핑** 을 저장하며,
**변화 시그널 이벤트** (TARGET_PRICE_UP / SUPPLY_SHORTAGE / RISK_WARNING …) 를
구조화한다. 종목별 컨센서스 + 보조 점수 `report_score` (기업 리포트) +
`theme_signal_score` (테마·시그널 기반 선행 신호) 를 계산해 추천 / 종목 상세에
참고 근거로 노출한다. 추천 산식 본 weight 는 손대지 않고 ±5점 cap 보조 가산만.

**v0.4 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI / 라우터 — import 는 운영자 CLI 만, 응답에만 변화
- ❌ 리포트 자동 크롤링 / 스크레이핑
- ❌ 리포트 원문 전문 (PDF body / paragraph) DB 저장
- ❌ PDF 파일 자체 git 레포 / DB BLOB 저장 — `source_url` 또는 `source_file_path` 만
- ❌ `source_file_path` 외부 노출 (API 응답 / 프런트 / e2e 모두에서 마스킹 또는 미포함)
- ❌ 외부 공유 / 공개 API
- ❌ 뉴스 / 공시 실시간 수집 (별도 v0.5+ cycle)
- ❌ 즐겨찾기 / 관심 종목 / 인증 / Strategy / Backtest / MockBroker (v0.5+ 후보 그대로)
- ❌ HoldingCheck 산식 변경 (보유 점검은 그대로)
- ❌ 추천 산식 본 weight 변경 — `report_score` 는 ±5점 cap 보조 가산만

### Phase A — DB 모델 6종 + Repository ✅ 인수

> 원안 (3 모델) 에서 6 모델로 확장 — Theme + ThemeStockMapping + SignalEvent 추가.
> 기업 / 산업 / 테마 / 원자재 / 매크로 / 전략 리포트 모두 단일 `analyst_reports`
> 테이블에 `report_type` 으로 구분 저장.

- [x] `app/db/models.py` — `AnalystReport` (28 컬럼: symbol nullable / report_type / broker_name / analyst_name / published_at / title / rating / normalized_rating / target_price / previous_target_price / current_price_at_report / currency / summary ≤500 / positive_points / risk_points / source_url / source_file_path / language / source_reliability_score / extraction_method / extraction_confidence / duplicate_group_key / TimestampMixin)
- [x] `app/db/models.py` — `ReportTheme` (theme_name / theme_category 13종 / direction / time_horizon / source_report_id FK / extraction_method)
- [x] `app/db/models.py` — `ThemeStockMapping` (theme_id FK / symbol / market / exchange / country / relation_type / impact_direction / impact_strength / impact_path 11종 / benefit_type / time_lag)
- [x] `app/db/models.py` — `ReportSignalEvent` (report_id FK / symbol nullable / theme_id nullable FK / event_type 18종 / direction / strength / time_horizon / evidence_json)
- [x] `app/db/models.py` — `ReportConsensusSnapshot` (window_days 추가, unique 가 `(symbol, snapshot_date, window_days)` 로 확장)
- [x] `app/db/models.py` — `ReportScoreLog` (report_score + theme_signal_score 둘 다 nullable, theme_count / signal_event_count / theme_signal_bonus / event_signal_bonus / risk_penalty 추가)
- [x] Unique constraints: 6 테이블 모두 spec 일치
- [x] `relationship` + cascade `all, delete-orphan` (`AnalystReport.themes` / `signal_events`, `ReportTheme.stock_mappings` / `signal_events`)
- [x] `app/data/repositories/analyst_reports.py` (신규) — `create` / `get_by_id` / `get_by_unique` / `upsert_unique` / `list_by_symbol` / `list_by_report_type` / `list_recent` / `list_recent_by_broker` / `search_text`
- [x] `app/data/repositories/report_themes.py` (신규) — `create` / `upsert_by_report_and_theme` / `list_recent` / `list_by_category` / `list_by_direction` / `list_by_source_report`
- [x] `app/data/repositories/theme_stock_mappings.py` (신규) — `create` / `upsert_by_theme_and_symbol` / `list_by_theme` / `list_by_symbol` / `list_positive_by_symbol` / `list_negative_by_symbol` / `list_by_impact_path`
- [x] `app/data/repositories/report_signal_events.py` (신규) — `create` / `upsert_by_report_event_symbol_theme` / `list_by_symbol` / `list_by_theme` / `list_by_event_type` / `list_recent` / `list_positive_by_symbol` / `list_negative_by_symbol`
- [x] `app/data/repositories/report_consensus_snapshots.py` (신규) — `upsert_by_symbol_date_window` / `get_latest_by_symbol` / `list_recent`
- [x] `app/data/repositories/report_score_logs.py` (신규) — `create` / `get_latest_by_symbol` / `list_recent_by_symbol` / `list_by_recommendation_run`
- [x] `app/data/repositories/__init__.py` — 6 Repository export 추가 (alphabetical 유지)
- [x] `tests/integration/test_analyst_report_repositories.py` 신규 — **16 케이스** (CRUD / unique / 글로벌 US 리포트 / null symbol THEME·MACRO·COMMODITY / search / 매핑 positive·negative / impact_path / signal event 분기 / consensus window / score log 정렬)
- [x] `DB_SCHEMA.md` — §18~23 추가, 저작권 정책 단락 명시
- 완료 기준: backend pytest **319 → 335 passed (+16)**, 회귀 0건. 태그 `v0.4-backend-reports`.

### Phase B — CSV import + 일별 컨센서스 잡 ✅ 인수

> Excel 직접 지원은 v0.5+ (openpyxl 의존성 도입 시) — Phase B 는 stdlib `csv`
> 만 사용 (pandas / openpyxl 의존성 미추가). 운영자는 Excel 에서 "다른 이름으로
> 저장 → CSV UTF-8" 로 export 후 import 하면 됨.

- [x] `scripts/import_analyst_reports.py` (신규, argparse) — `--file --commit --encoding --db-url`. 기본 dry-run, `--commit` 명시 시에만 DB 적재
- [x] `app/data/importers/analyst_reports.py` (신규) — 35 컬럼 CSV → up to 4 entity (report + theme + N mappings + signal_event) 변환 + 검증
- [x] CSV 헤더 forbidden 컬럼 13종 (`body`/`content`/`full_text`/`paragraph_text`/`article_body`/`raw_text`/`html_body`/`paragraphs`/`full_body`/`original_text`/`report_body`/`본문`/`원문`/`전문`) 거부 → `CsvForbiddenColumnError`
- [x] 필수 컬럼 4종 (`report_type`/`broker_name`/`published_at`/`title`) 검증, 그 외 모두 optional
- [x] enum 검증 11종 (`report_type`/`normalized_rating`/`theme_category`/`theme_direction`/`theme_time_horizon`/`impact_direction`/`impact_path`/`relation_type`/`benefit_type`/`signal_event_type`/`signal_direction`)
- [x] 숫자 검증 (`target_price`/`previous_target_price`/`current_price_at_report`/`signal_strength` ∈ [0,1])
- [x] 날짜 검증 (`published_at` ISO `YYYY-MM-DD`)
- [x] 멱등 로직: 4 entity 모두 `get_by_unique` → 존재 시 skip, 부재 시 create (`skipped_duplicates` 카운트)
- [x] `summary` > 500자 시 truncate + `truncated_summaries` 카운트
- [x] `related_symbols` 세미콜론 / 쉼표 구분 → 종목별 1 mapping
- [x] CLI 출력에 `source_file_path` 미노출 (에러 메시지조차 컬럼명 + 정상 enum/date/숫자만 echo)
- [x] `tests/fixtures/analyst_reports_sample.csv` (신규, 3 row: COMPANY 삼성전자 + THEME 메모리 쇼티지 + COMMODITY Cu) — 가상 데이터, 실제 증권사 원문 0건
- [x] `app/scheduler/jobs.py` — `update_report_consensus_snapshots` 잡 신규 (활성 윈도우 default 90일, COMPANY 타입만, 종목별 upsert)
- [x] `app/scheduler/scheduler.py` — 잡 등록 (기본 매일 06:30 KST, 06:00 텔레그램 발송 직후 / 08:30 prе-market check 직전)
- [x] `tests/integration/test_analyst_report_import.py` 신규 — **19 케이스** (sample fixture / dry-run / commit / 멱등 / forbidden 컬럼 영문·한글 / required 누락 / enum / date / 숫자 / 500자 truncate / signal_strength 범위 / theme 추출 / 매핑 multiple / signal 추출 / source_file_path 마스킹 / programmatic entry)
- [x] `tests/integration/test_consensus_snapshot_job.py` 신규 — **8 케이스** (NO_DATA / 다종목 산정 / 윈도우 외 제외 / non-COMPANY 제외 / 멱등 upsert / job_runs 기록 / 등록 검증 2건)
- [x] `tests/integration/test_scheduler_jobs.py` 갱신 — `test_job_functions_registry_covers_all_six_jobs` → `..._seven_jobs` 로 이름·내용 갱신
- [x] `INTEGRATION_RUNBOOK.md` §9 추가 — dry-run / commit / 인코딩 / DB URL / 컨센서스 잡 수동 트리거 / 점검 5 단락
- 완료 기준: backend pytest **335 → 362 passed (+27)**, 회귀 0건. 태그 `v0.4-import-pipeline`.

### Phase C — `report_score` 계산기 + ScoreProducer 통합

- [x] `app/analysis/report_score_calculator.py` (신규) — `calculate_report_score(consensus, latest_close) -> ReportScoreResult` 순수 함수
- [x] 산식: `clip(50 + (target_upside_pct * 0.5) + (rating_score_avg * 10) + recency_bonus, 0, 100)` — `report_count = 0 → null`
- [x] `app/decision/recommendation_engine.py` — 종목별 `latest_consensus + latest_close` 로 score 계산 → `report_score_logs` 추가 → `recommendation.total_score` 후처리 가산 (±5점 cap)
- [x] `app/decision/recommendation_engine.py` — `decision_logs.rule_result_json["report_evidence"]` 추가 (top themes / top events / report_count / adjustment)
- [x] `app/api/schemas.py` — `RecommendationItemSchema` 에 `report_score`, `theme_signal_score`, `report_evidence` 추가
- [x] `tests/unit/test_report_score_calculator.py` (신규, 12 케이스: null / upside clip / rating 평균 / recency / clamp / adjustment / theme signal)
- [x] `tests/integration/test_recommendation_engine.py` — `report_score` / `theme_signal_score` 가산·감산, evidence, `report_score_logs` 저장 보강
- [x] `tests/integration/test_api_routes.py` — `/api/recommendations/latest` 응답 `report_score` / `theme_signal_score` / `report_evidence` 노출
- [x] `app/decision/holding_check_engine.py` 변경 0건 (HoldingCheck 산식 그대로 유지)
- [x] `app/decision/scoring_engine.py` 본 weight 변경 0건
- 완료 기준: backend pytest **379 passed** / frontend vitest **59 passed** / frontend build **passed** / Playwright e2e **8 passed**. 회귀 0건. 태그 `v0.4-report-score`.

### Phase D — 프런트 (StockDetail 리포트 + 추천 컬럼)

- [x] `app/api/routes.py` — `GET /api/stocks/{symbol}/reports` 신규 read-only 라우터 + `/api/stocks/{symbol}.analyst_reports` 응답 통합
- [x] `app/api/schemas.py` — `AnalystReportSchema`, `ReportConsensusSchema`, `RelatedThemeSchema`, `ReportSignalEventSchema`, `StockReportsResponse` 신규
- [x] `app/api/schemas.py` — `AnalystReportSchema` 에서 `source_file_path` **제외** (응답 마스킹)
- [x] `tests/integration/test_api_routes.py` — happy / empty / 404 / `source_file_path` 부재 단언 보강
- [x] `frontend/src/api/types.ts` — `AnalystReport` (no source_file_path), `ReportConsensus`, `RelatedTheme`, `ReportSignalEvent`, `StockReportsResponse` 추가
- [x] `frontend/src/hooks/useStockReports.ts` — 별도 hook 없이 기존 `useStockDetail` 응답의 `analyst_reports` 블록 재사용
- [x] `frontend/src/pages/StockDetail/AnalystReportsCard.tsx` (신규, 컨센서스 + 최근 리포트 + 관련 테마 + 시그널 카드)
- [x] `frontend/src/pages/StockDetail/index.tsx` — 차트 카드 다음에 리포트 카드 추가
- [x] `frontend/src/pages/Recommendations/RecommendationsTable.tsx` — `report_score` / `theme_signal_score` 컬럼 + evidence 요약 + null fallback `—`
- [x] `frontend/src/tests/StockDetail.test.tsx` — 리포트 카드 happy / empty / `source_file_path` 부재 보강
- [x] `frontend/src/tests/Recommendations.test.tsx` — score 컬럼 happy / null fallback 보강
- [x] `frontend/src/tests/mswServer.ts` — stock detail 응답 embedded block 방식이라 별도 `/reports` 핸들러 불필요
- [x] `frontend/e2e/fixtures/apiMocks.ts` — 005930 sample reports fixture
- [x] `frontend/e2e/dashboard.spec.ts` — 리포트 카드 노출 + `source_file_path` 미노출 e2e 보강
- 완료 기준: backend pytest **382 passed** / frontend vitest **60 passed** / frontend build **passed** / Playwright e2e **9 passed**. 회귀 0건. 태그 `v0.4-frontend-reports`.

### Phase E — v0.4 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.4.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.5 후보 / 운영 가이드 / **저작권·보안**)
- [x] `RELEASE_NOTES_v0.4.md` §보안 — 4 정책 명시 (원문 본문 미저장 / PDF 미저장 / 자동 크롤링 금지 / source_file_path 외부 노출 금지)
- [x] `README.md` 상단 마감 배너 v0.4 갱신 + 누적 태그 라인 + 저작권 한 줄
- [x] `PROJECT_STATUS.md` §0 v0.4 시작 → v0.4 마감으로 in-place 갱신, §0-1 v0.3 / §0-2 v0.2 / §0-3 v0.1 그대로 보존
- [x] `TASKS.md` v0.4 phase 모두 [x]
- [x] backend pytest + frontend vitest + e2e + build 4 게이트 그린 (재확인 완료: backend **382 passed** / vitest **60 passed** / build / e2e **9 passed** — Phase D 시점과 동일, 회귀 0건)
- [x] tag `v0.4-final` + push (commit `17f9fed`, 게이트 재확인 commit `0f25be6`)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.4 붙여넣기 (UI 작업).

## v0.5 — News, Disclosure & Theme Ranking ✅ 마감

기준선: `v0.4-final` (HEAD `0f25be6`). 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0005` 참조.

**v0.5 마감 게이트 (Phase E 시점)**: backend pytest **481 passed** / frontend
vitest **68 passed** / frontend build 그린 / Playwright e2e **11 passed**. 누적
태그 `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` →
`v0.5-frontend-themes` → `v0.5-final` (Phase E 후 부여).

**v0.5 핵심 목표**

뉴스 / 공시 메타데이터를 v0.1 부터 비어 있던 `news_items` 테이블에 처음으로 채우고,
`DummyScoreProducer.news_score` (가중치 25%) 를 첫 real 화한다 (`RealNewsScoreProducer`).
`RISK_DISCLOSURE` 카테고리는 RiskEngine 의 `risk_flags` / `risk_penalty` 로 보강된다.
v0.4 의 테마·매핑·시그널 데이터는 `/themes` 9번째 화면으로 처음 surface 되며,
StockDetail 의 "관련 테마" 카드도 `impact_path` icon + reason 으로 가시화 강화된다.

**v0.5 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.4 일관 정책 유지)
- ❌ 뉴스 / 공시 본문 (paragraph) DB 저장 — title / URL / 메타데이터 / 분류 / sentiment 라벨만 (v0.4 저작권 정책 패턴 유지)
- ❌ 자동 fetch default ON — `Settings.news_collection_enabled` / `disclosure_collection_enabled` = false (운영자가 `.env` 에 명시 enable 시에만 동작)
- ❌ 재무 / 실적 점수 실제화 — v0.6 후보 (DART 재무제표 파싱은 별도 cycle)
- ❌ 관심종목 / Watchlist / 인증 — v0.6 후보 (POST 도입은 인증 사이클과 묶음)
- ❌ Strategy / Backtest / MockBroker — v0.7+ 후보
- ❌ HoldingCheckEngine 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 — `news_score` 가 50 → real 로 교체되지만 weight 25% 그대로
- ❌ LLM 자동 sentiment 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.6+ 후보

### Phase A — News data layer + collector skeleton ✅ 인수 (PR1 + PR2)

> Phase A 는 두 PR 로 분리. **PR1 = data layer skeleton** (interface + DTO +
> collector + repository + 모델 컬럼 + 통합 테스트). **PR2 = scheduler integration**
> (`collect_news` 잡 + Settings flag + scheduler 등록). PR1 인수 시 backend
> pytest **382 → 401 passed (+19)**, PR2 인수 시 **401 → 406 passed (+5)**,
> 회귀 0건. 두 PR 누적 후 태그 `v0.5-news-collector`.

**PR1 — Data layer skeleton ✅ 인수**

- [x] `app/data/interfaces.py` — `NewsProviderInterface` ABC (`fetch_recent_news(*, symbols, since, limit) -> list[NewsItemDTO]`)
- [x] `app/data/dtos.py` — `NewsItemDTO` dataclass (9 fields, no body/content/full_text/paragraph_text)
- [x] `app/data/collectors/news_collector.py` (신규) — `NewsCollector` + `NewsCollectorResult` (fetched / inserted / skipped_duplicates / truncated_summaries). 멱등 + summary 500자 truncate 카운트
- [x] `app/data/collectors/__init__.py` — `NewsCollector` / `NewsCollectorResult` export
- [x] `app/db/models.py` — `NewsItem.category: String(32) nullable, index=True` ALTER ADD COLUMN
- [x] `app/data/repositories/news_items.py` — `get_by_url` / `upsert_by_url` (멱등, returns `(item, inserted)`) / `list_recent_by_symbol` (JSON contains via Python filter) / `list_recent_by_category`
- [x] `tests/mocks/fake_news_provider.py` (신규) — `FakeNewsProvider` 결정론적 3-row 샘플 (NEWS / EARNINGS_REPORT / RISK_DISCLOSURE 카테고리 각 1건)
- [x] `tests/integration/test_news_collector.py` 신규 (**19 케이스**: 본문 컬럼 0 가드 (DTO + ORM 양쪽) / category 컬럼 추가 가드 / 9 fields exactness / FakeNewsProvider determinism + symbol·since 필터 + interface 구현 / collector 첫 run 3건 insert / 재실행 멱등 / category persist / related_symbols + sentiment persist / source fallback to provider / summary truncate count / empty provider / repository upsert_by_url 멱등 + empty url reject / list_recent_by_symbol JSON contains + since 필터 / list_recent_by_category 정렬)
- [x] backend pytest **382 → 401 passed (+19)**, 회귀 0건
- [x] `DB_SCHEMA.md` §8 `news_items.category` 컬럼 + 저작권 정책 한 단락 추가

**PR2 — Scheduler integration ✅ 인수**

- [x] `app/config/settings.py` — `news_collection_enabled: bool = False` (default OFF, `NEWS_COLLECTION_ENABLED` env var 매핑)
- [x] `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_NEWS` 상수 + `_resolve_news_provider(session)` helper + `collect_news(session)` 함수 (3-way branch: disabled → SKIPPED + reason="news_collection_disabled" / enabled+no_provider → SKIPPED + reason="no_provider_configured" / enabled+provider → NewsCollector 실행 + counters)
- [x] `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_NEWS` import + DEFAULT_SCHEDULE 19:00 KST 등록
- [x] `app/scheduler/jobs.py` `JOB_FUNCTIONS` registry 7 → **8 jobs**
- [x] `tests/integration/test_scheduler_jobs.py` 갱신 — `test_job_functions_registry_covers_all_seven_jobs` → `..._eight_jobs` + `test_default_schedule_includes_collect_news_at_1900_kst` 추가 + `collect_news` 분기 테스트 4건 (disabled provider 미호출 검증 / enabled+no_provider SKIPPED / enabled+FakeNewsProvider 3 inserted / 멱등 재실행 3 skipped_duplicates)
- [x] `tests/unit/test_project_structure.py::test_settings_defaults` — `news_collection_enabled is False` 단언 추가
- [x] backend pytest **401 → 406 passed (+5)**, 회귀 0건. frontend vitest 60 / build / e2e 9 변경 없음
- 완료 기준 (PR2): backend pytest 401 → 406 passed (+5), 회귀 0건. Phase A 누적 PR1+PR2 마감 → 태그 `v0.5-news-collector`.

### Phase B — Disclosure subset + 분류 + 종목 매핑 ✅ 인수

- [x] `app/data/interfaces.py` — `DisclosureProviderInterface` ABC (`fetch_recent_disclosures(*, symbols, since, limit) -> list[DisclosureItemDTO]`)
- [x] `app/data/dtos.py` — `DisclosureItemDTO` dataclass (9 fields: title / url / provider / published_at / symbol / company_name / disclosure_type / category / summary). 본문 paragraph / body / content / full_text / raw_text / paragraph_text / 본문 / 원문 / 전문 등 13종 forbidden 필드 0건 (테스트 명시 단언)
- [x] `app/data/collectors/disclosure_collector.py` (신규) — `classify_disclosure(title, disclosure_type, summary)` 순수 함수 + `DisclosureCollector` + `DisclosureCollectorResult`
- [x] 분류 카테고리 5종 + priority order: RISK_DISCLOSURE > EARNINGS_REPORT > OWNERSHIP_CHANGE > GOVERNANCE > OTHER. 한글 keyword (소송 / 횡령 / 배임 / 거래정지 / 감사의견 / 회생 / 파산 / 실적 / 잠정 / 영업이익 / 당기순이익 / 최대주주 / 지분 / 보유주식 / 이사회 / 사외이사 / 감사위원회 / 주주총회) + 영문 keyword 동시 지원
- [x] `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_DISCLOSURES` 상수 + `_resolve_disclosure_provider(session)` helper + `collect_disclosures(session)` 함수. **3-way branch**: disabled → SKIPPED + reason="disclosure_collection_disabled" / enabled+no_provider → SKIPPED + reason="no_provider_configured" / enabled+provider → DisclosureCollector 실행 + counters + classified_counts. JOB_FUNCTIONS registry **8 → 9 jobs**
- [x] `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_DISCLOSURES` import + DEFAULT_SCHEDULE 20:00 KST 등록
- [x] `app/config/settings.py` — `disclosure_collection_enabled: bool = False` (default OFF, `DISCLOSURE_COLLECTION_ENABLED` env var 매핑)
- [x] `app/data/collectors/__init__.py` — `DisclosureCollector` / `DisclosureCollectorResult` / `classify_disclosure` / 5 CATEGORY_* 상수 export
- [x] `tests/mocks/fake_disclosure_provider.py` (신규) — `FakeDisclosureProvider` 결정론적 4-row 샘플 (EARNINGS / OWNERSHIP / RISK / GOVERNANCE 각 1건). symbols / since / limit 필터 지원
- [x] `tests/integration/test_disclosure_collector.py` 신규 — **24 케이스** (DTO 본문 필드 0 가드 / DTO 정확히 9 fields / classify Korean 12 케이스 (parametrized) / classify priority RISK > EARNINGS / classify priority RISK > GOVERNANCE / classify uses disclosure_type / classify uses summary / classify OTHER fallback / FakeProvider determinism / symbols·since 필터 / interface 구현 / collector 4건 insert + classified_counts / 멱등 재실행 4 skipped_duplicates / category 컬럼 persist / summary 500자 truncate / empty provider / related_symbols persist)
- [x] `tests/integration/test_scheduler_jobs.py` 갱신 — `..._eight_jobs` → `..._nine_jobs` registry + `test_default_schedule_includes_collect_disclosures_at_2000_kst` + `collect_disclosures` 분기 4건 (disabled / enabled+no_provider / enabled+FakeProvider 4 inserted + classified_counts / 멱등)
- [x] `tests/unit/test_project_structure.py::test_settings_defaults` — `disclosure_collection_enabled is False` 단언 추가
- [x] `INTEGRATION_RUNBOOK.md` §11 신규 — collect_disclosures 5 단락 (기본 동작 / opt-in / 분류 룰 표 / 수동 트리거 / 운영 점검 / 롤백). §10 News 와 동일 패턴
- [x] `DB_SCHEMA.md` §8 `news_items.category` 설명 보강 — 뉴스/공시 통합 저장 + DisclosureCollector keyword priority 명시
- [x] backend pytest **406 → 440 passed (+34)**, 회귀 0건. frontend vitest 60 / build / e2e 9 변경 없음
- 완료 기준: backend pytest 406 → 440 passed (+34), 회귀 0건. 태그 `v0.5-disclosure-pipeline`.

### Phase C — `RealNewsScoreProducer` + `DisclosureRiskProducer` + ScoreProducerInterface ABC ✅ 인수

- [x] `app/analysis/score_producers.py` — `ScoreProducerInterface` ABC 추출. `DummyScoreProducer` 가 ABC 구현체로 유지 (기존 호출자 호환)
- [x] `app/analysis/score_producers.py` — `RealNewsScoreProducer` 신규. composition 패턴 — fallback (default DummyScoreProducer) 가 supply/fundamental/earnings/ai 처리, news_score 만 NewsItemRepository 기반 real 화. 산식: `clip(50 + weighted_sentiment * 5 / max(news_count, 1), 0, 100)`. `news_count = 0 → 50` (Dummy fallback 호환). recency: ≤24h:1.0 / ≤3d:0.7 / ≤7d:0.3 / 그 외:0. SQLite/Postgres tz roundtrip 호환 (`_to_naive_utc` helper).
- [x] `app/analysis/score_producers.py` — `DisclosureRiskProducer` + `DisclosureRiskResult`. 14일 윈도우 + symbol-first 필터 + category=RISK_DISCLOSURE. `penalty_addition = min(count × 3, 10)` cap. count=0 → flag=None / penalty=0. Evidence top 3 by recency.
- [x] `app/decision/risk_engine.py` — `evaluate_recommendation` / `evaluate_holding` 에 `disclosure_risk_count: int = 0` + `disclosure_penalty_addition: Decimal = 0` 파라미터 추가. count > 0 시 `RISK_FLAG_DISCLOSURE` 추가 + penalty 가산. **default 0 으로 backward compat** (기존 호출자 영향 0). `details` 에 `disclosure_risk_count` / `disclosure_penalty_addition` 기록.
- [x] `app/decision/recommendation_engine.py` — constructor 에 `disclosure_risk_producer` 옵션 추가 + `score_producer` 타입을 `ScoreProducerInterface` 로 확장. `generate()` 에서 producer 호출 → RiskEngine 에 disclosure 파라미터 전달 → `_Candidate.disclosure_risk_evidence` 저장 → `_persist_candidate()` 에서 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 양쪽에 `news_evidence` (components.metadata 에서 추출) + `disclosure_risk_evidence` 기록
- [x] `app/decision/holding_check_engine.py` — 동일 패턴. ScoringEngine 본 산식 / 3-pass 흐름 변경 0건. news_score 만 real 화 + RiskEngine 에 disclosure 파라미터 전달 + 양쪽 evidence 기록
- [x] API schema — `RecommendationItemSchema` / `HoldingCheckSchema` 의 `news_evidence` 별도 필드 추가는 **Phase D 로 이연** (사용자 spec "검토" 단계). evidence 는 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 에 이미 저장 — Phase D 의 frontend 노출 시점에 명시 schema 필드 추가
- [x] **Safe-fields-only whitelist 강제**: producer 가 evidence 빌더에서 `title / url / provider / published_at / sentiment` 만 노출 (body / content / full_text / source_file_path 0건). 단위 테스트가 명시 단언
- [x] `tests/unit/test_real_news_score_producer.py` 신규 — **17 케이스**: news_count=0 / 양수 recent / 음수 recent / 6일 (≤7d) / 7일 윈도우 외 제외 / mixed sentiment / evidence top 3 / fallback delegation / score_holding 패턴 + DisclosureRiskProducer 8 케이스 (no risk / 1 → 3 penalty / 3 → 9 penalty / 10 → cap 10 / 14일 윈도우 / symbol 필터 / non-risk category 제외 / evidence top 3)
- [x] `tests/integration/test_recommendation_engine.py` RealNewsScoreProducer 시나리오 보강 5건 (real news_score persist / news_evidence in decision_log + safe fields / RISK_DISCLOSURE flag + evidence + penalty / no-news fallback to 50 / dummy-only backward compat with no evidence)
- [x] `tests/integration/test_holding_check_engine.py` 보강 3건 (real news_score in HoldingCheck / RISK_DISCLOSURE flag + evidence / 기존 MA20_BREAKDOWN + STOP_LOSS_NEAR + RISK_DISCLOSURE 동시 누적 검증)
- [x] `tests/unit/test_risk_engine.py` `RISK_DISCLOSURE` flag 케이스 5건 (default 0 backward compat / count>0 → flag+penalty / 기존 flags 와 누적 / holding default 0 / holding count>0)
- [x] HoldingCheckEngine / ScoringEngine 본 weight 산식 변경 0건 검증 — 기존 회귀 테스트 모두 그대로 통과
- 완료 기준: backend pytest **440 → 470 passed (+30)**, frontend vitest 60 / build / e2e 9 변경 없음, 회귀 0건. 태그 `v0.5-news-score`.

### Phase D — 테마 랭킹 화면 + StockDetail 영향 설명 강화

- [ ] `app/api/routes.py` — `GET /api/themes/ranking?as_of=...&category=...&direction=...&limit=20` 신규 (read-only)
- [ ] `app/api/routes.py` — `GET /api/themes/{theme_id}` 신규 (read-only). 테마 + 매핑 종목 + 최근 시그널 이벤트
- [ ] `app/api/schemas.py` — `ThemeRankingItemSchema` / `ThemeDetailResponse` 신규
- [ ] `tests/integration/test_api_routes.py` happy / empty / 필터 / 404 ~4건
- [ ] `frontend/src/api/types.ts` — `ThemeRankingItem` / `ThemeDetailResponse` 타입 추가
- [ ] `frontend/src/hooks/useThemeRanking.ts` (신규)
- [ ] `frontend/src/hooks/useThemeDetail.ts` (신규)
- [ ] `frontend/src/pages/Themes/index.tsx` (신규) — 랭킹 + 검색 / 카테고리 / direction 필터
- [ ] `frontend/src/pages/Themes/ThemeDetail.tsx` (신규) — 테마 상세 + 매핑 종목 + 시그널 이벤트
- [ ] `frontend/src/router.tsx` — `/themes` + `/themes/:themeId` lazy route
- [ ] `frontend/src/components/Sidebar.tsx` — "테마 (β)" 9번째 메뉴
- [ ] `frontend/src/pages/StockDetail/AnalystReportsCard.tsx` — `impact_path` icon + reason 가시화 강화 + 테마 클릭 → `/themes/:id`
- [ ] `frontend/src/tests/Themes.test.tsx` 신규 (~3 케이스: happy / empty / 필터)
- [ ] `frontend/src/tests/mswServer.ts` — `/api/themes/*` 핸들러
- [ ] `frontend/e2e/fixtures/apiMocks.ts` — fixture 추가
- [ ] `frontend/e2e/dashboard.spec.ts` — 9 메뉴 nav 검증 + `/themes` 화면 visit + 자동매매 부재 가드 통과 확인 ~1건 (e2e 9 → 10)
- 완료 기준: backend pytest ~415 → ~419, frontend vitest 60 → ~63, e2e 9 → 10. 태그 `v0.5-frontend-themes`.

#### Phase D 인수 결과 ✅ (실측)

- [x] backend `/api/themes/ranking` + `/api/themes/{theme_id}` (read-only). `ThemeRankingItemSchema` / `ThemeRankingResponse` / `ThemeStockMappingSchema` / `ThemeDetailResponse` 신규
- [x] `RecommendationItemSchema` 에 `news_evidence` + `disclosure_risk_evidence` nullable 필드 추가 (Phase C 가 snapshot 에 저장만 해 둔 evidence 를 surface)
- [x] frontend `/themes` + `/themes/:themeId` 신규 페이지 + Sidebar 9th menu (`테마 (β)`) + lazy router
- [x] `RelatedThemesCard` 테마 → `/themes/:id` 클릭 + impact_path / impact_direction badge
- [x] `RecommendationsTable` news/disclosure evidence 두 컬럼 추가
- [x] `mswServer.ts` 기본 핸들러 + `apiMocks.ts` fixture 보강
- [x] tests: backend pytest **470 → 481 (+11)** / frontend vitest **60 → 68 (+8)** / e2e **9 → 11 (+2)** / build 그린
- [x] source_file_path 0건 노출 가드 — 테마 ranking / detail / RecommendationsTable 응답 + e2e
- [x] 회귀 0건. KIS / Telegram / scheduler / 자동매매 / POST 라우터 / 산식 본 weight 변경 0건. 태그 `v0.5-frontend-themes` 부여 예정

### Phase E — v0.5 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.5.md` 신규 (산출물 / 검증 / 안전 정책 / 한계 / v0.6 후보 / 운영 가이드 / 누적 태그)
- [x] `RELEASE_NOTES_v0.5.md` 안전 정책 — News / Disclosure 본문 paragraph 미저장 / 자동 fetch default OFF / source URL 만 / 수동 trigger 위주 / `source_file_path` 미노출 / Evidence whitelist 명시
- [x] `README.md` 상단 마감 배너 v0.4 → v0.5 갱신 + 누적 태그 라인 + 저작권·데이터 정책 한 단락 + §1 누적 기능 v0.5 항목 5종 + §2 제외 범위 v0.5 정책 4건 + §4 문서 표 + §6 누적 사이클 / 영역 표 + §11 회귀 기준선
- [x] `PROJECT_STATUS.md` §0 v0.5 시작 → v0.5 마감 in-place 갱신, §0-1 v0.4 / §0-2 v0.3 / §0-3 v0.2 / §0-4 v0.1 그대로 유지 (이미 Phase A 진입 시 강등 완료) + Phase E 결과 블록 추가
- [x] `TASKS.md` v0.5 Phase D / Phase E 체크박스 [x] + v0.5 전체 마감 헤더
- [x] `ROADMAP.md` v0.5 행 마감 표시 + v0.5 phase 표 ✅ + v0.6 후보 정리 (이미 cycle 진입 시 갱신 완료, Phase E 시 정합성 점검만)
- [x] `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `INTEGRATION_RUNBOOK.md` / `DB_SCHEMA.md` 정합성 점검 (Phase B/C/D 인수 시 이미 갱신된 항목 재확인 — `/api/themes/*`, recommendation evidence, source_file_path 미노출, 본문 미저장 정책)
- [x] backend pytest + frontend vitest + e2e + build 4 게이트 재확인 — **481 / 68 / 11 / build 그린**, 회귀 0건
- [x] tag `v0.5-final` + push (커밋 `9ccf0f8`, 태그 `v0.5-final` origin/main 동기화 완료)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.5 붙여넣기 (UI 작업).

## v0.6 — Fundamental & Earnings Intelligence ✅ 마감 (2026-05-06)

기준선: `v0.5-final` (HEAD `9ccf0f8`). 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0006` 참조.

**v0.6 핵심 목표**

운영자 수동 CSV / DART subset 1단계로 **재무 지표 시계열 (`fundamental_snapshots`) +
실적 이벤트 (`earnings_events`)** 데이터를 도입하고, `DummyScoreProducer` 5
컴포넌트 중 두 번째 큰 weight 인 `fundamental_score` (recommendation 25%) 와
HoldingCheckEngine 의 `earnings_score` 를 **첫 real 화** 한다 (`RealFundamentalScoreProducer`
+ `RealEarningsScoreProducer`). v0.4 의 Analyst Report CSV import 패턴
(`scripts/import_analyst_reports.py`) 을 그대로 재사용 — forbidden body column
13종 거부, summary 500자 truncate, source_file_path 마스킹. 추후 DART API
provider 를 붙일 수 있게 `FundamentalProviderInterface` / `EarningsProviderInterface`
ABC 만 미리 두고 실 API 구현체는 v0.7+ 로 이연 (FakeProvider 만 제공).

**v0.6 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.5 일관 정책 유지)
- ❌ DART API 자동 호출 — 1단계는 운영자 CSV 만. ABC + Fake provider 만, 실 API 구현체는 v0.7+
- ❌ 자동 fetch default ON — `Settings.fundamental_collection_enabled` / `earnings_collection_enabled` = false
- ❌ 재무제표 PDF / Excel BLOB 저장 — CSV 정량 지표 메타데이터만
- ❌ 재무 / 실적 본문 paragraph 저장 — 짧은 운영자 메모 (≤500자) 만
- ❌ ScoringEngine 본 weight 변경 — `fundamental_score` 가 50 → real 로 교체되지만 weight 15% 그대로
- ❌ HoldingCheckEngine 본 weight 변경 — `earnings_score` 가 50 → real 로 교체되지만 weight 그대로
- ❌ 관심종목 / Watchlist / 인증 — v0.7 후보 (POST 도입 + 인증 별도 cycle)
- ❌ Strategy / Backtest / MockBroker — v0.8+ 후보
- ❌ LLM 자동 재무 / 어닝 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.7+
- ❌ KIS API 외 외부 자격증명 자동 호출

### Phase A — Fundamental data layer + CSV import

**PR1 — FundamentalSnapshot ORM + Repository ✅ 인수**

**PR2 — Fundamental CSV import pipeline ✅ 인수**

- [x] `app/data/dtos.py` — `FundamentalSnapshotDTO` dataclass (20 fields: symbol / snapshot_date / fiscal_year / fiscal_quarter / 15 numeric metrics / source). body / content / full_text / paragraph / raw_text / html_body / 본문 / 원문 / 전문 / source_file_path 필드 0건
- [x] `app/data/interfaces.py` — `FundamentalProviderInterface` ABC (`fetch_fundamentals(symbols, fiscal_year, fiscal_quarter=None) -> list[FundamentalSnapshotDTO]`)
- [x] `app/db/models.py` — `FundamentalSnapshot` ORM 신규 (24번째 테이블). UniqueConstraint(`symbol`, `snapshot_date`, `fiscal_year`, `fiscal_quarter`)
- [x] `app/data/repositories/fundamental_snapshots.py` — `FundamentalSnapshotRepository` 신규 (`create`, `list_recent_by_symbol`, `list_by_fiscal_year`, `get_latest_by_symbol`, `upsert_by_symbol_period` 멱등)
- [x] `app/data/repositories/__init__.py` — export 갱신
- [x] `app/data/importers/fundamentals.py` 신규 — CSV → FundamentalSnapshotDTO 변환 + forbidden body/source_file_path/blob column 거부 + dry-run/commit 집계 (`inserted` / `updated` / `unchanged`)
- [x] `scripts/import_fundamentals.py` 신규 — argparse CLI (default dry-run, `--commit` 시 적재). `--file`, `--encoding`, `--db-url` 지원
- [x] `tests/mocks/fake_fundamental_provider.py` 신규 — `FakeFundamentalProvider` 결정론적 3-row 샘플. symbols / fiscal_year / fiscal_quarter 필터 지원
- [x] `tests/integration/test_fundamental_repository.py` 신규 (ORM metadata / create / upsert 멱등 / latest / recent 정렬 / fiscal_year 조회 / nullable quarter / Decimal / 본문 컬럼 0 가드)
- [x] `tests/integration/test_fundamental_import.py` 신규 (DTO forbidden guard / FakeProvider / dry-run / commit / reimport idempotency / forbidden column / required columns / date-year-quarter validation / Decimal / negative policy / CLI run_import)
- [x] `tests/fixtures/fundamentals_sample.csv` 신규 — 3종목 가상 샘플
- [x] `DB_SCHEMA.md` §24 신규 — `fundamental_snapshots` 컬럼 + 저작권 정책 한 단락
- 완료 기준: backend pytest **481 → ~510 passed (+~30)**, 회귀 0건. 태그 `v0.6-fundamental-data-layer`.

### Phase B — Earnings event layer + 어닝 캘린더 import

- [x] `app/data/dtos.py` — `EarningsEventDTO` dataclass (18 fields, ORM 대응). body / content / full_text / paragraph / raw_text / html_body / 본문 / 원문 / 전문 필드 0건
- [x] `app/data/interfaces.py` — `EarningsProviderInterface` ABC (`fetch_earnings_events(symbols, since=None, until=None, limit=100)`)
- [x] `app/db/models.py` — `EarningsEvent` ORM 신규 (25번째 테이블). UniqueConstraint(`symbol`, `event_date`, `fiscal_year`, `fiscal_quarter`, `event_type`)
- [x] `app/data/repositories/earnings_events.py` — `EarningsEventRepository` 신규 (`create`, `upsert_by_symbol_event`, `get_latest_by_symbol`, `list_recent_by_symbol`, `list_upcoming`, `list_by_surprise_type`)
- [ ] `app/data/importers/earnings.py` 신규 — CSV → DTO + forbidden body column 거부 + classification 룰
- [x] `app/data/importers/earnings.py` 신규 — CSV → EarningsEventDTO 변환 + forbidden body/source_file_path/blob column 거부 + BEAT/MEET/MISS/UNKNOWN surprise 계산
- [x] `scripts/import_earnings.py` 신규 — argparse CLI (default dry-run, `--commit`, `--encoding`, `--db-url`)
- [ ] `tests/mocks/fake_earnings_provider.py` 신규 — 결정론적 6-row 샘플 (4 REPORT + 2 ANNOUNCEMENT)
- [x] `tests/mocks/fake_earnings_provider.py` 신규 — BEAT / MEET / MISS / upcoming UNKNOWN 결정론 샘플
- [x] `tests/fixtures/earnings_events_sample.csv` 신규 — 4종목 가상 샘플
- [x] `tests/integration/test_earnings_repository.py` 신규 (ORM 본문 0 / create / upsert / latest / recent / upcoming / surprise_type 조회)
- [x] `tests/integration/test_earnings_import.py` 신규 (DTO guard / FakeProvider / dry-run / commit / forbidden body / enum/date/year/quarter validation / surprise 계산 / memo truncate / 멱등)
- [x] `DB_SCHEMA.md` §25 신규 — `earnings_events`
- [ ] `INTEGRATION_RUNBOOK.md` §13 신규 — 어닝 / 재무 import 운영 절차 (v0.5 §10 News / §11 Disclosure / §12 테마 패턴 그대로)
- 완료 기준: backend pytest **~510 → ~545 passed (+~35)**, 회귀 0건. 태그 `v0.6-earnings-event-pipeline`.

### Phase C — `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + Engine 통합

- [x] `app/analysis/score_producers.py` — `RealFundamentalScoreProducer` 신규. 기존 `ScoreProducerInterface` composition 패턴 유지, fallback 이 news/supply/earnings/ai 를 처리하고 fundamental_score 만 `FundamentalSnapshotRepository.get_latest_by_symbol` 기반 real 화
- [x] `app/analysis/score_producers.py` — `RealEarningsScoreProducer` 신규. 기존 `ScoreProducerInterface` composition 패턴 유지, fallback 이 news/supply/fundamental/ai 를 처리하고 holding 의 earnings_score 만 `EarningsEventRepository.get_latest_by_symbol` 기반 real 화
- [x] 산식 명시: `fundamental_score = clip(50 + ROE/PER/PBR/growth/debt/dividend rule adjustment, 0, 100)` + `earnings_score = clip(50 + (surprise_type + surprise_pct cap) * recency_multiplier, 0, 100)`. 데이터 부족 → 50
- [x] `app/decision/recommendation_engine.py` — 기존 `score_producer` 주입 구조를 유지하고 `_persist_candidate()` 에서 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 양쪽에 `fundamental_evidence` 기록
- [x] `app/decision/holding_check_engine.py` — 기존 `score_producer` 주입 구조를 유지하고 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 양쪽에 `earnings_evidence` 기록
- [x] **Safe-fields whitelist 강제** — evidence 빌더가 정량 지표 + event classification 만 노출. summary / source / source_file_path / extraction_method / 본문 필드 0건. 단위 테스트가 키 집합 명시 단언
- [x] `tests/unit/test_real_fundamental_earnings_score_producers.py` 신규 (fundamental: 데이터 0 → 50 / 좋은 재무 가산 / 나쁜 재무 감산 / debt penalty / growth / clamp / evidence whitelist, earnings: 데이터 0 → 50 / BEAT / MISS / MEET / surprise cap / old event decay / upcoming UNKNOWN / evidence whitelist)
- [x] `tests/integration/test_recommendation_engine.py` Phase C 보강 (real fundamental_score persist / fundamental_evidence in decision_log + data_snapshot / safe fields / ScoringEngine 본 weight 변경 0건 회귀)
- [x] `tests/integration/test_holding_check_engine.py` Phase C 보강 (real earnings_score in HoldingCheck / earnings_evidence in decision_log + data_snapshot / safe fields / Holding ScoringEngine 본 weight 변경 0건 회귀)
- [x] HoldingCheckEngine / ScoringEngine 본 weight 산식 변경 0건 — 기존 회귀 테스트 모두 그대로 통과
- 완료 기준: backend pytest 전체 회귀 + frontend vitest / build / e2e 재확인. 태그 `v0.6-fundamental-score`.

### Phase D — 프런트 통합 + 정합성 화면 ✅ 인수

- [x] `app/api/routes.py` — `GET /api/stocks/{symbol}/fundamentals?limit=` 신규 (read-only). FundamentalSnapshot 시계열, source_file_path 응답 0건
- [x] `app/api/routes.py` — `GET /api/stocks/{symbol}/earnings?limit=` 신규 (read-only). EarningsEvent 시계열, memo 500자 cap
- [x] `app/api/routes.py` — `GET /api/calendar/earnings?from_date=&to_date=&surprise_type=&limit=` 신규 (read-only). 다가오는 / 최근 캘린더 (default from_date=오늘)
- [x] `app/api/schemas.py` — `FundamentalSnapshotSchema` / `StockFundamentalsResponse` / `EarningsEventSchema` / `StockEarningsResponse` / `EarningsCalendarItemSchema` / `EarningsCalendarResponse` 신규 (6종)
- [x] `app/api/schemas.py` — `RecommendationItemSchema` 에 `fundamental_evidence` + `earnings_evidence` 필드 추가 (라우터 화이트리스트 적용). pre-v0.6 → null
- [x] `app/api/schemas.py` — `HoldingCheckSchema` 에 `earnings_evidence` + `fundamental_evidence` + `news_evidence` + `disclosure_risk_evidence` 필드 추가 (v0.5 Phase D 에서 이연된 holding evidence 노출 작업 흡수)
- [x] `app/api/routes.py` — `_whitelist_evidence(snapshot, key, allowed)` helper 신규 + `_FUNDAMENTAL_EVIDENCE_FIELDS` / `_EARNINGS_EVIDENCE_FIELDS` 화이트리스트 set 신규. 라우터 단계 defense-in-depth.
- [x] `tests/integration/test_api_routes.py` 보강 14 케이스 (fundamentals happy / empty / 404 / limit clamp, earnings happy / empty / 404, calendar happy + from/to + surprise_type filter, calendar default = today, calendar limit clamp, recommendation fundamental_evidence whitelist + pre-v0.6 → null, holding earnings_evidence whitelist + pre-v0.6 → null)
- [x] `frontend/src/api/types.ts` — `FundamentalSnapshot` / `StockFundamentalsResponse` / `EarningsEvent` / `StockEarningsResponse` / `EarningsCalendarItem` / `EarningsCalendarResponse` / `FundamentalEvidence` / `EarningsEvidence` 타입 신규
- [x] `frontend/src/hooks/useStockFundamentals.ts` 신규 (TanStack Query, staleTime 60_000)
- [x] `frontend/src/hooks/useStockEarnings.ts` 신규
- [x] `frontend/src/hooks/useEarningsCalendar.ts` 신규
- [x] `frontend/src/pages/StockDetail/FundamentalsCard.tsx` 신규 — 최근 fiscal period + history 시계열 (PER / PBR / ROE / 부채비율 / 배당수익률 / 매출 성장률 / 영업이익 성장률 + EPS / BPS)
- [x] `frontend/src/pages/StockDetail/EarningsCard.tsx` 신규 — 최근 이벤트 + history. BEAT/MEET/MISS/UNKNOWN tone-color badge + surprise_pct + actual vs consensus
- [x] `frontend/src/pages/StockDetail/index.tsx` — Fundamentals + Earnings 카드 lg:grid-cols-2 추가
- [x] `frontend/src/pages/TodayReport/index.tsx` — "다가오는 실적 발표" `UpcomingEarningsCard` 추가 (useEarningsCalendar limit=5)
- [x] `frontend/src/pages/Recommendations/RecommendationsTable.tsx` — `fund evidence` + `earnings evidence` 두 cell 추가 (compact summary, null → "—")
- [x] `frontend/src/pages/StockDetail/index.tsx` `RecentHoldingChecksCard` — `earnings evidence` 컬럼 추가 (v0.5 에서 이연된 holding evidence 노출 일부 흡수)
- [x] `frontend/src/tests/mswServer.ts` — `/api/stocks/:symbol/fundamentals` / `/api/stocks/:symbol/earnings` / `/api/calendar/earnings` default 핸들러 3종 추가 (모두 빈 응답)
- [x] `frontend/src/tests/StockDetail.test.tsx` 보강 — Fundamentals 카드 happy/empty/error 3건 + Earnings 카드 happy/empty/error 3건 + recent holding check earnings_evidence cell 1건
- [x] `frontend/src/tests/Recommendations.test.tsx` 보강 — fund/earnings evidence cell happy + null fallback 케이스 + forbidden 필드 미노출 단언
- [x] `frontend/src/tests/TodayReport.test.tsx` 보강 — UpcomingEarnings happy + empty 2건
- [x] `frontend/e2e/fixtures/apiMocks.ts` — `STOCK_FUNDAMENTALS_005930` / `STOCK_EARNINGS_005930` / `EARNINGS_CALENDAR` fixture + 라우터 패턴 추가
- [x] `frontend/e2e/dashboard.spec.ts` — Recommendations evidence cell 단언 보강 + StockDetail Fundamentals + Earnings 카드 + Today UpcomingEarnings 3건 추가 (e2e 11 → 13)
- [x] 완료 기준: backend pytest **544 → 558 passed (+14)**, frontend vitest **68 → 77 passed (+9)**, e2e **11 → 13 passed (+2)**, build 그린 (`tsc --noEmit && vite build`), 회귀 0건. source_file_path 0건 노출 가드 (`_assert_no_source_file_path`). ScoringEngine 본 weight 변경 0건. 태그 `v0.6-frontend-fundamentals`.

### Phase E — v0.6 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.6.md` 신규 (산출물 / 검증 / 안전 정책 / 한계 / v0.7 후보 / 운영 가이드 / 누적 태그)
- [x] `RELEASE_NOTES_v0.6.md` 안전 정책 — Fundamental/Earnings 본문 paragraph 미저장 / 자동 fetch default OFF / DART API 자동 호출 0건 / source_file_path 미노출 / Evidence whitelist 명시
- [x] `README.md` 상단 마감 배너 v0.5 → v0.6 갱신 + 누적 태그 라인 + 저작권·데이터 정책 한 단락 + §1 누적 기능 v0.6 항목 + §2 제외 범위 v0.6 정책 + §4 문서 표 + §6 누적 사이클 / 영역 표 + §11 회귀 기준선 (481 → 558)
- [x] `PROJECT_STATUS.md` §0 v0.6 진행 → v0.6 마감 in-place 갱신, §0-1 (이전 v0.6 진행 스냅샷) / §0-2 v0.5 / §0-3 v0.4 / §0-4 v0.3 / §0-5 v0.2 / §0-6 v0.1 으로 강등
- [x] `TASKS.md` v0.6 phase 모두 [x] + v0.6 전체 마감 헤더
- [x] `ROADMAP.md` v0.6 행 마감 표시 + v0.6 phase 표 ✅ + v0.7 후보 정리
- [x] `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `INTEGRATION_RUNBOOK.md` / `DB_SCHEMA.md` 정합성 점검 + 마감 시점 헤더 갱신
- [x] backend pytest + frontend vitest + e2e + build 4 게이트 그린 (재확인) — **558 / 77 / 13 / build**
- [ ] tag `v0.6-final` + push (운영자 수동)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.6 붙여넣기 (UI 작업).

## v0.7 — Strategy & Backtest Foundation ✅ 마감 (2026-05-06)

기준선: `v0.6-final` (HEAD `e729d60`). 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0007` 참조.

**v0.7 핵심 목표**

v0.1~v0.6 누적된 추천 판단 축 (technical / report / theme / news / disclosure /
fundamental / earnings + risk_penalty) 위에 **`StrategyInterface` ABC + 룰 기반
전략 2~3종 + `BacktestEngine` + 비용 모델 + 시장 국면별 분리 + 백테스트 결과
read-only 화면** 을 도입한다. 다음 자연 질문 "이 추천이 돈이 되는가?" 에 답하기
위한 단계 — `recommendation_results` (1·3·5·20일) 가 이미 적재 중이라 즉시
활용 가능. 자동매매 진입 (Future Backlog) 전 반드시 거쳐야 할 검증 cycle.

**v0.7 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.6 일관 정책 유지)
- ❌ 인증 / Watchlist (v0.8 후보로 묶음)
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 의 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (Strategy / Backtest 검증 후 v0.10+ 검토)
- ❌ ScoringEngine 본 weight 변경 — RecommendationEngine / HoldingCheckEngine 산식 0건 변경
- ❌ HoldingCheckEngine 산식 변경
- ❌ LLM 자동 전략 생성 — Phase A 는 룰 기반만, LLM 보강은 v0.8+ 후보
- ❌ Alembic 도입 (v0.7 신규 테이블 2개 추가 후 v0.8 권장)
- ❌ 실 비용 / 세금 데이터 fetch — `CostModel` 은 placeholder constant 만, 실 broker fee schedule 은 v0.8+ 후보
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.8+ 후보
- ❌ 백테스트 결과 자동 텔레그램 알림 — read-only 화면만, 자동 발송 0건

### Phase A — Strategy interface + 룰 기반 전략 정의 ✅ 인수

- [x] `app/strategy/__init__.py` 신규 — 패키지 진입점 + 공개 심볼 export (`StrategyInterface` / `StrategySignal` / `ScoreSnapshot` / 3 룰 기반 전략 / 액션 상수)
- [x] `app/strategy/interfaces.py` — `StrategySignal` dataclass (frozen, `action` STRATEGY_ACTIONS 검증 + `confidence` 자동 [0,1] clamp) + `ScoreSnapshot` dataclass (frozen, 14 필드 모두 nullable + `risk_flags` default_factory + `SCORE_SNAPSHOT_FIELDS` frozenset) + `StrategyInterface` ABC (`name` / `version` 추상 property + `evaluate` 추상 method)
- [x] `app/strategy/rule_based.py` — `TopGradeStrategy` (S/A → BUY, D → AVOID, conf 0.9/0.75/0.5) + `HighScoreStrategy` (≥75 → BUY linear ramp, ≤35 → AVOID linear ramp) + `MultiSignalStrategy` (HIGH risk / RISK_DISCLOSURE / total≤35 → AVOID; total≥65 + fundamental≥60 + news≥50 + earnings≥50-or-None → BUY; evidence 기반 +0.10 BEAT / +0.05 news skew boost)
- [x] `tests/unit/test_rule_based_strategies.py` 신규 — **56 케이스**:
  - StrategySignal action validation (1) + 정상 액션 parametrize (3) + confidence clamp (7) + non-Decimal coercion (1)
  - ScoreSnapshot 최소 생성 (1) + order field 부재 가드 (1) + risk_flags 인스턴스 격리 (1)
  - StrategyInterface ABC 직접 인스턴스화 차단 (1) + 3 구현체 호환 가드 (1)
  - TopGrade S/A → BUY (parametrize 2) + D → AVOID (1) + B/C/Z/empty/None → PASS (parametrize 5) + lowercase normalize (1)
  - HighScore action threshold parametrize (10) + score=None → PASS (1) + confidence range guard (1)
  - MultiSignal happy BUY (1) + earnings None BUY (1) + HIGH risk AVOID (1) + RISK_DISCLOSURE flag AVOID (1) + low total AVOID (1) + mid total PASS (1) + 3 component threshold PASS (3) + BEAT boost (1) + news skew boost (1) + combined boost clamp (1) + non-positive skew no boost (1) + missing evidence dict (1) + malformed news_evidence (1)
  - 3 전략 × 빈 snapshot → PASS 가드 (parametrize 3)
- 안전 범위: KIS / DART / Telegram 호출 0건, scheduler job 0건, API 라우터 0건, frontend 변경 0건, DB 모델 변경 0건, 자동매매/주문 코드 0건. `ScoreSnapshot` 에 quantity / price / account / broker / order_type / side 필드 부재 (단언으로 가드)
- 완료 기준: backend pytest **558 → 614 passed (+56)**, 회귀 0건. 태그 `v0.7-strategy-interface`.

### Phase B — Backtest engine + recommendation_results 활용 ✅ 인수

- [x] `app/db/models.py` — `BacktestRun` 신규 (26번째 테이블, 25 컬럼: signal/buy/avoid/pass count + win_rate_1d/3d/5d/20d + avg_return_1d/3d/5d/20d + max_drawdown + status + config_json + summary_json + TimestampMixin) + `BacktestResult` 신규 (27번째 테이블, 17 컬럼). FK + Unique + Cascade 정책 명시
- [x] `app/data/repositories/backtest_runs.py` 신규 — `BacktestRunRepository` (create / get_by_id / list_recent / list_by_strategy / mark_finished / mark_failed) + `STATUS_DRY_RUN` / `STATUS_SUCCESS` / `STATUS_FAILED` 상수
- [x] `app/data/repositories/backtest_results.py` 신규 — `BacktestResultRepository` (create / bulk_insert / list_by_run / list_by_symbol / aggregate_by_run / aggregate_by_signal_action)
- [x] `app/data/repositories/__init__.py` — 두 repository export 추가 + `__all__` 갱신
- [x] `app/strategy/registry.py` 신규 — `STRATEGY_REGISTRY` dict + `KNOWN_STRATEGIES` tuple + `UnknownStrategyError` + `get_strategy(name)` lookup. CLI 에서 strategy name 으로 선택 가능
- [x] `app/strategy/__init__.py` — registry 심볼 re-export
- [x] `app/backtest/__init__.py` 신규
- [x] `app/backtest/engine.py` — `BacktestEngine` (`run(strategy, start_date, end_date, dry_run, limit, run_date)`) + `BacktestRunSummary` dataclass (`as_dict()` 포함) + `build_score_snapshot(rec, snapshot)` helper + `BUY_ONLY_METRICS_NOTE` 상수. 산식: signal/buy/pass/avoid count, BUY 신호만 대상으로 win_rate / avg_return (Decimal quantize 0.0001), max_drawdown = min(BUY rows.max_drawdown), missing_result_count_per_horizon dict
- [x] `scripts/run_backtest.py` 신규 — argparse CLI. `--strategy` 필수 (choices=KNOWN_STRATEGIES), `--from-date` / `--to-date` (YYYY-MM-DD) / `--commit` (없으면 dry-run) / `--db-url` / `--limit`. `_print_summary` 가 horizon 별 win_rate / avg_return + missing_result_count + backtest_run_id 출력
- [x] `tests/integration/test_backtest_repositories.py` 신규 — **20 케이스** (ORM metadata 2 + BacktestRunRepository 7 + BacktestResultRepository 6 + Unique constraint 2 + cascade delete + relationship 2)
- [x] `tests/integration/test_backtest_engine.py` 신규 — **18 케이스** (build_score_snapshot 3 + dry-run/commit 2 + 3 strategies × happy 3 + metrics 4 + date filter 1 + CLI 4)
- [x] `DB_SCHEMA.md` §26 / §27 신규 — backtest_runs + backtest_results 컬럼 + Unique + Index + Cascade + BUY-only 산식 정책 + Alembic 도입 후보 명시
- [x] `INTEGRATION_RUNBOOK.md` §16 신규 — 전략 목록 / dry-run / commit / 결과 조회 / BUY-only 산식 정책 / 안전 가드
- 안전 범위: 라우터 0건, frontend 0건, scheduler 0건, KIS / DART / RSS / Telegram 외부 호출 0건. `app/backtest/` + `app/strategy/` 어디에도 `requests` / `httpx` / `aiohttp` / `urllib` / `BrokerInterface` import 0건. backtest_results 에 broker / 주문 / 계좌 / 가격 / 수량 컬럼 부재
- 완료 기준: backend pytest **614 → 652 passed (+38)**, 회귀 0건. 태그 `v0.7-backtest-engine`.

### Phase C — 시장 국면별 + 비용 모델 ✅ 인수

- [x] `app/backtest/cost_model.py` 신규 — `CostModel` (frozen dataclass): buy_fee 0.015% / sell_fee 0.015% / sell_tax 0.20% / slippage 0.10% / total_cost 0.33% / `apply(raw_return)` (raw_return-percent에 total_cost×100 빼기, None 입력 None 반환) / `version` 필드 + `COST_MODEL_VERSION = "constant-v1"` 상수
- [x] `app/backtest/regime_split.py` 신규 — `assign_regime(session, signal_date, market="KOSPI") -> str | None` (at-or-before 가장 최근 `MarketRegime.regime`) + `display_bucket` (None → `UNCLASSIFIED`) + `UNCLASSIFIED_BUCKET` / `DEFAULT_MARKET` 상수
- [x] `app/db/models.py` `BacktestResult` 보강 — `cost_adjusted_return_5d` Numeric(12,4) nullable + `regime` String(32) nullable index. Phase B 의 신규 테이블 정의에 흡수되므로 Phase B + Phase C 단일 cycle 마이그레이션 (운영 DB 별도 ALTER 안내는 DB_SCHEMA §27)
- [x] `app/data/repositories/backtest_results.py` `aggregate_by_regime` 추가 — `{regime_or_unclassified: count}` GROUP BY, NULL → `unclassified_label` 폴딩
- [x] `app/backtest/engine.py` 보강 — `BacktestEngine.__init__` 에 `cost_model` + `regime_market` 옵셔널 파라미터. `run()` 에서 BUY 신호만 cost_adjusted_return_5d 계산 (PASS/AVOID는 NULL), 모든 row 에 regime 할당. `_aggregate` 에 `cost_adjusted_avg_return_5d` 추가. `_build_regime_breakdown` helper (BUY rows GROUP BY regime → win_rate_5d / avg_return_5d / cost_adjusted_avg_return_5d, buy_count desc 정렬). `BacktestRunSummary` 에 `cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` / `regime_breakdown: list[RegimeBreakdownEntry]` 필드 + `summary_json` / `config_json` 에 동일 데이터 반영
- [x] `app/backtest/__init__.py` — 신규 심볼 export
- [x] `scripts/run_backtest.py` — `_print_summary` 에 `cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` / `regime_breakdown` (regime / buy / win_rate_5d / avg_return_5d / cost_adj) 출력 추가. 기존 출력 유지
- [x] `tests/unit/test_cost_model.py` 신규 — **9 케이스** (version 상수 / total_cost = 0.33% / apply 양수·음수·zero·None / custom 비율 / custom version / frozen dataclass)
- [x] `tests/integration/test_backtest_regime.py` 신규 — **12 케이스** (assign_regime 4: exact / at-or-before fallback / 사전 데이터 부재 None / market 필터; engine 8: dry-run summary 노출 / NULL → UNCLASSIFIED bucket / commit 시 컬럼 영속 / PASS/AVOID는 cost_adjusted NULL but regime 할당 / regime_breakdown GROUP BY + 정렬 / aggregate_by_regime / NULL bucket 폴딩 / custom CostModel 전파)
- 안전 범위: 라우터 0건, frontend 0건, 외부 호출 0건. `app/backtest/` 어디에도 `requests` / `httpx` / `aiohttp` / `urllib` / KIS / DART / Telegram / `BrokerInterface` import 0건 (grep 검증). ScoringEngine 본 weight 변경 0건
- 완료 기준: backend pytest **652 → 673 passed (+21)**, 회귀 0건. 태그 `v0.7-backtest-cost-regime`.

### Phase D — read-only API 3종 + 프런트 백테스트 화면 ✅ 인수

- [x] `app/api/routes.py` — `GET /api/strategies` 신규 (registry 기반 / DB 0건 / docstring 첫 줄을 description 으로 노출)
- [x] `app/api/routes.py` — `GET /api/backtest/runs?strategy=&limit=` 신규 (목록, run_date desc 정렬, `summary_json` 의 cost/regime 메타를 응답 최상위로 추출)
- [x] `app/api/routes.py` — `GET /api/backtest/runs/{run_id}` 신규 (상세 + results + regime_breakdown + cost_model_version + total_cost + notes). 404 정책
- [x] `app/api/schemas.py` — `StrategySchema` / `StrategiesResponse` / `BacktestRunSchema` / `BacktestRunsResponse` / `BacktestResultSchema` / `RegimeBreakdownSchema` / `BacktestRunDetailResponse` 7 신규. Decimal-as-string 패턴 유지
- [x] `app/data/repositories/backtest_results.py` `create()` 시그니처에 `cost_adjusted_return_5d` + `regime` keyword 추가 (Phase C 컬럼 호환성). 기존 호출자 회귀 0건 — keyword 만 추가
- [x] `tests/integration/test_api_routes.py` 보강 9 케이스 (`/api/strategies` 3 룰 노출 + version + description / `/api/backtest/runs` empty / happy 정렬 + cost meta / strategy filter / limit clamp / detail happy + regime breakdown + cost_adjusted / 404 / forbidden 키 (broker / quantity / order_type / source_file_path) 미노출 가드 / 모든 응답 `_assert_no_source_file_path`)
- [x] `frontend/src/api/types.ts` — `StrategyItem` / `StrategiesResponse` / `BacktestRunItem` / `BacktestRunsResponse` / `BacktestResultItem` / `RegimeBreakdownItem` / `BacktestRunDetailResponse` 7 신규
- [x] `frontend/src/hooks/useStrategies.ts` 신규 (staleTime 5분)
- [x] `frontend/src/hooks/useBacktestRuns.ts` 신규 (staleTime 60초, strategy/limit 파라미터)
- [x] `frontend/src/hooks/useBacktestRunDetail.ts` 신규 (staleTime 60초, runId enabled gate)
- [x] `frontend/src/pages/Backtest/index.tsx` 신규 — 10번째 화면. 상단 `StrategyListSection` (3 카드 grid) + 중단 `RunsTableSection` (전략 filter radiogroup + 클릭 가능한 run 표) + 하단 `RunDetailSection` (선택 시 노출, regime_breakdown 표 + 신호 row 표 + cost_model_version / total_cost / BUY-only note). `ActionBadge` (BUY/PASS/AVOID tone-color)
- [x] `frontend/src/components/layout/Sidebar.tsx` — `FlaskConical` 아이콘 import + 8번째 위치에 `백테스트 (β)` 메뉴 추가 (Sidebar 9 → 10 메뉴, 주석 갱신)
- [x] `frontend/src/router.tsx` — `BacktestPage` lazy import + `/backtest` route 추가
- [x] `frontend/src/tests/mswServer.ts` — `/api/strategies` / `/api/backtest/runs` / `/api/backtest/runs/:runId` 3 default 핸들러 (모두 빈 응답 / 404)
- [x] `frontend/src/tests/Backtest.test.tsx` 신규 — **7 케이스** (happy / empty / runs 500 / detail 클릭 시 로드 + regime + BUY-only note / detail 500 / strategy filter URL 변경 / 자동매매·order UI + forbidden 토큰 미노출)
- [x] `frontend/e2e/fixtures/apiMocks.ts` — `STRATEGIES` + `BACKTEST_RUNS_LIST` + `BACKTEST_RUN_DETAIL_42` fixture + 라우터 패턴 추가
- [x] `frontend/e2e/dashboard.spec.ts` — sidebar nav 테스트에 `백테스트 (β)` 추가 + 신규 `Backtest screen surfaces strategies + runs + detail` e2e (전략 3종 + run 행 + 클릭 시 detail + regime + cost_model + forbidden 토큰 가드 + raw JSON `order_type`/`quantity` 0건) + `no automation / order UI` 테스트의 targets 에 `/backtest` 추가. e2e 13 → 14 (+1)
- 안전 범위: POST 0건, 외부 호출 0건, scheduler 0건, 자동매매 0건. BacktestEngine 산식 / CostModel / regime_split / DB 모델 변경 0건 (read-only API + UI 만 추가)
- 완료 기준: backend pytest **673 → 682 passed (+9)**, frontend vitest **77 → 84 passed (+7)**, e2e **13 → 14 passed (+1)**, build 그린, 회귀 0건. source_file_path / 주문 관련 필드 0건 노출 가드. 태그 `v0.7-frontend-backtest`.

### Phase E — v0.7 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.7.md` 신규 (산출물 / 검증 / 안전 정책 / 한계 / v0.8 후보 / 운영 가이드 / 누적 태그)
- [x] `RELEASE_NOTES_v0.7.md` 안전 정책 — 자동매매 부재 / POST 미도입 / ScoringEngine 본 weight 변경 0건 / 비용 모델 placeholder 명시 / cost_model_version 추적 / `source_file_path` / `broker` / `account` / `quantity` / `order_price` / `order_type` / `side` 미노출 / 외부 API 자동 호출 0건
- [x] `README.md` 상단 마감 배너 v0.6 → v0.7 갱신 + 누적 태그 라인 (v0.7-strategy-interface → v0.7-backtest-engine → v0.7-backtest-cost-regime → v0.7-frontend-backtest → v0.7-final 예정) + §1 누적 기능 v0.7 항목 4종 (StrategyInterface / BacktestEngine / CostModel / `/backtest` 화면) + §2 제외 범위 v0.7 정책 5건 + §4 문서 표 + §6 누적 사이클 / 영역 표 (Strategy/Backtest layer 추가) + §11 회귀 기준선 (558 → 682)
- [x] `PROJECT_STATUS.md` §0 v0.7 진행 → v0.7 마감 in-place 갱신, §0-1 (이전 v0.7 진행 스냅샷) / §0-2 v0.6 / §0-3 v0.6 진행 / §0-4 v0.5 / §0-5 v0.4 / §0-6 v0.3 / §0-7 v0.2 / §0-8 v0.1 으로 강등
- [x] `TASKS.md` v0.7 phase 모두 [x] + v0.7 전체 마감 헤더 + v0.8+ Backlog 정리
- [x] `ROADMAP.md` v0.7 행 마감 표시 + v0.7 phase 표 ✅ + v0.8 후보 정리
- [x] `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `INTEGRATION_RUNBOOK.md` / `DB_SCHEMA.md` 정합성 점검 + 마감 시점 헤더 갱신
- [x] backend pytest + frontend vitest + e2e + build 4 게이트 그린 (재확인) — **682 / 84 / 14 / build**
- [ ] tag `v0.7-final` + push (운영자 수동)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.7 붙여넣기 (UI 작업).

## v0.8 — User & Migration Foundation ✅ 마감 (2026-05-06)

기준선: `v0.7-final` (HEAD `1f5b01f`). 자세한 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0008` 참조.

**v0.8 핵심 목표**

v0.1 ~ v0.7 동안 일관 유지된 read-only 정책의 **첫 변경 cycle**. 27 테이블
시점에 **Alembic baseline** 을 도입하고, 단일 사용자 인증 기반 (`AUTH_ENABLED`
토글 + JWT) 위에 **Watchlist 도메인** 을 통해 POST/DELETE 라우터를 처음
도입한다. 자동매매 / 실주문 / Broker / 실 외부 API / LLM 은 **여전히 0건**
— Watchlist 와 인증에 한정된 POST 첫 도입이다. ScoringEngine /
HoldingCheckEngine 본 weight 변경 0건 정책 그대로.

**v0.8 에서 절대 하지 않을 것**

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ Broker 구현 (`BrokerInterface` placeholder 유지)
- ❌ POST 라우터 확장 — `POST /api/auth/login` + `POST/DELETE /api/watchlists/...` **2 도메인만**
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (v0.10+)
- ❌ ScoringEngine / HoldingCheckEngine 본 weight 변경
- ❌ LLM 자동 전략 생성 / 자동 분석
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.9 후보
- ❌ Watchlist 자동 텔레그램 / 가격 알림 — 알림 시스템 변경 0건
- ❌ 다중 사용자 / SaaS / RBAC — 단일 admin user 만
- ❌ OAuth / SSO — 단일 username/password + bcrypt + JWT 만
- ❌ Refresh token / token revocation — 24h JWT TTL + 재로그인만
- ❌ WebSocket / SSE — 폴링 그대로
- ❌ Recommendations / Backtest / Today 산식 변경 — 즐겨찾기는 표시/필터만

### Phase A — Alembic baseline 도입 ✅ 인수

- [x] `alembic.ini` 신규 — script_location / file_template / `path_separator = os` / sqlalchemy.url 비워둠 (env.py 가 Settings 에서 결정)
- [x] `alembic/env.py` 신규 — `target_metadata = app.db.models.Base.metadata` + `_resolve_database_url()` 가 `-x url=...` > `alembic.ini` > `Settings.effective_database_url` 순으로 해석. SQLite 시 `render_as_batch=True`. `compare_type=True` + `compare_server_default=True`. offline / online 모두 지원
- [x] `alembic/script.py.mako` 신규 (표준 템플릿)
- [x] `alembic/versions/0001_baseline_v0_7.py` 신규 — autogenerate 로 생성한 27 테이블 baseline (`op.create_table()` 27건 + 인덱스 / FK / Unique 모두 포함, `op.drop_table()` 27건 역순). Phase A 정책 명시 docstring (신규 DB / stamp / 운영 절차 / autogenerate 검증 origin)
- [x] `scripts/migrate.py` 신규 — `alembic` thin wrapper (`current` / `history` / `heads` / `upgrade --to` / `downgrade --to` / `stamp --revision` / `offline-sql --to`). `--db-url` override + `--ini` 경로 옵션
- [x] `tests/integration/test_alembic_migration.py` 신규 — **16 케이스** (head 단일 / upgrade head + 27 테이블 + spot-check 9 / alembic_version 스탬프 / compare_metadata diff 0건 / stamp 시나리오 (Base.metadata.create_all 후) / downgrade base / offline-sql + DB 미생성 / parametrize spot-check 9). 모든 케이스가 `tmp_path` 임시 DB 만 사용
- [x] `pyproject.toml` — `alembic>=1.13,<2.0` 추가 (psycopg2-binary 와 SQLAlchemy 사이)
- [x] `.github/workflows/ci.yml` — backend 잡 내부 `alembic -x url=sqlite:///$RUNNER_TEMP/ci_alembic_smoke.db upgrade head` step 추가 (pytest 직전 fast signal)
- [x] `INTEGRATION_RUNBOOK.md` §17 신규 — 8 sub-section (alembic 골격 / 신규 DB 초기화 / 기존 운영 DB stamp / Phase B 후속 revision 추가 / 운영 DB upgrade / 실패 롤백 원칙 / Settings 정합성 / 안전 가드)
- [x] `DB_SCHEMA.md` 상단 — "v0.8 부터 Alembic 으로 관리한다" 명시 + baseline revision 경로 + INTEGRATION_RUNBOOK §17 link + CI compare_metadata 가드 안내
- [x] `TESTING.md` §6.16 신규 — Alembic migration 테스트 16 케이스 상세 + 안전 가드 + 회귀 기준 (682 → 698)
- 안전 범위: 라우터 0건, frontend 0건, 신규 테이블 0건 (baseline 만), 외부 호출 0건. 운영 DB 변경 0건 (운영자 수동 실행 시점에만 적용). DB 모델 / ScoringEngine / RecommendationEngine / HoldingCheckEngine / BacktestEngine / CostModel / regime_split 변경 0건. POST / PUT / DELETE 라우터 0건
- 완료 기준: backend pytest **682 → 698 passed (+16)**, autogenerate diff 0건 단언 통과, alembic upgrade head + downgrade base + stamp 시나리오 모두 그린, 회귀 0건. 태그 `v0.8-alembic-baseline`.

### Phase B — 단일 사용자 인증 기반 ✅ 인수

- [x] `app/db/models.py` — `User` 신규 (28번째 테이블, username unique + scrypt password_hash + is_active + is_admin + last_login_at) + `LoginAuditLog` 신규 (29번째 테이블, username + user_id FK + event_type + source_ip_hash + user_agent_hash + 복합 index 2종)
- [x] `app/db/__init__.py` — User + LoginAuditLog re-export
- [x] `app/data/repositories/users.py` 신규 — `UserRepository` (create / get_by_id / get_by_username / set_last_login / deactivate)
- [x] `app/data/repositories/login_audit_logs.py` 신규 — `LoginAuditLogRepository` (create / list_recent / list_by_username / list_by_user) + `EVENT_LOGIN_SUCCESS` / `EVENT_LOGIN_FAILED` / `EVENT_LOGOUT` 상수 + event_type validation
- [x] `app/data/repositories/__init__.py` — UserRepository + LoginAuditLogRepository export 추가
- [x] `app/auth/__init__.py` 신규 — public surface (`PasswordHasher` / `JwtIssuer` / `AuthService` / `hash_for_audit` / `validate_auth_settings` / `AuthenticatedUser` / `LoginResult` / `MissingSecretError` / `InvalidTokenError` / `ExpiredTokenError`)
- [x] `app/auth/security.py` 신규 — scrypt 기반 `PasswordHasher` (`hash_password` / `verify_password` + malformed hash 입력 raise 0건) + `JwtIssuer` (HS256, issue/decode + ExpiredTokenError + InvalidTokenError + MissingSecretError) + `hash_for_audit` (SHA256 hex, None/empty → None) + `AuthService` (login → LOGIN_SUCCESS/FAILED audit + set_last_login + token; record_logout → LOGOUT audit) + `validate_auth_settings` (AUTH_ENABLED=true → JWT_SECRET 필수)
- [x] `app/auth/dependencies.py` 신규 — `get_current_user` (AUTH_ENABLED=false 시 dev fallback user_id=1, AUTH_ENABLED=true 시 Bearer token 검증) + `require_auth` (Phase C Watchlist 보호 라우터용) + ephemeral per-process secret (AUTH_ENABLED=false + JWT_SECRET 미설정 시 dev fallback) + `extract_client_ip` (X-Forwarded-For → request.client.host)
- [x] `app/api/auth_routes.py` 신규 — `POST /api/auth/login` (첫 POST, generic 401 + LoginAuditLog) + `POST /api/auth/logout` + `GET /api/auth/me` (AUTH_ENABLED=false 시 fallback / true 시 user 조회 + deactivate 시 401). LoginRequest / LoginResponse / LoginUser / LogoutResponse / MeResponse Pydantic schema 자체 정의
- [x] `app/api/__init__.py` — auth_router export
- [x] `app/main.py` — auth_router include + `validate_auth_settings(settings)` startup 호출 (AUTH_ENABLED=true + JWT_SECRET 미설정 시 startup 거부)
- [x] `app/config/settings.py` — `auth_enabled` (default false) + `jwt_secret` (default None) + `jwt_algorithm` (default HS256) + `jwt_expires_minutes` (default 1440) + `password_hash_n` / `r` / `p` (scrypt 비용 파라미터) 추가
- [x] `scripts/create_admin.py` 신규 — argparse CLI (`--username` / `--password` / `--db-url` / `--no-admin` / `--update-if-exists`) + ADMIN_PASSWORD env var + interactive prompt + 평문 / hash 출력 0건
- [x] `alembic/versions/0002_auth_foundation.py` 신규 — autogenerate 결과 (users + login_audit_logs op.create_table + 5 인덱스) + Phase B 정책 docstring (down_revision=`0001_baseline_v0_7`)
- [x] `pyproject.toml` — `PyJWT>=2.8,<3.0` 추가 (bcrypt 는 MSYS2 UCRT64 wheel 부재로 stdlib `hashlib.scrypt` 채택, comment 명시)
- [x] `tests/unit/test_auth_security.py` 신규 — **26 케이스**: PasswordHasher (8 + 5 parametrize), JwtIssuer (5), hash_for_audit (3 + 3 parametrize), validate_auth_settings (4)
- [x] `tests/integration/test_auth_repositories.py` 신규 — **15 케이스**: UserRepository (7 — create / get_by_username / get_by_id / unique / set_last_login / deactivate / admin), LoginAuditLogRepository (8 — success / unknown user / event_type validation / **평문 IP/UA 미저장** / list_recent / list_by_username / list_by_user)
- [x] `tests/integration/test_auth_routes.py` 신규 — **14 케이스**: AUTH_ENABLED=false (5) / AUTH_ENABLED=true + token (8) / 기존 read-only 라우터 OPEN 가드 (1)
- [x] `tests/integration/test_create_admin_cli.py` 신규 — **5 케이스**: 정상 생성 / 중복 거부 / `--update-if-exists` / `--no-admin` / 빈 password
- [x] `tests/integration/test_alembic_migration.py` 갱신 — `HEAD_REVISION = "0002_auth_foundation"` / `EXPECTED_TABLE_COUNT = 29` / spot-check 에 users + login_audit_logs 추가. `compare_metadata` diff 0건 단언 유지
- [x] `API_SPEC.md` §17 신규 — auth endpoint 3개 + 정책 (generic 401 / password_hash 미노출 / 평문 IP/UA 미저장 / 기존 read-only 보호 안 함) + 금지 API 갱신
- [x] `DB_SCHEMA.md` §28 / §29 신규 — User + LoginAuditLog 컬럼 + Index + Unique + 정책
- [x] `INTEGRATION_RUNBOOK.md` §18 신규 (6 sub-section: admin 계정 생성 / AUTH_ENABLED=true 전환 / login smoke / audit log 확인 / 운영 이슈 / 안전 가드)
- [x] `TESTING.md` §6.17 신규 — 5 sub-section (Unit 26 / Repo 15 / API 14 / CLI 5 / Alembic head 갱신) + 회귀 기준 698 → 760
- 안전 범위: 자동매매 0건, 실 외부 API (KIS / DART / RSS / Telegram) 호출 0건, scheduler job 0건, ScoringEngine / RecommendationEngine / HoldingCheckEngine / BacktestEngine / CostModel / regime_split 변경 0건. 기존 read-only GET 라우터 동작 변경 0건 (AUTH_ENABLED=true 모드에서도 그대로 OPEN). POST 라우터 5건 → **3건만** (`/api/auth/login` + `/api/auth/logout` + `/api/auth/me` 는 GET 이므로 POST 2건). Watchlist 라우터 0건 (Phase C). 평문 IP / 평문 user agent / 평문 password 저장 0건
- 완료 기준: backend pytest **698 → 760 passed (+62)** (1 deselected 그대로), `AUTH_ENABLED=false` 모드에서 기존 v0.7 회귀 테스트 100% 그대로 통과, alembic head = `0002_auth_foundation`, compare_metadata diff 0건. 태그 `v0.8-auth-foundation`.

### Phase C — Watchlist DB / API ✅ 인수

- [x] `app/db/models.py` — `Watchlist` 신규 (30번째 테이블, user_id FK + name + is_default + Unique(user_id, name) + User.watchlists relationship cascade) + `WatchlistItem` 신규 (31번째 테이블, watchlist_id FK ON DELETE CASCADE + symbol(32) index + memo(500) nullable + Unique(watchlist_id, symbol) + Watchlist.items cascade="all, delete-orphan")
- [x] `app/db/__init__.py` — Watchlist + WatchlistItem re-export
- [x] `app/data/repositories/watchlists.py` 신규 — `WatchlistRepository` (create / get_by_user_and_id / get_default_for_user / get_or_create_default / list_by_user / rename / set_default / delete) + 단일 default invariant 강제 (`_clear_default_for_user`) + ownership-scoped 조회만 노출 + `DEFAULT_WATCHLIST_NAME = "기본"`
- [x] `app/data/repositories/watchlist_items.py` 신규 — `WatchlistItemRepository` (add_item / update_memo / remove_item / get_item / list_items / list_symbols / exists) + `normalize_symbol` (trim + UPPER + None / empty 거부) + `MAX_MEMO_LENGTH = 500` + `_validate_memo` defensive ValueError
- [x] `app/data/repositories/__init__.py` — WatchlistRepository + WatchlistItemRepository import + export 추가
- [x] `app/api/watchlist_routes.py` 신규 — 5 라우터 (`GET /api/watchlists` + `GET /api/watchlists/{id}` + `POST /api/watchlists` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`). 모두 `require_auth` 가드 + `_load_owned_watchlist` (cross-user 시 404). Pydantic schema 자체 정의 (WatchlistItemSchema / WatchlistSchema with item_count / WatchlistDetailSchema / WatchlistsResponse / CreateWatchlistRequest with name validator / CreateWatchlistItemRequest with symbol normalize + memo length validator / StatusResponse). symbol 은 stocks 테이블 존재 여부 확인 후 추가 (404 if missing)
- [x] `app/api/__init__.py` — watchlist_router export 추가
- [x] `app/main.py` — watchlist_router include
- [x] `alembic/versions/0003_watchlist.py` 신규 — autogenerate 결과 (watchlists + watchlist_items op.create_table + 3 인덱스 + 2 unique constraint) + Phase C 정책 docstring (down_revision = `0002_auth_foundation`)
- [x] `tests/integration/test_watchlist_repositories.py` 신규 — **27 케이스**: normalize_symbol (4 parametrize + 2 edge), WatchlistRepository (10 — create / list_by_user 정렬 / get_default / get_or_create_default 멱등 / Unique IntegrityError / set_default demote / create+is_default demote / cross-user 격리 (get_by_user_and_id None) / list_by_user 격리 / cascade delete), WatchlistItemRepository (12 — symbol normalize / Unique 후 collide / 다른 watchlist 같은 symbol OK / memo limit / over / remove True/False / remove normalize / list_items / list_symbols / update_memo / **broker / account / quantity / order_* / 가격 컬럼 0건 단언**)
- [x] `tests/integration/test_watchlist_routes.py` 신규 — **19 케이스**: AUTH_ENABLED=false 12 (list / create + 중복 409 + 빈 name 422 + is_default 단일 invariant / detail + 404 / item create + symbol normalize + 중복 409 + unknown symbol 404 + memo over 422 / delete + path symbol normalize + 404 missing) / AUTH_ENABLED=true 4 (token 없음 401 + WWW-Authenticate Bearer / valid token 200 / **cross-user 404 (GET + POST + DELETE)** / **request body user_id 무시 (spoofing 가드)**) / 보안 3 (`_assert_no_forbidden_fields` recursive 스캔 — broker / account / quantity / order_* / source_file_path / password_hash / token / secret / jwt_secret / scrypt$ 0건)
- [x] `tests/integration/test_alembic_migration.py` 갱신 — `HEAD_REVISION = "0003_watchlist"` / `EXPECTED_TABLE_COUNT = 31` / spot-check 에 watchlists + watchlist_items 추가. `compare_metadata` diff 0건 단언 유지
- [x] `API_SPEC.md` §18 신규 — Watchlist 5 라우터 + 인증 정책 + cross-user 404 정책 + forbidden 필드 + 응답 schema 예시 + Phase C 한계 (PUT / DELETE watchlist / 가격 alert 보류)
- [x] `DB_SCHEMA.md` §30 / §31 신규 — Watchlist / WatchlistItem 컬럼 + Unique + Cascade + 정책 + 운영 마이그레이션 안내
- [x] `INTEGRATION_RUNBOOK.md` §19 신규 (6 sub-section: 신규 환경 부트스트랩 / dev smoke / prod smoke / 보안 회귀 점검 / cross-user 격리 점검 / Phase C 안전 가드)
- [x] `TESTING.md` §6.18 신규 — Repository 27 + API 19 + Alembic head 갱신 + 회귀 기준 (760 → 808)
- 안전 범위: Watchlist 외 도메인 POST/PUT/DELETE 0건 (Phase C 도입 라우터 = Watchlist 5건만). 자동매매 / 실 외부 API 호출 / scheduler 0건. ScoringEngine / RecommendationEngine / HoldingCheckEngine / BacktestEngine / CostModel / regime_split 변경 0건. 기존 read-only GET 라우터 동작 변경 0건. WatchlistItem ORM 컬럼에 broker / account / quantity / order_* / 가격 필드 0건 (회귀 단언). request body 의 `user_id` 자동 drop (spoofing 가드)
- 완료 기준: backend pytest **760 → 808 passed (+48)** (1 deselected 그대로), alembic head = `0003_watchlist`, compare_metadata diff 0건. 태그 `v0.8-watchlist-api`.

### Phase D — Watchlist 프런트 + Today / StockDetail 통합 ✅ 인수

- [x] `frontend/src/api/client.ts` — `setAuthToken` / `getAuthToken` / `removeAuthToken` / `buildAuthHeaders` / `apiPost` / `apiDelete` 추가. Authorization 헤더 자동 첨부
- [x] `frontend/src/api/types.ts` — `LoginUser` / `LoginResponse` / `MeResponse` / `WatchlistItem` / `Watchlist` / `WatchlistDetail` / `WatchlistsResponse` / `WatchlistStatusResponse` 신규 타입 추가
- [x] `frontend/src/api/auth.ts` 신규 — `login(username, password)` / `logout()` / `getMe()` API call
- [x] `frontend/src/api/watchlists.ts` 신규 — `listWatchlists` / `getWatchlist` / `createWatchlist` / `addWatchlistItem` / `removeWatchlistItem` CRUD
- [x] `frontend/src/store/auth.tsx` 신규 — `AuthProvider` (getMe 자동 호출, AUTH_ENABLED=false 시 즉시 인증, token 절대 렌더링 안 함) + `useAuth()` hook
- [x] `frontend/src/hooks/useWatchlists.ts` 신규 — `useWatchlists` / `useWatchlist` / `useDefaultWatchlistId` / `useIsInWatchlist` / `useCreateWatchlist` / `useAddWatchlistItem` / `useRemoveWatchlistItem` (useMutation 첫 도입, onSuccess invalidate)
- [x] `frontend/src/pages/Login/index.tsx` 신규 — AUTH_ENABLED=false 시 자동 redirect, password 필드 매 시도 후 clear, access_token 절대 렌더링 안 함
- [x] `frontend/src/pages/Watchlist/index.tsx` 신규 — 11번째 화면. `WatchlistListPanel` / `CreateWatchlistPanel` / `WatchlistDetailPanel` / `WatchlistItemRow` / `AddItemForm` (404/409/422/401 error 처리)
- [x] `frontend/src/components/layout/Sidebar.tsx` — `Star` 아이콘 + `관심종목` 메뉴 추가 (Sidebar 10 → 11), footer v0.8 갱신
- [x] `frontend/src/router.tsx` — `WatchlistPage` lazy route + `/watchlist` / `LoginPage` lazy route + `/login` (AppLayout 외부)
- [x] `frontend/src/App.tsx` — `AuthProvider` wrapper 추가
- [x] `frontend/src/pages/StockDetail/index.tsx` — `FavoriteButton` 컴포넌트 추가 (관심목록 없으면 자동 생성, data-active / aria-pressed 토글)
- [x] `frontend/src/pages/TodayReport/index.tsx` — `WatchlistCard` 컴포넌트 추가 (default watchlist 표시, empty placeholder 링크)
- [x] `frontend/src/tests/mswServer.ts` — `/api/auth/me` / `/api/auth/login` / `/api/auth/logout` / `/api/watchlists` / `/api/watchlists/:id` / `POST /api/watchlists` / `POST /:id/items` / `DELETE /:id/items/:symbol` 핸들러 추가
- [x] `frontend/src/tests/renderWithProviders.tsx` — `AuthProvider` wrapper 추가
- [x] `frontend/src/tests/Login.test.tsx` 신규 — **8 케이스** (auth_disabled auto-redirect / form render / success redirect / 401 error / 500 error / password clear / token 미노출 / submit disabled)
- [x] `frontend/src/tests/Watchlist.test.tsx` 신규 — **12 케이스** (empty placeholder / 500 error / list + detail happy / items empty / create success / 409 duplicate / add item / add 404 / add 409 / add 401 / remove item / forbidden fields)
- [x] `frontend/src/tests/StockDetail.test.tsx` — **+6 케이스** FavoriteButton (inactive / active / add mutation / remove mutation / auto-create watchlist / error on 500)
- [x] `frontend/src/tests/TodayReport.test.tsx` — **+3 케이스** WatchlistCard (happy / empty items / no watchlists)
- [x] `frontend/e2e/fixtures/apiMocks.ts` — auth + watchlist fixture 추가, handle 함수 method 매칭 지원
- [x] `frontend/e2e/dashboard.spec.ts` — sidebar nav 테스트 9 → 11 메뉴 갱신 + Phase D e2e 5건 추가 (Login auto-redirect / Watchlist empty state / Today WatchlistCard / StockDetail FavoriteButton / Watchlist forbidden fields)
- 안전 범위: POST 0건 신규 추가 (Phase C 의 라우터만 사용), 외부 호출 0건, 자동매매 0건, BacktestEngine 변경 0건. 즐겨찾기 mutation 외 모든 라우터는 read-only. `broker` / `account` / `quantity` / `order_*` / `password` / `access_token` 렌더링 0건
- 완료 기준: frontend vitest **84 → 113 passed (+29)**, e2e **14 → 19 passed (+5)**, build 그린, 회귀 0건. source_file_path / 주문 관련 필드 0건 노출 가드. 태그 `v0.8-frontend-watchlist`.

### Phase E — v0.8 릴리스 문서 / 마감 ✅ 인수

- [x] `RELEASE_NOTES_v0.8.md` 신규 (산출물 / 검증 / 안전 정책 / 한계 / v0.9 후보 / 운영 가이드 / 누적 태그)
- [x] `RELEASE_NOTES_v0.8.md` 안전 정책 — Alembic baseline 정책 / 단일 사용자 인증 / `AUTH_ENABLED` 토글 / POST 라우터 5건 한정 / 평문 IP 미저장 / 평문 password 미저장 / refresh token 미도입 / 다중 사용자 미지원 / `source_file_path` / `broker` / `account` / `quantity` / `order_*` 미노출 / 외부 API 자동 호출 0건
- [x] `README.md` 상단 마감 배너 v0.7 → v0.8 갱신 + 누적 태그 라인 + §1 누적 기능 v0.8 항목 4종 + §2 제외 범위 v0.8 정책 + §4 문서 표 + §6 누적 사이클 / 영역 표 + §11 회귀 기준선 (808 / 113 / 19)
- [x] `PROJECT_STATUS.md` §0 v0.8 마감 선언 in-place 갱신, §0-1 v0.8 시작 선언 강등, §0-2 v0.7 마감 (순차 강등)
- [x] `TASKS.md` v0.8 phase 모두 [x] + v0.8 전체 마감 헤더
- [x] `ROADMAP.md` v0.8 행 ✅ 마감 표시 + v0.8 phase 표 ✅
- [x] `ARCHITECTURE.md` / `TESTING.md` 헤더 v0.8 기준 갱신
- [x] backend pytest **808** + frontend vitest **113** + e2e **19** + build 4 게이트 그린 (재확인)
- [ ] tag `v0.8-final` + push (운영자 수동)
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.8 붙여넣기 (UI 작업).

**실제 결과 (Phase E 시점)**: vitest **113 passed** (16 파일) / e2e **19 passed** / build 그린 / backend pytest **808 passed** (1 deselected, 가상환경 필요). 태그 `v0.8-frontend-watchlist` 커밋 `65a0c94` 로컬 생성 완료.

## v0.9 — Operational Security & Watchlist Polish (시작: 2026-05-06)

세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0009`
기준선 태그: `v0.8-final` / 회귀 게이트: pytest **808** / vitest **113** / e2e **19** / build 그린

### Phase A: Security Hardening ✅ 완료

- [x] `app/middleware/security_headers.py` — `SecurityHeadersMiddleware` (X-Content-Type-Options / X-Frame-Options / Referrer-Policy / Permissions-Policy; CSP는 Phase D+ 예정)
- [x] `app/middleware/rate_limit.py` — `slowapi` rate limit (기본 100/min / 로그인 5/min; UUID 키 전략으로 disabled 시 no-op)
- [x] `app/auth/brute_force.py` — 인메모리 brute force protection (5회 실패 → 15분 잠금; composite key: username+ip_hash)
- [x] `app/config/settings.py` — 8개 보안 환경 변수 추가 (`RATE_LIMIT_ENABLED` / `RATE_LIMIT_AUTH` / `RATE_LIMIT_DEFAULT` / `SECURITY_HEADERS_ENABLED` / `AUTH_BRUTEFORCE_*`)
- [x] `pyproject.toml` — `slowapi>=0.1.9,<1.0` 추가
- [x] `app/api/auth_routes.py` — `@limiter.limit` 데코레이터 + brute force pre-check + LOCKOUT_REJECTED 감사 기록 + 항상 generic 401
- [x] `app/main.py` — SecurityHeadersMiddleware + SlowAPIMiddleware + BruteForceGuard 와이어링
- [x] `tests/conftest.py` — autouse fixture (rate limit + brute force 전체 테스트 비활성화)
- [x] `tests/unit/test_security_headers.py` 신규 (8 tests)
- [x] `tests/unit/test_rate_limit.py` 신규 (6 tests)
- [x] `tests/unit/test_brute_force.py` 신규 (12 tests)
- [x] `tests/integration/test_auth_security.py` 신규 (통합 보안 테스트: lockout / PII 해시 / 응답 유출 / endpoint count guard / auto-trade guard)
- [x] backend pytest **845 passed** (기준선 808 + 37 신규) / 회귀 0건
- [ ] tag `v0.9-security-hardening` + push

### Phase B: Error Monitoring + Structured Logging ✅ 완료

- [x] `app/config/logging.py` — 구조화 로깅 강화 (`STRUCTURED_LOGGING_ENABLED` 분기: text/JSON, `SensitiveFilter` + `RequestIDFilter` autouse)
- [x] `app/middleware/request_id.py` — `RequestIDMiddleware` (`X-Request-ID` 생성/보존, `request.state.request_id`, `ContextVar` → 로그 자동 포함)
- [x] `app/monitoring/sentry.py` — Optional Sentry SDK (`SENTRY_ENABLED=false` 기본 / DSN 미설정 시 WARNING 후 skip / `before_send` 비밀값 마스킹)
- [x] `app/main.py` — RequestIDMiddleware 미들웨어 스택 삽입, 전역 exception handler (500 generic + request_id 포함), Sentry init 훅
- [x] `app/config/settings.py` — 5개 신규 환경 변수 (`STRUCTURED_LOGGING_ENABLED` / `LOG_REQUEST_ID_ENABLED` / `SENTRY_ENABLED` / `SENTRY_DSN` / `SENTRY_ENVIRONMENT`)
- [x] `pyproject.toml` — `python-json-logger>=2.0,<3.0` + `sentry-sdk>=2.0,<3.0` 추가
- [x] `frontend/src/components/common/ErrorBoundary.tsx` 신규 (class component, 기본 fallback UI + 다시 시도 버튼 + custom fallback prop)
- [x] `frontend/src/lib/logger.ts` 신규 (환경별 console 분기 유틸)
- [x] `frontend/src/App.tsx` — ErrorBoundary로 전체 앱 root wrap
- [x] `tests/unit/test_logging_config.py` 신규 (12 tests: SensitiveFilter 6 + configure_logging 5 + RequestIDFilter 1)
- [x] `tests/unit/test_request_id.py` 신규 (5 tests: UUID 생성 / 보존 / 유니크 / auth / 429 헤더)
- [x] `tests/unit/test_sentry.py` 신규 (7 tests: disabled / no-DSN warning / sdk init / before_send 마스킹 4종)
- [x] `frontend/src/tests/ErrorBoundary.test.tsx` 신규 (4 tests)
- [x] backend pytest **869 passed** (기준선 845 + 24 신규) / 회귀 0건
- [x] frontend vitest **117 passed** (기준선 113 + 4 신규) / build 그린
- [ ] tag `v0.9-monitoring` + push

### Phase C: Watchlist API 고도화 + UserPreference + Provider 회복성 ✅ 완료

- [x] `app/api/watchlist_routes.py` — PATCH /api/watchlists/{id} (rename + set_default) 추가
- [x] `app/api/watchlist_routes.py` — DELETE /api/watchlists/{id} (cascade delete) 추가
- [x] `app/api/watchlist_routes.py` — GET /api/watchlists/{id}/items (limit/offset/symbol_prefix) 추가
- [x] `app/api/watchlist_routes.py` — PATCH /api/watchlists/{id}/items/{symbol} (메모 편집) 추가
- [x] `app/db/models.py` — `UserPreference` 32번째 ORM 테이블 추가 (broker/account/quantity/order_* 0건)
- [x] `app/api/preferences_routes.py` — GET /api/users/me/preferences + PUT /api/users/me/preferences 추가
- [x] `alembic/versions/0004_user_preferences.py` — UserPreference 테이블 생성 (32nd)
- [x] `app/data/repositories/user_preferences.py` — get_or_create / update / set_default_watchlist 등
- [x] `app/data/provider_resilience.py` — ProviderCallResult / ProviderErrorKind / retry_with_backoff / CircuitBreaker 추가
- [x] `tests/integration/test_watchlist_phase_c.py` 신규 (20 tests)
- [x] `tests/integration/test_user_preferences.py` 신규 (17 tests)
- [x] `tests/unit/test_provider_resilience.py` 신규 (19 tests)
- [x] alembic upgrade head 성공 + compare_metadata diff 0건
- [x] backend pytest **916 passed** (기준선 869 + 47 신규) / 회귀 0건
- [ ] tag `v0.9-watchlist-api` + push

### Phase D: Frontend 관리 UI ✅ 인수

- [x] `frontend/src/api/client.ts` — `apiPatch` / `apiPut` 추가
- [x] `frontend/src/api/types.ts` — `UserPreference`, `UserPreferenceUpdateRequest`, `WatchlistItemsResponse` 타입 추가
- [x] `frontend/src/api/watchlists.ts` — `updateWatchlist`, `deleteWatchlist`, `updateWatchlistItemMemo`, `listWatchlistItems` 추가
- [x] `frontend/src/api/preferences.ts` 신규 — `getMyPreferences`, `updateMyPreferences`
- [x] `frontend/src/hooks/useWatchlists.ts` — `useUpdateWatchlist`, `useDeleteWatchlist`, `useUpdateWatchlistItemMemo` 추가
- [x] `frontend/src/hooks/useUserPreferences.ts` 신규 — `useUserPreferences`, `useUpdateUserPreferences`, `useEffectiveDefaultWatchlistId`
- [x] `frontend/src/pages/Watchlist/index.tsx` — rename(inline) + delete + set-default + memo edit + item filter
- [x] `frontend/src/pages/Settings/index.tsx` 확장 — UserPreference 섹션 (GET/PUT: default_watchlist_id / default_market / default_strategy / notification on-off)
- [x] `frontend/src/pages/TodayReport/index.tsx` — WatchlistCard가 `useEffectiveDefaultWatchlistId` 사용
- [x] `frontend/src/pages/StockDetail/index.tsx` — FavoriteButton이 `useEffectiveDefaultWatchlistId` 사용
- [x] `frontend/src/tests/mswServer.ts` — Phase C/D 핸들러 추가 (PATCH watchlist, DELETE watchlist, GET/PATCH items, GET/PUT preferences)
- [x] `frontend/src/tests/WatchlistManage.test.tsx` 신규 (21 tests — rename/409/cancel, set-default, delete/404, memo/422/cancel, filter, forbidden fields)
- [x] `frontend/src/tests/UserPreferences.test.tsx` 신규 (15 tests — Settings preference GET/PUT, TodayReport watchlist, FavoriteButton preference)
- [x] vitest **146 passed** / build 그린 / tsc 오류 0건
- [x] tag `v0.9-frontend` + push (commit `cfa6f2c`)

### Phase E: 마감 (문서) ✅ 인수

- [x] `RELEASE_NOTES_v0.9.md` 작성 (Phase A~D 산출물 + 최종 게이트 + 안전 정책 + v0.10 후보)
- [x] `README.md` v0.9 갱신 (기능 목록 / 제외 범위 / 누적 사이클 표 / 회귀 기준선)
- [x] `PROJECT_STATUS.md` §0 v0.9 마감 선언으로 교체
- [x] `ROADMAP.md` v0.9 행 ✅ 마감 + v0.10+ 후보 반영
- [x] `TESTING.md` 기준선 갱신 (916 pytest / 146 vitest / 19 e2e — Phase D 시점 이미 반영)
- [x] `ARCHITECTURE.md` v0.9 마감 시점 반영 (보안 미들웨어 레이어 / UserPreference / provider 회복성)
- [x] `API_SPEC.md` / `INTEGRATION_RUNBOOK.md` 헤더 정합성 갱신
- [x] tag `v0.9-final` + push (commit `6062ad4`, 누적 5 태그 모두 원격 push 확인)
- 완료 기준: 4 게이트 그린 (pytest 916 / vitest 146 / e2e 19 / build) + 5 누적 태그 push + RELEASE_NOTES_v0.9.md 작성

---

## v0.10 — Real Provider Readiness & Resilience ✅ 마감

기준선: `v0.9-final`. 최종 게이트: **pytest 1045 (1 deselected) / vitest 153 /
e2e 20 / build 그린**. 마감 태그 `v0.10-final`. Alembic head `0004_user_preferences`
그대로 (v0.10 신규 revision 0건).

세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0010` / 마감 사유: [`RELEASE_NOTES_v0.10.md`](./RELEASE_NOTES_v0.10.md)

### Phase A: Provider Resilience 실 적용 ✅ 인수

- [x] `ProviderHealthMonitor` 클래스 구현 (`app/data/provider_health_monitor.py`)
- [x] `call_with_resilience()` 공통 래퍼 구현 (retry + circuit breaker + failure isolation + request_id 로그)
- [x] `app/config/settings.py` — provider resilience 런타임 설정 7종 추가 (provider_resilience_enabled=False 기본)
- [x] 단위 테스트 31건 (`tests/data/test_provider_health_monitor.py`)
- [x] 기존 916건 회귀 0건 추가 실패 확인 (947 passed)
- [x] `tag v0.10-provider-resilience + push`

### Phase B: DART Provider 구현 ✅ 인수

- [x] `app/config/settings.py` 에 DART 런타임 6종 추가 (`dart_enabled=False` / `dart_api_key=""` / `dart_base_url` / `dart_timeout_s` / `dart_max_attempts` / `dart_provider_name`)
- [x] `DartFundamentalProvider` 구현 (`app/data/dart_provider.py`) — `fnlttSinglAcnt` 단일 재무제표 endpoint mock
- [x] `DartEarningsProvider` 구현 — 동일 endpoint 의 actual 만 추출 (consensus 는 `None`, DART 비공개)
- [x] `DartDisclosureProvider` 구현 — `/api/list.json` 공시 목록 mock
- [x] `call_with_resilience()` (Phase A 의 retry + circuit breaker + failure isolation) 을 DART 호출 경계 100% 적용
- [x] `DART_ENABLED=false` 시 `DartNotConfiguredError` raise — provider 인스턴스화 / transport 호출 0건 검증
- [x] 단위 테스트 49건 (`tests/data/test_dart_provider.py`, mock fixture 기반)
- [x] `SensitiveFilter` 에 `crtfc_key` / `crtfckey` / `dart_key` 패턴 명시 추가 — `dart_api_key` / `DART_API_KEY` 는 기존 `api_key` 패턴 매칭 (테스트로 보강)
- [x] 본문 / 전문 / 원문 / `body` / `full_text` / `paragraph` / `raw_text` / `html_body` 등 forbidden 필드는 parser 가 strip — DTO 자체에 해당 필드 부재 단언
- [x] 외부 네트워크 호출 0건 가드 (`httpx.Client` 미생성 단언 테스트)
- [x] `tag v0.10-dart-provider + push`

### Phase C: RSS/News Provider 준비 ✅ 인수

- [x] `app/config/settings.py` 에 RSS 런타임 5종 추가 (`rss_news_enabled=False` / `rss_feed_urls=""` / `rss_timeout_s=10.0` / `rss_max_attempts=3` / `rss_provider_name="rss"`)
- [x] `RssNewsProvider` 구현 (`app/data/rss_provider.py`) — `NewsProviderInterface` 구현, transport 주입형 (Phase B DART 패턴 동일)
- [x] RSS 2.0 + Atom 두 포맷 모두 stdlib `xml.etree.ElementTree` 로 파싱 — 신규 의존성 0건 (`feedparser` 미사용)
- [x] body/content/full_text/paragraph/raw_text/html_body/본문/원문/전문 등 forbidden 필드는 parser 가 strip — DTO 자체에 부재
- [x] `<description>` 내 HTML 태그 strip + summary 500자 truncate
- [x] URL dedup (`dedup_items` first-wins, 단일 fetch 호출 내 / 다중 feed 합산 후)
- [x] `news_items.url` UNIQUE 정책과 정합 — collector 경계에서 upsert-ignore (문서)
- [x] `call_with_resilience()` 적용 — provider_name=`"rss"`, retry / circuit breaker / failure isolation 자동 상속
- [x] 단위 테스트 33건 (`tests/data/test_rss_provider.py`, mock XML fixture 기반)
- [x] `RSS_NEWS_ENABLED=false` 또는 `RSS_FEED_URLS` 빈 문자열 시 `RssNotConfiguredError` raise — provider 인스턴스화 / transport 호출 0건
- [x] feed URL 의 query string secret (`?api_key=...`) 은 로그에 미노출 (`_safe_url_for_log` 가 query / fragment strip)
- [x] 외부 네트워크 호출 0건 가드 (`httpx.Client` 미생성 단언)
- [x] `tag v0.10-rss-provider + push`

### Phase D: 운영 모니터링 강화 ✅ 인수

- [x] `GET /api/health/providers` 라우터 구현 (`app/api/health_routes.py`) — `ProviderHealthMonitor.get_all_status()` + Settings opt-in 플래그 합성
- [x] canonical 3 provider (`kis` / `dart` / `rss`) 항상 노출 + experimental provider monitor iteration 순서로 append
- [x] `last_error_message` 응답 미포함 (URL query secret 누출 방지) — `last_error_kind` enum 만 노출
- [x] POST / PUT / DELETE 0건 (모두 405) — provider 토글은 `.env` 수정 + 재시작
- [x] `GET /api/health/jobs` — Phase D 범위 보류 (이미 `GET /api/jobs` 존재; 분리 필요시 v0.11+)
- [x] `frontend/src/api/providerHealth.ts` + `frontend/src/hooks/useProviderHealth.ts` 신규 (staleTime 30s, refetchInterval 60s, refetchOnWindowFocus=false)
- [x] Settings 화면에 `ProviderHealthPanel` 추가 — provider별 enabled / configured / circuit_state 배지 + counts + last_error_kind
- [x] backend pytest 17건 (`tests/integration/test_health_providers.py`) — happy / disabled / OPEN / secret-mask / no-network / 405 가드
- [x] vitest 7건 (`frontend/src/tests/ProviderHealthPanel.test.tsx`) — happy / disabled / OPEN badge / 500 error / empty / secret 미렌더링 / read-only (button 0건)
- [x] e2e 1건 (`Settings shows the read-only Provider Health panel`) — DART/RSS disabled 표시 + 패널 내 button 0건 + raw payload secret 0건
- [x] `apiMocks.ts` + `mswServer.ts` 에 `/api/health/providers` 기본 핸들러 추가
- [x] `tag v0.10-health-api + push`

### Phase E: 마감 (문서) ✅ 인수

- [x] `RELEASE_NOTES_v0.10.md` 작성 (Phase A~D 산출물 + 최종 게이트 + 안전 정책 + v0.11 후보)
- [x] `README.md` v0.10 갱신 (기능 목록 / 제외 범위 / 누적 사이클 표 / 회귀 기준선)
- [x] `PROJECT_STATUS.md` §0 v0.10 마감 선언으로 교체 (이전 §0-1 → §0-2 → §0-3 시간순 강등)
- [x] `ROADMAP.md` v0.10 행 ✅ 마감 + v0.11 후보 정리
- [x] `TESTING.md` 기준선 갱신 (1045 pytest / 153 vitest / 20 e2e / build 그린)
- [x] `ARCHITECTURE.md` v0.10 마감 시점 반영
- [x] `tag v0.10-final + push`

---

## v0.11 — Real Provider Transport & Observability ✅ 마감

기준선: `v0.10-final`. 최종 게이트: **pytest 1119 (1 deselected) / vitest 158 /
e2e 21 / build 그린**. 마감 태그 `v0.11-final`. Alembic head `0004_user_preferences`
그대로 (v0.11 신규 revision 0건).

세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0011` / 마감 사유: [`RELEASE_NOTES_v0.11.md`](./RELEASE_NOTES_v0.11.md)

### Phase A: DART HTTP Transport ✅ 인수

- [x] `respx>=0.21,<0.22` 의존성 추가 (테스트 전용, `[project.optional-dependencies] dev`)
- [x] `app/data/dart_provider.py` 에 `HttpxDartTransport` 구현 (`DartTransport` protocol 구현체) — `httpx` lazy import 로 v0.10 monkeypatch 가드와 호환
- [x] `create_dart_providers` factory — `transport=None` + `DART_ENABLED=true` 시 `HttpxDartTransport` 자동 주입 (`_default_transport` helper 분리)
- [x] HTTP status / DART `status` 코드 → `ProviderErrorKind` 매핑 (`classify_dart_status` 재사용)
- [x] `httpx.TimeoutException` → TIMEOUT, 4xx → CLIENT_ERROR, 5xx → SERVER_ERROR, JSON 디코딩 실패 / 비-object body → UNKNOWN
- [x] respx mock 테스트 27건 (`tests/data/test_dart_http_transport.py`) — HTTP 매핑 + DART 코드 + factory + resilience integration + secret discipline + zero-network guard
- [x] `DART_ENABLED=false` 시 `httpx.Client` 미생성 단언 유지 (v0.10 49 케이스 회귀 0건)
- [x] `DART_API_KEY` / `crtfc_key` 평문 로그 0건 — `_SensitiveQueryStringFilter` 가 httpx INFO 로그의 query string secret 마스킹 (`crtfc_key=***`)
- [x] httpx exception `__str__` → `result.error_message` 미반영 (예외 클래스명만 노출, URL secret 누출 차단)
- [x] `tag v0.11-dart-transport + push`

### Phase B: RSS HTTP Transport ✅ 인수

- [x] `_SensitiveQueryStringFilter` + `install_sensitive_qs_filter` 를 Phase A `dart_provider.py` 에서 `app/config/logging.py` 로 추출 — DART/RSS 공유, 누적 idempotent 설치
- [x] `app/data/rss_provider.py` 에 `HttpxRssTransport` 구현 (`RssTransport` protocol, lazy httpx import)
- [x] `create_rss_provider` factory — `transport=None` + `RSS_NEWS_ENABLED=true` + `RSS_FEED_URLS` 설정 시 `_default_transport` 자동 주입
- [x] HTTP 200 → `ProviderCallResult.ok(response.content)`; 4xx → CLIENT_ERROR; 5xx → SERVER_ERROR; TimeoutException → TIMEOUT; 기타 HTTPError → UNKNOWN (예외 클래스명만 message)
- [x] `follow_redirects=True` + httpx 기본 max redirect cap (20)
- [x] respx mock 테스트 19건 (`tests/data/test_rss_http_transport.py`) — RSS 2.0 / Atom + 4xx / 5xx / timeout / connect / 비-XML 격리 / factory + resilience + secret 마스킹 + zero-network
- [x] feed URL query secret (`?api_key=PRIVATE-FEED-SECRET-XYZ`) caplog / `result.error_message` / `monitor.last_error_message` 평문 0건
- [x] `RSS_NEWS_ENABLED=false` / 빈 `RSS_FEED_URLS` 시 `httpx.Client` 미생성 (AssertionError 가드)
- [x] v0.10 Phase C 33 케이스 회귀 0건 (호출자 transport 주입 path 가드 유효)
- [x] DART Phase A 49+27 케이스 회귀 0건 (filter 추출 후에도 동일 동작)
- [x] `tag v0.11-rss-transport + push`

### Phase C: Provider Observability Layer ✅ 인수

- [x] `prometheus-client>=0.19,<1.0` 의존성 추가 (Apache 2.0)
- [x] `ProviderStats` 에 `recent_calls: deque(maxlen=200)` + `recent_failures: deque(maxlen=50)` 추가 — `CallRecord` / `FailureRecord` frozen dataclass (timestamp + enum + ints만, message 필드 부재로 secret 누출 차단)
- [x] `ProviderHealthMonitor.summary_24h(now=None)` 구현 — `Summary24h` dataclass 반환 (`call_count_24h` / `success_count_24h` / `failure_count_24h` / `success_rate_24h` / `avg_attempts`, 0 호출 시 None)
- [x] `reset()` 가 ring buffer 도 clear
- [x] `record_result` 가 lazy `_emit_prometheus` hook 호출 — try/except 로 observability 가 provider 호출 path 를 절대 break 하지 않음
- [x] `app/monitoring/prometheus.py` 신규 — `PrometheusMetrics` bundle (Counter 4종 + Gauge 1종 + Histogram 1종) + `set_metrics` / `get_metrics` / `init_default_metrics` / `record_call` / `mark_unregistered` / `render_metrics` API
- [x] Circuit state 정수 인코딩: CLOSED=0 / OPEN=1 / HALF_OPEN=2 / UNREGISTERED=3
- [x] `app/api/metrics_routes.py` 신규 — `GET /metrics` (`PROMETHEUS_ENABLED=false` → 404, true → 200 + `text/plain`); POST/PUT/DELETE 모두 405
- [x] `app/main.py` 가 startup 시 `init_default_metrics(settings)` 호출 (idempotent + Prometheus disabled 시 no-op)
- [x] `app/config/settings.py` — `prometheus_enabled=False` / `prometheus_path="/metrics"` 추가
- [x] 단위 테스트 21건 (`tests/data/test_provider_observability.py`) — ring buffer maxlen / 24h window 경계 + 외부 `now` injection / Prometheus counter+gauge+histogram 라인 / collector registry 격리 (fresh `CollectorRegistry` per test) / `/metrics` 404·200·405 / DART/RSS secret 미포함 / Prometheus 예외 swallow / httpx.Client 미생성 단언
- [x] v0.10 monitor 31 + DART skeleton 49 + DART http 27 + RSS skeleton 33 + RSS http 19 = 159 케이스 회귀 0건
- [x] `tag v0.11-observability + push`

### Phase D: `/api/health/providers` 확장 + Settings 패널 보강 ✅ 인수

- [x] `ProviderHealthItem` schema 확장 — `call_count_24h` / `success_count_24h` / `failure_count_24h` / `success_rate_24h: float?` / `avg_attempts_24h: float?` / `recent_failures: list[RecentFailureSummary]` (last 5)
- [x] `RecentFailureSummary` 신규 schema — `{timestamp, error_kind}` 만 (message text 0건, URL secret 누출 차단 정책 유지)
- [x] `ProviderHealthMonitor` 에 `get_summary_24h(name)` / `get_recent_failures(name, limit=5)` 공개 accessor 추가 (`_providers` private 직접 참조 제거)
- [x] `_build_item` + `_serialise_recent_failures` — newest-first 정렬 후 `_RECENT_FAILURE_LIMIT=5` cap
- [x] `last_error_message` 응답 미포함 정책 유지
- [x] `frontend/src/api/types.ts` schema 동기화 (`RecentFailureSummary` + `ProviderHealthItem` 6 신규 필드)
- [x] `frontend/src/components/common/ProviderHealthPanel.tsx` 보강 — `SuccessRateBar` (≥99% emerald / ≥95% amber / <95% red / null slate) + `avg_attempts` 셀 + `RecentFailuresList` + `ProviderRecentFailuresSection` (실패가 1건 이상인 provider 만 카드 노출)
- [x] backend pytest +7 (`tests/integration/test_health_providers.py`) — happy / cap / newest-first / message 미노출 / paranoid secret + 16 forbidden / zero-window 안전 / experimental provider
- [x] vitest +5 (`frontend/src/tests/ProviderHealthPanel.test.tsx`) — success_rate / avg_attempts cell / recent_failures newest-first / empty placeholder / secret 미렌더링 / read-only
- [x] e2e +1 (`Settings Provider Health panel surfaces v0.11 Phase D 24h aggregates and recent failures`) — KIS fixture progress bar + DART/RSS 빈 placeholder + 패널 내 button 0건 + 16 forbidden secret 0건
- [x] MSW + e2e fixtures 신규 필드 sync (KIS 50 calls / 1 TIMEOUT failure 시연용)
- [x] `tag v0.11-health-extended + push`

### Phase E: 마감 (문서) ✅ 인수

- [x] `RELEASE_NOTES_v0.11.md` 작성 (Phase A~D 산출물 + 최종 게이트 + 안전 정책 + v0.12 후보)
- [x] `README.md` v0.11 갱신 (마감 배너 + 누적 기능 + 제외 범위 + 누적 사이클 표 + 회귀 기준선 1119/158/21)
- [x] `PROJECT_STATUS.md` §0 v0.11 마감 선언으로 교체 (이전 §0 v0.11 시작 → §0-1 강등, §0-1 v0.10 마감 → §0-2, §0-2 v0.10 시작 → §0-3, §0-3 v0.9 마감 → §0-4, §0-4 v0.9 시작 → §0-5)
- [x] `ROADMAP.md` v0.11 행 ✅ 마감 + v0.12+ 후보 정리 + 장기 비전 갱신 + Future Backlog v0.11 GET /metrics 안내
- [x] `TESTING.md` 기준선 갱신 (1119 pytest / 158 vitest / 21 e2e — Phase D 시점에 이미 갱신 완료)
- [x] `ARCHITECTURE.md` v0.11 마감 시점 반영
- [x] `API_SPEC.md` `/metrics` (default 404) + `/api/health/providers` 6 신규 필드 안내 (Phase C/D 시점에 이미 갱신 완료)
- [x] `INTEGRATION_RUNBOOK.md` v0.11 마감 시점 반영
- [ ] `tag v0.11-final + push`

---

## v0.12 — Provider Data Scoring & Backtest Validation ✅ 마감

기준선: `v0.11-final`. 회귀 게이트: pytest 1119 / vitest 158 / e2e 21 / build 그린.
세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0012`. 채택 시나리오: **Scenario X — Provider
Data Scoring + Backtest Validation** (Provider 데이터 → DB → existing producer 자동
흡수 + walk-forward backtest 검증 + 다중 전략 비교 + read-only API/UI 확장).
ScoringEngine 본 weight 변경 0건 — *데이터 입력* 만 fake → real. DART/RSS/Prometheus
/Provider Data Ingestion 모두 default OFF 유지.

### Phase A: Provider Data Ingestion (default OFF) ✅ 인수

- [x] `app/config/settings.py` 에 `PROVIDER_DATA_INGESTION_ENABLED: bool = False` 추가
- [x] `NewsItemDTO` / `DisclosureItemDTO` / `FundamentalSnapshotDTO` / `EarningsEventDTO` 모두에 `data_source: str = "FAKE"` 필드 + `DATA_SOURCE_PROVIDER`/`FAKE`/`CSV`/`MANUAL` 상수 + `ALLOWED_DATA_SOURCES` frozenset
- [x] DART parser (`parse_fundamentals` / `parse_earnings` / `parse_disclosure_item`) 가 `data_source=DATA_SOURCE_PROVIDER` 설정
- [x] RSS parser (`_parse_rss_item` / `_parse_atom_entry`) 가 `data_source=DATA_SOURCE_PROVIDER` 설정
- [x] CSV importer (`FundamentalCsvImporter._parse_row` / `EarningsCsvImporter._parse_row`) 가 `data_source=DATA_SOURCE_CSV` 설정
- [x] Importer `_dto_fields` 가 `data_source` 를 repository upsert 인자에서 제거 (DB 컬럼 부재 — runtime-only)
- [x] `app/data/ingestion.py` 신규 모듈 + 4 어댑터: `ingest_dart_disclosures` / `ingest_rss_news` / `ingest_dart_fundamentals` / `ingest_dart_earnings`
- [x] 모든 어댑터 entry 첫 줄에서 `Settings.provider_data_ingestion_enabled` 검사 → `False` 시 즉시 `skipped_disabled=True` 반환 (provider 미생성, httpx.Client 미생성, DB write 0건)
- [x] DART/RSS 자체 default OFF 도 soft-skip (raise 안 함, `skipped_disabled=True` 반환) — operator 가 master flag 만 켜고 DART 키 늦게 설정해도 안전
- [x] v0.5/v0.6 producer (`RealNewsScoreProducer` / `DisclosureRiskProducer` / `RealFundamentalScoreProducer` / `RealEarningsScoreProducer`) 변경 0건 — DTO `data_source` 는 runtime-only, producer 는 기존 DB 컬럼만 read
- [x] ScoringEngine.NEW_RECOMMENDATION_WEIGHTS / HOLDING_WEIGHTS 회귀 단언 (Decimal 정확도 포함)
- [x] DTO body field 부재 단언 4 케이스 (parametrize) + DB 모델 body 컬럼 부재 단언 3 케이스 (NewsItem / FundamentalSnapshot / EarningsEvent)
- [x] DART_API_KEY (`SUPER-SECRET-KEY-DO-NOT-LOG-XYZ`) caplog 평문 0건
- [x] RSS feed URL query secret (`?api_key=PRIVATE-FEED-SECRET-XYZ`) caplog 평문 0건
- [x] 호출자가 직접 transport 주입 시 `httpx.Client` 미생성 단언 (4 어댑터 동시 검증)
- [x] 통합 테스트 30건 (`tests/integration/test_provider_data_ingestion.py`)
- [x] v0.10/v0.11 누적 회귀 0건 — backend pytest 1119 → 1149 (+30)
- [x] `tag v0.12-provider-ingestion + push`

### Phase B: Walk-forward Backtest Engine ✅ 인수

- [x] `app/backtest/walk_forward.py` 신규 — `WalkForwardBacktestEngine` + `FoldResult` + `WalkForwardSummary` + `generate_folds()`
- [x] train/validate window sliding: `train_window_days=60`, `validate_window_days=20`, `gap_days=0` 기본값; 각 step은 `validate_window_days`씩 슬라이드해 OOS 겹침 없음
- [x] per-fold IS/OOS metrics (`win_rate_5d` / `avg_return_5d` 등) + `avg_oos_win_rate_5d` / `avg_oos_avg_return_5d` 집계
- [x] fold metadata를 `backtest_runs.summary_json["walk_forward_folds"]` 에 저장 — **Alembic revision 0건**
- [x] `scripts/run_backtest.py` 보강 — `--walk-forward`, `--train-window-days`, `--validate-window-days`, `--gap-days` CLI 옵션
- [x] 통합 테스트 17건 (`tests/integration/test_walk_forward_engine.py`) — 폴드 생성 순수논리 5건 + 엔진 dry/commit 9건 + CLI 2건 + 직렬화 1건
- [x] v0.7 BacktestEngine 회귀 0건 — backend pytest 1149→1167 (+17, 1 deselected 유지)
- [x] `tag v0.12-walk-forward + push`

### Phase C: Multi-strategy Comparison + Regime/Sector Breakdown ✅ 인수

- [x] `app/backtest/multi_strategy_runner.py` 신규 — `MultiStrategyRunner` + `StrategyResult` + `MultiStrategyComparison` + `_find_best()`
- [x] `app/backtest/regime_breakdown.py` 신규 — `SectorBreakdownEntry` + `aggregate_sector_breakdown()` 순수 집계 helper
- [x] 비교 결과를 `backtest_runs.summary_json["multi_strategy_comparison"]` 에 직렬화; 기존 Phase B `walk_forward_folds` key와 충돌 없음 — Alembic revision 0건
- [x] `scripts/run_backtest.py` 보강 — `--multi`, `--strategies top_grade,high_score`, `--no-regime-breakdown`, `--no-sector-breakdown` CLI 옵션
- [x] 같은 기간/유니버스 보장 (`_fetch_recs_with_sector` 동일 쿼리 패턴) + sector 누락 종목 → `UNKNOWN` bucket 안전 처리
- [x] 통합 테스트 16건 (`tests/integration/test_multi_strategy_comparison.py`) — sector 순수집계 2건 + 엔진 dry 3건 + 순위 2건 + breakdown 3건 + commit 2건 + 직렬화 1건 + CLI 3건
- [x] v0.7 + Phase B 회귀 0건 — backend pytest 1167→1183 (+16, 1 deselected 유지)
- [x] `tag v0.12-multi-strategy + push`

### Phase D: Backtest Read-only API/UI 확장 + Provider Score Evidence ✅

- [x] `GET /api/backtest/runs/{id}/folds` 신규 read-only — walk-forward fold 목록 노출
- [x] `GET /api/backtest/runs/{id}/comparison` 신규 read-only — 다중 전략 비교 결과 노출
- [x] `BacktestFoldSchema` / `BacktestFoldsResponse` / `BacktestComparisonStrategySchema` / `BacktestComparisonResponse` / `SectorBreakdownSchema` 신규 (모두 read-only, `app/api/schemas.py`)
- [x] POST/PUT/DELETE 신규 0건 — 모든 신규 라우터 GET only (mutation 405 검증 pytest 2건)
- [x] `evidence_json.data_source` chip 렌더 — `BacktestResultItem.evidence_json` 기존 필드 활용 (`"PROVIDER"` / `"FAKE"` / `"CSV"` / `"MANUAL"`) — DB 모델 / 스키마 무변경
- [x] `frontend/src/api/types.ts` — `BacktestFoldItem`, `BacktestFoldsResponse`, `SectorBreakdownItem`, `BacktestComparisonStrategyItem`, `BacktestComparisonResponse` 추가
- [x] `frontend/src/hooks/useBacktestFolds.ts` / `useBacktestComparison.ts` 신규
- [x] `frontend/src/pages/Backtest/index.tsx` 보강 — walk-forward fold 표 + 다중전략 비교 표 + sector breakdown + best strategy 강조 + data_source chip
- [x] backend 통합 테스트 14건 (`tests/integration/test_backtest_api_phase_d.py`) — folds happy/empty/404/malformed, comparison happy/empty/404/malformed, 405 ×2, forbidden field ×2
- [x] vitest 9건 추가 (`frontend/src/tests/Backtest.test.tsx`) — folds 2건 + comparison 2건 + data_source chip 2건 + forbidden 1건 (기존 7건 포함 총 16건)
- [x] MSW default 핸들러 2건 추가 (`mswServer.ts`) — folds / comparison 빈 응답
- [x] secret / token / api_key / URL query secret / body text 노출 0건 paranoid scan 완료
- [x] `tag v0.12-scoring-readonly + push`

### Phase E: 마감 (문서) ✅ 인수

- [x] `RELEASE_NOTES_v0.12.md` 작성 (Phase A~D 산출물 + 최종 게이트 + 안전 정책 + v0.13 후보)
- [x] `README.md` v0.12 갱신 (기능 목록 / 제외 범위 / 누적 사이클 표 / 회귀 기준선)
- [x] `PROJECT_STATUS.md` §0 v0.12 마감 선언으로 교체
- [x] `ROADMAP.md` v0.12 행 ✅ 마감
- [x] `TESTING.md` 기준선 갱신 (1194 pytest / 165 vitest / 21 e2e)
- [x] `ARCHITECTURE.md` v0.12 마감 시점 반영
- [x] `API_SPEC.md` `/folds` + `/comparison` + `evidence.data_source` 안내 (Phase D 에서 완료)
- [x] `INTEGRATION_RUNBOOK.md` Provider Data Ingestion enable 절차 + walk-forward CLI 안내
- [x] `tag v0.12-final + push`

---

## v0.13 — Provider Score Policy & Validation Report ✅ 마감

기준선: `v0.12-final`. 회귀 게이트: pytest 1194 / vitest 165 / e2e 21 / build 그린.
세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0013`. 채택 시나리오: **Scenario X —
Provider Score Policy + Score Delta + Validation Report + Backtest Export CLI**.
ScoringEngine 본 weight 변경 0건 — policy factor 는 producer 출력에 곱해지는 별도 layer.
DART/RSS/Prometheus/Provider Data Ingestion 모두 default OFF 유지. Alembic revision 0건.

### Phase A: Provider Score Policy Engine ✅ 완료 (`v0.13-provider-policy`)

- [x] `app/scoring/provider_policy.py` 신규 — `ProviderScorePolicy` + `DATA_SOURCE_RELIABILITY` 매핑 + `_BYPASS_SOURCES` + `_to_decimal()`
- [x] `app/scoring/__init__.py` 신규 — `ProviderScorePolicy` / `DATA_SOURCE_RELIABILITY` export
- [x] `app/config/settings.py` 에 `PROVIDER_SCORE_POLICY_ENABLED: bool = False` 추가 (v0.13 Phase A — 코멘트 포함)
- [ ] `RealNewsScoreProducer` / `DisclosureRiskProducer` / `RealFundamentalScoreProducer` / `RealEarningsScoreProducer` 에 policy 통합 (FAKE bypass, PROVIDER/CSV/MANUAL factor 적용) — **Phase B+ 범위**
- [x] ScoringEngine weight (`technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%`) 회귀 단언 (Decimal 정확도 포함) — weight 변경 0건 (`test_scoring_engine_new_recommendation_weights_unchanged` / `test_scoring_engine_holding_weights_unchanged`)
- [x] 단위 테스트 28건 (`tests/unit/test_provider_policy.py`) — factor 매핑 / FAKE bypass / policy OFF bypass / 경계값 / 음수 / float·Decimal 입력 / ROUND_HALF_UP / 외부 호출 0건 단언
- [x] `tag v0.13-provider-policy + push` — **게이트: pytest 1223 / vitest 165 / build 그린**

### Phase B: Score Delta Recording in Evidence ✅ 완료 (`v0.13-score-delta`)

- [x] `app/scoring/score_delta.py` 신규 — `ScoreDeltaResult` + `ComponentDelta` + `compute_score_delta()`
- [x] `app/scoring/__init__.py` — `ScoreDeltaResult` / `ComponentDelta` / `compute_score_delta` export 추가
- [x] `RecommendationEngine` — `score_policy` 파라미터 + `score_delta` evidence_json 기록 (Alembic 0건)
- [x] `HoldingCheckEngine` — `score_policy` 파라미터 + `score_delta` evidence_json 기록 (Alembic 0건)
- [x] `app/api/routes.py` — `_SCORE_DELTA_EVIDENCE_FIELDS` whitelist + recommendation / holding_check 양쪽 추출
- [x] `app/api/schemas.py` — `RecommendationItemSchema` / `HoldingCheckSchema` 에 `score_delta` 필드 추가
- [x] 단위 테스트 18건 (`tests/unit/test_score_delta.py`) — policy OFF / FAKE bypass / CSV·MANUAL·PROVIDER attenuation / multi-component / None score / rounding / as_dict() / ScoringEngine weight 단언
- [x] `tag v0.13-score-delta + push` — **게이트: pytest 1241 / vitest 165 / build 그린**

### Phase C: Validation Report read-only API ✅ 완료 (`v0.13-validation-api`)

- [x] `app/api/validation_routes.py` 신규 — `GET /api/validation/report` + `/by-strategy` + `/by-regime` + `/by-sector` (GET only, POST/PUT/PATCH/DELETE 405)
- [x] `app/api/schemas.py` — `ScoreDeltaSummarySchema` / `ValidationStrategySummarySchema` / `ValidationRegimeSummarySchema` / `ValidationSectorSummarySchema` / `ValidationReportSchema` / `ValidationStrategyResponse` / `ValidationRegimeResponse` / `ValidationSectorResponse` 8종 추가
- [x] `app/api/__init__.py` — `validation_router` export 추가
- [x] `app/main.py` — `validation_router` 등록
- [x] 통합 테스트 36건 (`tests/integration/test_validation_report.py`) — happy/empty/malformed skip/data_source bucket/policy_enabled_count/delta sign count/forbidden field/405×16(4 endpoint × 4 method)/socket monkeypatch
- [x] `frontend/src/api/types.ts` — ValidationReport 8종 타입 추가 (ScoreDeltaSummary / ValidationReportResponse / ValidationStrategySummary / ValidationStrategyResponse / ValidationRegimeSummary / ValidationRegimeResponse / ValidationSectorSummary / ValidationSectorResponse)
- [x] `frontend/src/api/validation.ts` 신규 — fetchValidationReport / fetchValidationByStrategy / fetchValidationByRegime / fetchValidationBySector
- [x] `frontend/src/hooks/useValidationReport.ts` 신규 — 4 hooks (staleTime: 60_000)
- [x] `frontend/src/pages/Validation/index.tsx` 신규 (12번째 화면 `/validation`) — 전체요약 카드 / ScoreDelta 카드 / 전략표 / 국면표 / 섹터표 / loading·error·empty state / data-testid 완비
- [x] `frontend/src/router.tsx` — ValidationPage lazy import + `/validation` route 추가
- [x] `frontend/src/components/layout/Sidebar.tsx` — ClipboardCheck 아이콘 검증리포트 메뉴 (12번째) + v0.13 footer 갱신
- [x] `frontend/src/tests/mswServer.ts` — 4 validation GET 핸들러 추가 (by-strategy/by-regime/by-sector/report)
- [x] `frontend/src/tests/Validation.test.tsx` 신규 — **10건** (page wrapper / empty state / happy summary / strategy table / regime row / sector row / error state / forbidden field guard / empty data_source chips / null cost_adjusted dash)
- [x] `frontend/e2e/fixtures/apiMocks.ts` — VALIDATION_REPORT_EMPTY fixture + 4 route patterns
- [x] `frontend/e2e/dashboard.spec.ts` — sidebar "11 → 12 menus" + 검증리포트 navigation check + `/validation` no-automation 경로 추가
- [x] `tag v0.13-validation-api + push` — **게이트: pytest 1277 / vitest 165 / build 그린**

### Phase D: Validation Report Frontend ✅ 완료 (`v0.13-validation-ui`)

**게이트: vitest 175 passed (165 → 175, +10) / build 그린 / e2e 불변**

### Phase D: Backtest Export CLI — v0.14+ 이연

> 이번 사이클에서 구현하지 않고 v0.14+ 로 이연. 기능 코드 수정 없이 문서 마감 우선.

- [ ] `scripts/export_backtest.py` 신규 — `--run-id`, `--format csv/json`, `--output PATH`, `--dry-run` **(v0.14+ 이연)**
- [ ] fold / comparison / sector breakdown 포함 **(v0.14+ 이연)**
- [ ] export 출력 파일에 API key / secret / source_file_path 포함 0건 (forbidden field guard) **(v0.14+ 이연)**
- [ ] 통합 테스트 ~8건 (`tests/integration/test_backtest_export.py`) **(v0.14+ 이연)**

### Phase E: 마감 (문서) ✅ 완료 (`v0.13-final`)

- [x] `RELEASE_NOTES_v0.13.md` 작성 (Phase A~D 산출물 + 최종 게이트 + 안전 정책 + v0.14 후보)
- [x] `README.md` v0.13 갱신 (기능 목록 / 제외 범위 / 회귀 기준선 / 누적 사이클 표)
- [x] `PROJECT_STATUS.md` §0 v0.13 마감 선언으로 교체 (이전 §0 → §0-1, v0.12 마감 → §0-2)
- [x] `ROADMAP.md` v0.13 행 ✅ 마감
- [x] `TESTING.md` 기준선 기확인 (1277 pytest / 175 vitest / 21 e2e — Phase D 시 이미 갱신)
- [x] `ARCHITECTURE.md` v0.13 마감 시점 반영
- [x] `API_SPEC.md` `/validation/report` 엔드포인트 + score_delta evidence 안내
- [x] `INTEGRATION_RUNBOOK.md` score policy enable 절차 안내
- [x] `tag v0.13-final + push`

---

## v0.14 — Paper / Simulation Trading Foundation (시작 선언)

기준선: `v0.13-final`. 회귀 게이트: pytest 1277 / vitest 175 / e2e 21 / build 그린.
세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0014`. 채택 시나리오: **Scenario X —
Paper Trading Full Stack (SimulationBroker + VirtualAccount/Order/Position/PnL)**.
자동매매 / 실 KIS 주문 / FULL_AUTO 0건.

### Phase A: Backtest Export CLI + ProviderScorePolicy→Producer 통합 ✅

- [x] `scripts/export_backtest.py` 신규 — `--run-id`, `--format csv|json`, `--output PATH`, `--dry-run`, `--db-url`
- [x] forbidden field guard: evidence_json / source_file_path / config_json / summary_json / reason 등 제외 (`FORBIDDEN_EXPORT_FIELDS` 상수)
- [x] 통합 테스트 23건 (`tests/integration/test_backtest_export.py`) — CSV/JSON 출력 / 금지 필드 / dry-run / RunNotFoundError / main() CLI / Decimal·datetime 직렬화 / 네트워크 0건
- [x] `app/analysis/score_producers.py` — `RealNewsScoreProducer` / `RealFundamentalScoreProducer` / `RealEarningsScoreProducer` 에 `ProviderScorePolicy.apply()` 통합 (PROVIDER_SCORE_POLICY_ENABLED=False 기본 유지)
- [x] 단위 테스트 25건 추가 (`tests/unit/test_score_producers.py`) — policy 통합 단언 (OFF 시 동일 / CSV·MANUAL 감쇠 / FAKE bypass / None fallback 1.00 / weight 불변 / 네트워크 0건)
- [x] **게이트: pytest 1322 passed (기준 1277 +45)** — 회귀 0건
- [ ] `tag v0.14-export-policy + push`

### Phase B: SimulationBroker + VirtualAccount/VirtualOrder 도메인 ✅

- [x] `app/broker/__init__.py` — `SimulationBroker` / `SubmitResult` / `PaperTradingDisabledError` / `SimulationBrokerError` export
- [x] `app/broker/simulation_broker.py` 신규 — `SimulationBroker` (BrokerInterface 첫 구현체). `submit_order` 는 PAPER_TRADING_ENABLED=False 또는 account.paper_trading_enabled=False 시 `PaperTradingDisabledError` 발생, 정상 시 `VirtualOrder(CREATED)` DB write. idempotency_key 중복은 기존 row 반환 (`SubmitResult.deduplicated=True`). `cancel_order` 는 CREATED/SUBMITTED → CANCELED 만 허용, terminal/fill 진행 상태(FILLED/PARTIALLY_FILLED/CANCELED/REJECTED) 거부. `execute_pending_orders` 는 Phase C placeholder (`NotImplementedError`)
- [x] `app/db/models.py` — `VirtualAccount` (33번째) + `VirtualOrder` (34번째) ORM 추가. forbidden 컬럼 0건 (broker_order_id / kis_order_id / real_account / api_key / token / secret)
- [x] `alembic/versions/0005_virtual_trading_core.py` 신규 — 2 테이블 + 4 인덱스 + 2 unique constraint (`uq_virtual_accounts_user_name`, `uq_virtual_orders_account_idempotency`) + downgrade 포함
- [x] `app/data/repositories/virtual_account.py` 신규 — `create / get_by_id / list_by_user / get_default / update_cash_balance / set_paper_trading_enabled`
- [x] `app/data/repositories/virtual_order.py` 신규 — `create / get_by_id / list_by_account / get_by_idempotency_key / update_status / cancel`. side / order_type / status / quantity / limit_price 검증
- [x] `app/config/settings.py` — `paper_trading_enabled: bool = False` (env `PAPER_TRADING_ENABLED`)
- [x] `tests/unit/test_project_structure.py` — `paper_trading_enabled` 기본 False 단언 추가
- [x] `tests/unit/test_simulation_broker.py` 신규 (29건) — switch off / on, validation, idempotency, cancel, terminal-state guard, AST 기반 forbidden import 0건 단언, source-grep KIS/httpx/requests 0건 단언, `execute_pending_orders` Phase C placeholder
- [x] `tests/integration/test_virtual_trading_core.py` 신규 (16건) — repository CRUD, unique 제약 IntegrityError, cascade delete, broker end-to-end, forbidden 컬럼 0건, `alembic upgrade head` 가 두 신규 테이블 생성, `alembic downgrade 0004` 가 두 테이블만 drop
- [x] `tests/integration/test_alembic_migration.py` — `HEAD_REVISION='0005_virtual_trading_core'`, `EXPECTED_TABLE_COUNT=34`, spot-check / parametrize 에 `virtual_accounts` / `virtual_orders` 추가
- [x] `compare_metadata` 0건 가드 통과 (CI 강제)
- [x] **게이트: pytest 1322 → 1365 passed (+43)** — 회귀 0건. KIS API / 외부 네트워크 / Paper Trading API 라우터 / 프런트 변경 0건
- [ ] `tag v0.14-sim-broker + push`

### Phase C: VirtualPosition + PnL 추적 + CostModel 확장 ✅

- [x] `app/db/models.py` — `VirtualPosition` (35번째) + `VirtualFill` (36번째) + `VirtualPnLSnapshot` (37번째) ORM 추가. forbidden 컬럼 0건
- [x] `alembic/versions/0006_virtual_positions.py` 신규 — 3 테이블 + 11 인덱스 + 2 unique 제약 + downgrade
- [x] `app/data/repositories/virtual_position.py` 신규 — `get_by_account_symbol / list_by_account / list_open_by_account / get_or_create / upsert_position / update_realized_pnl / apply_buy / apply_sell`. `InsufficientPositionError` (숏셀링 거부)
- [x] `app/data/repositories/virtual_fill.py` 신규 — `create / list_by_order / list_by_account` (validation: side ∈ {BUY,SELL} / qty>0 / price>0 / cost ≥0)
- [x] `app/data/repositories/virtual_pnl_snapshot.py` 신규 — `create_or_replace_snapshot (idempotent upsert) / list_by_account (date range) / get_by_account_date`
- [x] `app/paper/__init__.py` + `app/paper/pnl_tracker.py` 신규 — `PnLTracker.apply_fill` (BUY: cash↓ position↑ avg_cost rebase; SELL: cash↑ realized_pnl 누적 + zero-out 시 avg_cost 리셋) + `create_daily_pnl_snapshot` (open positions × daily_prices.close, missing price = 0 graceful) + `InsufficientCashError`
- [x] `app/backtest/cost_model.py` — `PaperTradingCostModel` (paper-v1) 추가: buy_fee 0.015% / sell_fee 0.015% / sell_tax 0.18% (매도 only) / slippage 0.05%. **기존 CostModel 상수 변경 0건** (BacktestEngine 회귀 0건)
- [x] `app/broker/simulation_broker.py` — `execute_pending_orders(session, *, as_of_date, account_id?, pnl_tracker?, price_lookback_days=0)` 구현. MARKET = close 즉시 체결 / LIMIT BUY = close ≤ limit / LIMIT SELL = close ≥ limit / no price → skip / terminal status → skip / InsufficientCashError → REJECTED / InsufficientPositionError → REJECTED. `ExecutePendingResult` (filled / rejected / skipped_no_price / skipped_limit_unmet / skipped_terminal)
- [x] `tests/unit/test_paper_cost_model.py` 신규 8건 — 기본 rate / 기존 CostModel 회귀 / BUY·SELL 계산 / 잘못된 입력 거부 / frozen
- [x] `tests/integration/test_virtual_pnl_engine.py` 신규 27건 — repository CRUD / unique constraint / apply_buy/sell / insufficient cash / insufficient position / daily snapshot / missing price graceful / execute_pending MARKET·LIMIT·no-price·terminal·reject·account-filter / forbidden 컬럼 / Alembic upgrade·downgrade / forbidden imports AST
- [x] `tests/integration/test_alembic_migration.py` — `HEAD_REVISION='0006_virtual_positions'`, `EXPECTED_TABLE_COUNT=37`, spot-check / parametrize 에 3 테이블 추가
- [x] `tests/unit/test_simulation_broker.py` — Phase B placeholder 단언 제거 (이제 본 구현 존재; 통합 테스트가 행동 검증)
- [x] `compare_metadata` 0건 가드 통과
- [x] **게이트: pytest 1365 → 1405 passed (+40)** — 회귀 0건. KIS API / 외부 네트워크 / Paper Trading API 라우터 / 프런트 변경 0건. ScoringEngine / HoldingCheckEngine 본 weight 변경 0건
- [ ] `tag v0.14-pnl-tracker + push`

### Phase D: Paper Trading API + 스케줄러 잡

- [ ] `app/api/paper_routes.py` 신규
  - `GET /api/paper/account` — VirtualAccount 집계 (read-only)
  - `GET /api/paper/orders` — 주문 이력 (read-only)
  - `GET /api/paper/positions` — 포지션 현황 (read-only)
  - `GET /api/paper/pnl` — PnL 이력 (read-only)
  - `POST /api/paper/orders` — paper order 생성 (PAPER_TRADING_ENABLED=True + AUTH required, KIS API 0건)
  - `DELETE /api/paper/orders/{id}` — paper order 취소
- [ ] `app/api/schemas.py` — Paper Trading 스키마 8종 추가
- [ ] `app/api/__init__.py` — `paper_router` export
- [ ] `app/main.py` — `paper_router` 등록
- [ ] `app/scheduler/jobs.py` — `execute_paper_orders` (16:00 KST) + `create_paper_pnl_snapshot` (16:30 KST) 잡 추가
- [ ] `app/scheduler/scheduler.py` — 2 잡 등록 (PAPER_TRADING_ENABLED=False 시 SKIPPED)
- [ ] `tests/integration/test_paper_api.py` 신규 (~26건) — GET read-only / POST paper order / KIS API 0건 단언 / 405 guard
- [ ] `tag v0.14-paper-api + push` — **게이트: pytest ~1393 (+~26)**

### Phase E: Frontend 13번째 화면 + 마감 문서

- [ ] `frontend/src/api/types.ts` — Paper Trading 타입 추가
- [ ] `frontend/src/api/paper.ts` 신규 — fetchPaperAccount / fetchPaperOrders / fetchPaperPositions / fetchPaperPnl / submitPaperOrder / cancelPaperOrder
- [ ] `frontend/src/hooks/usePaperTrading.ts` 신규 — 6 TanStack Query hooks
- [ ] `frontend/src/pages/PaperTrading/index.tsx` 신규 (13번째 화면 `/paper`) — VirtualAccountCard / PaperOrderForm / VirtualPositionsTable / PnLChart / PaperOrdersTable
- [ ] `frontend/src/router.tsx` — PaperTradingPage lazy + `/paper` route
- [ ] `frontend/src/components/layout/Sidebar.tsx` — `TrendingUp` 아이콘 + `페이퍼 트레이딩 (β)` 메뉴 (13번째)
- [ ] `frontend/src/tests/mswServer.ts` — paper GET 핸들러 추가 (default empty)
- [ ] `frontend/src/tests/PaperTrading.test.tsx` 신규 — vitest ~10건 (page wrapper / empty / happy / no-automation guard)
- [ ] `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts` — sidebar 12→13 menus + `/paper` navigation
- [ ] `RELEASE_NOTES_v0.14.md` 신규
- [ ] `README.md` v0.14 갱신 (배너 / 기능 목록 / 누적 사이클 표 / 회귀 기준선)
- [ ] `PROJECT_STATUS.md` §0 v0.14 마감 선언
- [ ] `ROADMAP.md` v0.14 행 ✅ 마감
- [ ] `TESTING.md` 기준선 갱신
- [ ] `ARCHITECTURE.md` / `API_SPEC.md` / `INTEGRATION_RUNBOOK.md` / `DB_SCHEMA.md` v0.14 반영
- [ ] 최종 4 게이트 확인 (pytest ~1393 / vitest ~185 / e2e 22 / build)
- [ ] `tag v0.14-final + push`

---

## v0.15+ — Backlog

자세한 분류는 [`ROADMAP.md`](./ROADMAP.md) / [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) 참조. 한 줄 요약:

- **Approval Trading 준비** — OrderCandidate / 승인 플로우 설계 + skeleton (Paper Trading 안정 후, v0.15 후보)
- **ScoringEngine 본 weight 보강** — v0.13/v0.14 validation report 결과 기반 (누적 데이터 6개월+ 필요)
- **Grafana dashboard JSON 동봉** — v0.11 Prometheus exporter 위 시각화 layer (외부 인프라)
- **ProviderHealthMonitor 영속화** — DB / Redis 백업으로 재시작 후 history 유지
- **인증 고도화** — refresh token / 다중 사용자 / OAuth / RBAC (단일 사용자 운영 검증 후)
- **CSP / rate limit 튜닝** — 실 트래픽 수집 후 정책 수립
- **LLM sentiment / 자동 요약** — 룰 기반 검증 후 (외부 LLM API 비용 / 보안 / 라이선스)
- **WebSocket / SSE 실시간 갱신** — Provider Health / 백테스트 진행 (현재 polling)
- **`/api/health/jobs` 분리 + Provider toggle GUI** — 인증 + 보안 검토 동반
- **모바일 / 태블릿 / lightweight-charts 마이그레이션** — UX 고도화
- **Watchlist 가격 알림 / target return alert** — 알림 시스템 별도 cycle
- **Future Backlog (자동매매)** — APPROVAL / SMALL_AUTO / FULL_AUTO 모두 별도 보안·컴플라이언스 사이클 선행 필수

## 완료 기준

- [x] v0.1 기능이 mock 데이터로 동작 (`scripts/seed_mock_data.py` + `INTEGRATION_RUNBOOK.md`)
- [x] 핵심 테스트 통과 (296 passed)
- [x] 실거래 주문 코드 없음 (`BrokerInterface` placeholder만 존재)
- [x] snapshot/log 저장 가능 (`data_snapshots`, `decision_logs`, `job_runs`, `notification_logs`)
- [x] 텔레그램 메시지 포맷 가능 (DRY_RUN 기본)
- [x] 대시보드 API 응답 가능 (13개 GET 라우터, holding metric summary 포함)
