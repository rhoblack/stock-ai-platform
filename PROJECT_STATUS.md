# PROJECT_STATUS.md

v0.1 진행 상태 스냅샷 (현재 세션 종료 시점). 새 Codex 세션이 이어서 작업을
시작할 때 가장 먼저 읽어야 할 파일이다. AGENTS.md / TASKS.md와 함께 사용한다.

---

## 1. 완료된 Phase

| Phase | 범위 | 주요 산출물 |
|---|---|---|
| **0** 프로젝트 준비 | 13개 문서 + 초기 커밋 | AGENTS.md, README, ARCHITECTURE, API_SPEC, DB_SCHEMA, ROADMAP, SECURITY, TESTING, TASKS, PLANS, brief / detailed_spec / agent_creation_spec |
| **1** 아키텍처/골격 | FastAPI 앱, 4개 인터페이스 | `app/main.py`, `app/config/`, `DataProviderInterface`, `AIProviderInterface`, `BrokerInterface`, `StrategyInterface`, `.env.example` |
| **2** DB/Repository | 17개 ORM 모델 + Repository | `app/db/{base,models,session}.py`, `app/data/repositories/*.py` (16개 클래스) |
| **3-1** KIS DTO/normalizer/validator | DTO + 정규화 + 품질 검사 | `app/data/dtos.py`, `app/data/normalizers/kis.py`, `app/data/validators/quality.py` |
| **3-2** KIS HTTP 클라이언트 | httpx 기반 read-only 클라이언트 | `app/data/collectors/kis_client.py` (토큰/현재가/일봉/시총) |
| **3-3** Collector | KIS raw → DB 저장 흐름 | `DailyPriceCollector`, `MarketCapRankingCollector`, `FakeKisDataProvider` (테스트용) |
| **4-1** TechnicalAnalyzer | 순수 지표 계산기 | `app/analysis/technical_analyzer.py` (MA/RSI/MACD/breakout/ma_alignment/technical_score) |
| **4-2** IndicatorService + ScoringEngine | 저장 서비스 + 점수 산식 | `app/analysis/indicator_service.py`, `app/decision/scoring_engine.py` (신규 추천/보유 가중치) |
| **5-1** RecommendationEngine | 추천 골격 (placeholder 점수) | `app/decision/recommendation_engine.py`, `recommendation_runs/recommendations/data_snapshots/decision_logs` 4개 테이블 일괄 저장 |
| **5-2** HoldingCheckEngine | 장전/장후 보유 점검 | `app/decision/holding_check_engine.py`, HOLD/WATCH/REDUCE/SELL_REVIEW 결정, 위험 경고 평가 |
| **5-3** RiskEngine | risk_penalty / risk_level / risk_flags | `app/decision/risk_engine.py`, ScoringEngine 및 양 Engine 연결, `data_snapshots`/`decision_logs`에 risk 결과 기록 |
| **5 후속** 추천 성과 검증 | 1/3/5/20일 후 수익률 계산 | `app/decision/recommendation_result_service.py`, `recommendation_results` upsert 멱등 |
| **6** Notification & Report | 텔레그램용 텍스트 + 발송 + 로그 | `app/notification/report_generator.py`, `telegram_notifier.py`, `notification_service.py` (DRY_RUN 기본) |
| **7** Backend API | 13개 read-only GET 라우터 | `app/api/{schemas,routes}.py`, FastAPI lifespan 통합, 모든 Decimal은 JSON 문자열 직렬화 |
| **7 후속** API 성과 노출 | 추천 항목에 `results[]` + history 집계 | `RecommendationResultSchema`, `RecommendationHistoryItem` 확장 (`success_rate`, `avg_close_return_{1,3,5,20}d`) |
| **8** Scheduler + 6개 Job | APScheduler + `run_job` 래퍼 | `app/scheduler/{jobs,scheduler}.py`, FastAPI lifespan에서 lazy import 후 시작/종료, `SCHEDULER_ENABLED` 제어 |
| **8 후속** Dispatcher 연결 | 추천/보유/ALERT 잡 → 텔레그램 자동 발송 | `app/notification/dispatchers.py`, 잡에서 `session.info["job_run_id"]`로 `notification_logs.related_job_id` 자동 연결, `HoldingRiskAlertDispatcher` 연동 완료 |

브리프 전체 v0.1 범위 + 일부 v0.2 후속 (성과 검증, dispatcher) 까지 도달.

---

## 2. 현재 테스트 결과

```text
266 passed in 5.00s
```

| 영역 | 파일 수 | 테스트 수 |
|---|---:|---:|
| `tests/unit/` | 10 | 124 |
| `tests/integration/` | 11 | 142 |

**테스트 파일별 카운트:**

```text
tests/integration/test_api_routes.py                     35
tests/integration/test_collectors.py                      8
tests/integration/test_dispatchers.py                    11
tests/integration/test_holding_check_engine.py           17
tests/integration/test_indicator_service.py               7
tests/integration/test_notification_service.py            6
tests/integration/test_recommendation_engine.py          13
tests/integration/test_recommendation_result_service.py  13
tests/integration/test_repositories.py                    6
tests/integration/test_scheduler_jobs.py                 19
tests/integration/test_v01_required_repositories.py       7
tests/unit/test_data_quality_checker.py                   4
tests/unit/test_kis_client_http.py                        9
tests/unit/test_kis_normalizers.py                        3
tests/unit/test_project_structure.py                      4
tests/unit/test_report_generator.py                      12
tests/unit/test_risk_engine.py                           25
tests/unit/test_scheduler_module.py                       5
tests/unit/test_scoring_engine.py                        16
tests/unit/test_technical_analyzer.py                    32
tests/unit/test_telegram_notifier.py                     14
```

회귀 0건. 모든 외부 호출(KIS, Telegram)은 mock transport / dry-run 으로만 접근.

---

## 3. 변경된 주요 모듈

| 패키지 | 핵심 모듈 | 책임 |
|---|---|---|
| `app/config/` | `settings.py`, `logging.py` | env 기반 Settings (`@lru_cache`), telegram/KIS/feature flags 포함 |
| `app/db/` | `base.py`, `models.py`, `session.py` | SQLAlchemy 2.0, 17개 v0.1 테이블, `SessionLocal` |
| `app/data/` | `interfaces.py`, `dtos.py`, `collectors/`, `normalizers/`, `validators/`, `repositories/` | 외부 API 경계, 16개 Repository, KisClient + 정규화 + 품질 검사 |
| `app/analysis/` | `technical_analyzer.py`, `indicator_service.py` | 순수 지표 계산 + `daily_prices` → `stock_indicators` upsert |
| `app/decision/` | `scoring_engine.py`, `risk_engine.py`, `recommendation_engine.py`, `holding_check_engine.py`, `recommendation_result_service.py` | 점수/리스크/추천/보유점검/사후 성과 |
| `app/notification/` | `report_generator.py`, `telegram_notifier.py`, `notification_service.py`, `dispatchers.py` | 텔레그램 텍스트 포맷 + 발송 (DRY_RUN 기본) + 로그 + dispatcher |
| `app/api/` | `schemas.py`, `routes.py` | 13개 GET 라우터, Pydantic v1 schema, Decimal → str 일관 직렬화 |
| `app/scheduler/` | `jobs.py`, `scheduler.py` | `run_job` 2-session 래퍼, 6개 잡, APScheduler `BackgroundScheduler` |
| `app/main.py` | FastAPI 앱 + `lifespan` | 라우터 등록, 스케줄러 lazy import 시작/종료, `/health` |

**의존성 (`pyproject.toml`):** fastapi 0.99, pydantic 1.10, SQLAlchemy 2.0, httpx 0.24+, uvicorn 0.30+, python-dotenv, **apscheduler 3.10+** (Phase 8에서 추가).

---

## 4. 아직 하지 않은 작업

**v0.1 범위 안에서 남은 것**

- `collect_market_close_data` 잡의 실제 KIS 수집 연결 (현재 placeholder; 실 KIS API 키 + Phase 3-3 collector 호출 연결 필요)
- 캔들 패턴 / ATR 변동성 컴포넌트 → `technical_score` 산식 보강 (Phase 4 후속)
- News / Supply / Fundamental / Earnings / AI dummy score producer → 등급 분포 활성화 (현재 technical 단독으로 D~C에 머무름)
- `/api/stocks/{symbol}` 응답에 그 종목의 최근 추천 이력 + `recommendation_results` join
- `/api/holdings/{symbol}/checks` 응답에 일별 손익률 추세 등 metric 추가
- PROJECT_STATUS.md (현재 파일) — 신규 세션마다 수동 갱신 필요

**v0.2 이후로 미룬 범위**

- React/Next.js PC 대시보드 프론트엔드
- 전략(장기/중기/단기) 관리, SIGNAL/PAPER 모드
- 백테스트 엔진, walk-forward 검증, 그리드 서치 튜닝
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래)

---

## 5. 다음에 이어서 할 첫 번째 작업

**News/Supply/Fundamental/Earnings/AI dummy score producer (등급 분포 활성화) 및 API 응답에 추천 이력 Join**

이유:
- 즉시 ALERT dispatcher 연동까지 포함해 추천 및 점검, 알림(Dispatcher)의 기초 흐름이 모두 완료되었습니다.
- 현재 신규 추천 및 보유 점수 산출 시 technical(기술적 분석) 단독으로만 점수가 책정되어 있어, 등급 분포가 D~C 하위권에 머물고 있습니다. 
- 이를 해소하기 위해 나머지 정성적/정량적 지표(News, Fundamental 등)에 대한 Dummy Score를 부여하여 S~D 등급이 정상적으로 분포되도록 활성화하는 작업이 필수적입니다.
- 연이어 대시보드 API(`.api/stocks/{symbol}`)에서 그 종목의 과거 추천 이력(`recommendation_results`)을 Join하여 프론트엔드가 활용할 수 있게 완성도를 높입니다.

---

## 6. 주의해야 할 v0.1 금지사항

`AGENTS.md` "Out of Scope" 섹션과 `SECURITY.md`를 어기지 말 것. 핵심:

**기능 금지**

- 실거래 자동매매, FULL_AUTO 모드, 가상 증권사 서버, 전략 자동 튜닝, 전용 AI 모델 학습
- KIS 주문 API 실행 (조회만 OK; 주문은 `BrokerInterface` placeholder만 유지)
- 대시보드 라우터 안에서 추천 생성 / 보유점검 실행 / 지표 재계산 / KIS 호출
- POST/PUT/DELETE 라우터 (현재 13개 모두 GET; 새 POST 라우터 만들지 말 것)
- 자동매매 / 주문 / 비중 결정 코드를 AI나 LLM이 단독으로 호출하는 경로

**보안 / 비밀**

- KIS app_key / app_secret / access_token / refresh_token / 계좌번호
- Telegram bot_token, chat_id (chat_id는 `12****90` 형태로만 노출)
- OpenAI API key, DB 비밀번호
- 위 값을 코드 / 로그 / 테스트 / 응답 본문 어디에도 평문 노출 금지
- `.env`는 절대 커밋 금지, `.env.example`만 커밋

**테스트**

- 실제 KIS API 호출하는 테스트 금지 → `httpx.MockTransport` 또는 `FakeKisDataProvider`
- 실제 텔레그램 발송 테스트 금지 → `telegram_enabled=False` (DRY_RUN) 또는 `httpx.MockTransport`
- 시간이 실제로 될 때까지 기다리는 스케줄러 테스트 금지 → 잡 함수를 직접 호출
- 실제 API 키 / 계좌번호를 테스트에 사용 금지 (모두 `fake_*` placeholder 사용)

**아키텍처 경계**

- Data 모듈은 판단하지 않는다 (Collector → Recommendation 직접 호출 금지)
- Analysis 모듈은 외부 API 호출하지 않는다
- Recommendation/Holding 모듈은 KIS API 직접 호출하지 않는다 (Repository 경유)
- AI 모듈이 직접 매매하지 않는다
- 라우터는 Repository 또는 service를 통해서만 데이터 조회
- 새 잡이 라우터를 호출하지 않는다 (잡 → service / dispatcher 직접)

**관찰성**

- 모든 추천/보유점검은 `data_snapshots` + `decision_logs`에 기록 가능해야 함
- 모든 잡 실행은 `job_runs`에 기록 (성공/PARTIAL/FAILED)
- 모든 텔레그램 발송 시도는 `notification_logs`에 기록 (DRY_RUN/SUCCESS/FAILED/DISABLED)

---

## 7. 다음 Codex 세션 첫 프롬프트

새 세션을 시작하면 아래 프롬프트를 그대로 사용한다.

```text
이 프로젝트의 AGENTS.md, TASKS.md, PROJECT_STATUS.md, SECURITY.md를 먼저 읽고
v0.1 범위 / 현재 진행 상태 / 금지사항을 파악해줘.

코드는 아직 수정하지 마. 다음 두 가지만 알려줘.
1. PROJECT_STATUS.md 의 "5. 다음에 이어서 할 첫 번째 작업"이 여전히 적합한가?
   (그 사이 사용자가 다른 우선순위를 말하지 않았다면 적합하다고 가정)
2. 작업을 시작하기 전에 미리 알아둬야 할 의문/리스크가 있는가?

내가 "진행해" 라고 답하면 그때부터 다음 작업의 PM/Architect 시점으로
PLANS.md 형식의 짧은 실행 계획을 먼저 작성해줘 (수정할 파일 / 새로 만들
파일 / 단계 / 테스트 / 완료 기준 / 위험 요소). 계획을 내가 승인하면
구현으로 들어가.

작업 중에는 v0.1 금지사항(특히 실거래 / 실 KIS 호출 / 실 텔레그램 발송 /
라우터 안에서 무거운 로직)을 어기지 마. 새 기능은 항상:
  - 기존 service/engine을 호출하거나
  - 기존이 없으면 안전한 placeholder를 반환하고
  - 모든 외부 호출은 mock 가능한 구조로 만들고
  - 모든 추천/보유점검/잡/알림은 snapshot/log/job_runs/notification_logs로
    추적 가능하게 만들어.
```
