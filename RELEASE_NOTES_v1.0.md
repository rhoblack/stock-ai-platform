# Release Notes — v1.0 Small Approval Trading Release (DRAFT)

> ⚠️ **본 문서는 v1.0 사이클 진행 중 누적되는 초안이다.**
> Phase A 진입 시점에 시작 — Phase B~E 가 마감되는 시점에 본 릴리스 노트로 확정된다.
> v1.0-final 태그는 [`RUNBOOK_REAL_TRADING.md`](./RUNBOOK_REAL_TRADING.md) §8 의 운영
> 체크리스트가 모두 ✅ 가 된 다음에만 발행한다.
>
> 현재 상태: **Phase A 완료 (운영 진입 체크리스트 + 최종 safety gate 잠금)** —
> 실 KIS 호출 / Alembic / DB 모델 / API 라우터 / 프런트 변경은 모두 0 건.

기준 태그: `v0.16-final` (HEAD `2d262d5`, pytest 1905 / vitest 214 / e2e 24 / build 그린)
목표 마감 태그: `v1.0-final`
관련 계획: [`PLANS.md`](./PLANS.md) `PLAN-0017` /
관련 작업 목록: [`TASKS.md`](./TASKS.md) v1.0 Phase A~E

---

## 핵심 요약 (목표)

v1.0 은 v0.1~v0.16 누적 안전 인프라 위에서 **소액·승인 기반 첫 실 KIS 주문 실행**을
가능하게 하는 사이클이다. 본질은 "실 transport 가 끼워졌고, 모든 게이트가 통과될 때만
소액·1 건씩 실주문이 가능하다" 이며, **자동 진입은 없다** — 운영자가 `.env` 에서 명시
활성화 + 사용자가 화면에서 명시 승인 + Pre-trade risk + KillSwitch + 일일/회당 한도가
모두 통과될 때 1 건씩만 나간다.

채택 시나리오: **Scenario X — Small Approval Trading Release** (PLAN-0017 4 시나리오 비교
결과 채택. Reconciliation 은 v1.1 이연. SMALL_AUTO / FULL_AUTO 는 본 프로젝트 명시 금지
정책으로 기각.)

---

## Phase A — Real trading operating checklist + final safety gates ✅ (Phase 진행 중)

**목표:** 실 KIS transport 구현 (Phase B) 진입 전에 운영 진입 체크리스트와 최종 safety
gate 를 문서·설정·테스트로 잠근다. 코드 변경은 settings 검증 helper 1 종 추가뿐 — DB
/ Alembic / API / 프런트 / 실 KIS 호출 모두 0 건.

### A.1 신규 문서

- [`RUNBOOK_REAL_TRADING.md`](./RUNBOOK_REAL_TRADING.md) (신규) — § 1~9 작성 완료
  - § 1 실거래 활성화 전제 조건 (운영자 9 항목 체크리스트)
  - § 2 `.env` 활성화 절차 (5 단계 — `AUTH_ENABLED` → `TRADING_SAFETY_ENABLED` →
    `REAL_TRADING_ENABLED` → `KIS_ORDER_ENABLED` → `REAL_ORDER_DRY_RUN=false` 마지막)
  - § 3 KillSwitch ON / OFF 절차
  - § 4 비상 중지 절차 (1 분 / 5~30 분 / 정상 복귀)
  - § 5 주문 실패 대응 절차 (TIMEOUT / NETWORK_ERROR / 4xx / 응답 누락 4 분기)
  - § 6 체결 불일치 대응 절차 (Fill Sync `delta < 0` / KIS 잔고 불일치 시)
  - § 7 dry-run rollback 절차 (`REAL_ORDER_DRY_RUN=true` 즉시 복귀)
  - § 8 GitHub Release / 운영 체크리스트 (5 카테고리)
  - § 9 v1.0 에서 하지 않을 것 (FULL_AUTO / SMALL_AUTO / 사용자 승인 없는 주문 / 등 14 항목 잠금)

### A.2 신규 helper (코드)

- `app/config/settings.py`:
  - `RECOMMENDED_MAX_REAL_ORDER_AMOUNT_KRW = 1_000_000` (모듈 상수)
  - `RECOMMENDED_MAX_REAL_DAILY_ORDER_AMOUNT_KRW = 10_000_000` (모듈 상수)
  - `validate_real_trading_operating_limits(settings) -> list[str]` (순수 advisory helper)
- 기존 `Settings` 필드 / `__post_init__` 검증 / `_as_strict_bool` / `_as_float` /
  `can_attempt_real_order_settings()` 변경 0 건 (회귀 0)
- 신규 `Settings` 필드 0 건 — 운영 한도 임계값은 모듈 상수로만 노출

### A.3 신규 / 갱신 테스트

`tests/unit/test_safety_settings.py` 에 v1.0 Phase A 단위 테스트 +30 건:
- §14 RUNBOOK_REAL_TRADING.md 존재 + 17 종 필수 키워드 (env-var name + § 1~9 + FULL_AUTO/SMALL_AUTO + paranoid 정책 라인)
- §15 paranoid default 재검증 (v0.15 + v0.16 + v0.14 + v0.8 layer 일관)
- §16 `validate_real_trading_operating_limits()` 6 케이스 (defaults / 회당 초과 / 일일 초과 / 둘 다 / pure / 경계)
- §17 `can_attempt_real_order_settings()` × RUNBOOK §2 9 키 일관성 (6 게이트 each closed → blocks)
- §18 Phase B scope guard (`HttpxKisOrderTransport` / 실 transport 미존재 단언 4 종)
- §19 Alembic head `0010_real_fills` 변경 0 건 + pyproject `httpx` / `respx` 보존 + 외부 broker SDK 미추가

### A.4 게이트

- pytest **1905 → 1935 passed (+30)** / 회귀 0 건
- Alembic head: `0010_real_fills` (변경 0 건, 41 테이블 그대로)
- DB 모델 변경 0 건 / API 라우터 변경 0 건 / 프런트 변경 0 건
- 신규 pip 의존성 0 건 (`httpx` / `respx` / stdlib 만)
- 실 KIS API 호출 0 건 / 외부 네트워크 호출 0 건
- API key / app_secret / access_token / account_number 평문 저장·로그 0 건

### A.5 안전 정책 (Phase A 잠금)

- `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` / `REAL_ORDER_DRY_RUN=true`
  paranoid default 그대로 유지
- `KILL_SWITCH_ENABLED=true` / `TRADING_SAFETY_ENABLED=false` / `APPROVAL_REQUIRED=true`
  v0.15 paranoid 그대로 유지
- `MAX_REAL_ORDER_AMOUNT=100_000` / `MAX_REAL_DAILY_ORDER_AMOUNT=1_000_000` v0.16 paranoid 그대로 유지
- `validate_real_trading_operating_limits()` 가 100k / 1M 기본에서 advisory 0 건 반환
- 운영자가 `.env` 에서 회당 1M / 일일 10M 초과로 설정 시 advisory 1~2 건 반환 (예외 raise 없음)
- FULL_AUTO / SMALL_AUTO / 사용자 승인 없는 주문 / 자동 진입 0 건 (v0.1~v0.16 일관)

### A.6 태그

- `v1.0-operating-checklist` (예상 — Phase A 종료 시점에 발행)

---

## Phase B — KIS real order transport with mock-only tests ✅ (Phase 진행 중)

**목표 달성:** `HttpxKisOrderTransport` (`KisOrderClientInterface` 의 첫 실 구현체) 추가 +
respx / httpx.MockTransport 100% mock + 마스킹 + raw response 차단 + retry/timeout 정책.
실 KIS 호출 0 건. RealOrderExecutor real path wiring 0 건 (Phase C scope).

### B.1 신규 파일

- `app/broker/kis_order_transport_real.py` (≈540 lines) — 첫 실 transport 구현체.
  메서드 3종 (`place_order` / `query_fill_status` / `cancel_order`) + pure helper
  `_run_with_retries` + `_RetryAttempt` 내부 sentinel + `PlaceClassification` /
  `FillClassification` / `CancelClassification` enum
- `tests/unit/test_kis_order_transport_real.py` — 53 단위 테스트 (전부 mock)

### B.2 수정 파일

- `app/broker/__init__.py` — 4 신규 export (`HttpxKisOrderTransport` + 3 classification enum)
- `app/config/settings.py` — 4 신규 settings (`kis_order_base_url` / `kis_order_place_timeout_s` /
  `kis_order_query_timeout_s` / `kis_order_cancel_timeout_s`) + `__post_init__` 양수 검증.
  신규 인증 settings 추가 0 건 — 기존 `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO` 재사용
- `tests/unit/test_safety_settings.py` — Phase A → Phase B scope guard 전환
  (`test_v10_phase_a_httpx_kis_order_transport_module_absent` →
  `test_v10_phase_b_httpx_kis_order_transport_module_present`, assertion 반전)

### B.3 Retry / Timeout 정책

| 메서드 | timeout | retry | 사유 |
|---|---|---|---|
| `place_order` | 5s | **0** | 중복 주문 위험 — TIMEOUT/NETWORK_ERROR 발생 시 운영자 RUNBOOK §5 수동 매칭 |
| `query_fill_status` | 10s | 최대 2 | idempotent — TimeoutException / HTTPError transient failure 만 재시도 |
| `cancel_order` | 5s | 최대 2 | idempotent — KIS 가 이미 취소된 주문에 대해 business code REJECTED 반환 |

HTTP 4xx / 5xx 응답은 모든 메서드에서 재시도 0 건 (서버에 도달했고 정의된 답을 받음).

### B.4 응답 분류 (whitelist 필드만 — raw response 저장·반환 0건)

- `place_order` 5종: SUBMITTED / REJECTED / TIMEOUT / NETWORK_ERROR / UNKNOWN
- `query_fill_status` 6종 (FULL / PARTIAL / NONE / REJECTED / CANCELED / UNKNOWN) →
  `KisFillStatusResult.status` 5 KIS canonical (FILLED / PARTIALLY_FILLED / PENDING /
  REJECTED / CANCELED) 매핑. UNKNOWN 은 `success=False` + `status=PENDING` + `message="UNKNOWN: ..."` 로 surface
- `cancel_order` 5종: CANCELED / REJECTED / TIMEOUT / NETWORK_ERROR / UNKNOWN

KIS 응답에서 whitelist 필드만 추출 (`output.ODNO` / `rt_cd` / `msg1` / `output1.ord_qty` /
`tot_ccld_qty` / `cncl_yn` / `rjct_yn`) 후 immutable 데이터클래스 (`KisOrderResult` /
`KisFillStatusResult` / `KisCancelResult`) 로 재투영. Raw dict 는 호출 종료 시 폐기.

### B.5 마스킹 / 자격증명 정책

- `mask_sensitive_order_payload()` (v0.16) — 디버그 로그에서 모든 payload 자동 마스킹
- `install_sensitive_qs_filter("httpx")` (v0.11) — httpx INFO 로그 라인의 query string 자동 마스킹.
  `__init__` 에서 idempotent 호출
- `__repr__` / `__str__` / `as_dict()` — `app_key` / `app_secret` / `access_token` / `account_no`
  평문 0 건. account_no 는 `****<last4>` 형태만
- caplog 단언 — KIS 서버에 자격증명 헤더 정상 전달은 검증, 동시에 로그 평문 노출 0 건 검증
- broker_order_no — result `order_no` 필드로 평문 반환 (상위 계층 Phase C executor 에서 SHA-256 해싱 후
  `RealOrder.broker_order_no_hash` 로 저장)

### B.6 AST + 모듈 import 가드

- 모듈-레벨 `import httpx` 0 건 — lazy `__init__` 내부만 (AST top-level walk 로 단언)
- `requests` / `urllib` 0 건 (전체 AST walk)
- `app.providers.kis` / `app.data.collectors.kis_client` 0 건 — read-only 데이터 layer 와 구조적 분리

### B.7 게이트

- pytest **1942 → 1995 passed (+53)** / 회귀 0 건
- Alembic head: `0010_real_fills` (변경 0 건, 41 테이블 그대로)
- DB 모델 변경 0 건 / API 라우터 변경 0 건 / 프런트 변경 0 건
- 신규 pip 의존성 0 건 (`httpx` v0.11 부터 production / `respx` v0.11 부터 dev 그대로)
- 실 KIS API 호출 0 건 / 외부 네트워크 호출 0 건 — `httpx.MockTransport` + `respx.mock` 100%
- API key / app_secret / access_token / account_number 평문 저장·로그 0 건
- raw KIS response 저장·반환 0 건

### B.8 안전 정책 (Phase B 잠금 — Phase C wiring 전)

- `HttpxKisOrderTransport` 가 `RealOrderExecutor` 에 wire-up 되지 **않음** — Phase B 는 transport
  객체만 제공. 운영자가 settings 활성화하더라도 executor 는 여전히 `dry_run=True` +
  `FakeKisOrderTransport` 만 사용 (Phase C 에서 wiring 추가 시점에 실 transport 도달 가능)
- Phase B 종료 시점에도 v0.16 paranoid default 9 종 그대로 유지 — 실 KIS 호출은 운영자가 RUNBOOK §1 9
  항목 + §2 5 단계 통과 + Phase C 마감 후에만 가능

### B.9 태그

- `v1.0-kis-real-transport` (예상 — Phase B 종료 시점에 발행)

---

## Phase C — RealOrderExecutor real path behind strict gates ✅ (Phase 진행 중)

**목표 달성:** v0.16 8-gate dry-run 전용 executor → v1.0 **10-gate + dry-run vs real path 분기**.
HttpxKisOrderTransport 는 DI 주입만 (executor 코드는 import 0 건). plaintext KIS order_no /
raw response / 자격증명 어디에도 저장·로그 0 건. 실 KIS 호출 0 건 — 통합 테스트는 모두 respx mock.

### C.1 신규 / 갱신 파일

- `app/broker/real_order_executor.py` 갱신 — 10-gate + `_resolve_real_transport()` + `_execute_real()`
  + `_scrub()` + `_classify_place_message()` 추가. `__init__(transport=, real_transport_factory=)` 확장
- `app/data/repositories/real_order.py` 갱신 — `exists_non_failed_for_candidate(candidate_id)` 헬퍼
  추가
- `app/data/repositories/approval_audit_log.py` 갱신 — `VALID_EVENT_TYPES` 에 `REAL_ORDER_SUBMITTED` /
  `REAL_ORDER_FAILED` 2 종 추가
- `tests/unit/test_real_order_executor.py` Phase C 단위 테스트 +37 건
- `tests/integration/test_real_order_executor_integration.py` (신규) 8 건 통합 테스트
- `tests/unit/test_safety_settings.py` Phase C scope guard 전환 (assertion 반전)

### C.2 10-gate ordering

1. CANDIDATE_NOT_FOUND / NOT_APPROVED
2. DUPLICATE_REAL_ORDER (real) / ALREADY_EXECUTED (dry)
3. KILL_SWITCH_ON
4. **TRADING_SAFETY_DISABLED** (v1.0 신규)
5. REAL_TRADING_DISABLED
6. KIS_ORDER_DISABLED
7. AMOUNT_EXCEEDS_PER_ORDER_CAP
8. AMOUNT_EXCEEDS_DAILY_CAP (KST 일일 누적)
9. RISK_REJECTED (PreTradeRiskEngine)
10. **TRANSPORT_UNAVAILABLE** (real path only, v1.0 신규)

dry-run 은 ①~⑨ 만, real path 는 ①~⑩ 모두. Gate ordering test 가 `kill_switch=True+safety=False` →
`KILL_SWITCH_ON` 이 먼저 fire 되는 것을 단언.

### C.3 dry-run vs real path 분기

- `real_order_dry_run=True` → 기존 dry-run 경로 (`FakeKisOrderTransport.place_order()` →
  `RealOrder(dry_run=True, status=DRY_RUN)`) 그대로
- `real_order_dry_run=False` → real path:
  1. `RealOrder(dry_run=False, status=CREATED)` 선저장 + `session.flush()` (DB anchor 보장,
     RUNBOOK §5 수동 매칭 지원)
  2. `transport.place_order(KisOrderRequest)` 1 회 호출 — Phase B retry=0 정책 보존
  3. `_classify_place_message(result.message)` → 5 분류 (SUBMITTED/REJECTED/TIMEOUT/NETWORK_ERROR/UNKNOWN)
  4. SUBMITTED → `mark_submitted(broker_order_no_hash=sha256(order_no))` /
     비-SUBMITTED → `mark_failed(error_code=cls, error_message=_scrub(msg)[:500])`
  5. ApprovalAuditLog `REAL_ORDER_SUBMITTED` 또는 `REAL_ORDER_FAILED` 1 행

### C.4 broker_order_no_hash + plaintext 차단

- `broker_order_no_hash` = SHA-256 64-char hex of `KisOrderResult.order_no`
- 평문 KIS order_no 어디에도 저장·로그·반환 0 건 (단언):
  - `RealOrder.broker_order_no_hash` / `fake_order_no` / `error_message` / `error_code` 모두 부재
  - `ExecutorResult.message` / `as_dict()` hash-only / status-only
  - audit details `broker_order_no_hash_prefix` 16-char hex 만 (full hash 도 미노출)
- 단위 테스트가 secret marker 주입 후 `RealOrder.*` / `ExecutorResult.*` 모두 부재 단언

### C.5 ApprovalAuditLog 연동

- `VALID_EVENT_TYPES` 신규 2 종: `REAL_ORDER_SUBMITTED` / `REAL_ORDER_FAILED`
- `_FORBIDDEN_DETAILS_KEYS` 13 종 정책 변경 0 건 — `real_order_id` / `kis_order_id` /
  `api_key` / `secret` / `account_number` 등 차단 유지
- audit details whitelist (6 키, 모두 forbidden 미포함):
  - `classification` (SUBMITTED/REJECTED/TIMEOUT/NETWORK_ERROR/UNKNOWN)
  - `dry_run` (boolean — real path 항상 False)
  - `symbol` / `side` / `quantity`
  - `broker_order_no_hash_prefix` (16자 hex, SUBMITTED 만)
- 실패 시에도 audit 1 행 보장 — 운영자가 retroactive recovery 시 timeline 추적 가능

### C.6 sensitive substring scrubbing

`_scrub()` helper — KIS msg 가 평문 6 substring 포함 시 case-insensitive `***` 치환:
`api_key` / `appsecret` / `secretkey` / `access_token` / `authorization` / `account_no`.
RealOrderRepository 의 `_check_error_message()` 검증 통과 보장 (raise 없음). 단위 테스트가
`access_token=ABC123 / api_key=DEF456` 포함 메시지가 DB 에 저장될 때 평문 0 건임을 단언.

### C.7 RealOrderRepository 헬퍼

`exists_non_failed_for_candidate(candidate_id) -> bool`:
- True: 동일 candidate 의 RealOrder 가 `{DRY_RUN, CREATED, SUBMITTED, PARTIALLY_FILLED, FILLED}` 중
  하나로 존재
- False: 0 건이거나 모두 `{FAILED, REJECTED, CANCELED}` 인 경우 (재시도 가능)
- 9 단위 테스트 (empty / non-failed parametrize 5 / failed-terminal parametrize 3)

### C.8 Constructor / DI

- `RealOrderExecutor(transport=None, real_transport_factory=None)`. 기본 생성자는 Fake-only —
  v0.16 회귀 0 건
- `_resolve_real_transport(settings)` 우선순위: factory(settings) → 명시 주입 non-Fake transport →
  None (gate 10 차단). Factory 가 Fake 반환 또는 raise 시 None
- 통합 테스트가 `HttpxKisOrderTransport(client=httpx.Client(transport=httpx.MockTransport(handler)))`
  주입 → respx-style end-to-end 검증

### C.9 anchor row before KIS call

`RealOrder(dry_run=False, status=CREATED)` 행은 transport.place_order() 호출 직전에 `session.flush()`
까지 완료. `_AnchorObservingTransport` (단위) + `httpx.MockTransport` handler (통합) 가 transport
호출 시점에 DB 의 `RealOrder.candidate_id == cid` row 수를 기록 — 두 케이스 모두 정확히 1 row 보장.
응답 손실 시 운영자가 RUNBOOK §5 수동 매칭 절차로 recovery 가능.

### C.10 AST + import 가드

- `real_order_executor.py` 직접 `httpx.Client` 0 건 / `httpx` import 0 건
- `requests` / `urllib` / `app.providers.kis` / `app.broker.kis_order_transport_real` 직접 import
  0 건 — transport 는 항상 DI 만 (`KisOrderClientInterface` 인자로 주입)

### C.11 게이트

- pytest **1995 → 2040 passed (+45)** / 회귀 0 건
- Alembic head: `0010_real_fills` (변경 0 건, 41 테이블 그대로)
- DB 모델 변경 0 건 / API 라우터 변경 0 건 / 프런트 변경 0 건
- 신규 pip 의존성 0 건 (`httpx` / `respx` / stdlib 만)
- 실 KIS API 호출 0 건 / 외부 네트워크 호출 0 건 — `httpx.MockTransport` + `respx` + `_StubTransport` 100%
- API key / app_secret / access_token / account_number / plaintext order_no 평문 저장·로그 0 건
- raw KIS response 저장·반환 0 건
- FULL_AUTO / SMALL_AUTO / 사용자 승인 없는 주문 0 건

### C.12 안전 정책 (Phase C 잠금 — Phase D 전)

- 기본 `RealOrderExecutor()` 는 여전히 Fake-only — Phase D ApprovalService wiring 까지는 production
  경로에서 실 transport 도달 0 건
- 운영자가 명시 주입 (`RealOrderExecutor(transport=HttpxKisOrderTransport(...))`) 한 인스턴스만
  real path 진입 가능. 테스트는 모두 respx-mocked client 주입
- candidate 상태는 real 실행 후에도 APPROVED 그대로 — RealOrder 상태가 source of truth (FILLED 등의
  자동 전이는 v1.1 자동 reconciliation 도입 후 검토)
- v1.0 paranoid default 9 종 그대로 유지 — `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` /
  `REAL_ORDER_DRY_RUN=true` 등

### C.13 태그

- `v1.0-real-order-executor-real` (예상 — Phase C 종료 시점에 발행)

---

## Phase D — Fill Sync actual transport + idempotent RealFill update ✅ (Phase 진행 중)

**목표 달성:** v0.16 mock-only `FillSyncService` → v1.0 **델타 기반 idempotent + 6 분류 + audit +
DRY_RUN skip**. `POST /api/real-orders/{order_id}/sync` (v1.0 SOLE RealOrder mutation, mutating
endpoint 합계 15 → 16). 실 KIS 호출 0건 (모든 통합 테스트는 `httpx.MockTransport` + DB).

### D.1 신규 / 갱신 파일

신규:
- `tests/integration/test_fill_sync_integration.py` (7 건) — `httpx.MockTransport` + DB end-to-end
- `tests/integration/test_real_order_sync_api.py` (10 건) — `POST /sync` HTTP 통합

수정:
- `app/broker/fill_sync_service.py` — v0.16 mock-only → v1.0 델타 기반 idempotent + 6 분류 + audit + DRY_RUN skip
- `app/data/repositories/real_fill.py` — `total_filled_quantity(real_order_id)` 헬퍼 추가
- `app/data/repositories/approval_audit_log.py` — `VALID_EVENT_TYPES` 3 종 추가
- `app/api/real_order_routes.py` — `POST /api/real-orders/{order_id}/sync` 신규 mutation +
  `_require_trading_safety_enabled` / `_require_kill_switch_off` helpers
- `app/api/schemas.py` — `RealOrderSyncRequest` + `RealOrderSyncResponse` 신규
- `tests/unit/test_fill_sync_service.py` — Phase D +24 + 기존 v0.16 테스트 갱신
- `tests/unit/test_safety_settings.py` — Phase D scope guard 5 종 전환
- `tests/integration/test_auth_security.py` — mutating endpoint count 15 → 16

### D.2 6-class 분류

| KIS 응답 | classification | RealOrder.status 전이 |
|---|---|---|
| `success=True, status=FILLED` | FULL | → FILLED |
| `success=True, status=PARTIALLY_FILLED` | PARTIAL | → PARTIALLY_FILLED |
| `success=True, status=PENDING` | NONE | (변경 없음) |
| `success=False, status=PENDING` | FAILED | (변경 없음) |
| `success=False, status=REJECTED` | REJECTED | → REJECTED |
| `success=False, status=CANCELED` | CANCELED | → CANCELED |
| transport raise | FAILED | (변경 없음) |

### D.3 델타 기반 idempotency

```
existing_total = RealFillRepository.total_filled_quantity(real_order_id)
kis_total      = _effective_kis_total(classification, response, total_qty)
delta          = kis_total - existing_total

delta > 0 → RealFill(quantity=delta, ...) 1행 + audit REAL_ORDER_FILL_SYNCED
delta == 0 → 신규 행 0건 (idempotent) + audit REAL_ORDER_FILL_SYNCED
delta < 0 → audit FILL_SYNC_NEGATIVE_DELTA + return FAILED, skipped_reason=NEGATIVE_DELTA
```

`_effective_kis_total()` 정책:
- FULL → `max(filled_quantity, total_qty)` (FakeKisOrderTransport 호환)
- PARTIAL → `filled_quantity`
- NONE/REJECTED/CANCELED/FAILED → 0

### D.4 DRY_RUN skip 정책

DRY_RUN RealOrder 또는 `dry_run=True` 인 경우 **transport 호출 없이** 즉시 NONE 반환
(`skipped_reason="DRY_RUN_ORDER_SKIPPED"`). v0.16 의 "FakeTransport 가 항상 FILLED 반환" 동작은
의도적으로 폐지 — 실 transport (HttpxKisOrderTransport) 가 fake order_no 로 KIS 를 조회하면
실 broker order_no 와 충돌할 위험을 차단. 단언 테스트 1 건이 `_BoomTransport` 로 transport 호출 0건
강제 검증.

### D.5 plaintext kis_order_no 정책

`sync_fills(session, real_order_id, *, kis_order_no_plaintext=None)` 의 옵션 파라미터.
운영자가 보유한 KIS 평문 주문번호를 in-memory 만 transport 에 전달 — `RealFill` / `RealOrder` /
audit details / 응답 본문 어디에도 저장 0건 (단언 통합 테스트 2 건).

### D.6 ApprovalAuditLog 연동

- 3 신규 event_type: `REAL_ORDER_FILL_SYNCED` / `REAL_ORDER_FILL_FAILED` / `FILL_SYNC_NEGATIVE_DELTA`
- audit details whitelist (모두 forbidden 13 종 미포함):
  - `classification` (FULL / PARTIAL / NONE / REJECTED / CANCELED / FAILED)
  - `dry_run` (boolean)
  - `symbol` / `side`
  - `delta` / `existing_total` / `kis_total` (negative-delta audit 만)
  - `kis_status` (FAILED audit 만)

### D.7 POST /api/real-orders/{order_id}/sync API

- v1.0 의 SOLE RealOrder mutation 라우터
- 게이트: AUTH + TRADING_SAFETY_ENABLED + KILL_SWITCH_OFF (v0.15 패턴)
- REAL_TRADING_ENABLED / KIS_ORDER_ENABLED 의도적 미강제 (사고 후 sync 가능 — RUNBOOK §6)
- `RealOrderSyncResponse` 7 필드 (real_order_id / real_order_status / fill_status / fills_added /
  fills_total / synced_at / message). 응답 본문 forbidden substring 0건
- 에러 코드: 200 / 401 / 404 / 405 (PUT/PATCH/DELETE) / 503 × 2 (TRADING_SAFETY_DISABLED, KILL_SWITCH_ON)

### D.8 게이트

- pytest **2040 → 2082 passed (+42)** / 회귀 0 건
- Alembic head: `0010_real_fills` (변경 0 건, 41 테이블 그대로)
- DB 모델 변경 0 건 / 프런트 변경 0 건
- 신규 pip 의존성 0 건 (`httpx` / `respx` / stdlib 만)
- 실 KIS API 호출 0 건 / 외부 네트워크 호출 0 건
- API key / app_secret / access_token / account_no / plaintext order_no 평문 저장·로그·응답 0 건
- raw KIS response 저장·반환 0 건
- 자동 polling scheduler job 0 건 / Reconciliation 0 건 (모두 v1.1 이연)
- mutating endpoint count: 15 → 16

### D.9 안전 정책 (Phase D 잠금 — Phase E 전)

- `POST /sync` 는 **수동 트리거 only** — 자동 폴링 잡 0건 (RUNBOOK §6.0)
- DRY_RUN RealOrder 는 transport 호출 0건 — 실 KIS 의 fake order_no 충돌 차단
- plaintext order_no 는 in-memory transport 통과만 — 모든 영속화 layer (DB / audit / 응답) 에서 0건
- v1.0 paranoid default 9 종 그대로 유지

### D.10 태그

- `v1.0-fill-sync-real` (예상 — Phase D 종료 시점에 발행)

---

## Phase E — Runbook / UI status polish / v1.0-final release ⏳ (대기)

상세: PLAN-0017 Phase E. 15 번째 화면 강화 (RealTradingModeBanner / Sync Fill 버튼) +
RELEASE_NOTES_v1.0 본문 마감 + RUNBOOK 최종 + 4 게이트 확인.

---

## v1.0 핵심 정책 (cycle-wide, 잠정)

- **paranoid default 9 종 유지** — `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` /
  `REAL_ORDER_DRY_RUN=true` / `MAX_REAL_ORDER_AMOUNT=100_000` /
  `MAX_REAL_DAILY_ORDER_AMOUNT=1_000_000` / `KILL_SWITCH_ENABLED=true` /
  `TRADING_SAFETY_ENABLED=false` / `APPROVAL_REQUIRED=true` / `PAPER_TRADING_ENABLED=false`
- **실 KIS 호출은 `HttpxKisOrderTransport` 만** (Phase B 부터 도입) — 모든 테스트에서
  `respx` mock + monkeypatch 가드, 실 KIS 호출 0 건
- **사용자 승인 없는 주문 0 건** — `OrderCandidate(status=APPROVED)` 만 RealOrderExecutor 진입
- **소액 / 일일 한도 강제** + **중복 주문 가드** (게이트 9, Phase C)
- **API key / secret / app_key / app_secret / access_token / account_number 평문 0 건**
- **raw KIS response 저장 0 건** — `RealOrder` / `RealFill` 모든 필드에서 금지
- **mutation 라우터 1 건 신규** (`POST /api/real-orders/{id}/sync`, Phase D) — KillSwitch +
  TradingSafety + AUTH 3 중 게이트 (v0.15 패턴)
- **Alembic revision 0 건** — 기존 schema 재사용 (델타 기반 idempotency)
- **신규 pip 의존성 0 건**
- **Reconciliation 0 건** — v1.1 이연
- **자동 폴링 잡 0 건** — Fill Sync 는 수동 트리거만
- **FULL_AUTO / SMALL_AUTO / 자동매매 0 건** — 본 프로젝트 명시 금지 정책 그대로

---

## v1.1+ 후보 (참고)

- Reconciliation (`reconciliation_runs` / `reconciliation_mismatches` 신규 + Alembic 1~2 건) +
  자동 Fill Sync 폴링 잡 + PreTradeRiskEngine 신규 룰 (호가 jump / 시장 시간 외 / 종목당 일일 한도 / 연속 실패)
- `submitted_at` / `filled_at` timestamps + `kis_request_id_hash` (Alembic 1 건)
- `RealOrder` 운영 화면 actionable CTA ("Cancel" 버튼)
- 운영 모니터링 통합 (`RealOrder` 상태 변화 → Prometheus / Grafana / Telegram)
- ScoringEngine 본 weight 보강 (v0.13 ProviderScorePolicy 데이터 누적 6 개월+ 후)

자세한 분류: [`ROADMAP.md`](./ROADMAP.md) v1.1+ 후보 절.
