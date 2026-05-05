# PROJECT_STATUS.md

진행 상태 스냅샷. 새 Codex 세션이 이어서 작업을 시작할 때 가장 먼저 읽어야 할
파일이다. AGENTS.md / TASKS.md와 함께 사용한다. §0 은 항상 가장 최근 사이클의
**시작 또는 마감 선언**을 담고, 이전 사이클의 마감 선언은 §0-1, §0-2, §0-3,
§0-4 … 로 강등된다 (시간순 역배열).

---

## 0. v0.5 시작 선언 — News, Disclosure & Theme Ranking

**v0.5 cycle 진입.** 기준선 `v0.4-final` (HEAD `0f25be6` 시점, origin/main 동기화 완료). v0.1 backend + v0.2 frontend + v0.3 분석·운영 + v0.4 Analyst & Theme Intelligence 모두 마감 위에 **News / Disclosure 데이터 라인** + **테마 랭킹 화면** 5 phase 를 진행한다. v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책 + v0.4 의 저작권 정책 (본문 paragraph 미저장 / 자동 fetch default OFF) 모두 그대로 유지한다.

### v0.5 핵심 목표

뉴스 / 공시 메타데이터를 v0.1 부터 비어 있던 `news_items` 테이블에 **처음으로 채우고**,
`DummyScoreProducer.news_score` (가중치 25%) 를 **첫 real 화** 한다 (`RealNewsScoreProducer`).
`RISK_DISCLOSURE` 카테고리는 `RiskEngine` 의 `risk_flags` / `risk_penalty` 로 보강된다.
v0.4 의 **테마·매핑·시그널 데이터는 `/themes` 9번째 화면으로 처음 surface** 되며,
StockDetail 의 "관련 테마" 카드도 `impact_path` icon + reason 으로 가시화 강화된다.
추천 산식 본 weight (technical 35% + news 25% + supply 15% + fundamental 15% +
ai 10% - risk_penalty) 는 변경하지 않는다 — `news_score` 가 placeholder 50 → real
값으로 교체될 뿐.

### v0.5 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 (예정) |
|---|---|---|---|
| A | News data layer (`NewsProviderInterface` + `NewsCollector` + `news_items.category` 컬럼 + `collect_news` 잡 19:00 KST) | ✅ 인수 (PR1: pytest 382 → 401 / PR2: 401 → 406, 회귀 0건) | `v0.5-news-collector` |
| B | Disclosure subset + 분류 5종 + `collect_disclosures` 잡 (20:00 KST) | ✅ 인수 (backend pytest 406 → 440, 회귀 0건) | `v0.5-disclosure-pipeline` |
| C | `RealNewsScoreProducer` + `DisclosureRiskProducer` + `ScoreProducerInterface` ABC 추출 + RecommendationEngine 통합 | ⏳ | `v0.5-news-score` |
| D | 백엔드 `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` + 프런트 `/themes` 9번째 화면 + StockDetail 영향 강화 | ⏳ | `v0.5-frontend-themes` |
| E | `RELEASE_NOTES_v0.5.md` + README / PROJECT_STATUS / TASKS / ARCHITECTURE 마감 + tag `v0.5-final` | ⏳ | `v0.5-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0005`, 체크리스트는 [`TASKS.md`](./TASKS.md) `v0.5 — News, Disclosure & Theme Ranking` 섹션 참조.

### Phase A PR1 결과 (요약) — Data layer skeleton

> Phase A 는 **PR1 (data layer skeleton)** + **PR2 (scheduler integration)** 두
> PR 로 분리한다. PR1 인수 시점 = backend pytest **382 → 401 passed (+19)**,
> 회귀 0건. PR2 인수 후 태그 `v0.5-news-collector` 부여.

- `app/data/interfaces.py` — `NewsProviderInterface` ABC 신규 (`fetch_recent_news(*, symbols, since, limit) -> list[NewsItemDTO]`). 기존 `DataProviderInterface.fetch_news` 의 raw-dict placeholder 와는 별개.
- `app/data/dtos.py` — `NewsItemDTO` dataclass 신규 (9 필드: title / url / provider / published_at / symbol / source / category / sentiment_label / summary). **본문 paragraph / body / content / full_text / raw_text / paragraph_text / 본문 / 원문 / 전문 등 13종 forbidden 필드 0건** (테스트가 명시적 단언).
- `app/data/collectors/news_collector.py` 신규 — `NewsCollector` + `NewsCollectorResult` (fetched / inserted / skipped_duplicates / truncated_summaries). url-keyed 멱등, 재실행 시 0 중복. summary 500자 초과 시 truncate count 만 보고하고 persist 는 다음 phase 의 schema 확장에서 검토.
- `app/db/models.py` — `NewsItem.category: String(32) nullable, index=True` ALTER ADD COLUMN. 6 enum 값 (NEWS / EARNINGS_REPORT / OWNERSHIP_CHANGE / RISK_DISCLOSURE / GOVERNANCE / OTHER). destructive 0건.
- `app/data/repositories/news_items.py` — 기존 `list_by_time_range` 외 4 신규 메서드 (`get_by_url`, `upsert_by_url` 멱등, `list_recent_by_symbol` JSON contains via Python filter, `list_recent_by_category`).
- `tests/mocks/fake_news_provider.py` 신규 — `FakeNewsProvider` 결정론적 3-row 샘플 (NEWS / EARNINGS_REPORT / RISK_DISCLOSURE 카테고리 각 1건). `since` / `symbols` / `limit` 필터 지원.
- `tests/integration/test_news_collector.py` 신규 — **19 케이스**:
  - copyright/scope guards (4건): DTO 본문 필드 0 / DTO 정확히 9 fields / ORM 본문 컬럼 0 / category 컬럼 존재
  - FakeNewsProvider (3건): determinism / symbols·since 필터 / interface 구현
  - NewsCollector flow (6건): 첫 run 3건 insert / 재실행 멱등 0 insert / category persist / related_symbols + sentiment persist / source fallback to provider / summary truncate count / empty provider 처리
  - Repository (5건): upsert_by_url returns inserted flag / empty url reject / list_recent_by_symbol JSON contains + since 필터 / list_recent_by_category 정렬·필터
- 회귀: backend pytest **382 → 401 passed (+19)**. frontend / e2e / build 변경 0건. KIS / Telegram / scheduler / API 라우터 / 프런트 0건 변경 (정책 준수).
- `DB_SCHEMA.md` §8 `news_items` 갱신 — `category` 컬럼 + 저작권 정책 한 단락.

**Phase A PR2 (scheduler integration) 진입 시 첫 작업**: `app/config/settings.py` 에 `news_collection_enabled: bool = False` 추가 → `app/scheduler/jobs.py` 에 `collect_news` 잡 + flag 분기 (false → NO_DATA, true → NewsCollector 실행) → `app/scheduler/scheduler.py` 에 19:00 KST 등록 → `tests/integration/test_scheduler_jobs.py` registry 7→8 jobs + flag 분기 케이스 ~3건.

### Phase A PR2 결과 (요약) — Scheduler integration

> Phase A 의 두 번째 PR. 직전 PR1 의 data layer 위에 8번째 일별 잡 (19:00 KST) 을
> 등록하되, **default OFF**. 운영자가 `.env` 에 `NEWS_COLLECTION_ENABLED=true`
> 를 명시 설정한 경우에만 NewsCollector 가 동작. 두 PR 누적 후 태그 `v0.5-news-collector` 부여.

- `app/config/settings.py` — `news_collection_enabled: bool = False` 추가. `NEWS_COLLECTION_ENABLED` env var 매핑 (default false). v0.1 부터 유지된 default-OFF feature flag 패턴 (`feature_real_order_execution` / `feature_full_auto` / `feature_paper_trading` / `telegram_enabled` 등) 과 동일.
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_NEWS` 상수 + `_resolve_news_provider(session)` helper (`session.info["news_provider"]` 에서 주입 받음, 없으면 None) + `collect_news(session)` 함수. **3-way branch**: (1) disabled → SUCCESS + `data_status: SKIPPED` + `reason: "news_collection_disabled"` (provider 호출 0건, 외부 호출 0건), (2) enabled + provider 미주입 → SUCCESS + `data_status: SKIPPED` + `reason: "no_provider_configured"` (실 RSS / DART 구현체가 없는 v0.5 시점의 운영 default 동작), (3) enabled + provider 주입 → `NewsCollector.collect_recent` 실행 + counters (fetched / inserted / skipped_duplicates / truncated_summaries) `result_summary` 에 기록.
- `app/scheduler/scheduler.py` — `JOB_NAME_COLLECT_NEWS` import + `DEFAULT_SCHEDULE` 19:00 KST 등록 (KIS 마감 데이터 18:00 + 지표 계산 18:30 직후 슬롯). 주석에 PR2 컨텍스트 + default-OFF 정책 명시.
- `app/scheduler/jobs.py` `JOB_FUNCTIONS` registry **7 → 8 jobs**.
- `tests/integration/test_scheduler_jobs.py` 갱신 — `test_job_functions_registry_covers_all_seven_jobs` → `..._eight_jobs`. 신규 5 케이스: `test_default_schedule_includes_collect_news_at_1900_kst` / `test_collect_news_disabled_returns_skipped_without_invoking_provider` (provider spy 가 disabled 분기에서 호출 0건 검증) / `test_collect_news_enabled_without_provider_returns_skipped` / `test_collect_news_enabled_with_fake_provider_inserts_three_rows` / `test_collect_news_enabled_re_run_is_idempotent` (재실행 시 3 skipped_duplicates).
- `tests/unit/test_project_structure.py::test_settings_defaults` — `news_collection_enabled is False` 단언 추가.
- 회귀: backend pytest **401 → 406 passed (+5)**. frontend vitest 60 / build / e2e 9 변경 없음 (코드 변경이 backend scheduler 에 한정).
- API 라우터 / 프런트 / KIS / Telegram / 자동매매 / 외부 호출 일체 변경 0건. NEWS_COLLECTION_ENABLED 가 default false 라 프로덕션 동작 영향 0건 (기존 7 잡 timeline + 19:00 SKIPPED 1 잡 추가).

### Phase B 결과 (요약) — Disclosure subset + 분류 + collect_disclosures 잡

> Phase A 의 News 패턴을 그대로 복제 + 공시 keyword 분류 (5 카테고리, priority
> order) 추가. 잡 timeline 9 잡 누적 (20:00 KST collect_disclosures 추가).
> default OFF — 운영자가 .env 에 `DISCLOSURE_COLLECTION_ENABLED=true` 명시 시
> 에만 동작.

- `app/data/interfaces.py` — `DisclosureProviderInterface` ABC (`fetch_recent_disclosures(*, symbols, since, limit)`). NewsProviderInterface 와 동일 typed 패턴.
- `app/data/dtos.py` — `DisclosureItemDTO` 신규 (9 fields: title / url / provider / published_at / symbol / company_name / disclosure_type / category / summary). 본문 paragraph / body / content / full_text 등 13종 forbidden 필드 0건 (테스트 명시 단언).
- `app/data/collectors/disclosure_collector.py` 신규 — `classify_disclosure(title, disclosure_type, summary) -> str` 순수 함수 + `DisclosureCollector` + `DisclosureCollectorResult`. 분류 5 카테고리 + priority order: **RISK_DISCLOSURE > EARNINGS_REPORT > OWNERSHIP_CHANGE > GOVERNANCE > OTHER** (RISK 우선 — 안전 신호가 실적 신호보다 중요). 한글 keyword (소송 / 횡령 / 배임 / 거래정지 / 감사의견 / 회생 / 파산 / 실적 / 잠정 / 영업이익 / 당기순이익 / 최대주주 / 지분 / 이사회 / 사외이사 등) + 영문 keyword (lawsuit / fraud / earnings / governance 등) 동시 지원.
- `app/scheduler/jobs.py` — `JOB_NAME_COLLECT_DISCLOSURES` + `_resolve_disclosure_provider(session)` + `collect_disclosures(session)`. Phase A 의 `collect_news` 와 동일 3-way branch 패턴 (disabled → SKIPPED disclosure_collection_disabled / enabled+no_provider → SKIPPED no_provider_configured / enabled+provider → DisclosureCollector 실행). `result_summary` 에 `classified_counts` 추가 (5 enum 별 inserted 수). `JOB_FUNCTIONS` **8 → 9 jobs**.
- `app/scheduler/scheduler.py` — DEFAULT_SCHEDULE `(20, 0)` 등록. Phase A 의 19:00 collect_news 직후 슬롯.
- `app/config/settings.py` — `disclosure_collection_enabled: bool = False` 추가 (default OFF, `DISCLOSURE_COLLECTION_ENABLED` env var 매핑).
- `tests/mocks/fake_disclosure_provider.py` 신규 — `FakeDisclosureProvider` 결정론적 4-row 샘플: EARNINGS (삼성전자 1Q 실적) / OWNERSHIP (SK하이닉스 대량보유 변동) / RISK (A사 거래정지 + 감사의견 거절) / GOVERNANCE (B사 사외이사 선임). `symbols` / `since` / `limit` 필터 지원.
- `tests/integration/test_disclosure_collector.py` 신규 — **24 케이스**: copyright/scope guards 2 (DTO 본문 필드 0 / 9 fields exactness) / 분류 룰 18 (12 parametrized Korean keywords + RISK > EARNINGS priority + RISK > GOVERNANCE priority + uses disclosure_type / uses summary / OTHER fallback + 영문 keyword) / FakeProvider 4 (determinism / symbols 필터 / since 필터 / interface 구현) / collector flow 7 (4 inserted + classified_counts / 멱등 4 skipped_duplicates / category persist / summary truncate / empty provider / related_symbols persist) / 메타.
- `tests/integration/test_scheduler_jobs.py` 갱신 — registry 8 → 9 jobs + 20:00 KST schedule 검증 + collect_disclosures 4 분기 케이스 (disabled / enabled+no_provider / enabled+FakeProvider 4 inserted + classified_counts / 멱등).
- `tests/unit/test_project_structure.py::test_settings_defaults` — `disclosure_collection_enabled is False` 단언 추가.
- `DB_SCHEMA.md` §8 `news_items.category` 설명 보강 — 뉴스/공시 통합 저장 + DisclosureCollector keyword priority 명시.
- `INTEGRATION_RUNBOOK.md` §11 신규 — 5 단락 (기본 동작 / opt-in / 분류 룰 표 / 수동 트리거 / 운영 점검 / 롤백). §10 News 와 동일 패턴.
- 회귀: backend pytest **406 → 440 passed (+34)**. frontend vitest 60 / build / e2e 9 변경 없음. KIS / Telegram / API 라우터 / 프런트 / 자동매매 / 외부 호출 일체 변경 0건. DISCLOSURE_COLLECTION_ENABLED default false 라 프로덕션 동작 영향 0건 (8 잡 timeline + 20:00 SKIPPED 1 잡 추가).

### 후보 비교 / 선택 사유 (요약)

7 개 v0.5 후보 중 채택:

- ✅ **News / 공시 실제화** — `DummyScoreProducer.news_score` 25% weight 첫 real 화 (가장 큰 점수 품질 영향)
- ✅ **테마 랭킹 화면** — v0.4 누적 데이터의 첫 surface
- △ **리포트 인텔리전스 고도화** — Phase D 의 StockDetail 영향 가시화 강화로 부분 채택

미채택 → v0.6+ 로 미룸:

- ❌ **재무 / 실적 점수 실제화** (DART 재무제표 파싱 별도 cycle)
- ❌ **관심종목 / Watchlist** (POST 첫 도입은 인증과 묶음)
- ❌ **인증 / 보안** (Watchlist 와 묶어서 v0.6)
- ❌ **전략 / 백테스트 / 자동매매** (v0.7+ Future Backlog)

### `news_score` 산식 (Phase C 상세)

```
recency_factor = sum_{news in last 7d} (
    weight_by_age * sentiment_mapping(news.sentiment)
)
weight_by_age      = 1.0 (≤24h) / 0.7 (≤3d) / 0.3 (≤7d)
sentiment_mapping  = POSITIVE: +1, NEUTRAL: 0, NEGATIVE: -1, UNKNOWN: 0
news_score         = clip( 50 + recency_factor * 5 / news_count, 0, 100 )
                   = 50 if news_count == 0  (Dummy fallback 호환)

# RiskEngine 보강
if any(category=RISK_DISCLOSURE in last 14d):
    risk_flags     += "RISK_DISCLOSURE"
    risk_penalty   += min(risk_disclosures_count * 3, 10)   # cap +10
```

본 weight 산식은 손대지 않는다 — `news_score` 가 50 → real 로 교체되지만 가중치
25% 그대로. `decision_logs.rule_result_json["news_evidence"]` 추가 (top 3 / sentiment
분포 / recency).

### v0.5 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST / PUT / DELETE 라우터 (read-only API 만 — v0.1 ~ v0.4 일관 정책 유지)
- ❌ 뉴스 / 공시 본문 (paragraph) DB 저장 — title / URL / 메타데이터 / 분류 / sentiment 라벨만 (v0.4 저작권 정책 패턴 유지)
- ❌ 자동 fetch default ON — `news_collection_enabled` / `disclosure_collection_enabled` = false (운영자가 `.env` 에 명시 enable 시에만 동작)
- ❌ 재무 / 실적 점수 실제화 — v0.6 후보
- ❌ 관심종목 / Watchlist / 인증 — v0.6 후보 (POST 도입은 인증 사이클과 묶음)
- ❌ Strategy / Backtest / MockBroker — v0.7+ 후보
- ❌ HoldingCheckEngine 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 (`news_score` 만 placeholder 교체)
- ❌ KIS API 외 외부 자격증명 추가 — 무료 RSS / DART 공공 API 만 (default OFF, opt-in)
- ❌ LLM 자동 sentiment 분석 — Phase C 는 룰 기반만, LLM 보강은 v0.6+

### v0.5 백엔드 정책 변경 안내

`v0.4-final` 동결을 v0.5 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터 / 잡 트리거 / 자동매매 코드는 추가하지 않는다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| A | `app/db/models.py` `NewsItem.category` ALTER ADD COLUMN (nullable) | 신규 컬럼 1개 |
| A | `app/data/interfaces.py` / `dtos.py` / `collectors/news_collector.py` (신규) | News provider ABC + DTO + collector |
| A | `app/data/repositories/news_items.py` | `upsert_by_url` / `list_recent_by_symbol` 등 메서드 추가 |
| A/B | `app/scheduler/jobs.py` / `scheduler.py` | `collect_news` (8번째) + `collect_disclosures` (9번째) 등록 |
| A/B | `app/config/settings.py` | `news_collection_enabled` / `disclosure_collection_enabled` (default False) |
| B | `app/data/collectors/disclosure_collector.py` (신규) | 공시 분류 룰 (keyword → category 5종) |
| C | `app/analysis/score_producers.py` | `ScoreProducerInterface` ABC 추출 + `RealNewsScoreProducer` + `DisclosureRiskProducer` 신규 |
| C | `app/decision/risk_engine.py` | `RISK_DISCLOSURE` flag 처리 (penalty 가산, max +10) |
| C | `app/decision/recommendation_engine.py` / `holding_check_engine.py` | score_producer ABC 주입 + `news_evidence` 기록 |
| C | `app/api/schemas.py` | `news_evidence` 필드 추가 |
| D | `app/api/routes.py` | `GET /api/themes/ranking` + `GET /api/themes/{theme_id}` (read-only) |
| D | `app/api/schemas.py` | `ThemeRankingItemSchema` / `ThemeDetailResponse` 신규 |
| D | `frontend/src/pages/Themes/` (신규 디렉터리) + `router.tsx` + `Sidebar` | `/themes` 9번째 화면 |

**HoldingCheckEngine / ScoringEngine 본 weight 산식은 손대지 않는다.** 신규 컬럼 1개 + 신규 테이블 0건 — destructive 0건. 운영 환경 마이그레이션 = `ALTER TABLE news_items ADD COLUMN category VARCHAR(32);` 한 줄.

---

## 0-1. v0.4 마감 선언 — Analyst & Theme Intelligence

**v0.4 Analyst & Theme Intelligence 사이클은 종료 (마감) 상태이다.** 기준선
`v0.3-final` 위에 리포트 메타데이터 저장, CSV import, 컨센서스 스냅샷,
`report_score` / `theme_signal_score`, StockDetail / Recommendations 대시보드 표시까지
완료했다. v0.1 의 read-only / 자동매매 부재 / 비밀 마스킹 / mock·DRY_RUN 정책은
그대로 유지했다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.4-final` 예정 |
| 현재 인수 태그 | `v0.4-frontend-reports` |
| 마감 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | **backend pytest 382 / frontend vitest 60 / frontend build 통과 / Playwright e2e 9** |
| 자동매매 / 실 주문 / POST | **v0.4 범위 밖** — POST 라우터 0건, 주문 코드 0건 |
| 저작권·보안 | 원문 전문 미저장, PDF BLOB 미저장, 자동 크롤링 0건, `source_file_path` 외부 노출 0건 |

### v0.4 핵심 목표

증권사 애널리스트 리포트 (기업 / 산업 / 테마 / 원자재 / 매크로 / 전략) 메타데이터를
**CSV / Excel 로 import** 하고, 리포트에서 추출한 **투자 테마** 와 **테마 → 종목
매핑** 을 저장하며, 목표가 상향 / 공급 부족 / 수요 회복 같은 **변화 시그널 이벤트**
를 구조화한다. 보조 점수 `report_score` (기업 리포트 기반) + `theme_signal_score`
(테마·시그널 기반 선행 신호) 를 계산해 추천 / 종목 상세에 참고 근거로 노출한다.
추천 최종 산식 본 weight 는 변경하지 않고, ±5점 cap 보조 가산만 적용한다.

### v0.4 범위 (Phase A~E)

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | **DB 모델 6종 + Repository** (`analyst_reports` / `report_themes` / `theme_stock_mappings` / `report_signal_events` / `report_consensus_snapshots` / `report_score_logs`) + 통합 테스트 16건 | ✅ 인수 (backend pytest 319 → 335, 회귀 0건) | `v0.4-backend-reports` |
| B | **CSV import CLI (리포트 + 테마 + 매핑 + 시그널) + 일별 컨센서스 스냅샷 잡** + 통합 테스트 27건 | ✅ 인수 (backend pytest 335 → 362, 회귀 0건) | `v0.4-import-pipeline` |
| C | `report_score` + `theme_signal_score` 계산기 + RecommendationEngine 통합 (±5점 cap 합산) + decision evidence | ✅ 인수 (backend pytest 379 / vitest 59 / build / e2e 8, 회귀 0건) | `v0.4-report-score` |
| D | 프런트 (StockDetail 리포트·테마·시그널 카드 + Recommendations score 컬럼 2개) | ✅ 인수 (backend pytest 382 / vitest 60 / build / e2e 9, 회귀 0건) | `v0.4-frontend-reports` |
| E | `RELEASE_NOTES_v0.4.md` + README / PROJECT_STATUS / TASKS 마감 + tag `v0.4-final` | ✅ 문서 마감 / 최종 게이트 재확인 권한 이슈 | `v0.4-final` |

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0004`, 체크리스트는
[`TASKS.md`](./TASKS.md) `v0.4 — Analyst & Theme Intelligence` 섹션 참조.

### Phase A 결과 (요약)

- `app/db/models.py` 에 6 테이블 신규 — `AnalystReport` (28 컬럼, COMPANY/SECTOR/INDUSTRY/THEME/COMMODITY/MACRO/STRATEGY 7 타입을 단일 테이블에서 `report_type` 으로 구분, `symbol` nullable 허용) / `ReportTheme` (theme_category 13종 + direction + time_horizon, FK source_report) / `ThemeStockMapping` (impact_direction + impact_path 11종 + relation_type + benefit_type, 글로벌 ticker 지원) / `ReportSignalEvent` (event_type 18종, evidence_json) / `ReportConsensusSnapshot` (window_days 별 분리) / `ReportScoreLog` (report_score + theme_signal_score 둘 다 보관).
- `app/data/repositories/` 에 6 Repository 신규 + `__init__.py` export 갱신. 각 repo 가 `create` + `upsert_by_*` 멱등 + 다양한 list 쿼리 (theme/symbol/direction/path/event_type/recent) 제공.
- `tests/integration/test_analyst_report_repositories.py` **16 케이스** — CRUD / unique 충돌 / 글로벌 US 리포트 (NVDA / NASDAQ / USD / Goldman Sachs broker) / null symbol (THEME / MACRO / COMMODITY) / 종목 search / 테마 카테고리·방향 / 매핑 positive·negative · impact_path / signal event 분기 / consensus window 30/90 분리 / score log recommendation_run 연계.
- 백엔드 pytest **319 → 335 passed (+16)**. frontend / e2e / build 회귀 0건 (변경 없음).
- `DB_SCHEMA.md` §18~23 추가, 저작권 정책 단락 명시. 운영 환경 마이그레이션 = 신규 `CREATE TABLE` 6 줄, destructive 0건.

### Phase B 결과 (요약)

- `app/data/importers/analyst_reports.py` 신규 — `AnalystReportCsvImporter` 가 35 컬럼 CSV 한 row 를 최대 4 entity (report + theme + N mappings + signal_event) 로 분해. enum 검증 11종, 헤더 forbidden body-column 13종 거부 (`body`/`content`/`full_text`/`paragraph_text`/`article_body`/`raw_text`/`html_body`/`paragraphs`/`full_body`/`original_text`/`report_body`/`본문`/`원문`/`전문`).
- `scripts/import_analyst_reports.py` 신규 — argparse CLI (`--file --commit --encoding --db-url`). 기본 dry-run, `--commit` 명시 시에만 DB 적재. 출력 summary 에 `source_file_path` 0건 노출 (basename 마스킹), 에러 메시지조차 컬럼명 + 정상 enum/date/숫자만 echo.
- `tests/fixtures/analyst_reports_sample.csv` 신규 (3 row: COMPANY 삼성전자 + THEME 메모리 쇼티지 + COMMODITY Cu) — 모두 가상 데이터, 실제 증권사 원문 0건.
- `app/scheduler/jobs.py` — `update_report_consensus_snapshots` 잡 신규. COMPANY 타입 + 발행 후 90일 이내 활성 리포트만 종목별 집계해 `report_consensus_snapshots.upsert_by_symbol_date_window` 로 멱등 upsert. NO_DATA / SUCCESS 분기. KIS / 텔레그램 / 외부 호출 0건.
- `app/scheduler/scheduler.py` — 06:30 KST 잡 등록 (06:00 텔레그램 발송 직후 / 08:30 pre-market check 직전 시간 슬롯). 7번째 등록 잡.
- `tests/integration/test_analyst_report_import.py` (19 케이스) + `tests/integration/test_consensus_snapshot_job.py` (8 케이스) 신규. `tests/integration/test_scheduler_jobs.py` 의 6 jobs registry 검증 → 7 jobs 로 갱신.
- `INTEGRATION_RUNBOOK.md` §9 신규 (dry-run / commit / 인코딩 / DB URL / 컨센서스 잡 수동 트리거 / 점검 5 단락).
- 백엔드 pytest **335 → 362 passed (+27)**. frontend / e2e / build 회귀 0건 (변경 없음).
- API 라우터 / 추천 엔진 / 점수 산식 / 프런트 / KIS / 텔레그램 / 자동매매 일체 변경 0건 (정책 준수). pandas / openpyxl 의존성 미추가 (stdlib `csv` 만 사용).

### Phase C 결과 (요약)

- `app/analysis/report_score_calculator.py` 신규 — `report_score`, `theme_signal_score`, 두 점수의 ±5점 cap 보조 가산을 순수 함수로 분리했다. `report_count = 0` 이면 `report_score = null`, 테마/시그널이 모두 없으면 `theme_signal_score = null` 로 처리해 기존 추천 점수 영향은 0이다.
- `app/decision/recommendation_engine.py` — 후보 종목별 최신 consensus snapshot, 최신 close, theme mapping, recent signal event 를 조회해 두 보조 점수를 계산하고 `recommendation.total_score` 에 후처리 가산만 적용한다. 기존 ScoringEngine 본 weight 는 변경하지 않았다.
- `report_score_logs` 에 추천 실행별 계산 이력을 저장하고, `decision_logs.rule_result_json["report_evidence"]` 에 score/evidence/adjustment 를 기록한다.
- `app/api/schemas.py`, `app/api/routes.py` — `RecommendationItemSchema` 에 `report_score`, `theme_signal_score`, `report_evidence` 를 nullable 필드로 추가했다. 기존 응답 필드는 유지된다.
- `tests/unit/test_report_score_calculator.py` 신규 12건, `tests/integration/test_recommendation_engine.py` / `tests/integration/test_api_routes.py` 보강. Phase C targeted pytest **77 passed**, 전체 회귀 게이트 **backend pytest 379 / frontend vitest 59 / build / Playwright e2e 8 passed**.
- HoldingCheckEngine / ScoringEngine 본 weight / KIS / 텔레그램 / 자동매매 / POST 라우터 / 프런트 화면 변경 0건.

### Phase D 결과 (요약)

- `GET /api/stocks/{symbol}` 응답에 `analyst_reports` 블록을 추가하고, 동일 구조를 반환하는 read-only `GET /api/stocks/{symbol}/reports` 라우터를 추가했다.
- `analyst_reports` 는 `latest_consensus`, `recent_reports`, `related_themes`, `recent_signal_events` 를 포함한다. `source_url` 은 허용하고 `source_file_path` 는 schema/응답에서 제외했다.
- StockDetail 화면에 Analyst Consensus, Recent Reports, Related Themes, Signal Events 카드를 추가했다. 데이터 없음 상태는 각 카드별 empty placeholder 로 처리한다.
- Recommendations 테이블에 `report_score`, `theme_signal_score`, `report_evidence` 요약 컬럼을 추가했다. null 값은 `—` 로 표시한다.
- API/vitest/e2e fixture 모두에서 `source_file_path` 미노출 검증을 추가했다.
- 회귀 게이트: backend pytest **382 passed**, frontend vitest **60 passed**, frontend build **passed**, Playwright e2e **9 passed**.
- POST 라우터 / KIS 호출 / 텔레그램 발송 / 자동매매 / 주문 코드 / 리포트 자동 크롤링 / 원문 전문 노출 / ScoringEngine 본 weight 변경 0건.

### Phase E 결과 (요약)

- `RELEASE_NOTES_v0.4.md` 신규 작성. Phase A~D 산출물, 테스트 결과, 저작권·보안 정책, 제외 범위, 알려진 한계, v0.5 후보를 정리했다.
- `README.md`, `PROJECT_STATUS.md`, `TASKS.md` 를 v0.4 마감 상태로 갱신했다.
- `API_SPEC.md` / `DB_SCHEMA.md` 기준으로 `source_file_path` 미노출 정책과 analyst report read-only API 설명을 재확인했다.
- 회귀 게이트 4종 재확인 완료 — backend pytest **382 passed**, frontend vitest **60 passed**, frontend build **passed**, Playwright e2e **9 passed**. Phase D 시점 baseline 과 동일 (회귀 0건).
- 기능 코드 / 백엔드 라우터 / 프런트 화면 / DB 모델 변경 0건.

### v0.5 후보

- Excel 직접 import 지원
- 운영자용 import 검증 리포트 개선
- StockDetail 리포트 필터/정렬 고도화
- HoldingCheckEngine에 report/theme 보조 근거를 별도 phase로 검토
- 관심종목/즐겨찾기
- 인증/권한
- 실제 News/Fundamental/Earnings 파이프라인
- Dependabot / CI 운영 보강
- 운영 DB migration 스크립트 정리

자동매매, 실주문, POST 트리거는 v0.5 후보가 아니다. 별도 보안/컴플라이언스/리스크
사이클이 선행되어야 한다.

### v0.4 데이터 모델 요약 (6 테이블)

- **`analyst_reports`** — 모든 리포트 메타 (28 컬럼, `report_type` 7종 단일 테이블, 글로벌 ticker / currency / language 지원). Unique `(broker_name, published_at, title)`. **`source_file_path` 는 API 응답 / 프런트에서 미노출** (Phase D 의 schema 단에서 마스킹).
- **`report_themes`** — 리포트에서 추출한 투자 테마. theme_category 13종 (SEMICONDUCTOR / AI / COMMODITY / ENERGY / DEFENSE / SHIPBUILDING / BIO / AUTO / BATTERY / POWER_GRID / DATA_CENTER / MACRO / CUSTOM). FK source_report.
- **`theme_stock_mappings`** — 테마 → 종목 영향 매핑. impact_direction (POSITIVE/NEGATIVE/MIXED/NEUTRAL) + impact_path 11종 + relation_type + benefit_type + time_lag. 글로벌 종목 동일 테이블.
- **`report_signal_events`** — 변화 시그널 이벤트. event_type 18종 (TARGET_PRICE_UP / SUPPLY_SHORTAGE / DEMAND_RECOVERY / RISK_WARNING …) + direction + strength + evidence_json. FK report + nullable theme.
- **`report_consensus_snapshots`** — 종목별 일별 컨센서스. `window_days` 별 분리 저장 (default 90일). Unique `(symbol, snapshot_date, window_days)`.
- **`report_score_logs`** — 두 점수 (report_score + theme_signal_score) 계산 이력. theme_count / signal_event_count / theme_signal_bonus / event_signal_bonus / risk_penalty + evidence_json. `recommendation_runs.run_id` 와 nullable FK 연계.

### v0.4 `report_score` + `theme_signal_score` 산식 (요약)

```
# (1) 기업 리포트 기반
report_score = clip( 50 + (target_upside_pct * 0.5) + (rating_score_avg * 10) + recency_bonus, 0, 100 )

# (2) 테마·시그널 기반 선행 신호
theme_signal_score = clip( 50 + theme_signal_bonus + event_signal_bonus - risk_penalty, 0, 100 )

# (3) 추천 보조 (±5 cap, 두 점수 합산)
total_score_after = clip( total_score + clip( (report_score - 50) * 0.1, -5, +5 )
                                       + clip( (theme_signal_score - 50) * 0.1, -5, +5 ), 0, 100 )
```

`report_count = 0` → `report_score = null` (영향 0). 시그널 / 테마 0 → `theme_signal_score = null`.

### v0.4 에서 절대 하지 않을 것 (정책)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO
- ❌ POST 트리거 UI / 라우터 — import 는 운영자 CLI 만, GET 응답에만 변화
- ❌ 리포트 자동 크롤링 / 스크레이핑 — v0.4 는 수동 CSV/Excel + MANUAL/RULE_BASED/LLM_ASSISTED 태깅만 (자동 fetch 는 v0.5+)
- ❌ 리포트 원문 전문 (PDF body / paragraph) DB 저장 — 운영자 직접 작성 짧은 요약 (≤500자) 만
- ❌ PDF 파일 자체 git 레포 / DB BLOB 저장 — `source_url` 또는 `source_file_path` 만
- ❌ `source_file_path` 외부 노출 — API 응답 / 프런트 / e2e 모두에서 마스킹 또는 미포함
- ❌ 외부 공유 / 공개 API
- ❌ LLM 자동 요약 — Phase A 는 미구현, `extraction_method` / `extraction_confidence` 필드만 미리 둠 (v0.5+ 후보)
- ❌ 뉴스 / 공시 / 재무 / 실적 실시간 수집 — v0.5+ 별도 cycle
- ❌ 즐겨찾기 / 관심 종목 / 인증 / Strategy / Backtest / MockBroker — v0.5+ 후보 그대로
- ❌ HoldingCheck 산식 변경 (보유 점검 그대로)
- ❌ 추천 산식 본 weight 변경 — 두 score 모두 ±5점 cap 보조 가산만

### v0.4 백엔드 동결 정책 변경 안내

`v0.3-final` 동결을 v0.4 에서 일부 깬다. 변경 범위는 다음으로 한정 — POST 라우터
/ 잡 트리거 / 자동매매 코드는 추가하지 않는다.

| Phase | 변경 파일 | 종류 | 상태 |
|---|---|---|---|
| A | `app/db/models.py` | ALTER ADD TABLE **6개** | ✅ |
| A | `app/data/repositories/{analyst_reports,report_themes,theme_stock_mappings,report_signal_events,report_consensus_snapshots,report_score_logs}.py` | 신규 Repository 6개 | ✅ |
| A | `app/data/repositories/__init__.py` | export 추가 | ✅ |
| A | `tests/integration/test_analyst_report_repositories.py` | 16 케이스 신규 | ✅ |
| B | `scripts/import_analyst_reports.py` | 신규 CLI (dry-run/commit, 리포트 + 테마 + 매핑 + 시그널) | ✅ |
| B | `app/scheduler/jobs.py`, `app/scheduler/scheduler.py` | `update_report_consensus_snapshots` 잡 1건 추가 | ✅ |
| C | `app/analysis/report_score_calculator.py` | 신규 순수 함수 (report_score + theme_signal_score) | ✅ |
| C | `app/decision/recommendation_engine.py` | 두 score 후처리 가산 + decision evidence 기록 | ✅ |
| C/D | `app/api/schemas.py` | 신규 schema 4종 (`AnalystReportSchema` / `ReportThemeSchema` / `ThemeStockMappingSchema` / `ReportSignalEventSchema`) + `RecommendationItemSchema` 확장 | ✅ Phase C: 추천 응답 score 필드 |
| D | `app/api/routes.py` | 신규 read-only `GET /api/stocks/{symbol}/reports` 등 | ✅ |

**HoldingCheckEngine / ScoringEngine 본 weight 산식 / 6 잡 시그니처는 손대지
않는다.** 신규 테이블 추가는 `CREATE TABLE` 이라 destructive 0건이지만 운영
환경 마이그레이션 안내 필수 ([`DB_SCHEMA.md`](./DB_SCHEMA.md) 끝부분 박스 참조).

---

## 0-2. v0.3 마감 선언 — 분석 보강 + 운영 정착

**v0.3 분석 보강 + 운영 정착 사이클은 종료 (마감) 상태이다.** 신규 기능 / 잡 /
라우터 / 화면 추가는 사용자의 명시적 v0.4 진입 요청 전까지 진행하지 않는다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.3-final` |
| 인수 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | **백엔드 pytest 319 / frontend vitest 59 / Playwright e2e 8 / build 그대로** (외부 호출 0건, mock / DRY_RUN 만) |
| 자동매매 / 실 주문 | **v0.3 범위 밖** — `BrokerInterface` ABC placeholder 그대로 유지 / POST 트리거 0건 |
| 누적 인수 태그 | `v0.3-phase-a-ci` → `v0.3-backend-analysis` → `v0.3-frontend-calendar` → `v0.3-frontend-stock-chart` → **`v0.3-final`** |
| 종합 인수 사유 | [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) |

### v0.3 4 phase 인수 결과

| Phase | 작업 | 상태 | 산출 태그 |
|---|---|---|---|
| A | GitHub Actions CI (backend pytest + frontend vitest+build + Playwright e2e 3 job) | ✅ 인수 | `v0.3-phase-a-ci` |
| B | 캔들 패턴 5종 + Wilder ATR(14) + 변동성 분류 → `technical_score` 산식 보강 (DB 컬럼 +3) | ✅ 인수 (backend pytest 296 → 314, vitest / e2e / build 회귀 0) | `v0.3-backend-analysis` |
| C | 정적 KRX 휴장일 캘린더 (2025–2027) + Today/Jobs/Holdings MarketStatusBanner | ✅ 인수 (vitest 36 → 55, e2e 6 → 7, build / backend pytest 314 회귀 0) | `v0.3-frontend-calendar` |
| D | `GET /api/stocks/{symbol}/prices` 신규 + StockDetail 일봉 라인 차트 (Recharts) | ✅ 인수 (backend pytest 314 → 319, vitest 55 → 59, e2e 7 → 8, build 그대로) | `v0.3-frontend-stock-chart` |
| E | `RELEASE_NOTES_v0.3.md` + README / PROJECT_STATUS / TASKS 마감 + tag `v0.3-final` | ✅ 인수 (코드 변경 없음, 4 게이트 그대로) | `v0.3-final` |

### Phase A 결과 (요약)

- `.github/workflows/ci.yml` 신규 — main / PR 양쪽에서 3 job 자동 실행: (1) backend pytest python 3.12 + `pip install -e ".[dev]"`, (2) frontend vitest + lint + build node 20, (3) Playwright e2e (`playwright install chromium` + `npm run e2e` + `playwright-report/` artifact 업로드).
- PR 1건 의도적 실패로 빨강 한 번 확인 → 픽스 후 그린 상태로 마감.
- 코드 변경 없음 (워크플로우 / config 만 추가). `.github/dependabot.yml` 은 v0.4 후보로 보류.

### Phase B 결과 (요약)

- `app/analysis/technical_analyzer.py` 에 캔들 5종 (DOJI / HAMMER / SHOOTING_STAR / BULLISH_ENGULFING / BEARISH_ENGULFING) detector + Wilder ATR(14) + 4단계 volatility band (LOW/NORMAL/HIGH/EXTREME) 추가.
- `calculate_technical_score` 에 보조 가산/감산 (`candle_bonus` ±5 cap, `volatility_bonus` -5~+2) 후 0~100 clamp 명시. 새 인자는 모두 default None 이라 기존 호출자는 수치 변화 0건.
- `StockIndicator` 에 nullable 컬럼 3개 추가 (`atr14 Numeric(20,4)`, `candle_patterns JSON`, `volatility_band String(16)`). ALTER ADD only — 기존 데이터 무영향.
- `StockIndicatorRepository.upsert` 시그니처에 신규 키워드 3개 (default None) + `TechnicalIndicatorService` 가 snapshot 의 신규 필드를 그대로 upsert.
- `StockIndicatorSchema` (Pydantic) 에 3개 optional 필드 추가 → `/api/stocks/{symbol}.latest_indicator` 응답에 자동 포함. 프런트 타입은 Phase D 에서 명시 추가 예정.
- 단위 테스트 16건 신규 (analyzer 32 → 48), 통합 테스트 2건 신규 (indicator 7 → 9), 기존 회귀 0건. 백엔드 전체: **296 → 314 passed**.
- 부수 정정: `frontend/vite.config.ts` 의 vitest `include` / `exclude` 추가 — Playwright e2e 파일 (`e2e/**/*.spec.ts`) 이 vitest 의 기본 glob 에 잡혀 collect 단계 실패하던 노이즈 제거.

### Phase C 결과 (요약)

- `frontend/src/data/krxHolidays.ts` 신규 — 2025~2027 KRX 휴장일 정적 JSON. 카테고리 6종 (`fixed` / `lunar` / `substitute` / `election` / `temporary` / `year-end`). 주석에 출처 (KRX 공식 휴장일 안내) + 매년 갱신 절차 4단계 (KRX 공지 확인 → 다음 해 항목 추가 → 테스트 1~2건 추가 → PR / push → CI 회귀).
- `frontend/src/lib/marketCalendar.ts` 신규 — KST(`Asia/Seoul`) 기준 `todayInSeoul` + UTC midnight 산술 기반 `dayOfWeek` / `isWeekend` / `getHoliday` / `isHoliday` / `isMarketClosed` / `isMarketOpen` / `nextOpenDay` (max 30 day scan, throw on exceed) / `previousOpenDay` / `classifyMarketStatus` (open / WEEKEND / HOLIDAY 분기 + `nextOpen`). 외부 API / 백엔드 호출 0건.
- `frontend/src/components/common/MarketStatusBanner.tsx` 신규 — `data-state` 3 분기 (`open` 에메랄드 / `holiday` 앰버 / `weekend` 뉴트럴). 헤드라인 / 디테일 한국어. `date?` prop 으로 시점 freeze 가능 (테스트용).
- Today / Jobs / Holdings 화면 헤더 직후에 `<MarketStatusBanner />` 1줄 통합. 다른 화면 (Recommendations / History / StockDetail / MarketCapTop / Settings) 은 v0.3 범위 외라 미통합.
- 단위 테스트 19건 신규 (`marketCalendar.test.tsx` 15 + `MarketStatusBanner.test.tsx` 4) → vitest **36 → 55 passed**.
- e2e 1건 신규 — Today / Jobs / Holdings 3 경로에서 `data-testid="market-status-banner"` 노출 + `data-state` 정합성 검증 → playwright **6 → 7 passed**.
- 회귀: backend pytest 314 / build 그대로. 백엔드 코드 변경 0건 (정책 준수).

### Phase D 결과 (요약)

- `app/api/routes.py` 에 read-only `GET /api/stocks/{symbol}/prices?days=120` 신규. `days` 는 `Query(120, ge=1, le=500)` 검증, `daily_prices` 만 조회 (KIS 호출 0건). `app/api/schemas.py` 에 `StockPriceSeriesResponse` 추가 (`symbol`, `days`, `count`, `prices[DailyPriceSchema]`).
- `DailyPriceRepository.list_by_symbol` 가 이미 최신 N건을 날짜 오름차순으로 반환하는 형태라 라우터는 wrapping 만. 응답 일자 정렬 = ascending (차트 그대로 사용 가능). 404: 종목 없음, 200 + count=0: 종목은 있으나 일봉 0건.
- `tests/integration/test_api_routes.py` 에 5건 신규 (`stock_prices_returns_series_ascending_with_default_days` / `caps_to_requested_days_param` / `returns_empty_when_no_prices_seeded` / `404_for_unknown_symbol` / `validates_days_bounds` 0/501 → 422). 백엔드 전체: **314 → 319 passed**.
- 프런트: `useStockPriceSeries(symbol, { days })` 훅 (queryKey `['stocks', symbol, 'prices', { days }]`, staleTime 60s, `enabled: !!symbol`) + `StockPriceSeriesResponse` 타입 추가.
- `frontend/src/pages/StockDetail/PriceChart.tsx` 신규 — Recharts `LineChart` (close 추세). `data-testid="price-chart"` / 빈 상태 `price-chart-empty`. Recharts 는 `vendor-charts` 청크에 격리되어 있고 StockDetail 페이지 자체가 router 레벨 `React.lazy` 라 별도 lazy wrap 불필요.
- `frontend/src/pages/StockDetail/index.tsx` 에 `PriceChartCard` 추가 — 30/60/120/250 days 선택자 (`role="tab"`, 기본 120d active), loading / error / empty / success 4 상태. POST 트리거 / 자동매매 UI 0건.
- vitest 4건 신규 (chart success / empty / error / days 선택자 토글 + searchParams 검증), MSW 기본 핸들러 `/api/stocks/:symbol/prices` (count=0) 추가, e2e fixture `STOCK_PRICE_SERIES_005930` (5건) + 라우트 패턴 `/api/stocks/005930/prices` 우선순위 등록. 프런트 vitest **55 → 59**, Playwright e2e **7 → 8**.
- 빌드 그대로 (vendor-charts 청크 383.32 kB 동일, StockDetail 페이지 청크만 8.28 → 11.36 kB 증가). 정책: 자동매매 / KIS 호출 / 텔레그램 / POST 라우터 / 추천·보유 산식 0건 변경.

### Phase E 결과 (요약)

- `RELEASE_NOTES_v0.3.md` 신규 (산출물 / 검증 / 제외 / 한계 / v0.4 후보 / 인수자 가이드 / 보안).
- `README.md` 상단 마감 배너 갱신 — v0.3 마감 선언으로 교체, v0.1 / v0.2 는 누적 태그 라인으로 흡수.
- `PROJECT_STATUS.md` §0 v0.3 마감 선언으로 변경 (본 섹션). 기존 §0-1 v0.2 / §0-2 v0.1 마감 선언은 그대로 보존.
- `TASKS.md` v0.3 Phase E 모든 [x] + v0.4 백로그 정리.
- 4 게이트 재확인 — backend pytest **319**, frontend vitest **59**, frontend build 그대로, Playwright e2e **8**. 회귀 0건.
- **코드 변경 0건** (문서 마감 위주). 백엔드 라우터 / 프런트 화면 / 잡 / 산식 / 비밀값 일체 손대지 않음.

세부 계획은 [`PLANS.md`](./PLANS.md) `PLAN-0003`, 체크리스트는 [`TASKS.md`](./TASKS.md) `v0.3 — 분석 보강 + 운영 정착` 섹션 참조.

### v0.3 에서 끝까지 하지 않은 것 (정책 재확인)

- ❌ 실거래 자동매매 / 실 KIS 주문 / FULL_AUTO / APPROVAL / SMALL_AUTO — 코드 0건 추가
- ❌ POST 트리거 UI (수동 잡 실행 / 추천 즉시 생성 / 보유 추가·삭제 폼) — frontend / backend 양쪽 0건
- ❌ 실 News / Supply / Fundamental / Earnings 외부 파이프라인 — `DummyScoreProducer` placeholder 유지, 캔들/ATR/변동성만 추가 (기존 일봉 데이터로 계산)
- ❌ 즐겨찾기 / 관심 종목 / 인증 / 모니터링 / 모바일 — 모두 v0.4+ 후보

### v0.3 백엔드 동결 정책 변경 (확정)

`v0.1-backend-final` 동결을 v0.3 에서 일부 깬 범위는 다음으로 한정 — POST 라우터 /
잡 트리거 / 자동매매 코드는 추가하지 않았다.

| Phase | 변경 파일 | 종류 |
|---|---|---|
| B | `app/analysis/technical_analyzer.py` | 신규 함수 (캔들 5종 / ATR / 변동성), 기존 산식 시그니처는 default None 키워드만 추가 |
| B | `app/db/models.py` | `StockIndicator` ALTER ADD 3 컬럼 (모두 nullable) |
| B | `app/data/repositories/stock_indicators.py` | `upsert` 키워드 3개 추가 |
| B | `app/analysis/indicator_service.py` | snapshot 의 신규 필드 persist |
| B/D | `app/api/schemas.py` | `StockIndicatorSchema` +3 optional / `StockPriceSeriesResponse` 신규 |
| D | `app/api/routes.py` | 신규 read-only `GET /api/stocks/{symbol}/prices` 1개 |
| B/D | `tests/integration/test_*.py` | +5 (Phase B indicator) +5 (Phase D prices) |

DB 컬럼 추가는 `ALTER TABLE ADD COLUMN` 만이라 destructive 하지 않다. 운영 환경
마이그레이션 안내는 [`RELEASE_NOTES_v0.3.md`](./RELEASE_NOTES_v0.3.md) §7.3 참조.

---

## 0-3. v0.2 PC 대시보드 마감 선언

**v0.2 frontend 는 종료 (마감) 상태이다.** v0.1 backend 동결 (`v0.1-backend-final`)
위에 PC 대시보드 8 화면이 모두 read-only 로 연결되었고, vitest 36 + Playwright
e2e 6 + 백엔드 pytest 296 회귀 게이트가 모두 통과. 종합 인수 사유는
[`RELEASE_NOTES_v0.2_FRONTEND.md`](./RELEASE_NOTES_v0.2_FRONTEND.md) 참조.

| 항목 | 값 |
|---|---|
| 최종 frontend 태그 | `v0.2-frontend-final` |
| 누적 frontend 태그 | `phase-a` (골격) → `phase-b` (Today/Jobs) → `phase-c` (Recommendations/History) → `phase-d` (Holdings/StockDetail) → `phase-e` (MarketCap/Settings) → `final` (lazy + e2e + Docker + 릴리스) |
| 8 화면 | 오늘 / 추천 / 추천 이력 / 보유 / 종목 상세 / 시총 TOP / 잡 / 설정 — 모두 실 데이터 연동 + 빈/에러 상태 처리 |
| 번들 (첫 진입 Today) | ≈ 297 kB / gzip ~80 kB (lazy + manualChunks 적용 후). Recharts 청크는 추세 화면 진입 시에만 로드 |
| Docker | `docker compose up --build` → 백엔드 (8000) + 프런트 (8080) 동시 기동, nginx `/api` → backend proxy |
| 자동매매 / 실 주문 | **v0.2 범위 밖** — `BrokerInterface` ABC placeholder 유지 / POST 트리거 UI 0건 |

---

## 0-4. v0.1 백엔드 마감 선언 (참고)

**v0.1 백엔드는 종료 (마감) 상태이다.** 새 기능 / 리팩터 / 잡 / 라우터 추가는
사용자의 명시적 v0.2 backend 진입 요청 전까지 진행하지 않는다.

| 항목 | 값 |
|---|---|
| 최종 태그 | `v0.1-backend-kis-paper-verified` |
| 인수 일자 | 2026-05-05 (Asia/Seoul) |
| 회귀 게이트 | pytest **296 passed** (외부 호출 0건, mock / DRY_RUN 만) |
| 통합 검증 | mock seed (§2 "v0.1 통합 실행 결과") + 실 KIS 모의투자 read-only (§2 "실 KIS 운영 검증 결과" + 후속) 모두 1회 통과 |
| 자동매매 / 실 주문 | **v0.1 범위 밖** — `BrokerInterface` ABC placeholder 만 유지 (구체 구현 0건) |
| 누적 인수 태그 | `v0.1-foundation-checkpoint` → `v0.1-backend-accepted` → `v0.1-backend-kis-paper-verified` |

마감 선언의 종합 사유 / 산출물 / 알려진 한계 / v0.2 후보는
[`RELEASE_NOTES_v0.1_BACKEND.md`](./RELEASE_NOTES_v0.1_BACKEND.md) 에 정리.

---

## 1. 완료된 Phase

| Phase | 범위 | 주요 산출물 |
|---|---|---|
| **0** 프로젝트 준비 | 13개 문서 + 초기 커밋 | AGENTS.md, README, ARCHITECTURE, API_SPEC, DB_SCHEMA, ROADMAP, SECURITY, TESTING, TASKS, PLANS, brief / detailed_spec / agent_creation_spec |
| **1** 아키텍처/골격 | FastAPI 앱, 4개 인터페이스 | `app/main.py`, `app/config/`, `DataProviderInterface`, `AIProviderInterface`, `BrokerInterface`, `StrategyInterface`, `.env.example` |
| **2** DB/Repository | 17개 ORM 모델 + Repository | `app/db/{base,models,session}.py`, `app/data/repositories/*.py` (16개 클래스) |
| **3-1** KIS DTO/normalizer/validator | DTO + 정규화 + 품질 검사 | `app/data/dtos.py`, `app/data/normalizers/kis.py`, `app/data/validators/quality.py` |
| **3-2** KIS HTTP 클라이언트 | httpx 기반 read-only 클라이언트 | `app/data/collectors/kis_client.py` (토큰/현재가/일봉/시총) |
| **3-3** Collector | KIS raw → DB 저장 흐름 | `DailyPriceCollector`, `MarketCapRankingCollector`, `FakeKisDataProvider` (테스트용) |
| **4-1** TechnicalAnalyzer | 순수 지표 계산기 | `app/analysis/technical_analyzer.py` (MA/RSI/MACD/breakout/ma_alignment/technical_score) |
| **4-2** IndicatorService + ScoringEngine | 저장 서비스 + 점수 산식 | `app/analysis/indicator_service.py`, `app/decision/scoring_engine.py` (신규 추천/보유 가중치) |
| **5-1** RecommendationEngine | 추천 골격 (placeholder 점수) | `app/decision/recommendation_engine.py`, `recommendation_runs/recommendations/data_snapshots/decision_logs` 4개 테이블 일괄 저장 |
| **5-2** HoldingCheckEngine | 장전/장후 보유 점검 | `app/decision/holding_check_engine.py`, HOLD/WATCH/REDUCE/SELL_REVIEW 결정, 위험 경고 평가 |
| **5-3** RiskEngine | risk_penalty / risk_level / risk_flags | `app/decision/risk_engine.py`, ScoringEngine 및 양 Engine 연결, `data_snapshots`/`decision_logs`에 risk 결과 기록 |
| **5 후속** 추천 성과 검증 | 1/3/5/20일 후 수익률 계산 | `app/decision/recommendation_result_service.py`, `recommendation_results` upsert 멱등 |
| **6** Notification & Report | 텔레그램용 텍스트 + 발송 + 로그 | `app/notification/report_generator.py`, `telegram_notifier.py`, `notification_service.py` (DRY_RUN 기본) |
| **7** Backend API | 13개 read-only GET 라우터 | `app/api/{schemas,routes}.py`, FastAPI lifespan 통합, 모든 Decimal은 JSON 문자열 직렬화 |
| **7 후속** API 성과 노출 | 추천 항목에 `results[]` + history 집계 | `RecommendationResultSchema`, `RecommendationHistoryItem` 확장 (`success_rate`, `avg_close_return_{1,3,5,20}d`) |
| **8** Scheduler + 6개 Job | APScheduler + `run_job` 래퍼 | `app/scheduler/{jobs,scheduler}.py`, FastAPI lifespan에서 lazy import 후 시작/종료, `SCHEDULER_ENABLED` 제어 |
| **8 후속** Dispatcher 연결 | 추천/보유/ALERT 잡 → 텔레그램 자동 발송 | `app/notification/dispatchers.py`, 잡에서 `session.info["job_run_id"]`로 `notification_logs.related_job_id` 자동 연결, `HoldingRiskAlertDispatcher` 연동 완료 |
| **8 후속** 잡 최종 점검 | 6개 잡 모두 dispatcher / engine / NO_DATA·PARTIAL 분기 정리 | `send_recommendation_report`은 최신 run을 dispatcher로 발송 (NO_DATA 단락), `run_pre/post_market_holding_check`은 활성 보유 없으면 NO_DATA 단락, `update_recommendation_results`는 `data_status` SUCCESS/PARTIAL/NO_DATA + skipped_no_reference 시 PARTIAL |
| **4 후속** Dummy score producer | News/Supply/Fundamental/Earnings/AI 컴포넌트 점수 placeholder | `app/analysis/score_producers.py` (`DummyScoreProducer`), `RecommendationEngine`/`HoldingCheckEngine` 생성자 default 주입 — neutral 50 + volume_ratio_20d / ma_alignment 기반 룰베이스 ±5 nudge, 메타데이터 `decision_logs.rule_result_json["score_producer"]`에 저장 |
| **7 후속** Stock detail 추천 이력 join | `/api/stocks/{symbol}` 응답에 추천 이력 + 1/3/5/20일 성과 | `_resolve_recent_recommendations_for_symbol` (Recommendation+RecommendationRun join, run_date desc), `RecommendationItemSchema.results: List[RecommendationResultSchema]` 채움, `recommendation_limit`/`holding_check_limit` 쿼리 파라미터 |
| **7 후속** Holding check 추세 metric | `/api/holdings/{symbol}/checks` 응답에 종목 단위 summary 추가 | `HoldingCheckSymbolMetrics`/`HoldingCheckSymbolResponse` 신규 schema, summary는 limit 무관하게 종목 전체 이력 집계 (total/alert/high_risk count + latest/previous/change + best/worst return rate + latest decision/risk_level), 정렬 규칙 `(check_date desc, POST > PRE)` |
| **9** v0.1 통합 시나리오 / mock seed | 실 KIS·실 텔레그램 없이 백엔드 전체 흐름 로컬 검증 | `scripts/seed_mock_data.py` (멱등 + `--reset`), `INTEGRATION_RUNBOOK.md` (사전준비 → 시드 → 6개 잡 수동 트리거 → 13개 GET API → 로그 검증 → 회귀 게이트), README §9 진입점 |

브리프 전체 v0.1 범위 + 일부 v0.2 후속 (성과 검증, dispatcher, holding metric, 통합 시나리오) 까지 도달. **v0.1 백엔드 마감 상태** — 코드 변경이 남은 v0.1 항목은 §4 "남은 v0.1 작업" 의 두 건뿐이며, 이번 작업으로 신규 세션 / QA 인수자가 mock seed + runbook 만으로 전체 흐름을 30분 안에 검증 가능.

---

## 2. 현재 테스트 결과

```text
296 passed in 5.48s
```

| 영역 | 파일 수 | 테스트 수 |
|---|---:|---:|
| `tests/unit/` | 11 | 127 |
| `tests/integration/` | 11 | 169 |

**테스트 파일별 카운트:**

```text
tests/integration/test_api_routes.py                     42
tests/integration/test_collectors.py                      8
tests/integration/test_dispatchers.py                    16
tests/integration/test_holding_check_engine.py           17
tests/integration/test_indicator_service.py               7
tests/integration/test_notification_service.py            6
tests/integration/test_recommendation_engine.py          13
tests/integration/test_recommendation_result_service.py  13
tests/integration/test_repositories.py                    6
tests/integration/test_scheduler_jobs.py                 34
tests/integration/test_v01_required_repositories.py       7
tests/unit/test_data_quality_checker.py                   4
tests/unit/test_kis_client_http.py                        9
tests/unit/test_kis_normalizers.py                        3
tests/unit/test_project_structure.py                      4
tests/unit/test_report_generator.py                      12
tests/unit/test_risk_engine.py                           25
tests/unit/test_scheduler_module.py                       5
tests/unit/test_score_producers.py                        3
tests/unit/test_scoring_engine.py                        16
tests/unit/test_technical_analyzer.py                    32
tests/unit/test_telegram_notifier.py                     14
```

회귀 0건. 모든 외부 호출(KIS, Telegram)은 mock transport / dry-run 으로만 접근.

### v0.1 통합 실행 결과 (1회 수행)

`INTEGRATION_RUNBOOK.md` §1 ~ §5 시나리오를 실제로 1회 수행한 결과 (UTC
2026-05-04 22:52 / Asia/Seoul 2026-05-05 07:52, throwaway SQLite 파일).

**1. Seed (`scripts.seed_mock_data --reset`)**

```text
stocks:5  market_cap_rankings:5  universe_members:5  daily_prices:150
stock_indicators:5  holdings:2  recommendation_runs:3  recommendations:8
holding_checks:4  data_snapshots:12
```

**2~7. 6개 잡 수동 트리거 (모두 SUCCESS, dry-run)**

| 잡 | status | 핵심 result_summary |
|---|---|---|
| `collect_market_close_data` | SUCCESS | mock provider 주입, market_cap_status=SUCCESS, daily=5/5 success |
| `calculate_technical_indicators` | SUCCESS | members=5, snapshots_saved=5, skipped=0, fail=0 |
| `send_recommendation_report` | SUCCESS | notification_status=DRY_RUN, run_date=2026-05-04, recs=3, msg_len=364 |
| `run_pre_market_holding_check` | SUCCESS | check_type=PRE_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `run_post_market_holding_check` | SUCCESS | check_type=POST_MARKET, checked=2, alert_count=2, alert_sent=2, dry_run=True |
| `update_recommendation_results` | SUCCESS | data_status=SUCCESS, runs=3, processed=8, upserted=32, pending=29, success=0, failed=3, skipped_no_ref=0 |

**8. notification_logs / job_runs**

- `notification_logs`: 7건 — REPORT 3 (recommendation 1 + holding pre/post 2) + ALERT 4 (HIGH_RISK 3 + CHECK_ALERT 1, target dedup 키 정상)
- `job_runs`: 6건, 모두 SUCCESS. result_summary / status / error_message / finished_at 정상 기록
- `holding_checks`: 8건 (005930 5 + 000660 3) — 시드의 4건 + 잡이 새 일자(Asia/Seoul today)에 추가한 4건

**9. 13개 GET API 응답**

```text
200 /health
200 /api/reports/today
200 /api/recommendations/latest    (recommendations=3)
200 /api/recommendations/history   (items=3 — 시드한 3개 run)
200 /api/holdings                  (holdings=2)
200 /api/holdings/checks/latest    (items=2)
200 /api/holdings/005930/checks    (items=5 + summary)
200 /api/stocks/005930
200 /api/universe/market-cap-top   (items=2 — 잡이 limit=2로 갱신)
200 /api/market-regime/latest
200 /api/news                      (items=0 — 시드 미적재)
200 /api/jobs                      (items=6)
200 /api/settings                  (KIS/Telegram 자격증명 마스킹)
```

`/api/holdings/005930/checks` summary 표본:
`total=5, alert=3, high_risk=2, latest_decision=SELL_REVIEW,
latest_risk_level=MEDIUM, latest_total_score=16.2500, previous=4.2500,
change=12.0000`.

**관찰 / 알아둘 점**

- `seed_mock_data`는 `datetime.now(UTC).date()`를 "today"로 사용하지만,
  스케줄러 잡은 `_today_in_default_timezone()` (`settings.timezone`,
  default Asia/Seoul)을 사용. 시드 실행 시각이 UTC 15:00 이후 (≈ Seoul
  24:00 이후) 이면 시드 "today"가 잡의 "today"보다 하루 빠르게 나오고,
  잡은 새 일자에 fresh 행을 만들어 둘 다 공존한다. 데이터 손상은 아니며
  대시보드 추세 metric도 정상 동작.
- `update_recommendation_results`는 시드 가격 30봉 안에서 1/3/5/20일 후
  검증을 수행 — 가장 오래된 run (today-7) 만 1/3/5일 모두 평가 가능, 나머지는
  PENDING이 다수.
- 회귀 게이트 `pytest`: **296 passed in 5.87s** (이번 실행 직후 동일 결과 확인).

### 실 KIS 운영 검증 결과 (1회 수행)

`KIS_OPS_CHECKLIST.md` 절차에 따라 실 KIS 모의투자 키 + 검증용 비공개 텔레그램
채팅방 기준으로 1회 시도. read-only 인증과 일봉 조회는 통과, 시총 상위
endpoint 에서 KIS contract 결함 1건이 발견되어 **collect 잡은 FAILED**.

**검증 모드**

- `KIS_USE_PAPER=true` (모의투자 서버 `openapivts.koreainvestment.com:29443`)
- `TELEGRAM_ENABLED=false`
- `SCHEDULER_ENABLED=false`
- `FEATURE_REAL_ORDER_EXECUTION=false`
- `FEATURE_FULL_AUTO=false`
- 검증용 DB: `sqlite:///./stock_ai_kis_check.db` (운영 / 시드 DB 와 격리)

**사전 안전 점검 (모두 통과)**

- `.env` git ignore / 미커밋 / 이력 부재
- `.env` ACL 좁히기 적용 (Owner + Admins + SYSTEM 만 FullControl, CodexSandboxUsers 는 Read 만)
- `Settings()` 로딩 시 `kis_app_key` / `kis_app_secret` / `kis_account_no` /
  `telegram_bot_token` / `telegram_chat_id` 모두 마스킹된 형태로만 표시
- `/api/settings` 라우터 응답에서도 동일한 마스킹 + 안전 플래그 모두 false
- 실주문 / 자동매매 코드 부재: `place_order` / `order_execute` / KIS 주문
  엔드포인트 / `BrokerInterface` 구체 구현 모두 0건 — `BrokerInterface` 는
  `app/broker/interfaces.py` 의 ABC 정의(`raise NotImplementedError`) 로만 존재

**KIS read-only 단건 검증**

- 토큰 발급 (`/oauth2/tokenP`): ✅ SUCCESS (token length=346, 본문 비노출)
- 005930 일봉 조회 (`/uapi/domestic-stock/v1/quotations/inquire-daily-price`): ✅ SUCCESS
  - 조회 기간: 2026-04-28 ~ 2026-05-05 (영업일 4건)
  - 반환 row 수: 4
  - 첫 행 (최신순): `date=20260504, close=232500`
  - 마지막 행: `date=20260428, close=222000`
  - 모의투자 시세는 paper 서버 자체 시뮬레이션 값이므로 실시장과 다름 (정상)

**`collect_market_close_data` 잡 결과**

- 잡 자체는 정상 호출 (스키마 자동 생성, 안전 가드 통과, `job_runs` 행 정상 기록)
- 시총 상위 endpoint 호출에서 KIS 서버가 거절 →
  `KIS API error OPSQ2001: ERROR INPUT FIELD NOT FOUND [FID_COND_SCR_DIV_CODE]`
- 결과: `status=FAILED`, `market_cap_status=FAILED`, `daily_price_status=SKIPPED`
  (시총 단계 실패로 daily 수집은 의도적으로 실행되지 않음)

**영향 범위 (이번 1회 검증 기준)**

| KIS 경로 | 결과 |
|---|---|
| 토큰 발급 | ✅ |
| 일봉 조회 | ✅ |
| 시총 상위 ranking | ❌ contract 결함 1개 (필드 누락) |

따라서 v0.1 KIS 클라이언트의 read-only 경로 중 **시총 상위 endpoint 1개만**
paper 서버와 contract 가 어긋남. 인증 / 일봉은 정상 동작.

**Known Issue**

- `app/data/collectors/kis_client.py:fetch_market_cap_rankings` 의 query
  파라미터에 `FID_COND_SCR_DIV_CODE` 가 누락. KIS 시총 상위 화면 카테고리
  코드(후보값 `"20174"`) 추가 필요.
- `tests/unit/test_kis_client_http.py` 의 captured query params 도 실 KIS
  contract 에 맞춰 신규 파라미터 transmit 검증으로 갱신 필요.
- mock HTTP 테스트만으로는 이 누락이 드러나지 않으므로, 후속 픽스 시 paper
  서버 1회 재검증을 절차에 명시.

**다음 조치**

1. 별도 코드 수정 세션에서 `fetch_market_cap_rankings` 파라미터 보정 1줄 추가 + 단위 테스트 갱신.
2. 픽스 commit 후 `collect_market_close_data` 잡을 paper 서버에서 1회 재실행 → market_cap → daily_prices → 시총 + 일봉 모두 SUCCESS 확인.
3. 그 다음 단계로 `calculate_technical_indicators` → `send_recommendation_report` (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 시범 운행 진입.

**비밀 / 토큰**

본 절에는 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 / chat_id 평문이
일체 기록되지 않았다. 모든 비밀은 마스킹 형태(예: `5015****1-01`)로만
참조한다. 운영 검증 도중 발급된 KIS 액세스 토큰도 디스크 / 로그에 남지 않음
(`LOG_TO_FILE=false`).

### 후속 검증 — 시총 픽스 적용 후 (3회 시도)

`fetch_market_cap_rankings` 의 query 에 `FID_COND_SCR_DIV_CODE="20174"` 를
추가하는 픽스 (`eb8452a`) 적용 후 `collect_market_close_data` 잡을 동일한
검증 환경 (`KIS_USE_PAPER=true` / 검증용 DB / `MARKET_CAP_LIMIT=5`) 에서 3회
재실행. lookback 은 1·2회는 2일, 3회차는 7일.

**시총 상위 endpoint — 3/3 SUCCESS**

- 3회 모두 `market_cap_status=SUCCESS`, KOSPI 시총 상위 5건 정상 응답.
- `stocks` (5 신규 → 이후 0 신규, idempotent), `market_cap_rankings` (3회
  모두 5건, snapshot replace 정상), `stock_universe_members` (5 신규 → 0)
  저장 정상. KIS 시총 상위 endpoint contract 결함은 완전 해소.

**일봉 endpoint — signature 정상 / 종목별 paper 서버 한계 노출**

| 종목 | 1차 (lookback=2) | 2차 (lookback=2) | 3차 (lookback=7) | 누적 |
|---|---|---|---|---|
| 005930 (삼성전자) | ❌ | ✅ | ✅ (3 rows) | 2/3 |
| 005935 (삼성전자우) | ✅ | ❌ | ✅ (3 rows) | 2/3 |
| 402340 (SK스퀘어) | ✅ | ❌ | ❌ | 1/3 |
| 000660 (SK하이닉스) | ❌ | ❌ | ❌ | 0/3 |
| 373220 (LGES) | ❌ | ❌ | ❌ | 0/3 |

- 005930 / 005935 가 안정 SUCCESS 한 사실로 일봉 endpoint signature 자체는
  정상으로 판단. 직전 단건 검증 (`fetch_daily_prices(005930, 7일)` 4 rows)
  과 일관됨.
- 000660 / 373220 은 lookback / 호출 시점 무관하게 항시 `KIS HTTP 500`
  반환 → KIS 모의투자 서버의 종목별 시뮬레이션 데이터 또는 캐시 미적재
  문제로 추정. 코드 contract 결함으로 보지 않음.
- 402340 은 randomize 패턴 (run 마다 결과 변동) — 동일 paper 서버
  transient 5xx 패턴.

**잡 동작 정상 분기**

- 3회 모두 `status=PARTIAL`, `error_message="N daily price collections failed"`,
  종목별 실패는 `result_summary.failures` 항목 단위로 격리 기록.
- `job_runs` 행은 RUNNING → PARTIAL 전환 + `finished_at` / `result_summary` /
  `error_message` 정상 채워짐.
- 성공 종목의 `daily_prices` upsert + `market_cap_rankings` snapshot replace
  는 PARTIAL 상황에서도 의도대로 commit 됨 → DB 무결성 유지.

**회귀 게이트**

- 시총 픽스 직후 `pytest`: **296 passed in 5.87s** (회귀 0건).
- 본 후속 검증은 코드 변경을 동반하지 않음.

**판단 / 다음 단계**

- v0.1 백엔드 코드는 인수 (accepted) 상태 유지. KIS contract 픽스 1건이
  추가되었지만 영향 범위는 단일 endpoint 의 query 파라미터 한 줄로 좁고
  paper 서버에서 실측 검증됨.
- 본격 운영 검증 (전 종목 일봉 SUCCESS 확인) 은 KIS 실서버
  (`KIS_USE_PAPER=false`) 또는 paper 서버의 종목별 시뮬레이션 데이터가
  안정화된 시점에 다시 수행. v0.1 잡의 PARTIAL 격리 동작이 검증되었으므로
  실서버 진입 시 일부 종목 실패가 나오더라도 전체 흐름이 멈추지 않음.
- 다음 검증 cycle 에서는 `calculate_technical_indicators` → `send_recommendation_report`
  (DRY_RUN) → 보유 점검 → 성과 업데이트 순서로 진입 가능 (시총·일봉
  데이터 일부라도 적재된 상태).

---

## 3. 변경된 주요 모듈

| 패키지 | 핵심 모듈 | 책임 |
|---|---|---|
| `app/config/` | `settings.py`, `logging.py` | env 기반 Settings (`@lru_cache`), telegram/KIS/feature flags 포함 |
| `app/db/` | `base.py`, `models.py`, `session.py` | SQLAlchemy 2.0, 17개 v0.1 테이블, `SessionLocal` |
| `app/data/` | `interfaces.py`, `dtos.py`, `collectors/`, `normalizers/`, `validators/`, `repositories/` | 외부 API 경계, 16개 Repository, KisClient + 정규화 + 품질 검사 |
| `app/analysis/` | `technical_analyzer.py`, `indicator_service.py` | 순수 지표 계산 + `daily_prices` → `stock_indicators` upsert |
| `app/decision/` | `scoring_engine.py`, `risk_engine.py`, `recommendation_engine.py`, `holding_check_engine.py`, `recommendation_result_service.py` | 점수/리스크/추천/보유점검/사후 성과 |
| `app/notification/` | `report_generator.py`, `telegram_notifier.py`, `notification_service.py`, `dispatchers.py` | 텔레그램 텍스트 포맷 + 발송 (DRY_RUN 기본) + 로그 + dispatcher |
| `app/api/` | `schemas.py`, `routes.py` | 13개 GET 라우터, Pydantic v1 schema, Decimal → str 일관 직렬화 |
| `app/scheduler/` | `jobs.py`, `scheduler.py` | `run_job` 2-session 래퍼, 6개 잡, APScheduler `BackgroundScheduler` |
| `app/main.py` | FastAPI 앱 + `lifespan` | 라우터 등록, 스케줄러 lazy import 시작/종료, `/health` |

**의존성 (`pyproject.toml`):** fastapi 0.99, pydantic 1.10, SQLAlchemy 2.0, httpx 0.24+, uvicorn 0.30+, python-dotenv, **apscheduler 3.10+** (Phase 8에서 추가).

---

## 4. 아직 하지 않은 작업

**v0.1 범위 안에서 남은 것 (코드 변경 0건)**

코드 작업은 모두 완료. 운영 / 문서 단계만 남아있다.

- 실 KIS 키 + 실 텔레그램으로 1회 운영 검증 — 코드 경로는 완성되어 있고
  `KisClient`가 `settings`에서 자동 연결됨. `.env` 채움 + 안전 플래그 확인 +
  체크리스트 항목별 통과만 필요. 절차는 [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md)
  로 분리 정리.
- PROJECT_STATUS.md / TASKS.md — 신규 세션마다 수동 갱신 필요

**v0.2 이후로 미룬 범위 (Backlog)**

- 캔들 패턴 (망치형/장악형 등) + ATR 변동성 컴포넌트 → `technical_score` 산식 보강
  (Phase 4 후속, 신규 분석 기능 — v0.1 마감 시점에 명시적으로 v0.2 이동)
- React/Next.js PC 대시보드 프론트엔드
- 전략(장기/중기/단기) 관리, SIGNAL/PAPER 모드
- 백테스트 엔진, walk-forward 검증, 그리드 서치 튜닝
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 v0.1은 `DummyScoreProducer` 룰베이스 placeholder)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실거래)

---

## 5. 다음에 이어서 할 첫 번째 작업

**v0.1 백엔드는 마감 상태 (tag `v0.1-backend-accepted`).** 남은 코드 작업 없음.
다음 세션이 우선 처리할 항목은 다음 1건:

- **운영 검증 1회** — [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 항목별로
  실 KIS 키 + 실 텔레그램(검증용 비공개 채팅방)에서 1회 통과 후 결과를
  PROJECT_STATUS.md §2 "v0.1 통합 실행 결과" 아래 새 하위 절로 기록한다.
  코드 변경 없음.

캔들 패턴 / ATR / 그 외 신규 분석·전략·프론트엔드는 모두 v0.2 Backlog (§4)로
이동했으므로, 사용자의 명시적 v0.2 진입 요청 없이는 진행하지 않는다.
v0.1 마감 후의 새 기능 (잡 / 라우터 / 엔진 / dispatcher 추가)도 마찬가지.

---

## 6. 주의해야 할 v0.1 금지사항

`AGENTS.md` "Out of Scope" 섹션과 `SECURITY.md`를 어기지 말 것. 핵심:

**기능 금지**

- 실거래 자동매매, FULL_AUTO 모드, 가상 증권사 서버, 전략 자동 튜닝, 전용 AI 모델 학습
- KIS 주문 API 실행 (조회만 OK; 주문은 `BrokerInterface` placeholder만 유지)
- 대시보드 라우터 안에서 추천 생성 / 보유점검 실행 / 지표 재계산 / KIS 호출
- POST/PUT/DELETE 라우터 (현재 13개 모두 GET; 새 POST 라우터 만들지 말 것)
- 자동매매 / 주문 / 비중 결정 코드를 AI나 LLM이 단독으로 호출하는 경로

**보안 / 비밀**

- KIS app_key / app_secret / access_token / refresh_token / 계좌번호
- Telegram bot_token, chat_id (chat_id는 `12****90` 형태로만 노출)
- OpenAI API key, DB 비밀번호
- 위 값을 코드 / 로그 / 테스트 / 응답 본문 어디에도 평문 노출 금지
- `.env`는 절대 커밋 금지, `.env.example`만 커밋

**테스트**

- 실제 KIS API 호출하는 테스트 금지 → `httpx.MockTransport` 또는 `FakeKisDataProvider`
- 실제 텔레그램 발송 테스트 금지 → `telegram_enabled=False` (DRY_RUN) 또는 `httpx.MockTransport`
- 시간이 실제로 될 때까지 기다리는 스케줄러 테스트 금지 → 잡 함수를 직접 호출
- 실제 API 키 / 계좌번호를 테스트에 사용 금지 (모두 `fake_*` placeholder 사용)

**아키텍처 경계**

- Data 모듈은 판단하지 않는다 (Collector → Recommendation 직접 호출 금지)
- Analysis 모듈은 외부 API 호출하지 않는다
- Recommendation/Holding 모듈은 KIS API 직접 호출하지 않는다 (Repository 경유)
- AI 모듈이 직접 매매하지 않는다
- 라우터는 Repository 또는 service를 통해서만 데이터 조회
- 새 잡이 라우터를 호출하지 않는다 (잡 → service / dispatcher 직접)

**관찰성**

- 모든 추천/보유점검은 `data_snapshots` + `decision_logs`에 기록 가능해야 함
- 모든 잡 실행은 `job_runs`에 기록 (성공/PARTIAL/FAILED)
- 모든 텔레그램 발송 시도는 `notification_logs`에 기록 (DRY_RUN/SUCCESS/FAILED/DISABLED)

---

## 7. 다음 Codex 세션 첫 프롬프트

새 세션을 시작하면 아래 프롬프트를 그대로 사용한다.

```text
이 프로젝트의 AGENTS.md, TASKS.md, PROJECT_STATUS.md, SECURITY.md를 먼저 읽고
v0.1 범위 / 현재 진행 상태 / 금지사항을 파악해줘.

코드는 아직 수정하지 마. 다음 두 가지만 알려줘.
1. PROJECT_STATUS.md 의 "5. 다음에 이어서 할 첫 번째 작업"이 여전히 적합한가?
   (그 사이 사용자가 다른 우선순위를 말하지 않았다면 적합하다고 가정)
2. 작업을 시작하기 전에 미리 알아둬야 할 의문/리스크가 있는가?

내가 "진행해" 라고 답하면 그때부터 다음 작업의 PM/Architect 시점으로
PLANS.md 형식의 짧은 실행 계획을 먼저 작성해줘 (수정할 파일 / 새로 만들
파일 / 단계 / 테스트 / 완료 기준 / 위험 요소). 계획을 내가 승인하면
구현으로 들어가.

작업 중에는 v0.1 금지사항(특히 실거래 / 실 KIS 호출 / 실 텔레그램 발송 /
라우터 안에서 무거운 로직)을 어기지 마. 새 기능은 항상:
  - 기존 service/engine을 호출하거나
  - 기존이 없으면 안전한 placeholder를 반환하고
  - 모든 외부 호출은 mock 가능한 구조로 만들고
  - 모든 추천/보유점검/잡/알림은 snapshot/log/job_runs/notification_logs로
    추적 가능하게 만들어.
```
