# INTEGRATION_RUNBOOK.md

v0.1 백엔드 전체 흐름을 **실 KIS / 실 텔레그램 없이** 로컬에서 검증하는 시나리오 문서.
새 세션 / QA 인수자가 이 문서 하나만 따라가면 6개 잡 + 13개 GET API + dispatcher
DRY_RUN 흐름까지 모두 한 번씩 자극할 수 있도록 구성한다.

> 모든 단계는 **read-only 또는 mock 경계 안**에서만 동작한다. 실제 KIS API,
> Telegram BOT API, 주문 / 자동매매 코드는 호출되지 않는다.

---

## 0. 사전 준비

### 0.1 의존성 설치

```powershell
C:\msys64\ucrt64\bin\python.exe -m venv .venv
.\.venv\bin\python.exe -m pip install -e ".[dev]"
```

### 0.2 환경 변수

`.env.example`을 복사한 뒤 다음 키만 dry-run 친화적으로 두면 된다.

```text
TELEGRAM_ENABLED=false
SCHEDULER_ENABLED=false
FEATURE_REAL_ORDER_EXECUTION=false
FEATURE_FULL_AUTO=false
SQLITE_DATABASE_URL=sqlite:///./stock_ai.db
```

KIS / Telegram 실 자격증명은 비워두거나 `fake_*` 값을 넣는다. 어느 쪽이든
v0.1 흐름은 mock / DRY_RUN 으로만 흐른다.

### 0.3 테스트 게이트

회귀가 없는 상태에서 시나리오를 시작한다.

```powershell
.\.venv\bin\python.exe -m pytest -q
```

기준 결과: **296 passed**.

---

## 1. Mock seed 데이터 적재

`scripts/seed_mock_data.py`는 v0.1 엔진/라우터/잡이 읽는 모든 v0.1 테이블에
결정론적인 mock 데이터를 채워준다.

### 1.1 시드 명령

```powershell
.\.venv\bin\python.exe -m scripts.seed_mock_data --reset
```

옵션:

- `--reset`: 모든 테이블 drop + recreate 후 시드 (로컬 SQLite 한정 권장).
- `--db-url <SQLAlchemy URL>`: 기본값 `settings.effective_database_url` 대신
  Docker Postgres 등을 명시적으로 지정. 예: `--db-url postgresql+psycopg2://stock_user:stock_password@127.0.0.1:5432/stock_db`

### 1.2 시드 범위

| 테이블 | 건수 | 내용 |
|---|---:|---|
| `stocks` | 5 | KOSPI: 005930 삼성전자, 000660 SK하이닉스, 035420 NAVER, 005380 현대차, 035720 카카오 |
| `market_cap_rankings` | 5 | 오늘자 KOSPI 상위 5종목 (snapshot-replace) |
| `stock_universes` + `stock_universe_members` | 1 + 5 | `MARKET_CAP_TOP_500` |
| `daily_prices` | 30/종목 (총 150) | 추세·변동성 파라미터 기반 결정론적 OHLCV |
| `stock_indicators` | 5 | 오늘자 MA5/MA20/MA60/RSI14/MACD/volume_ratio_20d/breakout/ma_alignment/technical_score |
| `holdings` | 2 | `005930` (avg 66000), `000660` (avg 190000), 모두 active |
| `recommendation_runs` | 3 | 오늘 / 오늘-3 / 오늘-7 |
| `recommendations` | 8 | 위 3개 run 안에서 TOP 3/3/2 |
| `data_snapshots` | 12 | 추천/보유점검 시점 snapshot |
| `holding_checks` | 4 | 005930 어제 PRE / 오늘 PRE / 오늘 POST + 000660 오늘 PRE |

### 1.3 시드가 건드리지 않는 테이블

다음은 잡/실데이터가 채워야 하는 테이블이라 시드는 비워둔다 — 일부러 비워둠으로써
시나리오 §3에서 잡 실행으로 채워지는 것을 관찰할 수 있다.

- `job_runs`
- `notification_logs`
- `decision_logs`
- `recommendation_results`
- `news_items`, `market_regimes`

### 1.4 멱등성

같은 명령을 `--reset` 없이 다시 실행해도 row 중복은 발생하지 않는다.
`market_cap_rankings`만 `replace_for_date_market` 의미상 매번 5건 재기록 카운트로
보고되지만 총 row 수는 5로 유지된다.

---

## 2. 데이터 확인 (FastAPI 기동 전)

### 2.1 SQLite 직접 조회

```powershell
.\.venv\bin\python.exe -c "from sqlalchemy import create_engine, text; e=create_engine('sqlite:///./stock_ai.db'); print(list(e.connect().execute(text('SELECT symbol, name FROM stocks'))))"
```

### 2.2 FastAPI 기동

```powershell
.\.venv\bin\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`/health` 200 OK 확인.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

---

## 3. 6개 스케줄러 잡 수동 트리거

`SCHEDULER_ENABLED=false` 상태에서 잡 함수를 직접 호출해 결과 / `job_runs` /
`notification_logs` 행이 정상 기록되는지 확인한다. 모든 호출은 dry-run 친화적
(`telegram_enabled=False` → DRY_RUN, KIS 호출은 실 키가 없으면 인증 단계에서 즉시
실패하므로 §3.1 만 mock 주입).

### 3.1 collect_market_close_data

실 KIS 키 없이 mock provider 를 주입해 호출한다. 잡이 `MarketCapRankingCollector`
+ `DailyPriceCollector` 까지 정상 배선되었음을 확인.

```powershell
.\.venv\bin\python.exe - <<'PY'
from datetime import date
from app.db.session import SessionLocal
from app.scheduler.jobs import collect_market_close_data, JOB_NAME_COLLECT_MARKET_CLOSE, run_job
from tests.mocks.fake_kis_client import FakeKisDataProvider
from tests.mocks.kis_responses import DAILY_PRICE_RESPONSE, MARKET_CAP_RANKING_RESPONSE

def wrapped(session):
    session.info["data_provider"] = FakeKisDataProvider(
        market_cap_responses={("KOSPI", date(2026, 5, 5)): list(MARKET_CAP_RANKING_RESPONSE["output"])},
        daily_price_responses={"005930": list(DAILY_PRICE_RESPONSE["output2"]), "000660": list(DAILY_PRICE_RESPONSE["output2"])},
    )
    session.info["market_close_config"] = {"target_date": date(2026, 5, 5), "limit": 2}
    return collect_market_close_data(session)

from app.db.session import create_session_factory
factory = create_session_factory()
outcome = run_job(session_factory=factory, job_name=JOB_NAME_COLLECT_MARKET_CLOSE, fn=wrapped)
print(outcome.status, outcome.result_summary)
PY
```

### 3.2 calculate_technical_indicators

```powershell
.\.venv\bin\python.exe - <<'PY'
from app.db.session import create_session_factory
from app.scheduler.jobs import calculate_technical_indicators, JOB_NAME_CALCULATE_INDICATORS, run_job
factory = create_session_factory()
outcome = run_job(session_factory=factory, job_name=JOB_NAME_CALCULATE_INDICATORS, fn=calculate_technical_indicators)
print(outcome.status, outcome.result_summary)
PY
```

### 3.3 send_recommendation_report

`recommendation_runs` 가 시드되어 있으면 최신 run 을 dispatcher 가 DRY_RUN 으로
포맷한다. `notification_status="DRY_RUN"`, `notification_logs` 에 REPORT 행 1건.

```powershell
.\.venv\bin\python.exe - <<'PY'
from app.db.session import create_session_factory
from app.scheduler.jobs import send_recommendation_report, JOB_NAME_SEND_RECOMMENDATION_REPORT, run_job
factory = create_session_factory()
outcome = run_job(session_factory=factory, job_name=JOB_NAME_SEND_RECOMMENDATION_REPORT, fn=send_recommendation_report)
print(outcome.status, outcome.result_summary)
PY
```

### 3.4 run_pre_market_holding_check / run_post_market_holding_check

활성 보유 종목이 있으면 `HoldingCheckEngine` 이 점검을 생성하고 dispatcher 가 REPORT
+ HIGH risk 항목별 ALERT 를 dry-run 으로 기록한다. 보유가 없으면 `notification_status="NO_DATA"`.

```powershell
.\.venv\bin\python.exe - <<'PY'
from app.db.session import create_session_factory
from app.scheduler.jobs import (
    run_pre_market_holding_check,
    run_post_market_holding_check,
    JOB_NAME_PRE_MARKET_HOLDING_CHECK,
    JOB_NAME_POST_MARKET_HOLDING_CHECK,
    run_job,
)
factory = create_session_factory()
for name, fn in [
    (JOB_NAME_PRE_MARKET_HOLDING_CHECK, run_pre_market_holding_check),
    (JOB_NAME_POST_MARKET_HOLDING_CHECK, run_post_market_holding_check),
]:
    outcome = run_job(session_factory=factory, job_name=name, fn=fn)
    print(name, outcome.status, outcome.result_summary)
PY
```

### 3.5 update_recommendation_results

`lookback_days=60` 안의 `recommendation_runs` 를 모두 평가해 `recommendation_results`
에 1/3/5/20일 후 수익률을 upsert. 가격이 충분치 않으면 PENDING으로 남고 `data_status="PARTIAL"`.

```powershell
.\.venv\bin\python.exe - <<'PY'
from app.db.session import create_session_factory
from app.scheduler.jobs import update_recommendation_results, JOB_NAME_UPDATE_RECOMMENDATION_RESULTS, run_job
factory = create_session_factory()
outcome = run_job(session_factory=factory, job_name=JOB_NAME_UPDATE_RECOMMENDATION_RESULTS, fn=update_recommendation_results)
print(outcome.status, outcome.result_summary)
PY
```

### 3.6 잡 결과 관찰

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/jobs?limit=10 | ConvertTo-Json -Depth 6
```

각 row 가 `result_summary` (잡별 키 포함) + `status` SUCCESS/PARTIAL 분류로 보여야 한다.

---

## 4. 주요 API 조회 시나리오

다음 13개 read-only GET 라우터 모두 200 응답을 확인한다 (`Invoke-RestMethod`
또는 `curl`).

| 영역 | 엔드포인트 | 기대 |
|---|---|---|
| 오늘 리포트 | `/api/reports/today` | 추천 + 보유점검 + alert 묶음 |
| 추천 (최신/이력) | `/api/recommendations/latest`, `/api/recommendations/history` | 시드된 3개 run 노출, history는 success_rate / avg_close_return_{1,3,5,20}d 집계 (잡 §3.5 후) |
| 추천 run 상세 | `/api/recommendations/runs/{run_id}` | run 내 모든 추천 + results[] |
| 보유 | `/api/holdings`, `/api/holdings/checks/latest` | 시드된 2종목, 최신 점검 |
| 종목별 점검 | `/api/holdings/{symbol}/checks` (예: `005930`) | items[] + summary (total_check_count, alert_count, high_risk_count, latest/best/worst return rate, total_score_change) |
| 종목 상세 | `/api/stocks/{symbol}` (예: `005930`) | latest_price/indicator + recent_recommendations[*].results[] + recent_holding_checks[] |
| 시총 TOP | `/api/universe/market-cap-top` | 5종목 |
| 시장 레짐 | `/api/market-regime/latest` | 시드 안 되어 있으므로 비어있을 수 있음 (정상) |
| 뉴스 | `/api/news` | 시드 안 되어 있으므로 비어있을 수 있음 (정상) |
| 잡 | `/api/jobs`, `/api/jobs/{job_id}` | §3 에서 만든 job_runs 행 |
| 설정 | `/api/settings` | KIS / Telegram 자격증명은 마스킹 |

### 4.1 흥미로운 검증 포인트

- `/api/holdings/005930/checks` summary: `total_check_count=3`, `alert_count=1`,
  `high_risk_count=1`, `latest_total_score=48.0000`, `previous_total_score=60.0000`,
  `total_score_change=-12.0000`, `best_return_rate=4`, `worst_return_rate=2` (등 시드 값).
- `/api/recommendations/history` (잡 §3.5 실행 후): `success_rate` 가 NULL이 아닌 값으로 채워지는지.
- `/api/jobs`: `result_summary["data_status"]` (update_recommendation_results),
  `result_summary["notification_status"]` (send_recommendation_report,
  pre/post holding check) 키가 정상 노출되는지.

---

## 5. notification_logs / decision_logs 검증

```powershell
.\.venv\bin\python.exe - <<'PY'
from sqlalchemy import create_engine, text
e = create_engine("sqlite:///./stock_ai.db")
with e.connect() as conn:
    for table in ("job_runs", "notification_logs", "decision_logs"):
        rows = list(conn.execute(text(f"SELECT count(*) FROM {table}")))
        print(table, rows)
PY
```

기대:

- `job_runs`: §3 단계에서 호출한 잡 수 만큼 (6) RUNNING → SUCCESS / PARTIAL.
- `notification_logs`: send_recommendation_report DRY_RUN 1건 + holding check
  REPORT 2건 (PRE/POST) + HIGH risk holding 만큼의 ALERT 1건.
- `decision_logs`: holding-check 잡 호출 시 활성 보유 종목 × 각 점검 시점만큼.

---

## 6. 정리 / 종료

```powershell
# uvicorn 종료 후
Remove-Item .\stock_ai.db   # 로컬 SQLite 데이터 폐기
```

Docker Compose 환경이면 `docker compose down -v` 로 볼륨까지 삭제.

---

## 7. 회귀 / 안전 게이트 (작업 종료 시 항상 확인)

```powershell
.\.venv\bin\python.exe -m pytest -q
```

296 passed 가 유지되면 v0.1 통합 시나리오가 변경되지 않은 것.

---

## 8. v0.2 이후 (Backlog)

이 시나리오에서는 다루지 않는다 — `TASKS.md` Backlog 섹션 참조.

- 캔들 패턴 / ATR 컴포넌트 → `technical_score` 보강 (Phase 4 후속, 신규 분석 기능)
- 실 News / Supply / Fundamental / Earnings 파이프라인
- 실 KIS 키 운영 검증 (`.env` 채워 dry-run 외 환경 1회 검증)
- React / Next.js 대시보드 프론트엔드
- Strategy / Backtest / MockBroker / 자동매매
