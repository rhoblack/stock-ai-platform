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

- 실 News / Supply / Fundamental / Earnings 파이프라인 (DummyScoreProducer 대체)
- 즐겨찾기 / 관심 종목 (POST 라우터 도입 — backend 정책 변경)
- 글로벌 검색 (cmd+k)
- 인증 / 권한 (사내망 외 노출 시)
- Sentry / Prometheus 운영 모니터링
- 자동매매 (별도 보안 / 컴플라이언스 cycle 선행 필수): MockBroker → APPROVAL → SMALL_AUTO
