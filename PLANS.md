# PLANS.md

Codex가 긴 작업을 수행할 때 사용하는 실행 계획 문서다.

## 사용 원칙

긴 구현 작업을 시작하기 전에 Codex는 다음 형식으로 계획을 작성한다.

```text
목표:
범위:
수정할 파일:
수정하지 않을 파일:
단계:
테스트:
완료 기준:
위험 요소:
```

## 계획 템플릿

### Plan ID

`PLAN-YYYYMMDD-번호`

### 목표

무엇을 구현할지 한 문장으로 설명한다.

### 범위

이번 계획에 포함되는 작업.

### 제외 범위

이번 계획에서 하지 않을 작업.

### 수정할 파일

예상 수정 파일 목록.

### 단계

1. ...
2. ...
3. ...

### 테스트

- 실행할 테스트
- mock 처리할 외부 API
- 수동 확인 항목

### 완료 기준

- 코드 실행 가능
- 테스트 통과
- 문서 갱신
- AGENTS.md 원칙 위반 없음

## 예시

### PLAN-0001: DB 모델 1차 구현

목표:
v0.1 핵심 DB 모델과 Repository 기반을 구현한다.

범위:
- stocks
- holdings
- daily_prices
- stock_indicators
- job_runs

제외 범위:
- 추천 로직
- KIS API 호출
- 텔레그램
- 대시보드 프론트엔드

수정할 파일:
- app/db/models.py
- app/db/session.py
- app/data/repositories/*.py
- tests/db/test_models.py

단계:
1. SQLAlchemy Base와 세션 설정
2. 핵심 모델 작성
3. 인덱스 추가
4. Repository 작성
5. 테스트 작성

테스트:
- pytest tests/db

완료 기준:
- DB 모델 import 가능
- 테스트 DB에서 create/drop 가능
- Repository 저장/조회 테스트 통과

---

## PLAN-0003: v0.3 분석 보강 + 운영 정착 (5 Phase)

### 기준선

- 시작 태그: `v0.2-frontend-final` (GitHub `origin/main` 동기화 완료)
- v0.1 backend / v0.2 frontend 양쪽 인수 완료. 회귀 게이트: backend pytest 296, frontend vitest 36, e2e 6, build 통과
- v0.3 는 v0.1-backend-final 동결을 일부 깨고 새로운 backend 라인 (`v0.3-backend-*` 태그군) 을 시작한다. 단 read-only / mock 경계 / 자동매매 부재 정책은 동일하게 유지한다

### 목표

(1) 추천 점수의 등급 분포가 D~C 에 몰리는 문제를 캔들 패턴 + ATR 변동성 컴포넌트로 완화하고, (2) PC 대시보드 운영 사용성 (휴장일 / 종목 상세 차트) 을 채우며, (3) GitHub Actions CI 로 회귀 자동 게이트를 정착시키고, (4) v0.3 릴리스 문서로 마감한다.

### 범위 (5 Phase)

- Phase A — GitHub Actions CI (backend pytest + frontend vitest + e2e + build, PR 머지 게이트)
- Phase B — 캔들 패턴 + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
- Phase C — 한국거래소 휴장일 캘린더 (정적 JSON 우선, 프런트 배너)
- Phase D — `GET /api/stocks/{symbol}/prices` 신규 endpoint + StockDetail 일봉 차트 (Recharts)
- Phase E — `RELEASE_NOTES_v0.3.md` 신규 + README / PROJECT_STATUS 마감 선언 + tag `v0.3-final`

### 제외 범위 (v0.3 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI (수동 잡 실행 / 추천 즉시 생성 / 추가·삭제 폼)
- ❌ 실 News / Supply / Fundamental / Earnings 외부 파이프라인 (계속 `DummyScoreProducer` placeholder 유지. 캔들/ATR 만 추가)
- ❌ 즐겨찾기 / 관심 종목 (POST 필요해 별도 cycle)
- ❌ 인증 / 권한 (단일 사용자 / 사내망 가정 유지)
- ❌ Sentry / Prometheus / 운영 모니터링 (Phase F+ 후보로 미룸)
- ❌ Strategy / Backtest / MockBroker / SimulationBroker
- ❌ 모바일 / 태블릿 레이아웃 (PC 1280px+ 우선 유지)

---

### Phase A — GitHub Actions CI

**목표:** PR / push 시 backend + frontend 회귀가 자동으로 검증되는 머지 게이트 정착.

**수정할 파일:**

- `.github/workflows/ci.yml` (신규) — Python + Node 두 잡 매트릭스
- (선택) `.github/dependabot.yml` (신규) — 의존성 업데이트 자동 PR

**수정하지 않을 파일:**

- `app/`, `tests/`, `frontend/src/` 등 코드 / 테스트 파일은 손대지 않는다 (CI 가 기존 회귀를 그대로 실행)

**단계:**

1. backend job: `python 3.12` setup → `pip install -e ".[dev]"` → `pytest -q`
2. frontend job (병렬): `node 20` + `cache: npm` → `npm ci` → `npm run lint && npm run test && npm run build`
3. e2e job (frontend job 의존): `npx playwright install chromium` → `npm run e2e` (artifact 로 `playwright-report/` 업로드)
4. all-green 정책: 3 job 모두 성공 시 머지 가능 (branch protection 설정은 GitHub UI 에서 사용자가 직접)

**테스트:**

- 본 phase 자체는 코드 변경 없음 → 회귀 테스트는 CI 가 자기 자신을 실행해 검증
- PR 1건 만들어서 일부러 깨뜨려보고 (예: 임시 commit) CI 가 빨갛게 실패하는지 1회 확인

**완료 기준:**

- main 브랜치 + 임의 PR 에서 `Backend / pytest` `Frontend / vitest+build` `Frontend / e2e` 3 체크가 모두 정상 표시
- backend 296 / frontend vitest 36 / e2e 6 / build 통과
- README 에 CI 배지 (선택)

**위험 요소:**

- Playwright chromium 다운로드가 GitHub-hosted runner 에서 캐시되어야 빠름. cache key 미스 시 phase 1회당 ~2분 소요.
- npm 캐시 미스 + Python venv 미스 시 워크플로 시간 5분+ 가능. 처음 한 번만 감수.

---

### Phase B — 캔들 패턴 + ATR 변동성 컴포넌트

**목표:** 추천 / 보유 점수의 `technical_score` 산식에 캔들 패턴 시그널과 ATR 변동성 컴포넌트를 추가해 등급 분포가 더 넓어지도록 보강.

**수정할 파일:**

- `app/analysis/technical_analyzer.py` — `compute_atr14`, `detect_candle_patterns` 추가. `IndicatorSnapshot` 또는 부속 dataclass 에 `atr14`, `candle_patterns: list[str]` 필드 추가. `technical_score` 합산식에 가중치 작게 (≤ ±5 점 범위) 적용.
- `app/db/models.py` — `StockIndicator` 에 `atr14` (Numeric) + `candle_patterns` (JSON) 컬럼 추가.
- `app/data/repositories/stock_indicators.py` — `upsert` 시그니처에 새 두 필드 추가.
- `app/analysis/indicator_service.py` — analyzer 산출 결과를 그대로 upsert.
- `app/api/schemas.py` — `StockIndicatorSchema` 에 `atr14` (string), `candle_patterns` (List[str]) 추가.
- `tests/unit/test_technical_analyzer.py` — ATR 계산 / 캔들 패턴 검출 단위 테스트 (~6 신규)
- `tests/integration/test_indicator_service.py` — 신규 컬럼이 DB 까지 흘러가는지 검증
- `tests/integration/test_repositories.py` — upsert 시그니처 변경에 맞춰 1~2건 보강
- (DB 스키마 추가) — Alembic 미사용 단계라 `Base.metadata.create_all` 만으로 검증 DB 갱신. 운영 환경은 별도 마이그레이션 필요 (Phase B 외 별도 ops 작업으로 분리 명시).

**수정하지 않을 파일:**

- `app/decision/scoring_engine.py` — 가중치 산식 본체는 안 바꾼다 (technical_score 입력만 더 풍부해짐)
- `app/decision/recommendation_engine.py`, `app/decision/holding_check_engine.py` — 시그니처 동일
- `frontend/` — 본 phase 에서는 변경 없음 (Phase D 에서 차트 도입할 때 `latest_indicator.candle_patterns` 노출 가능)

**단계:**

1. ATR(14) 계산 함수 + 단위 테스트
2. 캔들 패턴 (망치형 / 도지 / 장악형 / 슈팅스타 4종 우선) 검출 + 단위 테스트
3. `technical_score` 합산에 weight 적용 (예: ATR 정규화 ±2 점, 패턴 적중 +3 / -3 점, 합 보정 후 0~100 clamp 유지)
4. ORM + Repository + Schema 컬럼 추가
5. IndicatorService 가 새 필드 채우는지 통합 테스트
6. 회귀 게이트: backend `pytest` 296+ → 296 + N (신규 테스트 만큼) 통과

**테스트:**

- ATR / 캔들 패턴 단위 테스트 (각 케이스 수동 검증된 OHLC fixture)
- IndicatorService 가 새 필드를 stock_indicators 에 upsert 하는 통합 테스트
- ScoringEngine 회귀 — 기존 weighted total_score 기댓값이 컴포넌트 수정 후에도 단위 테스트에서 깨지지 않는지 (가중치가 작아 여유 있음)

**완료 기준:**

- backend `pytest -q` 통과 (296 + 신규)
- mock seed 적재 후 `/api/stocks/{symbol}` 응답에 `latest_indicator.atr14`, `candle_patterns` 노출
- 등급 분포가 mock seed 5종목 기준에서 S~C 까지 분포 (이전 D~C 한정에서 개선)
- AGENTS.md 원칙 위반 없음 (분석 모듈은 외부 API 호출하지 않음 / 점수 산식 산출만)

**위험 요소:**

- DB 스키마 컬럼 추가 → 운영 DB 마이그레이션 필요. Phase B 자체는 신규 컬럼만 추가 (ALTER ADD COLUMN) 라 destructive 아님. 운영자에게 별도 안내.
- ATR 가중치를 잘못 잡으면 기존 점수와 상충 → 보수적으로 ±2 점 이내로 시작.
- 캔들 패턴 false-positive 가 많으면 잡음 → 첫 cycle 은 4 패턴만, 보수적 임계.

---

### Phase C — 한국거래소 휴장일 캘린더

**목표:** Today / Jobs 화면 등에서 "오늘 휴장 / 다음 영업일 N월 N일" 안내를 표시해 잡 미실행이 정상 상태인지 즉시 판별 가능하게 한다.

**수정할 파일:**

- `frontend/src/data/krxHolidays.ts` (신규) — KRX 공식 휴장일 정적 JSON (2026 + 2027 까지 우선). 출처와 갱신 절차 주석 명시.
- `frontend/src/lib/marketCalendar.ts` (신규) — `isMarketClosed(date)`, `nextOpenDay(date)`, `previousOpenDay(date)` 유틸.
- `frontend/src/components/common/MarketStatusBanner.tsx` (신규) — Today / Jobs / Holdings 페이지 헤더 옆에 "장 운영 / 휴장 (사유)" 배지.
- `frontend/src/pages/TodayReport/index.tsx`, `frontend/src/pages/Jobs/index.tsx`, `frontend/src/pages/Holdings/index.tsx` — Banner 추가.
- `frontend/src/tests/marketCalendar.test.tsx` (신규) — 휴장일 6~8건 테이블 테스트 (주말 / 신정 / 광복절 / 시장 임시휴장 등).
- `frontend/src/tests/MarketStatusBanner.test.tsx` (신규) — 휴장일/평일 분기 렌더 테스트.

**수정하지 않을 파일:**

- `app/` 백엔드 코드 (휴장일은 정적 JSON 으로 시작. 운영 안정 후 백엔드 endpoint 도입은 v0.4 후보)

**단계:**

1. KRX 공식 휴장일을 2026~2027 범위로 수동 수집 → JSON 정리
2. `marketCalendar.ts` 유틸 + 단위 테스트 (주말 자동 탐지 + 휴장일 룩업)
3. `MarketStatusBanner` 컴포넌트
4. 3 화면 (Today / Jobs / Holdings) 헤더에 통합
5. e2e 가 빨강 안 나도록 fixture 의 "오늘 날짜" 가 평일이라고 가정 (또는 navigator 의 시점을 freeze 하는 helper)

**테스트:**

- 휴장일 (2026-01-01, 2026-03-01, 2026-05-05 등) 테이블 단위 테스트
- 평일 / 주말 / 휴장일 각 경우 banner 렌더 분기 테스트
- e2e: 기존 6건 + Banner 노출 (평일 가정) 1건 추가

**완료 기준:**

- 휴장일 데이터 ≥ 2년치 포함
- 3 화면에서 Banner 가 평일/휴장일 분기로 노출
- `npm run test` 36 → 약 40 passed
- `npm run e2e` 6 → 7 passed

**위험 요소:**

- 정적 JSON 은 수동 갱신 필요 — README 에 갱신 절차 (KRX 공식 발표 → JSON 추가) 명시. v0.4 에 백엔드 자동 갱신 endpoint 후보로 등재.
- 시점 freeze 가 어려우면 Banner 의 "오늘 휴장" 케이스 e2e 는 단위 테스트로만 검증.

---

### Phase D — StockDetail 일봉 차트

**목표:** 종목 상세 화면에 최근 N일 일봉 (close + 거래량) 시계열 차트를 추가해 단순 텍스트 표 외 시각화를 제공한다.

**수정할 파일:**

- `app/api/routes.py` — `GET /api/stocks/{symbol}/prices?days=120` 신규 read-only 라우터. `DailyPriceRepository.list_in_range` 활용.
- `app/api/schemas.py` — `StockPriceSeriesResponse { symbol, items: List[DailyPriceSchema] }` 추가 (기존 `DailyPriceSchema` 재사용).
- `tests/integration/test_api_routes.py` — 신규 라우터 happy / empty / 404 3건 추가.
- `frontend/src/api/types.ts` — `StockPriceSeriesResponse` 타입 추가.
- `frontend/src/hooks/useStockPriceSeries.ts` (신규) — `useQuery`, staleTime 5분.
- `frontend/src/pages/StockDetail/PriceChart.tsx` (신규) — `TrendLineChart` 재사용 또는 ComposedChart (close 라인 + volume 막대 옵션).
- `frontend/src/pages/StockDetail/index.tsx` — 차트 카드 추가. 데이터 부족 시 placeholder.
- `frontend/src/tests/StockDetail.test.tsx` — 차트 happy / empty 분기 보강 (~2 신규).
- `frontend/src/tests/mswServer.ts` — 기본 handler 에 `/api/stocks/:symbol/prices` 추가.
- `frontend/e2e/fixtures/apiMocks.ts` — fixture 1건 추가.

**수정하지 않을 파일:**

- 기존 잡 / 엔진 / scoring — 변경 없음
- 백엔드 schema 변경 외 라우터는 손대지 않는다

**단계:**

1. 백엔드 endpoint 추가 + 통합 테스트 3종 (happy 60일 / 빈 / 404)
2. 프런트 hook + 타입
3. PriceChart 컴포넌트 (Recharts ComposedChart 또는 LineChart 단순화)
4. StockDetail 통합 + 테스트 보강
5. e2e fixture 갱신 + 1건 추가

**테스트:**

- backend `pytest -q` (296 + Phase B + Phase D 신규 추가분)
- frontend `npm run test` (40~ → 42~)
- frontend `npm run e2e` (7 → 8)
- mock seed 적재 후 `/stocks/005930` 에서 차트 시각 확인

**완료 기준:**

- `/api/stocks/{symbol}/prices?days=N` 200 OK + 빈 배열 fallback (잘못된 symbol 은 404 vs 빈 — 결정 필요. 권장: 404)
- StockDetail 화면에 close 라인 차트 노출, 데이터 없으면 placeholder
- 모든 회귀 게이트 통과

**위험 요소:**

- 1년 (250 영업일) 이상 요청 시 응답 페이로드 커짐. `days <= 500` 제한.
- Recharts ComposedChart 가 `vendor-charts` 청크에 이미 포함되어 추가 번들 영향은 거의 없음.

---

### Phase E — v0.3 릴리스 문서

**목표:** v0.3 인수 종료 선언과 산출물 / 알려진 한계 / v0.4 후보를 정리한다.

**수정할 파일:**

- `RELEASE_NOTES_v0.3.md` (신규) — 7 섹션 (산출물 / 검증 / 제외 범위 / 알려진 한계 / v0.4 후보 / 운영 가이드 / 보안)
- `README.md` — 상단 인용 블록 v0.3 마감 갱신 + 누적 태그 라인
- `PROJECT_STATUS.md` — §0 v0.3 마감, 기존 §0 → §0-1 (v0.2), §0-2 (v0.1)
- `TASKS.md` — Phase A~E 체크박스 모두 [x]

**단계:**

1. 모든 phase 통과 / 회귀 게이트 통과 후
2. `RELEASE_NOTES_v0.3.md` 작성
3. README / PROJECT_STATUS / TASKS 동기화
4. tag `v0.3-final` 부여 + GitHub push

**테스트:**

- 코드 변경 없음. 단 release 직전 backend pytest + frontend vitest + e2e + build 4 게이트 마지막 1회 실행.

**완료 기준:**

- `RELEASE_NOTES_v0.3.md` 작성 완료
- 4 게이트 모두 그린
- tag `v0.3-final` push 완료
- README 마감 배너 갱신

**위험 요소:**

- Phase 통과 검증 누락 → 마감 직전에 4 게이트 동시 실행으로 차단

---

### v0.3 누적 태그 (예정)

```
v0.2-frontend-final              ← v0.3 시작점
v0.3-phase-a-ci                  ← Phase A 인수
v0.3-backend-analysis            ← Phase B 인수 (캔들+ATR)
v0.3-frontend-calendar           ← Phase C 인수
v0.3-frontend-stock-chart        ← Phase D 인수
v0.3-final                       ← Phase E 인수 / 마감 선언
```

### v0.4+ 후보 (Backlog 등재용)

- 실 News / Supply / Fundamental / Earnings 파이프라인 (DummyScoreProducer 대체) — v0.5+
- 즐겨찾기 / 관심 종목 (POST 라우터 도입 — backend 정책 변경) — v0.5+
- 글로벌 검색 (cmd+k)
- 인증 / 권한 (사내망 외 노출 시)
- Sentry / Prometheus 운영 모니터링
- 자동매매 (별도 보안 / 컴플라이언스 cycle 선행 필수): MockBroker → APPROVAL → SMALL_AUTO

---

## PLAN-0004: v0.4 증권사 리포트 분석 (5 Phase)

### 기준선

- 시작 태그: `v0.3-final` (HEAD `f6b0ba5` 시점, origin/main 동기화 완료)
- v0.1 backend / v0.2 frontend / v0.3 분석·운영 모두 인수 완료. 회귀 게이트: backend pytest 319, frontend vitest 59, e2e 8, build 통과
- v0.4 는 v0.3-final 기준선 위에 **증권사 애널리스트 리포트 데이터 라인** 을 신규 추가한다. 자동매매 / 실 주문 / FULL_AUTO / POST 트리거 / 인증 정책은 v0.3 그대로 유지한다 (여전히 사내망 / 단일 사용자 / read-only 가정)

### 목표

(1) 증권사 애널리스트 리포트 메타데이터를 CSV / Excel 로 import 하고, (2) 종목별 컨센서스 (평균 목표가 / rating 분포 / 최신 발행일) 스냅샷을 일별 갱신하며, (3) 보조 점수 `report_score` 를 계산해 추천 화면 / 종목 상세에 참고 근거로 노출한다. 추천 최종 산식은 급격히 바꾸지 않고 ±5점 cap 으로 보조 가산만 한다.

### 핵심 제약 (저작권 / 컴플라이언스)

- ❌ 리포트 원문 전문 (PDF body, 본문 paragraph) DB 저장 금지 — 메타데이터 + 운영자가 직접 작성한 짧은 요약 (`<= 500자`) 만
- ❌ PDF 파일 자체를 git 레포 / DB BLOB 으로 저장 금지 — `source_url` (외부 발행처 URL) 또는 `source_file_path` (운영자 로컬 경로) 만 보관
- ❌ 자동 크롤링 / 스크레이핑 금지 — v0.4 는 CSV/Excel 수동 import 만. 자동 fetch 는 v0.5+ (저작권 검토 선행)
- ❌ 외부 공유 / 공개 — `source_file_path` 는 admin-only 응답 또는 마스킹 (예: `D:\reports\****`). API 외부 노출 시 path 노출 금지
- ❌ 추천 산식 급변경 — `report_score` 는 보조 (±5점 cap), `total_score` 의 본 weight (technical 50% / news 10% / supply 10% / fundamental 10% / ai 20%) 는 손대지 않음

### 범위 (5 Phase)

- Phase A — DB 모델 3종 + Repository (analyst_reports / report_consensus_snapshots / report_score_logs) + 단위 테스트
- Phase B — CSV / Excel import 명령 (`scripts/import_analyst_reports.py`) + 일별 컨센서스 스냅샷 잡 + 통합 테스트
- Phase C — `report_score` 계산기 + ScoreProducer 통합 (보조 ±5점 cap) + decision_logs evidence 기록
- Phase D — 프런트 (StockDetail 리포트 섹션 + 추천 화면 report_score 컬럼) + msw / e2e fixture
- Phase E — `RELEASE_NOTES_v0.4.md` 신규 + README / PROJECT_STATUS 마감 선언 + tag `v0.4-final`

### 제외 범위 (v0.4 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI / 라우터 — import 는 운영자 CLI (`python -m scripts.import_analyst_reports`) 만, GET 응답에만 변화
- ❌ 리포트 자동 크롤링 / 스크레이핑
- ❌ 리포트 원문 전문 / PDF BLOB DB 저장
- ❌ 리포트 외부 공유 / 공개 API
- ❌ 뉴스 / 공시 실시간 수집 (별도 v0.5+ cycle)
- ❌ 즐겨찾기 / 관심 종목 / 인증 / Strategy / Backtest / MockBroker (v0.5+ 후보 그대로)
- ❌ HoldingCheck 산식 변경 (`report_score` 는 추천 산식에만 보조 가산, 보유 점검은 그대로)

### 데이터 모델 (Phase A 상세)

**`analyst_reports` (개별 리포트 레코드)**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | autoincrement |
| `symbol` | String(32) | 종목코드, indexed, FK 미사용 (Stock 테이블과 느슨한 연결) |
| `broker_name` | String(64) | 발행 증권사 (예: "삼성증권") |
| `analyst_name` | String(64) nullable | 작성자 이름 |
| `published_at` | Date | 발행일 (KST) |
| `title` | String(200) | 짧은 제목 — 원문 인용 ≤ 200자 (저작권 fair-use 한도) |
| `summary` | String(500) nullable | 운영자가 직접 작성한 한국어 요약 — 원문 paragraph 인용 금지 |
| `rating` | String(16) nullable | enum: `STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL` / null |
| `target_price` | Numeric(20,4) nullable | 목표가 (원) |
| `source_url` | String(500) nullable | 외부 발행처 URL |
| `source_file_path` | String(500) nullable | 운영자 로컬 PDF 경로 — API 응답에는 마스킹 |
| `import_source` | String(16) | enum: `CSV` / `EXCEL` / `MANUAL` |
| `created_at`, `updated_at` | TimestampMixin | |

**Unique constraint**: `(symbol, broker_name, published_at, title)` — 동일 리포트 중복 import 방지.

**`report_consensus_snapshots` (종목별 일별 컨센서스 집계)**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `symbol` | String(32) | indexed |
| `snapshot_date` | Date | 집계 기준일 (KST) |
| `report_count` | Integer | 집계 시점에 활성 리포트 수 (예: 발행 후 90일 이내) |
| `avg_target_price` | Numeric(20,4) nullable | |
| `min_target_price`, `max_target_price` | Numeric(20,4) nullable | |
| `strong_buy_count`, `buy_count`, `hold_count`, `sell_count`, `strong_sell_count` | Integer default 0 | |
| `latest_published_at` | Date nullable | 가장 최신 리포트 발행일 |
| `created_at` | TimestampMixin | |

**Unique constraint**: `(symbol, snapshot_date)`.

**`report_score_logs` (점수 계산 이력)**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `symbol` | String(32) | |
| `calculated_at` | DateTime | UTC |
| `run_id` | Integer FK(`recommendation_runs.run_id`) nullable | 추천 잡과 연계된 경우 |
| `consensus_snapshot_id` | Integer FK(`report_consensus_snapshots.id`) nullable | |
| `report_score` | Numeric(6,2) nullable | 0~100, `report_count = 0` 일 때 null |
| `target_upside_pct` | Numeric(8,4) nullable | (avg_target_price - latest_close) / latest_close * 100 |
| `rating_score_avg` | Numeric(6,4) nullable | -2 ~ +2 |
| `recency_bonus` | Numeric(4,2) nullable | 0 ~ 5 |
| `evidence_json` | JSON | top 3 리포트 메타 (broker / rating / target_price) + raw counts |
| `created_at` | TimestampMixin | |

### `report_score` 산식 (Phase C 상세)

`report_count = 0` → `report_score = null` (점수 산식에 영향 0).

```
target_upside_pct = clip( (avg_target_price - latest_close) / latest_close * 100, -40, +60 )
rating_score_avg  = ( STRONG_BUY*2 + BUY*1 + HOLD*0 + SELL*(-1) + STRONG_SELL*(-2) ) / report_count
recency_bonus = 5  if any report in last 14 days
              = 3  if last 14~30 days
              = 0  otherwise
report_score = clip( 50 + (target_upside_pct * 0.5) + (rating_score_avg * 10) + recency_bonus, 0, 100 )
```

추천 점수 보조:

```
recommendation.total_score_after = clip( recommendation.total_score + report_bonus, 0, 100 )
report_bonus = 0                       if report_score is null
            = clip( (report_score - 50) * 0.1, -5, +5 )   otherwise
```

`±5점 cap` — 기존 weight 산식은 손대지 않고 후처리 가산만. `decision_logs.rule_result_json["report_evidence"]` 에 `{report_score, report_count, top_3, avg_target_price, snapshot_id}` 기록.

### 프런트 노출 (Phase D 상세)

- **StockDetail 화면**: 새 카드 `증권사 리포트 (N건)` — 상단에 컨센서스 요약 (평균 목표가 / BUY 비율 / 최신 발행일 / `report_score`), 하단에 최근 5건 (broker / 발행일 / rating / 목표가 / summary 첫 줄). `source_url` 클릭 → 새 탭. **`source_file_path` 는 응답에 미포함**.
- **Recommendations 화면**: TOP 5 테이블에 `report_score` 컬럼 추가. null 이면 `—` 표시. tooltip 으로 `(target ↑X% · BUY N / HOLD N · 최신 YYYY-MM-DD)` 노출.
- **Today / RecommendationHistory / Holdings / MarketCapTop**: 이번 cycle 에선 변경 없음 (보조 정보의 1차 노출만). v0.5 에서 확장 검토.

### v0.4 누적 태그 (예정)

```
v0.3-final                       ← v0.4 시작점 (HEAD f6b0ba5)
v0.4-backend-reports             ← Phase A 인수 (DB 모델 + repo)
v0.4-import-pipeline             ← Phase B 인수 (CSV/Excel + consensus 잡)
v0.4-report-score                ← Phase C 인수 (score 계산 + decision_logs)
v0.4-frontend-reports            ← Phase D 인수 (UI 통합)
v0.4-final                       ← Phase E 인수 / 마감 선언
```

---

### Phase A — DB 모델 3종 + Repository

**목표:** 증권사 리포트 + 컨센서스 + 점수 로그 ORM / Repository 도입. 코드 라우터 / 잡 / 엔진 / 점수 산식은 손대지 않는다.

**수정할 파일:**

- `app/db/models.py` — `AnalystReport`, `ReportConsensusSnapshot`, `ReportScoreLog` 클래스 3개 신규
- `app/data/repositories/__init__.py` — 3 Repository export
- `app/data/repositories/analyst_reports.py` (신규) — `add` / `get_by_symbol` / `delete_by_id` (admin) + unique 제약 충돌 시 idempotent upsert
- `app/data/repositories/report_consensus_snapshots.py` (신규) — `upsert(symbol, snapshot_date, ...)` + `get_latest_by_symbol`
- `app/data/repositories/report_score_logs.py` (신규) — `add` + `get_latest_by_symbol`
- `tests/unit/test_analyst_report_repository.py` (신규) — 3 Repository 단위 테스트 ~10건 (CRUD, unique 충돌, NULL 처리)
- `DB_SCHEMA.md` — 3 테이블 추가 명세

**수정하지 않을 파일:**

- `app/api/`, `app/decision/`, `app/scheduler/`, `app/notification/`, `frontend/` — 본 phase 에서 변경 없음

**단계:**

1. ORM 클래스 3개 + TimestampMixin 적용
2. Repository 3개 + 단위 테스트
3. `Base.metadata.create_all` 로 검증 DB 마이그레이션 (운영 환경은 ALTER ADD TABLE 만이라 destructive 아님 — 운영자 안내는 RELEASE_NOTES_v0.4 에 명시)
4. `DB_SCHEMA.md` 갱신

**테스트:**

- 단위 테스트 ~10 신규 (analyst_reports CRUD / unique 충돌 / consensus upsert / score_logs add)
- 회귀 게이트: backend `pytest -q` 319 + 신규 → 모두 통과

**완료 기준:**

- backend pytest 통과 (319 + 신규)
- 3 테이블 ORM + Repository 동작 + 단위 테스트 통과
- AGENTS.md 원칙 위반 없음 (외부 호출 0건)

**위험 요소:**

- 신규 테이블 3개 → 운영 환경 마이그레이션 필요. ALTER ADD TABLE 만이라 destructive 아니지만 안내 필수.
- `analyst_reports.title` / `summary` 의 글자 수 한계가 너무 작으면 일부 리포트 import 실패. 실 데이터 1회 sample import 후 재조정 가능.

### Phase B — CSV / Excel import + 일별 컨센서스 스냅샷 잡

**목표:** 운영자가 CLI 로 리포트 메타데이터를 import 하고, 잡이 일별 컨센서스를 자동 스냅샷한다.

**수정할 파일:**

- `scripts/import_analyst_reports.py` (신규) — argparse CLI: `--file path.csv|path.xlsx --broker "삼성증권" --dry-run`. CSV / Excel 양쪽 지원 (`pandas.read_csv` / `read_excel`). 멱등 (unique 충돌 시 skip). DRY_RUN 기본 false 가 아니라 **default true** — `--commit` 명시 시에만 DB 적재.
- `app/scheduler/jobs.py` — `update_report_consensus_snapshots` 잡 신규 (각 종목별 활성 리포트 → 컨센서스 스냅샷 upsert). 기본 매일 06:30 KST.
- `app/scheduler/scheduler.py` — 잡 등록.
- `tests/integration/test_analyst_report_import.py` (신규) — sample CSV (`tests/fixtures/analyst_reports_sample.csv`) 로 import → DB 검증 ~6건
- `tests/integration/test_consensus_snapshot_job.py` (신규) — 잡 1회 실행 → 컨센서스 산정 검증 ~4건
- `INTEGRATION_RUNBOOK.md` — `python -m scripts.import_analyst_reports --file ... --commit` 운영 절차 추가

**수정하지 않을 파일:**

- `app/decision/`, `frontend/` — 본 phase 에서 변경 없음
- 추천 / 보유 잡 — 시그니처 / 산식 손대지 않음

**단계:**

1. CSV/Excel 입력 스키마 정의 (`symbol, broker_name, analyst_name, published_at, title, summary, rating, target_price, source_url, source_file_path`) + sample fixture
2. import CLI (`--dry-run` / `--commit` / `--file` / `--broker` / `--encoding`) — 기본 dry-run, validation 실패 시 row-level 에러 리포트
3. `update_report_consensus_snapshots` 잡 구현 (활성 윈도우 = 발행 후 90일 이내, 그 이상은 컨센서스 제외)
4. 통합 테스트 (sample CSV → import → consensus 잡 → 스냅샷 검증)

**테스트:**

- sample CSV 5~10건 import → analyst_reports 5~10 row, unique 충돌 시 skip count 정확
- 잡 실행 후 종목별 컨센서스: avg_target_price / rating 분포 / latest_published_at
- backend `pytest -q` 회귀 0건

**완료 기준:**

- CLI dry-run + commit 양쪽 동작
- 잡이 종목별 컨센서스 스냅샷을 멱등 upsert
- backend pytest +10건 (import 6 + consensus 4) 통과
- INTEGRATION_RUNBOOK 운영 절차 1줄 추가

**위험 요소:**

- 입력 CSV 인코딩 (한글 broker / analyst 이름) — UTF-8 BOM / EUC-KR 모두 받도록 `--encoding` 옵션
- 활성 윈도우 (발행 후 90일) 가 너무 짧으면 표본 부족. 90일 default + 운영자가 `--active-days` 로 override 가능

### Phase C — `report_score` 계산기 + ScoreProducer 통합 + decision evidence

**목표:** 컨센서스 스냅샷 → `report_score` 계산 → 추천 점수에 ±5점 cap 으로 보조 가산. 추천 산식 본 weight 는 손대지 않는다.

**수정할 파일:**

- `app/analysis/report_score_calculator.py` (신규) — `calculate_report_score(consensus, latest_close) -> ReportScoreResult` 순수 함수
- `app/decision/recommendation_engine.py` — `RecommendationEngine.run` 에서 종목별 `latest_consensus + latest_close` 로 `report_score` 계산 → `report_score_logs` 에 기록 → `recommendation.total_score` 후처리 가산 (±5점 cap)
- `app/decision/recommendation_engine.py` — `decision_logs.rule_result_json["report_evidence"]` 추가
- `app/api/schemas.py` — `RecommendationItemSchema` 에 `report_score: Optional[str]` + `report_evidence: Optional[Dict]` 추가
- `tests/unit/test_report_score_calculator.py` (신규) — 산식 단위 테스트 ~12건 (null / upside / rating / recency / clip 경계)
- `tests/integration/test_recommendation_engine.py` — `report_score` 가산 시나리오 보강 ~3건
- `tests/integration/test_api_routes.py` — `/api/recommendations/latest` 응답에 `report_score` 노출 검증 ~2건

**수정하지 않을 파일:**

- `app/decision/holding_check_engine.py` — HoldingCheck 산식은 v0.4 에서 변경 없음
- `app/decision/scoring_engine.py` — base weight 산식 본체는 안 바꾼다
- `frontend/` — 본 phase 에서 변경 없음 (Phase D 에서 노출)

**단계:**

1. 순수 산식 함수 + 단위 테스트 (mock consensus + close 로 ±5 cap 검증)
2. RecommendationEngine 가 종목별 consensus 조회 → score 계산 → log → bonus 가산
3. `decision_logs` evidence 기록
4. API 스키마 `report_score` 노출 + 통합 테스트
5. mock seed 에 sample report 1~2건 추가하여 실제 흐름 검증 (추천 5종목 중 1~2종목에 `report_score` 표시)

**테스트:**

- 산식 단위: report_count=0 → null / upside +30% + STRONG_BUY 평균 → 90 / 음수 + HOLD → 45 / 14일 이내 발행 → +5 / 14~30일 → +3 / 30일 이상 → 0
- 통합: 추천 잡 → recommendation.total_score 가 ±5 범위 안에서 변동, `report_score_logs` 행 추가, `decision_logs.rule_result_json` 에 evidence
- API: `/api/recommendations/latest` 응답에 `report_score`, `report_evidence`
- 회귀: 기존 추천 / 보유 점검 / 잡 / 통계 테스트 0건 깨짐

**완료 기준:**

- backend pytest +17건 (산식 12 + 추천 통합 3 + API 2) 통과
- mock seed 에서 sample report 1~2건 적용 시 `total_score` ±5 변동 확인
- `decision_logs` 에 evidence JSON 적재 확인

**위험 요소:**

- 추천 score weight 가 갑자기 흔들려 등급 분포가 비정상화 → `±5점 cap + report_count=0 → null` 안전장치로 보호
- consensus 산정 누락 (잡 미실행 / 종목별 데이터 0) → `report_score = null` 로 처리 (점수 산식 영향 0)

### Phase D — 프런트 (StockDetail 리포트 섹션 + 추천 컬럼)

**목표:** StockDetail 화면에 컨센서스 카드 + 최근 리포트 5건, 추천 화면 테이블에 `report_score` 컬럼 추가.

**수정할 파일:**

- `app/api/routes.py` — `GET /api/stocks/{symbol}/reports?limit=10` 신규 read-only 라우터 (`AnalystReport` + 종목별 최신 컨센서스). 또는 `GET /api/stocks/{symbol}` 응답에 `latest_consensus + recent_reports[]` 필드 통합 (택일, PR 시 결정)
- `app/api/schemas.py` — `AnalystReportSchema`, `ReportConsensusSchema` 신규 + `StockDetailResponse` 또는 신규 응답 스키마에 추가
- `tests/integration/test_api_routes.py` — 신규 라우터 happy / empty / 404 ~3건
- `frontend/src/api/types.ts` — `AnalystReport`, `ReportConsensus` 타입 추가
- `frontend/src/hooks/useStockReports.ts` (신규) — `useQuery`, staleTime 5분
- `frontend/src/pages/StockDetail/AnalystReportsCard.tsx` (신규) — 컨센서스 요약 + 최근 5건 테이블, source_url 클릭 가능, `source_file_path` 미노출
- `frontend/src/pages/StockDetail/index.tsx` — 차트 카드 다음에 리포트 카드 추가
- `frontend/src/pages/Recommendations/RecommendationsTable.tsx` (또는 해당 컬럼 정의) — `report_score` 컬럼 + tooltip
- `frontend/src/tests/StockDetail.test.tsx` — 리포트 카드 happy / empty / 보조 source_file_path 부재 검증 ~3건
- `frontend/src/tests/Recommendations.test.tsx` — `report_score` 컬럼 노출 + null fallback 검증 ~1건
- `frontend/src/tests/mswServer.ts` + `frontend/e2e/fixtures/apiMocks.ts` — handler / fixture 추가
- `frontend/e2e/dashboard.spec.ts` — 리포트 카드 노출 + source_file_path 부재 e2e ~1건

**수정하지 않을 파일:**

- `app/decision/`, `app/scheduler/` — 본 phase 에서 변경 없음
- Today / RecommendationHistory / Holdings / MarketCapTop — 보조 정보 1차 노출만, 후속 cycle 에서 검토

**단계:**

1. 백엔드 신규 라우터 + 통합 테스트
2. 프런트 hook + 타입 + AnalystReportsCard
3. StockDetail 통합 + 테스트
4. Recommendations `report_score` 컬럼 + 테스트
5. e2e: 리포트 카드 + source_file_path 부재 (마스킹 정책 검증)

**테스트:**

- backend pytest +3
- frontend vitest +4
- e2e +1
- mock seed 에서 1~2 종목에 sample report → StockDetail 시각 확인

**완료 기준:**

- StockDetail 에서 리포트 카드 (컨센서스 + 최근 5건) 노출
- 추천 화면 테이블에 `report_score` 컬럼 + null fallback `—`
- `source_file_path` 가 API 응답 / 프런트 / e2e 모두에서 0건 노출 (마스킹 정책)
- 회귀 게이트 모두 그린

**위험 요소:**

- StockDetail 카드 추가 → 페이지 청크 +N kB. lazy 로드는 페이지 단위로 이미 적용되어 있어 영향 제한적
- `source_file_path` 노출 누락 검증 → e2e 에서 명시적 부재 단언으로 보호

### Phase E — v0.4 릴리스 문서

**목표:** v0.4 인수 종료 선언, 산출물 / 검증 / 제외 / 한계 / v0.5 후보 / 운영 가이드 / 보안 (저작권 정책 명시) 정리.

**수정할 파일:**

- `RELEASE_NOTES_v0.4.md` (신규) — 7 섹션 (산출물 / 검증 / 제외 범위 / 알려진 한계 / v0.5 후보 / 운영 가이드 / **저작권·보안**)
- `README.md` — 상단 인용 블록 v0.4 마감 갱신 + 누적 태그 라인 + 저작권 한 줄
- `PROJECT_STATUS.md` — §0 v0.4 마감 선언, 기존 §0 v0.4 시작 → §0 v0.4 마감으로 in-place 갱신, §0-1 v0.3 마감, §0-2 v0.2, §0-3 v0.1
- `TASKS.md` — Phase A~E 모두 [x]

**단계:**

1. 모든 phase 통과 / 회귀 게이트 통과 후
2. `RELEASE_NOTES_v0.4.md` 작성 (저작권 정책 명시 — 원문 본문 미저장 / 자동 크롤링 미구현 / source_file_path 마스킹)
3. README / PROJECT_STATUS / TASKS 동기화
4. tag `v0.4-final` 부여 + GitHub push

**테스트:**

- 코드 변경 없음. 단 release 직전 backend pytest + frontend vitest + e2e + build 4 게이트 마지막 1회 실행

**완료 기준:**

- `RELEASE_NOTES_v0.4.md` 작성 완료
- 4 게이트 모두 그린
- tag `v0.4-final` push 완료
- README 마감 배너 갱신

**위험 요소:**

- 저작권 한계 명시 누락 → `RELEASE_NOTES_v0.4.md` §보안 섹션을 정책 4 항목 (원문 미저장 / PDF 미저장 / 자동 크롤링 금지 / 외부 공유 금지) 으로 명시
