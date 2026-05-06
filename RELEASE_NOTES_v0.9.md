# Release Notes — v0.9 Operational Security & Watchlist Polish

마감 일자: **2026-05-07**
마감 태그: `v0.9-final`
기준선: `v0.8-final` (HEAD `80f0bac`)

---

## 1. 사이클 개요

v0.8 에서 처음 도입한 JWT 인증 + Watchlist POST/DELETE 라우터 위에
**운영 필수 보안·모니터링** 과 **Watchlist·UserPreference 고도화** 를 쌓은 사이클.

- **보안** — rate limit / security headers / brute force guard (Phase A)
- **운영 모니터링** — RequestID / 구조화 로깅 / optional Sentry / ErrorBoundary (Phase B)
- **백엔드 고도화** — Watchlist rename·delete·default·memo API + UserPreference 32번째 테이블 + Provider resilience skeleton (Phase C)
- **프런트 고도화** — Watchlist 관리 UI + UserPreference Settings 화면 + Today/StockDetail preference 연동 (Phase D)

자동매매 / 실주문 / Broker / LLM / 실 외부 API 는 **여전히 0건**.
Watchlist 와 UserPreference 에 한정된 PATCH/DELETE 추가이다.

---

## 2. Phase 별 산출물

### Phase A — Security Hardening (`v0.9-security-hardening`)

**목표**: v0.8 에서 처음 노출된 POST 라우터(인증 + Watchlist)에 운영 전 필수 보안 레이어 추가.

| 파일 | 내용 |
|---|---|
| `app/middleware/security_headers.py` | `SecurityHeadersMiddleware` — X-Content-Type-Options / X-Frame-Options / Referrer-Policy / Permissions-Policy 4종 주입 (`app.state.security_headers_enabled` 토글) |
| `app/middleware/rate_limit.py` | slowapi 기반 rate limit — login 5/min, 기타 100/min; `RATE_LIMIT_ENABLED=false` 시 exempt UUID 키로 no-op |
| `app/auth/brute_force.py` | 인메모리 `BruteForceGuard` — composite key (username:ip_hash), max_failures / window / lockout 파라미터 설정 가능; 잠금 시 generic 401 (user existence 비노출); `LOCKOUT_REJECTED` 감사 로그 기록 |
| `app/config/settings.py` 보강 | `RATE_LIMIT_ENABLED` / `RATE_LIMIT_AUTH` / `RATE_LIMIT_DEFAULT` / `SECURITY_HEADERS_ENABLED` / `AUTH_BRUTEFORCE_*` 8개 환경 변수 추가 |
| `tests/unit/test_security_headers.py` | 8 케이스 |
| `tests/unit/test_brute_force.py` | 12 케이스 |
| `tests/unit/test_rate_limit.py` | 6 케이스 |
| `tests/integration/test_auth_security.py` | 11 케이스 |

게이트: backend pytest **808 → 845 passed (+37)**, 회귀 0건.

---

### Phase B — Structured Logging & Monitoring (`v0.9-monitoring`)

**목표**: 운영 환경에서 로그 추적과 에러 캡처가 가능하도록 구조화 로깅 + optional Sentry + 프런트 ErrorBoundary 도입.

| 파일 | 내용 |
|---|---|
| `app/middleware/request_id.py` | `RequestIDMiddleware` — X-Request-ID 헤더 보존/생성, ContextVar 에 주입, 모든 로그에 자동 포함 |
| `app/config/logging.py` | `configure_logging()` — `SensitiveFilter` (password/token/secret extra 마스킹) + `RequestIDFilter` + `LOG_FORMAT=json` 시 `pythonjsonlogger` 포매터 |
| `app/monitoring/sentry.py` | optional Sentry init (`SENTRY_ENABLED=false` 기본) — `send_default_pii=False`, `before_send` hook 으로 password/token/Authorization 헤더 redact |
| `app/api/routes.py` 보강 | 전역 Exception handler — generic 500 + request_id 응답 (stack trace 미노출); `/api/health` 상세 응답 확장 (uptime_seconds / db_connected / version) |
| `frontend/src/components/ErrorBoundary.tsx` | `componentDidCatch` → `console.error` only, 외부 전송 없음 |
| `tests/unit/test_logging_config.py` | 12 케이스 |
| `tests/integration/test_request_id_middleware.py` | 12 케이스 |

게이트: backend pytest **845 → 869 passed (+24)** (순증 수정), 회귀 0건.

---

### Phase C — Watchlist API 고도화 + UserPreference + Provider Resilience (`v0.9-watchlist-api`)

**목표**: v0.8 Watchlist GET/POST/DELETE 5건 위에 rename·default·delete·memo 4건 추가 + UserPreference 32번째 테이블 + provider 회복성 skeleton.

#### Watchlist API 고도화

| 엔드포인트 | 내용 |
|---|---|
| `PATCH /api/watchlists/{id}` | name 변경 / is_default 토글 (이전 default 자동 demote); 타인 watchlist → 404 |
| `DELETE /api/watchlists/{id}` | watchlist 자체 삭제 + items cascade; 기본 목록 삭제 허용 (UserPreference ON DELETE SET NULL) |
| `GET /api/watchlists/{id}/items` | 페이지네이션 (limit/offset) + symbol_prefix 필터; 응답: total / items / limit / offset |
| `PATCH /api/watchlists/{id}/items/{symbol}` | memo 수정 / null 로 초기화; symbol normalize 적용 |

#### UserPreference — 32번째 테이블

| 항목 | 내용 |
|---|---|
| ORM | `user_preferences` — UNIQUE(user_id), `default_watchlist_id` FK (ON DELETE SET NULL), `default_market`, `default_strategy`, `dashboard_layout_json`, `notification_preferences_json` |
| Alembic | `alembic/versions/0004_user_preferences.py` (down_revision `0003_watchlist`); `compare_metadata` diff 0건 |
| Repository | `UserPreferenceRepository.get_or_create_for_user` / `update` (sentinel partial) / `set_default_watchlist` / `update_dashboard_layout` / `update_notification_preferences` |
| API | `GET /api/users/me/preferences` (lazy-create) / `PUT /api/users/me/preferences` (watchlist 소유권 검증; 비밀 키 rejection 422) |

#### Provider Resilience Skeleton

| 컴포넌트 | 내용 |
|---|---|
| `ProviderErrorKind` | TIMEOUT / RATE_LIMIT / SERVER_ERROR / CLIENT_ERROR / UNKNOWN |
| `ProviderCallResult` | `.ok()` / `.fail()` class method, value / error_kind / attempts |
| `retry_with_backoff()` | 지수 백오프 (`base_delay_s × 2^(attempt-1)`), `max_delay_s` cap, CLIENT_ERROR 비재시도 |
| `CircuitBreaker` | CLOSED → OPEN (N failures) → HALF_OPEN (timeout) → CLOSED (probe 성공) / OPEN (probe 실패); `reset()` 강제 전환 |

실 provider 강제 적용 0건 (opt-in skeleton).

테스트:
- `tests/integration/test_watchlist_phase_c.py` 신규 (20 케이스)
- `tests/integration/test_user_preferences.py` 신규 (17 케이스)
- `tests/unit/test_provider_resilience.py` 신규 (19 케이스)

게이트: backend pytest **869 → 916 passed (+47)**, 회귀 0건.

---

### Phase D — Frontend 관리 UI (`v0.9-frontend`)

**목표**: Phase C 에서 추가된 API 를 소비하는 Watchlist 관리 UI + UserPreference Settings 섹션 + Today/StockDetail preference 연동.

#### API 클라이언트 보강

- `frontend/src/api/client.ts` — `apiPatch` / `apiPut` 추가
- `frontend/src/api/watchlists.ts` — `updateWatchlist` / `deleteWatchlist` / `updateWatchlistItemMemo` / `listWatchlistItems` 추가
- `frontend/src/api/preferences.ts` 신규 — `getMyPreferences` / `updateMyPreferences`
- `frontend/src/api/types.ts` — `UserPreference` / `UserPreferenceUpdateRequest` / `WatchlistItemsResponse` 타입 추가

#### Hooks 보강

- `frontend/src/hooks/useWatchlists.ts` — `useUpdateWatchlist` / `useDeleteWatchlist` / `useUpdateWatchlistItemMemo` 추가
- `frontend/src/hooks/useUserPreferences.ts` 신규 — `useUserPreferences` / `useUpdateUserPreferences` / `useEffectiveDefaultWatchlistId`
  - preference priority chain: `preference.default_watchlist_id` → watchlist `is_default` flag → first watchlist

#### UI 고도화

| 화면 | 변경 |
|---|---|
| Watchlist `/watchlist` | 목록 rename(inline form) / delete / set-default(드롭다운 메뉴) + item memo 인라인 편집 + item 필터/검색 + 에러 분기(409/422/404) |
| Settings `/settings` | UserPreference 섹션 추가 (default_watchlist_id 선택 / default_market / default_strategy / notification 체크박스); 저장 성공 메시지 / 에러 분기 |
| TodayReport `/` | WatchlistCard — `useEffectiveDefaultWatchlistId` (preference → fallback) |
| StockDetail `/stocks/:symbol` | FavoriteButton — `useEffectiveDefaultWatchlistId` + 409 idempotent 처리 |

#### 테스트

- `frontend/src/tests/WatchlistManage.test.tsx` 신규 (21 케이스)
- `frontend/src/tests/UserPreferences.test.tsx` 신규 (15 케이스)
- `frontend/src/tests/mswServer.ts` — Phase C/D 핸들러 추가

게이트: frontend vitest **117 → 146 passed (+29)**, build 그린, tsc 오류 0건, 회귀 0건.

---

## 3. 최종 테스트 게이트 (v0.9 마감 시점)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend pytest | `python -m pytest -q --tb=no` | **916 passed** (1 deselected — test_settings_defaults 로컬 .env 충돌) |
| frontend vitest | `cd frontend && npm run test -- --run` | **146 passed** (19 파일) |
| frontend build | `cd frontend && npm run build` | ✓ built in 2.65s |
| Playwright e2e | `cd frontend && npx playwright test` | **19 passed** (chromium) |

회귀 0건. 자동매매 / 실주문 / 실 KIS / Telegram 실제 호출 0건.

---

## 4. 안전 정책

### 4.1 자동매매 / 실주문 완전 미포함

- `BrokerInterface` — ABC placeholder 만 유지. 구현체 0건.
- `FULL_AUTO` / `APPROVAL` / `SMALL_AUTO` / `MockBroker` / `ReplayBroker` 코드 일체 없음.
- `WatchlistItem` ORM 에 broker / account / quantity / order_price / order_type / side 컬럼 0건 (repo 단언 + e2e 단언 유지).
- `StrategySignal.action` 은 분석 신호 전용 — 실제 주문 전송 경로 없음.

### 4.2 비밀값 미노출

- API 응답 어디에도 `password` / `password_hash` / `access_token` / `jwt_secret` / `secret` / `source_file_path` / `broker` / `account` / `quantity` / `order_price` / `order_type` / `side` 포함 불가.
- `LoginAuditLog.source_ip_hash` / `user_agent_hash` — SHA256 64자 hex 만 저장 (평문 IP / user-agent 저장 0건).
- 로그: `SensitiveFilter` 가 extra 키 이름 기반 redact.
- Sentry (옵션): `before_send` 가 request.data / headers 스캔 후 redact.

### 4.3 외부 API 실제 호출 없음

- KIS API — mock / test 환경에서 `FakeKisDataProvider` 만 사용. `KIS_USE_PAPER=true` 기본.
- DART / RSS / 뉴스 외부 API — v0.5/v0.6 에서 ABC 인터페이스만 추가됨. 실 호출 0건. `news_collection_enabled` / `disclosure_collection_enabled` 기본 false.
- Telegram — `TELEGRAM_ENABLED=false` 기본. 모든 테스트에서 실제 발송 0건.

### 4.4 UserPreference 알림 설정

- `notification_preferences_json.enabled` 은 UI 저장만. Telegram / WebSocket / SSE / 푸시 연결 0건.
- 알림 발송 구현은 v0.10+ 후보.

### 4.5 Watchlist / UserPreference 외 도메인 mutation 없음

- v0.9 Phase C/D 에서 추가된 write 라우터: PATCH/DELETE watchlist (4건) + GET/PUT preferences (2건) — 총 6건 추가.
- 그 외 도메인 (recommendations / holdings / backtest / themes / fundamentals / earnings) 은 여전히 read-only GET 만.
- ScoringEngine / HoldingCheckEngine / RecommendationEngine 본 weight 산식 변경 0건.

---

## 5. 알려진 한계

| 항목 | 상태 |
|---|---|
| Sentry optional, 기본 off | `SENTRY_ENABLED=false` — 운영 투입 시 DSN + 환경 변수 설정 필요 |
| Provider resilience skeleton | `retry_with_backoff` / `CircuitBreaker` 구현 완료, 실 KIS/DART provider 에 아직 적용 미완 |
| UserPreference 단일 사용자 중심 | 다중 사용자 / RBAC 미지원 — `AUTH_ENABLED=true` + 단일 사용자 운영 기준 |
| rate limit 튜닝 미완 | 현재 기본값 (login 5/min, others 100/min) — 실 트래픽 기준 조정 필요 |
| CSP 미적용 | Vite devserver / nginx 프록시 충돌 우려로 보류 — v0.10+ 후보 |
| 실 DART/RSS provider 미구현 | v0.5/v0.6 에서 ABC만 추가됨 — 라이선스 검토(사람) 선행 필수 |
| 자동매매 미진입 | BrokerInterface placeholder 유지 — 별도 보안/컴플라이언스/자본 한도 사이클 선행 필수 |
| notification_preferences_json | 저장만, 실 발송 연결 없음 — v0.10+ 에서 실 Telegram / 웹훅 연결 고려 |

---

## 6. v0.10 후보

| 후보 | 사유 |
|---|---|
| 실 DART / RSS provider | v0.5/v0.6 ABC 위에 추가 — 라이선스 / 스로틀링 / CI 외부 호출 차단 정책 동반 |
| Provider resilience 실 적용 | `retry_with_backoff` / `CircuitBreaker` → KIS / DART / RSS 래핑 |
| 운영 모니터링 고도화 | Prometheus exporter + Grafana 대시보드 — 외부 노출 규모 확인 후 |
| CSP / CSRF / rate limit 고도화 | 운영 트래픽 수집 후 세부 정책 수립 |
| 인증 고도화 | refresh token / 다중 사용자 / OAuth — 단일 사용자 운영 검증 후 |
| 백테스트 고도화 | walk-forward / multi-strategy / 실거래 비용 세밀화 (v0.7 placeholder → real) |
| Watchlist 가격 알림 / target return alert | 알림 시스템 변경 = 별도 cycle |
| Paper/Simulation Trading 준비 | MockBroker / ReplayBroker skeleton 도입 — 별도 보안·컴플라이언스 사이클 선행 |
| LLM 보강 | News sentiment / 재무 분석 자동화 — 룰 기반 검증 + 데이터 누적 후 |
| Approval Trading Safety Layer | 별도 장기 후보 — 자동매매 전단계 (수동 승인) |

> **자동매매 / 실주문 (FULL_AUTO / SMALL_AUTO / BrokerInterface 구현)** 는 v0.10+ 에도
> Future Backlog 유지. 별도 보안·컴플라이언스·자본 한도 사이클 선행 없이는 진입 불가.

---

## 7. 누적 태그

| 태그 | Phase | 내용 |
|---|---|---|
| `v0.9-security-hardening` | A | SecurityHeadersMiddleware + rate limit + BruteForceGuard |
| `v0.9-monitoring` | B | RequestIDMiddleware + 구조화 로깅 + optional Sentry + ErrorBoundary |
| `v0.9-watchlist-api` | C | Watchlist PATCH/DELETE 4건 + UserPreference (32번째 테이블) + Provider resilience skeleton |
| `v0.9-frontend` | D | Watchlist 관리 UI + UserPreference Settings + Today/StockDetail preference 연동 |
| `v0.9-final` | E | 마감 문서 + 최종 게이트 재확인 |

이전 사이클 마감 태그:
`v0.1-backend-final` → `v0.1-backend-kis-paper-verified` → `v0.2-frontend-final` →
`v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` →
`v0.3-frontend-stock-chart` → `v0.3-final` → `v0.4-backend-reports` →
`v0.4-import-pipeline` → `v0.4-report-score` → `v0.4-frontend-reports` →
`v0.4-final` → `v0.5-news-collector` → `v0.5-disclosure-pipeline` →
`v0.5-news-score` → `v0.5-frontend-themes` → `v0.5-final` →
`v0.6-fundamental-data-layer` → `v0.6-earnings-event-pipeline` →
`v0.6-fundamental-score` → `v0.6-frontend-fundamentals` → `v0.6-final` →
`v0.7-strategy-interface` → `v0.7-backtest-engine` → `v0.7-backtest-cost-regime` →
`v0.7-frontend-backtest` → `v0.7-final` → `v0.8-alembic-baseline` →
`v0.8-auth-foundation` → `v0.8-watchlist-api` → `v0.8-frontend-watchlist` →
`v0.8-final` → `v0.9-security-hardening` → `v0.9-monitoring` →
`v0.9-watchlist-api` → `v0.9-frontend` → **`v0.9-final`**.
