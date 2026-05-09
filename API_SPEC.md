# API_SPEC.md

> 본 문서는 **v1.0 Phase D 진행 시점** 기준이다 (이전 마감 태그 `v0.16-final`,
> 현재 태그 `v1.0-real-order-executor-real`).
>
> **v1.0 Phase D 신규 엔드포인트 (mutation 1건 추가, 합계 15 → 16):**
>
> - `POST /api/real-orders/{order_id}/sync` — RealOrder 의 KIS 체결 상태를 수동 트리거로
>   sync. v1.0 의 SOLE RealOrder mutation 라우터.
>   - **3중 게이트:** AUTH (`require_auth`, AUTH_ENABLED=true 시 401 if missing Bearer) +
>     `TRADING_SAFETY_ENABLED=true` (else 503) + `KILL_SWITCH_ENABLED=false` (else 503).
>   - `REAL_TRADING_ENABLED` / `KIS_ORDER_ENABLED` 는 **의도적으로 미강제** — 운영자가
>     사고 후 sync 가능해야 함 (RUNBOOK §6 기준).
>   - **요청 본문 (옵션):** `RealOrderSyncRequest { kis_order_no?: string }` — 운영자가
>     KIS HTS 등에서 보유한 plaintext 주문번호를 in-memory 만 transport 에 전달.
>     RealFill / RealOrder / audit / 응답 본문 어디에도 저장 0건.
>   - **응답:** `RealOrderSyncResponse { real_order_id, real_order_status, fill_status,
>     fills_added, fills_total, synced_at, message }`.
>     - `fill_status`: `FULL` / `PARTIAL` / `NONE` / `REJECTED` / `CANCELED` / `FAILED` (6 분류).
>     - `fills_added`: delta>0 시 1, idempotent 시 0.
>     - `fills_total`: sync 후 RealFill quantity 누적합.
>   - **금지 응답 substring 0건:** `api_key` / `app_secret` / `appsecret` / `access_token` /
>     `kis_account_no` / `kis_app_key` / `kis_app_secret` / `broker_order_no` /
>     `broker_order_id` / `kis_order_id` / `real_account` / `raw_text` / `raw_response` /
>     `full_text` / `source_file_path` / `jwt_secret`.
>   - **에러 코드:** 200 / 401 / 404 (order not found) / 405 (PUT/PATCH/DELETE) /
>     503 (TRADING_SAFETY_DISABLED 또는 KILL_SWITCH_ON).
>
> **DRY_RUN RealOrder 정책:** sync 호출 시 transport 호출 0건으로 즉시 NONE 반환
> (`message="sync skipped: DRY_RUN_ORDER_SKIPPED"`). v0.16 의 "FakeTransport 가 항상 FILLED
> 반환" 동작은 v1.0 에서 의도적으로 폐지 — 실 KIS 의 fake order_no 충돌 위험 차단.
>
> **델타 기반 idempotency:** 반복 sync 호출은 `kis_total - existing_total = 0` 이면 신규
> RealFill 행 0건 (idempotent). delta < 0 (KIS 가 내부 합계보다 작은 filled_quantity 보고) →
> `ApprovalAuditLog(FILL_SYNC_NEGATIVE_DELTA)` 1행 + `fill_status="FAILED"` 반환 (RUNBOOK §6).
>
> **v0.16 Phase E read-only 엔드포인트 (변경 0건):**
>
> - `GET /api/real-orders?status=&candidate_id=&limit=&offset=` — RealOrder 목록 조회
>   (read-only). status / candidate_id 필터. 기본 limit=100, offset=0. 응답 타입:
>   `RealOrdersResponse { items: RealOrder[], total, limit, offset }`.
>   **금지 응답 필드 0건**: `broker_order_no_hash` / `api_key` / `app_secret` /
>   `access_token` / `raw_response` / `account_number` / `real_account`.
> - `GET /api/real-orders/{id}` — RealOrder 상세 + 연관 RealFill 전체.
>   응답 타입: `RealOrderDetailResponse { order: RealOrder, fills: RealFill[] }`.
>   금지 필드 동일. order not found → 404.
>
> **real_order_routes.py forbidden import (AST 회귀 단언):**
> `httpx / requests / urllib / urllib3` 0건. transport 는 항상 DI.
>
> **mutation 라우터 변동:** v0.15 마감 시 15건 → v1.0 Phase D 16건 (real-orders sync 1 추가).
> 실 KIS / FULL_AUTO / SMALL_AUTO 라우터는 여전히 0건.
>
> 본 문서는 **v0.15 마감 시점** 기준이다 (마감 태그 `v0.15-final`).
> v0.15 Phase D 가 **Approval Trading Safety Layer API** 7 라우터
> (read-only GET 3건 + mutation 4건) 를 추가했고, Phase E 는 14번째 프런트
> 화면 `/approvals` 에서 본 7 라우터를 모두 소비한다 (백엔드 라우터 변경 0건).
>
> **v0.15 Phase D 신규 엔드포인트:**
>
> - `GET /api/approvals/candidates?status=&account_id=&limit=` — OrderCandidate
>   목록 (read-only). status 필터 미지정 시 PENDING_APPROVAL 만 반환
> - `GET /api/approvals/candidates/{id}` — 후보 + risk_check_result
>   whitelist 반환. forbidden 응답 필드 0건
> - `POST /api/approvals/candidates` — 후보 생성 + PreTradeRiskEngine 평가.
>   3중 게이트: `TRADING_SAFETY_ENABLED=true` + `KILL_SWITCH_ENABLED=false`
>   + `require_auth`. 통과 시 PENDING_APPROVAL, 실패 시 RISK_REJECTED.
>   audit row: CREATED → RISK_CHECKED → (RISK_REJECTED?)
> - `POST /api/approvals/{id}/approve` — 3중 게이트. PENDING_APPROVAL → 재
>   risk check → APPROVED → `SimulationBroker.submit_order` (paper only) →
>   EXECUTED_PAPER + virtual_order_id attach. **실 KIS 주문 / 실 broker
>   호출 0건** (AST 회귀 단언). audit: APPROVED + EXECUTED_PAPER
> - `POST /api/approvals/{id}/reject` — 3중 게이트. body `{reason}` 필수
>   (256자 자동 truncate). audit: REJECTED
> - `POST /api/approvals/{id}/expire` — TRADING_SAFETY_ENABLED 필요 (kill
>   switch 무관 — 만료는 운영자 안전 가드와 분리). audit: EXPIRED
> - `GET /api/approvals/audit?candidate_id=&event_type=&limit=` — 감사 로그
>   조회 (read-only). 평문 IP / user_agent 응답 0건 — DB 저장도 SHA256 만
>
> **forbidden 응답 필드 (회귀 단언):** `api_key` / `token` / `secret` /
> `source_file_path` / `broker_order_id` / `kis_order_id` / `real_account` /
> `real_order_id` / `broker` / `account_number` / `raw_text` / `body` /
> `full_text` 0건.
>
> **approval_routes.py / approval_service.py forbidden import (AST 회귀
> 단언):** `requests / httpx / urllib / urllib3 / app.kis /
> app.data.dart_provider / app.data.rss_provider /
> app.data.collectors.kis_client` 0건.
>
> **mutation 라우터 변동:** v0.14 의 11건 → v0.15 Phase D 15건 (+4 approval).
> 실 KIS / FULL_AUTO / SMALL_AUTO 라우터는 여전히 0건.
>
> 본 문서는 **v0.14 마감 시점** 기준이다 (마감 태그 `v0.14-final`).
> v0.14 Phase D 가 **Paper / Simulation Trading API** 6 라우터 (read-only
> GET 4건 + mutation 2건) 를 추가했다. 모든 mutation 은 `Settings.paper_trading_enabled=true`
> + `require_auth` 필요. `PAPER_TRADING_ENABLED=false` (default) 시 mutation
> 라우터는 **503 Service Unavailable** 응답. 실 KIS 주문 / 자동매매 / FULL_AUTO
> 라우터 0건 그대로 유지.
>
> **v0.14 Phase D 신규 엔드포인트 (write 라우터 +2건, read-only GET +4건):**
> - `GET /api/paper/account` — VirtualAccount 합산 (cash / market_value /
>   total_value / realized_pnl / unrealized_pnl). 최신 VirtualPnLSnapshot
>   기반 합산. `account_id` query 옵션.
> - `GET /api/paper/orders?status=&symbol=&limit=` — 주문 이력. `id` desc 정렬.
> - `GET /api/paper/positions?include_closed=` — 포지션 현황. open positions 만
>   기본 노출, `last_close` / `market_value` / `unrealized_pnl` 는 daily_prices.close
>   기반 lookback 14일 평가.
> - `GET /api/paper/pnl?from_date=&to_date=&limit=` — VirtualPnLSnapshot 시계열.
>   inverted date range → 422.
> - `POST /api/paper/orders` — `SimulationBroker.submit_order` 호출. PAPER_TRADING_ENABLED=false
>   시 503. AUTH 필요. body: `symbol / side / quantity / order_type / limit_price?
>   / idempotency_key? / note? / account_id?`. idempotency_key 중복 시 기존 row
>   반환 + `deduplicated=true`. 검증 실패 → 422.
> - `DELETE /api/paper/orders/{id}?reason=` — `SimulationBroker.cancel_order`.
>   CREATED/SUBMITTED → CANCELED. terminal/fill 상태 → 422. unknown id → 404.
>   PAPER_TRADING_ENABLED=false 시 503. AUTH 필요.
>
> **forbidden 응답 필드 (회귀 단언):** `api_key` / `token` / `secret` /
> `source_file_path` / `broker_order_id` / `kis_order_id` / `real_account` /
> `broker` / `account_number` / `raw_text` / `body` / `full_text` 0건.
>
> **paper_routes.py forbidden import (AST 회귀 단언):** `requests / httpx /
> urllib / urllib3 / app.kis / app.data.dart_provider / app.data.rss_provider /
> app.data.collectors.kis_client` 0건.
>
> **mutation 라우터 변동:** v0.9 의 9건 → v0.14 Phase D 11건 (+2 paper). 실 KIS
> / FULL_AUTO / SMALL_AUTO / APPROVAL 라우터는 여전히 0건.
>
> 본 문서는 **v0.13 마감 시점** 기준이다 (마감 태그 `v0.13-final`).
> v0.5 §14 테마 + v0.6 §15 재무·실적 + v0.7 §16 백테스트 + v0.8 §17 인증 +
> v0.8 §18 Watchlist + v0.9 §19 Watchlist 고도화 + v0.9 §20 UserPreference +
> v0.10 §21 Provider Health (read-only) + v0.11 Phase D 의 6 신규 필드 (24h
> aggregates + recent_failures) + v0.12 §22 백테스트 확장 (folds + comparison) +
> v0.13 §23 Validation Report + score_delta evidence 안내가 모두 반영되어 있다.
>
> **v0.13 신규 엔드포인트 (write 라우터 0건 추가, read-only GET 4건):**
> - `GET /api/validation/report` — 전체 요약 (`run_count` / `signal_count` / `buy_count` /
>   `win_rate_5d` / `avg_return_5d` / `score_delta` 집계). `score_delta.data_source_counts` 는
>   PROVIDER/CSV/MANUAL/FAKE 소스별 집계. **POST/PUT/PATCH/DELETE → 405**.
> - `GET /api/validation/report/by-strategy` — 전략별 집계 (`strategy_name` /
>   `run_count` / `signal_count` / `buy_count` / `win_rate_5d` / `avg_return_5d` /
>   `cost_adjusted_avg_return_5d` / `max_drawdown`).
> - `GET /api/validation/report/by-regime` — 시장 국면별 집계 (`regime` /
>   `buy_count` / `win_rate_5d` / `avg_return_5d`).
> - `GET /api/validation/report/by-sector` — 섹터별 집계 (`sector` /
>   `buy_count` / `win_rate_5d` / `avg_return_5d`). Stock LEFT JOIN, 매핑 없는 경우 `UNKNOWN`.
>
> **score_delta evidence (v0.13):** `RecommendationItemSchema` / `HoldingCheckSchema` 에
> `score_delta?: ScoreDeltaSummary` nullable 필드 추가. `evidence_json` raw 미노출 —
> `_SCORE_DELTA_EVIDENCE_FIELDS` whitelist 추출만. `PROVIDER_SCORE_POLICY_ENABLED=False` 기본.
>
> **v0.11 신규 엔드포인트 (write 라우터 0건 추가, read-only GET 1건):**
> - `GET /metrics` — Prometheus text format. `PROMETHEUS_ENABLED=false` (기본)
>   시 404, true 시 200+text/plain. POST/PUT/DELETE 모두 405. counter/gauge/
>   histogram 라벨은 `provider` + `error_kind` 만 (URL / API key / message text
>   일체 노출 0건). 자세한 metric 카탈로그는 `app/monitoring/prometheus.py` 의
>   `PrometheusMetrics.build` 참조.
>
> v0.13 cycle 의 누적 write 라우터 변동 0건 (v0.9 의 11건 그대로 유지).
>
> **v0.9 Phase C 신규 엔드포인트 (v0.8 5건 + v0.9 6건 = 총 11건 write 라우터):**
> - `PATCH /api/watchlists/{id}` — name 변경 / is_default 토글 (이전 default 자동 demote)
> - `DELETE /api/watchlists/{id}` — watchlist 삭제 + items cascade (기본 목록 삭제 허용)
> - `GET /api/watchlists/{id}/items` — 페이지네이션 (limit/offset) + symbol_prefix 필터
> - `PATCH /api/watchlists/{id}/items/{symbol}` — memo 수정 / null 초기화
> - `GET /api/users/me/preferences` — lazy-create 후 반환
> - `PUT /api/users/me/preferences` — watchlist 소유권 검증; 비밀 키 포함 시 422
>
> 모든 신규 엔드포인트: password / password_hash / access_token / jwt_secret /
> source_file_path / broker / account / quantity / order_price / order_type / side
> 응답 0건 가드.

FastAPI 기반 PC 대시보드 API 명세이다.

v0.1 ~ v0.7 모든 사이클의 API는 조회 중심이었다 (read-only GET 만). v0.8 Phase
B 에서 단일 사용자 인증 도메인 한정으로 **POST 라우터 첫 도입** —
`POST /api/auth/login` / `POST /api/auth/logout` / `GET /api/auth/me` 3건.
v0.8 Phase C 에서 **Watchlist 도메인 한정으로 POST/DELETE 추가** —
`GET/POST /api/watchlists` / `GET /api/watchlists/{id}` / `POST/DELETE
/api/watchlists/{id}/items[/{symbol}]` 5건. 그 외 도메인 (recommendations /
holdings / backtest / 잡 트리거 / 알림 / 점수 등) 은 여전히 read-only GET 만.
실거래 주문 API는 구현하지 않는다.

v0.7 마감 시점 기준으로 23+ GET 라우터가 `app/api/routes.py`에 구현되어 있고
[Pydantic schema](app/api/schemas.py)는 risk_summary, risk_level, risk_flags,
decision, alert 정보를 응답에 포함한다. Decimal 컬럼은 정밀도 보존을 위해
JSON에 모두 문자열로 직렬화된다 (예: `total_score: "82.0000"`).

Phase 7 후속에서 추천 성과(`recommendation_results`)가 응답에 노출된다:

* `GET /api/recommendations/{run_id}` 와 `GET /api/recommendations/latest` 의
  각 recommendation 항목에 `results: List[RecommendationResultSchema]` 필드 포함
  (`days_after`, `result_date`, `open/high/low/close/max_return`, `max_drawdown`,
  `result_status`).
* 추천 실행 객체(`run`)에는 `telegram_sent`가 포함된다. DRY_RUN/FAILED/DISABLED는
  실제 발송이 아니므로 `false`로 유지된다.
* 각 recommendation 항목에는 component score 확인용 `technical_score`,
  `news_score`, `supply_score`, `fundamental_score`, `ai_score`, `risk_score`가
  문자열 Decimal로 포함된다.
* 각 recommendation 항목에는 기존 `risk_summary`와 함께 대시보드 표시용
  `risk_level`, `risk_flags` 평탄 필드도 포함된다.
* v0.4 Phase C 부터 각 recommendation 항목에는 Analyst & Theme Intelligence
  보조 점수 `report_score`, `theme_signal_score`, `report_evidence`가 nullable
  필드로 포함된다. 값이 없으면 `null`이며, `source_file_path`는 노출하지 않는다.
* v0.5 Phase D 부터 각 recommendation 항목에는 `news_evidence`,
  `disclosure_risk_evidence` 필드가 nullable 로 포함된다 (Phase C 의
  `RealNewsScoreProducer` / `DisclosureRiskProducer` 가 wired 된 run 에서만
  값이 채워지며, 둘 다 `DataSnapshot.market_context_json` 에서 읽어와
  whitelist 된 안전 필드만 노출 — 본문 / `source_file_path` 등 절대 미노출).
* `GET /api/reports/today` 응답의 `top_recommendations`도 동일 `results` 필드 노출.
* `GET /api/recommendations/history` 응답의 각 항목에 `success_rate` (days_after=5
  finalized 행 기준 0~100 백분율) 및 `avg_close_return_1d/3d/5d/20d` 집계 필드 포함.
  데이터가 없으면 `null`로 일관 처리.

## 공통 응답 원칙

- JSON 응답
- 날짜는 ISO 8601 사용
- 금액/가격은 숫자 사용
- 오류 응답 형식 통일

## 1. 오늘의 리포트

### GET /api/reports/today

오늘 시장 요약, 추천 종목, 보유 종목 경고를 조회한다.

응답 예시:

```json
{
  "date": "2026-05-04",
  "market_summary": {
    "regime": "UPTREND_EARLY",
    "market_score": 72,
    "risk_level": "MEDIUM"
  },
  "top_recommendations": [],
  "holding_alerts": [],
  "job_status": "SUCCESS"
}
```

## 2. 최신 추천

### GET /api/recommendations/latest

최신 추천 실행 결과를 조회한다.

Query:

- `market`: optional
- `limit`: default 10

## 3. 추천 이력

### GET /api/recommendations/history

날짜별 추천 실행 이력을 조회한다.

Query:

- `start_date`
- `end_date`
- `page`
- `page_size`

## 4. 추천 상세

### GET /api/recommendations/{run_id}

특정 추천 실행의 상세 종목 리스트를 조회한다.

## 5. 보유 종목

### GET /api/holdings

현재 보유 종목을 조회한다.

## 6. 최신 보유 점검

### GET /api/holdings/checks/latest

최신 장전/장후 보유 점검 결과를 조회한다.

Query:

- `check_type`: PRE_MARKET or POST_MARKET optional

## 7. 종목별 보유 점검 이력

### GET /api/holdings/{symbol}/checks

특정 종목의 점검 이력을 조회한다.

응답:

* `items`: 최신순(`check_date` desc, 동일 일자에서는 POST_MARKET 이 PRE_MARKET 보다 뒤)
  으로 정렬된 보유 점검 이력. 각 항목은 `decision`, `alert`, `risk_level`,
  `risk_flags`, `risk_summary`를 포함한다.
* `summary`: 동일 종목 전체 점검 이력에 대한 추세/카운트 metric. 데이터가
  없으면 카운트 필드는 0, 그 외 필드는 `null`로 일관 처리된다. 필드:
  * `total_check_count`, `alert_count`, `high_risk_count`
  * `latest_check_date`, `latest_decision`, `latest_risk_level`
  * `latest_total_score`, `previous_total_score`, `total_score_change`
    (점검 1건뿐이면 previous/change 는 `null`)
  * `latest_return_rate`, `best_return_rate`, `worst_return_rate`

Query:

- `limit`: items 만 잘라낸다 (default 20, max 200). `summary` 는 limit 과 무관하게
  종목 전체 이력을 기준으로 집계된다.

## 8. 종목 상세

### GET /api/stocks/{symbol}

종목 상세 화면용 데이터를 조회한다.

응답에는 다음 필드가 포함된다:

* `stock`: 종목 기본정보
* `latest_price`: 최신 일봉 가격 (`daily_prices`)
* `latest_indicator`: 최신 기술 지표 (`stock_indicators`)
* `analyst_reports`: v0.4 Phase D Analyst & Theme Intelligence 요약.
  * `latest_consensus`: 최신 `report_consensus_snapshots` 1건. `report_count`,
    `avg_target_price`, `min_target_price`, `max_target_price`, rating distribution,
    `latest_published_at` 포함.
  * `recent_reports`: 최근 analyst report 목록. `broker_name`, `published_at`,
    `title`, `rating`, `target_price`, 짧은 `summary`, `source_url` 포함.
  * `related_themes`: 종목 관련 테마와 mapping 영향. `theme_name`,
    `theme_category`, `direction`, `time_horizon`, `impact_direction`,
    `impact_path` 포함.
  * `recent_signal_events`: 최근 signal event 목록. `event_type`, `direction`,
    `strength`, 짧은 `summary` 포함.
  * `source_file_path`는 schema와 응답에서 제외한다.
* `recent_recommendations`: 최근 추천 이력. 각 항목은 `run_id`, `run_date`,
  `telegram_sent`, component score, `risk_level`, `risk_flags`, `risk_summary`,
  `results[]` 추천 성과를 포함한다.
* `recent_holding_checks`: 최근 보유 점검 이력. 각 항목은 `decision`, `alert`,
  `risk_level`, `risk_flags`, `risk_summary`를 포함한다.

Query:

- `recommendation_limit`: default 10, max 100
- `holding_check_limit`: default 20, max 200
- `report_limit`: default 5, max 50
- `theme_limit`: default 10, max 50
- `signal_limit`: default 10, max 50

### GET /api/stocks/{symbol}/reports

종목 상세의 Analyst & Theme Intelligence 블록만 조회하는 read-only API이다.
`GET /api/stocks/{symbol}.analyst_reports`와 동일한 구조를 반환한다.

Query:

- `report_limit`: default 5, max 50
- `theme_limit`: default 10, max 50
- `signal_limit`: default 10, max 50

오류:

- 404: 해당 `symbol` 의 `stocks` 레코드가 존재하지 않음

### GET /api/stocks/{symbol}/prices

종목 상세 화면 일봉 차트용 가격 시계열 (read-only). KIS API 호출 없이 기존
`daily_prices` 테이블만 조회한다.

응답:

* `symbol`: 요청 심볼
* `days`: 요청한 기간 길이
* `count`: 실제 반환된 일봉 수 (≤ `days`)
* `prices[]`: 날짜 오름차순 (가장 오래된 일자가 첫 항목, 최신 일자가 마지막 항목).
  각 항목은 `date`, `open`, `high`, `low`, `close`, `volume`, `trading_value` 를 포함한다.
  Decimal 필드는 `string` 으로 직렬화 (lossless). `volume` 은 `int`.

Query:

- `days`: default 120, min 1, max 500. 검증 실패 시 422.

오류:

- 404: 해당 `symbol` 의 `stocks` 레코드가 존재하지 않음
- 200 (count=0, prices=[]): `stocks` 는 있으나 `daily_prices` 에 데이터가 없음

## 9. 시가총액 TOP 500

### GET /api/universe/market-cap-top

시가총액 상위 종목 유니버스를 조회한다.

Query:

- `market`: KOSPI/KOSDAQ/ALL
- `date`
- `limit`
- `sector`

## 10. 시장 국면

### GET /api/market-regime/latest

최신 시장 국면 판단 결과를 조회한다.

## 11. 뉴스

### GET /api/news

뉴스 목록을 조회한다.

Query:

- `symbol`
- `theme`
- `start_time`
- `end_time`
- `sentiment`

## 12. 시스템 작업 로그

### GET /api/jobs

스케줄러 작업 실행 로그를 조회한다.

응답의 각 job item은 원본 `result_summary`를 유지하면서, 대시보드 표시용으로
다음 필드를 가능한 경우 평탄화해 제공한다:

- `success_count`
- `failed_count`
- `skipped_count`
- `partial_count`
- `total_count`
- `provider_type`
- `universe_name`
- `batch_size`

Query:

- `job_name`
- `status`
- `start_date`
- `end_date`

### GET /api/jobs/{job_id}

job_runs 단건 상세를 조회한다.

응답은 `/api/jobs`와 동일한 평탄화 필드를 포함하고, 원본 `result_summary` JSON을 그대로 반환한다.
`result_summary`에 다음 상세 배열이 있으면 최상위 필드로도 그대로 노출한다:

- `successes`
- `skipped`
- `failures`
- `batches`

공통 평탄화 필드:

- `success_count`
- `failed_count`
- `skipped_count`
- `partial_count`
- `total_count`
- `provider_type`
- `universe_name`
- `batch_size`

존재하지 않는 `job_id`는 `404`를 반환한다.

## 13. 설정

### GET /api/settings

현재 시스템 설정을 조회한다.

## 14. 테마 (v0.5 Phase D)

### GET /api/themes/ranking

증권사 리포트에서 추출된 테마 랭킹을 조회한다. 정렬은 `id` 내림차순(가장 최근
삽입 순)이며, 응답의 각 항목에는 `mapping_count`(연결 종목 수)와
`signal_event_count`(연결 시그널 이벤트 수)가 포함된다. `source_file_path`는
응답에 절대 노출되지 않는다.

Query:

- `category`: optional. 예) `SEMICONDUCTOR`, `RISK`, `SECONDARY_BATTERY`
- `direction`: optional. `POSITIVE` / `NEGATIVE` / `NEUTRAL` 중 하나. 다른 값은 422
- `limit`: default 50, min 1, max 200

응답 예시:

```json
{
  "items": [
    {
      "theme_id": 41,
      "theme_name": "HBM",
      "theme_category": "SEMICONDUCTOR",
      "direction": "POSITIVE",
      "time_horizon": "MID",
      "summary": "AI 서버 메모리 수요",
      "confidence": "0.800",
      "source_report_id": 12,
      "mapping_count": 2,
      "signal_event_count": 1
    }
  ],
  "category": null,
  "direction": null,
  "limit": 50
}
```

### GET /api/themes/{theme_id}

테마 단건 상세 + 연결된 종목 매핑 + 시그널 이벤트를 조회한다. 응답의 매핑
항목은 `theme_*` 필드를 포함하지 않는다 (theme 가 부모 컨텍스트). 시그널
이벤트는 기존 `ReportSignalEventSchema` 형태(`evidence_json` 포함, 본문 미노출).

Query:

- `mapping_limit`: default 50, min 1, max 200
- `signal_limit`: default 50, min 1, max 200

오류:

- 404: 해당 `theme_id` 의 `report_themes` 레코드가 없음

## 15. 재무 / 실적 (v0.6 Phase D)

### GET /api/stocks/{symbol}/fundamentals

종목별 최신 재무 스냅샷과 최근 재무 히스토리를 조회한다. v0.6 Phase A 의
`fundamental_snapshots` 테이블에 적재된 정량 지표만 노출하며, 운영자 메모 /
원문 / 본문 / `source_file_path` / PDF / Excel BLOB 은 응답·로그·프런트
어디에도 절대 노출되지 않는다.

Query:

- `limit`: default 8, min 1, max 40

오류:

- 404: 해당 `symbol` 의 `stocks` 레코드가 없음

응답 예시:

```json
{
  "symbol": "005930",
  "latest": {
    "snapshot_date": "2026-05-01",
    "fiscal_year": 2025,
    "fiscal_quarter": 4,
    "revenue": "100000.0000",
    "operating_income": "20000.0000",
    "net_income": "15000.0000",
    "total_assets": "500000.0000",
    "total_liabilities": "200000.0000",
    "total_equity": "300000.0000",
    "eps": "3500.0000",
    "bps": "60000.0000",
    "per": "12.0000",
    "pbr": "1.2000",
    "roe": "18.0000",
    "debt_ratio": "40.0000",
    "dividend_yield": "2.5000",
    "revenue_growth_yoy": "12.0000",
    "operating_income_growth_yoy": "18.0000",
    "source": "MANUAL"
  },
  "history": [...],
  "count": 4
}
```

### GET /api/stocks/{symbol}/earnings

종목별 최근 실적 이벤트(발표 + 컨센서스 surprise)를 조회한다. v0.6 Phase B 의
`earnings_events` 테이블 데이터를 노출. `memo` 는 500자 이하만 노출하며 본문 /
원문 / `source_file_path` 등은 0건.

Query:

- `limit`: default 8, min 1, max 40

오류:

- 404: 해당 `symbol` 의 `stocks` 레코드가 없음

응답 예시:

```json
{
  "symbol": "005930",
  "latest": {
    "event_date": "2026-05-01",
    "fiscal_year": 2026,
    "fiscal_quarter": 1,
    "event_type": "REPORT",
    "company_name": "삼성전자",
    "revenue_actual": null,
    "revenue_consensus": null,
    "operating_income_actual": "110.0000",
    "operating_income_consensus": "100.0000",
    "net_income_actual": null,
    "net_income_consensus": null,
    "eps_actual": "3500.0000",
    "eps_consensus": "3300.0000",
    "surprise_type": "BEAT",
    "surprise_pct": "10.0000",
    "source": "MANUAL",
    "memo": null
  },
  "events": [...],
  "count": 4
}
```

### GET /api/calendar/earnings

최근 / 다가오는 실적 이벤트를 캘린더 형태로 조회한다. `from_date` 가
생략되면 "오늘 (UTC) 이후"만 반환한다 (Today 카드 기본 use case).

Query:

- `from_date`: optional. ISO date (예: `2026-05-01`)
- `to_date`: optional. ISO date
- `surprise_type`: optional. `BEAT` / `MEET` / `MISS` / `UNKNOWN` 등 필터
- `limit`: default 20, min 1, max 100

응답 예시:

```json
{
  "items": [
    {
      "symbol": "005930",
      "company_name": "삼성전자",
      "event_date": "2026-05-08",
      "fiscal_year": 2026,
      "fiscal_quarter": 1,
      "event_type": "ANNOUNCEMENT",
      "surprise_type": null,
      "surprise_pct": null
    }
  ],
  "count": 1,
  "from_date": null,
  "to_date": null,
  "surprise_type": null,
  "limit": 20
}
```

### Recommendation / HoldingCheck evidence 확장 (v0.6 Phase D)

기존 `RecommendationItemSchema` / `HoldingCheckSchema` 응답에 다음 nullable
필드가 추가된다 (pre-v0.6 snapshot → null).

- `RecommendationItemSchema.fundamental_evidence`: `RealFundamentalScoreProducer` 가
  생성한 evidence dict. **whitelist**: `snapshot_date / fiscal_year /
  fiscal_quarter / per / pbr / roe / debt_ratio / revenue_growth_yoy /
  operating_income_growth_yoy / dividend_yield / reason`. 그 외 키는 라우터
  레벨에서 즉시 제거.
- `RecommendationItemSchema.earnings_evidence`: 현재는 항상 null (Phase C 에서
  RealEarningsScoreProducer 는 holding 흐름에만 주입). 미래 호환을 위해 schema
  필드는 유지.
- `HoldingCheckSchema.fundamental_evidence`: 동일 whitelist.
- `HoldingCheckSchema.earnings_evidence`: `RealEarningsScoreProducer` 가 생성한
  evidence dict. **whitelist**: `latest_event_date / fiscal_year /
  fiscal_quarter / event_type / surprise_type / surprise_pct /
  operating_income_actual / operating_income_consensus / reason`.
- `HoldingCheckSchema.news_evidence` / `disclosure_risk_evidence`: v0.5 Phase D 에서
  recommendation 에만 노출되던 evidence 가 holding check 응답에도 동일 형식으로
  노출 (Phase D 에서 이연 작업 흡수).

`source_file_path` / `body` / `content` / `full_text` / `raw_text` /
`paragraph` / `html_body` / `본문` / `원문` / `전문` 등 13종 forbidden 필드는
어떤 evidence 응답에도 0건 노출 — `_assert_no_source_file_path` recursive
helper 가 모든 신규 케이스에서 검증.

## 16. 백테스트 / 전략 (v0.7 Phase D)

### GET /api/strategies

등록된 룰 기반 전략 목록을 조회한다. 데이터는 backend 의 `app/strategy/registry.py`
의 `KNOWN_STRATEGIES` / `STRATEGY_REGISTRY` 에서 직접 빌드 — DB 접근 0건, 외부
API 호출 0건. 응답 항목의 `description` 은 전략 클래스 docstring 의 첫 줄.

응답 예시:

```json
{
  "items": [
    {
      "name": "TopGradeStrategy",
      "version": "v1.0.0",
      "description": "Trade on the recommendation grade alone."
    }
  ],
  "count": 3
}
```

### GET /api/backtest/runs

`BacktestRunRepository` 가 적재한 최근 백테스트 실행 목록. 정렬은 `run_date desc`.
`summary_json` 에 들어 있는 `cost_model_version` / `total_cost` /
`cost_adjusted_avg_return_5d` 는 라우터에서 추출해 응답 최상위 필드로 노출.

Query:

- `strategy`: optional. 전략 short name (`top_grade` / `high_score` / `multi_signal` 등)
- `limit`: default 20, min 1, max 100

응답 예시:

```json
{
  "items": [
    {
      "id": 42,
      "strategy_name": "top_grade",
      "strategy_version": "v1.0.0",
      "run_date": "2026-05-06",
      "start_date": "2026-04-01",
      "end_date": "2026-05-04",
      "signal_count": 5,
      "buy_count": 2,
      "pass_count": 2,
      "avoid_count": 1,
      "win_rate_5d": "0.5000",
      "avg_return_5d": "1.5000",
      "cost_adjusted_avg_return_5d": "1.1700",
      "max_drawdown": "-2.5000",
      "status": "SUCCESS",
      "cost_model_version": "constant-v1",
      "total_cost": "0.00330"
    }
  ],
  "count": 1,
  "strategy": null,
  "limit": 20
}
```

### GET /api/backtest/runs/{run_id}

특정 백테스트 실행의 상세 — run 헤더 + 신호 row 전체 + regime breakdown +
cost model 메타.

오류:

- 404: 해당 `run_id` 의 `backtest_runs` 행이 없음

응답 예시:

```json
{
  "run": { "...BacktestRunSchema..." },
  "results": [
    {
      "id": 1001,
      "symbol": "005930",
      "recommendation_id": 71,
      "signal_action": "BUY",
      "confidence": "0.7500",
      "reason": "grade=A",
      "grade": "A",
      "total_score": "80.0000",
      "return_5d": "1.5000",
      "cost_adjusted_return_5d": "1.1700",
      "max_drawdown": "-2.5000",
      "result_status": "SUCCESS",
      "regime": "UPTREND_EARLY",
      "evidence_json": { "grade": "A" }
    }
  ],
  "regime_breakdown": [
    {
      "regime": "UPTREND_EARLY",
      "buy_count": 2,
      "win_rate_5d": "0.5000",
      "avg_return_5d": "1.5000",
      "cost_adjusted_avg_return_5d": "1.1700"
    }
  ],
  "cost_model_version": "constant-v1",
  "total_cost": "0.00330",
  "summary_json": { "...": "..." },
  "notes": "win_rate / avg_return / max_drawdown are computed over BUY signals only."
}
```

**금지 필드**: `backtest_results` ORM 자체에 broker / account / quantity /
order_price / order_type / side 컬럼이 없으므로 응답에도 0건. e2e 테스트가 raw
JSON 트리에서 `source_file_path` / `order_type` / `quantity` 0건을 단언한다.

### GET /api/backtest/runs/{run_id}/folds

*(v0.12 Phase D)* Walk-forward 백테스트의 fold 목록을 `summary_json["walk_forward_folds"]`
에서 읽어 반환한다. DB 모델 변경 / Alembic revision 없이 순수 JSON 파싱.

오류:

- 404: 해당 `run_id` 의 `backtest_runs` 행이 없음
- key 부재 (`walk_forward_folds` 없음) → 200 + `folds: []` (not 404)
- non-dict 항목은 자동 건너뜀

응답 예시:

```json
{
  "run_id": 42,
  "mode": "walk_forward",
  "total_folds": 2,
  "avg_oos_win_rate_5d": "0.6000",
  "avg_oos_avg_return_5d": "1.2500",
  "folds": [
    {
      "fold_index": 0,
      "train_start": "2023-01-01",
      "train_end": "2023-06-30",
      "validate_start": "2023-07-01",
      "validate_end": "2023-09-30",
      "is_oos_gap": 0,
      "is_signal_count": 20,
      "is_buy_count": 12,
      "is_win_rate_5d": "0.6667",
      "is_avg_return_5d": "1.5000",
      "oos_signal_count": 10,
      "oos_buy_count": 6,
      "oos_win_rate_5d": "0.6000",
      "oos_avg_return_5d": "1.2000"
    }
  ]
}
```

**금지 동사**: POST/PUT/PATCH/DELETE → 405. 금지 필드: `source_file_path` / `raw_text` /
`본문` / `api_key` / `token` / `secret` / `order_id` / `quantity` / `broker` 0건.

### GET /api/backtest/runs/{run_id}/comparison

*(v0.12 Phase D)* Multi-strategy 비교 결과를 `summary_json["multi_strategy_comparison"]`
에서 읽어 반환한다. 각 전략의 sector/regime breakdown 포함.

오류:

- 404: 해당 `run_id` 의 `backtest_runs` 행이 없음
- key 부재 (`multi_strategy_comparison` 없음) → 200 + `strategies: []` (not 404)
- non-dict 항목은 자동 건너뜀

응답 예시:

```json
{
  "run_id": 42,
  "mode": "multi_strategy_comparison",
  "total_strategies": 2,
  "best_strategy_by_win_rate_5d": "TopGradeStrategy",
  "best_strategy_by_avg_return_5d": "TopGradeStrategy",
  "strategies": [
    {
      "strategy_name": "TopGradeStrategy",
      "strategy_version": "v1",
      "signal_count": 30,
      "buy_count": 18,
      "pass_count": 12,
      "avoid_count": 0,
      "win_rate_5d": "0.6667",
      "avg_return_5d": "1.5000",
      "cost_adjusted_avg_return_5d": "1.1700",
      "max_drawdown": "-2.5000",
      "regime_breakdown": [
        {
          "regime": "UPTREND_EARLY",
          "buy_count": 10,
          "win_rate_5d": "0.7000",
          "avg_return_5d": "2.0000",
          "cost_adjusted_avg_return_5d": "1.6700"
        }
      ],
      "sector_breakdown": [
        {
          "sector": "반도체",
          "signal_count": 15,
          "buy_count": 10,
          "win_rate_5d": "0.7000",
          "avg_return_5d": "1.8000"
        }
      ]
    }
  ]
}
```

**금지 동사**: POST/PUT/PATCH/DELETE → 405. 금지 필드: `source_file_path` / `raw_text` /
`본문` / `api_key` / `token` / `secret` / `order_id` / `quantity` / `broker` 0건.

## 16-B. Validation Report (v0.13 Phase C)

`backtest_runs` / `backtest_results` 기존 테이블 기반 읽기 전용 집계 API.
Alembic revision 0건. 신규 mutation 라우터 0건. raw evidence_json 미노출.

### GET /api/validation/report

전체 백테스트 실행을 집계한 요약 + score_delta 통계.

응답 예시:

```json
{
  "generated_at": "2026-05-07T10:00:00+00:00",
  "run_count": 5,
  "signal_count": 50,
  "buy_count": 20,
  "win_rate_5d": "0.6500",
  "avg_return_5d": "0.0250",
  "score_delta": {
    "total_scored": 15,
    "policy_enabled_count": 10,
    "avg_delta": "-3.2000",
    "positive_delta_count": 2,
    "negative_delta_count": 10,
    "neutral_delta_count": 3,
    "data_source_counts": {"CSV": 8, "PROVIDER": 5, "MANUAL": 2}
  }
}
```

### GET /api/validation/report/by-strategy

전략별 집계. `strategy_name` 알파벳 오름차순 정렬.

```json
{
  "count": 2,
  "items": [
    {
      "strategy_name": "TopGradeStrategy",
      "run_count": 3,
      "signal_count": 30,
      "buy_count": 12,
      "win_rate_5d": "0.7500",
      "avg_return_5d": "0.0350",
      "cost_adjusted_avg_return_5d": "0.0300",
      "max_drawdown": "-0.0500"
    }
  ]
}
```

### GET /api/validation/report/by-regime

BUY 신호를 regime 별로 집계. 승률 = `return_5d > 0` 비율.

```json
{
  "count": 2,
  "items": [
    {"regime": "BEAR", "buy_count": 5, "win_rate_5d": "0.4000", "avg_return_5d": "-0.0100"},
    {"regime": "BULL", "buy_count": 15, "win_rate_5d": "0.8000", "avg_return_5d": "0.0500"}
  ]
}
```

- `regime=NULL` → `"UNCLASSIFIED"` 버킷

### GET /api/validation/report/by-sector

BUY 신호를 `stocks.sector` 기반으로 집계. LEFT JOIN으로 symbol → sector 매핑.

```json
{
  "count": 2,
  "items": [
    {"sector": "IT서비스", "buy_count": 8, "win_rate_5d": "0.6250", "avg_return_5d": "0.0200"},
    {"sector": "반도체", "buy_count": 12, "win_rate_5d": "0.7500", "avg_return_5d": "0.0400"}
  ]
}
```

- `stocks` 테이블에 없는 symbol → `"UNKNOWN"` 버킷

**공통 정책**: POST/PUT/PATCH/DELETE → 405. 응답에 `raw_text` / `body` / `source_file_path` /
`evidence_json` 원본 0건. `score_delta.data_source_counts` 는 `PROVIDER` / `CSV` / `MANUAL` /
`FAKE` / `UNKNOWN` 5개 버킷만 사용.

## 17. 인증 (v0.8 Phase B)

v0.1 ~ v0.7 동안 일관 유지된 read-only 정책의 **첫 변경 cycle**. POST 라우터
3건만 추가 — 그 외 도메인 (recommendations / holdings / backtest / 잡 트리거 /
알림 / 점수 등) POST/PUT/DELETE 0건. 다중 사용자 / OAuth / SSO / refresh token
은 구현 범위 밖이다.

**운영 모드**: `Settings.auth_enabled` (env `AUTH_ENABLED`) 토글 — `false`
default 면 dev / CI 호환성 유지 (기존 GET 라우터 그대로 OPEN, login 도 ephemeral
secret 으로 동작). `true` 시 `JWT_SECRET` 미설정이면 startup 거부 (`MissingSecretError`).
어느 모드에서도 기존 read-only GET 라우터는 강제 보호되지 않는다 — Watchlist
(Phase C) 가 첫 보호 라우터 후보.

### POST /api/auth/login

요청:

```json
{
  "username": "admin",
  "password": "hunter2!"
}
```

성공 (200):

```json
{
  "access_token": "eyJhbGciOiJI...",
  "token_type": "bearer",
  "expires_in": 86400,
  "issued_at": "2026-05-06T00:00:00+00:00",
  "expires_at": "2026-05-07T00:00:00+00:00",
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": true
  }
}
```

실패 (401):

```json
{ "detail": "invalid username or password" }
```

- 응답에 `password_hash` / `password` / `scrypt$...` 0건 (e2e + integration 가드).
- 실패 응답은 "unknown user" / "wrong password" / "deactivated" 를 단일 generic
  메시지로 통일 — username 존재 여부 노출 0건.
- 모든 시도는 `LoginAuditLog` 에 기록 (성공 = LOGIN_SUCCESS / 실패 = LOGIN_FAILED).
  `source_ip` 와 `user_agent` 는 SHA256 해시만 저장 (평문 0건).

### POST /api/auth/logout

요청 헤더에 `Authorization: Bearer <token>` (있으면 user 확인). body 없음.

성공 (200): `{"status": "ok"}`

- JWT 자체는 stateless — token revocation list 미구현.
- audit log 에 LOGOUT 이벤트만 기록.

### GET /api/auth/me

`AUTH_ENABLED=false`:

```json
{ "auth_enabled": false, "via": "auth_disabled_fallback", "user": null }
```

`AUTH_ENABLED=true` + 유효 Bearer token:

```json
{
  "auth_enabled": true,
  "via": "token",
  "user": { "id": 1, "username": "admin", "is_admin": true }
}
```

- `AUTH_ENABLED=true` 인데 token 없음 / 만료 / 위조 → 401 (`WWW-Authenticate: Bearer`)
- `AUTH_ENABLED=true` + token 발급 후 user 가 deactivate 된 경우 → 401
- 응답에 `password_hash` 0건 (DB row → schema 변환 시 명시적으로 제외)

**금지 필드** (v0.1 ~ v0.7 누적 정책 그대로 유지):

- `password_hash` / `password` / `scrypt$...` 노출 0건
- `source_file_path` 노출 0건 (audit / user 응답에는 source_file_path 자체가 없음)
- `broker` / `account` / `quantity` / `order_*` 0건
- 평문 IP / 평문 user agent 0건 (audit row 의 `source_ip_hash` /
  `user_agent_hash` 만, 라우터에서 schema 화 안 함)

## 18. Watchlist (v0.8 Phase C)

Watchlist 도메인 한정으로 read/write API. 5 라우터 모두 `require_auth` 가드를
거치며, 사용자별 데이터 격리는 라우터 레이어에서 `user_id` 기준으로 강제한다.

**인증 정책**:

- `AUTH_ENABLED=true`: Bearer token 필수. 401 + `WWW-Authenticate: Bearer`
- `AUTH_ENABLED=false` (dev / CI default): `require_auth` 가 dev fallback
  identity 로 해석 (user_id=1) — 기존 read-only 흐름 유지
- 다른 user 의 watchlist 에 접근 시 모두 **404** (403 아님 — 존재 여부 노출 0건)
- request body 에 `user_id` 포함 0건. 항상 token / dev context 에서 결정

**금지 필드 (응답)**:

- `broker` / `account` / `quantity` / `order_price` / `order_type` / `side` /
  `buy_price` / `sell_price` 0건 (WatchlistItem ORM column 자체 부재)
- `source_file_path` / `password_hash` / `password` / `scrypt$...` /
  `token` / `secret` / `jwt_secret` 0건

### GET /api/watchlists

응답 (200):

```json
{
  "watchlists": [
    {
      "id": 1,
      "name": "기본",
      "is_default": true,
      "item_count": 3,
      "created_at": "2026-05-06T00:00:00+00:00",
      "updated_at": "2026-05-06T00:00:00+00:00"
    }
  ]
}
```

- 정렬: `is_default desc, id asc`
- 401 (auth on, token 없음 / 무효 / 만료)

### GET /api/watchlists/{watchlist_id}

응답 (200): 위 schema 에 `items: [WatchlistItemSchema]` 추가

```json
{
  "id": 1,
  "name": "기본",
  "is_default": true,
  "item_count": 2,
  "created_at": "...",
  "updated_at": "...",
  "items": [
    {
      "id": 10,
      "symbol": "005930",
      "memo": "삼전 메모",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

- 404: 존재하지 않거나 다른 user 소유 (둘 다 동일 응답)
- 401: auth on + token 없음

### POST /api/watchlists

요청:

```json
{ "name": "단기", "is_default": false }
```

응답 (201): `WatchlistSchema` (위와 동일, `item_count = 0`)

- 422: name 빈 문자열 / 64자 초과
- 409: 같은 user 의 동일 name 중복
- `is_default=true` 이면 같은 user 의 기존 default 자동 demote (단일 default invariant)
- 401: auth on + token 없음

### POST /api/watchlists/{watchlist_id}/items

요청:

```json
{ "symbol": "005930", "memo": "장기 보유 후보" }
```

응답 (201):

```json
{
  "id": 10,
  "symbol": "005930",
  "memo": "장기 보유 후보",
  "created_at": "...",
  "updated_at": "..."
}
```

- symbol 은 자동 normalize (trim + uppercase) — `"  aapl "` → `"AAPL"`
- 404 (1): watchlist 존재 X 또는 다른 user 소유
- 404 (2): symbol 이 `stocks` 테이블에 없음 (`symbol not found in stocks`)
- 409: 동일 watchlist 에 이미 같은 symbol 존재
- 422: memo 500자 초과 / symbol 빈 문자열
- 401: auth on + token 없음

### DELETE /api/watchlists/{watchlist_id}/items/{symbol}

응답 (200):

```json
{ "status": "ok" }
```

- symbol path parameter 도 자동 normalize
- 404 (1): watchlist 존재 X 또는 다른 user 소유
- 404 (2): item 이 watchlist 에 없음
- 401: auth on + token 없음

### Phase C 한계 / 보류

- `DELETE /api/watchlists/{id}` (watchlist 자체 삭제) — Phase C 보류, v0.9 후보 → **v0.9 Phase C 에서 구현 완료**
- `PUT /api/watchlists/{id}` (rename / set_default) — Phase C 보류, v0.9 후보 → **v0.9 Phase C 에서 PATCH 로 구현 완료**
- `PUT /api/watchlists/{id}/items/{symbol}` (memo 수정) — Phase C 보류 → **v0.9 Phase C 에서 PATCH 로 구현 완료**
- 가격 / 등락률 / 점수 join — 별도 GET 라우터 호출로 클라이언트 측 결합 (Phase D 프런트)
- 알림 / 가격 트리거 — 별도 알림 cycle 후보 (v0.9+)

## 19. Watchlist 고도화 + UserPreference (v0.9 Phase C)

> v0.9 Phase C 에서 추가된 4개 Watchlist 엔드포인트 + UserPreference GET/PUT.
> AUTH_ENABLED=false 시 dev fallback user_id=1 사용, true 시 Bearer token 필수.

### PATCH /api/watchlists/{watchlist_id}

Watchlist 이름 변경 또는 기본 watchlist 지정.

요청 필드 (최소 1개 필수):

| 필드 | 타입 | 설명 |
|---|---|---|
| name | string? | 새 이름 (1-100자) |
| is_default | bool? | true 지정 시 해당 유저의 기존 default watchlist 자동 demote |

응답: `WatchlistSchema` (id / name / is_default / item_count / created_at / updated_at)

- 아무 필드도 없으면 422
- 타 유저 watchlist → 404

### DELETE /api/watchlists/{watchlist_id}

Watchlist 삭제. 포함된 WatchlistItem 전부 cascade 삭제.

응답:

```json
{ "status": "ok" }
```

- default watchlist 도 삭제 가능 (보호 없음)
- 타 유저 watchlist → 404

### GET /api/watchlists/{watchlist_id}/items

페이지네이션된 watchlist 항목 조회.

쿼리 파라미터:

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| limit | 50 | 한 번에 반환할 최대 건수 |
| offset | 0 | 건너뛸 행 수 |
| symbol_prefix | (없음) | symbol 앞자리 필터 (대소문자 무관) |

응답:

```json
{
  "total": 5,
  "items": [
    { "id": 1, "watchlist_id": 2, "symbol": "AAPL", "memo": "핵심 보유", "created_at": "...", "updated_at": "..." }
  ],
  "limit": 50,
  "offset": 0
}
```

- 타 유저 watchlist → 404

### PATCH /api/watchlists/{watchlist_id}/items/{symbol}

Watchlist 항목의 메모 수정.

요청:

```json
{ "memo": "새 메모" }
```

`memo: null` 로 보내면 메모 초기화.

응답: `WatchlistItemSchema` (id / watchlist_id / symbol / memo / created_at / updated_at)

- 항목 없으면 404

### GET /api/users/me/preferences

현재 사용자의 설정 조회. 없으면 빈 행 자동 생성 (lazy create).

응답:

```json
{
  "id": 1,
  "user_id": 1,
  "default_watchlist_id": null,
  "default_market": null,
  "default_strategy": null,
  "dashboard_layout_json": null,
  "notification_preferences_json": null,
  "created_at": "...",
  "updated_at": "..."
}
```

- AUTH_ENABLED=true 시 Bearer token 필수 (401)

### PUT /api/users/me/preferences

설정 부분 업데이트. 제공된 필드만 변경, 나머지는 그대로.

요청 필드 (모두 optional):

| 필드 | 타입 | 제약 |
|---|---|---|
| default_watchlist_id | int? | null 로 초기화 가능. 타 유저 watchlist_id → 404 |
| default_market | string? | null 로 초기화 가능 |
| default_strategy | string? | null 로 초기화 가능 |
| dashboard_layout_json | dict? | 임의 JSON |
| notification_preferences_json | dict? | 비밀 키 (password / secret / token / jwt / hash / key) 포함 시 422 |

응답: `UserPreferenceSchema` (위 GET 응답과 동일)

- AUTH_ENABLED=true 시 Bearer token 필수 (401)

### v0.9 Phase C 금지 필드 / 정책

- 모든 신규 응답에 password / password_hash / access_token / jwt_secret / secret / broker / account / quantity / order_price / order_type / side / source_file_path **0건**
- `notification_preferences_json` 의 비밀 키 포함 시 422 (저장 전 거부)
- Detailed health endpoint (`GET /api/health/detailed`) — v0.10 후보 (v0.9 미구현)

## v0.10 Phase D — Provider Health (read-only)

### GET /api/health/providers

`ProviderHealthMonitor` (in-memory) 의 현재 상태와 운영자 opt-in 플래그를 합쳐
provider 별 read-only 스냅샷을 반환한다.

**정책:**
- 외부 HTTP 호출 0건 — 응답은 in-memory 통계 + Settings 만으로 구성
- POST / PUT / DELETE 0건 — provider enable/disable 토글은 `.env` 수정 + 백엔드
  재시작으로만 가능 (해당 메서드는 모두 405)
- 응답에 절대 포함되지 않는 필드: `dart_api_key`, `crtfc_key`, `kis_app_key`,
  `kis_app_secret`, `rss_feed_urls`, `access_token`, `password`,
  `last_error_message` (URL query secret 포함 가능성). `last_error_kind`
  (TIMEOUT / SERVER_ERROR / CLIENT_ERROR / RATE_LIMIT / UNKNOWN) 만 노출
- 응답은 항상 canonical 3 provider (`kis`, `dart`, `rss`) 를 우선 포함하며
  추가 등록된 experimental provider 가 있을 경우 monitor iteration 순서로 append

**응답 (`ProviderHealthResponse`):**

```json
{
  "items": [
    {
      "provider_name": "dart",
      "enabled": false,
      "configured": false,
      "circuit_state": "UNREGISTERED",
      "call_count": 0,
      "success_count": 0,
      "failure_count": 0,
      "last_error_kind": null,
      "last_called_at": null
    }
  ],
  "count": 3
}
```

| 필드 | 타입 | 의미 |
|---|---|---|
| provider_name | string | `kis` / `dart` / `rss` 또는 운영자가 등록한 임의 이름 |
| enabled | bool | 운영자 토글 (`DART_ENABLED` / `RSS_NEWS_ENABLED` / KIS key 존재) |
| configured | bool | 최소 자격증명 / config 존재 (DART_API_KEY / RSS_FEED_URLS / KIS app_key+secret) |
| circuit_state | string | `CLOSED` / `OPEN` / `HALF_OPEN` / `UNREGISTERED` |
| call_count | int | monitor 가 기록한 누적 호출 수 |
| success_count | int | 성공 횟수 |
| failure_count | int | 실패 횟수 |
| last_error_kind | string? | 마지막 실패의 `ProviderErrorKind` enum 값 (`TIMEOUT` 등) |
| last_called_at | string? | ISO-8601 UTC, in-memory 만 (재시작 시 초기화) |
| call_count_24h | int | **(v0.11 Phase D)** 최근 24h 호출 수 (ring buffer 집계) |
| success_count_24h | int | **(v0.11 Phase D)** 최근 24h 성공 수 |
| failure_count_24h | int | **(v0.11 Phase D)** 최근 24h 실패 수 |
| success_rate_24h | float? | **(v0.11 Phase D)** 0.0~1.0; 24h call_count=0 일 때 `null` |
| avg_attempts_24h | float? | **(v0.11 Phase D)** retry 평균; 24h call_count=0 일 때 `null` |
| recent_failures | list | **(v0.11 Phase D)** 최신 5건, 각 항목은 `{timestamp, error_kind}` 만 (message text 0건) |

**상태 조합 의미:**

| enabled | configured | circuit_state | UI 표시 |
|---|---|---|---|
| false | false | UNREGISTERED | "비활성 — .env 에서 enable 필요" |
| true | false | UNREGISTERED | "활성이지만 자격증명 누락 — DART_API_KEY 등 확인 필요" (warning) |
| true | true | CLOSED | "정상 동작 중" |
| true | true | OPEN | "circuit breaker OPEN — 외부 provider 장애로 fast-fail 중" |
| true | true | HALF_OPEN | "복구 시도 중 — probe 호출 1회 진행" |

**금지:**
- POST / PUT / DELETE `/api/health/providers` (모두 405)
- provider enable / disable / reset breaker 등 mutation API 0건 (운영자 직접 재시작)

## 금지 API

v0.1 ~ v0.8 모든 cycle 에서 다음 API 는 만들지 않는다.

```text
POST /api/orders
POST /api/trading/auto
POST /api/trading/full-auto
POST /api/broker/place-order
POST /api/jobs/trigger              # 잡 수동 트리거 = v0.9+ 후보 (인증 + 보안 검토 후)
POST /api/recommendations            # 추천 즉시 생성 = v0.9+ 후보
POST /api/backtest/runs              # 백테스트 시작 = v0.9+ 후보
DELETE /api/recommendations/{id}     # 운영자 재정의 = 권한 검토 필요
```

v0.8 누적 도입 POST/DELETE 는 인증 도메인 (`/api/auth/login` + `/api/auth/logout`) +
Watchlist 도메인 (`POST /api/watchlists` + `POST /api/watchlists/{id}/items` +
`DELETE /api/watchlists/{id}/items/{symbol}`) **5건** 뿐. v0.9 Phase C 에서 추가된
mutating 엔드포인트 4건 (PATCH watchlist + DELETE watchlist + PATCH item + PUT preferences) 포함
**누적 9건**. 그 외 도메인 (Recommendations / Holdings / Backtest / Jobs / Notifications / Scoring)
POST/PUT/DELETE 는 v0.9 cycle 에서도 추가하지 않는다.
