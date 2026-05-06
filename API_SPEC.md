# API_SPEC.md

> 본 문서는 **v0.8 Phase B 시점** 기준이다 (`v0.8-auth-foundation` 누적).
> v0.5 §14 테마 + v0.6 §15 재무·실적 + v0.7 §16 백테스트 + v0.8 §17 인증 +
> 추천 / 보유 evidence 화이트리스트 + Strategy / Backtest 응답에 broker / 주문
> 필드 0건 가드가 모두 반영되어 있다.

FastAPI 기반 PC 대시보드 API 명세이다.

v0.1 ~ v0.7 모든 사이클의 API는 조회 중심이었다 (read-only GET 만). v0.8 Phase
B 에서 단일 사용자 인증 도메인 한정으로 **POST 라우터 첫 도입** —
`POST /api/auth/login` / `POST /api/auth/logout` / `GET /api/auth/me` 3건. 그
외 도메인 (recommendations / holdings / backtest / 잡 트리거 / 알림 / 점수 등)
은 여전히 read-only GET 만. 실거래 주문 API는 구현하지 않는다.

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

v0.8 Phase B 가 도입한 POST 는 `/api/auth/login` + `/api/auth/logout` 2건뿐이다.
Watchlist (`/api/watchlists/...`) 는 Phase C 후보 — Phase B 에서는 도입하지 않는다.
