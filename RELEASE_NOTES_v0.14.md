# RELEASE_NOTES_v0.14.md — Paper / Simulation Trading Foundation

> 마감 태그: `v0.14-final`
> 마감 일자: **2026-05-08 (Asia/Seoul)**
> 기준 태그: `v0.13-final` → 마감 태그: `v0.14-final`
> 세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0014`

---

## 1. 사이클 요약

v0.14 는 **Paper / Simulation Trading 기반**을 완성한 사이클이다. 가상 계좌(`VirtualAccount`),
가상 주문(`VirtualOrder`), 가상 포지션 / 체결 / 일별 PnL 스냅샷, `SimulationBroker`
(BrokerInterface 첫 구현체), `PnLTracker`, Paper Trading API 6 라우터, 스케줄러
잡 2건, 그리고 13번째 프런트 화면 `/paper` 를 모두 도입했다.

**v0.1 ~ v0.13 의 안전 정책은 그대로 유지된다** — 실 KIS 주문 / 실 Broker /
자동매매 / FULL_AUTO / SMALL_AUTO / APPROVAL 코드 0건. 모든 paper 코드 경로는
실 KIS 주문과 물리적으로 분리되어 있고, AST + grep + 통합 테스트가 KIS / DART /
RSS / requests / httpx import 0건을 강제한다.

| Phase | 내용 | 태그 | 게이트 |
|---|---|---|---|
| A | Backtest Export CLI + ProviderScorePolicy → producer 통합 | `v0.14-export-policy` | pytest **1277→1322 (+45)** |
| B | SimulationBroker + VirtualAccount/VirtualOrder ORM + Alembic 0005 | `v0.14-sim-broker` | pytest **1322→1365 (+43)** |
| C | VirtualPosition + VirtualFill + VirtualPnLSnapshot + PnLTracker + execute_pending_orders + Alembic 0006 | `v0.14-pnl-tracker` | pytest **1365→1405 (+40)** |
| D | Paper Trading API (GET 4 + POST 1 + DELETE 1) + 스케줄러 잡 2건 | `v0.14-paper-api` | pytest **1405→1438 (+33)** |
| E | 프런트 13번째 화면 `/paper` + 본 release notes + 마감 문서 + 4 게이트 최종 확인 | `v0.14-final` | vitest **175→186 (+11)** / e2e **21→22 (+1)** |

---

## 2. 산출물 상세

### Phase A — Backtest Export CLI + ProviderScorePolicy → producer 통합

- `scripts/export_backtest.py` 신규 — `--run-id` / `--format csv|json` / `--output PATH` /
  `--dry-run` / `--db-url` 지원. `FORBIDDEN_EXPORT_FIELDS` 화이트리스트 (evidence_json /
  source_file_path / config_json / summary_json / reason 미노출).
- `app/analysis/score_producers.py` — `RealNewsScoreProducer` /
  `RealFundamentalScoreProducer` / `RealEarningsScoreProducer` 에 `ProviderScorePolicy.apply()`
  통합. `PROVIDER_SCORE_POLICY_ENABLED=False` 기본 (기존 동작 0건 변경).
- 통합 23건 + 단위 25건 신규.

### Phase B — SimulationBroker + VirtualAccount / VirtualOrder

- `app/db/models.py` — `VirtualAccount` (33번째) + `VirtualOrder` (34번째) ORM 추가.
- `alembic/versions/0005_virtual_trading_core.py` 신규 — 2 테이블 + 4 인덱스 + unique 2건.
- `app/data/repositories/virtual_account.py` / `virtual_order.py` 신규.
- `app/broker/simulation_broker.py` 신규 — `SimulationBroker` (BrokerInterface 첫
  구현체). `submit_order` 는 `PAPER_TRADING_ENABLED=False` 또는 account.paper_trading_enabled=False
  시 `PaperTradingDisabledError`. idempotency_key 중복은 기존 row 반환
  (`SubmitResult.deduplicated=True`). `cancel_order` 는 CREATED/SUBMITTED → CANCELED 만 허용.
- `app/config/settings.py` — `paper_trading_enabled: bool = False` 추가.
- 단위 29건 + 통합 16건 + Alembic spot-check 갱신.
- **금지 컬럼 0건**: `broker_order_id / kis_order_id / real_account / api_key / token / secret`.
- **AST 회귀 단언**: simulation_broker.py 의 forbidden import 0건.

### Phase C — VirtualPosition + VirtualFill + VirtualPnLSnapshot + PnLTracker + execute_pending_orders

- `app/db/models.py` — `VirtualPosition` (35) + `VirtualFill` (36) + `VirtualPnLSnapshot` (37) ORM.
- `alembic/versions/0006_virtual_positions.py` 신규 — 3 테이블 + 11 인덱스 + unique 2건.
- `app/data/repositories/virtual_position.py` — `apply_buy` (cost-basis blend) /
  `apply_sell` (realized PnL 누적, 0 도달 시 avg_cost 리셋) / `InsufficientPositionError`.
- `app/data/repositories/virtual_fill.py` — 비용 4종 분리 저장 (fee / stamp_tax / slippage / gross / net).
- `app/data/repositories/virtual_pnl_snapshot.py` — `create_or_replace_snapshot` (idempotent upsert).
- `app/paper/pnl_tracker.py` 신규 — `PnLTracker.apply_fill` (BUY: cash↓ position↑ avg_cost rebase;
  SELL: cash↑ realized_pnl 누적 + zero 시 avg_cost 리셋) + `create_daily_pnl_snapshot`
  (open positions × daily_prices.close, 가격 없는 종목은 0 graceful).
- `app/backtest/cost_model.py` — `PaperTradingCostModel` (paper-v1) 추가:
  buy_fee 0.015% / sell_fee 0.015% / sell_tax 0.18% (매도 only) / slippage 0.05%.
  **기존 `CostModel` (constant-v1) 상수 변경 0건** — BacktestEngine 회귀 0건.
- `app/broker/simulation_broker.py` — `execute_pending_orders(session, *, as_of_date,
  account_id?, pnl_tracker?, price_lookback_days=0)` 본 구현. MARKET 즉시 체결 / LIMIT BUY
  close ≤ limit / LIMIT SELL close ≥ limit / no price → skip / terminal → skip / cash·position
  부족 → REJECTED. `ExecutePendingResult` 구조화 결과.
- 단위 8건 + 통합 27건 + Alembic spot-check 갱신.

### Phase D — Paper Trading API + 스케줄러 잡

- `app/api/paper_routes.py` 신규 — 6 엔드포인트:
  - `GET /api/paper/account` — VirtualAccount + 최신 PnL snapshot 합산
  - `GET /api/paper/orders?status=&symbol=&limit=` — 주문 이력 (id desc)
  - `GET /api/paper/positions?include_closed=` — daily_prices.close lookback 14일 평가
  - `GET /api/paper/pnl?from_date=&to_date=&limit=` — VirtualPnLSnapshot 시계열 (inverted → 422)
  - `POST /api/paper/orders` — `SimulationBroker.submit_order`. AUTH + PAPER_TRADING_ENABLED 필요.
    idempotency_key 중복 시 기존 order + `deduplicated=true`. disabled → 503
  - `DELETE /api/paper/orders/{id}?reason=` — `SimulationBroker.cancel_order`.
    terminal → 422, unknown → 404. AUTH + PAPER_TRADING_ENABLED 필요
- `app/api/schemas.py` — 10종 paper 스키마 추가. forbidden 응답 필드 12종 0건
  (api_key / token / secret / source_file_path / broker_order_id / kis_order_id /
  real_account / broker / account_number / raw_text / body / full_text).
- `app/scheduler/jobs.py` — `execute_paper_orders` (16:00 KST) +
  `create_paper_pnl_snapshot` (16:30 KST) 신규. PAPER_TRADING_ENABLED=false → SKIPPED;
  enabled 시 active VirtualAccount 전체 처리 (per-account 격리).
- 통합 25건 + scheduler 8건 + auth_security 가드 정밀화.

### Phase E — 프런트 13번째 화면 `/paper` + 마감 문서

- `frontend/src/api/paper.ts` 신규 — `fetchPaperAccount` / `fetchPaperOrders` /
  `fetchPaperPositions` / `fetchPaperPnl` / `submitPaperOrder` / `cancelPaperOrder`.
  호출 URL은 `/api/paper/*` 6종만.
- `frontend/src/hooks/usePaperTrading.ts` 신규 — 6 TanStack Query hooks
  (read 4 + mutation 2). mutation 후 paper namespace 전체 invalidate.
- `frontend/src/pages/PaperTrading/index.tsx` 신규 (13번째 화면) — 5 컴포넌트:
  `VirtualAccountCard` / `PaperOrderForm` / `VirtualPositionsTable` / `PnLTable` /
  `PaperOrdersTable` + 정책 배너 + disabled 503 친절 안내. 버튼 라벨은 "페이퍼 주문
  만들기" — "주문 실행" / "place order" 같은 actionable CTA 없음.
- `frontend/src/router.tsx` + `frontend/src/components/layout/Sidebar.tsx` —
  13번째 메뉴 `/paper` (`LineChart` 아이콘, "페이퍼 트레이딩 (β)").
  사이드바 footer 도 "v0.14 dashboard" / "실 KIS 주문 / 자동매매 미포함" 으로 갱신.
- `frontend/src/api/types.ts` — `PaperAccount` / `PaperOrder` / `PaperPosition` /
  `PaperPnLSnapshot` / `CreatePaperOrderRequest` / 응답 wrapper 타입 추가.
- `frontend/src/tests/PaperTrading.test.tsx` 신규 vitest 11건 — page render /
  account happy / 404 empty placeholders / positions / pnl / orders / disabled 503 /
  submit success / cancel mutation / forbidden DOM 토큰 0건 / 자동매매 CTA 0건.
- `frontend/src/tests/mswServer.ts` — paper 6 엔드포인트 mock 추가 (POST/DELETE 기본 503).
- `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts` —
  sidebar 12 → 13 menus, `/paper` happy-path navigation, raw payload forbidden 검사,
  disabled banner 시나리오 추가.

---

## 3. 최종 게이트 (v0.14-final)

| 게이트 | 결과 |
|---|---|
| backend pytest | **1438 → 1438 passed** (Phase E 는 frontend only — backend 회귀 0건) |
| frontend vitest | **186 passed** (Phase D end 175 → Phase E 186, +11 — PaperTrading.test 신규) |
| frontend build | **그린** (`tsc --noEmit && vite build`) |
| Playwright e2e | **22 passed** (Phase D end 21 → Phase E 22, +1 — `/paper` happy-path) |
| Alembic head | `0006_virtual_positions` (Phase E revision 0건) |
| `compare_metadata` diff | **0건** (CI 강제) |

---

## 4. 안전 정책 (v0.14 누적)

- **실 KIS 주문 / 실 Broker / 자동매매 / FULL_AUTO / SMALL_AUTO / APPROVAL 코드 0건**
  (v0.1 ~ v0.14 일관). `BrokerInterface` 의 첫 구현체는 `SimulationBroker` (paper 전용)
  뿐이며, KisBroker / 실거래 브로커는 여전히 placeholder.
- **`PAPER_TRADING_ENABLED=false` 기본** — `SimulationBroker.submit_order` 는 거부,
  Paper Trading mutation API는 503 응답, 스케줄러 잡 2건은 SKIPPED.
- **VirtualOrder 와 실 KIS 주문은 코드 경로 / 테이블 / 라우터 / 스키마가 완전히 분리**
  — 혼동 불가 구조.
- **forbidden 응답 / DOM 필드 0건** (12종): `api_key / token / secret / source_file_path /
  broker_order_id / kis_order_id / real_account / broker / account_number / raw_text /
  body / full_text` — backend Pydantic 스키마 + frontend 컴포넌트 + e2e raw payload
  검사로 3중 단언.
- **외부 네트워크 호출 0건** — `app/broker/simulation_broker.py` /
  `app/paper/pnl_tracker.py` / `app/api/paper_routes.py` / 3 신규 repository 모두 AST
  검사로 `requests / httpx / urllib / urllib3 / app.kis / app.data.dart_provider /
  app.data.rss_provider` import 0건 강제.
- **ScoringEngine / HoldingCheckEngine 본 weight 변경 0건** —
  technical 35% / news 25% / supply 15% / fundamental 15% / ai 10% 그대로.
- **기존 backtest CostModel 상수 변경 0건** — `PaperTradingCostModel` (paper-v1) 신규
  추가, `CostModel` (constant-v1) 보존.
- **신규 pip 의존성 0건**.
- **자동매매 CTA UI 0건** — submit 버튼 라벨은 "페이퍼 주문 만들기", 모든 본문은
  "페이퍼" / "가상" / "시뮬레이션" 용어를 명시. e2e 가 "자동매매 시작" / "실거래 시작" /
  "주문 실행" / "FULL_AUTO" / "place real order" 등 패턴 0건을 강제.

---

## 5. 알려진 한계

- **단일 사용자 / 단일 계좌 가정** — v0.14 는 첫 VirtualAccount 를 자동 선택한다.
  멀티 계좌 / 멀티 사용자 UI 는 v0.15+ 후보.
- **체결 모델은 종가 기반** — `daily_prices.close` 만 사용. 호가 / 분봉 / 슬리피지의
  현실적 모델링은 후속 사이클 후보. 현재는 보수적 단일 가격에 0.05% 슬리피지 가정만 적용.
- **PnL 차트 미구현** — Phase E 는 일별 PnL 을 표 형태로만 노출. 차트 (Recharts)
  연동은 v0.15+ 에서 검토.
- **Paper 잡의 telegram 알림 미구현** — paper 주문/체결/일별 PnL 텔레그램 발송은
  v0.14 범위 외. 기존 텔레그램 dispatcher 는 그대로 read-only 추천 / 보유점검 리포트만 처리.
- **Approval 트레이딩 / OrderCandidate 미구현** — paper trading 안정 후 별도 보안 ·
  컴플라이언스 사이클에서 검토 (PLAN-0015+ 후보).
- **로컬 `.env` `MARKET_CAP_LIMIT=5` 등 운영자 오버라이드 시 `tests/unit/test_project_structure.py::test_settings_defaults`
  1건이 환경 의존적으로 실패** — CI 환경 (.env clean) 에서는 통과. v0.14 회귀와 무관한
  사전 존재 이슈.

---

## 6. v0.15 후보

- **Approval 트레이딩 준비** — OrderCandidate / 승인 플로우 설계 + skeleton.
  Paper Trading 안정 후 진입 (별도 보안 사이클 선행 필요).
- **PnL 차트 / 백테스트와의 비교 화면** — Recharts 기반 일별 자산 추이.
  paper 결과를 backtest 결과와 같은 축에서 비교.
- **multi-account / 멀티 사용자 UI** — 계좌 선택 / 권한 분리.
- **paper 텔레그램 알림** — 일별 PnL 요약, 거부된 주문 알림 (DRY_RUN 기본 유지).
- **ScoringEngine 본 weight 보강** — v0.13 / v0.14 validation report 누적 데이터
  6 개월+ 충분 시 검토 (지금은 데이터 부족).
- **paper trading 호가/분봉 체결 모델 정밀화** — 호가창 시뮬레이션 / 부분 체결 /
  시간외 단일가 등.
- **Grafana + ProviderHealthMonitor 영속화** — 외부 인프라 도입 사이클 후보.

---

## 7. 누적 사이클 / 태그

| 버전 | 마감 태그 | 핵심 기능 |
|---|---|---|
| v0.1 | `v0.1-backend-final` | FastAPI 백엔드 + 17 ORM 테이블 + read-only API + 6 스케줄러 잡 |
| v0.2 | `v0.2-frontend-final` | Vite/React/TS PC 대시보드 + msw + Playwright e2e |
| v0.3 | `v0.3-backend-analysis` | 캔들 패턴 5종 + Wilder ATR(14) + 4단계 변동성 분류 |
| v0.4 | `v0.4-final` | Analyst & Theme Intelligence (6 ORM) + 자동 크롤링 0건 |
| v0.5 | `v0.5-final` | News + Disclosure Collector + 테마 랭킹 |
| v0.6 | `v0.6-final` | Fundamental & Earnings Intelligence + read-only API |
| v0.7 | `v0.7-final` | Strategy & Backtest Engine + Cost Model + 시장 국면 |
| v0.8 | `v0.8-final` | Alembic baseline + 단일 사용자 인증 + Watchlist |
| v0.9 | `v0.9-final` | Security Hardening + Sentry + UserPreference |
| v0.10 | `v0.10-final` | Provider Resilience + DART/RSS skeleton + Health API |
| v0.11 | `v0.11-final` | Real Provider Transport + Prometheus + 24h aggregates |
| v0.12 | `v0.12-final` | Provider Data Ingestion + Walk-forward Backtest + 12번째 화면 |
| v0.13 | `v0.13-final` | Provider Score Policy + Validation Report (12번째 화면 fix) |
| **v0.14** | **`v0.14-final`** | **Paper / Simulation Trading Foundation (5 ORM + 6 API + 2 jobs + 13번째 화면)** |

이 시점의 누적: **37 ORM 테이블 / 51+ FastAPI 라우터 / 11 스케줄러 잡 / 13 프런트 화면 /
backend pytest 1438 / vitest 186 / e2e 22 / Alembic 6 revisions**.

---

## 8. 운영 절차 변경

- 운영자가 `.env` 에 `PAPER_TRADING_ENABLED=true` + `AUTH_ENABLED=true` +
  `JWT_SECRET=<32-char>` + `SCHEDULER_ENABLED=true` 를 명시 설정한 뒤
  `alembic upgrade head` (head 가 `0006_virtual_positions` 인지 확인) 로 활성화.
- VirtualAccount 1건 시드는 `INTEGRATION_RUNBOOK.md` §22.2 절차 참조.
- read-only GET 4종은 PAPER_TRADING_ENABLED 무관하게 동작 — 비활성 상태에서도 과거
  paper 데이터 조회 가능.
- mutation (POST/DELETE) 만 PAPER_TRADING_ENABLED + AUTH 필요 — 비활성 상태에서는
  503 응답.
- `/paper` 화면은 항상 정책 배너 + "모의투자 모드" 라벨 표시.
