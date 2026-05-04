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
| **8 후속** 잡 최종 점검 | 6개 잡 모두 dispatcher / engine / NO_DATA·PARTIAL 분기 정리 | `send_recommendation_report`은 최신 run을 dispatcher로 발송 (NO_DATA 단락), `run_pre/post_market_holding_check`은 활성 보유 없으면 NO_DATA 단락, `update_recommendation_results`는 `data_status` SUCCESS/PARTIAL/NO_DATA + skipped_no_reference 시 PARTIAL |
| **4 후속** Dummy score producer | News/Supply/Fundamental/Earnings/AI 컴포넌트 점수 placeholder | `app/analysis/score_producers.py` (`DummyScoreProducer`), `RecommendationEngine`/`HoldingCheckEngine` 생성자 default 주입 — neutral 50 + volume_ratio_20d / ma_alignment 기반 룰베이스 ±5 nudge, 메타데이터 `decision_logs.rule_result_json["score_producer"]`에 저장 |
| **7 후속** Stock detail 추천 이력 join | `/api/stocks/{symbol}` 응답에 추천 이력 + 1/3/5/20일 성과 | `_resolve_recent_recommendations_for_symbol` (Recommendation+RecommendationRun join, run_date desc), `RecommendationItemSchema.results: List[RecommendationResultSchema]` 채움, `recommendation_limit`/`holding_check_limit` 쿼리 파라미터 |
| **7 후속** Holding check 추세 metric | `/api/holdings/{symbol}/checks` 응답에 종목 단위 summary 추가 | `HoldingCheckSymbolMetrics`/`HoldingCheckSymbolResponse` 신규 schema, summary는 limit 무관하게 종목 전체 이력 집계 (total/alert/high_risk count + latest/previous/change + best/worst return rate + latest decision/risk_level), 정렬 규칙 `(check_date desc, POST > PRE)` |
| **9** v0.1 통합 시나리오 / mock seed | 실 KIS·실 텔레그램 없이 백엔드 전체 흐름 로컬 검증 | `scripts/seed_mock_data.py` (멱등 + `--reset`), `INTEGRATION_RUNBOOK.md` (사전준비 → 시드 → 6개 잡 수동 트리거 → 13개 GET API → 로그 검증 → 회귀 게이트), README §9 진입점 |

브리프 전체 v0.1 범위 + 일부 v0.2 후속 (성과 검증, dispatcher, holding metric, 통합 시나리오) 까지 도달. **v0.1 백엔드 마감 상태** — 코드 변경이 남은 v0.1 항목은 §4 "남은 v0.1 작업" 의 두 건뿐이며, 이번 작업으로 신규 세션 / QA 인수자가 mock seed + runbook 만으로 전체 흐름을 30분 안에 검증 가능.

---

## 2. 현재 테스트 결과

```text
296 passed in 5.48s
```

| 영역 | 파일 수 | 테스트 수 |
|---|---:|---:|
| `tests/unit/` | 11 | 127 |
| `tests/integration/` | 11 | 169 |

**테스트 파일별 카운트:**

```text
tests/integration/test_api_routes.py                     42
tests/integration/test_collectors.py                      8
tests/integration/test_dispatchers.py                    16
tests/integration/test_holding_check_engine.py           17
tests/integration/test_indicator_service.py               7
tests/integration/test_notification_service.py            6
tests/integration/test_recommendation_engine.py          13
tests/integration/test_recommendation_result_service.py  13
tests/integration/test_repositories.py                    6
tests/integration/test_scheduler_jobs.py                 34
tests/integration/test_v01_required_repositories.py       7
tests/unit/test_data_quality_checker.py                   4
tests/unit/test_kis_client_http.py                        9
tests/unit/test_kis_normalizers.py                        3
tests/unit/test_project_structure.py                      4
tests/unit/test_report_generator.py                      12
tests/unit/test_risk_engine.py                           25
tests/unit/test_scheduler_module.py                       5
tests/unit/test_score_producers.py                        3
tests/unit/test_scoring_engine.py                        16
tests/unit/test_technical_analyzer.py                    32
tests/unit/test_telegram_notifier.py                     14
```

회귀 0건. 모든 외부 호출(KIS, Telegram)은 mock transport / dry-run 으로만 접근.

### v0.1 통합 실행 결과 (1회 수행)

`INTEGRATION_RUNBOOK.md` §1 ~ §5 시나리오를 실제로 1회 수행한 결과 (UTC
2026-05-04 22:52 / Asia/Seoul 2026-05-05 07:52, throwaway SQLite 파일).

**1. Seed (`scripts.seed_mock_data --reset`)**

```text
stocks:5  market_cap_rankings:5  universe_members:5  daily_prices:150
stock_indicators:5  holdings:2  recommendation_runs:3  recommendations:8
holding_checks:4  data_snapshots:12
```

**2~7. 6개 잡 수동 트리거 (모두 SUCCESS, dry-run)**

| 잡 | status | 핵심 result_summary |
|---|---|---|
| `collect_market_close_data` | SUCCESS | mock provider 주입, market_cap_status=SUCCESS, daily=5/5 success |
| `calculate_technical_indicators` | SUCCESS | members=5, snapshots_saved=5, skipped=0, fail=0 |
| `send_recommendation_report` | SUCCESS | notification_status=DRY_RUN, run_date=2026-05-04, recs=3, msg_len=364 |
| `run_pre_market_holding_check` | SUCCESS | check_type=PRE_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `run_post_market_holding_check` | SUCCESS | check_type=POST_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `update_recommendation_results` | SUCCESS | data_status=SUCCESS, runs=3, processed=8, upserted=32, pending=29, success=0, failed=3, skipped_no_ref=0 |

**8. notification_logs / job_runs**

- `notification_logs`: 7건 — REPORT 3 (recommendation 1 + holding pre/post 2) + ALERT 4 (HIGH_RISK 3 + CHECK_ALERT 1, target dedup 키 정상)
- `job_runs`: 6건, 모두 SUCCESS. result_summary / status / error_message / finished_at 정상 기록
- `holding_checks`: 8건 (005930 5 + 000660 3) — 시드의 4건 + 잡이 새 일자(Asia/Seoul today)에 추가한 4건

**9. 13개 GET API 응답**

```text
200 /health
200 /api/reports/today
200 /api/recommendations/latest    (recommendations=3)
200 /api/recommendations/history   (items=3 — 시드한 3개 run)
200 /api/holdings                  (holdings=2)
200 /api/holdings/checks/latest    (items=2)
200 /api/holdings/005930/checks    (items=5 + summary)
200 /api/stocks/005930
200 /api/universe/market-cap-top   (items=2 — 잡이 limit=2로 갱신)
200 /api/market-regime/latest
200 /api/news                      (items=0 — 시드 미적재)
200 /api/jobs                      (items=6)
200 /api/settings                  (KIS/Telegram 자격증명 마스킹)
```

`/api/holdings/005930/checks` summary 표본:
`total=5, alert=3, high_risk=2, latest_decision=SELL_REVIEW,
latest_risk_level=MEDIUM, latest_total_score=16.2500, previous=4.2500,
change=12.0000`.

**관찰 / 알아둘 점**

- `seed_mock_data`는 `datetime.now(UTC).date()`를 "today"로 사용하지만,
  스케줄러 잡은 `_today_in_default_timezone()` (`settings.timezone`,
  default Asia/Seoul)을 사용. 시드 실행 시각이 UTC 15:00 이후 (≈ Seoul
  24:00 이후) 이면 시드 "today"가 잡의 "today"보다 하루 빠르게 나오고,
  잡은 새 일자에 fresh 행을 만들어 둘 다 공존한다. 데이터 손상은 아니며
  대시보드 추세 metric도 정상 동작.
- `update_recommendation_results`는 시드 가격 30봉 안에서 1/3/5/20일 후
  검증을 수행 — 가장 오래된 run (today-7) 만 1/3/5일 모두 평가 가능, 나머지는
  PENDING이 다수.
- 회귀 게이트 `pytest`: **296 passed in 5.87s** (이번 실행 직후 동일 결과 확인).

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

**v0.1 범위 안에서 남은 것 (코드 변경)**

- 캔들 패턴 / ATR 변동성 컴포넌트 → `technical_score` 산식 보강 (Phase 4 후속, 신규 분석 기능 — 본 세션에서는 의도적으로 손대지 않음. Backlog 이동도 무방)

**v0.1 범위 안에서 남은 것 (운영)**

- `collect_market_close_data` 잡의 실 KIS 키 운영 검증 — 코드 경로는 완성되어 있고 `KisClient`가 `settings`에서 자동 연결됨. 남은 것은 실제 발급 키를 `.env`에 채워 dry-run 외 환경에서 한 번 검증하는 운영 단계 (코드 변경 없음)
- PROJECT_STATUS.md / TASKS.md — 신규 세션마다 수동 갱신 필요

**v0.2 이후로 미룬 범위 (Backlog)**

- React/Next.js PC 대시보드 프론트엔드
- 전략(장기/중기/단기) 관리, SIGNAL/PAPER 모드
- 백테스트 엔진, walk-forward 검증, 그리드 서치 튜닝
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 v0.1은 `DummyScoreProducer` 룰베이스 placeholder)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래)

---

## 5. 다음에 이어서 할 첫 번째 작업

**v0.1 백엔드는 마감 상태.** 남은 코드 작업은 캔들 패턴 / ATR 컴포넌트 추가 1건뿐이며, 본 작업은 신규 분석 기능이라 v0.2 Backlog로 이동 가능. 사용자가 신규 기능 진행을 명시하기 전까지 다음 세션이 우선 처리할 항목은 다음 둘 중 하나:

1. **운영 검증 1회** — `.env` 에 실 KIS 키 + dry-run 환경(파일 SQLite 또는 docker-compose Postgres)에서 `INTEGRATION_RUNBOOK.md` §1 → §3 → §4 시나리오 1회 수행 후 결과를 PROJECT_STATUS.md §2에 기록. 코드 변경 없음.
2. **(선택) 캔들 패턴 / ATR 컴포넌트** — `technical_analyzer.py` 에 hammer / engulfing / 14-day ATR 계산 추가, `technical_score` 합산 가중치 미세 조정. 단위 테스트 동반.

이 외 잡 / 라우터 / 엔진 / dispatcher 변경은 v0.1 마감 후의 새 기능이라 명시적 요청 없이는 진행하지 않는다.

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
