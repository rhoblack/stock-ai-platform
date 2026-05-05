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

- [ ] `app/api/routes.py` — `GET /api/stocks/{symbol}/reports?limit=10` 신규 read-only 라우터 (또는 `/api/stocks/{symbol}` 응답에 `latest_consensus + recent_reports[]` 통합 — PR 시 결정)
- [ ] `app/api/schemas.py` — `AnalystReportSchema`, `ReportConsensusSchema` 신규
- [ ] `app/api/schemas.py` — `AnalystReportSchema` 에서 `source_file_path` **제외** (응답 마스킹)
- [ ] `tests/integration/test_api_routes.py` — happy / empty / 404 / `source_file_path` 부재 단언 ~3건
- [ ] `frontend/src/api/types.ts` — `AnalystReport` (no source_file_path), `ReportConsensus`, `StockReportsResponse` 추가
- [ ] `frontend/src/hooks/useStockReports.ts` (신규)
- [ ] `frontend/src/pages/StockDetail/AnalystReportsCard.tsx` (신규, 컨센서스 요약 + 최근 5건 + source_url 클릭)
- [ ] `frontend/src/pages/StockDetail/index.tsx` — 차트 카드 다음에 리포트 카드 추가
- [ ] `frontend/src/pages/Recommendations/RecommendationsTable.tsx` — `report_score` 컬럼 + tooltip + null fallback `—`
- [ ] `frontend/src/tests/StockDetail.test.tsx` — 리포트 카드 happy / empty / `source_file_path` 부재 ~3건
- [ ] `frontend/src/tests/Recommendations.test.tsx` — `report_score` 컬럼 happy / null fallback ~1건
- [ ] `frontend/src/tests/mswServer.ts` — `/api/stocks/:symbol/reports` 기본 핸들러
- [ ] `frontend/e2e/fixtures/apiMocks.ts` — 005930 sample reports fixture
- [ ] `frontend/e2e/dashboard.spec.ts` — 리포트 카드 노출 + `source_file_path` 미노출 e2e ~1건
- 완료 기준: backend pytest ~356 → ~359, frontend vitest 59 → ~63, e2e 8 → 9. 태그 `v0.4-frontend-reports`.

### Phase E — v0.4 릴리스 문서 / 마감

- [ ] `RELEASE_NOTES_v0.4.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.5 후보 / 운영 가이드 / **저작권·보안**)
- [ ] `RELEASE_NOTES_v0.4.md` §보안 — 4 정책 명시 (원문 본문 미저장 / PDF 미저장 / 자동 크롤링 금지 / source_file_path 외부 노출 금지)
- [ ] `README.md` 상단 마감 배너 v0.4 갱신 + 누적 태그 라인 + 저작권 한 줄
- [ ] `PROJECT_STATUS.md` §0 v0.4 시작 → v0.4 마감으로 in-place 갱신, §0-1 v0.3 / §0-2 v0.2 / §0-3 v0.1 그대로 보존
- [ ] `TASKS.md` v0.4 phase 모두 [x]
- [ ] backend pytest + frontend vitest + e2e + build 4 게이트 그린 (재확인)
- [ ] tag `v0.4-final` + push
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES_v0.4 붙여넣기 (UI 작업).

## 완료 기준

- [x] v0.1 기능이 mock 데이터로 동작 (`scripts/seed_mock_data.py` + `INTEGRATION_RUNBOOK.md`)
- [x] 핵심 테스트 통과 (296 passed)
- [x] 실거래 주문 코드 없음 (`BrokerInterface` placeholder만 존재)
- [x] snapshot/log 저장 가능 (`data_snapshots`, `decision_logs`, `job_runs`, `notification_logs`)
- [x] 텔레그램 메시지 포맷 가능 (DRY_RUN 기본)
- [x] 대시보드 API 응답 가능 (13개 GET 라우터, holding metric summary 포함)
