# Stock AI Platform

[![CI](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/rhoblack/stock-ai-platform/actions/workflows/ci.yml)

한국투자증권 API 기반 AI 주식 분석·추천·보유점검 플랫폼입니다.

> **v0.16 Real Order Integration Skeleton — 마감 완료.**
> 최종 마감 태그 `v0.16-final`. v0.16 은 v0.15 위에 **RealTradingSettings (5 신규 필드,
> paranoid defaults) + KIS Order Wrapper Skeleton (FakeKisOrderTransport) +
> RealOrder / RealFill ORM (40·41번째, Alembic 2 revisions) + RealOrderExecutor
> (8-gate dry-run 전용) + FillSyncService (mock transport 주입형) +
> 15번째 프런트 화면 `/real-orders` (read-only dry-run 결과 표시)** 5 Phase 를 완성한 사이클이다.
> **Phase A** (`RealTradingSettings` 5 신규 필드 — `real_trading_enabled=False` /
> `kis_order_enabled=False` / `real_order_dry_run=True` / `max_real_order_amount=5M` /
> `max_real_daily_order_amount=50M` + `can_attempt_real_order_settings()` helper) →
> **Phase B** (`KisOrderClientInterface` ABC + `KisOrderRequest` / `KisOrderResult` 불변 dataclass +
> `FakeKisOrderTransport` + `mask_sensitive_order_payload()` + AST 가드) →
> **Phase C** (`RealOrder` ORM 40번째 + `RealFill` ORM 41번째 + Alembic 0009/0010 +
> `RealOrderRepository` / `RealFillRepository`) →
> **Phase D** (`RealOrderExecutor` 8-gate 안전 검사 + `FillSyncService` mock + dry-run 전용 실행) →
> **Phase E** (`/real-orders` 15번째 프런트 화면 + backend GET API 2종 +
> `RealTradingSafetyBanner` 항상 표시 + RELEASE_NOTES_v0.16 + 4 게이트 최종 확인,
> vitest +13 / e2e +1).
> **실 KIS HTTP 호출 0건** — `FakeKisOrderTransport` 전용 (`httpx` / `requests` / `urllib`
> import AST 가드). **KIS API key / secret / 계좌번호 평문 저장 0건** —
> `mask_sensitive_order_payload` + `broker_order_no_hash` (SHA-256 hex 만). 실 KIS 주문 /
> 자동매매 / FULL_AUTO / SMALL_AUTO 코드 0건은 그대로 (v0.1 ~ v0.16 일관). 모든 실거래
> 게이트 기본값: `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` /
> `REAL_ORDER_DRY_RUN=true`. 운영자가 명시적으로 활성화하지 않으면 아무 변화도 없다.
>
> 최신 통과 회귀 게이트 — **백엔드 pytest 1905 / frontend vitest 214 /
> Playwright e2e 24 / build 통과**. 자동매매 / 실 주문 / FULL_AUTO /
> SMALL_AUTO 는 모든 사이클에서 코드 일체 포함하지 않습니다 (`BrokerInterface` 의
> 첫 구현체는 paper 전용 `SimulationBroker` 하나뿐 — KIS / 실거래 브로커는 여전히
> placeholder). 인증 (`AUTH_ENABLED=false` 기본) 이므로 기존 read-only GET API 는
> 그대로 OPEN; mutation 은 AUTH + (`PAPER_TRADING_ENABLED` 또는
> `TRADING_SAFETY_ENABLED + KILL_SWITCH_ENABLED=false`) 양쪽 필요. 자세한 정책은
> [`AGENTS.md`](./AGENTS.md) / [`ROADMAP.md`](./ROADMAP.md) 참조.
>
> **저작권 / 데이터 정책 (v0.4 ~ v0.12 누적)**: 리포트·뉴스·공시·재무·실적 원문 본문
> (paragraph) 저장 0건, PDF / Excel BLOB 저장 0건, 자동 크롤링 0건,
> `source_file_path` 외부 노출 0건. `WatchlistItem` / `UserPreference` / backtest
> 관련 ORM 에 broker / account / quantity / order_* 컬럼 0건.
> **평문 IP / 평문 password 저장 0건** — `LoginAuditLog.source_ip_hash` 는
> SHA256 만, password 는 scrypt hash 만. 알림 설정 UI 는 저장 전용 — 실 Telegram
> 발송 0건. **DART_API_KEY / crtfc_key / RSS feed URL 의 query string secret 은
> 응답 / 로그 / UI 어디에도 평문 노출 0건** — `SensitiveFilter` (6 변형 마스킹) +
> 공유 `SensitiveQueryStringFilter` (httpx INFO 로그의 `?crtfc_key=...` /
> `?api_key=...` 자동 마스킹) + transport `error_message` 가 예외 클래스명만
> carry + Provider Health 응답에서 `last_error_message` 의도적 미포함 + paranoid
> forbidden substring scan. **외부 API 자동 호출 0건** — 모든 테스트에서
> `respx` transport-layer mock + `httpx.Client` 미생성 단언 병행.
>
> **누적 인수 태그**: `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
> → `v0.2-frontend-final` → `v0.3-phase-a-ci` → `v0.3-backend-analysis` →
> `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final` →
> `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` →
> `v0.4-frontend-reports` → `v0.4-final` →
> `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` →
> `v0.5-frontend-themes` → `v0.5-final` →
> `v0.6-fundamental-data-layer` → `v0.6-earnings-event-pipeline` →
> `v0.6-fundamental-score` → `v0.6-frontend-fundamentals` → `v0.6-final` →
> `v0.7-strategy-interface` → `v0.7-backtest-engine` → `v0.7-backtest-cost-regime`
> → `v0.7-frontend-backtest` → `v0.7-final` →
> `v0.8-alembic-baseline` → `v0.8-auth-foundation` → `v0.8-watchlist-api`
> → `v0.8-frontend-watchlist` → `v0.8-final` →
> `v0.9-security-hardening` → `v0.9-monitoring` → `v0.9-watchlist-api`
> → `v0.9-frontend` → `v0.9-final` →
> `v0.10-provider-runtime` → `v0.10-provider-resilience` → `v0.10-dart-provider`
> → `v0.10-rss-provider` → `v0.10-health-api` → `v0.10-final` →
> `v0.11-dart-transport` → `v0.11-rss-transport` → `v0.11-observability` →
> `v0.11-health-extended` → `v0.11-final` →
> `v0.12-provider-ingestion` → `v0.12-walk-forward` → `v0.12-multi-strategy` →
> `v0.12-scoring-readonly` → `v0.12-final` →
> `v0.13-provider-policy` → `v0.13-score-delta` → `v0.13-validation-api` →
> `v0.13-validation-ui` → `v0.13-final` →
> `v0.14-export-policy` → `v0.14-sim-broker` → `v0.14-pnl-tracker` →
> `v0.14-paper-api` → `v0.14-final` →
> `v0.15-safety-settings` → `v0.15-order-candidate` → `v0.15-pre-trade-risk` →
> `v0.15-approval-api` → `v0.15-final` →
> `v0.16-real-trading-settings` → `v0.16-kis-order-wrapper` → `v0.16-real-order-orm` →
> `v0.16-real-order-executor` → **`v0.16-final`**.
>
> 이전 사이클 마감 사유: [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md)
> (백엔드, 296 passed) / [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md)
> (PC 대시보드 8 화면, vitest 36 / e2e 6) / [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md)
> (v0.3 분석·운영, 319 / 59 / 8) / [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md)
> (v0.4 Analyst & Theme Intelligence, 382 / 60 / 9) /
> [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md) (v0.5 News·공시·테마 랭킹, 481 / 68 / 11) /
> [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md) (v0.6 Fundamental & Earnings,
> 558 / 77 / 13) /
> [`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md) (v0.7 Strategy & Backtest,
> 682 / 84 / 14) /
> [`RELEASE_NOTES_v0.8.md`](./RELEASE_NOTES_v0.8.md) (v0.8 User & Migration Foundation,
> 808 / 113 / 19) /
> [`RELEASE_NOTES_v0.9.md`](./RELEASE_NOTES_v0.9.md) (v0.9 Operational Security &
> Watchlist Polish, 916 / 146 / 19) /
> [`RELEASE_NOTES_v0.10.md`](./RELEASE_NOTES_v0.10.md) (v0.10 Real Provider Readiness
> & Resilience, 1045 / 153 / 20) /
> [`RELEASE_NOTES_v0.11.md`](./RELEASE_NOTES_v0.11.md) (v0.11 Real Provider Transport
> & Observability, 1119 / 158 / 21) /
> [`RELEASE_NOTES_v0.12.md`](./RELEASE_NOTES_v0.12.md) (v0.12 Provider Data Scoring
> & Backtest Validation, 1194 / 165 / 21) /
> [`RELEASE_NOTES_v0.13.md`](./RELEASE_NOTES_v0.13.md) (v0.13 Provider Score Policy
> & Validation Report, 1277 / 175 / 21) /
> [`RELEASE_NOTES_v0.14.md`](./RELEASE_NOTES_v0.14.md) (v0.14 Paper / Simulation
> Trading Foundation, 1438 / 186 / 22) /
> [`RELEASE_NOTES_v0.15.md`](./RELEASE_NOTES_v0.15.md) (v0.15 Approval Trading
> Safety Layer, 1693 / 201 / 23) /
> [`RELEASE_NOTES_v0.16.md`](./RELEASE_NOTES_v0.16.md) (v0.16 Real Order Integration
> Skeleton, **1905 / 214 / 24**). 다음 사이클 후보는 [`ROADMAP.md`](./ROADMAP.md) v0.17 참조.

## 1. 프로젝트 목표

본 프로젝트는 **실거래 자동매매가 아닌 read-only 분석 / 추천 / 보유점검 +
증권사 리포트·테마 인텔리전스 + News·공시 데이터 라인 + 재무·실적 인텔리전스 +
Strategy & Backtest 검증 + 대시보드** 플랫폼입니다.

현재까지 마감된 사이클 (v0.1 ~ v0.16) 의 누적 기능:

- 한국투자증권 API 기반 read-only 데이터 수집
- 시가총액 TOP 500 종목 유니버스 관리
- 관심종목 / 보유종목 관리
- 일봉 / 현재가 저장
- 기술적 지표 (MA / RSI / MACD / breakout / ma_alignment) + **캔들 5종 / Wilder ATR(14) / 4단계 변동성** (v0.3)
- 보유 종목 장전 / 장후 점검
- 신규 추천 TOP 5 + 1/3/5/20일 후 성과 검증
- 텔레그램 알림 (DRY_RUN 기본)
- FastAPI **read-only** 대시보드 API (17+ GET, **POST 0건**)
- **PC 대시보드 SPA** (14 화면, Vite + React + TypeScript) — v0.2 → v0.15
- **KRX 휴장일 정적 캘린더 + MarketStatusBanner** — v0.3
- **StockDetail 일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자** — v0.3
- **GitHub Actions CI** (3 잡: backend pytest / frontend vitest+build / Playwright e2e) — v0.3
- **증권사 애널리스트 리포트 인텔리전스 DB 기반** (6 ORM + 6 Repository) — v0.4
- **CSV import pipeline + 일별 컨센서스 스냅샷 잡** — v0.4
- **`report_score` / `theme_signal_score` 추천 보조 통합** — v0.4
- **StockDetail 리포트/컨센서스/테마/시그널 카드 + Recommendations score 컬럼** — v0.4
- **News / 공시 데이터 라인** — `NewsProviderInterface` / `DisclosureProviderInterface` ABC + `NewsCollector` / `DisclosureCollector` + `news_items.category` + 공시 5 카테고리 keyword 분류 + `collect_news` (19:00) / `collect_disclosures` (20:00) 잡 (모두 default OFF) — v0.5
- **`news_score` 첫 real 화 + RiskEngine 보강** — `RealNewsScoreProducer` (composition 패턴) + `DisclosureRiskProducer` (`RISK_DISCLOSURE` flag + cap +10 penalty) + `ScoreProducerInterface` ABC — v0.5
- **테마 랭킹 / 상세 화면** — `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` + 프런트 9번째 화면 `/themes` + `/themes/:theme_id` + Sidebar `테마 (β)` 메뉴 — v0.5
- **추천 응답 evidence 노출** — `RecommendationItemSchema.news_evidence` + `disclosure_risk_evidence` (whitelist 안전 필드만) + `RelatedThemesCard` 테마 링크 + `RecommendationsTable` evidence 컬럼 — v0.5
- **재무 / 실적 데이터 라인** — `FundamentalProviderInterface` / `EarningsProviderInterface` ABC + `FundamentalSnapshot` (24번째) + `EarningsEvent` (25번째) ORM + `scripts/import_fundamentals.py` / `scripts/import_earnings.py` argparse CLI (default dry-run) + BEAT/MEET/MISS 분류 + `FakeFundamentalProvider` / `FakeEarningsProvider` (실 DART 호출 0건) — v0.6
- **`fundamental_score` + `earnings_score` 첫 real 화** — `RealFundamentalScoreProducer` (composition 패턴, recommendation 가중치 15%) + `RealEarningsScoreProducer` (HoldingCheckEngine). 산식 모두 룰 기반, snapshot/event 부재 시 50 fallback. 본 weight 변경 0건 — v0.6
- **재무 / 실적 read-only API 3종** — `GET /api/stocks/{symbol}/fundamentals` + `GET /api/stocks/{symbol}/earnings` + `GET /api/calendar/earnings` (모두 read-only, source_file_path 0건) — v0.6
- **StockDetail 두 카드 + Today 한 카드 + Recommendations / Holdings evidence** — `FundamentalsCard` (PER/PBR/ROE/부채/배당/성장률 + history) + `EarningsCard` (BEAT/MEET/MISS tone-color badge + actual vs consensus + history) + `UpcomingEarningsCard` (limit 5) + `RecommendationsTable` 의 fund/earnings evidence cell + `RecentHoldingChecksCard` 의 earnings evidence 컬럼 + `HoldingCheckSchema` 의 evidence 3종 (v0.5 이연분 흡수) — v0.6
- **`StrategyInterface` ABC + 룰 기반 전략 3종** — `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` (모두 pure-function + `[0, 1]` confidence clamp + null/malformed evidence raise 0건). `StrategySignal` BUY/PASS/AVOID 는 분석 신호이지 매매 주문 아님 — `ScoreSnapshot` 에 broker / quantity / order 필드 0건 가드 — v0.7
- **`BacktestEngine` + 신규 테이블 2개 (`backtest_runs` 26번째 + `backtest_results` 27번째)** — 과거 `recommendations` + `recommendation_results` 위에 전략을 replay 해서 승률 / 평균 수익률 / max drawdown 계산. BUY-only metrics 정책 + horizon 별 missing_result_count + cascade delete + `scripts/run_backtest.py` argparse CLI (default dry-run, `--commit` 시 적재) — v0.7
- **`CostModel` placeholder + 시장 국면별 분리** — `total_cost = 0.33%` 차감 (`constant-v1`) + `assign_regime(session, signal_date)` (`MarketRegime.date <= signal_date` 가장 최근). `cost_adjusted_return_5d` / `regime` 컬럼 + `regime_breakdown` summary. 실 broker fee schedule fetch 는 v0.8+ 후보 — v0.7
- **백엔드 백테스트 read-only API 3종** — `GET /api/strategies` (registry 기반, DB 0건) + `GET /api/backtest/runs?strategy=&limit=` + `GET /api/backtest/runs/{run_id}` (regime breakdown + cost_model_version + BUY-only notes) — v0.7
- **프런트 10번째 화면 `/backtest` (Sidebar `백테스트 (β)`)** — 상단 전략 카드 grid + 중단 클릭 가능한 run 표 (전략 filter radiogroup) + 하단 detail 패널 (regime breakdown + 신호 row 표 + cost_model badge + BUY-only note). 자동매매 / order CTA 0건 — v0.7
- **Alembic baseline 도입 (v0.8)** — 27 테이블 baseline (`0001`) + 인증 (`0002`) + Watchlist (`0003`), `compare_metadata` 0건 가드, CI smoke step
- **단일 사용자 인증 (v0.8)** — `AUTH_ENABLED` 토글 + JWT HS256 + scrypt password hash + `LoginAuditLog` (source_ip_hash SHA256) + `scripts/create_admin.py` CLI
- **Watchlist 도메인 GET/POST/DELETE (v0.8)** — `Watchlist` (30번째 테이블) + `WatchlistItem` (31번째) + 5 라우터 + cross-user 404 격리 + spoofing 가드 + broker/account/quantity/order_* 컬럼 0건
- **Watchlist 프런트 11번째 화면 + Login (v0.8)** — `/watchlist` (WatchlistListPanel / DetailPanel / AddItemForm) + `/login` (AUTH_ENABLED=false 자동 redirect) + StockDetail `FavoriteButton` + Today `WatchlistCard`
- **Security Hardening (v0.9)** — `SecurityHeadersMiddleware` (4종 헤더) + slowapi rate limit (login 5/min / others 100/min / exempt UUID test모드) + `BruteForceGuard` (composite key + generic 401 + LOCKOUT_REJECTED 감사 로그)
- **구조화 로깅 · 모니터링 (v0.9)** — `RequestIDMiddleware` (X-Request-ID 전파) + `SensitiveFilter` (password/token/secret 마스킹) + `LOG_FORMAT=json` 옵션 + optional Sentry (`SENTRY_ENABLED=false` 기본, `send_default_pii=False`) + 프런트 `ErrorBoundary`
- **Watchlist API 고도화 (v0.9)** — `PATCH /api/watchlists/{id}` (rename / set-default) + `DELETE /api/watchlists/{id}` + `GET /api/watchlists/{id}/items` (페이지네이션 + symbol_prefix) + `PATCH /api/watchlists/{id}/items/{symbol}` (memo)
- **UserPreference — 32번째 테이블 (v0.9)** — `user_preferences` ORM + Alembic `0004_user_preferences` + `GET /api/users/me/preferences` / `PUT /api/users/me/preferences` + `default_watchlist_id` FK (ON DELETE SET NULL) + `default_market` / `default_strategy` / `notification_preferences_json`
- **Provider Resilience skeleton (v0.9)** — `ProviderCallResult` / `ProviderErrorKind` + `retry_with_backoff()` (지수 백오프, CLIENT_ERROR 비재시도) + `CircuitBreaker` (CLOSED→OPEN→HALF_OPEN→CLOSED). 실 provider 강제 적용 0건
- **Frontend 관리 UI (v0.9)** — Watchlist 인라인 rename/delete/set-default/memo edit/item filter + Settings UserPreference 섹션 + Today/StockDetail `useEffectiveDefaultWatchlistId` preference priority chain
- **Provider Resilience Runtime (v0.10)** — `ProviderHealthMonitor` (registry / call_count / success_count / failure_count / last_error_kind / circuit_state) + `call_with_resilience(provider_name, fn, ...)` (retry + circuit breaker + failure isolation, **never raises**) + 6 settings (`PROVIDER_RESILIENCE_ENABLED=False` 기본 + timeout / max_attempts / base/max delay / breaker threshold / reset timeout)
- **DART Provider Skeleton (v0.10)** — `DartFundamentalProvider` / `DartEarningsProvider` / `DartDisclosureProvider` (모두 `_DartProviderBase` 상속, transport 주입형). `parse_fundamentals` (whitelist account 6종) + `parse_earnings` (actual 만, consensus None) + `parse_disclosures` (rcept_no/rcept_dt 누락 row 개별 skip). Forbidden body field (`body / content / full_text / paragraph / raw_text / html_body / 본문 / 원문 / 전문`) 사전 strip + DTO 자체에 부재. `crtfc_key` 는 `_call` 내부에서만 params 에 주입; `SensitiveFilter` 가 6 변형 (`dart_api_key / DART_API_KEY / crtfc_key / CRTFC_KEY / crtfckey / dart_key`) 마스킹. `DART_ENABLED=False` 기본
- **RSS/News Provider Skeleton (v0.10)** — `RssNewsProvider` (RSS 2.0 + Atom 동시 지원, root tag 자동 분기). `_parse_rss_item` / `_parse_atom_entry` 모두 metadata 만 추출 (`<content>` 미참조). `<description>` HTML 태그 정규식 strip + summary 500자 truncate + URL dedup first-wins (`news_items.url` UNIQUE 정합). `_safe_url_for_log` 가 query string + fragment strip 후 host + path 만 로그 → feed URL 의 `?api_key=...` 평문 노출 0건. `RSS_NEWS_ENABLED=False` / `RSS_FEED_URLS=""` 기본. **신규 pip 의존성 0건** (stdlib `xml.etree.ElementTree` only)
- **Provider Health API + UI (v0.10)** — `GET /api/health/providers` (read-only, POST/PUT/DELETE 모두 405). canonical 3 provider (`kis` / `dart` / `rss`) 항상 노출 + experimental provider monitor iteration 순서 append. `last_error_message` 응답 미포함 (URL query secret 누출 차단) — `last_error_kind` enum 만 노출. Settings 화면에 `ProviderHealthPanel` (read-only table, 9열, badge 색상별 circuit_state, 패널 내 button / form 0건)
- **DART HTTP Transport (v0.11)** — `HttpxDartTransport` (lazy httpx import + `httpx.Client(base_url=settings.dart_base_url, timeout=settings.dart_timeout_s)`). `create_dart_providers(transport=None)` + `DART_ENABLED=true` + `DART_API_KEY` 시 자동 주입. HTTP/DART status (`000`/`010..101`/`800/900`) → `ProviderCallResult` 매핑, `httpx.HTTPError.__str__` 미포함 (URL secret 누출 차단). `respx` mock 27 케이스
- **RSS HTTP Transport (v0.11)** — `HttpxRssTransport` (`follow_redirects=True`). `create_rss_provider(transport=None)` + `RSS_NEWS_ENABLED=true` + `RSS_FEED_URLS` 시 자동 주입. HTTP 200 → `ok(response.content)` (parser 가 인코딩 처리). `respx` mock 19 케이스
- **공유 SensitiveQueryStringFilter (v0.11)** — Phase A 의 dart_provider 내부 헬퍼를 `app/config/logging.py` 로 추출 → DART/RSS 양쪽 transport 가 idempotent 설치. httpx INFO 로그의 `?crtfc_key=ABC&...` / `?api_key=XYZ&...` / `?token=...` 등을 `=***` 로 자동 마스킹
- **Provider Observability + Prometheus exporter (v0.11)** — `ProviderHealthMonitor` 에 bounded ring buffer (`recent_calls` deque maxlen=200 + `recent_failures` deque maxlen=50) + `Summary24h(call_count_24h / success_count_24h / failure_count_24h / success_rate_24h / avg_attempts)`. optional `prometheus-client` (Apache 2.0): 4 Counter + 1 Gauge (circuit_state CLOSED=0/OPEN=1/HALF_OPEN=2/UNREGISTERED=3) + 1 Histogram (attempts). `GET /metrics` → `PROMETHEUS_ENABLED=false` 기본 시 404, true 시 200+text/plain. POST/PUT/DELETE 405. lazy `_emit_prometheus` hook (try/except 격리)
- **Provider Health API/UI 24h aggregates (v0.11)** — `/api/health/providers` 6 신규 필드 (`call_count_24h` / `success_count_24h` / `failure_count_24h` / `success_rate_24h: float?` / `avg_attempts_24h: float?` / `recent_failures: list[5]`). `RecentFailureSummary` 는 `{timestamp, error_kind}` 만 (message 필드 부재). Settings 패널에 `SuccessRateBar` (≥99% emerald / ≥95% amber / <95% red / null slate) + `avg_attempts` 셀 + `RecentFailuresList` 카드 (실패 1건+ provider 만 노출). 패널 내 button / form / switch 0건 유지
- data_snapshots / decision_logs / job_runs / notification_logs persistence
- **Provider Data Ingestion (v0.12)** — `app/data/ingestion.py` 4 어댑터 (`ingest_dart_disclosures` / `ingest_rss_news` / `ingest_dart_fundamentals` / `ingest_dart_earnings`). `PROVIDER_DATA_INGESTION_ENABLED=False` 기본. 4 DTO 에 `data_source: str` provenance (`PROVIDER`/`FAKE`/`CSV`/`MANUAL`). ScoringEngine weight 변경 0건 / Alembic revision 0건
- **Walk-forward Backtest Engine (v0.12)** — `WalkForwardBacktestEngine` + `generate_folds()` (60/20일 기본 sliding, IS/OOS 겹침 없음) + IS/OOS `win_rate_5d` / `avg_return_5d` 집계 + `summary_json["walk_forward_folds"]` 직렬화 + CLI `--walk-forward` / `--train-window-days` / `--validate-window-days` / `--gap-days`
- **Multi-strategy Comparison + Sector Breakdown (v0.12)** — `MultiStrategyRunner` + `SectorBreakdownEntry` + `aggregate_sector_breakdown()` + `summary_json["multi_strategy_comparison"]` 직렬화 + `best_strategy_by_win_rate_5d` / `_by_avg_return_5d` ranking + CLI `--multi` / `--strategies`
- **Backtest read-only API 확장 (v0.12)** — `GET /api/backtest/runs/{id}/folds` + `GET /api/backtest/runs/{id}/comparison` (GET only, mutation 405). fold 표 / comparison 표 / sector breakdown / best strategy 배지 / `data_source` chip (PROVIDER=파랑 / FAKE=황 / CSV=보라 / MANUAL=회색) 프런트 보강
- **ProviderScorePolicy 승수 엔진 (v0.13)** — `PROVIDER=1.00` / `CSV=0.90` / `MANUAL=0.80` / `FAKE=bypass`. `PROVIDER_SCORE_POLICY_ENABLED=False` 기본 — 명시 enable 시에만 적용. ScoringEngine weight 변경 0건
- **Score Delta in evidence_json (v0.13)** — `ScoreDeltaResult` (`score_before`/`score_after`/`delta`/`components[]`) ROUND_HALF_UP 4dp. `RecommendationEngine` / `HoldingCheckEngine` 선택 파라미터 — Alembic 0건 (기존 `evidence_json` JSON 컬럼 재활용)
- **Validation Report read-only API 4종 (v0.13)** — `GET /api/validation/report` + `/by-strategy` + `/by-regime` + `/by-sector`. POST/PUT/PATCH/DELETE → 405. forbidden field guard (`evidence_json` raw / `source_file_path` 미노출)
- **Validation Report 프런트 12번째 화면 (v0.13)** — `/validation` (전체 요약 카드 + ScoreDelta 카드 + 전략·국면·섹터 표 + data_source chip). `ClipboardCheck` sidebar 아이콘. `useValidationReport` TanStack Query hooks (`staleTime: 60_000`)
- **Backtest Export CLI (v0.14)** — `scripts/export_backtest.py` argparse CLI (`--run-id` / `--format csv|json` / `--output PATH` / `--dry-run`). `FORBIDDEN_EXPORT_FIELDS` 가드 (evidence_json / source_file_path / config_json / summary_json / reason 미노출)
- **SimulationBroker — BrokerInterface 첫 구현체 (v0.14)** — `app/broker/simulation_broker.py`. paper / simulation 전용. `submit_order` (PAPER_TRADING_ENABLED=false 시 거부 + idempotency_key 중복 → 기존 row + `deduplicated=true`) / `cancel_order` (CREATED·SUBMITTED → CANCELED) / `execute_pending_orders` (daily_prices.close 기반 매칭, MARKET 즉시 / LIMIT crossing / no-price skip / cash·position 부족 → REJECTED). KIS / DART / RSS / requests / httpx import 0건 (AST 회귀 단언)
- **VirtualAccount / VirtualOrder / VirtualPosition / VirtualFill / VirtualPnLSnapshot — 5 신규 ORM (v0.14)** — Alembic 2 revisions (`0005_virtual_trading_core` Phase B + `0006_virtual_positions` Phase C). 누적 37 테이블. forbidden 컬럼 0건 (broker_order_id / kis_order_id / real_account / api_key / token / secret)
- **PnLTracker (v0.14)** — `app/paper/pnl_tracker.py`. `apply_fill` BUY 시 cash↓·position↑·avg_cost cost-basis blend / SELL 시 cash↑·realized_pnl 누적·zero 도달 시 avg_cost 리셋. `create_daily_pnl_snapshot` open positions × daily_prices.close (가격 없는 종목은 0 graceful). `InsufficientCashError` / `InsufficientPositionError` 로 BUY/SELL 차단
- **PaperTradingCostModel paper-v1 (v0.14)** — buy_fee/sell_fee 0.015% / sell_tax 0.18% (매도 only) / slippage 0.05%. 기존 backtest CostModel constant-v1 변경 0건
- **Paper Trading API 6 라우터 (v0.14)** — `GET /api/paper/account` / `/orders` / `/positions` / `/pnl` (read-only) + `POST /api/paper/orders` / `DELETE /api/paper/orders/{id}` (PAPER_TRADING_ENABLED + AUTH 필요, disabled → 503). 응답 forbidden 필드 12종 (api_key / token / secret / source_file_path / broker_order_id / kis_order_id / real_account / broker / account_number / raw_text / body / full_text) 0건
- **Paper Trading 스케줄러 잡 2건 (v0.14)** — `execute_paper_orders` (16:00 KST) + `create_paper_pnl_snapshot` (16:30 KST). PAPER_TRADING_ENABLED=false 기본 → SKIPPED, enabled 시 active VirtualAccount 전체 처리 (per-account isolation)
- **페이퍼 트레이딩 13번째 프런트 화면 (v0.14)** — `/paper` (`PaperTradingPage`: VirtualAccountCard + PaperOrderForm + VirtualPositionsTable + PnLTable + PaperOrdersTable + 정책 배너 + 503 disabled 안내). `LineChart` sidebar 아이콘 "페이퍼 트레이딩 (β)". `usePaperTrading` TanStack Query hooks 6종. 버튼 라벨 "페이퍼 주문 만들기" — "주문 실행" / "place order" CTA 0건
- **SafetySettings + KillSwitch (v0.15)** — `app/config/settings.py` 7 신규 필드 (`trading_safety_enabled` / `kill_switch_enabled` / `approval_required` / `max_order_amount` / `max_daily_order_amount` / `max_position_ratio` / `max_daily_loss_amount`). paranoid default — `trading_safety_enabled=false` / **`kill_switch_enabled=true`** (master block ON 기본) / `approval_required=true` / `max_order_amount=100,000` / `max_daily_order_amount=1,000,000` / `max_position_ratio=0.20` / `max_daily_loss_amount=500,000`. `_as_strict_bool` helper (typo 시 default 유지). `__post_init__` 경계 검증 (위반 시 ValueError)
- **OrderCandidate 8-state 머신 (v0.15)** — `OrderCandidate` (38번째 ORM) + Alembic 0007. 상태: `DRAFT → RISK_CHECKING → (RISK_REJECTED | PENDING_APPROVAL) → (APPROVED → EXECUTED_PAPER | REJECTED | EXPIRED)`. forbidden 컬럼 0건 (broker_order_id / kis_order_id / real_account / api_key / token / secret)
- **PreTradeRiskEngine 7 HARD 룰 (v0.15)** — `app/risk/pre_trade_risk_engine.py`. `account_paper_enabled` / `kill_switch_off` / `per_symbol_limit` / `daily_total_limit` / `position_ratio_limit` / `daily_loss_limit` / `duplicate_recent` (5분 윈도). `RiskCheckResult` (`policy_version` / `passed` / `violations[]`) 구조화 결과. KIS / DART / RSS / requests / httpx import 0건 (AST 회귀 단언)
- **Approval Workflow API 7종 + ApprovalAuditLog (v0.15)** — `GET /api/approvals/candidates` / `/candidates/{id}` / `/audit` (read-only) + `POST /api/approvals/candidates` / `/{id}/approve` / `/{id}/reject` / `/{id}/expire` (TRADING_SAFETY_ENABLED + KILL_SWITCH_ENABLED=false + AUTH 3중 게이트, disabled → 503). `ApprovalAuditLog` (39번째 ORM) + Alembic 0008 — append-only, 수정/삭제 API 0건. `ApprovalService.approve` 는 `SimulationBroker.submit_order` 만 호출 (KIS API 호출 0건 AST 단언). `expire_pending_approvals` IntervalTrigger 5분 잡
- **승인 대기 14번째 프런트 화면 (v0.15)** — `/approvals` (`ApprovalsPage`: PolicyBanner + PendingCandidatesTable + CandidateDetailDrawer (CandidateSummary + RiskCheckPanel + AuditTimeline) + NewCandidateForm + HistoryTable). `ShieldCheck` sidebar 아이콘 "승인 대기 (β)". `useApprovals` TanStack Query hooks 7종 (read 3 + mutation 4, mutation 후 approval/paper 두 namespace invalidate). 버튼 라벨 "승인 (paper 실행)" / "거절" / "만료" / "후보 만들기 (Risk Check)" — "주문 실행" / "place real order" / "FULL_AUTO" / "SMALL_AUTO" / "자동매매" CTA 0건. 503 응답은 `approvals-disabled-banner` / `approvals-kill-switch-banner` 친절 안내
- **RealTradingSettings (v0.16 Phase A)** — `app/config/settings.py` 5 신규 필드 (`real_trading_enabled=False` / `kis_order_enabled=False` / `real_order_dry_run=True` / `max_real_order_amount=5_000_000` / `max_real_daily_order_amount=50_000_000`). paranoid 기본 — 운영자가 명시하지 않으면 모든 실거래 경로 비활성. `can_attempt_real_order_settings()` 6-gate AND 판단 함수. `__post_init__` 검증 (max_real_order_amount ≤ max_real_daily_order_amount)
- **KIS Order Wrapper Skeleton (v0.16 Phase B)** — `app/broker/kis_order_client.py`. `KisOrderClientInterface` ABC (`place_order` / `query_fill_status` / `cancel_order`) + `KisOrderRequest` (account_no 마스킹 불변 객체) + `KisOrderResult` / `KisFillStatusResult` / `KisCancelResult` 불변 dataclass + `FakeKisOrderTransport` (FAKE-xxxx 가짜 주문번호, 항상 FILLED) + `mask_sensitive_order_payload()` (api_key / secret / account_no 마스킹). httpx / requests / urllib import 0건 (AST 가드). `KisHttpOrderTransport` 미구현 (v0.17+ scope)
- **RealOrder / RealFill ORM (v0.16 Phase C)** — `RealOrder` (40번째, `real_orders` 테이블, status 8종, `broker_order_no_hash` SHA-256 해시만) + `RealFill` (41번째, `real_fills` 테이블) + Alembic `0009_real_orders` + `0010_real_fills` + `RealOrderRepository` / `RealFillRepository`. 브로커 주문번호 평문 저장 0건
- **RealOrderExecutor 8-gate (v0.16 Phase D)** — `app/broker/real_order_executor.py`. 8 안전 게이트 (candidate APPROVED / 중복 가드 / kill_switch=False / real_trading_enabled / kis_order_enabled / 단건 한도 / 일일 누적 KST / PreTradeRiskEngine 재검사). dry_run=True → `FakeKisOrderTransport` → DRY_RUN RealOrder 저장. dry_run=False → `REAL_ORDER_NOT_IMPLEMENTED` (v0.17 scope). httpx / requests / urllib import 0건 (AST 가드)
- **FillSyncService mock (v0.16 Phase D)** — `app/broker/fill_sync_service.py`. `FILLED` → `RealFill(FULL)` + 주문 상태 갱신 / `PARTIALLY_FILLED` → `RealFill(PARTIAL)` / `DRY_RUN` 주문 상태 갱신 불가 (terminal). transport 주입 가능 (테스트용 stub)
- **실주문 준비 15번째 프런트 화면 (v0.16 Phase E)** — `/real-orders` (`RealOrdersPage`: `RealTradingSafetyBanner` 항상 표시 ("현재 화면은 dry-run / 기록 조회 전용" + "실제 KIS 주문은 실행되지 않습니다") + `RealOrderSummaryCards` + `RealOrdersTable` + `RealOrderDetailPanel` + `RealFillsTable`). `TrendingUp` sidebar 아이콘 "실주문 준비 (β)". `useRealOrders` / `useRealOrderDetail` TanStack Query hooks (read-only, mutation hook 0건). 금지 필드 미렌더링 (broker_order_no_hash / api_key / raw_response / account_number / real_account). 실주문 실행 / 자동매매 / FULL_AUTO / SMALL_AUTO actionable CTA 0건
- **Real Orders read-only API (v0.16 Phase E)** — `GET /api/real-orders` (status / candidate_id / limit / offset 필터) + `GET /api/real-orders/{id}` (주문 상세 + fills). POST / PUT / DELETE 0건. 금지 응답 필드 0건 (broker_order_no_hash / api_key / app_secret / access_token / raw_response / account_number / real_account)
- 테스트 가능한 구조 (backend pytest **1905**, vitest **214**, e2e **24**, build)

## 2. 전체 사이클 제외 범위 (v0.1 ~ v0.16 일관 정책)

다음 기능은 **모든 사이클에서 코드 일체 포함하지 않습니다.** 자동매매 진입은
별도 보안 / 컴플라이언스 사이클이 선행되어야 가능합니다.

- 실거래 자동매매 (FULL_AUTO / APPROVAL / SMALL_AUTO 모드)
- 실제 주문 API 실행 (`BrokerInterface` 는 ABC placeholder 만 유지)
- POST / PUT / DELETE 라우터 — **v0.8 에서 인증·Watchlist 에 한해 5건 첫 도입** (`POST /api/auth/login` + `POST /api/auth/logout` + `POST /api/watchlists` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`). 그 외 도메인 0건
- 가상 증권사 서버 / MockBroker / ReplayBroker / SimulationBroker
- 전략 자동 튜닝 / Strategy 모듈
- 전용 AI 모델 학습 / Custom AI training
- 대량 가상 데이터 생성
- 완전한 백테스트 시스템
- **(v0.4)** 증권사 리포트 자동 크롤링 / 스크레이핑 (수동 CSV 만)
- **(v0.4)** 리포트 원문 본문 / PDF BLOB 저장
- **(v0.4)** `source_file_path` API / 프런트 / e2e 노출
- **(v0.5)** News / 공시 자동 크롤링 / 스크레이핑 (FakeProvider 만, 실 RSS / DART API 호출 0건)
- **(v0.5)** News / 공시 본문 paragraph 저장 — 메타데이터 (title / url / provider / category / sentiment / 짧은 summary) 만
- **(v0.5)** 자동 fetch default ON — `news_collection_enabled` / `disclosure_collection_enabled` 기본 false
- **(v0.5)** 추천 산식 본 weight 변경 — `news_score` 만 50 → real, 가중치 25% 그대로
- **(v0.6)** DART API 자동 호출 / 자동 크롤링 (1단계는 운영자 수동 CSV 만, 실 provider 는 v0.7+ 후보)
- **(v0.6)** 재무 / 실적 본문 paragraph 저장 — 정량 지표 + 짧은 메모 (≤500자) + URL / source 메타데이터만
- **(v0.6)** 재무제표 PDF / Excel BLOB DB 저장
- **(v0.6)** 재무 / 실적 자동 fetch default ON — `fundamental_collection_enabled` / `earnings_collection_enabled` 기본 false (v0.6 시점에서는 scheduler job 자체 미추가)
- **(v0.6)** 추천 / 보유 산식 본 weight 변경 — `fundamental_score` 만 50 → real (가중치 15%), `earnings_score` 만 50 → real (가중치 그대로)
- **(v0.7)** `StrategySignal` 을 매매 주문으로 사용 — 분석 신호 전용. `ScoreSnapshot` / `BacktestResult` 에 broker / account / quantity / order_price / order_type / side 필드 0건
- **(v0.7)** Strategy / Backtest 결과 자동 텔레그램 발송 — read-only 화면만, 자동 발송 0건
- **(v0.7)** 백테스트 run 트리거 UI — `/backtest` 화면에 "Run backtest" 버튼 없음. 운영자가 `scripts/run_backtest.py --commit` 으로 적재한 결과만 read-only 노출 (POST 도입은 v0.8 의 인증과 묶음)
- **(v0.7)** 실 broker fee schedule / 종목별 stamp duty / tick-size 슬리피지 fetch — `CostModel` 은 `constant-v1` placeholder 만, 실 적용은 v0.8+ 후보
- **(v0.7)** LLM 기반 자동 전략 생성 — 룰 기반만, LLM 보강은 v0.8+ 후보
- **(v0.8)** 다중 사용자 / OAuth / SSO / RBAC — 단일 admin user 만 (`AUTH_ENABLED` 토글)
- **(v0.8)** Refresh token / token revocation list — 24h JWT TTL + 재로그인만
- **(v0.8)** Watchlist 가격 알림 / target return alert — 표시·필터만, 알림 시스템 변경 0건
- **(v0.8)** 평문 IP / 평문 password 저장 — `source_ip_hash` SHA256 만 / scrypt hash 만
- **(v0.9)** Provider resilience 실 provider 강제 적용 — skeleton 완성, KIS/DART 래핑은 v0.10 후보
- **(v0.9)** CSP (Content-Security-Policy) 헤더 — Vite devserver / nginx 충돌 우려, v0.10 후보
- **(v0.9)** notification_preferences_json 실 발송 연결 — UI 저장만, Telegram / 푸시 연결 0건
- **(v0.9)** Prometheus exporter / Grafana 대시보드 — 외부 노출 규모 확인 후 v0.10 후보
- **(v0.10)** DART / RSS 실 httpx transport 도입 — provider skeleton + parser 만, 실 HTTP 전송은 v0.11+ 라이선스 검토(사람) 선행 후 → **v0.11 Phase A/B 에서 도입 완료** (default OFF 유지)
- **(v0.10)** DART / RSS 데이터의 ScoringEngine weight 반영 — provider skeleton 만, 추천·보유 산식 본 weight 변경 0건 (v0.11+ 후보)
- **(v0.10)** Provider enable/disable toggle UI / mutation API — `.env` + 백엔드 재시작만, GUI toggle 0건 (v0.11+ 인증·보안 검토 후)
- **(v0.10)** Prometheus exporter / Grafana / 외부 시계열 DB — `ProviderHealthMonitor` 는 in-memory only (서버 재시작 시 초기화), 외부 노출은 v0.11+ → **v0.11 Phase C 에서 Prometheus exporter 도입** (default OFF, Grafana dashboard 동봉은 v0.12+)
- **(v0.10)** `GET /api/health/jobs` 별도 엔드포인트 — 기존 `/api/jobs` 동일 정보 제공으로 보류 (v0.11+ 분리 검토)
- **(v0.11)** DART / RSS 실 transport 가 도입됐지만 ScoringEngine weight 반영은 여전히 0건 — v0.12+ (누적 데이터 검증 후)
- **(v0.11)** Grafana dashboard JSON 동봉 — Prometheus exporter 까지만, 시각화 layer 는 외부 인프라 (v0.12+)
- **(v0.11)** ProviderHealthMonitor 영속화 — bounded ring buffer (200 calls / 50 failures) only, 서버 재시작 시 초기화. DB / Redis 백업은 v0.12+
- **(v0.11)** Provider toggle GUI / mutation API — `.env` + 재시작만 그대로, GUI 토글 0건 (v0.12+ 인증·보안 검토 후)
- **(v0.11)** WebSocket / SSE 실시간 갱신 — Provider Health 패널은 30s staleTime + 60s refetchInterval polling, 실시간 push 는 v0.12+
- **(v0.11)** `GET /api/health/jobs` 분리 — 여전히 보류, 기존 `/api/jobs` 가 동일 정보 제공 (v0.12+)
- **(v0.13)** Backtest Export CLI (`scripts/export_backtest.py`) — v0.14+ 이연 (기능 코드 수정 없이 문서 마감 우선)
- **(v0.13)** ProviderScorePolicy → producer 자동 통합 — `ProviderScorePolicy` 는 독립 유틸로 존재하지만 실 producer 에 자동 연결 미완성. v0.14+ (누적 backtest 검증 기반)

위 항목은 모두 [`ROADMAP.md`](./ROADMAP.md) 의 Future Backlog 로 분류되어 있고,
각 항목은 진입 전제 조건 (예: 인증 / 컴플라이언스 / 자본 한도) 이 명시되어
있습니다.

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
| [`AGENTS.md`](./AGENTS.md) | Codex 가 매번 따라야 하는 핵심 지침 — 프로젝트 전체 (v0.1~v0.7) 규칙, 13 코딩 에이전트 역할 |
| [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) | 현재 사이클 상태 / 시작·마감 선언 / Phase 결과 요약. 새 세션이 가장 먼저 읽어야 할 파일 |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 시스템 구조 — 10 layer (Data / Repository / Analysis / Report Intelligence / Scoring / Notification / API / Frontend / Scheduler / Ops·CI) + Strategy / Backtest layer (v0.7) |
| [`ROADMAP.md`](./ROADMAP.md) | v0.1 ~ v0.7 진행 이력 + v0.8 후보 + Future Backlog (자동매매) |
| [`TASKS.md`](./TASKS.md) | 사이클별 phase 체크리스트 |
| [`PLANS.md`](./PLANS.md) | Codex 실행 계획 (PLAN-0001 ~ PLAN-0007) |
| [`API_SPEC.md`](./API_SPEC.md) | FastAPI read-only GET API 명세 (23+ GET, POST 0건, v0.5 §14 테마 + v0.6 §15 재무·실적 + v0.7 §16 백테스트 포함) |
| [`DB_SCHEMA.md`](./DB_SCHEMA.md) | 27 테이블 (v0.1 17 + v0.4 6 + v0.6 2 + v0.7 2) 명세 + 저작권 정책 + v0.5 `news_items.category` |
| [`TESTING.md`](./TESTING.md) | 테스트 전략 + 게이트 baseline (682 / 84 / 14 / build) |
| [`SECURITY.md`](./SECURITY.md) | 보안 원칙 (KIS / Telegram / source_file_path 마스킹 + News·공시·재무·실적 본문 미저장 + Strategy/Backtest 주문 필드 미노출) |
| [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) | mock seed 통합 시나리오 + KIS 모의투자 검증 + News·공시·테마·재무·실적·백테스트 운영 절차 (v0.5 §10~§12 + v0.6 §13~§15 + v0.7 §16) |
| [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) | 운영 KIS 키 사전 검증 체크리스트 |
| [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) | v0.1 백엔드 마감 선언 |
| [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) | v0.2 프런트 MVP 마감 선언 |
| [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) | v0.3 분석·운영 마감 선언 |
| [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md) | v0.4 Analyst & Theme Intelligence 마감 선언 |
| [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md) | v0.5 News·공시·테마 랭킹 마감 선언 |
| [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md) | v0.6 Fundamental & Earnings Intelligence 마감 선언 |
| [`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md) | v0.7 Strategy & Backtest Foundation 마감 선언 |
| [`RELEASE_NOTES_v0.8.md`](./RELEASE_NOTES_v0.8.md) | v0.8 User & Migration Foundation 마감 선언 |
| [`RELEASE_NOTES_v0.9.md`](./RELEASE_NOTES_v0.9.md) | v0.9 Operational Security & Watchlist Polish 마감 선언 |
| [`RELEASE_NOTES_v0.10.md`](./RELEASE_NOTES_v0.10.md) | v0.10 Real Provider Readiness & Resilience 마감 선언 |
| [`RELEASE_NOTES_v0.11.md`](./RELEASE_NOTES_v0.11.md) | v0.11 Real Provider Transport & Observability 마감 선언 |
| `stock_ai_project_codex_brief.md` | 초기 프로젝트 브리프 (역사적 — 실제 진행은 ROADMAP 참조) |
| `stock_ai_detailed_spec.md` | 초기 상세 기능 명세 (역사적) |
| `codex_agent_creation_spec.md` | 초기 코딩 에이전트 생성 명세 (역사적) |
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

## 6. 누적 사이클 상태 (v0.1 ~ v0.15)

| 사이클 | 상태 | 회귀 게이트 | 최종 태그 |
|---|---|---|---|
| v0.1 Backend | ✅ 마감 | pytest 296 | `v0.1-backend-kis-paper-verified` |
| v0.2 Frontend MVP | ✅ 마감 | pytest 296 / vitest 36 / e2e 6 | `v0.2-frontend-final` |
| v0.3 Analysis & Ops | ✅ 마감 | pytest 319 / vitest 59 / e2e 8 | `v0.3-final` |
| v0.4 Analyst & Theme Intelligence | ✅ 마감 | pytest 382 / vitest 60 / e2e 9 / build | `v0.4-final` |
| v0.5 News, Disclosure & Theme Ranking | ✅ 마감 | pytest 481 / vitest 68 / e2e 11 / build | `v0.5-final` |
| v0.6 Fundamental & Earnings Intelligence | ✅ 마감 | pytest 558 / vitest 77 / e2e 13 / build | `v0.6-final` |
| v0.7 Phase A — StrategyInterface + 룰 기반 전략 3종 | ✅ 인수 | pytest 614 | `v0.7-strategy-interface` |
| v0.7 Phase B — BacktestEngine + 신규 테이블 2개 + CLI | ✅ 인수 | pytest 652 | `v0.7-backtest-engine` |
| v0.7 Phase C — CostModel + 시장 국면별 분리 | ✅ 인수 | pytest 673 | `v0.7-backtest-cost-regime` |
| v0.7 Phase D — read-only API 3종 + 10번째 화면 `/backtest` | ✅ 인수 | pytest 682 / vitest 84 / e2e 14 | `v0.7-frontend-backtest` |
| v0.7 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 682 / vitest 84 / e2e 14 / build | `v0.7-final` |
| v0.8 Phase A — Alembic baseline (27 테이블) | ✅ 인수 | pytest 698 | `v0.8-alembic-baseline` |
| v0.8 Phase B — 단일 사용자 인증 (JWT + scrypt) | ✅ 인수 | pytest 760 | `v0.8-auth-foundation` |
| v0.8 Phase C — Watchlist DB / API (5 라우터) | ✅ 인수 | pytest 808 | `v0.8-watchlist-api` |
| v0.8 Phase D — Watchlist 프런트 11번째 화면 + Login | ✅ 인수 | pytest 808 / vitest 113 / e2e 19 | `v0.8-frontend-watchlist` |
| v0.8 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 808 / vitest 113 / e2e 19 / build | `v0.8-final` |
| v0.9 Phase A — Security Hardening | ✅ 인수 | pytest 845 | `v0.9-security-hardening` |
| v0.9 Phase B — RequestID + 구조화 로깅 + Sentry optional | ✅ 인수 | pytest 869 | `v0.9-monitoring` |
| v0.9 Phase C — Watchlist PATCH/DELETE 4건 + UserPreference + Provider resilience skeleton | ✅ 인수 | pytest 916 | `v0.9-watchlist-api` |
| v0.9 Phase D — Watchlist 관리 UI + UserPreference Settings | ✅ 인수 | pytest 916 / vitest 146 / e2e 19 | `v0.9-frontend` |
| v0.9 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 916 / vitest 146 / e2e 19 / build | `v0.9-final` |
| v0.10 Phase A — Provider Resilience Runtime (`ProviderHealthMonitor` + `call_with_resilience()` + 6 settings) | ✅ 인수 | pytest 947 (+31) | `v0.10-provider-resilience` |
| v0.10 Phase B — DART Provider Skeleton (DartFundamental/Earnings/Disclosure, parser + body strip + crtfc_key 마스킹) | ✅ 인수 | pytest 995 (+48) | `v0.10-dart-provider` |
| v0.10 Phase C — RSS/News Provider Skeleton (RSS 2.0 + Atom, dedup + URL secret 마스킹, stdlib only) | ✅ 인수 | pytest 1028 (+33) | `v0.10-rss-provider` |
| v0.10 Phase D — Provider Health API + UI (`GET /api/health/providers` + Settings 패널, POST/PUT/DELETE 405) | ✅ 인수 | pytest 1045 (+17) / vitest 153 (+7) / e2e 20 (+1) | `v0.10-health-api` |
| v0.10 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 1045 / vitest 153 / e2e 20 / build | `v0.10-final` |
| v0.11 Phase A — DART HTTP Transport (`HttpxDartTransport` + factory 자동 주입 + `_SensitiveQueryStringFilter`) | ✅ 인수 | pytest 1072 (+27) | `v0.11-dart-transport` |
| v0.11 Phase B — RSS HTTP Transport (`HttpxRssTransport` + 공유 `SensitiveQueryStringFilter` 추출) | ✅ 인수 | pytest 1091 (+19) | `v0.11-rss-transport` |
| v0.11 Phase C — Provider Observability + Prometheus exporter (`ProviderHealthMonitor` ring buffer + `Summary24h` + `prometheus-client` `/metrics` default 404) | ✅ 인수 | pytest 1112 (+21) | `v0.11-observability` |
| v0.11 Phase D — Provider Health API/UI 24h aggregates (`success_rate_24h` / `recent_failures[5]` + `SuccessRateBar` + `RecentFailuresList`) | ✅ 인수 | pytest 1119 (+7) / vitest 158 (+5) / e2e 21 (+1) | `v0.11-health-extended` |
| v0.11 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 1119 / vitest 158 / e2e 21 / build | `v0.11-final` |
| v0.12 Phase A — Provider Data Ingestion (4 어댑터, `data_source` provenance, `PROVIDER_DATA_INGESTION_ENABLED=false`) | ✅ 인수 | pytest 1149 (+30) | `v0.12-provider-ingestion` |
| v0.12 Phase B — Walk-forward Backtest Engine (`WalkForwardBacktestEngine` + `generate_folds()`, IS/OOS sliding) | ✅ 인수 | pytest 1166 (+17) | `v0.12-walk-forward` |
| v0.12 Phase C — Multi-strategy Comparison + Sector Breakdown (`MultiStrategyRunner`, `aggregate_sector_breakdown()`) | ✅ 인수 | pytest 1182 (+16) | `v0.12-multi-strategy` |
| v0.12 Phase D — Backtest read-only API 확장 + fold/comparison UI + `data_source` chip | ✅ 인수 | pytest 1194 (+12) / vitest 165 (+7) / e2e 21 | `v0.12-scoring-readonly` |
| v0.12 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 1194 / vitest 165 / e2e 21 / build | `v0.12-final` |
| v0.13 Phase A — ProviderScorePolicy 승수 엔진 + ScoringEngine weight 회귀 단언 | ✅ 인수 | pytest 1223 (+29) | `v0.13-provider-policy` |
| v0.13 Phase B — Score Delta in evidence_json (`ScoreDeltaResult`, Alembic 0건) | ✅ 인수 | pytest 1241 (+18) | `v0.13-score-delta` |
| v0.13 Phase C — Validation Report read-only API 4종 (POST→405, forbidden field guard) | ✅ 인수 | pytest 1277 (+36) | `v0.13-validation-api` |
| v0.13 Phase D — Validation Report 12번째 화면 `/validation` + vitest 10건 | ✅ 인수 | vitest 175 (+10) / e2e 21 | `v0.13-validation-ui` |
| v0.13 Phase E — 마감 선언 | ✅ 문서 마감 | pytest 1277 / vitest 175 / e2e 21 / build | `v0.13-final` |
| v0.14 Phase A — Backtest Export CLI + ProviderScorePolicy → producer 통합 | ✅ 인수 | pytest 1322 (+45) | `v0.14-export-policy` |
| v0.14 Phase B — SimulationBroker + VirtualAccount/VirtualOrder + Alembic 0005 | ✅ 인수 | pytest 1365 (+43) | `v0.14-sim-broker` |
| v0.14 Phase C — VirtualPosition/VirtualFill/VirtualPnLSnapshot + PnLTracker + execute_pending_orders + Alembic 0006 | ✅ 인수 | pytest 1405 (+40) | `v0.14-pnl-tracker` |
| v0.14 Phase D — Paper Trading API 6 라우터 + 스케줄러 잡 2건 | ✅ 인수 | pytest 1438 (+33) | `v0.14-paper-api` |
| v0.14 Phase E — 페이퍼 트레이딩 13번째 화면 `/paper` + 마감 문서 | ✅ 문서 마감 | pytest 1438 / vitest 186 / e2e 22 / build | `v0.14-final` |
| v0.15 Phase A — SafetySettings + KillSwitch + 안전 default 7건 | ✅ 인수 | pytest ~1465 | `v0.15-safety-settings` |
| v0.15 Phase B — OrderCandidate ORM (38) + Repository + Alembic 0007 + 8-state 머신 | ✅ 인수 | pytest ~1505 | `v0.15-order-candidate` |
| v0.15 Phase C — PreTradeRiskEngine 7 hard 룰 + RiskCheckResult | ✅ 인수 | pytest ~1545 | `v0.15-pre-trade-risk` |
| v0.15 Phase D — Approval Workflow API 7종 + ApprovalAuditLog (39) + Alembic 0008 + ApprovalService + expire 잡 | ✅ 인수 | pytest 1693 | `v0.15-approval-api` |
| v0.15 Phase E — 승인 대기 14번째 화면 `/approvals` + 마감 문서 | ✅ 문서 마감 | pytest 1693 / vitest 201 / e2e 23 / build | `v0.15-final` |

### 영역별 상태

| 영역 | 상태 |
|---|---|
| DB 모델 / Repository | 17 + 6 + 2 + 2 = **27 테이블 ORM**, 16 + 6 + 2 + 2 = **26 Repository**. v0.5 는 `news_items.category` ALTER ADD COLUMN, v0.6 은 `fundamental_snapshots` + `earnings_events` 신규, v0.7 은 `backtest_runs` + `backtest_results` 신규 |
| KIS 데이터 수집 | `KisClient` + 정규화 / 품질 검사 / `DailyPriceCollector` / `MarketCapRankingCollector` (mock-injectable) |
| **News / 공시 데이터 라인 (v0.5)** | `NewsProviderInterface` / `DisclosureProviderInterface` ABC + `NewsCollector` / `DisclosureCollector` + 9 필드 DTO (본문 0건) + `news_items.category` 6 enum + 공시 5 카테고리 keyword 분류 + `collect_news` (19:00) / `collect_disclosures` (20:00) 잡 (모두 default OFF) |
| **재무 / 실적 데이터 라인 (v0.6)** | `FundamentalProviderInterface` / `EarningsProviderInterface` ABC + `FundamentalSnapshot` (24번째, 8 정량 지표) + `EarningsEvent` (25번째, BEAT/MEET/MISS) + `scripts/import_fundamentals.py` / `scripts/import_earnings.py` argparse CLI (default dry-run) + `FakeFundamentalProvider` / `FakeEarningsProvider` (실 DART 호출 0건) |
| 분석 / 점수 | `TechnicalAnalyzer` (MA/RSI/MACD/breakout/ma_alignment + 캔들 5종 / ATR / 변동성), `ScoringEngine`, `RiskEngine`, `ScoreProducerInterface` ABC + `DummyScoreProducer` + `RealNewsScoreProducer` + `DisclosureRiskProducer` (v0.5) + `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` (v0.6) |
| **Strategy / Backtest (v0.7)** | `StrategyInterface` ABC + `StrategySignal` (BUY/PASS/AVOID, `[0,1]` confidence) + `ScoreSnapshot` (broker/주문 필드 0건) + `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` 3종 (룰 기반) + `BacktestEngine` (recommendation_results replay → win_rate / avg_return / max_drawdown, BUY-only 산식) + `CostModel` `constant-v1` (총 0.33% 차감) + `assign_regime` (MarketRegime at-or-before 매칭) + `scripts/run_backtest.py` argparse CLI (default dry-run) |
| 추천 / 보유 점검 | `RecommendationEngine`, `HoldingCheckEngine` (PRE/POST), `RecommendationResultService` (1/3/5/20일 성과). v0.5 의 evidence 4종 + **v0.6 의 `fundamental_evidence` (recommendation) + `earnings_evidence` (holding)** 모두 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 에 기록 |
| 알림 / 리포트 | `ReportGenerator` + `TelegramNotifier` (DRY_RUN 기본) + `NotificationService` + 3 dispatcher |
| Backend API | read-only GET API **23+ 라우터**. v0.5 `/api/themes/ranking` + `/api/themes/{theme_id}` + v0.6 `/api/stocks/{symbol}/fundamentals` + `/api/stocks/{symbol}/earnings` + `/api/calendar/earnings` + **v0.7 `/api/strategies` + `/api/backtest/runs` + `/api/backtest/runs/{run_id}`**. POST 0건. RecommendationItemSchema / HoldingCheckSchema 에 evidence 4종 nullable 필드 (라우터 단계 화이트리스트) |
| Scheduler | APScheduler + `run_job` 래퍼 + **9개 잡** (v0.4 Phase B `update_report_consensus_snapshots` 06:30 + v0.5 `collect_news` 19:00 + `collect_disclosures` 20:00, 두 v0.5 잡은 default OFF). v0.6 에서는 scheduler job 추가 0건 (수동 CSV import 만) |
| Import Pipeline | v0.4 `scripts/import_analyst_reports.py` + **v0.6 `scripts/import_fundamentals.py` + `scripts/import_earnings.py`** (모두 argparse CLI, default dry-run, `--commit` 시 DB 적재). Forbidden body column 13종 거부, `summary` / `memo` 500자 truncate, `source_file_path` 마스킹. pandas / openpyxl 의존성 0건 |
| Frontend | Vite + React + TS, **10 화면** (v0.5 `테마 (β)` + v0.7 `백테스트 (β)` 추가), 코드 스플릿, KRX 휴장 배너, StockDetail 일봉 차트 + 리포트 카드 + 테마 링크 + impact_path badge + Fundamentals + Earnings 카드 (v0.6) + Today UpcomingEarnings 카드 (v0.6) + Recommendations evidence 4종 cell + Holdings/HoldingChecks earnings evidence cell + **Backtest 화면 (전략 카드 grid + run 표 + detail 패널 + regime breakdown + cost_model badge + BUY-only note)** (v0.7), msw + Playwright |
| **Report Intelligence (v0.4)** | 6 ORM + 6 Repository + CSV import + consensus snapshot job + report/theme score + dashboard 표시 |
| **News·Disclosure Intelligence (v0.5)** | `news_items` 통합 저장 (뉴스 + 공시) + `RealNewsScoreProducer` 가 `news_score` 25% 첫 real 화 + `DisclosureRiskProducer` 가 `RISK_DISCLOSURE` flag + cap +10 penalty + 추천·보유 evidence 노출 |
| **Fundamental·Earnings Intelligence (v0.6)** | 2 ORM + 2 Repository + 2 CSV import + RealFundamentalScoreProducer 가 `fundamental_score` 15% 첫 real 화 + RealEarningsScoreProducer 가 holding `earnings_score` 첫 real 화 + 3 read-only API + StockDetail 2 카드 + Today 1 카드 + Recommendations / Holdings evidence cell |
| **Strategy & Backtest Foundation (v0.7)** | `StrategyInterface` ABC + 룰 기반 전략 3종 (TopGrade / HighScore / MultiSignal) + `BacktestEngine` (BUY-only metrics) + 신규 테이블 2개 (`backtest_runs` 26 / `backtest_results` 27) + `CostModel` `constant-v1` (총 0.33% 차감) + `assign_regime` (MarketRegime at-or-before) + 3 read-only API (`/api/strategies` + `/api/backtest/runs` + `/api/backtest/runs/{run_id}`) + 10번째 화면 `/backtest` (Sidebar `백테스트 (β)`) + `scripts/run_backtest.py` argparse CLI (default dry-run) |
| **User & Migration Foundation (v0.8)** | Alembic baseline (`0001`/`0002`/`0003`) + `User` (28번째) + `LoginAuditLog` (29번째, source_ip_hash SHA256) + `Watchlist` (30번째) + `WatchlistItem` (31번째, broker/account/quantity/order_* 0건) + JWT HS256 + scrypt + `AUTH_ENABLED` 토글 + 5 write 라우터 (auth 3 + watchlist 2) + cross-user 404 격리 + 11번째 화면 `/watchlist` + `/login` + StockDetail `FavoriteButton` + Today `WatchlistCard` |
| Ops / CI | GitHub Actions 3 잡 (backend pytest / vitest+build / Playwright e2e), main + PR 자동 검증, mock 환경 변수 |
| 통합 검증 | `scripts/seed_mock_data.py` (멱등) + `INTEGRATION_RUNBOOK.md` (§10 News / §11 Disclosure / §12 테마 / §13 Fundamental CSV / §14 Earnings CSV / §15 read-only API + **§16 백테스트 CLI + read-only API + 화면**) |

세부 산출물 / 테스트 카운트 / 변경 이력은 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md)
와 [`TASKS.md`](./TASKS.md) 참고. v0.8 후보는 [`ROADMAP.md`](./ROADMAP.md) 참조.

## 7. 실행 순서 (권장)

새 세션 / 인수자 / QA 가 한 번에 따라가야 할 표준 순서. 각 단계는 모두 dry-run
/ mock-only — 실 KIS 호출, 실 텔레그램 발송, 자동매매 코드는 이 순서 안에서
절대 동작하지 않는다.

| 단계 | 명령 | 출력 / 검증 |
|---|---|---|
| 7.1 의존성 | `.\.venv\bin\python.exe -m pip install -e ".[dev]"` | 정상 설치 |
| 7.2 Docker (권장) 또는 로컬 uvicorn | §8 또는 §9 | `/health` 200 |
| 7.3 Mock seed | `.\.venv\bin\python.exe -m scripts.seed_mock_data --reset` | stocks 5 / daily_prices 150 등 (§10) |
| 7.4 통합 시나리오 (9잡 + 23+ API) | [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §3 ~ §5 / §10 ~ §16 따라감 | 모든 잡 SUCCESS (collect_news / collect_disclosures 는 default SKIPPED), API 200, notification_logs DRY_RUN |
| 7.5 회귀 게이트 | `.\.venv\bin\python.exe -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults` | 1119 passed, 1 deselected (v0.11 마감 시점) — 로컬 `.env` dev override 가 있으면 `test_settings_defaults` 1건은 deselect, CI clean env 에서는 자동 통과 |
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

실 KIS 키 / 실 텔레그램 없이 백엔드 전체 흐름 (v0.1 베이스 + v0.3 분석 보강)
을 로컬에서 검증하려면 `scripts/seed_mock_data.py` 로 결정론적 mock 데이터를
적재한 뒤, [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) 에 정리된 6개 잡
+ 14+ GET API 시나리오를 따라간다.

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

외부 API, 텔레그램, 주문 기능은 테스트에서 실제로 호출하지 않습니다 (mock /
`httpx.MockTransport` / `FakeKisDataProvider`).

현재 회귀 기준선 (v0.8 마감 시점):

- backend pytest **808 passed** (v0.1 296 → v0.3 319 → v0.4 382 → v0.5 481 → v0.6 558 → v0.7 682 → v0.8 Phase A 698 → Phase B 760 → Phase C 808). 로컬 `.env` 의 dev override (`MARKET_CAP_LIMIT=5` 등) 가 있으면 `tests/unit/test_project_structure.py::test_settings_defaults` 1건은 환경 의존으로 실패하므로 `--deselect` 또는 명시 env override 필요. CI clean env 에서는 자동 통과
- frontend vitest **113 passed** (16 파일)
- Playwright e2e **19 passed** (chromium + page.route mock)
- frontend build (`tsc --noEmit && vite build`) 그린

자세한 테스트 정책 / 카테고리는 [`TESTING.md`](./TESTING.md) 참조.

## 12. CI (GitHub Actions)

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) 이 push / pull_request 이벤트 (대상: `main`) 마다 다음 3 잡을 자동 실행합니다.

| 잡 | 단계 |
|---|---|
| `backend / pytest` | Python 3.12 + pip cache → `pip install -e ".[dev]"` → `pytest -q` |
| `frontend / vitest + build` | Node 20 + npm cache → `npm ci` → `npm run test` → `npm run build` |
| `frontend / playwright e2e` | Node 20 + npm cache + Playwright 브라우저 캐시 → `npm ci` → `npx playwright install --with-deps chromium` → `npm run build` → `npm run e2e` (`vite preview` + `page.route` mock — 실 백엔드 / KIS / Telegram 호출 0건). 실패 시 `playwright-report/` artifact 업로드 |

CI 환경 변수는 모두 mock / dry-run 값으로 강제됩니다 (`KIS_USE_PAPER=true`, `TELEGRAM_ENABLED=false`, `FEATURE_REAL_ORDER_EXECUTION=false`, `FEATURE_FULL_AUTO=false`, fake KIS / Telegram 키). 실 자격증명 / 실 KIS API / 실 텔레그램 봇 사용 0건.

로컬에서 동일 게이트를 돌릴 때:

```powershell
# 백엔드
.\.venv\bin\python.exe -m pytest -q

# 프런트
cd frontend
npm run test
npm run build
npm run e2e
```

## 13. 운영 전 KIS 실 키 검증

운영 환경에서 실 KIS 키 + 실 텔레그램으로 한 번 검증하기 전에는
[`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 의 체크리스트를 항목 단위로
확인한다. 코드 변경 없이 `.env` / 운영 SOP 만으로 통과해야 한다.

## 14. Codex 첫 실행 프롬프트 예시

```text
AGENTS.md, PROJECT_STATUS.md (§0), ARCHITECTURE.md, TASKS.md, ROADMAP.md 를
먼저 읽고, 현재 사이클 (v0.8 마감 — v0.9 후보 검토 대기) 범위를 벗어나지
않는 개발 계획을 작성해줘.
아직 코드는 수정하지 말고 TASKS.md 업데이트 계획만 제안해줘.
```

## 15. 주의

이 프로젝트는 **투자 판단 보조 도구** 입니다. v0.1 ~ v0.8 어디에도 실제 주문 /
자동매매 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드를 구현하지 않습니다.
v0.7 의 `StrategySignal` (BUY/PASS/AVOID) 도 분석 신호이지 매매 주문이 아닙니다.
v0.8 의 `WatchlistItem` 도 즐겨찾기 저장 전용 — broker / 주문 / 계좌 / 수량 필드
0건, Watchlist `POST` 는 즐겨찾기 추가/삭제만입니다.

자동매매 진입은 별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실
제한 사이클이 선행되어야 검토할 수 있습니다 ([`ROADMAP.md`](./ROADMAP.md) 의
Future Backlog 참조).
