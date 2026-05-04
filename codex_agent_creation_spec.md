# Codex 코딩 에이전트 생성 명세서

프로젝트명: **한국투자증권 API 기반 AI 주식 분석·추천·보유점검 플랫폼**

문서 목적:  
이 문서는 Codex 또는 로컬 개발 에이전트 시스템이 본 프로젝트를 안정적으로 구현할 수 있도록, **코딩 에이전트의 역할, 책임, 작업 범위, 금지사항, 산출물, 프롬프트 템플릿, 개발 순서**를 정의한다.

본 문서는 `stock_ai_project_codex_brief.md`, `stock_ai_detailed_spec.md`와 함께 사용한다.

---

## 1. 프로젝트 목표 요약

### v0.1 목표

v0.1은 실거래 자동매매가 아니라, **한국 주식 중심 AI 점검/추천 리포트 시스템**이다.

v0.1에 포함할 기능:

1. 한국투자증권 API 기반 데이터 수집
2. 시가총액 TOP 500 종목 관리
3. 관심종목/보유종목 관리
4. 기술적 지표 계산
5. 보유 종목 장전/장후 점검
6. 신규 추천 종목 TOP 5 리포트
7. 추천 이력 저장
8. 추천 후 성과 검증 기초
9. 텔레그램 알림
10. PC 대시보드용 백엔드 API
11. 데이터 스냅샷 및 판단 로그 저장
12. 테스트 가능한 구조

v0.1에서 제외할 기능:

1. 실거래 자동매매
2. 주문 API 실제 실행
3. 가상 증권사 서버
4. 전략 자동 튜닝
5. 전용 AI 모델 학습
6. 대량 가상 데이터 생성
7. 완전한 백테스트 시스템
8. FULL_AUTO 모드

---

## 2. 핵심 개발 원칙

모든 에이전트는 아래 원칙을 반드시 지켜야 한다.

### 2.1 계층 분리 원칙

```text
Data 모듈은 판단하지 않는다.
Analysis 모듈은 주문하지 않는다.
AI 모듈은 직접 매매하지 않는다.
Recommendation/Holding 모듈은 외부 API를 직접 호출하지 않는다.
RiskEngine은 모든 실행 판단의 최종 게이트다.
BrokerInterface 없이 주문 기능을 구현하지 않는다.
```

### 2.2 v0.1 안전 원칙

```text
v0.1에서는 실거래 주문 기능을 구현하지 않는다.
주문 API는 인터페이스 또는 placeholder만 둔다.
AI 판단은 설명과 근거 생성에만 사용한다.
추천과 보유 판단은 반드시 data_snapshots와 decision_logs에 기록한다.
API 키, 계좌번호, 토큰은 코드와 로그에 노출하지 않는다.
```

### 2.3 개발 방식 원칙

```text
작업 단위는 작게 나눈다.
한 에이전트가 다른 에이전트의 영역을 임의로 수정하지 않는다.
핵심 로직에는 테스트를 함께 작성한다.
문서와 코드가 불일치하면 문서를 갱신한다.
외부 API 호출은 테스트에서 mock 처리한다.
```

---

## 3. v0.1 핵심 코딩 에이전트 목록

v0.1에서는 아래 8개 에이전트를 중심으로 개발한다.

```text
1. PM / Architect Agent
2. DB / Repository Agent
3. KIS & Data Agent
4. Analysis & Scoring Agent
5. Recommendation & Holding Agent
6. Notification & Report Agent
7. Backend API Agent
8. Test / Review / Docs Agent
```

향후 확장 시 추가할 에이전트:

```text
9. Dashboard Frontend Agent
10. Strategy Agent
11. Backtest Agent
12. Simulation Agent
13. AI/LLM Agent
14. DevOps Agent
15. Security Agent
16. Auto Trading Agent
```

---

# Part A. v0.1 핵심 에이전트 명세

---

## 4. PM / Architect Agent

### 4.1 역할

프로젝트 전체 구조와 개발 범위를 관리하는 총괄 에이전트다.

### 4.2 책임

- v0.1 범위 고정
- 프로젝트 폴더 구조 설계
- 계층 간 의존성 방향 정의
- 핵심 인터페이스 정의
- 에이전트별 작업 분해
- 기능 과확장 방지
- 코드 구조 리뷰 기준 수립
- 각 에이전트 산출물의 통합 방향 결정

### 4.3 담당 산출물

```text
README.md
ARCHITECTURE.md
app/ 기본 폴더 구조
핵심 interface 파일
개발 태스크 목록
v0.1 범위 정의 문서
```

### 4.4 담당 파일 예시

```text
app/
├─ main.py
├─ config/
├─ data/
├─ analysis/
├─ decision/
├─ ai/
├─ notification/
├─ api/
├─ db/
├─ scheduler/
├─ broker/
└─ tests/
```

### 4.5 해야 할 일

- 모듈 경계를 명확히 정의한다.
- `DataProviderInterface`, `AIProviderInterface`, `BrokerInterface`, `StrategyInterface`의 기본 틀을 만든다.
- v0.1에서 구현하지 않을 기능은 placeholder 또는 문서로만 남긴다.
- 자동매매 관련 실거래 코드는 비활성 상태로 유지한다.

### 4.6 하면 안 되는 일

- KIS API 세부 구현
- 기술적 지표 계산 세부 구현
- 텔레그램 메시지 포맷 세부 구현
- 실거래 주문 기능 구현
- v0.1 범위 외 기능 추가

### 4.7 Codex 프롬프트 템플릿

```text
너는 PM / Architect Agent다.

목표:
한국투자증권 API 기반 AI 주식 분석/추천/보유점검 플랫폼의 v0.1 구조를 설계한다.

반드시 지켜야 할 원칙:
1. v0.1에서는 실거래 자동매매를 구현하지 않는다.
2. Data, Analysis, Decision, Notification, API, DB 계층을 분리한다.
3. 향후 확장을 위해 BrokerInterface, AIProviderInterface, DataProviderInterface, StrategyInterface를 준비한다.
4. 각 계층은 자신의 책임만 가진다.

작업:
- 프로젝트 폴더 구조를 생성하라.
- 핵심 인터페이스 파일을 작성하라.
- README 또는 ARCHITECTURE 문서를 갱신하라.
- v0.1 구현 범위와 제외 범위를 명확히 기록하라.
```

---

## 5. DB / Repository Agent

### 5.1 역할

데이터베이스 모델, ORM, Repository, 마이그레이션을 담당한다.

### 5.2 책임

- SQLAlchemy ORM 모델 작성
- DB 테이블 관계 설계
- 날짜/종목코드 기반 인덱스 설계
- upsert 로직 설계
- Repository 계층 구현
- `data_snapshots`, `decision_logs`, `job_runs` 설계
- DB 조회/저장 테스트 작성

### 5.3 v0.1 필수 테이블

```text
stocks
holdings
daily_prices
stock_indicators
market_cap_rankings
stock_universes
stock_universe_members
news_items
market_regimes
recommendation_runs
recommendations
recommendation_results
holding_checks
data_snapshots
decision_logs
job_runs
notification_logs
```

### 5.4 해야 할 일

- 모든 테이블에 `created_at`, `updated_at`을 가능한 한 포함한다.
- `symbol`, `date`, `run_id`, `snapshot_id`에 필요한 인덱스를 추가한다.
- 추천과 보유 점검은 `data_snapshots`와 연결 가능해야 한다.
- 판단 근거는 `decision_logs`에 저장 가능해야 한다.
- 외부 API 응답 원문 전체 저장은 최소화하고, 필요한 정규화 데이터와 스냅샷을 저장한다.

### 5.5 하면 안 되는 일

- KIS API 직접 호출
- 추천 판단 로직 구현
- 텔레그램 발송
- 기술적 지표 계산
- 실거래 주문 처리

### 5.6 Repository 예시

```text
StockRepository
PriceRepository
IndicatorRepository
NewsRepository
RecommendationRepository
HoldingRepository
SnapshotRepository
DecisionLogRepository
JobRunRepository
```

### 5.7 Codex 프롬프트 템플릿

```text
너는 DB / Repository Agent다.

목표:
v0.1 필수 테이블을 SQLAlchemy ORM 모델과 Repository 계층으로 구현한다.

작업:
1. stocks, holdings, daily_prices, stock_indicators, market_cap_rankings, news_items, market_regimes,
   recommendation_runs, recommendations, recommendation_results, holding_checks,
   data_snapshots, decision_logs, job_runs, notification_logs 모델을 작성하라.
2. symbol/date 기반 조회를 위한 인덱스를 추가하라.
3. Repository 패턴으로 조회/저장/upsert 메서드를 작성하라.
4. 추천과 보유 점검 데이터는 data_snapshots와 연결될 수 있게 설계하라.
5. pytest 기반 기본 저장/조회 테스트를 작성하라.

금지:
- 외부 API 호출 코드를 작성하지 마라.
- 추천 판단이나 점수 계산 로직을 작성하지 마라.
```

---

## 6. KIS & Data Agent

### 6.1 역할

한국투자증권 API 연동과 외부 데이터 수집/정제를 담당한다.

### 6.2 책임

- KIS API 클라이언트 작성
- 인증 토큰 발급/갱신
- 국내주식 현재가 조회
- 국내주식 일봉 조회
- 시가총액 상위 종목 조회
- 잔고 조회 또는 수동 보유종목 입력 지원
- 뉴스 수집 기초 구조
- 데이터 정규화
- DB 저장 서비스
- 데이터 품질 검사
- API 실패 재시도 처리

### 6.3 담당 모듈

```text
app/data/collectors/kis_collector.py
app/data/collectors/news_collector.py
app/data/normalizers/
app/data/validators/
app/data/services/
```

### 6.4 해야 할 일

- API 키와 토큰은 `.env` 또는 안전한 설정에서 읽는다.
- 로그에 API 키, 계좌번호, 토큰을 출력하지 않는다.
- 외부 API 응답을 내부 표준 DTO로 변환한다.
- 일봉 데이터는 `daily_prices`에 저장한다.
- 시총 TOP 500은 `market_cap_rankings`와 universe 테이블에 저장한다.
- 데이터 누락/중복/이상치를 검사한다.
- 실패 시 재시도와 부분 실패 처리를 구현한다.

### 6.5 하면 안 되는 일

- 추천 종목 선정
- 매수/매도 판단
- 실거래 주문 API 구현
- 텔레그램 발송
- 기술 점수 계산

### 6.6 데이터 품질 체크 항목

```text
가격 누락
거래량 0
중복 일봉
비정상 급등락
뉴스 중복
뉴스 발행시간 누락
API 응답 실패
분석 대상 종목 누락
```

### 6.7 Codex 프롬프트 템플릿

```text
너는 KIS & Data Agent다.

목표:
한국투자증권 API와 외부 데이터 수집 구조를 구현한다.

작업:
1. KisClient를 작성하라.
2. 인증 토큰 발급/갱신 구조를 만들라.
3. 국내주식 현재가, 일봉, 시가총액 상위 종목 조회 메서드를 작성하라.
4. 조회 결과를 내부 DTO로 정규화하라.
5. Collector Service를 만들어 daily_prices, market_cap_rankings, stock_universes에 저장하라.
6. DataQualityChecker를 작성하라.
7. 외부 API 호출 테스트는 mock으로 작성하라.

금지:
- v0.1에서 주문 API를 구현하지 마라.
- 추천 판단이나 점수 계산을 하지 마라.
- API 키와 토큰을 로그에 남기지 마라.
```

---

## 7. Analysis & Scoring Agent

### 7.1 역할

기술적 분석, 시장 점수, 종목 점수 산식을 담당한다.

### 7.2 책임

- 이동평균 계산
- RSI 계산
- MACD 계산
- 거래량 비율 계산
- 돌파 여부 계산
- 기술 점수 계산
- 신규 추천 점수 산식 구현
- 보유 종목 점수 산식 구현
- 리스크 감점 기본 구조 구현

### 7.3 담당 모듈

```text
app/analysis/technical_analyzer.py
app/analysis/volume_analyzer.py
app/analysis/market_regime_analyzer.py
app/decision/scoring_engine.py
```

### 7.4 기술 지표

```text
MA5
MA20
MA60
MA120
RSI14
MACD
volume_ratio_20d
breakout_20d
breakout_60d
ma_alignment
technical_score
```

### 7.5 신규 추천 점수 공식 v0.1

```text
total_score =
technical_score * 0.35
+ news_score * 0.25
+ supply_score * 0.15
+ fundamental_score * 0.15
+ ai_score * 0.10
- risk_penalty
```

### 7.6 보유 종목 점수 공식 v0.1

```text
holding_score =
technical_score * 0.35
+ news_score * 0.20
+ earnings_score * 0.20
+ ai_score * 0.15
+ profit_management_score * 0.10
- risk_penalty
```

### 7.7 해야 할 일

- 계산 결과는 `stock_indicators`에 저장 가능해야 한다.
- 점수 계산 함수는 순수 함수에 가깝게 작성한다.
- 단위 테스트를 반드시 작성한다.
- 지표 계산은 외부 API에 의존하지 않는다.
- 분석 결과는 추천 판단의 입력으로만 사용한다.

### 7.8 하면 안 되는 일

- 외부 API 직접 호출
- 텔레그램 발송
- 추천 결과 저장
- 보유 종목 판단 문구 생성
- 주문 실행

### 7.9 Codex 프롬프트 템플릿

```text
너는 Analysis & Scoring Agent다.

목표:
주가 일봉 데이터를 기반으로 기술적 지표와 점수 계산 엔진을 구현한다.

작업:
1. MA5, MA20, MA60, MA120을 계산하라.
2. RSI14와 MACD를 계산하라.
3. volume_ratio_20d, breakout_20d, breakout_60d, ma_alignment를 계산하라.
4. stock_indicators 저장용 결과 DTO를 작성하라.
5. 신규 추천 점수와 보유 종목 점수 계산 함수를 작성하라.
6. pytest로 지표 계산과 점수 계산 테스트를 작성하라.

금지:
- 추천 종목을 직접 선정하지 마라.
- API 수집 코드를 작성하지 마라.
- 주문 또는 알림 코드를 작성하지 마라.
```

---

## 8. Recommendation & Holding Agent

### 8.1 역할

신규 추천 종목 생성과 보유 종목 장전/장후 점검을 담당한다.

### 8.2 책임

- 시총 TOP 500 기반 추천 후보 필터링
- 신규 추천 TOP 5 생성
- 추천 실행 기록 저장
- 추천 당시 data snapshot 저장
- 추천 판단 decision log 저장
- 보유 종목 수익률 계산
- 보유 종목 장전/장후 점검
- 보유 판단 결과 생성
- 위험 경고 조건 생성
- 추천 성과 검증 기초

### 8.3 담당 모듈

```text
app/decision/recommendation_engine.py
app/decision/holding_check_engine.py
app/decision/risk_engine.py
app/decision/decision_logger.py
```

### 8.4 신규 추천 처리 흐름

```text
시총 TOP 500
→ 거래대금/유동성 필터
→ 위험 종목 제외
→ 기술/뉴스/수급/실적/AI 점수 계산
→ 후보 30개 압축
→ TOP 5 추천 생성
→ recommendation_runs 저장
→ recommendations 저장
→ data_snapshots 저장
→ decision_logs 저장
```

### 8.5 보유 종목 점검 흐름

```text
holdings 조회
→ 현재가/기술지표/뉴스 점수 조회
→ 수익률 계산
→ 보유 점수 계산
→ 판단 생성
→ 위험 경고 조건 확인
→ holding_checks 저장
→ data_snapshots 저장
→ decision_logs 저장
```

### 8.6 보유 판단 결과

```text
강한 보유
보유 유지
관찰 필요
비중 축소 검토
매도 검토
신규 매수 금지
```

### 8.7 위험 경고 조건 v0.1

```text
전회차 대비 점수 15점 이상 하락
20일선 이탈
손절 기준 접근
악재 뉴스 발생
시장 급락장 전환
```

### 8.8 해야 할 일

- 외부 API 직접 호출 없이 Repository를 통해 데이터 조회
- 추천 및 보유 판단 결과 저장
- snapshot과 decision log를 반드시 생성
- AI 판단은 선택적으로 사용하되 없어도 동작
- 리스크 감점과 경고를 명확히 표시

### 8.9 하면 안 되는 일

- KIS API 직접 호출
- 텔레그램 직접 발송
- 기술 지표 직접 재계산
- 실거래 주문 실행
- AI 판단만으로 최종 결론 내리기

### 8.10 Codex 프롬프트 템플릿

```text
너는 Recommendation & Holding Agent다.

목표:
신규 추천 종목 생성과 보유 종목 장전/장후 점검 서비스를 구현한다.

작업:
1. RecommendationEngine을 작성하라.
2. 시총 TOP 500 유니버스에서 필터링 후 추천 TOP 5를 생성하라.
3. recommendation_runs, recommendations, data_snapshots, decision_logs에 저장하라.
4. HoldingCheckEngine을 작성하라.
5. holdings의 종목별 수익률, 점수, 판단 결과를 계산하여 holding_checks에 저장하라.
6. 점수 급락, 20일선 이탈 등 위험 경고를 생성하라.
7. 테스트를 작성하라.

금지:
- KIS API를 직접 호출하지 마라.
- 텔레그램을 직접 발송하지 마라.
- 실거래 주문 기능을 구현하지 마라.
```

---

## 9. Notification & Report Agent

### 9.1 역할

텔레그램 알림과 리포트 생성을 담당한다.

### 9.2 책임

- 아침 6시 신규 추천 리포트 생성
- 장전 보유 종목 점검 리포트 생성
- 장후 보유 종목 점검 리포트 생성
- 위험 경고 메시지 생성
- Telegram Bot API 발송
- 발송 결과 저장
- 발송 실패 재시도
- 메시지 길이 관리

### 9.3 담당 모듈

```text
app/notification/report_generator.py
app/notification/telegram_notifier.py
app/notification/message_formatters.py
```

### 9.4 텔레그램 리포트 종류

```text
06:00 신규 추천 리포트
08:30 장전 보유 점검
16:30 장후 보유 점검
조건 발생 시 위험 경고
```

### 9.5 메시지 원칙

- 텔레그램은 요약 중심
- PC 대시보드는 상세 중심
- 메시지는 너무 길지 않게 구성
- 핵심 점수, 판단, 리스크, 확인 조건만 표시
- 실패 시 job_runs 또는 notification_logs에 기록

### 9.6 해야 할 일

- 메시지 포맷터를 기능별로 분리한다.
- TelegramNotifier는 메시지 발송만 담당한다.
- 리포트 데이터는 DB 또는 서비스 결과에서 받는다.
- 토큰과 chat_id는 `.env`에서 읽는다.
- 전송 실패 시 재시도한다.

### 9.7 하면 안 되는 일

- 추천 판단 변경
- 점수 계산
- KIS API 호출
- 보유 점검 생성
- 실거래 주문

### 9.8 Codex 프롬프트 템플릿

```text
너는 Notification & Report Agent다.

목표:
추천 리포트, 장전/장후 보유 점검, 위험 경고 메시지를 생성하고 텔레그램으로 발송하는 기능을 구현한다.

작업:
1. ReportGenerator를 작성하라.
2. 추천 리포트, 장전 점검, 장후 점검, 위험 경고 메시지 포맷터를 분리하라.
3. TelegramNotifier를 작성하라.
4. 토큰과 chat_id는 .env에서 읽게 하라.
5. 발송 결과를 notification_logs 또는 job_runs에 저장하라.
6. 메시지 포맷 테스트를 작성하라.

금지:
- 추천 로직과 점수 계산을 수정하지 마라.
- 외부 주식 API를 호출하지 마라.
```

---

## 10. Backend API Agent

### 10.1 역할

PC 대시보드가 사용할 FastAPI 백엔드 API를 담당한다.

### 10.2 책임

- FastAPI 라우터 작성
- Pydantic schema 작성
- 대시보드 조회 API 구현
- 필터/정렬/페이지네이션 기초 구현
- 시스템 로그 조회 API
- 설정 조회 API
- API 응답 테스트

### 10.3 v0.1 API 목록

```text
GET /api/reports/today
GET /api/recommendations/latest
GET /api/recommendations/history
GET /api/recommendations/{run_id}
GET /api/holdings
GET /api/holdings/checks/latest
GET /api/holdings/{symbol}/checks
GET /api/stocks/{symbol}
GET /api/universe/market-cap-top
GET /api/market-regime/latest
GET /api/news
GET /api/jobs
GET /api/settings
```

### 10.4 해야 할 일

- API는 Repository 또는 Service를 통해서만 데이터 조회
- API 내부에서 지표 계산이나 추천 생성 금지
- Pydantic response schema 사용
- 오류 응답 형식 통일
- 대시보드가 사용할 수 있도록 JSON 구조 안정화

### 10.5 하면 안 되는 일

- 데이터 수집 실행
- 추천 판단 실행
- 기술 지표 계산
- 텔레그램 발송
- 주문 실행

### 10.6 Codex 프롬프트 템플릿

```text
너는 Backend API Agent다.

목표:
PC 대시보드용 FastAPI API를 구현한다.

작업:
1. v0.1 API 라우터를 작성하라.
2. Pydantic request/response schema를 작성하라.
3. 오늘의 리포트, 추천 종목, 추천 이력, 보유 종목 점검, 종목 상세, 시총 TOP 500, 시장 국면, 시스템 로그 조회 API를 구현하라.
4. Repository를 통해서만 DB를 조회하라.
5. API 테스트를 작성하라.

금지:
- API 라우터 안에서 데이터 수집, 지표 계산, 추천 실행을 하지 마라.
- 주문 관련 API를 구현하지 마라.
```

---

## 11. Test / Review / Docs Agent

### 11.1 역할

테스트, 코드 리뷰, 문서화를 담당한다.

### 11.2 책임

- pytest 테스트 작성
- 외부 API mock 테스트
- 핵심 모듈 단위 테스트
- 통합 테스트 기초
- 코드 구조 리뷰
- 보안 리뷰
- v0.1 범위 위반 검사
- README 갱신
- `.env.example` 작성
- 실행 방법 문서화

### 11.3 테스트 대상

```text
DB 모델 저장/조회
Repository upsert
KIS Client mock
DataQualityChecker
TechnicalAnalyzer
ScoringEngine
RecommendationEngine
HoldingCheckEngine
ReportGenerator
Telegram 메시지 포맷
Backend API
```

### 11.4 코드 리뷰 체크리스트

```text
Data 모듈이 판단 로직을 포함하지 않는가?
Analysis 모듈이 외부 API를 직접 호출하지 않는가?
Recommendation 모듈이 KIS API를 직접 호출하지 않는가?
AI 모듈이 주문 기능을 갖지 않는가?
v0.1에 주문 API가 구현되지 않았는가?
API 키/토큰이 로그에 노출되지 않는가?
snapshot과 decision log가 저장되는가?
테스트가 핵심 로직을 커버하는가?
```

### 11.5 해야 할 일

- 각 핵심 모듈 완료 후 테스트를 작성한다.
- 구조 위반을 발견하면 수정 제안을 남긴다.
- README와 개발 문서를 계속 갱신한다.
- 자동매매 관련 코드가 v0.1에 들어오지 않도록 검사한다.

### 11.6 하면 안 되는 일

- 핵심 기능을 임의로 변경
- 에이전트 경계를 무시하고 대량 수정
- 실제 API 키를 테스트에 사용
- 실거래 주문 기능 추가

### 11.7 Codex 프롬프트 템플릿

```text
너는 Test / Review / Docs Agent다.

목표:
현재 코드의 테스트, 구조 리뷰, 문서화를 수행한다.

작업:
1. pytest 기반 테스트를 작성하라.
2. 외부 API 호출은 mock 처리하라.
3. TechnicalAnalyzer, ScoringEngine, RecommendationEngine, HoldingCheckEngine, ReportGenerator 테스트를 작성하라.
4. 코드 구조가 계층 분리 원칙을 지키는지 리뷰하라.
5. README.md, .env.example, 실행 방법 문서를 갱신하라.
6. v0.1 범위를 벗어난 자동매매/주문 코드가 있는지 검사하라.

금지:
- 실거래 주문 기능을 추가하지 마라.
- API 키를 코드나 테스트에 넣지 마라.
```

---

# Part B. 향후 확장 에이전트 명세

---

## 12. Dashboard Frontend Agent

### 역할

React 또는 Next.js 기반 PC 대시보드를 담당한다.

### 투입 시점

Backend API가 안정화된 후 투입한다.

### 주요 화면

```text
오늘의 리포트
보유 종목 점검
추천 종목
추천 이력
종목 상세
시가총액 TOP 500
시장 국면
뉴스/공시
시스템 로그
설정
```

### 프롬프트 템플릿

```text
너는 Dashboard Frontend Agent다.
FastAPI 백엔드 API를 사용하는 PC 대시보드를 구현한다.
v0.1 화면은 오늘의 리포트, 보유 종목 점검, 추천 종목, 추천 이력, 종목 상세, 시총 TOP 500, 시스템 로그다.
카드형 요약, 정렬 가능한 테이블, 종목 상세 차트 영역을 포함하라.
```

---

## 13. Strategy Agent

### 역할

장기/중기/단기 전략 관리와 매매 신호 생성을 담당한다.

### 투입 시점

v0.2 이후.

### 책임

```text
전략 템플릿 관리
전략별 조건 관리
SIGNAL/PAPER 모드 관리
시장 국면별 전략 ON/OFF
trade_signals 생성
```

### 금지

v0.2에서도 실거래 주문 실행은 금지.

---

## 14. Backtest Agent

### 역할

과거 데이터 기반 전략 검증을 담당한다.

### 투입 시점

v0.2 또는 v0.3.

### 책임

```text
과거 데이터 백테스트
수수료/세금/슬리피지 반영
성과 지표 계산
시장 국면별 성과 분석
전략 버전 비교
```

---

## 15. Simulation Agent

### 역할

가상 차트, 가상 뉴스, 가상 증권사 서버 테스트를 담당한다.

### 투입 시점

v0.4 이후.

### 책임

```text
MockBroker
ReplayBroker
SimulationBroker
Synthetic Market Generator
Synthetic News Generator
Virtual Account
Virtual Order Matching
```

---

## 16. AI/LLM Agent

### 역할

로컬 LLM, 클라우드 LLM, 전용 AI 모델 연동을 강화한다.

### 투입 시점

v0.1에서는 DummyProvider만 사용 가능. 실제 강화는 v0.2 이후.

### 책임

```text
AIProviderInterface 구현
LocalLLMProvider
CloudLLMProvider
뉴스 요약
추천 근거 생성
리스크 설명
리포트 문장 생성
```

### 금지

AI가 직접 주문하거나 RiskEngine을 우회하면 안 된다.

---

## 17. DevOps Agent

### 역할

실행 환경, Docker, 스케줄러, 백업을 담당한다.

### 책임

```text
docker-compose.yml
PostgreSQL 컨테이너
backend 실행
dashboard 실행
.env.example
로그 폴더
DB 백업 스크립트
스케줄러 실행 설정
```

---

## 18. Security Agent

### 역할

실거래 API 연동 전 보안 검증을 담당한다.

### 투입 시점

v0.5~v1.0.

### 책임

```text
API 키 보안
토큰 마스킹
계좌정보 보호
실거래 모드 잠금
비상정지 기능 검증
로그 보안 검증
```

---

## 19. Auto Trading Agent

### 역할

소액 자동매매 기능을 담당한다.

### 투입 시점

v1.0 이후.

### 책임

```text
APPROVAL 모드
SMALL_AUTO 모드
한국투자증권 주문 API
주문 전 RiskEngine 검증
주문 로그 저장
비상정지
일일 손실 제한
```

### 금지

FULL_AUTO 기본 활성화 금지.

---

# Part C. 에이전트 운용 방법

---

## 20. 권장 개발 순서

```text
1. PM / Architect Agent
2. DB / Repository Agent
3. DevOps 최소 환경
4. KIS & Data Agent
5. Analysis & Scoring Agent
6. Recommendation & Holding Agent
7. Notification & Report Agent
8. Backend API Agent
9. Test / Review / Docs Agent
10. Dashboard Frontend Agent
```

---

## 21. 작업 단위 원칙

좋은 작업 요청:

```text
stocks, daily_prices, holdings ORM 모델과 Repository만 작성하라.
```

나쁜 작업 요청:

```text
전체 시스템을 모두 구현하라.
```

Codex 작업은 가능한 한 작게 나누어야 한다.

---

## 22. 에이전트 호출 예시

### 예시 1: DB 작업

```text
너는 DB / Repository Agent다.
v0.1 필수 테이블 중 stocks, daily_prices, holdings, stock_indicators 모델만 먼저 작성하라.
SQLAlchemy 2.0 스타일로 작성하고, symbol/date 인덱스를 추가하라.
테스트도 함께 작성하라.
```

### 예시 2: 기술 분석 작업

```text
너는 Analysis & Scoring Agent다.
daily_prices 리스트를 입력받아 MA5, MA20, MA60, RSI14, volume_ratio_20d를 계산하는 TechnicalAnalyzer를 작성하라.
DB 접근은 하지 말고 순수 계산 함수로 먼저 구현하라.
pytest 테스트를 작성하라.
```

### 예시 3: 코드 리뷰 작업

```text
너는 Test / Review / Docs Agent다.
현재 코드가 계층 분리 원칙을 지키는지 리뷰하라.
Data 계층이 Decision 계층을 import하는지, Recommendation 계층이 KIS API를 직접 호출하는지 확인하라.
문제점과 수정안을 제시하라.
```

---

## 23. 에이전트 간 수정 충돌 방지 규칙

```text
1. 각 작업은 담당 모듈만 수정한다.
2. 다른 모듈 수정이 필요하면 먼저 제안한다.
3. 공통 인터페이스 변경은 PM / Architect Agent 승인 후 진행한다.
4. DB 스키마 변경은 DB / Repository Agent가 담당한다.
5. 점수 산식 변경은 Analysis & Scoring Agent가 담당한다.
6. 추천 판단 변경은 Recommendation & Holding Agent가 담당한다.
7. 텔레그램 문구 변경은 Notification & Report Agent가 담당한다.
8. 테스트 추가는 Test / Review / Docs Agent가 담당한다.
```

---

## 24. Definition of Done

각 에이전트 작업은 아래 조건을 만족해야 완료로 본다.

```text
코드가 실행된다.
테스트가 있다.
기존 테스트가 깨지지 않는다.
문서 또는 주석이 필요한 부분에 설명이 있다.
v0.1 범위를 벗어나지 않는다.
API 키나 민감정보가 노출되지 않는다.
계층 분리 원칙을 위반하지 않는다.
```

---

## 25. v0.1 완료 기준

```text
1. KIS API 또는 mock 데이터로 시총 TOP 500/일봉/현재가 수집 가능
2. daily_prices 저장 가능
3. 기술 지표 계산 가능
4. 보유 종목 등록 가능
5. 보유 종목 장전/장후 점검 생성 가능
6. 신규 추천 TOP 5 생성 가능
7. 추천 이력 저장 가능
8. data_snapshots와 decision_logs 저장 가능
9. 텔레그램 리포트 발송 가능
10. FastAPI로 대시보드 조회 API 제공 가능
11. 핵심 로직 테스트 존재
12. README에 실행 방법 정리
```

---

# Part D. 최상위 Codex 초기 지시문

로컬 PC에서 Codex를 시작할 때 아래 지시문을 먼저 제공한다.

```text
너는 한국투자증권 API 기반 AI 주식 분석/추천/보유점검 플랫폼을 개발하는 코딩 에이전트 팀이다.

참고 문서:
- stock_ai_project_codex_brief.md
- stock_ai_detailed_spec.md
- codex_agent_creation_spec.md

v0.1 목표:
한국 주식 중심으로 데이터 수집, 기술적 분석, 보유 종목 장전/장후 점검,
신규 추천 리포트, 텔레그램 알림, PC 대시보드용 백엔드 API를 구현한다.

v0.1 제외:
실거래 자동매매, 주문 API 실제 실행, 가상 증권사 서버, 전용 AI 모델 학습,
전략 자동 튜닝, FULL_AUTO 모드.

핵심 원칙:
1. Data 모듈은 판단하지 않는다.
2. Analysis 모듈은 주문하지 않는다.
3. AI 모듈은 직접 매매하지 않는다.
4. Recommendation/Holding 모듈은 외부 API를 직접 호출하지 않는다.
5. RiskEngine은 모든 실행의 최종 게이트다.
6. 실거래 주문 API는 v0.1에서 구현하지 않는다.
7. 모든 추천과 판단은 data_snapshots와 decision_logs에 기록한다.
8. 외부 API 키, 계좌번호, 토큰은 코드와 로그에 노출하지 않는다.
9. 테스트 가능한 구조로 작성한다.

작업 방식:
- 에이전트 역할을 명시하고 작업한다.
- 작은 단위로 구현한다.
- 작업 후 테스트와 문서를 갱신한다.
```

---

# Part E. 최종 권장 에이전트 구조

## v0.1 실전 운용 구조

```text
1. PM / Architect Agent
2. DB / Repository Agent
3. KIS & Data Agent
4. Analysis & Scoring Agent
5. Recommendation & Holding Agent
6. Notification & Report Agent
7. Backend API Agent
8. Test / Review / Docs Agent
```

## v0.2 이후 확장 구조

```text
9. Dashboard Frontend Agent
10. Strategy Agent
11. Backtest Agent
12. AI/LLM Agent
```

## v0.4 이후 고급 확장 구조

```text
13. Simulation Agent
14. DevOps Agent
15. Security Agent
16. Auto Trading Agent
```

---

## 마지막 원칙

이 프로젝트의 에이전트 구조는 기능을 많이 만드는 것보다 **경계를 지키는 것**이 중요하다.

```text
좋은 에이전트 구조 = 역할 분리 + 작은 작업 + 테스트 + 문서화 + 안전한 확장
```

v0.1은 작게 완성하고, 이후 전략/백테스트/가상매매/자동매매로 확장한다.
