# RELEASE_NOTES_v0.5

## v0.5 News, Disclosure & Theme Ranking 마감

v0.5 는 v0.1 부터 비어 있던 `news_items` 테이블을 처음으로 채우고, `DummyScoreProducer.news_score`
(가중치 25%) 를 처음으로 real 값으로 교체하며, v0.4 누적 테마·매핑·시그널 데이터를
프런트 9번째 화면 `/themes` 로 처음 surface 한 사이클이다. v0.1 ~ v0.4 의 read-only
원칙, 비밀값 마스킹, mock·DRY_RUN 정책, v0.4 의 저작권 정책 (본문 paragraph 미저장 /
자동 fetch default OFF / `source_file_path` 미노출) 은 모두 그대로 유지했다.

자동매매 / 실 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO / POST 라우터 / 자동 크롤링은
이번 사이클에도 코드 일체 추가하지 않았다.

- 최종 태그 예정: `v0.5-final`
- 인수 일자: 2026-05-05 (Asia/Seoul)
- 직전 누적 태그: `v0.5-frontend-themes` (Phase D)
- 기준선: `v0.4-final` — 백엔드 pytest 382 / vitest 60 / build / e2e 9
- 마감 기준선: 백엔드 pytest **481** / vitest **68** / build / e2e **11**

## 핵심 변화 한 줄 요약

- **News 데이터 라인 첫 도입** — `NewsProviderInterface` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 (19:00 KST, default OFF)
- **공시 데이터 라인 첫 도입** — `DisclosureProviderInterface` + `DisclosureCollector` + 5 카테고리 keyword 분류 + `collect_disclosures` 잡 (20:00 KST, default OFF)
- **`news_score` 첫 real 화** — `RealNewsScoreProducer` (composition 패턴, fallback 으로 supply/fundamental/earnings/ai 위임). 산식 `clip(50 + weighted_sentiment * 5 / max(news_count, 1), 0, 100)`. recency ≤24h:1.0 / ≤3d:0.7 / ≤7d:0.3
- **RiskEngine 강화** — `DisclosureRiskProducer` 가 14일 윈도우의 RISK_DISCLOSURE 카테고리 공시를 카운트해 `RISK_DISCLOSURE` flag + `min(count × 3, 10)` cap penalty 가산. `news_score` 가중치 25% / ScoringEngine 본 weight 변경 0건
- **테마 랭킹 surface** — `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) + 프런트 `/themes` + `/themes/:theme_id` 9번째 화면 + Sidebar `테마 (β)` 메뉴
- **추천 evidence 노출 강화** — `RecommendationItemSchema.news_evidence` + `disclosure_risk_evidence` (`DataSnapshot.market_context_json` 에서 추출, whitelist 안전 필드만). StockDetail RelatedThemesCard 의 테마 → `/themes/:id` 링크 + impact_path / impact_direction badge

## Phase A — News data layer + collect_news job

> 두 PR 로 분리 진행. PR1 = data layer skeleton, PR2 = scheduler integration.
> 누적 태그 `v0.5-news-collector`.

### PR1 — Data layer skeleton

- `app/data/interfaces.py` — `NewsProviderInterface` ABC (`fetch_recent_news(*, symbols, since, limit) -> list[NewsItemDTO]`)
- `app/data/dtos.py` — `NewsItemDTO` dataclass 9 필드 (title / url / provider / published_at / symbol / source / category / sentiment_label / summary). **본문 paragraph / body / content / full_text / paragraph_text / 본문 / 원문 / 전문 등 13종 forbidden 필드 0건**
- `app/data/collectors/news_collector.py` — `NewsCollector` + `NewsCollectorResult` (fetched / inserted / skipped_duplicates / truncated_summaries). url-keyed 멱등, 재실행 시 0 중복. summary 500자 초과 시 truncate count 만 보고
- `app/db/models.py` — `NewsItem.category: String(32) nullable, index=True` ALTER ADD COLUMN. 6 enum 값 (NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER)
- `app/data/repositories/news_items.py` — `get_by_url` / `upsert_by_url` (멱등, returns `(item, inserted)`) / `list_recent_by_symbol` (Python-side related_symbols 필터) / `list_recent_by_category`
- 테스트: `tests/integration/test_news_collector.py` 신규 19 케이스 (DTO 본문 0 가드 / 9 fields / FakeNewsProvider determinism / 멱등 / category persist / repository 메서드)
- 회귀: backend pytest **382 → 401 (+19)**

### PR2 — Scheduler integration

- `app/config/settings.py` — `news_collection_enabled: bool = False` (default OFF, `NEWS_COLLECTION_ENABLED` env var)
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_NEWS` + `_resolve_news_provider(session)` helper + `collect_news(session)` 함수. 3-way branch: disabled → SKIPPED + reason="news_collection_disabled" / enabled+no_provider → SKIPPED / enabled+provider → `NewsCollector.collect_recent`
- `app/scheduler/scheduler.py` — DEFAULT_SCHEDULE 19:00 KST 등록. `JOB_FUNCTIONS` registry 7 → **8 jobs**
- 테스트: scheduler 분기 5건 추가 (default schedule 19:00 / disabled provider 미호출 / enabled+no_provider / enabled+FakeProvider 3 inserted / 재실행 멱등)
- 회귀: backend pytest **401 → 406 (+5)**, frontend / e2e / build 변경 0

## Phase B — Disclosure subset + 분류 + collect_disclosures job

> 태그 `v0.5-disclosure-pipeline`. Phase A 의 News 패턴을 그대로 복제 +
> 공시 keyword 분류 추가.

- `app/data/interfaces.py` — `DisclosureProviderInterface` ABC
- `app/data/dtos.py` — `DisclosureItemDTO` 9 필드 (title / url / provider / published_at / symbol / company_name / disclosure_type / category / summary). 13종 forbidden 본문 필드 0건
- `app/data/collectors/disclosure_collector.py` — `classify_disclosure(title, disclosure_type, summary)` 순수 함수 + `DisclosureCollector` + `DisclosureCollectorResult`
- 분류 priority order (5 카테고리): `RISK_DISCLOSURE` > `EARNINGS_REPORT` > `OWNERSHIP_CHANGE` > `GOVERNANCE` > `OTHER`. 한글 keyword (소송 / 횡령 / 배임 / 거래정지 / 감사의견 / 회생 / 파산 / 실적 / 잠정 / 영업이익 / 당기순이익 / 최대주주 / 지분 / 보유주식 / 이사회 / 사외이사 / 감사위원회 / 주주총회) + 영문 keyword 동시 지원
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_DISCLOSURES` + `collect_disclosures(session)` 함수 (3-way branch). `JOB_FUNCTIONS` registry 8 → **9 jobs**. DEFAULT_SCHEDULE 20:00 KST
- `app/config/settings.py` — `disclosure_collection_enabled: bool = False`
- 테스트: `tests/integration/test_disclosure_collector.py` 신규 24 케이스 (DTO 가드 / 12 parametrized 한글 분류 / priority RISK > EARNINGS / GOVERNANCE / OTHER fallback / FakeDisclosureProvider 4 / collector flow 7) + scheduler 보강 5건
- `INTEGRATION_RUNBOOK.md` §11 신규 — 운영자 가이드 5 단락
- 회귀: backend pytest **406 → 440 (+34)**, frontend / e2e / build 변경 0

## Phase C — RealNewsScoreProducer + DisclosureRiskProducer + RiskEngine 보강

> 태그 `v0.5-news-score`. v0.1 의 `DummyScoreProducer.news_score = 50` placeholder
> 가 처음으로 real 값으로 교체. **추천·보유 본 weight 산식은 0건 변경**.

- `app/analysis/score_producers.py` 전면 정리 — `ScoreProducerInterface` ABC 추출. `DummyScoreProducer` 가 ABC 구현체로 유지 (기존 호출자 호환)
- `RealNewsScoreProducer` 신규. composition 패턴 — fallback (default DummyScoreProducer) 가 supply / fundamental / earnings / ai 처리, news_score 만 NewsItemRepository 기반 real 화. 산식:
  ```
  weighted_sentiment = sum_{news in last 7d} (
      weight_by_age * sentiment_mapping(news.sentiment)
  )
  weight_by_age      = 1.0 (≤24h) / 0.7 (≤3d) / 0.3 (≤7d)
  sentiment_mapping  = POSITIVE: +1, NEUTRAL: 0, NEGATIVE: -1, UNKNOWN: 0
  news_score         = clip( 50 + weighted_sentiment * 5 / max(news_count, 1), 0, 100 )
                     = 50 if news_count == 0      (Dummy fallback 호환)
  ```
- SQLite/Postgres tz roundtrip 호환 (`_to_naive_utc` helper)
- `DisclosureRiskProducer` 신규. 14일 윈도우 + symbol-first 필터 + `category=RISK_DISCLOSURE`. `penalty_addition = min(count × 3, 10)` cap. count=0 → flag=None / penalty=0. Evidence top 3 by recency
- `app/decision/risk_engine.py` — `evaluate_recommendation` / `evaluate_holding` 에 `disclosure_risk_count: int = 0` + `disclosure_penalty_addition: Decimal = 0` 파라미터 추가. count > 0 시 `RISK_FLAG_DISCLOSURE` 추가 + penalty 가산. **default 0 으로 backward compat**
- `app/decision/recommendation_engine.py` / `holding_check_engine.py` — constructor 에 `disclosure_risk_producer: DisclosureRiskProducer | None = None` 추가. `score_producer` 타입 `DummyScoreProducer | None` → `ScoreProducerInterface | None`. evidence 를 `data_snapshots.market_context_json` + `decision_logs.rule_result_json` 양쪽에 기록
- **Safe-fields whitelist 강제** — evidence 빌더가 `title / url / provider / published_at / sentiment` 만 노출 (body / content / full_text / source_file_path 등 0건). 단위 테스트가 키 집합 명시 단언
- 테스트: `tests/unit/test_real_news_score_producer.py` 신규 17 케이스 (RealNewsScoreProducer 9 + DisclosureRiskProducer 8) + RecommendationEngine 보강 5 + HoldingCheckEngine 보강 3 + RiskEngine 보강 5
- 회귀: backend pytest **440 → 470 (+30)**. ScoringEngine 본 weight (technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%) 산식 0건 변경

## Phase D — Theme ranking API + dashboard + evidence 노출

> 태그 `v0.5-frontend-themes`. v0.4 누적 테마·매핑·시그널 데이터를 첫 surface +
> Phase C 가 JSON 컬럼에만 저장해 둔 evidence 를 명시 schema 필드로 노출.

### 백엔드

- `GET /api/themes/ranking` — query `category` / `direction` (POSITIVE/NEGATIVE/NEUTRAL, 다른 값 422) / `limit` (1~200, default 50). 응답 각 항목에 `mapping_count` + `signal_event_count` (단일 GROUP BY 쿼리). 정렬 `id` 내림차순 (가장 최근 삽입 순)
- `GET /api/themes/{theme_id}` — 단건 + 매핑 종목 + 시그널 이벤트. 매핑은 `theme_*` 필드 제외 (theme 가 부모). `mapping_limit` / `signal_limit` query (default 50, max 200)
- `app/api/schemas.py` — `ThemeRankingItemSchema` / `ThemeRankingResponse` / `ThemeStockMappingSchema` / `ThemeDetailResponse` 신규. 기존 `ReportSignalEventSchema` 재사용
- `RecommendationItemSchema` 보강 — `news_evidence: Optional[Dict[str, Any]]` + `disclosure_risk_evidence: Optional[Dict[str, Any]]` 필드 추가. `_recommendation_to_schema` 가 `DataSnapshot.market_context_json` 에서 추출. pre-v0.5 snapshot 은 둘 다 `null` (backward compat)

### 프런트

- `frontend/src/pages/Themes/index.tsx` — TanStack Table + direction radio + search filter + 정렬
- `frontend/src/pages/ThemeDetail/index.tsx` — KeyValueGrid 개요 + 영향 종목 카드 grid + 시그널 이벤트 표
- Sidebar 9번째 메뉴 `테마 (β)` (Tags 아이콘) 추가, lazy router route 2개 추가
- `RelatedThemesCard` 보강 (StockDetail) — 테마명 → `<Link to="/themes/:theme_id">`. `impact_path` 별도 monospace badge, `impact_direction` 색상 badge
- `RecommendationsTable` — `news evidence` (count + top news 제목 prefix) + `disclosure risk` (count + top 공시 제목 prefix) 두 컬럼 추가. nullable 시 `—`
- `frontend/src/api/types.ts` — `NewsEvidence` / `NewsEvidenceTopItem` / `DisclosureRiskEvidence` / `DisclosureRiskItem` / `ThemeRankingItem` / `ThemeRankingResponse` / `ThemeStockMapping` / `ThemeDetailResponse` 신규
- `useThemeRanking` / `useThemeDetail` hook 추가 (TanStack Query v5 패턴, staleTime 5분)

### 테스트

- backend pytest **470 → 481 (+11)** — 테마 ranking 6 + 테마 detail 4 + recommendation evidence 2
- frontend vitest **60 → 68 (+8)** — Themes 5 + ThemeDetail 3 + 기존 Recommendations / StockDetail / App 보강
- Playwright e2e **9 → 11 (+2)** — Themes 랭킹/상세 + StockDetail → Theme link 네비 + Recommendations evidence cells
- frontend build 그린

## Phase E — 마감 문서 / 회귀 게이트 재확인

이 단계. `RELEASE_NOTES_v0.5.md` 신규 + `README.md` 마감 배너 + `PROJECT_STATUS.md`
§0 마감 선언 + `TASKS.md` 체크박스 + `ROADMAP.md` v0.5 마감 + 4 게이트 재확인.
**코드 / 라우터 / DB 모델 / 프런트 화면 변경 0건**.

## 테스트 결과 (v0.5 마감 시점)

Phase D 인수 시점 + Phase E 마감 직전 재확인 모두 동일한 4 게이트 baseline:

- backend pytest: **481 passed** (v0.1 296 → v0.3 319 → v0.4 final 382 → v0.5 PR1 401 → PR2 406 → Phase B 440 → Phase C 470 → Phase D 481)
- frontend vitest: **68 passed** (13 파일, jsdom + msw v2)
- frontend build: **그린** (`tsc --noEmit && vite build`, vendor-charts 청크 383 kB / gzip 105 kB)
- Playwright e2e: **11 passed** (chromium + page.route mock)

테스트는 모두 mock / fixture 기반이다. KIS API 실제 호출, 텔레그램 실제 발송, 외부
RSS / DART API 실제 호출, 주문 실행은 0건이다.

## 안전 정책 (cycle-wide)

v0.4 의 저작권 정책 + v0.1 ~ v0.5 의 자동매매 부재 정책을 그대로 누적:

- **뉴스 / 공시 본문 전문 저장 금지** — `NewsItem` / `NewsItemDTO` / `DisclosureItemDTO` 어디에도 body / content / full_text / paragraph_text / raw_text / 본문 / 원문 / 전문 컬럼 없음. title / URL / provider / published_at / symbol / category / sentiment / 짧은 summary (≤500자) 만 저장. 단위 테스트가 13종 forbidden 필드 부재를 명시 단언
- **`source_file_path` 미노출** — 신규 `/api/themes/ranking` / `/api/themes/{theme_id}` / Recommendation evidence 응답 모두 `_assert_no_source_file_path` recursive helper 로 0건 노출 검증. v0.4 의 analyst report 정책 그대로 유지
- **수집 job default OFF** — `news_collection_enabled` / `disclosure_collection_enabled` 기본값 false. 운영자가 `.env` 에 명시 enable 시에만 동작. disabled 분기에서는 provider 호출 0건 (spy 검증)
- **외부 네트워크 테스트 금지** — `FakeNewsProvider` / `FakeDisclosureProvider` 결정론적 sample 만 사용. 실 RSS / DART 호출 0건. CI 환경에서도 외부 트래픽 0건
- **자동매매 / 실주문 / POST 트리거 0건** — v0.5 에서도 POST / PUT / DELETE 라우터 추가 0건. `BrokerInterface` ABC placeholder 그대로. 자동매매 / FULL_AUTO / APPROVAL / SMALL_AUTO 코드 0건
- **Evidence whitelist** — `news_evidence.top_news` 의 키 집합은 정확히 `{title, url, provider, published_at, sentiment}`. `disclosure_risk_evidence.recent_risk_disclosures` 는 sentiment 제외 4 키. 본문 / 내부 경로 절대 미포함
- **추천 산식 본 weight 변경 0건** — ScoringEngine (technical 35% / news 25% / supply 15% / fundamental 15% / ai 10%) 그대로. `news_score` 가 placeholder 50 → real 로 교체될 뿐 가중치 25% 유지
- **HoldingCheckEngine 산식 변경 0건** — 보유 점검 3-pass scoring flow 그대로
- **비밀값 마스킹 유지** — KIS 키 / Telegram 토큰 / 계좌번호 마스킹 정책, settings 응답 마스킹 검증 e2e 그대로 통과

## 알려진 한계

- **실 News / Disclosure provider 미구현** — `NewsProviderInterface` / `DisclosureProviderInterface` ABC 와 `FakeNewsProvider` / `FakeDisclosureProvider` 결정론적 샘플만 제공. 실 RSS / DART subset 구현체는 v0.6+ 후보 (수집 정책 + 라이선스 검토 동반)
- **News sentiment 룰 기반만** — v0.5 는 단순 매핑 (POSITIVE / NEUTRAL / NEGATIVE / UNKNOWN). LLM 기반 sentiment 분석은 v0.6+ 후보
- **공시 분류 keyword 기반만** — 5 카테고리 우선순위 룰. LLM 기반 분류는 v0.6+ 후보. 운영 중 오분류 발견 시 `app/data/collectors/disclosure_collector.py` keyword set 보강 필요
- **테마 랭킹 = 단순 id desc** — `mapping_count` / `signal_event_count` 가산 점수 기반 랭킹은 미구현. v0.6+ 후보
- **컨센서스 / report_score 는 v0.4 와 동일** — News·Disclosure 와 별도 보조 점수로 합산되지 않음
- **`HoldingCheckSchema` 의 evidence 노출 미포함** — Phase C 에서 holding_check 도 evidence 를 snapshot 에 저장하지만, Phase D 의 schema 노출은 RecommendationItemSchema 에만 적용. v0.6+ 후보
- **운영 DB 마이그레이션** — `news_items.category` ALTER ADD COLUMN 은 별도 절차로 적용해야 함 (Alembic 미사용)
- **인증 / 관심종목 / Watchlist** — 미구현. POST 라우터 도입은 인증 사이클과 묶음 (v0.6 후보)

## 제외 범위

다음은 모든 사이클 (v0.1 ~ v0.5) 과 동일하게 코드 일체 포함하지 않는다:

- 실거래 자동매매 (FULL_AUTO / APPROVAL / SMALL_AUTO)
- 실 KIS 주문 / `BrokerInterface` 구현체
- POST / PUT / DELETE 라우터 (read-only API 만)
- News / Disclosure 자동 크롤링 / 스크레이핑 (FakeProvider 만, 실 RSS / DART 호출 0건)
- 가상 증권사 (MockBroker / ReplayBroker / SimulationBroker)
- 전략 모듈 / Strategy / Backtest / 전용 ML 학습
- 인증 / 권한 / 사용자별 관심종목
- 뉴스 / 공시 / 리포트 본문 (paragraph) DB 저장
- LLM 기반 자동 sentiment / 자동 분류
- 추천 산식 본 weight 변경
- HoldingCheckEngine 산식 변경

## v0.6 후보

v0.5 마감 후 검토 가능한 후보들. 각 항목은 명시적 진입 요청 전까지 손대지 않는다.

### 데이터 / 분석 실제화

- **실 재무 / 실적 점수** — `FundamentalSnapshot` / `EarningsSnapshot` 테이블 신규 + DART 재무제표 파싱. PER/PBR/EPS/ROE/매출 성장률/영업이익 성장률/실적 컨센서스. `DummyScoreProducer.fundamental_score` / `earnings_score` 실제화
- **실 News / Disclosure provider 구현체** — RSS / DART subset 구현체 (라이선스 / 수집 정책 검토 동반)
- **테마 랭킹 점수화** — 단순 id desc → mapping_count + signal_event_count + recency 가중 score 도입
- **HoldingCheckSchema evidence 노출** — Phase D 에서 RecommendationItemSchema 에만 추가한 news_evidence / disclosure_risk_evidence 를 holding_check 응답에도 surface
- **LLM sentiment 보강** — 룰 기반 sentiment / 분류 → LLM 보강. `extraction_method` / `extraction_confidence` 필드 그대로 활용

### 인증 / 관심종목

- **인증 / 권한** — 단일 토큰 / API key 헤더부터. POST 라우터 도입 전제
- **즐겨찾기 / 관심종목** — Watchlist 테이블 신규 + POST `/api/watchlist`. 인증 동반 필수
- **글로벌 검색** (cmd+k), 사이드바 collapse, breadcrumb, loading skeleton 통일

### 운영 / UX

- **운영 모니터링** — Sentry / Prometheus / Grafana
- **모바일 / 태블릿 레이아웃** — 현재는 PC 1280px+ 우선
- **StockDetail 캔들 차트 + 거래량 BarChart + 이동평균 오버레이** — `lightweight-charts` 마이그레이션 검토
- **운영 DB migration** — Alembic 도입 + 누적 ALTER 자동화

### 백엔드 인프라

- **POST 트리거** (잡 수동 실행 / 추천 즉시 생성) — 인증 동반 필수
- **WebSocket / SSE 실시간 잡 상태** — 현재 polling
- **`.github/dependabot.yml`** — v0.3 Phase A 에서 보류된 항목

### Future Backlog (자동매매)

⚠ **별도 보안 / 컴플라이언스 / 자본 한도 / 비상정지 / 일일 손실 제한 사이클이
선행되어야 진입 가능.** v0.6 도 자동매매 부재 정책을 유지한다.

| 단계 | 진입 전제 |
|---|---|
| Strategy & Signal | 실 News (v0.5) + 실 재무 (v0.6) 후행 |
| Backtest 엔진 | Strategy 모듈 선행 |
| MockBroker / ReplayBroker / SimulationBroker | BrokerInterface 구현 진입 |
| 전용 ML 모델 | Backtest 데이터 누적 후행 |
| APPROVAL 모드 | 컴플라이언스 검토 + MockBroker 검증 |
| SMALL_AUTO | APPROVAL 안정 운영 후 |
| FULL_AUTO | 본 프로젝트 범위 외 |

## 운영 가이드 요약

자세한 절차는 [`INTEGRATION_RUNBOOK.md`](./INTEGRATION_RUNBOOK.md) 참조.

### 뉴스 수집 활성화 (운영자 명시 enable 필요)

```text
# .env
NEWS_COLLECTION_ENABLED=true
```

backend 재기동 후 19:00 KST 잡부터 NewsCollector 동작. provider 가 `session.info["news_provider"]`
에 주입되지 않으면 SUCCESS + `data_status: SKIPPED` (`reason: "no_provider_configured"`).
실 RSS / DART 구현체가 v0.5 시점에는 없으므로 운영 default 동작은 SKIPPED.

### 공시 수집 활성화

```text
# .env
DISCLOSURE_COLLECTION_ENABLED=true
```

backend 재기동 후 20:00 KST 잡부터 DisclosureCollector 동작. RISK_DISCLOSURE 카테고리는
v0.5 Phase C 의 `DisclosureRiskProducer` 가 RiskEngine 보강에 사용한다 (count > 0 시
`RISK_FLAG_DISCLOSURE` flag + min(count × 3, 10) penalty).

### 테마 랭킹 / 상세 화면

```
GET /api/themes/ranking?category=...&direction=...&limit=...
GET /api/themes/{theme_id}?mapping_limit=...&signal_limit=...
```

프런트는 `/themes` (사이드바 7번째 위치) + `/themes/:theme_id`. `report_themes` 행이
v0.4 Phase B 의 import 잡에서 만들어져 있어야 결과를 반환. 비어 있으면 응답 `items: []`,
화면은 "아직 테마 데이터가 없습니다" placeholder.

### 추천 응답의 evidence 필드

`/api/recommendations/latest` 등 모든 recommendation 응답에 `news_evidence` /
`disclosure_risk_evidence` 가 nullable dict 로 포함된다. `RealNewsScoreProducer` /
`DisclosureRiskProducer` 가 wired 되지 않은 pre-v0.5 run / 시드 데이터에서는 둘 다
`null`. Whitelist 정책 그대로 — 본문 / `source_file_path` / 운영자 로컬 경로 0건.

### 4 게이트 재실행 명령

```powershell
# 백엔드
.\.venv\bin\python.exe -m pytest -q

# 프런트
cd frontend
npm run test
npm run build
npm run e2e
```

## 누적 인수 태그 (v0.1 ~ v0.5)

- `v0.1-backend-final` → `v0.1-backend-kis-paper-verified`
- `v0.2-frontend-final`
- `v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → `v0.3-final`
- `v0.4-backend-reports` → `v0.4-import-pipeline` → `v0.4-report-score` → `v0.4-frontend-reports` → `v0.4-final`
- `v0.5-news-collector` → `v0.5-disclosure-pipeline` → `v0.5-news-score` → `v0.5-frontend-themes` → **`v0.5-final`** (예정)
