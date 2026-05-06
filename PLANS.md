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

## PLAN-0004: v0.4 Analyst & Theme Intelligence (5 Phase)

> **2026-05-05 갱신**: 원안 (3 모델: analyst_reports / consensus / score_logs) 에서
> 6 모델로 확장. 기업 리포트뿐 아니라 산업 / 테마 / 원자재 / 매크로 / 전략
> 리포트까지 포괄하고, 테마 (`report_themes`) → 종목 (`theme_stock_mappings`) 매핑과
> 변화 시그널 (`report_signal_events`) 을 별도 테이블로 분리한다. v0.4 의 핵심은
> "기업 리포트 점수화" 가 아니라 "리포트에서 추출한 테마·시그널을 활용한 선행
> 신호 인텔리전스" 로 재정의되었다.

### 기준선

- 시작 태그: `v0.3-final` (HEAD `f6b0ba5` 시점, origin/main 동기화 완료)
- v0.1 backend / v0.2 frontend / v0.3 분석·운영 모두 인수 완료. 회귀 게이트: backend pytest 319, frontend vitest 59, e2e 8, build 통과
- v0.4 는 v0.3-final 기준선 위에 **증권사 애널리스트 리포트 데이터 라인** 을 신규 추가한다. 자동매매 / 실 주문 / FULL_AUTO / POST 트리거 / 인증 정책은 v0.3 그대로 유지한다 (여전히 사내망 / 단일 사용자 / read-only 가정)

### 목표

(1) 기업 / 산업 / 테마 / 원자재 / 매크로 / 전략 리포트 메타데이터를 CSV / Excel 로
import 하고, (2) 리포트에서 추출한 **투자 테마** 와 **테마 → 종목 매핑** 을
저장하며, (3) 목표가 상향 / 공급 부족 / 수요 회복 같은 **변화 시그널 이벤트** 를
구조화하고, (4) 기업 리포트 기반 종목별 **컨센서스 스냅샷** 을 일별 갱신하며,
(5) 보조 점수 `report_score` (기업 리포트) + `theme_signal_score` (테마·시그널
기반 선행 신호) 를 계산해 추천 화면 / 종목 상세에 참고 근거로 노출한다. 추천 최종
산식은 급격히 바꾸지 않고 ±5점 cap 보조 가산만 한다.

### 핵심 제약 (저작권 / 컴플라이언스)

- ❌ 리포트 원문 전문 (PDF body, 본문 paragraph) DB 저장 금지 — 메타데이터 + 운영자가 직접 작성한 짧은 요약 (`<= 500자`) 만
- ❌ PDF 파일 자체를 git 레포 / DB BLOB 으로 저장 금지 — `source_url` (외부 발행처 URL) 또는 `source_file_path` (운영자 로컬 경로) 만 보관
- ❌ 자동 크롤링 / 스크레이핑 금지 — v0.4 는 CSV/Excel 수동 import 만. 자동 fetch 는 v0.5+ (저작권 검토 선행)
- ❌ 외부 공유 / 공개 — `source_file_path` 는 admin-only 응답 또는 마스킹 (예: `D:\reports\****`). API 외부 노출 시 path 노출 금지
- ❌ 추천 산식 급변경 — `report_score` 는 보조 (±5점 cap), `total_score` 의 본 weight (technical 50% / news 10% / supply 10% / fundamental 10% / ai 20%) 는 손대지 않음

### 범위 (5 Phase)

- Phase A — **DB 모델 6종 + Repository** (analyst_reports / report_themes / theme_stock_mappings / report_signal_events / report_consensus_snapshots / report_score_logs) + 통합 테스트 16건
- Phase B — CSV / Excel import 명령 (`scripts/import_analyst_reports.py` + 테마 / 매핑 / 시그널 import) + 일별 컨센서스 스냅샷 잡 + 통합 테스트
- Phase C — `report_score` (기업 리포트 기반) + `theme_signal_score` (테마·시그널 기반 선행 신호) 계산기 + RecommendationEngine 통합 (보조 ±5점 cap) + decision_logs evidence 기록
- Phase D — 프런트 (StockDetail 리포트·테마·시그널 카드 + 추천 화면 score 컬럼) + msw / e2e fixture
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

### 데이터 모델 (Phase A 상세 — 6 테이블, 실제 적용된 스키마)

세부 컬럼 명세는 [`DB_SCHEMA.md`](./DB_SCHEMA.md) §18~23 참조. 본 섹션은 v0.4
설계 의도 / 관계 / 저작권 정책만 요약한다.

**관계**:

```
analyst_reports (1) ─── (N) report_themes
                  │
                  └─ (N) report_signal_events ─── (N) report_themes (theme_id, nullable)
                                                          │
                                                          └─ (N) theme_stock_mappings
report_consensus_snapshots ── unique(symbol, snapshot_date, window_days)
report_score_logs ── nullable FK → recommendation_runs.run_id
```

**테이블 6종 한 줄 요약**:

| 테이블 | 역할 | Unique |
|---|---|---|
| `analyst_reports` | 모든 리포트 메타 (COMPANY/SECTOR/INDUSTRY/THEME/COMMODITY/MACRO/STRATEGY) — 원문 본문 미저장 | `(broker_name, published_at, title)` |
| `report_themes` | 리포트에서 추출한 투자 테마 (HBM, 구리부족, AI 데이터센터 …) | `(source_report_id, theme_name)` |
| `theme_stock_mappings` | 테마 → 종목 영향 매핑 (`impact_direction`, `impact_path`, `relation_type`) — 글로벌 ticker 포함 | `(theme_id, symbol)` |
| `report_signal_events` | 변화 시그널 이벤트 (TARGET_PRICE_UP, SUPPLY_SHORTAGE, RISK_WARNING …) — `evidence_json` 포함 | `(report_id, event_type, symbol, theme_id)` |
| `report_consensus_snapshots` | 일별 컨센서스 집계 (window_days 별) | `(symbol, snapshot_date, window_days)` |
| `report_score_logs` | `report_score` + `theme_signal_score` 계산 이력 | `(symbol, score_date, recommendation_run_id)` |

**저작권 정책 (모든 테이블 공통)**:

- 원문 본문 (PDF body / paragraph) 저장 0건 — `summary` / `positive_points` / `risk_points` / `source_sentence_summary` 는 모두 **운영자가 직접 작성한 짧은 요약** (≤ 500자) 만 허용
- PDF BLOB DB 저장 0건 — `source_url` (외부 URL) 또는 `source_file_path` (운영자 로컬 경로) 만 보관
- `source_file_path` 는 API 응답 / 프런트 / e2e 어디서도 노출하지 않는다 (Phase D 의 schema 마스킹으로 보강)
- 자동 크롤링 0건 — 모든 import 는 수동 (`extraction_method` 필드로 출처 태깅: `MANUAL` / `CSV_IMPORT` / `RULE_BASED` / `LLM_ASSISTED`)
- LLM 자동 요약은 **Phase A 에서 미구현** — 미래에 붙일 수 있도록 `extraction_method` 와 `extraction_confidence` (0~1) 필드만 미리 둠

### `report_score` + `theme_signal_score` 산식 (Phase C 상세)

**(1) `report_score` — 기업 리포트 기반.** `report_count = 0` → null.

```
target_upside_pct = clip( (avg_target_price - latest_close) / latest_close * 100, -40, +60 )
rating_score_avg  = ( STRONG_BUY*2 + BUY*1 + HOLD*0 + SELL*(-1) + STRONG_SELL*(-2) ) / report_count
recency_bonus     = 5 (≤14d) / 3 (14~30d) / 0 (>30d)
report_score      = clip( 50 + (target_upside_pct * 0.5) + (rating_score_avg * 10) + recency_bonus, 0, 100 )
```

**(2) `theme_signal_score` — 테마·시그널 기반 선행 신호.** 종목별로 활성 테마 매핑
(`theme_stock_mappings.impact_direction`) + 시그널 이벤트 (`report_signal_events.direction`)
를 가중 평균. 신호 없으면 null.

```
theme_bonus  = sum( impact_strength * 가중치(direction) ) / theme_count    # POSITIVE +1, NEGATIVE -1, MIXED 0
event_bonus  = sum( strength * 가중치(direction) ) / event_count           # 동일 가중치
recency_bonus = 5 (≤14d 발행 리포트의 시그널) / 3 (14~30d) / 0 (>30d)
risk_penalty  = clip( count(RISK_WARNING) * 2.5, 0, 10 )
theme_signal_score = clip( 50 + theme_signal_bonus + event_signal_bonus - risk_penalty, 0, 100 )
```

**(3) 추천 점수 보조 (±5점 cap, 두 점수 합산):**

```
recommendation.total_score_after = clip( total_score + report_bonus + theme_bonus, 0, 100 )
report_bonus = clip( (report_score - 50) * 0.1, -5, +5 )       if report_score is not null else 0
theme_bonus  = clip( (theme_signal_score - 50) * 0.1, -5, +5 ) if theme_signal_score is not null else 0
```

기존 weight 산식 (technical 50% / news 10% / supply 10% / fundamental 10% / ai 20%) 은
**손대지 않고 후처리 가산만**. `decision_logs.rule_result_json["report_evidence"]`
에 `{report_score, theme_signal_score, report_count, theme_count, signal_event_count, top_brokers, top_themes, top_events, snapshot_id}` 기록.

### 프런트 노출 (Phase D 상세)

- **StockDetail 화면**: 3 카드 추가 — (1) `증권사 리포트 (N건)` 컨센서스 + 최근 5건 (broker / 발행일 / rating / 목표가 / summary), (2) `관련 테마 (N건)` 종목에 영향을 주는 활성 테마 (theme_name / category / direction / impact_path / time_lag), (3) `시그널 이벤트 (N건)` 최근 시그널 (event_type / direction / strength / summary). 모두 `source_url` 클릭 가능, `source_file_path` 는 응답 / 화면 어디에도 미노출.
- **Recommendations 화면**: TOP 5 테이블에 `report_score` 와 `theme_signal_score` 두 컬럼 추가. null fallback `—`. tooltip 으로 evidence 짧게 노출.
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

### Phase A — DB 모델 6종 + Repository ✅ 인수

**목표:** Analyst & Theme Intelligence 의 6 테이블 + Repository + 통합 테스트.
라우터 / 잡 / 엔진 / 점수 산식은 손대지 않는다.

**산출 (실제 적용된 파일):**

- `app/db/models.py` — `AnalystReport`, `ReportTheme`, `ThemeStockMapping`, `ReportSignalEvent`, `ReportConsensusSnapshot`, `ReportScoreLog` 6 클래스 신규. 모두 SQLAlchemy 2.0 `Mapped[T] + mapped_column` 스타일. `relationship` 으로 `AnalystReport.themes` / `signal_events`, `ReportTheme.stock_mappings` / `signal_events` 연결 (cascade `all, delete-orphan` 적용)
- `app/data/repositories/analyst_reports.py` (신규) — `create` / `get_by_id` / `get_by_unique` / `upsert_unique` / `list_by_symbol` / `list_by_report_type` / `list_recent` / `list_recent_by_broker` / `search_text`
- `app/data/repositories/report_themes.py` (신규) — `create` / `upsert_by_report_and_theme` / `list_recent` / `list_by_category` / `list_by_direction` / `list_by_source_report`
- `app/data/repositories/theme_stock_mappings.py` (신규) — `create` / `upsert_by_theme_and_symbol` / `list_by_theme` / `list_by_symbol` / `list_positive_by_symbol` / `list_negative_by_symbol` / `list_by_impact_path`
- `app/data/repositories/report_signal_events.py` (신규) — `create` / `upsert_by_report_event_symbol_theme` / `list_by_symbol` / `list_by_theme` / `list_by_event_type` / `list_recent` / `list_positive_by_symbol` / `list_negative_by_symbol`
- `app/data/repositories/report_consensus_snapshots.py` (신규) — `upsert_by_symbol_date_window` (window_days 별 분리 저장) / `get_latest_by_symbol` / `list_recent`
- `app/data/repositories/report_score_logs.py` (신규) — `create` / `get_latest_by_symbol` / `list_recent_by_symbol` / `list_by_recommendation_run`
- `app/data/repositories/__init__.py` — 6 Repository export 추가 (alphabetical 정렬 유지)
- `tests/integration/test_analyst_report_repositories.py` (신규, **16 케이스**)
- `DB_SCHEMA.md` — §18~23 신규 (6 테이블 명세 + 저작권 정책 명시)

**수정하지 않은 파일 (정책 준수):**

- `app/api/`, `app/decision/`, `app/scheduler/`, `app/notification/`, `frontend/` — 0건
- 추천 / 보유 / scoring / KIS / 텔레그램 관련 코드 0건

**Phase A 단계:**

1. 6 ORM 클래스 + TimestampMixin (4개) / 별도 `created_at` (2개: ReportConsensusSnapshot, ReportScoreLog) — spec 일치
2. 6 Repository + 단위 / 통합 테스트 16건
3. `__init__.py` export 갱신
4. `DB_SCHEMA.md` §18~23 추가 (저작권 한 단락 명시)
5. 단일 `Base.metadata.create_all` 로 검증 DB 자동 마이그레이션 (운영 안내는 §운영 환경 마이그레이션 박스에 명시)

**테스트 결과:**

- backend pytest **319 → 335 passed (+16)**, 회귀 0건
- 16 케이스 분포: AnalystReport 6 (CRUD / unique / 글로벌 US 종목 / null symbol / 타입별 / search) + ReportTheme 2 + ThemeStockMapping 2 + ReportSignalEvent 2 + Consensus 1 + ScoreLog 2 + 메타 1

**완료 기준 (모두 충족):**

- backend pytest 통과 (335)
- 6 테이블 ORM + Repository 동작
- AGENTS.md 원칙 위반 0건 (외부 호출 / 라우터 / 잡 / 산식 변경 0건)

**위험 요소 (해소 / 잔존):**

- 신규 테이블 6개 → 운영 환경 마이그레이션 필요. `CREATE TABLE` 만이라 destructive 0건, 안내는 `DB_SCHEMA.md` 박스에 명시 (해소)
- `report_signal_events` unique `(report_id, event_type, symbol, theme_id)` 에서 NULL 은 distinct (SQLite/PG default) — 향후 NULLS NOT DISTINCT 가 필요하면 v0.5 에서 검토 (잔존, 영향 미미)
- `analyst_reports.title` 길이 255 / `summary` 500 — 실 import 시 부족하면 Phase B 직전에 ALTER COLUMN 으로 확장 가능 (잔존, low risk)

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

---

## PLAN-0005: v0.5 News, Disclosure & Theme Ranking (5 Phase)

### 기준선

- 시작 태그: `v0.4-final` (HEAD `0f25be6` 시점, origin/main 동기화 완료)
- v0.1 ~ v0.4 모두 인수 완료. 회귀 게이트: backend pytest **382**, frontend vitest **60**, e2e **9**, build 통과
- v0.5 는 v0.4-final 위에 **News / Disclosure 데이터 라인** + **테마 랭킹 화면** 을 신규 추가한다. v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 (본문 paragraph 미저장 / 자동 크롤링 default OFF) 모두 그대로 유지한다.

### 후보 비교 (v0.5 진입 시점 기준)

| # | 후보 | 가치 | 난이도 | 위험 | 의존성 | v0.5 채택 |
|---|---|---|---|---|---|---|
| 1 | News / 공시 실제화 | 높음 (DummyScoreProducer.news_score 25% weight 첫 real 화) | 중 (NewsItem 테이블 v0.1 부터 존재, collector 신규) | 중 (외부 source 의존 / 저작권) | KIS placeholder method 부재 → 신규 collector | ✅ 채택 (Phase A·B·C) |
| 2 | 재무 / 실적 점수 실제화 | 높음 (장기 가치) | 높음 (DART API + 신규 테이블 2종) | 높음 (재무제표 파싱 정확성) | FundamentalSnapshot / EarningsSnapshot 신규 | ❌ v0.6 후보 (DART 학습 비용 별도 cycle 필요) |
| 3 | 리포트 인텔리전스 고도화 | 중 (v0.4 산식 미세 튜닝) | 낮음~중 | 낮음 | v0.4 인프라 그대로 | △ 부분 채택 (Phase D — `/themes` 화면 + impact_path 가시화) |
| 4 | 관심종목 / Watchlist | 중 (UX) | 중 (POST 라우터 + 인증) | 중 (백엔드 read-only 정책 깨기) | 인증 의존 | ❌ v0.6 후보 (POST 도입은 인증 사이클과 묶음) |
| 5 | 인증 / 보안 | 중 (POST 의 전제) | 중-높음 | 중 (잘못 설계 시 보안 구멍) | — | ❌ v0.6 후보 (Watchlist 와 묶어서) |
| 6 | 전략 / 백테스트 기초 | 중 (장기) | 매우 높음 | 중 | Strategy ABC 부재 | ❌ v0.7+ 후보 (실 News + 재무 데이터 후행) |
| 7 | 자동매매 / 실 주문 | (위험) | 매우 높음 | 매우 높음 | 모든 위 + 컴플라이언스 | ❌ Future Backlog (별도 보안 / 컴플라이언스 사이클 선행) |

### 시나리오 옵션

**Scenario X — 데이터 + UX 균형 (권장 ✅)**

- Phase A: News data layer (collector + provider ABC + collect_news 잡 19:00 KST)
- Phase B: Disclosure subset (DART / 공시 메타 + 분류 + collect_disclosures 잡 20:00 KST)
- Phase C: `RealNewsScoreProducer` + `DisclosureRiskProducer` + `ScoreProducerInterface` ABC 추출 + RecommendationEngine 통합
- Phase D: 테마 랭킹 화면 + 종목→테마 reverse view + StockDetail 영향 설명 강화
- Phase E: 마감

**Scenario Y — News/Disclosure deep**

- Phase A: News provider + 1 RSS source
- Phase B: Disclosure provider + DART subset
- Phase C: news_score sentiment 분석 (룰 기반 + cluster dedup)
- Phase D: disclosure_event → RiskEngine 보강 (RISK_DISCLOSURE risk_flag 추가, risk_penalty 가산)
- Phase E: 마감
- 테마 랭킹 화면은 v0.6 으로 미룸 — 백엔드만 깊게 작업

**Scenario Z — Theme/Report intelligence deep**

- Phase A: 리포트 신뢰도 / broker_country 가중치 / 중복 검출 강화
- Phase B: 테마 랭킹 알고리즘 (활성도 / impact_strength / recency 결합)
- Phase C: `/themes` 화면 + 종목 영향 설명 강화
- Phase D: report_score / theme_signal_score 산식 미세 튜닝 (recency exponential decay)
- Phase E: 마감
- News / 공시는 v0.6 으로 미룸 — 화면 / 산식 미세 조정 위주

**최종 추천**: **Scenario X**. 이유:

- 사용자 기본 추천과 정렬 (뉴스/공시 + 리포트·테마 인텔리전스 + 테마 랭킹)
- DummyScoreProducer 의 5 컴포넌트 (news / supply / fundamental / earnings / ai) 중 가장 가치가 큰 `news_score` (가중치 25%) 를 첫 real 화 — 추천 점수 품질에 가장 큰 영향
- v0.4 의 테마·시그널 데이터가 v0.5 까지 surface 0 인 상태인데 `/themes` 화면으로 첫 노출 — 누적 데이터의 가시성 회복
- Y 는 백엔드만 두꺼워지고 화면 정체, Z 는 데이터 layer 정체 — 둘 다 누적 가치 손실
- 재무 / Watchlist / 인증은 별도 cycle 로 분리하는 게 검증 / 정책 / 일정 모두 안전

### 범위 (5 Phase)

- **Phase A** — News data layer + collector skeleton (`NewsProviderInterface` ABC + `FakeNewsProvider` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 19:00 KST + 단위 / 통합 테스트)
- **Phase B** — Disclosure subset + 분류 + 종목 매핑 (`DisclosureProviderInterface` + Fake provider + `news_items.category` 활용 + `collect_disclosures` 잡 20:00 KST + 단위 / 통합 테스트)
- **Phase C** — `RealNewsScoreProducer` + `DisclosureRiskProducer` + `ScoreProducerInterface` ABC 추출 + RecommendationEngine 통합 (Dummy → Real news_score, RiskEngine 의 `RISK_DISCLOSURE` flag 추가) + decision_logs evidence 확장
- **Phase D** — 백엔드 `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) + 프런트 `/themes` 9번째 화면 + StockDetail 영향 설명 강화 + msw / e2e fixture
- **Phase E** — `RELEASE_NOTES_v0.5.md` 신규 + README / PROJECT_STATUS / TASKS 마감 + tag `v0.5-final`

### 제외 범위 (v0.5 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.4 일관 정책)
- ❌ 뉴스 / 공시 본문 (paragraph) DB 저장 — title / URL / 메타데이터 / 분류 / sentiment 라벨만
- ❌ 자동 fetch default ON — `Settings.news_collection_enabled` / `disclosure_collection_enabled` = false (운영자 명시 enable)
- ❌ 재무 / 실적 점수 실제화 — v0.6 후보 (DART 재무제표 파싱은 별도 cycle)
- ❌ 관심종목 / Watchlist / 인증 — v0.6 후보 (POST 도입은 인증 사이클과 묶음)
- ❌ Strategy / Backtest / MockBroker — v0.7+ 후보 (실 News + 재무 데이터 후행)
- ❌ HoldingCheckEngine 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 — `news_score` 가 50 → real 로 교체되지만 weight 25% 그대로
- ❌ KIS API 외 외부 자격증명 추가 — 무료 RSS / DART 공공 API 만 (default OFF)
- ❌ LLM 자동 sentiment 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.6+ 후보

### 데이터 모델 변경 (Phase A 상세)

**`news_items` 컬럼 1개 추가** (ALTER ADD COLUMN, nullable):

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `category` | String(32) nullable | NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER. v0.1 부터 존재한 `theme` / `sentiment` / `importance` 는 그대로 유지. |

신규 테이블 0건 — 기존 `news_items` 테이블을 News + Disclosure 양쪽에 활용 (`category` 컬럼으로 구분). 운영 환경 마이그레이션 = `ALTER TABLE news_items ADD COLUMN category VARCHAR(32);` 한 줄, destructive 0건.

### Score 산식 (Phase C 상세)

**`news_score` 산식** — `RealNewsScoreProducer`:

```
recency_factor = sum_{news in last 7d} (
    weight_by_age * sentiment_mapping(news.sentiment)
)
weight_by_age = 1.0 (≤24h) / 0.7 (≤3d) / 0.3 (≤7d)
sentiment_mapping = POSITIVE: +1, NEUTRAL: 0, NEGATIVE: -1, UNKNOWN: 0
news_score = clip( 50 + recency_factor * 5 / news_count, 0, 100 )

# news_count = 0 → 50 (placeholder behavior 유지, dummy 와 호환)
```

**`disclosure_signal`** — `DisclosureRiskProducer` (RiskEngine 보강):

```
risk_disclosures = filter(news_items, category=RISK_DISCLOSURE, last 14d)
if risk_disclosures non-empty:
    add risk_flag "RISK_DISCLOSURE" to risk_assessment.flags
    risk_penalty += min(risk_disclosures_count * 3, 10)  # cap +10
```

**추천 점수 통합**: `DummyScoreProducer.score_recommendation` 의 `news_score = 50` placeholder 자리에 `RealNewsScoreProducer` 결과 대입. 본 weight (technical 35% + news 25% + supply 15% + fundamental 15% + ai 10% - risk_penalty) 산식은 손대지 않는다. `decision_logs.rule_result_json["news_evidence"]` 추가 (top 3 news / sentiment 분포 / recency).

### 프런트 노출 (Phase D 상세)

- **신규 화면 `/themes` (9번째 화면)** — 활성 테마 랭킹 (최근 30일 발행 리포트 기준). 컬럼: theme_name / theme_category / direction / report_count / mapping_count / signal_event_count / avg_impact_strength / latest_published_at. 검색 / 카테고리 필터 / direction 필터.
- **테마 상세 (`/themes/:id`)** — 테마 메타 + 매핑된 종목 리스트 (impact_direction / impact_path / time_lag) + 최근 시그널 이벤트 5건. 종목 클릭 시 StockDetail 로 이동.
- **StockDetail 의 "관련 테마" 카드 강화** — 기존 v0.4 카드에 `impact_path` icon (DEMAND_INCREASE / SUPPLY_SHORTAGE / COST_PRESSURE 등 11종) + reason 한 줄 가시화 추가. 테마 클릭 시 `/themes/:id` 로 이동.
- **사이드바 nav 9번째 메뉴** — "테마 (β)" 추가 (v0.5 에서 첫 surface 라 베타 라벨).
- **기존 8 화면 변경 0건** — Today / Recommendations / History / Holdings / MarketCapTop / Jobs / Settings 손대지 않음.

### v0.5 누적 태그 (예정)

```
v0.4-final                      ← v0.5 시작점 (HEAD 0f25be6)
v0.5-news-collector             ← Phase A 인수 (NewsCollector + collect_news 잡)
v0.5-disclosure-pipeline        ← Phase B 인수 (Disclosure subset + collect_disclosures 잡)
v0.5-news-score                 ← Phase C 인수 (RealNewsScoreProducer + RiskEngine 보강)
v0.5-frontend-themes            ← Phase D 인수 (/themes 화면 + StockDetail 영향 강화)
v0.5-final                      ← Phase E 인수 / 마감 선언
```

### v0.6+ 후보 (Backlog 등재용)

- 실 재무 / 실적 점수 (PER/PBR/EPS/ROE + DART 재무제표 파싱) — `FundamentalSnapshot` / `EarningsSnapshot` 신규
- 인증 / API key + Watchlist (POST 첫 도입)
- LLM 보강 (analyst report 자동 요약 + news sentiment LLM 보강)
- News/Disclosure 출처 다중화 (RSS 다중 + 외부 API)
- KRX 휴장일 자동 fetch
- 운영 모니터링 (Sentry / Prometheus / Grafana)
- 모바일 / 태블릿 레이아웃
- 자동매매 (별도 보안 / 컴플라이언스 cycle 선행 필수): MockBroker → APPROVAL → SMALL_AUTO

---

### Phase A — News data layer + collector skeleton

**목표:** `news_items` 테이블에 처음으로 데이터가 채워지는 read-only 수집 파이프라인. 기본 default OFF — 운영자가 `.env` 에 `NEWS_COLLECTION_ENABLED=true` 명시 시에만 동작.

**수정할 파일:**

- `app/data/interfaces.py` — `NewsProviderInterface` ABC 추가 (`fetch_news(start_time, end_time, symbols=None) -> list[NewsItemDTO]`)
- `app/data/dtos.py` — `NewsItemDTO` dataclass 추가
- `app/data/collectors/news_collector.py` (신규) — `NewsCollector` 서비스. provider → normalize → `NewsItemRepository.upsert` 흐름. 멱등 (URL hash unique).
- `app/data/collectors/__init__.py` — 신규 export
- `app/db/models.py` — `NewsItem.category: String(32) nullable` ALTER ADD COLUMN
- `app/data/repositories/news_items.py` — `upsert_by_url` / `list_recent_by_symbol` / `list_by_category_and_date` 메서드 추가
- `app/scheduler/jobs.py` — `collect_news` 잡 신규. 활성 시 19:00 KST 에 NewsCollector 실행. NEWS_COLLECTION_ENABLED=false 시 NO_DATA + status=SUCCESS.
- `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_NEWS` 등록 (8번째 잡, 19:00 KST)
- `app/config/settings.py` — `news_collection_enabled: bool = False` 추가
- `tests/mocks/fake_news_provider.py` (신규) — `FakeNewsProvider` for tests
- `tests/integration/test_news_collector.py` (신규) — happy / 멱등 / NEWS_COLLECTION_ENABLED 분기 / unknown symbol 처리 ~5건
- `tests/integration/test_scheduler_jobs.py` — registry 7 → 8 jobs 갱신 + `collect_news` 시간 검증
- `DB_SCHEMA.md` — `news_items` §9 에 `category` 컬럼 추가 명시

**수정하지 않을 파일:**

- `app/decision/`, `app/notification/`, `frontend/` — 본 phase 에서 변경 없음
- KIS / Telegram 관련 코드 0건 (NewsCollector 는 별도 provider)

**단계:**

1. `NewsProviderInterface` ABC + `NewsItemDTO` + `FakeNewsProvider` (mock-only)
2. `NewsCollector` 서비스 + 단위 / 통합 테스트
3. `news_items.category` ALTER ADD COLUMN
4. `Settings.news_collection_enabled = False` (default OFF) + 잡 등록
5. `tests/integration/test_scheduler_jobs.py` 의 7 jobs registry → 8 jobs

**테스트:**

- 단위: `NewsCollector` happy / 빈 응답 / 잘못된 url skip / sentiment / theme 정규화
- 통합: NEWS_COLLECTION_ENABLED=false → 잡이 NO_DATA 로 SUCCESS 반환, 행 0건
- 통합: NEWS_COLLECTION_ENABLED=true + FakeNewsProvider → 행 N건 upsert, 멱등 재실행 시 추가 행 0건
- 회귀: backend pytest 382 + 신규 → 모두 통과

**완료 기준:**

- backend pytest 382 → ~390 passed
- `news_items` 에 FakeNewsProvider 데이터 정상 적재
- 8번째 잡 `collect_news` (19:00 KST) 등록 + DEFAULT_SCHEDULE 노출
- 외부 호출 0건 (NEWS_COLLECTION_ENABLED=false default)
- 태그 `v0.5-news-collector`

**위험 요소:**

- `news_items.url` unique 제약 (현재 nullable) — `upsert_by_url` 의 NULL 처리 명시
- 외부 source 의존 → v0.5 는 FakeNewsProvider + 1 free RSS 만, 자동 fetch default OFF
- 잡 시간 충돌 — 19:00 비어 있음 (확인 완료)

### Phase B — Disclosure subset + 분류 + 종목 매핑

**목표:** 공시 메타데이터 수집 + 카테고리 분류 (EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER). DART API 자동 fetch 는 default OFF, 수동 / Fake provider 위주.

**수정할 파일:**

- `app/data/interfaces.py` — `DisclosureProviderInterface` ABC
- `app/data/dtos.py` — `DisclosureItemDTO` dataclass
- `app/data/collectors/disclosure_collector.py` (신규) — `DisclosureCollector` + 분류 함수 (룰 기반: keyword → category)
- `app/data/collectors/__init__.py` — export 추가
- `app/scheduler/jobs.py` — `collect_disclosures` 잡 (20:00 KST)
- `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_DISCLOSURES` (9번째 잡)
- `app/config/settings.py` — `disclosure_collection_enabled: bool = False`
- `tests/mocks/fake_disclosure_provider.py` (신규)
- `tests/integration/test_disclosure_collector.py` (신규, ~6 케이스)
- `tests/integration/test_scheduler_jobs.py` — 9 jobs registry 갱신
- `INTEGRATION_RUNBOOK.md` — §10 News / Disclosure 운영 절차 추가

**테스트:**

- 단위: 분류 룰 (keyword → category) 정확성 (실적공시 → EARNINGS_REPORT, 주식 등 대량보유 → OWNERSHIP_CHANGE, 거래정지 → RISK_DISCLOSURE 등)
- 통합: Fake provider 활성 시 N건 upsert, 분류 정확도, 멱등성

**완료 기준:**

- backend pytest ~390 → ~398 passed
- 9번째 잡 `collect_disclosures` 등록
- 태그 `v0.5-disclosure-pipeline`

**위험 요소:**

- DART API rate limit / 한국어 분류 정확도 → v0.5 는 룰 기반 keyword 매칭 + 운영자 검토. LLM 분류는 v0.6+ 후보.

### Phase C — `RealNewsScoreProducer` + RiskEngine 보강

**목표:** DummyScoreProducer 의 `news_score = 50` placeholder 를 real 산식으로 교체. RiskEngine 에 `RISK_DISCLOSURE` flag 추가.

**수정할 파일:**

- `app/analysis/score_producers.py` — `ScoreProducerInterface` ABC 추출. `DummyScoreProducer` 는 ABC 구현체로 유지. `RealNewsScoreProducer` 신규.
- `app/decision/risk_engine.py` — `evaluate_recommendation` / `evaluate_holding` 에 `risk_disclosure_count` 입력 + `RISK_DISCLOSURE` flag 처리 (penalty +N, max +10)
- `app/decision/recommendation_engine.py` — score_producer 가 ABC 통해 주입. RealNewsScoreProducer 사용 시 NewsItem 조회 + 산식 적용. evidence 기록.
- `app/decision/holding_check_engine.py` — 동일 패턴
- `app/api/schemas.py` — `RecommendationItemSchema` / `HoldingCheckSchema` 의 `news_evidence: Optional[Dict]` 추가
- `tests/unit/test_real_news_score_producer.py` (신규, ~10 케이스)
- `tests/integration/test_recommendation_engine.py` — RealNewsScoreProducer 시나리오 보강 ~3건
- `tests/integration/test_risk_engine.py` — RISK_DISCLOSURE flag 케이스 ~2건
- `tests/integration/test_api_routes.py` — `/api/recommendations/latest` 의 `news_evidence` 노출 ~2건

**테스트:**

- 단위: 산식 — news_count=0 → 50 / +1 sentiment 우세 + recency ≤24h → 60+ / -1 sentiment 우세 → 40- / clip 경계
- 통합: RecommendationEngine 가 NewsItem 조회 → news_score 가 50 이외 값 → recommendations.news_score 컬럼에 반영
- 통합: RISK_DISCLOSURE 발견 시 risk_penalty 가산 + flags 에 추가
- 회귀: HoldingCheckEngine / ScoringEngine 본 weight 산식 0건 변경, 기존 테스트 통과

**완료 기준:**

- backend pytest ~398 → ~415 passed
- DummyScoreProducer.news_score = 50 placeholder → RealNewsScoreProducer real 값
- 태그 `v0.5-news-score`

**위험 요소:**

- 추천 점수 분포 변동 → news_score 가 갑자기 흔들리면 등급 분포가 비정상화. mock seed 1회 적용 후 등급 분포 직전 / 직후 비교 검증.
- RealNewsScoreProducer 가 `news_count = 0` 시 50 fallback (Dummy 와 동일) 안전망.

### Phase D — 테마 랭킹 화면 + StockDetail 영향 설명 강화

**목표:** v0.4 의 테마·매핑·시그널 데이터를 처음으로 화면에 surface. `/themes` 신규 화면 + StockDetail 영향 가시화 강화.

**수정할 파일:**

- `app/api/routes.py` — `GET /api/themes/ranking?as_of=...&category=...&direction=...&limit=20` (신규) + `GET /api/themes/{theme_id}` (신규). 모두 read-only.
- `app/api/schemas.py` — `ThemeRankingItemSchema` / `ThemeDetailResponse` 신규
- `tests/integration/test_api_routes.py` — happy / empty / 필터 / 404 ~4건
- `frontend/src/api/types.ts` — `ThemeRankingItem` / `ThemeDetailResponse` 타입 추가
- `frontend/src/hooks/useThemeRanking.ts` (신규)
- `frontend/src/hooks/useThemeDetail.ts` (신규)
- `frontend/src/pages/Themes/index.tsx` (신규) — 랭킹 리스트 + 검색 / 필터
- `frontend/src/pages/Themes/ThemeDetail.tsx` (신규) — 테마 상세 + 매핑 종목 + 시그널 이벤트
- `frontend/src/router.tsx` — `/themes` + `/themes/:themeId` lazy route 추가
- `frontend/src/components/Sidebar.tsx` — "테마 (β)" 9번째 메뉴
- `frontend/src/pages/StockDetail/AnalystReportsCard.tsx` — 관련 테마 섹션에 `impact_path` icon + reason 가시화 보강 (테마 클릭 → `/themes/:id`)
- `frontend/src/tests/Themes.test.tsx` (신규, ~3 케이스: happy / empty / 필터)
- `frontend/src/tests/mswServer.ts` — `/api/themes/*` 핸들러
- `frontend/e2e/fixtures/apiMocks.ts` — fixture 추가
- `frontend/e2e/dashboard.spec.ts` — 9 메뉴 nav 검증 + `/themes` 화면 visit + 자동매매 부재 가드 e2e 통과 확인 ~1건

**테스트:**

- backend pytest +4
- frontend vitest +3
- e2e +1 (9 → 10)

**완료 기준:**

- `/themes` 화면 노출 + 테마 상세 navigation
- 사이드바 9 메뉴
- StockDetail 영향 설명 강화
- 회귀 게이트 모두 그린
- 태그 `v0.5-frontend-themes`

**위험 요소:**

- 9번째 사이드바 메뉴 추가 시 layout overflow → "(β)" 라벨로 짧게. 1280px width 검증.
- `/themes` 화면이 활성 테마 0 시 빈 상태 처리 — placeholder 명시.

### Phase E — v0.5 릴리스 문서 / 마감

**목표:** v0.5 인수 종료 선언, 산출물 / 검증 / 제외 / 한계 / v0.6 후보 / 운영 가이드 / 저작권·보안 정리.

**수정할 파일:**

- `RELEASE_NOTES_v0.5.md` (신규) — 7 섹션 (산출물 / 검증 / 제외 범위 / 알려진 한계 / v0.6 후보 / 운영 가이드 / 저작권·보안)
- `README.md` — 상단 마감 배너 v0.5 갱신 + 누적 태그 라인 + 저작권 한 줄
- `PROJECT_STATUS.md` — §0 v0.5 시작 → v0.5 마감 in-place 갱신, §0-1 v0.4 / §0-2 v0.3 / §0-3 v0.2 / §0-4 v0.1 으로 강등
- `TASKS.md` — v0.5 phase 모두 [x]
- `ARCHITECTURE.md` — 11 layer 구조 (News/Disclosure layer 추가) 반영

**단계:**

1. 모든 phase 통과 / 4 게이트 그린
2. `RELEASE_NOTES_v0.5.md` 작성
3. README / PROJECT_STATUS / TASKS / ARCHITECTURE 동기화
4. tag `v0.5-final` 부여 + push

**테스트:**

- 코드 변경 없음. release 직전 4 게이트 1회 실행 (backend pytest ~419 / vitest ~63 / e2e ~10 / build).

**완료 기준:**

- `RELEASE_NOTES_v0.5.md` 작성 완료
- 4 게이트 모두 그린
- tag `v0.5-final` push 완료

**위험 요소:**

- News/Disclosure 자동 fetch flag 가 운영 환경에서 실수로 ON 되어 외부 source 호출 → `.env.example` 에 `NEWS_COLLECTION_ENABLED=false` / `DISCLOSURE_COLLECTION_ENABLED=false` 명시 + `KIS_OPS_CHECKLIST.md` 에 운영 진입 체크 항목 추가

---

## PLAN-0006: v0.6 Fundamental & Earnings Intelligence (5 Phase)

### 기준선

- 시작 태그: `v0.5-final` (HEAD `9ccf0f8` 시점, origin/main 동기화 완료)
- v0.1 ~ v0.5 모두 인수 완료. 회귀 게이트: backend pytest **481**, frontend vitest **68**, e2e **11**, build 통과
- v0.6 은 v0.5-final 위에 **재무 데이터 라인 + 어닝 인텔리전스** 를 신규 추가한다. v0.4 의 Analyst Report CSV import 패턴을 그대로 재사용해 **운영자 수동 CSV / DART subset placeholder** 1단계로 도입하고, 추후 DART API provider 를 붙일 수 있게 `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 만 미리 둔다.
- v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 (본문 paragraph 미저장 / `source_file_path` 미노출) + v0.5 의 자동 fetch default OFF 정책 모두 그대로 유지한다.

### 후보 비교 (v0.6 진입 시점 기준)

| # | 후보 | 가치 | 난이도 | 위험 | 의존성 | v0.6 채택 |
|---|---|---|---|---|---|---|
| 1 | 재무 / 실적 점수 실제화 (`fundamental_score` 25%) | 매우 높음 (DummyScoreProducer 5 컴포넌트 중 두 번째 큰 weight 첫 real 화) | 중 (CSV 1단계 도입은 v0.4 패턴 재사용, DART 자동 연동은 v0.7+ 로 이연) | 낮음 (CSV 운영자 입력만, 자동 호출 0건) | `FundamentalSnapshot` 신규 테이블 1개 | ✅ 채택 (Phase A·C) |
| 2 | 어닝 인텔리전스 (실적 발표일 + 서프라이즈 + 컨센서스 차이) | 높음 (HoldingCheckEngine 의 `earnings_score` 최초 real 화 + Today 화면 다가오는 발표) | 중 (CSV 입력 + 분류 룰) | 낮음-중 (실적 데이터 정확성은 운영자 입력 책임) | `EarningsEvent` 신규 테이블 1개 | ✅ 채택 (Phase B·C) |
| 3 | 점수 정합성 / 통합 evidence 화면 | 중-높음 (v0.5 의 news/disclosure + v0.4 의 report/theme + v0.6 의 fundamental/earnings 통합 noise 정리) | 낮음 (read-only 화면) | 낮음 | v0.5 evidence 인프라 그대로 | ✅ 채택 (Phase D) |
| 4 | 관심종목 / Watchlist | 중 (UX) | 중-높음 (POST 첫 도입 + 인증 묶음) | 중-높음 (read-only 정책 깨짐) | 인증 의존 | ❌ v0.7 후보 (POST + 인증 별도 cycle) |
| 5 | 인증 / 보안 | 중 (POST 의 전제) | 중-높음 | 중 (잘못 설계 시 보안 구멍) | — | ❌ v0.7 후보 (Watchlist 와 묶어서) |
| 6 | 전략 / 백테스트 기초 (`StrategyInterface` 구체화) | 중 (장기) | 매우 높음 | 중 | 실 News (v0.5) + 재무 (v0.6) 데이터 후행 필요 | ❌ v0.8+ 후보 |
| 7 | 자동매매 / 실 주문 | (위험) | 매우 높음 | 매우 높음 | 모든 위 + 컴플라이언스 | ❌ Future Backlog (별도 보안 / 컴플라이언스 사이클 선행) |

### 시나리오 옵션

**Scenario X — Fundamental + Earnings + 정합성 (권장 ✅)**

- Phase A: Fundamental data layer (CSV import + `FundamentalSnapshot` 테이블 + 8 지표 + `FundamentalProviderInterface` ABC)
- Phase B: Earnings event layer (CSV import + `EarningsEvent` 테이블 + 어닝 캘린더 + BEAT/MEET/MISS 분류 + `EarningsProviderInterface` ABC)
- Phase C: `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` + RecommendationEngine·HoldingCheckEngine 통합
- Phase D: 프런트 (StockDetail Fundamental·Earnings 카드 + Today 다가오는 어닝 + Recommendations/Holdings evidence 정합성 통합)
- Phase E: 마감

**Scenario Y — Fundamental deep + Backtest 기초**

- Phase A·B·C: 재무·어닝 (X 와 동일)
- Phase D: `StrategyInterface` ABC 구체화 + 과거 추천 backtest 시뮬레이터 (read-only) + 수수료/세금/슬리피지 placeholder
- Phase E: 마감
- 화면 통합 / 정합성 작업은 v0.7 로 미룸 — backend / 산식 위주

**Scenario Z — Watchlist + 인증 + Fundamental 일부**

- Phase A: 인증 (단일 사용자 토큰 + audit log + middleware)
- Phase B: Watchlist (POST 첫 도입 + DB + UI)
- Phase C: Fundamental import (CSV 만, score 통합 미포함)
- Phase D: 통합 화면
- Phase E: 마감
- read-only 정책 깨기 + 데이터 가치 분산. 사용자 명시 ("자동매매 제외 + 재무·실적 중심") 와 정렬 안 됨

**최종 추천**: **Scenario X**. 이유:

- 사용자 기본 추천과 정렬 (재무·실적 점수 실제화 + 어닝 인텔리전스 기초)
- DummyScoreProducer 5 컴포넌트 중 v0.5 에서 `news` (25%) real 화 → v0.6 에서 `fundamental` (25%) + `earnings` (HoldingCheck 만) 가 다음으로 큰 가치
- v0.4 의 Analyst Report CSV import 패턴 (`scripts/import_analyst_reports.py` + forbidden body column 검증 + summary 500자 truncate + source_file_path 마스킹) 을 그대로 재사용 — 위험 / 학습 비용 최소
- DART 자동 연동 부담 회피 — `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 만 두고 실 API 구현은 v0.7+ 로 이연 (`FakeFundamentalProvider` / `FakeEarningsProvider` 만 제공)
- POST 도입 회피 — read-only API 정책 v0.6 에서도 유지 (Watchlist / 인증은 v0.7+ 로 미룸)
- Y (백테스트) 는 화면 정체 / 산식 검증 부족 / 수수료·세금 모델링 위험. Z 는 정책 변경 (POST 첫 도입) + 사용자 명시와 다름

### 범위 (5 Phase)

- **Phase A** — Fundamental data layer + CSV import (`FundamentalProviderInterface` ABC + `FakeFundamentalProvider` + `FundamentalSnapshot` ORM + Repository + `scripts/import_fundamentals.py` argparse CLI default dry-run + `app/data/importers/fundamentals.py` (forbidden body column 검증) + 단위/통합 테스트)
- **Phase B** — Earnings event layer + CSV import + 어닝 캘린더 (`EarningsProviderInterface` ABC + `FakeEarningsProvider` + `EarningsEvent` ORM + Repository + `scripts/import_earnings.py` argparse CLI + `app/data/importers/earnings.py` + BEAT/MEET/MISS 분류 룰 + 단위/통합 테스트)
- **Phase C** — `RealFundamentalScoreProducer` + `RealEarningsScoreProducer` (composition 패턴, fallback DummyScoreProducer) + RecommendationEngine·HoldingCheckEngine 통합 + decision_logs/data_snapshots 에 `fundamental_evidence` / `earnings_evidence` 기록 + safe-fields whitelist + 단위/통합 테스트
- **Phase D** — 백엔드 read-only API (`GET /api/stocks/{symbol}/fundamentals` + `GET /api/stocks/{symbol}/earnings` + `GET /api/calendar/earnings?since=&until=`) + `RecommendationItemSchema` / `HoldingCheckSchema` 에 `fundamental_evidence` / `earnings_evidence` nullable 필드 추가 + 프런트 StockDetail Fundamental·Earnings 카드 + Today 다가오는 어닝 카드 + Recommendations/Holdings evidence 정합성 통합 + msw/e2e fixture
- **Phase E** — `RELEASE_NOTES_v0.6.md` 신규 + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE / API_SPEC / TESTING / DB_SCHEMA / INTEGRATION_RUNBOOK 마감 + 4 게이트 재확인 + tag `v0.6-final`

### 제외 범위 (v0.6 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.5 일관 정책)
- ❌ DART API 자동 호출 — 1단계는 운영자 CSV import 만. `FundamentalProviderInterface` / `EarningsProviderInterface` ABC 와 Fake provider 만 제공. 실 API 구현체는 v0.7+ 후보
- ❌ 자동 fetch default ON — `Settings.fundamental_collection_enabled` / `earnings_collection_enabled` = false (운영자 명시 enable + 실 provider 주입 시에만 동작, v0.5 패턴 재사용)
- ❌ 재무제표 원문 PDF / Excel BLOB 저장 — CSV 메타데이터 (정량 지표 + fiscal_period + source_url) 만
- ❌ 재무제표 본문 paragraph 저장 — analyst report 처럼 짧은 운영자 메모 (≤500자) 만
- ❌ ScoringEngine 본 weight 변경 — `fundamental_score` 가 placeholder 50 → real 로 교체되지만 weight 15% 그대로 (recommendation 산식). HoldingCheck 의 `earnings_score` 도 동일
- ❌ 관심종목 / Watchlist / 인증 — v0.7 후보 (POST 도입 + 인증 사이클 별도)
- ❌ Strategy / Backtest / MockBroker — v0.8+ 후보
- ❌ LLM 자동 재무 분석 — Phase C 는 룰 기반 / percentile 기반만, LLM 보강은 v0.7+ 후보
- ❌ HoldingCheckEngine 산식 본 weight 변경 — `earnings_score` 가 placeholder 50 → real 로 교체되지만 가중치 그대로
- ❌ KIS API 외 외부 자격증명 추가 / 자동 호출

### 데이터 모델 변경 (신규 테이블 2개)

**`fundamental_snapshots` (24번째 테이블)**

운영자가 직접 입력하거나 향후 DART provider 가 적재하는 정량 지표 시계열.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `symbol` | String(32) NOT NULL index | |
| `snapshot_date` | Date NOT NULL index | 데이터 기준일 (예: 분기 보고서 발표일) |
| `fiscal_year` | Integer NOT NULL | 회계연도 (2026 등) |
| `fiscal_quarter` | Integer nullable | 1/2/3/4 또는 NULL (연간) |
| `per` | Numeric(8,2) nullable | Price/Earnings |
| `pbr` | Numeric(8,2) nullable | Price/Book |
| `eps` | Numeric(12,2) nullable | 주당순이익 (KRW) |
| `roe` | Numeric(6,2) nullable | 자기자본이익률 (%) |
| `revenue_growth_yoy` | Numeric(6,2) nullable | 매출 성장률 YoY (%) |
| `operating_income_growth_yoy` | Numeric(6,2) nullable | 영업이익 성장률 YoY (%) |
| `debt_ratio` | Numeric(6,2) nullable | 부채비율 (%) |
| `dividend_yield` | Numeric(6,2) nullable | 배당수익률 (%) |
| `summary` | String(500) nullable | 운영자 짧은 메모 (≤500자, body/content/full_text 0건) |
| `source` | String(32) nullable | "DART" / "MANUAL" / "FAKE" 등 |
| `source_url` | String(500) nullable | DART 공시 URL 등 (외부 노출 가능) |
| `source_file_path` | String(500) nullable | 운영자 로컬 파일 경로 (마스킹 후 외부 미노출) |
| `extraction_method` | String(16) NOT NULL | "MANUAL" / "DART_API" / "FAKE" |
| `extraction_confidence` | Numeric(4,3) nullable | |
| `created_at` / `updated_at` | DateTime | TimestampMixin |

UniqueConstraint(`symbol`, `snapshot_date`, `fiscal_year`, `fiscal_quarter`).

**`earnings_events` (25번째 테이블)**

실적 발표 이벤트 + 컨센서스 대비 surprise.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `symbol` | String(32) NOT NULL index | |
| `event_date` | Date NOT NULL index | 실적 발표일 (또는 예정일) |
| `event_type` | String(16) NOT NULL | "ANNOUNCEMENT" (예정) / "REPORT" (확정) |
| `fiscal_year` | Integer NOT NULL | |
| `fiscal_quarter` | Integer nullable | 1/2/3/4 또는 NULL (연간) |
| `expected_eps` | Numeric(12,2) nullable | 컨센서스 EPS |
| `actual_eps` | Numeric(12,2) nullable | 발표 EPS (REPORT 시) |
| `eps_surprise_pct` | Numeric(6,2) nullable | (actual - expected) / |expected| * 100 |
| `expected_revenue` | Numeric(20,0) nullable | 컨센서스 매출 (KRW) |
| `actual_revenue` | Numeric(20,0) nullable | 발표 매출 |
| `revenue_surprise_pct` | Numeric(6,2) nullable | |
| `expected_operating_income` | Numeric(20,0) nullable | |
| `actual_operating_income` | Numeric(20,0) nullable | |
| `operating_income_surprise_pct` | Numeric(6,2) nullable | |
| `classification` | String(16) nullable | "BEAT" / "MEET" / "MISS" — surprise_pct 임계값 룰 (예: ≥+5% BEAT / [-5%, +5%] MEET / ≤-5% MISS) |
| `summary` | String(500) nullable | 짧은 메모 |
| `source` | String(32) nullable | |
| `source_url` | String(500) nullable | |
| `source_file_path` | String(500) nullable | 마스킹 후 외부 미노출 |
| `extraction_method` | String(16) NOT NULL | |
| `created_at` / `updated_at` | DateTime | |

UniqueConstraint(`symbol`, `fiscal_year`, `fiscal_quarter`, `event_type`).

기존 테이블 변경 0건. 운영 환경 마이그레이션 = `CREATE TABLE fundamental_snapshots ...; CREATE TABLE earnings_events ...;` 두 줄, destructive 0건.

### Score 산식 (Phase C 상세)

**`fundamental_score` 산식** — `RealFundamentalScoreProducer` (Phase C 구현 기준):

```
# snapshot 가져오기 — symbol 의 가장 최신 fundamental_snapshots 행
score = 50
score += clip(roe, -10, 25) * 0.6
score += per_bucket_adjustment        # <=8:+8 / <=15:+4 / <=25:0 / <=40:-6 / >40:-12
score += pbr_bucket_adjustment        # <=1:+4 / >=2.5:-4 / >=4:-8
score += clip(revenue_growth_yoy, -20, 30) * 0.25
score += clip(operating_income_growth_yoy, -30, 50) * 0.25
score += debt_ratio_adjustment        # <=50:+3 / >=100:-8 / >=200:-15
score += min(dividend_yield, 5) * 0.8
fundamental_score = clip(score, 0, 100)

# snapshot 없음 → 50 (Dummy fallback 호환)
```

PER / PBR / 부채비율은 과열 또는 레버리지 위험을 보수적으로 감산하고, ROE / 성장률 /
배당수익률은 상한을 둔 작은 가산으로만 반영한다. 본 추천 weight 는 변경하지 않는다.

**`earnings_score` 산식** — `RealEarningsScoreProducer` (HoldingCheckEngine 적용):

```
event = latest earnings_events row by symbol
base_delta = +10 (BEAT) / 0 (MEET, UNKNOWN) / -10 (MISS)
surprise_delta = clip(surprise_pct * 0.5, -10, +10)
recency_multiplier = 0.5 (future) / 1.0 (<=30d) / 0.6 (<=90d) / 0.3 (>90d)
earnings_score = clip(50 + (base_delta + surprise_delta) * recency_multiplier, 0, 100)

# event 없음 → 50
```

다가오는 UNKNOWN 이벤트는 중립 점수에 recency metadata 만 남기는 방향으로 처리한다.

**추천 / 보유 통합**: 기존 `ScoreProducerInterface` 주입 구조를 그대로 사용한다.
`RealFundamentalScoreProducer.score_recommendation` 은 fallback 결과에서
`fundamental_score` 만 교체하고, `RealEarningsScoreProducer.score_holding` 은 fallback
결과에서 `earnings_score` 만 교체한다. 본 weight (recommendation: technical 35% +
news 25% + supply 15% + **fundamental 15%** + ai 10% - risk_penalty / holding:
technical 35% + news 20% + **earnings 20%** + ai 15% + profit 10% - risk_penalty)
산식은 손대지 않는다. `decision_logs.rule_result_json["fundamental_evidence"]` /
`["earnings_evidence"]` 와 `data_snapshots.market_context_json` 에 동일 evidence 를
추가한다.

### Evidence whitelist (저작권 / 안전 정책)

- **`fundamental_evidence`**: `{snapshot_date, fiscal_year, fiscal_quarter, per, pbr, roe, debt_ratio, revenue_growth_yoy, operating_income_growth_yoy, dividend_yield}`. source / summary / source_file_path / extraction_method / 본문 필드 0건
- **`earnings_evidence`**: `{latest_event_date, fiscal_year, fiscal_quarter, event_type, surprise_type, surprise_pct, operating_income_actual, operating_income_consensus}`. source / memo / summary / source_file_path / 본문 필드 0건
- 단위 테스트가 evidence 의 키 집합을 명시 단언 — v0.5 Phase C 의 `news_evidence.top_news` whitelist 패턴 그대로
- `source_file_path` 는 모든 응답 / 프런트 / e2e 에서 0건 노출 — `_assert_no_source_file_path` recursive helper 가 신규 케이스에서 검증

### CSV import 정책 (Phase A·B 상세)

v0.4 의 `scripts/import_analyst_reports.py` 패턴 그대로 재사용:

- argparse CLI, default dry-run, `--commit` 명시 시에만 DB 적재
- forbidden body column 13종 검증 — `body / content / full_text / paragraph_text / raw_text / 본문 / 원문 / 전문 / disclosure_text / report_text / news_body / article_body / pdf_text` 가 헤더에 포함되면 즉시 거부
- `summary` 500자 초과 시 truncate count 만 보고 (persist 시 truncate)
- `source_file_path` 는 마스킹 helper (`mask_sensitive_value`) 통과 후 응답에 노출 — 실 path 는 DB 에만 저장
- 단위 테스트가 forbidden column 거부 / dry-run / commit / 멱등 / 재실행 시 0 중복 / summary truncate 모두 검증

### 프런트 노출 (Phase D 상세)

- **신규 카드 — StockDetail "Fundamental Snapshot"**: 최근 4 분기 시계열. PER / PBR / ROE / 매출 성장률 / 영업이익 성장률 / 부채비율 / 배당수익률 + sub_scores + 종합 fundamental_score
- **신규 카드 — StockDetail "Earnings History"**: 최근 8 분기 + 다가오는 ANNOUNCEMENT D-Day. classification (BEAT/MEET/MISS) badge + eps_surprise_pct + revenue_surprise_pct
- **Today 화면 — "다가오는 어닝 발표 (D-7 이내)"**: 보유 종목 + 추천 종목 union 의 ANNOUNCEMENT 가운데 days_to_event ≤ 7 인 것 표시. 클릭 시 종목 상세
- **Recommendations 테이블 — `fundamental evidence` + `earnings evidence` 두 컬럼 추가** (v0.5 Phase D 의 `news evidence` / `disclosure risk` 패턴 그대로)
- **Holdings 테이블 — `earnings evidence` 컬럼 추가** (v0.5 Phase D 에서 이연됐던 holding_check evidence 노출 작업 포함)
- **사이드바 변경 0건** — 9 메뉴 그대로 (`테마 (β)` 다음에 새 메뉴 추가하지 않음, 기존 화면 카드 보강만)
- **기존 화면 변경 최소화** — Recommendations / Holdings / StockDetail 카드만 보강. Today / RecommendationHistory / Themes / MarketCapTop / Jobs / Settings 손대지 않음

### v0.6 누적 태그 (예정)

```
v0.5-final                       ← v0.6 시작점 (HEAD 9ccf0f8)
v0.6-fundamental-data-layer      ← Phase A 인수 (FundamentalSnapshot + import CLI)
v0.6-earnings-event-pipeline     ← Phase B 인수 (EarningsEvent + 어닝 캘린더 import)
v0.6-fundamental-score           ← Phase C 인수 (RealFundamentalScoreProducer + RealEarningsScoreProducer)
v0.6-frontend-fundamentals       ← Phase D 인수 (StockDetail 카드 + Today 다가오는 어닝)
v0.6-final                       ← Phase E 마감 (RELEASE_NOTES_v0.6.md + 4 게이트)
```

### v0.7+ 후보 (Backlog 등재용)

| 후보 | 분류 | v0.6 채택 안 한 이유 |
|---|---|---|
| 인증 / 권한 / 단일 사용자 토큰 + audit log | UX / 보안 | POST 도입 전제 + 별도 보안 cycle 필요 |
| 관심종목 / Watchlist (POST 라우터 첫 도입) | UX | 인증 동반 필수 |
| Strategy / Backtest 기초 (`StrategyInterface` ABC + 과거 추천 backtest 시뮬레이터) | 분석 / 자동매매 전 단계 | 실 News (v0.5) + 재무 (v0.6) 데이터 후행 검증 후 |
| 실 DART API 구현체 (`DartFundamentalProvider` / `DartEarningsProvider`) | 데이터 / 분석 실제화 | v0.6 은 ABC + Fake + CSV 만, 실 API 는 라이선스/정책/스로틀링 검토 필요 |
| 실 RSS / News API 구현체 | 데이터 라인 | v0.5 ABC 위에 추가, 라이선스 검토 |
| LLM 기반 재무 / 어닝 / 뉴스 자동 분석 | AI 강화 | 룰 기반 검증 후 |
| 운영 모니터링 (Sentry / Prometheus / Grafana) | 운영 | v0.6 까지 read-only + 단일 운영자 → 모니터링 확장 후행 |
| 모바일 / 태블릿 레이아웃 | UX | PC 1280px+ 우선 |
| Alembic 도입 + 마이그레이션 자동화 | 인프라 | 누적 ALTER 가 v0.5 `news_items.category` + v0.6 신규 테이블 2개 → 4건 누적 시점에 도입 |
| `lightweight-charts` 마이그레이션 | UX | Recharts 한계 도달 시 |
| WebSocket / SSE 실시간 잡 상태 | 운영 | 인증 후행 |
| `.github/dependabot.yml` | 인프라 | v0.3 Phase A 보류 항목 |

### 단계별 산출물 / 게이트 (예상)

| Phase | 신규 파일 | 변경 파일 | 게이트 | 누적 태그 |
|---|---|---|---|---|
| A | `app/data/dtos.py` (FundamentalSnapshotDTO) / `app/data/interfaces.py` (FundamentalProviderInterface) / `app/data/importers/fundamentals.py` / `scripts/import_fundamentals.py` / `app/data/repositories/fundamental_snapshots.py` / `tests/integration/test_fundamental_import.py` / `tests/integration/test_fundamental_repository.py` / `tests/mocks/fake_fundamental_provider.py` | `app/db/models.py` (+1 테이블) / `app/data/repositories/__init__.py` / `app/data/collectors/__init__.py` / `DB_SCHEMA.md` (§9 신규) | backend pytest **481 → ~510** | `v0.6-fundamental-data-layer` |
| B | `app/data/dtos.py` (+EarningsEventDTO) / `app/data/interfaces.py` (+EarningsProviderInterface) / `app/data/importers/earnings.py` / `scripts/import_earnings.py` / `app/data/repositories/earnings_events.py` / `tests/integration/test_earnings_import.py` / `tests/integration/test_earnings_repository.py` / `tests/mocks/fake_earnings_provider.py` | `app/db/models.py` (+1 테이블) / `DB_SCHEMA.md` (§10 신규) / `INTEGRATION_RUNBOOK.md` (§13 신규 — 어닝 import 운영 절차) | backend pytest **~510 → ~545** | `v0.6-earnings-event-pipeline` |
| C | `app/analysis/score_producers.py` (+RealFundamentalScoreProducer + RealEarningsScoreProducer) / `tests/unit/test_real_fundamental_earnings_score_producers.py` | `app/decision/recommendation_engine.py` (evidence) / `app/decision/holding_check_engine.py` (evidence) / `tests/integration/test_recommendation_engine.py` / `tests/integration/test_holding_check_engine.py` | backend pytest 전체 회귀, ScoringEngine 본 weight 변경 0건 | `v0.6-fundamental-score` |
| D | `frontend/src/pages/StockDetail/FundamentalsCard.tsx` / `EarningsCard.tsx` / `frontend/src/hooks/useStockFundamentals.ts` / `useStockEarnings.ts` / `useEarningsCalendar.ts` / `frontend/src/tests/Fundamentals.test.tsx` | `app/api/routes.py` (+3 GET) / `app/api/schemas.py` (+5 schema) / `frontend/src/api/types.ts` / `frontend/src/pages/Recommendations/RecommendationsTable.tsx` / `Holdings*` / `frontend/src/pages/TodayReport/index.tsx` / `frontend/e2e/fixtures/apiMocks.ts` / `frontend/e2e/dashboard.spec.ts` | backend pytest **~580 → ~595**, vitest **68 → ~78**, e2e **11 → 13** | `v0.6-frontend-fundamentals` |
| E | `RELEASE_NOTES_v0.6.md` | `README.md` / `PROJECT_STATUS.md` / `TASKS.md` / `ROADMAP.md` / `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `DB_SCHEMA.md` / `INTEGRATION_RUNBOOK.md` | 4 게이트 재확인, 회귀 0건 | `v0.6-final` |

### 위험 요소

- **DART CSV 포맷 다양성** — 운영자가 직접 CSV 만들 때 컬럼명 / 단위 (백만원 vs 억원) / 비율 표기 (% 포함 여부) 가 들쭉날쭉 → Phase A·B importer 가 명확한 `expected_columns` 화이트리스트 + 단위 변환 helper + 검증 실패 시 dry-run 리포트로 조기 감지
- **fundamental_score 산식 의존성** — percentile 기반이 아닌 절댓값 기반이라 시장 환경 (예: 금리 변화) 에 민감 → v0.6 은 단순 산식으로 시작하고 v0.7 에서 시장 percentile / 섹터 평균 도입 검토. PLAN 에 명시
- **earnings 데이터 정확성** — 운영자 수동 입력 오류 가능성 → importer 가 expected_eps / actual_eps null 둘 중 하나만 있어도 허용, surprise_pct 계산은 NULL safe. 분류는 운영자 입력 우선
- **HoldingCheckEngine 본 weight 변경 위험** — `earnings_score` 가 50 → real 로 교체되면 기존 회귀 테스트가 깨질 수 있음 → Phase C 시작 시 본 weight 변경 0건 명시 + 기존 회귀 테스트 모두 그대로 통과하는지 우선 검증

**완료 기준 (cycle-wide):**

- 모든 phase 통과 / 4 게이트 그린 (backend pytest ~595 / vitest ~78 / e2e 13 / build)
- `RELEASE_NOTES_v0.6.md` 작성 완료
- 5 누적 태그 부여 + push
- 자동매매 / POST 라우터 / DART 자동 호출 / 본 weight 변경 0건 가드 모두 통과
- `source_file_path` 외부 노출 0건 (helper 검증)
- forbidden body column 13종 거부 가드 통과 (CSV importer)

---

## PLAN-0007: v0.7 Strategy & Backtest Foundation (5 Phase)

### 기준선

- 시작 태그: `v0.6-final` (HEAD `e729d60` 시점, origin/main 동기화 완료)
- v0.1 ~ v0.6 모두 인수 완료. 회귀 게이트: backend pytest **558**, frontend vitest **77**, e2e **13**, build 통과
- v0.7 은 v0.6-final 위에 **전략 정의 (StrategyInterface 구체화) + 과거 추천 결과 기반 백테스트 엔진 + 시장 국면별 / 비용 모델 + 백테스트 화면** 을 신규 추가한다.
- v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 (본문 paragraph 미저장 / `source_file_path` 미노출) + v0.5 의 자동 fetch default OFF + v0.6 의 evidence whitelist + ScoringEngine 본 weight 0건 변경 정책 모두 그대로 유지한다.
- v0.7 도 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST 라우터 / 실 외부 API 자동 호출 / Telegram 실 발송 0건 정책을 유지한다.

### 후보 비교 (v0.7 진입 시점 기준)

| # | 후보 | 가치 | 난이도 | 위험 | 의존성 | v0.7 채택 |
|---|---|---|---|---|---|---|
| 1 | Strategy / Backtest 기초 (`StrategyInterface` + BacktestEngine + 룰 기반 전략 + 비용 모델 + 백테스트 화면) | 매우 높음 — v0.1~v0.6 누적 추천 판단 축이 충분히 풍부해진 상태에서 "이 추천이 돈이 되는가?" 가 다음 자연 질문. `recommendation_results` (1/3/5/20일) 가 이미 적재 중이라 즉시 활용 가능. 자동매매 진입 전 반드시 거쳐야 할 검증 단계 | 중 — 신규 테이블 1~2개, 외부 의존성 0건, 기존 read-only 정책 그대로 유지. 핵심은 산식 검증 | 낮음~중 — 비용 모델 / 산식 오류 시 백테스트 결과 왜곡 가능 (검증 테스트로 방어) | `recommendation_results` 충분히 누적, `MarketRegimeRepository` 기존 활용, `ReturnRate` 컴포넌트 기존 활용 | ✅ 채택 (Phase A·B·C·D) |
| 2 | Watchlist + 인증 | 중 — 단일 사용자 환경에서는 즉각 가치 작음. 다만 POST 첫 도입은 미래 자동매매 / 사용자별 알림 / audit log 기반 | 중~높음 — POST 라우터 정책 변경 + DB + UI + 인증 묶음. 사실상 인증과 같이 가야 함 | 중~높음 — POST 도입은 v0.1~v0.6 일관 정책의 첫 변경. 인증 없이 POST 만 도입하면 외부 노출 시 위험. 잘못 설계 시 retrofit 비용 큼 | 인증 의존 | ❌ v0.8 후보 (인증과 묶음) |
| 3 | 인증 / 보안 단독 | 중 — 외부 노출 시점에 필수. 현재 로컬 단일 사용자 환경에서는 즉각 가치 작음 | 중 — 단일 토큰 / API key + 헤더 검증 + audit log. 단순하지만 잘못 설계 시 v0.7+ 모든 cycle 에 영향 | 중 — 잘못 설계 시 모든 cycle retrofit | 없음. Watchlist 와 같이 가는 게 자연스러움 | ❌ v0.8 후보 (Watchlist 와 묶음) |
| 4 | 실 DART / 실 RSS provider | 중~높음 — 운영자 수동 CSV burden 제거 | 높음 — 외부 API 라이선스 / rate limit / 실패 격리 / retry / 데이터 정규화 / 인증. CSV 패턴과 다름. **라이선스 검토 (사람) 가 가장 큰 불확실성** | 높음 — 외부 의존성 첫 도입 = 외부 장애 / 라이선스 변경 / 데이터 품질 변동에 노출. CI 환경에서 외부 호출 차단 정책 추가 필요 | 라이선스 검토 선행, ABC는 v0.5/v0.6 에 이미 있음 | ❌ v0.8+ 후보 (라이선스 검토 + 별도 cycle) |
| 5 | 운영 모니터링 (Sentry / Prometheus / Grafana) | 중 — 외부 노출 / 다중 사용자 시점에 중요. 단일 사용자 + 로컬 환경에서는 즉각 가치 작음 | 낮음~중 — Sentry / Prometheus 통합. 인프라 의존성 추가 | 낮음 — read-only | 외부 노출 후 더 가치 | ❌ v0.8+ 후보 (인증 도입 후) |
| 6 | DB migration / Alembic | 중 — 누적 ALTER 가 v0.5 1건 + v0.6 2건 + v0.7 신규 테이블 1~2건 → 4~5건 누적 시점에 도입 적기 | 낮음 — 기존 metadata 베이스라인 캡처 후 점진 적용 | 낮음~중 — 운영 DB baseline 생성 시 신중 | 없음 | △ v0.8 후보 (v0.7 신규 테이블 추가 후 진입 권장) |
| 7 | 자동매매 / 실주문 | (위험) | 매우 높음 | 매우 높음 | 모든 위 + 컴플라이언스 + Strategy/Backtest 검증 후행 | ❌ Future Backlog (별도 보안/컴플라이언스/자본 한도 사이클 선행) |

### 시나리오 옵션

**Scenario X — Strategy / Backtest 기초 (권장 ✅)**

- Phase A: `StrategyInterface` ABC + 룰 기반 전략 2~3종 (`TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy`) + 단위 테스트
- Phase B: `BacktestEngine` + `backtest_runs` (26번째) + `backtest_results` (27번째) 테이블 + `scripts/run_backtest.py` argparse CLI (default dry-run) + 단위/통합 테스트
- Phase C: 시장 국면별 성과 분석 (`MarketRegimeRepository` 활용) + 비용 모델 (수수료 / 거래세 / 슬리피지 placeholder) + cost-adjusted return
- Phase D: 백엔드 read-only API 3종 (`/api/strategies` + `/api/backtest/runs` + `/api/backtest/runs/{run_id}`) + 프런트 10번째 화면 `/backtest`
- Phase E: 마감 (`RELEASE_NOTES_v0.7.md` + 4 게이트 재확인 + tag `v0.7-final`)

**Scenario Y — Watchlist + 인증**

- Phase A: 인증 (단일 사용자 토큰 + audit log + middleware)
- Phase B: Watchlist 모델 + Repository
- Phase C: POST 라우터 첫 도입 + 인증 가드
- Phase D: 프런트 Watchlist 화면 + 개인화 Today
- Phase E: 마감
- POST 도입은 v0.1~v0.6 일관 정책의 첫 변경. 단일 사용자 환경에서는 즉각 가치 작음. **자동매매 진입 전 Strategy/Backtest 검증을 안 하고 인증만 먼저 하면 다음 단계에 무엇을 해야 할지 불명확**

**Scenario Z — 실 provider 연동 + 운영 모니터링**

- Phase A: `DartFundamentalProvider` + `DartEarningsProvider` 골격 (라이선스 검토 동반)
- Phase B: `RssNewsProvider` 골격
- Phase C: rate limit / retry / 실패 격리 / CI 외부 호출 차단
- Phase D: Sentry / Prometheus 통합
- Phase E: 마감
- **단일 cycle 에 너무 많이 묶여 있음**. 라이선스 검토 (사람 작업) 가 코드 cycle 외 단계라 진입 시점 예측 어려움. 외부 API 의존성 첫 도입 + 운영 인프라 도입을 동시에 하는 것은 위험

**최종 추천**: **Scenario X — Strategy / Backtest 기초**. 이유:

- v0.1~v0.6 누적 데이터 충분: technical / report / theme / news / disclosure / fundamental / earnings + `recommendation_results` 1·3·5·20일 수익률 + max drawdown + result_status
- "추천이 돈이 되는가?" 가 v0.6 마감 직후 가장 자연스러운 다음 질문
- 외부 의존성 0건 → 안전하고 빠르게 진입 가능 (Scenario Z 와 정반대)
- **자동매매 진입 전 필수 검증 단계** — Future Backlog (Strategy & Signal → Backtest → MockBroker → APPROVAL → SMALL_AUTO → FULL_AUTO) 의 첫 항목
- ScoringEngine 본 weight 변경 0건, POST 라우터 0건, 실 KIS / DART / Telegram 호출 0건 — v0.1~v0.6 일관 정책 그대로
- 사용자 명시 추천 (Strategy/Backtest 기초) 과 정렬

향후 권장 cycle 순서:
- v0.7 (이번): Strategy / Backtest 기초 (Scenario X)
- v0.8: Watchlist + 인증 (Scenario Y) + Alembic 도입
- v0.9: 실 DART / 실 RSS provider (Scenario Z 일부) + 운영 모니터링
- v0.10+: APPROVAL 모드 진입 검토 (별도 보안/컴플라이언스 cycle 선행)

### 범위 (5 Phase)

- **Phase A — Strategy interface + 룰 기반 전략 정의**
  `app/strategy/interfaces.py` (`StrategyInterface` ABC + `StrategySignal` dataclass + `ScoreSnapshot` dataclass) + `app/strategy/rule_based.py` (`TopGradeStrategy` / `HighScoreStrategy` / `MultiSignalStrategy` 3종 구현체) + `tests/unit/test_rule_based_strategies.py` 신규. **신규 테이블 0건 / 라우터 0건 / 프런트 0건 / 자동매매 0건** — 신호 산출만.
- **Phase B — Backtest engine + recommendation_results 활용**
  `app/db/models.py` (+`BacktestRun` 26번째 + `BacktestResult` 27번째) + `app/data/repositories/backtest_runs.py` + `app/data/repositories/backtest_results.py` + `app/backtest/engine.py` (`BacktestEngine` — 전략 + 추천 이력 + `recommendation_results` 데이터로 성과 집계) + `scripts/run_backtest.py` argparse CLI (default dry-run, `--commit` 시 적재) + `tests/integration/test_backtest_engine.py` 신규. 메트릭: 승률 / 평균 수익률 / max drawdown / 1·3·5·20일 평균 / 시그널 카운트.
- **Phase C — 시장 국면별 + 비용 모델**
  `app/backtest/cost_model.py` (`CostModel` — 매수 수수료 0.015% / 매도 수수료 0.015% + 거래세 0.20% / 슬리피지 0.1%) + `app/backtest/regime_split.py` (시장 국면별 성과 분리, `MarketRegimeRepository` 활용) + `BacktestResult` 에 `cost_adjusted_return` / `regime` 컬럼 추가 + 단위 테스트 보강.
- **Phase D — 백엔드 read-only API + 프런트 화면**
  `GET /api/strategies` (목록) + `GET /api/backtest/runs?strategy=&limit=` (목록) + `GET /api/backtest/runs/{run_id}` (상세) 3종 신규. `app/api/schemas.py` 보강 (`StrategySchema` / `BacktestRunSchema` / `BacktestResultSchema` / `BacktestRunDetailResponse`). 프런트 10번째 화면 `/backtest` (Sidebar `백테스트 (β)` 메뉴 추가) + msw + e2e 보강.
- **Phase E — `RELEASE_NOTES_v0.7.md` 신규 + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE / API_SPEC / TESTING / DB_SCHEMA / INTEGRATION_RUNBOOK 마감 + 4 게이트 재확인 + tag `v0.7-final`.**

### 제외 범위 (v0.7 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 — read-only API 만 (v0.1 ~ v0.6 일관 정책 유지)
- ❌ 인증 / Watchlist (v0.8 후보로 묶음)
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 의 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (Strategy / Backtest 검증 후 v0.10+ 검토)
- ❌ ScoringEngine 본 weight 변경 — `RecommendationEngine` / `HoldingCheckEngine` 산식 0건 변경
- ❌ HoldingCheckEngine 산식 변경
- ❌ LLM 자동 전략 생성 — Phase A 는 룰 기반만, LLM 보강은 v0.8+ 후보
- ❌ Alembic 도입 (v0.7 신규 테이블 1~2개 추가 후 v0.8 권장)
- ❌ 실 비용 / 세금 데이터 fetch — `CostModel` 은 placeholder constant 만, 실제 broker fee schedule 은 v0.8+ 후보
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.8+ 후보
- ❌ 백테스트 결과 자동 텔레그램 알림 — read-only 화면만, 자동 발송 0건

### 데이터 모델 변경 (신규 테이블 2개)

**`backtest_runs` (26번째 테이블)**

백테스트 실행 단위.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `strategy_name` | String(64) NOT NULL index | "TopGradeStrategy" 등 |
| `strategy_version` | String(32) NOT NULL | "v1.0.0" 등 |
| `started_at` | DateTime NOT NULL index | 실행 시작 시각 (UTC) |
| `finished_at` | DateTime nullable | 실행 종료 시각 |
| `status` | String(16) NOT NULL | "RUNNING" / "SUCCESS" / "FAILED" |
| `from_date` | Date NOT NULL | 백테스트 대상 기간 시작 |
| `to_date` | Date NOT NULL | 백테스트 대상 기간 끝 |
| `total_signals` | Integer NOT NULL default 0 | 전략이 생성한 신호 총 개수 |
| `evaluated_signals` | Integer NOT NULL default 0 | 결과가 있어 평가 가능한 신호 수 |
| `summary_json` | JSON nullable | 승률 / 평균 수익률 / max DD / regime breakdown 요약 dict |
| `error_message` | Text nullable | 실패 시 에러 메시지 |
| `created_at` / `updated_at` | DateTime | TimestampMixin |

**`backtest_results` (27번째 테이블)**

신호 단위 백테스트 결과.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `run_id` | FK → backtest_runs.id NOT NULL index | |
| `recommendation_id` | FK → recommendations.id nullable | NULL = 백테스트 신호가 추천 이력에 매칭 안 됨 |
| `symbol` | String(32) NOT NULL index | |
| `signal_date` | Date NOT NULL index | 신호 발생일 |
| `entry_score` | Numeric(8,4) nullable | 신호 시점 total_score |
| `regime` | String(32) nullable index | "UPTREND_EARLY" 등 (`MarketRegimeRepository` 매칭) |
| `return_1d` | Numeric(12,4) nullable | recommendation_results 에서 가져옴 |
| `return_3d` | Numeric(12,4) nullable | |
| `return_5d` | Numeric(12,4) nullable | |
| `return_20d` | Numeric(12,4) nullable | |
| `max_drawdown` | Numeric(12,4) nullable | |
| `cost_adjusted_return_5d` | Numeric(12,4) nullable | Phase C 의 비용 모델 적용 후 |
| `result_status` | String(16) nullable | "WIN" / "LOSS" / "BREAK_EVEN" |
| `created_at` | DateTime | TimestampMixin (no updated_at — 결과는 immutable) |

UniqueConstraint(`run_id`, `symbol`, `signal_date`).

기존 테이블 변경 0건. 운영 환경 마이그레이션 = `CREATE TABLE backtest_runs ...; CREATE TABLE backtest_results ...;` 두 줄, destructive 0건.

### Score 산식 / Backtest 메트릭 (Phase B·C 상세)

**`StrategySignal` 산출 룰 (Phase A 구현체 예시):**

```
TopGradeStrategy.evaluate(snapshot):
  if snapshot.grade == "A": return BUY
  else: return PASS

HighScoreStrategy.evaluate(snapshot):
  if snapshot.total_score >= 75: return BUY
  elif snapshot.total_score <= 35: return AVOID
  else: return PASS

MultiSignalStrategy.evaluate(snapshot):
  if (snapshot.fundamental_score >= 60
      and snapshot.earnings_evidence.surprise_type == "BEAT"
      and snapshot.news_evidence.positive_count > snapshot.news_evidence.negative_count
      and snapshot.disclosure_risk_evidence.risk_disclosure_count == 0):
    return BUY
  else: return PASS
```

**Backtest 메트릭 (Phase B):**

```
win_rate = WIN_count / evaluated_signals
avg_return_5d = mean(return_5d)
max_drawdown = min(max_drawdown across signals)
sharpe_proxy = avg_return_5d / stdev(return_5d)   # 단순 비율, risk-free rate 0 가정
```

**비용 모델 (Phase C):**

```
buy_fee_rate    = 0.00015   # 0.015%
sell_fee_rate   = 0.00015   # 0.015%
sell_tax_rate   = 0.0020    # 0.20% (KRX 거래세, 코스피 기준)
slippage_rate   = 0.001     # 0.1% (보수적 추정)

cost_adjusted_return = raw_return - (buy_fee_rate + sell_fee_rate + sell_tax_rate + 2 * slippage_rate)
                     ≈ raw_return - 0.45%
```

placeholder 값. 실 broker 수수료 schedule / 종목별 거래세 / 호가 단위별 슬리피지는 v0.8+ 후보.

**시장 국면별 분리 (Phase C):**

`MarketRegimeRepository.list_by_date_range(from_date, to_date)` 로 신호 시점 regime 매칭 → `BacktestResult.regime` 컬럼 채움. 백테스트 요약은 regime 별 win_rate / avg_return 분리해서 `BacktestRun.summary_json` 에 저장.

### 프런트 노출 (Phase D 상세)

- **신규 화면 `/backtest`** (10번째 화면, Sidebar `백테스트 (β)` 메뉴 추가)
  - 상단: 전략 목록 (`/api/strategies`) + run 시작 가능 표시 (단순 안내, 실제 run 트리거는 운영자 수동 CLI — POST 미도입)
  - 중단: 최근 백테스트 run 표 (날짜 / strategy / win_rate / avg_return_5d / max DD / cost_adjusted)
  - 하단: run 클릭 시 상세 (signal 목록 + regime 별 breakdown + 비용 모델 적용 전/후 비교)
- **StockDetail 변경 0건** — 백테스트는 종목 단위가 아니라 전략 단위로 분석. StockDetail 카드는 v0.6 그대로
- **Recommendations / Holdings 변경 0건** — 백테스트는 별도 화면, 기존 추천/보유 화면에 컬럼 추가 없음
- **사이드바**: 9 → 10 메뉴

### v0.7 누적 태그 (예정)

```
v0.6-final                       ← v0.7 시작점 (HEAD e729d60)
v0.7-strategy-interface          ← Phase A 인수 (StrategyInterface + 룰 기반 전략)
v0.7-backtest-engine             ← Phase B 인수 (BacktestEngine + 신규 테이블 + CLI)
v0.7-backtest-cost-regime        ← Phase C 인수 (비용 모델 + regime 분리)
v0.7-frontend-backtest           ← Phase D 인수 (read-only API 3종 + 10번째 화면)
v0.7-final                       ← Phase E 마감 (RELEASE_NOTES_v0.7 + 4 게이트)
```

### v0.8+ 후보 (Backlog 등재용)

| 후보 | 분류 | v0.7 채택 안 한 이유 |
|---|---|---|
| Watchlist + 인증 (POST 첫 도입) | UX / 보안 | POST 정책 변경 = 별도 보안 cycle. v0.7 의 Strategy / Backtest 와 묶으면 단일 cycle 범위 초과 |
| Alembic 도입 + 마이그레이션 자동화 | 인프라 | 누적 ALTER 가 v0.5 1건 + v0.6 2건 + v0.7 신규 2건 = 5건 시점에 도입. v0.7 신규 테이블 추가 후가 진입 적기 |
| 실 DART API 구현체 (`DartFundamentalProvider` / `DartEarningsProvider`) | 데이터 / 분석 실제화 | 라이선스 / 스로틀링 / 정책 검토 동반. 라이선스 검토는 코드 cycle 외 작업 |
| 실 RSS / News API 구현체 | 데이터 라인 | v0.5 ABC 위에 추가, 라이선스 검토 |
| LLM 기반 자동 전략 생성 / 자동 평가 | AI 강화 | 룰 기반 검증 후 |
| 운영 모니터링 (Sentry / Prometheus / Grafana) | 운영 | 인증 도입 후 |
| WebSocket / SSE 실시간 백테스트 진행 상태 | 운영 | 인증 도입 후 |
| 모바일 / 태블릿 레이아웃 | UX | PC 1280px+ 우선 |
| `lightweight-charts` 마이그레이션 | UX | Recharts 한계 도달 시 |
| 실 broker 수수료 schedule + 호가 단위별 슬리피지 | 비용 정확도 | placeholder 산식 검증 후 |
| 다중 전략 동시 백테스트 + 포트폴리오 합산 | Backtest 고도화 | v0.7 단일 전략 검증 후 |

### 단계별 산출물 / 게이트 (예상)

| Phase | 신규 파일 | 변경 파일 | 게이트 (예상) | 누적 태그 |
|---|---|---|---|---|
| A | `app/strategy/interfaces.py` / `app/strategy/rule_based.py` / `tests/unit/test_rule_based_strategies.py` | (없음 — backend 전용) | backend pytest **558 → ~580 (+~22)** | `v0.7-strategy-interface` |
| B | `app/backtest/engine.py` / `app/data/repositories/backtest_runs.py` / `app/data/repositories/backtest_results.py` / `scripts/run_backtest.py` / `tests/integration/test_backtest_engine.py` / `tests/integration/test_backtest_repositories.py` | `app/db/models.py` (+2 테이블) / `app/data/repositories/__init__.py` / `DB_SCHEMA.md` (§26 §27 신규) | backend pytest **~580 → ~610 (+~30)** | `v0.7-backtest-engine` |
| C | `app/backtest/cost_model.py` / `app/backtest/regime_split.py` / `tests/unit/test_cost_model.py` / `tests/integration/test_backtest_regime.py` | `app/db/models.py` (BacktestResult.cost_adjusted_return / regime 컬럼) / Phase B 의 engine 보강 | backend pytest **~610 → ~625 (+~15)** | `v0.7-backtest-cost-regime` |
| D | `app/api/routes.py` (+3 GET) / `app/api/schemas.py` (+4 schema) / `frontend/src/api/types.ts` (+8 타입) / `frontend/src/hooks/useStrategies.ts` / `useBacktestRuns.ts` / `useBacktestRunDetail.ts` / `frontend/src/pages/Backtest/index.tsx` + 하위 컴포넌트 / `frontend/src/tests/Backtest.test.tsx` | `frontend/src/components/Sidebar.tsx` (10번째 메뉴) / `frontend/src/router.tsx` (lazy route) / `frontend/src/tests/mswServer.ts` / `frontend/e2e/fixtures/apiMocks.ts` / `frontend/e2e/dashboard.spec.ts` (10 메뉴 + 백테스트 화면 보강) | backend pytest **~625 → ~640 (+~15)** / vitest **77 → ~88 (+~11)** / e2e **13 → 15 (+2)** | `v0.7-frontend-backtest` |
| E | `RELEASE_NOTES_v0.7.md` | `README.md` / `PROJECT_STATUS.md` / `TASKS.md` / `ROADMAP.md` / `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `DB_SCHEMA.md` / `INTEGRATION_RUNBOOK.md` | 4 게이트 재확인, 회귀 0건 | `v0.7-final` |

### 위험 요소

- **`recommendation_results` 가 누적되지 않은 종목 / 기간** — `recommendation_results` 가 비어 있으면 backtest 가 skip 또는 NULL 결과. `BacktestEngine` 이 `evaluated_signals < total_signals` 명시 + summary 에 누락 비율 노출
- **비용 모델 placeholder 값의 신뢰도** — 0.45% 차감은 실제 broker / 종목 / 호가 단위에 따라 다름. `CostModel` 단위 테스트가 산식 명시 단언 + 응답 schema 에 `cost_model_version` 메타 포함 (운영자가 모델 변경 시 추적 가능)
- **시장 국면 미분류 신호** — 신호 시점에 `MarketRegime` 행이 없으면 `regime = NULL`. summary breakdown 에 "UNCLASSIFIED" bucket 명시
- **POST 미도입 정책 + 운영자 수동 CLI 의 UX 문제** — 백테스트 화면에서 "run 시작" 버튼이 동작하지 않고 안내 문구만 노출. 운영자는 `scripts/run_backtest.py` 를 별도 셸에서 실행. v0.8 의 POST 도입 시 자연스럽게 통합 가능
- **신규 테이블 2개 + 기존 ALTER 1건 누적** — Alembic 미사용 정책 유지. 운영 DB 적용 시 INTEGRATION_RUNBOOK §16 에 수동 SQL 명시
- **백테스트 결과 누설 우려** — `summary_json` / `regime` 컬럼에 종목명 / 사용자 식별 정보 포함 0건. 운영자 메모 컬럼 미추가 (저작권 정책 v0.4~v0.6 누적 유지)

**완료 기준 (cycle-wide):**

- 모든 phase 통과 / 4 게이트 그린 (backend pytest ~640 / vitest ~88 / e2e 15 / build)
- `RELEASE_NOTES_v0.7.md` 작성 완료
- 5 누적 태그 부여 + push
- 자동매매 / POST 라우터 / 실 외부 API / 본 weight 변경 0건 가드 모두 통과
- `source_file_path` 외부 노출 0건 (helper 검증)
- ScoringEngine 본 weight (recommendation: 35/25/15/15/10, holding: 35/20/20/15/10) 회귀 테스트 0건 변경 통과

---

## PLAN-0008: v0.8 User & Migration Foundation (5 Phase)

### 기준선

- 시작 태그: `v0.7-final` (HEAD `1f5b01f` 시점, origin/main 동기화 완료, 5 누적 태그 모두 push 완료)
- v0.1 ~ v0.7 모두 인수 완료. 회귀 게이트: backend pytest **682 passed (1 deselected)**, frontend vitest **84 passed**, Playwright e2e **14 passed**, build 그린
- v0.8 은 v0.7-final 위에 **Alembic baseline 도입 + 단일 사용자 인증 기반 + Watchlist DB/API + Watchlist 프런트 + Today/StockDetail 즐겨찾기 통합** 5 phase 누적이다. v0.1 부터 일관 유지된 read-only 정책의 첫 변경 — POST/DELETE 라우터가 인증 가드와 묶여서 처음 도입된다.
- v0.1 의 read-only 외부 호출 부재 / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 (본문 paragraph 미저장 / `source_file_path` 미노출) + v0.5 의 자동 fetch default OFF + v0.6 의 evidence whitelist + v0.7 의 BUY-only metrics + ScoringEngine / HoldingCheckEngine 본 weight 0건 변경 정책 모두 그대로 유지한다.
- v0.8 도 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / 실 외부 API 자동 호출 / Telegram 실 발송 0건 정책을 유지한다. **POST 도입은 인증 + Watchlist 두 영역에 한정** — 그 외 도메인의 POST/PUT/DELETE 는 추가하지 않는다.

### 후보 비교 (v0.8 진입 시점 기준)

| # | 후보 | 가치 | 난이도 | 위험 | 의존성 | v0.8 채택 |
|---|---|---|---|---|---|---|
| 1 | Alembic DB migration 도입 | 매우 높음 — 27 테이블 + v0.5/v0.6/v0.7 누적 ALTER 5건 시점. Watchlist 등 신규 테이블 추가 전에 baseline 잡는 것이 자연. SQLite/PostgreSQL 양쪽 운영 시 필수 | 낮음~중 — 기존 ORM metadata 를 baseline 으로 capture, 빈 revision 0001. `env.py` + URL 분기. CI 검증 포함 | 낮음 — baseline 단계는 destructive 0건. 운영 DB 적용 시 backup 절차 동반 | 없음 (먼저 진입 가능) | ✅ 채택 (Phase A) |
| 2 | 단일 사용자 인증 / 보안 | 매우 높음 — POST 라우터 첫 도입의 전제. 외부 노출 시 필수. `AUTH_ENABLED` 토글 → 로컬 dev / CI 호환성 유지 | 중 — bcrypt + JWT (HS256) + 미들웨어 + 보호 라우터 데코레이터. audit log 동반 | 중 — 잘못 설계 시 v0.9+ 모든 POST cycle 에 영향. JWT 비밀키 / 토큰 TTL / refresh 정책 신중 | 없음 (DB 신규 테이블 1~2개) | ✅ 채택 (Phase B) |
| 3 | Watchlist / 관심종목 (POST 첫 도입) | 매우 높음 — 사용자 체감 가치 최대. POST 라우터 첫 도입 후보로 이상적 (단일 사용자 + 단일 도메인) | 중 — DB 2 테이블 + GET/POST/DELETE 라우터 + 인증 가드. 프런트 즐겨찾기 토글 + Today 카드 통합 | 중 — POST 첫 도입은 v0.1~v0.7 일관 정책의 첫 변경. 인증 동반 필수 | Phase B (인증) 의존 | ✅ 채택 (Phase C·D) |
| 4 | 사용자 설정 (관심 시장 / 기본 필터 / 알림 선호도) | 중 — 단일 사용자 환경에서는 즉각 가치 작음. 인증 후 자연스럽게 확장 가능 | 중 — `UserPreference` 테이블 + GET/PUT 라우터 + 프런트 Settings 화면 보강 | 낮음 | Phase B (인증) 의존 | ❌ v0.9 후보 (Watchlist 와 묶어서 너무 큼) |
| 5 | 운영 모니터링 (Sentry / Prometheus / Grafana) | 중 — 외부 노출 / 다중 사용자 시점에 중요. 단일 사용자 + 로컬 환경에서는 즉각 가치 작음 | 낮음~중 — Sentry SDK + Prometheus exporter + Grafana 대시보드 | 낮음 — read-only | 인증 도입 후 더 가치 | ❌ v0.9 후보 (외부 노출 시점에 함께) |
| 6 | 실 DART API 구현체 | 중~높음 — 운영자 수동 CSV burden 제거 | 높음 — 외부 API 라이선스 / rate limit / 실패 격리 / retry / 데이터 정규화 | 높음 — 외부 의존성 첫 도입. **라이선스 검토 (사람) 가 가장 큰 불확실성** | 라이선스 검토 선행 | ❌ v0.9+ 후보 (라이선스 검토 + 별도 cycle) |
| 7 | 실 RSS / News API 구현체 | 중~높음 | 높음 | 높음 | 라이선스 검토 선행 | ❌ v0.9+ 후보 |
| 8 | LLM 자동 전략 생성 | 중 — 룰 기반 검증 후 단계 | 높음 | 높음 | v0.7 룰 기반 검증 누적 후 | ❌ v0.10+ 후보 |
| 9 | 백테스트 고도화 (multi-strategy / walk-forward / per-symbol stamp duty) | 중 — v0.7 placeholder 검증 후 | 중~높음 | 낮음 | v0.7 사용 데이터 누적 후 | ❌ v0.9+ 후보 |
| 10 | 자동매매 / 실주문 | (위험) | 매우 높음 | 매우 높음 | 모든 위 + 컴플라이언스 + Strategy/Backtest 실 검증 + MockBroker 후행 | ❌ Future Backlog (별도 보안/컴플라이언스/자본 한도 사이클 선행) |

### 시나리오 옵션

**Scenario X — Alembic + 인증 + Watchlist (권장 ✅)**

- Phase A: Alembic baseline (`alembic init` + `env.py` + 27 테이블 baseline revision `0001_baseline_v0_7` + CI `alembic upgrade head` 검증)
- Phase B: 단일 사용자 인증 (`User` 28번째 테이블 + `LoginAuditLog` 29번째 + JWT + `AUTH_ENABLED` 토글 + `POST /api/auth/login` 첫 POST + 보호 데코레이터 + `scripts/create_admin.py` CLI)
- Phase C: Watchlist DB/API (`Watchlist` 30번째 + `WatchlistItem` 31번째 + GET/POST/DELETE 라우터 + 인증 가드 + Alembic revision `0002_watchlist`)
- Phase D: Watchlist 프런트 + Today/StockDetail 통합 (11번째 화면 `/watchlist` + StockDetail 즐겨찾기 별 토글 + Today "내 관심종목" 카드 + Recommendations 즐겨찾기 컬럼)
- Phase E: 마감 (`RELEASE_NOTES_v0.8.md` + 4 게이트 재확인 + tag `v0.8-final`)

**Scenario Y — Alembic 만 도입 + 인증/Watchlist 는 v0.9 분리**

- Phase A: Alembic baseline
- Phase B: Alembic 운영 가이드 + INTEGRATION_RUNBOOK 보강 + offline mode SQL 출력
- Phase C: 백테스트 화면 보강 (regime breakdown 시각화 / cost_model 변경 추적 등 v0.7 후속)
- Phase D: README / 문서 정리
- Phase E: 마감
- **단점**: cycle 가치가 작음. POST 라우터 / 인증은 결국 v0.9 에서 해야 하므로 분할 의미가 적음. Alembic baseline 자체는 1주 미만 작업

**Scenario Z — Watchlist 만 인증 없이 (로컬 단일 사용자용)**

- Phase A: Alembic baseline
- Phase B: Watchlist DB/API (POST 도입, 인증 가드 없이 단일 사용자 fixed user_id=1)
- Phase C: Watchlist 프런트
- Phase D: Today / StockDetail 통합
- Phase E: 마감
- **위험**: POST 라우터를 인증 없이 도입하면 외부 노출 시 즉시 위험. 일단 로컬용으로 풀고 나중에 retrofit 하는 것은 보안 antipattern. 단일 사용자 → 다중 사용자 retrofit 비용 매우 큼. **권장하지 않음**

**Scenario W — 운영 모니터링 우선**

- Phase A: Sentry 통합
- Phase B: Prometheus exporter + Grafana 대시보드
- Phase C: job_health dashboard 보강
- Phase D: Alembic baseline
- Phase E: 마감
- **단점**: 단일 사용자 + 로컬 환경에서는 모니터링의 즉각 가치 작음. POST 라우터 도입의 전제인 인증을 미루는 것은 v0.9 에서 동일한 cycle 이 또 발생함. 외부 노출 시점에 함께 도입하는 것이 자연스러움

**최종 추천**: **Scenario X — Alembic + 인증 + Watchlist (User & Migration Foundation)**. 이유:

- v0.7 마감 시점에 27 테이블 + 누적 ALTER 5건 → Alembic 도입 적기. **Watchlist 등 신규 테이블 추가 전에 baseline 잡는 것이 자연**
- v0.7 까지 read-only 일관 정책으로 POST 라우터 0건. Watchlist 는 사용자 체감 가치가 매우 크고 POST 첫 도입의 자연스러운 후보 (단일 도메인 + 단일 사용자 + audit log 동반)
- **인증 없이 POST 만 도입은 위험 (Scenario Z)** — 인증과 Watchlist 를 묶는 것이 보안 정합성 측면에서 옳음
- Alembic + 인증 + Watchlist 를 한 cycle 에 묶는 것은 단일 cycle 범위로 적절 (v0.4·v0.6 의 5 phase 패턴과 동일 규모)
- ScoringEngine / HoldingCheckEngine 본 weight 변경 0건, 자동매매 / 실 KIS / DART / Telegram 호출 0건 — v0.1~v0.7 일관 정책 그대로
- 사용자 명시 추천 (User & Migration Foundation) 과 정렬

향후 권장 cycle 순서:

- v0.8 (이번): Alembic + 인증 + Watchlist (Scenario X)
- v0.9: 사용자 설정 + 운영 모니터링 (Sentry / Prometheus) + 백테스트 화면 보강
- v0.10: 실 DART / 실 RSS provider (라이선스 검토 후) + 백테스트 고도화 (walk-forward 등)
- v0.11+: APPROVAL 모드 진입 검토 (별도 보안/컴플라이언스 cycle 선행)

### 범위 (5 Phase)

- **Phase A — Alembic baseline 도입**
  `alembic.ini` + `alembic/env.py` (SQLite + PostgreSQL URL 분기, `app.db.models.Base.metadata` 참조) + `alembic/versions/0001_baseline_v0_7.py` (현 27 테이블 baseline, 빈 upgrade/downgrade — 기존 metadata snapshot) + `scripts/migrate.py` 보조 (alembic upgrade/downgrade wrapper) + `tests/integration/test_alembic_migration.py` (`alembic upgrade head` 후 ORM metadata 와 비교, autogenerate diff 0건 단언) + CI 잡 추가 (`alembic upgrade head` 검증). **신규 테이블 0건 / 라우터 0건 / 프런트 0건 / 자동매매 0건** — baseline 만.
- **Phase B — 단일 사용자 인증 기반**
  `app/db/models.py` (+`User` 28번째 + `LoginAuditLog` 29번째) + `app/data/repositories/users.py` + `app/data/repositories/login_audit_logs.py` + `app/auth/__init__.py` (`AuthService` + `JwtIssuer` + `PasswordHasher` (`bcrypt`) + `AUTH_ENABLED` flag) + `app/auth/dependencies.py` (`get_current_user` FastAPI Depends + `require_auth` 데코레이터) + `app/api/auth_routes.py` (`POST /api/auth/login` 첫 POST + `POST /api/auth/logout` + `GET /api/auth/me`) + `scripts/create_admin.py` argparse CLI (default dry-run, `--commit` 시 단일 admin user 생성, password prompt) + `alembic/versions/0002_user_audit.py` + 단위/통합 테스트 보강.
- **Phase C — Watchlist DB / API**
  `app/db/models.py` (+`Watchlist` 30번째 + `WatchlistItem` 31번째) + `app/data/repositories/watchlists.py` + `app/data/repositories/watchlist_items.py` + `app/api/routes.py` (+`GET /api/watchlists`, `GET /api/watchlists/{id}/items`, `POST /api/watchlists/{id}/items`, `DELETE /api/watchlists/{id}/items/{symbol}` — POST/DELETE 는 `require_auth` 가드) + `app/api/schemas.py` (`WatchlistSchema` / `WatchlistItemSchema` / `WatchlistCreateRequest` / `WatchlistItemAddRequest`) + `alembic/versions/0003_watchlist.py` + 통합 테스트 보강 (인증 OFF 시 401 / 인증 ON + JWT 시 200 / forbidden 키 미노출).
- **Phase D — Watchlist 프런트 + Today / StockDetail 통합**
  `frontend/src/pages/Watchlist/index.tsx` 신규 (11번째 화면, 즐겨찾기 종목 표 + 추가/삭제 폼) + `frontend/src/components/layout/Sidebar.tsx` (10 → 11 메뉴, `Star` 아이콘) + `frontend/src/router.tsx` (`/watchlist` lazy route) + `frontend/src/hooks/useWatchlist.ts` / `useWatchlistItems.ts` / `useAddWatchlistItem.ts` / `useRemoveWatchlistItem.ts` (`useMutation` 첫 도입) + `frontend/src/components/auth/LoginForm.tsx` (단순 토큰 입력 또는 username/password 폼, JWT localStorage 저장) + `frontend/src/api/client.ts` (Authorization 헤더 자동 첨부, 401 시 재로그인 redirect) + StockDetail 헤더에 즐겨찾기 별 토글 + Today 화면 "내 관심종목" 카드 신규 + Recommendations 표 즐겨찾기 컬럼 + msw + e2e 보강.
- **Phase E — `RELEASE_NOTES_v0.8.md` 신규 + README / PROJECT_STATUS / TASKS / ROADMAP / ARCHITECTURE / API_SPEC / TESTING / DB_SCHEMA / INTEGRATION_RUNBOOK 마감 + 4 게이트 재확인 + tag `v0.8-final`.**

### 제외 범위 (v0.8 에서 절대 하지 않을 것)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ Broker 구현 (`BrokerInterface` placeholder 유지)
- ❌ POST 라우터 확장 — `POST /api/auth/login` + `POST/DELETE /api/watchlists/...` **2 도메인만**. 그 외 (Recommendations / Holdings / Backtest / 잡 트리거 / 알림 / 점수 등) POST/PUT/DELETE 0건
- ❌ 실 DART / 실 RSS / 실 News API 호출 (v0.5 / v0.6 의 ABC + Fake provider 정책 유지)
- ❌ MockBroker / ReplayBroker / SimulationBroker (v0.10+ 검토)
- ❌ ScoringEngine 본 weight 변경 — RecommendationEngine / HoldingCheckEngine 산식 0건 변경
- ❌ HoldingCheckEngine 산식 변경
- ❌ LLM 자동 전략 생성 / 자동 분석
- ❌ 운영 모니터링 (Sentry / Prometheus / Grafana) — v0.9 후보
- ❌ Watchlist 자동 텔레그램 알림 — 알림 시스템 변경 0건 (v0.9 후보)
- ❌ 다중 사용자 / SaaS / 권한 (RBAC) — 단일 admin user 만
- ❌ OAuth / SSO — 단일 username/password + bcrypt + JWT 만
- ❌ Refresh token / token revocation list — 24h JWT TTL + 재로그인만
- ❌ 비밀번호 변경 / 비밀번호 재설정 / 이메일 발송 — 운영자 수동 (`scripts/create_admin.py` 재실행 또는 DB 직접 수정)
- ❌ WebSocket / SSE — 폴링 그대로
- ❌ Recommendations / Backtest / Today 의 개인화 알고리즘 변경 — 즐겨찾기는 표시/필터만, 산식 변경 0건
- ❌ 알람 (price alert / target return alert) — Watchlist 메모만, 트리거 0건

### Alembic baseline 전략

**baseline revision (`0001_baseline_v0_7`)**:

- v0.7 마감 시점의 27 테이블 metadata 를 그대로 baseline 으로 잡는다
- `upgrade()` / `downgrade()` 둘 다 빈 함수 (`pass`) — 운영/dev DB 가 이미 27 테이블을 가지고 있음을 가정 (`scripts/init_db.py` 또는 ORM `Base.metadata.create_all()` 로 생성)
- **CI / 신규 환경 호환**: `alembic upgrade head` 가 빈 DB 에 대해 동작하지 않게, baseline revision 의 `upgrade()` 가 `Base.metadata.create_all(bind=op.get_bind())` 호출 (한 번만). 또는 별도 `--init` 플래그로 분기
- 대안: baseline 을 `op.create_table(...)` 27건 SQL 로 풀어 쓰기 (autogenerate). **권장** — 표준 Alembic 패턴 + offline mode SQL 출력 가능 + 신규 환경에서 `alembic upgrade head` 하나로 DB 구축 가능
- baseline 이후 모든 변경은 신규 revision 으로 (Phase B `0002_user_audit.py` + Phase C `0003_watchlist.py`)

**`env.py` 설계**:

- `target_metadata = app.db.models.Base.metadata`
- `sqlalchemy.url` 은 `app.config.get_settings().database_url` 에서 읽기 (SQLite / PostgreSQL 양쪽 지원)
- offline mode SQL 출력 가능 (`alembic upgrade head --sql`)

**CI 검증**:

- 신규 GitHub Actions 잡: `pytest tests/integration/test_alembic_migration.py` — 임시 SQLite 에 `alembic upgrade head` → ORM metadata 와 비교 (`MigrationContext.compare_metadata` 결과 0건 단언)
- 기존 backend / frontend / e2e 잡 그대로

**운영 DB 적용 절차** (`INTEGRATION_RUNBOOK.md` §17 신규):

```text
1. 운영 DB backup (sqlite: 파일 복사 / postgres: pg_dump)
2. alembic stamp 0001_baseline_v0_7   # 기존 27 테이블이 있는 운영 DB 를 baseline 으로 marking
3. alembic upgrade head                 # Phase B/C 의 0002, 0003 적용
4. smoke test (pytest --smoke + 4 화면 수동)
5. 실패 시 rollback (alembic downgrade -1)
```

### 인증 정책

**`AUTH_ENABLED` 토글** (`app/config.py` 의 `Settings` 에 신규):

| 환경 | `AUTH_ENABLED` 기본값 | 동작 |
|---|---|---|
| dev / local | `false` | `require_auth` 가드가 우회 — 모든 라우터 OPEN. 단일 admin user 자동 사용 (`get_current_user` 가 user_id=1 fixed return) |
| CI | `false` | dev 동일 — 기존 회귀 테스트 그대로 통과 |
| prod | `true` (운영자가 `.env` 명시) | `require_auth` 가드 활성. 보호 라우터 (POST /api/auth/login 제외 모든 POST/DELETE) 가 401 반환 |

- 보호 라우터: `POST /api/watchlists/{id}/items`, `DELETE /api/watchlists/{id}/items/{symbol}`, `POST /api/auth/logout`, `GET /api/auth/me`
- 비보호 라우터: 기존 GET 라우터 모두 + `POST /api/auth/login`
- **GET 보호 옵션**: `Settings.protect_get_routes` (default `false`) — 외부 공개 시 운영자가 명시 enable 시에만 GET 도 401 반환
- **JWT 정책**:
  - HS256, secret 은 `Settings.jwt_secret` (default 미설정, prod 에서 미설정 시 startup 거부)
  - TTL 24h (`Settings.jwt_ttl_hours = 24`)
  - Refresh token 미도입 — 만료 시 재로그인. `iat` / `exp` claim 만
  - JWT payload 에 `user_id` + `username` 만 (이메일 / role 미도입)
- **bcrypt**: cost factor 12 (Phase B 단위 테스트는 cost 4 로 빠르게)
- **audit log** (`LoginAuditLog`):
  - 모든 `POST /api/auth/login` 시도 (성공/실패) 기록
  - `event` IN (`LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`)
  - `source_ip` 는 SHA256 해시만 저장 (개인정보 미저장)
  - `user_agent` 는 길이 제한 (≤255)

### Watchlist 데이터 모델

**`watchlists` (30번째 테이블)**:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users.id NOT NULL index | 단일 사용자 환경에서는 1 fixed |
| `name` | String(64) NOT NULL | "기본" / "단기" / "장기" 등 |
| `is_default` | Boolean NOT NULL default false | 사용자당 1개만 default |
| `created_at` / `updated_at` | DateTime | TimestampMixin |

UniqueConstraint(`user_id`, `name`).

**`watchlist_items` (31번째 테이블)**:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `watchlist_id` | FK → watchlists.id NOT NULL index ON DELETE CASCADE | |
| `symbol` | String(32) NOT NULL index | KRX 6자리 |
| `memo` | String(500) nullable | 운영자 메모 (≤500자) |
| `added_at` | DateTime NOT NULL default now | |
| `created_at` / `updated_at` | DateTime | TimestampMixin |

UniqueConstraint(`watchlist_id`, `symbol`).

**`users` (28번째 테이블)**:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `username` | String(64) NOT NULL unique index | |
| `password_hash` | String(255) NOT NULL | bcrypt hash |
| `is_active` | Boolean NOT NULL default true | |
| `created_at` / `updated_at` | DateTime | TimestampMixin |

**`login_audit_logs` (29번째 테이블)**:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK → users.id nullable index | LOGIN_FAILED 시 user 미식별 가능 → NULL |
| `attempted_username` | String(64) nullable | LOGIN_FAILED 시 입력된 username (감사용) |
| `event` | String(32) NOT NULL index | LOGIN_SUCCESS / LOGIN_FAILED / LOGOUT |
| `source_ip_hash` | String(64) nullable | SHA256(source_ip) — 평문 IP 저장 0건 |
| `user_agent` | String(255) nullable | |
| `occurred_at` | DateTime NOT NULL default now index | |
| `created_at` | DateTime | TimestampMixin (no updated_at — 로그는 immutable) |

운영자가 ROW 삭제 가능하도록 별도 retention CLI (Phase B 부수 — `scripts/purge_login_audit.py`, default dry-run, ≥90일 행 삭제).

### 프런트 노출 (Phase D 상세)

- **신규 화면 `/watchlist`** (11번째 화면, Sidebar `관심종목 ★` 메뉴 추가) — 즐겨찾기 종목 표 (symbol / 종목명 / 현재가 / 등락률 / 추가일 / 메모 / 삭제 버튼) + 추가 폼 (symbol 입력 + 메모 입력 + 추가 버튼). 단일 watchlist (default `기본`) 만 노출
- **StockDetail 헤더** — 즐겨찾기 별 토글 (★/☆) 추가. 클릭 시 `useAddWatchlistItem` / `useRemoveWatchlistItem` mutation
- **Today 화면 "내 관심종목" 카드** — 즐겨찾기 종목의 오늘 등락률 / 추천 / 점수 요약 (read-only, 자동 alert 0건)
- **Recommendations 표** — 종목 옆에 즐겨찾기 별 컬럼 (시각적 표시만, 정렬 변경 0건)
- **Sidebar**: 10 → 11 메뉴 (`Star` 아이콘, `백테스트 (β)` 아래)
- **로그인 화면** — `Settings.AUTH_ENABLED = true` 시 모든 화면 진입 전 `/login` redirect. 단순 username/password 폼. JWT 는 `localStorage.auth_token` 저장 + `Authorization: Bearer ...` 자동 첨부. 401 시 `/login` 재진입
- **`AUTH_ENABLED = false` 모드**: 로그인 화면 우회, 모든 화면 그대로. 즐겨찾기 mutation 도 user_id=1 fixed 로 동작 (개발 호환성)

### v0.8 누적 태그 (예정)

```
v0.7-final                     ← v0.8 시작점 (HEAD 1f5b01f)
v0.8-alembic-baseline          ← Phase A 인수 (Alembic init + baseline revision + CI 검증)
v0.8-auth-foundation           ← Phase B 인수 (User + LoginAuditLog + JWT + AUTH_ENABLED + 첫 POST)
v0.8-watchlist-api             ← Phase C 인수 (Watchlist + WatchlistItem + GET/POST/DELETE + 인증 가드)
v0.8-frontend-watchlist        ← Phase D 인수 (11번째 화면 + StockDetail/Today 통합 + 로그인 화면)
v0.8-final                     ← Phase E 마감 (RELEASE_NOTES_v0.8 + 4 게이트)
```

### v0.9+ 후보 (Backlog 등재용)

| 후보 | 분류 | v0.8 채택 안 한 이유 |
|---|---|---|
| 사용자 설정 (관심 시장 / 기본 필터 / 알림 선호도) | UX | Watchlist 와 묶으면 단일 cycle 범위 초과. v0.9 자연 후보 |
| 운영 모니터링 (Sentry / Prometheus / Grafana) | 운영 | 외부 노출 시점에 함께 도입 권장. v0.9 인증 도입 검증 후 |
| 실 DART API 구현체 | 데이터 / 분석 실제화 | 라이선스 검토 (사람 작업) 가 코드 cycle 외 단계 |
| 실 RSS / News API 구현체 | 데이터 라인 | 라이선스 검토 동반 |
| 백테스트 고도화 (multi-strategy / walk-forward / per-symbol stamp duty) | Backtest | v0.7 placeholder 운영 데이터 누적 후 |
| LLM 보강 (sentiment / 재무 분석 / 자동 전략) | AI | 룰 기반 검증 + 운영 데이터 누적 후 |
| WebSocket / SSE 실시간 잡 / 백테스트 진행 | UX | 인증 도입 후 가치 ↑ |
| 모바일 / 태블릿 레이아웃 | UX | PC 1280px+ 우선 |
| `lightweight-charts` 마이그레이션 | UX | Recharts 한계 도달 시 |
| Watchlist 가격 알림 / target return alert | 알림 | 알림 시스템 변경 = 별도 cycle |
| 다중 사용자 / SaaS / RBAC | 인증 고도화 | 단일 사용자 검증 후 |
| OAuth / SSO | 인증 고도화 | 단일 사용자 검증 후 |
| Refresh token / token revocation | 인증 고도화 | 24h TTL 운영 검증 후 |

### 단계별 산출물 / 게이트 (예상)

| Phase | 신규 파일 | 변경 파일 | 게이트 (예상) | 누적 태그 |
|---|---|---|---|---|
| A | `alembic.ini` / `alembic/env.py` / `alembic/script.py.mako` / `alembic/versions/0001_baseline_v0_7.py` / `scripts/migrate.py` / `tests/integration/test_alembic_migration.py` | `requirements.txt` (+`alembic`) / `INTEGRATION_RUNBOOK.md` (§17 신규) / `.github/workflows/ci.yml` (alembic 검증 step) | backend pytest **682 → ~692 (+~10)** | `v0.8-alembic-baseline` |
| B | `app/db/models.py` (+User + LoginAuditLog) / `app/data/repositories/users.py` / `app/data/repositories/login_audit_logs.py` / `app/auth/__init__.py` / `app/auth/dependencies.py` / `app/api/auth_routes.py` / `scripts/create_admin.py` / `scripts/purge_login_audit.py` / `alembic/versions/0002_user_audit.py` / `tests/unit/test_auth_service.py` / `tests/integration/test_auth_routes.py` | `app/api/main.py` (auth router include) / `app/config.py` (`AUTH_ENABLED` / `JWT_SECRET` / `JWT_TTL_HOURS` / `PROTECT_GET_ROUTES`) / `requirements.txt` (+`bcrypt`, +`pyjwt`) / `DB_SCHEMA.md` (§28 §29 신규) | backend pytest **~692 → ~735 (+~43)** | `v0.8-auth-foundation` |
| C | `app/db/models.py` (+Watchlist + WatchlistItem) / `app/data/repositories/watchlists.py` / `app/data/repositories/watchlist_items.py` / `alembic/versions/0003_watchlist.py` / `tests/integration/test_watchlist_routes.py` | `app/api/routes.py` (+4 라우터) / `app/api/schemas.py` (+4 schema) / `DB_SCHEMA.md` (§30 §31 신규) / `API_SPEC.md` (Watchlist 섹션 신규) | backend pytest **~735 → ~770 (+~35)** | `v0.8-watchlist-api` |
| D | `frontend/src/pages/Watchlist/index.tsx` / `frontend/src/pages/Login/index.tsx` / `frontend/src/components/auth/LoginForm.tsx` / `frontend/src/hooks/useWatchlist.ts` / `useWatchlistItems.ts` / `useAddWatchlistItem.ts` / `useRemoveWatchlistItem.ts` / `useAuthStatus.ts` / `frontend/src/api/auth.ts` / `frontend/src/tests/Watchlist.test.tsx` / `frontend/src/tests/Login.test.tsx` | `frontend/src/api/client.ts` (Authorization 자동 첨부 + 401 redirect) / `frontend/src/components/layout/Sidebar.tsx` (11 메뉴) / `frontend/src/router.tsx` (`/watchlist` + `/login` lazy) / `frontend/src/pages/StockDetail/...` (즐겨찾기 별 토글) / `frontend/src/pages/Today/...` (내 관심종목 카드) / `frontend/src/pages/Recommendations/...` (즐겨찾기 컬럼) / `frontend/src/tests/mswServer.ts` / `frontend/e2e/fixtures/apiMocks.ts` / `frontend/e2e/dashboard.spec.ts` (11 메뉴 + Watchlist + Login 경로) | backend pytest **~770 → ~775 (+~5)** / vitest **84 → ~95 (+~11)** / e2e **14 → 16 (+2)** | `v0.8-frontend-watchlist` |
| E | `RELEASE_NOTES_v0.8.md` | `README.md` / `PROJECT_STATUS.md` / `TASKS.md` / `ROADMAP.md` / `ARCHITECTURE.md` / `API_SPEC.md` / `TESTING.md` / `DB_SCHEMA.md` / `INTEGRATION_RUNBOOK.md` | 4 게이트 재확인, 회귀 0건 | `v0.8-final` |

### 위험 요소

- **Alembic baseline 의 빈 DB 호환성** — baseline revision 을 빈 함수로 두면 신규 환경에서 `alembic upgrade head` 가 DB 를 생성하지 못함. baseline 을 `op.create_table()` 27건 SQL 로 풀어 쓰는 표준 패턴 채택 + autogenerate diff 0건 단언 테스트로 방어
- **운영 DB 의 Alembic stamp 누락** — 기존 운영 DB 가 27 테이블을 갖고 있는데 `alembic upgrade head` 시도 시 `0001_baseline_v0_7` 의 `create_table` 이 IntegrityError. INTEGRATION_RUNBOOK §17 에 `alembic stamp 0001_baseline_v0_7` 절차 명시 + Phase A 통합 테스트가 stamp 시나리오 커버
- **`AUTH_ENABLED = false` 모드의 보안 함정** — dev / CI 호환성을 위해 가드 우회. 운영자가 prod 배포 시 `.env` 에 명시 enable 안 하면 인증 무력화. `app/api/main.py` startup 시 `AUTH_ENABLED=false` + `prod` 환경 결합 시 경고 로그 + Sentry 대체 stderr 경고. 운영 가이드 INTEGRATION_RUNBOOK §17·§18 에 명시
- **JWT secret 미설정** — `JWT_SECRET` 미설정 + `AUTH_ENABLED=true` 시 startup 거부 (`ValueError: JWT_SECRET required when AUTH_ENABLED=true`). `scripts/create_admin.py` 첫 실행 시 secret 생성 가이드 출력
- **단일 사용자 환경에서 user_id=1 fixed 의 retrofit 비용** — 다중 사용자 도입 시 `Watchlist.user_id` 가 이미 FK 로 잡혀 있어 자연스럽게 확장 가능. 모든 라우터가 `get_current_user()` 통해 user 추출 — fixed user 의존성 0건 (Phase B 단위 테스트로 가드)
- **bcrypt cost 12 의 단위 테스트 속도** — 단위 테스트는 cost 4 사용 (`PasswordHasher(cost_factor=4)` injection), 통합 테스트만 cost 12. CI 시간 영향 ≤ +5초
- **POST 라우터 첫 도입의 evidence 노출 위험** — POST `/api/watchlists/{id}/items` body 에 `symbol` + `memo` 만. 응답에 `broker` / `account` / `quantity` / `order_*` / `source_file_path` 0건. v0.7 의 forbidden token 가드가 e2e 에서 raw JSON 트리 검사로 자동 커버 (`/watchlist` 추가)
- **POST 도입 후 mutation rate limit 미도입** — v0.8 은 단일 사용자 + 로컬 환경 가정. rate limit 은 v0.9 운영 모니터링 cycle 후보 (`slowapi` 등)
- **CSRF / SameSite 정책** — JWT 는 localStorage 저장 → CSRF 자동 보호. 단, XSS 위험은 별도 (v0.2 부터 React 의 자동 escape 의존). `Content-Security-Policy` 헤더 도입은 v0.9 운영 모니터링 cycle 후보
- **누적 신규 테이블 4개 + Alembic 도입** — 27 → 31 테이블. `DB_SCHEMA.md` 에 §28·§29·§30·§31 신규 + Alembic revision 흐름 도식. 기존 ALTER 0건 (모든 신규는 신규 테이블만)
- **Phase D 의 `useMutation` 첫 도입** — v0.7 까지 `useQuery` 만 사용. msw v2 의 mutation 응답 패턴 + Playwright 의 mutation flow 가드 (성공 → 즐겨찾기 ★ 활성, 실패 → toast). `frontend/src/tests/Watchlist.test.tsx` 가 happy / 401 / 500 / network error 4 시나리오 커버

**완료 기준 (cycle-wide):**

- 모든 phase 통과 / 4 게이트 그린 (backend pytest ~775 / vitest ~95 / e2e 16 / build)
- `RELEASE_NOTES_v0.8.md` 작성 완료
- 5 누적 태그 부여 + push
- POST 라우터 = 5건만 (`POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/watchlists/{id}/items`, `DELETE /api/watchlists/{id}/items/{symbol}`, `GET /api/auth/me`) — 그 외 도메인 POST/PUT/DELETE 0건 가드
- 자동매매 / 실 KIS / DART / Telegram 자동 호출 0건 가드
- ScoringEngine 본 weight (recommendation: 35/25/15/15/10, holding: 35/20/20/15/10) 회귀 테스트 0건 변경 통과
- `AUTH_ENABLED=false` 모드에서 v0.7 회귀 테스트 100% 그대로 통과 (CI 호환성)
- `AUTH_ENABLED=true` + JWT 시 보호 라우터 401/200 분기 단언
- `source_file_path` / `broker` / `account` / `quantity` / `order_*` 외부 노출 0건 (helper 검증, Watchlist 응답 포함)
- Alembic `compare_metadata` diff 0건 단언 (baseline 정합성)

---

## PLAN-0009: v0.9 Operational Security & Watchlist Polish (5 Phase)

### 기준선

- 시작 태그: `v0.8-final` (HEAD `80f0bac` 시점, origin/main 동기화 완료, 5 누적 태그 모두 push 완료)
- v0.1 ~ v0.8 모두 인수 완료. 회귀 게이트: backend pytest **808 passed (1 deselected)**, frontend vitest **113 passed**, Playwright e2e **19 passed**, build 그린
- v0.9 는 v0.8-final 위에 **보안 강화 + 운영 모니터링 + Watchlist API 고도화 + UserPreference 기초** 5 phase 누적이다. v0.8 에서 POST 라우터(5건)와 인증(JWT + scrypt)이 도입되었으므로, v0.9 에서는 그 위에 운영 필수 기반(rate limit / security headers / Sentry) 과 UX 고도화(Watchlist rename/delete/default + 메모 편집 + UserPreference) 를 쌓는다.
- v0.1 의 자동매매 부재 / 실 KIS 주문 0건 / DRY_RUN 기본 / mock·Fake provider 정책 + v0.4 의 저작권 정책 + v0.5 의 자동 fetch default OFF + v0.6 의 evidence whitelist + v0.7 의 BUY-only metrics + v0.8 의 POST 5건 한정 + 단일 사용자 정책 모두 그대로 유지한다.
- v0.9 도 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / 실 외부 API 자동 호출 / Telegram 실 발송 0건 정책을 유지한다. **실 DART / 실 RSS provider 구현은 라이선스 검토(사람) 선행 없이 코드 추가 불가** — v0.9 에서는 인터페이스 + 회복성 레이어(retry decorator / failure isolation / provider_status enum) 강화만 수행한다.

### 후보 비교 (v0.9 진입 시점 기준)

| # | 후보 | 가치 | 난이도 | 위험 | 외부 의존성 | 라이선스 위험 | v1.0 기여 | v0.9 채택 |
|---|---|---|---|---|---|---|---|---|
| 1 | 보안 강화 (rate limit / security headers / brute force) | 높음 — POST 라우터 운영 전 필수. rate limit 없으면 login endpoint 노출 위험 | 낮음~중 — `slowapi` + middleware 추가 | 낮음 | slowapi (MIT) | 없음 | 매우 높음 | ✅ 채택 (Phase A) |
| 2 | 운영 모니터링 (Sentry + 구조화 로깅) | 높음 — v0.9 부터 외부 노출 가능성 증가. 장애 가시성 필수 | 낮음~중 — sentry-sdk (SENTRY_ENABLED=false 기본) + LOG_FORMAT=json env | 낮음 | sentry-sdk (BSL) | 없음 | 높음 | ✅ 채택 (Phase B) |
| 3 | Watchlist API 고도화 (PUT rename / DELETE list / default / 메모) | 중~높음 — 사용자 체감 가치. v0.8 에서 create/add/delete-item 만 구현 | 중 — PUT/DELETE 신규 라우터 4건 + cascade delete + Alembic revision | 낮음 | 없음 | 없음 | 중 | ✅ 채택 (Phase C) |
| 4 | UserPreference 기초 (기본 watchlist / 기본 시장 / 기본 전략) | 중 — 단일 사용자이므로 즉각 가치 작음. 하지만 32번째 테이블 + GET/PUT preference API 는 향후 다중 사용자 기반 | 중 — 신규 테이블 + Alembic revision + GET/PUT /api/me/preferences | 낮음 | 없음 | 없음 | 중~높음 | ✅ 채택 (Phase C, Watchlist 와 묶음) |
| 5 | Provider 회복성 레이어 (retry decorator / failure isolation / status enum) | 중 — 실 provider 없는 상태에서도 인터페이스 강화. `/api/jobs` 응답에 provider health 추가 | 낮음~중 — ABC + Fake provider 내부 리팩터. 실 provider 구현 0건 | 낮음 | 없음 | 없음 | 높음 | ✅ 채택 (Phase C, 범위 내) |
| 6 | Frontend 관리 UI (Watchlist rename/delete/default + 메모 인라인 편집 + Settings 화면) | 중~높음 — Phase C API 없이 진행 불가. Phase C 와 연동 | 중 — React mutation + vitest + e2e 보강 | 낮음 | 없음 | 없음 | 중 | ✅ 채택 (Phase D) |
| 7 | 실 DART API 구현체 | 중~높음 | 높음 | 높음 | 외부 API 높음 | **라이선스 검토 필수 (사람)** | 높음 | ❌ v0.9+ 후보 — 라이선스 검토 선행 |
| 8 | 실 RSS / News API 구현체 | 중~높음 | 높음 | 높음 | 외부 API 높음 | **라이선스 검토 필수 (사람)** | 높음 | ❌ v0.9+ 후보 — 라이선스 검토 선행 |
| 9 | 백테스트 고도화 (walk-forward / multi-strategy / per-symbol slippage) | 높음 (v1.0) | 높음 | 낮음 | 없음 | 없음 | 매우 높음 | ❌ v0.10 후보 — v0.7~v0.8 데이터 누적 필요 |
| 10 | 인증 고도화 (다중 사용자 / OAuth / refresh token) | 중 | 높음 | 중 | 없음 | 없음 | 높음 | ❌ v0.10+ 후보 — 단일 사용자 운영 검증 후 |
| 11 | LLM 자동 전략 생성 | 낮음~중 | 매우 높음 | 높음 | LLM API | 없음 | 중 | ❌ v0.11+ 후보 |
| 12 | 자동매매 / 실주문 | (위험) | 매우 높음 | 매우 높음 | KIS 실 주문 API | 라이선스 + 컴플라이언스 | — | ❌ Future Backlog |

### 시나리오 옵션

**Scenario X — Security + Monitoring + Provider 회복성 (권장 기반 ✅)**

- Phase A: 보안 강화 — `slowapi` rate limit (login 10/min, watchlist write 30/min) + CORS `ALLOWED_ORIGINS` 환경변수 + security headers middleware (X-Content-Type-Options / X-Frame-Options / Referrer-Policy / HSTS) + CSP 기초 + brute force protection (LoginAuditLog 기반 카운터 → 5회 실패 시 15분 잠금)
- Phase B: 운영 모니터링 — `sentry-sdk` backend (SENTRY_DSN env + SENTRY_ENABLED=false default) + JSON 구조화 로깅 (LOG_FORMAT=json env) + React ErrorBoundary + frontend Sentry optional (VITE_SENTRY_DSN) + `/api/jobs` failure summary 보강
- Phase C: Watchlist API 고도화 + UserPreference + Provider 회복성 — PUT/DELETE 라우터 4건 + `UserPreference` 32번째 테이블 + Alembic revision 0004~0005 + provider_status enum + retry decorator
- Phase D: Frontend — Watchlist 관리 UI + Settings 화면 보강 + React ErrorBoundary wrap + vitest/e2e 보강
- Phase E: 마감 — `RELEASE_NOTES_v0.9.md` + 4 게이트 재확인 + tag `v0.9-final`

**Scenario Y — Watchlist Polish + UserPreference (UX 우선)**

- Phase A~D: 보안 강화 없이 Watchlist rename/delete/default + UserPreference + 프런트 UI 집중
- **단점**: rate limit / security headers 없이 POST 라우터를 운영하면 외부 노출 시 위험. Phase A 보안 강화가 운영 필수 — 건너뛸 수 없음. **권장하지 않음**

**Scenario Z — 백테스트 고도화 우선**

- Phase A~D: walk-forward / multi-strategy / per-symbol slippage
- **단점**: v0.7 이후 데이터 누적 기간이 충분하지 않음. walk-forward 는 최소 6개월 이상의 recommendation_results 가 있어야 의미 있음. 현재 시기상조. **v0.10 후보**

**Scenario W — 실 DART/RSS Provider 구현**

- Phase A~D: DartFundamentalProvider / RssNewsProvider 구현
- **단점**: 라이선스 검토(사람) 없이 코드 추가 불가. DART OpenAPI 이용 약관 / 상업 목적 가부 / Rate limit 정책을 법무 또는 운영자가 확인해야 함. **현 cycle 부적합**

**채택 결론: Scenario X 수정 — Operational Security & Watchlist Polish (권장 ✅)**

Scenario X 의 Security + Monitoring 기반 위에 Scenario Y 의 Watchlist Polish + UserPreference 를 합친다. 백테스트 / 실 Provider / LLM 은 모두 미착수.

### Phase A: Security Hardening

**목표**: POST 라우터 운영 전 필수 보안 레이어 완성. v0.8 에서 도입한 JWT + scrypt 위에 rate limit / CORS 강화 / security headers / brute force protection 추가.

**산출물**:

1. `app/middleware/security_headers.py` — `SecurityHeadersMiddleware` (Starlette `BaseHTTPMiddleware` 상속)
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: geolocation=(), camera=()`
   - `Strict-Transport-Security: max-age=63072000; includeSubDomains` (HTTPS 환경만)
   - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:` (기초 CSP)
2. `app/middleware/rate_limit.py` — `slowapi` (MIT) 기반 Rate Limiter
   - `POST /api/auth/login`: 10/min per IP
   - `POST /api/watchlists`, `POST /api/watchlists/{id}/items`, `DELETE /api/watchlists/{id}/items/{symbol}`: 30/min per IP
   - `GET` 라우터: 제한 없음
3. `app/auth/brute_force.py` — LoginAuditLog 기반 카운터
   - 동일 username 5회 실패 → 15분 잠금 (`X-Retry-After` 헤더 반환)
   - 잠금 상태는 DB (LoginAuditLog) 에서 쿼리 — 인메모리 캐시 없이 stateless
4. `app/config.py` 환경 변수 추가
   - `ALLOWED_ORIGINS`: comma-separated, default `http://localhost:5173`
   - `RATE_LIMIT_ENABLED`: bool, default `true`
   - `BRUTE_FORCE_ENABLED`: bool, default `true`
   - `BRUTE_FORCE_MAX_ATTEMPTS`: int, default `5`
   - `BRUTE_FORCE_LOCKOUT_MINUTES`: int, default `15`
5. `tests/unit/test_security_headers.py` — SecurityHeadersMiddleware 응답 헤더 단언 (~8 tests)
6. `tests/unit/test_rate_limit.py` — rate limit 초과 시 429 단언 (~6 tests)
7. `tests/unit/test_brute_force.py` — 5회 실패 → 423 Locked + X-Retry-After 단언 (~8 tests)
8. `requirements.txt` — `slowapi>=0.1.9` 추가

**정책 가드** (Phase A 에서 하지 않을 것):

- ❌ 실 KIS / DART / RSS / Telegram 자동 호출
- ❌ DB 모델 신규 테이블 추가 (LoginAuditLog 기존 테이블 조회만)
- ❌ 새 API 라우터 (보안 미들웨어만)
- ❌ 프런트엔드 변경

**인수 게이트**: backend pytest ~830 passed / 4 게이트 그린 / 태그 `v0.9-security-hardening`

---

### Phase B: Error Monitoring + Structured Logging

**목표**: 운영 가시성 확보. Sentry 통합(optional) + JSON 구조화 로깅 + React ErrorBoundary.

**산출물**:

1. `app/logging_config.py` — 구조화 로깅 설정
   - `LOG_FORMAT=json` 환경변수 → `structlog` 또는 `python-json-logger` 기반 JSON 포맷
   - `LOG_FORMAT=text` (default) → 기존 uvicorn 포맷 유지
   - 로그 필드: `timestamp`, `level`, `logger`, `message`, `request_id`, `user_id` (인증 컨텍스트)
2. `app/middleware/request_id.py` — `RequestIDMiddleware` (`X-Request-ID` 헤더 + 로그 컨텍스트 주입)
3. `app/monitoring/sentry.py` — Sentry SDK 통합
   - `SENTRY_ENABLED=false` 기본 — 미설정 시 0건 외부 전송
   - `SENTRY_DSN` 환경변수 없으면 skip
   - `SENTRY_TRACES_SAMPLE_RATE=0.1` 기본
   - `before_send` hook — PII 필터링 (email / IP / token field 제거)
4. `/api/jobs` 라우터 보강 — `failure_summary` 필드: 최근 24h 실패 잡 건수 + 마지막 오류 메시지 요약
5. `frontend/src/components/ErrorBoundary.tsx` — React ErrorBoundary 컴포넌트
   - 페이지별 wrap: `<App>` 최상위 + 개별 화면 (Watchlist / StockDetail / Backtest)
   - fallback UI: "오류가 발생했습니다. 새로고침 해주세요." + reload 버튼
   - `VITE_SENTRY_DSN` 환경변수 있을 때만 Sentry 보고
6. `tests/unit/test_logging_config.py` — JSON 포맷 단언 (~6 tests)
7. `tests/unit/test_request_id.py` — X-Request-ID 헤더 전파 단언 (~4 tests)
8. `requirements.txt` — `sentry-sdk>=2.0` + `python-json-logger>=2.0` 추가

**정책 가드** (Phase B 에서 하지 않을 것):

- ❌ Prometheus exporter / Grafana 대시보드 (v0.10+ 후보)
- ❌ 실 Sentry 전송 (SENTRY_ENABLED=false 기본 유지)
- ❌ PII (email / IP / token) Sentry 전송
- ❌ DB 모델 신규 테이블 추가
- ❌ 새 비즈니스 로직 API 라우터

**인수 게이트**: backend pytest ~850 passed / 4 게이트 그린 / 태그 `v0.9-monitoring`

---

### Phase C: Watchlist API 고도화 + UserPreference + Provider 회복성

**목표**: v0.8 의 create/add-item/delete-item 5건 위에 rename/delete-list/set-default/memo-edit 4건 추가 + UserPreference 32번째 테이블 + provider 회복성 인터페이스 강화.

**산출물**:

1. 새 API 라우터 4건 (`app/api/watchlist_routes.py` 확장)
   - `PUT /api/watchlists/{id}` — watchlist rename (body: `{"name": "..."}`)
   - `DELETE /api/watchlists/{id}` — watchlist + 모든 items cascade delete
   - `PUT /api/watchlists/{id}/default` — default watchlist 지정 (UserPreference 연동)
   - `PUT /api/watchlists/{id}/items/{symbol}` — item 메모 편집 (body: `{"memo": "..."}`)
2. `app/db/models.py` — `UserPreference` 32번째 ORM 테이블
   - `id`, `user_id` (FK → User), `default_watchlist_id` (FK → Watchlist, nullable), `default_market` (str, nullable), `default_strategy` (str, nullable), `created_at`, `updated_at`
   - 정책 가드 필드 0건: `broker`, `account`, `quantity`, `order_*`
3. `app/api/user_routes.py` — UserPreference 라우터
   - `GET /api/me/preferences` — 현재 로그인 사용자 preferences 조회
   - `PUT /api/me/preferences` — preferences 업데이트
4. `alembic/versions/0004_watchlist_enhance.py` — WatchlistItem.memo 컬럼 추가
5. `alembic/versions/0005_user_preference.py` — UserPreference 테이블 생성
6. `app/data/provider_base.py` 또는 `app/data/collectors/base.py` — provider 회복성 인터페이스
   - `ProviderStatus` enum: `DISABLED / HEALTHY / ERROR / RATE_LIMITED`
   - `@retry_with_backoff(max_retries=3, base_delay=1.0)` decorator
   - `ProviderHealthSnapshot`: `status`, `last_success_at`, `last_error_at`, `consecutive_failures`
   - `/api/jobs` 응답에 `provider_health` dict 추가 (각 provider 의 `ProviderHealthSnapshot`)
7. `tests/unit/test_watchlist_api_v2.py` — PUT/DELETE 신규 라우터 단언 (~30 tests)
   - cross-user 403 isolation
   - cascade delete 단언 (items 포함 삭제)
   - memo 업데이트 단언
8. `tests/unit/test_user_preferences.py` — GET/PUT /api/me/preferences 단언 (~12 tests)
9. `tests/unit/test_provider_resilience.py` — retry decorator + ProviderStatus 전환 단언 (~10 tests)

**정책 가드** (Phase C 에서 하지 않을 것):

- ❌ 실 DART / RSS provider 구현 (ProviderStatus + retry interface 만)
- ❌ WatchlistItem 에 broker/account/quantity/order_* 컬럼 추가
- ❌ 자동매매 / BrokerInterface 구현
- ❌ UserPreference 에 KIS 계좌 / 자동매매 설정 추가
- ❌ 다중 사용자 / RBAC

**인수 게이트**: backend pytest ~910 passed / alembic upgrade head 성공 / alembic compare_metadata diff 0건 / 4 게이트 그린 / 태그 `v0.9-watchlist-api`

---

### Phase D: Frontend 관리 UI

**목표**: Phase C API 와 연동하는 프런트엔드 관리 UI 완성. Watchlist rename/delete/default + 메모 인라인 편집 + Settings 화면 보강.

**산출물**:

1. `frontend/src/pages/Watchlist.tsx` 확장
   - 목록 헤더에 "목록 이름 수정" 연필 아이콘 → inline rename (PUT /api/watchlists/{id})
   - "목록 삭제" 버튼 → 확인 모달 → DELETE /api/watchlists/{id}
   - "기본 목록으로 설정" 버튼 → PUT /api/watchlists/{id}/default
   - WatchlistItem 행 메모 셀 → 클릭 시 inline text input → PUT /api/watchlists/{id}/items/{symbol}
2. `frontend/src/pages/Settings.tsx` (신규 또는 기존 확장)
   - `GET /api/me/preferences` 조회
   - 기본 시장 선택 (드롭다운: ALL / KOSPI / KOSDAQ)
   - 기본 전략 선택 (드롭다운: MomentumStrategy / MeanReversionStrategy / BreakoutStrategy)
   - 기본 Watchlist 선택 (watchlist 목록에서 선택)
   - `PUT /api/me/preferences` 저장
3. ErrorBoundary wrap (Phase B 컴포넌트 활용)
   - 각 화면 라우터에 `<ErrorBoundary>` 감싸기
4. `frontend/src/store/watchlistSlice.ts` 확장 — rename/delete/setDefault/updateMemo action
5. `frontend/src/tests/WatchlistManage.test.tsx` — rename/delete/default/memo useMutation 시나리오 (~20 tests)
6. `frontend/src/tests/Settings.test.tsx` — preferences GET/PUT 시나리오 (~10 tests)
7. `e2e/watchlist_manage.spec.ts` — rename / delete / default 플로우 e2e 5건 추가
8. `e2e/settings.spec.ts` — preferences 저장 플로우 e2e 3건 추가

**정책 가드** (Phase D 에서 하지 않을 것):

- ❌ 자동매매 UI / 브로커 연동 UI
- ❌ KIS 실 계좌 정보 표시
- ❌ Watchlist 자동 가격 알림 / 텔레그램 알림 UI
- ❌ 다중 사용자 관리 UI / 어드민 패널
- ❌ Recommendations / Backtest / Holdings 산식 변경

**인수 게이트**: vitest ~130 passed / e2e ~27 passed / build 그린 / 태그 `v0.9-frontend`

---

### Phase E: 마감

**목표**: v0.9 cycle 마감 선언, 릴리즈 노트 + 문서 갱신 + 태그 push.

**산출물**:

1. `RELEASE_NOTES_v0.9.md` — Phase A~D 산출물 + 최종 게이트 수치 + 안전 정책 + 알려진 한계 + v0.10 후보
2. `README.md` — v0.9 누적 내용 반영 (기능 목록 / 제외 범위 / 누적 사이클 표 / 회귀 기준선)
3. `PROJECT_STATUS.md` — §0 v0.9 마감 선언으로 교체, §0-1 강등 연쇄
4. `TASKS.md` — v0.9 Phase E 체크리스트 완료 처리
5. `ROADMAP.md` — v0.9 행 ✅ 마감 + v0.10+ 후보 반영
6. `TESTING.md` — 기준선 ~130 vitest / ~27 e2e / ~910 pytest 갱신
7. `ARCHITECTURE.md` — v0.9 마감 시점 반영 (보안 미들웨어 레이어, UserPreference, provider 회복성)
8. tag `v0.9-final` + push

**인수 게이트**: 4 게이트 그린 (backend pytest ~910 / vitest ~130 / e2e ~27 / build) / 5 누적 태그 push 완료

---

### v0.9 정책 (변경 없을 항목)

- ❌ 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ `BrokerInterface` 구현 (placeholder 유지)
- ❌ 실 DART / 실 RSS / 실 News API 자동 호출 — 라이선스 검토(사람) 선행 없이 구현 불가
- ❌ MockBroker / ReplayBroker / SimulationBroker
- ❌ ScoringEngine / HoldingCheckEngine 본 weight 변경
- ❌ Recommendations / Backtest / Today 산식 변경
- ❌ 다중 사용자 / RBAC / OAuth / SSO / refresh token
- ❌ WebSocket / SSE
- ❌ Prometheus exporter / Grafana 대시보드 (v0.10+ 후보)
- ❌ LLM 자동 전략 / 자동 분석
- ❌ WatchlistItem 에 broker/account/quantity/order_* 컬럼 추가
- ❌ Telegram 실 발송 (DRY_RUN 기본 유지)
- ❌ 평문 IP / 평문 password 저장 (SHA256 해시 / scrypt 유지)
- ❌ `source_file_path` / 본문 paragraph 외부 노출

### v0.9 새로 허용하는 POST/PUT/DELETE (v0.8 5건 + v0.9 추가 6건 = 누적 11건)

| 메서드 | 경로 | 설명 | Phase |
|---|---|---|---|
| POST | `/api/auth/login` | 로그인 (v0.8) | v0.8 |
| POST | `/api/auth/logout` | 로그아웃 (v0.8) | v0.8 |
| GET | `/api/auth/me` | 내 정보 조회 (v0.8, GET 이지만 인증 전용) | v0.8 |
| POST | `/api/watchlists` | 목록 생성 (v0.8) | v0.8 |
| POST | `/api/watchlists/{id}/items` | 종목 추가 (v0.8) | v0.8 |
| DELETE | `/api/watchlists/{id}/items/{symbol}` | 종목 삭제 (v0.8) | v0.8 |
| PUT | `/api/watchlists/{id}` | 목록 이름 변경 (v0.9 신규) | v0.9 C |
| DELETE | `/api/watchlists/{id}` | 목록 삭제 (cascade) (v0.9 신규) | v0.9 C |
| PUT | `/api/watchlists/{id}/default` | 기본 목록 지정 (v0.9 신규) | v0.9 C |
| PUT | `/api/watchlists/{id}/items/{symbol}` | 종목 메모 편집 (v0.9 신규) | v0.9 C |
| GET | `/api/me/preferences` | 사용자 설정 조회 (v0.9 신규) | v0.9 C |
| PUT | `/api/me/preferences` | 사용자 설정 저장 (v0.9 신규) | v0.9 C |

그 외 모든 도메인 (Recommendations / Holdings / Backtest / 잡 트리거 / 알림 / 점수) POST/PUT/DELETE = 0건

### 완료 기준 (cycle-wide)

- 모든 phase 통과 / 4 게이트 그린 (backend pytest ~910 / vitest ~130 / e2e ~27 / build)
- `RELEASE_NOTES_v0.9.md` 작성 완료
- 5 누적 태그 부여 + push: `v0.9-security-hardening` → `v0.9-monitoring` → `v0.9-watchlist-api` → `v0.9-frontend` → `v0.9-final`
- 새 PUT/DELETE 라우터 6건 = cross-user 403 isolation 단언 포함
- `UserPreference` 테이블 = broker/account/quantity/order_* 컬럼 0건 가드
- Alembic 0004~0005 revision 적용 + `compare_metadata` diff 0건 단언
- `SENTRY_ENABLED=false` 기본 — 미설정 시 외부 전송 0건
- `RATE_LIMIT_ENABLED=true` 기본 — login 10/min + watchlist write 30/min
- `AUTH_ENABLED=false` 모드에서 v0.8 회귀 테스트 100% 그대로 통과
- 실 DART / 실 RSS / 실 News API 자동 호출 0건 — provider_status + retry interface 만 추가
- 자동매매 / BrokerInterface 구현 0건
