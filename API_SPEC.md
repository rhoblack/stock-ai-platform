# API_SPEC.md

FastAPI 기반 PC 대시보드 API 명세 초안이다.

v0.1 API는 조회 중심이다.  
실거래 주문 API는 구현하지 않는다.

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

## 8. 종목 상세

### GET /api/stocks/{symbol}

종목 기본정보, 최신 가격, 지표, 뉴스, 추천 이력을 조회한다.

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

Query:

- `job_name`
- `status`
- `start_date`
- `end_date`

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
