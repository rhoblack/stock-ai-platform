# AGENTS.md

## Project

This project is a Korean stock AI analysis, recommendation, and holding-check platform based on the Korea Investment & Securities API.

The project language for documentation may be Korean. Code identifiers should use clear English names.

This file is the persistent instruction file for Codex. Codex should read and follow this file every time it works on this repository.

---

## v0.1 Goal

v0.1 is **not** an auto-trading system.

v0.1 must implement:

- Korea Investment & Securities API data collection
- Market-cap TOP 500 universe management
- Watchlist and holdings management
- Daily price and current price storage
- Technical indicators:
  - MA5
  - MA20
  - MA60
  - MA120
  - RSI14
  - MACD
  - volume_ratio_20d
  - breakout_20d
  - breakout_60d
  - ma_alignment
- Pre-market holding checks
- Post-market holding checks
- Daily top recommendation report
- Recommendation history storage
- Basic recommendation performance tracking
- Telegram notifications
- FastAPI dashboard APIs
- data_snapshots
- decision_logs
- job_runs
- notification_logs
- testable architecture

---

## Out of Scope for v0.1

Do **not** implement these features in v0.1:

- Real auto trading
- Real Korea Investment & Securities order execution
- FULL_AUTO mode
- Virtual broker server
- Strategy auto tuning
- Custom AI model training
- Massive synthetic data generation
- Complete backtesting system
- Real-money trading workflow

Order-related code may exist only as an interface, placeholder, or disabled future extension.

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
- v0.1 must not execute real orders.
- Each module must keep a narrow responsibility.
- Prefer service/repository boundaries over large all-in-one scripts.

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

In v0.1, the future trading flow must remain disabled.

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

Required v0.1 tables:

- `stocks`
- `holdings`
- `daily_prices`
- `stock_indicators`
- `market_cap_rankings`
- `stock_universes`
- `stock_universe_members`
- `news_items`
- `market_regimes`
- `recommendation_runs`
- `recommendations`
- `recommendation_results`
- `holding_checks`
- `data_snapshots`
- `decision_logs`
- `job_runs`
- `notification_logs`

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
- Check that v0.1 does not include real order execution.
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
- v0.1 must not include active real order execution.

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

Do not add v0.2+ features unless explicitly requested.

---

## v0.1 Coding Agents

Use these coding-agent roles when assigning work to Codex.

### 1. PM / Architect Agent

Responsibilities:

- Maintain v0.1 scope.
- Define folder structure.
- Define interfaces.
- Review dependency direction.
- Prevent overengineering.

### 2. DB / Repository Agent

Responsibilities:

- SQLAlchemy ORM models.
- Repository layer.
- Migrations.
- Indexes.
- Upsert logic.
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

---

## Future Agents

Do not implement these in v0.1 unless explicitly requested.

### Dashboard Frontend Agent

For React or Next.js PC dashboard.

### Strategy Agent

For long/mid/short strategy management and signal generation.

### Backtest Agent

For historical strategy testing and performance metrics.

### Simulation Agent

For mock broker, replay broker, virtual market, synthetic data, and synthetic news.

### AI/LLM Agent

For stronger local/cloud LLM integration and future custom AI models.

### DevOps Agent

For Docker, deployment, backup, scheduling, and production runtime hardening.

### Security Agent

For real-trading preparation and credential hardening.

### Auto Trading Agent

For APPROVAL and SMALL_AUTO modes after sufficient testing.

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

## Daily Schedule v0.1

Recommended schedule:

```text
18:00  Collect Korean market close data
18:30  Calculate technical indicators
19:00  Collect news/disclosures
20:00  Calculate market regime
21:00  Generate preliminary recommendation candidates
05:30  Reflect US/global market context
06:00  Send daily recommendation Telegram report
08:30  Run pre-market holding check
16:30  Run post-market holding check
17:00  Update recommendation/holding performance
```

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
- v0.1 scope is respected.
- Architecture boundaries are respected.
- Documentation is updated if behavior changed.
- External API calls are mocked in tests.

---

## Final Reminder

The purpose of v0.1 is not to maximize trading profit.

The purpose of v0.1 is to build a stable, explainable, testable foundation:

```text
Data collection
→ Analysis
→ Scoring
→ Recommendation
→ Holding check
→ Snapshot/log
→ Telegram/report
→ Dashboard API
```

Future versions may add strategy, backtest, simulation, custom AI, and small-capital auto trading only after v0.1 is stable.
