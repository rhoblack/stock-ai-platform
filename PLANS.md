# PLANS.md

Codex가 긴 작업을 수행할 때 사용하는 실행 계획 문서다.

## 사용 원칙

긴 구현 작업을 시작하기 전에 Codex는 다음 형식으로 계획을 작성한다.

```text
목표:
범위:
수정할 파일:
수정하지 않을 파일:
단계:
테스트:
완료 기준:
위험 요소:
```

## 계획 템플릿

### Plan ID

`PLAN-YYYYMMDD-번호`

### 목표

무엇을 구현할지 한 문장으로 설명한다.

### 범위

이번 계획에 포함되는 작업.

### 제외 범위

이번 계획에서 하지 않을 작업.

### 수정할 파일

예상 수정 파일 목록.

### 단계

1. ...
2. ...
3. ...

### 테스트

- 실행할 테스트
- mock 처리할 외부 API
- 수동 확인 항목

### 완료 기준

- 코드 실행 가능
- 테스트 통과
- 문서 갱신
- AGENTS.md 원칙 위반 없음

## 예시

### PLAN-0001: DB 모델 1차 구현

목표:
v0.1 핵심 DB 모델과 Repository 기반을 구현한다.

범위:
- stocks
- holdings
- daily_prices
- stock_indicators
- job_runs

제외 범위:
- 추천 로직
- KIS API 호출
- 텔레그램
- 대시보드 프론트엔드

수정할 파일:
- app/db/models.py
- app/db/session.py
- app/data/repositories/*.py
- tests/db/test_models.py

단계:
1. SQLAlchemy Base와 세션 설정
2. 핵심 모델 작성
3. 인덱스 추가
4. Repository 작성
5. 테스트 작성

테스트:
- pytest tests/db

완료 기준:
- DB 모델 import 가능
- 테스트 DB에서 create/drop 가능
- Repository 저장/조회 테스트 통과
