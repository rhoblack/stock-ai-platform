# DB_SCHEMA.md

v0.1 데이터베이스 스키마 초안이다.

## 1. stocks

종목 기본정보.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| market | KRX/NASDAQ/NYSE |
| symbol | 종목코드 |
| name | 종목명 |
| sector | 업종 |
| theme_tags | 테마 태그 |
| is_active | 분석 대상 여부 |
| created_at | 생성일 |
| updated_at | 수정일 |

## 2. holdings

보유 종목.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | 종목코드 |
| quantity | 수량 |
| avg_buy_price | 평균 매수가 |
| strategy_type | 장기/중기/단기 |
| memo | 메모 |
| is_active | 보유 여부 |
| created_at | 생성일 |
| updated_at | 수정일 |

## 3. daily_prices

일봉 데이터.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| date | 날짜 |
| symbol | 종목코드 |
| open | 시가 |
| high | 고가 |
| low | 저가 |
| close | 종가 |
| volume | 거래량 |
| trading_value | 거래대금 |
| created_at | 생성일 |

유니크 키 권장:

```text
symbol + date
```

## 4. stock_indicators

기술 지표.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| date | 날짜 |
| symbol | 종목코드 |
| ma5 | 5일 이동평균 |
| ma20 | 20일 이동평균 |
| ma60 | 60일 이동평균 |
| ma120 | 120일 이동평균 |
| rsi14 | RSI14 |
| macd | MACD |
| macd_signal | MACD Signal |
| volume_ratio_20d | 20일 평균 대비 거래량 |
| breakout_20d | 20일 고점 돌파 여부 |
| breakout_60d | 60일 고점 돌파 여부 |
| ma_alignment | 정배열/역배열 |
| technical_score | 기술 점수 |

## 5. market_cap_rankings

시가총액 순위.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| rank_date | 기준일 |
| market | KOSPI/KOSDAQ/ALL |
| rank | 순위 |
| symbol | 종목코드 |
| name | 종목명 |
| market_cap | 시가총액 |
| close_price | 종가 |
| listed_shares | 상장주식수 |
| sector | 업종 |
| trading_value | 거래대금 |
| is_analysis_target | 분석 대상 여부 |

## 6. stock_universes

분석 유니버스.

| 컬럼 | 설명 |
|---|---|
| universe_id | 유니버스 ID |
| name | 이름 |
| description | 설명 |
| is_active | 사용 여부 |
| created_at | 생성일 |

예:

```text
MARKET_CAP_TOP_500
KOSPI_TOP_300
KOSDAQ_TOP_200
WATCHLIST
HOLDINGS
```

## 7. stock_universe_members

유니버스 구성 종목.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| universe_id | 유니버스 ID |
| symbol | 종목코드 |
| added_at | 편입일 |
| removed_at | 제외일 |
| reason | 편입/제외 이유 |

## 8. news_items

뉴스 데이터.

| 컬럼 | 설명 |
|---|---|
| id | 뉴스 ID |
| published_at | 발행 시각 |
| available_at | 시스템 사용 가능 시각 |
| source | 출처 |
| title | 제목 |
| url | 링크 |
| related_symbols | 관련 종목 |
| sentiment | 긍정/중립/부정 |
| importance | 중요도 |
| theme | 테마 |
| created_at | 생성일 |

뉴스 원문 전체 저장은 주의한다.

## 9. market_regimes

시장 국면.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| date | 날짜 |
| market | KOSPI/KOSDAQ/NASDAQ |
| regime | 상승/횡보/하락/테마/급락 |
| market_score | 시장 점수 |
| risk_level | LOW/MEDIUM/HIGH |
| reason | 판단 근거 |
| created_at | 생성일 |

## 10. recommendation_runs

추천 실행 단위.

| 컬럼 | 설명 |
|---|---|
| run_id | 실행 ID |
| run_date | 추천 날짜 |
| started_at | 시작 시각 |
| finished_at | 종료 시각 |
| market_summary | 시장 요약 JSON |
| status | 성공/실패 |
| telegram_sent | 발송 여부 |

## 11. recommendations

추천 종목.

| 컬럼 | 설명 |
|---|---|
| id | 추천 ID |
| run_id | 실행 ID |
| rank | 순위 |
| market | 시장 |
| symbol | 종목코드 |
| name | 종목명 |
| grade | S/A/B/C/D |
| total_score | 종합 점수 |
| technical_score | 기술 점수 |
| news_score | 뉴스 점수 |
| supply_score | 수급 점수 |
| fundamental_score | 실적/재무 점수 |
| ai_score | AI 점수 |
| risk_score | 리스크 점수 |
| reason | 추천 사유 |
| risk_note | 리스크 설명 |
| watch_condition | 관찰 조건 |
| invalid_condition | 제외 조건 |
| snapshot_id | 데이터 스냅샷 ID |

## 12. recommendation_results

추천 후 성과.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| recommendation_id | 추천 ID |
| result_date | 검증 날짜 |
| days_after | 1/3/5/20 |
| open_return | 시가 기준 수익률 |
| high_return | 고가 기준 수익률 |
| low_return | 저가 기준 하락률 |
| close_return | 종가 기준 수익률 |
| max_drawdown | 최대 하락률 |
| result_status | 성공/실패/보류 |

## 13. holding_checks

보유 종목 점검.

| 컬럼 | 설명 |
|---|---|
| id | 점검 ID |
| check_date | 점검 날짜 |
| check_type | PRE_MARKET/POST_MARKET |
| symbol | 종목코드 |
| current_price | 현재가 |
| avg_buy_price | 평균단가 |
| return_rate | 수익률 |
| technical_score | 기술 점수 |
| news_score | 뉴스 점수 |
| earnings_score | 실적 점수 |
| ai_score | AI 점수 |
| risk_score | 리스크 점수 |
| total_score | 종합 점수 |
| grade | 등급 |
| decision | 판단 |
| reason | 근거 |
| alert | 경고 여부 |
| snapshot_id | 스냅샷 ID |

## 14. data_snapshots

판단 당시 데이터 스냅샷.

| 컬럼 | 설명 |
|---|---|
| snapshot_id | 스냅샷 ID |
| snapshot_time | 생성 시각 |
| symbol | 종목코드 |
| snapshot_type | RECOMMENDATION/HOLDING_CHECK |
| price_data_json | 가격 데이터 |
| indicator_data_json | 지표 데이터 |
| news_data_json | 뉴스 데이터 |
| market_context_json | 시장 상황 |
| created_at | 생성일 |

## 15. decision_logs

판단 로그.

| 컬럼 | 설명 |
|---|---|
| decision_id | 판단 ID |
| decision_type | RECOMMENDATION/HOLDING/RISK |
| symbol | 종목코드 |
| input_snapshot_id | 입력 스냅샷 |
| rule_result_json | 룰 결과 |
| ai_result_json | AI 결과 |
| risk_result_json | 리스크 결과 |
| final_decision | 최종 판단 |
| reason | 판단 근거 |
| created_at | 생성일 |

## 16. job_runs

스케줄러 작업 로그.

| 컬럼 | 설명 |
|---|---|
| job_id | 작업 ID |
| job_name | 작업명 |
| started_at | 시작 |
| finished_at | 종료 |
| status | SUCCESS/FAILED/PARTIAL |
| error_message | 오류 |
| result_summary | 결과 요약 |

## 17. notification_logs

텔레그램 등 알림 발송 로그.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| channel | TELEGRAM |
| message_type | REPORT/ALERT |
| target | 수신 대상 |
| sent_at | 발송 시각 |
| status | 성공/실패 |
| error_message | 오류 |
| related_job_id | 관련 job |
