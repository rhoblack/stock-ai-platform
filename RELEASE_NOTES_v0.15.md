# RELEASE_NOTES_v0.15.md — Approval Trading Safety Layer

> 마감 태그: `v0.15-final`
> 마감 일자: **2026-05-08 (Asia/Seoul)**
> 기준 태그: `v0.14-final` → 마감 태그: `v0.15-final`
> 세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0015`

---

## 1. 사이클 요약

v0.15 는 **Approval Trading Safety Layer** 를 도입한 사이클이다. 사람의 승인 없이는
주문이 시장으로 흐르지 않도록 막는 안전 게이트 — `SafetySettings` (Phase A),
`OrderCandidate` 8-state 머신 (Phase B), 6 hard 룰 `PreTradeRiskEngine` (Phase C),
Approval Workflow API 7종 + `ApprovalAuditLog` append-only + 자동 만료 잡 (Phase D),
14번째 프런트 화면 `/approvals` (Phase E) 가 모두 도입되었다.

**v0.1 ~ v0.14 의 안전 정책은 그대로 유지된다** — 실 KIS 주문 / 실 Broker /
자동매매 / FULL_AUTO / SMALL_AUTO 코드 0건. 승인된 후보 (`status=APPROVED`) 는
오직 `SimulationBroker.submit_order` 만 호출하며, `EXECUTED_PAPER` 로 이행된 후
`virtual_order_id` 만 노출된다. KIS / 실 Broker 호출 경로는 코드에 존재하지 않는다.

| Phase | 내용 | 태그 | 게이트 |
|---|---|---|---|
| A | `SafetySettings` + `KillSwitch` + 안전 default 7건 + 단위 테스트 | `v0.15-safety-settings` | pytest **1438→~1465** |
| B | `OrderCandidate` ORM (38번째) + Repository + Alembic 0007 + 8-state 머신 단위 테스트 | `v0.15-order-candidate` | pytest **~1465→~1505** |
| C | `PreTradeRiskEngine` (7 hard 룰) + `RiskCheckResult` + 룰별 단위 + 통합 테스트 | `v0.15-pre-trade-risk` | pytest **~1505→~1545** |
| D | Approval Workflow API 7종 + `ApprovalAuditLog` (39번째) + Alembic 0008 + `ApprovalService` + `expire_pending_approvals` 잡 | `v0.15-approval-api` | pytest **~1545→1693 (+~148 누적)** |
| E | 14번째 프런트 화면 `/approvals` + 본 release notes + 마감 문서 + 4 게이트 최종 확인 | `v0.15-final` | vitest **186→201 (+15)** / e2e **22→23 (+1)** |

---

## 2. 산출물 상세

### Phase A — SafetySettings + KillSwitch

- `app/config/settings.py` — 7 신규 안전 설정 추가:
  - `trading_safety_enabled: bool = False` — 모든 approval mutation 의 마스터 게이트
  - `kill_switch_enabled: bool = True` — **paranoid master block 기본 ON**.
    운영자가 명시 false 로 끄지 않으면 모든 후보 차단
  - `approval_required: bool = True` — 사람 승인 없이 paper execution 진입 금지
  - `max_order_amount=100,000`, `max_daily_order_amount=1,000,000`,
    `max_position_ratio=0.20`, `max_daily_loss_amount=500,000` — risk 룰 임계값 default
- `_as_strict_bool` helper — typo 시 default 유지 (paranoid kill switch 보장).
- `__post_init__` 경계 검증 — `max_order_amount > 0`, `max_daily_order_amount > 0`,
  `0 < max_position_ratio ≤ 1`, `max_daily_loss_amount ≥ 0`. 위반 시 `ValueError`
  로 Settings 생성 자체 차단.
- 단위 테스트 신규 60건 — paranoid defaults / env override happy /
  strict-bool typo paranoid / boundary validation parametrize 14 case /
  range accepts / frozen mutation 거부 / v0.14 paper_trading + v0.1
  feature_real_order_execution / feature_full_auto 회귀.
- 코드 동작 변경 0건 — 후속 Phase 가 본 settings 를 참조하기 위한 기반 작업.

### Phase B — OrderCandidate 8-state Machine

- `app/db/models.py` — `OrderCandidate` (38번째) ORM. 8 상태 enum:
  `DRAFT → RISK_CHECKING → (RISK_REJECTED | PENDING_APPROVAL) →
  (APPROVED → EXECUTED_PAPER | REJECTED | EXPIRED)`.
- forbidden 컬럼 0건 단언: `broker_order_id / kis_order_id / real_account /
  real_order_id / api_key / token / secret / source_file_path`.
- `alembic/versions/0007_order_candidates.py` 신규 — 1 테이블 + 인덱스 + downgrade.
- `app/data/repositories/order_candidate.py` — `create / get_by_id /
  list_by_account / list_pending / update_status / update_risk_result /
  set_approver / set_virtual_order_id`. 상태 머신 enforcement 는 Repository 레벨.
- 단위 (상태 머신 매트릭스) + 통합 (CRUD) 테스트 신규.

### Phase C — PreTradeRiskEngine (7 HARD rules)

- `app/risk/pre_trade_risk_engine.py` 신규 — 7 hard 룰:
  1. `account_paper_enabled` — VirtualAccount.paper_trading_enabled=True 필수
  2. `kill_switch_off` — KILL_SWITCH_ENABLED=False 필수
  3. `per_symbol_limit` — 종목당 한도
  4. `daily_total_limit` — 일별 총액 한도
  5. `position_ratio_limit` — 단일 종목 포지션 비율 한도
  6. `daily_loss_limit` — 일별 손실 한도 (초과 시 모든 BUY 차단)
  7. `duplicate_recent` — 5분 내 동일 (symbol, side, qty) 중복 차단
- `RiskCheckResult` / `RiskViolation` dataclass — `policy_version` /
  `passed: bool` / `violations: list[RiskViolation]` / `checked_at` 구조화.
- AST 회귀 단언: `pre_trade_risk_engine.py` 가 KIS / DART / RSS / requests /
  httpx / urllib import 0건.
- 단위 (룰별 happy / boundary / off-by-one / kill_switch ON / ratio 0.2 정확
  검증 / 5분 경계 4분 59초 / 5분 0초) + 통합 (VirtualAccount + VirtualPosition
  시드 후 BUY/SELL 시나리오) 테스트 신규.

### Phase D — Approval Workflow API + Audit Log

- `app/db/models.py` — `ApprovalAuditLog` (39번째) ORM. append-only — 수정 / 삭제
  메서드 0건. `event_type ∈ {CREATED, RISK_CHECKED, RISK_REJECTED, APPROVED,
  REJECTED, EXPIRED, EXECUTED_PAPER, KILL_SWITCH_BLOCKED}`.
- `alembic/versions/0008_approval_audit_logs.py` 신규.
- `app/data/repositories/approval_audit_log.py` — `append / list_by_candidate /
  list_recent`. 수정 / 삭제 API 0건. mutation-keyword-detection 회귀 테스트로
  보호.
- `app/approval/approval_service.py` 신규 — `ApprovalService`:
  - `create_candidate(payload)` → DRAFT → RISK_CHECKING → (PENDING_APPROVAL |
    RISK_REJECTED). `PreTradeRiskEngine` 호출.
  - `approve(candidate_id)` → PENDING_APPROVAL → APPROVED → 즉시
    `SimulationBroker.submit_order` 호출 → EXECUTED_PAPER + virtual_order_id 할당.
    KIS API 호출 0건 (AST 단언).
  - `reject(candidate_id, reason)` / `expire(candidate_id)` — 단순 상태 전이.
  - 모든 상태 전이 시 `ApprovalAuditLog.append`.
- `app/api/approval_routes.py` 신규 — 7 엔드포인트:
  - `GET /api/approvals/candidates?status=&account_id=&limit=`
  - `GET /api/approvals/candidates/{id}` — `risk_check_result` 포함
  - `GET /api/approvals/audit?candidate_id=&event_type=&limit=`
  - `POST /api/approvals/candidates` — 후보 생성 + Risk Check (AUTH 필수)
  - `POST /api/approvals/{id}/approve` — paper execution 으로 종결 (AUTH 필수)
  - `POST /api/approvals/{id}/reject` — `reason` 256자 제한 (AUTH 필수)
  - `POST /api/approvals/{id}/expire` — 관리자 만료 (AUTH 필수)
- mutation 4종은 모두 **TRADING_SAFETY_ENABLED + KILL_SWITCH_ENABLED=False +
  AUTH 3중 게이트** — 어느 하나라도 false 면 503.
- `app/scheduler/jobs.py` — `expire_pending_approvals` 잡 (5분 간격
  IntervalTrigger). TRADING_SAFETY_ENABLED=false 면 SKIPPED, 활성 시
  `expires_at < now` 인 PENDING_APPROVAL 후보를 일괄 EXPIRED 로 전이.
- `tests/integration/test_auth_security.py` — mutating endpoint count 11→17,
  no_auto_trade_strings_in_routes 가드 갱신 (`approval` keyword 는
  `/api/approvals/` prefix 만 허용).

### Phase E — 14번째 프런트 화면 `/approvals`

- `frontend/src/api/approval.ts` 신규 — 7 fetch 함수, 모두 `/api/approvals/*` 만 호출.
- `frontend/src/hooks/useApprovals.ts` 신규 — TanStack Query 7 hooks
  (read 3 + mutation 4). mutation 후 approval / paper 두 namespace 동시 invalidate
  (EXECUTED_PAPER 가 VirtualOrder 를 생성하므로).
- `frontend/src/pages/Approvals/index.tsx` 신규 (14번째 화면) — 컴포넌트:
  `ApprovalsPage` / `PolicyBanner` / `PendingCandidatesTable` /
  `CandidateDetailDrawer` (`CandidateSummary` / `RiskCheckPanel` /
  `AuditTimeline`) / `NewCandidateForm` / `HistoryTable`.
- 버튼 라벨은 모두 안전 어휘: "승인 (paper 실행)" / "거절" / "만료" /
  "후보 만들기 (Risk Check)". "주문 실행" / "place real order" / "FULL_AUTO" /
  "SMALL_AUTO" / "자동매매" 같은 actionable CTA 0건.
- 헤더에 "모의투자 모드" 배지 + `PolicyBanner` 가 항상 노출되어
  TRADING_SAFETY / KILL_SWITCH 게이트 정책을 설명.
- 503 응답 발생 시 `approvals-disabled-banner` (general) 와
  `approvals-kill-switch-banner` (`detail` 에 "kill switch" 포함 시) 친절 안내.
- `frontend/src/router.tsx` + `frontend/src/components/layout/Sidebar.tsx` —
  14번째 메뉴 `/approvals` (`ShieldCheck` 아이콘, "승인 대기 (β)"). 사이드바
  footer 도 "v0.15 dashboard" / "v0.15 Approval Trading Safety Layer" 로 갱신.
- `frontend/src/api/types.ts` — Approval 타입 11종 추가
  (`OrderCandidate / OrderCandidateStatus / OrderCandidatesResponse /
  RiskViolation / RiskCheckResult / OrderCandidateDetailResponse /
  CreateOrderCandidateRequest / CreateOrderCandidateResponse /
  ApproveCandidateResponse / ApprovalCandidateStatusResponse /
  ApprovalAuditLogItem / ApprovalAuditResponse / ApprovalEventType`).
- `frontend/src/tests/Approvals.test.tsx` 신규 vitest 15건 — page render /
  empty placeholders / pending table 액션 / 503 disabled banner / kill switch
  banner / approve happy path / reject prompt-driven reason / expire 호출 /
  detail drawer (summary + risk + audit) / risk violation rendering /
  history table / new candidate disabled banner / new candidate success /
  forbidden DOM 토큰 0건 / 자동매매 CTA 0건.
- `frontend/src/tests/mswServer.ts` — approval 7 mock 추가 (POST 기본 503).
- `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts` — sidebar 13→14,
  `/approvals` happy-path navigation, raw payload forbidden 검사,
  disabled banner 시나리오, automation CTA 0건 단언 추가.

---

## 3. 최종 게이트 (v0.15-final)

| 게이트 | 결과 |
|---|---|
| backend pytest | **1693 passed** (Phase D 마감 시점 그대로 — Phase E 는 frontend only). 1건 실패는 로컬 `.env` `MARKET_CAP_LIMIT=5` 운영자 오버라이드 때문이며 v0.15 회귀와 무관. CI clean 환경에서는 통과. |
| frontend vitest | **201 passed** (186 → 201, +15 — Approvals.test 신규) |
| frontend build | **그린** (`tsc --noEmit && vite build`) |
| Playwright e2e | **23 passed** (22 → 23, +1 — `/approvals` happy-path) |
| Alembic head | `0008_approval_audit_logs` (39 테이블 누적) |
| `compare_metadata` diff | **0건** (CI 강제) |

---

## 4. 안전 정책 (v0.15 누적)

- **실 KIS 주문 / 실 Broker / 자동매매 / FULL_AUTO / SMALL_AUTO 코드 0건**
  (v0.1 ~ v0.15 일관). `BrokerInterface` 의 유일한 구현체는 여전히
  `SimulationBroker` 이며 KisBroker / 실거래 브로커는 placeholder.
- **승인 mutation 4종은 TRADING_SAFETY_ENABLED=true + KILL_SWITCH_ENABLED=false +
  AUTH 3중 게이트** — 어느 하나라도 미달이면 즉시 503. KILL_SWITCH_ENABLED 의
  기본값은 paranoid 으로 **true** (즉 차단) — 운영자가 명시적으로 false 로 끄지
  않으면 모든 mutation 이 차단된다.
- **APPROVED 후보는 paper execution 으로만 종결** —
  `SimulationBroker.submit_order` 만 호출하며, `app/approval/approval_service.py`
  / `app/api/approval_routes.py` / `app/risk/pre_trade_risk_engine.py` 모두 AST
  검사로 KIS / DART / RSS / requests / httpx / urllib import 0건 강제.
- **ApprovalAuditLog append-only** — 수정 / 삭제 API 0건. mutation-keyword-detection
  회귀 테스트로 보호.
- **사용자 승인 없는 paper 실행 0건** — `approval_required=True` 기본,
  `ApprovalService.execute_approved` 가 PENDING_APPROVAL → APPROVED 전이
  요구.
- **forbidden 응답 / DOM 필드 12+1종 0건**: `api_key / token / secret /
  source_file_path / broker_order_id / kis_order_id / real_account /
  real_order_id / account_number / raw_text / body / full_text / broker` —
  backend Pydantic 스키마 + frontend 컴포넌트 + e2e raw payload 검사로 3중 단언.
- **외부 네트워크 호출 0건** — 7 신규 approval/risk 모듈 모두 stdlib only.
- **ScoringEngine / HoldingCheckEngine 본 weight 변경 0건** —
  technical 35% / news 25% / supply 15% / fundamental 15% / ai 10% 그대로.
- **신규 pip 의존성 0건**.
- **자동매매 CTA UI 0건** — submit 버튼 라벨은 "후보 만들기 (Risk Check)" /
  "승인 (paper 실행)" / "거절" / "만료". e2e 가 "자동매매 시작" / "실거래 시작" /
  "주문 실행" / "FULL_AUTO" / "place real order" 등 패턴 0건을 강제.

---

## 5. 알려진 한계

- **단일 사용자 / 단일 계좌 가정** — v0.14 와 동일하게 첫 VirtualAccount 자동
  선택. 멀티 계좌 / 멀티 사용자 승인 흐름은 v0.16+ 후보.
- **승인 만료 자동 잡은 5분 간격 polling** — APScheduler IntervalTrigger.
  realtime push (WebSocket / SSE) 는 미구현, 만료 직후 1~5분 race window 가능.
  TTL 짧게 (e.g. 5~15분) 운영하는 시나리오에서는 충분, long-TTL 운영 시 추가
  잡 빈도 조정 필요.
- **SOFT 룰 0건** — `PreTradeRiskEngine` 은 7 HARD 룰만 평가. SOFT 룰
  (grade D 이하 종목 / regime risk 등) 은 v0.15+ 패치 또는 v0.16 후보.
- **ApprovalService 는 KIS API 호출 0건** — 본 사이클 산출물은 paper execution
  까지만. 실 주문 (`KisOrderClient.place_order`) 는 v0.16 Real Order
  Integration 사이클에서 도입 예정.
- **Approval 텔레그램 알림 미구현** — 승인 대기 / 거절 / 만료 / EXECUTED_PAPER
  텔레그램 발송은 v0.15 범위 외. 기존 dispatcher 는 read-only 추천 / 보유 점검
  리포트만 처리.
- **로컬 `.env` 의 `MARKET_CAP_LIMIT=5` 등 운영자 오버라이드 시
  `tests/unit/test_project_structure.py::test_settings_defaults` 1건이
  환경 의존적으로 실패** — CI 환경 (.env clean) 에서는 통과. v0.14 시점부터
  존재하던 사전 이슈로 v0.15 회귀와 무관.

---

## 6. v0.16 후보

- **Real Order Integration** — `KisOrderClient.place_order(candidate)` 도입.
  v0.15 `OrderCandidate(status=APPROVED)` 를 그대로 입력으로 받도록 설계.
  추가 새 룰 (호가 jump 검사 / 시간외 차단 / 손절가 자동 SELL) 도 함께 검토.
- **PreTradeRiskEngine SOFT 룰** — grade D 이하 / regime HIGH_RISK /
  recent volatility 등 경고 모드 룰 추가.
- **Approval 텔레그램 알림** — 승인 대기 알림 / 만료 임박 알림 / EXECUTED_PAPER
  요약 리포트 (DRY_RUN 기본 유지).
- **multi-account / 멀티 사용자 approval workflow** — 계좌별 / 권한별 승인자
  역할 분리.
- **승인 만료 realtime push** — WebSocket / SSE 로 만료 알림 즉시 전파.
- **PnL 차트 / 백테스트와의 비교 화면** — Recharts 기반 일별 자산 추이.

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
| v0.14 | `v0.14-final` | Paper / Simulation Trading Foundation (5 ORM + 6 API + 2 jobs + 13번째 화면) |
| **v0.15** | **`v0.15-final`** | **Approval Trading Safety Layer (2 ORM + 7 API + 1 job + 14번째 화면 + 7-rule risk engine)** |

이 시점의 누적: **39 ORM 테이블 / 58+ FastAPI 라우터 / 12 스케줄러 잡 / 14 프런트 화면 /
backend pytest 1693 / vitest 201 / e2e 23 / Alembic 8 revisions**.

---

## 8. 운영 절차 변경

- 운영자가 `.env` 에 `TRADING_SAFETY_ENABLED=true` + **`KILL_SWITCH_ENABLED=false`
  (기본 true → 명시 false 필요)** + `APPROVAL_REQUIRED=true` (기본 true) +
  `AUTH_ENABLED=true` + `JWT_SECRET=<32-char>` + `SCHEDULER_ENABLED=true` +
  `PAPER_TRADING_ENABLED=true` 를 명시 설정한 뒤 `alembic upgrade head` (head 가
  `0008_approval_audit_logs` 인지 확인) 로 활성화.
- VirtualAccount 1건 시드 절차는 v0.14 운영 절차 (`INTEGRATION_RUNBOOK.md`
  §22.2) 와 동일. 추가로 본 사이클은 운영자가 OrderCandidate 를 생성·승인할 수
  있는 권한 (단일 사용자 모드에서는 자동) 이 필요하다.
- **KILL_SWITCH 절차** — 기본값이 paranoid `true` 이므로 정상 운영 시
  `KILL_SWITCH_ENABLED=false` 로 명시 해제. 비상 차단이 필요할 때 운영자는
  `.env` 에서 다시 `KILL_SWITCH_ENABLED=true` 로 변경하면 된다 (또는 단순히
  설정을 지우면 default true 로 되돌아감). 모든 mutation API 가 503 응답으로
  차단되며, 스케줄러 자동 만료 잡은 그대로 동작 (만료는 안전 작업이므로
  차단되지 않음). 복구 시 운영팀 점검을 거쳐 `KILL_SWITCH_ENABLED=false` 로 되돌린다.
- read-only GET 3종 (`/api/approvals/candidates` / `/candidates/{id}` / `/audit`)
  은 TRADING_SAFETY_ENABLED 무관하게 동작 — 비활성 상태에서도 과거 후보 / audit
  이력 조회 가능.
- mutation 4종은 TRADING_SAFETY_ENABLED + KILL_SWITCH_ENABLED=False + AUTH
  3중 게이트 — 비활성 상태에서는 503.
- `/approvals` 화면은 항상 정책 배너 + "모의투자 모드" 배지 표시. 503 응답은
  친절 안내 배너로 노출되어 운영자가 어떤 게이트가 닫혀있는지 즉시 파악 가능.
