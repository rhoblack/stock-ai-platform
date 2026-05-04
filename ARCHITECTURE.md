# Architecture

## 1. 핵심 구조

이 프로젝트는 다음 흐름을 따른다.

```text
External APIs
→ Data Collection
→ Repository
→ Analysis
→ Scoring
→ Recommendation / Holding Check
→ Risk Gate
→ Report / Notification / Dashboard
```

향후 자동매매 확장 시 흐름:

```text
Strategy Signal
→ AI Judgement
→ RiskEngine
→ BrokerInterface
→ TradeLogger
```

v0.1에서는 자동매매 흐름을 비활성 상태로 둔다.

## 2. 계층 구조

```text
app/
├─ config/
├─ db/
├─ data/
├─ analysis/
├─ decision/
├─ ai/
├─ notification/
├─ api/
├─ scheduler/
├─ broker/
└─ tests/
```

## 3. 계층별 책임

### Data Layer

외부 API 호출, 정규화, 저장을 담당한다.

- KIS API
- 뉴스 수집
- 공시 수집
- 시가총액 TOP 500
- 데이터 품질 검사

Data Layer는 추천 판단을 하지 않는다.

### Analysis Layer

저장된 데이터를 분석 가능한 지표로 바꾼다.

- 이동평균
- RSI
- MACD
- 거래량 비율
- 돌파 여부
- 시장 국면 기초 점수

Analysis Layer는 주문하지 않는다.

### Scoring / Decision Layer

점수 계산, 추천, 보유 점검을 담당한다.

- ScoringEngine
- RecommendationEngine
- HoldingCheckEngine
- RiskEngine
- DecisionLogger

Recommendation/Holding 모듈은 외부 API를 직접 호출하지 않는다.

### Notification Layer

리포트 생성과 알림 발송을 담당한다.

- ReportGenerator
- TelegramNotifier
- NotificationLog

Notification 모듈은 추천 로직을 변경하지 않는다.

### API Layer

PC 대시보드용 읽기 API를 제공한다.

FastAPI 라우터는 지표 계산이나 추천 생성을 직접 하지 않는다.

## 4. 핵심 인터페이스

### DataProviderInterface

외부 데이터 공급자 교체를 위한 인터페이스.

### AIProviderInterface

Dummy, Local LLM, Cloud LLM, Custom Model을 교체 가능하게 만든다.

### BrokerInterface

미래 확장용이다.

- KisBroker
- MockBroker
- ReplayBroker
- SimulationBroker

v0.1에서는 주문 실행 구현 금지.

### StrategyInterface

미래 전략/백테스트 확장용이다.

v0.1에서는 placeholder만 둔다.

## 5. 핵심 안전 규칙

- AI는 주문하지 않는다.
- RiskEngine은 미래 실행의 최종 게이트다.
- v0.1은 실거래를 하지 않는다.
- 모든 판단은 snapshot/log로 추적 가능해야 한다.
