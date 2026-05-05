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

## Backlog (v0.2 이후)

v0.1 범위 외. v0.3 cycle 진입 시점에 일부는 v0.3 phase 로 승격되었다 (아래 v0.3 섹션 참조).

- [x] **v0.2 PC 대시보드 프론트엔드** — `v0.2-frontend-final` 마감 ✅ (Vite + React, 8 화면)
- [→ v0.3 Phase B] 캔들 패턴 + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
- [ ] Strategy 모듈 (장기/중기/단기 관리, SIGNAL / PAPER 모드)
- [ ] Backtest 엔진 (walk-forward 검증, 그리드 서치 튜닝)
- [ ] MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- [ ] 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- [ ] 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 `DummyScoreProducer` placeholder)
- [ ] APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래 — `BrokerInterface` placeholder만 유지)
- [ ] 인증 / 권한 (단일 사용자 / 사내망 외 노출 시)
- [ ] 운영 모니터링 (Sentry / Prometheus / Grafana)
- [ ] 즐겨찾기 / 관심 종목 (POST 라우터 도입 필요)
- [ ] 글로벌 검색 (cmd+k)
- [ ] 모바일 / 태블릿 레이아웃

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

### Phase B — 캔들 패턴 + ATR 변동성 컴포넌트

- [ ] `app/analysis/technical_analyzer.py` — `compute_atr14`, `detect_candle_patterns(망치형/도지/장악형/슈팅스타)` 구현
- [ ] `IndicatorSnapshot` (또는 부속) 에 `atr14`, `candle_patterns` 추가
- [ ] `technical_score` 합산식 보강 (가중치 ±5 점 이내, 0~100 clamp 유지)
- [ ] `app/db/models.py` `StockIndicator` 컬럼 추가: `atr14`, `candle_patterns` (JSON)
- [ ] `app/data/repositories/stock_indicators.py` `upsert` 시그니처 갱신
- [ ] `app/analysis/indicator_service.py` 신규 필드 채움
- [ ] `app/api/schemas.py` `StockIndicatorSchema` 에 두 필드 추가
- [ ] `tests/unit/test_technical_analyzer.py` ATR / 캔들 패턴 단위 테스트 (~6 신규)
- [ ] `tests/integration/test_indicator_service.py` 신규 컬럼 통합 검증
- [ ] backend `pytest -q` 296 → 296 + N 통과
- [ ] mock seed 적재 후 `/api/stocks/005930` 응답에 `atr14` / `candle_patterns` 노출
- 완료 기준: 등급 분포 S~C 까지 분포 (이전 D~C 대비 개선). 태그 `v0.3-backend-analysis`.

### Phase C — 한국거래소 휴장일 캘린더

- [ ] `frontend/src/data/krxHolidays.ts` 정적 JSON (2026~2027 +) — 출처 / 갱신 절차 주석
- [ ] `frontend/src/lib/marketCalendar.ts` — `isMarketClosed` / `nextOpenDay` / `previousOpenDay`
- [ ] `frontend/src/components/common/MarketStatusBanner.tsx`
- [ ] Today / Jobs / Holdings 헤더에 Banner 통합
- [ ] `frontend/src/tests/marketCalendar.test.tsx` (신규) — 6~8 케이스
- [ ] `frontend/src/tests/MarketStatusBanner.test.tsx` (신규)
- [ ] e2e: 평일 가정 fixture, Banner 노출 검증 1건 추가 (6 → 7)
- 완료 기준: 휴장/평일/주말 분기 정확. vitest 36 → ~40, e2e 6 → 7. 태그 `v0.3-frontend-calendar`.

### Phase D — StockDetail 일봉 차트

- [ ] `app/api/routes.py` — `GET /api/stocks/{symbol}/prices?days=120` (max 500) 신규
- [ ] `app/api/schemas.py` — `StockPriceSeriesResponse` 추가
- [ ] `tests/integration/test_api_routes.py` — happy / empty / 404 3건
- [ ] `frontend/src/api/types.ts` — `StockPriceSeriesResponse` 추가
- [ ] `frontend/src/hooks/useStockPriceSeries.ts` (신규)
- [ ] `frontend/src/pages/StockDetail/PriceChart.tsx` (신규, Recharts 재사용)
- [ ] `frontend/src/pages/StockDetail/index.tsx` 차트 카드 + empty placeholder
- [ ] `frontend/src/tests/StockDetail.test.tsx` 차트 happy / empty 보강
- [ ] `frontend/src/tests/mswServer.ts` + `frontend/e2e/fixtures/apiMocks.ts` handler 추가
- 완료 기준: backend pytest +3, frontend vitest ~+2, e2e ~+1. 차트가 종목 상세 화면에 노출. 태그 `v0.3-frontend-stock-chart`.

### Phase E — v0.3 릴리스 문서 / 마감

- [ ] `RELEASE_NOTES_v0.3.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.4 후보 / 가이드 / 보안)
- [ ] `README.md` 상단 마감 배너 갱신 + 누적 태그 라인
- [ ] `PROJECT_STATUS.md` §0 v0.3 마감, 기존 §0 → §0-1, §0-2
- [ ] `TASKS.md` v0.3 phase 모두 [x]
- [ ] backend pytest + frontend vitest + e2e + build 4 게이트 그린
- [ ] tag `v0.3-final` + push
- 완료 기준: 모든 게이트 그린, tag publish, GitHub Release 본문에 RELEASE_NOTES 붙여넣기 (UI 작업).

## 완료 기준

- [x] v0.1 기능이 mock 데이터로 동작 (`scripts/seed_mock_data.py` + `INTEGRATION_RUNBOOK.md`)
- [x] 핵심 테스트 통과 (296 passed)
- [x] 실거래 주문 코드 없음 (`BrokerInterface` placeholder만 존재)
- [x] snapshot/log 저장 가능 (`data_snapshots`, `decision_logs`, `job_runs`, `notification_logs`)
- [x] 텔레그램 메시지 포맷 가능 (DRY_RUN 기본)
- [x] 대시보드 API 응답 가능 (13개 GET 라우터, holding metric summary 포함)
