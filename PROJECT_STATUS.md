# PROJECT_STATUS.md

v0.1 진행 상태 스냅샷 (현재 세션 종료 시점). 새 Codex 세션이 이어서 작업을
시작할 때 가장 먼저 읽어야 할 파일이다. AGENTS.md / TASKS.md와 함께 사용한다.

---

## 0. v0.3 시작 선언 — 분석 보강 + 운영 정착

**v0.3 cycle 진입.** 기준선 `v0.2-frontend-final`. v0.1 backend + v0.2 frontend 양쪽 마감 위에 분석 / UX / CI 5 phase 를 진행한다. v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 정책은 그대로 유지한다.

### v0.3 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | GitHub Actions CI (backend pytest + frontend vitest+build + Playwright e2e) | ✅ 인수 (CI 그린 확인 후) | `v0.3-phase-a-ci` |
| B | 캔들 패턴 + ATR 변동성 컴포넌트 → `technical_score` 산식 보강 (백엔드, DB 컬럼 추가) | ⏳ 진입 대기 | `v0.3-backend-analysis` |
| C | 한국거래소 휴장일 캘린더 (정적 JSON, Today/Jobs/Holdings 배너) | ⏳ | `v0.3-frontend-calendar` |
| D | `GET /api/stocks/{symbol}/prices` 신규 + StockDetail 일봉 차트 (Recharts) | ⏳ | `v0.3-frontend-stock-chart` |
| E | `RELEASE_NOTES_v0.3.md` + README/PROJECT_STATUS/TASKS 마감 + tag `v0.3-final` | ⏳ | `v0.3-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0003`, 체크리스트는 [`TASKS.md`](./TASKS.md) `v0.3 — 분석 보강 + 운영 정착` 섹션 참조.

### v0.3 에서 절대 하지 않을 것 (정책 재확인)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI (수동 잡 실행 / 추천 즉시 생성 / 보유 추가·삭제 폼)
- ❌ 실 News / Supply / Fundamental / Earnings 외부 파이프라인 (placeholder 유지, 캔들/ATR 만 추가)
- ❌ 즐겨찾기 / 관심 종목 / 인증 / 모니터링 / 모바일 — 모두 v0.4+ 후보

### v0.3 백엔드 동결 정책 변경 안내

`v0.1-backend-final` 동결을 일부 깬다. Phase B 가 `app/analysis/`, `app/db/models.py` (`StockIndicator` 컬럼 2개 추가), `app/data/repositories/stock_indicators.py`, `app/analysis/indicator_service.py`, `app/api/schemas.py` 를 수정. Phase D 가 `app/api/routes.py`, `app/api/schemas.py` 에 신규 read-only GET 1개 추가. **POST 라우터 / 잡 트리거 / 자동매매 코드는 추가하지 않는다.** DB 컬럼 추가는 ALTER ADD 만이라 destructive 아니지만 운영 환경 마이그레이션 안내가 필요.

---

## 0-1. v0.2 PC 대시보드 마감 선언

**v0.2 frontend 는 종료 (마감) 상태이다.** v0.1 backend 동결 (`v0.1-backend-final`)
위에 PC 대시보드 8 화면이 모두 read-only 로 연결되었고, vitest 36 + Playwright
e2e 6 + 백엔드 pytest 296 회귀 게이트가 모두 통과. 종합 인수 사유는
[`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) 참조.

| 항목 | 값 |
|---|---|
| 최종 frontend 태그 | `v0.2-frontend-final` |
| 누적 frontend 태그 | `phase-a` (골격) → `phase-b` (Today/Jobs) → `phase-c` (Recommendations/History) → `phase-d` (Holdings/StockDetail) → `phase-e` (MarketCap/Settings) → `final` (lazy + e2e + Docker + 릴리스) |
| 8 화면 | 오늘 / 추천 / 추천 이력 / 보유 / 종목 상세 / 시총 TOP / 잡 / 설정 — 모두 실 데이터 연동 + 빈/에러 상태 처리 |
| 번들 (첫 진입 Today) | ≈ 297 kB / gzip ~80 kB (lazy + manualChunks 적용 후). Recharts 청크는 추세 화면 진입 시에만 로드 |
| Docker | `docker compose up --build` → 백엔드 (8000) + 프런트 (8080) 동시 기동, nginx `/api` → backend proxy |
| 자동매매 / 실 주문 | **v0.2 범위 밖** — `BrokerInterface` ABC placeholder 유지 / POST 트리거 UI 0건 |

---

## 0-2. v0.1 백엔드 마감 선언 (참고)

**v0.1 백엔드는 종료 (마감) 상태이다.** 새 기능 / 리팩터 / 잡 / 라우터 추가는
사용자의 명시적 v0.2 backend 진입 요청 전까지 진행하지 않는다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.1-backend-kis-paper-verified` |
| 인수 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | pytest **296 passed** (외부 호출 0건, mock / DRY_RUN 만) |
| 통합 검증 | mock seed (§2 "v0.1 통합 실행 결과") + 실 KIS 모의투자 read-only (§2 "실 KIS 운영 검증 결과" + 후속) 모두 1회 통과 |
| 자동매매 / 실 주문 | **v0.1 범위 밖** — `BrokerInterface` ABC placeholder 만 유지 (구체 구현 0건) |
| 누적 인수 태그 | `v0.1-foundation-checkpoint` → `v0.1-backend-accepted` → `v0.1-backend-kis-paper-verified` |

마감 선언의 종합 사유 / 산출물 / 알려진 한계 / v0.2 후보는
[`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) 에 정리.

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

### 실 KIS 운영 검증 결과 (1회 수행)

`KIS_OPS_CHECKLIST.md` 절차에 따라 실 KIS 모의투자 키 + 검증용 비공개 텔레그램
채팅방 기준으로 1회 시도. read-only 인증과 일봉 조회는 통과, 시총 상위
endpoint 에서 KIS contract 결함 1건이 발견되어 **collect 잡은 FAILED**.

**검증 모드**

- `KIS_USE_PAPER=true` (모의투자 서버 `openapivts.koreainvestment.com:29443`)
- `TELEGRAM_ENABLED=false`
- `SCHEDULER_ENABLED=false`
- `FEATURE_REAL_ORDER_EXECUTION=false`
- `FEATURE_FULL_AUTO=false`
- 검증용 DB: `sqlite:///./stock_ai_kis_check.db` (운영 / 시드 DB 와 격리)

**사전 안전 점검 (모두 통과)**

- `.env` git ignore / 미커밋 / 이력 부재
- `.env` ACL 좁히기 적용 (Owner + Admins + SYSTEM 만 FullControl, CodexSandboxUsers 는 Read 만)
- `Settings()` 로딩 시 `kis_app_key` / `kis_app_secret` / `kis_account_no` /
  `telegram_bot_token` / `telegram_chat_id` 모두 마스킹된 형태로만 표시
- `/api/settings` 라우터 응답에서도 동일한 마스킹 + 안전 플래그 모두 false
- 실주문 / 자동매매 코드 부재: `place_order` / `order_execute` / KIS 주문
  엔드포인트 / `BrokerInterface` 구체 구현 모두 0건 — `BrokerInterface` 는
  `app/broker/interfaces.py` 의 ABC 정의(`raise NotImplementedError`) 로만 존재

**KIS read-only 단건 검증**

- 토큰 발급 (`/oauth2/tokenP`): ✅ SUCCESS (token length=346, 본문 비노출)
- 005930 일봉 조회 (`/uapi/domestic-stock/v1/quotations/inquire-daily-price`): ✅ SUCCESS
  - 조회 기간: 2026-04-28 ~ 2026-05-05 (영업일 4건)
  - 반환 row 수: 4
  - 첫 행 (최신순): `date=20260504, close=232500`
  - 마지막 행: `date=20260428, close=222000`
  - 모의투자 시세는 paper 서버 자체 시뮬레이션 값이므로 실시장과 다름 (정상)

**`collect_market_close_data` 잡 결과**

- 잡 자체는 정상 호출 (스키마 자동 생성, 안전 가드 통과, `job_runs` 행 정상 기록)
- 시총 상위 endpoint 호출에서 KIS 서버가 거절 →
  `KIS API error OPSQ2001: ERROR INPUT FIELD NOT FOUND [FID_COND_SCR_DIV_CODE]`
- 결과: `status=FAILED`, `market_cap_status=FAILED`, `daily_price_status=SKIPPED`
  (시총 단계 실패로 daily 수집은 의도적으로 실행되지 않음)

**영향 범위 (이번 1회 검증 기준)**

| KIS 경로 | 결과 |
|---|---|
| 토큰 발급 | ✅ |
| 일봉 조회 | ✅ |
| 시총 상위 ranking | ❌ contract 결함 1개 (필드 누락) |

따라서 v0.1 KIS 클라이언트의 read-only 경로 중 **시총 상위 endpoint 1개만**
paper 서버와 contract 가 어긋남. 인증 / 일봉은 정상 동작.

**Known Issue**

- `app/data/collectors/kis_client.py:fetch_market_cap_rankings` 의 query
  파라미터에 `FID_COND_SCR_DIV_CODE` 가 누락. KIS 시총 상위 화면 카테고리
  코드(후보값 `"20174"`) 추가 필요.
- `tests/unit/test_kis_client_http.py` 의 captured query params 도 실 KIS
  contract 에 맞춰 신규 파라미터 transmit 검증으로 갱신 필요.
- mock HTTP 테스트만으로는 이 누락이 드러나지 않으므로, 후속 픽스 시 paper
  서버 1회 재검증을 절차에 명시.

**다음 조치**

1. 별도 코드 수정 세션에서 `fetch_market_cap_rankings` 파라미터 보정 1줄 추가 + 단위 테스트 갱신.
2. 픽스 commit 후 `collect_market_close_data` 잡을 paper 서버에서 1회 재실행 → market_cap → daily_prices → 시총 + 일봉 모두 SUCCESS 확인.
3. 그 다음 단계로 `calculate_technical_indicators` → `send_recommendation_report` (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 시범 운행 진입.

**비밀 / 토큰**

본 절에는 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 / chat_id 평문이
일체 기록되지 않았다. 모든 비밀은 마스킹 형태(예: `5015****1-01`)로만
참조한다. 운영 검증 도중 발급된 KIS 액세스 토큰도 디스크 / 로그에 남지 않음
(`LOG_TO_FILE=false`).

### 후속 검증 — 시총 픽스 적용 후 (3회 시도)

`fetch_market_cap_rankings` 의 query 에 `FID_COND_SCR_DIV_CODE="20174"` 를
추가하는 픽스 (`eb8452a`) 적용 후 `collect_market_close_data` 잡을 동일한
검증 환경 (`KIS_USE_PAPER=true` / 검증용 DB / `MARKET_CAP_LIMIT=5`) 에서 3회
재실행. lookback 은 1·2회는 2일, 3회차는 7일.

**시총 상위 endpoint — 3/3 SUCCESS**

- 3회 모두 `market_cap_status=SUCCESS`, KOSPI 시총 상위 5건 정상 응답.
- `stocks` (5 신규 → 이후 0 신규, idempotent), `market_cap_rankings` (3회
  모두 5건, snapshot replace 정상), `stock_universe_members` (5 신규 → 0)
  저장 정상. KIS 시총 상위 endpoint contract 결함은 완전 해소.

**일봉 endpoint — signature 정상 / 종목별 paper 서버 한계 노출**

| 종목 | 1차 (lookback=2) | 2차 (lookback=2) | 3차 (lookback=7) | 누적 |
|---|---|---|---|---|
| 005930 (삼성전자) | ❌ | ✅ | ✅ (3 rows) | 2/3 |
| 005935 (삼성전자우) | ✅ | ❌ | ✅ (3 rows) | 2/3 |
| 402340 (SK스퀘어) | ✅ | ❌ | ❌ | 1/3 |
| 000660 (SK하이닉스) | ❌ | ❌ | ❌ | 0/3 |
| 373220 (LGES) | ❌ | ❌ | ❌ | 0/3 |

- 005930 / 005935 가 안정 SUCCESS 한 사실로 일봉 endpoint signature 자체는
  정상으로 판단. 직전 단건 검증 (`fetch_daily_prices(005930, 7일)` 4 rows)
  과 일관됨.
- 000660 / 373220 은 lookback / 호출 시점 무관하게 항시 `KIS HTTP 500`
  반환 → KIS 모의투자 서버의 종목별 시뮬레이션 데이터 또는 캐시 미적재
  문제로 추정. 코드 contract 결함으로 보지 않음.
- 402340 은 randomize 패턴 (run 마다 결과 변동) — 동일 paper 서버
  transient 5xx 패턴.

**잡 동작 정상 분기**

- 3회 모두 `status=PARTIAL`, `error_message="N daily price collections failed"`,
  종목별 실패는 `result_summary.failures` 항목 단위로 격리 기록.
- `job_runs` 행은 RUNNING → PARTIAL 전환 + `finished_at` / `result_summary` /
  `error_message` 정상 채워짐.
- 성공 종목의 `daily_prices` upsert + `market_cap_rankings` snapshot replace
  는 PARTIAL 상황에서도 의도대로 commit 됨 → DB 무결성 유지.

**회귀 게이트**

- 시총 픽스 직후 `pytest`: **296 passed in 5.87s** (회귀 0건).
- 본 후속 검증은 코드 변경을 동반하지 않음.

**판단 / 다음 단계**

- v0.1 백엔드 코드는 인수 (accepted) 상태 유지. KIS contract 픽스 1건이
  추가되었지만 영향 범위는 단일 endpoint 의 query 파라미터 한 줄로 좁고
  paper 서버에서 실측 검증됨.
- 본격 운영 검증 (전 종목 일봉 SUCCESS 확인) 은 KIS 실서버
  (`KIS_USE_PAPER=false`) 또는 paper 서버의 종목별 시뮬레이션 데이터가
  안정화된 시점에 다시 수행. v0.1 잡의 PARTIAL 격리 동작이 검증되었으므로
  실서버 진입 시 일부 종목 실패가 나오더라도 전체 흐름이 멈추지 않음.
- 다음 검증 cycle 에서는 `calculate_technical_indicators` → `send_recommendation_report`
  (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 진입 가능 (시총·일봉
  데이터 일부라도 적재된 상태).

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

**v0.1 범위 안에서 남은 것 (코드 변경 0건)**

코드 작업은 모두 완료. 운영 / 문서 단계만 남아있다.

- 실 KIS 키 + 실 텔레그램으로 1회 운영 검증 — 코드 경로는 완성되어 있고
  `KisClient`가 `settings`에서 자동 연결됨. `.env` 채움 + 안전 플래그 확인 +
  체크리스트 항목별 통과만 필요. 절차는 [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md)
  로 분리 정리.
- PROJECT_STATUS.md / TASKS.md — 신규 세션마다 수동 갱신 필요

**v0.2 이후로 미룬 범위 (Backlog)**

- 캔들 패턴 (망치형/장악형 등) + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
  (Phase 4 후속, 신규 분석 기능 — v0.1 마감 시점에 명시적으로 v0.2 이동)
- React/Next.js PC 대시보드 프론트엔드
- 전략(장기/중기/단기) 관리, SIGNAL/PAPER 모드
- 백테스트 엔진, walk-forward 검증, 그리드 서치 튜닝
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 v0.1은 `DummyScoreProducer` 룰베이스 placeholder)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래)

---

## 5. 다음에 이어서 할 첫 번째 작업

**v0.1 백엔드는 마감 상태 (tag `v0.1-backend-accepted`).** 남은 코드 작업 없음.
다음 세션이 우선 처리할 항목은 다음 1건:

- **운영 검증 1회** — [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 항목별로
  실 KIS 키 + 실 텔레그램(검증용 비공개 채팅방)에서 1회 통과 후 결과를
  PROJECT_STATUS.md §2 "v0.1 통합 실행 결과" 아래 새 하위 절로 기록한다.
  코드 변경 없음.

캔들 패턴 / ATR / 그 외 신규 분석·전략·프론트엔드는 모두 v0.2 Backlog (§4)로
이동했으므로, 사용자의 명시적 v0.2 진입 요청 없이는 진행하지 않는다.
v0.1 마감 후의 새 기능 (잡 / 라우터 / 엔진 / dispatcher 추가)도 마찬가지.

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
