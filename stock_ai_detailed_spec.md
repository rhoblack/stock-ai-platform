# AI 주식 분석·추천·보유점검·전략검증 플랫폼 상세 명세서 v0.1

> 목적: 이 문서는 로컬 PC에서 Codex와 함께 개발을 진행하기 위한 상세 기능 명세서이다.  
> 프로젝트는 한국투자증권 API를 중심으로 한국 주식 분석을 우선 구현하고, 이후 미국 주식 참고 분석, 전략 백테스트, 가상매매, 자동매매, 전용 AI 모델까지 확장 가능한 구조를 목표로 한다.

---

## 0. 프로젝트 한 줄 정의

**한국투자증권 API 기반 AI 주식 분석 플랫폼**  
한국 주식 중심으로 주가·기술적 지표·뉴스·공시·실적·시장 국면을 분석하여 매일 추천 종목과 보유 종목 점검 결과를 생성하고, 텔레그램과 PC 대시보드로 제공한다. 향후 전략별 가상매매, 백테스트, 자동 튜닝, 전용 AI 모델, 소액 자동매매까지 확장한다.

---

## 1. 프로젝트 목표

### 1.1 v0.1 목표

v0.1은 실거래 자동매매가 아니라 **분석·점검·추천 리포트 시스템**이다.

핵심 목표:

1. 한국투자증권 API로 국내 주식 데이터를 수집한다.
2. 시가총액 상위 500개 종목과 관심종목, 보유종목을 관리한다.
3. 기술적 지표를 계산하고 종목별 점수를 산출한다.
4. 보유 종목을 장 시작 전과 장 종료 후 점검한다.
5. 매일 오전 6시에 신규 추천 후보를 텔레그램으로 발송한다.
6. 추천 이력과 보유 점검 이력을 날짜별로 저장한다.
7. PC 대시보드에서 오늘 리포트, 보유 종목, 추천 이력, 종목 상세를 확인한다.

### 1.2 v0.1에서 하지 않는 것

v0.1에서는 아래 기능을 직접 실행하지 않는다. 단, 확장 가능한 구조와 인터페이스는 설계에 포함한다.

- 실거래 자동매매
- 소액 자동매매
- 주문 API 실행
- 가상 증권사 서버
- 대량 가상 데이터 생성
- 전용 AI 모델 학습
- 전략 자동 튜닝
- 고급 백테스트

---

## 2. 주요 사용자 시나리오

### 2.1 매일 아침 사용 흐름

```text
06:00  텔레그램으로 오늘의 신규 추천 리포트 수신
08:30  보유 종목 장전 점검 리포트 수신
09:00  한국장 시작
15:30  한국장 종료
16:30  보유 종목 장후 점검 리포트 수신
저녁   PC 대시보드에서 상세 분석 확인
```

### 2.2 주말 사용 흐름

```text
주간 추천 성과 확인
보유 종목 점수 변화 확인
추천 실패/성공 종목 복기
관심종목 추가/삭제
전략 후보 검토
```

---

## 3. 전체 시스템 아키텍처

### 3.1 계층 구조

```text
[External APIs]
├─ 한국투자증권 API
├─ 뉴스/RSS/API
├─ DART 공시
├─ 환율/지수/매크로 데이터
└─ 향후 미국/유럽 데이터

        ↓

[Data Ingestion Layer]
├─ Collectors
├─ Normalizers
├─ Validators
├─ Availability Checker
└─ Repository

        ↓

[Analysis Layer]
├─ Technical Analysis
├─ Volume/Supply Analysis
├─ News/Disclosure Analysis
├─ Fundamental Analysis
├─ Theme Analysis
└─ Market Regime Analysis

        ↓

[Scoring Layer]
├─ Stock Score
├─ Holding Score
├─ Market Score
├─ Strategy Suitability Score
└─ Risk Score

        ↓

[Decision Layer]
├─ Recommendation Engine
├─ Holding Check Engine
├─ Strategy Engine
├─ AI Judgement Engine
└─ Decision Logger

        ↓

[Risk Gate]
├─ Market Risk Check
├─ Position Risk Check
├─ Strategy Risk Check
├─ News Risk Check
├─ API/Execution Risk Check
└─ Final Allow/Block

        ↓

[Execution Layer]
├─ Report Generator
├─ Telegram Notifier
├─ Dashboard API
├─ Paper Trading
├─ Approval Trading
└─ Real Trading

        ↓

[Broker Interface]
├─ KisBroker
├─ MockBroker
├─ ReplayBroker
└─ SimulationBroker
```

### 3.2 핵심 설계 원칙

1. 데이터 수집 모듈은 판단하지 않는다.
2. 분석 모듈은 주문하지 않는다.
3. AI 모듈은 직접 매매하지 않는다.
4. 전략 모듈은 리스크 엔진을 우회할 수 없다.
5. 실거래 주문은 반드시 BrokerInterface를 통해서만 실행한다.
6. 추천 당시의 데이터 스냅샷을 반드시 저장한다.
7. 모든 판단은 decision_logs에 저장한다.
8. v0.1에서는 실거래 주문 기능을 비활성화한다.

---

## 4. 기술 스택 권장안

### 4.1 백엔드

| 영역 | 추천 |
|---|---|
| 언어 | Python |
| API 서버 | FastAPI |
| 스케줄러 | APScheduler |
| DB | PostgreSQL, 초기 개발은 SQLite 가능 |
| ORM | SQLAlchemy |
| 데이터 분석 | pandas, numpy |
| 기술 지표 | pandas-ta 또는 직접 구현 |
| AI 연동 | Local LLM / Cloud LLM 교체 가능 구조 |
| 환경 관리 | uv 또는 pip/venv |
| 배포 | Docker Compose |

### 4.2 프론트엔드

| 영역 | 추천 |
|---|---|
| 프레임워크 | React 또는 Next.js |
| 차트 | TradingView Lightweight Charts |
| 테이블 | TanStack Table |
| 스타일 | Tailwind CSS |
| 상태관리 | React Query, Zustand |

### 4.3 알림

| 영역 | 추천 |
|---|---|
| 메시지 | Telegram Bot API |
| 장기 확장 | 이메일, 카카오톡, Slack |

---

## 5. 프로젝트 폴더 구조 초안

```text
stock_ai_platform/
├─ app/
│  ├─ main.py
│  ├─ config/
│  │  ├─ settings.py
│  │  ├─ secrets.py
│  │  └─ logging.py
│  │
│  ├─ api/
│  │  ├─ dashboard_routes.py
│  │  ├─ recommendation_routes.py
│  │  ├─ holding_routes.py
│  │  ├─ strategy_routes.py
│  │  └─ broker_routes.py
│  │
│  ├─ data/
│  │  ├─ collectors/
│  │  │  ├─ kis_collector.py
│  │  │  ├─ news_collector.py
│  │  │  ├─ dart_collector.py
│  │  │  └─ macro_collector.py
│  │  ├─ normalizers/
│  │  ├─ validators/
│  │  └─ repositories/
│  │
│  ├─ analysis/
│  │  ├─ technical_analyzer.py
│  │  ├─ volume_analyzer.py
│  │  ├─ news_analyzer.py
│  │  ├─ fundamental_analyzer.py
│  │  ├─ market_regime_analyzer.py
│  │  └─ theme_analyzer.py
│  │
│  ├─ scoring/
│  │  ├─ stock_scoring.py
│  │  ├─ holding_scoring.py
│  │  ├─ market_scoring.py
│  │  └─ risk_scoring.py
│  │
│  ├─ decision/
│  │  ├─ recommendation_engine.py
│  │  ├─ holding_check_engine.py
│  │  ├─ strategy_engine.py
│  │  ├─ strategy_selection_engine.py
│  │  ├─ risk_engine.py
│  │  └─ ai_judgement_engine.py
│  │
│  ├─ ai/
│  │  ├─ providers/
│  │  │  ├─ cloud_llm_provider.py
│  │  │  ├─ local_llm_provider.py
│  │  │  └─ custom_model_provider.py
│  │  ├─ prompts/
│  │  └─ training/
│  │
│  ├─ broker/
│  │  ├─ broker_interface.py
│  │  ├─ kis_broker.py
│  │  ├─ mock_broker.py
│  │  ├─ replay_broker.py
│  │  └─ simulation_broker.py
│  │
│  ├─ trading/
│  │  ├─ paper_trading_engine.py
│  │  ├─ order_approval_engine.py
│  │  ├─ auto_trading_engine.py
│  │  └─ trade_logger.py
│  │
│  ├─ backtest/
│  │  ├─ backtest_engine.py
│  │  ├─ strategy_tuner.py
│  │  ├─ walk_forward_validator.py
│  │  └─ performance_analyzer.py
│  │
│  ├─ simulation/
│  │  ├─ synthetic_market_generator.py
│  │  ├─ synthetic_news_generator.py
│  │  ├─ scenario_generator.py
│  │  └─ virtual_exchange.py
│  │
│  ├─ notification/
│  │  ├─ telegram_notifier.py
│  │  └─ report_generator.py
│  │
│  ├─ scheduler/
│  │  ├─ daily_jobs.py
│  │  ├─ market_jobs.py
│  │  └─ scheduler.py
│  │
│  └─ db/
│     ├─ models.py
│     ├─ session.py
│     └─ migrations/
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

## 6. v0.1 상세 기능 명세

---

# 6.1 종목 유니버스 관리 기능

## 6.1.1 기능명

**시가총액 상위 500 종목 조회 및 분석 유니버스 관리**

## 6.1.2 목적

한국 주식 전체를 무작정 분석하지 않고, 유동성과 대표성이 있는 종목군을 기본 분석 대상으로 삼기 위함이다.

## 6.1.3 v0.1 범위

- 한국 주식 시가총액 상위 500개 종목 조회
- 코스피/코스닥 구분
- 날짜별 순위 저장
- 분석 대상 ON/OFF 관리
- 추천 엔진의 기본 유니버스로 사용

## 6.1.4 추천 구성

| 구분 | 개수 |
|---|---:|
| 코스피 시총 상위 | 300개 |
| 코스닥 시총 상위 | 200개 |
| 총합 | 500개 |

## 6.1.5 확장 기능

- 시가총액 순위 변화 감지
- 500위 밖에서 500위 안으로 진입한 종목 감지
- 섹터별 시가총액 상위 종목 조회
- 전략별 유니버스 선택

---

# 6.2 관심종목 관리 기능

## 6.2.1 목적

사용자가 직접 추적하고 싶은 종목을 관리한다.

## 6.2.2 기능

- 관심종목 추가
- 관심종목 삭제
- 관심종목 태그 설정
- 메모 작성
- 관심종목 분석 대상 포함 여부 설정

## 6.2.3 필드

| 필드 | 설명 |
|---|---|
| symbol | 종목코드 |
| name | 종목명 |
| market | KOSPI/KOSDAQ/NASDAQ 등 |
| tags | 반도체, AI, 방산 등 |
| memo | 사용자 메모 |
| is_active | 분석 여부 |

---

# 6.3 보유종목 관리 기능

## 6.3.1 목적

사용자가 실제 보유한 종목을 장전/장후로 점검하기 위해 관리한다.

## 6.3.2 기능

- 보유 종목 입력
- 평균 매수가 입력
- 수량 입력
- 매수일 입력
- 전략 구분 입력: 장기/중기/단기
- 목표가, 손절가 입력
- 보유 메모 입력
- 한국투자증권 API 잔고 연동은 v0.2 이후 확장 가능

## 6.3.3 필드

| 필드 | 설명 |
|---|---|
| symbol | 종목코드 |
| quantity | 보유 수량 |
| avg_buy_price | 평균 매수가 |
| buy_date | 매수일 |
| strategy_type | 장기/중기/단기 |
| target_price | 목표가 |
| stop_loss_price | 손절가 |
| memo | 메모 |
| is_active | 보유 여부 |

---

# 6.4 데이터 수집 기능

## 6.4.1 한국투자증권 API 데이터

### 수집 대상

| 데이터 | 용도 |
|---|---|
| 현재가 | 보유 수익률, 장전/장후 점검 |
| 일봉 OHLCV | 기술적 지표 계산 |
| 거래량/거래대금 | 유동성, 거래량 분석 |
| 시가총액 순위 | TOP 500 유니버스 생성 |
| 해외 주요 지수 | 미국장 참고 |
| 환율 | 시장 국면 판단 |

## 6.4.2 뉴스 데이터

v0.1에서는 뉴스 전문 저장보다 아래 정보 중심으로 저장한다.

| 데이터 | 설명 |
|---|---|
| title | 뉴스 제목 |
| url | 원문 링크 |
| source | 출처 |
| published_at | 발행 시각 |
| related_symbols | 관련 종목 |
| theme | 관련 테마 |
| sentiment | 긍정/중립/부정 |
| importance | 중요도 |

## 6.4.3 공시 데이터

DART 연동은 v0.1에서 간단 수집, v0.2 이후 강화한다.

| 데이터 | 설명 |
|---|---|
| 공시 제목 | 공시명 |
| 공시 시간 | published_at |
| 종목코드 | symbol |
| 공시 유형 | 실적, 수주, 증자, 소송 등 |
| 중요도 | importance |
| 리스크 수준 | risk_level |

---

# 6.5 기술적 분석 기능

## 6.5.1 목적

종목 추천과 보유 점검에 필요한 정량 지표를 자체 프로그램이 계산한다.

## 6.5.2 지표 목록

| 지표 | 설명 |
|---|---|
| MA5 | 5일 이동평균 |
| MA20 | 20일 이동평균 |
| MA60 | 60일 이동평균 |
| MA120 | 120일 이동평균 |
| RSI14 | 14일 RSI |
| MACD | MACD 값 |
| MACD Signal | 신호선 |
| Volume Ratio 20D | 20일 평균 대비 거래량 비율 |
| Trading Value Ratio | 거래대금 증가율 |
| 20D High Breakout | 20일 신고가 돌파 여부 |
| 60D High Breakout | 60일 신고가 돌파 여부 |
| 52W High Breakout | 52주 신고가 돌파 여부 |
| Candle Pattern | 장대양봉, 장대음봉, 윗꼬리 등 |

## 6.5.3 기술 점수 예시

기술 점수는 100점 만점으로 계산한다.

| 항목 | 배점 |
|---|---:|
| 이동평균 추세 | 25 |
| 거래량/거래대금 | 20 |
| 돌파 신호 | 20 |
| 모멘텀 지표 | 15 |
| 캔들 패턴 | 10 |
| 변동성/리스크 | 10 |

## 6.5.4 이동평균 점수 예시

| 조건 | 점수 |
|---|---:|
| 5일선 > 20일선 > 60일선 | +25 |
| 현재가 > 20일선 > 60일선 | +20 |
| 현재가가 20일선 회복 | +15 |
| 현재가 < 20일선 | -10 |
| 20일선 < 60일선 | -15 |

## 6.5.5 거래량 점수 예시

| 조건 | 점수 |
|---|---:|
| 20일 평균 대비 300% 이상 | +20 |
| 200% 이상 | +15 |
| 150% 이상 | +10 |
| 100% 이하 | 0 |
| 하락일 거래량 급증 | -10 |

---

# 6.6 시장 국면 판단 기능

## 6.6.1 목적

현재 시장이 상승장, 횡보장, 하락장, 테마장, 급락장 중 어디에 가까운지 판단한다.

## 6.6.2 v0.1 방식

v0.1에서는 전용 AI 모델이 아니라 **룰 기반 시장 점수**로 시작한다.

## 6.6.3 시장 국면 종류

| 국면 | 설명 |
|---|---|
| 상승장 | 지수 상승 추세, 상승 종목 증가 |
| 상승장 초기 | 20일선 회복, 거래대금 증가 |
| 과열장 | 상승은 강하지만 추격 위험 큼 |
| 횡보장 | 박스권 등락, 방향성 부족 |
| 하락장 | 지수 하락 추세, 신규 매수 위험 |
| 급락장 | 급격한 하락, 자동매수 중지 필요 |
| 테마장 | 특정 섹터만 강한 장세 |
| 변동성 장세 | 위아래 흔들림이 큰 장세 |

## 6.6.4 시장 점수 산식

```text
시장 점수 =
지수 추세 25%
+ 시장 폭 15%
+ 거래대금 15%
+ 수급 15%
+ 미국장 영향 15%
+ 뉴스/매크로 리스크 15%
```

## 6.6.5 점수 해석

| 점수 | 판단 |
|---:|---|
| 80~100 | 강한 상승장 |
| 65~79 | 상승장 |
| 50~64 | 횡보/중립 |
| 35~49 | 약세장 |
| 0~34 | 하락/위험장 |

---

# 6.7 신규 추천 기능

## 6.7.1 목적

매일 오전 6시에 한국 주식 중심 신규 추천 후보를 생성한다.

## 6.7.2 추천 대상

v0.1 기본 대상:

1. 시가총액 TOP 500
2. 관심종목
3. 보유종목은 별도 점검 대상으로 우선 처리

## 6.7.3 추천 후보 생성 흐름

```text
시가총액 TOP 500
↓
관리종목/거래정지 제외
↓
거래대금 부족 종목 제외
↓
기술 점수 계산
↓
뉴스/테마 점수 계산
↓
수급/실적 점수 반영
↓
1차 후보 30개 선정
↓
AI 판단/근거 작성
↓
추천 TOP 5~10 생성
↓
DB 저장
↓
텔레그램 발송
```

## 6.7.4 추천 점수 산식

```text
신규 추천 점수 =
기술 점수 35%
+ 뉴스/테마 점수 25%
+ 수급 점수 15%
+ 실적/재무 점수 15%
+ AI 판단 점수 10%
- 리스크 감점
```

## 6.7.5 추천 등급

| 등급 | 의미 |
|---|---|
| S | 강한 관찰 후보 |
| A | 매수 검토 후보 |
| B | 관심 유지 후보 |
| C | 조건 부족 |
| D | 제외 |

## 6.7.6 추천 결과 필드

| 필드 | 설명 |
|---|---|
| rank | 추천 순위 |
| symbol | 종목코드 |
| name | 종목명 |
| grade | S/A/B/C/D |
| total_score | 종합 점수 |
| technical_score | 기술 점수 |
| news_score | 뉴스 점수 |
| fundamental_score | 실적/재무 점수 |
| ai_score | AI 점수 |
| risk_score | 리스크 점수 |
| reason | 추천 사유 |
| watch_condition | 관찰 조건 |
| invalid_condition | 제외 조건 |
| risk_note | 리스크 설명 |

---

# 6.8 보유 종목 장전/장후 점검 기능

## 6.8.1 목적

사용자가 매수한 종목을 매일 두 번 점검하여 보유 유지, 주의, 비중 축소, 매도 검토 판단을 보조한다.

## 6.8.2 실행 시점

| 점검 | 시간 | 목적 |
|---|---|---|
| 장전 점검 | 08:30~08:50 | 당일 대응 시나리오 |
| 장후 점검 | 16:00~17:00 | 당일 흐름 복기 및 다음날 대응 |

## 6.8.3 보유 종목 점수 산식

```text
보유 종목 점수 =
기술 점수 35%
+ 뉴스/공시 점수 20%
+ 실적/재무 점수 20%
+ AI 판단 점수 15%
+ 수익 관리 점수 10%
- 리스크 감점
```

## 6.8.4 보유 판단 등급

| 점수 | 등급 | 판단 |
|---:|---|---|
| 85~100 | S | 강한 보유 |
| 70~84 | A | 보유 유지 |
| 55~69 | B | 관찰 필요 |
| 40~54 | C | 주의 구간 |
| 0~39 | D | 매도 검토 |

## 6.8.5 판단 문구

| 판단 | 의미 |
|---|---|
| 강한 보유 | 추세와 근거가 강함 |
| 보유 유지 | 특별한 훼손 없음 |
| 관찰 필요 | 일부 리스크 존재 |
| 비중 축소 검토 | 점수 하락 또는 추세 약화 |
| 매도 검토 | 주요 조건 훼손 |
| 신규 매수 금지 | 보유는 가능하지만 추가 매수 위험 |
| 손절 기준 접근 | 손절가 또는 주요 지지선 근접 |
| 익절 기준 접근 | 목표가 또는 과열 구간 접근 |

## 6.8.6 장전 리포트 예시

```text
[보유 종목 장전 점검] 2026-05-05 08:40

1. 삼성전자 / A등급 / 73점
- 수익률: +4.8%
- 판단: 보유 유지
- 체크: 20일선 유지 여부
- 주의: 단기 저항선 근접

2. SK하이닉스 / S등급 / 86점
- 수익률: +9.2%
- 판단: 강한 보유
- 체크: 갭상승 후 거래량 유지
- 주의: RSI 과열권 진입
```

## 6.8.7 장후 리포트 예시

```text
[보유 종목 장후 점검] 2026-05-05 16:30

오늘 보유 종목 요약

1. 삼성전자 / A → A / 73점 → 75점
- 종가 상승, 20일선 유지
- 거래량 보통
- 판단: 보유 유지

2. 한미반도체 / B → C / 61점 → 49점
- 20일선 이탈
- 거래량 동반 하락
- 판단: 비중 축소 검토
```

---

# 6.9 추천 성과 검증 기능

## 6.9.1 목적

추천 종목의 실제 성과를 추적하여 추천 품질을 검증한다.

## 6.9.2 검증 기간

| 기간 | 용도 |
|---|---|
| 1일 후 | 단기 반응 |
| 3일 후 | 단기 추세 |
| 5일 후 | 주간 성과 |
| 20일 후 | 스윙 성과 |

## 6.9.3 검증 항목

| 항목 | 설명 |
|---|---|
| open_return | 시가 기준 수익률 |
| high_return | 고가 기준 수익률 |
| low_return | 저가 기준 하락률 |
| close_return | 종가 기준 수익률 |
| max_return | 추천 후 최대 상승률 |
| max_drawdown | 추천 후 최대 하락률 |
| result_status | 성공/실패/보류 |

## 6.9.4 성공 기준 예시

v0.1에서는 단순 기준으로 시작한다.

| 기준 | 판단 |
|---|---|
| 5일 내 고가 +3% 이상 | 성공 |
| 5일 내 종가 +1% 이상 | 부분 성공 |
| 5일 내 -5% 이상 하락 | 실패 |
| 데이터 부족 | 보류 |

---

# 6.10 텔레그램 알림 기능

## 6.10.1 알림 종류

| 알림 | 시간 |
|---|---|
| 신규 추천 리포트 | 06:00 |
| 보유 종목 장전 점검 | 08:30 |
| 보유 종목 장후 점검 | 16:30 |
| 위험 경고 | 조건 발생 시 |
| 시스템 오류 | 작업 실패 시 |

## 6.10.2 신규 추천 리포트 예시

```text
[AI 주식 리포트] 2026-05-05 06:00

오늘의 시장 요약
- 시장 국면: 상승장 초기
- 미국 반도체주 강세
- 환율 안정
- 관심 테마: 반도체, 전력기기, 방산

한국 주식 관찰 후보 TOP 5

1. SK하이닉스 / S등급 / 87점
- 근거: HBM 뉴스 증가, 거래량 20일 평균 대비 165%
- 관찰: 시초가 갭상승 후 눌림 여부
- 리스크: 단기 과열

2. 한미반도체 / A등급 / 82점
- 근거: HBM 장비 테마 지속
- 관찰: 전고점 돌파 여부
- 리스크: 변동성 큼

자세한 내용은 PC 대시보드에서 확인
```

## 6.10.3 위험 경고 조건

| 조건 | 알림 |
|---|---|
| 보유 종목 점수 15점 이상 하락 | 즉시 |
| 20일선 이탈 | 즉시 |
| 악재 뉴스 발생 | 즉시 또는 장후 |
| 시장 급락장 전환 | 즉시 |
| 손절 기준 접근 | 즉시 |
| 데이터 수집 실패 | 시스템 알림 |

---

# 6.11 PC 대시보드 기능

## 6.11.1 v0.1 메뉴

```text
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
```

## 6.11.2 오늘의 리포트 화면

목적: 오늘 시장, 추천 종목, 보유 종목 경고를 한눈에 본다.

구성:

- 시장 국면 카드
- 시장 위험도 카드
- 주요 지수/환율 카드
- 오늘 추천 TOP 5
- 보유 종목 경고
- 주요 뉴스/테마
- 시스템 실행 상태

## 6.11.3 보유 종목 점검 화면

| 종목 | 수익률 | 종합점수 | 등급 | 판단 | 전일 대비 | 경고 |
|---|---:|---:|---|---|---:|---|
| 삼성전자 | +4.8% | 75 | A | 보유 유지 | +2 | 없음 |
| SK하이닉스 | +9.2% | 81 | A | 보유 유지 | -5 | 과열 |
| 한미반도체 | -2.1% | 49 | C | 비중 축소 검토 | -12 | 20일선 이탈 |

## 6.11.4 추천 종목 화면

| 순위 | 종목 | 시장 | 등급 | 종합점수 | 기술 | 뉴스 | 수급 | 리스크 | 판단 |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | SK하이닉스 | KOSPI | S | 87 | 86 | 90 | 78 | 낮음 | 관찰 후보 |
| 2 | 한미반도체 | KOSDAQ | A | 82 | 84 | 88 | 70 | 중간 | 매수 검토 |

## 6.11.5 추천 이력 화면

| 날짜 | 추천 수 | 평균 1일 수익률 | 평균 5일 수익률 | 성공률 | 시장 국면 |
|---|---:|---:|---:|---:|---|
| 2026-05-05 | 10 | +1.2% | +3.8% | 70% | 상승장 |
| 2026-05-04 | 10 | -0.4% | +0.6% | 45% | 횡보장 |

## 6.11.6 종목 상세 화면

구성:

- 종목명/코드/현재가/등락률/시가총액/거래대금
- 내 보유 정보: 평균단가, 수량, 수익률, 투자금
- 점수 카드: 종합, 기술, 뉴스, 실적, AI, 리스크
- 일봉 차트 + 이동평균선 + 거래량
- 기술적 분석: RSI, MACD, 거래량, 돌파 여부
- 뉴스/공시 목록
- AI 판단 근거
- 과거 추천 이력과 성과

## 6.11.7 시가총액 TOP 500 화면

| 순위 | 종목 | 시장 | 시가총액 | 등락률 | 거래대금 | 기술점수 | 뉴스점수 | 분석대상 |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | 삼성전자 | KOSPI | 000조 | +0.8% | 000억 | 72 | 65 | ON |

필터:

- 코스피/코스닥
- 섹터
- 시총 순위
- 거래대금
- 기술점수
- 뉴스점수
- 분석대상 ON/OFF

## 6.11.8 시장 국면 화면

| 항목 | 값 |
|---|---|
| 코스피 국면 | 상승장 초기 |
| 코스닥 국면 | 테마장 |
| 시장 점수 | 72 |
| 위험도 | 중간 |
| 상승 종목 비율 | 61% |
| 거래대금 변화 | +18% |
| 외국인 수급 | 순매수 |
| 미국장 영향 | 긍정 |
| 환율 영향 | 중립 |

## 6.11.9 시스템 로그 화면

| 작업 | 실행 시간 | 상태 | 결과 |
|---|---|---|---|
| 한국장 마감 데이터 수집 | 18:00 | 성공 | 500종목 |
| 기술 지표 계산 | 18:30 | 성공 | 500종목 |
| 뉴스 수집 | 19:00 | 일부 실패 | 23건 실패 |
| 추천 리포트 생성 | 06:00 | 성공 | 발송 완료 |

---

## 7. 확장 기능 명세

---

# 7.1 전략 관리 기능 v0.2+

## 목적

장기/중기/단기 전략을 분리하고 시장 국면별로 적합한 전략을 선택한다.

## 전략 카테고리

| 카테고리 | 목적 | 보유 기간 |
|---|---|---:|
| 장기 | 기업 성장성 중심 | 6개월~수년 |
| 중기 | 추세·실적·테마 중심 | 수주~수개월 |
| 단기 | 모멘텀·수급 중심 | 당일~수일 |
| 리스크 관리 | 보유 종목 방어 | 상시 |

## 전략 예시

| 전략명 | 유형 | 설명 |
|---|---|---|
| 장기 성장주 분할매수 | 장기 | 실적 성장주 눌림 매수 |
| 중기 추세추종 | 중기 | 20일/60일선 추세 회복 |
| 주도 테마 추적 | 중기 | 뉴스·거래대금 집중 테마 |
| 박스권 스윙 | 중기 | 지지선 매수, 저항선 매도 |
| 단기 거래량 돌파 | 단기 | 거래량 급증 + 전고점 돌파 |
| 리스크 오프 | 방어 | 하락장 신규매수 중지 |

---

# 7.2 자동매매 운용 모드 v0.2+

| 모드 | 설명 |
|---|---|
| SIGNAL | 신호만 생성 |
| PAPER | 가상매매 |
| APPROVAL | 주문 전 사용자 승인 |
| SMALL_AUTO | 소액 자동매매 |
| FULL_AUTO | 완전 자동매매 |

초기 권장 순서:

```text
SIGNAL → PAPER → APPROVAL → SMALL_AUTO
```

`FULL_AUTO`는 기본 비활성화한다.

---

# 7.3 백테스트/자동 튜닝 v0.3+

## 기능

- 전략 템플릿 선택
- 파라미터 범위 설정
- 대량 백테스트 실행
- 성과 지표 계산
- 과최적화 검증
- 최적 파라미터 후보 선정
- 가상매매 적용

## 평가 지표

| 지표 | 설명 |
|---|---|
| 총수익률 | 전체 수익률 |
| 연수익률 | 연환산 수익률 |
| MDD | 최대 낙폭 |
| 승률 | 성공 거래 비율 |
| 손익비 | 평균 이익/평균 손실 |
| Profit Factor | 총이익/총손실 |
| 거래 수 | 통계 신뢰도 |
| 평균 보유일 | 전략 성격 파악 |

## 전략 평가 점수

```text
전략 평가 점수 =
연평균 수익률 점수 30%
+ MDD 안정성 점수 25%
+ 손익비 점수 20%
+ 승률 점수 10%
+ 거래수 신뢰도 점수 10%
+ 시장국면 적합도 5%
```

---

# 7.4 가상 증권사 서버 v0.4+

## 목적

실제 한국투자증권 API에 붙이기 전에 로컬 PC에서 주문/체결/잔고/가상시장/가상뉴스를 테스트한다.

## 구성

```text
Mock Broker API
├─ 가상 인증
├─ 가상 현재가
├─ 가상 일봉/분봉
├─ 주문 접수
├─ 체결 처리
├─ 잔고 조회
├─ 주문 내역
└─ 체결 내역
```

## Broker 종류

| Broker | 역할 |
|---|---|
| KisBroker | 실제 한국투자증권 API |
| MockBroker | 단순 가상 증권사 |
| ReplayBroker | 과거 데이터 리플레이 |
| SimulationBroker | 가상 시장 생성 |

---

# 7.5 전용 AI 모델 v0.5+

## 목적

LLM이 아니라 프로젝트 전용 머신러닝 모델로 시장 국면과 전략 선택을 판단한다.

## 모델 종류

| 모델 | 역할 |
|---|---|
| Market Regime Model | 시장 국면 판단 |
| Strategy Selection Model | 전략 자동 선택 |
| Risk Prediction Model | 급락/손실 위험 예측 |
| Stock Scoring Model | 종목 점수 보정 |
| News Impact Model | 뉴스 영향 점수화 |
| Performance Feedback Model | 추천/전략 성과 반영 |
| LLM Report Agent | 설명과 리포트 작성 |

## 권장 순서

```text
룰 기반 시장 판단
→ LightGBM/XGBoost 기반 국면 모델
→ 전략별 성과 예측 모델
→ 리스크 예측 모델
→ LLM 리포트 엔진과 결합
```

---

## 8. 핵심 인터페이스 명세

### 8.1 BrokerInterface

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

    def get_trade_history(self, start_date: str, end_date: str):
        pass
```

### 8.2 AIProviderInterface

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

### 8.3 StrategyInterface

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

### 8.4 DataProviderInterface

```python
class DataProviderInterface:
    def fetch_daily_prices(self, symbols, date):
        pass

    def fetch_news(self, query, start_time, end_time):
        pass

    def fetch_disclosures(self, symbols, date):
        pass

    def fetch_macro_data(self, date):
        pass
```

---

## 9. 데이터베이스 상세 명세

### 9.1 stocks

| 컬럼 | 타입 예시 | 설명 |
|---|---|---|
| id | integer | 내부 ID |
| market | text | KRX/NASDAQ/NYSE |
| symbol | text | 종목코드 |
| name | text | 종목명 |
| sector | text | 업종 |
| theme_tags | json/text | 테마 태그 |
| is_active | boolean | 분석 대상 여부 |
| created_at | datetime | 생성일 |
| updated_at | datetime | 수정일 |

### 9.2 market_cap_rankings

| 컬럼 | 타입 예시 | 설명 |
|---|---|---|
| rank_date | date | 기준일 |
| market | text | KOSPI/KOSDAQ/ALL |
| rank | integer | 시가총액 순위 |
| symbol | text | 종목코드 |
| name | text | 종목명 |
| market_cap | numeric | 시가총액 |
| close_price | numeric | 종가 |
| listed_shares | numeric | 상장주식수 |
| sector | text | 업종 |
| trading_value | numeric | 거래대금 |
| is_analysis_target | boolean | 분석 대상 여부 |

### 9.3 stock_universes

| 컬럼 | 설명 |
|---|---|
| universe_id | 유니버스 ID |
| name | MARKET_CAP_TOP_500 등 |
| description | 설명 |
| is_active | 사용 여부 |
| created_at | 생성일 |

### 9.4 stock_universe_members

| 컬럼 | 설명 |
|---|---|
| universe_id | 유니버스 ID |
| symbol | 종목코드 |
| added_at | 편입일 |
| removed_at | 제외일 |
| reason | 편입/제외 이유 |

### 9.5 daily_prices

| 컬럼 | 설명 |
|---|---|
| date | 날짜 |
| symbol | 종목코드 |
| open | 시가 |
| high | 고가 |
| low | 저가 |
| close | 종가 |
| volume | 거래량 |
| trading_value | 거래대금 |
| adjusted_close | 수정주가, 선택 |

### 9.6 stock_indicators

| 컬럼 | 설명 |
|---|---|
| date | 날짜 |
| symbol | 종목코드 |
| ma5 | 5일선 |
| ma20 | 20일선 |
| ma60 | 60일선 |
| ma120 | 120일선 |
| rsi14 | RSI |
| macd | MACD |
| macd_signal | MACD 신호선 |
| volume_ratio_20d | 20일 평균 대비 거래량 |
| breakout_20d | 20일 신고가 돌파 |
| breakout_60d | 60일 신고가 돌파 |
| technical_score | 기술 점수 |

### 9.7 news_items

| 컬럼 | 설명 |
|---|---|
| id | 뉴스 ID |
| published_at | 발행 시간 |
| available_at | 시스템 사용 가능 시간 |
| source | 출처 |
| title | 제목 |
| url | 링크 |
| related_symbols | 관련 종목 |
| sentiment | 긍정/중립/부정 |
| importance | 중요도 |
| theme | 테마 |
| summary | 요약 |

### 9.8 disclosures

| 컬럼 | 설명 |
|---|---|
| id | 공시 ID |
| published_at | 공시 시간 |
| available_at | 사용 가능 시간 |
| symbol | 종목코드 |
| title | 공시 제목 |
| disclosure_type | 실적/수주/증자/소송 등 |
| importance | 중요도 |
| risk_level | 리스크 |
| url | 링크 |

### 9.9 market_regimes

| 컬럼 | 설명 |
|---|---|
| date | 날짜 |
| market | KOSPI/KOSDAQ/NASDAQ |
| regime | 상승/횡보/하락/테마/급락 |
| market_score | 시장 점수 |
| risk_level | LOW/MID/HIGH |
| trend_score | 추세 점수 |
| breadth_score | 시장 폭 점수 |
| liquidity_score | 거래대금 점수 |
| global_score | 미국장 영향 점수 |
| reason | 판단 근거 |

### 9.10 recommendation_runs

| 컬럼 | 설명 |
|---|---|
| run_id | 추천 실행 ID |
| run_date | 추천 날짜 |
| started_at | 시작 시간 |
| finished_at | 종료 시간 |
| market_summary | 시장 요약 |
| status | 성공/실패 |
| telegram_sent | 발송 여부 |

### 9.11 recommendations

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
| fundamental_score | 실적 점수 |
| ai_score | AI 점수 |
| risk_score | 리스크 점수 |
| reason | 추천 사유 |
| watch_condition | 관찰 조건 |
| invalid_condition | 제외 조건 |
| risk_note | 리스크 설명 |
| snapshot_id | 데이터 스냅샷 ID |

### 9.12 recommendation_results

| 컬럼 | 설명 |
|---|---|
| recommendation_id | 추천 ID |
| result_date | 검증 날짜 |
| days_after | 1/3/5/20 |
| open_return | 시가 기준 수익률 |
| high_return | 고가 기준 수익률 |
| low_return | 저가 기준 하락률 |
| close_return | 종가 기준 수익률 |
| max_return | 최대 상승률 |
| max_drawdown | 최대 하락률 |
| result_status | 성공/실패/보류 |

### 9.13 holdings

| 컬럼 | 설명 |
|---|---|
| id | 보유 ID |
| symbol | 종목코드 |
| quantity | 보유 수량 |
| avg_buy_price | 평균 매수가 |
| buy_date | 매수일 |
| strategy_type | 장기/중기/단기 |
| target_price | 목표가 |
| stop_loss_price | 손절가 |
| memo | 메모 |
| is_active | 보유 여부 |

### 9.14 holding_checks

| 컬럼 | 설명 |
|---|---|
| id | 점검 ID |
| check_date | 날짜 |
| check_type | 장전/장후 |
| symbol | 종목코드 |
| current_price | 현재가 |
| return_rate | 수익률 |
| technical_score | 기술 점수 |
| news_score | 뉴스 점수 |
| earnings_score | 실적 점수 |
| ai_score | AI 점수 |
| risk_score | 리스크 점수 |
| total_score | 종합 점수 |
| grade | S/A/B/C/D |
| decision | 보유/주의/축소/매도검토 |
| reason | 판단 근거 |
| watch_condition | 유지 조건 |
| exit_condition | 이탈 조건 |
| snapshot_id | 스냅샷 ID |

### 9.15 data_snapshots

| 컬럼 | 설명 |
|---|---|
| snapshot_id | 스냅샷 ID |
| snapshot_time | 생성 시간 |
| symbol | 종목코드 |
| price_data_json | 가격 데이터 |
| indicator_data_json | 지표 데이터 |
| news_data_json | 뉴스 데이터 |
| market_context_json | 시장 컨텍스트 |
| created_at | 생성일 |

### 9.16 decision_logs

| 컬럼 | 설명 |
|---|---|
| decision_id | 판단 ID |
| decision_type | 추천/보유점검/전략신호 |
| symbol | 종목코드 |
| input_snapshot_id | 입력 스냅샷 |
| rule_result_json | 룰 결과 |
| ai_result_json | AI 결과 |
| risk_result_json | 리스크 결과 |
| final_decision | 최종 판단 |
| reason | 판단 근거 |
| created_at | 생성일 |

### 9.17 job_runs

| 컬럼 | 설명 |
|---|---|
| job_id | 작업 ID |
| job_name | 작업명 |
| started_at | 시작 시간 |
| finished_at | 종료 시간 |
| status | 성공/실패/부분성공 |
| error_message | 오류 메시지 |
| result_summary | 결과 요약 |

---

## 10. 일일 스케줄 명세

### 10.1 v0.1 스케줄

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

### 10.2 실패 처리

작업 실패 시 전체 시스템을 중단하지 않는다.

예:

```text
주가/기술 분석 성공
뉴스 분석 실패
→ 뉴스 점수 제외하고 리포트 생성
→ 텔레그램에 “뉴스 수집 실패” 표시
→ job_runs에 부분 실패 기록
```

재시도 정책:

1. 1차 실패 시 1회 재시도
2. 2차 실패 시 부분 결과 생성
3. 심각한 실패는 텔레그램 시스템 경고 발송

---

## 11. 리스크 관리 원칙

### 11.1 기본 원칙

1. AI 단독 주문 금지
2. v0.1 실거래 주문 금지
3. 손실 제한 우선
4. 종목당 한도 적용
5. 전략별 자금 한도 적용
6. 시장 급락 시 신규 매수 차단
7. 악재 뉴스 발생 시 매수 차단
8. 모든 판단 로그 저장
9. 모든 추천 스냅샷 저장
10. 실거래 전 비상정지 구현 필수

### 11.2 향후 자동매매 리스크 조건

| 조건 | 조치 |
|---|---|
| 시장 급락장 | 신규 매수 중지 |
| 보유 종목 20일선 이탈 | 경고/축소 검토 |
| 악재 뉴스 발생 | 신규 매수 차단 |
| 일일 손실 한도 초과 | 전략 중지 |
| 3회 연속 손실 | 전략 자동 정지 |
| API 오류 발생 | 주문 차단 |
| 주문 중복 감지 | 주문 차단 |

---

## 12. AI 사용 원칙

### 12.1 v0.1 AI 역할

| 역할 | 사용 여부 |
|---|---|
| 뉴스 요약 | 사용 |
| 추천 근거 작성 | 사용 |
| 리스크 설명 | 사용 |
| 텔레그램 문장 생성 | 사용 |
| 시장 국면 판단 | 룰 기반 우선 |
| 전략 자동 선택 | v0.2 이후 |
| 자동매매 판단 | v0.3 이후 |
| 전용 AI 모델 | v0.5 이후 |

### 12.2 AI 판단 제한

AI는 아래 작업을 직접 수행하지 않는다.

- 실거래 주문
- 자금 비중 최종 결정
- 손절 기준 무시
- 리스크 엔진 우회
- 데이터 계산

### 12.3 권장 구조

```text
정량 점수: 자체 프로그램
뉴스/근거 해석: LLM
시장 국면: 룰 기반 → 전용 AI 모델
전략 선택: 룰 + 전용 모델
주문 허용: RiskEngine
```

---

## 13. v0.1 개발 우선순위

### 13.1 1차 개발

1. 프로젝트 기본 구조 생성
2. DB 모델 생성
3. 환경 설정 관리
4. 한국투자증권 API 인증/기본 조회
5. 종목 기본정보 저장
6. 시가총액 TOP 500 저장
7. 일봉 데이터 저장
8. 기술 지표 계산

### 13.2 2차 개발

1. 보유 종목 관리
2. 보유 종목 장후 점검
3. 보유 종목 장전 점검
4. 텔레그램 알림
5. job_runs 로그 저장

### 13.3 3차 개발

1. 뉴스 수집
2. 뉴스 요약/점수화
3. 신규 추천 후보 생성
4. 추천 이력 저장
5. 추천 성과 검증

### 13.4 4차 개발

1. PC 대시보드 기본
2. 오늘의 리포트 화면
3. 보유 종목 점검 화면
4. 추천 종목/추천 이력 화면
5. 종목 상세 화면
6. 시스템 로그 화면

---

## 14. v0.1 완료 기준

| 기준 | 목표 |
|---|---|
| 데이터 수집 | 매일 정상 수집 |
| 기술 지표 계산 | TOP 500 대상 계산 가능 |
| 보유 점검 | 장전/장후 리포트 생성 |
| 신규 추천 | 매일 오전 6시 추천 생성 |
| 텔레그램 | 정상 발송 |
| 추천 이력 | 날짜별 저장 및 조회 가능 |
| 추천 성과 | 1/3/5/20일 후 자동 계산 |
| PC 대시보드 | 주요 화면 조회 가능 |
| 로그 | 작업 성공/실패 확인 가능 |

v0.1의 성공 기준에는 수익률을 넣지 않는다.  
v0.1의 성공 기준은 **시스템이 안정적으로 동작하고 데이터가 누적되는 것**이다.

---

## 15. Codex 개발 지침

### 15.1 구현 시 우선순위

1. 작게 동작하는 코드를 먼저 만든다.
2. 실거래 주문은 절대 구현하지 않는다.
3. BrokerInterface는 처음부터 만든다.
4. 실제 KisBroker는 조회 기능부터 구현한다.
5. MockBroker는 주문 기능 확장 대비용으로 빈 구조를 만든다.
6. 모든 자동 실행 작업은 job_runs에 기록한다.
7. 추천/보유 판단은 data_snapshots와 decision_logs에 연결한다.
8. 모든 외부 API 키는 .env에서 읽는다.
9. API 키와 계좌 정보는 로그에 남기지 않는다.
10. 테스트 가능한 함수 단위로 구현한다.

### 15.2 금지 사항

- 분석 코드 안에서 직접 주문 실행 금지
- AI 응답만으로 점수 전체 결정 금지
- 뉴스 전문을 무단 저장하는 구조 금지
- 추천 당시 스냅샷 없이 추천 저장 금지
- 백테스트에 미래 데이터 사용 금지
- v0.1에서 실거래 자동매매 구현 금지

---

## 16. 향후 로드맵 요약

| 버전 | 핵심 |
|---|---|
| v0.1 | 데이터 수집 + 보유 점검 + 추천 리포트 |
| v0.2 | 기본 백테스트 + 가상매매 + 전략 관리 |
| v0.3 | 전략 자동 튜닝 + Walk-forward 검증 |
| v0.4 | MockBroker + ReplayBroker + 가상 증권사 서버 |
| v0.5 | 시장 국면 전용 AI 모델 + 전략 선택 모델 |
| v1.0 | 주문 승인 모드 + 소액 자동매매 |

---

## 17. 최종 설계 결론

이 프로젝트는 다음 순서로 확장한다.

```text
데이터 수집
→ 기술적 분석
→ 보유 종목 점검
→ 신규 추천 리포트
→ 추천 성과 검증
→ 전략 관리
→ 가상매매
→ 백테스트/자동 튜닝
→ 가상 증권사 서버
→ 전용 AI 모델
→ 소액 자동매매
```

최종 목표는 단순 종목 추천 앱이 아니라,

**한국 주식 중심 AI 투자 분석·전략 검증·가상매매·자동매매 연구 플랫폼**이다.

