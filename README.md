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

## 6. v0.1 백엔드 완료 상태

**v0.1 백엔드 마감 (tag `v0.1-backend-accepted`).** Phase 0~9 모두 완료, 통합
시나리오 1회 수행 검증 완료. 전체 회귀 테스트: **296 passed**.

| 영역 | 상태 |
|---|---|
| DB 모델 / Repository | 17개 테이블 ORM, 16개 Repository |
| KIS 데이터 수집 | `KisClient` + 정규화 / 품질 검사 / `DailyPriceCollector` / `MarketCapRankingCollector` (mock-injectable) |
| 분석 / 점수 | `TechnicalAnalyzer` (MA/RSI/MACD/breakout/ma_alignment), `ScoringEngine`, `RiskEngine`, `DummyScoreProducer` (News/Supply/Fundamental/Earnings/AI placeholder) |
| 추천 / 보유 점검 | `RecommendationEngine`, `HoldingCheckEngine` (PRE/POST), `RecommendationResultService` (1/3/5/20일 성과) |
| 알림 / 리포트 | `ReportGenerator` + `TelegramNotifier` (DRY_RUN 기본) + `NotificationService` + 3개 dispatcher (REPORT / ALERT) |
| Backend API | 13개 read-only GET, `/api/holdings/{symbol}/checks` summary metric 포함, `/api/jobs` 진단 |
| Scheduler | APScheduler + `run_job` 래퍼 + 6개 잡 (NO_DATA / PARTIAL 분기, dispatcher 연동, `notification_logs.related_job_id` 자동 연결) |
| 통합 검증 | `scripts/seed_mock_data.py` (멱등) + `INTEGRATION_RUNBOOK.md` (6잡 + 13API + 로그 검증), 1회 수행 결과는 `PROJECT_STATUS.md` §2 |

세부 산출물 / 테스트 카운트 / 변경 이력은 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
와 [`TASKS.md`](./TASKS.md) 참고.

**v0.1 제외 범위 재확인 (코드 미존재 또는 placeholder만 유지):**

- 실거래 자동매매, FULL_AUTO 모드, 가상 증권사 서버, 실제 KIS 주문 API 실행
  (`BrokerInterface`는 placeholder만 유지)
- 전략 자동 튜닝, 전용 AI 모델 학습, 백테스트 엔진
- React / Next.js PC 대시보드 프론트엔드

**v0.2 Backlog로 이동된 항목:**

- 캔들 패턴 (망치형/장악형 등) + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현 v0.1은 `DummyScoreProducer`)
- Strategy / Backtest / MockBroker / APPROVAL·SMALL_AUTO 모드

## 7. 실행 순서 (권장)

v0.1 인수자 / 새 세션 / QA 가 한 번에 따라가야 할 표준 순서. 각 단계는
모두 dry-run / mock-only — 실 KIS 호출, 실 텔레그램 발송, 자동매매 코드는
이 순서 안에서 절대 동작하지 않는다.

| 단계 | 명령 | 출력 / 검증 |
|---|---|---|
| 7.1 의존성 | `.\.venv\bin\python.exe -m pip install -e ".[dev]"` | 정상 설치 |
| 7.2 Docker (권장) 또는 로컬 uvicorn | §8 또는 §9 | `/health` 200 |
| 7.3 Mock seed | `.\.venv\bin\python.exe -m scripts.seed_mock_data --reset` | stocks 5 / daily_prices 150 등 (§10) |
| 7.4 통합 시나리오 (6잡 + 13API) | [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §3 ~ §5 그대로 따라감 | 모든 잡 SUCCESS, 13/13 API 200, notification_logs DRY_RUN |
| 7.5 회귀 게이트 | `.\.venv\bin\python.exe -m pytest -q` | 296 passed |
| 7.6 (운영 전) 실 KIS 키 사전 검증 | [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) | 체크리스트 항목별 통과 — 코드 변경 없음 |

## 8. Docker 로컬 실행

Docker Compose는 v0.1 로컬 검증용으로 PostgreSQL과 FastAPI backend를 함께 실행한다.
기본 설정은 안전하게 `SCHEDULER_ENABLED=false`, `TELEGRAM_ENABLED=false`,
`FEATURE_REAL_ORDER_EXECUTION=false`, `FEATURE_FULL_AUTO=false`로 고정되어 실제 KIS 주문,
자동매매, 텔레그램 발송을 하지 않는다.

```powershell
docker compose up --build
Invoke-RestMethod http://127.0.0.1:8000/health
```

Compose 기본 DB URL:

```text
postgresql+psycopg2://stock_user:stock_password@db:5432/stock_db
```

종료 / 볼륨 정리:

```powershell
docker compose down       # 컨테이너만 종료
docker compose down -v    # DB 볼륨까지 삭제 (필요 시에만)
```

로그 파일을 남기고 싶으면 `.env` 또는 Compose 환경변수에서 `LOG_TO_FILE=true`로 설정한다.
로그 디렉터리는 기본적으로 `logs/`이며, Git에는 `.gitkeep`만 유지된다.

## 9. 로컬 uvicorn 실행 (대안)

Docker 를 쓰지 않을 때.

```powershell
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\bin\python.exe -m pip install -e ".[dev]"
.\.venv\bin\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/health
```

MSYS2 Python에서 `greenlet` 빌드 오류로 SQLAlchemy 설치가 실패하면 현재 동기식 DB
테스트 범위에서는 다음 명령으로 로컬 검증이 가능하다.

```powershell
.\.venv\bin\python.exe -m pip install "fastapi>=0.99,<0.100" "pydantic>=1.10,<2.0" "uvicorn>=0.30,<1.0" "pytest>=8.0,<9.0" "httpx>=0.24,<0.27" "python-dotenv>=1.0,<2.0"
.\.venv\bin\python.exe -m pip install "SQLAlchemy>=2.0,<3.0" --no-deps
.\.venv\bin\python.exe -m pip install -e . --no-deps
```

## 10. Mock Seed 데이터 / 통합 실행 시나리오

실 KIS 키 / 실 텔레그램 없이 v0.1 백엔드 전체 흐름을 로컬에서 검증하려면
`scripts/seed_mock_data.py` 로 결정론적 mock 데이터를 적재한 뒤,
`INTEGRATION_RUNBOOK.md` 에 정리된 6개 잡 + 13개 GET API 시나리오를 따라간다.

```powershell
# 1) Mock 시드 적재 (로컬 SQLite, 멱등 — `--reset`은 destructive)
.\.venv\bin\python.exe -m scripts.seed_mock_data --reset

# 2) 시나리오는 INTEGRATION_RUNBOOK.md §3 (잡), §4 (API) 참조
```

시드 범위: stocks, market_cap_rankings, stock_universes/members, daily_prices,
stock_indicators, holdings, recommendation_runs, recommendations, data_snapshots,
holding_checks. 자세한 건수와 종목 / 점검 데이터 구성은
[INTEGRATION_RUNBOOK.md §1.2](./INTEGRATION_RUNBOOK.md) 참고.

가장 최근 통합 실행 결과(6잡 SUCCESS, 13/13 API 200, notification_logs 7건 등)는
[`PROJECT_STATUS.md` §2 "v0.1 통합 실행 결과"](./PROJECT_STATUS.md) 에 인수
스냅샷으로 보관되어 있다.

## 11. 테스트

```powershell
.\.venv\bin\python.exe -m pytest
```

외부 API, 텔레그램, 주문 기능은 테스트에서 실제로 호출하지 않습니다.
현재 회귀 기준선: **296 passed**.

## 12. 운영 전 KIS 실 키 검증

운영 환경에서 실 KIS 키 + 실 텔레그램으로 한 번 검증하기 전에는
[`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 의 체크리스트를 항목 단위로
확인한다. 코드 변경 없이 `.env` / 운영 SOP 만으로 통과해야 한다.

## 13. Codex 첫 실행 프롬프트 예시

```text
AGENTS.md, stock_ai_project_codex_brief.md, stock_ai_detailed_spec.md,
codex_agent_creation_spec.md, ARCHITECTURE.md, TASKS.md를 먼저 읽고,
v0.1 범위를 벗어나지 않는 개발 계획을 작성해줘.
아직 코드는 수정하지 말고 TASKS.md 업데이트 계획만 제안해줘.
```

## 14. 주의

이 프로젝트는 투자 판단 보조 도구입니다.  
v0.1에서는 실제 주문이나 자동매매를 구현하지 않습니다.
