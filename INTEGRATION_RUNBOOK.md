# INTEGRATION_RUNBOOK.md

> 본 문서는 **v0.7 마감 시점** 기준이다 (`v0.7-frontend-backtest` 누적,
> `v0.7-final` 마감 예정). v0.5 §10 (News) / §11 (Disclosure) / §12 (테마) +
> v0.6 §13 (Fundamental CSV) / §14 (Earnings CSV) / §15 (read-only API) +
> v0.7 §16 (백테스트 CLI + read-only API + 화면) 모두 반영.

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

v0.4 Phase B 인수 시점 기준: **362 passed**. v0.3 마감 시점 (319) → v0.4 Phase A
(335) → v0.4 Phase B (362) 누적 증분이 모두 0 회귀로 유지.

---

## 8. v0.2 이후 (Backlog)

이 시나리오에서는 다루지 않는다 — `TASKS.md` Backlog 섹션 참조.

- 캔들 패턴 / ATR 컴포넌트 → `technical_score` 보강 (Phase 4 후속, 신규 분석 기능)
- 실 News / Supply / Fundamental / Earnings 파이프라인
- 실 KIS 키 운영 검증 (`.env` 채워 dry-run 외 환경 1회 검증)
- React / Next.js 대시보드 프론트엔드
- Strategy / Backtest / MockBroker / 자동매매

---

## 9. 증권사 리포트 import (v0.4 Phase B+)

운영자가 직접 작성한 메타데이터 CSV 를 시스템에 적재하는 절차. 자동 크롤링 /
원문 본문 저장 / PDF BLOB 저장은 모두 금지 (`PROJECT_STATUS.md` §0 v0.4 정책).

### 9.1 입력 CSV 준비

스키마는 [`tests/fixtures/analyst_reports_sample.csv`](./tests/fixtures/analyst_reports_sample.csv)
참조. 35 컬럼 중 필수는 `report_type`, `broker_name`, `published_at`, `title`
4개. 그 외는 모두 optional. 한 row 가 최대 4 entity (report + theme + N
mappings + signal_event) 를 만들 수 있다.

**저작권 정책 (importer 가 거부하는 컬럼)**: `body`, `content`, `full_text`,
`raw_text`, `paragraph_text`, `paragraphs`, `article_body`, `full_body`,
`original_text`, `html_body`, `report_body`, `본문`, `원문`, `전문`. 본문 / 단락
텍스트 columns 가 헤더에 있으면 import 자체를 거부한다.

### 9.2 dry-run (검증만, DB 변경 없음)

```powershell
.\.venv\bin\python.exe -m scripts.import_analyst_reports `
    --file .\tests\fixtures\analyst_reports_sample.csv
```

출력 예:

```
Analyst-report import — DRY-RUN (no DB writes)
  file: analyst_reports_sample.csv
  total_rows         : 3
  inserted_reports   : 3
  skipped_duplicates : 0
  inserted_themes    : 3
  inserted_mappings  : 5
  inserted_signal_events: 3
  truncated_summaries: 0
  validation_errors  : 0
```

`validation_errors > 0` 이면 row 별 에러 메시지가 같이 출력 (최대 20건).
**`source_file_path` 는 어떤 출력에도 노출되지 않는다** — 에러 메시지조차 컬럼명
+ 정상 enum/date/숫자 후보 값만 echo 한다.

### 9.3 commit (실제 DB 적재)

```powershell
.\.venv\bin\python.exe -m scripts.import_analyst_reports `
    --file .\tests\fixtures\analyst_reports_sample.csv `
    --commit
```

re-run 은 멱등 — 동일 `(broker_name, published_at, title)` 은 `skipped_duplicates`
로 카운트되고 새 row 가 추가되지 않는다.

### 9.4 인코딩 / DB URL 옵션

- `--encoding cp949` 또는 `--encoding euc-kr` — 레거시 Excel 한국어 export 대응
- `--db-url sqlite:///./trial.db` — 트라이얼용 별도 DB 경로

### 9.5 일별 컨센서스 스냅샷 잡

`update_report_consensus_snapshots` (06:30 KST) 가 자동 실행되며, COMPANY 타입
리포트 중 발행 후 90일 이내 항목을 종목별 집계해 `report_consensus_snapshots`
에 upsert. 수동 트리거 (테스트용):

```powershell
.\.venv\bin\python.exe -c "
from app.scheduler.jobs import run_job, update_report_consensus_snapshots, JOB_NAME_UPDATE_REPORT_CONSENSUS
from app.db.session import create_db_engine, create_session_factory
engine = create_db_engine()
factory = create_session_factory(engine)
outcome = run_job(session_factory=factory, job_name=JOB_NAME_UPDATE_REPORT_CONSENSUS, fn=update_report_consensus_snapshots)
print(outcome.status, outcome.result_summary)
"
```

활성 리포트 0건이면 `data_status=NO_DATA + status=SUCCESS`.

### 9.6 운영 점검

- `job_runs` 테이블에서 `job_name='update_report_consensus_snapshots'` 행을 확인
- `report_consensus_snapshots` 의 `(symbol, snapshot_date, window_days=90)` 행이 종목별로 1건씩 갱신되는지 확인
- 컨센서스가 산정되지 않은 종목은 컨센서스 row 자체가 부재 (오류 아님 — Phase C 의 score 계산이 null fallback)

---

## 10. 뉴스 수집 (v0.5 Phase A)

`collect_news` 잡 (8번째, 19:00 KST) 은 **default OFF** — 운영자가 명시적으로
opt-in 한 경우에만 NewsCollector 가 실 외부 provider 를 호출한다. v0.1 부터
유지된 read-only / 외부 호출 0건 정책의 연장.

### 10.1 기본 동작 (default — 외부 호출 0건)

`.env` 에 `NEWS_COLLECTION_ENABLED=true` 가 없거나 false 인 상태:

- 19:00 KST 에 `collect_news` 잡이 실행되지만 즉시 SKIPPED 분기로 종료
- `JobRun.result_summary = { phase: "v0.5-A", data_status: "SKIPPED", reason: "news_collection_disabled", fetched: 0, ... }`
- 외부 provider 생성 / 호출 일체 없음

### 10.2 NewsCollector 활성화 (운영자 opt-in)

`.env` 에 다음 한 줄 추가 후 backend 재기동:

```
NEWS_COLLECTION_ENABLED=true
```

이 상태에서 `collect_news` 잡은 두 가지 분기:

- 운영 환경에 실 NewsProvider 가 주입되지 않은 경우 (v0.5 Phase A 시점 default — 실 RSS / DART 구현체 부재):
  → SKIPPED + `reason: "no_provider_configured"`. 외부 호출 0건. v0.5 Phase B+ 또는 별도 cycle 에서 실 provider 가 도입되면 자동 활성화.
- 실 provider 가 주입된 경우 (v0.6+ 후보):
  → NewsCollector 실행 + `result_summary.data_status = "SUCCESS"` + counters (fetched / inserted / skipped_duplicates / truncated_summaries).

### 10.3 수동 트리거 (테스트 / 디버깅용)

```powershell
.\.venv\bin\python.exe -c "
from sqlalchemy.orm import sessionmaker
from app.db.session import create_db_engine
from app.scheduler.jobs import run_job, collect_news, JOB_NAME_COLLECT_NEWS
from app.config.settings import Settings
from tests.mocks.fake_news_provider import FakeNewsProvider

engine = create_db_engine()
factory = sessionmaker(engine, future=True)

def fn(session):
    s = Settings()
    object.__setattr__(s, 'news_collection_enabled', True)
    session.info['settings'] = s
    session.info['news_provider'] = FakeNewsProvider()  # 결정론적 3-row 샘플
    return collect_news(session)

outcome = run_job(session_factory=factory, job_name=JOB_NAME_COLLECT_NEWS, fn=fn)
print(outcome.status, outcome.result_summary)
"
```

### 10.4 운영 점검

- `job_runs` 에서 `job_name='collect_news'` 행 확인 (`status` / `result_summary.data_status` / `result_summary.reason`)
- enabled 상태에서 수집된 뉴스는 `news_items` 테이블에 적재 (PR1 의 `category` 컬럼 + url-keyed 멱등 upsert)
- 활성 NewsProvider 가 외부 API rate limit 에 걸리거나 실패하면 잡 wrapper 가 자동 FAILED 기록 → `job_runs.error_message` 에 예외 타입 + 메시지 노출

### 10.5 비활성화 / 롤백

`.env` 에서 `NEWS_COLLECTION_ENABLED` 라인을 제거하거나 `false` 로 변경 후
backend 재기동. 다음 19:00 KST 잡부터 SKIPPED 로 자동 전환. 기존 적재된
`news_items` 행은 그대로 유지 (운영자가 수동으로 정리).

---

## 11. 공시 수집 (v0.5 Phase B)

`collect_disclosures` 잡 (9번째, 20:00 KST) 은 §10 `collect_news` 와 동일한
default-OFF 패턴. DART / KRX 외부 호출 0건이 default. 운영자가 명시적으로
`DISCLOSURE_COLLECTION_ENABLED=true` opt-in 한 경우에만 `DisclosureCollector` 가
provider 를 호출한다. 분류 결과는 `news_items.category` (Phase A 컬럼) 에
저장되며 NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE /
GOVERNANCE / OTHER 6 enum 중 하나.

### 11.1 기본 동작 (default — 외부 호출 0건)

`.env` 에 `DISCLOSURE_COLLECTION_ENABLED` 가 없거나 false:

- 20:00 KST 잡이 즉시 SKIPPED 로 종료
- `JobRun.result_summary = { phase: "v0.5-B", data_status: "SKIPPED", reason: "disclosure_collection_disabled", ... }`
- 외부 provider 생성 / 호출 0건

### 11.2 활성화 (운영자 opt-in)

```
DISCLOSURE_COLLECTION_ENABLED=true
```

- 실 DART / KRX provider 미주입 (v0.5 Phase B 시점 default — 실 구현체 부재):
  → SKIPPED + `reason: "no_provider_configured"`. 외부 호출 0건.
- 실 provider 주입 (v0.6+ 후보) 또는 테스트의 FakeDisclosureProvider:
  → DisclosureCollector 실행 + `result_summary.data_status: "SUCCESS"` + counters
  + `classified_counts` (5 enum 별 inserted 수).

### 11.3 분류 룰 (priority order)

| 우선순위 | 카테고리 | 한글 keyword (대표) | 영문 keyword |
|---|---|---|---|
| 1 | RISK_DISCLOSURE | 소송 / 횡령 / 배임 / 거래정지 / 감사의견 / 회생 / 파산 | lawsuit / litigation / fraud / embezzlement |
| 2 | EARNINGS_REPORT | 실적 / 잠정 / 영업이익 / 당기순이익 | earnings / guidance |
| 3 | OWNERSHIP_CHANGE | 최대주주 / 지분 / 보유주식 / 주식 등의 대량보유 | ownership |
| 4 | GOVERNANCE | 이사회 / 사외이사 / 감사위원회 / 주주총회 / 정관 변경 | governance / board |
| 5 | OTHER (fallback) | — | — |

매칭 대상: `(title, disclosure_type, summary)` join 후 lowercase. 한글은 lower
변환에 영향받지 않음. RISK 가 우선 — 실적 발표와 소송이 동시에 등장하면
RISK_DISCLOSURE 로 분류.

### 11.4 수동 트리거 (테스트 / 디버깅)

```powershell
.\.venv\bin\python.exe -c "
from sqlalchemy.orm import sessionmaker
from app.db.session import create_db_engine
from app.scheduler.jobs import run_job, collect_disclosures, JOB_NAME_COLLECT_DISCLOSURES
from app.config.settings import Settings
from tests.mocks.fake_disclosure_provider import FakeDisclosureProvider

engine = create_db_engine()
factory = sessionmaker(engine, future=True)

def fn(session):
    s = Settings()
    object.__setattr__(s, 'disclosure_collection_enabled', True)
    session.info['settings'] = s
    session.info['disclosure_provider'] = FakeDisclosureProvider()  # 결정론 4-row 샘플
    return collect_disclosures(session)

outcome = run_job(session_factory=factory, job_name=JOB_NAME_COLLECT_DISCLOSURES, fn=fn)
print(outcome.status, outcome.result_summary)
"
```

### 11.5 운영 점검

- `job_runs` 에서 `job_name='collect_disclosures'` 행 확인
- `news_items` 에서 `category IN ('EARNINGS_REPORT', 'OWNERSHIP_CHANGE', 'RISK_DISCLOSURE', 'GOVERNANCE')` 행이 적재되었는지 확인
- 분류 정확도가 의심되면 `app/data/collectors/disclosure_collector.py` 의 4 keyword set 을 운영 데이터 기반으로 보강 (LLM 분류는 v0.6+ 후보)
- RISK_DISCLOSURE 행은 v0.5 Phase C 의 `DisclosureRiskProducer` 가 RiskEngine 보강에 사용할 예정 (현재 Phase B 에서는 데이터 적재만)

### 11.6 비활성화 / 롤백

`.env` 에서 `DISCLOSURE_COLLECTION_ENABLED` 제거 또는 `false` 변경 후 backend
재기동. 다음 20:00 KST 잡부터 SKIPPED 자동 전환. 기존 적재된 `news_items` 행은
그대로 유지.

## 12. 테마 랭킹 / 상세 (v0.5 Phase D)

v0.4 가 `report_themes` / `theme_stock_mappings` / `report_signal_events` 에
누적해 온 데이터를 첫 surface 한 cycle. 신규 read-only 엔드포인트와 9번째 사이드바
화면이 도입되었고, recommendation 응답에 `news_evidence` / `disclosure_risk_evidence`
가 명시 필드로 노출된다. **신규 잡 / 외부 호출 / POST 라우터는 0건 추가**.

### 12.1 신규 read-only API

```
GET /api/themes/ranking?category=...&direction=...&limit=...
GET /api/themes/{theme_id}?mapping_limit=...&signal_limit=...
```

빠른 확인:

```powershell
curl http://127.0.0.1:8000/api/themes/ranking?limit=5 | jq
curl http://127.0.0.1:8000/api/themes/ranking?direction=POSITIVE | jq
curl http://127.0.0.1:8000/api/themes/41 | jq
```

`direction` 은 `POSITIVE` / `NEGATIVE` / `NEUTRAL` 만 허용 — 다른 값은 422.
응답에는 `mapping_count` + `signal_event_count` 가 단일 GROUP BY 쿼리로 계산되어
포함된다. `source_file_path` 는 ranking / detail 모두에서 절대 노출되지 않는다.

### 12.2 프런트 9번째 메뉴

사이드바 7번째 위치에 `테마 (β)` 메뉴 추가 (시가총액 TOP 과 시스템 로그 사이).
`/themes` 는 카테고리 / direction 필터 + 검색 + TanStack Table 정렬 (mapping_count
desc 가 default). 테마 행 클릭 → `/themes/:theme_id` 로 이동, 영향 종목 카드의
종목 코드를 다시 클릭하면 기존 `/stocks/:symbol` 화면으로 이어진다 (StockDetail
의 RelatedThemesCard 에서도 반대 방향 네비게이션 동작).

### 12.3 Recommendation 응답의 evidence 필드

v0.5 Phase C 에서 `DataSnapshot.market_context_json` 에 저장만 되어 있던
`news_evidence` / `disclosure_risk_evidence` 가 `RecommendationItemSchema` 의
nullable dict 필드로 surface 된다. `RealNewsScoreProducer` /
`DisclosureRiskProducer` 가 wired 되지 않은 pre-v0.5 run / 시드 데이터에서는
두 필드 모두 `null`. Whitelist 정책 그대로 — `top_news` 는 정확히
`{title, url, provider, published_at, sentiment}`, `recent_risk_disclosures` 는
sentiment 제외. 본문 / `source_file_path` / 운영자 로컬 경로 0건.

### 12.4 운영 점검

- 새 잡 / 새 외부 호출 / 새 POST 라우터 추가 0건 → `job_runs` / 외부 트래픽
  변화 0건 (검증: `SELECT job_name, COUNT(*) FROM job_runs GROUP BY job_name`
  vs Phase C 직후 결과 동일)
- `report_themes` 행이 v0.4 Phase B 의 import 잡에서 만들어져 있어야
  `/api/themes/ranking` 이 결과를 반환. 비어 있으면 응답은 `items: []` 이고
  화면은 "아직 테마 데이터가 없습니다" placeholder
- frontend 4 게이트: backend pytest **481** / vitest **68** / build / e2e **11**
  (`npm run e2e` — Playwright 1.x chromium)
## 13. Fundamental CSV 수동 import (v0.6 Phase A PR2)

`fundamental_snapshots` 는 운영자가 준비한 CSV 로만 수동 적재한다. 기본은 dry-run 이며,
`--commit` 을 붙인 경우에만 DB 에 저장된다. DART/KIS API 호출, scheduler job, API 라우터,
프론트 화면은 이 단계에 없다.

### 13.1 CSV 필수 컬럼

```text
symbol,snapshot_date,fiscal_year,source
```

선택 숫자 컬럼:

```text
fiscal_quarter,revenue,operating_income,net_income,total_assets,total_liabilities,
total_equity,eps,bps,per,pbr,roe,debt_ratio,dividend_yield,
revenue_growth_yoy,operating_income_growth_yoy
```

`body`, `content`, `full_text`, `paragraph`, `raw_text`, `html_body`, `본문`,
`원문`, `전문`, `source_file_path`, PDF/Excel BLOB 계열 컬럼은 파일 단위로 거부된다.

### 13.2 dry-run 검증

```powershell
.\.venv\bin\python.exe -m scripts.import_fundamentals --file tests\fixtures\fundamentals_sample.csv
```

출력 요약:

```text
total_rows / inserted / updated / unchanged / skipped_duplicates / validation_errors / truncated_notes
```

### 13.3 commit 적재

```powershell
.\.venv\bin\python.exe -m scripts.import_fundamentals --file tests\fixtures\fundamentals_sample.csv --commit
```

DB URL 을 따로 지정할 때:

```powershell
.\.venv\bin\python.exe -m scripts.import_fundamentals --file fundamentals.csv --db-url sqlite:///./trial.db --commit
```

동일한 `(symbol, snapshot_date, fiscal_year, fiscal_quarter)` 를 다시 적재하면 값이 같을 때
`unchanged`, 값이 다를 때 `updated` 로 집계된다.

### 13.4 validation 정책

- `snapshot_date`: ISO `YYYY-MM-DD`
- `fiscal_year`: integer
- `fiscal_quarter`: `1~4` 또는 empty
- `NaN`, `-`, empty, `None`, `null`, `N/A`: optional 숫자에서 `None`
- `revenue`, `total_assets`, `total_liabilities`, `total_equity`: 음수 불허
- `operating_income`, `net_income`, `eps`, `roe`, 성장률 계열: 음수 허용

## 14. Earnings CSV 수동 import (v0.6 Phase B)

`earnings_events` 는 실적 이벤트와 어닝 캘린더의 read-only 기반 데이터다. Phase B 에서는
운영자 CSV 수동 import 만 제공한다. 기본은 dry-run 이며 DART/KIS API, scheduler job,
API 라우터, 프론트 화면은 추가하지 않는다.

### 14.1 CSV 필수 컬럼

```text
symbol,event_date,fiscal_year,event_type
```

선택 컬럼:

```text
company_name,fiscal_quarter,revenue_actual,revenue_consensus,
operating_income_actual,operating_income_consensus,net_income_actual,
net_income_consensus,eps_actual,eps_consensus,surprise_type,surprise_pct,
source,memo
```

`event_type` 은 `PRELIMINARY`, `FINAL`, `GUIDANCE`, `CONSENSUS`, `OTHER`.
`surprise_type` 은 `BEAT`, `MEET`, `MISS`, `UNKNOWN`.

### 14.2 dry-run 검증

```powershell
.\.venv\bin\python.exe -m scripts.import_earnings --file tests\fixtures\earnings_events_sample.csv
```

### 14.3 commit 적재

```powershell
.\.venv\bin\python.exe -m scripts.import_earnings --file tests\fixtures\earnings_events_sample.csv --commit
```

DB URL override:

```powershell
.\.venv\bin\python.exe -m scripts.import_earnings --file earnings.csv --db-url sqlite:///./trial.db --commit
```

### 14.4 surprise 계산 정책

- CSV 에 `surprise_type` 이 있으면 해당 값을 우선 사용
- `surprise_type` 이 없고 `operating_income_actual` / `operating_income_consensus` 가 있으면 자동 계산
- `surprise_pct = (actual - consensus) / abs(consensus) * 100`
- `surprise_pct >= 5`: `BEAT`
- `-5 < surprise_pct < 5`: `MEET`
- `surprise_pct <= -5`: `MISS`
- consensus 가 0 또는 empty 이면 `UNKNOWN`

### 14.5 validation 정책

- `event_date`: ISO `YYYY-MM-DD`
- `fiscal_year`: integer
- `fiscal_quarter`: `1~4` 또는 empty
- `memo`: 500자 초과 시 truncate 후 `truncated_notes` 증가
- `revenue_actual`, `revenue_consensus`: 음수 불허
- `operating_income`, `net_income`, `eps` 계열 actual/consensus: 적자 기업을 위해 음수 허용
- `body`, `content`, `full_text`, `paragraph`, `raw_text`, `html_body`, `본문`,
  `원문`, `전문`, `source_file_path`, PDF/Excel BLOB 계열 컬럼은 파일 단위로 거부

## 15. 재무 / 실적 read-only API 확인 (v0.6 Phase D)

v0.6 Phase D 가 backend 에 추가한 read-only API 3종은 외부 API 호출 0건 / POST
0건 / DART 자동 호출 0건 / Telegram 발송 0건. 운영자가 health check 또는
대시보드 검증 단계에서 다음 명령으로 응답 형식을 확인할 수 있다.

### 15.1 신규 endpoint

| 경로 | 목적 | 주요 query |
|---|---|---|
| `GET /api/stocks/{symbol}/fundamentals` | 종목별 최신 재무 + 최근 history | `limit` (기본 8, 최대 40) |
| `GET /api/stocks/{symbol}/earnings` | 종목별 최근 실적 이벤트 + history | `limit` (기본 8, 최대 40) |
| `GET /api/calendar/earnings` | 최근/다가오는 실적 캘린더 | `from_date` / `to_date` / `surprise_type` / `limit` (기본 20, 최대 100). `from_date` 미지정 시 "오늘 이후" |

### 15.2 수동 응답 확인 (PowerShell)

```powershell
# 백엔드가 8000 포트에서 떠 있어야 한다 (uvicorn / docker-compose)
Invoke-WebRequest http://127.0.0.1:8000/api/stocks/005930/fundamentals?limit=4 |
  Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:8000/api/stocks/005930/earnings?limit=4 |
  Select-Object -ExpandProperty Content
Invoke-WebRequest "http://127.0.0.1:8000/api/calendar/earnings?from_date=2026-05-01&to_date=2026-05-31&limit=10" |
  Select-Object -ExpandProperty Content
```

### 15.3 안전 가드

- 응답 트리에 `source_file_path`, `body`, `content`, `full_text`, `raw_text`,
  `paragraph`, `html_body`, `본문`, `원문`, `전문` 13종 forbidden 키워드 0건이어야
  한다. backend pytest 의 `_assert_no_source_file_path` recursive helper +
  명시 substring 검사가 자동 검증.
- `RecommendationItemSchema.fundamental_evidence` /
  `HoldingCheckSchema.earnings_evidence` 응답은 라우터 단계 화이트리스트
  (`_FUNDAMENTAL_EVIDENCE_FIELDS` / `_EARNINGS_EVIDENCE_FIELDS`) 를 거친다.
  수동으로 점검하려면 `set(payload["recommendations"][0]["fundamental_evidence"].keys())`
  가 허용 키 집합의 부분집합인지 확인.
- evidence 키가 모두 forbidden 이라 화이트리스트 후 빈 dict 가 되면 응답은
  null 로 강등 — 프런트 placeholder ("—") 와 동일한 시그널.
- `EarningsEventSchema.memo` 는 500자 초과 시 라우터에서 자동 truncate.
- 자동매매 / 주문 / 신규 POST 라우터 / DART 자동 호출 / Telegram 자동 발송 0건
  유지 (정책 v0.1 ~ v0.5 동일).

## 16. 백테스트 CLI 운영 (v0.7 Phase B)

`scripts/run_backtest.py` 는 v0.7 Phase A 의 `StrategyInterface` 구현체를 과거
`recommendations` + `recommendation_results` 데이터에 적용해서 승률 / 평균
수익률 / max drawdown 을 계산한다. 외부 API / 텔레그램 / 주문 호출은 0건.

### 16.1 사용 가능한 전략

`app/strategy/registry.py` 의 `KNOWN_STRATEGIES`:

- `top_grade` — `TopGradeStrategy v1.0.0` (grade S/A → BUY, D → AVOID)
- `high_score` — `HighScoreStrategy v1.0.0` (total_score ≥75 → BUY, ≤35 → AVOID)
- `multi_signal` — `MultiSignalStrategy v1.0.0` (total≥65 + fundamental≥60 + news≥50 + earnings≥50/None + ¬HIGH risk + ¬RISK_DISCLOSURE → BUY)

### 16.2 기본 dry-run

```powershell
.\.venv\bin\python.exe -m scripts.run_backtest --strategy top_grade
```

dry-run 은 DB 저장 0건. 동일 신호 평가 결과를 stdout 으로만 노출한다 — `signal_count`,
`buy_count` / `pass_count` / `avoid_count`, `win_rate_*` / `avg_return_*` /
`max_drawdown`, horizon 별 `missing_result_count`.

### 16.3 commit (BacktestRun + BacktestResult 적재)

```powershell
.\.venv\bin\python.exe -m scripts.run_backtest --strategy multi_signal `
    --from-date 2026-04-01 --to-date 2026-05-04 --commit
```

`--commit` 시:
- `backtest_runs` 1행 추가 (status `SUCCESS` 또는 `FAILED`)
- `backtest_results` N행 추가 (평가된 recommendation 당 1행)
- 중복 적재 방지: `(backtest_run_id, recommendation_id)` Unique 제약

### 16.4 결과 조회 (read-only API 는 v0.7 Phase D 에서 추가 예정)

Phase B 시점에서는 SQL / Repository 로 직접 확인:

```python
from app.data.repositories import BacktestRunRepository, BacktestResultRepository

with session_factory() as session:
    runs = BacktestRunRepository(session).list_recent(limit=10)
    for run in runs:
        print(run.strategy_name, run.run_date, run.buy_count, run.win_rate_5d)
    if runs:
        rows = BacktestResultRepository(session).list_by_run(runs[0].id)
        for row in rows[:5]:
            print(row.symbol, row.signal_action, row.return_5d, row.confidence)
```

### 16.5 통계 정책 (BUY-only)

`win_rate_*` / `avg_return_*` / `max_drawdown` 은 **BUY 신호만** 대상. PASS /
AVOID 는 `*_count` 에는 잡히지만 수익률 통계에서 제외된다 (`BUY_ONLY_METRICS_NOTE`
가 응답 / `summary_json.notes` 에 함께 노출). 한 horizon 의
`recommendation_results.close_return` 이 NULL 인 BUY 신호는 그 horizon 의
계산에서 제외되고 `summary_json.missing_result_count_per_horizon[h]` 에 카운트만
가산 — 전체 run 은 실패하지 않는다.

### 16.6 비용 모델 + 시장 국면별 (v0.7 Phase C)

CLI 출력에 다음 필드가 추가된다:

```
  cost_model_version            : constant-v1
  total_cost (fraction)         : 0.00330
  cost_adjusted_avg_return_5d   : 2.6700
  regime_breakdown              :
    - UPTREND_EARLY  buy=12  win_rate_5d=0.6667  avg_return_5d=2.5000  cost_adj=2.1700
    - DOWNTREND      buy=4   win_rate_5d=0.2500  avg_return_5d=-0.8000 cost_adj=-1.1300
    - UNCLASSIFIED   buy=2   win_rate_5d=0.5000  avg_return_5d=1.0000  cost_adj=0.6700
```

- **`CostModel`** (placeholder constant 만): `buy_fee 0.015%` + `sell_fee 0.015%` +
  `sell_tax 0.20%` + `slippage 0.10%` = **`total_cost 0.33%`**. BUY 신호의
  `return_5d` 에서 자동 차감되어 `cost_adjusted_return_5d` 컬럼 + summary 평균
  필드에 반영. PASS / AVOID 는 `cost_adjusted_return_5d=NULL` (수수료 차감 없음).
  실 broker fee schedule fetch 는 v0.8+ 후보.
- **`assign_regime(session, signal_date, market="KOSPI")`** — `MarketRegime.date
  <= signal_date` 가운데 가장 최근 row 의 `regime` 반환. 매칭 실패 시 NULL →
  display 단계에서 `UNCLASSIFIED` bucket 으로 폴딩. DB 컬럼은 NULL 그대로 저장
  되므로 regime 데이터 후행 적재 후 backtest 재실행 시 자연스럽게 재분류.
- **`BacktestResultRepository.aggregate_by_regime(run_id)`** — `{regime: count}`
  GROUP BY 결과. NULL regime 은 `UNCLASSIFIED` 로 폴딩.
- **운영 DB ALTER**: 기존 Phase B 단계에 적재된 운영 DB 가 있다면 다음 SQL
  세 줄 실행 (destructive 0건):
  ```sql
  ALTER TABLE backtest_results ADD COLUMN cost_adjusted_return_5d NUMERIC(12, 4);
  ALTER TABLE backtest_results ADD COLUMN regime VARCHAR(32);
  CREATE INDEX ix_backtest_results_regime ON backtest_results (regime);
  ```

### 16.7 read-only API + 프런트 화면 (v0.7 Phase D)

Phase D 부터는 백테스트 결과를 read-only API + 10번째 화면 `/backtest` 로 직접
조회 가능. 외부 호출 / POST / Telegram / 자동매매 0건.

API 3종:

| 경로 | 목적 | 주요 query |
|---|---|---|
| `GET /api/strategies` | 룰 기반 전략 목록 (registry 기반 / DB 0건) | (없음) |
| `GET /api/backtest/runs` | 최근 BacktestRun 목록 (run_date desc) | `strategy` (`top_grade` 등) / `limit` (1~100, 기본 20) |
| `GET /api/backtest/runs/{run_id}` | 상세 + results + regime_breakdown + cost_model_version + total_cost + BUY-only notes | (없음) |

수동 응답 확인 (PowerShell):

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/strategies | Select-Object -ExpandProperty Content
Invoke-WebRequest "http://127.0.0.1:8000/api/backtest/runs?strategy=top_grade&limit=10" | Select-Object -ExpandProperty Content
Invoke-WebRequest http://127.0.0.1:8000/api/backtest/runs/42 | Select-Object -ExpandProperty Content
```

프런트 화면 (`/backtest`, Sidebar 10번째 `백테스트 (β)`):

- 상단: 등록된 전략 카드 grid (name + version + description)
- 중단: 최근 BacktestRun 표 (run row 클릭 가능, 전략 filter radiogroup)
- 하단: 선택한 run 의 상세 (regime_breakdown 표 + 신호 row 표 +
  cost_model_version / total_cost / BUY-only note)

**run 트리거는 화면에 없다** — 운영자가 `scripts/run_backtest.py --commit` 으로
적재한 결과만 화면이 read-only 로 노출. POST 라우터 / 자동매매 / Broker 호출
0건은 v0.1 ~ v0.7 일관 정책.

### 16.8 안전 가드

- `BacktestEngine` / 전략 / CLI 어디에도 `requests` / `httpx` / `aiohttp` /
  `urllib` / KIS / DART / Telegram / `BrokerInterface` import 0건. 외부 호출
  0건 보장.
- 신호 데이터 (`backtest_results`) 에 broker / 주문 / 계좌 / 가격 / 수량 컬럼
  부재 — `ScoreSnapshot` 단계에서 이미 차단된다.
- v0.7 신규 테이블 2개 추가 후 누적 ALTER 5건 시점 → v0.8 의 Alembic 도입 진입
  적기 (운영 DB 마이그레이션 자동화 검토).

## 17. Alembic 운영 절차 (v0.8 Phase A)

v0.7-final 시점의 27 테이블을 baseline 으로 등록한 Alembic 도입이 v0.8 Phase A
에서 완료되었다. 본 섹션은 운영 DB 에 baseline 을 적용하고, 이후 Phase B/C
revision 을 안전하게 layering 하는 절차다.

**핵심 원칙**

- 운영 DB 변경은 항상 백업 → stamp / upgrade → smoke test → 실패 시 백업 복구.
- `alembic upgrade head` 를 자동화 (cron / CI deploy hook) 하지 않는다 — 운영자
  명시 실행 시점에만 동작한다.
- `alembic downgrade` 는 dev / 검증 전용. 운영 환경 롤백은 백업 복구가 원칙.
- Settings 의 `effective_database_url` 흐름 (DATABASE_URL > SQLITE_DATABASE_URL)
  을 그대로 따르며, ad-hoc 검증 시에만 `-x url=...` 또는
  `python -m scripts.migrate ... --db-url=...` 로 1회 override.

### 17.1 alembic 골격 (Phase A 산출)

| 파일 | 역할 |
|---|---|
| `alembic.ini` | 설정 (script_location = `alembic/`, sqlalchemy.url 비워둠) |
| `alembic/env.py` | `app.db.models.Base.metadata` 를 target_metadata 로 사용. URL 은 `-x url=` > `alembic.ini` > `Settings.effective_database_url` 순으로 결정. SQLite 시 `render_as_batch=True` |
| `alembic/script.py.mako` | revision 템플릿 |
| `alembic/versions/0001_baseline_v0_7.py` | v0.7-final 27 테이블 baseline |
| `scripts/migrate.py` | `alembic` 의 thin wrapper CLI (current / history / heads / upgrade / downgrade / stamp / offline-sql) |
| `tests/integration/test_alembic_migration.py` | upgrade head + compare_metadata 0건 + stamp / downgrade / offline-sql 검증 (16 케이스) |

### 17.2 신규 DB 초기화 (개발 / CI / 신규 운영)

빈 DB 에 처음 적재할 때:

```bash
# (1) Settings 가 가리키는 DB 에 27 테이블 baseline 생성
python -m scripts.migrate upgrade --to head

# (2) 현재 revision 확인
python -m scripts.migrate current

# (3) (개발용) mock seed 적재 — 17.x 의 seed_mock_data.py 절차 그대로
python -m scripts.seed_mock_data
```

`alembic upgrade head` 는 baseline (`0001_baseline_v0_7`) 을 즉시 적용하며,
이후 Phase B/C 에서 추가될 revision 도 한 번에 따라간다. `alembic_version`
테이블이 자동 생성되어 head revision 이 기록된다.

### 17.3 기존 운영 DB stamp 절차 (이미 27 테이블이 있는 경우)

v0.7-final 까지 운영자는 `Base.metadata.create_all()` 또는 mock seed 로 DB 를
구성했다. 이미 27 테이블이 있는 운영 DB 에 `alembic upgrade head` 를 그대로
실행하면 `CREATE TABLE` 충돌이 난다. 절차는 stamp 다.

```bash
# (0) 반드시 백업 먼저
cp ./stock_ai_kis_check.db ./stock_ai_kis_check.db.backup_$(date +%Y%m%d_%H%M%S)

# (1) 현재 DB 스키마와 baseline 정합성 확인 (drift 가 있으면 v0.7-final 이 아님 — 중단)
python -m scripts.migrate offline-sql --to head | head -20

# (2) baseline 으로 stamp — alembic_version 테이블만 새로 만들고 DDL 실행 0건
python -m scripts.migrate stamp --revision 0001_baseline_v0_7

# (3) 현재 revision 확인 — 0001_baseline_v0_7 출력
python -m scripts.migrate current

# (4) Phase B/C 의 후속 revision 만 적용 (현 시점에는 head 와 baseline 이 같으므로 no-op)
python -m scripts.migrate upgrade --to head
```

stamp 는 DDL 을 0건 실행하고 `alembic_version` 테이블에 baseline revision id
를 기록만 한다. 이후 추가될 Phase B (`0002_user_audit`) 와 Phase C
(`0003_watchlist`) revision 은 `upgrade head` 시 비-baseline 차이만 적용한다.

### 17.4 Phase B 이후 revision 추가 절차 (v0.8 후속 Phase)

Phase B/C 작업자가 새 ORM 모델 (User / LoginAuditLog / Watchlist /
WatchlistItem) 을 추가한 뒤:

```bash
# (1) ORM 변경 후 autogenerate revision 생성
#     (--rev-id 는 Phase B = 0002_user_audit / Phase C = 0003_watchlist 권장)
python -m alembic revision --autogenerate -m "user + login_audit_logs" --rev-id 0002_user_audit

# (2) 생성된 alembic/versions/0002_user_audit.py 를 검토 (autogen 결과를 그대로 사용하지 말 것)

# (3) 임시 DB 에서 round-trip 검증
python -m alembic -x url=sqlite:///./_revrt.db upgrade head
python -m alembic -x url=sqlite:///./_revrt.db downgrade -1
python -m alembic -x url=sqlite:///./_revrt.db upgrade head
rm ./_revrt.db

# (4) tests/integration/test_alembic_migration.py 가 그대로 그린인지 확인
pytest tests/integration/test_alembic_migration.py -q

# (5) 운영 DB 적용은 17.5 의 backup → upgrade → smoke 절차로 별도 진행
```

### 17.5 운영 DB upgrade 절차 (Phase B/C revision 적용)

```bash
# (0) 백업
cp ./stock_ai_kis_check.db ./stock_ai_kis_check.db.backup_$(date +%Y%m%d_%H%M%S)

# (1) (선택) 적용될 SQL 미리 검토
python -m scripts.migrate offline-sql --to head

# (2) 현재 revision 확인
python -m scripts.migrate current

# (3) upgrade — head 까지 모든 revision 순차 적용
python -m scripts.migrate upgrade --to head

# (4) smoke test
pytest -q tests/integration/test_alembic_migration.py
pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults

# (5) 화면 / API 수동 확인 (Today / Recommendations / 백테스트 4 화면 진입)
```

### 17.6 실패 시 롤백 원칙

- `alembic upgrade` 가 운영 DB 에서 실패한 경우 → **alembic downgrade 사용 금지**.
  17.5 (0) 에서 만든 `.backup_YYYYMMDD_HHMMSS` 파일을 그대로 복구한다.

  ```bash
  mv ./stock_ai_kis_check.db.backup_20260601_103000 ./stock_ai_kis_check.db
  ```

- 개발 / dev DB 에서는 `alembic downgrade -1` 또는 `--to base` 가 가능하다 —
  단, autogenerate 가 잘 처리하지 못한 (예: SQLite 의 일부 ALTER 한계) 경우가
  있을 수 있어 dev 환경에서도 백업이 권장된다.

- 신규 (빈) DB 에서 실패한 경우 → 단순히 DB 파일 삭제 후 17.2 처음부터 재실행.

### 17.7 Settings / 환경 변수 정합성

- `Settings.effective_database_url` = `DATABASE_URL or SQLITE_DATABASE_URL`.
- `alembic/env.py` 가 같은 값을 사용 (`-x url=...` override 가 없을 때).
- `pyproject.toml` 의존성에 `alembic>=1.13,<2.0` 추가됨 — 운영 환경 재배포 시
  `pip install -e ".[dev]"` 로 같이 깔린다.
- `.env` 의 `DATABASE_URL` / `SQLITE_DATABASE_URL` 값이 운영 DB 를 가리키는지
  17.5 진입 전 `python -m scripts.migrate current --db-url ...` 로 1회 명시
  검증 권장.

### 17.8 안전 가드 (Phase A 시점)

- 운영 DB 자동 migration 호출 0건 — 모든 명령은 운영자 명시 실행.
- `alembic` / `scripts/migrate.py` 어디에도 KIS / DART / RSS / 뉴스 / Telegram /
  Broker import 0건. 외부 호출 0건.
- POST / PUT / DELETE 라우터 추가 0건 (Phase A 는 인프라만).
- DB 모델 / ScoringEngine / RecommendationEngine / HoldingCheckEngine /
  BacktestEngine 변경 0건. ORM 27 테이블 그대로.
- CI 잡은 `RUNNER_TEMP/ci_alembic_smoke.db` 라는 임시 SQLite 만 사용 — 운영
  DB 0건 접근.

