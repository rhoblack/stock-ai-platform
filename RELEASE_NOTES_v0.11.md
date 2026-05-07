# Release Notes — v0.11 Real Provider Transport & Observability

마감 일자: **2026-05-07**
마감 태그: `v0.11-final`
기준선: `v0.10-final` (HEAD `c56faf9`)

---

## 1. 사이클 개요

v0.10 의 transport 주입형 DART / RSS skeleton 위에 **실 httpx 전송** 과
**provider observability 인프라** 를 쌓은 사이클. 모든 provider 는 default OFF
유지 — 운영자가 `.env` 에서 명시 enable + 라이선스 검토(사람) 선행 시에만 실
HTTP 가 발생한다. ScoringEngine 본 weight 변경 0건, 자동매매 / 실주문 / Broker
코드 0건, Alembic 새 revision 0건.

- **DART HTTP Transport** (Phase A) — `HttpxDartTransport` + factory 자동 주입
  + 27 respx mock 테스트
- **RSS HTTP Transport** (Phase B) — `HttpxRssTransport` + 19 respx mock
  테스트 + `SensitiveQueryStringFilter` 를 `app/config/logging.py` 로 추출
  (DART/RSS 공유)
- **Provider Observability + Prometheus** (Phase C) — bounded ring buffer +
  `Summary24h` + optional `prometheus-client` `/metrics` (default OFF)
- **Provider Health API/UI 확장** (Phase D) — `/api/health/providers` 에 24h
  aggregates + `recent_failures[5]` 추가 + Settings 패널에 `SuccessRateBar` /
  `RecentFailuresList` UI

자동매매 / 실주문 / Broker 구현 / LLM / Telegram 자동 발송 은 **모두 0건** 유지.
provider toggle / reset mutation API 0건.

---

## 2. Phase 별 산출물

### Phase A — DART HTTP Transport (`v0.11-dart-transport`)

**목표**: v0.10 의 transport 주입형 `DartFundamental/Earnings/Disclosure` 위에 실
httpx 전송 구현. `DART_ENABLED=false` 기본 유지.

| 파일 | 내용 |
|---|---|
| `app/data/dart_provider.py` | `HttpxDartTransport` (lazy httpx import + close/__del__) + `_default_transport` helper + `create_dart_providers` 자동 주입 (DART_ENABLED=true + DART_API_KEY 검증 후) |
| `app/data/dart_provider.py` 응답 매핑 | HTTP 200+`status="000"`→ok / `010..101`→CLIENT_ERROR / `800/900`→SERVER_ERROR / 비-JSON→UNKNOWN / 4xx→CLIENT / 5xx→SERVER / TimeoutException→TIMEOUT / HTTPError→UNKNOWN (예외 클래스명만 message) |
| `app/data/dart_provider.py` secret 마스킹 | `_SensitiveQueryStringFilter` + `_install_sensitive_qs_filter` (Phase B 에서 `app/config/logging.py` 로 추출) — httpx INFO 로그의 `crtfc_key=...` 자동 마스킹 |
| `pyproject.toml` | `respx>=0.21,<0.22` (dev only, BSD-3) |
| `tests/data/test_dart_http_transport.py` | 27 신규 케이스 — HTTP/DART 매핑 10 + factory 3 + resilience 3 + secret 3 + zero-network 1 + status code 변형 7 |

게이트: backend pytest **1045 → 1072 passed (+27)**, 회귀 0건.

---

### Phase B — RSS HTTP Transport (`v0.11-rss-transport`)

**목표**: v0.10 의 transport 주입형 `RssNewsProvider` 위에 실 httpx 전송 구현.
`RSS_NEWS_ENABLED=false` 기본 유지. Phase A 의 `_SensitiveQueryStringFilter` 를
`app/config/logging.py` 로 추출하여 DART/RSS 공유.

| 파일 | 내용 |
|---|---|
| `app/config/logging.py` | `SensitiveQueryStringFilter` + `install_sensitive_qs_filter` 추가 (Phase A 의 dart_provider 내부 헬퍼를 promote) — DART/RSS 양쪽 transport 가 idempotent 설치 |
| `app/data/dart_provider.py` | 로컬 filter 제거 + 공통 `install_sensitive_qs_filter` import — 동작 100% 호환, Phase A 49+27 케이스 회귀 0건 |
| `app/data/rss_provider.py` | `HttpxRssTransport` (lazy httpx import + `follow_redirects=True` + close/__del__) + `_default_transport` helper + `create_rss_provider` 자동 주입 |
| `app/data/rss_provider.py` 응답 매핑 | HTTP 200→`ok(response.content)` (raw bytes; parser 가 인코딩) / 4xx→CLIENT / 5xx→SERVER / TimeoutException→TIMEOUT / HTTPError→UNKNOWN (예외 클래스명만 message) |
| `tests/data/test_rss_http_transport.py` | 19 신규 케이스 — HTTP/parser 매핑 8 + factory 4 + resilience 3 + secret 3 (PRIVATE-FEED-SECRET-XYZ canary) + zero-network 1 |

게이트: backend pytest **1072 → 1091 passed (+19)**, 회귀 0건.
신규 pip 의존성 0건 (Phase A 의 respx 그대로 사용).

---

### Phase C — Provider Observability + Prometheus (`v0.11-observability`)

**목표**: v0.10 의 `ProviderHealthMonitor` 위에 bounded ring buffer + 24h
summary + optional Prometheus exporter 추가. **Alembic revision 0건** —
모든 observability state 가 in-memory bounded.

| 파일 | 내용 |
|---|---|
| `app/data/provider_health_monitor.py` 확장 | `CallRecord` / `FailureRecord` / `Summary24h` frozen dataclass (timestamp + enum + ints만, message 필드 부재). `ProviderStats.recent_calls` (deque maxlen=200) + `recent_failures` (deque maxlen=50). `summary_24h(now=None)` 메소드. `record_result` 가 ring buffer append + lazy `_emit_prometheus` 호출 (try/except 격리). `reset()` 가 ring buffer 도 clear |
| `app/monitoring/prometheus.py` (신규) | `PrometheusMetrics` bundle (4 Counter + 1 Gauge + 1 Histogram). `set_metrics` / `get_metrics` / `init_default_metrics` / `record_call` / `mark_unregistered` / `render_metrics`. circuit_state 정수 인코딩 (CLOSED=0/OPEN=1/HALF_OPEN=2/UNREGISTERED=3). isolated `CollectorRegistry` per test |
| `app/api/metrics_routes.py` (신규) | `GET /metrics` — `PROMETHEUS_ENABLED=false` 시 404, true 시 200+text/plain. POST/PUT/DELETE 모두 405. `include_in_schema=False` |
| `app/config/settings.py` | `prometheus_enabled=False` 기본 + `prometheus_path="/metrics"` 추가 |
| `app/main.py` | startup 시 `init_default_metrics(settings)` 호출 (idempotent + Prometheus disabled 시 no-op) + `metrics_router` 마운트 |
| `pyproject.toml` | `prometheus-client>=0.19,<1.0` (Apache 2.0, pure Python) production 의존성 추가 |
| `tests/data/test_provider_observability.py` | 21 신규 케이스 — ring buffer + Summary24h 7 + Prometheus bundle 7 + GET /metrics 5 + zero-network 가드 + Prometheus 예외 swallow |

게이트: backend pytest **1091 → 1112 passed (+21)**, 회귀 0건.

---

### Phase D — Provider Health API/UI 확장 (`v0.11-health-extended`)

**목표**: Phase C 의 24h aggregates + recent_failures 를 `/api/health/providers`
와 Settings 패널에 read-only 노출. provider toggle / reset mutation API 0건.

| 파일 | 내용 |
|---|---|
| `app/data/provider_health_monitor.py` | `get_summary_24h(name)` / `get_recent_failures(name, limit=5)` 공개 accessor 추가 — route 가 `_providers` private 직접 참조 제거 |
| `app/api/health_routes.py` | `RecentFailureSummary` schema (`{timestamp, error_kind}` 만; message 필드 부재) + `ProviderHealthItem` 6 필드 추가 (`call_count_24h` / `success_count_24h` / `failure_count_24h` / `success_rate_24h: float?` / `avg_attempts_24h: float?` / `recent_failures: list[5]`) + `_serialise_recent_failures` (newest-first cap) |
| `frontend/src/api/types.ts` | `RecentFailureSummary` 신규 + `ProviderHealthItem` 6 필드 sync |
| `frontend/src/components/common/ProviderHealthPanel.tsx` | `SuccessRateBar` (≥99% emerald / ≥95% amber / <95% red / null slate) + `avg_attempts` 셀 + `RecentFailuresList` + `ProviderRecentFailuresSection` (실패 1건+ provider 만 카드 노출). 패널 내 button/form/switch/textbox 0건 |
| `frontend/src/tests/mswServer.ts` + `frontend/e2e/fixtures/apiMocks.ts` | 6 신규 필드 sync; e2e fixture 는 KIS 50 calls / 1 TIMEOUT failure 시연 |
| `tests/integration/test_health_providers.py` | +7 케이스 — 빈 상태 defaults / 24h 집계 / cap 5 + newest-first / message 필드 부재 / 16 forbidden paranoid scan / zero-window 안전 / experimental provider |
| `frontend/src/tests/ProviderHealthPanel.test.tsx` | +5 케이스 — success_rate / avg_attempts cell / recent_failures newest-first / empty placeholder / hypothetical secret 미렌더링 / read-only |
| `frontend/e2e/dashboard.spec.ts` | +1 케이스 — `/settings` 패널의 Phase D cell visibility + 16 forbidden secret 0건 |

게이트: backend pytest **1112 → 1119 passed (+7)** / vitest **153 → 158 passed (+5)** /
e2e **20 → 21 passed (+1)** / build 그린. 회귀 0건.

---

### Phase E — Closure (`v0.11-final`)

본 release notes 작성 + README / PROJECT_STATUS / ROADMAP / TASKS / TESTING /
ARCHITECTURE / API_SPEC / INTEGRATION_RUNBOOK v0.11-final 갱신 + 4 게이트 최종
재확인.

---

## 3. 최종 테스트 게이트 (v0.11 마감 시점)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend pytest | `python -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults` | **1119 passed, 1 deselected** (test_settings_defaults 로컬 .env 충돌 — Phase A 부터 baseline 인계) |
| frontend vitest | `cd frontend && npm run test -- --run` | **158 passed** (20 파일) |
| frontend build | `cd frontend && npm run build` | ✓ built (3.40s) |
| Playwright e2e | `cd frontend && npx playwright test` | **21 passed** (chromium) |

회귀 0건. 자동매매 / 실주문 / 실 KIS / 실 DART / 실 RSS / Telegram 실제 호출 0건
(`respx` transport-layer mock + `httpx.Client` monkeypatch 가드). 신규 Alembic
revision 0건 (head 그대로 `0004_user_preferences`).

v0.10 baseline 대비: pytest **+74** (1045→1119) / vitest **+5** (153→158) /
e2e **+1** (20→21) / 신규 의존성 **+2** (`respx`, `prometheus-client`).

---

## 4. 안전 정책

### 4.1 자동매매 / 실주문 완전 미포함 (v0.1~v0.11 누적)

- `BrokerInterface` — ABC placeholder 만 유지. 구현체 0건.
- `FULL_AUTO` / `APPROVAL` / `SMALL_AUTO` / `MockBroker` / `ReplayBroker` 코드 일체 없음.
- `WatchlistItem` ORM 에 broker / account / quantity / order_price / order_type / side 컬럼 0건.
- `StrategySignal.action` 은 분석 신호 전용 — 실제 주문 전송 경로 없음.

### 4.2 외부 API 자동 호출 0건 — provider default OFF 유지

- DART OpenAPI — `DART_ENABLED=False` 기본. true 일 때만 `HttpxDartTransport` 가
  자동 주입되며, 모든 테스트는 `respx` 로 transport layer 인터셉트
- RSS / News — `RSS_NEWS_ENABLED=False` 기본 + `RSS_FEED_URLS` 미설정 시 즉시
  `RssNotConfiguredError`. Atom/RSS 2.0 모두 운영자 approved URL 만
- Prometheus exporter — `PROMETHEUS_ENABLED=False` 기본. true 일 때만 `/metrics`
  → 200+text/plain; false 시 404
- KIS — `KIS_USE_PAPER=true` 기본 (모의투자). 실 주문 transport 0건
- Telegram — `TELEGRAM_ENABLED=false` 기본. 실 발송 0건
- 통합 검증: `tests/data/test_dart_http_transport.py` /
  `tests/data/test_rss_http_transport.py` / `tests/data/test_provider_observability.py`
  / `tests/integration/test_health_providers.py` 모두 `httpx.Client` 미생성
  단언 (monkeypatch `AssertionError` 가드)

### 4.3 본문 / 비밀값 미저장 / 미노출 — 5 layer

1. **DART/RSS parser** — forbidden body field (`body / content / full_text /
   paragraph / raw_text / html_body / 본문 / 원문 / 전문` 등 13종) 사전 strip
2. **Transport `error_message`** — `httpx.HTTPError.__str__` 가 URL 전체 (key
   포함) 를 carry 해도 transport 는 예외 클래스명만 (`type(exc).__name__`)
   기록 → `result.error_message` 에 평문 0건
3. **`SensitiveQueryStringFilter`** (Phase A 신규, Phase B 에서 공유로 추출) —
   httpx INFO 로그의 `?crtfc_key=ABC` / `?api_key=XYZ` / `?token=...` 등을
   `=***` 로 마스킹. DART + RSS 양쪽 transport 가 idempotent 설치
4. **Provider Observability schema** — `CallRecord` / `FailureRecord` /
   `RecentFailureSummary` 모두 `error_message` 필드 자체 부재. ring buffer 도,
   `/api/health/providers` 응답도, `/metrics` payload 도 transport 디테일
   carry 불가
5. **`/api/health/providers` paranoid scan** — 16종 forbidden substring
   (`crtfc_key` / `dart_api_key` / `DART_API_KEY` / `rss_feed_urls` /
   `kis_app_secret` / `last_error_message` / `?api_key=` / `access_token` /
   `password` / `LEAKDART` / `LEAKRSS` / `LEAKMEXYZ` 등) backend + e2e 단언

### 4.4 Provider Health UI 는 read-only

- `/api/health/providers` 는 GET only (POST/PUT/DELETE 모두 405).
- `/metrics` 도 GET only (POST/PUT/DELETE 모두 405).
- Provider Health 패널 내부에 button / checkbox / switch / form / textbox **0건**
  (Phase D 추가 후에도 vitest + e2e 단언 유지).
- enable/disable 토글 / breaker reset / failure clear 등 mutation API 0건 —
  운영자가 `.env` 수정 + 백엔드 재시작 으로만 변경.

### 4.5 ScoringEngine / HoldingCheckEngine 본 weight 변경 0건

- v0.1 ~ v0.11 일관 — recommendation 산식 (technical 35% / news 25% /
  supply 15% / fundamental 15% / ai 10%) + holding 산식 (technical 35% /
  news 20% / earnings 20% / ai 15% / profit_management 10%) 그대로.
- DART/RSS 실 transport 도입했지만 ScoringEngine 신규 weight 0건 — DART/RSS
  score 반영은 v0.12+ 후보.

### 4.6 Alembic 새 revision 0건

- v0.11 cycle 동안 신규 ORM / table / 컬럼 변경 0건.
- Alembic head 그대로 `0004_user_preferences` (v0.10 마감 상태와 동일).
- Provider observability ring buffer / Prometheus collector 모두 in-memory
  bounded — 영속화 0건 (서버 재시작 시 초기화).

---

## 5. 알려진 한계

| 항목 | 상태 |
|---|---|
| DART/RSS provider score 반영 미완 | 실 transport 는 도입됐지만 `RealNewsScoreProducer` (v0.5) / `RealFundamentalScoreProducer` (v0.6) 가 아직 DART/RSS 데이터를 흡수하지 않음. ScoringEngine weight 보강은 v0.12+ — 누적 데이터 검증 후 |
| Grafana dashboard 미동봉 | Phase C 의 Prometheus exporter 까지만, Grafana 자체는 외부 인프라. dashboard JSON 은 v0.12+ 후보 |
| ProviderHealthMonitor 영속화 미지원 | bounded ring buffer (200 calls / 50 failures cap) only — 서버 재시작 시 카운터 / 회로 상태 / 24h aggregates 모두 초기화. Prometheus exporter 가 외부 시계열 DB 연결 가교 역할 |
| Provider toggle GUI 미구현 | enable/disable / breaker reset 은 `.env` + 재시작만. operator 가 GUI 에서 toggle 하는 것은 v0.12+ 인증 + 보안 검토 후 |
| `GET /api/health/jobs` 미추가 | Phase D 범위에서 보류. 기존 `GET /api/jobs` 가 동일 정보 제공. 분리 필요 시 v0.12+ |
| RSS feed URL 정적 등록 | `RSS_FEED_URLS` env 콤마 구분 — 운영자가 직접 검토한 URL 만. 자동 discovery / 동적 추가 0건 |
| 자동매매 미진입 | `BrokerInterface` placeholder 유지. 별도 보안 / 컴플라이언스 / 자본 한도 사이클 선행 필수 |
| LLM 보강 미진입 | News sentiment / 재무 분석 / 자동 전략 모두 룰 기반 — LLM 보강은 v0.12+ |
| WebSocket / SSE 미구현 | Provider Health 패널은 30s staleTime + 60s refetchInterval polling. 실시간 갱신은 v0.12+ |
| KIS 실 주문 transport 미진입 | KIS read-only paper transport 만, 실 주문은 Future Backlog (보안·컴플라이언스 사이클 선행) |

---

## 6. v0.12 후보

| 후보 | 사유 |
|---|---|
| DART/RSS score 반영 | v0.5 `RealNewsScoreProducer` / v0.6 `RealFundamentalScoreProducer` 위에 v0.11 의 실 transport 결과 연결. 룰 기반 검증 후 ScoringEngine weight 보강 |
| 백테스트 고도화 | walk-forward 검증 / 다중 전략 포트폴리오 / 실 broker fee schedule. recommendation_results 3~6개월 누적 후 |
| Grafana dashboard 동봉 | v0.11 Prometheus exporter 위에 시각화 layer (Grafana JSON 동봉) |
| 인증 고도화 | refresh token / 다중 사용자 / OAuth / SSO / RBAC. 단일 사용자 운영 검증 후 |
| CSP / rate limit 고도화 | v0.9 의 rate limit 기본값을 실 트래픽 기준 튜닝 + CSP 정책 (Vite devserver / nginx 충돌 검토 후) |
| LLM 보강 | News sentiment / 재무 분석 / 어닝 surprise 보강 / 자동 전략 생성 — 룰 기반 검증 + 데이터 누적 후 |
| WebSocket / SSE | Provider Health / Jobs / 백테스트 진행 실시간 갱신 (현재 polling) |
| `GET /api/health/jobs` 분리 + Provider toggle GUI | 운영자가 GUI 로 provider 상태 / job 진행 상황 모니터링 (인증 + 보안 검토 동반) |
| ProviderHealthMonitor 영속화 | DB / Redis 등에 ring buffer 저장 — 재시작 후 history 보존 |
| Watchlist 가격 알림 / target return alert | 알림 시스템 = 별도 cycle (Telegram 실 발송 + 트리거 디자인 동반) |
| Paper / Simulation Trading 준비 | MockBroker / ReplayBroker / SimulationBroker skeleton — 보안 / 컴플라이언스 사이클 선행 |

> **자동매매 / 실주문 (FULL_AUTO / SMALL_AUTO / BrokerInterface 구현)** 는 v0.12+
> 에도 Future Backlog 유지. 별도 보안·컴플라이언스·자본 한도 사이클 선행 없이는
> 진입 불가.

---

## 7. 누적 태그

| 태그 | Phase | 내용 |
|---|---|---|
| `v0.11-dart-transport` | A | `HttpxDartTransport` (lazy httpx import) + factory 자동 주입 + `_SensitiveQueryStringFilter` (httpx URL secret 마스킹) + 27 respx 테스트 |
| `v0.11-rss-transport` | B | `HttpxRssTransport` (follow_redirects=True) + factory 자동 주입 + `SensitiveQueryStringFilter` 를 `app/config/logging.py` 로 추출 (DART/RSS 공유) + 19 respx 테스트 |
| `v0.11-observability` | C | `ProviderHealthMonitor` ring buffer (200 calls / 50 failures) + `Summary24h` + `prometheus-client` Counter+Gauge+Histogram + `GET /metrics` (default 404) + 21 테스트 |
| `v0.11-health-extended` | D | `/api/health/providers` 6 신규 필드 + `RecentFailureSummary` schema + Settings `SuccessRateBar` / `RecentFailuresList` + 13 테스트 (backend 7 + vitest 5 + e2e 1) |
| `v0.11-final` | E | 마감 문서 + 4 게이트 최종 재확인 |

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
`v0.10-rss-provider` → `v0.10-health-api` → `v0.10-final` →
`v0.11-dart-transport` → `v0.11-rss-transport` → `v0.11-observability` →
`v0.11-health-extended` → **`v0.11-final`**.
