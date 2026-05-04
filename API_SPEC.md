# API_SPEC.md

FastAPI 기반 PC 대시보드 API 명세이다.

v0.1 API는 조회 중심이다.  
실거래 주문 API는 구현하지 않는다.

Phase 7 기준 13개 GET 라우터가 `app/api/routes.py`에 구현되어 있고
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
* `recent_recommendations`: 최근 추천 이력. 각 항목은 `run_id`, `run_date`,
  `telegram_sent`, component score, `risk_level`, `risk_flags`, `risk_summary`,
  `results[]` 추천 성과를 포함한다.
* `recent_holding_checks`: 최근 보유 점검 이력. 각 항목은 `decision`, `alert`,
  `risk_level`, `risk_flags`, `risk_summary`를 포함한다.

Query:

- `recommendation_limit`: default 10, max 100
- `holding_check_limit`: default 20, max 200

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

## 금지 API

v0.1에서는 다음 API를 만들지 않는다.

```text
POST /api/orders
POST /api/trading/auto
POST /api/trading/full-auto
POST /api/broker/place-order
```
