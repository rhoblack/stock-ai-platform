# DB_SCHEMA.md

> 본 문서는 **v0.8 Phase C 시점** 기준이다 (`v0.7-final` 위에 Alembic baseline
> + auth foundation + watchlist 도입 완료). 누적 31 테이블 (v0.1 17 + v0.4 6 +
> v0.6 2 + v0.7 2 + v0.8 4). 자동매매 / 주문 / 계좌 / 가격 / 수량 컬럼 0건
> 정책 그대로 유지. v0.8 Phase B 가 도입한 `users.password_hash` 는 scrypt
> 해시만 저장 (평문 0건). `login_audit_logs.source_ip_hash` /
> `user_agent_hash` 는 SHA256 해시만 저장 (평문 IP / user agent 0건). v0.8
> Phase C 의 `watchlist_items` 는 broker / account / quantity / order_* /
> source_file_path 컬럼 0건 (favourite 만, 주문 아님 — `WatchlistItem.__table__`
> 컬럼 가드 단언이 회귀 방지).
>
> **v0.8 부터 Alembic 으로 관리한다.** 27 테이블의 baseline revision 은
> `alembic/versions/0001_baseline_v0_7.py`. 이후 모든 ORM 변경은 신규 revision
> 으로 추가한다 (manual ALTER 금지). 운영 DB 절차 / stamp / upgrade / 롤백은
> [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §17 참조. CI 는
> `tests/integration/test_alembic_migration.py` 가 `compare_metadata` diff 0건을
> 강제 — ORM 변경이 revision 없이 머지되면 CI 가 즉시 실패한다.

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

뉴스 / 공시 메타데이터. v0.1 부터 테이블은 존재하지만 v0.5 Phase A 까지 비어
있었으며, v0.5 Phase A 첫 PR 에서 `category` 컬럼 ALTER ADD + `NewsCollector`
로 처음 채워지기 시작한다.

| 컬럼 | 설명 |
|---|---|
| id | 뉴스 ID |
| published_at | 발행 시각 |
| available_at | 시스템 사용 가능 시각 |
| source | 출처 (publisher 이름; collector 가 DTO source 또는 provider 이름으로 채움) |
| title | 제목 (≤ 500자) |
| url | 링크 (최대 1000자, nullable) |
| related_symbols | 관련 종목 (JSON 배열) |
| sentiment | POSITIVE / NEUTRAL / NEGATIVE / UNKNOWN |
| importance | 중요도 |
| theme | 자유 텍스트 테마 라벨 |
| category | **(v0.5 Phase A 신규)** NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER. nullable, indexed. v0.5 Phase B 의 `DisclosureCollector` 가 keyword 분류 (priority RISK > EARNINGS > OWNERSHIP > GOVERNANCE > OTHER) 결과를 본 컬럼에 채운다 — 뉴스 / 공시 모두 동일 테이블에 통합 저장. |
| created_at | 생성일 |

**Unique**: `(source, url)`. **Index**: `published_at` / `source` / `theme` /
`category` / `(published_at, source)`.

**저작권 정책 (v0.5 일관)**: 뉴스 / 공시 본문 paragraph / full_text / raw_html 은
**저장하지 않는다**. `title` (제목, fair-use 한도) 와 `url` (외부 발행처 링크)
만 저장하며, 짧은 운영자 요약은 향후 phase 에서 별도 컬럼으로 추가 검토.
NewsCollector 는 `summary` 길이가 500자를 초과하면 truncate count 로 보고하지만
DTO summary 자체는 v0.5 Phase A 첫 PR 에서 persist 하지 않는다.

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

---

## v0.4 — Analyst & Theme Intelligence (Phase A)

증권사 애널리스트 리포트 (기업 / 산업 / 테마 / 원자재 / 매크로 / 전략) 메타데이터,
리포트에서 추출한 투자 테마, 테마와 종목의 연결 관계, 발견된 시그널 이벤트, 일별
컨센서스 스냅샷, 점수 계산 로그를 저장한다.

**저작권 / 컴플라이언스**: 모든 테이블에 원문 본문 (PDF body / paragraph) 은
저장하지 않는다. `analyst_reports.summary` 는 운영자가 직접 작성한 짧은 요약
(≤ 500자) 이며 `positive_points` / `risk_points` 는 핵심 포인트 bullet 만 허용
(원문 인용 금지). `source_file_path` 는 운영자 로컬 PDF 경로 — **API 응답 / 프런트
/ e2e 어디서도 노출하지 않는다** (마스킹은 Phase D 의 schema 단에서 수행).

### 18. analyst_reports

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | 종목코드 (nullable — THEME / MACRO / COMMODITY 리포트는 null 허용) |
| company_name | 기업명 |
| market | KOSPI / KOSDAQ / US / JP / ... |
| exchange | 거래소 (NYSE / NASDAQ / KRX 등) |
| country | KR / US / JP / ... |
| report_type | COMPANY / SECTOR / INDUSTRY / THEME / COMMODITY / MACRO / STRATEGY |
| broker_name | 발행 증권사 |
| broker_country | 증권사 본사 국가 |
| analyst_name | 애널리스트 이름 |
| published_at | 발행일 (KST) |
| title | 짧은 제목 (≤ 255자, 원문 fair-use 인용 한도) |
| rating | 원문 그대로 (예: "Outperform") |
| normalized_rating | STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL |
| target_price | 목표가 |
| previous_target_price | 이전 목표가 (변경 추적) |
| current_price_at_report | 발행 시점 현재가 |
| currency | KRW / USD / ... |
| summary | 운영자 요약 (≤ 500자, 원문 본문 미저장) |
| positive_points | 긍정 포인트 bullet (text) |
| risk_points | 리스크 bullet (text) |
| source_url | 외부 발행처 URL |
| source_file_path | 운영자 로컬 PDF 경로 — **API 응답 미노출** |
| language | ko / en / ja |
| source_reliability_score | 출처 신뢰도 (0~100) |
| extraction_method | MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED |
| extraction_confidence | 추출 신뢰도 (0~1) |
| duplicate_group_key | 동일 리포트 군 식별자 |
| created_at, updated_at | TimestampMixin |

**Unique**: `(broker_name, published_at, title)`. **Index**: `symbol`, `report_type`, `published_at`, `duplicate_group_key`.

### 19. report_themes

리포트에서 추출한 투자 테마 — 산업 / 테마 / 원자재 / 매크로 리포트의 핵심
주제. 동일 리포트에서 여러 테마가 추출될 수 있다.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| theme_name | 자유 텍스트 (예: "HBM", "구리 공급 부족", "AI 데이터센터") |
| theme_category | SEMICONDUCTOR / AI / COMMODITY / ENERGY / DEFENSE / SHIPBUILDING / BIO / AUTO / BATTERY / POWER_GRID / DATA_CENTER / MACRO / CUSTOM |
| direction | POSITIVE / NEGATIVE / MIXED / NEUTRAL |
| confidence | 0~1 |
| time_horizon | IMMEDIATE / SHORT_TERM / MID_TERM / LONG_TERM / UNKNOWN |
| summary | 테마 요약 (≤ 500자) |
| source_report_id | FK → analyst_reports.id |
| extraction_method | MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED |
| extraction_confidence | 0~1 |
| created_at, updated_at | |

**Unique**: `(source_report_id, theme_name)`. **Index**: `theme_name`, `theme_category`, `direction`, `source_report_id`.

### 20. theme_stock_mappings

테마와 종목의 연결 — 어떤 테마가 어떤 종목에 어떤 방향 / 경로로 영향을 주는지
기록. 글로벌 종목 (US 등) 도 동일 테이블에 저장한다.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| theme_id | FK → report_themes.id |
| symbol | 종목코드 (글로벌 ticker 도 저장) |
| company_name | |
| market, exchange, country | |
| relation_type | PRODUCER / CONSUMER / SUPPLIER / EQUIPMENT / MATERIAL / BENEFICIARY / COST_PRESSURE / COMPETITOR / CUSTOMER / CUSTOM |
| impact_direction | POSITIVE / NEGATIVE / MIXED / NEUTRAL |
| impact_strength | 0~1 |
| impact_path | DEMAND_INCREASE / PRICE_INCREASE / COST_PRESSURE / CAPEX_EXPANSION / SUPPLY_SHORTAGE / POLICY_SUPPORT / EXPORT_GROWTH / MARGIN_IMPROVEMENT / INVENTORY_CYCLE / RATE_FX_IMPACT / CUSTOM |
| benefit_type | DIRECT / INDIRECT / SUPPLY_CHAIN / COST_PASS_THROUGH / SENTIMENT / CUSTOM |
| time_lag | IMMEDIATE / SHORT_TERM / MID_TERM / LONG_TERM / UNKNOWN |
| reason | 자유 텍스트 (≤ 500자) |
| source_sentence_summary | 근거 문장 요약 (≤ 500자, 원문 paragraph 직접 인용 금지) |
| extraction_method, extraction_confidence | |
| created_at, updated_at | |

**Unique**: `(theme_id, symbol)`. **Index**: `symbol`, `impact_direction`, `impact_path`.

### 21. report_signal_events

리포트에서 발견된 중요 변화 시그널 — 목표가 상향, 투자의견 상향, 실적 추정 변화,
공급 부족, 수요 회복, ASP 상승, 원자재 가격 상승, 리스크 경고 등.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| report_id | FK → analyst_reports.id |
| symbol | 영향 종목 (nullable — 매크로 / 테마 시그널은 null 가능) |
| theme_id | FK → report_themes.id (nullable) |
| event_type | RATING_UPGRADE / RATING_DOWNGRADE / TARGET_PRICE_UP / TARGET_PRICE_DOWN / EARNINGS_REVISION_UP / EARNINGS_REVISION_DOWN / SUPPLY_SHORTAGE / DEMAND_RECOVERY / ASP_RISE / INVENTORY_DRAW_DOWN / CAPEX_EXPANSION / POLICY_SUPPORT / COMMODITY_PRICE_RISE / FX_RATE_IMPACT / MARGIN_IMPROVEMENT / MARGIN_PRESSURE / RISK_WARNING / CUSTOM |
| direction | POSITIVE / NEGATIVE / MIXED / NEUTRAL |
| strength | 0~1 |
| time_horizon | IMMEDIATE / SHORT_TERM / MID_TERM / LONG_TERM / UNKNOWN |
| summary | 시그널 요약 (≤ 500자) |
| evidence_json | { "prev_rating": "...", "new_rating": "...", "delta_pct": ... } 등 |
| extraction_method, extraction_confidence | |
| created_at, updated_at | |

**Unique**: `(report_id, event_type, symbol, theme_id)` — NULL 은 distinct (SQLite/PG 기본). **Index**: `symbol`, `event_type`, `direction`, `theme_id`.

### 22. report_consensus_snapshots

기업 리포트 기반 종목별 일별 컨센서스 집계. 활성 윈도우는 발행 후 N일 (기본 90)
이내 리포트만 포함.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | 종목코드 |
| snapshot_date | 집계 기준일 (KST) |
| window_days | 활성 윈도우 (기본 90일) |
| report_count | 활성 리포트 수 |
| avg_target_price, min_target_price, max_target_price | |
| strong_buy_count, buy_count, hold_count, sell_count, strong_sell_count | rating 분포 |
| latest_published_at | 가장 최신 리포트 발행일 |
| created_at | |

**Unique**: `(symbol, snapshot_date, window_days)`. **Index**: `symbol`, `snapshot_date`.

### 23. report_score_logs

`report_score` 와 `theme_signal_score` 계산 이력. `recommendation_runs.run_id` 와
nullable FK 로 연계되어 추천 잡의 cycle 별 evidence 를 추적한다.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | |
| score_date | 계산 기준일 |
| report_score | 0~100 (기업 리포트 기반, report_count=0 시 null) |
| theme_signal_score | 0~100 (테마 + 시그널 기반, 산정 0 시 null) |
| report_count | 활성 기업 리포트 수 |
| theme_count | 활성 테마 매핑 수 |
| signal_event_count | 활성 시그널 이벤트 수 |
| target_upside_pct | (avg_target - latest_close) / latest_close * 100 |
| rating_score_avg | -2 ~ +2 (STRONG_BUY=2, ..., STRONG_SELL=-2 평균) |
| recency_bonus | 0~5 |
| theme_signal_bonus | 0~5 |
| event_signal_bonus | 0~5 |
| risk_penalty | 0~10 (RISK_WARNING 기반) |
| evidence_json | top brokers / top themes / top events / snapshot_id 등 |
| recommendation_run_id | FK → recommendation_runs.run_id (nullable) |
| created_at | |

**Unique**: `(symbol, score_date, recommendation_run_id)`. **Index**: `symbol`, `score_date`, `recommendation_run_id`.

## 24. fundamental_snapshots

v0.6 Phase A PR1 에서 추가한 재무 지표 스냅샷 테이블. 수동 CSV / 향후 DART subset
정규화 결과를 저장하기 위한 기반이며, 이번 PR 에서는 import / provider / scheduler / API 를
추가하지 않는다.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | 종목코드. indexed |
| snapshot_date | 스냅샷 기준일. indexed |
| fiscal_year | 회계연도. indexed |
| fiscal_quarter | 회계분기. nullable. 연간 데이터는 null 허용 |
| revenue | 매출액 |
| operating_income | 영업이익 |
| net_income | 순이익 |
| total_assets | 총자산 |
| total_liabilities | 총부채 |
| total_equity | 총자본 |
| eps | EPS |
| bps | BPS |
| per | PER |
| pbr | PBR |
| roe | ROE |
| debt_ratio | 부채비율 |
| dividend_yield | 배당수익률 |
| revenue_growth_yoy | 전년 대비 매출 성장률 |
| operating_income_growth_yoy | 전년 대비 영업이익 성장률 |
| source | 데이터 출처 태그. 예: MANUAL_CSV |
| created_at, updated_at | 생성 / 갱신 시각 |

**Unique**: `(symbol, snapshot_date, fiscal_year, fiscal_quarter)`. **Index**:
`symbol`, `snapshot_date`, `fiscal_year`.

**저작권 / 보안 정책**: 재무제표 PDF / Excel BLOB, 원문 전문, 본문 paragraph,
body / content / full_text / raw_text / source_file_path 계열 컬럼은 저장하지 않는다.
정규화된 수치 지표와 출처 태그만 저장한다.

**CSV import 정책 (v0.6 Phase A PR2)**: `scripts/import_fundamentals.py` 는 기본
dry-run 이며 `--commit` 을 붙인 경우에만 저장한다. 필수 컬럼은 `symbol`,
`snapshot_date`, `fiscal_year`, `source`; `fiscal_quarter` 와 수치 metric 은 선택값.
동일 unique key 재import 시 값이 같으면 `unchanged`, 값이 다르면 `updated` 로 집계한다.
`source_file_path` / 본문 / BLOB 컬럼은 파일 단위로 거부한다.

> **운영 환경 마이그레이션**: v0.6 Phase A PR1 은 신규 `CREATE TABLE
> fundamental_snapshots ...` 1개만 추가한다. 기존 테이블 destructive 변경 0건.

## 25. earnings_events

v0.6 Phase B 에서 추가한 실적 이벤트 / 어닝 캘린더 기반 테이블. 수동 CSV 로만
적재하며, 이번 Phase 에서는 DART API provider / scheduler / API / frontend 를 추가하지
않는다.

| 컬럼 | 설명 |
|---|---|
| id | 내부 ID |
| symbol | 종목코드. indexed |
| company_name | 회사명. nullable |
| event_date | 실적 이벤트 기준일 / 발표 예정일. indexed |
| fiscal_year | 회계연도 |
| fiscal_quarter | 회계분기. nullable |
| event_type | PRELIMINARY / FINAL / GUIDANCE / CONSENSUS / OTHER |
| revenue_actual, revenue_consensus | 매출 실제 / 컨센서스 |
| operating_income_actual, operating_income_consensus | 영업이익 실제 / 컨센서스 |
| net_income_actual, net_income_consensus | 순이익 실제 / 컨센서스 |
| eps_actual, eps_consensus | EPS 실제 / 컨센서스 |
| surprise_type | BEAT / MEET / MISS / UNKNOWN. indexed |
| surprise_pct | `(actual - consensus) / abs(consensus) * 100` |
| source | 데이터 출처 태그 |
| memo | 운영자 메모. 500자 제한 |
| created_at, updated_at | 생성 / 갱신 시각 |

**Unique**: `(symbol, event_date, fiscal_year, fiscal_quarter, event_type)`.
**Index**: `symbol`, `event_date`, `surprise_type`.

**CSV import 정책 (v0.6 Phase B)**: `scripts/import_earnings.py` 는 기본 dry-run 이며
`--commit` 을 붙인 경우에만 저장한다. `surprise_type` 이 CSV 에 있으면 우선 사용하고,
없으면 `operating_income_actual` / `operating_income_consensus` 로 자동 계산한다.
`surprise_pct >= 5` 는 BEAT, `-5 < surprise_pct < 5` 는 MEET,
`surprise_pct <= -5` 는 MISS, consensus 가 0 또는 NULL 이면 UNKNOWN.

**저작권 / 보안 정책**: 실적 발표 원문 전문, 본문 paragraph, PDF / Excel BLOB,
body / content / full_text / raw_text / html_body / source_file_path 계열 컬럼은 저장하지
않는다. 정규화된 수치 지표, 이벤트 메타데이터, 짧은 memo 만 저장한다.

> **운영 환경 마이그레이션**: v0.6 Phase B 는 신규 `CREATE TABLE earnings_events ...`
> 1개만 추가한다. 기존 테이블 destructive 변경 0건.

> **운영 환경 마이그레이션**: v0.4 Phase A 는 신규 `CREATE TABLE` 6개 — 기존
> 데이터는 손대지 않는다 (destructive 0건). Alembic 미사용 환경은
> `Base.metadata.create_all` 또는 동등한 SQL 6 줄을 한 번 실행하면 된다.

## v0.7 Phase B — Strategy & Backtest Foundation (2 신규 테이블)

## 26. backtest_runs

전략 단위 백테스트 실행 헤더. 각 행은 `BacktestEngine.run()` 한 번에 대응한다.
`scripts/run_backtest.py --commit` 으로만 적재된다 (dry-run 은 0건 저장).

| 컬럼 | 설명 |
|---|---|
| `id` | PK |
| `strategy_name` | 전략 short name (`top_grade` / `high_score` / `multi_signal`). NOT NULL index |
| `strategy_version` | 전략 구현체 `version` 속성 (예: `v1.0.0`). NOT NULL |
| `run_date` | 백테스트 실행일 (UTC). NOT NULL index |
| `start_date` | 평가 대상 RecommendationRun.run_date 하한. nullable |
| `end_date` | 평가 대상 RecommendationRun.run_date 상한. nullable |
| `signal_count` | 평가된 전체 신호 수 (BUY+PASS+AVOID 합). NOT NULL default 0 |
| `buy_count` | BUY 신호 수. NOT NULL default 0 |
| `avoid_count` | AVOID 신호 수. NOT NULL default 0 |
| `pass_count` | PASS 신호 수. NOT NULL default 0 |
| `win_rate_1d` / `_3d` / `_5d` / `_20d` | BUY 신호 중 `close_return > 0` 비율 (Numeric(6,4)). nullable (BUY 0건 또는 horizon 결과 0건이면 NULL) |
| `avg_return_1d` / `_3d` / `_5d` / `_20d` | BUY 신호의 horizon 평균 수익률 (Numeric(12,4)). nullable |
| `max_drawdown` | BUY 신호의 `recommendation_results.max_drawdown` 최솟값 (가장 깊은 excursion). nullable |
| `status` | `DRY_RUN` / `SUCCESS` / `FAILED`. NOT NULL default `DRY_RUN`. dry-run 모드는 저장 자체가 안 되므로 실제 적재 row 는 `SUCCESS` 또는 `FAILED` 만 |
| `error_message` | `FAILED` 일 때 메시지. nullable Text |
| `config_json` | `{ "limit": int|null, "horizons": [1,3,5,20], ... }` JSON. nullable |
| `summary_json` | `{ "missing_result_count_per_horizon": {...}, "notes": "..." }` JSON. nullable |
| `created_at` / `updated_at` | TimestampMixin |

**Index**: `strategy_name`, `run_date`.

**산식 정책**: `win_rate_*` / `avg_return_*` / `max_drawdown` 은 **BUY 신호만**
대상으로 한다. PASS / AVOID 는 `*_count` 에는 포함되지만 수익률 집계에서 제외 —
`summary_json.notes` 에 명시된 `BUY_ONLY_METRICS_NOTE` 가 동일 정책을 응답에 함께
실어준다. horizon 별 `recommendation_results.close_return` 이 NULL 인 BUY 신호는
해당 horizon 의 win_rate / avg_return 계산에서 제외되고
`summary_json.missing_result_count_per_horizon[h]` 에 카운트만 가산된다.

**보안 정책**: broker / 주문 / 계좌 / 가격 / 수량 정보는 어떤 컬럼에도 저장하지
않는다. `BacktestEngine` 자체가 외부 API / Telegram / KIS / DART 호출 0건.

## 27. backtest_results

전략이 평가한 신호 단위 row. 한 신호 = 하나의 Recommendation 매칭 + horizon
수익률 스냅샷.

| 컬럼 | 설명 |
|---|---|
| `id` | PK |
| `backtest_run_id` | FK → `backtest_runs.id` ON DELETE CASCADE. NOT NULL index |
| `symbol` | 종목 코드. NOT NULL index |
| `recommendation_id` | FK → `recommendations.id`. nullable |
| `recommendation_result_id` | FK → `recommendation_results.id`. nullable (5d 기준으로 1건 대표 매칭) |
| `signal_action` | `BUY` / `PASS` / `AVOID`. NOT NULL index |
| `confidence` | StrategySignal 의 [0, 1] confidence (Numeric(5,4)). nullable |
| `reason` | StrategySignal 의 사유 텍스트. nullable Text |
| `grade` | 평가 시점 Recommendation.grade 스냅샷. nullable |
| `total_score` | 평가 시점 Recommendation.total_score 스냅샷. nullable |
| `return_1d` / `_3d` / `_5d` / `_20d` | 매칭된 RecommendationResult.close_return 복사값. nullable Numeric(12,4) |
| `max_drawdown` | 매칭된 RecommendationResult 의 max_drawdown (5d 기준). nullable |
| `result_status` | RecommendationResult.result_status 복사값. nullable |
| `cost_adjusted_return_5d` | **v0.7 Phase C 추가** — `return_5d - CostModel.total_cost * 100`. **BUY 신호만** 채워지고 PASS / AVOID 는 NULL. Numeric(12,4) |
| `regime` | **v0.7 Phase C 추가** — `assign_regime(session, run_date)` 결과. signal 시점에 at-or-before 가장 최근 `MarketRegime.regime`. NULL 일 수 있음 (regime 데이터 미적재 구간). String(32) index |
| `evidence_json` | StrategySignal.evidence 그대로. nullable JSON |
| `created_at` | NOT NULL |

**Unique**: `(backtest_run_id, recommendation_id)` — 한 run 안에서 같은
recommendation 을 두 번 평가하지 않도록 가드. `recommendation_id` 가 NULL 인
경우 (snapshot 없는 신호 — 현재 구현에서는 발생하지 않지만 미래 호환성을 위해
허용) 는 unique 제약에서 제외된다 (SQLite/Postgres NULL semantics).

**Index**: `backtest_run_id`, `symbol`, `signal_action`.

**Cascade**: BacktestRun 삭제 시 결과도 함께 삭제 (`cascade="all, delete-orphan"`).
운영 SQLite 환경은 `PRAGMA foreign_keys = ON` 활성화 필요.

> **운영 환경 마이그레이션**: v0.7 Phase B 는 신규 `CREATE TABLE backtest_runs ...;
> CREATE TABLE backtest_results ...;` 두 줄. 기존 테이블 destructive 변경 0건.
> Alembic 미사용 환경은 `Base.metadata.create_all` 또는 동등한 두 줄 SQL 한 번
> 실행. 누적 ALTER 카운트 = v0.5 1건 + v0.6 2건 + v0.7 2건 = **5건** → v0.8 의
> Alembic 도입 후보 진입 적기.

> **운영 환경 마이그레이션 (v0.7 Phase C)**: Phase C 는 `backtest_results` 에
> `cost_adjusted_return_5d` (Numeric(12,4) nullable) + `regime` (String(32)
> nullable index) **두 컬럼 추가**. Phase B 가 도입한 신규 테이블에 흡수되므로
> Alembic 미사용 환경에서 v0.7 cycle 한 번에 `Base.metadata.create_all()` 만
> 실행하면 정합. 이미 Phase B 시점에 backtest_results 테이블을 생성한 운영 DB
> 가 있다면 다음 두 줄 SQL 만 추가하면 된다 (destructive 0건):
> ```sql
> ALTER TABLE backtest_results ADD COLUMN cost_adjusted_return_5d NUMERIC(12, 4);
> ALTER TABLE backtest_results ADD COLUMN regime VARCHAR(32);
> CREATE INDEX ix_backtest_results_regime ON backtest_results (regime);
> ```

## 28. users (v0.8 Phase B)

단일 admin 사용자 계정. 다중 사용자 / RBAC / OAuth / SSO 는 v0.8 범위 밖
(PLAN-0008 참조). `password_hash` 는 `app.auth.security.PasswordHasher` 가
생성한 scrypt 해시 (`scrypt$<n>$<r>$<p>$<salt_b64>$<derived_b64>`) — **평문
저장 0건**.

| 컬럼 | 설명 |
|---|---|
| id | PK |
| username | unique index, 64자 |
| password_hash | scrypt 해시, 255자 |
| is_active | 비활성화 시 false → 로그인 거부 |
| is_admin | admin 권한 표시 (v0.8 단일 사용자 기준 항상 true) |
| last_login_at | nullable. AuthService.login 성공 시 현재 UTC 갱신 |
| created_at / updated_at | TimestampMixin |

**관계**: `audit_logs` ← LoginAuditLog.user_id (1:N).

**API 응답에 노출되는 필드**: `id`, `username`, `is_admin` 만 (LoginUser
schema). `password_hash` / `last_login_at` 는 절대 응답에 포함되지 않는다.

## 29. login_audit_logs (v0.8 Phase B)

LOGIN_SUCCESS / LOGIN_FAILED / LOGOUT 이벤트 append-only 감사 로그.
`source_ip` 와 `user_agent` 는 라우터 단계에서 `app.auth.security.hash_for_audit`
가 생성한 **SHA256 hex** 만 저장 — 평문 IP / user agent 0건.

| 컬럼 | 설명 |
|---|---|
| id | PK |
| username | nullable index, 64자. LOGIN_FAILED 에서 unknown user 도 기록 |
| user_id | nullable FK → users.id index. unknown user 시 NULL |
| event_type | LOGIN_SUCCESS / LOGIN_FAILED / LOGOUT (index) |
| source_ip_hash | SHA256 hex (64 chars) nullable |
| user_agent_hash | SHA256 hex (64 chars) nullable |
| created_at | NOT NULL index, TimestampMixin 부분 (이 테이블은 immutable, updated_at 부재) |

**복합 인덱스**:
- `ix_login_audit_logs_username_created` (`username`, `created_at`) — 사용자별 조회
- `ix_login_audit_logs_event_created` (`event_type`, `created_at`) — 이벤트별 조회

**삭제 / 갱신 정책**: append-only. retention 정책은 v0.9+ 후보.

> **운영 환경 마이그레이션 (v0.8 Phase B)**: Alembic revision
> `0002_auth_foundation` 이 두 테이블 생성. v0.8 Phase A 의 baseline `0001` 위에
> layering — `alembic upgrade head` 한 번이면 적용. 기존 운영 DB 가 baseline 만
> stamp 된 상태라면 `alembic upgrade head` 가 0002 만 실제 실행 (INTEGRATION_RUNBOOK
> §17.5 절차).

## 30. watchlists (v0.8 Phase C)

사용자별 관심종목 묶음. 한 user 가 여러 watchlist 를 가질 수 있고, 그 중 최대
하나만 `is_default = True` (단일-default invariant 는 `WatchlistRepository` 가
강제 — DB CHECK 가 아닌 application 레벨 보장).

| 컬럼 | 설명 |
|---|---|
| id | PK |
| user_id | FK → users.id, NOT NULL, index |
| name | String(64) NOT NULL — 빈 문자열 금지 (API validator) |
| is_default | Boolean NOT NULL default false — 같은 user 내 단일 default |
| created_at / updated_at | TimestampMixin |

**Unique**: `(user_id, name)` — 같은 user 가 동일 이름 watchlist 둘 만들지 못함.
**Index**: `user_id` (사용자별 조회).

**관계**: `User.watchlists` ← Watchlist (1:N) / `Watchlist.items` ←
WatchlistItem (1:N, ON DELETE CASCADE 는 application + DB 양쪽).

## 31. watchlist_items (v0.8 Phase C)

특정 watchlist 안에 포함된 종목 + 운영자 메모. **broker / account / quantity /
order_price / order_type / side / buy_price / sell_price 컬럼 0건** — Watchlist
는 즐겨찾기지 주문이 아니다 (회귀 단언:
`tests/integration/test_watchlist_repositories.py::test_no_order_or_quantity_columns_on_watchlist_item`).

| 컬럼 | 설명 |
|---|---|
| id | PK |
| watchlist_id | FK → watchlists.id ON DELETE CASCADE, NOT NULL, index |
| symbol | String(32) NOT NULL index — `app.data.repositories.watchlist_items.normalize_symbol` 가 trim + UPPER 보장 |
| memo | String(500) nullable — 500자 이하, API validator + Repository defensive ValueError |
| created_at / updated_at | TimestampMixin |

**Unique**: `(watchlist_id, symbol)` — 같은 watchlist 에 동일 symbol 중복 금지.
**Index**: `watchlist_id`, `symbol`.

**Cascade**: Watchlist 삭제 시 자동 drop (DB FK ON DELETE CASCADE + ORM
`cascade="all, delete-orphan"`). SQLite 는 `PRAGMA foreign_keys=ON` 필요 —
테스트 fixture 가 이를 보장한다.

> **운영 환경 마이그레이션 (v0.8 Phase C)**: Alembic revision `0003_watchlist`
> 가 두 테이블 생성. v0.8 Phase B 의 `0002_auth_foundation` 위에 layering —
> `alembic upgrade head` 한 번이면 적용. 기존 운영 DB 가 baseline + auth 까지
> 적용된 상태라면 `alembic upgrade head` 가 0003 만 실제 실행
> (INTEGRATION_RUNBOOK §17.5 절차). 다운그레이드 (`alembic downgrade -1`) 는
> watchlists / watchlist_items 만 drop, auth 테이블은 보존.
