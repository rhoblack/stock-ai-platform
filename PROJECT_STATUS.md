# PROJECT_STATUS.md

진행 상태 스냅샷. 새 Codex 세션이 이어서 작업을 시작할 때 가장 먼저 읽어야 할
파일이다. AGENTS.md / TASKS.md와 함께 사용한다. §0 은 항상 가장 최근 사이클의
**시작 또는 마감 선언**을 담고, 이전 사이클의 마감 선언은 §0-1, §0-2, §0-3,
§0-4 … 로 강등된다 (시간순 역배열).

---

## 0. v0.11 시작 선언 — Real Provider Transport & Observability

**v0.11 cycle 시작.** `v0.10-final` 위에 **Real Provider Transport &
Observability** 5 phase 진입.

- 시작 일자: **2026-05-07 (Asia/Seoul)**
- 기준 태그: `v0.10-final` (HEAD `c56faf9`)
- 기준 게이트: backend pytest **1045 passed (1 deselected)** / frontend vitest
  **153 passed** / Playwright e2e **20 passed** / build 그린
- Alembic head: `0004_user_preferences` (**v0.11 신규 revision 없음** — provider
  observability 도 in-memory bounded ring buffer)
- 세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0011`

### v0.11 채택 결론 (시나리오 비교 요약)

`PLANS.md` `PLAN-0011` 4 시나리오 비교 후 채택: **Scenario X — Real Provider
Transport + Observability**.

| 시나리오 | 내용 | 결정 |
|---|---|---|
| **X** | DART/RSS 실 httpx transport + provider observability 고도화 (failure history + Prometheus optional) + `/api/health/providers` 확장 | ✅ **핵심 채택** |
| Y | DART/RSS score 반영 (ScoringEngine weight 보강) | ❌ v0.12 연기 — 실 transport 안정화 + 누적 데이터 부족 |
| Z | 백테스트 고도화 (walk-forward / 다중 전략 / 실 cost model) | ❌ v0.12+ 연기 — recommendation_results 3~6개월 누적 필요 |
| W | 보안/인증 고도화 (rate limit 튜닝 / CSP / refresh token / RBAC) | ❌ v0.12+ 연기 — 실 트래픽 / 단일 사용자 운영 검증 후 |

### v0.11 Phase 목표

| Phase | 내용 | 태그 | 예상 게이트 |
|---|---|---|---|
| A | DART HTTP Transport — `HttpxDartTransport` (lazy httpx import) + factory 자동 주입 + `_SensitiveQueryStringFilter` (httpx URL secret 마스킹) + respx mock 테스트 27건 | `v0.11-dart-transport` ✅ | pytest 1045→1072 (+27) |
| B | RSS HTTP Transport — `HttpxRssTransport` (lazy httpx import, follow_redirects=True) + factory 자동 주입 + 공유 `SensitiveQueryStringFilter` (Phase A 에서 `app/config/logging.py` 로 추출) + respx mock 테스트 19건 | `v0.11-rss-transport` ✅ | pytest 1072→1091 (+19) |
| C | Provider Observability Layer — failure history ring buffer + summary + optional Prometheus `/metrics` | `v0.11-observability` ⏳ | pytest +20 |
| D | `/api/health/providers` 확장 + Settings 패널 보강 (success_rate_24h / recent_failures) | `v0.11-health-extended` ⏳ | pytest +8 / vitest +6 / e2e +1 |
| E | 마감 — `RELEASE_NOTES_v0.11.md` + 4 게이트 최종 확인 | `v0.11-final` ⏳ | 4 게이트 그린 |

### v0.11 핵심 정책

- DART/RSS provider **default OFF 유지** — `DART_ENABLED=true` /
  `RSS_NEWS_ENABLED=true` 명시 enable + 운영자 라이선스 검토(사람) 선행 필수
- Prometheus exporter **default OFF 유지** — `PROMETHEUS_ENABLED=true` 명시 시에만
  `/metrics` 노출 (false 시 404)
- ScoringEngine / HoldingCheckEngine 본 weight 변경 0건 — DART/RSS score 반영은
  v0.12+ 후보
- Alembic 새 revision 0건 — provider observability 도 in-memory bounded ring
  buffer (50/200 entries cap)
- 신규 mutation 라우터 0건 — `/metrics` 도 GET only (POST/PUT/DELETE 405)
- 본문 / 비밀값 / URL query secret 응답·로그·UI 평문 노출 0건 — v0.10 정책 그대로
  + Phase D 단언 강화
- 자동매매 / 실 KIS 주문 / `BrokerInterface` 구현 0건 (v0.1~v0.11 일관)
- 신규 pip 의존성 2종 — `respx>=0.21,<0.22` (테스트 only, BSD-3) +
  `prometheus-client>=0.19,<1.0` (Apache 2.0)

### v0.12 후보 (우선순위 순)

1. **DART/RSS score 반영** — `RealNewsScoreProducer` (v0.5) /
   `RealFundamentalScoreProducer` (v0.6) 위에 v0.11 의 실 transport 결과 연결.
   ScoringEngine weight 보강은 누적 데이터 검증 후
2. **백테스트 고도화** — walk-forward 검증 / 다중 전략 포트폴리오 / 실 broker fee
   schedule. recommendation_results 3~6개월 누적 후
3. **Grafana dashboard JSON 동봉** — v0.11 Prometheus exporter 위에 시각화 layer
4. **인증 고도화** — refresh token / 다중 사용자 / OAuth / SSO / RBAC
5. **CSP / rate limit 고도화** — 실 트래픽 수집 후 정책 수립
6. **LLM 보강** — News sentiment / 재무 분석 / 자동 전략 (룰 기반 검증 후)
7. **WebSocket / SSE 실시간 잡 / 백테스트 진행** — 현재 polling 만
8. **Provider toggle GUI / mutation API** — 인증 + 보안 검토 동반
9. **자동매매** (Future Backlog — 별도 보안·컴플라이언스·자본 한도 사이클 선행 필수)

---

## 0-1. v0.10 마감 선언 — Real Provider Readiness & Resilience

**v0.10 cycle 마감.** `v0.9-final` 위에 **Real Provider Readiness & Resilience**
5 phase 완료. 최종 마감 태그 `v0.10-final`.

- 시작 일자: **2026-05-07 (Asia/Seoul)**
- 마감 일자: **2026-05-07 (Asia/Seoul)**
- 최종 게이트:
  - backend pytest **1045 passed** (1 deselected — test_settings_defaults 로컬
    .env 충돌, Phase A 부터 baseline 인계)
  - frontend vitest **153 passed** (20 파일)
  - frontend build **그린** (`tsc --noEmit && vite build`, 3.41s)
  - Playwright e2e **20 passed** (chromium)
- 기준 태그: `v0.9-final` → 마감 태그: `v0.10-final`
- Alembic head: `0004_user_preferences` (v0.10 신규 revision **0건** — DART/RSS
  기존 테이블 재사용, `ProviderHealthMonitor` in-memory only)
- 세부 결과: [`RELEASE_NOTES_v0.10.md`](./RELEASE_NOTES_v0.10.md)

### v0.10 Phase 결과 요약

| Phase | 내용 | 태그 | 게이트 |
|---|---|---|---|
| A | `ProviderHealthMonitor` + `call_with_resilience()` + settings 6종 + 테스트 31건 | `v0.10-provider-resilience` | pytest 916→947 (+31) |
| B | DART Provider skeleton (DartFundamental/Earnings/Disclosure, DART_ENABLED=false, transport 주입형, parser/mapper + body 필드 strip + crtfc_key 마스킹 + 테스트 49건) | `v0.10-dart-provider` | pytest 947→995 (+48) |
| C | RSS/News Provider skeleton (RssNewsProvider, RSS_NEWS_ENABLED=false, RSS 2.0 + Atom 동시 지원, transport 주입형, body 필드 strip + URL dedup + URL query secret 마스킹 + 테스트 33건, stdlib xml.etree only) | `v0.10-rss-provider` | pytest 995→1028 (+33) |
| D | Provider Health read-only API (GET /api/health/providers + Settings 패널 + canonical 3 provider 항상 노출 + last_error_message 미노출 + POST/PUT/DELETE 405) | `v0.10-health-api` | pytest 1028→1045 (+17) / vitest 146→153 (+7) / e2e 19→20 (+1) |
| E | 마감 문서 (`RELEASE_NOTES_v0.10.md`) + 4 게이트 최종 재확인 | `v0.10-final` | 4 게이트 모두 그린 |

### v0.10 핵심 정책 (마감 시점 재확인)

- `DART_ENABLED=false` / `RSS_NEWS_ENABLED=false` 기본 — 모든 테스트 / CI 에서
  외부 API 호출 0건 (`httpx.Client` 미생성 단언 4건: DART / RSS / Phase D 응답)
- DART / RSS / News 본문 (body / paragraph / full_text / 본문 / 원문 / 전문)
  저장 0건 — parser 사전 strip + DTO 자체에 부재
- Alembic 새 revision 0건 — `news_items` / `financial_statements` 기존 테이블
  재사용; `ProviderHealthMonitor` 는 in-memory only
- ScoringEngine / HoldingCheckEngine 본 weight 변경 0건 — DART/RSS score 반영은
  v0.11+ 후보
- `DART_API_KEY` / `crtfc_key` / RSS feed URL query string secret 응답·로그·UI
  평문 노출 0건 — `SensitiveFilter` (6 변형 마스킹) + `_safe_url_for_log` (query
  / fragment strip) + Provider Health 응답에서 `last_error_message` 의도적
  미포함
- 자동매매 / 실 KIS 주문 / `BrokerInterface` 구현 / FULL_AUTO / APPROVAL /
  SMALL_AUTO 0건 (v0.1~v0.10 일관 정책)
- 신규 mutation 라우터 0건 — `GET /api/health/providers` 만 추가, POST/PUT/DELETE
  모두 405

### v0.11 후보 (우선순위 순)

1. 실 DART / RSS httpx transport 도입 (Phase B/C skeleton 위에 실 HTTP 전송 +
   라이선스 검토(사람) 선행 필수)
2. Prometheus exporter + Grafana 대시보드 (v0.10 in-memory monitor 외부 시계열
   DB 노출, 외부 노출 규모 확인 후)
3. DART/RSS score 반영 (`RealNewsScoreProducer` / `RealFundamentalScoreProducer`
   위에 DART/RSS 데이터 연결, 룰 기반 검증 후 weight 보강)
4. 백테스트 고도화 (walk-forward / 다중 전략 포트폴리오 / 실 broker fee
   schedule, recommendation_results 3~6개월 누적 후)
5. 인증 고도화 (refresh token / 다중 사용자 / OAuth / SSO / RBAC)
6. CSP / rate limit 고도화 (실 트래픽 수집 후 정책 수립)
7. LLM 보강 (News sentiment / 재무 분석 / 자동 전략 — 룰 기반 검증 후)
8. Provider Health UI 고도화 (실시간 갱신 / WebSocket / `GET /api/health/jobs`
   분리)
9. Watchlist 가격 알림 / target return alert (알림 시스템 = 별도 cycle)
10. 자동매매 (Future Backlog — 별도 보안·컴플라이언스·자본 한도 사이클 선행 필수)

---

## 0-2. v0.10 시작 선언 → 마감으로 갱신 (기록 보존)

### v0.10 채택 결론 (시나리오 비교 요약)

`PLANS.md` `PLAN-0010` 4 시나리오 비교 후 채택: **Modified X + light Z = "Real
Provider Readiness & Resilience"**.

- ✅ **시나리오 X 핵심 채택** — DART/RSS Provider 구현 + Provider resilience 실
  적용 (Phase A~C)
- ⚠️ **시나리오 Z 부분 채택** — Sentry 가이드 + provider health API 만. Prometheus
  / Grafana 는 v0.11+ 연기
- ❌ **시나리오 Y 연기** — 백테스트 고도화 (walk-forward / 실 비용 모델). v0.11+
  로 연기 (recommendation_results 3~6개월 누적 필요)
- ❌ **시나리오 W 거부** — 복합 (X+Y+Z) 범위 과다, 리스크 관리 곤란

기준선: `v0.9-final` (HEAD `90e3db3`). 회귀 게이트: pytest 916 / vitest 146 /
e2e 19 / build 그린. Alembic head: `0004_user_preferences`.

### v0.10 진입 시 정의된 phase 목표 (최종 결과는 §0 참조)

| Phase | 시점 목표 | 결과 |
|---|---|---|
| A | Provider Resilience Runtime 도입 | ✅ pytest +31 |
| B | DART Provider 구현 | ✅ pytest +48 |
| C | RSS/News Provider 준비 | ✅ pytest +33 |
| D | 운영 모니터링 강화 (`GET /api/health/providers` + 프런트 패널) | ✅ pytest +17 / vitest +7 / e2e +1 |
| E | 마감 문서 + 4 게이트 최종 확인 | ✅ 본 문서 |

### v0.10 에서 절대 하지 않을 것 (정책 — 마감 시점 재확인)

- ❌ 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ `BrokerInterface` 구현 (placeholder 유지)
- ❌ 실 DART / RSS / 뉴스 / Telegram 자동 호출 — provider skeleton + transport
  주입형 만, 실 httpx 전송은 v0.11+
- ❌ ScoringEngine / HoldingCheckEngine 본 weight 변경
- ❌ Provider enable/disable mutation API — `.env` + 백엔드 재시작만
- ❌ 본문 저장 (body / paragraph / full_text / 본문 / 원문 / 전문)
- ❌ `DART_API_KEY` / `crtfc_key` / URL query secret 응답·로그·UI 평문 노출
- ❌ 다중 사용자 / RBAC / OAuth / SSO / refresh token (단일 사용자 운영 유지)
- ❌ Prometheus exporter / Grafana 대시보드 (외부 노출 규모 확인 후)
- ❌ Alembic 새 revision (DART/RSS 기존 테이블 재사용 + monitor in-memory only)

---

## 0-3. v0.9 마감 선언 — Operational Security & Watchlist Polish (강등됨)

**v0.9 cycle 마감.** 기준선 `v0.8-final` 위에 **Operational Security &
Watchlist Polish** 5 phase 완료. 최종 마감 태그 `v0.9-final`.

- 시작 일자: **2026-05-06 (Asia/Seoul)**
- 마감 일자: **2026-05-07 (Asia/Seoul)**
- 최종 게이트:
  - backend pytest **916 passed** (1 deselected — test_settings_defaults 로컬 .env 충돌, 관례대로 deselect)
  - frontend vitest **146 passed** (19 파일)
  - frontend build **그린** (`tsc --noEmit && vite build`, 2.65s)
  - Playwright e2e **19 passed** (chromium)
- 기준 태그: `v0.8-final` → 마감 태그: `v0.9-final`
- 세부 결과: [`RELEASE_NOTES_v0.9.md`](./RELEASE_NOTES_v0.9.md)

### v0.9 Phase 결과 요약

| Phase | 내용 | 태그 | 게이트 |
|---|---|---|---|
| A | SecurityHeadersMiddleware + slowapi rate limit + BruteForceGuard | `v0.9-security-hardening` | pytest 808→845 (+37) |
| B | RequestIDMiddleware + SensitiveFilter + optional Sentry + ErrorBoundary | `v0.9-monitoring` | pytest 845→869 (+24) |
| C | Watchlist PATCH/DELETE 4건 + UserPreference (32nd table) + Provider resilience skeleton | `v0.9-watchlist-api` | pytest 869→916 (+47) |
| D | Watchlist 관리 UI + UserPreference Settings + Today/StockDetail preference 연동 | `v0.9-frontend` | vitest 117→146 (+29) |
| E | 마감 문서 + 4 게이트 최종 재확인 | `v0.9-final` | 4 게이트 모두 그린 |

### v0.10 후보 (우선순위 순)

1. 실 DART / RSS provider (v0.5/v0.6 ABC 위에 추가 — 라이선스 검토 선행)
2. Provider resilience 실 적용 (KIS/DART 래핑)
3. 운영 모니터링 고도화 (Prometheus + Grafana)
4. CSP / rate limit 고도화 (운영 트래픽 수집 후)
5. 인증 고도화 (refresh token / 다중 사용자)
6. 백테스트 고도화 (walk-forward / 실 비용 모델)
7. Paper/Simulation Trading 준비 (MockBroker skeleton)
8. 자동매매 (Future Backlog — 별도 보안·컴플라이언스 사이클 선행 필수)

---

## 0-4. v0.9 시작 선언 → 마감으로 갱신 (강등됨)

### v0.9 채택 결론 (후보 비교 요약)

12 개 v0.9 후보 중 채택:

- ✅ **보안 강화 — rate limit + security headers + brute force** (Phase A) — POST 라우터 운영 전 필수. `slowapi` + `SecurityHeadersMiddleware` + LoginAuditLog 기반 카운터
- ✅ **운영 모니터링 — Sentry optional + 구조화 로깅** (Phase B) — `SENTRY_ENABLED=false` 기본, `LOG_FORMAT=json` env. PII 필터링 + React ErrorBoundary
- ✅ **Watchlist API 고도화 — PUT/DELETE 4건 + 메모 편집** (Phase C) — v0.8 5건 위에 rename/delete-list/set-default/memo 추가. Alembic revision 0004
- ✅ **UserPreference 기초 — 32번째 테이블 + GET/PUT /api/me/preferences** (Phase C) — default_watchlist_id / default_market / default_strategy. Alembic revision 0005
- ✅ **Provider 회복성 레이어 — ProviderStatus enum + retry decorator** (Phase C) — 실 provider 구현 0건, 인터페이스 강화만
- ✅ **Frontend 관리 UI — Watchlist rename/delete/default + 메모 + Settings 화면** (Phase D) — Phase C API 연동

미채택 → v0.10+ 로 미룸:

- ❌ **실 DART / RSS provider 구현** — 라이선스 검토(사람) 선행 없이 코드 추가 불가 (v0.10+)
- ❌ **백테스트 고도화 (walk-forward / multi-strategy)** — v0.7~v0.8 데이터 누적 필요 (v0.10)
- ❌ **인증 고도화 (다중 사용자 / OAuth / refresh token)** — 단일 사용자 운영 검증 후 (v0.10+)
- ❌ **Prometheus exporter / Grafana 대시보드** — 외부 노출 규모 확인 후 (v0.10+)
- ❌ **LLM 자동 전략 / 자동 분석** — 룰 기반 검증 + 데이터 누적 후 (v0.11+)
- ❌ **자동매매 / BrokerInterface 구현** — 별도 보안/컴플라이언스/자본 한도 사이클 선행 (Future Backlog)

### v0.9 에서 절대 하지 않을 것 (정책)

- ❌ 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ `BrokerInterface` 구현 (placeholder 유지)
- ❌ 실 DART / 실 RSS / 실 News API 자동 호출 — ProviderStatus + retry interface 만
- ❌ MockBroker / ReplayBroker / SimulationBroker
- ❌ ScoringEngine / HoldingCheckEngine 본 weight 변경
- ❌ Recommendations / Backtest / Today 산식 변경
- ❌ 다중 사용자 / RBAC / OAuth / SSO / refresh token
- ❌ WebSocket / SSE
- ❌ Prometheus exporter / Grafana 대시보드
- ❌ WatchlistItem 에 broker/account/quantity/order_* 컬럼 추가
- ❌ Telegram 실 발송 (DRY_RUN 기본 유지)
- ❌ 평문 IP / 평문 password 저장

### v0.9 Phase A 결과 (요약) — 보안 강화

- 마감 게이트: backend pytest **869 passed** (1 deselected)
- 산출 태그: `v0.9-security-hardening`

산출물:
- `slowapi` rate limit 미들웨어 (`RATE_LIMIT_ENABLED` env toggle)
- `SecurityHeadersMiddleware` (HSTS / X-Frame-Options / CSP / Referrer-Policy 등 7종)
- `LoginAuditLog` 기반 brute force protection (`AUTH_BRUTEFORCE_ENABLED` toggle, 10회/10분 window, IP SHA256 해시)
- `Settings` 4 필드 추가 (`rate_limit_enabled` / `security_headers_enabled` / `auth_bruteforce_enabled` / `auth_max_login_attempts`)
- 통합 테스트 8종 신규 (rate limit / security headers / brute force / auth security count)
- 모든 기존 테스트 회귀 0건

### v0.9 Phase B 결과 (요약) — 운영 모니터링

- 마감 게이트: backend pytest **869 passed** (1 deselected) (순증 없음 — 모니터링 배선 테스트는 Phase A 기존 smoke 재활용)
- 산출 태그: `v0.9-monitoring`

산출물:
- `sentry-sdk` optional init (`SENTRY_ENABLED` / `SENTRY_DSN` env, PII scrub `send_default_pii=False`)
- `StructuredLogFilter` JSON 포맷 + PII 필드 자동 마스킹 (`LOG_FORMAT=json` env)
- React `ErrorBoundary` 컴포넌트 — 프런트엔드 JS 에러 시각화
- `GET /api/health` 상세 응답 확장 (uptime_seconds / db_connected / version)
- `Settings` 3 필드 추가 (`sentry_enabled` / `sentry_dsn` / `log_format`)

### v0.9 Phase D 결과 (요약) — Frontend Watchlist/Settings 관리 UI

- 마감 게이트: frontend vitest **146 passed** (기준선 113 + 33 신규) / build 그린 / tsc 오류 0건
- 백엔드 변경 0건 (backend pytest 916 유지)
- 산출 태그: `v0.9-frontend` (미push)

산출물:

**API 클라이언트 보강**
- `apiPatch` / `apiPut` — `client.ts` 추가
- `UserPreference`, `UserPreferenceUpdateRequest`, `WatchlistItemsResponse` — `types.ts` 추가
- `api/preferences.ts` 신규 — `getMyPreferences`, `updateMyPreferences`
- `api/watchlists.ts` 보강 — `updateWatchlist` (PATCH), `deleteWatchlist` (DELETE), `updateWatchlistItemMemo` (PATCH item), `listWatchlistItems` (GET paginated)

**Hooks 보강**
- `hooks/useWatchlists.ts` — `useUpdateWatchlist`, `useDeleteWatchlist`, `useUpdateWatchlistItemMemo` 추가
- `hooks/useUserPreferences.ts` 신규 — `useUserPreferences`, `useUpdateUserPreferences`, `useEffectiveDefaultWatchlistId`
  - preference priority: `preference.default_watchlist_id` → watchlist `is_default` flag → first watchlist

**Watchlist 관리 UI 고도화**
- `pages/Watchlist/index.tsx` — 목록 rename(inline) / delete / set-default(메뉴 드롭다운) + item memo 인라인 편집 + item 필터/검색 + 에러별 분기(409/422/404)
- 기본 목록 삭제 허용 (API ON DELETE SET NULL 정책 반영), 삭제 후 deselect

**UserPreference Settings UI**
- `pages/Settings/index.tsx` — 기존 read-only 진단 위에 UserPreference 섹션(writable) 추가
  - default_watchlist_id 선택(watchlist 목록 연동) / default_market / default_strategy / notification on-off (UI 저장 전용, 실제 발송 없음)
  - 저장 성공 메시지 / 401/404/422 에러 분기

**TodayReport / StockDetail 연동**
- `WatchlistCard` — `useEffectiveDefaultWatchlistId` 사용 (preference → fallback)
- `FavoriteButton` — `useEffectiveDefaultWatchlistId` 사용 (preference → fallback), 409 idempotent 처리

**테스트**
- `tests/WatchlistManage.test.tsx` 신규 — 21 tests (rename/409/cancel, set-default, delete/404, memo/422/cancel, item filter, forbidden fields)
- `tests/UserPreferences.test.tsx` 신규 — 15 tests (Settings GET/PUT, TodayReport preference priority, FavoriteButton preference, 409 idempotent, 500 error)
- `tests/mswServer.ts` — PATCH/DELETE watchlist, PATCH item, GET/PUT preferences 핸들러 추가
- 기존 테스트 회귀 0건

**보안 / forbidden field**
- UserPreference 폼에 password/token/jwt_secret/broker/quantity/order_price/자동매매/매수/매도 미노출 검증
- 알림 설정: UI 저장 전용, Telegram/실 발송 연결 0건

---

### v0.9 Phase C 결과 (요약) — Watchlist 고도화 + UserPreference + Provider 회복성

- 마감 게이트: backend pytest **916 passed** (1 deselected) — 47건 순증
- 산출 태그: `v0.9-watchlist-api` (예정)
- frontend / e2e / build 변경 0건 (Phase C 는 백엔드만; 프런트 관리 UI 는 Phase D)

산출물:

**Watchlist API 고도화 (4 신규 엔드포인트)**
- `PATCH /api/watchlists/{id}` — rename / set_default (기존 default 자동 demote)
- `DELETE /api/watchlists/{id}` — watchlist 자체 삭제 (items cascade)
- `GET /api/watchlists/{id}/items` — 페이지네이션 + symbol_prefix 필터 (total/items/limit/offset)
- `PATCH /api/watchlists/{id}/items/{symbol}` — memo 수정 / null 로 초기화

**UserPreference — 32번째 테이블**
- `UserPreference` ORM 모델: `default_watchlist_id` FK (`ondelete="SET NULL"`) / `default_market` / `default_strategy` / `dashboard_layout_json` / `notification_preferences_json`
- Alembic revision `0004_user_preferences` (down_revision `0003_watchlist`, `compare_metadata` diff 0건)
- `UserPreferenceRepository`: `get_or_create_for_user` / `update` (sentinel partial) / `set_default_watchlist` / `update_dashboard_layout` / `update_notification_preferences`
- `GET /api/users/me/preferences` — lazy create on first call
- `PUT /api/users/me/preferences` — watchlist ownership 검증, 비밀 키 rejection (422)
- cross-user isolation: 모든 신규 엔드포인트 타 유저 자원 → 404 (403 not 404 — existence 비노출)

**Provider 회복성 skeleton**
- `ProviderErrorKind` str enum (TIMEOUT / RATE_LIMIT / SERVER_ERROR / CLIENT_ERROR / UNKNOWN)
- `ProviderCallResult` dataclass (`.ok()` / `.fail()` class methods)
- `retry_with_backoff()` — exponential backoff (`base_delay_s * 2^(attempt-1)`, `max_delay_s` cap), `CLIENT_ERROR` 비재시도
- `CircuitBreaker` dataclass — CLOSED → OPEN (N failures) → HALF_OPEN (timeout) → CLOSED (probe 성공) / OPEN (probe 실패)
- 실 provider 강제 래핑 0건 (opt-in skeleton)

**보안 / forbidden field 가드**
- 모든 신규 API 응답에 password / password_hash / access_token / jwt_secret / secret / broker / account / quantity / order_price / order_type / side / source_file_path **0건** 검증 완료
- `notification_preferences_json` 에 비밀 키 포함 시 422 반환

**테스트**
- `tests/integration/test_watchlist_phase_c.py` 20건 신규
- `tests/integration/test_user_preferences.py` 17건 신규 (repository 7 + API GET/PUT 5 + auth required 2 + forbidden field guard 2 + secret key rejection 1)
- `tests/unit/test_provider_resilience.py` 19건 신규 (retry 9 + circuit breaker 10)
- `test_alembic_migration.py`: HEAD_REVISION `0004_user_preferences`, EXPECTED_TABLE_COUNT 32
- `test_auth_security.py`: mutating endpoint count 9 (auth 2 + watchlist 6 + preferences 1)

**Alembic head:** `0003_watchlist` → `0004_user_preferences`, `compare_metadata` diff 0건

---

## 0-1. v0.8 마감 선언 — User & Migration Foundation (강등됨)

> v0.9 시작 선언 시점에 §0-1 로 강등.

**v0.8 cycle 마감.** 기준선 `v0.7-final` (HEAD `1f5b01f`) 위에 **User &
Migration Foundation** 5 phase 완료. v0.1 ~ v0.7 동안 일관 유지된 read-only
정책의 **첫 변경 cycle** — Alembic baseline + 단일 사용자 인증 + Watchlist
도메인 POST/DELETE 첫 도입 + Watchlist 프런트 11번째 화면 모두 마감.

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 마감 게이트: backend pytest **808 passed (1 deselected)**
  / frontend vitest **113 passed** / Playwright e2e **19 passed** / build 그린
- 누적 인수 태그: `v0.8-alembic-baseline` → `v0.8-auth-foundation` →
  `v0.8-watchlist-api` → `v0.8-frontend-watchlist` → **`v0.8-final`**
- 마감 사유: [`RELEASE_NOTES_v0.8.md`](./RELEASE_NOTES_v0.8.md)

### v0.8 마감 요약

| Phase | 작업 | 상태 | 산출 태그 | 게이트 |
|---|---|---|---|---|
| A | Alembic baseline (27 테이블 + CI smoke) | ✅ 인수 | `v0.8-alembic-baseline` | pytest 698 |
| B | 단일 사용자 인증 (User 28 + LoginAuditLog 29 + JWT + scrypt) | ✅ 인수 | `v0.8-auth-foundation` | pytest 760 |
| C | Watchlist DB / API (Watchlist 30 + WatchlistItem 31 + 5 라우터) | ✅ 인수 | `v0.8-watchlist-api` | pytest 808 |
| D | Watchlist 프런트 + Login + FavoriteButton + WatchlistCard | ✅ 인수 | `v0.8-frontend-watchlist` | vitest 113 / e2e 19 |
| E | RELEASE_NOTES + 문서 마감 | ✅ 완료 | `v0.8-final` | 4 게이트 그린 |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0008`, 체크리스트는 [`TASKS.md`](./TASKS.md)
`v0.8 — User & Migration Foundation` 섹션 참조.

---

## 0-2. v0.8 시작 선언 — User & Migration Foundation (강등됨)

> v0.8 Phase E 시점에 §0-1 로 강등. 원본 §0 (v0.8 시작 선언) 의 상세 내용을 보존.

### 후보 비교 / 선택 사유 (요약)

10 개 v0.8 후보 중 채택:

- ✅ **Alembic baseline 도입** (Phase A) — 27 테이블 + 누적 ALTER 5건 시점, Watchlist 신규 테이블 추가 전 baseline 잡는 것이 자연
- ✅ **단일 사용자 인증** (Phase B) — POST 라우터 첫 도입 전제. `AUTH_ENABLED` 토글로 dev/CI 호환성 유지
- ✅ **Watchlist DB/API + 프런트** (Phase C·D) — POST 첫 도입의 자연스러운 후보 (단일 도메인 + 단일 사용자 + audit log 동반)

미채택 → v0.9+ 로 미룸:

- ❌ **사용자 설정 (관심 시장 / 알림 선호도)** — Watchlist 와 묶으면 단일 cycle 범위 초과 (v0.9)
- ❌ **운영 모니터링 (Sentry / Prometheus)** — 외부 노출 시점에 함께 도입 권장 (v0.9)
- ❌ **실 DART API 구현체** — 라이선스 검토 (사람) 가 코드 cycle 외 단계 (v0.9+)
- ❌ **실 RSS / News API 구현체** — 라이선스 검토 동반 (v0.9+)
- ❌ **백테스트 고도화** — v0.7 placeholder 운영 데이터 누적 후 (v0.9+)
- ❌ **LLM 보강** — 룰 기반 검증 + 운영 데이터 누적 후 (v0.10+)
- ❌ **자동매매 / 실주문** — 별도 보안/컴플라이언스/자본 한도 사이클 선행 (Future Backlog)

### v0.8 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ Broker 구현 (`BrokerInterface` placeholder 유지)
- ❌ POST 라우터 확장 — `POST /api/auth/login` + `POST /api/auth/logout` + `GET /api/auth/me` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}` **5건만**. 그 외 도메인 (Recommendations / Holdings / Backtest / 잡 트리거 / 알림 / 점수 등) POST/PUT/DELETE 0건
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 의 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (v0.10+ 검토)
- ❌ ScoringEngine 본 weight 변경 — RecommendationEngine / HoldingCheckEngine 산식 0건 변경
- ❌ HoldingCheckEngine 산식 변경
- ❌ LLM 자동 전략 생성 / 자동 분석
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.9 후보
- ❌ Watchlist 자동 텔레그램 / 가격 알림 — 알림 시스템 변경 0건
- ❌ 다중 사용자 / SaaS / RBAC — 단일 admin user 만
- ❌ OAuth / SSO — 단일 username/password + bcrypt + JWT 만
- ❌ Refresh token / token revocation list — 24h JWT TTL + 재로그인만
- ❌ WebSocket / SSE — 폴링 그대로
- ❌ Recommendations / Backtest / Today 산식 변경 — 즐겨찾기는 표시/필터만, 정렬·점수 변경 0건

### v0.8 백엔드 정책 변경 안내

`v0.7-final` 동결을 v0.8 에서 일부 깬다. 변경 범위는 다음으로 한정 — 그 외 도메인의 POST/PUT/DELETE / 자동매매 코드 / 본 weight 산식은 추가하지 않는다.

- POST 라우터 5건 신규 (auth 3건 + watchlist 2건)
- DB 신규 테이블 4개 (User 28 + LoginAuditLog 29 + Watchlist 30 + WatchlistItem 31)
- Alembic 도입 + baseline + revision 3건 (0001 baseline + 0002 user_audit + 0003 watchlist)
- `app/auth/` 패키지 신규 (`AuthService` + `JwtIssuer` + `PasswordHasher` + `get_current_user` + `require_auth`)
- `Settings` 4 필드 추가 (`AUTH_ENABLED` / `JWT_SECRET` / `JWT_TTL_HOURS` / `PROTECT_GET_ROUTES`)
- 의존성 2개 추가 (`bcrypt>=4.0` + `pyjwt>=2.8` + `alembic>=1.13`)

기존 GET 라우터 동작 / scheduler / KIS / DART / Telegram / ScoringEngine / HoldingCheckEngine / BacktestEngine / CostModel / regime_split / `Settings` 기존 필드 모두 변경 0건. `AUTH_ENABLED=false` (default) 모드에서 v0.7 회귀 테스트 100% 그대로 통과.

### Alembic baseline 전략 (요약)

- baseline `0001_baseline_v0_7.py` = v0.7 마감 시점의 27 테이블을 `op.create_table()` 27건 SQL 로 풀어 쓴 표준 Alembic 패턴 (autogenerate 결과)
- `target_metadata = app.db.models.Base.metadata`, `Settings.database_url` 분기 (SQLite + PostgreSQL 양쪽 지원)
- 신규 환경: `alembic upgrade head` 하나로 27 테이블 → 31 테이블 전부 생성
- 기존 운영 DB: `alembic stamp 0001_baseline_v0_7` → `alembic upgrade head` (Phase B/C 의 0002, 0003 만 실제 실행)
- CI 잡 추가: 임시 SQLite 에 `alembic upgrade head` → ORM `Base.metadata` 와 `MigrationContext.compare_metadata` diff 0건 단언
- offline mode SQL 출력 가능 (`alembic upgrade head --sql`)
- 운영 DB 적용 절차는 `INTEGRATION_RUNBOOK.md` §17 신규에 명시 (backup → stamp → upgrade → smoke → rollback)

### 인증 / Watchlist 정책 (요약)

**`AUTH_ENABLED` 토글 (`app/config.py` Settings 신규)**:

| 환경 | 기본값 | 동작 |
|---|---|---|
| dev / local | `false` | `require_auth` 가드가 우회. 모든 라우터 OPEN. 단일 admin user 자동 사용 (user_id=1 fixed return) |
| CI | `false` | dev 동일 — 기존 회귀 테스트 그대로 통과 |
| prod | `true` (운영자 명시) | `require_auth` 가드 활성. 보호 라우터가 401 반환. `JWT_SECRET` 미설정 시 startup 거부 |

**JWT 정책**: HS256, TTL 24h (`Settings.jwt_ttl_hours`), refresh token 미도입, payload 에 `user_id` + `username` 만 (이메일 / role 미도입). bcrypt cost 12 (단위 테스트는 cost 4).

**audit log (`LoginAuditLog`)**: `LOGIN_SUCCESS` / `LOGIN_FAILED` / `LOGOUT` 이벤트 모두 기록. `source_ip` 는 SHA256 해시만 저장 (평문 IP 0건). `user_agent` ≤255자.

**Watchlist 데이터 모델**: `Watchlist` (user_id FK + name + is_default) + `WatchlistItem` (watchlist_id FK ON DELETE CASCADE + symbol + memo ≤500자). 단일 사용자 환경에서는 user_id=1 fixed.

**Watchlist 라우터**:

- `GET /api/watchlists` (목록, 인증 필수 — `AUTH_ENABLED=true` 시)
- `GET /api/watchlists/{id}/items` (목록, 인증 필수)
- `POST /api/watchlists/{id}/items` (`require_auth` 가드, body `{symbol, memo?}`)
- `DELETE /api/watchlists/{id}/items/{symbol}` (`require_auth` 가드)

응답 / 본문에 `broker` / `account` / `quantity` / `order_*` / `source_file_path` 0건 (e2e raw JSON 가드).

### v0.9+ 후보 (시작 시점 미리 정리)

자세한 분류는 [`ROADMAP.md`](./ROADMAP.md) §8 + [`PLANS.md`](./PLANS.md) `PLAN-0008` "v0.9+ 후보". 한 줄 요약:

- **사용자 설정 (관심 시장 / 기본 필터 / 알림 선호도)** — 인증 후 자연 확장
- **운영 모니터링 (Sentry / Prometheus / Grafana)** — 외부 노출 시점에 함께
- **실 DART / 실 RSS provider** — 라이선스 검토 동반
- **백테스트 고도화** — 다중 전략 / walk-forward / 종목별 stamp duty
- **LLM 보강** — News sentiment / 재무 분석 / 자동 전략 생성
- **WebSocket / SSE** — 실시간 잡 / 백테스트 진행
- **모바일 / lightweight-charts 마이그레이션** — UX 고도화
- **Watchlist 가격 알림 / target return alert** — 알림 시스템 변경 = 별도 cycle
- **인증 고도화 (다중 사용자 / OAuth / SSO / refresh token)** — 단일 사용자 검증 후

### 위험 요소 (요약)

- **Alembic baseline 의 빈 DB 호환성** — baseline 을 `op.create_table()` 27건 SQL 로 풀어 쓰는 표준 패턴 채택 + autogenerate diff 0건 단언 테스트로 방어
- **운영 DB 의 Alembic stamp 누락** — INTEGRATION_RUNBOOK §17 에 stamp 절차 명시 + Phase A 통합 테스트가 stamp 시나리오 커버
- **`AUTH_ENABLED=false` 모드의 보안 함정** — startup 시 `prod` 환경 + `AUTH_ENABLED=false` 결합 감지 → stderr 경고
- **`JWT_SECRET` 미설정** — `AUTH_ENABLED=true` 시 startup 거부
- **POST 라우터 첫 도입의 evidence 노출 위험** — Watchlist 응답 schema 에 forbidden token 0건 가드 (e2e raw JSON 검사)
- **CSRF / SameSite / Content-Security-Policy** — JWT localStorage 저장 → CSRF 자동 보호. CSP 헤더 도입은 v0.9 운영 모니터링 cycle 후보
- **누적 신규 테이블 4개 + Alembic 도입** — 27 → 31 테이블. 기존 ALTER 0건 (모든 신규는 신규 테이블만)
- **`useMutation` 첫 도입** — v0.7 까지 `useQuery` 만 사용. msw v2 + Playwright mutation flow 가드 신규

### v0.8 Phase A 결과 (요약) — Alembic baseline 도입

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 회귀 게이트: backend pytest **682 → 698 passed (+16)** (1 deselected 그대로),
  frontend / e2e / build 변경 0건 (Phase A 는 백엔드 인프라만)
- 누적 인수 태그 (예정): `v0.8-alembic-baseline`

**산출물:**

- `alembic.ini` (script_location / `path_separator = os` / sqlalchemy.url 비워둠 — env.py 가 Settings 에서 결정)
- `alembic/env.py` — `target_metadata = Base.metadata` + `_resolve_database_url()` 가
  `-x url=...` > `alembic.ini` > `Settings.effective_database_url` 순으로 해석.
  SQLite 시 `render_as_batch=True`. `compare_type=True` + `compare_server_default=True`.
  offline / online 양쪽 지원.
- `alembic/script.py.mako` — 표준 revision 템플릿
- `alembic/versions/0001_baseline_v0_7.py` — autogenerate 결과 (빈 SQLite 대상).
  `op.create_table()` 27건 (FK / Unique / Index 모두 포함), `op.drop_table()` 27건
  역순. Phase A 정책 명시 docstring (신규 DB 절차 / stamp 절차 / 운영 적용 / 자동
  생성 origin / `compare_metadata` 가드).
- `scripts/migrate.py` — `alembic` thin wrapper 7 subcommand (`current` / `history` /
  `heads` / `upgrade --to` / `downgrade --to` / `stamp --revision` / `offline-sql --to`).
  `--db-url` override + `--ini` 경로 옵션. 명시 실행만 (자동 호출 금지).
- `tests/integration/test_alembic_migration.py` — **16 케이스**:
  - `test_baseline_revision_exists_and_is_head` — `0001_baseline_v0_7` 가 단일 head
  - `test_upgrade_head_creates_all_27_tables` — 27 테이블 + spot-check 9
  - `test_alembic_version_table_stamped_at_baseline` — `MigrationContext.get_current_revision()`
  - `test_compare_metadata_after_upgrade_is_empty` — **load-bearing**: ORM 변경 시 CI fail
  - `test_stamp_marks_existing_db_at_baseline_without_running_ddl` — 운영 stamp 시나리오
  - `test_downgrade_base_cleanly_drops_all_baseline_tables` — round-trip
  - `test_offline_mode_emits_sql_without_connecting` — DB 미생성 + SQL 출력
  - `test_spot_check_each_required_table_present` — parametrize 9 테이블
- `pyproject.toml` — `alembic>=1.13,<2.0` 추가
- `.github/workflows/ci.yml` — backend 잡 내부 `alembic upgrade head` step 추가
  (`RUNNER_TEMP/ci_alembic_smoke.db` 임시 DB 사용)
- `INTEGRATION_RUNBOOK.md` §17 신규 (8 sub-section: 골격 / 신규 DB / stamp /
  Phase B 후속 revision / 운영 upgrade / 실패 롤백 / Settings 정합성 / 안전 가드)
- `DB_SCHEMA.md` 상단 — "v0.8 부터 Alembic 으로 관리" + baseline revision 경로 +
  CI compare_metadata 가드 명시
- `TESTING.md` §6.16 신규 — Alembic migration 16 케이스 상세

**Baseline 전략:**

- v0.7-final HEAD `1f5b01f` 시점의 27 테이블을 baseline 으로 등록
- `op.create_table()` 27건 / `op.drop_table()` 27건 역순 — autogenerate 가 FK
  의존성 순서대로 정렬
- 신규 DB: `alembic upgrade head` 한 번에 27 테이블 생성
- 기존 운영 DB: 백업 → `alembic stamp 0001_baseline_v0_7` → DDL 0건, 이후
  Phase B/C revision 만 `upgrade head` 로 layering
- 롤백: 운영은 백업 복구가 원칙 (`alembic downgrade` 는 dev / 검증용)
- `compare_metadata` 검증: ORM 변경 시 revision 누락이 즉시 CI fail

**안전 범위:**

- DB 모델 / ScoringEngine / RecommendationEngine / HoldingCheckEngine /
  BacktestEngine / CostModel / regime_split 변경 0건
- POST / PUT / DELETE 라우터 0건 (Phase A 는 인프라만)
- frontend 변경 0건 (vitest / build / e2e 영향 없음)
- 외부 API (KIS / DART / RSS / Telegram) 호출 0건 — `alembic` /
  `scripts/migrate.py` 에 import 0건
- 테스트는 `tmp_path` 임시 SQLite 만 사용 — 운영 / 개발 DB 0건 접근
- CI 는 `RUNNER_TEMP/ci_alembic_smoke.db` 만 사용

### v0.8 Phase B 결과 (요약) — 단일 사용자 인증 foundation

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 회귀 게이트: backend pytest **698 → 760 passed (+62)** (1 deselected 그대로),
  frontend / e2e / build 변경 0건 (Phase B 는 백엔드 + CLI 만; 프런트 로그인
  화면은 Phase D 후보)
- 누적 인수 태그 (예정): `v0.8-auth-foundation`

**산출물:**

- `app/db/models.py` — `User` (28번째 테이블, username unique + scrypt
  password_hash + is_active + is_admin + last_login_at) + `LoginAuditLog`
  (29번째 테이블, username + user_id FK + event_type + source_ip_hash +
  user_agent_hash + 복합 index 2종)
- `app/data/repositories/users.py` — `UserRepository` (5 method) +
  `app/data/repositories/login_audit_logs.py` — `LoginAuditLogRepository`
  (4 method) + EVENT 상수 + event_type validation
- `app/auth/security.py` — scrypt 기반 `PasswordHasher` (bcrypt 대신; MSYS2
  UCRT64 wheel 부재 + 보안 동등성 — 메모리 hard) + `JwtIssuer` (HS256, 24h
  default) + `hash_for_audit` (SHA256) + `AuthService` (login → audit + token,
  generic failure) + `validate_auth_settings` (AUTH_ENABLED=true → JWT_SECRET
  필수)
- `app/auth/dependencies.py` — `get_current_user` (AUTH_ENABLED=false 시 dev
  fallback user_id=1, true 시 Bearer token 검증) + `require_auth` (Phase C
  Watchlist 보호 라우터용 placeholder) + ephemeral per-process secret +
  `extract_client_ip`
- `app/api/auth_routes.py` — `POST /api/auth/login` (첫 POST) +
  `POST /api/auth/logout` + `GET /api/auth/me`. Pydantic schema 자체 정의
  (LoginRequest / LoginResponse / LoginUser / LogoutResponse / MeResponse)
- `app/main.py` — auth_router include + `validate_auth_settings(settings)`
  startup 호출
- `app/config/settings.py` — `auth_enabled` / `jwt_secret` / `jwt_algorithm`
  / `jwt_expires_minutes` / `password_hash_n` / `r` / `p` 7 필드 추가
- `scripts/create_admin.py` — argparse CLI (interactive / env var / `--db-url`
  / `--no-admin` / `--update-if-exists`) + 평문 / hash 출력 0건
- `alembic/versions/0002_auth_foundation.py` — autogenerate 결과 (down_revision
  = `0001_baseline_v0_7`) + Phase B 정책 docstring
- `pyproject.toml` — `PyJWT>=2.8,<3.0` 추가. bcrypt 미채택 사유 (scrypt
  stdlib 채택) inline comment
- `tests/unit/test_auth_security.py` — **26 케이스** (PasswordHasher / JwtIssuer
  / hash_for_audit / validate_auth_settings)
- `tests/integration/test_auth_repositories.py` — **15 케이스** (User /
  LoginAuditLog 검증, **평문 IP/UA 미저장 가드 포함**)
- `tests/integration/test_auth_routes.py` — **14 케이스** (AUTH_ENABLED=false
  + true 양쪽 모드, generic 401, audit hash 가드, 기존 read-only OPEN 가드)
- `tests/integration/test_create_admin_cli.py` — **5 케이스** (정상 생성 /
  중복 / update-if-exists / no-admin / empty password)
- `tests/integration/test_alembic_migration.py` 갱신 — `HEAD_REVISION =
  "0002_auth_foundation"` + `EXPECTED_TABLE_COUNT = 29` + spot-check 11 →
  13 항목 (users + login_audit_logs 추가). `compare_metadata` diff 0건 가드
  유지
- `API_SPEC.md` §17 신규 — auth endpoint 3개 + 정책 + 금지 API 갱신
- `DB_SCHEMA.md` §28 / §29 신규 + 상단 헤더 (27 → 29 테이블)
- `INTEGRATION_RUNBOOK.md` §18 신규 (6 sub-section)
- `TESTING.md` §6.17 신규 (5 sub-section + 회귀 기준)

**Auth settings 정책 요약:**

| 환경 | `AUTH_ENABLED` | 동작 |
|---|---|---|
| dev / local / CI | `false` (default) | 기존 GET 라우터 그대로 OPEN. login 도 ephemeral per-process secret 으로 동작 (재시작 시 token 무효) |
| prod | `true` (`.env` 명시) | `require_auth` 가드 활성. `JWT_SECRET` 미설정 시 startup 거부 |

- `JWT_SECRET` 누락 + AUTH_ENABLED=true → `MissingSecretError` (startup 거부)
- bcrypt 대신 stdlib `hashlib.scrypt` (RFC 7914, 메모리 hard, MSYS2 UCRT64
  wheel 부재 회피, n=2^14 default)
- JWT TTL 기본 24h, refresh token 미구현 (만료 시 재로그인)

**보안 가드 결과:**

- 평문 password 저장 0건 — `users.password_hash` 는 항상 scrypt
- 평문 IP / 평문 user agent 저장 0건 — `login_audit_logs.source_ip_hash` /
  `user_agent_hash` 는 항상 SHA256 hex 64자 (e2e 단언)
- API 응답에 `password_hash` / `scrypt$` 0건 (login + me 응답 + create_admin
  CLI stdout/stderr 모두 가드)
- Login 실패 응답이 unknown user / wrong password / deactivated 를 generic
  메시지로 통일 — username 존재 여부 노출 0건
- ScoringEngine / RecommendationEngine / HoldingCheckEngine / BacktestEngine
  / CostModel / regime_split 변경 0건
- 기존 read-only GET 라우터 동작 변경 0건 (AUTH_ENABLED=true 에서도 OPEN)
- POST 라우터 = `/api/auth/login` + `/api/auth/logout` 2건만. 그 외 도메인
  POST/PUT/DELETE 0건

**Alembic head:**

- `0001_baseline_v0_7` → `0002_auth_foundation` (down_revision 정합)
- `compare_metadata` diff 0건 단언 통과 (load-bearing 가드)
- baseline `0001` 은 변경 0건 (Phase A 결과 그대로)

### v0.8 Phase C 결과 (요약) — Watchlist DB / API

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 회귀 게이트: backend pytest **760 → 808 passed (+48)** (1 deselected 그대로),
  frontend / e2e / build 변경 0건 (Phase C 는 백엔드만; 프런트 Watchlist 화면 /
  Login 화면 / StockDetail 별 토글은 Phase D 후보)
- 누적 인수 태그 (예정): `v0.8-watchlist-api`

**산출물:**

- `app/db/models.py` — `Watchlist` (30번째, user_id FK + name + is_default +
  Unique(user_id, name) + User.watchlists relationship cascade) +
  `WatchlistItem` (31번째, watchlist_id FK ON DELETE CASCADE + symbol(32) index +
  memo(500) nullable + Unique(watchlist_id, symbol)). **broker / account /
  quantity / order_* / 가격 컬럼 0건** (회귀 단언)
- `app/db/__init__.py` — Watchlist + WatchlistItem re-export
- `app/data/repositories/watchlists.py` — `WatchlistRepository` 8 method, 단일
  default invariant 강제 (`_clear_default_for_user`), ownership-scoped 조회만
  노출 (`get_by_user_and_id`), `DEFAULT_WATCHLIST_NAME = "기본"`
- `app/data/repositories/watchlist_items.py` — `WatchlistItemRepository` 7
  method + `normalize_symbol` (trim + UPPER) + `MAX_MEMO_LENGTH = 500` +
  `_validate_memo` defensive ValueError
- `app/data/repositories/__init__.py` — 두 신규 repo export
- `app/api/watchlist_routes.py` 신규 — 5 라우터 (`GET /api/watchlists` +
  `GET /api/watchlists/{id}` + `POST /api/watchlists` +
  `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`).
  모두 `require_auth` 가드, cross-user 시 **404** (403 아님). symbol 은 stocks
  테이블 존재 검증 후 추가. Pydantic schema 자체 정의 (8종)
- `app/api/__init__.py` + `app/main.py` — watchlist_router include
- `alembic/versions/0003_watchlist.py` — autogenerate 결과 (down_revision =
  `0002_auth_foundation`) + Phase C 정책 docstring
- `tests/integration/test_watchlist_repositories.py` — **27 케이스**
- `tests/integration/test_watchlist_routes.py` — **19 케이스** (AUTH=false 12
  + AUTH=true 4 + 보안/spoofing 3)
- `tests/integration/test_alembic_migration.py` 갱신 — `HEAD_REVISION =
  "0003_watchlist"` + `EXPECTED_TABLE_COUNT = 31` + spot-check 13 → 15
- `API_SPEC.md` §18 + 헤더 + 금지 API 갱신 (Phase C 5건 누적)
- `DB_SCHEMA.md` §30 / §31 + 헤더 (29 → 31 테이블)
- `INTEGRATION_RUNBOOK.md` §19 신규 (6 sub-section)
- `TESTING.md` §6.18 신규

**Watchlist API 정책 요약:**

| 라우터 | 인증 | 동작 |
|---|---|---|
| `GET /api/watchlists` | require_auth | user 의 watchlist 목록 (default 우선 정렬, item_count 포함) |
| `GET /api/watchlists/{id}` | require_auth | 상세 + items[]. cross-user / missing → 404 |
| `POST /api/watchlists` | require_auth | body `{name, is_default?}`. 중복 name → 409, 빈 name → 422, is_default 단일 invariant |
| `POST /api/watchlists/{id}/items` | require_auth | body `{symbol, memo?}`. symbol normalize (trim + UPPER), stocks 미존재 → 404, 중복 → 409, memo > 500 → 422 |
| `DELETE /api/watchlists/{id}/items/{symbol}` | require_auth | path symbol 도 normalize. missing → 404 |

**인증 / 권한 정책:**

- `AUTH_ENABLED=true`: 5 라우터 모두 Bearer token 필수. 토큰 없음 / 무효 / 만료 →
  401 + `WWW-Authenticate: Bearer`
- `AUTH_ENABLED=false` (dev / CI default): `require_auth` 가 dev fallback
  identity (user_id=1) 로 해석 — 기존 read-only 흐름 유지
- 다른 user 의 watchlist 접근 시 **404** (403 아님 — ownership 노출 0건)
- request body 의 `user_id` 는 schema 에 정의되지 않아 자동 drop —
  spoofing 시도 시 새 watchlist 가 token 의 user 에게 귀속 (회귀 단언:
  `test_request_body_user_id_is_ignored`)
- 기존 read-only GET 라우터는 여전히 OPEN (Watchlist 만 보호). Phase C 가
  read-only 정책 retrofit 안 함

**Forbidden field / 보안 가드 결과:**

- `WatchlistItem.__table__.columns` 에 broker / account / quantity / order_price
  / order_type / side / buy_price / sell_price 0건 (회귀 단언:
  `test_no_order_or_quantity_columns_on_watchlist_item`)
- 모든 응답 (list / create / detail / item create) recursive 스캔 → forbidden
  토큰 (broker / account / quantity / order_* / source_file_path / password_hash
  / password / token / secret / jwt_secret / scrypt$) 0건
  (`test_response_never_leaks_password_hash_or_token`)
- cross-user 접근 시 동일 404 메시지 — ownership 노출 0건
- request body user_id spoofing → token user 우선

**Alembic head:**

- `0002_auth_foundation` → `0003_watchlist` (down_revision 정합)
- `compare_metadata` diff 0건 (load-bearing)
- 0001 / 0002 변경 0건
- 운영 적용: `alembic upgrade head` 한 번이면 Phase B → C 차이 적용 (
  INTEGRATION_RUNBOOK §17.5 절차)

---

## 0-3. v0.7 마감 선언 — Strategy & Backtest Foundation

**v0.7 cycle 마감.** 기준선 `v0.6-final` (HEAD `e729d60` 시점, origin/main
동기화 완료, 5 누적 태그 모두 push 완료). v0.1 backend + v0.2 frontend + v0.3
분석·운영 + v0.4 Analyst & Theme Intelligence + v0.5 News·공시·테마 랭킹 +
v0.6 Fundamental & Earnings Intelligence 모두 마감 위에 **Strategy / Backtest
기초** 5 phase 누적 완료. 누적 인수 태그는 `v0.7-frontend-backtest` (Phase D)
이고, Phase E 마감 후 태그 `v0.7-final` 부여 예정.

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 마감 게이트: backend pytest **682 passed** (1 deselected: `.env` dev override
  의존 `test_settings_defaults`, CI clean env 자동 통과) / frontend vitest
  **84 passed** / frontend build 그린 / Playwright e2e **14 passed**
- 누적 인수 태그: `v0.7-strategy-interface` → `v0.7-backtest-engine` →
  `v0.7-backtest-cost-regime` → **`v0.7-frontend-backtest`** → `v0.7-final`
  (Phase E 후 부여)
- 마감 사유: [`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md)

### v0.7 핵심 산출물 한 줄 요약

- **`StrategyInterface` ABC + 룰 기반 전략 3종 첫 도입** (Phase A) —
  `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy`. pure-function +
  `[0, 1]` confidence 자동 clamp + null/malformed evidence 에서도 raise 0건.
  `StrategySignal` 은 분석 신호이지 매매 주문 아님 — `ScoreSnapshot` 에 broker /
  주문 / 가격 / 수량 / 계좌 필드 0건.
- **`BacktestRun` (26번째) + `BacktestResult` (27번째) + `BacktestEngine` + CLI**
  (Phase B) — `recommendations` + `recommendation_results` 위에 전략 replay →
  승률 / 평균 수익률 / max drawdown 계산. BUY-only metrics + horizon 별
  `missing_result_count_per_horizon`. `scripts/run_backtest.py` argparse CLI
  default dry-run.
- **`CostModel` placeholder + 시장 국면별 분리** (Phase C) — `total_cost = 0.33%`
  차감 (`constant-v1`) + `assign_regime(session, signal_date)` (`MarketRegime.date
  <= signal_date` 가장 최근). `cost_adjusted_return_5d` / `regime` 컬럼 +
  `regime_breakdown` summary. 실 broker fee schedule fetch 는 v0.8+ 후보.
- **백엔드 read-only API 3종 + 프런트 10번째 화면 `/backtest`** (Phase D) —
  `GET /api/strategies` (registry 기반, DB 0건) + `GET /api/backtest/runs?strategy=&limit=`
  + `GET /api/backtest/runs/{run_id}` (regime breakdown + cost_model_version +
  BUY-only notes). Sidebar `백테스트 (β)` 메뉴 (9 → 10).

### v0.7 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | `StrategyInterface` + `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` 3종 + 단위 테스트 | ✅ 완료 | `v0.7-strategy-interface` |
| B | `BacktestRun` (26) + `BacktestResult` (27) + `BacktestEngine` + `scripts/run_backtest.py` CLI + 통합 테스트 | ✅ 완료 | `v0.7-backtest-engine` |
| C | `CostModel` placeholder (총 0.33%) + `assign_regime` + `cost_adjusted_return_5d` / `regime` 컬럼 | ✅ 완료 | `v0.7-backtest-cost-regime` |
| D | read-only API 3종 + 프런트 10번째 화면 `/backtest` + Sidebar `백테스트 (β)` | ✅ 완료 | `v0.7-frontend-backtest` |
| E | `RELEASE_NOTES_v0.7.md` + README / PROJECT_STATUS / TASKS / ROADMAP / 정합성 점검 + tag `v0.7-final` | ✅ 문서 마감 (코드 변경 0건) | `v0.7-final` (Phase E 후 부여) |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0007`, 체크리스트는 [`TASKS.md`](./TASKS.md)
`v0.7 — Strategy & Backtest Foundation` 섹션 참조.

### v0.8 후보 (마감 후 검토 대기)

자세한 분류는 [`ROADMAP.md`](./ROADMAP.md) §8 + [`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md)
"v0.8 후보". 한 줄 요약:

- **인증 / Watchlist (POST 첫 도입)** — 단일 토큰 → POST 라우터 → Watchlist (인증 동반 필수). 백테스트 run 트리거 UI 도 함께
- **Alembic 도입** — 누적 ALTER 5건 시점 (v0.5 1건 + v0.6 2건 + v0.7 2건) 진입 적기
- **실 DART / 실 RSS provider** — v0.5/v0.6 ABC 위에 실 구현체. 라이선스 검토 동반
- **운영 모니터링** — Sentry / Prometheus / Grafana, 인증 도입 후
- **백테스트 고도화** — 다중 전략 동시 / walk-forward / 종목별 stamp duty / 호가 단위 슬리피지
- **LLM 보강** — 룰 기반 전략 → LLM 자동 생성, sentiment / 재무 분석
- **모바일 / lightweight-charts 마이그레이션** — UX 고도화

---

## 0-4. v0.7 진행 선언 — Strategy & Backtest Foundation (강등됨, Phase D 시점 스냅샷)

**v0.7 cycle 진행 중 (Phase D 완료).** 기준선 `v0.6-final`
(HEAD `e729d60` 시점, origin/main 동기화 완료, 5 누적 태그
`v0.6-fundamental-data-layer` → `v0.6-earnings-event-pipeline` →
`v0.6-fundamental-score` → `v0.6-frontend-fundamentals` → `v0.6-final` 모두
push 완료). v0.1 backend + v0.2 frontend + v0.3 분석·운영 + v0.4 Analyst &
Theme Intelligence + v0.5 News·공시·테마 랭킹 + v0.6 Fundamental & Earnings
Intelligence 모두 마감 위에 **Strategy / Backtest 기초** 5 phase 를 진행한다.
v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의
저작권 정책 + v0.5 의 자동 fetch default OFF + v0.6 의 evidence whitelist +
ScoringEngine 본 weight 0건 변경 정책 모두 그대로 유지한다.

### v0.7 핵심 목표

v0.1~v0.6 누적된 추천 판단 축 (technical / report / theme / news / disclosure /
fundamental / earnings + risk_penalty + recommendation_results 1·3·5·20일) 위에
**`StrategyInterface` ABC + 룰 기반 전략 2~3종 + `BacktestEngine` + 비용 모델 +
시장 국면별 분리 + 백테스트 결과 read-only 화면** 을 도입한다. 다음 자연 질문
"이 추천이 돈이 되는가?" 에 답하기 위한 단계 — 자동매매 진입 (Future Backlog)
전 반드시 거쳐야 할 검증 cycle. 실주문 / POST 라우터 / 외부 API 자동 호출은
v0.7 에서도 추가하지 않는다.

### v0.7 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 (예정) |
|---|---|---|---|
| A | Strategy interface + 룰 기반 전략 정의 (`StrategyInterface` ABC + `TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` + 단위 테스트) | ✅ 완료 | `v0.7-strategy-interface` |
| B | Backtest engine + 신규 테이블 2개 (`BacktestRun` 26번째 + `BacktestResult` 27번째) + `scripts/run_backtest.py` argparse CLI (default dry-run) + 통합 테스트 | ✅ 완료 | `v0.7-backtest-engine` |
| C | 비용 모델 (`CostModel` placeholder 0.33% 차감) + 시장 국면별 분리 (`MarketRegime` at-or-before 매칭) + cost_adjusted_return_5d / regime 컬럼 | ✅ 완료 | `v0.7-backtest-cost-regime` |
| D | 백엔드 read-only API 3종 (`/api/strategies` + `/api/backtest/runs` + `/api/backtest/runs/{run_id}`) + 프런트 10번째 화면 `/backtest` + Sidebar `백테스트 (β)` 메뉴 | ✅ 완료 | `v0.7-frontend-backtest` |
| E | `RELEASE_NOTES_v0.7.md` + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE 마감 + tag `v0.7-final` | ⏳ | `v0.7-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0007`, 체크리스트는 [`TASKS.md`](./TASKS.md)
`v0.7 — Strategy & Backtest Foundation` 섹션 참조.

### 후보 비교 / 선택 사유 (요약)

7 개 v0.7 후보 중 채택:

- ✅ **Strategy / Backtest 기초** (Phase A·B·C·D) — 누적 데이터 충분, 외부 의존 0건, 자동매매 진입 전 필수 검증, 사용자 명시 추천과 정렬

미채택 → v0.8+ 로 미룸:

- ❌ **Watchlist + 인증** — POST 첫 도입 = 별도 보안 cycle 권장 (v0.8 에서 Strategy/Backtest 검증 후 진입)
- ❌ **인증 / 보안 단독** — Watchlist 와 묶음 (v0.8)
- ❌ **실 DART / 실 RSS provider** — 라이선스 검토 (사람 작업) 가 코드 cycle 외 단계, 외부 API 의존성 첫 도입 = 별도 cycle (v0.8+)
- ❌ **운영 모니터링** — 인증 도입 후 (v0.8+)
- ❌ **DB migration / Alembic** — v0.7 신규 테이블 2개 추가 후 v0.8 진입 적기
- ❌ **자동매매 / 실주문** — Future Backlog (별도 보안 / 컴플라이언스 / 자본 한도 사이클 선행)

### v0.7 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 (read-only API 만 — v0.1 ~ v0.6 일관 정책 유지)
- ❌ 인증 / Watchlist (v0.8 후보로 묶음)
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 의 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (v0.10+ 검토)
- ❌ ScoringEngine 본 weight 변경 — RecommendationEngine / HoldingCheckEngine 산식 0건 변경
- ❌ HoldingCheckEngine 산식 변경
- ❌ LLM 자동 전략 생성 — Phase A 는 룰 기반만, LLM 보강은 v0.8+ 후보
- ❌ Alembic 도입 (v0.7 신규 테이블 2개 추가 후 v0.8 권장)
- ❌ 실 비용 / 세금 데이터 fetch — `CostModel` 은 placeholder constant 만
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.8+ 후보
- ❌ 백테스트 결과 자동 텔레그램 알림 — read-only 화면만, 자동 발송 0건
- ❌ KIS API 외 외부 자격증명 자동 호출

### v0.7 백엔드 정책 변경 안내

`v0.6-final` 동결을 v0.7 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터 / 잡 트리거 / 자동매매 코드 / 본 weight 산식은 추가하지 않는다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| A | `app/strategy/interfaces.py` (신규) / `app/strategy/rule_based.py` (신규) | Strategy ABC + 룰 기반 구현체 3종 |
| B | `app/db/models.py` `BacktestRun` + `BacktestResult` 신규 (26·27번째 테이블) | 신규 테이블 2개 |
| B | `app/data/repositories/backtest_runs.py` / `backtest_results.py` (신규) | 신규 Repository 2개 |
| B | `app/backtest/engine.py` (신규) | BacktestEngine |
| B | `scripts/run_backtest.py` (신규) | argparse CLI (default dry-run) |
| C | `app/backtest/cost_model.py` / `regime_split.py` (신규) | 비용 모델 + regime 매칭 |
| C | `app/db/models.py` `BacktestResult.cost_adjusted_return_5d` + `regime` 컬럼 (Phase B 의 신규 테이블에 흡수, 별도 ALTER 0건) | 신규 컬럼 2개 (Phase B 와 동일 테이블) |
| D | `app/api/routes.py` | GET 라우터 3개 추가 (read-only) |
| D | `app/api/schemas.py` | 4 신규 schema |
| D | `frontend/src/pages/Backtest/` (신규 폴더) | 10번째 화면 |
| D | `frontend/src/components/Sidebar.tsx` (또는 동등) | 9 → 10 메뉴 |
| D | `frontend/src/api/types.ts` / `hooks/` | 타입 + hook 신규 |

DB 마이그레이션 = `CREATE TABLE backtest_runs ...; CREATE TABLE backtest_results ...;` 두 줄, destructive 0건. 기존 테이블 변경 0건.

### v0.7 Phase A 결과 (요약) — Strategy interface + 룰 기반 전략 3종

> Phase A 는 backend 순수 로직만 추가. DB 모델 / 라우터 / 프런트 / scheduler /
> Telegram / 자동매매 / 외부 호출 0건. 전략 신호는 매매 주문이 아니라 백테스트
> / 분석용 신호임이 코드 + 단위 테스트 양쪽에서 명시된다.

- `app/strategy/__init__.py` 신규 — 패키지 진입점. 공개 심볼 (`StrategyInterface`,
  `StrategySignal`, `ScoreSnapshot`, `TopGradeStrategy`, `HighScoreStrategy`,
  `MultiSignalStrategy`, 액션 상수 3종 + `STRATEGY_ACTIONS` / `SCORE_SNAPSHOT_FIELDS`)
  re-export.
- `app/strategy/interfaces.py` 신규:
  - `StrategySignal` (frozen dataclass) — `action` (BUY / PASS / AVOID 외 값 거부 →
    `ValueError`), `confidence` (Decimal, `__post_init__` 에서 `[0, 1]` 자동 clamp +
    non-Decimal 입력 자동 coerce), `reason` (str), `evidence` (`dict | None`).
    "주문이 아니다 — quantity / price / account / broker 없음" 명시 docstring.
  - `ScoreSnapshot` (frozen dataclass) — 14 필드 (`symbol`, `total_score`, `grade`,
    `technical_score`, `news_score`, `supply_score`, `fundamental_score`,
    `earnings_score`, `ai_score`, `report_score`, `theme_signal_score`,
    `risk_level`, `risk_flags`, `evidence`). 수치는 모두 nullable, `risk_flags` 는
    `default_factory=list` 로 인스턴스 격리.
  - `StrategyInterface` (ABC) — `name` / `version` 추상 property + `evaluate(snapshot)
    -> StrategySignal` 추상 method. **외부 API / DB / Telegram / 주문 호출 금지**
    docstring 명시.
  - `STRATEGY_ACTIONS` frozenset + `SCORE_SNAPSHOT_FIELDS` frozenset (테스트
    가드용).
- `app/strategy/rule_based.py` 신규:
  - `TopGradeStrategy` v1.0.0 — grade `S` → BUY (conf 0.9), `A` → BUY (conf 0.75),
    `D` → AVOID (conf 0.75), 그 외 / `None` → PASS (conf 0.5). lowercase 입력
    자동 normalize.
  - `HighScoreStrategy` v1.0.0 — `total_score >= 75` → BUY (linear 75→0.6 / 100→1.0),
    `<= 35` → AVOID (linear 35→0.6 / 0→0.985), 그 외 / `None` → PASS (conf 0.5).
    confidence 는 `StrategySignal` post-init clamp.
  - `MultiSignalStrategy` v1.0.0 — AVOID 우선 게이트 (HIGH risk → conf 0.85,
    `RISK_DISCLOSURE` flag → conf 0.85, `total_score <= 35` → conf 0.7) → BUY 게이트
    (`total >= 65` AND `fundamental >= 60` AND `news >= 50` AND `(earnings >= 50
    or None)` AND not HIGH risk AND no RISK_DISCLOSURE → conf 0.7) → 나머지 PASS.
    BUY 시 evidence-driven boost: `earnings_evidence.surprise_type == "BEAT"` →
    +0.10, `news_evidence.positive_count > negative_count` → +0.05. `evidence`
    가 `None` / 비-dict / 비-int count 등 malformed 일 때 raise 0건.
- `tests/unit/test_rule_based_strategies.py` 신규 — **56 케이스** 단위 테스트:
  - StrategySignal: action 검증 1 + parametrize 정상 액션 3 + confidence clamp
    parametrize 7 + non-Decimal coerce 1 = **12**
  - ScoreSnapshot: 최소 생성 1 + order field 부재 가드 1 (quantity / price /
    account / broker / order_type / side 모두 필드에 없음 단언) + risk_flags
    인스턴스 격리 1 = **3**
  - StrategyInterface: ABC 직접 인스턴스화 차단 1 + 3 구현체 호환 가드 1 = **2**
  - TopGradeStrategy: parametrize 2 + AVOID 1 + parametrize 5 + lowercase 1 = **9**
  - HighScoreStrategy: parametrize 10 + None → PASS 1 + confidence 범위 가드 1 = **12**
  - MultiSignalStrategy: BUY 1 + earnings None BUY 1 + HIGH AVOID 1 + DISCLOSURE
    AVOID 1 + low total AVOID 1 + mid PASS 1 + 3 component threshold PASS 3 +
    BEAT boost 1 + news skew boost 1 + combined boost clamp 1 + non-positive skew
    no boost 1 + missing evidence 1 + malformed evidence 1 = **15**
  - 3 전략 × 빈 snapshot → PASS 가드 parametrize 3 = **3**
- 회귀: backend pytest **558 → 614 passed (+56)**. frontend / e2e / build 변경
  0건. 라우터 / 프런트 / DB 모델 / scheduler / Telegram / 자동매매 / 외부 호출
  0건. ScoringEngine 본 weight 변경 0건.
- 안전 범위: `app/strategy/` 전 파일에서 `requests`, `httpx`, `aiohttp`, `urllib`,
  KIS 클라이언트, DART 클라이언트, Telegram, `app.db.session`, `app.data.repositories`
  import 0건. `BrokerInterface` 호출 0건.

### v0.7 Phase B 결과 (요약) — Backtest engine + 신규 테이블 2개 + CLI

> Phase B 는 backend 데이터 / 엔진 layer 만 추가. API 라우터 / 프런트 / 비용
> 모델 / 시장 국면 분리 / scheduler / Telegram / 자동매매 / 외부 호출 0건.
> CostModel / regime split 은 Phase C 로 이연.

- `app/db/models.py` — `BacktestRun` 신규 (26번째 테이블, TimestampMixin) +
  `BacktestResult` 신규 (27번째 테이블). `BacktestResult.backtest_run_id` →
  `backtest_runs.id` ON DELETE CASCADE + `cascade="all, delete-orphan"` relationship.
  Unique `(backtest_run_id, recommendation_id)` 가드.
- `app/data/repositories/backtest_runs.py` 신규 — `BacktestRunRepository`:
  `create` / `get_by_id` / `list_recent` / `list_by_strategy` / `mark_finished`
  (모든 metric 일괄 update + status SUCCESS) / `mark_failed` (status FAILED +
  error_message). 상태 상수 `STATUS_DRY_RUN` / `STATUS_SUCCESS` / `STATUS_FAILED`.
- `app/data/repositories/backtest_results.py` 신규 — `BacktestResultRepository`:
  `create` / `bulk_insert` (Iterable → flush 한 번) / `list_by_run` / `list_by_symbol` /
  `aggregate_by_run` (`{action: count}` GROUP BY) / `aggregate_by_signal_action`.
- `app/data/repositories/__init__.py` — 두 repository export + `__all__` 갱신.
- `app/strategy/registry.py` 신규 — `STRATEGY_REGISTRY` dict +
  `KNOWN_STRATEGIES = ("high_score", "multi_signal", "top_grade")` +
  `UnknownStrategyError(KeyError)` + `get_strategy(name) -> StrategyInterface`.
  `app/strategy/__init__.py` 가 registry 심볼을 re-export.
- `app/backtest/__init__.py` + `app/backtest/engine.py` 신규:
  - `BacktestEngine(session)` — `BacktestRunRepository` + `BacktestResultRepository`
    composition. 외부 의존성 0건.
  - `BacktestEngine.run(strategy, start_date=None, end_date=None, dry_run=True,
    limit=None, run_date=None) -> BacktestRunSummary` — `Recommendation` +
    `RecommendationRun` + `DataSnapshot` outer join 으로 데이터 fetch →
    `build_score_snapshot` 으로 `ScoreSnapshot` 빌드 → `strategy.evaluate()` →
    horizon 1·3·5·20일 `RecommendationResult.close_return` 매칭 → 통계 집계.
    dry_run=True 면 DB 0건 저장하고 summary 만 반환.
  - `build_score_snapshot(rec, snapshot)` helper — `Recommendation` row +
    `DataSnapshot.market_context_json` 의 evidence 4종 (`news_evidence`,
    `disclosure_risk_evidence`, `fundamental_evidence`, `earnings_evidence`) +
    `risk_summary.level` / `flags` 를 `ScoreSnapshot` 으로 정규화. malformed JSON
    (str / list / 비-dict) 에 대해 raise 0건 — 누락 키는 None / 빈 리스트로
    fallback. **broker / 주문 / 가격 / 수량 필드 0건** (Phase A 의
    `SCORE_SNAPSHOT_FIELDS` frozenset 가드와 부합).
  - `BUY_ONLY_METRICS_NOTE` 상수 — "win_rate / avg_return / max_drawdown 은 BUY
    신호만 대상이고 PASS / AVOID 는 *_count 에만 잡힘" 정책 텍스트가 응답 +
    `summary_json.notes` 에 함께 노출. horizon 별 NULL 결과는
    `missing_result_count_per_horizon` 에 카운트만 가산하고 그 horizon 평균에서
    제외 (전체 run 은 실패하지 않음).
  - `BacktestRunSummary` (frozen dataclass) — dry_run / commit 양쪽이 동일 schema
    반환. `as_dict()` 직렬화 helper.
- `scripts/run_backtest.py` 신규 — argparse CLI. `--strategy` 필수
  (choices=KNOWN_STRATEGIES) + `--from-date` / `--to-date` (YYYY-MM-DD) /
  `--commit` (없으면 dry-run rollback) / `--db-url` / `--limit`. `_print_summary` 가
  signal/buy/pass/avoid count + horizon 별 win_rate/avg_return + max_drawdown +
  missing_result_count + backtest_run_id + BUY_ONLY_METRICS_NOTE 출력. `main()` 의
  `UnknownStrategyError` 캐치 → exit 2.
- `tests/integration/test_backtest_repositories.py` 신규 — **20 케이스**:
  ORM metadata (2: 두 테이블 모두 expected 컬럼 set 포함) + `BacktestRunRepository`
  (create defaults / get / list_recent 정렬 / list_by_strategy 필터 /
  mark_finished metrics 일괄 update / mark_failed = 7) + `BacktestResultRepository`
  (create / bulk_insert / empty bulk_insert / list_by_run 정렬 / list_by_symbol /
  aggregate_by_run / aggregate_by_signal_action = 7) + Unique constraint (중복 거부 +
  NULL recommendation_id 중복 허용 = 2) + cascade delete + relationship 자식 로드 (2).
- `tests/integration/test_backtest_engine.py` 신규 — **18 케이스**: `build_score_snapshot`
  (3: 정상 / snapshot 없음 / malformed market_context) + dry-run/commit (2: dry-run
  DB 0건 / commit BacktestRun + Result 적재) + 3 strategies × happy (3:
  TopGrade BUY/PASS/AVOID 분포 / HighScore action split / MultiSignal full evidence) +
  metrics (4: BUY-only 산식 / missing horizon 카운트 / BUY 0건 → None / max_drawdown
  최솟값) + buy-only 노트 + date filter (1: start/end_date 에 RecommendationRun 외부
  배제) + CLI (4: dry-run DB 0건 / commit 적재 / unknown strategy `UnknownStrategyError` /
  `main()` smoke).
- 회귀: backend pytest **614 → 652 passed (+38)**. frontend / e2e / build 변경
  0건. ScoringEngine 본 weight 변경 0건. 라우터 / 프런트 / scheduler 0건.
- 안전 범위: `app/backtest/` + `app/strategy/` 어디에도 `requests` / `httpx` /
  `aiohttp` / `urllib` / KIS 클라이언트 / DART 클라이언트 / Telegram /
  `BrokerInterface` import 0건 (grep 검증). `backtest_results` 에 broker / 주문 /
  계좌 / 가격 / 수량 컬럼 부재.

### v0.7 Phase C 결과 (요약) — CostModel + 시장 국면별 분리

> Phase C 는 backend 분석 layer 보강만. API 라우터 / 프런트 / scheduler /
> Telegram / 외부 호출 / 자동매매 0건. CostModel 은 placeholder constant 만 —
> 실 broker fee schedule fetch 는 v0.8+ 후보.

- `app/backtest/cost_model.py` 신규 — `CostModel` (frozen dataclass):
  `buy_fee=0.00015` + `sell_fee=0.00015` + `sell_tax=0.0020` + `slippage=0.0010`
  → `total_cost = 0.0033 (0.33%)`. `apply(raw_return: Decimal | None) -> Decimal | None`
  은 `recommendation_results.close_return` 의 % 단위에 맞춰 `total_cost × 100` 을
  뺀다 (예: 1.5% → 1.17%). `version` 필드 + `COST_MODEL_VERSION = "constant-v1"`
  상수 노출. v0.8+ 의 실 broker schedule 도입 시 `version` 필드만 갱신하면
  추적 가능.
- `app/backtest/regime_split.py` 신규 — `assign_regime(session, signal_date,
  market="KOSPI") -> str | None`. `MarketRegime.date <= signal_date` 가운데 가장
  최근 `regime` 반환. 없으면 None. `display_bucket(regime)` helper 가
  None 입력을 `UNCLASSIFIED_BUCKET` 으로 매핑 (DB 컬럼은 NULL 그대로 — 미래
  regime 데이터 적재 후 재분류 가능). 외부 호출 0건.
- `app/db/models.py` `BacktestResult` 보강 — `cost_adjusted_return_5d`
  Numeric(12,4) nullable + `regime` String(32) nullable index. Phase B 의 신규
  테이블 정의에 흡수되므로 단일 cycle 마이그레이션은 정합. 기존 운영 DB 가
  Phase B 만 적재된 상태라면 `ALTER TABLE backtest_results ADD COLUMN
  cost_adjusted_return_5d NUMERIC(12, 4); ALTER TABLE backtest_results ADD
  COLUMN regime VARCHAR(32); CREATE INDEX ix_backtest_results_regime ON
  backtest_results (regime);` 세 줄로 정합 (DB_SCHEMA §27 명시, destructive 0건).
- `app/data/repositories/backtest_results.py` `aggregate_by_regime` 추가 —
  `{regime_or_unclassified_label: count}` GROUP BY. NULL regime 자동 폴딩.
- `app/backtest/engine.py` 보강:
  - `BacktestEngine.__init__(session, *, cost_model=None, regime_market="KOSPI")` —
    `CostModel` 주입 가능, default 는 `CostModel()`. 회귀를 위해 keyword-only.
  - `run()` 안에서 신호별 BUY 인 row 만 `cost_model.apply(return_5d)` 계산 →
    `cost_adjusted_return_5d` (PASS / AVOID 는 NULL). 모든 row 에
    `assign_regime(session, run_date, market)` 호출 → `regime` 컬럼.
  - `_aggregate` 에 `cost_adjusted_avg_return_5d` 추가 (BUY 신호 중 NULL 아닌
    cost_adjusted 평균, Decimal quantize 0.0001).
  - `_build_regime_breakdown` helper 신규 — BUY rows GROUP BY regime →
    `RegimeBreakdownEntry(regime, buy_count, win_rate_5d, avg_return_5d,
    cost_adjusted_avg_return_5d)`. `buy_count desc` + bucket name asc 정렬로
    결정성 보장.
  - `BacktestRunSummary` 에 `cost_model_version` / `total_cost` /
    `cost_adjusted_avg_return_5d` / `regime_breakdown: list[RegimeBreakdownEntry]`
    필드 + `as_dict()` 직렬화. `summary_json` / `config_json` 양쪽에 동일 데이터
    persist.
- `scripts/run_backtest.py` `_print_summary` — `cost_model_version` /
  `total_cost (fraction)` / `cost_adjusted_avg_return_5d` 줄 추가 + (있으면)
  `regime_breakdown` 표 (regime / buy / win_rate_5d / avg_return_5d /
  cost_adj). 기존 `signal_count` / `*_count` / horizon win/avg/missing /
  backtest_run_id / notes 출력 유지.
- 테스트:
  - `tests/unit/test_cost_model.py` 신규 — **9 케이스** (version 상수 / 0.33%
    total_cost / apply 양수·음수·zero·None / custom rate / custom version /
    frozen dataclass 변경 거부)
  - `tests/integration/test_backtest_regime.py` 신규 — **12 케이스**
    (assign_regime 4: exact match / at-or-before fallback / 사전 데이터 부재
    None / market 필터; engine summary 8: dry-run 노출 / NULL → UNCLASSIFIED
    bucket / commit 시 두 컬럼 영속 + summary_json carry / PASS/AVOID 의
    cost_adjusted NULL but regime 할당 / regime_breakdown GROUP BY +
    `buy_count desc` 정렬 / aggregate_by_regime / NULL bucket 폴딩 / custom
    CostModel 전파)
- 회귀: backend pytest **652 → 673 passed (+21)**. 기존 Phase B 테스트 38건 그대로
  통과. frontend / e2e / build 변경 0건. ScoringEngine 본 weight 변경 0건.
  라우터 / 프런트 / scheduler 0건.
- 안전 범위: `app/backtest/` + `app/strategy/` 어디에도 외부 HTTP / KIS / DART /
  Telegram / `BrokerInterface` import 0건 (grep 검증 유지). `BacktestResult` 에
  broker / 주문 / 계좌 / 가격 / 수량 컬럼 부재. CostModel 은 placeholder
  constant 만 — 실 broker fee schedule fetch / 종목별 stamp duty / tick-size
  슬리피지 모델링은 v0.8+ 후보로 명시 (cost_model.py docstring + DB_SCHEMA).

### v0.7 Phase D 결과 (요약) — read-only API 3종 + 10번째 화면 `/backtest`

> Phase D 는 read-only API + UI 만 추가. BacktestEngine 산식 / CostModel /
> regime_split / DB 모델 변경 0건. POST 라우터 / 자동매매 / 외부 호출 / Telegram
> 0건. Sidebar 9 → 10 메뉴.

- `app/api/schemas.py` — 7 신규 schema:
  - `StrategySchema` (name / version / description) + `StrategiesResponse`
  - `BacktestRunSchema` (15 metric + cost_model_version + total_cost) +
    `BacktestRunsResponse` (items + count + strategy + limit)
  - `BacktestResultSchema` (signal + horizon + cost_adjusted + regime +
    evidence_json) + `RegimeBreakdownSchema` + `BacktestRunDetailResponse`.
    Decimal-as-string 패턴 유지. broker / order / quantity / account 필드 0건.
- `app/api/routes.py` — 3 신규 GET 라우터:
  - `GET /api/strategies` — `KNOWN_STRATEGIES` 순회 + `get_strategy(name)` 호출.
    DB 접근 0건. `description` 은 `_strategy_description(strategy)` helper 가
    docstring 첫 줄 추출.
  - `GET /api/backtest/runs?strategy=&limit=` — `BacktestRunRepository.list_recent`
    또는 `list_by_strategy`. `_backtest_run_to_schema` 가 `summary_json` 의
    `cost_model_version` / `total_cost` / `cost_adjusted_avg_return_5d` 를 응답
    최상위 필드로 추출. `limit` Query 검증 1~100.
  - `GET /api/backtest/runs/{run_id}` — `BacktestRunRepository.get_by_id` (없으면
    404) + `BacktestResultRepository.list_by_run` + `_regime_breakdown_from_summary`
    helper. `summary_json` 의 `regime_breakdown` list 를 `RegimeBreakdownSchema` 로
    변환 (malformed 방어 — list / dict 가 아니면 빈 list 반환).
- `app/data/repositories/backtest_results.py` `create()` — `cost_adjusted_return_5d`
  + `regime` keyword 추가 (Phase C 컬럼 호환). 기존 호출자 회귀 0건 (keyword 만 추가).
- `tests/integration/test_api_routes.py` 보강 — **9 신규 케이스**:
  `_BACKTEST_FORBIDDEN_FIELDS` (16종: source_file_path / body / content /
  full_text / raw_text / paragraph / html_body / 본문 / 원문 / 전문 / broker /
  account / quantity / order_price / order_type / side) + `_seed_backtest_run` /
  `_seed_backtest_result` 헬퍼. 케이스: strategies 3종 노출 + version /
  description 단언 / runs empty / runs happy 정렬 + cost meta / strategy filter /
  limit clamp 422 / detail happy + regime_breakdown + cost_adjusted + BUY-only
  notes / detail 404 / forbidden tokens 미노출 가드 / `_assert_no_source_file_path`
  recursive 가드.
- `frontend/src/api/types.ts` — 7 신규 type. broker / order / account 필드 부재.
- `frontend/src/hooks/useStrategies.ts` (staleTime 5분) +
  `useBacktestRuns.ts` (60초, strategy/limit 파라미터) +
  `useBacktestRunDetail.ts` (60초, runId enabled gate) 신규.
- `frontend/src/pages/Backtest/index.tsx` 신규 — 10번째 화면, 단일 파일에 3
  서브컴포넌트:
  - `StrategyListSection` — 3 카드 grid (`md:grid-cols-3`), description
    `line-clamp-3`, version 모노스페이스
  - `RunsTableSection` — strategy filter radiogroup (ALL + N strategies) +
    클릭 가능한 run 표 (strategy / run_date / signals / B/P/A / win_rate_5d /
    avg_return_5d / cost_adj_5d / max_dd / status). 선택 row 하이라이트.
  - `RunDetailSection` — selected run 의 detail. cost_model_version / total_cost
    헤더 + BUY-only note (amber 배경) + regime_breakdown 표 + 신호 row 표
    (`ActionBadge` BUY/PASS/AVOID tone-color + cost_adjusted 컬럼)
- `frontend/src/components/layout/Sidebar.tsx` — `FlaskConical` 아이콘 + 8번째
  위치에 `백테스트 (β)` 메뉴 추가. `NAV_ITEMS` 9 → 10. 주석 갱신
  (`v0.7 Phase D adds 백테스트`).
- `frontend/src/router.tsx` — `BacktestPage` lazy import + `/backtest` Route 추가.
- `frontend/src/tests/mswServer.ts` — 3 default 핸들러 (모두 빈 응답 / 404).
- `frontend/src/tests/Backtest.test.tsx` 신규 — **7 케이스**: happy / empty /
  runs 500 / detail 클릭 시 로드 + regime + BUY-only note + cost_model badge /
  detail 500 / strategy filter URL 변경 단언 / 자동매매·order UI + forbidden
  토큰 미노출 (form / submit / 실거래 / 자동매매 / 주문 실행 / source_file_path /
  원문 / 본문 모두 0건).
- `frontend/e2e/fixtures/apiMocks.ts` — `STRATEGIES` + `BACKTEST_RUNS_LIST` +
  `BACKTEST_RUN_DETAIL_42` fixture + 라우터 패턴 추가 (specific runs/42 가
  generic /runs 보다 앞에 위치).
- `frontend/e2e/dashboard.spec.ts` — sidebar nav 테스트에 `백테스트 (β)` 추가 +
  신규 `Backtest screen surfaces strategies + runs + detail` 테스트 (전략 3종 +
  run row + 클릭 시 detail + regime + cost_model + forbidden 토큰 가드 + raw
  JSON `order_type` / `quantity` / `source_file_path` 0건) + `no automation /
  order UI` targets 에 `/backtest` 추가.
- 회귀: backend pytest **673 → 682 passed (+9)**, frontend vitest **77 → 84
  passed (+7)**, e2e **13 → 14 passed (+1)**, build 그린 (vendor-charts 383 kB /
  gzip 105 kB). BacktestEngine 산식 / CostModel / regime_split / DB 모델 / 자동매매 /
  POST / 외부 호출 / Telegram 0건. ScoringEngine 본 weight 변경 0건.
- 안전 범위: `BacktestResultSchema` / `BacktestRunSchema` / `BacktestRunDetailResponse`
  어디에도 broker / account / quantity / order_price / order_type / side 필드
  0건. e2e 테스트가 raw JSON 트리에서 forbidden 토큰 0건을 단언. v0.6 의
  `_assert_no_source_file_path` recursive 가드 그대로 새 응답 트리 적용.

### v0.7 누적 태그 (예정)

- `v0.6-final` (시작점, HEAD `e729d60`)
- `v0.7-strategy-interface` (Phase A 인수)
- `v0.7-backtest-engine` (Phase B 인수)
- `v0.7-backtest-cost-regime` (Phase C 인수)
- `v0.7-frontend-backtest` (Phase D 인수)
- `v0.7-final` (Phase E 마감)

---

## 0-5. v0.6 마감 선언 — Fundamental & Earnings Intelligence

**v0.6 cycle 마감.** 기준선 `v0.5-final` (HEAD `9ccf0f8` 시점, origin/main
동기화 완료). v0.1 backend + v0.2 frontend + v0.3 분석·운영 + v0.4 Analyst &
Theme Intelligence + v0.5 News·공시·테마 랭킹 모두 마감 위에 **재무 / 실적
데이터 라인 + 어닝 인텔리전스 기초** 5 phase 누적 완료. 누적 인수 태그는
`v0.6-frontend-fundamentals` (Phase D) 이고, Phase E 마감 후 태그
`v0.6-final` 부여 예정.

- 마감 일자: **2026-05-06 (Asia/Seoul)**
- 마감 게이트: backend pytest **558 passed** (deselect 1: `.env` dev override 의존
  `test_settings_defaults`, CI clean env 자동 통과) / frontend vitest **77 passed** /
  frontend build 그린 / Playwright e2e **13 passed**
- 누적 인수 태그: (Phase A 별도 태그 부재 — `0d3dba5` + `da3567f`) →
  `v0.6-earnings-event-pipeline` → `v0.6-fundamental-score` →
  **`v0.6-frontend-fundamentals`** → `v0.6-final` (Phase E 후 부여)
- 마감 사유: [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md)

### v0.6 핵심 산출물 한 줄 요약

- **재무 데이터 라인** — `FundamentalProviderInterface` ABC + `FundamentalSnapshot` (24번째 테이블) + Repository + `scripts/import_fundamentals.py` argparse CLI (default dry-run)
- **실적 이벤트 데이터 라인** — `EarningsProviderInterface` ABC + `EarningsEvent` (25번째 테이블) + Repository + `scripts/import_earnings.py` + BEAT/MEET/MISS 분류 룰
- **`fundamental_score` 첫 real 화** — `RealFundamentalScoreProducer` (composition 패턴, fallback 으로 news/supply/earnings/ai 위임). 산식 `clip(50 + ROE/PER/PBR/growth/debt/dividend rule adjustment, 0, 100)` / snapshot 부재 → 50
- **`earnings_score` 첫 real 화 (HoldingCheckEngine)** — `RealEarningsScoreProducer` (composition 패턴). 산식 `clip(50 + (base_delta + surprise_delta) * recency_multiplier, 0, 100)` / event 부재 → 50
- **백엔드 read-only API 3종** — `GET /api/stocks/{symbol}/fundamentals` + `GET /api/stocks/{symbol}/earnings` + `GET /api/calendar/earnings` (모두 read-only, source_file_path 0건 노출)
- **추천 / 보유 evidence 노출 강화** — `RecommendationItemSchema.fundamental_evidence` + `earnings_evidence`, `HoldingCheckSchema.earnings_evidence` + `news_evidence` + `disclosure_risk_evidence` (v0.5 Phase D 이연분 흡수). 모두 라우터 단계 화이트리스트 통과
- **StockDetail 두 카드 + Today 한 카드 + Recommendations 두 cell + Holdings cell** — `FundamentalsCard` (PER/PBR/ROE/부채/배당/성장률 + history) + `EarningsCard` (BEAT/MEET/MISS tone-color badge + actual vs consensus + history) + `UpcomingEarningsCard` (limit 5) + `RecommendationsTable` `fund evidence` / `earnings evidence` cell + `RecentHoldingChecksCard` earnings evidence 컬럼

### v0.6 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | Fundamental data layer + CSV import | ✅ 완료 (별도 태그 부재 — 커밋으로 추적) | `0d3dba5` + `da3567f` |
| B | Earnings event layer + CSV import | ✅ 완료 | `v0.6-earnings-event-pipeline` |
| C | `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + RecommendationEngine·HoldingCheckEngine evidence 통합 | ✅ 완료 | `v0.6-fundamental-score` |
| D | 백엔드 read-only API 3종 + StockDetail 카드 + Today 카드 + Recommendations / Holdings evidence cell | ✅ 완료 | `v0.6-frontend-fundamentals` |
| E | `RELEASE_NOTES_v0.6.md` + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE 마감 + tag `v0.6-final` | ✅ 문서 마감 (코드 변경 0건) | `v0.6-final` (Phase E 후 부여) |

### v0.7 후보 (마감 후 검토 대기)

자세한 분류는 [`ROADMAP.md`](./ROADMAP.md) §7 + [`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md)
"v0.7 후보". 한 줄 요약:

- **데이터 / 분석 실제화** — 실 DART API (`DartFundamentalProvider` / `DartEarningsProvider`), 실 RSS / News API, 재무 score percentile 정규화, earnings surprise 다지표 가중, LLM sentiment / 재무 분석 보강
- **인증 / 관심종목** — 단일 토큰 → POST 라우터 → Watchlist (인증 동반 필수)
- **운영 / UX** — Sentry / Prometheus / Grafana, 모바일 레이아웃, lightweight-charts 마이그레이션, Alembic 도입
- **Future Backlog (자동매매)** — Strategy / Backtest / MockBroker / APPROVAL / SMALL_AUTO / FULL_AUTO 모두 별도 보안·컴플라이언스 사이클 선행 필수

---

## 0-6. v0.6 진행 선언 — Fundamental & Earnings Intelligence (강등됨, Phase D 시점 스냅샷)

**v0.6 cycle 진행 중 (Phase D 완료, Phase E 마감 대기).** 기준선 `v0.5-final`
(HEAD `9ccf0f8` 시점, origin/main 동기화 완료). v0.1 backend + v0.2 frontend +
v0.3 분석·운영 + v0.4 Analyst & Theme Intelligence + v0.5 News·공시·테마
랭킹 모두 마감 위에 **재무 / 실적 데이터 라인 + 어닝 인텔리전스 기초** 5
phase 를 진행한다. v0.1 의
read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책
(본문 paragraph 미저장 / `source_file_path` 미노출) + v0.5 의 자동 fetch default
OFF 정책 모두 그대로 유지한다.

### v0.6 핵심 목표

운영자 수동 CSV / DART subset 1단계로 **재무 지표 시계열 (`fundamental_snapshots`)
+ 실적 이벤트 (`earnings_events`)** 데이터를 도입하고, `DummyScoreProducer` 5
컴포넌트 중 추천 본 weight 15% 인 `fundamental_score` 와
HoldingCheckEngine 의 `earnings_score` 를 **첫 real 화** 한다 (`RealFundamentalScoreProducer`
+ `RealEarningsScoreProducer`). v0.4 의 Analyst Report CSV import 패턴을 그대로
재사용 (forbidden body column 13종 거부 / summary 500자 truncate /
source_file_path 마스킹). 추후 DART API provider 를 붙일 수 있게
`FundamentalProviderInterface` / `EarningsProviderInterface` ABC 만 미리 두고 실
API 구현체는 v0.7+ 로 이연 (FakeProvider 만 제공). 추천 산식 본 weight
(technical 35% + news 25% + supply 15% + fundamental 15% + ai 10% - risk_penalty)
+ HoldingCheckEngine 산식 본 weight 변경 0건 — `fundamental_score` /
`earnings_score` 가 placeholder 50 → real 로 교체될 뿐.

### v0.6 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 (예정) |
|---|---|---|---|
| A | Fundamental data layer (`FundamentalProviderInterface` ABC + `FundamentalSnapshot` 24번째 테이블 + Repository + `scripts/import_fundamentals.py` argparse CLI + 8 지표 검증) | ✅ PR1+PR2 완료 / PR3 또는 Phase B 대기 | `v0.6-fundamental-data-layer` |
| B | Earnings event layer + 어닝 캘린더 (`EarningsProviderInterface` ABC + `EarningsEvent` 25번째 테이블 + Repository + `scripts/import_earnings.py` + BEAT/MEET/MISS 분류 룰) | ✅ 완료 | `v0.6-earnings-event-pipeline` |
| C | `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + RecommendationEngine·HoldingCheckEngine 통합 + decision evidence 기록 | ✅ 완료 | `v0.6-fundamental-score` |
| D | 백엔드 read-only API 3종 (`/api/stocks/{symbol}/fundamentals` + `/api/stocks/{symbol}/earnings` + `/api/calendar/earnings`) + `RecommendationItemSchema` / `HoldingCheckSchema` evidence 필드 + 프런트 StockDetail 카드 + Today 다가오는 어닝 + Recommendations/Holdings evidence 통합 | ✅ 완료 | `v0.6-frontend-fundamentals` |
| E | `RELEASE_NOTES_v0.6.md` + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE 마감 + tag `v0.6-final` | ⏳ | `v0.6-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0006`, 체크리스트는 [`TASKS.md`](./TASKS.md)
`v0.6 — Fundamental & Earnings Intelligence` 섹션 참조.

### 후보 비교 / 선택 사유 (요약)

7 개 v0.6 후보 중 채택:

- ✅ **재무 / 실적 점수 실제화** (Phase A·C) — DummyScoreProducer 5 컴포넌트 중 두 번째 큰 weight (fundamental 25%) 첫 real 화
- ✅ **어닝 인텔리전스 기초** (Phase B·C) — HoldingCheckEngine 의 earnings_score 최초 real 화 + Today 다가오는 발표 화면
- ✅ **점수 정합성 / 통합 evidence 화면** (Phase D) — v0.4 report/theme + v0.5 news/disclosure + v0.6 fundamental/earnings noise 정리 + holding evidence 노출 (v0.5 에서 이연)

미채택 → v0.7+ 로 미룸:

- ❌ **관심종목 / Watchlist** — POST 첫 도입 + 인증 사이클 별도
- ❌ **인증 / 보안** — Watchlist 와 묶어서 v0.7
- ❌ **전략 / 백테스트 기초** (StrategyInterface 구체화) — 실 News (v0.5) + 재무 (v0.6) 데이터 후행 검증 후, v0.8+
- ❌ **자동매매 / 실 주문** — Future Backlog (별도 보안 / 컴플라이언스 / 자본 한도 사이클)

### v0.6 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 (read-only API 만 — v0.1 ~ v0.5 일관 정책 유지)
- ❌ DART API 자동 호출 — 1단계는 운영자 CSV 만. ABC + Fake provider 만, 실 API 는 v0.7+
- ❌ 자동 fetch default ON — `Settings.fundamental_collection_enabled` / `earnings_collection_enabled` = false (운영자 명시 enable + 실 provider 주입 시에만 동작)
- ❌ 재무제표 PDF / Excel BLOB 저장 — CSV 정량 지표 메타데이터만
- ❌ 재무 / 실적 본문 paragraph 저장 — 짧은 운영자 메모 (≤500자) 만
- ❌ 추천 산식 본 weight 변경 — `fundamental_score` 가 50 → real 로 교체되지만 weight 15% 그대로
- ❌ HoldingCheckEngine 산식 본 weight 변경 — `earnings_score` 가 50 → real 로 교체되지만 weight 그대로
- ❌ 관심종목 / Watchlist / 인증 — v0.7 후보
- ❌ Strategy / Backtest / MockBroker — v0.8+ 후보
- ❌ LLM 자동 재무 / 어닝 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.7+
- ❌ KIS API 외 외부 자격증명 자동 호출

### v0.6 백엔드 정책 변경 안내

`v0.5-final` 동결을 v0.6 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터 / 잡 트리거 / 자동매매 코드 / 본 weight 산식은 추가하지 않는다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| A | `app/db/models.py` `FundamentalSnapshot` 신규 (24번째 테이블) | 신규 테이블 1개 |
| A | `app/data/interfaces.py` / `dtos.py` / `importers/fundamentals.py` (신규) | Fundamental provider ABC + DTO + importer |
| A | `app/data/repositories/fundamental_snapshots.py` (신규) | 신규 Repository |
| A | `scripts/import_fundamentals.py` (신규) | argparse CLI (default dry-run) |
| B | `app/db/models.py` `EarningsEvent` 신규 (25번째 테이블) | 신규 테이블 1개 |
| B | `app/data/importers/earnings.py` / `repositories/earnings_events.py` (신규) | Earnings provider ABC + DTO + importer + Repository |
| B | `scripts/import_earnings.py` (신규) | argparse CLI |
| C | `app/analysis/score_producers.py` | `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` 추가 |
| C | `app/decision/recommendation_engine.py` / `holding_check_engine.py` | 기존 `score_producer` composition 주입 유지 + evidence 기록 |
| D | `app/api/routes.py` | GET 라우터 3개 추가 (read-only) |
| D | `app/api/schemas.py` | `RecommendationItemSchema` / `HoldingCheckSchema` evidence 필드 + 5 신규 schema |
| D | `frontend/src/pages/StockDetail/` | Fundamental·Earnings 카드 추가 |
| D | `frontend/src/pages/TodayReport/` | 다가오는 어닝 카드 추가 |
| D | `frontend/src/pages/Recommendations/` / `Holdings/` | evidence 컬럼 추가 |
| D | `frontend/src/api/types.ts` / `hooks/` | 타입 + hook 신규 |

DB 마이그레이션 = `CREATE TABLE fundamental_snapshots ...; CREATE TABLE earnings_events ...;` 두 줄, destructive 0건. 기존 테이블 변경 0건.

### v0.6 Phase A PR1 결과 (요약) — FundamentalSnapshot ORM + Repository

> Phase A 전체 중 첫 번째 PR. 이번 PR 은 `FundamentalSnapshot` 24번째 테이블과
> Repository 기반만 추가하고, CSV import / provider / scheduler / API / frontend 는
> 후속 PR 로 남겼다.

- `app/db/models.py` — `fundamental_snapshots` 신규. `symbol`, `snapshot_date`,
  `fiscal_year` 인덱스와 `(symbol, snapshot_date, fiscal_year, fiscal_quarter)`
  unique constraint 추가. `fiscal_quarter` 는 연간 데이터 저장을 위해 nullable.
- `app/data/repositories/fundamental_snapshots.py` — `create`,
  `upsert_by_symbol_period`, `get_latest_by_symbol`, `list_recent_by_symbol`,
  `list_by_fiscal_year` 추가. upsert 는 같은 period row 를 찾아 정규화 metric 필드를
  갱신하고 같은 row 를 반환하는 정책.
- `app/data/repositories/__init__.py` — `FundamentalSnapshotRepository` export.
- `tests/integration/test_fundamental_repository.py` — metadata 생성, CRUD, upsert 멱등,
  latest/recent/fiscal_year 조회, nullable quarter, Decimal round-trip, 본문/원문/blob
  컬럼 부재 가드.
- `DB_SCHEMA.md` / `TASKS.md` — Phase A PR1 범위와 `fundamental_snapshots` 정책 갱신.
- 안전 범위: DART / KIS / Telegram 호출 0건, POST 라우터 0건, 자동매매/주문 코드 0건,
  재무제표 PDF/Excel BLOB 및 본문 paragraph 저장 0건.

### v0.6 Phase A PR2 결과 (요약) — Fundamental CSV import pipeline

> Phase A 의 두 번째 PR. PR1 의 `fundamental_snapshots` 테이블과 Repository 위에
> 운영자 수동 CSV import 경로를 추가했다. 기본은 dry-run 이며 `--commit` 을 붙인
> 경우에만 저장한다.

- `app/data/dtos.py` — `FundamentalSnapshotDTO` 신규. 정규화된 수치 지표와 `source`
  만 포함하고 body / content / full_text / paragraph / raw_text / html_body /
  source_file_path / 본문 / 원문 / 전문 필드 0건.
- `app/data/interfaces.py` — `FundamentalProviderInterface` ABC 신규
  (`fetch_fundamentals(symbols, fiscal_year, fiscal_quarter=None)`). 실 DART 구현체는
  추가하지 않았다.
- `tests/mocks/fake_fundamental_provider.py` — 외부 API 호출 없는 결정론적 3-row
  FakeProvider.
- `app/data/importers/fundamentals.py` — CSV header validation + row validation +
  `FundamentalSnapshotRepository.upsert_by_symbol_period` 기반 import. 재import 시 값이
  같으면 `unchanged`, 값이 다르면 `updated` 로 집계.
- `scripts/import_fundamentals.py` — argparse CLI. `--file` 필수, `--encoding`
  기본 `utf-8-sig`, `--db-url` override, `--commit` 없는 기본 dry-run.
- `tests/fixtures/fundamentals_sample.csv` / `tests/integration/test_fundamental_import.py`
  — dry-run, commit, reimport 멱등, forbidden column, 필수 컬럼, 날짜/연도/분기,
  Decimal, 음수 허용/불허 정책, CLI `run_import` 검증.
- 안전 범위: DART / KIS / Telegram 호출 0건, scheduler job 0건, API 라우터 0건,
  frontend 변경 0건, 자동매매/주문 코드 0건.

### v0.6 Phase B 결과 (요약) — Earnings event layer + CSV import

> `earnings_events` 25번째 테이블과 수동 CSV import 기반을 추가했다. Phase B 에서도
> DART API provider / scheduler job / API 라우터 / frontend 는 추가하지 않았다.

- `app/db/models.py` — `EarningsEvent` 신규. Unique key 는
  `(symbol, event_date, fiscal_year, fiscal_quarter, event_type)`, 인덱스는
  `symbol`, `event_date`, `surprise_type`.
- `app/data/repositories/earnings_events.py` — `create`,
  `upsert_by_symbol_event`, `get_latest_by_symbol`, `list_recent_by_symbol`,
  `list_upcoming`, `list_by_surprise_type`.
- `app/data/dtos.py` / `app/data/interfaces.py` — `EarningsEventDTO` 와
  `EarningsProviderInterface.fetch_earnings_events(...)` 추가. 실 구현체는 없음.
- `tests/mocks/fake_earnings_provider.py` — BEAT / MEET / MISS / upcoming UNKNOWN
  결정론 샘플. 외부 API 호출 0건.
- `app/data/importers/earnings.py` / `scripts/import_earnings.py` — 기본 dry-run,
  `--commit` 저장, `--file`, `--encoding`, `--db-url` 지원.
- surprise 계산: CSV `surprise_type` 우선. 없으면
  `operating_income_actual` / `operating_income_consensus` 로
  `(actual - consensus) / abs(consensus) * 100` 계산. `>=5` BEAT, `<=-5` MISS,
  그 사이는 MEET, consensus 0/NULL 은 UNKNOWN.
- `tests/fixtures/earnings_events_sample.csv`,
  `tests/integration/test_earnings_repository.py`,
  `tests/integration/test_earnings_import.py` 추가.
- 안전 범위: DART / KIS / Telegram 호출 0건, scheduler job 0건, API 라우터 0건,
  frontend 변경 0건, 자동매매/주문 코드 0건, 원문/본문/BLOB 저장 0건.

### v0.6 Phase C 결과 (요약) — Fundamental / Earnings score real 화

> Phase A/B 의 수동 CSV 기반 데이터 위에 점수 producer 만 추가했다. API 라우터,
> scheduler job, 프런트 화면, 자동매매/주문 코드는 추가하지 않았다.

- `app/analysis/score_producers.py` — `RealFundamentalScoreProducer` 신규.
  기존 `ScoreProducerInterface` composition 패턴을 유지해 news/supply/earnings/ai 는
  fallback 에 맡기고, 추천용 `fundamental_score` 만
  `FundamentalSnapshotRepository.get_latest_by_symbol` 기반으로 교체한다.
- `RealEarningsScoreProducer` 신규. 보유점검용 `earnings_score` 만
  `EarningsEventRepository.get_latest_by_symbol` 기반으로 교체하고, 나머지 컴포넌트는
  fallback producer 를 그대로 사용한다.
- `app/decision/recommendation_engine.py` — `DataSnapshot.market_context_json` 과
  `DecisionLog.rule_result_json` 에 `fundamental_evidence` 를 기록한다.
- `app/decision/holding_check_engine.py` — 같은 방식으로 `earnings_evidence` 를 기록한다.
- `fundamental_evidence` safe fields: `snapshot_date`, `fiscal_year`,
  `fiscal_quarter`, `per`, `pbr`, `roe`, `debt_ratio`, `revenue_growth_yoy`,
  `operating_income_growth_yoy`, `dividend_yield`.
- `earnings_evidence` safe fields: `latest_event_date`, `fiscal_year`,
  `fiscal_quarter`, `event_type`, `surprise_type`, `surprise_pct`,
  `operating_income_actual`, `operating_income_consensus`.
- 안전 범위: ScoringEngine 본 weight 변경 0건, DART / KIS / Telegram 호출 0건,
  API 라우터 0건, frontend 변경 0건, 자동매매/주문 코드 0건, 원문/본문/BLOB/파일 경로
  evidence 노출 0건.

### v0.6 Phase D 결과 (요약) — 백엔드 read-only API 3종 + 프런트 카드 + evidence 노출

> Phase A/B/C 의 데이터·점수 layer 위에 **read-only API 3종** + **프런트
> 카드 / evidence cell** 만 추가. POST 라우터 / scheduler job / 자동매매 / DART
> 자동 호출 / Telegram 발송 0건. ScoringEngine 본 weight 변경 0건.

- `app/api/routes.py` — `GET /api/stocks/{symbol}/fundamentals?limit=`,
  `GET /api/stocks/{symbol}/earnings?limit=`,
  `GET /api/calendar/earnings?from_date=&to_date=&surprise_type=&limit=` 신규 3종.
  Stock master 없으면 404 (기존 `/api/stocks/{symbol}/reports` 정책 재사용).
  `from_date` 미지정 시 캘린더는 "오늘 (UTC) 이후" 만 반환.
- `app/api/schemas.py` — `FundamentalSnapshotSchema` / `StockFundamentalsResponse` /
  `EarningsEventSchema` / `StockEarningsResponse` / `EarningsCalendarItemSchema` /
  `EarningsCalendarResponse` 6 신규 schema. 전부 numeric 필드는 Decimal-as-string
  (`_BaseSchema` 의 `_decimal_to_str` validator). `memo` 는 500자 cap.
- `app/api/schemas.py` — `RecommendationItemSchema` 에 `fundamental_evidence` +
  `earnings_evidence` (Optional[Dict]) 추가, `HoldingCheckSchema` 에
  `news_evidence` + `disclosure_risk_evidence` + `earnings_evidence` 3종 추가
  (v0.5 Phase D 에서 이연된 holding evidence 노출 작업 흡수).
- `app/api/routes.py` — `_whitelist_evidence(snapshot, key, allowed)` helper +
  `_FUNDAMENTAL_EVIDENCE_FIELDS` / `_EARNINGS_EVIDENCE_FIELDS` set 신규.
  Phase C 의 score producer 단계 + Phase D 의 라우터 단계로 **defense-in-depth
  2 단 화이트리스트** — 비전제적 future producer 변경에도 forbidden 키 누설 0건.
- `app/api/routes.py` — `_recommendation_to_schema` 가 `fundamental_evidence` /
  `earnings_evidence` 두 키를 화이트리스트 후 schema 에 주입.
  `_holding_check_to_schema` 도 동일 방식으로 `news_evidence` /
  `disclosure_risk_evidence` / `earnings_evidence` 3종 주입.
- `frontend/src/api/types.ts` — 6 response 타입 + `FundamentalEvidence` /
  `EarningsEvidence` 신규. `RecommendationItem` / `HoldingCheck` 에 evidence
  optional 필드 추가.
- `frontend/src/hooks/useStockFundamentals.ts` /
  `useStockEarnings.ts` / `useEarningsCalendar.ts` 신규 — TanStack Query, staleTime
  60초 (StockDetail 계열과 동일).
- `frontend/src/pages/StockDetail/FundamentalsCard.tsx` 신규 — 최근 fiscal
  period KeyValueGrid (PER / PBR / ROE / 부채비율 / 배당수익률 / 매출 성장률 /
  영업이익 성장률 / EPS / BPS) + history 시계열 테이블 (count > 1 시).
- `frontend/src/pages/StockDetail/EarningsCard.tsx` 신규 — 최근 이벤트 +
  BEAT/MEET/MISS/UNKNOWN tone-color badge (`SurpriseBadge` 인라인 컴포넌트) +
  surprise_pct + actual vs consensus 3-tile + history 테이블.
- `frontend/src/pages/StockDetail/index.tsx` — Fundamentals + Earnings 카드를
  `lg:grid-cols-2` 한 행에 추가. `RecentHoldingChecksCard` 에 `earnings evidence`
  컬럼 추가.
- `frontend/src/pages/TodayReport/index.tsx` — `UpcomingEarningsCard` 인라인
  컴포넌트 추가. `useEarningsCalendar({ limit: 5 })` 로 가까운 5건 표시.
- `frontend/src/pages/Recommendations/RecommendationsTable.tsx` — `fund evidence`
  + `earnings evidence` 두 cell 추가 (compact summary, null/reason sentinel → "—").
- `frontend/src/tests/mswServer.ts` — 3 신규 default 핸들러 + `/api/stocks/:symbol`
  catch-all 404 보다 앞에 배치.
- `frontend/e2e/fixtures/apiMocks.ts` — `STOCK_FUNDAMENTALS_005930` /
  `STOCK_EARNINGS_005930` / `EARNINGS_CALENDAR` fixture + 라우터 패턴 추가.
- 회귀 게이트:
  - backend pytest **544 → 558 passed (+14)**
  - frontend vitest **68 → 77 passed (+9)**
  - frontend build 그린 (`tsc --noEmit && vite build`, vendor-charts 383 kB / gzip 105 kB)
  - Playwright e2e **11 → 13 passed (+2)** (chromium + page.route mock)
- 안전 범위: KIS / DART / Telegram 호출 0건, POST/PUT/DELETE 라우터 0건, scheduler
  job 0건, scoring engine weight 변경 0건, 자동매매/주문 코드 0건. 응답 트리에
  `source_file_path` / `body` / `content` / `full_text` / `raw_text` /
  `paragraph` / `html_body` / `본문` / `원문` / `전문` 13종 forbidden 키워드 0건
  노출 (`_assert_no_source_file_path` recursive 가드 + 명시 substring 검사).

### v0.6 누적 태그 (예정)

- `v0.5-final` (시작점, HEAD `9ccf0f8`)
- `v0.6-fundamental-data-layer` (Phase A 인수)
- `v0.6-earnings-event-pipeline` (Phase B 인수)
- `v0.6-fundamental-score` (Phase C 인수)
- `v0.6-frontend-fundamentals` (Phase D 인수)
- `v0.6-final` (Phase E 마감)

---

## 0-7. v0.5 마감 선언 — News, Disclosure & Theme Ranking

**v0.5 cycle 마감.** 기준선 `v0.4-final` (HEAD `0f25be6` 시점) 위에 5 phase 누적
완료. 누적 인수 태그는 `v0.5-frontend-themes` (Phase D) 이고, Phase E 마감 후
태그 `v0.5-final` 부여 예정. v0.1 backend + v0.2 frontend + v0.3 분석·운영 +
v0.4 Analyst & Theme Intelligence + v0.5 News·공시·테마 랭킹 모두 누적 마감.
v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의
저작권 정책 (본문 paragraph 미저장 / 자동 fetch default OFF / `source_file_path`
미노출) 모두 그대로 유지했다.

- 마감 일자: **2026-05-05 (Asia/Seoul)**
- 마감 게이트: backend pytest **481 passed** / frontend vitest **68 passed** /
  frontend build 그린 / Playwright e2e **11 passed**
- 누적 인수 태그: `v0.5-news-collector` → `v0.5-disclosure-pipeline` →
  `v0.5-news-score` → **`v0.5-frontend-themes`** → `v0.5-final` (Phase E 후 부여)
- 마감 사유: [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md)

### v0.5 핵심 산출물 한 줄 요약

- **News 데이터 라인** — `NewsProviderInterface` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 (19:00 KST, default OFF)
- **공시 데이터 라인** — `DisclosureProviderInterface` + `DisclosureCollector` + 5 카테고리 keyword 분류 + `collect_disclosures` 잡 (20:00 KST, default OFF)
- **`news_score` 첫 real 화** — `RealNewsScoreProducer` (composition 패턴, fallback 으로 supply/fundamental/earnings/ai 위임). 산식 `clip(50 + weighted_sentiment * 5 / max(news_count, 1), 0, 100)`
- **RiskEngine 보강** — `DisclosureRiskProducer` 가 14일 윈도우의 `RISK_DISCLOSURE` 카테고리 공시를 카운트해 `RISK_DISCLOSURE` flag + `min(count × 3, 10)` cap penalty 추가. ScoringEngine 본 weight 변경 0건
- **테마 랭킹 / 상세 화면** — `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) + 프런트 `/themes` + `/themes/:theme_id` 9번째 화면 + Sidebar `테마 (β)` 메뉴
- **추천 evidence 노출** — `RecommendationItemSchema.news_evidence` + `disclosure_risk_evidence` (whitelist 안전 필드만). `RelatedThemesCard` 테마 → `/themes/:id` 링크 + impact_path / impact_direction badge. `RecommendationsTable` evidence 컬럼 추가

### v0.5 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | News data layer (`NewsProviderInterface` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 19:00 KST) | ✅ 인수 (PR1: pytest 382 → 401 / PR2: 401 → 406, 회귀 0건) | `v0.5-news-collector` |
| B | Disclosure subset + 분류 5종 + `collect_disclosures` 잡 (20:00 KST) | ✅ 인수 (backend pytest 406 → 440, 회귀 0건) | `v0.5-disclosure-pipeline` |
| C | `RealNewsScoreProducer` + `DisclosureRiskProducer` + `ScoreProducerInterface` ABC 추출 + RecommendationEngine·HoldingCheckEngine·RiskEngine 통합 | ✅ 인수 (backend pytest 440 → 470 passed (+30), 회귀 0건) | `v0.5-news-score` |
| D | 백엔드 `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` + 프런트 `/themes` 9번째 화면 + StockDetail 영향 강화 | ✅ 인수 (backend pytest 470 → 481 (+11), vitest 60 → 68 (+8), e2e 9 → 11 (+2), build 그린, 회귀 0건) | `v0.5-frontend-themes` |
| E | `RELEASE_NOTES_v0.5.md` + README / PROJECT_STATUS / TASKS / ARCHITECTURE / ROADMAP 마감 + tag `v0.5-final` | ✅ 문서 마감 (코드 변경 0건) | `v0.5-final` (Phase E 후 부여) |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0005`, 체크리스트는 [`TASKS.md`](./TASKS.md) `v0.5 — News, Disclosure & Theme Ranking` 섹션 참조.

### v0.6 후보 (마감 후 검토 대기)

자세한 분류는 [`ROADMAP.md`](./ROADMAP.md) §6 + [`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md)
"v0.6 후보". 한 줄 요약:

- **데이터 / 분석 실제화** — DART 재무제표 파싱 (FundamentalSnapshot / EarningsSnapshot), 실 RSS / DART subset 구현체, 테마 랭킹 점수화, HoldingCheckSchema evidence 노출, LLM sentiment 보강
- **인증 / 관심종목** — 단일 토큰 → POST 라우터 → Watchlist (인증 동반 필수)
- **운영 / UX** — Sentry / Prometheus / Grafana, 모바일 레이아웃, lightweight-charts 마이그레이션, Alembic 도입
- **Future Backlog (자동매매)** — Strategy / Backtest / MockBroker / APPROVAL / SMALL_AUTO / FULL_AUTO 모두 별도 보안·컴플라이언스 사이클 선행 필수

### Phase A PR1 결과 (요약) — Data layer skeleton

> Phase A 는 **PR1 (data layer skeleton)** + **PR2 (scheduler integration)** 두
> PR 로 분리한다. PR1 인수 시점 = backend pytest **382 → 401 passed (+19)**,
> 회귀 0건. PR2 인수 후 태그 `v0.5-news-collector` 부여.

- `app/data/interfaces.py` — `NewsProviderInterface` ABC 신규 (`fetch_recent_news(*, symbols, since, limit) -> list[NewsItemDTO]`). 기존 `DataProviderInterface.fetch_news` 의 raw-dict placeholder 와는 별개.
- `app/data/dtos.py` — `NewsItemDTO` dataclass 신규 (9 필드: title / url / provider / published_at / symbol / source / category / sentiment_label / summary). **본문 paragraph / body / content / full_text / raw_text / paragraph_text / 본문 / 원문 / 전문 등 13종 forbidden 필드 0건** (테스트가 명시적 단언).
- `app/data/collectors/news_collector.py` 신규 — `NewsCollector` + `NewsCollectorResult` (fetched / inserted / skipped_duplicates / truncated_summaries). url-keyed 멱등, 재실행 시 0 중복. summary 500자 초과 시 truncate count 만 보고하고 persist 는 다음 phase 의 schema 확장에서 검토.
- `app/db/models.py` — `NewsItem.category: String(32) nullable, index=True` ALTER ADD COLUMN. 6 enum 값 (NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER). destructive 0건.
- `app/data/repositories/news_items.py` — 기존 `list_by_time_range` 외 4 신규 메서드 (`get_by_url`, `upsert_by_url` 멱등, `list_recent_by_symbol` JSON contains via Python filter, `list_recent_by_category`).
- `tests/mocks/fake_news_provider.py` 신규 — `FakeNewsProvider` 결정론적 3-row 샘플 (NEWS / EARNINGS_REPORT / RISK_DISCLOSURE 카테고리 각 1건). `since` / `symbols` / `limit` 필터 지원.
- `tests/integration/test_news_collector.py` 신규 — **19 케이스**:
  - copyright/scope guards (4건): DTO 본문 필드 0 / DTO 정확히 9 fields / ORM 본문 컬럼 0 / category 컬럼 존재
  - FakeNewsProvider (3건): determinism / symbols·since 필터 / interface 구현
  - NewsCollector flow (6건): 첫 run 3건 insert / 재실행 멱등 0 insert / category persist / related_symbols + sentiment persist / source fallback to provider / summary truncate count / empty provider 처리
  - Repository (5건): upsert_by_url returns inserted flag / empty url reject / list_recent_by_symbol JSON contains + since 필터 / list_recent_by_category 정렬·필터
- 회귀: backend pytest **382 → 401 passed (+19)**. frontend / e2e / build 변경 0건. KIS / Telegram / scheduler / API 라우터 / 프런트 0건 변경 (정책 준수).
- `DB_SCHEMA.md` §8 `news_items` 갱신 — `category` 컬럼 + 저작권 정책 한 단락.

**Phase A PR2 (scheduler integration) 진입 시 첫 작업**: `app/config/settings.py` 에 `news_collection_enabled: bool = False` 추가 → `app/scheduler/jobs.py` 에 `collect_news` 잡 + flag 분기 (false → NO_DATA, true → NewsCollector 실행) → `app/scheduler/scheduler.py` 에 19:00 KST 등록 → `tests/integration/test_scheduler_jobs.py` registry 7→8 jobs + flag 분기 케이스 ~3건.

### Phase A PR2 결과 (요약) — Scheduler integration

> Phase A 의 두 번째 PR. 직전 PR1 의 data layer 위에 8번째 일별 잡 (19:00 KST) 을
> 등록하되, **default OFF**. 운영자가 `.env` 에 `NEWS_COLLECTION_ENABLED=true`
> 를 명시 설정한 경우에만 NewsCollector 가 동작. 두 PR 누적 후 태그 `v0.5-news-collector` 부여.

- `app/config/settings.py` — `news_collection_enabled: bool = False` 추가. `NEWS_COLLECTION_ENABLED` env var 매핑 (default false). v0.1 부터 유지된 default-OFF feature flag 패턴 (`feature_real_order_execution` / `feature_full_auto` / `feature_paper_trading` / `telegram_enabled` 등) 과 동일.
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_NEWS` 상수 + `_resolve_news_provider(session)` helper (`session.info["news_provider"]` 에서 주입 받음, 없으면 None) + `collect_news(session)` 함수. **3-way branch**: (1) disabled → SUCCESS + `data_status: SKIPPED` + `reason: "news_collection_disabled"` (provider 호출 0건, 외부 호출 0건), (2) enabled + provider 미주입 → SUCCESS + `data_status: SKIPPED` + `reason: "no_provider_configured"` (실 RSS / DART 구현체가 없는 v0.5 시점의 운영 default 동작), (3) enabled + provider 주입 → `NewsCollector.collect_recent` 실행 + counters (fetched / inserted / skipped_duplicates / truncated_summaries) `result_summary` 에 기록.
- `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_NEWS` import + `DEFAULT_SCHEDULE` 19:00 KST 등록 (KIS 마감 데이터 18:00 + 지표 계산 18:30 직후 슬롯). 주석에 PR2 컨텍스트 + default-OFF 정책 명시.
- `app/scheduler/jobs.py` `JOB_FUNCTIONS` registry **7 → 8 jobs**.
- `tests/integration/test_scheduler_jobs.py` 갱신 — `test_job_functions_registry_covers_all_seven_jobs` → `..._eight_jobs`. 신규 5 케이스: `test_default_schedule_includes_collect_news_at_1900_kst` / `test_collect_news_disabled_returns_skipped_without_invoking_provider` (provider spy 가 disabled 분기에서 호출 0건 검증) / `test_collect_news_enabled_without_provider_returns_skipped` / `test_collect_news_enabled_with_fake_provider_inserts_three_rows` / `test_collect_news_enabled_re_run_is_idempotent` (재실행 시 3 skipped_duplicates).
- `tests/unit/test_project_structure.py::test_settings_defaults` — `news_collection_enabled is False` 단언 추가.
- 회귀: backend pytest **401 → 406 passed (+5)**. frontend vitest 60 / build / e2e 9 변경 없음 (코드 변경이 backend scheduler 에 한정).
- API 라우터 / 프런트 / KIS / Telegram / 자동매매 / 외부 호출 일체 변경 0건. NEWS_COLLECTION_ENABLED 가 default false 라 프로덕션 동작 영향 0건 (기존 7 잡 timeline + 19:00 SKIPPED 1 잡 추가).

### Phase B 결과 (요약) — Disclosure subset + 분류 + collect_disclosures 잡

> Phase A 의 News 패턴을 그대로 복제 + 공시 keyword 분류 (5 카테고리, priority
> order) 추가. 잡 timeline 9 잡 누적 (20:00 KST collect_disclosures 추가).
> default OFF — 운영자가 .env 에 `DISCLOSURE_COLLECTION_ENABLED=true` 명시 시
> 에만 동작.

- `app/data/interfaces.py` — `DisclosureProviderInterface` ABC (`fetch_recent_disclosures(*, symbols, since, limit)`). NewsProviderInterface 와 동일 typed 패턴.
- `app/data/dtos.py` — `DisclosureItemDTO` 신규 (9 fields: title / url / provider / published_at / symbol / company_name / disclosure_type / category / summary). 본문 paragraph / body / content / full_text 등 13종 forbidden 필드 0건 (테스트 명시 단언).
- `app/data/collectors/disclosure_collector.py` 신규 — `classify_disclosure(title, disclosure_type, summary) -> str` 순수 함수 + `DisclosureCollector` + `DisclosureCollectorResult`. 분류 5 카테고리 + priority order: **RISK_DISCLOSURE > EARNINGS_REPORT > OWNERSHIP_CHANGE > GOVERNANCE > OTHER** (RISK 우선 — 안전 신호가 실적 신호보다 중요). 한글 keyword (소송 / 횡령 / 배임 / 거래정지 / 감사의견 / 회생 / 파산 / 실적 / 잠정 / 영업이익 / 당기순이익 / 최대주주 / 지분 / 이사회 / 사외이사 등) + 영문 keyword (lawsuit / fraud / earnings / governance 등) 동시 지원.
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_DISCLOSURES` + `_resolve_disclosure_provider(session)` + `collect_disclosures(session)`. Phase A 의 `collect_news` 와 동일 3-way branch 패턴 (disabled → SKIPPED disclosure_collection_disabled / enabled+no_provider → SKIPPED no_provider_configured / enabled+provider → DisclosureCollector 실행). `result_summary` 에 `classified_counts` 추가 (5 enum 별 inserted 수). `JOB_FUNCTIONS` **8 → 9 jobs**.
- `app/scheduler/scheduler.py` — DEFAULT_SCHEDULE `(20, 0)` 등록. Phase A 의 19:00 collect_news 직후 슬롯.
- `app/config/settings.py` — `disclosure_collection_enabled: bool = False` 추가 (default OFF, `DISCLOSURE_COLLECTION_ENABLED` env var 매핑).
- `tests/mocks/fake_disclosure_provider.py` 신규 — `FakeDisclosureProvider` 결정론적 4-row 샘플: EARNINGS (삼성전자 1Q 실적) / OWNERSHIP (SK하이닉스 대량보유 변동) / RISK (A사 거래정지 + 감사의견 거절) / GOVERNANCE (B사 사외이사 선임). `symbols` / `since` / `limit` 필터 지원.
- `tests/integration/test_disclosure_collector.py` 신규 — **24 케이스**: copyright/scope guards 2 (DTO 본문 필드 0 / 9 fields exactness) / 분류 룰 18 (12 parametrized Korean keywords + RISK > EARNINGS priority + RISK > GOVERNANCE priority + uses disclosure_type / uses summary / OTHER fallback + 영문 keyword) / FakeProvider 4 (determinism / symbols 필터 / since 필터 / interface 구현) / collector flow 7 (4 inserted + classified_counts / 멱등 4 skipped_duplicates / category persist / summary truncate / empty provider / related_symbols persist) / 메타.
- `tests/integration/test_scheduler_jobs.py` 갱신 — registry 8 → 9 jobs + 20:00 KST schedule 검증 + collect_disclosures 4 분기 케이스 (disabled / enabled+no_provider / enabled+FakeProvider 4 inserted + classified_counts / 멱등).
- `tests/unit/test_project_structure.py::test_settings_defaults` — `disclosure_collection_enabled is False` 단언 추가.
- `DB_SCHEMA.md` §8 `news_items.category` 설명 보강 — 뉴스/공시 통합 저장 + DisclosureCollector keyword priority 명시.
- `INTEGRATION_RUNBOOK.md` §11 신규 — 5 단락 (기본 동작 / opt-in / 분류 룰 표 / 수동 트리거 / 운영 점검 / 롤백). §10 News 와 동일 패턴.
- 회귀: backend pytest **406 → 440 passed (+34)**. frontend vitest 60 / build / e2e 9 변경 없음. KIS / Telegram / API 라우터 / 프런트 / 자동매매 / 외부 호출 일체 변경 0건. DISCLOSURE_COLLECTION_ENABLED default false 라 프로덕션 동작 영향 0건 (8 잡 timeline + 20:00 SKIPPED 1 잡 추가).

### Phase C 결과 (요약) — RealNewsScoreProducer + DisclosureRiskProducer + RiskEngine 보강

> v0.1 의 `DummyScoreProducer.news_score = 50` placeholder 가 **처음으로 real
> 값으로 교체**됨. RecommendationEngine / HoldingCheckEngine / RiskEngine 모두
> 새 producer 를 받지만, **추천·보유 본 weight 산식은 0건 변경**. v0.4-final
> 까지의 모든 회귀 테스트 그대로 통과.

- `app/analysis/score_producers.py` 전면 정리 — `ScoreProducerInterface` ABC 추출. `DummyScoreProducer` 가 ABC 구현체로 유지 (기존 호출자 호환). `RealNewsScoreProducer` (composition pattern, fallback 으로 supply/fundamental/earnings/ai 위임) + `DisclosureRiskProducer` (14일 윈도우 + RISK_DISCLOSURE 카테고리) 신규.
- 산식: `news_score = clip(50 + weighted_sentiment * 5 / max(news_count, 1), 0, 100)`. recency 가중치 (≤24h:1.0 / ≤3d:0.7 / ≤7d:0.3 / 그 외:0) × sentiment value (POSITIVE=+1 / NEUTRAL,UNKNOWN=0 / NEGATIVE=-1). `news_count = 0 → 50` (Dummy fallback 호환). SQLite/Postgres tz roundtrip 호환 (`_to_naive_utc` helper).
- `DisclosureRiskProducer.evaluate(symbol)`: 14일 이내 RISK_DISCLOSURE 카테고리 news_items 조회 → `penalty_addition = min(count × 3, 10)` cap → `flag = "RISK_DISCLOSURE"` (count>0 시).
- `app/decision/risk_engine.py` — `evaluate_recommendation` / `evaluate_holding` 에 `disclosure_risk_count: int = 0` + `disclosure_penalty_addition: Decimal = 0` 파라미터 추가. count > 0 시 `RISK_FLAG_DISCLOSURE` 추가 + penalty 가산. **default 0 으로 backward compat** — v0.4 이전 호출자 영향 0.
- `app/decision/recommendation_engine.py` — constructor 에 `disclosure_risk_producer: DisclosureRiskProducer | None = None` 추가. `score_producer` 타입 `DummyScoreProducer | None` → `ScoreProducerInterface | None`. `generate()` 에서 producer 호출 → RiskEngine 에 disclosure 파라미터 전달 → `_Candidate.disclosure_risk_evidence` 저장 → `_persist_candidate()` 에서 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 양쪽에 `news_evidence` (components.metadata 에서 추출) + `disclosure_risk_evidence` 기록.
- `app/decision/holding_check_engine.py` — 동일 패턴. ScoringEngine 본 산식 / 3-pass 흐름 변경 0건. news_score 만 real 화 + RiskEngine 에 disclosure 파라미터 전달 + 양쪽 evidence 기록.
- **저작권 / 안전 정책 강제**: producer 가 evidence 빌더에서 `title / url / provider / published_at / sentiment` 만 노출 (body / content / full_text / source_file_path 등 0건). 단위 테스트가 evidence 의 키 집합을 명시 단언.
- `tests/unit/test_real_news_score_producer.py` 신규 — **17 케이스** (RealNewsScoreProducer 9 + DisclosureRiskProducer 8). `tests/integration/test_recommendation_engine.py` 보강 5건 + `test_holding_check_engine.py` 보강 3건 + `test_risk_engine.py` 보강 5건.
- 회귀: backend pytest **440 → 470 passed (+30)**. frontend vitest 60 / build / e2e 9 변경 없음. ScoringEngine 본 weight (technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%) 산식 0건 변경 — `news_score` 가 50 → real 로 교체될 뿐 가중치 25% 그대로.
- API 라우터 / 프런트 / KIS / Telegram / 자동매매 일체 변경 0건. `news_evidence` / `disclosure_risk_evidence` 의 명시적 schema 필드 추가 (RecommendationItemSchema 등) 는 frontend 노출 시점인 **Phase D 로 이연** — 지금은 JSON 컬럼 (`market_context_json` / `rule_result_json`) 에 저장만.

### 후보 비교 / 선택 사유 (요약)

7 개 v0.5 후보 중 채택:

- ✅ **News / 공시 실제화** — `DummyScoreProducer.news_score` 25% weight 첫 real 화 (가장 큰 점수 품질 영향)
- ✅ **테마 랭킹 화면** — v0.4 누적 데이터의 첫 surface
- △ **리포트 인텔리전스 고도화** — Phase D 의 StockDetail 영향 가시화 강화로 부분 채택

미채택 → v0.6+ 로 미룸:

- ❌ **재무 / 실적 점수 실제화** (DART 재무제표 파싱 별도 cycle)
- ❌ **관심종목 / Watchlist** (POST 첫 도입은 인증과 묶음)
- ❌ **인증 / 보안** (Watchlist 와 묶어서 v0.6)
- ❌ **전략 / 백테스트 / 자동매매** (v0.7+ Future Backlog)

### `news_score` 산식 (Phase C 상세)

```
recency_factor = sum_{news in last 7d} (
    weight_by_age * sentiment_mapping(news.sentiment)
)
weight_by_age      = 1.0 (≤24h) / 0.7 (≤3d) / 0.3 (≤7d)
sentiment_mapping  = POSITIVE: +1, NEUTRAL: 0, NEGATIVE: -1, UNKNOWN: 0
news_score         = clip( 50 + recency_factor * 5 / news_count, 0, 100 )
                   = 50 if news_count == 0  (Dummy fallback 호환)

# RiskEngine 보강
if any(category=RISK_DISCLOSURE in last 14d):
    risk_flags     += "RISK_DISCLOSURE"
    risk_penalty   += min(risk_disclosures_count * 3, 10)   # cap +10
```

본 weight 산식은 손대지 않는다 — `news_score` 가 50 → real 로 교체되지만 가중치
25% 그대로. `decision_logs.rule_result_json["news_evidence"]` 추가 (top 3 / sentiment
분포 / recency).

### Phase D 결과 (요약) — Theme ranking API + 9th menu + Recommendation evidence surfacing

> v0.4 누적 테마·매핑·시그널 데이터를 **첫 surface**. v0.5 Phase C 가
> JSON 컬럼에 저장만 해두었던 `news_evidence` / `disclosure_risk_evidence` 도
> RecommendationItemSchema 의 명시적 nullable 필드로 노출. 4 게이트 모두 그린.

- 백엔드 신규 read-only 엔드포인트 2건:
  - `GET /api/themes/ranking` — query `category` / `direction` (POSITIVE/NEGATIVE/NEUTRAL, 다른 값 422) / `limit` (1~200, default 50). 응답 각 항목에 `mapping_count` + `signal_event_count` (단일 grouped query 로 계산). 정렬 `id` 내림차순 (가장 최근 삽입 순). `source_file_path` 0건 노출.
  - `GET /api/themes/{theme_id}` — 단건 + 매핑 + 시그널 이벤트. 매핑은 `theme_*` 필드 제외 (theme 가 부모 컨텍스트). `mapping_limit` / `signal_limit` query (default 50, max 200).
- 신규 schema (`app/api/schemas.py`): `ThemeRankingItemSchema`, `ThemeRankingResponse`, `ThemeStockMappingSchema`, `ThemeDetailResponse`. 기존 `ReportSignalEventSchema` 재사용.
- `RecommendationItemSchema` 보강 — `news_evidence: Optional[Dict[str, Any]]` + `disclosure_risk_evidence: Optional[Dict[str, Any]]` 필드 추가. v0.5 Phase C 가 `DataSnapshot.market_context_json` 에 저장한 evidence 를 routes 의 `_recommendation_to_schema` 에서 추출해 surface. pre-v0.5 snapshot 은 두 필드 모두 `null` (backward compat).
- 프런트 신규 페이지 2개: `/themes` (Themes ranking, TanStack Table + direction radio + search filter + impact badge styling) + `/themes/:themeId` (Theme detail, KeyValueGrid 개요 + 영향 종목 카드 grid + 시그널 이벤트 표). Sidebar 9th 메뉴 `테마 (β)` 추가 (Tags 아이콘). React Router lazy chunk 2개 추가.
- 프런트 보강:
  - `RelatedThemesCard` (StockDetail) — 테마명을 `<Link to="/themes/{theme_id}">` 로 클릭 가능. `impact_path` 가 별도 monospace badge 로 분리, `impact_direction` 도 색상 badge.
  - `RecommendationsTable` — `news evidence` (count + top news 제목 prefix) + `disclosure risk` (count + top 공시 제목 prefix) 두 컬럼 추가. nullable 시 `—`.
- `frontend/src/api/types.ts` — `NewsEvidence` / `NewsEvidenceTopItem` / `DisclosureRiskEvidence` / `DisclosureRiskItem` / `ThemeRankingItem` / `ThemeRankingResponse` / `ThemeStockMapping` / `ThemeDetailResponse` 신규.
- 신규 hook 2개: `useThemeRanking` / `useThemeDetail` (TanStack Query v5 patterns 그대로 따름, staleTime 5분).
- 테스트:
  - backend pytest **470 → 481 (+11)** — 테마 ranking 6 (전체 + filter + invalid 422 + empty + limit + source_file_path 가드) + 테마 detail 4 (mappings + 404 + empty signals + source_file_path 가드 통합) + recommendation 2 (news/disclosure evidence whitelist 노출 + pre-v0.5 backward compat).
  - frontend vitest **60 → 68 (+8)** — `Themes.test.tsx` 5 (랭킹 happy / direction filter / search / empty / 500) + 3 (detail happy / 404 / empty signals). 기존 Recommendations / StockDetail / App 테스트도 9th menu / theme link / news+disclosure cell 단언으로 보강.
  - Playwright e2e **9 → 11 (+2)** — Themes 랭킹/상세 + StockDetail → Theme link 네비게이션 + Recommendations evidence cells. 기존 8-menu walk 테스트도 9-menu 로 갱신.
  - frontend build 그린 (vendor-charts 청크 변동 0).
- 안전 가드: 테마 ranking / detail / StockDetail / Recommendations 응답에 `source_file_path` 0건 노출 (`_assert_no_source_file_path` recursive helper 가 신규 케이스 3건에서 검증). evidence 필드의 키 집합 whitelist 단언 (top_news 정확히 `{title, url, provider, published_at, sentiment}`).
- 회귀 0건. KIS / Telegram / scheduler / 자동매매 / POST 라우터 / 산식 본 weight 일체 변경 0건.

**Phase E 진입 시 첫 작업**: `RELEASE_NOTES_v0.5.md` 작성 (Phase A~D 누적 산출 요약, 통계 481/68/build/11) + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE 마감 + 4 게이트 재검증 + tag `v0.5-final`.

### Phase E 결과 (요약) — 마감 문서 / 회귀 게이트 재확인

> 코드 / 라우터 / DB 모델 / 프런트 화면 / 외부 호출 변경 0건. 문서·릴리스 노트
> 만 작성하고 4 게이트 그대로 통과 확인.

- `RELEASE_NOTES_v0.5.md` 신규 — Phase A~D 산출물 / 4 게이트 결과 / 안전 정책
  / 알려진 한계 / v0.6 후보 / 운영 가이드 요약 / 누적 인수 태그
- `README.md` 상단 마감 배너 v0.4 → v0.5 갱신 + §1 누적 기능 (v0.5 항목 5종 추가)
  + §2 제외 범위 (v0.5 정책 4건 추가) + §4 문서 표 (RELEASE_NOTES_v0.5 + ROADMAP
  v0.6) + §6 누적 사이클 표 (v0.5 phase 5행 추가) + §6 영역별 상태 (News·공시 라인
  / 9 화면 / 9 잡 / 추천 evidence 컬럼 반영) + §11 회귀 기준선 (382/60/9 → 481/68/11)
- `PROJECT_STATUS.md` §0 시작 선언 → 마감 선언 변경 (이 블록), Phase A~E 결과
  요약 누적
- `TASKS.md` v0.5 Phase D / Phase E 체크박스 완료 + v0.5 전체 마감 표기
- `ROADMAP.md` v0.5 행 상태 갱신 + v0.5 phase 표 (✅ 마감) + 누적 태그 라인
- `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `INTEGRATION_RUNBOOK.md` /
  `DB_SCHEMA.md` 정합성 점검 — 이미 Phase B / C / D 인수 시 갱신된 항목 재확인
  (v0.5 §10 / §11 / §12 운영 절차, API §14 테마, TESTING §6.9 v0.5 카운트, DB §8
  category 컬럼)
- 4 게이트 재실행 결과: backend pytest **481 passed** / frontend vitest **68
  passed** / frontend build 그린 / Playwright e2e **11 passed**. 회귀 0건.

이후 절차: `git tag v0.5-final` + `git push origin main --tags`. GitHub Release
본문에 `RELEASE_NOTES_v0.5.md` 붙여넣기 (UI 작업).

### v0.5 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 (read-only API 만 — v0.1 ~ v0.4 일관 정책 유지)
- ❌ 뉴스 / 공시 본문 (paragraph) DB 저장 — title / URL / 메타데이터 / 분류 / sentiment 라벨만 (v0.4 저작권 정책 패턴 유지)
- ❌ 자동 fetch default ON — `news_collection_enabled` / `disclosure_collection_enabled` = false (운영자가 `.env` 에 명시 enable 시에만 동작)
- ❌ 재무 / 실적 점수 실제화 — v0.6 후보
- ❌ 관심종목 / Watchlist / 인증 — v0.6 후보 (POST 도입은 인증 사이클과 묶음)
- ❌ Strategy / Backtest / MockBroker — v0.7+ 후보
- ❌ HoldingCheckEngine 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 (`news_score` 만 placeholder 교체)
- ❌ KIS API 외 외부 자격증명 추가 — 무료 RSS / DART 공공 API 만 (default OFF, opt-in)
- ❌ LLM 자동 sentiment 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.6+

### v0.5 백엔드 정책 변경 안내

`v0.4-final` 동결을 v0.5 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터 / 잡 트리거 / 자동매매 코드는 추가하지 않는다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| A | `app/db/models.py` `NewsItem.category` ALTER ADD COLUMN (nullable) | 신규 컬럼 1개 |
| A | `app/data/interfaces.py` / `dtos.py` / `collectors/news_collector.py` (신규) | News provider ABC + DTO + collector |
| A | `app/data/repositories/news_items.py` | `upsert_by_url` / `list_recent_by_symbol` 등 메서드 추가 |
| A/B | `app/scheduler/jobs.py` / `scheduler.py` | `collect_news` (8번째) + `collect_disclosures` (9번째) 등록 |
| A/B | `app/config/settings.py` | `news_collection_enabled` / `disclosure_collection_enabled` (default False) |
| B | `app/data/collectors/disclosure_collector.py` (신규) | 공시 분류 룰 (keyword → category 5종) |
| C | `app/analysis/score_producers.py` | `ScoreProducerInterface` ABC 추출 + `RealNewsScoreProducer` + `DisclosureRiskProducer` 신규 |
| C | `app/decision/risk_engine.py` | `RISK_DISCLOSURE` flag 처리 (penalty 가산, max +10) |
| C | `app/decision/recommendation_engine.py` / `holding_check_engine.py` | score_producer ABC 주입 + `news_evidence` 기록 |
| C | `app/api/schemas.py` | `news_evidence` 필드 추가 |
| D | `app/api/routes.py` | `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) |
| D | `app/api/schemas.py` | `ThemeRankingItemSchema` / `ThemeDetailResponse` 신규 |
| D | `frontend/src/pages/Themes/` (신규 디렉터리) + `router.tsx` + `Sidebar` | `/themes` 9번째 화면 |

**HoldingCheckEngine / ScoringEngine 본 weight 산식은 손대지 않는다.** 신규 컬럼 1개 + 신규 테이블 0건 — destructive 0건. 운영 환경 마이그레이션 = `ALTER TABLE news_items ADD COLUMN category VARCHAR(32);` 한 줄.

---

## 0-8. v0.4 마감 선언 — Analyst & Theme Intelligence

**v0.4 Analyst & Theme Intelligence 사이클은 종료 (마감) 상태이다.** 기준선
`v0.3-final` 위에 리포트 메타데이터 저장, CSV import, 컨센서스 스냅샷,
`report_score` / `theme_signal_score`, StockDetail / Recommendations 대시보드 표시까지
완료했다. v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책은
그대로 유지했다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.4-final` 예정 |
| 현재 인수 태그 | `v0.4-frontend-reports` |
| 마감 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | **backend pytest 382 / frontend vitest 60 / frontend build 통과 / Playwright e2e 9** |
| 자동매매 / 실 주문 / POST | **v0.4 범위 밖** — POST 라우터 0건, 주문 코드 0건 |
| 저작권·보안 | 원문 전문 미저장, PDF BLOB 미저장, 자동 크롤링 0건, `source_file_path` 외부 노출 0건 |

### v0.4 핵심 목표

증권사 애널리스트 리포트 (기업 / 산업 / 테마 / 원자재 / 매크로 / 전략) 메타데이터를
**CSV / Excel 로 import** 하고, 리포트에서 추출한 **투자 테마** 와 **테마 → 종목
매핑** 을 저장하며, 목표가 상향 / 공급 부족 / 수요 회복 같은 **변화 시그널 이벤트**
를 구조화한다. 보조 점수 `report_score` (기업 리포트 기반) + `theme_signal_score`
(테마·시그널 기반 선행 신호) 를 계산해 추천 / 종목 상세에 참고 근거로 노출한다.
추천 최종 산식 본 weight 는 변경하지 않고, ±5점 cap 보조 가산만 적용한다.

### v0.4 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | **DB 모델 6종 + Repository** (`analyst_reports` / `report_themes` / `theme_stock_mappings` / `report_signal_events` / `report_consensus_snapshots` / `report_score_logs`) + 통합 테스트 16건 | ✅ 인수 (backend pytest 319 → 335, 회귀 0건) | `v0.4-backend-reports` |
| B | **CSV import CLI (리포트 + 테마 + 매핑 + 시그널) + 일별 컨센서스 스냅샷 잡** + 통합 테스트 27건 | ✅ 인수 (backend pytest 335 → 362, 회귀 0건) | `v0.4-import-pipeline` |
| C | `report_score` + `theme_signal_score` 계산기 + RecommendationEngine 통합 (±5점 cap 합산) + decision evidence | ✅ 인수 (backend pytest 379 / vitest 59 / build / e2e 8, 회귀 0건) | `v0.4-report-score` |
| D | 프런트 (StockDetail 리포트·테마·시그널 카드 + Recommendations score 컬럼 2개) | ✅ 인수 (backend pytest 382 / vitest 60 / build / e2e 9, 회귀 0건) | `v0.4-frontend-reports` |
| E | `RELEASE_NOTES_v0.4.md` + README / PROJECT_STATUS / TASKS 마감 + tag `v0.4-final` | ✅ 문서 마감 / 최종 게이트 재확인 권한 이슈 | `v0.4-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0004`, 체크리스트는
[`TASKS.md`](./TASKS.md) `v0.4 — Analyst & Theme Intelligence` 섹션 참조.

### Phase A 결과 (요약)

- `app/db/models.py` 에 6 테이블 신규 — `AnalystReport` (28 컬럼, COMPANY/SECTOR/INDUSTRY/THEME/COMMODITY/MACRO/STRATEGY 7 타입을 단일 테이블에서 `report_type` 으로 구분, `symbol` nullable 허용) / `ReportTheme` (theme_category 13종 + direction + time_horizon, FK source_report) / `ThemeStockMapping` (impact_direction + impact_path 11종 + relation_type + benefit_type, 글로벌 ticker 지원) / `ReportSignalEvent` (event_type 18종, evidence_json) / `ReportConsensusSnapshot` (window_days 별 분리) / `ReportScoreLog` (report_score + theme_signal_score 둘 다 보관).
- `app/data/repositories/` 에 6 Repository 신규 + `__init__.py` export 갱신. 각 repo 가 `create` + `upsert_by_*` 멱등 + 다양한 list 쿼리 (theme/symbol/direction/path/event_type/recent) 제공.
- `tests/integration/test_analyst_report_repositories.py` **16 케이스** — CRUD / unique 충돌 / 글로벌 US 리포트 (NVDA / NASDAQ / USD / Goldman Sachs broker) / null symbol (THEME / MACRO / COMMODITY) / 종목 search / 테마 카테고리·방향 / 매핑 positive·negative · impact_path / signal event 분기 / consensus window 30/90 분리 / score log recommendation_run 연계.
- 백엔드 pytest **319 → 335 passed (+16)**. frontend / e2e / build 회귀 0건 (변경 없음).
- `DB_SCHEMA.md` §18~23 추가, 저작권 정책 단락 명시. 운영 환경 마이그레이션 = 신규 `CREATE TABLE` 6 줄, destructive 0건.

### Phase B 결과 (요약)

- `app/data/importers/analyst_reports.py` 신규 — `AnalystReportCsvImporter` 가 35 컬럼 CSV 한 row 를 최대 4 entity (report + theme + N mappings + signal_event) 로 분해. enum 검증 11종, 헤더 forbidden body-column 13종 거부 (`body`/`content`/`full_text`/`paragraph_text`/`article_body`/`raw_text`/`html_body`/`paragraphs`/`full_body`/`original_text`/`report_body`/`본문`/`원문`/`전문`).
- `scripts/import_analyst_reports.py` 신규 — argparse CLI (`--file --commit --encoding --db-url`). 기본 dry-run, `--commit` 명시 시에만 DB 적재. 출력 summary 에 `source_file_path` 0건 노출 (basename 마스킹), 에러 메시지조차 컬럼명 + 정상 enum/date/숫자만 echo.
- `tests/fixtures/analyst_reports_sample.csv` 신규 (3 row: COMPANY 삼성전자 + THEME 메모리 쇼티지 + COMMODITY Cu) — 모두 가상 데이터, 실제 증권사 원문 0건.
- `app/scheduler/jobs.py` — `update_report_consensus_snapshots` 잡 신규. COMPANY 타입 + 발행 후 90일 이내 활성 리포트만 종목별 집계해 `report_consensus_snapshots.upsert_by_symbol_date_window` 로 멱등 upsert. NO_DATA / SUCCESS 분기. KIS / 텔레그램 / 외부 호출 0건.
- `app/scheduler/scheduler.py` — 06:30 KST 잡 등록 (06:00 텔레그램 발송 직후 / 08:30 pre-market check 직전 시간 슬롯). 7번째 등록 잡.
- `tests/integration/test_analyst_report_import.py` (19 케이스) + `tests/integration/test_consensus_snapshot_job.py` (8 케이스) 신규. `tests/integration/test_scheduler_jobs.py` 의 6 jobs registry 검증 → 7 jobs 로 갱신.
- `INTEGRATION_RUNBOOK.md` §9 신규 (dry-run / commit / 인코딩 / DB URL / 컨센서스 잡 수동 트리거 / 점검 5 단락).
- 백엔드 pytest **335 → 362 passed (+27)**. frontend / e2e / build 회귀 0건 (변경 없음).
- API 라우터 / 추천 엔진 / 점수 산식 / 프런트 / KIS / 텔레그램 / 자동매매 일체 변경 0건 (정책 준수). pandas / openpyxl 의존성 미추가 (stdlib `csv` 만 사용).

### Phase C 결과 (요약)

- `app/analysis/report_score_calculator.py` 신규 — `report_score`, `theme_signal_score`, 두 점수의 ±5점 cap 보조 가산을 순수 함수로 분리했다. `report_count = 0` 이면 `report_score = null`, 테마/시그널이 모두 없으면 `theme_signal_score = null` 로 처리해 기존 추천 점수 영향은 0이다.
- `app/decision/recommendation_engine.py` — 후보 종목별 최신 consensus snapshot, 최신 close, theme mapping, recent signal event 를 조회해 두 보조 점수를 계산하고 `recommendation.total_score` 에 후처리 가산만 적용한다. 기존 ScoringEngine 본 weight 는 변경하지 않았다.
- `report_score_logs` 에 추천 실행별 계산 이력을 저장하고, `decision_logs.rule_result_json["report_evidence"]` 에 score/evidence/adjustment 를 기록한다.
- `app/api/schemas.py`, `app/api/routes.py` — `RecommendationItemSchema` 에 `report_score`, `theme_signal_score`, `report_evidence` 를 nullable 필드로 추가했다. 기존 응답 필드는 유지된다.
- `tests/unit/test_report_score_calculator.py` 신규 12건, `tests/integration/test_recommendation_engine.py` / `tests/integration/test_api_routes.py` 보강. Phase C targeted pytest **77 passed**, 전체 회귀 게이트 **backend pytest 379 / frontend vitest 59 / build / Playwright e2e 8 passed**.
- HoldingCheckEngine / ScoringEngine 본 weight / KIS / 텔레그램 / 자동매매 / POST 라우터 / 프런트 화면 변경 0건.

### Phase D 결과 (요약)

- `GET /api/stocks/{symbol}` 응답에 `analyst_reports` 블록을 추가하고, 동일 구조를 반환하는 read-only `GET /api/stocks/{symbol}/reports` 라우터를 추가했다.
- `analyst_reports` 는 `latest_consensus`, `recent_reports`, `related_themes`, `recent_signal_events` 를 포함한다. `source_url` 은 허용하고 `source_file_path` 는 schema/응답에서 제외했다.
- StockDetail 화면에 Analyst Consensus, Recent Reports, Related Themes, Signal Events 카드를 추가했다. 데이터 없음 상태는 각 카드별 empty placeholder 로 처리한다.
- Recommendations 테이블에 `report_score`, `theme_signal_score`, `report_evidence` 요약 컬럼을 추가했다. null 값은 `—` 로 표시한다.
- API/vitest/e2e fixture 모두에서 `source_file_path` 미노출 검증을 추가했다.
- 회귀 게이트: backend pytest **382 passed**, frontend vitest **60 passed**, frontend build **passed**, Playwright e2e **9 passed**.
- POST 라우터 / KIS 호출 / 텔레그램 발송 / 자동매매 / 주문 코드 / 리포트 자동 크롤링 / 원문 전문 노출 / ScoringEngine 본 weight 변경 0건.

### Phase E 결과 (요약)

- `RELEASE_NOTES_v0.4.md` 신규 작성. Phase A~D 산출물, 테스트 결과, 저작권·보안 정책, 제외 범위, 알려진 한계, v0.5 후보를 정리했다.
- `README.md`, `PROJECT_STATUS.md`, `TASKS.md` 를 v0.4 마감 상태로 갱신했다.
- `API_SPEC.md` / `DB_SCHEMA.md` 기준으로 `source_file_path` 미노출 정책과 analyst report read-only API 설명을 재확인했다.
- 회귀 게이트 4종 재확인 완료 — backend pytest **382 passed**, frontend vitest **60 passed**, frontend build **passed**, Playwright e2e **9 passed**. Phase D 시점 baseline 과 동일 (회귀 0건).
- 기능 코드 / 백엔드 라우터 / 프런트 화면 / DB 모델 변경 0건.

### v0.5 후보

- Excel 직접 import 지원
- 운영자용 import 검증 리포트 개선
- StockDetail 리포트 필터/정렬 고도화
- HoldingCheckEngine에 report/theme 보조 근거를 별도 phase로 검토
- 관심종목/즐겨찾기
- 인증/권한
- 실제 News/Fundamental/Earnings 파이프라인
- Dependabot / CI 운영 보강
- 운영 DB migration 스크립트 정리

자동매매, 실주문, POST 트리거는 v0.5 후보가 아니다. 별도 보안/컴플라이언스/리스크
사이클이 선행되어야 한다.

### v0.4 데이터 모델 요약 (6 테이블)

- **`analyst_reports`** — 모든 리포트 메타 (28 컬럼, `report_type` 7종 단일 테이블, 글로벌 ticker / currency / language 지원). Unique `(broker_name, published_at, title)`. **`source_file_path` 는 API 응답 / 프런트에서 미노출** (Phase D 의 schema 단에서 마스킹).
- **`report_themes`** — 리포트에서 추출한 투자 테마. theme_category 13종 (SEMICONDUCTOR / AI / COMMODITY / ENERGY / DEFENSE / SHIPBUILDING / BIO / AUTO / BATTERY / POWER_GRID / DATA_CENTER / MACRO / CUSTOM). FK source_report.
- **`theme_stock_mappings`** — 테마 → 종목 영향 매핑. impact_direction (POSITIVE/NEGATIVE/MIXED/NEUTRAL) + impact_path 11종 + relation_type + benefit_type + time_lag. 글로벌 종목 동일 테이블.
- **`report_signal_events`** — 변화 시그널 이벤트. event_type 18종 (TARGET_PRICE_UP / SUPPLY_SHORTAGE / DEMAND_RECOVERY / RISK_WARNING …) + direction + strength + evidence_json. FK report + nullable theme.
- **`report_consensus_snapshots`** — 종목별 일별 컨센서스. `window_days` 별 분리 저장 (default 90일). Unique `(symbol, snapshot_date, window_days)`.
- **`report_score_logs`** — 두 점수 (report_score + theme_signal_score) 계산 이력. theme_count / signal_event_count / theme_signal_bonus / event_signal_bonus / risk_penalty + evidence_json. `recommendation_runs.run_id` 와 nullable FK 연계.

### v0.4 `report_score` + `theme_signal_score` 산식 (요약)

```
# (1) 기업 리포트 기반
report_score = clip( 50 + (target_upside_pct * 0.5) + (rating_score_avg * 10) + recency_bonus, 0, 100 )

# (2) 테마·시그널 기반 선행 신호
theme_signal_score = clip( 50 + theme_signal_bonus + event_signal_bonus - risk_penalty, 0, 100 )

# (3) 추천 보조 (±5 cap, 두 점수 합산)
total_score_after = clip( total_score + clip( (report_score - 50) * 0.1, -5, +5 )
                                       + clip( (theme_signal_score - 50) * 0.1, -5, +5 ), 0, 100 )
```

`report_count = 0` → `report_score = null` (영향 0). 시그널 / 테마 0 → `theme_signal_score = null`.

### v0.4 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI / 라우터 — import 는 운영자 CLI 만, GET 응답에만 변화
- ❌ 리포트 자동 크롤링 / 스크레이핑 — v0.4 는 수동 CSV/Excel + MANUAL/RULE_BASED/LLM_ASSISTED 태깅만 (자동 fetch 는 v0.5+)
- ❌ 리포트 원문 전문 (PDF body / paragraph) DB 저장 — 운영자 직접 작성 짧은 요약 (≤500자) 만
- ❌ PDF 파일 자체 git 레포 / DB BLOB 저장 — `source_url` 또는 `source_file_path` 만
- ❌ `source_file_path` 외부 노출 — API 응답 / 프런트 / e2e 모두에서 마스킹 또는 미포함
- ❌ 외부 공유 / 공개 API
- ❌ LLM 자동 요약 — Phase A 는 미구현, `extraction_method` / `extraction_confidence` 필드만 미리 둠 (v0.5+ 후보)
- ❌ 뉴스 / 공시 / 재무 / 실적 실시간 수집 — v0.5+ 별도 cycle
- ❌ 즐겨찾기 / 관심 종목 / 인증 / Strategy / Backtest / MockBroker — v0.5+ 후보 그대로
- ❌ HoldingCheck 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 — 두 score 모두 ±5점 cap 보조 가산만

### v0.4 백엔드 동결 정책 변경 안내

`v0.3-final` 동결을 v0.4 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터
/ 잡 트리거 / 자동매매 코드는 추가하지 않는다.

| Phase | 변경 파일 | 종류 | 상태 |
|---|---|---|---|
| A | `app/db/models.py` | ALTER ADD TABLE **6개** | ✅ |
| A | `app/data/repositories/{analyst_reports,report_themes,theme_stock_mappings,report_signal_events,report_consensus_snapshots,report_score_logs}.py` | 신규 Repository 6개 | ✅ |
| A | `app/data/repositories/__init__.py` | export 추가 | ✅ |
| A | `tests/integration/test_analyst_report_repositories.py` | 16 케이스 신규 | ✅ |
| B | `scripts/import_analyst_reports.py` | 신규 CLI (dry-run/commit, 리포트 + 테마 + 매핑 + 시그널) | ✅ |
| B | `app/scheduler/jobs.py`, `app/scheduler/scheduler.py` | `update_report_consensus_snapshots` 잡 1건 추가 | ✅ |
| C | `app/analysis/report_score_calculator.py` | 신규 순수 함수 (report_score + theme_signal_score) | ✅ |
| C | `app/decision/recommendation_engine.py` | 두 score 후처리 가산 + decision evidence 기록 | ✅ |
| C/D | `app/api/schemas.py` | 신규 schema 4종 (`AnalystReportSchema` / `ReportThemeSchema` / `ThemeStockMappingSchema` / `ReportSignalEventSchema`) + `RecommendationItemSchema` 확장 | ✅ Phase C: 추천 응답 score 필드 |
| D | `app/api/routes.py` | 신규 read-only `GET /api/stocks/{symbol}/reports` 등 | ✅ |

**HoldingCheckEngine / ScoringEngine 본 weight 산식 / 6 잡 시그니처는 손대지
않는다.** 신규 테이블 추가는 `CREATE TABLE` 이라 destructive 0건이지만 운영
환경 마이그레이션 안내 필수 ([`DB_SCHEMA.md`](./DB_SCHEMA.md) 끝부분 박스 참조).

---

## 0-9. v0.3 마감 선언 — 분석 보강 + 운영 정착

**v0.3 분석 보강 + 운영 정착 사이클은 종료 (마감) 상태이다.** 신규 기능 / 잡 /
라우터 / 화면 추가는 사용자의 명시적 v0.4 진입 요청 전까지 진행하지 않는다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.3-final` |
| 인수 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | **백엔드 pytest 319 / frontend vitest 59 / Playwright e2e 8 / build 그대로** (외부 호출 0건, mock / DRY_RUN 만) |
| 자동매매 / 실 주문 | **v0.3 범위 밖** — `BrokerInterface` ABC placeholder 그대로 유지 / POST 트리거 0건 |
| 누적 인수 태그 | `v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → **`v0.3-final`** |
| 종합 인수 사유 | [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) |

### v0.3 4 phase 인수 결과

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | GitHub Actions CI (backend pytest + frontend vitest+build + Playwright e2e 3 job) | ✅ 인수 | `v0.3-phase-a-ci` |
| B | 캔들 패턴 5종 + Wilder ATR(14) + 변동성 분류 → `technical_score` 산식 보강 (DB 컬럼 +3) | ✅ 인수 (backend pytest 296 → 314, vitest / e2e / build 회귀 0) | `v0.3-backend-analysis` |
| C | 정적 KRX 휴장일 캘린더 (2025–2027) + Today/Jobs/Holdings MarketStatusBanner | ✅ 인수 (vitest 36 → 55, e2e 6 → 7, build / backend pytest 314 회귀 0) | `v0.3-frontend-calendar` |
| D | `GET /api/stocks/{symbol}/prices` 신규 + StockDetail 일봉 라인 차트 (Recharts) | ✅ 인수 (backend pytest 314 → 319, vitest 55 → 59, e2e 7 → 8, build 그대로) | `v0.3-frontend-stock-chart` |
| E | `RELEASE_NOTES_v0.3.md` + README / PROJECT_STATUS / TASKS 마감 + tag `v0.3-final` | ✅ 인수 (코드 변경 없음, 4 게이트 그대로) | `v0.3-final` |

### Phase A 결과 (요약)

- `.github/workflows/ci.yml` 신규 — main / PR 양쪽에서 3 job 자동 실행: (1) backend pytest python 3.12 + `pip install -e ".[dev]"`, (2) frontend vitest + lint + build node 20, (3) Playwright e2e (`playwright install chromium` + `npm run e2e` + `playwright-report/` artifact 업로드).
- PR 1건 의도적 실패로 빨강 한 번 확인 → 픽스 후 그린 상태로 마감.
- 코드 변경 없음 (워크플로우 / config 만 추가). `.github/dependabot.yml` 은 v0.4 후보로 보류.

### Phase B 결과 (요약)

- `app/analysis/technical_analyzer.py` 에 캔들 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING / BEARISH_ENGULFING) detector + Wilder ATR(14) + 4단계 volatility band (LOW/NORMAL/HIGH/EXTREME) 추가.
- `calculate_technical_score` 에 보조 가산/감산 (`candle_bonus` ±5 cap, `volatility_bonus` -5~+2) 후 0~100 clamp 명시. 새 인자는 모두 default None 이라 기존 호출자는 수치 변화 0건.
- `StockIndicator` 에 nullable 컬럼 3개 추가 (`atr14 Numeric(20,4)`, `candle_patterns JSON`, `volatility_band String(16)`). ALTER ADD only — 기존 데이터 무영향.
- `StockIndicatorRepository.upsert` 시그니처에 신규 키워드 3개 (default None) + `TechnicalIndicatorService` 가 snapshot 의 신규 필드를 그대로 upsert.
- `StockIndicatorSchema` (Pydantic) 에 3개 optional 필드 추가 → `/api/stocks/{symbol}.latest_indicator` 응답에 자동 포함. 프런트 타입은 Phase D 에서 명시 추가 예정.
- 단위 테스트 16건 신규 (analyzer 32 → 48), 통합 테스트 2건 신규 (indicator 7 → 9), 기존 회귀 0건. 백엔드 전체: **296 → 314 passed**.
- 부수 정정: `frontend/vite.config.ts` 의 vitest `include` / `exclude` 추가 — Playwright e2e 파일 (`e2e/**/*.spec.ts`) 이 vitest 의 기본 glob 에 잡혀 collect 단계 실패하던 노이즈 제거.

### Phase C 결과 (요약)

- `frontend/src/data/krxHolidays.ts` 신규 — 2025~2027 KRX 휴장일 정적 JSON. 카테고리 6종 (`fixed` / `lunar` / `substitute` / `election` / `temporary` / `year-end`). 주석에 출처 (KRX 공식 휴장일 안내) + 매년 갱신 절차 4단계 (KRX 공지 확인 → 다음 해 항목 추가 → 테스트 1~2건 추가 → PR / push → CI 회귀).
- `frontend/src/lib/marketCalendar.ts` 신규 — KST(`Asia/Seoul`) 기준 `todayInSeoul` + UTC midnight 산술 기반 `dayOfWeek` / `isWeekend` / `getHoliday` / `isHoliday` / `isMarketClosed` / `isMarketOpen` / `nextOpenDay` (max 30 day scan, throw on exceed) / `previousOpenDay` / `classifyMarketStatus` (open / WEEKEND / HOLIDAY 분기 + `nextOpen`). 외부 API / 백엔드 호출 0건.
- `frontend/src/components/common/MarketStatusBanner.tsx` 신규 — `data-state` 3 분기 (`open` 에메랄드 / `holiday` 앰버 / `weekend` 뉴트럴). 헤드라인 / 디테일 한국어. `date?` prop 으로 시점 freeze 가능 (테스트용).
- Today / Jobs / Holdings 화면 헤더 직후에 `<MarketStatusBanner />` 1줄 통합. 다른 화면 (Recommendations / History / StockDetail / MarketCapTop / Settings) 은 v0.3 범위 외라 미통합.
- 단위 테스트 19건 신규 (`marketCalendar.test.tsx` 15 + `MarketStatusBanner.test.tsx` 4) → vitest **36 → 55 passed**.
- e2e 1건 신규 — Today / Jobs / Holdings 3 경로에서 `data-testid="market-status-banner"` 노출 + `data-state` 정합성 검증 → playwright **6 → 7 passed**.
- 회귀: backend pytest 314 / build 그대로. 백엔드 코드 변경 0건 (정책 준수).

### Phase D 결과 (요약)

- `app/api/routes.py` 에 read-only `GET /api/stocks/{symbol}/prices?days=120` 신규. `days` 는 `Query(120, ge=1, le=500)` 검증, `daily_prices` 만 조회 (KIS 호출 0건). `app/api/schemas.py` 에 `StockPriceSeriesResponse` 추가 (`symbol`, `days`, `count`, `prices[DailyPriceSchema]`).
- `DailyPriceRepository.list_by_symbol` 가 이미 최신 N건을 날짜 오름차순으로 반환하는 형태라 라우터는 wrapping 만. 응답 일자 정렬 = ascending (차트 그대로 사용 가능). 404: 종목 없음, 200 + count=0: 종목은 있으나 일봉 0건.
- `tests/integration/test_api_routes.py` 에 5건 신규 (`stock_prices_returns_series_ascending_with_default_days` / `caps_to_requested_days_param` / `returns_empty_when_no_prices_seeded` / `404_for_unknown_symbol` / `validates_days_bounds` 0/501 → 422). 백엔드 전체: **314 → 319 passed**.
- 프런트: `useStockPriceSeries(symbol, { days })` 훅 (queryKey `['stocks', symbol, 'prices', { days }]`, staleTime 60s, `enabled: !!symbol`) + `StockPriceSeriesResponse` 타입 추가.
- `frontend/src/pages/StockDetail/PriceChart.tsx` 신규 — Recharts `LineChart` (close 추세). `data-testid="price-chart"` / 빈 상태 `price-chart-empty`. Recharts 는 `vendor-charts` 청크에 격리되어 있고 StockDetail 페이지 자체가 router 레벨 `React.lazy` 라 별도 lazy wrap 불필요.
- `frontend/src/pages/StockDetail/index.tsx` 에 `PriceChartCard` 추가 — 30/60/120/250 days 선택자 (`role="tab"`, 기본 120d active), loading / error / empty / success 4 상태. POST 트리거 / 자동매매 UI 0건.
- vitest 4건 신규 (chart success / empty / error / days 선택자 토글 + searchParams 검증), MSW 기본 핸들러 `/api/stocks/:symbol/prices` (count=0) 추가, e2e fixture `STOCK_PRICE_SERIES_005930` (5건) + 라우트 패턴 `/api/stocks/005930/prices` 우선순위 등록. 프런트 vitest **55 → 59**, Playwright e2e **7 → 8**.
- 빌드 그대로 (vendor-charts 청크 383.32 kB 동일, StockDetail 페이지 청크만 8.28 → 11.36 kB 증가). 정책: 자동매매 / KIS 호출 / 텔레그램 / POST 라우터 / 추천·보유 산식 0건 변경.

### Phase E 결과 (요약)

- `RELEASE_NOTES_v0.3.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.4 후보 / 인수자 가이드 / 보안).
- `README.md` 상단 마감 배너 갱신 — v0.3 마감 선언으로 교체, v0.1 / v0.2 는 누적 태그 라인으로 흡수.
- `PROJECT_STATUS.md` §0 v0.3 마감 선언으로 변경 (본 섹션). 기존 §0-1 v0.2 / §0-2 v0.1 마감 선언은 그대로 보존.
- `TASKS.md` v0.3 Phase E 모든 [x] + v0.4 백로그 정리.
- 4 게이트 재확인 — backend pytest **319**, frontend vitest **59**, frontend build 그대로, Playwright e2e **8**. 회귀 0건.
- **코드 변경 0건** (문서 마감 위주). 백엔드 라우터 / 프런트 화면 / 잡 / 산식 / 비밀값 일체 손대지 않음.

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0003`, 체크리스트는 [`TASKS.md`](./TASKS.md) `v0.3 — 분석 보강 + 운영 정착` 섹션 참조.

### v0.3 에서 끝까지 하지 않은 것 (정책 재확인)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO — 코드 0건 추가
- ❌ POST 트리거 UI (수동 잡 실행 / 추천 즉시 생성 / 보유 추가·삭제 폼) — frontend / backend 양쪽 0건
- ❌ 실 News / Supply / Fundamental / Earnings 외부 파이프라인 — `DummyScoreProducer` placeholder 유지, 캔들/ATR/변동성만 추가 (기존 일봉 데이터로 계산)
- ❌ 즐겨찾기 / 관심 종목 / 인증 / 모니터링 / 모바일 — 모두 v0.4+ 후보

### v0.3 백엔드 동결 정책 변경 (확정)

`v0.1-backend-final` 동결을 v0.3 에서 일부 깬 범위는 다음으로 한정 — POST 라우터 /
잡 트리거 / 자동매매 코드는 추가하지 않았다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| B | `app/analysis/technical_analyzer.py` | 신규 함수 (캔들 5종 / ATR / 변동성), 기존 산식 시그니처는 default None 키워드만 추가 |
| B | `app/db/models.py` | `StockIndicator` ALTER ADD 3 컬럼 (모두 nullable) |
| B | `app/data/repositories/stock_indicators.py` | `upsert` 키워드 3개 추가 |
| B | `app/analysis/indicator_service.py` | snapshot 의 신규 필드 persist |
| B/D | `app/api/schemas.py` | `StockIndicatorSchema` +3 optional / `StockPriceSeriesResponse` 신규 |
| D | `app/api/routes.py` | 신규 read-only `GET /api/stocks/{symbol}/prices` 1개 |
| B/D | `tests/integration/test_*.py` | +5 (Phase B indicator) +5 (Phase D prices) |

DB 컬럼 추가는 `ALTER TABLE ADD COLUMN` 만이라 destructive 하지 않다. 운영 환경
마이그레이션 안내는 [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) §7.3 참조.

---

## 0-10. v0.2 PC 대시보드 마감 선언

**v0.2 frontend 는 종료 (마감) 상태이다.** v0.1 backend 동결 (`v0.1-backend-final`)
위에 PC 대시보드 8 화면이 모두 read-only 로 연결되었고, vitest 36 + Playwright
e2e 6 + 백엔드 pytest 296 회귀 게이트가 모두 통과. 종합 인수 사유는
[`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) 참조.

| 항목 | 값 |
|---|---|
| 최종 frontend 태그 | `v0.2-frontend-final` |
| 누적 frontend 태그 | `phase-a` (골격) → `phase-b` (Today/Jobs) → `phase-c` (Recommendations/History) → `phase-d` (Holdings/StockDetail) → `phase-e` (MarketCap/Settings) → `final` (lazy + e2e + Docker + 릴리스) |
| 8 화면 | 오늘 / 추천 / 추천 이력 / 보유 / 종목 상세 / 시총 TOP / 잡 / 설정 — 모두 실 데이터 연동 + 빈/에러 상태 처리 |
| 번들 (첫 진입 Today) | ≈ 297 kB / gzip ~80 kB (lazy + manualChunks 적용 후). Recharts 청크는 추세 화면 진입 시에만 로드 |
| Docker | `docker compose up --build` → 백엔드 (8000) + 프런트 (8080) 동시 기동, nginx `/api` → backend proxy |
| 자동매매 / 실 주문 | **v0.2 범위 밖** — `BrokerInterface` ABC placeholder 유지 / POST 트리거 UI 0건 |

---

## 0-11. v0.1 백엔드 마감 선언 (참고)

**v0.1 백엔드는 종료 (마감) 상태이다.** 새 기능 / 리팩터 / 잡 / 라우터 추가는
사용자의 명시적 v0.2 backend 진입 요청 전까지 진행하지 않는다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.1-backend-kis-paper-verified` |
| 인수 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | pytest **296 passed** (외부 호출 0건, mock / DRY_RUN 만) |
| 통합 검증 | mock seed (§2 "v0.1 통합 실행 결과") + 실 KIS 모의투자 read-only (§2 "실 KIS 운영 검증 결과" + 후속) 모두 1회 통과 |
| 자동매매 / 실 주문 | **v0.1 범위 밖** — `BrokerInterface` ABC placeholder 만 유지 (구체 구현 0건) |
| 누적 인수 태그 | `v0.1-foundation-checkpoint` → `v0.1-backend-accepted` → `v0.1-backend-kis-paper-verified` |

마감 선언의 종합 사유 / 산출물 / 알려진 한계 / v0.2 후보는
[`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) 에 정리.

---

## 1. 완료된 Phase

| Phase | 범위 | 주요 산출물 |
|---|---|---|
| **0** 프로젝트 준비 | 13개 문서 + 초기 커밋 | AGENTS.md, README, ARCHITECTURE, API_SPEC, DB_SCHEMA, ROADMAP, SECURITY, TESTING, TASKS, PLANS, brief / detailed_spec / agent_creation_spec |
| **1** 아키텍처/골격 | FastAPI 앱, 4개 인터페이스 | `app/main.py`, `app/config/`, `DataProviderInterface`, `AIProviderInterface`, `BrokerInterface`, `StrategyInterface`, `.env.example` |
| **2** DB/Repository | 17개 ORM 모델 + Repository | `app/db/{base,models,session}.py`, `app/data/repositories/*.py` (16개 클래스) |
| **3-1** KIS DTO/normalizer/validator | DTO + 정규화 + 품질 검사 | `app/data/dtos.py`, `app/data/normalizers/kis.py`, `app/data/validators/quality.py` |
| **3-2** KIS HTTP 클라이언트 | httpx 기반 read-only 클라이언트 | `app/data/collectors/kis_client.py` (토큰/현재가/일봉/시총) |
| **3-3** Collector | KIS raw → DB 저장 흐름 | `DailyPriceCollector`, `MarketCapRankingCollector`, `FakeKisDataProvider` (테스트용) |
| **4-1** TechnicalAnalyzer | 순수 지표 계산기 | `app/analysis/technical_analyzer.py` (MA/RSI/MACD/breakout/ma_alignment/technical_score) |
| **4-2** IndicatorService + ScoringEngine | 저장 서비스 + 점수 산식 | `app/analysis/indicator_service.py`, `app/decision/scoring_engine.py` (신규 추천/보유 가중치) |
| **5-1** RecommendationEngine | 추천 골격 (placeholder 점수) | `app/decision/recommendation_engine.py`, `recommendation_runs/recommendations/data_snapshots/decision_logs` 4개 테이블 일괄 저장 |
| **5-2** HoldingCheckEngine | 장전/장후 보유 점검 | `app/decision/holding_check_engine.py`, HOLD/WATCH/REDUCE/SELL_REVIEW 결정, 위험 경고 평가 |
| **5-3** RiskEngine | risk_penalty / risk_level / risk_flags | `app/decision/risk_engine.py`, ScoringEngine 및 양 Engine 연결, `data_snapshots`/`decision_logs`에 risk 결과 기록 |
| **5 후속** 추천 성과 검증 | 1/3/5/20일 후 수익률 계산 | `app/decision/recommendation_result_service.py`, `recommendation_results` upsert 멱등 |
| **6** Notification & Report | 텔레그램용 텍스트 + 발송 + 로그 | `app/notification/report_generator.py`, `telegram_notifier.py`, `notification_service.py` (DRY_RUN 기본) |
| **7** Backend API | 13개 read-only GET 라우터 | `app/api/{schemas,routes}.py`, FastAPI lifespan 통합, 모든 Decimal은 JSON 문자열 직렬화 |
| **7 후속** API 성과 노출 | 추천 항목에 `results[]` + history 집계 | `RecommendationResultSchema`, `RecommendationHistoryItem` 확장 (`success_rate`, `avg_close_return_{1,3,5,20}d`) |
| **8** Scheduler + 6개 Job | APScheduler + `run_job` 래퍼 | `app/scheduler/{jobs,scheduler}.py`, FastAPI lifespan에서 lazy import 후 시작/종료, `SCHEDULER_ENABLED` 제어 |
| **8 후속** Dispatcher 연결 | 추천/보유/ALERT 잡 → 텔레그램 자동 발송 | `app/notification/dispatchers.py`, 잡에서 `session.info["job_run_id"]`로 `notification_logs.related_job_id` 자동 연결, `HoldingRiskAlertDispatcher` 연동 완료 |
| **8 후속** 잡 최종 점검 | 6개 잡 모두 dispatcher / engine / NO_DATA·PARTIAL 분기 정리 | `send_recommendation_report`은 최신 run을 dispatcher로 발송 (NO_DATA 단락), `run_pre/post_market_holding_check`은 활성 보유 없으면 NO_DATA 단락, `update_recommendation_results`는 `data_status` SUCCESS/PARTIAL/NO_DATA + skipped_no_reference 시 PARTIAL |
| **4 후속** Dummy score producer | News/Supply/Fundamental/Earnings/AI 컴포넌트 점수 placeholder | `app/analysis/score_producers.py` (`DummyScoreProducer`), `RecommendationEngine`/`HoldingCheckEngine` 생성자 default 주입 — neutral 50 + volume_ratio_20d / ma_alignment 기반 룰베이스 ±5 nudge, 메타데이터 `decision_logs.rule_result_json["score_producer"]`에 저장 |
| **7 후속** Stock detail 추천 이력 join | `/api/stocks/{symbol}` 응답에 추천 이력 + 1/3/5/20일 성과 | `_resolve_recent_recommendations_for_symbol` (Recommendation+RecommendationRun join, run_date desc), `RecommendationItemSchema.results: List[RecommendationResultSchema]` 채움, `recommendation_limit`/`holding_check_limit` 쿼리 파라미터 |
| **7 후속** Holding check 추세 metric | `/api/holdings/{symbol}/checks` 응답에 종목 단위 summary 추가 | `HoldingCheckSymbolMetrics`/`HoldingCheckSymbolResponse` 신규 schema, summary는 limit 무관하게 종목 전체 이력 집계 (total/alert/high_risk count + latest/previous/change + best/worst return rate + latest decision/risk_level), 정렬 규칙 `(check_date desc, POST > PRE)` |
| **9** v0.1 통합 시나리오 / mock seed | 실 KIS·실 텔레그램 없이 백엔드 전체 흐름 로컬 검증 | `scripts/seed_mock_data.py` (멱등 + `--reset`), `INTEGRATION_RUNBOOK.md` (사전준비 → 시드 → 6개 잡 수동 트리거 → 13개 GET API → 로그 검증 → 회귀 게이트), README §9 진입점 |

브리프 전체 v0.1 범위 + 일부 v0.2 후속 (성과 검증, dispatcher, holding metric, 통합 시나리오) 까지 도달. **v0.1 백엔드 마감 상태** — 코드 변경이 남은 v0.1 항목은 §4 "남은 v0.1 작업" 의 두 건뿐이며, 이번 작업으로 신규 세션 / QA 인수자가 mock seed + runbook 만으로 전체 흐름을 30분 안에 검증 가능.

---

## 2. 현재 테스트 결과

```text
296 passed in 5.48s
```

| 영역 | 파일 수 | 테스트 수 |
|---|---:|---:|
| `tests/unit/` | 11 | 127 |
| `tests/integration/` | 11 | 169 |

**테스트 파일별 카운트:**

```text
tests/integration/test_api_routes.py                     42
tests/integration/test_collectors.py                      8
tests/integration/test_dispatchers.py                    16
tests/integration/test_holding_check_engine.py           17
tests/integration/test_indicator_service.py               7
tests/integration/test_notification_service.py            6
tests/integration/test_recommendation_engine.py          13
tests/integration/test_recommendation_result_service.py  13
tests/integration/test_repositories.py                    6
tests/integration/test_scheduler_jobs.py                 34
tests/integration/test_v01_required_repositories.py       7
tests/unit/test_data_quality_checker.py                   4
tests/unit/test_kis_client_http.py                        9
tests/unit/test_kis_normalizers.py                        3
tests/unit/test_project_structure.py                      4
tests/unit/test_report_generator.py                      12
tests/unit/test_risk_engine.py                           25
tests/unit/test_scheduler_module.py                       5
tests/unit/test_score_producers.py                        3
tests/unit/test_scoring_engine.py                        16
tests/unit/test_technical_analyzer.py                    32
tests/unit/test_telegram_notifier.py                     14
```

회귀 0건. 모든 외부 호출(KIS, Telegram)은 mock transport / dry-run 으로만 접근.

### v0.1 통합 실행 결과 (1회 수행)

`INTEGRATION_RUNBOOK.md` §1 ~ §5 시나리오를 실제로 1회 수행한 결과 (UTC
2026-05-04 22:52 / Asia/Seoul 2026-05-05 07:52, throwaway SQLite 파일).

**1. Seed (`scripts.seed_mock_data --reset`)**

```text
stocks:5  market_cap_rankings:5  universe_members:5  daily_prices:150
stock_indicators:5  holdings:2  recommendation_runs:3  recommendations:8
holding_checks:4  data_snapshots:12
```

**2~7. 6개 잡 수동 트리거 (모두 SUCCESS, dry-run)**

| 잡 | status | 핵심 result_summary |
|---|---|---|
| `collect_market_close_data` | SUCCESS | mock provider 주입, market_cap_status=SUCCESS, daily=5/5 success |
| `calculate_technical_indicators` | SUCCESS | members=5, snapshots_saved=5, skipped=0, fail=0 |
| `send_recommendation_report` | SUCCESS | notification_status=DRY_RUN, run_date=2026-05-04, recs=3, msg_len=364 |
| `run_pre_market_holding_check` | SUCCESS | check_type=PRE_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `run_post_market_holding_check` | SUCCESS | check_type=POST_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `update_recommendation_results` | SUCCESS | data_status=SUCCESS, runs=3, processed=8, upserted=32, pending=29, success=0, failed=3, skipped_no_ref=0 |

**8. notification_logs / job_runs**

- `notification_logs`: 7건 — REPORT 3 (recommendation 1 + holding pre/post 2) + ALERT 4 (HIGH_RISK 3 + CHECK_ALERT 1, target dedup 키 정상)
- `job_runs`: 6건, 모두 SUCCESS. result_summary / status / error_message / finished_at 정상 기록
- `holding_checks`: 8건 (005930 5 + 000660 3) — 시드의 4건 + 잡이 새 일자(Asia/Seoul today)에 추가한 4건

**9. 13개 GET API 응답**

```text
200 /health
200 /api/reports/today
200 /api/recommendations/latest    (recommendations=3)
200 /api/recommendations/history   (items=3 — 시드한 3개 run)
200 /api/holdings                  (holdings=2)
200 /api/holdings/checks/latest    (items=2)
200 /api/holdings/005930/checks    (items=5 + summary)
200 /api/stocks/005930
200 /api/universe/market-cap-top   (items=2 — 잡이 limit=2로 갱신)
200 /api/market-regime/latest
200 /api/news                      (items=0 — 시드 미적재)
200 /api/jobs                      (items=6)
200 /api/settings                  (KIS/Telegram 자격증명 마스킹)
```

`/api/holdings/005930/checks` summary 표본:
`total=5, alert=3, high_risk=2, latest_decision=SELL_REVIEW,
latest_risk_level=MEDIUM, latest_total_score=16.2500, previous=4.2500,
change=12.0000`.

**관찰 / 알아둘 점**

- `seed_mock_data`는 `datetime.now(UTC).date()`를 "today"로 사용하지만,
  스케줄러 잡은 `_today_in_default_timezone()` (`settings.timezone`,
  default Asia/Seoul)을 사용. 시드 실행 시각이 UTC 15:00 이후 (≈ Seoul
  24:00 이후) 이면 시드 "today"가 잡의 "today"보다 하루 빠르게 나오고,
  잡은 새 일자에 fresh 행을 만들어 둘 다 공존한다. 데이터 손상은 아니며
  대시보드 추세 metric도 정상 동작.
- `update_recommendation_results`는 시드 가격 30봉 안에서 1/3/5/20일 후
  검증을 수행 — 가장 오래된 run (today-7) 만 1/3/5일 모두 평가 가능, 나머지는
  PENDING이 다수.
- 회귀 게이트 `pytest`: **296 passed in 5.87s** (이번 실행 직후 동일 결과 확인).

### 실 KIS 운영 검증 결과 (1회 수행)

`KIS_OPS_CHECKLIST.md` 절차에 따라 실 KIS 모의투자 키 + 검증용 비공개 텔레그램
채팅방 기준으로 1회 시도. read-only 인증과 일봉 조회는 통과, 시총 상위
endpoint 에서 KIS contract 결함 1건이 발견되어 **collect 잡은 FAILED**.

**검증 모드**

- `KIS_USE_PAPER=true` (모의투자 서버 `openapivts.koreainvestment.com:29443`)
- `TELEGRAM_ENABLED=false`
- `SCHEDULER_ENABLED=false`
- `FEATURE_REAL_ORDER_EXECUTION=false`
- `FEATURE_FULL_AUTO=false`
- 검증용 DB: `sqlite:///./stock_ai_kis_check.db` (운영 / 시드 DB 와 격리)

**사전 안전 점검 (모두 통과)**

- `.env` git ignore / 미커밋 / 이력 부재
- `.env` ACL 좁히기 적용 (Owner + Admins + SYSTEM 만 FullControl, CodexSandboxUsers 는 Read 만)
- `Settings()` 로딩 시 `kis_app_key` / `kis_app_secret` / `kis_account_no` /
  `telegram_bot_token` / `telegram_chat_id` 모두 마스킹된 형태로만 표시
- `/api/settings` 라우터 응답에서도 동일한 마스킹 + 안전 플래그 모두 false
- 실주문 / 자동매매 코드 부재: `place_order` / `order_execute` / KIS 주문
  엔드포인트 / `BrokerInterface` 구체 구현 모두 0건 — `BrokerInterface` 는
  `app/broker/interfaces.py` 의 ABC 정의(`raise NotImplementedError`) 로만 존재

**KIS read-only 단건 검증**

- 토큰 발급 (`/oauth2/tokenP`): ✅ SUCCESS (token length=346, 본문 비노출)
- 005930 일봉 조회 (`/uapi/domestic-stock/v1/quotations/inquire-daily-price`): ✅ SUCCESS
  - 조회 기간: 2026-04-28 ~ 2026-05-05 (영업일 4건)
  - 반환 row 수: 4
  - 첫 행 (최신순): `date=20260504, close=232500`
  - 마지막 행: `date=20260428, close=222000`
  - 모의투자 시세는 paper 서버 자체 시뮬레이션 값이므로 실시장과 다름 (정상)

**`collect_market_close_data` 잡 결과**

- 잡 자체는 정상 호출 (스키마 자동 생성, 안전 가드 통과, `job_runs` 행 정상 기록)
- 시총 상위 endpoint 호출에서 KIS 서버가 거절 →
  `KIS API error OPSQ2001: ERROR INPUT FIELD NOT FOUND [FID_COND_SCR_DIV_CODE]`
- 결과: `status=FAILED`, `market_cap_status=FAILED`, `daily_price_status=SKIPPED`
  (시총 단계 실패로 daily 수집은 의도적으로 실행되지 않음)

**영향 범위 (이번 1회 검증 기준)**

| KIS 경로 | 결과 |
|---|---|
| 토큰 발급 | ✅ |
| 일봉 조회 | ✅ |
| 시총 상위 ranking | ❌ contract 결함 1개 (필드 누락) |

따라서 v0.1 KIS 클라이언트의 read-only 경로 중 **시총 상위 endpoint 1개만**
paper 서버와 contract 가 어긋남. 인증 / 일봉은 정상 동작.

**Known Issue**

- `app/data/collectors/kis_client.py:fetch_market_cap_rankings` 의 query
  파라미터에 `FID_COND_SCR_DIV_CODE` 가 누락. KIS 시총 상위 화면 카테고리
  코드(후보값 `"20174"`) 추가 필요.
- `tests/unit/test_kis_client_http.py` 의 captured query params 도 실 KIS
  contract 에 맞춰 신규 파라미터 transmit 검증으로 갱신 필요.
- mock HTTP 테스트만으로는 이 누락이 드러나지 않으므로, 후속 픽스 시 paper
  서버 1회 재검증을 절차에 명시.

**다음 조치**

1. 별도 코드 수정 세션에서 `fetch_market_cap_rankings` 파라미터 보정 1줄 추가 + 단위 테스트 갱신.
2. 픽스 commit 후 `collect_market_close_data` 잡을 paper 서버에서 1회 재실행 → market_cap → daily_prices → 시총 + 일봉 모두 SUCCESS 확인.
3. 그 다음 단계로 `calculate_technical_indicators` → `send_recommendation_report` (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 시범 운행 진입.

**비밀 / 토큰**

본 절에는 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 / chat_id 평문이
일체 기록되지 않았다. 모든 비밀은 마스킹 형태(예: `5015****1-01`)로만
참조한다. 운영 검증 도중 발급된 KIS 액세스 토큰도 디스크 / 로그에 남지 않음
(`LOG_TO_FILE=false`).

### 후속 검증 — 시총 픽스 적용 후 (3회 시도)

`fetch_market_cap_rankings` 의 query 에 `FID_COND_SCR_DIV_CODE="20174"` 를
추가하는 픽스 (`eb8452a`) 적용 후 `collect_market_close_data` 잡을 동일한
검증 환경 (`KIS_USE_PAPER=true` / 검증용 DB / `MARKET_CAP_LIMIT=5`) 에서 3회
재실행. lookback 은 1·2회는 2일, 3회차는 7일.

**시총 상위 endpoint — 3/3 SUCCESS**

- 3회 모두 `market_cap_status=SUCCESS`, KOSPI 시총 상위 5건 정상 응답.
- `stocks` (5 신규 → 이후 0 신규, idempotent), `market_cap_rankings` (3회
  모두 5건, snapshot replace 정상), `stock_universe_members` (5 신규 → 0)
  저장 정상. KIS 시총 상위 endpoint contract 결함은 완전 해소.

**일봉 endpoint — signature 정상 / 종목별 paper 서버 한계 노출**

| 종목 | 1차 (lookback=2) | 2차 (lookback=2) | 3차 (lookback=7) | 누적 |
|---|---|---|---|---|
| 005930 (삼성전자) | ❌ | ✅ | ✅ (3 rows) | 2/3 |
| 005935 (삼성전자우) | ✅ | ❌ | ✅ (3 rows) | 2/3 |
| 402340 (SK스퀘어) | ✅ | ❌ | ❌ | 1/3 |
| 000660 (SK하이닉스) | ❌ | ❌ | ❌ | 0/3 |
| 373220 (LGES) | ❌ | ❌ | ❌ | 0/3 |

- 005930 / 005935 가 안정 SUCCESS 한 사실로 일봉 endpoint signature 자체는
  정상으로 판단. 직전 단건 검증 (`fetch_daily_prices(005930, 7일)` 4 rows)
  과 일관됨.
- 000660 / 373220 은 lookback / 호출 시점 무관하게 항시 `KIS HTTP 500`
  반환 → KIS 모의투자 서버의 종목별 시뮬레이션 데이터 또는 캐시 미적재
  문제로 추정. 코드 contract 결함으로 보지 않음.
- 402340 은 randomize 패턴 (run 마다 결과 변동) — 동일 paper 서버
  transient 5xx 패턴.

**잡 동작 정상 분기**

- 3회 모두 `status=PARTIAL`, `error_message="N daily price collections failed"`,
  종목별 실패는 `result_summary.failures` 항목 단위로 격리 기록.
- `job_runs` 행은 RUNNING → PARTIAL 전환 + `finished_at` / `result_summary` /
  `error_message` 정상 채워짐.
- 성공 종목의 `daily_prices` upsert + `market_cap_rankings` snapshot replace
  는 PARTIAL 상황에서도 의도대로 commit 됨 → DB 무결성 유지.

**회귀 게이트**

- 시총 픽스 직후 `pytest`: **296 passed in 5.87s** (회귀 0건).
- 본 후속 검증은 코드 변경을 동반하지 않음.

**판단 / 다음 단계**

- v0.1 백엔드 코드는 인수 (accepted) 상태 유지. KIS contract 픽스 1건이
  추가되었지만 영향 범위는 단일 endpoint 의 query 파라미터 한 줄로 좁고
  paper 서버에서 실측 검증됨.
- 본격 운영 검증 (전 종목 일봉 SUCCESS 확인) 은 KIS 실서버
  (`KIS_USE_PAPER=false`) 또는 paper 서버의 종목별 시뮬레이션 데이터가
  안정화된 시점에 다시 수행. v0.1 잡의 PARTIAL 격리 동작이 검증되었으므로
  실서버 진입 시 일부 종목 실패가 나오더라도 전체 흐름이 멈추지 않음.
- 다음 검증 cycle 에서는 `calculate_technical_indicators` → `send_recommendation_report`
  (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 진입 가능 (시총·일봉
  데이터 일부라도 적재된 상태).

---

## 3. 변경된 주요 모듈

| 패키지 | 핵심 모듈 | 책임 |
|---|---|---|
| `app/config/` | `settings.py`, `logging.py` | env 기반 Settings (`@lru_cache`), telegram/KIS/feature flags 포함 |
| `app/db/` | `base.py`, `models.py`, `session.py` | SQLAlchemy 2.0, 17개 v0.1 테이블, `SessionLocal` |
| `app/data/` | `interfaces.py`, `dtos.py`, `collectors/`, `normalizers/`, `validators/`, `repositories/` | 외부 API 경계, 16개 Repository, KisClient + 정규화 + 품질 검사 |
| `app/analysis/` | `technical_analyzer.py`, `indicator_service.py` | 순수 지표 계산 + `daily_prices` → `stock_indicators` upsert |
| `app/decision/` | `scoring_engine.py`, `risk_engine.py`, `recommendation_engine.py`, `holding_check_engine.py`, `recommendation_result_service.py` | 점수/리스크/추천/보유점검/사후 성과 |
| `app/notification/` | `report_generator.py`, `telegram_notifier.py`, `notification_service.py`, `dispatchers.py` | 텔레그램 텍스트 포맷 + 발송 (DRY_RUN 기본) + 로그 + dispatcher |
| `app/api/` | `schemas.py`, `routes.py` | 13개 GET 라우터, Pydantic v1 schema, Decimal → str 일관 직렬화 |
| `app/scheduler/` | `jobs.py`, `scheduler.py` | `run_job` 2-session 래퍼, 6개 잡, APScheduler `BackgroundScheduler` |
| `app/main.py` | FastAPI 앱 + `lifespan` | 라우터 등록, 스케줄러 lazy import 시작/종료, `/health` |

**의존성 (`pyproject.toml`):** fastapi 0.99, pydantic 1.10, SQLAlchemy 2.0, httpx 0.24+, uvicorn 0.30+, python-dotenv, **apscheduler 3.10+** (Phase 8에서 추가).

---

## 4. 아직 하지 않은 작업

**v0.1 범위 안에서 남은 것 (코드 변경 0건)**

코드 작업은 모두 완료. 운영 / 문서 단계만 남아있다.

- 실 KIS 키 + 실 텔레그램으로 1회 운영 검증 — 코드 경로는 완성되어 있고
  `KisClient`가 `settings`에서 자동 연결됨. `.env` 채움 + 안전 플래그 확인 +
  체크리스트 항목별 통과만 필요. 절차는 [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md)
  로 분리 정리.
- PROJECT_STATUS.md / TASKS.md — 신규 세션마다 수동 갱신 필요

**v0.2 이후로 미룬 범위 (Backlog)**

- 캔들 패턴 (망치형/장악형 등) + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
  (Phase 4 후속, 신규 분석 기능 — v0.1 마감 시점에 명시적으로 v0.2 이동)
- React/Next.js PC 대시보드 프론트엔드
- 전략(장기/중기/단기) 관리, SIGNAL/PAPER 모드
- 백테스트 엔진, walk-forward 검증, 그리드 서치 튜닝
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 v0.1은 `DummyScoreProducer` 룰베이스 placeholder)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래)

---

## 5. 다음에 이어서 할 첫 번째 작업

**v0.1 백엔드는 마감 상태 (tag `v0.1-backend-accepted`).** 남은 코드 작업 없음.
다음 세션이 우선 처리할 항목은 다음 1건:

- **운영 검증 1회** — [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 항목별로
  실 KIS 키 + 실 텔레그램(검증용 비공개 채팅방)에서 1회 통과 후 결과를
  PROJECT_STATUS.md §2 "v0.1 통합 실행 결과" 아래 새 하위 절로 기록한다.
  코드 변경 없음.

캔들 패턴 / ATR / 그 외 신규 분석·전략·프론트엔드는 모두 v0.2 Backlog (§4)로
이동했으므로, 사용자의 명시적 v0.2 진입 요청 없이는 진행하지 않는다.
v0.1 마감 후의 새 기능 (잡 / 라우터 / 엔진 / dispatcher 추가)도 마찬가지.

---

## 6. 주의해야 할 v0.1 금지사항

`AGENTS.md` "Out of Scope" 섹션과 `SECURITY.md`를 어기지 말 것. 핵심:

**기능 금지**

- 실거래 자동매매, FULL_AUTO 모드, 가상 증권사 서버, 전략 자동 튜닝, 전용 AI 모델 학습
- KIS 주문 API 실행 (조회만 OK; 주문은 `BrokerInterface` placeholder만 유지)
- 대시보드 라우터 안에서 추천 생성 / 보유점검 실행 / 지표 재계산 / KIS 호출
- POST/PUT/DELETE 라우터 (현재 13개 모두 GET; 새 POST 라우터 만들지 말 것)
- 자동매매 / 주문 / 비중 결정 코드를 AI나 LLM이 단독으로 호출하는 경로

**보안 / 비밀**

- KIS app_key / app_secret / access_token / refresh_token / 계좌번호
- Telegram bot_token, chat_id (chat_id는 `12****90` 형태로만 노출)
- OpenAI API key, DB 비밀번호
- 위 값을 코드 / 로그 / 테스트 / 응답 본문 어디에도 평문 노출 금지
- `.env`는 절대 커밋 금지, `.env.example`만 커밋

**테스트**

- 실제 KIS API 호출하는 테스트 금지 → `httpx.MockTransport` 또는 `FakeKisDataProvider`
- 실제 텔레그램 발송 테스트 금지 → `telegram_enabled=False` (DRY_RUN) 또는 `httpx.MockTransport`
- 시간이 실제로 될 때까지 기다리는 스케줄러 테스트 금지 → 잡 함수를 직접 호출
- 실제 API 키 / 계좌번호를 테스트에 사용 금지 (모두 `fake_*` placeholder 사용)

**아키텍처 경계**

- Data 모듈은 판단하지 않는다 (Collector → Recommendation 직접 호출 금지)
- Analysis 모듈은 외부 API 호출하지 않는다
- Recommendation/Holding 모듈은 KIS API 직접 호출하지 않는다 (Repository 경유)
- AI 모듈이 직접 매매하지 않는다
- 라우터는 Repository 또는 service를 통해서만 데이터 조회
- 새 잡이 라우터를 호출하지 않는다 (잡 → service / dispatcher 직접)

**관찰성**

- 모든 추천/보유점검은 `data_snapshots` + `decision_logs`에 기록 가능해야 함
- 모든 잡 실행은 `job_runs`에 기록 (성공/PARTIAL/FAILED)
- 모든 텔레그램 발송 시도는 `notification_logs`에 기록 (DRY_RUN/SUCCESS/FAILED/DISABLED)

---

## 7. 다음 Codex 세션 첫 프롬프트

새 세션을 시작하면 아래 프롬프트를 그대로 사용한다.

```text
이 프로젝트의 AGENTS.md, TASKS.md, PROJECT_STATUS.md, SECURITY.md를 먼저 읽고
v0.1 범위 / 현재 진행 상태 / 금지사항을 파악해줘.

코드는 아직 수정하지 마. 다음 두 가지만 알려줘.
1. PROJECT_STATUS.md 의 "5. 다음에 이어서 할 첫 번째 작업"이 여전히 적합한가?
   (그 사이 사용자가 다른 우선순위를 말하지 않았다면 적합하다고 가정)
2. 작업을 시작하기 전에 미리 알아둬야 할 의문/리스크가 있는가?

내가 "진행해" 라고 답하면 그때부터 다음 작업의 PM/Architect 시점으로
PLANS.md 형식의 짧은 실행 계획을 먼저 작성해줘 (수정할 파일 / 새로 만들
파일 / 단계 / 테스트 / 완료 기준 / 위험 요소). 계획을 내가 승인하면
구현으로 들어가.

작업 중에는 v0.1 금지사항(특히 실거래 / 실 KIS 호출 / 실 텔레그램 발송 /
라우터 안에서 무거운 로직)을 어기지 마. 새 기능은 항상:
  - 기존 service/engine을 호출하거나
  - 기존이 없으면 안전한 placeholder를 반환하고
  - 모든 외부 호출은 mock 가능한 구조로 만들고
  - 모든 추천/보유점검/잡/알림은 snapshot/log/job_runs/notification_logs로
    추적 가능하게 만들어.
```
