# TASKS.md

이 파일은 Codex가 v0.1 개발 작업을 작게 나누어 진행하기 위한 태스크 목록이다.

## Phase 0 - 프로젝트 준비

- [ ] `AGENTS.md` 읽기
- [ ] 프로젝트 브리프/상세 명세/에이전트 명세 읽기
- [ ] v0.1 범위 확인
- [ ] v0.1 제외 범위 확인
- [ ] 초기 Git 커밋 생성

## Phase 1 - 아키텍처/골격

- [ ] FastAPI 프로젝트 기본 구조 생성
- [ ] config 모듈 생성
- [ ] logging 설정 생성
- [ ] DataProviderInterface 생성
- [ ] AIProviderInterface 생성
- [ ] BrokerInterface placeholder 생성
- [ ] StrategyInterface placeholder 생성
- [ ] 기본 README 갱신

## Phase 2 - DB/Repository

- [ ] SQLAlchemy 설정
- [ ] DB 세션 관리
- [ ] stocks 모델
- [ ] holdings 모델
- [ ] daily_prices 모델
- [ ] stock_indicators 모델
- [ ] market_cap_rankings 모델
- [ ] stock_universes 모델
- [ ] news_items 모델
- [ ] market_regimes 모델
- [ ] recommendation_runs 모델
- [ ] recommendations 모델
- [ ] recommendation_results 모델
- [ ] holding_checks 모델
- [ ] data_snapshots 모델
- [ ] decision_logs 모델
- [ ] job_runs 모델
- [ ] notification_logs 모델
- [ ] Repository 기본 구현
- [ ] DB 테스트 작성

## Phase 3 - KIS/Data

- [ ] KisClient 생성
- [ ] 인증 토큰 처리 placeholder
- [ ] 현재가 조회 메서드
- [ ] 일봉 조회 메서드
- [ ] 시가총액 상위 조회 메서드
- [ ] API 응답 정규화 DTO
- [ ] DataQualityChecker
- [ ] daily_prices 수집/저장 서비스
- [ ] market_cap_rankings 수집/저장 서비스
- [ ] Mock API 테스트

## Phase 4 - Analysis/Scoring

- [ ] MA 계산
- [ ] RSI 계산
- [ ] MACD 계산
- [ ] volume_ratio_20d 계산
- [ ] breakout_20d 계산
- [ ] breakout_60d 계산
- [ ] ma_alignment 계산
- [ ] technical_score 계산
- [ ] 신규 추천 점수 계산
- [ ] 보유 종목 점수 계산
- [ ] 지표/점수 테스트

## Phase 5 - Recommendation/Holding

- [ ] RecommendationEngine 생성
- [ ] 시총 TOP 500 기반 후보 필터링
- [ ] 추천 TOP 5 생성
- [ ] recommendation_runs 저장
- [ ] recommendations 저장
- [ ] data_snapshots 연결
- [ ] decision_logs 저장
- [ ] HoldingCheckEngine 생성
- [ ] 보유 종목 수익률 계산
- [ ] 장전/장후 점검 생성
- [ ] 위험 경고 조건 생성
- [ ] 서비스 테스트

## Phase 6 - Notification/Report

- [ ] ReportGenerator 생성
- [ ] 추천 리포트 포맷
- [ ] 장전 점검 리포트 포맷
- [ ] 장후 점검 리포트 포맷
- [ ] 위험 경고 포맷
- [ ] TelegramNotifier 생성
- [ ] notification_logs 저장
- [ ] 메시지 포맷 테스트

## Phase 7 - Backend API

- [ ] `/api/reports/today`
- [ ] `/api/recommendations/latest`
- [ ] `/api/recommendations/history`
- [ ] `/api/holdings`
- [ ] `/api/holdings/checks/latest`
- [ ] `/api/stocks/{symbol}`
- [ ] `/api/universe/market-cap-top`
- [ ] `/api/market-regime/latest`
- [ ] `/api/news`
- [ ] `/api/jobs`
- [ ] API schema 작성
- [ ] API 테스트

## Phase 8 - Scheduler

- [ ] APScheduler 설정
- [ ] 18:00 장마감 데이터 수집 job
- [ ] 18:30 지표 계산 job
- [ ] 06:00 추천 리포트 job
- [ ] 08:30 장전 점검 job
- [ ] 16:30 장후 점검 job
- [ ] job_runs 저장
- [ ] 실패/재시도 처리

## Phase 9 - 테스트/문서

- [ ] pytest 전체 실행
- [ ] 구조 경계 리뷰
- [ ] API 키 노출 여부 점검
- [ ] v0.1 범위 위반 점검
- [ ] README 갱신
- [ ] TESTING.md 갱신
- [ ] SECURITY.md 갱신

## 완료 기준

- [ ] v0.1 기능이 mock 데이터로 동작
- [ ] 핵심 테스트 통과
- [ ] 실거래 주문 코드 없음
- [ ] snapshot/log 저장 가능
- [ ] 텔레그램 메시지 포맷 가능
- [ ] 대시보드 API 응답 가능
