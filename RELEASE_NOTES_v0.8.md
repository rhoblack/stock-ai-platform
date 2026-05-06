# Release Notes — v0.8 User & Migration Foundation

마감 일자: **2026-05-06**
마감 태그: `v0.8-frontend-watchlist` (Phase D 누적) → `v0.8-final` (Phase E)
기준선: `v0.7-final` (HEAD `1f5b01f`)

---

## 1. 사이클 개요

v0.1 부터 일관 유지된 **read-only 정책의 첫 변경 cycle**. 27 테이블 + 누적
ALTER 5건 시점에 **Alembic baseline 도입** 으로 마이그레이션 기반을 잡고, 단일
사용자 인증 (`AUTH_ENABLED` 토글 + JWT + scrypt) + **Watchlist 도메인 POST/DELETE**
(첫 write 라우터) + Watchlist / Login 프런트 (11번째 화면) 를 추가했다.

자동매매 / 실주문 / Broker / 실 외부 API / LLM 은 **여전히 0건**. Watchlist 와
인증에 한정된 POST 첫 도입이다.

---

## 2. Phase 별 산출물

### Phase A — Alembic Baseline (`v0.8-alembic-baseline`)

- `alembic.ini` + `alembic/env.py` + `alembic/script.py.mako` 신규
- `alembic/versions/0001_baseline_v0_7.py` — 27 테이블 baseline
  (`op.create_table()` 27건 + 인덱스 / FK / Unique + downgrade 27건 역순)
- `scripts/migrate.py` — thin alembic wrapper (current / history / upgrade /
  downgrade / stamp / offline-sql)
- `tests/integration/test_alembic_migration.py` 신규 — **16 케이스**
  (upgrade head / spot-check 9 테이블 / compare_metadata 0건 / stamp / downgrade base / offline-sql)
- `pyproject.toml` — `alembic>=1.13,<2.0` 추가
- `.github/workflows/ci.yml` — `alembic upgrade head` smoke step 추가
- `INTEGRATION_RUNBOOK.md` §17 신규 (8 sub-section)
- `DB_SCHEMA.md` 상단 "v0.8 부터 Alembic 으로 관리" 명시
- **게이트: backend pytest 682 → 698 (+16)**

### Phase B — 단일 사용자 인증 (`v0.8-auth-foundation`)

- `app/db/models.py` — `User` (28번째, scrypt hash + is_admin) + `LoginAuditLog` (29번째, source_ip_hash SHA256)
- `app/auth/security.py` — `PasswordHasher` (scrypt) + `JwtIssuer` (HS256) + `hash_for_audit` + `AuthService` + `validate_auth_settings`
- `app/auth/dependencies.py` — `get_current_user` + `require_auth` + `AUTH_ENABLED=false` dev fallback
- `app/api/auth_routes.py` — `POST /api/auth/login` (첫 POST) + `POST /api/auth/logout` + `GET /api/auth/me`
- `scripts/create_admin.py` — argparse CLI (평문·hash 출력 0건)
- `alembic/versions/0002_auth_foundation.py` — users + login_audit_logs
- `pyproject.toml` — `PyJWT>=2.8,<3.0` 추가 (stdlib scrypt 채택으로 bcrypt 미추가)
- 테스트 56건 신규 — unit 26 (`test_auth_security.py`) + repo 15 (`test_auth_repositories.py`) + API 14 (`test_auth_routes.py`) + CLI 5 (`test_create_admin_cli.py`)
- `API_SPEC.md` §17 신규, `DB_SCHEMA.md` §28/§29 신규, `INTEGRATION_RUNBOOK.md` §18 신규
- **게이트: backend pytest 698 → 760 (+62)**

### Phase C — Watchlist DB / API (`v0.8-watchlist-api`)

- `app/db/models.py` — `Watchlist` (30번째, Unique(user_id, name)) + `WatchlistItem` (31번째, Unique(watchlist_id, symbol) + cascade delete)
- `app/data/repositories/watchlists.py` — `WatchlistRepository` (create / list_by_user / get_or_create_default / delete + ownership-scoped 조회 + 단일 default invariant)
- `app/data/repositories/watchlist_items.py` — `WatchlistItemRepository` (add / remove / memo update + normalize_symbol + memo ≤500 + broker/account/quantity/order_* 컬럼 0건 가드)
- `app/api/watchlist_routes.py` — 5 라우터 (`GET /api/watchlists` + `GET /api/watchlists/{id}` + `POST /api/watchlists` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`). 모두 `require_auth` 가드 + cross-user 404 + spoofing 가드 (request body user_id 무시)
- `alembic/versions/0003_watchlist.py` — watchlists + watchlist_items
- 테스트 46건 신규 — repo 27 (`test_watchlist_repositories.py`) + API 19 (`test_watchlist_routes.py`)
- `API_SPEC.md` §18 신규, `DB_SCHEMA.md` §30/§31 신규, `INTEGRATION_RUNBOOK.md` §19 신규
- **게이트: backend pytest 760 → 808 (+48)**

### Phase D — Watchlist 프런트 + Today/StockDetail 통합 (`v0.8-frontend-watchlist`)

- `frontend/src/api/client.ts` — `setAuthToken` / `apiPost` / `apiDelete` + Authorization 헤더 자동 첨부
- `frontend/src/api/auth.ts` + `frontend/src/api/watchlists.ts` 신규
- `frontend/src/store/auth.tsx` — `AuthProvider` (getMe 자동 호출, AUTH_ENABLED=false 즉시 인증, token 절대 렌더링 0건)
- `frontend/src/hooks/useWatchlists.ts` — useMutation 첫 도입 (add/remove/create + onSuccess invalidate)
- `frontend/src/pages/Login/index.tsx` — AUTH_ENABLED=false 자동 redirect + 매 시도 후 password clear + access_token 렌더링 0건
- `frontend/src/pages/Watchlist/index.tsx` — 11번째 화면 (WatchlistListPanel + CreateWatchlistPanel + WatchlistDetailPanel + AddItemForm 404/409/422/401 처리)
- `frontend/src/pages/StockDetail/index.tsx` — `FavoriteButton` 추가 (관심목록 없으면 자동 생성, data-active / aria-pressed 토글)
- `frontend/src/pages/TodayReport/index.tsx` — `WatchlistCard` 추가 (기본 목록 + empty placeholder 링크)
- `frontend/src/components/layout/Sidebar.tsx` — `관심종목` 메뉴 추가 (10 → 11)
- MSW 핸들러 확장 (auth + watchlist CRUD) + `renderWithProviders` AuthProvider wrapper
- 테스트 29건 신규 — Login.test 8 + Watchlist.test 12 + StockDetail.test +6 + TodayReport.test +3
- e2e 5건 신규 — Login auto-redirect / Watchlist empty / Today WatchlistCard / StockDetail FavoriteButton / Watchlist forbidden fields
- **게이트: vitest 84 → 113 (+29) / e2e 14 → 19 (+5)**

### Phase E — 문서 / 마감 (`v0.8-final`)

- 본 `RELEASE_NOTES_v0.8.md` 신규
- `README.md` v0.8 마감 배너 + 누적 태그 + §1 v0.8 기능 + §6 누적 표 갱신
- `PROJECT_STATUS.md` §0 v0.8 마감 선언
- `TASKS.md` Phase E [x] + v0.9 Backlog
- `ROADMAP.md` v0.8 ✅ 마감
- `ARCHITECTURE.md` / `TESTING.md` 헤더 v0.8 기준 갱신

---

## 3. 최종 회귀 게이트 (v0.8 마감 시점)

| 게이트 | 결과 | 누적 경로 |
|---|---|---|
| backend pytest | **808 passed (1 deselected)** | 682 → 698 (A) → 760 (B) → 808 (C) → 808 (D 변경 없음) |
| frontend vitest | **113 passed** (16 파일) | 84 → 113 (D) |
| Playwright e2e | **19 passed** (chromium) | 14 → 19 (D) |
| frontend build | **그린** (`tsc --noEmit && vite build`) | — |

---

## 4. 안전 정책 (v0.8 사이클 전체)

### 4.1 인증 정책

- `AUTH_ENABLED=false` (기본) → 기존 read-only API 전부 OPEN, dev fallback user 사용. CI 환경 호환
- `AUTH_ENABLED=true` → 기존 GET 라우터 여전히 OPEN (인증 불필요), Watchlist / Auth 라우터만 Bearer 토글
- JWT HS256, `JWT_SECRET` 환경변수 필수 (AUTH_ENABLED=true). 기동 시 `validate_auth_settings` 가 미설정 시 startup 거부
- 단일 admin user — 다중 사용자 / OAuth / SSO / RBAC 0건
- Refresh token / token revocation list 0건 — 24h TTL + 재로그인

### 4.2 데이터 보안

- **평문 IP 미저장** — `LoginAuditLog.source_ip_hash` 는 SHA256 만
- **평문 password 미저장** — scrypt cost-12 hash 만
- **password_hash / jwt_secret / scrypt$ 패턴** API 응답 / 프런트 0건 (회귀 단언)
- **`broker` / `account` / `quantity` / `order_*` / `source_file_path`** WatchlistItem ORM 컬럼 + API 응답 + 프런트 0건 (repo 단언 + e2e 단언)

### 4.3 API 범위 제한

- **POST 라우터 = 5건만**: `POST /api/auth/login` + `POST /api/auth/logout` + `GET /api/auth/me` + `POST /api/watchlists` + `POST /api/watchlists/{id}/items` + `DELETE /api/watchlists/{id}/items/{symbol}`. 그 외 도메인 POST/PUT/DELETE 0건
- **Cross-user 404 격리**: `_load_owned_watchlist` → 타 사용자 목록 조회 시 404 (정보 노출 방지)
- **Spoofing 가드**: request body 의 `user_id` 자동 무시 — 라우터가 token 의 user_id 만 사용

### 4.4 외부 호출 / 자동매매 / 산식

- 실 KIS / DART / RSS / Telegram API 자동 호출 0건
- 자동매매 / 실주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 0건
- `BrokerInterface` ABC placeholder 유지 — 구현체 0건
- ScoringEngine / RecommendationEngine / HoldingCheckEngine 본 weight 변경 0건
- BacktestEngine / CostModel / regime_split 변경 0건
- Watchlist FavoriteButton mutation 은 즐겨찾기 추가/삭제만 — 분석 산식 영향 0건

---

## 5. 알려진 한계 / 제외 범위

- **Watchlist 목록 이름 변경 (PUT) / 목록 삭제 (DELETE)** 미구현 — v0.9 후보
- **Watchlist 가격 알림 / target return alert** 0건 — 알림 시스템 변경 = 별도 사이클
- **다중 사용자 / OAuth / SSO** 0건 — 단일 admin user 만
- **Refresh token / WebSocket / SSE** 0건
- **모바일 / 태블릿 레이아웃** 0건 — PC 1280px+ 우선
- **실 DART / 실 RSS provider** 0건 — ABC + Fake 유지 (라이선스 검토 필요)
- **백테스트 trigger UI** 0건 — `scripts/run_backtest.py --commit` 운영자 수동만
- **`CostModel` 실 broker fee schedule** 0건 — `constant-v1` (0.33%) placeholder 유지
- **Alembic downgrade 운영 DB rollback** — 운영자 수동만. `downgrade` CLI 는 구현되었으나 자동 실행 없음

---

## 6. v0.9 후보 (우선순위 순)

1. **Watchlist 관리 고도화** — 목록 이름 변경 (PUT) / 목록 삭제 (DELETE) / 관심 종목 메모 수정
2. **사용자 설정** — 관심 시장 / 기본 필터 / 알림 선호도 (인증 후 자연 확장)
3. **운영 모니터링** — Sentry / Prometheus / Grafana (외부 노출 시점에 함께)
4. **CSRF / Content-Security-Policy 헤더** — 외부 노출 시 강화
5. **rate limit (`slowapi`)** — POST 라우터 + 인증 운영 검증 후
6. **실 DART / 실 RSS provider** — v0.5/v0.6 ABC 위에 DartProvider / RssProvider 추가 (라이선스 검토 동반)
7. **백테스트 고도화** — walk-forward / 다중 전략 포트폴리오 / 종목별 stamp duty
8. **LLM 보강** — News sentiment / 재무 분석 / 자동 전략 생성

---

## 7. 운영 가이드

### 7.1 신규 환경 초기화 (Alembic)

```powershell
# 새 DB — alembic upgrade head 로 31 테이블 한 번에 생성
.\.venv\Scripts\python.exe -m alembic upgrade head

# 기존 운영 DB (v0.7 이후) — stamp 후 이후 revision 적용
.\.venv\Scripts\python.exe -m alembic stamp 0001_baseline_v0_7
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 7.2 Auth 활성화

```dotenv
AUTH_ENABLED=true
JWT_SECRET=<64+ random chars>
```

```powershell
# 관리자 계정 생성 (최초 1회, 평문 password 출력 없음)
.\.venv\Scripts\python.exe -m scripts.create_admin --username admin
```

### 7.3 Watchlist smoke test

```powershell
# 1) login
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/auth/login `
  -ContentType application/json -Body '{"username":"admin","password":"<pw>"}'

# 2) list (empty)
Invoke-RestMethod -Method GET -Uri http://localhost:8000/api/watchlists `
  -Headers @{Authorization="Bearer <token>"}

# 3) create
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/watchlists `
  -ContentType application/json -Headers @{Authorization="Bearer <token>"} `
  -Body '{"name":"관심종목"}'
```

---

## 8. 누적 인수 태그 (v0.1 ~ v0.8)

```
v0.1-backend-final
v0.1-backend-kis-paper-verified
v0.2-frontend-final
v0.3-phase-a-ci
v0.3-backend-analysis
v0.3-frontend-calendar
v0.3-frontend-stock-chart
v0.3-final
v0.4-backend-reports
v0.4-import-pipeline
v0.4-report-score
v0.4-frontend-reports
v0.4-final
v0.5-news-collector
v0.5-disclosure-pipeline
v0.5-news-score
v0.5-frontend-themes
v0.5-final
v0.6-fundamental-data-layer
v0.6-earnings-event-pipeline
v0.6-fundamental-score
v0.6-frontend-fundamentals
v0.6-final
v0.7-strategy-interface
v0.7-backtest-engine
v0.7-backtest-cost-regime
v0.7-frontend-backtest
v0.7-final
v0.8-alembic-baseline
v0.8-auth-foundation
v0.8-watchlist-api
v0.8-frontend-watchlist
v0.8-final  ← 현재
```

이전 사이클 마감 사유:
[`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) (296 passed) /
[`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) (296/36/6) /
[`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) (319/59/8) /
[`RELEASE_NOTES_v0.4.md`](./RELEASE_NOTES_v0.4.md) (382/60/9) /
[`RELEASE_NOTES_v0.5.md`](./RELEASE_NOTES_v0.5.md) (481/68/11) /
[`RELEASE_NOTES_v0.6.md`](./RELEASE_NOTES_v0.6.md) (558/77/13) /
[`RELEASE_NOTES_v0.7.md`](./RELEASE_NOTES_v0.7.md) (682/84/14).
