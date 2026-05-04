# TESTING.md

## 1. 테스트 목표

v0.1의 목표는 실거래 없는 안정적인 분석/추천/보유점검 시스템이다.

테스트의 핵심은 다음이다.

- 지표 계산 정확성
- 점수 계산 일관성
- 추천/보유 판단 저장
- snapshot/log 저장
- 외부 API mock 처리
- 텔레그램 메시지 포맷
- FastAPI 조회 API
- v0.1 범위 위반 방지

## 2. 테스트 도구

- pytest
- pytest-asyncio 필요 시
- httpx TestClient
- respx 또는 responses
- SQLite test DB 또는 PostgreSQL test DB

## 3. 테스트 폴더 구조

```text
tests/
├─ unit/
│  ├─ test_technical_analyzer.py
│  ├─ test_scoring_engine.py
│  ├─ test_recommendation_engine.py
│  ├─ test_holding_check_engine.py
│  └─ test_report_generator.py
├─ integration/
│  ├─ test_repositories.py
│  ├─ test_api_routes.py
│  └─ test_scheduler_jobs.py
└─ mocks/
   ├─ kis_responses.py
   └─ sample_market_data.py
```

## 4. 필수 테스트

### TechnicalAnalyzer

- MA 계산
- RSI 계산
- MACD 계산
- volume_ratio_20d 계산
- breakout 계산
- 데이터 부족 시 처리

### ScoringEngine

- 신규 추천 점수 공식
- 보유 종목 점수 공식
- risk_penalty 반영
- AI 점수 비중 제한

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

## 5. 금지 사항

테스트에서 금지:

- 실제 KIS API 호출
- 실제 텔레그램 발송
- 실제 계좌번호 사용
- 실제 주문 API 호출
- 실거래 관련 테스트 구현

## 6. 테스트 실행 명령 예시

```powershell
.\.venv\bin\python.exe -m pytest
.\.venv\bin\python.exe -m pytest tests/unit
.\.venv\bin\python.exe -m pytest tests/integration
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

Phase 5-1 `RecommendationEngine` 통합 테스트는 SQLite in-memory DB와 Repository 9종을
연결해 추천 흐름 전체를 검증한다.

- 유니버스 미존재 / 멤버 0 → status="EMPTY" run 생성, recommendations 0건
- 지표 없는 종목 자동 skip + `skipped_no_indicator` 카운트
- TOP N 정렬 (`total_score desc`, 동점 시 `symbol asc`)
- `recommendation_runs` `started_at`/`finished_at`/`status`/`market_summary` 기록
- `recommendations` 행이 `data_snapshots`와 `decision_logs`에 같은 `snapshot_id`로 연결
- `news_score`/`supply_score`/`fundamental_score`/`ai_score`/`risk_score` 모두 None
- `reason` = "관찰 후보 …" / `risk_note` = "Phase 5-1 placeholder"
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
  - `holding_checks` 중 `alert=True` 인 항목에 대해 `risk_alert` 포맷터로 알림 생성
  - `notification_logs.message_type = "ALERT"` 로 저장
  - 동일한 `symbol + check_date + check_type` 대상은 재실행 시 중복 발송 방지 (Skip)
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

Phase 8 `Scheduler / Jobs` 테스트는 `BackgroundScheduler`를 실제로 시작하지
않고 잡 함수와 `run_job` 래퍼를 직접 호출해 검증한다 (시간 대기 / 실제
트리거 발화는 사용하지 않음).

`tests/integration/test_scheduler_jobs.py`:
- `run_job` 래퍼: SUCCESS / PARTIAL / FAILED(예외) / 예외 시 작업 세션 롤백 /
  성공 시 작업 세션 commit / 호출마다 별도 `job_run_id` / 등록된 잡 함수와
  연결
- 6개 잡 함수: 빈 DB → placeholder/skipped, 시드 후 실제 service/engine 호출
  검증 (`TechnicalIndicatorService`, `RecommendationEngine`, `HoldingCheckEngine`)
- 모든 잡 결과의 `telegram_sent`는 False, KIS API 호출 없음

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
- `news_score`/`earnings_score`/`ai_score`/`risk_score` 모두 None,
  `decision_logs.ai_result_json` = None, `placeholder_components` 명시
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

## 7. 코드 리뷰 체크리스트

- Data 모듈이 추천 판단을 하지 않는가?
- Analysis 모듈이 외부 API를 호출하지 않는가?
- Recommendation 모듈이 KIS API를 직접 호출하지 않는가?
- Notification 모듈이 점수 계산을 하지 않는가?
- API 라우터가 추천 생성을 직접 하지 않는가?
- 실거래 주문 코드가 없는가?
- API 키/토큰이 노출되지 않는가?
- snapshot/log 저장이 보장되는가?
