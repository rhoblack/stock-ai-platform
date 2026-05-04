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

Phase 1~3까지 진행되어 데이터 수집·정규화·검증·저장 흐름이 갖춰졌습니다.

- `app/main.py`: FastAPI 최소 앱과 `/health` 엔드포인트
- `app/config/`: 환경 설정과 logging 기본 구조
- `app/data/interfaces.py`: `DataProviderInterface`
- `app/ai/`: AI 보조 계층 경계와 `AIProviderInterface`
- `app/broker/`: 미래 확장용 `BrokerInterface` placeholder
- `app/decision/`: 미래 전략 확장용 `StrategyInterface` placeholder
- `app/db/`: SQLAlchemy 2.0 Base/Session, v0.1 필수 17개 테이블 ORM 모델
- `app/data/repositories/`: 테이블별 Repository (Stock/Daily/Indicator/Universe/Recommendation/Snapshot/DecisionLog 등)
- `app/data/collectors/kis_client.py`: httpx 기반 `KisClient` (토큰 발급, 현재가, 일봉, 시총 상위)
- `app/data/normalizers/kis.py`: KIS 응답 → DTO 변환
- `app/data/validators/quality.py`: `DataQualityChecker`
- `app/data/collectors/daily_price_collector.py`: KIS 일봉 raw → normalize → 품질 검사 → `daily_prices` upsert
- `app/data/collectors/market_cap_ranking_collector.py`: KIS 시총 raw → normalize → `market_cap_rankings` 스냅샷 교체 + `stocks`/`stock_universes`/`stock_universe_members` 동기화
- `app/analysis/technical_analyzer.py`: 일봉 DTO 시퀀스 → MA5/20/60/120, RSI14, MACD, volume_ratio_20d, breakout_20d/60d, ma_alignment, technical_score 산출 (`IndicatorSnapshot` 반환)
- `app/analysis/indicator_service.py`: `daily_prices` 조회 → `TechnicalAnalyzer` 실행 → `stock_indicators` upsert (단일/다중 종목)
- `app/decision/scoring_engine.py`: 신규 추천/보유 점수 산식 (`technical/news/supply/fundamental/ai`, `technical/news/earnings/ai/profit_management`), `risk_penalty` 반영, 0~100 clamp, `ScoreBreakdown` 반환
- `app/decision/recommendation_engine.py`: MARKET_CAP_TOP_500 유니버스 → 종목별 최신 `stock_indicators` → `ScoringEngine` → TOP N 관찰 후보 생성. `recommendation_runs`/`recommendations`/`data_snapshots`/`decision_logs`까지 일괄 저장. 뉴스/수급/실적/AI 점수는 Phase 5-1에서 placeholder
- `app/decision/holding_check_engine.py`: 활성 `holdings` → 최신 `daily_prices` + 최신 `stock_indicators` → `ScoringEngine.score_holding` → `holding_checks` upsert + `data_snapshots`/`decision_logs` 기록. PRE_MARKET / POST_MARKET 지원, 위험 경고 (점수 15점 이상 하락 / 20일선 이탈 / 손절 근접) 평가
- `app/decision/risk_engine.py`: 추천/보유 결과의 점수·경고·가격 위치를 바탕으로 risk_penalty + risk_level(LOW/MEDIUM/HIGH) + risk_flags 산출. ScoringEngine과 양 Engine에 연결
- `app/notification/report_generator.py`: 추천 리포트 / 장전·장후 보유 점검 리포트 / 위험 경고 텍스트 포맷터. HIGH risk_level 보유는 보고서 상단 우선 노출
- `app/notification/telegram_notifier.py`: Telegram BOT API 클라이언트. `TELEGRAM_ENABLED=false`면 dry-run, 자격증명 누락 시 DISABLED, 실패 시 FAILED 결과 반환 (실제 발송은 `httpx.Client` 주입으로 mock 가능)
- `app/notification/notification_service.py`: notifier + `notification_logs` 저장 글루
- `app/api/`: 13개 read-only GET 라우터 (`/api/reports/today`, `/api/recommendations/*`, `/api/holdings/*`, `/api/stocks/{symbol}`, `/api/universe/market-cap-top`, `/api/market-regime/latest`, `/api/news`, `/api/jobs`, `/api/settings`). risk_summary / decision / alert를 응답에 포함. `/api/settings`는 토큰·키·계좌번호를 마스킹
- `app/scheduler/jobs.py`: `run_job` 래퍼(2-session 패턴, `session.info["job_run_id"]`로 `notification_logs.related_job_id` 자동 연결) + 6개 v0.1 잡 함수
- `app/scheduler/scheduler.py`: APScheduler `BackgroundScheduler` 빌드 (Asia/Seoul 기본, cron 트리거, misfire 5분 허용, coalesce). FastAPI lifespan에서 `SCHEDULER_ENABLED=true`일 때 lazy import로 시작/종료
- `app/notification/dispatchers.py`: `RecommendationReportDispatcher` / `HoldingCheckReportDispatcher`. ORM 행 → `ReportGenerator` → `NotificationService` 흐름. `recommendation_runs.telegram_sent`는 실제 발송(`SUCCESS`)일 때만 True로 갱신, DRY_RUN/FAILED는 그대로 False
- `send_recommendation_report` / `run_pre_market_holding_check` / `run_post_market_holding_check` 잡: dispatcher와 연결되어 각 실행마다 `notification_logs` 행 생성 (DRY_RUN이 기본). job 결과 summary에 `notification_status`/`telegram_sent`/`notification_log_id`/`message_length` 노출
- `app/decision/recommendation_result_service.py`: 추천일 종가 기준 1/3/5/20일 후 open/high/low/close/max return + max_drawdown + result_status 산출. (recommendation_id, days_after) upsert로 멱등 재실행. SUCCESS(고가≥+3% 또는 종가≥+1%) / FAILED(저가≤-5%, 우선순위) / PENDING(데이터 부족 또는 신호 없음)
- `update_recommendation_results` 잡 (17:00): 위 서비스에 연결되어 `lookback_days=60` 범위의 모든 추천에 대해 결과 행을 upsert
- `tests/`: Phase 1~8 + dispatcher + result service 단위/통합 테스트, mock KIS 응답, mock Telegram transport, FastAPI TestClient 기반 API 테스트, `BackgroundScheduler.start` 없는 잡 함수 단위 테스트

아직 구현하지 않은 범위:

- 뉴스/수급/실적/AI 점수 producer (Phase 6+ rule/dummy)
- 캔들 패턴 / ATR 변동성 점수 보강 (Phase 4 후속)
- `collect_market_close_data` 잡의 실제 KIS 수집 연결 (현재 placeholder)
- 단일 종목 위험 발생 시 즉시 ALERT 발송 (`risk_alert` 포맷터는 있고 dispatcher 연결만 후속)
- `recommendation_results` 결과를 대시보드 API에 노출 (현재 DB에는 저장되지만 라우터 미연결)
- 텔레그램 발송 (Phase 6)
- FastAPI 대시보드 라우터 (Phase 7)
- 스케줄러 작업 (Phase 8)
- 주문 실행 또는 자동매매 기능 (v1.0+)

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
