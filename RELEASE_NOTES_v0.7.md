# RELEASE_NOTES_v0.7

## v0.7 Strategy & Backtest Foundation 마감

v0.7 은 v0.1 ~ v0.6 에서 누적된 추천 판단 축 (technical / report / theme /
news / disclosure / fundamental / earnings + risk_penalty + recommendation_results
1·3·5·20일 수익률) 위에 **`StrategyInterface` + 룰 기반 전략 3종 + `BacktestEngine`
+ `CostModel` + 시장 국면별 분리 + 백테스트 read-only 화면 (10번째)** 을 도입한
사이클이다. 다음 자연 질문 — "이 추천이 돈이 되는가?" — 에 답하기 위한 첫
backend 분석 layer + 운영자용 read-only 대시보드. v0.1 의 read-only / 자동매매
부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 + v0.5 의 자동
fetch default OFF + v0.6 의 evidence whitelist + ScoringEngine 본 weight 변경
0건 정책 모두 그대로 유지했다.

자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST 라우터 / 외부 API
자동 호출은 이번 사이클에도 코드 일체 추가하지 않았다. **`StrategySignal`
(BUY/PASS/AVOID) 은 분석 신호이지 매매 주문이 아니다** — `app/strategy/` +
`app/backtest/` 어디에도 broker / quantity / order_price / account / order_type /
side 필드 / 호출 0건 (grep 가드 + 단위 테스트 명시 단언).

- 최종 태그 예정: `v0.7-final`
- 인수 일자: 2026-05-06 (Asia/Seoul)
- 직전 누적 태그: `v0.7-frontend-backtest` (Phase D)
- 기준선: `v0.6-final` (HEAD `e729d60`) — 백엔드 pytest 558 / vitest 77 / build / e2e 13
- 마감 기준선: 백엔드 pytest **682** (1 deselected) / vitest **84** / build / e2e **14**

## 핵심 변화 한 줄 요약

- **`StrategyInterface` ABC + 룰 기반 전략 3종 첫 도입** — `TopGradeStrategy` /
  `HighScoreStrategy` / `MultiSignalStrategy` (Phase A). 모두 pure-function +
  `[0, 1]` confidence 자동 clamp + null/malformed evidence 에서도 raise 0건. v0.1
  부터 placeholder 였던 "판단 후의 재검증" layer 가 처음 생김.
- **`BacktestRun` (26번째 테이블) + `BacktestResult` (27번째 테이블) 신규** —
  `BacktestEngine` 가 과거 `recommendations` + `recommendation_results` 위에 전략을
  replay 해서 승률 / 평균 수익률 / max drawdown 을 계산 (Phase B). `scripts/run_backtest.py`
  argparse CLI (default dry-run). BUY-only metrics 정책 명시 + horizon 별
  `missing_result_count_per_horizon`.
- **`CostModel` placeholder + 시장 국면별 분리** — `total_cost = 0.33%` 차감
  (buy_fee 0.015% + sell_fee 0.015% + sell_tax 0.20% + slippage 0.10%) +
  `assign_regime(session, signal_date)` (`MarketRegime.date <= signal_date` 가장
  최근). `cost_adjusted_return_5d` / `regime` 컬럼 + `regime_breakdown`
  summary (Phase C). 실 broker fee schedule fetch 는 v0.8+ 후보로 명시.
- **백엔드 read-only API 3종** — `GET /api/strategies` (registry 기반, DB 0건) +
  `GET /api/backtest/runs?strategy=&limit=` + `GET /api/backtest/runs/{run_id}`
  (Phase D). `summary_json` 의 cost_model_version / total_cost /
  regime_breakdown 을 응답 최상위로 추출.
- **프런트 10번째 화면 `/backtest`** — Sidebar `백테스트 (β)` 메뉴 추가 (9 →
  10). 상단 전략 카드 grid + 중단 run 표 (전략 filter radiogroup) + 하단 detail
  패널 (regime breakdown + 신호 row 표 + cost_model_version + BUY-only note).
  자동매매 / order CTA 0건 — e2e `/backtest` targets 가드 통과.

## Phase A — Strategy interface + 룰 기반 전략 3종

> 태그 `v0.7-strategy-interface`. v0.1 부터 placeholder 였던 신호 산출 layer 의
> 첫 구현. backend 순수 로직만 — DB 모델 / 라우터 / 프런트 / scheduler /
> Telegram / 자동매매 / 외부 호출 0건.

- `app/strategy/__init__.py` + `app/strategy/interfaces.py` 신규:
  - `StrategySignal` (frozen dataclass) — `action` (`BUY` / `PASS` / `AVOID` 외
    값 거부 → `ValueError`), `confidence` (Decimal, `__post_init__` 에서 `[0, 1]`
    자동 clamp + non-Decimal 자동 coerce), `reason` (str), `evidence`
    (`dict | None`). "주문이 아니다 — quantity / price / account / broker 없음"
    docstring 명시.
  - `ScoreSnapshot` (frozen dataclass) — 14 필드 (`symbol`, `total_score`,
    `grade`, 5 component score, 2 보조 score, `risk_level`, `risk_flags`,
    `evidence`). 수치는 모두 nullable, `risk_flags` 는 `default_factory=list`.
    `SCORE_SNAPSHOT_FIELDS` frozenset 가드 — broker / 주문 필드 추가 시 단위
    테스트 즉시 깨짐.
  - `StrategyInterface` (ABC) — `name` / `version` 추상 property + `evaluate(snapshot)`
    추상 method. 외부 API / DB / Telegram / 주문 호출 금지.
- `app/strategy/rule_based.py` 신규:
  - `TopGradeStrategy v1.0.0` — grade `S` → BUY (0.9) / `A` → BUY (0.75) / `D`
    → AVOID (0.75) / 그 외·null → PASS (0.5). lowercase 자동 normalize.
  - `HighScoreStrategy v1.0.0` — `total_score >= 75` → BUY (linear 75→0.6,
    100→1.0), `<= 35` → AVOID (linear 35→0.6, 0→0.985), 그 외·null → PASS (0.5).
  - `MultiSignalStrategy v1.0.0` — AVOID 우선 게이트 (HIGH risk → 0.85,
    `RISK_DISCLOSURE` flag → 0.85, `total_score <= 35` → 0.7) → BUY 게이트
    (`total >= 65` AND `fundamental >= 60` AND `news >= 50` AND `(earnings >= 50
    or None)` AND not HIGH risk AND no RISK_DISCLOSURE → 0.7) → 나머지 PASS.
    BUY 시 evidence-driven boost: BEAT +0.10 / news skew>0 +0.05.
- `tests/unit/test_rule_based_strategies.py` 신규 — **56 케이스** (StrategySignal
  validation/clamp 12 + ScoreSnapshot null-safe + order field 부재 가드 3 +
  StrategyInterface ABC 차단 2 + 3 strategies × happy/edge/empty 37 + 3 strategies ×
  빈 snapshot → PASS 가드 3).
- 회귀: backend pytest **558 → 614 (+56)**. frontend / e2e / build 변경 0건.
  ScoringEngine 본 weight 변경 0건.

## Phase B — Backtest engine + 신규 테이블 2개 + CLI

> 태그 `v0.7-backtest-engine`. backend 데이터 / 엔진 layer 만 추가 — API 라우터 /
> 프런트 / scheduler / 비용 모델 / 시장 국면 분리는 Phase C·D 로 이연.

- `app/db/models.py` — `BacktestRun` (26번째 테이블, TimestampMixin) + `BacktestResult`
  (27번째 테이블) 신규. `BacktestResult.backtest_run_id` → `backtest_runs.id` ON
  DELETE CASCADE + `cascade="all, delete-orphan"` relationship. Unique
  `(backtest_run_id, recommendation_id)` 가드.
- `app/data/repositories/backtest_runs.py` 신규 — `BacktestRunRepository`:
  `create` / `get_by_id` / `list_recent` / `list_by_strategy` / `mark_finished`
  (모든 metric + summary_json 일괄 update + status SUCCESS) / `mark_failed`. 상태
  상수 `STATUS_DRY_RUN` / `STATUS_SUCCESS` / `STATUS_FAILED`.
- `app/data/repositories/backtest_results.py` 신규 — `BacktestResultRepository`:
  `create` / `bulk_insert` / `list_by_run` / `list_by_symbol` / `aggregate_by_run` /
  `aggregate_by_signal_action`.
- `app/strategy/registry.py` 신규 — `STRATEGY_REGISTRY` dict + `KNOWN_STRATEGIES`
  tuple + `UnknownStrategyError(KeyError)` + `get_strategy(name)`.
- `app/backtest/engine.py` 신규 — `BacktestEngine(session)` (`BacktestRunRepository` +
  `BacktestResultRepository` composition, 외부 의존성 0건) + `BacktestEngine.run(
  strategy, start_date, end_date, dry_run, limit, run_date)` + `BacktestRunSummary`
  (frozen dataclass, `as_dict()`) + `build_score_snapshot(rec, snapshot)` helper +
  `BUY_ONLY_METRICS_NOTE` 상수.
- `scripts/run_backtest.py` 신규 — argparse CLI. `--strategy` 필수 (choices=
  `KNOWN_STRATEGIES`) + `--from-date` / `--to-date` (YYYY-MM-DD) + `--commit`
  (없으면 dry-run rollback) + `--db-url` + `--limit`. `_print_summary` 가
  signal/buy/pass/avoid count + horizon 별 win_rate/avg_return + max_drawdown +
  missing_result_count + backtest_run_id + BUY_ONLY_METRICS_NOTE 출력.
- 통합 테스트: `tests/integration/test_backtest_repositories.py` (**20 케이스** —
  ORM metadata + Repository CRUD + Unique + cascade) + `tests/integration/test_backtest_engine.py`
  (**18 케이스** — build_score_snapshot + dry-run/commit + 3 strategies happy +
  metrics + date filter + CLI smoke).
- 회귀: backend pytest **614 → 652 (+38)**. frontend / e2e / build 변경 0건.

## Phase C — CostModel + 시장 국면별 분리

> 태그 `v0.7-backtest-cost-regime`. backend 분석 layer 보강만 — API 라우터 /
> 프런트 / 외부 호출 0건. CostModel 은 placeholder constant 만 (실 broker fee
> schedule fetch 는 v0.8+ 후보).

- `app/backtest/cost_model.py` 신규 — `CostModel` (frozen dataclass):
  `buy_fee=0.00015` + `sell_fee=0.00015` + `sell_tax=0.0020` + `slippage=0.0010`
  → `total_cost = 0.0033 (0.33%)`. `apply(raw_return)` 은 percent 단위 (예:
  1.5% → 1.17%). `version` 필드 + `COST_MODEL_VERSION = "constant-v1"` 상수.
- `app/backtest/regime_split.py` 신규 — `assign_regime(session, signal_date,
  market="KOSPI")` (`MarketRegime.date <= signal_date` 가운데 가장 최근 row 의
  `regime`) + `display_bucket(regime)` (None → `UNCLASSIFIED_BUCKET`).
- `app/db/models.py` `BacktestResult` 보강 — `cost_adjusted_return_5d`
  Numeric(12,4) nullable + `regime` String(32) nullable index. Phase B 의 신규
  테이블 정의에 흡수 (운영 DB ALTER 안내는 DB_SCHEMA §27).
- `app/data/repositories/backtest_results.py` `aggregate_by_regime` 추가 —
  `{regime_or_unclassified: count}` GROUP BY, NULL 자동 폴딩.
- `app/backtest/engine.py` 보강 — `BacktestEngine.__init__(*, cost_model=None,
  regime_market="KOSPI")` keyword 옵셔널. BUY 신호만 cost_adjusted_return_5d
  계산 (PASS/AVOID NULL). 모든 row 에 regime 할당. `_build_regime_breakdown`
  helper (BUY rows GROUP BY regime → win_rate_5d / avg_return_5d /
  cost_adjusted_avg_return_5d, `buy_count desc` 정렬). `BacktestRunSummary` 에
  `cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` /
  `regime_breakdown: list[RegimeBreakdownEntry]` 필드 + `summary_json` /
  `config_json` 양쪽에 데이터 persist.
- `scripts/run_backtest.py` 출력 보강 — `cost_model_version` / `total_cost
  (fraction)` / `cost_adjusted_avg_return_5d` / regime_breakdown 표.
- 테스트: `tests/unit/test_cost_model.py` (**9 케이스** — version / total_cost /
  apply 양수·음수·zero·None / custom rate / frozen) + `tests/integration/test_backtest_regime.py`
  (**12 케이스** — assign_regime 4 + engine summary 8 (NULL → UNCLASSIFIED /
  PASS·AVOID 의 cost_adjusted NULL but regime 할당 / aggregate_by_regime / custom
  CostModel 전파)).
- 회귀: backend pytest **652 → 673 (+21)**. 기존 Phase B 테스트 38건 그대로 통과.
  ScoringEngine 본 weight 변경 0건.

## Phase D — read-only API 3종 + 프런트 10번째 화면 `/backtest`

> 태그 `v0.7-frontend-backtest`. read-only API + UI 만 추가 — BacktestEngine
> 산식 / CostModel / regime_split / DB 모델 변경 0건. POST 라우터 / 자동매매 /
> 외부 호출 / Telegram 0건. Sidebar 9 → 10 메뉴.

### 백엔드

- `app/api/schemas.py` — 7 신규 schema (`StrategySchema` / `StrategiesResponse` /
  `BacktestRunSchema` / `BacktestRunsResponse` / `BacktestResultSchema` /
  `RegimeBreakdownSchema` / `BacktestRunDetailResponse`). Decimal-as-string
  패턴 유지. broker / order / quantity / account 필드 0건.
- `app/api/routes.py` — 3 신규 GET 라우터:
  - `GET /api/strategies` — `KNOWN_STRATEGIES` 순회 + `get_strategy(name)` 호출.
    DB 접근 0건. `description` 은 `_strategy_description(strategy)` helper 가
    docstring 첫 줄 추출.
  - `GET /api/backtest/runs?strategy=&limit=` — `BacktestRunRepository.list_recent`
    또는 `list_by_strategy`. `_backtest_run_to_schema` 가 `summary_json` 의
    cost_model_version / total_cost / cost_adjusted_avg_return_5d 를 응답 최상위
    필드로 추출. `limit` 1~100 검증 (FastAPI 자동 422).
  - `GET /api/backtest/runs/{run_id}` — `BacktestRunRepository.get_by_id` (없으면
    404) + `BacktestResultRepository.list_by_run` + `_regime_breakdown_from_summary`
    helper (malformed 방어 — list/dict 아니면 빈 list).
- `app/data/repositories/backtest_results.py` `create()` — `cost_adjusted_return_5d`
  + `regime` keyword 추가 (Phase C 컬럼 호환). 기존 호출자 회귀 0건.

### 프런트

- `frontend/src/api/types.ts` — 7 신규 type. `frontend/src/hooks/useStrategies.ts`
  (staleTime 5분) + `useBacktestRuns.ts` (60초) + `useBacktestRunDetail.ts` (60초,
  enabled gate) 신규.
- `frontend/src/pages/Backtest/index.tsx` 신규 (10번째 화면) — 단일 파일에 3
  서브컴포넌트 (`StrategyListSection` 카드 grid + `RunsTableSection` 클릭 가능한
  run 표 + 전략 filter radiogroup + `RunDetailSection` regime breakdown + 신호
  row 표 + cost_model badge + BUY-only note). `ActionBadge` BUY/PASS/AVOID
  tone-color.
- `frontend/src/components/layout/Sidebar.tsx` — `FlaskConical` + 8번째 위치에
  `백테스트 (β)` 메뉴 추가 (9 → 10).
- `frontend/src/router.tsx` — `BacktestPage` lazy + `/backtest` route 추가.
- `frontend/src/tests/mswServer.ts` — 3 default 핸들러 (모두 빈 응답 / 404).

### 테스트

- backend pytest **673 → 682 (+9)** — `_BACKTEST_FORBIDDEN_FIELDS` (16종:
  source_file_path / body / content / full_text / raw_text / paragraph /
  html_body / 본문 / 원문 / 전문 / broker / account / quantity / order_price /
  order_type / side) + strategies 3종 노출 / runs empty/happy/filter/limit clamp /
  detail happy/404 + regime + cost_adjusted + BUY-only notes / forbidden 토큰
  미노출 가드 / source_file_path recursive 가드.
- frontend vitest **77 → 84 (+7)** — Backtest happy / empty / 500 / detail 클릭 +
  cost_model + regime + BUY-only note / detail 500 / strategy filter URL 변경 /
  자동매매·order UI 부재 + forbidden 토큰 미노출.
- e2e **13 → 14 (+1)** — sidebar nav 보강 + 신규 `Backtest screen surfaces
  strategies + runs + detail` (3 strategy + run row + 클릭 시 detail + regime +
  cost_model + raw JSON `order_type` / `quantity` / `source_file_path` 0건). `no
  automation / order UI` targets 에 `/backtest` 추가.
- frontend build 그린 (vendor-charts 383 kB / gzip 105 kB).

## Phase E — 마감 문서 / 회귀 게이트 재확인

이 단계. `RELEASE_NOTES_v0.7.md` 신규 + `README.md` 마감 배너 +
`PROJECT_STATUS.md` §0 마감 선언 + `TASKS.md` 체크박스 + `ROADMAP.md` v0.7 마감 +
4 게이트 재확인. **코드 / 라우터 / DB 모델 / 프런트 화면 / 테스트 변경 0건**.

## 테스트 결과 (v0.7 마감 시점)

Phase D 인수 시점 + Phase E 마감 직전 재확인 모두 동일한 4 게이트 baseline:

- backend pytest: **682 passed, 1 deselected** (v0.1 296 → v0.3 319 → v0.4 final 382 → v0.5 final 481 → v0.6 final 558 → v0.7 Phase A 614 → Phase B 652 → Phase C 673 → Phase D 682)
- frontend vitest: **84 passed** (14 파일, jsdom + msw v2)
- frontend build: **그린** (`tsc --noEmit && vite build`, vendor-charts 청크 383 kB / gzip 105 kB)
- Playwright e2e: **14 passed** (chromium + page.route mock)

테스트는 모두 mock / fixture 기반이다. KIS API 실제 호출, 텔레그램 실제 발송,
외부 RSS / DART API 실제 호출, 주문 실행은 0건이다.

운영자 로컬 `.env` 의 dev override (`MARKET_CAP_LIMIT=5`, `DAILY_PRICE_LOOKBACK_DAYS=7`
등) 와 충돌하는 단일 케이스 `tests/unit/test_project_structure.py::test_settings_defaults`
는 v0.3 부터 알려진 환경 의존성이며, `--deselect tests/unit/test_project_structure.py::test_settings_defaults`
또는 명시적 env override (`MARKET_CAP_LIMIT=500 ...`) 로 우회한다. 실제 default
검증은 GitHub Actions CI 환경 (clean env) 에서 자동 통과한다.

## 안전 정책 (cycle-wide)

v0.6 의 evidence whitelist + v0.4~v0.5 의 저작권·자동 fetch 정책을 그대로 누적:

- **자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건** — `BrokerInterface`
  ABC placeholder 그대로. v0.7 어디에도 broker 호출 / 주문 실행 / 자본 한도 코드
  0건.
- **`StrategySignal` 은 분석 신호이지 주문이 아님** — `app/strategy/` +
  `app/backtest/` 어디에도 broker / quantity / order_price / account / order_type /
  side 필드 0건. `ScoreSnapshot` 의 `SCORE_SNAPSHOT_FIELDS` frozenset 가드 +
  `BacktestResult` ORM 컬럼 set + e2e raw JSON substring 검사 3중 보장.
- **POST / PUT / DELETE 라우터 0건** — v0.1 ~ v0.7 일관 정책. 백테스트 run
  트리거는 화면이 아니라 운영자 수동 CLI (`scripts/run_backtest.py --commit`)
  에서만 실행 가능.
- **외부 API 자동 호출 0건** — `app/strategy/` + `app/backtest/` 에서
  `requests` / `httpx` / `aiohttp` / `urllib` / KIS 클라이언트 / DART 클라이언트 /
  Telegram / `BrokerInterface` import 0건 (grep 검증). registry 기반 `/api/strategies`
  도 DB 접근 0건.
- **CostModel 은 placeholder constant 만** — 실 broker fee schedule / 종목별
  stamp duty / tick-size 슬리피지 fetch 0건. `cost_model_version =
  "constant-v1"` 가 응답에 함께 노출되어 모델 변경 추적 가능.
- **`source_file_path` / 본문 / 원문 / 전문 / body / content / full_text /
  raw_text / paragraph / html_body 13종 forbidden 키워드 0건 노출** — v0.4~v0.6
  정책 + Phase D 의 `_BACKTEST_FORBIDDEN_FIELDS` 16종 (위 13종 + broker / account /
  quantity / order_price / order_type / side) 추가 가드 + `_assert_no_source_file_path`
  recursive helper.
- **자동 fetch default OFF** — v0.5 / v0.6 의 `news_collection_enabled` /
  `disclosure_collection_enabled` / `fundamental_collection_enabled` /
  `earnings_collection_enabled` 모두 false 그대로. v0.7 은 backtest scheduler
  job 자체를 추가하지 않았으므로 default ON 정책 변경 0건.
- **ScoringEngine 본 weight 변경 0건** — RecommendationEngine (technical 35% /
  news 25% / supply 15% / fundamental 15% / ai 10%) + HoldingCheckEngine 산식
  그대로. `StrategyInterface` 는 ScoringEngine 입력을 평가만 할 뿐 가중치를
  바꾸지 않는다.
- **HoldingCheckEngine 산식 변경 0건** — 보유 점검 본 weight 그대로.
- **KIS API / Telegram 실제 호출 0건** — v0.1~v0.6 정책 그대로.
- **비밀값 마스킹 유지** — KIS 키 / Telegram 토큰 / 계좌번호 마스킹 정책,
  settings 응답 마스킹 검증 e2e 그대로 통과.

## 알려진 한계

- **전략 3종은 룰 기반** — `TopGradeStrategy` / `HighScoreStrategy` /
  `MultiSignalStrategy` 모두 단순 임계값 / boolean 조합. LLM 기반 자동 전략 생성 /
  hyperparameter 튜닝은 v0.8+ 후보.
- **CostModel 은 `constant-v1` placeholder** — 0.33% 차감 (KRX 코스피 보수치).
  실 broker fee schedule (per-tier / per-account) / 종목별 stamp duty (KOSPI vs
  KOSDAQ vs ETF) / tick-size aware 슬리피지 / borrow fee 는 v0.8+ 후보.
- **시장 국면 매칭은 기존 MarketRegime 데이터 의존** — `MarketRegime.date <=
  signal_date` 가운데 가장 최근 row 사용. regime 데이터가 비어 있는 구간은
  `UNCLASSIFIED` 버킷으로 폴딩. regime 데이터 후행 적재 후 backtest 재실행으로
  재분류 가능.
- **백테스트는 `recommendation_results` 위에서만 동작** — 1·3·5·20일 horizon
  return 이 적재되지 않은 신호는 그 horizon 의 win_rate / avg_return 에서
  제외되고 `missing_result_count_per_horizon` 에 카운트만 가산. 전체 run 은
  실패하지 않음.
- **실 broker 수수료 / 세금 schedule 미연동** — placeholder 만. 실 적용은 별도
  vendor / 라이선스 검토 cycle 필요.
- **운영 DB Alembic 미사용** — 누적 ALTER 가 v0.5 1건 + v0.6 2건 + v0.7 2건 =
  **5건** 시점. v0.8 의 Alembic 도입 후보 진입 적기.
- **로컬 `.env` 의 dev override 로 인한 `test_settings_defaults` 환경 의존** —
  v0.3 부터 알려진 한계. CI clean env 에서는 통과하지만 로컬에서 `MARKET_CAP_LIMIT=5`
  등을 설정한 경우 `--deselect` 또는 명시 env override 필요.
- **백테스트 run 트리거 UI 없음** — 화면에서 "Run backtest" 버튼이 없음. 운영자가
  `scripts/run_backtest.py --commit` 으로 적재한 결과만 read-only 노출. POST 도입은
  v0.8 의 인증과 묶음.
- **단일 전략만 한 번에 백테스트** — 다중 전략 동시 백테스트 + 포트폴리오 합산
  은 v0.8+ 후보.
- **인증 / 관심종목 / Watchlist 미구현** — v0.8 후보 (POST 도입 + 인증 묶음).

## 제외 범위

다음은 모든 사이클 (v0.1 ~ v0.7) 과 동일하게 코드 일체 포함하지 않는다:

- 실거래 자동매매 (FULL_AUTO / APPROVAL / SMALL_AUTO)
- 실 KIS 주문 / `BrokerInterface` 구현체
- POST / PUT / DELETE 라우터 (read-only API 만)
- News / Disclosure / Fundamental / Earnings 자동 크롤링 / 스크레이핑 (FakeProvider 만)
- 실 RSS / DART / News API 호출
- MockBroker / ReplayBroker / SimulationBroker
- 인증 / 권한 / 사용자별 관심종목
- 뉴스 / 공시 / 리포트 / 재무 / 실적 본문 (paragraph) DB 저장
- 재무제표 PDF / Excel BLOB 저장
- LLM 기반 자동 sentiment / 자동 분류 / 자동 재무 분석 / 자동 전략 생성
- 추천 산식 본 weight 변경
- HoldingCheckEngine 본 weight 변경
- 백테스트 결과 자동 텔레그램 알림
- 실 broker fee schedule fetch / 종목별 stamp duty fetch

## v0.8 후보

v0.7 마감 후 검토 가능한 후보들. 각 항목은 명시적 진입 요청 전까지 손대지 않는다.

### 인증 / Watchlist (v0.8 우선 후보)

- **인증 / 권한** — 단일 사용자 토큰 / API key 헤더부터. POST 라우터 도입 전제.
- **관심종목 / Watchlist** — 신규 테이블 + POST `/api/watchlist`. 인증 동반 필수.
- **Audit log** — POST 도입과 함께.
- **백테스트 run 트리거 UI** — POST `/api/backtest/runs` (인증 가드) → 화면에서
  "Run backtest" 버튼 활성화.

### 인프라

- **Alembic 도입 + 마이그레이션 자동화** — 누적 ALTER 5건 시점에 도입 적기.
- **운영 모니터링** — Sentry / Prometheus / Grafana. 인증 도입 후 가치 ↑.
- **WebSocket / SSE 실시간 백테스트 진행 상태** — 현재 polling.
- **`.github/dependabot.yml`** — v0.3 Phase A 보류 항목.

### 데이터 / 분석 실제화

- **실 DART API 구현체** — `DartFundamentalProvider` / `DartEarningsProvider`.
  라이선스 / 스로틀링 / 정책 검토 동반.
- **실 RSS / News API 구현체** — `RssNewsProvider` / `NaverNewsProvider`.
- **실 broker fee schedule fetch** — CostModel `constant-v1` 대체.

### 백테스트 고도화

- **다중 전략 동시 백테스트 + 포트폴리오 합산.**
- **walk-forward 검증** — 시간 누설 차단 + out-of-sample.
- **전략 hyperparameter Grid Search.**
- **종목별 / 섹터별 / 시가총액 구간별 성과 breakdown.**
- **종목별 stamp duty + 호가 단위별 슬리피지 모델링.**

### LLM / AI 강화

- **LLM 기반 전략 생성 / 평가** — 룰 기반 검증 후.
- **News / Disclosure LLM sentiment.**
- **재무 / 어닝 LLM 분석.**

### UX

- **모바일 / 태블릿 레이아웃** — 현재는 PC 1280px+ 우선.
- **`lightweight-charts` 마이그레이션** — Recharts 한계 도달 시.
- **글로벌 검색** (cmd+k), 사이드바 collapse, breadcrumb, loading skeleton 통일.

### Future Backlog (자동매매)

⚠ **별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실 제한 사이클이
선행되어야 진입 가능.** v0.8 도 자동매매 부재 정책을 유지한다.

| 단계 | 진입 전제 |
|---|---|
| Strategy & Signal | v0.7 ✅ Strategy + Backtest 검증 → 이제 SIGNAL 모드 활성화 가능. 인증 (v0.8) 후행. |
| Backtest 엔진 | v0.7 ✅ 기초 완료. 다중 전략 / walk-forward / 비용 정확도 고도화는 v0.8+ |
| MockBroker / ReplayBroker / SimulationBroker | BrokerInterface 구현 진입 |
| 전용 ML 모델 | Backtest 데이터 누적 후행 |
| APPROVAL 모드 | 컴플라이언스 검토 + MockBroker 검증 |
| SMALL_AUTO | APPROVAL 안정 운영 후 |
| FULL_AUTO | 본 프로젝트 범위 외 |

## 운영 가이드 요약

자세한 절차는 [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §16 참조.

### 백테스트 dry-run

```powershell
.\.venv\bin\python.exe -m scripts.run_backtest --strategy top_grade
```

dry-run 은 DB 저장 0건. 동일 신호 평가 결과를 stdout 으로 노출 — `signal_count` /
`buy_count` / `pass_count` / `avoid_count` / horizon 별 `win_rate` /
`avg_return` / `max_drawdown` / horizon 별 `missing_result_count` /
`cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` /
`regime_breakdown`.

### 백테스트 commit (BacktestRun + Result 적재)

```powershell
.\.venv\bin\python.exe -m scripts.run_backtest --strategy multi_signal `
    --from-date 2026-04-01 --to-date 2026-05-04 --commit
```

### 백테스트 결과 read-only 조회

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/strategies | Select-Object -ExpandProperty Content
Invoke-WebRequest "http://127.0.0.1:8000/api/backtest/runs?strategy=top_grade&limit=10" | Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:8000/api/backtest/runs/42 | Select-Object -ExpandProperty Content
```

또는 프런트 `/backtest` (Sidebar 10번째 `백테스트 (β)`) 에서 시각적으로 조회.

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

## 누적 인수 태그 (v0.1 ~ v0.7)

- `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
- `v0.2-frontend-final`
- `v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final`
- `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` → `v0.4-frontend-reports` → `v0.4-final`
- `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` → `v0.5-frontend-themes` → `v0.5-final`
- `v0.6-fundamental-data-layer` → `v0.6-earnings-event-pipeline` → `v0.6-fundamental-score` → `v0.6-frontend-fundamentals` → `v0.6-final`
- `v0.7-strategy-interface` → `v0.7-backtest-engine` → `v0.7-backtest-cost-regime` → **`v0.7-frontend-backtest`** → `v0.7-final` (예정)
