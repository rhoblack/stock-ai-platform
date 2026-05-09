# RUNBOOK_REAL_TRADING.md

> 본 문서는 v1.0 **Small Approval Trading Release** 의 운영 진입·차단·복구 절차를
> 정리한다. 실 KIS 주문은 v0.1~v0.16 의 모든 dry-run 인프라가 검증된 위에서만, 그리고
> 운영자가 본 문서의 §1 전제 조건을 모두 통과한 다음에만 활성화 가능하다.
>
> **핵심 원칙: 1 후보 = 1 사용자 승인 = 1 실주문.** 자동 진입 / FULL_AUTO / SMALL_AUTO
> / 사용자 승인 없는 주문은 본 프로젝트 명시 금지 정책이다 — 본 Runbook 의 어떤 절차도
> 그것을 우회하지 않는다.
>
> 관련 문서:
> [`PLANS.md`](./PLANS.md) `PLAN-0017` /
> [`TASKS.md`](./TASKS.md) v1.0 Phase A /
> [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) §0 /
> [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) §0~17 /
> [`SECURITY.md`](./SECURITY.md).

---

## §1. 실거래 활성화 전제 조건

본 절의 9 항목 중 **단 하나라도 충족되지 않으면 § 2 의 `.env` 활성화 절차에 진입하지
않는다.** 항목은 운영자 (사람) 가 점검하는 체크리스트이며, 자동화하지 않는다.

| # | 전제 조건 | 검증 방법 |
|---|---|---|
| 1 | v0.16-final 또는 그 이후 태그 기준 dry-run 운영을 **4 주 이상** 무사고로 통과했다 | `git log --tags --since="4 weeks ago"` + `RealOrder` (모두 `is_dry_run=True`) 누적 행 ≥ 1 |
| 2 | KIS Open API **개인용 / 실 거래 계정** 라이선스가 명시적으로 발급되어 있다 (모의투자 X) | KIS 운영 콘솔 / 라이선스 메모. `KIS_USE_PAPER=false` 사전 검증 |
| 3 | 운영자 책임·면책 정책이 문서로 합의되어 있다 — 본 Runbook §8 의 운영 체크리스트가 채워져 있다 | 운영 체크리스트 §8 모두 ✅ |
| 4 | 자본 한도 정책이 명문화되어 있다 — `MAX_REAL_ORDER_AMOUNT` (회당) ≤ 100,000 KRW, `MAX_REAL_DAILY_ORDER_AMOUNT` (일일 누적) ≤ 1,000,000 KRW 권장 | `.env` 검토 + Settings `__post_init__` 통과 |
| 5 | 비상 중지 채널이 1 개 이상 준비되어 있다 — `.env` 의 `KILL_SWITCH_ENABLED=true` 즉시 적용 가능한 SSH/콘솔 접근권 + `service` 또는 `docker compose restart` 권한 | 비상 시뮬레이션 1 회 (실 활성화 전) |
| 6 | `AUTH_ENABLED=true` 가 적용되어 있고, 단일 운영자 계정만 등록되어 있다 (`User` 테이블 1 행) | `GET /api/auth/me` 200 / 다른 user 0 |
| 7 | `TRADING_SAFETY_ENABLED` / `KILL_SWITCH_ENABLED` / `APPROVAL_REQUIRED` 의 v0.15 안전 layer 가 paper 운영 (`/approvals`) 으로 검증되어 있다 — 승인된 후보가 `SimulationBroker` 에서 정상 실행되는 것을 확인했다 | v0.15 운영 1 주 + `EXECUTED_PAPER` 후보 ≥ 1 |
| 8 | KillSwitch + PreTradeRiskEngine 재검사가 Executor 진입 시 실제로 작동한다는 것을 dry-run 으로 검증했다 — `RealOrderExecutor` 의 8-gate (v0.16) 가 현재 구현으로 모두 차단/통과 분기를 보였다 | `RealOrder` (`is_dry_run=True`) 다양한 reason 누적 |
| 9 | API key / app_secret / access_token / account_number 등 비밀값이 평문 로그·응답·DB 어디에도 존재하지 않는다 (v0.9 / v0.11 의 `SensitiveQueryStringFilter` + v0.16 의 `mask_sensitive_order_payload()` + `broker_order_no_hash` SHA-256 정책) | `grep -E "app_key|app_secret|access_token" logs/` 0 건 / `RealOrder` `broker_order_no_hash` 만 저장 확인 |

> ⚠️ **9 항목 중 하나라도 ✅ 가 아니면, 다음 절 §2 의 `.env` 활성화는 진행하지
> 않는다.** v0.16 의 dry-run 경로로 복귀하여 부족한 항목을 보강한 뒤 재시도한다.

### §1.10 v1.0 Phase C real-path 10-gate 체인 (참고)

`RealOrderExecutor.execute()` 가 `real_order_dry_run=False` 시 통과해야 하는 10-gate. 본 절의 § 1
9 전제 조건 (사람) 과는 별개로, 코드 레벨에서 **실주문 1 건마다** 통과되어야 하는 안전 검증.

| # | gate | 차단 reason | 데이터 소스 |
|---|---|---|---|
| 1 | candidate found + APPROVED | `CANDIDATE_NOT_FOUND` / `NOT_APPROVED` | DB |
| 2 | non-failed RealOrder 부재 | `DUPLICATE_REAL_ORDER` (real) / `ALREADY_EXECUTED` (dry) | DB |
| 3 | `kill_switch_enabled=False` | `KILL_SWITCH_ON` | Settings |
| 4 | `trading_safety_enabled=True` (v1.0 신규) | `TRADING_SAFETY_DISABLED` | Settings |
| 5 | `real_trading_enabled=True` | `REAL_TRADING_DISABLED` | Settings |
| 6 | `kis_order_enabled=True` | `KIS_ORDER_DISABLED` | Settings |
| 7 | 회당 한도 통과 | `AMOUNT_EXCEEDS_PER_ORDER_CAP` | Settings + candidate |
| 8 | KST 일일 누적 통과 | `AMOUNT_EXCEEDS_DAILY_CAP` | DB aggregate |
| 9 | `PreTradeRiskEngine.evaluate()` | `RISK_REJECTED` | DB |
| 10 | non-Fake transport 가용 (real path only, v1.0 신규) | `TRANSPORT_UNAVAILABLE` | DI |

dry-run 은 ①~⑨ 만, real path 는 ①~⑩ 모두. Gate ordering 은 빠른 (Settings) → 느린 (DB) → 가장
비싼 (RiskEngine) 순서이므로 cost-aware short-circuit. 게이트 모두 통과 후:

- dry-run → `FakeKisOrderTransport.place_order()` → `RealOrder(dry_run=True, status=DRY_RUN)`
- real → `RealOrder(dry_run=False, status=CREATED)` 선저장 + `flush()` → 실 transport place_order →
  분류 → SUBMITTED 또는 FAILED + ApprovalAuditLog 1 행

---

## §2. `.env` 활성화 절차

전제 조건 §1 9 항목이 모두 ✅ 가 된 다음에만 진행한다. 활성화는 **단계적**으로 진행하며,
각 단계에서 dry-run 검증 1 회를 추가로 통과해야 다음 단계로 넘어간다.

### 2.1 활성화 키

운영 진입을 위해 `.env` 가 가져야 하는 9 키 (모두 명시 — default 활용 금지):

```dotenv
AUTH_ENABLED=true
TRADING_SAFETY_ENABLED=true
KILL_SWITCH_ENABLED=false
APPROVAL_REQUIRED=true
REAL_TRADING_ENABLED=true
KIS_ORDER_ENABLED=true
REAL_ORDER_DRY_RUN=false
MAX_REAL_ORDER_AMOUNT=100000
MAX_REAL_DAILY_ORDER_AMOUNT=1000000
```

### 2.2 단계적 활성화

| 단계 | 동작 | 점검 |
|---|---|---|
| 1 | `AUTH_ENABLED=true` 만 활성화하고 운영자 계정으로 로그인 1 회 | `GET /api/auth/me` 200 |
| 2 | `TRADING_SAFETY_ENABLED=true` + `KILL_SWITCH_ENABLED=false` (v0.15 paper 활성화) — `/approvals` 에서 후보 1 건 승인 → `EXECUTED_PAPER` | `RealOrder` 행 0 변화 / `VirtualOrder` 정상 |
| 3 | `REAL_TRADING_ENABLED=true` (단, `REAL_ORDER_DRY_RUN=true` 유지) — Executor 가 dry-run 경로로 진입 | `RealOrder(is_dry_run=True, status=DRY_RUN)` 1 행 |
| 4 | `KIS_ORDER_ENABLED=true` (단, `REAL_ORDER_DRY_RUN=true` 유지) — Executor 가 transport 가용성 게이트 통과 | `RealOrder(is_dry_run=True)` 행 누적 (실 호출 0건) |
| 5 | **마지막**: `REAL_ORDER_DRY_RUN=false` 활성화 — 다음 1 후보 승인 시 실 KIS 호출 시작 | `RealOrder(is_dry_run=False, status=PENDING→SUBMITTED)` 1 행 + `broker_order_no_hash` set |

> **단계 5 진입 직후 첫 1 건은 운영자가 직접 KIS HTS 에서 주문 체결 결과를 수동
> 확인한다.** 응답이 손실되었거나 `RealOrder.status=FAILED` 라면 § 5 절차로 진입.

### 2.3 활성화 직후 점검

활성화 후 5 분 이내:

- `GET /api/real-orders` 가 200, `is_dry_run=false` 행 1 건 반환
- `GET /api/real-orders/{id}` 의 `broker_order_no_hash` 가 64 자 SHA-256 hex
- 응답 본문 / 로그에 `app_key` / `app_secret` / `access_token` / `account_no` 평문 0 건
- `GET /api/settings` 응답에 `api_key` / `secret` 류 키 0 건

---

## §3. KillSwitch 사용 절차

KillSwitch 는 **모든 mutation 을 즉시 503 으로 만드는 master block** 이다. 활성 시
`/api/approvals/*` mutation, `/api/paper/orders` mutation, `/api/real-orders/{id}/sync`
모두 차단된다 (v0.15 / v0.14 / v1.0 정책 일관). 진행 중인 RealOrder 자체는 영향 없음 —
KillSwitch 는 신규 진입을 막고, 진행 중 주문은 § 5 의 수동 절차로 처리.

### 3.1 ON 절차 (즉시 차단)

```bash
# .env 에서 한 줄만 변경 후 즉시 적용
KILL_SWITCH_ENABLED=true

# Settings 는 lru_cache 라 프로세스 재시작이 필요할 수 있다
docker compose restart backend
# 또는
systemctl restart stock-ai
```

또는 운영 콘솔에서 `KILL_SWITCH_ENABLED=true` env 만 export 후 service reload.
재시작 직후 `POST /api/approvals/{id}/approve` 가 503 / `POST /api/real-orders/{id}/sync`
가 503 이면 정상.

### 3.2 OFF 절차 (정상 복귀)

KillSwitch 를 OFF 하기 전, 다음 4 항목을 모두 점검:

- 직전 사고의 root cause 가 명문으로 정리되어 있다
- 정리된 root cause 가 코드 / 한도 / 운영 절차 중 어디서 막혔어야 했는지 결정되어 있다
- 코드 변경이 필요한 경우는 **OFF 전에** 배포 완료
- 한도 변경이 필요한 경우는 **OFF 전에** `MAX_REAL_*` 갱신

```bash
KILL_SWITCH_ENABLED=false
docker compose restart backend
```

OFF 직후 `GET /api/real-orders` 200 + 비-FAILED RealOrder 가 정상 표시 + 새 후보 승인이
정상적으로 진행되는지 1 건 dry-run 으로 재확인.

> ⚠️ KillSwitch 가 OFF 인데 `REAL_ORDER_DRY_RUN=true` 라면 Executor 는 자동으로
> dry-run 경로 fallback. 의도치 않게 실주문이 발생하지 않는다.

---

## §4. 비상 중지 절차

본 절은 `RealOrder` 가 **의도하지 않은 상태로 진행 중** 이거나, **체결 불일치가
의심**되거나, **외부에서 사고 보고**가 들어왔을 때 적용한다.

### 4.1 즉시 차단 (1 분 이내)

1. `.env` 에 `KILL_SWITCH_ENABLED=true` 적용 (§ 3.1) — **모든 mutation 차단**
2. `.env` 에 `KIS_ORDER_ENABLED=false` 적용 — 진행 중 KIS 호출이 있더라도 추가 호출 차단
3. `.env` 에 `REAL_ORDER_DRY_RUN=true` 적용 — 우발적 재진입 시 dry-run fallback 보장
4. 백엔드 프로세스 재시작 (Settings `lru_cache` flush)
5. 운영자가 KIS HTS 에 직접 로그인하여 미체결 주문 / 비정상 포지션 수동 확인

### 4.2 진행 중 RealOrder 처리 (5~30 분)

- `RealOrder(status=PENDING|SUBMITTED)` 행을 모두 조회
- 각 행의 `broker_order_no_hash` 와 KIS HTS 의 미체결 주문 목록을 1:1 비교
  (해시 비교 — 평문 매칭이 어렵다면 `RealOrder.created_at` 시각 + symbol + qty 로 1차 분류)
- 운영자가 KIS HTS 에서 미체결 주문을 **수동 취소** 또는 **수동 체결 확인**
- 그 다음 운영자 권한으로 `RealOrder.status` 를 수동 갱신:
  - 취소 확인 → `update_status('CANCELLED')` + `ApprovalAuditLog.append('REAL_ORDER_CANCELED_MANUAL', ...)` 1 행
  - 체결 확인 → `update_status('FILLED')` 또는 `'PARTIAL_FILLED'` + audit 1 행

### 4.3 정상 복귀 절차

§ 4.1 의 모든 환경변수를 다시 paranoid 로 둘 필요는 없다. 사고 정리 종료 후:

1. KIS HTS 잔고 = 내부 `RealOrder` / `RealFill` 합계 일치를 운영자가 확인
2. 사고 보고서 + audit log 1 행 작성 (`event_type='INCIDENT_RESOLVED'`)
3. § 3.2 의 KillSwitch OFF 절차 진행

---

## §5. 주문 실패 대응 절차

`RealOrder.status=FAILED` 가 발생한 경우. 원인은 **transport timeout / network error /
KIS 4xx / 응답 누락** 4 가지로 분류된다 (v1.0 Phase B `KisOrderResult` 5 분류 중 SUBMITTED / REJECTED
를 제외).

### 5.1 즉시 점검

- `RealOrder.error_message` (≤500자, 마스킹된 사유) 확인
- `ApprovalAuditLog` 의 `event_type='REAL_ORDER_FAILED'` 최근 행 1 건 확인
- 운영자가 KIS HTS 에서 동일 시간대 주문 이력을 **수동 조회**

### 5.2 분기 처리

v1.0 Phase C real path 는 KIS 응답을 5 분류 (SUBMITTED / REJECTED / TIMEOUT / NETWORK_ERROR /
UNKNOWN) 로 매핑하고, 비-SUBMITTED 4 분류 모두 `RealOrder.status=FAILED` + `error_code=<classification>` +
`ApprovalAuditLog(event_type='REAL_ORDER_FAILED', details={classification, dry_run, symbol, side, quantity})`
1 행을 자동 기록한다. 운영자가 보강할 분기는 다음과 같다.

| 상황 | 처리 |
|---|---|
| `RealOrder.error_code='REJECTED'` (HTTP 200 + rt_cd≠0 또는 4xx) | KIS 가 정의된 답을 줌. 신규 후보가 필요하면 candidate 를 EXPIRE 후 새로 만들 것. RealOrder 행은 그대로 FAILED 보존 |
| `RealOrder.error_code='TIMEOUT'` 또는 `NETWORK_ERROR` (응답 손실 가능) | KIS HTS 에서 **수동 조회**. 주문이 존재하지 않으면 `RealOrder.status=FAILED` 유지 + 운영자가 candidate 를 EXPIRE 후 신규 후보 작성. 주문이 존재하면 운영자 콘솔에서 `RealOrder.status` 를 적절히 수동 갱신 (`mark_submitted` / `update_status`) + audit 행 1 건 추가 |
| `RealOrder.error_code='UNKNOWN'` (HTTP 5xx 또는 parse 실패) | 운영자 KIS HTS 매칭 + 위와 동일한 수동 절차 |
| KIS HTS 에 해당 주문이 **존재하지 않음** | RealOrder 그대로 FAILED 유지. 동일 candidate 신규 RealOrder 생성은 자동 차단 — 게이트 2 (DUPLICATE_REAL_ORDER) 가 non-failed 활성 RealOrder 를 막음. 단 RealOrder 가 FAILED 상태이면 재시도가 자동 허용됨 (테스트로 보장) |
| KIS HTS 에 해당 주문이 **체결됨 / 미체결로 존재** | 응답 손실. 운영자가 직접 `RealOrder.status` 를 `SUBMITTED` 또는 `FILLED` 로 수동 갱신 + `ApprovalAuditLog.append('REAL_ORDER_RECONCILED_MANUAL', ...)` 1 행 (Phase D 또는 v1.1 에서 정식 event_type 추가 예정 — v1.0 에서는 임시 운영 용어). KIS 잔고 일치 확인 후 정상 운영 복귀 |
| KIS HTS 에 **취소 처리됨** | `RealOrder.status='CANCELED'` 로 수동 갱신 + audit 1 행 |

### 5.3 재시도 정책

place_order 는 **자동 재시도 없음** (중복 주문 위험). 동일 후보로 재진입은 운영자가
candidate 를 EXPIRE 후 새 후보를 생성하는 방식만 허용. `RealOrderExecutor` 의 게이트 9
(중복 가드) 가 application level 에서 강제한다.

---

## §6. 체결 불일치 대응 절차

Fill Sync (`POST /api/real-orders/{id}/sync`) 결과의 델타 비교에서 **`delta < 0`** 이
관측되었거나, KIS 잔고와 내부 `RealOrder` / `RealFill` 합계가 **일치하지 않을 때**.

### 6.0 v1.0 Phase D Fill Sync 정책 요약 (운영자 참고)

- `POST /api/real-orders/{order_id}/sync` 는 **수동 트리거 only** (자동 폴링 잡 0건 — v1.1)
- 게이트: AUTH + TRADING_SAFETY_ENABLED + KILL_SWITCH_OFF (3중)
- REAL_TRADING_ENABLED / KIS_ORDER_ENABLED 는 **미강제** — 사고 후에도 sync 가능
- 요청 본문 옵션: `{kis_order_no: <plaintext>}` — KIS HTS 에서 운영자가 직접 가져온 평문
  주문번호. transport 까지 in-memory 만 흐르고 어디에도 저장 0건
- 응답 분류 6 종: `FULL` / `PARTIAL` / `NONE` / `REJECTED` / `CANCELED` / `FAILED`
- 델타 idempotency: 반복 sync 시 `kis_total - existing_total = 0` 이면 신규 RealFill 행 0건
- DRY_RUN RealOrder 는 transport 호출 없이 즉시 NONE skip — 실 KIS 의 fake order_no 충돌 차단

### 6.1 즉시 차단

- § 4.1 의 비상 중지 절차 실행 — KillSwitch ON + KIS_ORDER_ENABLED=false + DRY_RUN=true
- `ApprovalAuditLog.append('FILL_SYNC_NEGATIVE_DELTA', ...)` (Phase D 자동) 또는
  `('RECONCILIATION_MISMATCH', ...)` (v1.1) 1 행이 자동 기록되어 있는지 확인

### 6.2 분석

- 해당 RealOrder 의 모든 RealFill 행을 시간순 조회
- KIS HTS 에서 동일 주문번호의 체결 내역을 수동 조회
- 합계 / 평단 / 시각이 일치하는지 행 단위 비교
- 누락 / 중복 / 시각 차이 (동일 ms 다른 fill_no) 어느 패턴인지 분류

### 6.3 처리

- **누락**: 수동으로 RealFill 행 추가 + audit 1 행 (`'FILL_SYNC_MANUAL_INSERT'`).
  v1.0 에서는 자동 보정 없음 — Reconciliation 자동화는 v1.1
- **중복**: 수동으로 잘못된 RealFill 행 1 건 삭제 (예외적 — 일반적으로 삭제 금지).
  audit 1 행 (`'FILL_SYNC_MANUAL_DELETE'`)
- **시각 차이**: 시각만 갱신 (삭제 없이) + audit 1 행

### 6.4 정상 복귀

KIS 잔고 = 내부 합계 일치 확인 후 § 3.2 KillSwitch OFF 절차.

> ⚠️ v1.0 에서 자동 Reconciliation 폴링 잡은 **0 건**. 체결 불일치는 운영자가 화면 /
> CLI 에서 명시 트리거 (`POST /sync`) 한 결과로만 발견된다. 자동화는 v1.1.

---

## §7. dry-run rollback 절차

실 거래에서 의심 동작이 보일 때, **사고로 가지 않고 즉시 dry-run 경로로 복귀**하는
절차. § 4 의 비상 중지보다 가벼운 단계.

### 7.1 즉시 dry-run 복귀

```bash
# .env 한 줄만 변경
REAL_ORDER_DRY_RUN=true

docker compose restart backend
```

이후 `RealOrderExecutor` 는 게이트 7 분기에서 자동으로 `FakeKisOrderTransport` 경로로
진입. **진행 중 RealOrder 의 status 는 변경되지 않는다** — 신규 진입만 dry-run 으로 전환.

### 7.2 점검

- 다음 1 건의 후보 승인 결과가 `RealOrder(is_dry_run=True, status=DRY_RUN)` 로 저장되는지 확인
- 진행 중 `is_dry_run=False` RealOrder 행은 § 5 / § 6 절차로 별도 처리

### 7.3 실 거래 재진입

§ 2.2 의 단계 5 (`REAL_ORDER_DRY_RUN=false`) 부터 재시작. 단계 1~4 는 이미 적용된 상태이므로
재실행 불필요.

---

## §8. GitHub Release / 운영 체크리스트

v1.0-final 태그 + GitHub Release 발행 시점에 운영자가 명시적으로 ✅ 표시해야 하는 항목.
이 체크리스트는 **본 Runbook 의 § 1 전제 조건과 별개** — § 1 은 .env 활성화 직전,
§ 8 은 릴리스 발행 직전에 점검한다.

### 8.1 코드 / 회귀 게이트

- [ ] backend pytest 전체 통과 (Phase E 종료 시점 ≈ 2025+ — Phase B 시점 1995 통과)
- [ ] frontend vitest 전체 통과 (≈ 219+ — Phase B 시점 214 그대로)
- [ ] frontend build 그린 (`tsc --noEmit && vite build`)
- [ ] Playwright e2e 전체 통과 (≈ 25+ — Phase B 시점 24 그대로)
- [ ] **`respx` + `httpx.MockTransport` mock-only 테스트 정책** — Phase B 의 53 신규
      `HttpxKisOrderTransport` 단위 테스트는 모두 mock transport 또는 respx route 만 사용,
      실 KIS endpoint 호출 0 건 (Phase B AST 가드 + caplog 단언으로 검증)
- [ ] AST 가드 — `kis_order_transport_real.py` 외에 직접 `httpx.Client` 호출 0 건. 본 모듈도
      모듈-레벨 `import httpx` 0 건 (lazy `__init__` 내부만, AST top-level walk 로 단언)
- [ ] AST 가드 — `from app.providers.kis` 직접 import 0 건 (`app/broker/`)
- [ ] AST 가드 — `requests` / `urllib` import 0 건 (`app/broker/`)
- [ ] Alembic head: `0010_real_fills` (v1.0 에서 변경 0 건, 41 테이블 그대로)

### 8.2 보안 / 비밀값

- [ ] `app_key` / `app_secret` / `access_token` / `account_no` / `cano` /
      `acnt_prdt_cd` 가 코드 / 로그 / 응답 / DB 어디에도 평문 0 건
- [ ] `mask_sensitive_order_payload()` 가 모든 transport 호출에서 호출됨
- [ ] `broker_order_no_hash` 만 저장 (KIS 평문 주문번호 0 건)
- [ ] raw KIS response (`raw_response` / `kis_response_raw` / `kis_fill_raw`) DB / 로그 / 응답 0 건
- [ ] `RealOrder` / `RealFill` schema 의 forbidden 컬럼 0 건 단언 통과
- [ ] `.env` 가 git 추적 대상이 아님 (`.gitignore` 확인)

### 8.3 정책 / 한도

- [ ] `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` /
      `REAL_ORDER_DRY_RUN=true` 가 paranoid default (코드 / 테스트 양쪽)
- [ ] `MAX_REAL_ORDER_AMOUNT` 권장 ≤ 100,000 KRW (`validate_real_trading_operating_limits()`
      가 100k 초과 시 warning 반환)
- [ ] `MAX_REAL_DAILY_ORDER_AMOUNT` 권장 ≤ 1,000,000 KRW
- [ ] `MAX_REAL_ORDER_AMOUNT` ≤ `MAX_REAL_DAILY_ORDER_AMOUNT` (Settings `__post_init__` 강제)
- [ ] mutation 라우터 1 건 신규 (`POST /api/real-orders/{id}/sync`) 외 read-only 정책 유지
- [ ] 새 mutation 은 KillSwitch + TradingSafety + AUTH 3중 게이트 (v0.15 패턴 동일)

### 8.4 문서

- [ ] `RELEASE_NOTES_v1.0.md` 본 작성 + Phase A~E 산출물 / 4 게이트 / 안전 정책 / v1.1 후보
- [ ] `RUNBOOK_REAL_TRADING.md` (본 문서) § 1~9 모두 채워져 있고 운영자가 1 회 검토 완료
- [ ] `README.md` v1.0-final 배너 갱신
- [ ] `PROJECT_STATUS.md` § 0 v1.0 마감 선언
- [ ] `ROADMAP.md` v1.0 행 ✅ 마감 + v1.1+ 후보 정리
- [ ] `INTEGRATION_RUNBOOK.md` v1.0 절 추가 (Real trading 운영 절차는 본 문서 참조)

### 8.5 운영 진입

- [ ] § 1 9 항목 모두 ✅
- [ ] § 2.2 단계적 활성화 절차 1~4 dry-run 검증 완료
- [ ] 단계 5 (`REAL_ORDER_DRY_RUN=false`) 진입 후 첫 1 건 KIS HTS 수동 매칭 확인
- [ ] 운영 1 주차 일일 KIS 잔고 vs 내부 합계 수동 reconciliation 1 회 / 일

---

## §9. v1.0 에서 하지 않을 것 (정책 잠금)

본 절은 **본 프로젝트 명시 금지 정책**의 재확인이다. 본 Runbook 의 어떤 절차도 다음을
우회하지 않는다.

- ❌ **FULL_AUTO 자동매매** — 본 프로젝트 범위 외 (별도 보안·컴플라이언스 사이클 선행 필수,
  v1.x 도 진입 금지)
- ❌ **SMALL_AUTO 자동매매** — 본 프로젝트 범위 외 (사용자 승인 없는 자동 진입 금지)
- ❌ **사용자 승인 없는 주문** — 1 후보 = 1 사용자 명시 승인 = 1 실주문 원칙. 자동 승인 0 건 /
  `APPROVAL_REQUIRED=False` 0 건
- ❌ **무제한 / 고빈도 주문** — `MAX_REAL_ORDER_AMOUNT` (회당) + `MAX_REAL_DAILY_ORDER_AMOUNT`
  (일일 누적) 강제. 1 후보 1 RealOrder 강제 (게이트 9 중복 가드)
- ❌ **레버리지 / 신용 / 공매도 / 파생상품** — 본 프로젝트 범위 외
- ❌ **LLM 직접 주문 실행** — LLM 은 분석·요약 보조 역할만. 주문 결정은 운영자
- ❌ **raw KIS response 저장** — `RealOrder` / `RealFill` 모든 필드에서 금지 (forbidden
  컬럼 가드 통과)
- ❌ **API key / app_secret / access_token / account_number 평문** 저장·로그·응답·UI 노출
- ❌ **KillSwitch ON 상태에서 mutation** — 모든 mutation 503 응답
- ❌ **위험 한도 우회** — `MAX_REAL_*` 검증 통과 없이는 진입 불가 (Settings `__post_init__`)
- ❌ **실거래 default ON** — `REAL_TRADING_ENABLED=false` / `KIS_ORDER_ENABLED=false` /
  `REAL_ORDER_DRY_RUN=true` paranoid default 그대로 유지
- ❌ **자동 Fill Sync 폴링 잡** — Fill Sync 는 수동 트리거만 (`POST /sync`). 자동 폴링은 v1.1 후보
- ❌ **Reconciliation 자동화** — v1.1 이연. v1.0 에서는 수동 비교만
- ❌ **다중 사용자 SaaS / RBAC / OAuth** — 단일 운영자 정책 유지 (v1.x+ 후보)
- ❌ **ScoringEngine 본 weight 변경** — v0.13 ProviderScorePolicy 위에 변경 0 건 유지

---

> **본 문서는 v1.0 사이클 동안 살아 있는 문서다.** Phase B~E 진행 중 운영 절차에
> 보강이 필요할 때마다 갱신한다. v1.0-final 태그 직전 § 8 체크리스트가 모두 ✅ 가
> 되어야 릴리스 발행이 가능하다.
