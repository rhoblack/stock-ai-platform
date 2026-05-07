# Release Notes — v0.12 Provider Data Scoring & Backtest Validation

> 마감 태그: `v0.12-final`  
> 기준 태그: `v0.11-final`  
> 마감 일자: **2026-05-07 (Asia/Seoul)**  
> 사이클: **Provider Data Scoring & Backtest Validation** (Phase A~E, 5 phase)

---

## 개요

v0.12 는 v0.11 의 **실 DART/RSS HTTP transport** 위에 **데이터 ingestion → DB 저장 →
기존 ScoringEngine 자동 흡수** 경로를 완성하고, **walk-forward backtest 검증 +
다중 전략 비교 + read-only API/UI 확장** 을 추가하는 사이클이다.

채택 시나리오: **Scenario X — Provider Data Scoring + Backtest Validation**

- Provider 데이터 → DB ingestion (기존 producer 자동 흡수, **ScoringEngine weight 변경 0건**)
- Walk-forward backtest engine (IS/OOS fold 분리 검증)
- Multi-strategy comparison + Regime/Sector breakdown
- Backtest 결과 read-only API 2종 + UI 보강 + `data_source` chip

---

## Phase 별 산출물

### Phase A — Provider Data Ingestion (default OFF)

> 태그: `v0.12-provider-ingestion` | pytest 1119 → 1149 (+30)

**신규 파일**
- `app/data/ingestion.py` — 4 어댑터: `ingest_dart_disclosures` / `ingest_rss_news` / `ingest_dart_fundamentals` / `ingest_dart_earnings`
- `tests/integration/test_provider_data_ingestion.py` — 30 케이스

**변경 파일**
- `app/config/settings.py` — `PROVIDER_DATA_INGESTION_ENABLED: bool = False` 추가
- 4 DTO (`NewsItemDTO` / `DisclosureItemDTO` / `FundamentalSnapshotDTO` / `EarningsEventDTO`) — `data_source: str = "FAKE"` 필드 + `DATA_SOURCE_*` 상수
- DART parser / RSS parser / CSV importer — `data_source` 자동 태깅

**핵심 정책**
- `PROVIDER_DATA_INGESTION_ENABLED=False` **기본** — 명시 enable 없이 ingestion 0건
- DART/RSS provider 도 개별 default OFF 유지 — master flag 켜도 provider OFF 면 soft-skip
- ScoringEngine / HoldingCheckEngine 본 weight 변경 0건
- Alembic 신규 revision 0건 — `data_source` 는 runtime-only DTO 필드 (DB 컬럼 없음)
- DART_API_KEY / RSS feed URL query secret caplog 평문 0건

**테스트 요약 (30 케이스)**
- default OFF 가드 6건 — 모든 어댑터 `PROVIDER_DATA_INGESTION_ENABLED=False` 시 즉시 skip
- happy path (어댑터 → DB) 4건 — 실 transport 없이 DTO 직주입
- DTO `data_source` provenance 4건 — PROVIDER/FAKE/CSV/MANUAL 태깅 확인
- body 부재 7 단언 — DTO / DB 컬럼에 body/paragraph/raw_text 없음
- secret caplog 단언 3건 — API key / feed URL query secret 평문 0건
- ScoringEngine weight 회귀 1건 — Decimal 정확도 포함

---

### Phase B — Walk-forward Backtest Engine

> 태그: `v0.12-walk-forward` | pytest 1149 → 1167 (+17, 1 deselected 유지)

**신규 파일**
- `app/backtest/walk_forward.py` — `WalkForwardBacktestEngine` + `FoldResult` + `WalkForwardSummary` + `generate_folds()`
- `tests/integration/test_walk_forward_engine.py` — 17 케이스

**변경 파일**
- `scripts/run_backtest.py` — `--walk-forward` / `--train-window-days` / `--validate-window-days` / `--gap-days` CLI 옵션 추가

**핵심 정책**
- train/validate window sliding: 기본 60일/20일, `gap_days=0`, 각 step 은 `validate_window_days` 씩 슬라이드 → OOS 겹침 없음
- IS (In-Sample) + OOS (Out-of-Sample) 각각 `win_rate_5d` / `avg_return_5d` 집계
- fold metadata → `backtest_runs.summary_json["walk_forward_folds"]` 직렬화 — Alembic revision 0건
- `BacktestEngine` / v0.7 stratergy 회귀 0건

**테스트 요약 (17 케이스)**
- `generate_folds()` 순수 논리 5건 (DB 없음)
- 엔진 dry-run 4건 + commit 3건
- CLI 옵션 2건
- IS/OOS 집계 1건 + 직렬화 2건

---

### Phase C — Multi-strategy Comparison + Regime/Sector Breakdown

> 태그: `v0.12-multi-strategy` | pytest 1167 → 1183 (+16, 1 deselected 유지)

**신규 파일**
- `app/backtest/multi_strategy_runner.py` — `MultiStrategyRunner` + `StrategyResult` + `MultiStrategyComparison` + `_find_best()`
- `app/backtest/regime_breakdown.py` — `SectorBreakdownEntry` + `aggregate_sector_breakdown()`
- `tests/integration/test_multi_strategy_comparison.py` — 16 케이스

**변경 파일**
- `scripts/run_backtest.py` — `--multi` / `--strategies` / `--no-regime-breakdown` / `--no-sector-breakdown` CLI 옵션

**핵심 정책**
- 같은 기간/유니버스 보장 — `_fetch_recs_with_sector()` 가 `BacktestEngine._fetch_recommendations()` 와 동일 ordering/limit
- sector 미분류 종목 → `UNKNOWN` bucket 안전 처리
- 비교 결과 → `backtest_runs.summary_json["multi_strategy_comparison"]` 직렬화 — Phase B `walk_forward_folds` key 충돌 없음, Alembic revision 0건
- commit 시 정확히 1건의 `BacktestRun(strategy_name="MULTI")` 영속

**테스트 요약 (16 케이스)**
- `aggregate_sector_breakdown()` 순수 논리 2건
- `MultiStrategyRunner` dry-run 3건
- best-strategy ranking 2건 (`best_strategy_by_win_rate_5d` / `_by_avg_return_5d`)
- sector/regime breakdown 3건
- commit 2건 + 직렬화 1건 + CLI 3건

---

### Phase D — Backtest Read-only API/UI 확장 + data_source chip

> 태그: `v0.12-scoring-readonly` | pytest 1183 → 1194 (+11) / vitest 158 → 165 (+7)

**신규 파일**
- `frontend/src/hooks/useBacktestFolds.ts`
- `frontend/src/hooks/useBacktestComparison.ts`
- `tests/integration/test_backtest_api_phase_d.py` — 12 케이스

**변경 파일**
- `app/api/schemas.py` — `SectorBreakdownSchema` / `BacktestFoldSchema` / `BacktestFoldsResponse` / `BacktestComparisonStrategySchema` / `BacktestComparisonResponse` 추가
- `app/api/routes.py` — `GET /api/backtest/runs/{id}/folds` + `GET /api/backtest/runs/{id}/comparison` + helper 3개
- `frontend/src/api/types.ts` — 5개 타입 추가
- `frontend/src/pages/Backtest/index.tsx` — fold 표 / comparison 표 / sector breakdown / best strategy 강조 / `data_source` chip 추가
- `frontend/src/tests/Backtest.test.tsx` — 7 케이스 추가
- `frontend/src/tests/mswServer.ts` — 기본 핸들러 2건 추가

**API 설계 정책**
- `GET /api/backtest/runs/{id}/folds` — `summary_json["walk_forward_folds"]` 파싱; key 부재 시 200 + 빈 목록 (not 404); run 행 없으면 404
- `GET /api/backtest/runs/{id}/comparison` — `summary_json["multi_strategy_comparison"]` 파싱; 동일 정책
- non-dict 항목 자동 건너뜀 (graceful malformed)
- POST/PUT/PATCH/DELETE → 405 (mutation guard pytest 2건)

**data_source chip 정책**
- `BacktestResultItem.evidence_json?.data_source` 를 그대로 읽음 — 새 DB 컬럼 / Alembic revision 없음
- 색 구분: `PROVIDER`=파랑 / `FAKE`=황 / `CSV`=보라 / `MANUAL`=회색
- null이면 chip 미노출

**테스트 요약 (backend 12 + vitest 7)**
- folds/comparison happy path, empty (key 부재), 404 (run 없음), non-dict skip
- 405 mutation guard 2건
- forbidden field scan 2건 (`source_file_path` / `raw_text` / `본문` / `api_key` / `token` / `secret` / `order_id` / `quantity` / `broker`)
- vitest: fold 표 2건 + comparison 표 2건 + data_source chip 2건 + forbidden 1건

---

## 최종 게이트 (v0.12-final 시점)

| 게이트 | 명령 | 결과 |
|---|---|---|
| backend pytest | `python -m pytest -q --deselect tests/unit/test_project_structure.py::test_settings_defaults` | **1194 passed, 1 deselected** |
| frontend vitest | `cd frontend && npm run test -- --run` | **165 passed** (20 파일) |
| frontend build | `cd frontend && npm run build` | **그린** (tsc --noEmit + vite build, ~2.9s) |
| Playwright e2e | `cd frontend && npm run e2e` | **21 passed** (chromium) |

v0.12 사이클 신규 테스트: backend +75 (Phase A 30 + B 17 + C 16 + D 12) / vitest +7.

---

## 안전 정책 (v0.12 전체 재확인)

| 정책 | 상태 |
|---|---|
| ScoringEngine 본 weight 변경 | **0건** — `technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%` 그대로 |
| HoldingCheckEngine 산식 변경 | **0건** |
| DART/RSS/Prometheus/Provider Data Ingestion default | **모두 OFF** (`False`) |
| 신규 Alembic revision | **0건** — walk-forward fold / comparison 결과 모두 `summary_json` 재활용 |
| 신규 mutation 라우터 (POST/PUT/DELETE) | **0건** (Phase D `/folds` / `/comparison` 모두 GET only) |
| 외부 네트워크 호출 (테스트 내) | **0건** (`respx` transport-layer mock + `httpx.Client` 미생성 단언) |
| 자동매매 / 실 KIS 주문 / BrokerInterface 구현 | **0건** (v0.1~v0.12 일관) |
| DART_API_KEY / RSS feed URL query secret 평문 | **0건** — `SensitiveFilter` + `SensitiveQueryStringFilter` + caplog scan |
| body / raw_text / 본문 / source_file_path 응답 노출 | **0건** — routes whitelist + paranoid substring scan |
| 신규 pip 의존성 | **0건** — v0.11 의 `respx` + `prometheus-client` 그대로 |

---

## 알려진 한계

1. **ScoringEngine weight 미보강** — Phase A 의 ingestion 이 producer 에 흐르지만 weight 자체는 v0.5/v0.6 룰 기반 그대로. 누적 DART/RSS 데이터 6개월+ 검증 후 v0.13 후보.
2. **ingestion default OFF** — `PROVIDER_DATA_INGESTION_ENABLED=True` 로 enable 하면 DART/RSS 가 가져온 데이터가 DB 에 적재되지만, 실 환경에서는 운영자가 직접 env 를 켜야 함.
3. **walk-forward fold 수 제한** — 역사 데이터 60일 미만 시 fold 0건. 짧은 look-back 구간에서는 검증 불가.
4. **Sector 미분류 → UNKNOWN** — `stock_universes` 에 sector 등록 없는 종목은 `UNKNOWN` bucket 에 집계됨. 실 운영 전 sector 매핑 보강 필요.
5. **백테스트 비용 모델 placeholder** — `CostModel` 은 `total_cost=0.33%` 상수. 실 broker fee schedule 연동은 v0.8+ 후보 미완.
6. **e2e Phase D 미보강** — Playwright e2e 는 Phase D fold 표 / comparison 표 검증 없음 (기존 21개 유지). 실 UI 검증은 vitest 수준.

---

## v0.13 후보 (우선순위 순)

1. **ScoringEngine 본 weight 보강** — v0.12 walk-forward 결과 기반으로 DART/RSS 비중 증가 (누적 데이터 6개월+ 검증 필요)
2. **Grafana dashboard JSON 동봉** — v0.11 Prometheus exporter 위 시각화 layer (외부 인프라)
3. **ProviderHealthMonitor 영속화** — DB / Redis 백업으로 재시작 후 call/failure history 유지
4. **인증 고도화** — refresh token / 다중 사용자 / OAuth / SSO / RBAC (단일 사용자 운영 검증 후)
5. **CSP / rate limit 튜닝** — 실 트래픽 수집 후 정책 수립
6. **LLM sentiment / 자동 요약** — 룰 기반 검증 후 (외부 LLM API 비용 / 보안 / 라이선스)
7. **WebSocket / SSE 실시간 갱신** — Provider Health / 백테스트 진행 / 잡 (현재 polling)
8. **`/api/health/jobs` 분리 + Provider toggle GUI** — 인증 + 보안 검토 동반
9. **CostModel 실 fee schedule 연동** — 실 broker API 비용 모델 교체 (v0.8 이연분)
10. **자동매매** (Future Backlog — 별도 보안·컴플라이언스·자본 한도 사이클 선행 필수)

---

## 누적 인수 태그

```
v0.1-backend-final → v0.1-backend-kis-paper-verified →
v0.2-frontend-final →
v0.3-phase-a-ci → v0.3-backend-analysis → v0.3-frontend-calendar → v0.3-frontend-stock-chart → v0.3-final →
v0.4-backend-reports → v0.4-import-pipeline → v0.4-report-score → v0.4-frontend-reports → v0.4-final →
v0.5-news-collector → v0.5-disclosure-pipeline → v0.5-news-score → v0.5-frontend-themes → v0.5-final →
v0.6-fundamental-data-layer → v0.6-earnings-event-pipeline → v0.6-fundamental-score → v0.6-frontend-fundamentals → v0.6-final →
v0.7-strategy-interface → v0.7-backtest-engine → v0.7-backtest-cost-regime → v0.7-frontend-backtest → v0.7-final →
v0.8-alembic-baseline → v0.8-auth-foundation → v0.8-watchlist-api → v0.8-frontend-watchlist → v0.8-final →
v0.9-security-hardening → v0.9-monitoring → v0.9-watchlist-api → v0.9-frontend → v0.9-final →
v0.10-provider-runtime → v0.10-provider-resilience → v0.10-dart-provider → v0.10-rss-provider → v0.10-health-api → v0.10-final →
v0.11-dart-transport → v0.11-rss-transport → v0.11-observability → v0.11-health-extended → v0.11-final →
v0.12-provider-ingestion → v0.12-walk-forward → v0.12-multi-strategy → v0.12-scoring-readonly → v0.12-final
```
