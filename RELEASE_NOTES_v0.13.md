# RELEASE_NOTES_v0.13.md — Provider Score Policy & Validation Report

> 마감 태그: `v0.13-final`  
> 마감 일자: **2026-05-08 (Asia/Seoul)**  
> 기준 태그: `v0.12-final` → 마감 태그: `v0.13-final`  
> 세부 계획: [`PLANS.md`](./PLANS.md) `PLAN-0013`

---

## 1. 사이클 요약

v0.13 은 **Provider Score Policy 승수 엔진 + Score Delta 기록 + Validation Report
read-only API/UI** 를 완성한 사이클이다.

| Phase | 내용 | 태그 | 게이트 |
|---|---|---|---|
| A | ProviderScorePolicy 승수 엔진 (`PROVIDER_SCORE_POLICY_ENABLED=False` 기본) | `v0.13-provider-policy` | pytest **1194→1223 (+29)** |
| B | Score Delta in evidence_json (`score_before`/`score_after`/`delta`, Alembic 0건) | `v0.13-score-delta` | pytest **1223→1241 (+18)** |
| C | Validation Report read-only API (`GET /api/validation/report` + 3 세부 엔드포인트) | `v0.13-validation-api` | pytest **1241→1277 (+36)** |
| D | Validation Report 프런트 12번째 화면 (`/validation`, `ClipboardCheck` sidebar) | `v0.13-validation-ui` | vitest **165→175 (+10)** |
| E | 마감 문서 (본 파일 + README/PROJECT_STATUS/ROADMAP/TASKS/ARCHITECTURE/API_SPEC/INTEGRATION_RUNBOOK) | `v0.13-final` | **4 게이트 그린** |

---

## 2. 산출물 상세

### Phase A — ProviderScorePolicy 승수 엔진

- `app/scoring/provider_policy.py` 신규
  - `ProviderScorePolicy` — `apply(score, data_source)` 순수 함수
  - `DATA_SOURCE_RELIABILITY`: `PROVIDER=1.00` / `CSV=0.90` / `MANUAL=0.80` / `FAKE=bypass`
  - `_BYPASS_SOURCES = {"FAKE"}` — FAKE 소스는 기존 점수 그대로 (정책 OFF 시 동작 보존)
- `app/scoring/__init__.py` 신규 — `ProviderScorePolicy` / `DATA_SOURCE_RELIABILITY` export
- `app/config/settings.py` — `PROVIDER_SCORE_POLICY_ENABLED: bool = False` 추가
- 단위 테스트 28건 (`tests/unit/test_provider_policy.py`)
  - factor 매핑 / FAKE bypass / policy OFF bypass / 경계값 / 음수 / float·Decimal 입력 /
    ROUND_HALF_UP / 외부 호출 0건 단언 / **ScoringEngine weight 회귀 단언 2건**
- **ScoringEngine 본 weight 변경 0건** — technical 35% / news 25% / supply 15% /
  fundamental 15% / ai 10% 그대로

### Phase B — Score Delta in Evidence JSON

- `app/scoring/score_delta.py` 신규
  - `ScoreDeltaResult` dataclass — `score_before`, `score_after`, `delta`, `components: list[ComponentDelta]`
  - `ComponentDelta` — `component_name`, `before`, `after`, `delta`
  - `compute_score_delta(before_dict, after_dict, *, rounding)` — ROUND_HALF_UP 4dp
- `app/scoring/__init__.py` — `ScoreDeltaResult` / `ComponentDelta` / `compute_score_delta` export 추가
- `RecommendationEngine` / `HoldingCheckEngine` — `score_policy` 선택 파라미터 추가
  - None 이면 delta 미기록 (기존 동작 그대로)
  - `ProviderScorePolicy` 전달 시 `market_context_json["score_delta"]` 키에 기록
- `app/api/routes.py` — `_SCORE_DELTA_EVIDENCE_FIELDS` whitelist 추가 (raw JSON 미노출)
- `app/api/schemas.py` — `RecommendationItemSchema` / `HoldingCheckSchema` 에 `score_delta` 필드 추가
- **Alembic revision 0건** — 기존 `evidence_json` JSON 컬럼 재활용
- 단위 테스트 18건 (`tests/unit/test_score_delta.py`)

### Phase C — Validation Report Read-only API

- `app/api/validation_routes.py` 신규 (prefix `/api/validation`)
  - `GET /report` — 전체 요약 (run_count / signal_count / buy_count / win_rate_5d / avg_return_5d / score_delta 집계)
  - `GET /report/by-strategy` — 전략별 집계
  - `GET /report/by-regime` — 시장 국면별 집계
  - `GET /report/by-sector` — 섹터별 집계 (Stock LEFT JOIN)
  - **POST/PUT/PATCH/DELETE → 405 (모든 엔드포인트)**
- `app/api/schemas.py` — 8종 Pydantic 스키마 추가
  - `ScoreDeltaSummarySchema` / `ValidationReportSchema`
  - `ValidationStrategySummarySchema` / `ValidationStrategyResponse`
  - `ValidationRegimeSummarySchema` / `ValidationRegimeResponse`
  - `ValidationSectorSummarySchema` / `ValidationSectorResponse`
- `app/main.py` — `validation_router` 등록
- forbidden field guard — `evidence_json` raw / `source_file_path` / `notes` 미노출
- score_delta 집계: `backtest_results.evidence_json["score_delta"]` whitelist 읽기 — malformed 자동 skip
- 통합 테스트 36건 (`tests/integration/test_validation_report.py`)
  - happy/empty/malformed skip / data_source bucket / policy_enabled_count / delta sign count /
    forbidden field / **405×16** (4 endpoint × 4 method) / socket monkeypatch

### Phase D — Validation Report 프런트엔드 (12번째 화면)

- `frontend/src/api/validation.ts` 신규 — 4 fetch 함수
- `frontend/src/hooks/useValidationReport.ts` 신규 — 4 TanStack Query hooks (`staleTime: 60_000`)
- `frontend/src/pages/Validation/index.tsx` 신규 (12번째 화면 `/validation`)
  - `OverallReportCard` — run_count / signal_count / buy_count / win_rate_5d / avg_return_5d StatCell
  - `ScoreDeltaCard` — total_scored / policy_enabled_count / avg_delta / pos·neg·neutral + data_source chip
  - `StrategyTableSection` — cost_adjusted + max_drawdown (null → "—")
  - `RegimeTableSection` / `SectorTableSection`
  - 각 섹션 loading / error / empty 상태 완비
- `frontend/src/router.tsx` — `ValidationPage` React.lazy 코드 스플릿 + `/validation` route
- `frontend/src/components/layout/Sidebar.tsx` — `ClipboardCheck` 아이콘 + `검증 리포트` 메뉴 (12번째)
- `frontend/src/tests/mswServer.ts` — 4 validation GET 핸들러 (default empty)
- `frontend/src/tests/Validation.test.tsx` 신규 — **vitest 10건**
- `frontend/e2e/fixtures/apiMocks.ts` + `dashboard.spec.ts` — e2e 연동 (sidebar 11→12 menus)

### Phase E — 마감 문서

Backtest Export CLI (`scripts/export_backtest.py`) 는 이번 사이클에서 구현하지 않고
**v0.14+ 로 이연** 한다. 이유: 기능 코드 수정 없이 문서 마감 우선.

---

## 3. 안전 정책

- **실거래 자동매매 0건** — `BrokerInterface` 는 ABC placeholder 유지. v0.1~v0.13 일관
- **자동 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드 0건**
- **Validation Report 엔드포인트 전부 read-only** — POST/PUT/PATCH/DELETE → 405
- **evidence_json raw 미노출** — score_delta 집계 전용 whitelist 추출만
- **PROVIDER_SCORE_POLICY_ENABLED=False 기본** — 운영자가 `.env` 에 명시 설정 시에만 승수 적용
- **Alembic revision 0건** — score_delta 는 기존 `evidence_json` JSON 컬럼 재활용;
  Validation Report 는 기존 `backtest_runs` / `backtest_results` 테이블 쿼리
- **신규 pip 의존성 0건** — stdlib 전용
- **DART/RSS/Prometheus/Provider Data Ingestion default OFF 유지** (v0.12 정책 그대로)
- **source_file_path / secret / api_key** 응답·로그·UI 어디에도 평문 0건

---

## 4. 최종 게이트 (v0.13-final 시점)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend pytest | `python -m pytest -q --tb=no` | **1277 passed** (36.15s) |
| frontend vitest | `cd frontend && npm run test -- --run` | **175 passed** |
| frontend build | `cd frontend && npm run build` | 그린 (`tsc --noEmit && vite build`) |
| Playwright e2e | `cd frontend && npm run e2e` | **21 passed** (chromium) |

---

## 5. 한계 및 알려진 사항

- `PROVIDER_SCORE_POLICY_ENABLED=True` 시 producer 통합 미완성 — `ProviderScorePolicy` 는
  독립 유틸로 존재하지만 실 producer (`RealNewsScoreProducer` / `RealFundamentalScoreProducer` 등) 에
  자동 연결되지 않음. v0.14+ 에서 통합 예정
- Backtest Export CLI (`scripts/export_backtest.py`) 미구현 — v0.14+ 이연
- Validation Report 는 `backtest_results` 테이블 기반이므로 backtest run 실행 전에는 모든 집계가 0

---

## 6. v0.14+ 후보

- **Backtest Export CLI** — `scripts/export_backtest.py` (stdlib csv, pip 0건, forbidden field guard)
- **ProviderScorePolicy → producer 통합** — `RealNewsScoreProducer` / `RealFundamentalScoreProducer` / `RealEarningsScoreProducer` 에 policy factor 자동 적용 (누적 backtest 검증 기반)
- **ScoringEngine weight 보강** — v0.13 validation report 결과 기반 (누적 데이터 6개월+ 필요)
- **ProviderHealthMonitor 영속화** — DB / Redis 백업 (현재 in-memory bounded ring buffer)
- **Grafana dashboard JSON 동봉** — Prometheus exporter 연결 완성 후
- **인증 고도화** — OAuth / SSO / RBAC (단일 admin user → 다중 사용자)
- **Paper trading / 가상매매 루프** — 별도 보안·컴플라이언스 사이클 필요

---

## 7. 누적 태그 목록

```
v0.1-backend-final → v0.1-backend-kis-paper-verified
v0.2-frontend-final
v0.3-phase-a-ci → v0.3-backend-analysis → v0.3-frontend-calendar → v0.3-frontend-stock-chart → v0.3-final
v0.4-backend-reports → v0.4-import-pipeline → v0.4-report-score → v0.4-frontend-reports → v0.4-final
v0.5-news-collector → v0.5-disclosure-pipeline → v0.5-news-score → v0.5-frontend-themes → v0.5-final
v0.6-fundamental-data-layer → v0.6-earnings-event-pipeline → v0.6-fundamental-score → v0.6-frontend-fundamentals → v0.6-final
v0.7-strategy-interface → v0.7-backtest-engine → v0.7-backtest-cost-regime → v0.7-frontend-backtest → v0.7-final
v0.8-alembic-baseline → v0.8-auth-foundation → v0.8-watchlist-api → v0.8-frontend-watchlist → v0.8-final
v0.9-security-hardening → v0.9-monitoring → v0.9-watchlist-api → v0.9-frontend → v0.9-final
v0.10-provider-runtime → v0.10-provider-resilience → v0.10-dart-provider → v0.10-rss-provider → v0.10-health-api → v0.10-final
v0.11-dart-transport → v0.11-rss-transport → v0.11-observability → v0.11-health-extended → v0.11-final
v0.12-provider-ingestion → v0.12-walk-forward → v0.12-multi-strategy → v0.12-scoring-readonly → v0.12-final
v0.13-provider-policy → v0.13-score-delta → v0.13-validation-api → v0.13-validation-ui → v0.13-final
```
