# Roadmap

> 본 문서는 **v0.4 Phase B 인수 시점** 기준으로 갱신되었다 (`v0.4-import-pipeline`
> 태그). 초안 (자동매매 중심 v0.2~v1.0 구상) 과 실제 진행 이력이 달라져 전면
> 재작성. 자동매매 / MockBroker / 백테스트 / FULL_AUTO 는 모두 **Future
> Backlog** 로 이동했고, 실제로 진행된 사이클은 분석·UX·CI·운영 정착 +
> 증권사 리포트 인텔리전스 중심이다.

## 진행 이력 요약

| 사이클 | 핵심 목표 | 상태 | 최종 태그 |
|---|---|---|---|
| v0.1 Backend | KIS read-only 데이터 + 분석 + 추천 + 보유 점검 + 텔레그램 + Backend API + 6 잡 | ✅ 마감 | `v0.1-backend-kis-paper-verified` |
| v0.2 Frontend MVP | PC 대시보드 8 화면 (Vite + React + TS), 코드 스플릿, Docker | ✅ 마감 | `v0.2-frontend-final` |
| v0.3 Analysis & Ops | GitHub Actions CI / 캔들·ATR / KRX 휴장 캘린더 / StockDetail 일봉 차트 | ✅ 마감 | `v0.3-final` |
| v0.4 Analyst & Theme Intelligence | 증권사 리포트 + 테마 매핑 + 변화 시그널 + 리포트 점수 통합 (Phase A~E) | 🟡 Phase A+B 인수 / Phase C 대기 | `v0.4-import-pipeline` (Phase B) |

---

## v0.1 — 분석 / 점검 / 리포트 기반 (✅ 마감)

기준선: KIS API 기반 read-only 시스템. 296 passed.

핵심 산출물:

- 17 ORM 모델 + 16 Repository
- KIS HTTP 클라이언트 + 정규화 + 품질 검사 + Fake provider
- 17 KRX 종목 + 시총 TOP 500 유니버스
- Technical 지표 (MA / RSI / MACD / breakout / ma_alignment)
- ScoringEngine + RecommendationEngine + HoldingCheckEngine + RiskEngine + DummyScoreProducer
- 보유 종목 장전 / 장후 점검
- 추천 TOP 5 + 1/3/5/20일 후 성과 검증
- TelegramNotifier (DRY_RUN 기본) + 3 dispatcher
- FastAPI 13 read-only GET 라우터
- APScheduler + 6 일별 잡
- mock seed (`scripts/seed_mock_data.py`) + INTEGRATION_RUNBOOK 통합 검증
- KIS 모의투자 서버 read-only 1회 인수

상세: [`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md)

---

## v0.2 — PC 대시보드 MVP (✅ 마감)

기준선: `v0.1-backend-final`. 백엔드 코드 0건 변경. vitest 36 / e2e 6.

핵심 산출물:

- Vite 5 + React 18 + TypeScript 5.5 + Tailwind 3.4 + TanStack Query/Table + Recharts
- 8 화면: Today / Recommendations / History / Holdings / StockDetail /
  MarketCapTop / Jobs / Settings — 모두 backend read-only API 만 소비
- 코드 스플릿 (page-level lazy + manualChunks: vendor-react / query / table /
  charts) — 첫 진입 (Today, no charts) ≈ gzip 80 kB
- 비밀값 마스킹 가드 (`secret-*` 노드 `data-masked="true"` + `⚠ unmasked` 부재 e2e)
- 자동매매 UI 부재 가드 (8 페이지 모두 `<button type="submit">` / `<form>` 0건,
  "실거래 시작 / 자동매매 시작 / 주문 실행" CTA 라벨 0건 e2e)
- Docker 배포 (`web` 컨테이너 nginx + `/api` proxy → backend, port 8080)
- Playwright e2e 6 + msw v2 + jsdom

상세: [`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md)

---

## v0.3 — 분석 보강 + 운영 정착 (✅ 마감)

기준선: `v0.2-frontend-final`. backend 296 → 319 / vitest 36 → 59 / e2e 6 → 8.

핵심 산출물 (5 phase):

- **Phase A** — GitHub Actions CI 3 잡 (backend pytest / frontend vitest+build /
  Playwright e2e). main / PR 자동 검증. 태그 `v0.3-phase-a-ci`.
- **Phase B** — 캔들 패턴 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING /
  BEARISH_ENGULFING) + Wilder ATR(14) + 4단계 변동성 분류. `technical_score` 에
  ±5점 cap 보조 가산. `StockIndicator` 에 nullable 컬럼 3개 추가 (atr14 /
  candle_patterns / volatility_band). 태그 `v0.3-backend-analysis`.
- **Phase C** — KRX 휴장일 정적 JSON (2025–2027) + `marketCalendar` 유틸 +
  `MarketStatusBanner` 컴포넌트 (Today / Jobs / Holdings 헤더). 외부 API 호출 0건.
  태그 `v0.3-frontend-calendar`.
- **Phase D** — `GET /api/stocks/{symbol}/prices?days=120` 신규 + StockDetail
  일봉 라인 차트 (Recharts) + 30/60/120/250 days 선택자. 태그
  `v0.3-frontend-stock-chart`.
- **Phase E** — `RELEASE_NOTES_v0.3.md` + 마감 선언. 태그 `v0.3-final`.

상세: [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md)

---

## v0.4 — Analyst & Theme Intelligence (🟡 Phase A+B 인수, Phase C 진입 대기)

기준선: `v0.3-final` (HEAD `f6b0ba5`). backend 319 → 335 (Phase A) → **362 (Phase B)**.

증권사 애널리스트 리포트 (기업 / 산업 / 테마 / 원자재 / 매크로 / 전략) 메타데이터를
저장 + 리포트에서 추출한 투자 테마와 종목 매핑 + 변화 시그널 이벤트를 구조화 +
보조 점수 (`report_score` + `theme_signal_score`) 를 추천에 ±5점 cap 가산.

| Phase | 작업 | 상태 | 태그 |
|---|---|---|---|
| A | DB 모델 6종 + Repository 6종 + 통합 테스트 16건 | ✅ 인수 | `v0.4-backend-reports` |
| B | CSV import CLI + 일별 컨센서스 스냅샷 잡 + 통합 테스트 27건 (import 19 + consensus 8) | ✅ 인수 | `v0.4-import-pipeline` |
| C | `report_score` + `theme_signal_score` 계산기 + RecommendationEngine 통합 (±5점 cap) + decision evidence | ⏳ 진입 대기 | `v0.4-report-score` |
| D | 프런트 (StockDetail 리포트·테마·시그널 카드 + Recommendations score 컬럼) | ⏳ | `v0.4-frontend-reports` |
| E | `RELEASE_NOTES_v0.4.md` + 마감 선언 | ⏳ | `v0.4-final` |

**Phase B 산출물** (인수 완료):

- `scripts/import_analyst_reports.py` — argparse CLI (default dry-run, `--commit` 시 DB 적재, `--encoding` / `--db-url` 옵션, `source_file_path` 미노출)
- `app/data/importers/analyst_reports.py` — 35 컬럼 CSV → 4 entity 분해 + 검증 + 멱등 upsert
- `update_report_consensus_snapshots` 잡 (06:30 KST, 7번째 잡 등록)
- `tests/fixtures/analyst_reports_sample.csv` (3 row: COMPANY 삼성전자 + THEME 메모리 쇼티지 + COMMODITY Cu, 가상 데이터)
- 통합 테스트 27건 (`test_analyst_report_import.py` 19 + `test_consensus_snapshot_job.py` 8)
- `INTEGRATION_RUNBOOK.md` §9 (dry-run / commit / 인코딩 / DB URL / 컨센서스 잡 수동 트리거 / 점검)

**저작권 / 컴플라이언스 정책 (전체 v0.4 사이클)**:

- 리포트 원문 본문 / paragraph DB 저장 0건
- PDF BLOB DB 저장 0건 — `source_url` 또는 `source_file_path` 만
- `source_file_path` 외부 노출 0건 (API 응답 / 프런트 / e2e 모두 마스킹)
- 자동 크롤링 / 스크레이핑 0건 (수동 CSV / Excel import 만)
- 외부 공유 / 공개 API 0건
- 추천 산식 본 weight 변경 0건 (보조 ±5점 cap 만)

상세 계획: [`PLANS.md`](./PLANS.md) `PLAN-0004`

---

## v0.5+ 후보

v0.4 마감 후 진입 가능 후보. 현재는 모두 미착수 — 명시적 진입 요청 전까지 손대지
않는다.

### 5.1 데이터 / 분석 실제화

- **실 News / 공시 파이프라인** — `DummyScoreProducer` 의 news/supply 컴포넌트를
  실제 뉴스·공시 수집기로 교체. `NewsItem` 테이블은 v0.1 부터 존재하지만 미수집.
- **실 재무 / 실적 점수** — `FundamentalSnapshot` / `EarningsSnapshot` 테이블 신규 +
  DART / 공공 API 연동. 추천 산식의 `fundamental_score` / `earnings_score` 컴포넌트
  실제화.
- **KRX 휴장일 자동 fetch** — 정적 JSON 의 수동 갱신 (매년) 을 자동 fetch 로 대체
  (한국거래소 공지 RSS / 공공 API).
- **추천 성과의 N=20 외 다른 기간 토글** — 현재는 1/3/5/20일 고정.

### 5.2 운영 / UX

- **즐겨찾기 / 관심 종목** — POST 라우터 도입 필요 (인증 동반 필수).
- **인증 / 권한** — 사내망 외 노출 시 단일 토큰 / API key 헤더부터.
- **운영 모니터링** — Sentry / Prometheus / Grafana.
- **글로벌 검색** (cmd+k), sidebar collapse, breadcrumb, loading skeleton 통일.
- **모바일 / 태블릿 레이아웃** — 현재는 PC 1280px+ 우선.
- **StockDetail 캔들 차트 + 거래량 BarChart + 이동평균 오버레이** — `lightweight-charts`
  마이그레이션 검토.

### 5.3 백엔드 인프라

- **POST 트리거** (잡 수동 실행 / 추천 즉시 생성) — 인증 동반 필수.
- **WebSocket / SSE 실시간 잡 상태** — 현재 polling.
- **`.github/dependabot.yml`** — v0.3 Phase A 에서 보류된 항목.

### 5.4 LLM / AI 강화

- **Analyst Report LLM 자동 요약** — v0.4 Phase A 의 `extraction_method` /
  `extraction_confidence` 필드를 활용해 LLM 추출 결과를 안전하게 mark.
- **AI Provider 교체** — 현 `DummyScoreProducer` → 로컬 / 클라우드 LLM 통합.

---

## Future Backlog — 자동매매 / 백테스트 / 가상매매

⚠ **모두 별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실 제한 사이클이
선행되어야 진입 가능.** v0.5 까지의 모든 후보는 자동매매 부재 정책을 유지한다.

| 단계 | 범위 | 진입 전제 |
|---|---|---|
| Strategy & Signal | StrategyInterface 활성화, SIGNAL 모드 | 실 News / 재무 데이터 (v0.5) 후행 |
| Backtest 엔진 | walk-forward 검증, Grid Search 튜닝, 시장 국면별 성과 분석 | Strategy 모듈 선행 |
| MockBroker / ReplayBroker / SimulationBroker | 가상 계좌 / 가상 주문·체결 / 가상 시나리오 / 스트레스 테스트 | BrokerInterface 구현 진입 |
| 전용 ML 모델 | Market Regime / Strategy Selection / Risk Prediction. 추천 성과 기반 재학습. LLM 과 전용 AI 역할 분리 | Backtest 데이터 누적 후행 |
| APPROVAL 모드 | 사용자 승인 후 실 KIS 주문 — 비상정지 / 일일 손실 제한 / 종목당 한도 / 전략별 한도 / 실거래 로그 / 보안 강화 동반 | 컴플라이언스 검토 + MockBroker 검증 |
| SMALL_AUTO | 소액 자동 — 위와 동일 보안 게이트 + 자본 상한 | APPROVAL 모드 안정 운영 후 |
| FULL_AUTO | 전면 자동 | 본 프로젝트 범위 외 — 별도 설계 cycle |

**전체 자동매매 흐름 (모두 미구현)**:

```text
Strategy Signal → AI Judgement → RiskEngine → BrokerInterface → TradeLogger
```

`BrokerInterface` 는 ABC placeholder 만 유지. v0.1 ~ v0.4 어디에도 구현체 없음.

---

## 장기 비전

AI 기반 개인용 주식 전략 연구 플랫폼.

```text
KIS data + 휴장 캘린더 + 증권사 리포트 + 테마 매핑 + 시그널 이벤트
   → 분석 / 점수 / 추천 / 보유 점검 / 컨센서스
   → 텔레그램 / 대시보드 (read-only)
   → (v0.5+) 실 News / 재무 / 인증 / Watchlist
   → (Future) Strategy / Backtest / 전용 AI / 가상매매 → APPROVAL → SMALL_AUTO
```

본 프로젝트는 **투자 판단 보조 도구**다. 자동매매는 오랜 검증과 보안 강화가
완료된 후에만 검토한다.
