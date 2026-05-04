# AI 주식 분석·추천·전략검증·자동매매 플랫폼 프로젝트 브리프

이 문서는 로컬 PC에서 Codex와 함께 개발을 진행하기 위해, 사용자와 ChatGPT가 대화로 설계한 주식 프로그램 프로젝트의 전체 맥락을 정리한 문서이다.

목표는 Codex가 이 문서를 읽고 프로젝트의 방향, 기능 범위, 시스템 구조, 개발 우선순위, 확장 전략을 이해한 뒤 코드 생성과 설계를 이어갈 수 있게 하는 것이다.

---

## 1. 프로젝트 개요

### 프로젝트 목적

한국 주식 중심의 AI 기반 주식 분석·추천·보유점검·전략검증·가상매매·자동매매 플랫폼을 만든다.

초기 버전은 실제 자동매매가 아니라, 다음 기능을 중심으로 한다.

- 한국투자증권 API 기반 주가 데이터 수집
- 보유 종목 장전/장후 점검
- 신규 추천 종목 아침 리포트
- 기술적 분석, 뉴스, 실적, AI 판단을 종합한 점수화
- 텔레그램 알림
- PC 대시보드
- 날짜별 추천 이력 저장 및 성과 검증

장기적으로는 다음 기능으로 확장한다.

- 장기/중기/단기 전략 관리
- 상승장/횡보장/하락장/테마장/급락장별 전략 자동 선택
- 가상매매
- 백테스트
- 전략 자동 튜닝
- 로컬 가상 증권사 서버
- 가상 차트/가상 뉴스 생성
- 전용 주식 AI 모델
- 소액 자동매매

---

## 2. 핵심 방향

이 프로젝트는 단순한 주식 추천 프로그램이 아니다.

최종 목표는 다음에 가깝다.

> 한국투자증권 API 기반 AI 주식 분석·추천·보유점검·전략검증·가상매매·자동매매 플랫폼

중요한 설계 철학은 다음과 같다.

1. AI에게 모든 판단을 맡기지 않는다.
2. 기초 데이터 계산과 검증은 자체 프로그램이 수행한다.
3. AI는 뉴스 요약, 리스크 설명, 종목 비교, 리포트 작성, 판단 보조 역할을 맡는다.
4. 자동매매는 반드시 리스크 엔진을 통과해야 한다.
5. 처음에는 가상매매와 리포트 중심으로 검증한다.
6. 실거래는 충분히 검증한 후 소액으로만 시작한다.
7. 모든 추천과 판단은 저장하고 사후 성과를 검증한다.

---

## 3. 시장 우선순위

사용자의 메인 시장은 한국 주식이다.

| 시장 | 역할 |
|---|---|
| 한국 | 메인 분석, 추천, 보유점검, 향후 자동매매 대상 |
| 미국 | 한국장 선행지표, 보조 추천, 반도체/AI/나스닥 영향 분석 |
| 유럽 | 직접 추천보다는 경제 뉴스, 방산, 전력, 에너지, 반도체 장비 등 매크로 참고 |

초기 버전은 한국 주식 중심으로 만든다.

---

## 4. 한국투자증권 API 사용

프로젝트의 핵심 데이터 및 주문 연동 API는 한국투자증권 Open API이다.

v0.1에서는 다음 목적으로 사용한다.

- 국내 주식 현재가 조회
- 국내 주식 일봉 데이터 조회
- 국내 주식 시가총액 상위 종목 조회
- 관심종목/보유종목 분석용 데이터 수집
- 향후 잔고/주문/체결/해외주식 데이터 확장

자동매매는 v0.1에 포함하지 않는다.

---

## 5. v0.1 목표

v0.1은 작게 시작해야 한다.

### v0.1 핵심 목표

> 한국 주식 중심 AI 점검/추천 리포트 시스템

### v0.1 포함 기능

- 한국투자증권 API 인증 및 데이터 수집
- 관심종목 관리
- 보유종목 관리
- 시가총액 상위 500 종목 조회 및 저장
- 일봉 데이터 저장
- 기술적 지표 계산
- 보유 종목 장전/장후 점검
- 아침 6시 신규 추천 리포트
- 날짜별 추천 이력 저장
- 추천 후 성과 검증
- 텔레그램 알림
- PC 대시보드 기본
- 뉴스 제목/링크/출처/시간 기반 간단 분석
- AI 기반 뉴스 요약 및 추천 근거 작성

### v0.1 제외 기능

- 실거래 자동매매
- 가상 증권사 서버
- 전용 AI 모델 학습
- 전략 자동 튜닝
- 대규모 가상 데이터 생성
- 복잡한 백테스트 엔진
- 완전한 자동 전략 선택

단, 확장을 고려해 인터페이스와 빈 구조는 미리 만들어둘 수 있다.

---

## 6. 핵심 일일 사용 흐름

### 아침 사용 흐름

1. 06:00 텔레그램으로 신규 추천 리포트 수신
2. 08:30 장전 보유 종목 점검 수신
3. 09:00 한국장 시작
4. 장중에는 위험 경고 발생 시 텔레그램 수신
5. 15:30 장 마감
6. 16:30 장후 보유 종목 점검 수신
7. PC 대시보드에서 상세 분석 확인

---

## 7. 일일 자동 실행 스케줄

초기 설계 기준 스케줄은 다음과 같다.

| 시간 | 작업 |
|---|---|
| 18:00 | 한국장 마감 데이터 수집 |
| 18:30 | 기술적 지표 계산 |
| 19:00 | 뉴스/공시 수집 |
| 20:00 | 시장 국면 판단 |
| 21:00 | 추천 후보 1차 선정 |
| 05:30 | 미국장/글로벌 영향 반영 |
| 06:00 | 신규 추천 텔레그램 발송 |
| 08:30 | 보유 종목 장전 점검 |
| 16:30 | 보유 종목 장후 점검 |
| 17:00 | 추천/보유 성과 업데이트 |

뉴스나 일부 데이터 수집이 실패하더라도 전체 리포트를 중단하지 않고 부분 리포트를 생성해야 한다.

---

## 8. 점수 체계

### 신규 추천 종목 점수

```text
신규 추천 점수 =
기술 점수 35%
+ 뉴스/테마 점수 25%
+ 수급 점수 15%
+ 실적/재무 점수 15%
+ AI 판단 점수 10%
- 리스크 감점
```

### 보유 종목 점수

```text
보유 종목 점수 =
기술 점수 35%
+ 뉴스/공시 점수 20%
+ 실적/재무 점수 20%
+ AI 판단 점수 15%
+ 수익 관리 점수 10%
- 리스크 감점
```

### 시장 국면 점수

```text
시장 점수 =
지수 추세 25%
+ 시장 폭 15%
+ 거래대금 15%
+ 수급 15%
+ 미국장 영향 15%
+ 뉴스/매크로 리스크 15%
```

v0.1에서는 이 산식을 명확하게 구현하고, 향후 백테스트 결과에 따라 가중치를 조정한다.

---

## 9. 판단 등급 체계

### 신규 추천 등급

| 등급 | 의미 |
|---|---|
| S | 강한 관찰 후보 |
| A | 매수 검토 후보 |
| B | 관심 유지 후보 |
| C | 조건 부족 |
| D | 제외 |

신규 추천은 바로 매수 지시가 아니라 관찰 후보 또는 매수 검토 후보로 표현한다.

### 보유 종목 판단

| 판단 | 의미 |
|---|---|
| 강한 보유 | 추세와 근거가 강함 |
| 보유 유지 | 특별한 훼손 없음 |
| 관찰 필요 | 일부 리스크 존재 |
| 비중 축소 검토 | 점수 하락 또는 추세 약화 |
| 매도 검토 | 주요 조건 훼손 |
| 신규 매수 금지 | 보유는 가능하지만 추가 매수 위험 |

---

## 10. 기술적 분석 기능

기술적 분석은 AI가 직접 계산하지 않는다.

자체 프로그램이 계산하고, AI는 해석한다.

### 주요 지표

- 5일 이동평균
- 20일 이동평균
- 60일 이동평균
- 120일 이동평균
- 이동평균 정배열/역배열
- RSI
- MACD
- 볼린저밴드
- 거래량 20일 평균 대비 비율
- 거래대금 증가율
- 20일 고점 돌파
- 60일 고점 돌파
- 52주 신고가
- 전고점 돌파
- 지지선/저항선
- 캔들 패턴
  - 장대양봉
  - 장대음봉
  - 긴 윗꼬리
  - 긴 아래꼬리
  - 도지
  - 상승 장악형
  - 하락 장악형

### 기술 점수 예시

| 항목 | 배점 |
|---|---:|
| 이동평균 추세 | 25 |
| 거래량 증가 | 20 |
| 돌파 신호 | 20 |
| 모멘텀 지표 | 15 |
| 캔들 패턴 | 10 |
| 변동성/리스크 | 10 |

---

## 11. 보유 종목 점검 기능

사용자가 매수한 종목은 매일 장전과 장후에 점검한다.

### 장전 점검

목적은 오늘 대응 시나리오를 제공하는 것이다.

분석 항목:

- 전일 종가 기준 기술 분석
- 밤사이 미국장 영향
- 새벽 뉴스
- 공시
- 오늘 대응 조건
- 유지 조건
- 이탈 조건
- 손절/익절 기준 접근 여부

### 장후 점검

목적은 오늘 흐름을 복기하고 내일 전략을 준비하는 것이다.

분석 항목:

- 당일 시가/고가/저가/종가
- 거래량
- 캔들
- 수급
- 뉴스/공시
- 점수 변화
- 보유 판단 변화

---

## 12. 신규 추천 리포트 기능

매일 아침 6시에 추천 리포트를 텔레그램으로 보낸다.

### 추천 대상

v0.1 기준 추천 유니버스:

- 보유종목
- 관심종목
- 코스피 시가총액 상위 종목
- 코스닥 시가총액 상위 종목
- 통합 시가총액 TOP 500

### 추천 개수

| 구분 | 개수 |
|---|---:|
| 한국 주식 추천 | TOP 5 |
| 한국 관심 후보 | 추가 5개 |
| 미국 참고 종목 | TOP 3 |
| 보유 종목 점검 | 전 종목 |
| 위험 경고 | 조건 발생 시만 |

---

## 13. 시가총액 상위 500 종목 기능

### 기능 목적

매일 한국 주식 시장의 시가총액 상위 500개 종목을 조회하고 저장해서 기본 분석 유니버스로 사용한다.

### v0.1 추천 기준

- 코스피 시총 상위 300개
- 코스닥 시총 상위 200개
- 또는 통합 시총 상위 500개

### 활용

- 신규 추천 후보군
- 전략별 분석 대상
- 시장 대표 종목 감시
- 저유동성 종목 제외
- 대시보드 조회

### 확장

- 시총 순위 변화 감지
- 섹터별 시총 분석
- 전략별 유니버스 선택
- 거래대금 필터 결합

---

## 14. 텔레그램 알림 정책

텔레그램은 요약과 경고 중심으로 사용한다.

### v0.1 알림

| 알림 | 시간 |
|---|---|
| 신규 추천 리포트 | 06:00 |
| 보유 종목 장전 점검 | 08:30 |
| 보유 종목 장후 점검 | 16:30 |
| 위험 경고 | 조건 발생 시 |

### 위험 경고 조건

- 보유 종목 점수 15점 이상 하락
- 20일선 이탈
- 손절가 근접
- 악재 뉴스 발생
- 시장 급락장 전환
- 거래량 동반 하락
- 실적 쇼크

알림은 과도하게 보내지 않도록 우선순위를 둔다.

---

## 15. PC 대시보드 설계

대시보드는 PC에서 상세 정보를 확인하기 위한 핵심 인터페이스이다.

### v0.1 메뉴

1. 오늘의 리포트
2. 보유 종목 점검
3. 추천 종목
4. 추천 이력
5. 종목 상세
6. 시가총액 TOP 500
7. 시장 국면
8. 뉴스/공시
9. 설정
10. 시스템 로그

### v0.2 이후 메뉴

11. 전략 관리
12. 가상매매
13. 백테스트
14. 전략 튜닝
15. 자동매매 설정

### 화면 구조

일반적인 PC 대시보드 구조는 다음과 같다.

```text
┌──────────────────────────────────────┐
│ 상단바: 날짜 / 시장상태 / 알림 / 설정 │
├──────────────┬───────────────────────┤
│ 왼쪽 메뉴     │ 메인 콘텐츠 영역        │
│              │ 카드 + 표 + 차트        │
└──────────────┴───────────────────────┘
```

### 우선 구현 화면

1. 오늘의 리포트
2. 보유 종목 점검
3. 추천 종목/추천 이력
4. 종목 상세

---

## 16. 전체 시스템 아키텍처

최종 추천 구조는 다음과 같다.

```text
External APIs
├─ KIS API
├─ News API/RSS
├─ DART
└─ Macro Data

        ↓

Data Ingestion Layer
├─ Collectors
├─ Normalizers
├─ Validators
├─ Availability Checker
└─ Repository

        ↓

Analysis Layer
├─ Technical Analysis
├─ Volume/Supply Analysis
├─ News/Disclosure Analysis
├─ Fundamental Analysis
├─ Theme Analysis
└─ Market Regime Analysis

        ↓

Scoring Layer
├─ Stock Score
├─ Holding Score
├─ Market Score
├─ Strategy Suitability Score
└─ Risk Score

        ↓

Decision Layer
├─ Recommendation Engine
├─ Holding Check Engine
├─ Strategy Engine
├─ AI Judgement Engine
└─ Decision Logger

        ↓

Risk Gate
├─ Market Risk Check
├─ Position Risk Check
├─ Strategy Risk Check
├─ News Risk Check
├─ API/Execution Risk Check
└─ Final Allow/Block

        ↓

Execution Layer
├─ Report Generator
├─ Telegram Notifier
├─ Dashboard API
├─ Paper Trading
├─ Approval Trading
└─ Real Trading

        ↓

Broker Interface
├─ KisBroker
├─ MockBroker
├─ ReplayBroker
└─ SimulationBroker
```

핵심 흐름은 다음과 같다.

```text
Data
→ Analysis
→ Scoring
→ Decision
→ Risk Gate
→ Execution
→ Broker
```

---

## 17. 핵심 설계 원칙

1. 데이터 수집 모듈은 판단하지 않는다.
2. 분석 모듈은 주문하지 않는다.
3. AI 모듈은 직접 매매하지 않는다.
4. 전략 모듈은 리스크 엔진을 우회할 수 없다.
5. 실거래 주문은 BrokerInterface를 통해서만 실행한다.
6. 추천 당시 데이터 스냅샷을 반드시 저장한다.
7. 모든 판단과 리스크 차단 이벤트를 로그로 저장한다.
8. 실거래 자동매매는 마지막 단계에서만 활성화한다.

---

## 18. 핵심 인터페이스

### BrokerInterface

실제 증권사, 가상 증권사, 과거 데이터 리플레이, 시뮬레이션 브로커를 같은 방식으로 다루기 위한 인터페이스이다.

```python
class BrokerInterface:
    def get_current_price(self, symbol: str):
        pass

    def get_ohlcv(self, symbol: str, start_date: str, end_date: str):
        pass

    def get_orderbook(self, symbol: str):
        pass

    def get_balance(self):
        pass

    def get_positions(self):
        pass

    def place_order(self, order):
        pass

    def cancel_order(self, order_id: str):
        pass

    def get_order_status(self, order_id: str):
        pass

    def get_trade_history(self):
        pass
```

구현체:

- KisBroker
- MockBroker
- ReplayBroker
- SimulationBroker

### AIProviderInterface

```python
class AIProviderInterface:
    def summarize_news(self, news_items):
        pass

    def judge_stock(self, stock_context):
        pass

    def explain_decision(self, decision_context):
        pass

    def generate_report(self, report_context):
        pass
```

구현체:

- CloudLLMProvider
- LocalLLMProvider
- RuleBasedProvider
- CustomModelProvider

### StrategyInterface

```python
class StrategyInterface:
    def generate_signal(self, market_context, stock_context, portfolio_context):
        pass

    def should_buy(self, context):
        pass

    def should_sell(self, context):
        pass

    def risk_rules(self):
        pass
```

구현체 예시:

- LongTermGrowthStrategy
- MidTermTrendStrategy
- ThemeMomentumStrategy
- BoxRangeStrategy
- RiskOffStrategy
- ShortTermBreakoutStrategy

---

## 19. AI 사용 전략

### LLM의 역할

LLM은 다음 역할에 적합하다.

- 뉴스 요약
- 뉴스/공시 의미 해석
- 추천 근거 작성
- 리스크 설명
- 텔레그램 리포트 문장 생성
- 전략 실패 복기 설명
- 사용자 질문 응답

### LLM이 하면 안 되는 것

- 직접 주문 실행
- 리스크 엔진 우회
- 자금 비중 단독 결정
- 손절 기준 무시
- 계산 지표 직접 산출

### 전용 AI 모델의 역할

장기적으로는 LLM이 아니라 전용 ML 모델을 만든다.

전용 AI 모델 후보:

- Market Regime Model: 시장 국면 판단
- Strategy Selection Model: 전략 자동 선택
- Risk Prediction Model: 급락/손실 위험 예측
- Stock Scoring Model: 종목 점수 보정
- News Impact Model: 뉴스 영향 점수화
- Performance Feedback Model: 추천/전략 성과 반영

초기에는 룰 기반으로 시작하고, 이후 LightGBM/XGBoost 등으로 확장한다.

---

## 20. 시장 국면 판단

### 시장 국면 종류

- 상승장
- 상승장 초기
- 과열 상승장
- 횡보장
- 하락장
- 급락장
- 테마장
- 실적장
- 변동성 장세

### 시장 국면 판단 데이터

- 코스피/코스닥 추세
- 지수 이동평균 위치
- 상승/하락 종목 비율
- 거래대금 변화
- 외국인/기관 수급
- 환율
- 나스닥/S&P500/필라델피아 반도체 지수
- 미국 주요 AI/반도체 종목 흐름
- 섹터 강도
- 뉴스 분위기
- 매크로 리스크

---

## 21. 전략 관리 및 자동매매 확장

### 전략 카테고리

| 카테고리 | 목적 | 보유 기간 |
|---|---|---:|
| 장기 투자 | 기업 성장성 중심 | 6개월~수년 |
| 중기 투자 | 추세·실적·테마 중심 | 수주~수개월 |
| 단기 매매 | 모멘텀·수급 중심 | 당일~수일 |
| 테스트 전략 | 검증용 | 자유 |

### 시장 국면별 전략

| 시장 국면 | 장기 전략 | 중기 전략 | 단기 전략 |
|---|---|---|---|
| 상승장 | 성장주 분할매수/보유 | 추세추종/돌파 | 모멘텀/눌림매수 |
| 횡보장 | 우량주 저가분할 | 박스권 매매 | 지지·저항 단타 |
| 하락장 | 현금비중 확대/분할 대기 | 방어주·상대강도 | 매매 축소/초단기만 |
| 급락장 | 대기 | 신호만 | 중지 |
| 테마장 | 핵심 테마 선별 | 주도 테마 추적 | 뉴스 모멘텀 |

### 자동매매 발전 단계

| 단계 | 설명 |
|---|---|
| SIGNAL | 신호만 생성 |
| PAPER | 가상매매 |
| APPROVAL | 주문 전 사용자 승인 |
| SMALL_AUTO | 소액 자동매매 |
| FULL_AUTO | 완전 자동매매 |

초기에는 SIGNAL과 PAPER만 사용한다.

---

## 22. 백테스트 및 자동 튜닝

장기적으로 전략 생성과 검증을 위해 백테스트·자동 튜닝 엔진을 만든다.

### 백테스트에서 반드시 반영할 것

- 매수/매도 수수료
- 증권거래세
- 슬리피지
- 거래량 제한
- 생존자 편향
- 미래 데이터 사용 금지
- 뉴스 발생 시점
- 공시 발생 시점

### 자동 튜닝 방식

- v0.1: 제외
- v0.2: 기본 백테스트
- v0.3: Grid Search
- v0.4: Walk-forward 검증
- v1.0: Bayesian Optimization 및 AI 보조 튜닝

---

## 23. 가상 증권사 서버 및 가상 데이터

장기 확장 기능으로 로컬 PC 안에 가상 증권사 서버를 만든다.

### 목적

- 실제 한국투자증권 API에 붙기 전 자동매매 로직 검증
- 주문/체결/잔고/수익률 테스트
- 급락장, 거래정지, 악재 뉴스 등 극단 상황 테스트
- 시장 국면별 전략 선택 검증
- 가상 차트/가상 뉴스 기반 대량 시뮬레이션

### 구성

- MockBroker
- Market Simulator
- News Simulator
- Order Engine
- Account Engine
- Risk Event Engine
- Strategy Tester
- Performance Analyzer
- Scenario Generator

### 주의

가상 데이터는 훈련장일 뿐 최종 실전 검증이 아니다.

반드시 다음 순서를 따른다.

```text
가상 데이터 대량 훈련
→ 실제 과거 데이터 백테스트
→ 워크포워드 검증
→ 실시간 가상매매
→ 소액 실거래
```

---

## 24. 데이터베이스 핵심 테이블

### v0.1 필수 테이블

- stocks
- holdings
- daily_prices
- stock_indicators
- news_items
- market_regimes
- recommendation_runs
- recommendations
- recommendation_results
- holding_checks
- data_snapshots
- decision_logs
- job_runs
- market_cap_rankings
- stock_universes
- stock_universe_members

### 향후 확장 테이블

- trading_strategies
- strategy_versions
- backtest_runs
- backtest_results
- trade_signals
- paper_trades
- real_trades
- strategy_performance
- risk_events

### 특히 중요한 테이블

#### data_snapshots

추천 당시 데이터를 고정 저장한다.

- snapshot_id
- snapshot_time
- symbol
- price_data_json
- indicator_data_json
- news_data_json
- market_context_json
- created_at

#### decision_logs

모든 판단 과정을 기록한다.

- decision_id
- decision_type
- symbol
- input_snapshot_id
- rule_result_json
- ai_result_json
- risk_result_json
- final_decision
- reason
- created_at

#### job_runs

자동 실행 작업의 성공/실패를 기록한다.

- job_id
- job_name
- started_at
- finished_at
- status
- error_message
- result_summary

---

## 25. 권장 기술 스택

### 백엔드

| 영역 | 추천 |
|---|---|
| 언어 | Python |
| API 서버 | FastAPI |
| 스케줄러 | APScheduler |
| DB | PostgreSQL |
| ORM | SQLAlchemy |
| 데이터 분석 | pandas, numpy |
| 기술적 지표 | pandas-ta 또는 직접 구현 |
| 백테스트 | 자체 엔진 |
| AI 모델 | scikit-learn, LightGBM, XGBoost |
| LLM | Local/Cloud 교체 가능 구조 |

### 프론트엔드

| 영역 | 추천 |
|---|---|
| 대시보드 | React 또는 Next.js |
| 차트 | TradingView Lightweight Charts |
| 테이블 | TanStack Table |
| 상태관리 | Zustand 또는 React Query |
| UI | Tailwind 기반 |

### 운영

| 영역 | 추천 |
|---|---|
| 로컬 실행 | Docker Compose |
| 로그 | structured logging |
| 백업 | DB 자동 백업 |
| 알림 | Telegram Bot |
| 비밀키 관리 | .env + 암호화 저장 |

---

## 26. 프로젝트 폴더 구조 초안

```text
stock_ai_platform/
├─ app/
│  ├─ main.py
│  ├─ config/
│  ├─ api/
│  ├─ data/
│  │  ├─ collectors/
│  │  ├─ normalizers/
│  │  ├─ validators/
│  │  └─ repositories/
│  ├─ analysis/
│  ├─ scoring/
│  ├─ decision/
│  ├─ risk/
│  ├─ ai/
│  ├─ broker/
│  ├─ trading/
│  ├─ backtest/
│  ├─ simulation/
│  ├─ notification/
│  ├─ scheduler/
│  └─ db/
│
├─ dashboard/
│  ├─ src/
│  └─ package.json
│
├─ scripts/
│  ├─ run_daily_report.py
│  ├─ run_holding_check.py
│  ├─ run_backtest.py
│  └─ generate_synthetic_data.py
│
├─ tests/
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

---

## 27. 보안 원칙

이 프로젝트는 계좌, API 키, 주문 기능과 연결될 수 있으므로 보안을 반드시 고려해야 한다.

- API 키를 코드에 직접 저장하지 않는다.
- `.env` 파일 또는 암호화된 secret storage를 사용한다.
- 한국투자증권 토큰은 마스킹 및 암호화한다.
- 실거래 모드는 기본 비활성화한다.
- 대시보드는 로그인 또는 로컬 제한을 적용한다.
- 텔레그램은 허용된 chat_id에만 발송한다.
- 로그에 계좌번호, API 키, 토큰이 남지 않도록 한다.
- 실거래 전 비상 정지 기능을 반드시 구현한다.

---

## 28. 개발 우선순위

### 추천 개발 순서

```text
1. DB 구조
2. 한국투자증권 API 데이터 수집
3. 일봉/기술 지표 계산
4. 보유 종목 입력/관리
5. 보유 종목 장후 점검
6. 텔레그램 알림
7. 아침 추천 리포트
8. 추천 이력 저장
9. PC 대시보드
10. 추천 성과 검증
```

처음부터 자동매매나 전용 AI 모델을 만들지 않는다.

---

## 29. v0.1 성공 기준

v0.1의 성공 기준은 수익률이 아니다.

초기 목표는 안정적으로 돌아가는 시스템이다.

| 기준 | 목표 |
|---|---|
| 매일 데이터 수집 성공 | 95% 이상 |
| 텔레그램 발송 성공 | 매일 정상 발송 |
| 보유 종목 점검 | 장전/장후 정상 생성 |
| 추천 이력 저장 | 날짜별 조회 가능 |
| 대시보드 확인 | PC에서 추천/보유 정보 확인 |
| 추천 성과 검증 | 1일/3일/5일 후 자동 계산 |
| 시스템 로그 | 오류 확인 가능 |

---

## 30. 최종 평가

이 프로젝트는 매우 유망하지만 범위가 크다.

성공을 위해서는 반드시 작은 버전부터 만들어야 한다.

최종 방향은 다음과 같다.

```text
추천 시스템
→ 보유 점검 시스템
→ 전략 관리 시스템
→ 가상매매 시스템
→ 백테스트/튜닝 시스템
→ 전용 AI 모델
→ 소액 자동매매 시스템
```

현재 가장 좋은 다음 단계는 다음이다.

> v0.1 기능명세서를 작성하고, DB 설계와 한국투자증권 API 수집 모듈부터 구현한다.

