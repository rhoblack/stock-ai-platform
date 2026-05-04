# Roadmap

## v0.1 - 분석/점검/리포트 기반 구축

목표: 실거래 없는 안정적인 분석/리포트 시스템.

포함:

- KIS API 데이터 수집
- 시가총액 TOP 500 유니버스
- 관심종목/보유종목
- 일봉/현재가 저장
- 기술적 지표 계산
- 신규 추천 TOP 5
- 보유 종목 장전/장후 점검
- 텔레그램 알림
- FastAPI 대시보드 API
- data_snapshots
- decision_logs
- job_runs
- 테스트

제외:

- 실거래 주문
- 자동매매
- 가상 증권사 서버
- 전략 튜닝
- 전용 AI 학습

## v0.2 - 전략/가상매매 기초

- 장기/중기/단기 전략 구조
- SIGNAL 모드
- PAPER 모드 기초
- 기본 백테스트
- 추천 성과 검증 강화
- 전략별 리포트

## v0.3 - 백테스트/튜닝

- 과거 데이터 리플레이
- 수수료/세금/슬리피지 반영
- 전략 버전 관리
- Grid Search 튜닝
- Walk-forward 검증
- 시장 국면별 성과 분석

## v0.4 - 가상 증권사/시뮬레이션

- MockBroker
- ReplayBroker
- SimulationBroker
- 가상 계좌
- 가상 주문/체결
- 가상 뉴스/시장 시나리오
- 스트레스 테스트

## v0.5 - 전용 AI 모델

- Market Regime Model
- Strategy Selection Model
- Risk Prediction Model
- 추천 성과 기반 재학습
- LLM과 전용 AI 역할 분리

## v1.0 - 소액 자동매매

- APPROVAL 모드
- SMALL_AUTO 모드
- KIS 주문 API
- 비상정지
- 일일 손실 제한
- 종목당/전략별 한도
- 실거래 로그
- 보안 강화

## 장기 목표

AI 기반 개인용 주식 전략 연구 플랫폼.

```text
추천
→ 보유 점검
→ 전략 관리
→ 가상매매
→ 백테스트/튜닝
→ 전용 AI
→ 소액 자동매매
```
