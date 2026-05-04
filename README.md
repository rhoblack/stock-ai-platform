# Stock AI Platform

한국투자증권 API 기반 AI 주식 분석·추천·보유점검 플랫폼입니다.

## 1. 프로젝트 목표

v0.1의 목표는 실거래 자동매매가 아닙니다.

v0.1은 다음 기능을 구현하는 안정적인 분석/리포트 시스템입니다.

- 한국투자증권 API 기반 데이터 수집
- 시가총액 TOP 500 종목 유니버스 관리
- 관심종목/보유종목 관리
- 일봉/현재가 저장
- 기술적 지표 계산
- 보유 종목 장전/장후 점검
- 신규 추천 TOP 5 리포트
- 추천 이력 저장
- 텔레그램 알림
- FastAPI 기반 대시보드 API
- data_snapshots / decision_logs / job_runs 저장
- 테스트 가능한 구조

## 2. v0.1 제외 범위

다음 기능은 v0.1에서 구현하지 않습니다.

- 실거래 자동매매
- 실제 주문 API 실행
- FULL_AUTO 모드
- 가상 증권사 서버
- 전략 자동 튜닝
- 전용 AI 모델 학습
- 대량 가상 데이터 생성
- 완전한 백테스트 시스템

## 3. 권장 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python, FastAPI |
| DB | PostgreSQL, SQLite 초기 허용 |
| ORM | SQLAlchemy |
| Scheduler | APScheduler |
| Analysis | pandas, numpy |
| Test | pytest |
| Notification | Telegram Bot API |
| Frontend | React 또는 Next.js |
| Config | .env |

## 4. 프로젝트 문서

| 파일 | 설명 |
|---|---|
| `AGENTS.md` | Codex가 매번 따라야 하는 핵심 지침 |
| `stock_ai_project_codex_brief.md` | 프로젝트 전체 브리프 |
| `stock_ai_detailed_spec.md` | 상세 기능 명세 |
| `codex_agent_creation_spec.md` | 코딩 에이전트 생성 명세 |
| `ARCHITECTURE.md` | 시스템 구조 |
| `ROADMAP.md` | 단계별 개발 로드맵 |
| `TASKS.md` | v0.1 개발 태스크 |
| `PLANS.md` | Codex 실행 계획 관리 |
| `API_SPEC.md` | FastAPI 대시보드 API 명세 |
| `DB_SCHEMA.md` | DB 테이블 설계 |
| `TESTING.md` | 테스트 전략 |
| `SECURITY.md` | 보안 원칙 |
| `.env.example` | 환경변수 예시 |

## 5. 권장 개발 순서

1. 아키텍처와 인터페이스
2. DB 모델과 Repository
3. 최소 실행환경
4. 한국투자증권 API 클라이언트
5. 데이터 수집/정제
6. 기술적 분석과 점수 계산
7. 추천/보유 점검 서비스
8. 텔레그램 리포트
9. FastAPI 대시보드 API
10. 테스트와 문서화

## 6. 현재 구현 상태

Phase 1 기준으로 프로젝트 기본 골격만 준비되어 있습니다.

- `app/main.py`: FastAPI 최소 앱과 `/health` 엔드포인트
- `app/config/`: 환경 설정과 logging 기본 구조
- `app/data/`: 데이터 수집 계층 경계와 `DataProviderInterface`
- `app/ai/`: AI 보조 계층 경계와 `AIProviderInterface`
- `app/broker/`: 미래 확장용 `BrokerInterface` placeholder
- `app/decision/`: 미래 전략 확장용 `StrategyInterface` placeholder
- `tests/`: Phase 1 import/설정 테스트

아직 구현하지 않은 범위:

- DB 모델과 Repository
- KIS API 실제 연동
- 기술 지표 계산
- 추천/보유 점검 로직
- 텔레그램 발송
- 스케줄러 작업
- 주문 실행 또는 자동매매 기능

## 7. 로컬 실행

현재 프로젝트는 `pyproject.toml`로 Python 의존성을 관리합니다.

```powershell
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\bin\python.exe -m pip install -e ".[dev]"
.\.venv\bin\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

MSYS2 Python에서 `greenlet` 빌드 오류로 SQLAlchemy 설치가 실패하면 현재 동기식 DB
테스트 범위에서는 다음 명령으로 로컬 검증이 가능하다.

```powershell
.\.venv\bin\python.exe -m pip install "fastapi>=0.99,<0.100" "pydantic>=1.10,<2.0" "uvicorn>=0.30,<1.0" "pytest>=8.0,<9.0" "httpx>=0.24,<0.27" "python-dotenv>=1.0,<2.0"
.\.venv\bin\python.exe -m pip install "SQLAlchemy>=2.0,<3.0" --no-deps
.\.venv\bin\python.exe -m pip install -e . --no-deps
```

상태 확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 8. 테스트

```powershell
.\.venv\bin\python.exe -m pytest
```

외부 API, 텔레그램, 주문 기능은 테스트에서 실제로 호출하지 않습니다.

## 9. Codex 첫 실행 프롬프트 예시

```text
AGENTS.md, stock_ai_project_codex_brief.md, stock_ai_detailed_spec.md,
codex_agent_creation_spec.md, ARCHITECTURE.md, TASKS.md를 먼저 읽고,
v0.1 범위를 벗어나지 않는 개발 계획을 작성해줘.
아직 코드는 수정하지 말고 TASKS.md 업데이트 계획만 제안해줘.
```

## 10. 주의

이 프로젝트는 투자 판단 보조 도구입니다.  
v0.1에서는 실제 주문이나 자동매매를 구현하지 않습니다.
