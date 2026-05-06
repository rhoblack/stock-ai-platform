# Roadmap

> 본 문서는 **v0.8 시작 선언 시점** 기준으로 갱신되었다 (직전 마감 태그
> `v0.7-final`). v0.8 은 **User & Migration Foundation** 사이클로, v0.1 부터
> 일관 유지된 read-only 정책의 첫 변경 — Alembic baseline 도입 + 단일 사용자
> 인증 기반 + Watchlist 도메인 POST/DELETE 첫 도입. 자동매매 / MockBroker /
> FULL_AUTO 는 여전히 **Future Backlog**. 실제로 진행된 사이클은 분석·UX·CI·운영
> 정착 + 증권사 리포트 인텔리전스 + 뉴스·공시 데이터 라인 + `news_score` 첫
> real 화 + 테마 랭킹 화면 + 재무·실적 데이터 라인 + `fundamental_score` /
> `earnings_score` 첫 real 화 + StockDetail Fundamental·Earnings 카드 +
> Strategy / Backtest 기초 (StrategyInterface + BacktestEngine + CostModel +
> 시장 국면별 분리 + 백테스트 화면) 중심이고, **v0.8 진입 시점부터 사용자
> 인증·Watchlist·Alembic** 으로 확장된다.

## 진행 이력 요약

| 사이클 | 핵심 목표 | 상태 | 최종 태그 |
|---|---|---|---|
| v0.1 Backend | KIS read-only 데이터 + 분석 + 추천 + 보유 점검 + 텔레그램 + Backend API + 6 잡 | ✅ 마감 | `v0.1-backend-kis-paper-verified` |
| v0.2 Frontend MVP | PC 대시보드 8 화면 (Vite + React + TS), 코드 스플릿, Docker | ✅ 마감 | `v0.2-frontend-final` |
| v0.3 Analysis & Ops | GitHub Actions CI / 캔들·ATR / KRX 휴장 캘린더 / StockDetail 일봉 차트 | ✅ 마감 | `v0.3-final` |
| v0.4 Analyst & Theme Intelligence | 증권사 리포트 + 테마 매핑 + 변화 시그널 + 리포트 점수 통합 + StockDetail 4 카드 | ✅ 마감 | `v0.4-final` |
| v0.5 News, Disclosure & Theme Ranking | News/공시 데이터 라인 + DummyScoreProducer.news_score 첫 real 화 + `/themes` 9번째 화면 | ✅ 마감 | `v0.5-final` |
| v0.6 Fundamental & Earnings Intelligence | 재무 / 실적 데이터 라인 (CSV import 1단계) + `fundamental_score` (15%) + `earnings_score` (HoldingCheck) 첫 real 화 + StockDetail Fundamental·Earnings 카드 + Today 다가오는 어닝 | ✅ 마감 | `v0.6-final` |
| v0.7 Strategy & Backtest Foundation | `StrategyInterface` + 룰 기반 전략 3종 + `BacktestEngine` (recommendation_results 1·3·5·20일 활용) + 비용 모델 (placeholder 0.33% 차감) + 시장 국면별 분리 + 백테스트 화면 (10번째) | ✅ 마감 | `v0.7-final` |
| v0.8 User & Migration Foundation | Alembic baseline (27 → 31 테이블) + 단일 사용자 인증 (`AUTH_ENABLED` 토글 + JWT) + Watchlist 도메인 GET/POST/DELETE (POST 라우터 첫 도입) + Watchlist 프런트 (11번째 화면) + StockDetail/Today 즐겨찾기 통합 | ✅ 마감 | `v0.8-final` |

---

## v0.1 — 분석 / 점검 / 리포트 기반 (✅ 마감)

기준선: KIS API 기반 read-only 시스템. 296 passed.

핵심 산출물:

- 17 ORM 모델 + 16 Repository
- KIS HTTP 클라이언트 + 정규화 + 품질 검사 + Fake provider
- 17 KRX 종목 + 시총 TOP 500 유니버스
- Technical 지표 (MA / RSI / MACD / breakout / ma_alignment)
- ScoringEngine + RecommendationEngine + HoldingCheckEngine + RiskEngine + DummyScoreProducer
- 보유 종목 장전 / 장후 점검
- 추천 TOP 5 + 1/3/5/20일 후 성과 검증
- TelegramNotifier (DRY_RUN 기본) + 3 dispatcher
- FastAPI 13 read-only GET 라우터
- APScheduler + 6 일별 잡
- mock seed (`scripts/seed_mock_data.py`) + INTEGRATION_RUNBOOK 통합 검증
- KIS 모의투자 서버 read-only 1회 인수

상세: [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md)

---

## v0.2 — PC 대시보드 MVP (✅ 마감)

기준선: `v0.1-backend-final`. 백엔드 코드 0건 변경. vitest 36 / e2e 6.

핵심 산출물:

- Vite 5 + React 18 + TypeScript 5.5 + Tailwind 3.4 + TanStack Query/Table + Recharts
- 8 화면: Today / Recommendations / History / Holdings / StockDetail /
  MarketCapTop / Jobs / Settings — 모두 backend read-only API 만 소비
- 코드 스플릿 (page-level lazy + manualChunks: vendor-react / query / table /
  charts) — 첫 진입 (Today, no charts) ≈ gzip 80 kB
- 비밀값 마스킹 가드 (`secret-*` 노드 `data-masked="true"` + `⚠ unmasked` 부재 e2e)
- 자동매매 UI 부재 가드 (8 페이지 모두 `<button type="submit">` / `<form>` 0건,
  "실거래 시작 / 자동매매 시작 / 주문 실행" CTA 라벨 0건 e2e)
- Docker 배포 (`web` 컨테이너 nginx + `/api` proxy → backend, port 8080)
- Playwright e2e 6 + msw v2 + jsdom

상세: [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md)

---

## v0.3 — 분석 보강 + 운영 정착 (✅ 마감)

기준선: `v0.2-frontend-final`. backend 296 → 319 / vitest 36 → 59 / e2e 6 → 8.

핵심 산출물 (5 phase):

- **Phase A** — GitHub Actions CI 3 잡 (backend pytest / frontend vitest+build /
  Playwright e2e). main / PR 자동 검증. 태그 `v0.3-phase-a-ci`.
- **Phase B** — 캔들 패턴 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING /
  BEARISH_ENGULFING) + Wilder ATR(14) + 4단계 변동성 분류. `technical_score` 에
  ±5점 cap 보조 가산. `StockIndicator` 에 nullable 컬럼 3개 추가 (atr14 /
  candle_patterns / volatility_band). 태그 `v0.3-backend-analysis`.
- **Phase C** — KRX 휴장일 정적 JSON (2025–2027) + `marketCalendar` 유틸 +
  `MarketStatusBanner` 컴포넌트 (Today / Jobs / Holdings 헤더). 외부 API 호출 0건.
  태그 `v0.3-frontend-calendar`.
- **Phase D** — `GET /api/stocks/{symbol}/prices?days=120` 신규 + StockDetail
  일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자. 태그
  `v0.3-frontend-stock-chart`.
- **Phase E** — `RELEASE_NOTES_v0.3.md` + 마감 선언. 태그 `v0.3-final`.

상세: [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md)

---

## v0.4 — Analyst & Theme Intelligence (✅ 마감)

기준선: `v0.3-final` (HEAD `f6b0ba5`). backend 319 → 335 (Phase A) → 362 (Phase B) → **382 (Phase D)**.

증권사 애널리스트 리포트 (기업 / 산업 / 테마 / 원자재 / 매크로 / 전략) 메타데이터를
저장 + 리포트에서 추출한 투자 테마와 종목 매핑 + 변화 시그널 이벤트를 구조화 +
보조 점수 (`report_score` + `theme_signal_score`) 를 추천에 ±5점 cap 가산 +
StockDetail 화면 4 카드 (Consensus / Reports / Themes / Signals) + Recommendations
점수 컬럼.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | DB 모델 6종 + Repository 6종 + 통합 테스트 16건 | ✅ 인수 | `v0.4-backend-reports` |
| B | CSV import CLI + 일별 컨센서스 스냅샷 잡 + 통합 테스트 27건 | ✅ 인수 | `v0.4-import-pipeline` |
| C | `report_score` + `theme_signal_score` 계산기 + RecommendationEngine 통합 (±5점 cap) + decision evidence | ✅ 인수 | `v0.4-report-score` |
| D | 프런트 (StockDetail 리포트·테마·시그널 4 카드 + Recommendations score 컬럼) | ✅ 인수 | `v0.4-frontend-reports` |
| E | `RELEASE_NOTES_v0.4.md` + 마감 선언 + 4 게이트 재확인 (382 / 60 / build / 9) | ✅ 인수 | `v0.4-final` |

**저작권 / 컴플라이언스 정책 (전체 v0.4 사이클, v0.5 에도 그대로 적용)**:

- 리포트 원문 본문 / paragraph DB 저장 0건
- PDF BLOB DB 저장 0건 — `source_url` 또는 `source_file_path` 만
- `source_file_path` 외부 노출 0건 (API 응답 / 프런트 / e2e 모두 마스킹)
- 자동 크롤링 / 스크레이핑 0건 (수동 CSV / Excel import 만)
- 외부 공유 / 공개 API 0건
- 추천 산식 본 weight 변경 0건 (보조 ±5점 cap 만)

상세: [`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md), [`PLANS.md`](./PLANS.md) `PLAN-0004`

---

## v0.5 — News, Disclosure & Theme Ranking (✅ 마감)

기준선: `v0.4-final` (HEAD `0f25be6`). 382 / 60 / build / 9 baseline 위에 5 phase
누적 — Dummy 5 컴포넌트 중 `news_score` (가중치 25%) 가 처음으로 real 화되었고,
v0.4 의 테마 데이터가 첫 surfacing (`/themes` 화면) 되었다. 마감 게이트 481 / 68
/ build / 11.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | News data layer — `NewsProviderInterface` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 (19:00 KST) | ✅ 인수 | `v0.5-news-collector` |
| B | Disclosure subset — 5 카테고리 keyword 분류 (RISK_DISCLOSURE / EARNINGS_REPORT / OWNERSHIP_CHANGE / GOVERNANCE / OTHER) + `collect_disclosures` 잡 (20:00 KST) | ✅ 인수 | `v0.5-disclosure-pipeline` |
| C | `RealNewsScoreProducer` + `DisclosureRiskProducer` + `ScoreProducerInterface` ABC 추출 + RecommendationEngine 통합 (Dummy → Real news_score, Risk 보강) + decision evidence | ✅ 인수 | `v0.5-news-score` |
| D | 백엔드 `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) + 프런트 `/themes` 9번째 화면 + StockDetail 영향 설명 강화 + Recommendation evidence 노출 | ✅ 인수 | `v0.5-frontend-themes` |
| E | `RELEASE_NOTES_v0.5.md` + 마감 선언 + 4 게이트 재확인 (481 / 68 / build / 11) | ✅ 문서 마감 | `v0.5-final` |

**v0.5 핵심 정책 (cycle-wide)**:

- 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건 — v0.1~v0.4 와 동일
- POST / PUT / DELETE 라우터 0건 (read-only API 만)
- 뉴스 / 공시 본문 (paragraph) DB 저장 0건 — title / URL / 메타데이터만 (v0.4 저작권 정책 패턴 유지)
- 자동 fetch default OFF (`Settings.news_collection_enabled` / `disclosure_collection_enabled` = false). 운영자가 `.env` 에 명시 enable 시에만 동작
- 재무 / 실적 점수 실제화 = **v0.6 후보** (PER/PBR/EPS/ROE + DART 재무제표 파싱은 별도 cycle)
- 관심종목 / 인증 = **v0.6 후보** (POST 도입 + 인증 동반)
- HoldingCheckEngine 산식 변경 0건 (보유 점검은 그대로)
- 추천 산식 본 weight 변경 0건 — `news_score` 가 50 → real 로 교체되지만 weight 25% 그대로

상세 계획: [`PLANS.md`](./PLANS.md) `PLAN-0005`

---

## v0.6 — Fundamental & Earnings Intelligence (✅ 마감)

기준선: `v0.5-final` (HEAD `9ccf0f8`). 481 / 68 / build / 11 baseline 위에 5 phase
누적 — Dummy 5 컴포넌트 중 `fundamental_score` (recommendation 15%) + HoldingCheckEngine
의 `earnings_score` 가 처음으로 real 화되었고, 운영자 수동 CSV import 기반으로
`fundamental_snapshots` (24번째 테이블) + `earnings_events` (25번째 테이블) 데이터가
도입되었다. 추천·보유 본 weight 산식은 변경하지 않았다 — placeholder 50 → real 로
교체되었을 뿐. 마감 게이트 558 / 77 / build / 13.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | Fundamental data layer — `FundamentalProviderInterface` + `FundamentalSnapshot` ORM (24번째 테이블, 8 지표) + `scripts/import_fundamentals.py` argparse CLI (default dry-run) | ✅ 인수 | (별도 태그 부재 — 커밋 `0d3dba5` + `da3567f` 로 추적) |
| B | Earnings event layer — `EarningsProviderInterface` + `EarningsEvent` ORM (25번째 테이블) + BEAT/MEET/MISS 분류 + `scripts/import_earnings.py` | ✅ 인수 | `v0.6-earnings-event-pipeline` |
| C | `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + RecommendationEngine·HoldingCheckEngine 통합 (Dummy → Real, 본 weight 변경 0건) + decision evidence | ✅ 인수 | `v0.6-fundamental-score` |
| D | 백엔드 read-only API 3종 (`/api/stocks/{symbol}/fundamentals` + `/api/stocks/{symbol}/earnings` + `/api/calendar/earnings`) + `RecommendationItemSchema`·`HoldingCheckSchema` evidence 필드 + 프런트 StockDetail Fundamental·Earnings 카드 + Today 다가오는 어닝 + Recommendations·Holdings evidence 통합 | ✅ 인수 | `v0.6-frontend-fundamentals` |
| E | `RELEASE_NOTES_v0.6.md` + 마감 선언 + 4 게이트 재확인 (558 / 77 / build / 13) | ✅ 문서 마감 | `v0.6-final` |

**v0.6 핵심 정책 (cycle-wide)**:

- 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건 — v0.1~v0.5 와 동일
- POST / PUT / DELETE 라우터 0건 (read-only API 만)
- DART API 자동 호출 0건 — 1단계는 운영자 CSV 만 (v0.4 Analyst Report import 패턴 그대로). ABC + Fake provider 만 두고 실 API 는 v0.7+ 후보
- 자동 fetch default OFF (`Settings.fundamental_collection_enabled` / `earnings_collection_enabled` = false). 운영자 명시 enable + 실 provider 주입 시에만 동작
- 재무제표 PDF / Excel BLOB DB 저장 0건 — CSV 정량 지표 + 짧은 메모 (≤500자) 만
- 본문 paragraph 저장 0건 (forbidden body column 13종 거부 가드)
- 추천 산식 본 weight 변경 0건 — `fundamental_score` 가 50 → real 로 교체되지만 weight 15% 그대로
- HoldingCheckEngine 본 weight 변경 0건 — `earnings_score` 가 50 → real 로 교체되지만 weight 그대로
- 관심종목 / Watchlist / 인증 = **v0.7 후보** (POST 도입 + 인증 묶음)
- Strategy / Backtest / MockBroker = **v0.8+ 후보**
- LLM 자동 재무·어닝 분석 = **v0.7+ 후보** (룰 기반 검증 후)

상세 계획: [`PLANS.md`](./PLANS.md) `PLAN-0006` / 마감 사유: [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md)

---

## v0.7 — Strategy & Backtest Foundation (✅ 마감)

기준선: `v0.6-final` (HEAD `e729d60`). 558 / 77 / build / 13 baseline 위에 5 phase
누적 — v0.1~v0.6 누적된 추천 판단 축 (technical / report / theme / news /
disclosure / fundamental / earnings + risk_penalty + recommendation_results
1·3·5·20일) 위에 **`StrategyInterface` ABC + 룰 기반 전략 3종 + `BacktestEngine` +
`CostModel` + 시장 국면별 분리 + 백테스트 화면** 을 도입했다. 다음 자연 질문
"이 추천이 돈이 되는가?" 에 답하기 위한 cycle. 마감 게이트 682 / 84 / build / 14.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | Strategy interface — `StrategyInterface` ABC + `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` 3종 + 단위 테스트 56개 | ✅ 인수 | `v0.7-strategy-interface` |
| B | Backtest engine — `BacktestRun` (26번째 테이블) + `BacktestResult` (27번째 테이블) + `BacktestEngine` + `scripts/run_backtest.py` (default dry-run) + 통합 테스트 38개 | ✅ 인수 | `v0.7-backtest-engine` |
| C | 비용 모델 + 시장 국면별 분리 — `CostModel` (placeholder buy 0.015% / sell 0.015% / 거래세 0.20% / 슬리피지 0.1% = **0.33% 차감**, `constant-v1`) + `assign_regime` (`MarketRegime.date <= signal_date` 가장 최근) + `cost_adjusted_return_5d` / `regime` 컬럼 + `regime_breakdown` summary | ✅ 인수 | `v0.7-backtest-cost-regime` |
| D | 백엔드 read-only API 3종 (`/api/strategies` + `/api/backtest/runs` + `/api/backtest/runs/{run_id}`) + 프런트 10번째 화면 `/backtest` + Sidebar `백테스트 (β)` 메뉴 | ✅ 인수 | `v0.7-frontend-backtest` |
| E | `RELEASE_NOTES_v0.7.md` + 마감 선언 + 4 게이트 재확인 (682 / 84 / build / 14) | ✅ 문서 마감 | `v0.7-final` |

**v0.7 핵심 정책 (cycle-wide)**:

- 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건 — v0.1~v0.6 와 동일
- POST / PUT / DELETE 라우터 0건 (read-only API 만)
- 인증 / Watchlist 0건 = **v0.8 후보** (POST 도입 + 인증 묶음)
- 실 DART / 실 RSS 호출 0건 — v0.5 / v0.6 의 ABC + Fake provider 정책 유지
- ScoringEngine 본 weight 변경 0건 — 추천 / 보유 산식 그대로
- HoldingCheckEngine 산식 변경 0건
- LLM 자동 전략 생성 0건 — 룰 기반만, LLM 보강은 v0.8+ 후보
- Alembic 도입 0건 — v0.7 신규 테이블 2개 추가 후 v0.8 권장
- 비용 모델은 placeholder constant 만 — 실 broker fee schedule 은 v0.8+ 후보
- 운영 모니터링 (Sentry / Prometheus / Grafana) 0건 — v0.8+ 후보
- 백테스트 결과 자동 텔레그램 알림 0건 — read-only 화면만

상세 계획: [`PLANS.md`](./PLANS.md) `PLAN-0007` / 마감 사유: [`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md)

---

## v0.8 — User & Migration Foundation (✅ 마감)

기준선: `v0.7-final` (HEAD `1f5b01f`). 682 / 84 / build / 14 baseline 위에 5
phase 누적 — v0.1 부터 일관 유지된 read-only 정책의 **첫 변경 cycle**.
27 테이블 + 누적 ALTER 5건 시점에 **Alembic baseline 도입** + 단일 사용자
인증 기반 (`AUTH_ENABLED` 토글 + JWT HS256 + scrypt + `LoginAuditLog`) 위에
**Watchlist 도메인 POST/DELETE 첫 도입** + Watchlist 프런트 11번째 화면 +
Login 화면 + StockDetail `FavoriteButton` + Today `WatchlistCard`. 마감
게이트: backend pytest **808 / vitest 113 / e2e 19 / build 그린**.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | Alembic baseline (`alembic.ini` + `env.py` + `0001_baseline_v0_7.py` 27 테이블 + CI 검증 + INTEGRATION_RUNBOOK §17) | ✅ 인수 | `v0.8-alembic-baseline` |
| B | 단일 사용자 인증 (`User` 28 + `LoginAuditLog` 29 + JWT + `AUTH_ENABLED` 토글 + `POST /api/auth/login` 첫 POST) | ✅ 인수 | `v0.8-auth-foundation` |
| C | Watchlist DB / API (`Watchlist` 30 + `WatchlistItem` 31 + GET/POST/DELETE 5 라우터 + 인증 가드) | ✅ 인수 | `v0.8-watchlist-api` |
| D | Watchlist 프런트 + Today/StockDetail 통합 (11번째 화면 + `/login` + Sidebar `관심종목`) | ✅ 인수 | `v0.8-frontend-watchlist` |
| E | `RELEASE_NOTES_v0.8.md` + 마감 + tag `v0.8-final` | ✅ 문서 마감 | `v0.8-final` |

**v0.8 핵심 정책 (cycle-wide)**:

- 자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건 — v0.1~v0.7 와 동일
- POST 라우터 = **5건만** (`POST /api/auth/login` + `POST /api/auth/logout` + `GET /api/auth/me` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`). 그 외 도메인 POST/PUT/DELETE 0건
- 실 DART / 실 RSS / 실 News API 호출 0건 — v0.5 / v0.6 ABC + Fake provider 정책 유지
- ScoringEngine / HoldingCheckEngine 본 weight 변경 0건
- LLM 자동 전략 생성 0건
- MockBroker / ReplayBroker / SimulationBroker 0건 (v0.10+ 검토)
- 다중 사용자 / SaaS / RBAC 0건 — 단일 admin user 만
- OAuth / SSO 0건 — 단일 username/password + bcrypt + JWT 만
- Refresh token / token revocation list 0건 — 24h JWT TTL + 재로그인만
- 운영 모니터링 (Sentry / Prometheus / Grafana) 0건 — v0.9 후보
- Watchlist 자동 텔레그램 / 가격 알림 0건 — 알림 시스템 변경 0건
- WebSocket / SSE 0건 — 폴링 그대로
- Recommendations / Backtest / Today 산식 변경 0건 — 즐겨찾기는 표시/필터만
- 평문 IP / 평문 password 저장 0건 — `LoginAuditLog.source_ip_hash` 는 SHA256 만, password 는 bcrypt cost 12

상세 계획: [`PLANS.md`](./PLANS.md) `PLAN-0008`

---

## v0.9+ 후보

v0.8 마감 후 진입 가능 후보. 현재는 모두 미착수 — 명시적 진입 요청 전까지 손대지 않는다.

### 8.1 사용자 설정 / 운영 모니터링 (v0.9 우선 후보)

- **사용자 설정** — 관심 시장 / 기본 대시보드 필터 / 기본 전략 / 알림 선호도. 인증 후 자연 확장.
- **운영 모니터링** — Sentry / Prometheus / Grafana / job health dashboard. 외부 노출 시점에 함께.
- **글로벌 검색** (cmd+k), 사이드바 collapse, breadcrumb, loading skeleton 통일.
- **CSRF / Content-Security-Policy 헤더** — 외부 노출 시 강화.
- **rate limit (`slowapi` 등)** — POST 라우터 + 인증 운영 검증 후.

### 8.2 데이터 / 분석 실제화

- **실 DART API 구현체** — v0.6 의 `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 위에 `DartFundamentalProvider` / `DartEarningsProvider` 추가. 라이선스 / 스로틀링 / 정책 검토 동반.
- **실 RSS / News API 구현체** — v0.5 의 `NewsProviderInterface` 위에 `RssNewsProvider` / `NaverNewsProvider` 등. 라이선스 검토 동반.
- **재무 score 산식 고도화** — v0.6 의 절댓값 기반 산식을 시장 percentile / 섹터 평균 기반으로 확장. 시장 환경 (금리 변화) 민감도 완화.
- **earnings surprise 다지표 가중** — operating income 단일 → EPS / 매출 / 순이익 가중 평균.
- **News/Disclosure 출처 확장** — 다중 RSS / DART subset / 외부 API.
- **KRX 휴장일 자동 fetch** — 정적 JSON 의 수동 갱신 (매년) 을 자동 fetch 로 대체.
- **추천 성과의 N=20 외 다른 기간 토글** — 현재는 1/3/5/20일 고정.

### 8.3 운영 / UX

- **운영 모니터링** — Sentry / Prometheus / Grafana. 인증 도입 후 가치 ↑.
- **모바일 / 태블릿 레이아웃** — 현재는 PC 1280px+ 우선.
- **StockDetail 캔들 차트 + 거래량 BarChart + 이동평균 오버레이** — `lightweight-charts` 마이그레이션 검토.

### 8.4 백엔드 인프라

- **POST 트리거** (잡 수동 실행 / 추천 즉시 생성 / 백테스트 시작) — 인증 동반 필수.
- **WebSocket / SSE 실시간 잡 / 백테스트 진행 상태** — 현재 polling.
- **`.github/dependabot.yml`** — v0.3 Phase A 에서 보류된 항목.

### 8.5 LLM / AI 강화

- **Analyst Report LLM 자동 요약** — v0.4 Phase A 의 `extraction_method` / `extraction_confidence` 필드를 활용해 LLM 추출 결과를 안전하게 mark.
- **News / Disclosure LLM sentiment** — v0.5 의 룰 기반 sentiment 를 LLM 보강.
- **재무 / 어닝 LLM 분석** — v0.6 의 룰 기반 산식을 LLM 보강 (예: 실적 발표 후 Q&A 톤 분석).
- **LLM 자동 전략 생성 / 평가** — v0.7 의 룰 기반 전략 → LLM 기반 (룰 기반 검증 후).
- **AI Provider 교체** — 현 `DummyScoreProducer` → 로컬 / 클라우드 LLM 통합.

### 8.6 백테스트 고도화 (v0.7 검증 후 단계적)

- **다중 전략 동시 백테스트 + 포트폴리오 합산** — v0.7 단일 전략 검증 후.
- **walk-forward 검증** — 시간 누설 차단 + out-of-sample 검증.
- **실 broker 수수료 schedule + 호가 단위별 슬리피지** — v0.7 placeholder 검증 후.
- **종목별 / 섹터별 / 시가총액 구간별 성과 breakdown.**
- **전략 hyperparameter Grid Search.**

---

## Future Backlog — 자동매매 / 백테스트 / 가상매매

⚠ **모두 별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실 제한 사이클이
선행되어야 진입 가능.** v0.5 ~ v0.8 의 모든 후보는 자동매매 부재 정책을 유지한다.

| 단계 | 범위 | 진입 전제 |
|---|---|---|
| Strategy & Signal | StrategyInterface 활성화 ✅, SIGNAL 모드 + 룰 기반 전략 ✅ + 백테스트 검증 ✅ | **v0.7 ✅ 마감** — 실 News (v0.5 ✅) + 재무 / 어닝 (v0.6 ✅) 위에 read-only 검증 완료. 다음 단계는 v0.8 (User & Migration Foundation, ⏳ 진행 중) 후행. |
| User & Auth Foundation | 단일 사용자 인증 + Watchlist + Alembic baseline + POST 첫 도입 | **v0.8 ✅ 마감** — POST 라우터 = 5건 한정 (auth 3 + watchlist 2). 다중 사용자 / OAuth / RBAC 0건 |
| Backtest 엔진 | walk-forward 검증, Grid Search 튜닝, 시장 국면별 성과 분석 | Strategy 모듈 선행 |
| MockBroker / ReplayBroker / SimulationBroker | 가상 계좌 / 가상 주문·체결 / 가상 시나리오 / 스트레스 테스트 | BrokerInterface 구현 진입 |
| 전용 ML 모델 | Market Regime / Strategy Selection / Risk Prediction. 추천 성과 기반 재학습. LLM 과 전용 AI 역할 분리 | Backtest 데이터 누적 후행 |
| APPROVAL 모드 | 사용자 승인 후 실 KIS 주문 — 비상정지 / 일일 손실 제한 / 종목당 한도 / 전략별 한도 / 실거래 로그 / 보안 강화 동반 | 컴플라이언스 검토 + MockBroker 검증 |
| SMALL_AUTO | 소액 자동 — 위와 동일 보안 게이트 + 자본 상한 | APPROVAL 모드 안정 운영 후 |
| FULL_AUTO | 전면 자동 | 본 프로젝트 범위 외 — 별도 설계 cycle |

**전체 자동매매 흐름 (모두 미구현)**:

```text
Strategy Signal → AI Judgement → RiskEngine → BrokerInterface → TradeLogger
```

`BrokerInterface` 는 ABC placeholder 만 유지. v0.1 ~ v0.8 어디에도 구현체 없음.
v0.7 의 `StrategySignal` 도 분석 신호이지 매매 주문이 아니다 — broker / 주문 /
계좌 / 가격 / 수량 / order_type / side 필드 0건. v0.8 의 Watchlist `POST` 도
즐겨찾기 추가/삭제만 — 주문 / Broker / 자동매매 0건.

---

## 장기 비전

AI 기반 개인용 주식 전략 연구 플랫폼.

```text
KIS data + 휴장 캘린더 + 증권사 리포트 + 테마 매핑 + 시그널 이벤트
   → 분석 / 점수 / 추천 / 보유 점검 / 컨센서스
   → 텔레그램 / 대시보드 (read-only)
   → (v0.5 ✅) 실 News / 공시 + 테마 랭킹 화면
   → (v0.6 ✅) 재무·실적 (CSV 1단계) + 어닝 캘린더 + StockDetail 통합
   → (v0.7 ✅) Strategy / Backtest 기초 + 비용 모델 + 백테스트 화면
   → (v0.8 ✅) Alembic baseline + 단일 사용자 인증 + Watchlist (POST 첫 도입) + 즐겨찾기 통합
   → (v0.9+) 사용자 설정 / 운영 모니터링 / DART 실 API / 백테스트 고도화 / LLM 보강
   → (Future) MockBroker / 가상매매 → APPROVAL → SMALL_AUTO
```

본 프로젝트는 **투자 판단 보조 도구**다. 자동매매는 오랜 검증과 보안 강화가
완료된 후에만 검토한다.
