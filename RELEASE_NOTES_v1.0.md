# Release Notes — v1.0 Small Approval Trading Release

마감 태그: `v1.0-final`
마감 일자: **2026-05-09 (Asia/Seoul)**
기준 태그: `v0.16-final` (HEAD `2d262d5`, pytest 1905 / vitest 214 / e2e 24 / build 그린)

---

## 핵심 요약

v1.0 은 v0.1~v0.16 누적 안전 인프라 위에서 **소액·승인 기반 첫 실 KIS 주문 실행 경로**를
구축한 사이클입니다. 자동 진입은 **0건** — 운영자가 `.env` 에서 명시 활성화 + 사용자가 화면에서
명시 승인 + 10-gate safety chain + KillSwitch + 일일/회당 한도가 모두 통과될 때만 1 건씩 실
주문이 가능합니다. FULL_AUTO / SMALL_AUTO / 사용자 승인 없는 주문은 v1.0 에서도 **0건 유지**.

채택 시나리오: **Scenario X — Small Approval Trading Release**
(Reconciliation 은 v1.1 이연. SMALL_AUTO 는 본 프로젝트 명시 금지 정책으로 기각.)

| 게이트 | 기준 (v0.16-final) | 마감 (v1.0-final) | 변동 |
|---|---|---|---|
| backend pytest | 1905 | **2082** | +177 |
| frontend vitest | 214 | **225** | +11 |
| frontend build | 그린 | 그린 | — |
| Playwright e2e | 24 | **25** | +1 |
| Alembic head | `0010_real_fills` (41 테이블) | `0010_real_fills` (41 테이블) | **변경 0건** |
| DB 모델 변경 | — | **0건** | — |
| 신규 pip 의존성 | — | **0건** | — |

전체 v1.0 사이클의 5 Phase 누적 태그:
`v1.0-operating-checklist` → `v1.0-kis-real-transport` → `v1.0-real-order-executor-real` →
`v1.0-fill-sync-real` → **`v1.0-final`**.

관련 계획: [`PLANS.md`](./PLANS.md) `PLAN-0017` /
관련 작업 목록: [`TASKS.md`](./TASKS.md) v1.0 Phase A~E /
운영 절차: [`RUNBOOK_REAL_TRADING.md`](./RUNBOOK_REAL_TRADING.md) §1~9

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

## Phase A — Real trading operating checklist + final safety gates ✅

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

## Phase B — KIS real order transport with mock-only tests ✅

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

## Phase C — RealOrderExecutor real path behind strict gates ✅

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

## Phase D — Fill Sync actual transport + idempotent RealFill update ✅

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

## Phase E — Runbook / UI status polish / v1.0-final release ✅

**목표 달성:** v0.16 read-only `/real-orders` 화면을 **RealTradingModeBanner + 수동 Sync Fill
버튼**까지 포함하는 v1.0 운영 화면으로 강화. RELEASE_NOTES / RUNBOOK §8 / README / PROJECT_STATUS /
ROADMAP / ARCHITECTURE / TESTING / API_SPEC / INTEGRATION_RUNBOOK 모두 v1.0-final 기준으로 마감.

### E.1 신규 / 갱신 파일

backend (최소 변경 — bool 필드 5종만 노출):
- `app/api/schemas.py` — `SettingsResponse` 에 `trading_safety_enabled` / `kill_switch_enabled` /
  `real_trading_enabled` / `kis_order_enabled` / `real_order_dry_run` 5 신규 필드 추가
- `app/api/routes.py` — `/api/settings` 응답 builder 에 위 5 필드 wiring 추가
  (secret / api_key / account_no 등 평문 노출 0건 유지)

frontend (15번째 화면 v1.0 운영 강화):
- `frontend/src/api/types.ts` — `SettingsResponse` 5 신규 bool 필드 +
  `RealOrderSyncRequest` / `RealOrderSyncResponse` / `RealOrderFillStatus` 신규 타입
- `frontend/src/api/realOrders.ts` — `syncRealOrder(orderId, body?)` 함수 추가
- `frontend/src/hooks/useRealOrders.ts` — `useSyncRealOrder` mutation hook 추가
  (real-orders namespace invalidate, retry: false)
- `frontend/src/pages/RealOrders/index.tsx`:
  - 기존 `RealTradingSafetyBanner` → `RealTradingModeBanner` 로 교체
    (settings 5 bool 플래그 badge + 4 종 mode badge: REAL TRADING ENABLED / DRY-RUN /
    KILL SWITCH ON / 전이 상태)
  - `SyncFillButton` 신규 — 4 disabled 조건 (DRY_RUN / KILL_SWITCH_ENABLED / TRADING_SAFETY_DISABLED /
    terminal status) + isPending spinner + success / error 메시지
  - 라벨은 "체결 동기화" / "Sync Fill" 만 (forbidden CTA 0건)
- `frontend/src/components/layout/Sidebar.tsx` — footer "v0.16 Real Order Integration Skeleton" →
  "v1.0 Small Approval Trading Release" + "v0.16 dashboard" → "v1.0 dashboard"
- `frontend/src/tests/RealOrders.test.tsx` — Phase E 테스트 +11 건 (banner 5 flag badge / mode 4 종 /
  Sync 버튼 가시성 + disabled 4 케이스 / mutation happy / mutation 503 error / forbidden CTA / plaintext)
- `frontend/src/tests/mswServer.ts` — `/api/settings` 응답에 5 신규 paranoid bool +
  `POST /api/real-orders/:orderId/sync` 기본 503 mock 추가

e2e:
- `frontend/e2e/fixtures/apiMocks.ts` — `SETTINGS_SAFE` 에 5 bool +
  `POST /api/real-orders/:id/sync` → 503 핸들러 추가
- `frontend/e2e/dashboard.spec.ts` — 기존 Real Orders e2e 강화 (5 flag badge + mode badge 단언) +
  신규 Sync Fill 버튼 e2e 1 건 (paranoid 기본 → disabled, KILL_SWITCH_ENABLED reason 단언,
  forbidden CTA 0건)

### E.2 RealTradingModeBanner

`useSettings()` 로 `/api/settings` 의 5 bool 을 구독하고 다음 4 mode 중 하나를 표시:

| 조건 | mode 라벨 | 색상 |
|---|---|---|
| `kill_switch_enabled=true` 또는 `trading_safety_enabled=false` | `KILL SWITCH ON` | amber |
| `real_order_dry_run=true` (kill switch off + safety on) | `DRY-RUN` | blue |
| `real_trading_enabled=true` + `kis_order_enabled=true` + `dry_run=false` | `REAL TRADING ENABLED` | red |
| 그 외 일부 게이트만 충족 | `전이 상태 (게이트 일부 미충족)` | yellow |

5 flag badge 는 각 환경변수 이름 그대로 표시 (`TRADING_SAFETY_ENABLED=true/false` 등). 안전한 값일 때
emerald 배지, 위험한 값일 때 red 배지로 시각 구분.

### E.3 SyncFillButton

4 disabled 조건 (모두 reason 메시지 동시 표시):
1. `order.dry_run === true` → "DRY_RUN 주문은 transport 호출 없이 skip 됩니다 (Phase D 정책)."
2. `settings.kill_switch_enabled === true` → "KILL_SWITCH_ENABLED=true 상태에서는 sync 가 차단됩니다."
3. `settings.trading_safety_enabled === false` → "TRADING_SAFETY_ENABLED=false 상태에서는 sync 가 차단됩니다."
4. `order.status` ∈ {FILLED, CANCELED, REJECTED, FAILED} → "이미 terminal 상태 (X) — sync 가 불필요합니다."

mutation 정책:
- `useSyncRealOrder` retry: false (운영자 trigger 만 — RUNBOOK §6 manual followup)
- onSuccess → `real-orders` namespace invalidate (table + detail panel 자동 refetch)
- isPending → spinner + button disabled
- isError → 빨강 메시지 ("체결 동기화 실패 — 잠시 후 다시 시도하거나 RUNBOOK §6 절차를 확인하세요.")
- isSuccess → emerald 메시지 (response.message echo, plaintext order_no 미포함)

### E.4 forbidden CTA / 평문 미노출 검증

- vitest §23 forbidden CTA scan: "실주문 실행" / "주문 전송" / "place real order" / "자동매매" /
  "FULL_AUTO" / "SMALL_AUTO" 모든 actionable element 에서 0건 단언
- vitest §24 plaintext settings substring scan: `kis_app_key` / `kis_app_secret` / `kis_account_no`
  의 marker (`PLAINTEXT-APP-KEY-99999` 등) 가 페이지 텍스트에 0건 단언
- e2e Real Orders forbidden DOM token 단언 확장: `broker_order_no` / `broker_order_id` /
  `kis_order_id` 추가 — 총 14 종 0 건 단언
- e2e Sync Fill 버튼 e2e 1 건이 paranoid 기본 (kill_switch=true) 에서 disabled 단언 +
  reason 메시지 "KILL_SWITCH_ENABLED" 포함 단언 + forbidden CTA 6 종 0 건 단언

### E.5 문서 마감

- `RELEASE_NOTES_v1.0.md` (본 문서) — 초안 헤더 → 마감 헤더 + Phase A~E 섹션 정리 + 4 게이트 변동 표
- `RUNBOOK_REAL_TRADING.md` — §8 운영 체크리스트 표시 정리 (5 카테고리 / 25 항목) + v1.0 마감 표시
- `README.md` — v1.0-final 배너 / 누적 사이클 표 / 회귀 기준선 갱신
- `PROJECT_STATUS.md` — §0 v1.0 시작 선언 → 마감 선언 갱신 (이전 §0 → §0-1 강등)
- `ROADMAP.md` — v1.0 행 ✅ 마감 + v1.1 (Reconciliation + 자동 Fill Sync 폴링) 후보 정리
- `TASKS.md` — Phase E 체크박스 전체 완료
- `ARCHITECTURE.md` — v1.0-final 흐름 마감 + 15 번째 화면 강화 흐름 반영
- `TESTING.md` — 최종 게이트 갱신 (2082 / 225 / 25 / 그린)
- `API_SPEC.md` — `POST /api/real-orders/{id}/sync` + Settings 5 bool 노출 명시
- `INTEGRATION_RUNBOOK.md` — v1.0 운영 절차는 RUNBOOK_REAL_TRADING.md 참조 명시

### E.6 게이트 (Phase E 종료 = v1.0-final 직전)

- backend pytest **2082 passed** (Phase D 와 동일, Phase E 는 backend 테스트 변경 0 건)
- frontend vitest **214 → 225 passed (+11)**
- frontend build 그린 (`tsc --noEmit && vite build`)
- Playwright e2e **24 → 25 passed (+1)**
- Alembic head: `0010_real_fills` (변경 0 건, 41 테이블 그대로)
- DB 모델 변경 0 건 / 신규 pip 0 건
- 실 KIS API 호출 0 건 / 외부 네트워크 호출 0 건
- 자동 polling job 0 건 / Reconciliation 0 건 (모두 v1.1 이연)
- forbidden CTA 0 건 / 평문 자격증명·order_no 0 건

### E.7 태그

- **`v1.0-final`** — Phase E 종료 + 모든 docs 마감 + 4 게이트 그린 후 발행

---

## v1.0 사이클 산출물 요약 (전체)

### 신규 모듈 / 파일

backend:
- `app/broker/kis_order_transport_real.py` (Phase B) — `HttpxKisOrderTransport` 첫 실 transport 구현체

frontend:
- `frontend/src/pages/RealOrders/` — 15번째 화면 (v0.16 신규, v1.0 강화)

문서:
- `RUNBOOK_REAL_TRADING.md` (Phase A) — 실거래 운영 체크리스트 §1~9
- `RELEASE_NOTES_v1.0.md` (Phase A 초안 → Phase E 본 마감)

테스트:
- `tests/unit/test_kis_order_transport_real.py` (Phase B, 53 건)
- `tests/integration/test_real_order_executor_integration.py` (Phase C, 8 건)
- `tests/integration/test_fill_sync_integration.py` (Phase D, 7 건)
- `tests/integration/test_real_order_sync_api.py` (Phase D, 10 건)

### 신규 mutation 라우터 (1 건)

- `POST /api/real-orders/{order_id}/sync` (Phase D) — 수동 Fill Sync 트리거.
  AUTH + TRADING_SAFETY_ENABLED + KILL_SWITCH_OFF 3중 게이트.
  mutating endpoint count: 15 → **16**.

### 신규 ApprovalAuditLog event_type (5 종)

- `REAL_ORDER_SUBMITTED` (Phase C) / `REAL_ORDER_FAILED` (Phase C)
- `REAL_ORDER_FILL_SYNCED` (Phase D) / `REAL_ORDER_FILL_FAILED` (Phase D) /
  `FILL_SYNC_NEGATIVE_DELTA` (Phase D)

### 신규 Settings 필드 (4 + 0)

- Phase B: `kis_order_base_url` / `kis_order_place_timeout_s` / `kis_order_query_timeout_s` /
  `kis_order_cancel_timeout_s` (4 종)
- Phase E: 신규 Settings 필드 0 건 — 기존 5 bool 을 `/api/settings` 응답에만 추가 노출

---

## 안전 정책 (cycle-wide)

- **paranoid default 9 종** 그대로 유지 — `REAL_TRADING_ENABLED=false` /
  `KIS_ORDER_ENABLED=false` / `REAL_ORDER_DRY_RUN=true` / `MAX_REAL_ORDER_AMOUNT=100_000` /
  `MAX_REAL_DAILY_ORDER_AMOUNT=1_000_000` / `KILL_SWITCH_ENABLED=true` /
  `TRADING_SAFETY_ENABLED=false` / `APPROVAL_REQUIRED=true` / `PAPER_TRADING_ENABLED=false`
- **실 KIS 호출은 `HttpxKisOrderTransport` 만** — 모든 테스트에서 `respx` mock + `httpx.MockTransport` +
  monkeypatch + `_StubTransport` + `_ScriptedTransport` 6중 가드. 실 KIS 호출 0 건
- **사용자 승인 없는 주문 0건** — `OrderCandidate(status=APPROVED)` 만 RealOrderExecutor 진입.
  1 후보 = 1 사용자 승인 = 1 실주문 원칙
- **소액 / 일일 한도 강제** + **중복 주문 가드** + **transport 가용성 검사** (10-gate)
- **API key / app_secret / access_token / account_no / plaintext order_no 평문 저장·로그·응답·렌더링 0건**
- **raw KIS response 저장·반환 0건** — whitelist 필드만 immutable 데이터클래스 / 스키마로 재투영
- **mutation 라우터 1 건만 신규** (`POST /sync`) — KillSwitch + TradingSafety + AUTH 3중 게이트
- **Alembic revision 0건** — 기존 schema 재사용 (델타 기반 idempotency)
- **신규 pip 의존성 0건** — `httpx` (기존) / `respx` (기존 dev) / stdlib 만
- **자동 polling 잡 0건** — Fill Sync 는 수동 트리거만 (Phase D `POST /sync`)
- **Reconciliation 0건** — v1.1 이연
- **FULL_AUTO / SMALL_AUTO 0건** — 본 프로젝트 명시 금지 정책
- **DART/RSS/Prometheus/Provider Data Ingestion/Score Policy/Paper Trading default OFF 유지**

---

## 실 KIS 호출 테스트 정책

전체 v1.0 사이클에서 **실 KIS API 호출 0 건**. 모든 테스트는 다음 6중 가드로 outbound traffic 차단:

1. **`respx` mock** — Phase B `HttpxKisOrderTransport` 단위 테스트 53 건 모두 사용
2. **`httpx.MockTransport(handler)`** — Phase C / D 통합 테스트가 transport 주입형으로 사용
3. **`monkeypatch`** — v0.10 부터 `httpx.Client` 직접 생성 차단 가드
4. **`_StubTransport`** — Phase C 단위 테스트의 programmable `KisOrderClientInterface` 구현
5. **`_ScriptedTransport`** — Phase D 단위 테스트의 5 분류 시뮬레이션 transport
6. **AST guard** — broker / executor / fill_sync 어디에서도 모듈-레벨 `import httpx` 0 건

CI / 로컬 / 운영 환경 모두에서 `respx` 가 모든 KIS endpoint 패턴을 가로채므로, 잘못해서 실
endpoint 가 호출되어도 traffic 이 외부로 나가지 않음.

---

## 알려진 한계 (v1.0 → v1.1 이연)

1. **plaintext kis_order_no 자동 보존 부재** — `RealOrder.broker_order_no_hash` 만 영속화하므로,
   FillSyncService 가 KIS 에 query_fill_status 를 호출할 때는 운영자가 plaintext 를 별도로 보유하고
   `POST /sync {kis_order_no: <plaintext>}` 형태로 in-memory 전달해야 함. 자동 plaintext 영속화는
   v1.1 의 idempotency key 컬럼 추가 후 검토 (보안 정책 함께 재검토).
2. **자동 Fill Sync 폴링 부재** — 운영자가 화면에서 "체결 동기화" 버튼을 명시 클릭해야 KIS 응답이
   반영됨. 자동 폴링 잡은 v1.1.
3. **Reconciliation 부재** — 내부 RealOrder/RealFill vs KIS 잔고 비교 로직 없음. mismatch 발견 시
   운영자가 수동으로 RUNBOOK §6 절차 진행.
4. **multi-broker 미지원** — KIS 외 다른 broker 추가 시 `KisOrderClientInterface` 의 일반화가 필요.
   현재는 KIS-only.
5. **frontend 에서 plaintext kis_order_no 입력 UI 부재** — Phase E 의 `useSyncRealOrder` mutation 은
   plaintext body 를 받을 수 있지만, UI 는 빈 body 만 전송. plaintext 입력 폼은 v1.1 에서 별도 보안
   검토 후 추가.
6. **실주문 실패 복구 자동화 부재** — `RealOrder.status=FAILED` 발생 시 운영자가 RUNBOOK §5 절차로
   수동 매칭 / 재시도 결정. 자동 복구 / 재시도 정책은 v1.1.
7. **운영 알림 (Telegram / Slack) 부재** — `REAL_ORDER_SUBMITTED` / `_FAILED` 등 audit 이벤트가
   외부 알림으로 자동 발송되지 않음. 운영자가 화면 / 로그 확인 책임.

---

## v1.1 후보

본격 진입 전 별도 보안·컴플라이언스 사이클을 거친다. 우선순위:

1. **Reconciliation 엔진** — 내부 `RealOrder` / `RealFill` vs KIS 잔고/체결 비교. mismatch 분류
   (수량 / 평단 / 미체결 / 누락) + 자동 KillSwitch 트리거 옵션.
   `reconciliation_runs` / `reconciliation_mismatches` 신규 테이블 (Alembic 1~2건).
   진입 전제: v1.0 운영 4 주 + 실주문 ≥10 건 누적
2. **자동 Fill Sync 폴링 잡** — `SUBMITTED` 상태 RealOrder 가 N 분 이상 갱신 없으면 자동 sync.
   `KIS_ORDER_ENABLED=true` 시에만 동작
3. **운영 알림** — `RealOrder` 상태 변화 → Prometheus metric + Grafana panel + Telegram 알림
   (DRY_RUN 정책 유지)
4. **실주문 실패 복구 고도화** — TIMEOUT / NETWORK_ERROR 의 자동 후속 sync (재시도 아님 — 응답
   확인 자동화) + KIS HTS 매칭 도구
5. **PreTradeRiskEngine 신규 룰** — 호가 jump 검사 / 시장 시간 외 차단 / 종목당 일일 한도 / 연속
   실패 종목 차단
6. **multi-broker 후보** — `KisOrderClientInterface` 일반화 + 다른 broker 어댑터 추가 가능 구조
   (현재는 KIS 전용 transport / endpoint 가정)
7. **`submitted_at` / `filled_at` 컬럼 + `kis_request_id_hash` (idempotency key)** — Alembic 1건
8. **frontend kis_order_no 입력 UI** — 보안 검토 후 입력 마스킹 + 즉시 폐기 + audit 강화
9. **다중 사용자 / RBAC / OAuth** — 단일 운영자 → 권한 분리

---

## 누적 태그 정리

| 사이클 | 태그 | 마감 일자 |
|---|---|---|
| v1.0 Phase A | `v1.0-operating-checklist` | 2026-05-09 |
| v1.0 Phase B | `v1.0-kis-real-transport` | 2026-05-09 |
| v1.0 Phase C | `v1.0-real-order-executor-real` | 2026-05-09 |
| v1.0 Phase D | `v1.0-fill-sync-real` | 2026-05-09 |
| **v1.0 Phase E** | **`v1.0-final`** | **2026-05-09** |

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
