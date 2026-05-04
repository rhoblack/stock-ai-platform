# TESTING.md

## 1. 테스트 목표

v0.1의 목표는 실거래 없는 안정적인 분석/추천/보유점검 시스템이다.

테스트의 핵심은 다음이다.

- 지표 계산 정확성
- 점수 계산 일관성
- 추천/보유 판단 저장
- snapshot/log 저장
- 외부 API mock 처리
- 텔레그램 메시지 포맷
- FastAPI 조회 API
- v0.1 범위 위반 방지

## 2. 테스트 도구

- pytest
- pytest-asyncio 필요 시
- httpx TestClient
- respx 또는 responses
- SQLite test DB 또는 PostgreSQL test DB

## 3. 테스트 폴더 구조

```text
tests/
├─ unit/
│  ├─ test_technical_analyzer.py
│  ├─ test_scoring_engine.py
│  ├─ test_recommendation_engine.py
│  ├─ test_holding_check_engine.py
│  └─ test_report_generator.py
├─ integration/
│  ├─ test_repositories.py
│  ├─ test_api_routes.py
│  └─ test_scheduler_jobs.py
└─ mocks/
   ├─ kis_responses.py
   └─ sample_market_data.py
```

## 4. 필수 테스트

### TechnicalAnalyzer

- MA 계산
- RSI 계산
- MACD 계산
- volume_ratio_20d 계산
- breakout 계산
- 데이터 부족 시 처리

### ScoringEngine

- 신규 추천 점수 공식
- 보유 종목 점수 공식
- risk_penalty 반영
- AI 점수 비중 제한

### RecommendationEngine

- 시총 TOP 500 필터링
- 위험 종목 제외
- TOP 5 생성
- recommendations 저장
- data_snapshots 생성
- decision_logs 생성

### HoldingCheckEngine

- 수익률 계산
- 장전/장후 점검 생성
- 점수 급락 경고
- 20일선 이탈 경고
- holding_checks 저장

### ReportGenerator

- 추천 리포트 포맷
- 장전 점검 포맷
- 장후 점검 포맷
- 위험 경고 포맷

### KIS Client

- 외부 API mock
- 인증 실패 처리
- 재시도 처리
- 응답 정규화

### Backend API

- 주요 GET API 응답
- schema 검증
- 없는 데이터 처리
- 페이지네이션/필터 기초

## 5. 금지 사항

테스트에서 금지:

- 실제 KIS API 호출
- 실제 텔레그램 발송
- 실제 계좌번호 사용
- 실제 주문 API 호출
- 실거래 관련 테스트 구현

## 6. 테스트 실행 명령 예시

```powershell
.\.venv\bin\python.exe -m pytest
.\.venv\bin\python.exe -m pytest tests/unit
.\.venv\bin\python.exe -m pytest tests/integration
```

DB/Repository 테스트는 SQLite 메모리 DB를 사용한다. 실제 KIS API, 텔레그램,
주문 API는 호출하지 않는다.

Phase 2 DB 테스트는 다음을 확인한다.

- v0.1 필수 테이블 생성
- Repository 저장/조회
- `daily_prices`의 `symbol + date` upsert
- `stock_universe_members`의 `universe_id + symbol` 중복 방지
- recommendation run/result/snapshot 관계
- holding check/decision log/snapshot 관계
- notification log/job run 관계

Phase 3-1 KIS/Data 테스트는 실제 KIS API를 호출하지 않고 mock 응답만 사용한다.

- KIS 현재가/일봉/시가총액 응답 normalizer
- DataQualityChecker의 중복/누락/이상값 감지
- 실제 API 키, 계좌번호, 토큰 사용 금지

Phase 3-2 KIS HTTP 구조 테스트도 실제 KIS API를 호출하지 않고 `httpx.MockTransport`
기반 mock 응답만 사용한다.

- `KisClient` 토큰 발급, 현재가, 일봉, 시가총액 상위 조회 request shape
- KIS API 오류 코드, HTTP 오류, timeout, JSON/응답 형식 오류 처리
- app key, app secret, bearer token 로그 마스킹
- 주문 API, 자동매매, 추천 로직, 기술 지표 계산, 텔레그램 발송 테스트 금지

## 7. 코드 리뷰 체크리스트

- Data 모듈이 추천 판단을 하지 않는가?
- Analysis 모듈이 외부 API를 호출하지 않는가?
- Recommendation 모듈이 KIS API를 직접 호출하지 않는가?
- Notification 모듈이 점수 계산을 하지 않는가?
- API 라우터가 추천 생성을 직접 하지 않는가?
- 실거래 주문 코드가 없는가?
- API 키/토큰이 노출되지 않는가?
- snapshot/log 저장이 보장되는가?
