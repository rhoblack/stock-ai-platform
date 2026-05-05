# AGENTS.md

## Project

This project is a Korean stock AI analysis, recommendation, holding-check, and
**analyst-report intelligence** platform based on the Korea Investment &
Securities API. Documentation may be Korean; code identifiers use English.

This file is the persistent instruction file for Codex. Codex should read and
follow this file every time it works on this repository.

**Current cycle baseline**: v0.4 Phase A complete (`v0.4-backend-reports`).
Cumulative scope = v0.1 Backend + v0.2 Frontend MVP + v0.3 Analysis/Ops +
v0.4 Phase A (DB models for analyst reports / themes / mappings / signal
events / consensus / score logs). Next: v0.4 Phase B — CSV import + consensus
snapshot job. Detailed history in [`ROADMAP.md`](./ROADMAP.md).

---

## Project Scope (v0.1 ~ v0.4 — cumulative)

The platform is **not** an auto-trading system. All four shipped cycles
preserve the read-only / no-auto-trade policy.

### Implemented (v0.1 ~ v0.4 Phase A)

- Korea Investment & Securities API data collection (read-only)
- Market-cap TOP 500 universe management
- Watchlist and holdings management
- Daily price and current price storage
- Technical indicators: MA5 / MA20 / MA60 / MA120 / RSI14 / MACD /
  volume_ratio_20d / breakout_20d / breakout_60d / ma_alignment
- **v0.3 — candle patterns (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING /
  BEARISH_ENGULFING) + Wilder ATR(14) + 4-band volatility classification**
- Pre-market and post-market holding checks
- Daily TOP-5 recommendation + 1/3/5/20-day performance tracking
- Recommendation history with performance backfill
- Telegram notifications (DRY_RUN by default)
- FastAPI **read-only** dashboard APIs (15+ GET endpoints, **0 POST**)
- **v0.2 — PC dashboard SPA (8 screens, Vite + React + TS)**
- **v0.3 — KRX holiday calendar (static JSON) + MarketStatusBanner**
- **v0.3 — `GET /api/stocks/{symbol}/prices` + StockDetail price chart**
- **v0.3 — GitHub Actions CI (3-job pipeline)**
- **v0.4 Phase A — analyst-report intelligence DB layer (6 ORM + 6 Repository)**
- data_snapshots / decision_logs / job_runs / notification_logs persistence
- Testable architecture (362 backend pytest baseline, 59 vitest, 8 e2e)

### Out of scope (v0.1 ~ v0.4 — cycle-wide policy)

Do **not** implement these — they apply to every cycle until an explicit
auto-trade cycle (separate compliance / security review) is requested:

- Real auto-trading
- Real Korea Investment & Securities order execution
- FULL_AUTO / APPROVAL / SMALL_AUTO modes
- POST / PUT / DELETE routers (read-only API only)
- Virtual broker server
- Strategy auto-tuning
- Custom AI model training
- Massive synthetic data generation
- Complete backtesting system
- Real-money trading workflow
- **(v0.4)** Auto-crawling of analyst reports — manual CSV/Excel import only
- **(v0.4)** Storing original report body / paragraph text — metadata + short
  operator-written summary (≤ 500 chars) only
- **(v0.4)** PDF BLOB storage in DB — `source_url` or `source_file_path` only
- **(v0.4)** Exposing `source_file_path` in API / frontend / e2e — masked
  everywhere

Order-related code may exist only as an interface (`BrokerInterface` ABC
placeholder), never as a working implementation.

---

## Core Architecture Rules

Follow these rules strictly:

- Data modules must not make investment decisions.
- Analysis modules must not place, simulate, or approve orders.
- AI modules must not directly trade.
- Recommendation and Holding modules must not call external APIs directly.
- Backend API routers must not calculate indicators or generate recommendations directly.
- RiskEngine is the final gate for any future execution.
- All future trading must go through BrokerInterface.
- No cycle (v0.1 ~ v0.4 and beyond, until an explicit auto-trade cycle) may
  execute real orders.
- API routers are **read-only GET only** — no POST / PUT / DELETE.
- Each module must keep a narrow responsibility.
- Prefer service/repository boundaries over large all-in-one scripts.
- **(v0.4)** Analyst report ingestion is **manual CSV/Excel only** — no
  auto-crawler. Original paragraph text / PDF body are never persisted.
- **(v0.4)** `source_file_path` is stored on disk for the operator's
  convenience but never exposed via API, frontend, e2e, or CLI summary output.

Correct data flow:

```text
External APIs
→ Data Collection
→ Repository
→ Analysis
→ Scoring
→ Recommendation / Holding Check
→ Risk Gate
→ Report / Notification / Dashboard
```

Future trading flow:

```text
Strategy Signal
→ AI Judgement
→ RiskEngine
→ BrokerInterface
→ TradeLogger
```

In v0.1 ~ v0.4, the future trading flow remains entirely disabled — no
implementation files exist for `Strategy Signal`, `BrokerInterface`
implementations, or `TradeLogger`.

---

## Required Logging and Snapshots

The system must preserve reasoning and historical context.

Required persistence rules:

- Store recommendation-time inputs in `data_snapshots`.
- Store all decision reasoning in `decision_logs`.
- Store scheduled job results in `job_runs`.
- Store Telegram delivery results in `notification_logs`.
- Store recommendation execution units in `recommendation_runs`.
- Store recommendation rows in `recommendations`.
- Store holding checks in `holding_checks`.

A recommendation or holding check should be explainable later using the snapshot and decision log that existed at the time of the decision.

---

## Core Tables

### v0.1 (17 tables — 마감)

- `stocks`, `holdings`, `daily_prices`, `stock_indicators`,
  `market_cap_rankings`, `stock_universes`, `stock_universe_members`,
  `news_items`, `market_regimes`, `recommendation_runs`, `recommendations`,
  `recommendation_results`, `holding_checks`, `data_snapshots`,
  `decision_logs`, `job_runs`, `notification_logs`

### v0.3 — additive nullable columns on `stock_indicators` (Phase B)

- `atr14 Numeric(20,4)`, `candle_patterns JSON`, `volatility_band String(16)`
  — all nullable, ALTER ADD only.

### v0.4 Phase A — analyst & theme intelligence (6 new tables)

- `analyst_reports` — all report types (COMPANY / SECTOR / INDUSTRY / THEME /
  COMMODITY / MACRO / STRATEGY) in one table, `symbol` nullable for
  theme/macro/commodity reports. Unique `(broker_name, published_at, title)`.
  **`source_file_path` is stored but masked in API responses.**
- `report_themes` — themes extracted from reports. `theme_category` 13 enums.
  Unique `(source_report_id, theme_name)`.
- `theme_stock_mappings` — theme → stock impact links. `impact_direction` /
  `impact_path` (11 enums) / `relation_type` (10) / `benefit_type` (6).
  Unique `(theme_id, symbol)`. Global tickers (US/NASDAQ/USD) supported.
- `report_signal_events` — discrete change signals (TARGET_PRICE_UP /
  SUPPLY_SHORTAGE / RISK_WARNING …). 18 `event_type` enums. Unique
  `(report_id, event_type, symbol, theme_id)`.
- `report_consensus_snapshots` — per-symbol per-window daily aggregates of
  COMPANY-type reports. Unique `(symbol, snapshot_date, window_days)`.
- `report_score_logs` — `report_score` + `theme_signal_score` calculation
  history with evidence JSON. Nullable FK to `recommendation_runs.run_id`.

Detailed column specs in [`DB_SCHEMA.md`](./DB_SCHEMA.md) §18~23.

Recommended table conventions:

- Use `created_at` and `updated_at` where appropriate.
- Add indexes for common lookups:
  - `symbol`
  - `date`
  - `run_id`
  - `snapshot_id`
  - `market`
- Use upsert behavior for daily market data.
- Avoid duplicate rows for the same `symbol + date` price data.

---

## Scoring Formulas

### New Recommendation Score

```text
total_score =
technical_score * 0.35
+ news_score * 0.25
+ supply_score * 0.15
+ fundamental_score * 0.15
+ ai_score * 0.10
- risk_penalty
```

### Holding Score

```text
holding_score =
technical_score * 0.35
+ news_score * 0.20
+ earnings_score * 0.20
+ ai_score * 0.15
+ profit_management_score * 0.10
- risk_penalty
```

### AI Score Rule

AI score must remain a supporting factor, not the dominant factor.

The program should calculate quantitative indicators and scores. AI should primarily help with:

- News summarization
- Risk explanation
- Recommendation reason writing
- Holding decision explanation
- Telegram report wording

AI must not directly execute or approve real orders.

---

## Module Boundaries

### KIS & Data

May:

- Call Korea Investment & Securities API.
- Normalize API responses.
- Save collected data.
- Validate missing or abnormal data.
- Manage market-cap TOP 500 universe data.

Must not:

- Recommend stocks.
- Calculate final investment decisions.
- Send Telegram messages.
- Execute orders.

---

### Analysis & Scoring

May:

- Calculate technical indicators.
- Calculate volume metrics.
- Calculate market/stock scores.
- Calculate risk penalties.
- Produce structured analysis results.

Must not:

- Call external APIs.
- Send Telegram messages.
- Execute orders.
- Select final recommendations by itself.
- Mutate portfolio or trade state.

---

### Recommendation & Holding

May:

- Create recommendation candidates.
- Generate final recommendation TOP lists.
- Create pre-market and post-market holding checks.
- Save snapshots and decision logs.
- Generate alert records.

Must not:

- Call Korea Investment & Securities API directly.
- Send Telegram directly.
- Execute orders.
- Recalculate low-level indicators directly when they should already exist.

---

### Notification & Report

May:

- Generate report text.
- Format Telegram messages.
- Send Telegram messages.
- Store notification results.

Must not:

- Change scoring formulas.
- Change recommendation logic.
- Call stock APIs.
- Execute orders.

---

### Backend API

May:

- Expose dashboard read APIs.
- Return reports, recommendations, holdings, stock details, market regimes, logs, and settings.
- Use Pydantic schemas.
- Use repositories/services for read access.

Must not:

- Run collectors directly inside routes.
- Calculate indicators inside routes.
- Generate recommendations inside routes.
- Send Telegram messages inside routes unless explicitly designed as an admin action.
- Execute orders.

---

### Test / Review / Docs

Must:

- Verify architecture boundaries.
- Check that the current cycle does not include real order execution.
- Add pytest tests for core logic.
- Update documentation when code behavior changes.
- Mock all external APIs in tests.

---

## Security Rules

Never commit or print:

- API keys
- account numbers
- access tokens
- refresh tokens
- Telegram bot token
- Telegram chat ID if considered private
- real account credentials

Required security rules:

- Use `.env` or secure configuration.
- Provide `.env.example` with placeholder values only.
- Mask secrets in logs.
- Do not put real credentials in tests.
- Do not hardcode secrets.
- Do not expose sensitive values in API responses.
- No cycle (v0.1 ~ v0.4 and beyond) may include active real order execution.

---

## Testing Rules

Use `pytest`.

Mock all external APIs.

Required tests:

- TechnicalAnalyzer
- ScoringEngine
- RecommendationEngine
- HoldingCheckEngine
- ReportGenerator
- Repository upsert/read behavior
- FastAPI dashboard endpoints
- Telegram message formatting
- DataQualityChecker

Recommended test categories:

```text
tests/unit/
tests/integration/
tests/mocks/
```

External API tests must use mock responses.

No test should require real KIS credentials.

---

## Development Workflow

Work in small steps.

Preferred order:

1. Architecture and interfaces
2. DB models and repositories
3. Minimal DevOps and `.env.example`
4. KIS client and data collectors
5. Technical analysis and scoring
6. Recommendation and holding check services
7. Telegram report generation
8. FastAPI dashboard APIs
9. Tests and documentation
10. Dashboard frontend

Do not advance to a future cycle / phase (e.g., from v0.4 Phase A to Phase B,
or from v0.4 to v0.5) unless explicitly requested by the project owner. The
current cycle baseline is recorded in [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
§0.

---

## Coding Agents (project-wide, v0.1 ~ v0.4)

Use these coding-agent roles when assigning work to Codex. Some agents are
cycle-specific (e.g., the v0.4 Analyst & Theme Intelligence agents); they
remain dormant until the relevant cycle is active.

### 1. PM / Architect Agent

Responsibilities:

- Maintain current cycle scope (v0.4 Phase B+ at present).
- Define folder structure.
- Define interfaces.
- Review dependency direction.
- Prevent overengineering.
- Update planning docs (PLANS / TASKS / PROJECT_STATUS / ROADMAP).

### 2. DB / Repository Agent

Responsibilities:

- SQLAlchemy ORM models.
- Repository layer.
- Migrations (`Base.metadata.create_all` for SQLite tests; ALTER ADD
  TABLE/COLUMN for production).
- Indexes.
- Upsert / idempotent helpers (`get_by_unique` → `create`).
- Snapshot/log table design.

### 3. KIS & Data Agent

Responsibilities:

- KIS API client.
- Data collectors.
- Data normalization.
- Data quality checks.
- Market-cap TOP 500 universe collection.

### 4. Analysis & Scoring Agent

Responsibilities:

- Technical indicators.
- Technical score.
- Market score.
- Recommendation score formula.
- Holding score formula.
- Unit tests for calculations.

### 5. Recommendation & Holding Agent

Responsibilities:

- Recommendation generation.
- Holding checks.
- Risk alert generation.
- Snapshot creation.
- Decision log creation.

### 6. Notification & Report Agent

Responsibilities:

- Report generation.
- Telegram message formatting.
- Telegram sending.
- Notification logging.

### 7. Backend API Agent

Responsibilities:

- FastAPI routes.
- Pydantic schemas.
- Dashboard read APIs.
- API tests.

### 8. Test / Review / Docs Agent

Responsibilities:

- Tests.
- Architecture review.
- Scope review.
- README updates.
- `.env.example`.
- Developer guide.
- Release notes (`RELEASE_NOTES_v0.X.md`).

### 9. Dashboard Frontend Agent (active since v0.2)

Responsibilities:

- Vite + React + TypeScript SPA.
- 8 dashboard screens (Today / Recommendations / History / Holdings /
  StockDetail / MarketCapTop / Jobs / Settings).
- TanStack Query / Table integrations, Recharts, Tailwind.
- vitest + msw (jsdom) and Playwright e2e (chromium + page.route mock).
- **Read-only only** — `<button type="submit">`, `<form>`, "주문 실행" CTAs
  must remain absent (e2e enforces this).
- Code splitting (`vendor-react/query/table/charts`, page-level lazy).

### 10. Ops / CI Agent (active since v0.3 Phase A)

Responsibilities:

- `.github/workflows/ci.yml` (3-job pipeline: backend pytest / frontend
  vitest+build / Playwright e2e).
- Docker compose (backend + nginx web + postgres) with safe defaults
  (`SCHEDULER_ENABLED=false`, `TELEGRAM_ENABLED=false`,
  `FEATURE_REAL_ORDER_EXECUTION=false`, `KIS_USE_PAPER=true`).
- Mock CI environment variables (no real KIS / Telegram credentials).
- `KIS_OPS_CHECKLIST.md` operator guidance.

### 11. Analyst Report Intelligence Agent (active since v0.4 Phase A)

Responsibilities:

- `analyst_reports` table — store metadata for all 7 report types (COMPANY /
  SECTOR / INDUSTRY / THEME / COMMODITY / MACRO / STRATEGY).
- `AnalystReportRepository` — CRUD + idempotent `upsert_unique` (skip on
  conflict).
- Enforce copyright policy at the schema layer:
  - `summary` ≤ 500 chars, operator-written only.
  - No `body` / `content` / `paragraph_text` / `full_text` / `본문` / `원문`
    / `전문` columns or fields, ever.
  - `source_file_path` stored but **never** echoed in API / frontend / e2e /
    CLI summary output.
- Global ticker support (market / exchange / country / currency /
  broker_country) so US/JP reports use the same table.
- `extraction_method` (MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED) and
  `extraction_confidence` (0~1) for downstream LLM workflows.

### 12. Import Pipeline Agent (v0.4 Phase B)

Responsibilities:

- `scripts/import_analyst_reports.py` — argparse CLI. **Default dry-run**;
  `--commit` to persist. Validates + summarizes.
- `app/data/importers/analyst_reports.py` — header-level rejection of
  forbidden body columns; row-level enum / date / numeric validation;
  truncation of `summary` > 500 chars with count.
- Single-file CSV: one row produces up to 4 entities (analyst_report +
  optional theme + N theme_stock_mappings + optional signal_event).
- Idempotent re-import: unique conflicts → `skipped_duplicates`.
- **Never** echo `source_file_path` in CLI output, error messages, or logs.
- **No auto-crawler / scraper** — manual operator-driven runs only. Auto
  fetching is a v0.5+ candidate after copyright review.

### 13. Theme Mapping Agent (v0.4 Phase B/C)

Responsibilities:

- `report_themes` (theme_category 13 enums) + `theme_stock_mappings`
  (impact_direction × impact_path 11 enums × relation_type 10 × benefit_type 6).
- Resolve `related_symbols` (semicolon/comma list) into N mappings per row.
- Provide read queries: `list_by_theme`, `list_by_symbol`,
  `list_positive_by_symbol`, `list_negative_by_symbol`, `list_by_impact_path`.
- Future: theme-name normalization (e.g., "HBM" vs "고대역폭 메모리") —
  v0.5+ candidate.

### 14. Report Scoring Agent (v0.4 Phase C)

Responsibilities:

- `app/analysis/report_score_calculator.py` — pure functions:
  - `report_score = clip(50 + target_upside_pct * 0.5 + rating_score_avg * 10
    + recency_bonus, 0, 100)` (null when `report_count = 0`).
  - `theme_signal_score = clip(50 + theme_bonus * 10 + event_bonus * 10 +
    recency_bonus - risk_penalty, 0, 100)` (null when no themes / events).
- RecommendationEngine integration: post-process `total_score` with **±5
  bonus per score (max ±10 combined)**. **Do not modify the base weight
  formula** (technical 35% / news 25% / supply 15% / fundamental 15% / ai
  10%).
- Persist evidence to `report_score_logs.evidence_json` and
  `decision_logs.rule_result_json["report_evidence"]`.
- Holding score formula remains unchanged in v0.4.

### 15. Auto Trading Agent (Future — gated)

⚠ **Not implemented in any cycle to date.** APPROVAL / SMALL_AUTO / FULL_AUTO
modes require:

- A separate compliance / security review cycle to precede activation.
- MockBroker / ReplayBroker / SimulationBroker validated first.
- Strategy + Backtest modules with proven track record.
- Capital limits, daily loss limits, per-symbol limits, per-strategy limits,
  emergency stop, real trade logging.
- KIS production key handling hardened beyond `.env`.

The `BrokerInterface` ABC remains a placeholder. No agent should propose
order-execution code without an explicit auto-trade cycle entry from the
project owner.

### Other Future Agents

Do not implement these unless explicitly requested:

- **Strategy Agent** — long/mid/short strategy management and signal
  generation. Gated on v0.5+ data (real News / Fundamentals).
- **Backtest Agent** — historical strategy testing, walk-forward validation,
  grid search.
- **Simulation Agent** — mock broker, replay broker, virtual market,
  synthetic data, synthetic news.
- **AI/LLM Agent** — stronger local/cloud LLM integration; custom AI models
  (Market Regime / Strategy Selection / Risk Prediction). The `extraction_method`
  /`extraction_confidence` fields on v0.4 tables are designed to receive
  LLM-assisted output safely when this agent activates.
- **News & Disclosure Agent** — replace `DummyScoreProducer.news_score` /
  `supply_score` with real pipelines.
- **Fundamentals & Earnings Agent** — replace
  `DummyScoreProducer.fundamental_score` / `earnings_score` with real
  pipelines (`FundamentalSnapshot` / `EarningsSnapshot` tables, DART API).
- **Watchlist & Auth Agent** — favorites, single-token API key, session
  hardening — gated on the first POST router introduction.
- **Operations Monitoring Agent** — Sentry / Prometheus / Grafana, KIS key
  rotation automation, Vault integration.

---

## Dashboard v0.1 Screens

The backend should support these dashboard views:

1. Today Report
2. Holding Checks
3. Recommendations
4. Recommendation History
5. Stock Detail
6. Market-cap TOP 500
7. Market Regime
8. News / Disclosures
9. Settings
10. System Logs

Dashboard should be detail-oriented on PC. Telegram should remain summary-oriented.

---

## Daily Schedule (current — v0.4 Phase A baseline)

The 6 jobs registered in `app/scheduler/scheduler.py`:

```text
18:00  collect_market_close_data            (KIS 시총 + 일봉)
18:30  calculate_technical_indicators       (지표 + 캔들/ATR/변동성, v0.3 Phase B+)
06:00  send_recommendation_report            (텔레그램 추천 발송, DRY_RUN 기본)
08:30  run_pre_market_holding_check
16:30  run_post_market_holding_check
17:00  update_recommendation_results         (1/3/5/20일 후 성과 갱신)
```

Planned additions:

- **v0.4 Phase B** — `update_report_consensus_snapshots` at **06:30 KST** (after
  06:00 telegram send, before 08:30 pre-market check) for the 7th job.

The original v0.1 plan also listed `19:00 collect news/disclosures` and
`20:00 market regime` slots — these remain in scope as v0.5+ candidates
(real News / Supply / Fundamental / Earnings pipelines, market regime model).

Scheduled jobs must write to `job_runs`.

Partial failure should not stop the whole system if the remaining report can still be generated.

Example:

```text
Price data succeeded.
News collection failed.
→ Generate report without news score.
→ Log news collection failure.
→ Notify system warning if needed.
```

---

## Definition of Done

A task is done only if:

- Code runs.
- Tests exist for core logic.
- Existing tests pass.
- No secret is exposed.
- Current cycle scope is respected (see [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) §0).
- Architecture boundaries are respected.
- Documentation is updated if behavior changed.
- External API calls are mocked in tests.

---

## Final Reminder

The purpose of every shipped cycle (v0.1 ~ v0.4) is **not** to maximize
trading profit.

The purpose is to build a stable, explainable, testable, **read-only**
foundation that can later (v0.5+ and beyond) be extended toward auto-trading
under separate compliance / security review:

```text
KIS data + KRX 휴장 캘린더 + 증권사 리포트 + 테마 매핑 + 시그널 이벤트
   → Analysis (지표 + 캔들 + ATR + 변동성)
   → Scoring (technical + dummy news/supply/fundamental/ai)
   → Recommendation / Holding check
   → Risk Gate
   → Snapshot / log
   → Telegram report (DRY_RUN)
   → Dashboard API + PC SPA
   → (v0.4 Phase C+) report_score / theme_signal_score 보조 가산
```

Auto-trading is **not** part of this foundation. Adding it requires a separate
compliance + security cycle that has not been started.

Future versions may add strategy, backtest, simulation, custom AI, and small-capital auto trading only after v0.1 is stable.
