# Architecture

> 본 문서는 **v1.0 마감 시점** 기준으로 갱신된다 (마감 태그 `v1.0-final`, 2026-05-09).
> v0.16 5 Phase 마감 + v1.0 Phase A·B·C·D·E 모두 완료.
>
> v1.0 Phase A (운영 진입 체크리스트) → Phase B (`HttpxKisOrderTransport`) → Phase C
> (RealOrderExecutor 10-gate + real path 분기) → Phase D (FillSyncService 델타 idempotent +
> POST /sync API) → **Phase E (`/real-orders` 강화 — RealTradingModeBanner + 수동 Sync Fill 버튼 +
> RELEASE_NOTES / RUNBOOK / 4 게이트 마감)**.
>
> 마감 게이트 (v1.0-final): backend pytest **2082** / frontend vitest **225** /
> Playwright e2e **25** / build 그린. Alembic head: `0010_real_fills` (41 테이블, v1.0 동안 변경 0건).
> mutating endpoint count: 15 → **16** (real-orders 1 추가).
>
> **v0.16 Real Order Skeleton 흐름 (dry-run 전용, 현재 production 경로):**
>
> `OrderCandidate (APPROVED)` → `RealOrderExecutor.execute(candidate_id)` →
> **8 안전 게이트** (①APPROVED 상태 ②중복 가드 ③kill_switch=False
> ④real_trading_enabled=True ⑤kis_order_enabled=True ⑥단건 한도 ⑦KST 일일 누적
> ⑧PreTradeRiskEngine 재검사) → `dry_run=True` → `FakeKisOrderTransport.place_order()`
> → `RealOrder(status=DRY_RUN, dry_run=True)` DB 저장 →
> `FillSyncService.sync(real_order)` → `FakeKisOrderTransport.query_fill_status()`
> (항상 FILLED) → `RealFill(fill_status=FULL)` DB 저장 →
> `GET /api/real-orders` → 15번째 화면 `/real-orders` read-only 표시.
>
> **v1.0 Phase B — `HttpxKisOrderTransport` 첫 실 transport 구현체 (mock-only 테스트):**
>
> `app/broker/kis_order_transport_real.py` — `KisOrderClientInterface` 의 첫 실
> 구현체. lazy `httpx` import (모듈 최상단 import 0건) + `respx` / `httpx.MockTransport`
> 100% — 53 단위 테스트가 mock transport 또는 respx route 사용, 실 KIS endpoint 호출 0건.
>
> **v1.0 Phase C — RealOrderExecutor 10-gate + dry-run vs real path 분기:**
>
> v0.16 Phase D 8-gate dry-run 전용 → v1.0 Phase C 10-gate + real path. 신규 gate 4
> (TRADING_SAFETY_DISABLED, v0.15 layer 명시 검증) + gate 10 (TRANSPORT_UNAVAILABLE,
> real path 진입 시 non-Fake transport 보장).
>
> ```text
> OrderCandidate (APPROVED) → RealOrderExecutor.execute(candidate_id, settings)
>   ① CANDIDATE_NOT_FOUND / NOT_APPROVED
>   ② DUPLICATE_REAL_ORDER (real) / ALREADY_EXECUTED (dry)  [exists_non_failed_for_candidate]
>   ③ KILL_SWITCH_ON
>   ④ TRADING_SAFETY_DISABLED                              [v1.0 신규]
>   ⑤ REAL_TRADING_DISABLED
>   ⑥ KIS_ORDER_DISABLED
>   ⑦ AMOUNT_EXCEEDS_PER_ORDER_CAP
>   ⑧ AMOUNT_EXCEEDS_DAILY_CAP                             [DB KST aggregate]
>   ⑨ RISK_REJECTED                                        [PreTradeRiskEngine]
>   → if real_order_dry_run=True:
>       FakeKisOrderTransport.place_order() → RealOrder(dry_run=True, status=DRY_RUN)
>   → if real_order_dry_run=False:
>       ⑩ TRANSPORT_UNAVAILABLE                            [v1.0 신규, _resolve_real_transport]
>       RealOrder(dry_run=False, status=CREATED) 선저장 + flush()  [DB anchor for RUNBOOK §5]
>       transport.place_order(KisOrderRequest)             [Phase B retry=0 보존]
>       _classify_place_message → 5 분류:
>         SUBMITTED → mark_submitted(broker_order_no_hash=sha256(order_no))
>                   + ApprovalAuditLog(REAL_ORDER_SUBMITTED, details whitelist 6 키)
>         REJECTED/TIMEOUT/NETWORK_ERROR/UNKNOWN
>                   → mark_failed(error_code=cls, error_message=_scrub(msg))
>                   + ApprovalAuditLog(REAL_ORDER_FAILED)
> ```
>
> Phase C는 `HttpxKisOrderTransport` 직접 import 0건 — transport 는 DI 만
> (`__init__(transport=, real_transport_factory=)`). 기본 생성자는 여전히 Fake-only로
> v0.16 회귀 0건. Phase D ApprovalService 가 실제 wiring (factory 주입 또는 명시 transport
> 주입). plaintext KIS order_no 어디에도 저장·로그 0건 — `broker_order_no_hash` SHA-256 64자
> 만 / audit details `broker_order_no_hash_prefix` 16자 만.
>
> **v1.0 Phase D — FillSyncService 델타 기반 idempotent 업데이트 + POST /sync API:**
>
> v0.16 Phase D mock-only FillSyncService → v1.0 Phase D delta-based idempotent + 6 분류 +
> audit. DRY_RUN RealOrder 는 transport 호출 0건으로 skip (실 KIS fake order_no 충돌 차단).
>
> ```text
> RealOrder (status=SUBMITTED) → FillSyncService.sync_fills(real_order_id, kis_order_no_plaintext?)
>   ① RealOrder 존재 검사
>   ② DRY_RUN skip (transport 호출 0건, NONE/DRY_RUN_ORDER_SKIPPED 반환)
>   ③ 터미널 status (FILLED/CANCELED/REJECTED/FAILED) skip
>   ④ transport.query_fill_status(plaintext or fake_order_no or pk)  [Phase B retry 정책 보존]
>      예외 raise → audit REAL_ORDER_FILL_FAILED + return FAILED
>   ⑤ _classify_fill_response → 6 분류:
>        FAILED  → audit REAL_ORDER_FILL_FAILED + return
>        REJECTED/CANCELED → status 전이 + audit REAL_ORDER_FILL_SYNCED + return
>        FULL/PARTIAL/NONE → 델타 계산:
>          existing_total = RealFillRepository.total_filled_quantity()
>          kis_total      = _effective_kis_total(classification, response, total_qty)
>          delta = kis_total - existing_total
>          delta < 0 → audit FILL_SYNC_NEGATIVE_DELTA + return FAILED
>          delta > 0 → RealFill(quantity=delta, ...) 1행 + status 전이 (FULL→FILLED, PARTIAL→PARTIALLY_FILLED)
>          delta == 0 → 신규 행 0건 (idempotent)
>          audit REAL_ORDER_FILL_SYNCED + return
> ```
>
> **POST /api/real-orders/{order_id}/sync — v1.0 의 SOLE RealOrder mutation 라우터.**
> AUTH + TRADING_SAFETY_ENABLED + KILL_SWITCH_OFF 3중 게이트 (v0.15 패턴). REAL_TRADING_ENABLED /
> KIS_ORDER_ENABLED 미강제 (사고 후 sync 가능 정책 — RUNBOOK §6 기준). 응답 `RealOrderSyncResponse`
> 7 필드 (real_order_id / real_order_status / fill_status / fills_added / fills_total / synced_at /
> message). plaintext kis_order_no 응답 echo 0건. PUT/PATCH/DELETE 405.
>
> **자동 polling scheduler job 0건** — Phase D 는 수동 트리거 only. 자동 폴링은 v1.1 (Reconciliation 과
> 함께). plaintext KIS order_no 정책: `sync_fills(kis_order_no_plaintext=...)` 옵션 파라미터로 운영자가
> in-memory 만 transport 에 전달, RealFill / RealOrder / audit / 응답 본문 어디에도 저장 0건.
>
> Phase B `HttpxKisOrderTransport` 는 독립 모듈로 존재하며 운영자가 `REAL_TRADING_ENABLED=true` +
> `KIS_ORDER_ENABLED=true` + `REAL_ORDER_DRY_RUN=false` 모두 명시 활성화 + Phase D ApprovalService
> wiring 후에만 실주문 path 도달 가능. Fill sync API 는 transport 만 wire 되면 (운영자가 명시 inject)
> 동작 — `REAL_TRADING_ENABLED` 와 무관.
>
> **Retry / Timeout 정책 (`HttpxKisOrderTransport`):**
>
> | 메서드 | timeout | retry | 사유 |
> |---|---|---|---|
> | `place_order` | 5s | **0** | 중복 주문 위험 — TIMEOUT/NETWORK_ERROR 발생 시 운영자 수동 매칭 |
> | `query_fill_status` | 10s | 최대 2 | idempotent — transient transport failure 만 재시도 |
> | `cancel_order` | 5s | 최대 2 | idempotent — KIS 가 이미 취소된 주문에 대해 business code 반환 |
>
> **응답 분류 (whitelist 필드만 — raw response 저장·반환 0건):**
>
> - `place_order` 5종: SUBMITTED / REJECTED / TIMEOUT / NETWORK_ERROR / UNKNOWN
> - `query_fill_status` 6종 (FULL / PARTIAL / NONE / REJECTED / CANCELED / UNKNOWN) →
>   `KisFillStatusResult.status` 5 KIS canonical (FILLED / PARTIALLY_FILLED / PENDING /
>   REJECTED / CANCELED) 매핑
> - `cancel_order` 5종: CANCELED / REJECTED / TIMEOUT / NETWORK_ERROR / UNKNOWN
>
> **마스킹 / 자격증명 정책:**
>
> `mask_sensitive_order_payload()` (v0.16) + `install_sensitive_qs_filter("httpx")` (v0.11) +
> `__repr__` / `as_dict()` 자격증명 미노출. caplog 단언으로 헤더가 KIS 서버에 도달은 성공하지만
> 로그 평문 노출 0건. account_no 는 `****<last4>` 형태만 노출. broker_order_no 는 result
> `order_no` 필드로 평문 반환 — 상위 계층 (Phase C executor) 이 SHA-256 해싱 후 `RealOrder.broker_order_no_hash` 로 저장.
>
> `KisHttpOrderTransport` (legacy 명명) 은 더 이상 미구현 표기 아님 — `HttpxKisOrderTransport` 가 그 역할.
> `broker_order_no_hash` = SHA-256 hex 만 저장 (KIS 주문번호 평문 저장 0건).
> httpx / requests / urllib import 0건 (AST 가드, executor + fill sync + real_order_routes 모두 +
> `kis_order_client.py` skeleton). `kis_order_transport_real.py` 만 lazy `httpx` import (1회, `__init__` 내부).
>
> **v0.15 Phase E** 가 추가한 프런트엔드:
> `frontend/src/api/approval.ts` (7 fetch) → `frontend/src/hooks/useApprovals.ts`
> (3 read + 4 mutation TanStack Query, mutation 후 approval/paper 두 namespace
> invalidate) → `frontend/src/pages/Approvals/index.tsx` (14번째 화면,
> `ApprovalsPage` / `PolicyBanner` / `PendingCandidatesTable` /
> `CandidateDetailDrawer` (`CandidateSummary` / `RiskCheckPanel` /
> `AuditTimeline`) / `NewCandidateForm` / `HistoryTable`) →
> `frontend/src/components/layout/Sidebar.tsx` 14번째 메뉴 (`ShieldCheck`,
> "승인 대기 (β)") → `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts`
> 23번째 e2e 시나리오 (raw payload forbidden 검사 + 503 disabled banner +
> automation CTA 0건 단언). 버튼 라벨은 "승인 (paper 실행)" / "거절" / "만료" /
> "후보 만들기 (Risk Check)" — "주문 실행" / "place real order" / FULL_AUTO /
> SMALL_AUTO / "자동매매" actionable CTA 0건. 503 응답은
> `approvals-disabled-banner` (general) / `approvals-kill-switch-banner`
> (`detail` 에 "kill switch" 포함 시) 친절 안내.
>
> 본 문서는 **v0.15 Phase D 시점** 기준으로 갱신된다 (`v0.15-approval-api`
> 태그 예정). v0.15 Approval Trading Safety Layer 가 Phase A → D 까지
> 진행되어, **OrderCandidate** (Phase B) → **PreTradeRiskEngine** (Phase C)
> → **ApprovalService + ApprovalAuditLog + Approval API + expire 잡** (Phase
> D) 의 종단 워크플로우가 완성되었다.
>
> **ApprovalService (`app/approval/approval_service.py`)** 는 OrderCandidate
> 8-state 머신 + PreTradeRiskEngine + ApprovalAuditLog (append-only) +
> `SimulationBroker.submit_order` (paper execution only) 를 결합한다.
> mutation API 7종 중 4건 (`POST /api/approvals/candidates` / `/approve` /
> `/reject` / `/expire`) 이 **3중 게이트** (`TRADING_SAFETY_ENABLED` +
> `KILL_SWITCH_ENABLED=False` + `require_auth`) 를 거친다. expire 라우터만
> kill_switch 무관 — TTL 만료는 운영자 안전 가드와 분리된다 (만료가
> 막히면 후보가 무한 누적). 승인된 후보는 `SimulationBroker.submit_order`
> 만 호출 (실 KIS / 실 broker 호출 0건, AST 회귀 단언). audit 의 8 event
> type (`CREATED / RISK_CHECKED / RISK_REJECTED / APPROVED / REJECTED /
> EXPIRED / EXECUTED_PAPER / KILL_SWITCH_BLOCKED`) 이 모든 state 전이를
> 영속 기록하며, 평문 IP / user-agent 는 SHA256 해시만 저장 (v0.8
> LoginAuditLog 정책 승계).
>
> 12번째 스케줄러 잡 `expire_pending_approvals` 는 `IntervalTrigger` 5분
> 주기 (Phase D 신규 `DEFAULT_INTERVAL_SCHEDULE`). 안전 게이트 OFF / 킬
> 스위치 ON 시 SKIPPED. mutation 라우터는 11 → 15건 (+approval 4); 실 KIS
> / FULL_AUTO / SMALL_AUTO 라우터는 여전히 **0건**. 14번째 프런트 화면
> `/approvals` 는 후속 phase E 책임. 실 KIS 주문 / 자동매매 / FULL_AUTO /
> SMALL_AUTO / APPROVAL 실거래 코드 0건은 v0.1 ~ v0.15 일관 정책으로 유지된다.
>
> 본 문서는 **v0.15 Phase C 시점** 기준으로 갱신된다 (`v0.15-pre-trade-risk`
> 태그 예정). v0.14 paper 시뮬레이션 위에, v0.15 의 Approval Trading Safety
> Layer 가 Phase A (SafetySettings 7종 + KillSwitch paranoid default) →
> Phase B (`OrderCandidate` 38번째 테이블 + 8-state 머신 + Alembic 0007) →
> Phase C (`PreTradeRiskEngine` 7 HARD 룰 + `RiskCheckResult` JSON-safe
> dataclass) 까지 진행되었다.
>
> **PreTradeRiskEngine (`app/risk/pre_trade_risk_engine.py`)**: read-only —
> DB write 0건. `evaluate(session, candidate, *, now=None)` 가 7 룰을
> 단락 회피 없이 모두 누적해 `RiskCheckResult(policy_version="pre-trade-v1",
> passed, violations, checked_at)` 를 돌려준다. 7 HARD 룰:
> ① **account_paper_enabled** — VirtualAccount.paper_trading_enabled=True 강제,
> ② **kill_switch_off** — `Settings.kill_switch_enabled=False` 명시 opt-out 필요,
> ③ **per_symbol_limit** — (account, symbol) 활성 후보 합 + 신규 ≤
> `max_order_amount`, ④ **daily_total_limit** — KST 오늘 활성 후보 합 + 신규 ≤
> `max_daily_order_amount`, ⑤ **position_ratio_limit** — BUY 시 (기존 포지션
> 시장가치 + estimated) / 총평가액 ≤ `max_position_ratio`, ⑥ **daily_loss_limit**
> — 최신 `VirtualPnLSnapshot.realized_pnl` ≥ `-max_daily_loss_amount`,
> ⑦ **duplicate_recent** — 최근 5분 내 동일 (account, symbol, side, quantity)
> 활성 후보 부재. 활성 정의 `ACTIVE_CANDIDATE_STATUSES = {DRAFT, RISK_CHECKING,
> PENDING_APPROVAL, APPROVED}` — terminal 4종 (RISK_REJECTED / REJECTED /
> EXPIRED / EXECUTED_PAPER) 은 누적 / duplicate 에서 제외되어 historical reject 가
> 신규 시도를 막지 않는다.
>
> **데이터 소스**: 모든 룰이 로컬 DB read 만 — `VirtualAccount` /
> `VirtualPosition` × `daily_prices.close` 폴백 / `VirtualPnLSnapshot.total_value`
> 우선 (snapshot 부재 시 cash_balance fallback) / `OrderCandidate` 활성 행. AST
> 회귀 단언이 KIS / DART / RSS / requests / httpx / urllib import 0건을 강제.
>
> **Phase D / E 책임**: ApprovalService 가 `engine.evaluate(...).to_dict()` 의
> 결과를 `OrderCandidateRepository.attach_risk_result(...)` 로 영속하고
> RISK_REJECTED ↔ PENDING_APPROVAL 상태 전이를 결정한다. ApprovalAuditLog +
> Approval API 7종 (Phase D) + 14번째 프런트 화면 `/approvals` (Phase E) 는 후속.
> 실 KIS 주문 / 자동매매 / FULL_AUTO / SMALL_AUTO / APPROVAL 실거래 코드 0건은
> v0.1 ~ v0.15 일관 정책으로 유지된다.
>
> 본 문서는 **v0.14 마감 시점** 기준으로 갱신된다 (마감 태그 `v0.14-final`).
> v0.14 5 Phase (Backtest Export CLI + ProviderScorePolicy 통합 → SimulationBroker +
> VirtualAccount/VirtualOrder + Alembic 0005 → VirtualPosition + VirtualFill +
> VirtualPnLSnapshot + PnLTracker + execute_pending_orders + Alembic 0006 →
> Paper Trading API 6 라우터 + 스케줄러 잡 2건 → 13번째 프런트 화면 `/paper`)
> 모두 마감. 누적 게이트: backend pytest **1438** / frontend vitest **186** /
> Playwright e2e **22** / build 그린.
>
> **v0.14 Phase E** 가 추가한 프런트엔드:
> `frontend/src/api/paper.ts` (6 fetch) → `frontend/src/hooks/usePaperTrading.ts`
> (4 read + 2 mutation TanStack Query) → `frontend/src/pages/PaperTrading/index.tsx`
> (13번째 화면, 5 컴포넌트 + 정책 배너 + 503 disabled 안내) →
> `frontend/src/components/layout/Sidebar.tsx` 13번째 메뉴 (`LineChart`,
> "페이퍼 트레이딩 (β)") → `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts`
> 22번째 e2e 시나리오 (raw payload forbidden 검사 + disabled banner). 버튼 라벨은
> "페이퍼 주문 만들기" — "주문 실행" / "place order" 같은 actionable CTA 0건.
> 응답 / DOM forbidden 필드 12종 (api_key / token / secret / source_file_path /
> broker_order_id / kis_order_id / real_account / broker / account_number /
> raw_text / body / full_text) 0건 단언.
>
> 본 문서는 **v0.14 Phase D 시점** 기준으로 갱신된다 (`v0.14-paper-api`
> 태그 예정). Phase C 의 PnL & Fill 엔진 위에, **Phase D** 가 Paper Trading
> API 6 라우터 (`/api/paper/account` / `/orders` / `/positions` / `/pnl`
> GET 4종 + `POST /orders` + `DELETE /orders/{id}`) + 스케줄러 잡 2건
> (`execute_paper_orders` 16:00 KST + `create_paper_pnl_snapshot` 16:30 KST)
> 을 추가했다. mutation 라우터는 `Settings.paper_trading_enabled=true` +
> `require_auth` 필요, disabled 시 503 응답. 스케줄러 잡은 default OFF →
> SKIPPED. 응답 forbidden 필드 12종 (api_key / token / secret /
> source_file_path / broker_order_id / kis_order_id / real_account / broker /
> account_number / raw_text / body / full_text) 0건 단언. paper_routes.py
> AST 검사로 KIS / DART / RSS / requests / httpx / urllib import 0건. 프런트
> 화면은 Phase E 책임. 실 KIS 주문 / 자동매매 / FULL_AUTO / SMALL_AUTO /
> APPROVAL 코드 0건은 그대로 유지된다.
>
> 본 문서는 **v0.14 Phase C 시점** 기준으로 갱신된다 (`v0.14-pnl-tracker`
> 태그 예정). Phase B 의 SimulationBroker / VirtualAccount / VirtualOrder
> 위에, **Phase C** 가 paper / simulation 트레이딩의 PnL & Fill 엔진을
> 추가했다 — `app/db/models.py` `VirtualPosition` (35) + `VirtualFill` (36)
> + `VirtualPnLSnapshot` (37), `alembic/versions/0006_virtual_positions.py`,
> `app/data/repositories/virtual_position.py` + `virtual_fill.py` +
> `virtual_pnl_snapshot.py`, `app/paper/pnl_tracker.py` (`PnLTracker`),
> `app/backtest/cost_model.py` 의 `PaperTradingCostModel` (paper-v1, 기존
> CostModel constant-v1 변경 0건), `app/broker/simulation_broker.py`
> 의 `execute_pending_orders()` 본 구현 (daily_prices.close 기준 매칭,
> MARKET 즉시 체결 / LIMIT crossing / no-price skip / cash·position 부족 →
> REJECTED / terminal idempotent skip). Paper Trading API 라우터 / 프런트
> 화면은 Phase D/E 책임. 실 KIS 주문 / 자동매매 / FULL_AUTO / SMALL_AUTO /
> APPROVAL 코드 0건은 그대로 유지된다.
>
> 본 문서는 **v0.14 Phase B 시점** 기준으로 갱신된다 (`v0.14-sim-broker` 태그
> 예정). v0.14 Phase A 의 Backtest Export CLI + ProviderScorePolicy producer
> 통합 위에, **Phase B** 가 paper / simulation 트레이딩 코어를 도입했다 —
> `app/broker/simulation_broker.py` `SimulationBroker` (`BrokerInterface` 첫
> 구현체, KIS / DART / RSS / requests / httpx import 0건),
> `app/db/models.py` `VirtualAccount` (33번째) + `VirtualOrder` (34번째),
> `alembic/versions/0005_virtual_trading_core.py`,
> `app/data/repositories/virtual_account.py` + `virtual_order.py`,
> `Settings.paper_trading_enabled=False` (default OFF). Paper Trading API
> 라우터 / 프런트 화면 / VirtualPosition / VirtualFill / VirtualPnLSnapshot /
> PnLTracker / `execute_pending_orders` 체결 로직은 모두 Phase C/D/E 책임.
> 실 KIS 주문 / 자동매매 / FULL_AUTO / SMALL_AUTO / APPROVAL 코드 0건은
> 그대로 유지된다.
>
> 본 문서는 **v0.13 마감 시점** 기준으로 갱신된다 (마감 태그 `v0.13-final`).
> **v0.13 Phase A** — `app/scoring/provider_policy.py` 신규: `ProviderScorePolicy` +
> `DATA_SOURCE_RELIABILITY` (PROVIDER=1.00 / CSV=0.90 / MANUAL=0.80) + `_BYPASS_SOURCES={"FAKE"}`.
> `settings.provider_score_policy_enabled=False` (default OFF). ScoringEngine weight 변경 0건.
> **v0.13 Phase B** — `app/scoring/score_delta.py` 신규: `ScoreDeltaResult` + `ComponentDelta` +
> `compute_score_delta()`. `RecommendationEngine` / `HoldingCheckEngine` 에 `score_policy` 선택
> 파라미터 추가 — None 이면 delta 미기록, ProviderScorePolicy 전달 시 `market_context_json`의
> `score_delta` 키에 기록. `app/api/routes.py` `_SCORE_DELTA_EVIDENCE_FIELDS` whitelist 추가.
> Alembic revision 0건 — 기존 `evidence_json` JSON 컬럼 재활용.
> **v0.13 Phase C** — `app/api/validation_routes.py` 신규 (prefix `/api/validation`):
> `GET /report` / `GET /report/by-strategy` / `GET /report/by-regime` / `GET /report/by-sector`.
> `app/api/schemas.py` 8종 추가 (`ScoreDeltaSummarySchema` + 7개 Validation 스키마).
> score_delta 집계: `backtest_results.evidence_json["score_delta"]` whitelist 읽기 —
> raw 노출 없음, malformed 자동 skip. sector 집계는 Stock LEFT JOIN으로 처리.
> **v0.13 Phase D** — 프런트 12번째 화면 `/validation`: `ValidationPage` + `ScoreDeltaCard` +
> 전략·국면·섹터 표 + data_source chip. `ClipboardCheck` sidebar 아이콘.
> `useValidationReport` / `useValidationByStrategy` / `useValidationByRegime` / `useValidationBySector`
> TanStack Query hooks (`staleTime: 60_000`). Backtest Export CLI 는 v0.14+ 이연.
> 최종 게이트(v0.13-final): pytest **1277** / vitest **175** / e2e **21** / build 그린.
>
> 본 문서는 **v0.12 마감 시점** 기준으로 갱신된다 (마감 태그 `v0.12-final`).
> v0.12 는 v0.11 위에 다음 4개 Phase 를 추가했다:
> **Phase A** — `app/data/ingestion.py` 4 어댑터 (default OFF,
> `PROVIDER_DATA_INGESTION_ENABLED=false`), 4 DTO `data_source` provenance,
> evidence 빌더 `data_source` 허용, Alembic revision 0건.
> **Phase B** — `app/backtest/walk_forward.py` (`WalkForwardBacktestEngine` +
> `generate_folds()`, IS/OOS fold sliding, `summary_json["walk_forward_folds"]`).
> **Phase C** — `app/backtest/multi_strategy_runner.py` (`MultiStrategyRunner` +
> `StrategyResult`) + `app/backtest/regime_breakdown.py` (`SectorBreakdownEntry` +
> `aggregate_sector_breakdown()`), `summary_json["multi_strategy_comparison"]`.
> **Phase D** — `GET /api/backtest/runs/{id}/folds` + `/comparison` (read-only,
> mutation 405), 5 Pydantic 스키마, `useBacktestFolds` / `useBacktestComparison`
> hooks, Backtest UI fold/comparison 표 + `data_source` chip.
> ScoringEngine / HoldingCheckEngine 본 weight 변경 0건. Alembic 신규 revision 0건.
> 최종 게이트: pytest 1194 / vitest 165 / e2e 21 / build 그린.
>
> 본 문서는 **v0.11 마감 시점** 기준으로 갱신된다 (마감 태그 `v0.11-final`).
> v0.1 Backend → v0.2 Frontend → v0.3 Analysis/Ops → v0.4 Analyst & Theme Intelligence →
> v0.5 News·공시·테마 랭킹 → v0.6 Fundamental & Earnings Intelligence →
> v0.7 Strategy & Backtest Foundation → v0.8 User & Migration Foundation →
> v0.9 Operational Security & Watchlist Polish →
> v0.10 Real Provider Readiness & Resilience →
> **v0.11 Real Provider Transport & Observability** (Phase A~D) 이 모두 누적된
> 상태의 시스템 구조를 반영한다.
> v0.10 의 `app/data/provider_health_monitor.py` + `dart_provider.py` (skeleton)
> + `rss_provider.py` (skeleton) + `app/api/health_routes.py` 위에, v0.11 은
> 다음을 추가했다 — `HttpxDartTransport` / `HttpxRssTransport` (lazy httpx
> import + factory 자동 주입, default OFF) + `app/config/logging.py` 의 공유
> `SensitiveQueryStringFilter` (DART/RSS 양쪽 transport 마스킹) + `ProviderStats`
> bounded ring buffer + `Summary24h` + `app/monitoring/prometheus.py`
> (`prometheus-client` based exporter, default OFF) + `app/api/metrics_routes.py`
> (`GET /metrics` 404 default) + `/api/health/providers` 6 신규 필드 + Settings
> `SuccessRateBar` / `RecentFailuresList`. **신규 Alembic revision 0건** —
> head 그대로 `0004_user_preferences`, observability 모두 in-memory bounded.

## 1. 핵심 흐름

이 프로젝트는 **read-only 분석·추천·보유점검 + 외부 신호 (휴장 캘린더 / 증권사
리포트 / 테마 매핑) 통합 + read-only 대시보드** 구조다. 자동매매 / 실 주문 /
POST 트리거 / FULL_AUTO / APPROVAL / SMALL_AUTO 는 **모든 사이클에서 코드
일체 포함하지 않는다** (`BrokerInterface` 는 ABC placeholder 만 유지).

```text
External Inputs                    Read-only Pipelines                Surfaces
─────────────────                  ───────────────────                ────────
KIS API (read)        ┐
                      ├─→ Data Collection ─→ Repository ─→ Analysis ─→ Scoring ─→ Recommendation / Holding Check ─→ Risk Gate ─→ Notification (DRY_RUN) + Dashboard API + PC Dashboard SPA
KRX 휴장일 (정적 JSON) ┘
                                              ↑
                              ┌───────────────┴────────────┐
Operator CSV (manual) ─→ Report Intelligence Layer ─→ Consensus Snapshot ─→ (Phase C+) Recommendation 보조 점수 ±5
```

향후 자동매매 흐름 (현재 어떤 사이클에도 미구현):

```text
Strategy Signal → AI Judgement → RiskEngine → BrokerInterface → TradeLogger
```

이 흐름은 v0.5+ 의 별도 보안 / 컴플라이언스 사이클이 선행되어야 진입 가능하다.
v0.1~v0.4 어디에도 활성화된 코드가 없다.

## 2. 레이어 구조 (v0.9 마감 기준)

```text
app/
├─ config/                  # Settings, .env 매핑, KIS / Telegram 마스킹
├─ middleware/               # v0.9 Phase A/B — SecurityHeadersMiddleware / RequestIDMiddleware / rate_limit (slowapi)
├─ auth/                    # JWT 발급·검증 (v0.8) + BruteForceGuard (v0.9 Phase A)
├─ config/                  # Settings (.env 매핑) + logging.py (SensitiveFilter / RequestIDFilter, v0.9 Phase B)
├─ monitoring/              # sentry.py optional init (v0.9 Phase B, SENTRY_ENABLED=false 기본)
├─ db/                      # SQLAlchemy 2.0 Base / 39 ORM 모델 (v0.1 17 + v0.4 6 + v0.6 2 + v0.7 2 + v0.8 4 + v0.9 1 + v0.14 5 + v0.15 2)
├─ data/
│  ├─ collectors/           # KIS read-only HTTP / DailyPriceCollector / MarketCapCollector / Fake provider
│  ├─ importers/            # operator CSV / Excel import (analyst reports, themes, mappings, signal events)
│  ├─ normalizers/          # KIS raw → DTO
│  ├─ validators/           # DataQualityChecker
│  ├─ provider_resilience.py # v0.9 Phase C — ProviderCallResult / retry_with_backoff / CircuitBreaker skeleton
│  ├─ provider_health_monitor.py # v0.10 Phase A — ProviderHealthMonitor + call_with_resilience() (registry + retry + breaker + failure isolation)
│  ├─ dart_provider.py      # v0.10 Phase B — DART OpenAPI provider skeleton (DartFundamental/Earnings/Disclosure, DART_ENABLED=false 기본, transport 주입형, parser/mapper, body 필드 strip)
│  ├─ rss_provider.py       # v0.10 Phase C — RssNewsProvider (RSS 2.0 + Atom, RSS_NEWS_ENABLED=false 기본, transport 주입형, body 필드 strip + URL dedup + URL query secret 마스킹, stdlib xml.etree only)
│  └─ repositories/         # 28 Repository (v0.1 16 + v0.4 6 + v0.6 2 + v0.8 3 + v0.9 1)
├─ analysis/                # TechnicalAnalyzer, IndicatorService, candle/ATR/volatility (v0.3 Phase B)
├─ decision/                # ScoringEngine, RecommendationEngine, HoldingCheckEngine, RiskEngine, score producers
├─ notification/            # ReportGenerator, TelegramNotifier (DRY_RUN), Dispatchers
├─ api/                     # FastAPI routers (23+ GET + 5 auth/watchlist POST/DELETE v0.8 + 6 watchlist/pref PATCH/PUT v0.9)
├─ scheduler/               # APScheduler + run_job wrapper + 9 jobs
├─ broker/                  # v0.14 Phase B — SimulationBroker (BrokerInterface 첫 구현체, paper trading 전용 / KIS API 0건). v0.14 Phase C 가 execute_pending_orders 본 구현 추가. 실 KIS / 자동매매 broker 는 여전히 placeholder
├─ paper/                   # v0.14 Phase C — PnLTracker (paper trading 전용 PnL / fill 엔진, daily_prices.close 기준 가격, 외부 호출 0건)
├─ risk/                    # v0.15 Phase C — PreTradeRiskEngine (7 HARD 룰, read-only DB read, RiskCheckResult JSON-safe). policy_version="pre-trade-v1". KIS / DART / RSS / requests / httpx import 0건
└─ approval/                # v0.15 Phase D — ApprovalService workflow orchestrator (OrderCandidate 8-state + PreTradeRiskEngine + ApprovalAuditLog append-only + SimulationBroker.submit_order paper only). 3중 게이트 (trading_safety + kill_switch + AUTH). 실 KIS 호출 0건 (AST 단언)

frontend/                   # v0.2 Vite/React/TS PC 대시보드 + v0.3~v0.14 누적
├─ src/
│  ├─ pages/                # 13 화면 + Login (Today/Recommendations/History/Holdings/StockDetail/MarketCap/Jobs/Settings/Themes/Backtest/Watchlist/Validation/PaperTrading + /login)
│  ├─ components/common/    # MarketStatusBanner, TrendLineChart, RiskBadge, GradePill, ErrorBoundary (v0.9), …
│  ├─ data/                 # KRX 휴장일 정적 JSON (2025–2027)
│  ├─ lib/                  # marketCalendar 등 read-only 유틸
│  ├─ hooks/                # useStockDetail, useStockPriceSeries, useWatchlists, useUserPreferences (v0.9), …
│  ├─ api/                  # apiFetch / apiPost / apiPatch / apiPut / apiDelete + 타입 (hand-written)
│  └─ tests/                # vitest + msw v2 (146 passed)
├─ e2e/                     # Playwright + page.route mock (19 passed)

scripts/                    # 운영자 CLI
├─ seed_mock_data.py        # v0.1 — mock seed 적재
└─ (v0.4 Phase B) import_analyst_reports.py — CSV/Excel 수동 import (예정)

.github/workflows/          # v0.3 Phase A — CI 3 job (backend pytest / frontend vitest+build / e2e)
```

## 3. 계층별 책임

### 3.1 Data Layer

외부 read-only 입력의 정규화 + 저장. KIS API, KRX 휴장일 정적 JSON, 운영자 CSV
import 가 모두 여기를 통과한다. **추천 판단을 하지 않는다.**

- `data/collectors/` — KIS HTTP 클라이언트 + 일봉 / 시총 collector + Fake provider
- `data/importers/` (v0.4) — 운영자 CSV → analyst_reports / report_themes /
  theme_stock_mappings / report_signal_events. **자동 크롤링 / 스크레이핑 0건**.
  PDF 본문 / paragraph 저장 금지. `source_file_path` 는 DB 에 저장되지만 API 응답
  / 프런트 어디에도 노출되지 않는다.
- `data/normalizers/`, `data/validators/` — KIS raw → DTO 변환 + 품질 검사

### 3.2 Repository Layer

ORM 모델 + 단순 CRUD / upsert. 로직 0. 22 Repository 가 단일 export 면 (`app.data.repositories`)
에서 노출된다.

### 3.3 Analysis Layer

저장된 데이터를 지표 / 패턴 / 변동성 분류로 변환.

- v0.1 — MA5/20/60/120, RSI14, MACD, 거래량 비율, breakout, ma_alignment, technical_score
- v0.3 Phase B — 캔들 패턴 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING /
  BEARISH_ENGULFING), Wilder ATR(14), 4단계 변동성 분류 (LOW / NORMAL / HIGH /
  EXTREME). `technical_score` 에 ±5점 cap 보조 가산.
- v0.4 Phase C (예정) — `report_score_calculator` (기업 리포트 + 테마·시그널
  기반 보조 점수)

**외부 API 호출 / 주문 0건.**

### 3.4 Report Intelligence Layer (v0.4)

증권사 애널리스트 리포트 메타데이터 + 추출된 투자 테마 + 테마→종목 매핑 +
변화 시그널 이벤트를 통합. 6 ORM + 6 Repository 가 핵심.

```text
analyst_reports (1) ──┬── (N) report_themes ──┬── (N) theme_stock_mappings
                      │                       │
                      └── (N) report_signal_events ──── (theme_id nullable FK)

report_consensus_snapshots          (per-symbol per-window 일별 집계)
report_score_logs                   (report_score + theme_signal_score 계산 이력)
```

- 7 report_type (COMPANY / SECTOR / INDUSTRY / THEME / COMMODITY / MACRO / STRATEGY)
  을 단일 테이블로 통합 — `symbol` nullable 로 매크로·테마·원자재 리포트 지원.
- 글로벌 종목 (US / NASDAQ / USD) 동일 테이블 저장 (market / exchange / country
  / currency / broker_country 컬럼).
- `extraction_method` (MANUAL / CSV_IMPORT / RULE_BASED / LLM_ASSISTED) 로 데이터
  출처를 태깅 — 미래에 LLM 자동 요약을 붙일 수 있도록 설계되었으나 v0.4 Phase
  A 에서는 미구현.
- **저작권 정책**: 원문 본문 / paragraph 저장 0건, PDF BLOB 0건, 자동 크롤링 0건,
  외부 공유 / 공개 API 0건.

### 3.5 Scoring / Decision Layer

- `ScoringEngine` — 신규 추천 (technical 35% + news 25% + supply 15% + fundamental
  15% + ai 10% - risk_penalty) / 보유 (technical 35% + news 20% + earnings 20% +
  ai 15% + profit_management 10% - risk_penalty)
- `RecommendationEngine`, `HoldingCheckEngine` — 후보 생성 + risk gate +
  snapshot/log 저장. 외부 API 호출 0건.
- `RiskEngine` — risk_penalty / risk_level / risk_flags. **모든 미래 자동매매의
  최종 게이트** (현재는 추천·보유 점검의 risk 라벨만 채움).
- v0.4 Phase C (예정): `report_score` + `theme_signal_score` 를 각 ±5점 cap 보조
  가산 (총 ±10점). **본 weight 산식은 손대지 않는다.**

### 3.6 Notification Layer

리포트 텍스트 생성 + 텔레그램 발송 + 알림 로그.

- 기본 `DRY_RUN` (`TELEGRAM_ENABLED=false`).
- 3 dispatcher (`RecommendationReportDispatcher`, `HoldingCheckReportDispatcher`,
  `HoldingRiskAlertDispatcher`) 가 잡과 연결되어 `notification_logs.related_job_id`
  를 자동 채운다.
- **추천 로직 / 점수 산식을 변경하지 않는다.**

### 3.7 API Layer (Backend, v0.1 ~ v0.3)

PC 대시보드용 read-only GET 라우터만 제공. **POST / PUT / DELETE 0건** —
v0.1~v0.4 일관 정책.

- v0.1: 13개 read-only GET (`/api/reports/today`, `/api/recommendations`, `/api/holdings/checks/latest`, `/api/stocks/{symbol}`, `/api/jobs`, `/api/settings`, …)
- v0.3 Phase D: `GET /api/stocks/{symbol}/prices?days=120` 추가 (일봉 차트 시계열)
- v0.4 Phase D (예정): `GET /api/stocks/{symbol}/reports` 신규 — 리포트 / 컨센서스 /
  최근 시그널 (read-only). `source_file_path` 는 schema 에서 마스킹.

라우터는 collector / 지표 계산 / 추천 생성을 직접 하지 않는다 — Repository 와
Pydantic schema 만 사용한다.

### 3.8 Frontend Layer (v0.2 ~ v0.9)

Vite + React + TypeScript 5.5 + Tailwind + TanStack Query/Table + Recharts. 11 화면
+ Login. Watchlist·UserPreference 도메인에 한해 POST/PATCH/DELETE 소비.
자동매매 form / submit / CTA 0건 — e2e 가 명시적으로 검증.

- v0.2 — 8 화면 MVP + 코드 스플릿 + Docker
- v0.3 — KRX 휴장일 캘린더 + `MarketStatusBanner` + StockDetail 일봉 차트
- v0.4 — StockDetail 리포트·테마·시그널 4 카드 + Recommendations score 컬럼
- v0.5 — 테마 랭킹 9번째 화면 + Recommendations evidence 컬럼
- v0.6 — StockDetail Fundamentals/Earnings 카드 + Today UpcomingEarnings + evidence
- v0.7 — 백테스트 10번째 화면 (전략 카드 + run 표 + detail 패널)
- v0.8 — Watchlist 11번째 화면 + `/login` + StockDetail `FavoriteButton` + Today `WatchlistCard`
- v0.9 — Watchlist 인라인 관리 UI (rename/delete/set-default/memo/filter) + Settings `UserPreference` 섹션 + `useEffectiveDefaultWatchlistId` preference priority + `ErrorBoundary`

### 3.9 Scheduler Layer

APScheduler + `run_job` wrapper. 6 개 잡이 매일 자동 실행되며 모두 `job_runs`
테이블에 audit 기록을 남긴다.

| 잡 | 시간 (KST) | 역할 |
|---|---|---|
| `collect_market_close_data` | 18:00 | 시총 + 일봉 수집 |
| `calculate_technical_indicators` | 18:30 | 지표 일괄 계산 (캔들 / ATR 포함, v0.3 Phase B+) |
| `send_recommendation_report` | 06:00 | 텔레그램 추천 발송 (DRY_RUN 기본) |
| `run_pre_market_holding_check` | 08:30 | 장전 보유 점검 |
| `run_post_market_holding_check` | 16:30 | 장후 보유 점검 |
| `update_recommendation_results` | 17:00 | 1/3/5/20일 후 성과 갱신 |
| `update_report_consensus_snapshots` (예정, v0.4 Phase B) | 06:30 | 리포트 컨센서스 일별 집계 |

부분 실패가 전체 시스템을 멈추지 않는다 (PARTIAL / NO_DATA 분기).

### 3.10 Ops / CI Layer (v0.3 Phase A)

`.github/workflows/ci.yml` — main / PR 양쪽에서 자동 실행되는 3 잡:

- `backend / pytest` — Python 3.12 + `pip install -e ".[dev]"` + `pytest -q`
- `frontend / vitest + build` — Node 20 + `npm ci` + `npm run test` + `npm run build`
- `frontend / playwright e2e` — `playwright install chromium` + `npm run e2e`,
  실패 시 `playwright-report/` artifact 업로드

CI 환경 변수는 모두 mock / dry-run (KIS_USE_PAPER=true, TELEGRAM_ENABLED=false,
FEATURE_REAL_ORDER_EXECUTION=false 등). 실 자격증명 / 실 KIS / 실 Telegram 호출
0건.

`Docker` (v0.2): backend (`uvicorn`) + nginx (frontend SPA + `/api` proxy) +
postgres compose. `web` 컨테이너가 `/api` / `/health` 를 `backend:8000` 으로
proxy.

### 3.11 Security Middleware Layer (v0.9 Phase A)

v0.9 Phase A 에서 신규 도입된 `app/middleware/` 패키지와 `app/auth/brute_force.py`.
모든 HTTP 응답 경로에 보안 레이어를 삽입하며, DB 스키마 변경 0건.

```text
HTTP Request
    │
    ▼
SecurityHeadersMiddleware  (outermost — 모든 응답에 4개 헤더 주입)
    │  X-Content-Type-Options: nosniff
    │  X-Frame-Options: DENY
    │  Referrer-Policy: no-referrer
    │  Permissions-Policy: camera=(), microphone=(), geolocation=()
    │  (app.state.security_headers_enabled=True 시 활성)
    ▼
SlowAPIMiddleware           (slowapi 0.1.9)
    │  key = client IP  (rate_limit_enabled=True 시)
    │  key = __exempt_{uuid} (rate_limit_enabled=False — test 모드)
    │  login 기본 5/min, 기타 100/min
    │  초과 시 429 Too Many Requests
    ▼
BruteForceGuard            (app/auth/brute_force.py — auth_routes 에서 pre-check)
    │  key = SHA256(username:ip_hash) — composite key
    │  max_failures=5, window=300s, lockout=900s (설정 가능)
    │  잠금 시 LOCKOUT_REJECTED audit 기록 후 generic 401
    │  성공 시 카운터 초기화
    ▼
Route Handlers             (실제 비즈니스 로직)
```

**설계 원칙:**
- `app.state.{flag}` 런타임 토글로 테스트 스위트에서 autouse fixture 가 전체 비활성화
- CSP 는 Vite 개발 서버 / nginx 프록시와 충돌 우려로 Phase D+ 예정 (현재 미주입)
- 브루트포스 상태는 프로세스 인메모리 전용 — Alembic revision 불필요
- `EVENT_LOCKOUT_REJECTED` 는 `login_audit_logs.event_type` VARCHAR 에 새 값 추가 (no migration)

### 3.12 Observability Layer (v0.9 Phase B)

`app/config/logging.py` / `app/middleware/request_id.py` / `app/monitoring/sentry.py` 신규.
DB 스키마 / Alembic revision / API 라우터 변경 0건.

```text
Inbound Request
    │
    ▼
SecurityHeadersMiddleware  (outermost — Phase A)
    │
    ▼
RequestIDMiddleware        (Phase B 신규)
    │  X-Request-ID: 있으면 보존 / 없으면 UUID4 생성
    │  request.state.request_id 설정
    │  request_id_var (ContextVar) 설정 → 모든 로그에 자동 포함
    │  응답 헤더에 X-Request-ID 추가
    ▼
SlowAPIMiddleware           (Phase A)
    │
    ▼
Route Handlers + Exception Handler
    │  전역 Exception handler: generic 500 + request_id 응답 포함
    │  stack trace → 로그 only (API 응답에 미노출)
    ▼
configure_logging()         (startup; app/config/logging.py)
    │  structured_logging_enabled=False → text format (기본)
    │  structured_logging_enabled=True  → pythonjsonlogger JSON
    │  SensitiveFilter   — password/token/secret 계열 extra 필드 마스킹
    │  RequestIDFilter   — 모든 로그 레코드에 request_id 주입
    ▼
Optional Sentry             (app/monitoring/sentry.py)
    │  sentry_enabled=False (기본) — 완전 no-op
    │  sentry_enabled=True + DSN 있음 → sentry_sdk.init (send_default_pii=False)
    │  before_send hook — password / token / Authorization 헤더 마스킹 후 전송
    │  sentry_enabled=True + DSN 없음 → WARNING 로그 후 skip (startup 차단 없음)
```

**비밀값 미노출 정책 (Phase B):**
- 로그: `SensitiveFilter` 가 extra 키 이름 기반 redact
- Sentry: `before_send` 가 extra / request.data / request.headers 스캔 후 redact
- API 500 응답: `{"detail": "internal server error", "request_id": "..."}` — stack trace 미포함
- frontend: `ErrorBoundary.componentDidCatch` → `console.error` only, 외부 전송 없음

### 3.13 Watchlist Polish + UserPreference + Provider Resilience (v0.9 Phase C)

**Watchlist API 고도화 (`app/api/watchlist_routes.py`):**
- `PATCH /api/watchlists/{id}` — name 변경 / is_default 토글
- `DELETE /api/watchlists/{id}` — cascade delete (items 포함)
- `GET /api/watchlists/{id}/items` — limit / offset / symbol_prefix 필터
- `PATCH /api/watchlists/{id}/items/{symbol}` — memo 수정

**UserPreference (`app/db/models.py`, `app/data/repositories/user_preferences.py`, `app/api/preferences_routes.py`):**
- 32번째 테이블 `user_preferences` — user당 1행 (UNIQUE user_id)
- `default_watchlist_id` nullable FK → watchlists.id (ON DELETE SET NULL)
- `dashboard_layout_json`, `notification_preferences_json` — 저장 전용, 실제 발송 없음
- `GET /api/users/me/preferences` — lazy-create 후 반환
- `PUT /api/users/me/preferences` — 전체 교체; watchlist 소유권 검증
- `user_id`는 request body에서 받지 않음 (토큰 / dev fallback 기반)

**Provider Resilience (`app/data/provider_resilience.py`):**
```text
ProviderCallResult        — 성공/실패 래퍼 (value / error_kind / error_message / attempts)
ProviderErrorKind         — TIMEOUT / RATE_LIMIT / SERVER_ERROR / CLIENT_ERROR / UNKNOWN
retry_with_backoff()      — 최대 N회 + 지수 백오프 (CLIENT_ERROR는 재시도 건너뜀)
CircuitBreaker            — CLOSED → OPEN → HALF_OPEN → CLOSED 상태 전이
```
- 실제 KIS / DART / RSS 호출 0건 (opt-in skeleton; 기존 provider 강제 적용 없음)
- DB 스키마 변경 없음 (Alembic: 0004_user_preferences만 추가)

### 3.14 Provider Resilience Runtime + DART Provider skeleton (v0.10 Phase A·B)

**Phase A — `app/data/provider_health_monitor.py`:**
- `ProviderHealthMonitor` — provider name 별 in-memory 통계 + circuit breaker
  보관 (singleton + per-test 격리 인스턴스)
- `call_with_resilience(provider_name, fn, ...)` — retry + circuit breaker +
  exception → `ProviderCallResult.fail(UNKNOWN)` 변환 (failure isolation,
  **never raises**)
- `Settings.provider_resilience_enabled=False` 기본 + 6 런타임 파라미터
  (timeout / max_attempts / base/max delay / breaker threshold / reset timeout)
- 잡 / scheduler 는 `result.success` 만 보고 분기 → 단일 provider 장애가
  전체 잡 파이프라인을 멈추지 않음

**Phase B — `app/data/dart_provider.py`:**
```text
DartFundamentalProvider   → FundamentalProviderInterface (fnlttSinglAcnt mock)
DartEarningsProvider      → EarningsProviderInterface    (fnlttSinglAcnt actual subset)
DartDisclosureProvider    → DisclosureProviderInterface  (/api/list.json mock)
```
- `Settings.dart_enabled=False` 기본 — `DartNotConfiguredError` raise (provider
  인스턴스화 / transport 호출 0건)
- **Transport 주입형** — Phase B 는 mock fixture 만 사용; 실 httpx 전송 도입은
  Phase D 로 이연. 모든 호출은 `call_with_resilience` 경유 → Phase A 의 retry +
  breaker + isolation 자동 상속
- Parser / mapper 는 forbidden body 필드 (`body` / `content` / `full_text` /
  `paragraph` / `raw_text` / `html_body` / `본문` / `원문` / `전문`) 를 strip
  후 DTO 생성. DTO (`FundamentalSnapshotDTO` / `EarningsEventDTO` /
  `DisclosureItemDTO`) 자체에 해당 필드 부재
- `crtfc_key` 는 provider 가 transport params 에 주입하지만 로그에는 노출되지
  않음. `SensitiveFilter` 에 `crtfc_key` / `crtfckey` / `dart_key` 패턴 명시
  추가 — `dart_api_key` / `DART_API_KEY` 는 기존 `api_key` 패턴 매칭
- DB 스키마 변경 없음 (`financial_statements` / `news_items` 기존 테이블 재사용,
  Alembic head 그대로 `0004_user_preferences`)

**Phase C — `app/data/rss_provider.py`:**
```text
RssNewsProvider           → NewsProviderInterface (RSS 2.0 + Atom 동시 지원)
parse_feed(payload, ...)  → root tag 기반 포맷 분기 (rss / feed)
dedup_items(items)        → URL first-wins (news_items.url UNIQUE 정합)
_safe_url_for_log(url)    → query / fragment strip 후 host + path 만 로그
```
- `Settings.rss_news_enabled=False` 기본 + `Settings.rss_feed_urls=""` 기본
  — `RssNotConfiguredError` raise. 운영자가 명시한 URL 만 fetch (자동
  discovery / crawling 0건)
- **신규 의존성 0건** — stdlib `xml.etree.ElementTree` 만 사용 (feedparser
  도입 검토했으나 RSS 2.0 + Atom subset 만 다루므로 불필요)
- Parser 가 forbidden body 필드 (`body` / `content` / `content_encoded` /
  `full_text` / `paragraph` / `raw_text` / `html` / `html_body` /
  `description_full` / `본문` / `원문` / `전문`) 를 사전 strip
- `<description>` 내 HTML 태그 strip + summary 500자 truncate — 본문 누출
  방지 다층 가드
- URL dedup 은 fetch 호출 단위 first-wins; collector → DB 저장 시 추가로
  `news_items.url` UNIQUE 가 두 번째 가드 (upsert-ignore)
- 모든 transport 호출이 `call_with_resilience(provider_name="rss", ...)` 경유
  — Phase A retry / circuit breaker / failure isolation 자동 상속
- feed URL 의 query string secret (`?api_key=...` / `?token=...`) 은 로그에
  미노출 — `_safe_url_for_log` 가 query / fragment strip 후 host + path 만
  emit
- DB 스키마 변경 없음 (`news_items` 기존 테이블 재사용, Alembic head 그대로
  `0004_user_preferences`)

### 3.14.1 Provider Observability Layer (v0.11 Phase C)

v0.10 의 `ProviderHealthMonitor` 위에 bounded ring buffer + 24h summary +
optional Prometheus exporter 를 추가한다. **Alembic revision 0건** —
`ProviderHealthMonitor` 와 ring buffer 모두 in-memory only.

**확장된 모니터 (`app/data/provider_health_monitor.py`):**
```text
ProviderStats
  ├─ recent_calls: deque[CallRecord]   maxlen=200    (bounded)
  ├─ recent_failures: deque[FailureRecord]  maxlen=50  (bounded)
  └─ summary_24h(now=None) → Summary24h
       (call_count_24h / success_count_24h / failure_count_24h /
        success_rate_24h / avg_attempts)

CallRecord/FailureRecord — frozen dataclass:
  timestamp + success + error_kind + attempts (no error_message → no URL secret leak)
```

**Optional Prometheus exporter (`app/monitoring/prometheus.py` + `app/api/metrics_routes.py`):**
- `PROMETHEUS_ENABLED=False` 기본 — `GET /metrics` → 404
- `PROMETHEUS_ENABLED=True` → `GET /metrics` 200 + `text/plain` (Prometheus
  text format)
- POST/PUT/DELETE `/metrics` 모두 405 (read-only 정책)
- Counter 4종: `provider_calls_total`, `provider_call_successes_total`,
  `provider_call_failures_total`, `provider_call_failures_by_kind_total`
- Gauge 1종: `provider_circuit_state` (CLOSED=0 / OPEN=1 / HALF_OPEN=2 /
  UNREGISTERED=3)
- Histogram 1종: `provider_call_attempts` (1/2/3/4/5/7/10 buckets)
- 라벨: `provider`, `error_kind` 만 (URL / API key / message text 일체 노출 0건)
- `monitor.record_result` → lazy `_emit_prometheus(name, stats, result, attempts)` →
  `prometheus.record_call`. **try/except 로 감싸 observability 가 provider 호출
  path 를 절대 break 하지 않음**
- 테스트 격리: `set_metrics(PrometheusMetrics.build(CollectorRegistry()))` 로
  per-test fresh registry 주입 → global `prometheus_client.REGISTRY` 오염 0건
- `app.main.create_app` startup 시 `init_default_metrics(settings)` 호출
  (idempotent + Prometheus disabled 시 no-op)

### 3.15 Provider Health read-only API (v0.10 Phase D)

**Backend — `app/api/health_routes.py`:**
```text
GET /api/health/providers
    └─ get_health_monitor() → ProviderHealthMonitor.get_status(name)
    └─ Settings (dart_enabled / rss_news_enabled / kis_app_key 등) opt-in 합성
    └─ ProviderHealthResponse(items=[ProviderHealthItem, ...], count)
```

```text
HTTP GET /api/health/providers
    │
    ▼
get_provider_health(settings)         (read-only handler)
    │  for name in (kis, dart, rss):
    │    enabled    = _is_enabled(name, settings)         (Settings 기반)
    │    configured = _is_configured(name, settings)      (자격증명 존재)
    │    stats      = monitor.get_status(name)            (in-memory)
    │    item       = ProviderHealthItem(...)              (no last_error_message)
    │  + monitor.get_all_status() 의 추가 등록 provider append
    ▼
ProviderHealthResponse  →  Pydantic 직렬화 (Decimal/dt 패턴 동일)
```

- canonical 3 provider (`kis` / `dart` / `rss`) 항상 포함 — 운영자가 어떤
  provider 도 활성화하지 않은 상태에서도 UI 가 default-OFF 를 명시적으로 표시
- POST / PUT / DELETE 0건 (모두 405) — provider enable/disable 토글은 `.env`
  + 백엔드 재시작으로만 가능 (v0.10 cycle 정책)
- 응답 secret 차단 whitelist: `last_error_message` 제외 / `dart_api_key` /
  `crtfc_key` / `kis_app_*` / `rss_feed_urls` / `?api_key=` / `access_token`
  /`password` 등 모두 0건 (테스트 paranoid 단언)
- 외부 네트워크 호출 0건 — handler 는 in-memory monitor + Settings 만 read

**Frontend:**
```text
frontend/src/api/providerHealth.ts        # GET /api/health/providers wrapper
frontend/src/hooks/useProviderHealth.ts   # useQuery, staleTime 30s, refetch 60s
frontend/src/components/common/ProviderHealthPanel.tsx
                                          # read-only table (provider × badges + counts)
```

- Settings 화면 (`/settings`) 의 UserPreference section 아래 + system
  read-only section 위에 삽입 — 운영자가 한 화면에서 KIS/DART/RSS 상태
  파악 가능
- Read-only — 패널 내 button / checkbox / switch / form 0건 (e2e 단언)
- 백엔드가 secret 을 leak 해도 컴포넌트가 그것을 렌더하지 않음 — UI 도
  whitelist 만 사용 (`provider_name / enabled / configured / circuit_state /
  call_count / success_count / failure_count / last_error_kind /
  last_called_at` 9 필드)

## 4. Import Pipeline (v0.4)

운영자가 직접 작성한 메타데이터 CSV 를 시스템에 적재하는 read-only 파이프라인.
v0.4 Phase B 에서 `scripts/import_analyst_reports.py` (argparse CLI, default
dry-run, `--commit` 시 DB 적재) + 입력 검증 + 멱등 upsert 로 구체화될 예정.

```text
operator CSV / Excel
   │  (manual run only — no auto-crawler)
   ▼
data/importers/  (Phase B 신규)
   │  validation: enum / date / number / 본문 column 거부
   │  truncation: summary > 500자 → truncate + count
   │  idempotency: get_by_unique → skip / create
   ▼
analyst_reports + report_themes + theme_stock_mappings + report_signal_events
   │
   ▼
update_report_consensus_snapshots (Phase B 신규 잡, 06:30 KST)
   │
   ▼
report_consensus_snapshots
```

`source_file_path` 는 운영자 로컬 PDF 경로 — DB 저장 후 어떤 출력에도 노출되지
않는다 (CLI summary / API 응답 / 프런트 / e2e 모두 마스킹). 자동 크롤링 /
스크레이핑은 v0.5+ 별도 저작권 검토 후 검토 가능.

## 5. 핵심 인터페이스

### DataProviderInterface

외부 데이터 공급자 교체용 ABC. v0.1 의 `KisDataProvider` (실 KIS) /
`FakeKisDataProvider` (테스트) 가 동일 인터페이스 구현. v0.5+ 에 News / 공시 /
재무 공급자가 같은 패턴으로 추가될 수 있다.

### AIProviderInterface / DummyScoreProducer

Dummy / Local LLM / Cloud LLM / Custom Model 을 교체 가능하게 만든다. v0.1 ~
v0.4 는 `DummyScoreProducer` (neutral 50 + rule 기반 ±5 보정) 만 사용. v0.5+ 에
실 News / Supply / Fundamental / Earnings 파이프라인이 도입되면 producer 가
교체된다.

### BrokerInterface

자동매매 / 가상매매 boundary. v0.14 Phase B 부터 첫 구현체가 도입된다.

- **`SimulationBroker` (v0.14 Phase B + Phase C)** —
  `app/broker/simulation_broker.py`. paper / simulation 전용.
  **KIS / DART / RSS / requests / httpx import 0건** (AST + grep 두 가지
  방법으로 회귀 단언).
  - `submit_order` (Phase B): `Settings.paper_trading_enabled=False`
    (default) 또는 account.paper_trading_enabled=False 시
    `PaperTradingDisabledError`. enable 시 `VirtualOrder(CREATED)` 행 작성,
    중복 idempotency_key 는 기존 행 반환 (`SubmitResult.deduplicated=True`).
  - `cancel_order` (Phase B): CREATED / SUBMITTED 만 CANCELED 로 이행, 그
    외 상태 거부.
  - `execute_pending_orders(session, *, as_of_date, account_id?,
    pnl_tracker?, price_lookback_days=0)` (Phase C 본 구현): MARKET → close
    즉시 체결, LIMIT BUY → close ≤ limit, LIMIT SELL → close ≥ limit.
    daily_prices 행이 없으면 skip (재실행 가능). cash 부족 →
    `InsufficientCashError` → REJECTED, position 부족 →
    `InsufficientPositionError` → REJECTED. terminal/fill 상태는 절대
    재실행되지 않는다 (이중 가드: SQL 필터 + defensive recheck).
    `ExecutePendingResult` 에 filled / rejected / skipped 카운트 노출.
- KisBroker (실거래) — v1.0+ 별도 보안·컴플라이언스 사이클 후 진입
- MockBroker / ReplayBroker — 필요시 검토

### PnLTracker (v0.14 Phase C)

`app/paper/pnl_tracker.py`. SimulationBroker 의 fill 엔진이 호출하는
bookkeeping 모듈.

- `apply_fill(session, *, order_id, account_id, symbol, side, quantity,
  fill_price)` — `PaperTradingCostModel` 로 fee / stamp_tax / slippage / net
  을 계산. BUY 는 cash 감소 + position quantity 증가 + cost-basis blended
  avg_cost 재계산, SELL 은 cash 증가 + realized_pnl 누적 + 0 도달 시
  avg_cost 리셋. `VirtualFill` row 와 mutation 모두 단일 트랜잭션 안에서
  실행되며 `FillResult` 로 반환.
- `create_daily_pnl_snapshot(session, *, account_id, snapshot_date,
  price_lookback_days=14)` — open positions 를 daily_prices.close 로 평가해
  market_value / total_value / unrealized_pnl 을 계산하고
  `virtual_pnl_snapshots` 에 idempotent upsert. 가격이 없는 종목은 0 기여
  (graceful) — 스냅샷 잡이 가격 누락에 실패하지 않는다.
- 외부 HTTP / KIS 호출 0건 (AST 회귀 단언).

### StrategyInterface

미래 전략 / 백테스트 확장용 placeholder. 현재 코드 미존재.

## 6. v0.1 ~ v0.4 일관 안전 규칙

- 모든 사이클에서 **자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드
  0건**.
- 모든 사이클에서 **POST / PUT / DELETE 라우터 0건** (read-only API 만).
- AI / Scoring / Notification 모듈은 직접 주문하지 않는다.
- Recommendation / Holding 은 외부 API 를 직접 호출하지 않는다.
- API 라우터는 collector / 지표 계산 / 추천 생성을 직접 하지 않는다.
- 모든 판단은 `data_snapshots` + `decision_logs` + `job_runs` + `notification_logs`
  로 추적 가능하다.
- v0.4 의 리포트 본문 / PDF BLOB 저장 0건 — 운영자 작성 짧은 요약만.
- 모든 비밀값 (KIS 키 / 텔레그램 토큰 / 계좌번호) 은 마스킹 (`5015****1-01`)
  되며 API 응답 / 프런트 / e2e 어디에도 평문 노출 0건.
- 모든 외부 호출 (KIS / Telegram) 은 테스트에서 mock 으로 대체 — `pytest -q`
  실행 시 외부 네트워크 0건.
