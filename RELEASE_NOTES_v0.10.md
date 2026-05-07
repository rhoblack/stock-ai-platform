# Release Notes — v0.10 Real Provider Readiness & Resilience

마감 일자: **2026-05-07**
마감 태그: `v0.10-final`
기준선: `v0.9-final` (HEAD `90e3db3`)

---

## 1. 사이클 개요

v0.9 에서 처음 도입한 `ProviderCallResult` / `retry_with_backoff()` /
`CircuitBreaker` skeleton 위에 **운영 가능한 외부 데이터 인프라** 의 첫 단계를
쌓은 사이클. 실 외부 호출은 여전히 0건이지만 — provider resilience runtime,
DART OpenAPI / RSS·Atom 두 provider skeleton, 그리고 운영자가 한눈에
provider 상태를 확인할 수 있는 read-only health API + UI 가 모두 준비되었다.

- **Provider Resilience Runtime** — `ProviderHealthMonitor` + `call_with_resilience()`
  + 6 settings + 31 tests (Phase A)
- **DART Provider Skeleton** — `DartFundamental/Earnings/Disclosure` + parser +
  body-strip + crtfc_key 마스킹 + 49 tests, transport 주입형 (Phase B)
- **RSS/News Provider Skeleton** — `RssNewsProvider` (RSS 2.0 + Atom) +
  dedup + URL query secret 마스킹 + 33 tests, stdlib xml.etree only (Phase C)
- **Provider Health API + UI** — `GET /api/health/providers` + `ProviderHealthPanel`
  Settings 패널 + 17 backend / 7 vitest / 1 e2e tests (Phase D)

자동매매 / 실주문 / Broker / 실 KIS / 실 DART / 실 RSS / Telegram 자동 발송 은
**모두 0건** 유지. 본 사이클의 모든 코드는 transport 주입형 skeleton이며,
실제 httpx 전송 도입은 v0.11+ 후보 (라이선스 검토 선행 필수).

---

## 2. Phase 별 산출물

### Phase A — Provider Resilience Runtime (`v0.10-provider-resilience`)

**목표**: v0.9 의 retry / circuit-breaker primitive 위에 provider 별 in-memory
상태 추적 + failure-isolation wrapper 를 추가해서 Phase B/C/D 가 안전하게 사용할
수 있도록 한다.

| 파일 | 내용 |
|---|---|
| `app/data/provider_health_monitor.py` (신규) | `ProviderHealthMonitor` (register / record_result / get_status / get_all_status / reset / reset_all) + `ProviderStats` dataclass + module-level singleton (`get_health_monitor()`) |
| `app/data/provider_health_monitor.py` (신규) | `call_with_resilience(provider_name, fn, ...)` — retry + circuit-breaker + `try/except` failure isolation. **never raises** — 모든 예외는 `ProviderCallResult.fail(UNKNOWN)` 로 변환. `request_id` 옵션으로 v0.9 `RequestIDMiddleware` 와 구조화 로그 상관관계 유지 |
| `app/config/settings.py` 보강 | `PROVIDER_RESILIENCE_ENABLED=False` 기본 + 6 런타임 설정 (timeout / max_attempts / base/max delay / circuit-breaker threshold / reset timeout) |
| `tests/data/test_provider_health_monitor.py` (신규) | 31 케이스 — `ProviderStats.to_dict` / register idempotency / record_result success+failure / reset+reset_all / circuit OPEN 전이 / call_with_resilience 성공 path / retry on SERVER_ERROR / CLIENT_ERROR 비재시도 / 예외 isolation / 반복 raise never propagates / OPEN 시 fast-fail / unregistered provider 대응 / request_id WARNING 로그 / settings 6종 default / stub provider job isolation 데모 |

게이트: backend pytest **916 → 947 passed (+31)**, 회귀 0건. Alembic revision 0건.

---

### Phase B — DART Provider Skeleton (`v0.10-dart-provider`)

**목표**: v0.6 의 `FundamentalProviderInterface` / `EarningsProviderInterface` +
v0.5 `DisclosureProviderInterface` ABC 위에 DART OpenAPI 구현체를 추가한다.
실 DART HTTP 호출 0건 — transport 주입형 skeleton 만.

| 파일 | 내용 |
|---|---|
| `app/data/dart_provider.py` (신규) | `DartFundamentalProvider` (`/api/fnlttSinglAcnt`) + `DartEarningsProvider` (동일 endpoint actual subset) + `DartDisclosureProvider` (`/api/list.json`) — 모두 `_DartProviderBase` 상속, `call_with_resilience(provider_name="dart", ...)` 경유 |
| `app/data/dart_provider.py` parser/mapper | `parse_fundamentals` (whitelist account 6종) + `parse_earnings` (actual 만 추출, consensus None — DART 비공개) + `parse_disclosure_item` / `parse_disclosures` (rcept_no/rcept_dt 누락 row 개별 skip) |
| `app/data/dart_provider.py` 정책 가드 | `_strip_forbidden_fields` 가 `body / content / full_text / paragraph / raw_text / html_body / 본문 / 원문 / 전문` 등 13종 사전 strip. `summary` 500자 truncate. `crtfc_key` 는 `_call` 내부에서만 params 에 주입 |
| `app/data/dart_provider.py` 매핑 | `classify_dart_status` — 000 (정상) / 010..013 / 020 / 100 / 101 (CLIENT_ERROR) / 800 / 900 (SERVER_ERROR) / 미정의 (UNKNOWN) |
| `app/config/settings.py` 보강 | `DART_ENABLED=False` / `DART_API_KEY=""` / `DART_BASE_URL` / `DART_TIMEOUT_S=10.0` / `DART_MAX_ATTEMPTS=3` / `DART_PROVIDER_NAME="dart"` 6 설정 |
| `app/config/logging.py` 보강 | `SensitiveFilter` regex 에 `crtfc_key / crtfckey / dart_key` 명시 추가, `\b` 경계 제거로 `dart_api_key` / `DART_API_KEY` 도 기존 `api_key` 패턴과 매칭 |
| `tests/data/test_dart_provider.py` (신규) | 49 케이스 — 6 settings / 4 disabled-guard / 10 status classifier / 12 parser+mapper (happy + malformed + body strip) / 9 provider integration (api_key 주입 + 실패 격리 + TIMEOUT / 예외 / circuit breaker trip / 다중 symbol corp_code / since 필터 / factory) / 3 DTO body-field 부재 / 8 SensitiveFilter 6 변형 + 안전 필드 + provider WARNING 로그 / 1 httpx.Client 미생성 단언 |

게이트: backend pytest **947 → 995 passed (+48)**, 회귀 0건. Alembic revision 0건.

---

### Phase C — RSS / News Provider Skeleton (`v0.10-rss-provider`)

**목표**: v0.5 `NewsProviderInterface` ABC 위에 `RssNewsProvider` 추가. 메타데이터
전용, 운영자 명시 URL 만, 신규 의존성 0건.

| 파일 | 내용 |
|---|---|
| `app/data/rss_provider.py` (신규) | `RssNewsProvider` — Phase B DART 와 동일한 transport 주입형 + `call_with_resilience(provider_name="rss", ...)` 경유; per-feed 실패 isolation (한 feed 실패해도 나머지 feed 계속) |
| `app/data/rss_provider.py` parser | `parse_feed` — root tag 기반 RSS 2.0 / Atom 자동 분기. `_parse_rss_item` (`<title>` / `<link>` / `<pubDate>` / `<description>` / `<category>`) + `_parse_atom_entry` (`<title>` / `<link rel="alternate">` / `<updated>` 또는 `<published>` / `<summary>` / `<category term=...>`) — `<content>` 는 의도적으로 미참조 (body shaped) |
| `app/data/rss_provider.py` 정책 가드 | `_strip_forbidden` 가 `body / content / content_encoded / full_text / paragraph / raw_text / html / html_body / description_full / 본문 / 원문 / 전문` strip. `<description>` 내 HTML 태그 정규식 strip + summary 500자 truncate. `dedup_items` URL first-wins. `_safe_url_for_log` 가 query string + fragment strip 후 host + path 만 로그 |
| `app/data/rss_provider.py` config | `RSS_NEWS_ENABLED=False` 또는 `RSS_FEED_URLS=""` 시 `RssNotConfiguredError` (provider 인스턴스화 / transport 호출 0건) |
| `app/config/settings.py` 보강 | `RSS_NEWS_ENABLED=False` / `RSS_FEED_URLS=""` / `RSS_TIMEOUT_S=10.0` / `RSS_MAX_ATTEMPTS=3` / `RSS_PROVIDER_NAME="rss"` 5 설정 |
| `tests/data/test_rss_provider.py` (신규) | 33 케이스 — 3 settings / 4 disabled-guard / 10 RSS+Atom parser (happy + HTML strip + per-item category override + 명시 source override + Atom updated/published fallback + invalid XML + unknown root + 빈 channel + 빈 feed) / 3 forbidden body field strip + DTO 부재 + summary 500자 truncate / 1 dedup first-wins / 9 provider integration (single feed + cross-feed dedup + per-feed isolation + TIMEOUT + 예외 격리 + circuit breaker trip + since 필터 + limit cap + factory) / 2 URL secret strip (`_safe_url_for_log` 단언 + 실 provider 로그 caplog 단언) / 1 httpx.Client 미생성 단언 |

게이트: backend pytest **995 → 1028 passed (+33)**, 회귀 0건.
신규 pip 의존성 0건 (`feedparser` 미도입, stdlib `xml.etree.ElementTree` only).

---

### Phase D — Provider Health Read-only API + UI (`v0.10-health-api`)

**목표**: Phase A~C 의 provider 상태를 한 화면에서 운영자가 확인할 수 있는
read-only API + Settings 패널을 추가한다. provider toggle / mutation 0건.

| 파일 | 내용 |
|---|---|
| `app/api/health_routes.py` (신규) | `GET /api/health/providers` — `ProviderHealthMonitor.get_status(name)` + `Settings` opt-in 플래그 합성 → `ProviderHealthResponse(items, count)`; canonical 3 provider (`kis` / `dart` / `rss`) 항상 노출 + experimental provider monitor iteration 순서로 append; `last_error_message` 응답 미포함 (URL query secret 누출 방지); POST/PUT/DELETE 모두 405 (read-only 정책) |
| `app/api/__init__.py` + `app/main.py` | `health_router` 등록 |
| `frontend/src/api/types.ts` 보강 | `ProviderCircuitState` (CLOSED / OPEN / HALF_OPEN / UNREGISTERED) + `ProviderHealthItem` (9 whitelist 필드) + `ProviderHealthResponse` |
| `frontend/src/api/providerHealth.ts` (신규) | `getProviderHealth()` — `apiFetch` wrapper |
| `frontend/src/hooks/useProviderHealth.ts` (신규) | `useQuery` (staleTime 30s, refetchInterval 60s, refetchOnWindowFocus=false) |
| `frontend/src/components/common/ProviderHealthPanel.tsx` (신규) | read-only table — 9열 (provider / enabled badge / configured badge / circuit_state badge / calls / ok / fail / last_error / last_called_at). Badge 색상 (CLOSED→emerald, HALF_OPEN→amber, OPEN→red, UNREGISTERED→slate); enabled-but-not-configured 분리 표시 (amber). 패널 내 button / checkbox / switch / form 0건 |
| `frontend/src/pages/Settings/index.tsx` 보강 | UserPreference 섹션 아래 + system read-only 섹션 위에 `<ProviderHealthPanel />` 삽입 |
| `frontend/src/tests/mswServer.ts` + `frontend/e2e/fixtures/apiMocks.ts` | `/api/health/providers` 기본 핸들러 + `PROVIDER_HEALTH_DEFAULT_OFF` fixture |
| `tests/integration/test_health_providers.py` (신규) | 17 케이스 — canonical 3 row 항상 노출 / DART·RSS default-OFF / enabled+configured 분리 / monitor 카운터 propagate / OPEN circuit state propagate / paranoid 14종 forbidden substring 단언 / `last_error_message` 미노출 단언 / httpx.Client 미생성 단언 / experimental provider append / POST/PUT/DELETE 405 |
| `frontend/src/tests/ProviderHealthPanel.test.tsx` (신규) | 7 케이스 — happy / disabled+not_configured 배지 / OPEN 배지 / 500 placeholder / empty placeholder / hypothetical secret leak 미렌더링 / read-only (button 0건) |
| `frontend/e2e/dashboard.spec.ts` 보강 | 1 신규 — `/settings` 패널 visible + DART/RSS data-enabled=false + 패널 내 button 0건 + page text + raw payload 양쪽에서 forbidden substring (`crtfc_key / dart_api_key / rss_feed_urls / kis_app_secret / last_error_message / access_token / password`) 0건 |

게이트: backend pytest **1028 → 1045 passed (+17)** / vitest **146 → 153 passed (+7)** /
e2e **19 → 20 passed (+1)** / build 그린 (3.41s). 회귀 0건.

---

### Phase E — Closure (`v0.10-final`)

본 release notes 작성 + README / PROJECT_STATUS / ROADMAP / TASKS / TESTING /
ARCHITECTURE / API_SPEC v0.10-final 갱신 + 4 게이트 최종 재확인.

---

## 3. 최종 테스트 게이트 (v0.10 마감 시점)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend pytest | `python -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults` | **1045 passed, 1 deselected** (test_settings_defaults 로컬 .env 충돌 — Phase A 부터 baseline 인계) |
| frontend vitest | `cd frontend && npm run test -- --run` | **153 passed** (20 파일) |
| frontend build | `cd frontend && npm run build` | ✓ built in 3.41s |
| Playwright e2e | `cd frontend && npx playwright test` | **20 passed** (chromium) |

회귀 0건. 자동매매 / 실주문 / 실 KIS / 실 DART / 실 RSS / Telegram 실제 호출 0건.
신규 Alembic revision 0건 (head 그대로 `0004_user_preferences`).

---

## 4. 안전 정책

### 4.1 자동매매 / 실주문 완전 미포함 (v0.1~v0.10 누적)

- `BrokerInterface` — ABC placeholder 만 유지. 구현체 0건.
- `FULL_AUTO` / `APPROVAL` / `SMALL_AUTO` / `MockBroker` / `ReplayBroker` 코드 일체 없음.
- `WatchlistItem` ORM 에 broker / account / quantity / order_price / order_type / side 컬럼 0건.
- `StrategySignal.action` 은 분석 신호 전용 — 실제 주문 전송 경로 없음.

### 4.2 외부 API 자동 호출 0건 — provider default OFF

- DART OpenAPI — `DART_ENABLED=False` 기본. true 일 때도 transport 주입형
  skeleton만 존재; 실 httpx 전송은 v0.11+ 라이선스 검토 후 별도 cycle.
- RSS / News — `RSS_NEWS_ENABLED=False` 기본. `RSS_FEED_URLS` 미설정 시 즉시
  `RssNotConfiguredError` (자동 discovery / crawling 0건).
- KIS — `KIS_USE_PAPER=true` 기본 (모의투자 서버). 모든 테스트는
  `FakeKisDataProvider` / `httpx.MockTransport` 만 사용.
- Telegram — `TELEGRAM_ENABLED=false` 기본. 모든 테스트에서 실 발송 0건.
- 통합 검증: `tests/data/test_dart_provider.py` / `tests/data/test_rss_provider.py`
  / `tests/integration/test_health_providers.py` 모두 `httpx.Client` 미생성
  단언 (monkeypatch `AssertionError` 가드).

### 4.3 본문 / 비밀값 미저장 / 미노출

- DART parser → `body / content / full_text / paragraph / raw_text / html_body /
  본문 / 원문 / 전문` 사전 strip. DTO 자체에 해당 필드 부재.
- RSS parser → 동일 forbidden field set + `<content:encoded>` /
  `description_full` 추가 strip. `<description>` HTML 태그 정규식 strip +
  summary 500자 truncate.
- `crtfc_key` (DART API key) — `SensitiveFilter` 가 6 변형 (`dart_api_key /
  DART_API_KEY / crtfc_key / CRTFC_KEY / crtfckey / dart_key`) 모두 mask.
  실 provider WARNING 로그에 평문 0건 (caplog 단언).
- RSS feed URL 의 query string secret (`?api_key=...` / `?token=...`) —
  `_safe_url_for_log` 가 query / fragment strip 후 host + path 만 로그.
- `GET /api/health/providers` 응답 — `last_error_message` 미포함
  (transport detail / URL query secret 누출 차단). `last_error_kind` enum 만
  노출.
- 14종 forbidden substring 종합 단언 (`crtfc_key / dart_api_key / DART_API_KEY /
  rss_feed_urls / kis_app_key / kis_app_secret / access_token / password /
  jwt_secret / ?api_key= / source_file_path / 본문 / 원문 / 전문`).

### 4.4 Provider Health UI 는 read-only

- `/api/health/providers` 는 GET only (POST/PUT/DELETE 모두 405).
- Provider Health 패널 내부에 button / checkbox / switch / form 0건 (e2e
  단언). enable/disable 토글은 `.env` 수정 + 백엔드 재시작 으로만 가능.
- 백엔드가 hypothetical 하게 secret 을 echo 해도 컴포넌트가 텍스트로
  렌더하지 않음 (vitest paranoid `container.textContent` 검사).

### 4.5 ScoringEngine / HoldingCheckEngine 본 weight 변경 0건

- v0.1 ~ v0.10 일관 — recommendation 산식 (technical 35% / news 25% /
  supply 15% / fundamental 15% / ai 10%) + holding 산식 (technical 35% /
  news 20% / earnings 20% / ai 15% / profit_management 10%) 그대로.
- DART/RSS provider 가 도입됐지만 ScoringEngine 에 신규 weight 0건 — score
  반영은 v0.11+ 후보.

### 4.6 Alembic 새 revision 0건

- v0.10 cycle 동안 신규 ORM / table / 컬럼 변경 0건.
- Alembic head 그대로 `0004_user_preferences` (v0.9 마감 상태와 동일).
- ProviderHealthMonitor 는 in-memory 만 (프로세스 재시작 시 초기화).

---

## 5. 알려진 한계

| 항목 | 상태 |
|---|---|
| DART / RSS 실 httpx transport 미구현 | 두 provider 모두 transport 주입형 skeleton 만. Phase D 운영자 / 라이선스 검토(사람) 후 v0.11+ 에서 실 httpx 전송 도입 예정 |
| Provider score 반영 미반영 | DART fundamental / earnings / RSS news 가 ScoringEngine weight 에 반영되지 않음 — v0.11+ 후보 |
| ProviderHealthMonitor 영속화 미지원 | in-memory only — 서버 재시작 시 카운터 / 회로 상태 초기화. 응답에 명시. Prometheus exporter / 외부 시계열 DB 연결은 v0.11+ |
| `GET /api/health/jobs` 미추가 | Phase D 범위에서 보류. 기존 `GET /api/jobs` 가 동일 정보 제공. 분리 필요 시 v0.11+ |
| Provider toggle UI 미구현 | enable/disable 은 `.env` + 재시작만. operator 가 GUI 에서 toggle 하는 것은 v0.11+ 인증 + 보안 검토 후 |
| RSS feed URL 정적 등록 | `RSS_FEED_URLS` env 콤마 구분 — 운영자가 직접 검토한 URL 만. 자동 discovery / 동적 추가 0건 |
| 자동매매 미진입 | `BrokerInterface` placeholder 유지. 별도 보안 / 컴플라이언스 / 자본 한도 사이클 선행 필수 |
| LLM 보강 미진입 | News sentiment / 재무 분석 / 자동 전략 모두 룰 기반 — LLM 보강은 v0.11+ |

---

## 6. v0.11 후보

| 후보 | 사유 |
|---|---|
| 실 DART / RSS httpx transport 도입 | Phase B/C skeleton 위에 실 HTTP 전송 + retry policy 튜닝. 라이선스 검토(사람) 선행 필수 |
| Prometheus exporter + Grafana 대시보드 | v0.10 ProviderHealthMonitor in-memory → 외부 시계열 DB 노출. 외부 노출 규모 확인 후 |
| DART/RSS score 반영 | `RealNewsScoreProducer` (v0.5) / `RealFundamentalScoreProducer` (v0.6) 위에 DART/RSS 데이터 연결. 룰 기반 검증 후 weight 보강 |
| 백테스트 고도화 | walk-forward / 다중 전략 포트폴리오 / 실 broker fee schedule. recommendation_results 3~6개월 누적 후 |
| 인증 고도화 | refresh token / 다중 사용자 / OAuth / SSO / RBAC. 단일 사용자 운영 검증 후 |
| CSP / rate limit 고도화 | v0.9 의 rate limit 기본값을 실 트래픽 기준으로 튜닝 + CSP 정책 수립 (Vite devserver / nginx 충돌 검토 후) |
| LLM 보강 | News sentiment / 재무 분석 / 어닝 surprise 보강 / 자동 전략 생성 — 룰 기반 검증 + 데이터 누적 후 |
| WebSocket / SSE 실시간 잡 / 백테스트 진행 | 현재 polling 만. 인증 + 모니터링 안정화 후 |
| Watchlist 가격 알림 / target return alert | 알림 시스템 = 별도 cycle (Telegram 실 발송 + 트리거 디자인 동반) |
| Paper / Simulation Trading 준비 | MockBroker / ReplayBroker / SimulationBroker skeleton — 별도 보안 / 컴플라이언스 사이클 선행 |
| Approval Trading Safety Layer | 자동매매 전 단계 (수동 승인) — 비상정지 / 일일 손실 제한 / 자본 한도 동반 |

> **자동매매 / 실주문 (FULL_AUTO / SMALL_AUTO / BrokerInterface 구현)** 는 v0.11+
> 에도 Future Backlog 유지. 별도 보안·컴플라이언스·자본 한도 사이클 선행 없이는
> 진입 불가.

---

## 7. 누적 태그

| 태그 | Phase | 내용 |
|---|---|---|
| `v0.10-provider-runtime` | A (보조) | settings 7종 + monitor module 첫 commit (Phase A 작업 분할) |
| `v0.10-provider-resilience` | A | `ProviderHealthMonitor` + `call_with_resilience()` + 31 tests |
| `v0.10-dart-provider` | B | DartFundamental/Earnings/Disclosure skeleton + parser/mapper + body strip + crtfc_key 마스킹 + 49 tests |
| `v0.10-rss-provider` | C | RssNewsProvider (RSS 2.0 + Atom) + dedup + URL query secret 마스킹 + 33 tests + stdlib only |
| `v0.10-health-api` | D | GET /api/health/providers + ProviderHealthPanel + 17 backend / 7 vitest / 1 e2e tests |
| `v0.10-final` | E | 마감 문서 + 4 게이트 최종 재확인 |

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
`v0.9-watchlist-api` → `v0.9-frontend` → `v0.9-final` →
`v0.10-provider-runtime` → `v0.10-provider-resilience` → `v0.10-dart-provider` →
`v0.10-rss-provider` → `v0.10-health-api` → **`v0.10-final`**.
