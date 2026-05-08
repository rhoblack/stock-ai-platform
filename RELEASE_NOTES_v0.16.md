# Release Notes — v0.16 Real Order Integration Skeleton & Fill Sync Readiness

마감 태그: `v0.16-final`  
마감 일자: **2026-05-08 (Asia/Seoul)**  
기준 태그: `v0.15-final`

---

## 핵심 요약

v0.16 은 **실거래 연결을 위한 최소 골격(skeleton)** 을 구축하는 사이클입니다.  
실제 KIS 주문 실행·체결 조회·자동매매는 **이번 버전에서도 0건** 으로 유지됩니다.  
모든 실거래 게이트는 `false` 기본값이며, 운영자가 명시적으로 활성화하지 않으면 아무 변화도 없습니다.

---

## Phase A — RealTradingSettings (안전 기본값 5종 신규)

- `real_trading_enabled=False` — 실거래 비활성 기본
- `kis_order_enabled=False` — KIS 주문 비활성 기본
- `real_order_dry_run=True` — dry-run 모드 기본
- `max_real_order_amount=5_000_000` — 단건 주문 상한 (₩5M)
- `max_real_daily_order_amount=50_000_000` — 일일 누적 상한 (₩50M)
- `__post_init__` 검증: 양수 + 상호 의존 (`max_real_order_amount ≤ max_real_daily_order_amount`)
- `can_attempt_real_order_settings(settings)` 순수 판단 함수 (6-gate AND)
- pytest **1693 → 1753 passed (+60)**
- 태그: `v0.16-real-trading-settings`

## Phase B — KIS Order Wrapper Skeleton + FakeKisOrderTransport

- `app/broker/kis_order_client.py` 신규:
  - `KisOrderClientInterface` ABC — `place_order / query_fill_status / cancel_order`
  - `KisOrderRequest` — account_no 마스킹 불변 객체
  - `KisOrderResult / KisFillStatusResult / KisCancelResult` 불변 dataclass
  - `FakeKisOrderTransport` — FAKE-xxxx 가짜 주문번호 반환, 항상 FILLED
  - `mask_sensitive_order_payload()` — api_key / secret / account_no 마스킹
- AST 가드: httpx / requests / urllib / KisHttpOrderTransport import 0건
- 민감값(api_key / secret / account_no) 평문 저장 0건
- pytest **1753 → 1787 passed (+34)**
- 태그: `v0.16-kis-order-wrapper`

## Phase C — RealOrder / RealFill ORM + Alembic 2 revisions

- `RealOrder` 40번째 ORM (`real_orders` 테이블):
  - status 8종 (DRY_RUN · CREATED · SUBMITTED · PARTIALLY_FILLED · FILLED · CANCELED · REJECTED · FAILED)
  - `broker_order_no_hash` — SHA-256 해시만 저장, 평문 KIS 주문번호 0건
  - `dry_run=True` 기본
- `RealFill` 41번째 ORM (`real_fills` 테이블)
- `alembic/versions/0009_real_orders.py` + `0010_real_fills.py`
- `RealOrderRepository` + `RealFillRepository`
- `compare_metadata` drift 0건 (server_default 제거)
- pytest **1787 → 1858 passed (+71)** / Alembic head `0010_real_fills` / 누적 41 테이블
- 태그: `v0.16-real-order-orm`

## Phase D — RealOrderExecutor dry-run 전용 + FillSyncService mock

- `app/broker/real_order_executor.py` 신규:
  - **8-gate 안전 검사** (빠른 순서로):
    1. candidate status == APPROVED
    2. 중복 실행 가드 (동일 candidate_id에 대한 활성 RealOrder 존재 여부)
    3. `kill_switch_enabled == False`
    4. `real_trading_enabled == True`
    5. `kis_order_enabled == True`
    6. `estimated_amount ≤ max_real_order_amount`
    7. 오늘 누적 KST 기준 합계 ≤ `max_real_daily_order_amount`
    8. `PreTradeRiskEngine.evaluate()` 재검사
  - 8 게이트 통과 후 `dry_run=True` → `FakeKisOrderTransport.place_order()` → `DRY_RUN` RealOrder 저장
  - `real_order_dry_run=False` → `REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D` 반환
- `app/broker/fill_sync_service.py` 신규:
  - `FILLED` → `RealFill(FULL)` 생성 + 주문 상태 갱신 (비터미널 주문만)
  - `PARTIALLY_FILLED` → `RealFill(PARTIAL)` 생성
  - `DRY_RUN` 주문: fill 생성 가능, 상태 갱신 불가 (터미널)
  - transport 주입 가능 (테스트용 stub)
- pytest **1858 → 1905 passed (+47)**
- 태그: `v0.16-real-order-executor`

## Phase E — Real Orders 15번째 화면 + 문서 마감

### 백엔드 read-only API

- `app/api/real_order_routes.py` 신규 (GET 전용, POST/PUT/DELETE 0건):
  - `GET /api/real-orders` — 목록 (status / candidate_id / limit / offset 필터)
  - `GET /api/real-orders/{id}` — 상세 + fills
- 응답 스키마: `RealOrderSchema / RealFillSchema / RealOrderDetailResponse / RealOrdersResponse`
- 금지 필드 미노출: `broker_order_no_hash / api_key / app_secret / access_token / raw_response / account_number / real_account`
- `test_no_auto_trade_strings_in_routes` 업데이트: `/api/real-orders` allowlist 추가

### 프론트엔드 15번째 화면 `/real-orders`

- `frontend/src/pages/RealOrders/index.tsx` 신규:
  - **RealTradingSafetyBanner** — "현재 화면은 dry-run / 기록 조회 전용입니다 / 실제 KIS 주문은 실행되지 않습니다" 항상 표시
  - **RealOrderSummaryCards** — 총 주문 수 / Dry-run 수 / 체결 완료 수
  - **RealOrdersTable** — 주문 목록 (status badge 포함)
  - **RealOrderDetailPanel** — 행 클릭 시 주문 상세 + 체결 내역
  - **RealFillsTable** — 체결 내역 (FULL / PARTIAL badge)
- `frontend/src/api/realOrders.ts` — `fetchRealOrders / fetchRealOrderDetail`
- `frontend/src/hooks/useRealOrders.ts` — `useRealOrders / useRealOrderDetail` (mutation hook 0건)
- `frontend/src/api/types.ts` — `RealOrder / RealFill / RealOrdersResponse / RealOrderDetailResponse`
- 금지 어휘 0건: 실주문 실행 / 주문 전송 / place real order / 자동매매 / FULL_AUTO / SMALL_AUTO
- 금지 필드 미렌더링: broker_order_no_hash / api_key / raw_response / account_number / real_account

### 사이드바 + 라우터

- `Sidebar.tsx`: TrendingUp 아이콘 + "실주문 준비 (β)" 13번째 항목 (approvals 다음, jobs 앞)
- `router.tsx`: `/real-orders` 라우트 추가
- footer: "v0.16 Real Order Integration Skeleton"

### 테스트 보강

- `frontend/src/tests/RealOrders.test.tsx` 신규 13건:
  - page render / safety banner / empty state / orders table / DRY_RUN badge / summary cards / detail panel / fills table / fills empty / error state / forbidden field 미렌더링 / 자동매매 CTA 없음 / mutation hook 0건
- `frontend/src/tests/mswServer.ts`: real-orders 2 mock 추가
- `frontend/e2e/fixtures/apiMocks.ts`: real-orders 2 mock 추가
- `frontend/e2e/dashboard.spec.ts`: 14 → **15** sidebar menus / Real Orders e2e 테스트 1건 추가

---

## 최종 4 게이트

| 게이트 | 결과 |
|---|---|
| backend pytest | **1905 passed** (+212 vs v0.15-final, 회귀 0건) |
| frontend vitest | **214 passed** (+13 vs v0.15-final, 회귀 0건) |
| Playwright e2e | **24 passed** (+1 vs v0.15-final, 회귀 0건) |
| frontend build | **통과** (tsc --noEmit + vite build 그린) |

---

## 안전 정책 (v0.16 기준)

| 항목 | v0.16 상태 |
|---|---|
| 실 KIS HTTP 호출 | **0건** — FakeKisOrderTransport 전용 |
| 실 KIS 주문 실행 | **불가** — real_order_dry_run=True 기본, dry_run=False 경로는 NOT_IMPLEMENTED 반환 |
| 자동매매 / FULL_AUTO / SMALL_AUTO | **0건** — 코드 미존재 |
| KIS API key / secret 평문 저장 | **0건** — mask_sensitive_order_payload 마스킹 |
| KIS 주문번호 평문 저장 | **0건** — broker_order_no_hash (SHA-256 hex 만) |
| raw KIS response 저장 | **0건** — FakeKisOrderTransport 사용, real transport 0건 |
| 계좌번호 / API key 화면 렌더링 | **0건** — forbidden field 스키마 미포함 + e2e 단언 |
| httpx / requests / urllib import | **0건** — AST 가드 (broker/ + executor + fill sync 모두) |
| real_trading_enabled 기본 | **False** |
| kis_order_enabled 기본 | **False** |
| real_order_dry_run 기본 | **True** |

---

## 알려진 한계

- `real_order_dry_run=False` 경로는 `REAL_ORDER_NOT_IMPLEMENTED_IN_PHASE_D` 응답 — 실 KIS 주문 경로 미구현 (Phase E+)
- `FakeKisOrderTransport.query_fill_status()` 는 항상 FILLED 반환 — 실 체결 조회 미구현
- `KisHttpOrderTransport` 는 존재하지 않음 — v0.17+ scope (컴플라이언스 / 보안 검토 후)
- Reconciliation (RealOrder vs KIS 실 체결 대조) → v0.17 이연
- `/api/real-orders` mutation 엔드포인트 (POST/PUT/DELETE) → 미구현, Phase E에서도 read-only

---

## v0.17 후보

- `KisHttpOrderTransport` 구현 (컴플라이언스 / 보안 검토 선행 필수)
- `real_order_dry_run=False` 실 KIS 주문 경로 구현
- Fill Sync 실 체결 조회 연동 (`FillSyncService` transport 교체)
- RealOrder ↔ KIS 체결 내역 Reconciliation
- `/api/real-orders` POST (RealOrderExecutor CLI → API 승격)

---

## 누적 태그 (v0.16)

`v0.16-real-trading-settings` → `v0.16-kis-order-wrapper` → `v0.16-real-order-orm` → `v0.16-real-order-executor` → **`v0.16-final`**
