# RELEASE_NOTES_v0.1_BACKEND.md

**v0.1 백엔드 마감 선언**

- 최종 태그: `v0.1-backend-kis-paper-verified`
- 인수 일자: 2026-05-05 (Asia/Seoul)
- 회귀 게이트: **pytest 296 passed**, mock 외부 호출만 사용 (실 KIS / 실 텔레그램 / 실 주문 0건)
- 누적 인수 태그
  - `v0.1-foundation-checkpoint` — 초기 골격 마감
  - `v0.1-backend-accepted` — mock seed 기반 통합 시나리오 1회 인수
  - `v0.1-backend-kis-paper-verified` — 실 KIS 모의투자 서버 read-only 검증 인수 (현재)

본 릴리스는 한국투자증권 API 기반 분석 / 추천 / 보유 점검 / 알림 / 대시보드
GET API + 스케줄러 백엔드의 v0.1 범위를 모두 마감한다. **자동매매 / 실
주문 / FULL_AUTO 모드는 v0.1 범위 밖**이며 본 릴리스에 코드 / 인터페이스
구현이 일체 포함되지 않는다 (`BrokerInterface` 는 ABC placeholder 만 유지).

---

## 1. 산출물 한 줄 요약

| 영역 | 산출물 |
|---|---|
| DB / Repository | 17개 v0.1 테이블 + 16개 Repository (`stocks`, `holdings`, `daily_prices`, `stock_indicators`, `market_cap_rankings`, `stock_universes`, `stock_universe_members`, `news_items`, `market_regimes`, `recommendation_runs`, `recommendations`, `recommendation_results`, `holding_checks`, `data_snapshots`, `decision_logs`, `job_runs`, `notification_logs`) |
| KIS 데이터 수집 | `KisClient` (토큰 / 현재가 / 일봉 / 시총 상위), `DailyPriceCollector`, `MarketCapRankingCollector`, DTO + normalizer + `DataQualityChecker`, mock-injectable transport |
| 분석 / 점수 | `TechnicalAnalyzer` (MA5/20/60/120, RSI14, MACD, volume_ratio_20d, breakout_20d/60d, ma_alignment, technical_score), `IndicatorService`, `ScoringEngine` (신규 추천 / 보유 가중치), `RiskEngine` (LOW/MEDIUM/HIGH + flags), `DummyScoreProducer` (News/Supply/Fundamental/Earnings/AI placeholder) |
| 의사결정 | `RecommendationEngine` (TOP-N + snapshot/decision_log), `HoldingCheckEngine` (PRE/POST + alert), `RecommendationResultService` (1/3/5/20일 후 성과 upsert) |
| 알림 / 리포트 | `ReportGenerator`, `TelegramNotifier` (`telegram_enabled=false` 기본 dry-run), `NotificationService`, 3개 dispatcher (Recommendation REPORT / HoldingCheck REPORT / HoldingRiskAlert) |
| Backend API | 13개 read-only GET (보고서 / 추천 latest·history·run / 보유 / 보유 점검 / 종목 상세 / 종목별 점검 metric / 시총 TOP / 시장 레짐 / 뉴스 / 잡 list·detail / 설정 마스킹) |
| Scheduler | APScheduler `BackgroundScheduler`, `run_job` 2-session 래퍼, 6개 잡 (수집 / 지표 / 추천 발송 / 장전 점검 / 장후 점검 / 성과 검증) — 각 잡 `data_status` / `notification_status` / `dry_run` / 카운트 키 노출 |
| Observability | 추천 / 보유점검 → `data_snapshots` + `decision_logs`, 잡 → `job_runs`, 알림 → `notification_logs`, dispatcher 호출은 `notification_logs.related_job_id` 자동 연결 |
| 통합 검증 자산 | `scripts/seed_mock_data.py` (멱등 + `--reset`), `INTEGRATION_RUNBOOK.md` (사전 준비 → 시드 → 6잡 수동 트리거 → 13 GET API → 로그 검증 → 회귀 게이트), `KIS_OPS_CHECKLIST.md` (실 KIS 운영 검증 9단계 체크리스트) |

세부 산출물 / 변경 이력은 [`PROJECT_STATUS.md`](./PROJECT_STATUS.md) 와
[`TASKS.md`](./TASKS.md), 결과 스냅샷은 [`PROJECT_STATUS.md` §2](./PROJECT_STATUS.md)
참조.

---

## 2. 검증 요약

### 2.1 단위 / 통합 회귀 게이트

```
296 passed in ~5.6s
```

- 외부 호출(KIS, Telegram, 주문)은 모두 mock transport / DRY_RUN 으로 격리
- v0.1 범위 위반 (실 주문 / FULL_AUTO / POST 라우터 등) 0건

### 2.2 mock seed 기반 통합 시나리오 (1회 수행)

`INTEGRATION_RUNBOOK.md` §1 ~ §5 를 throwaway SQLite 파일로 1회 수행:

- 6개 스케줄러 잡 모두 SUCCESS (의도된 PARTIAL 포함)
- 13개 GET API 모두 200, summary metric / 추천 이력 join / 잡 진단 정상
- `notification_logs` 7건 (REPORT 3 + ALERT 4), `job_runs` 6건 SUCCESS
- 자세한 결과는 [`PROJECT_STATUS.md` §2 "v0.1 통합 실행 결과 (1회 수행)"](./PROJECT_STATUS.md)

### 2.3 실 KIS 모의투자 서버 read-only 검증

`KIS_OPS_CHECKLIST.md` 절차로 실 KIS 모의투자 키 + 검증용 비공개 텔레그램
채팅방 기준 read-only 1회 통과:

- `.env` 안전 (gitignore / 미커밋 / ACL 좁히기) ✅
- `Settings()` 마스킹 + `/api/settings` 마스킹 ✅
- 실주문 / 자동매매 코드 부재 (정적 검색) ✅
- KIS 토큰 발급 + 005930 일봉 단건 ✅
- `collect_market_close_data` 시총 endpoint contract 픽스 (`eb8452a`,
  `FID_COND_SCR_DIV_CODE="20174"`) 검증 ✅ (3회 재실행 모두 SUCCESS)
- 일봉 endpoint signature 정상, 일부 paper 종목(`000660`, `373220`)은
  paper 서버의 시뮬레이션 데이터 / 캐시 미적재로 항시 5xx — 코드 결함이
  아닌 paper 서버 사이드 한계로 판정. v0.1 잡의 PARTIAL 격리 정상 동작
- 비밀값 평문 노출 0건, 발급 토큰 디스크 / 로그 비잔존
- 자세한 결과는 [`PROJECT_STATUS.md` §2 "실 KIS 운영 검증 결과"](./PROJECT_STATUS.md)
  와 그 아래 "후속 검증 — 시총 픽스 적용 후 (3회 시도)" 절

본격 운영 검증 (전 종목 일봉 SUCCESS) 은 KIS 실서버 (`KIS_USE_PAPER=false`)
또는 paper 서버의 종목별 시뮬레이션 데이터가 안정화된 시점에 다시 수행.

---

## 3. v0.1 제외 범위 재확인

다음 항목은 v0.1 범위 밖이며 본 릴리스에 코드 / 인터페이스 구현이 **포함되지
않는다**:

- 실거래 자동매매 / 실 KIS 주문 API 실행
- FULL_AUTO 모드, APPROVAL / SMALL_AUTO 모드
- 가상 증권사 서버, MockBroker / ReplayBroker / SimulationBroker
- Strategy 자동 튜닝, 전용 ML 모델 학습
- 백테스트 엔진 (walk-forward / 그리드 서치 등)
- React / Next.js PC 대시보드 프론트엔드
- 실 News / Supply / Fundamental / Earnings 파이프라인 (`DummyScoreProducer`
  룰베이스 placeholder 만 유지)

`BrokerInterface` (`app/broker/interfaces.py`) 는 ABC 정의 (`raise
NotImplementedError`) 로만 존재하며, 어느 구체 클래스도 구현하지 않는다.

---

## 4. 알려진 한계 / 후속 권장 (코드 변경 없는 사항)

| 항목 | 비고 |
|---|---|
| KIS 모의투자 서버 종목별 5xx | `000660`, `373220` 등 일부 종목은 paper 서버에서 일봉 endpoint 가 일관되게 5xx 반환. 코드 결함 아님 — KIS 측 데이터/캐시 한계. v0.1 잡의 PARTIAL 격리로 부분 실패가 전체 흐름을 막지 않음 |
| KIS 실서버 운영 검증 | `.env` 에 실서버 키 + `KIS_USE_PAPER=false` 로 1회 시범 운행 후 PROJECT_STATUS.md 에 결과 기록 권장. `KIS_OPS_CHECKLIST.md` 9단계 그대로 사용 가능 |
| seed `today` vs 잡 `today` 차이 | seed 는 UTC, 잡은 Asia/Seoul. UTC 15:00 이후 시드를 적재하면 잡이 새 일자로 fresh 행을 만들어 둘 다 공존. 데이터 손상 아님 (관찰 사항) |
| `update_recommendation_results` PENDING 다수 | mock seed 30봉 안에서 1/3/5/20일 후 검증 시 가장 오래된 run 만 다수 평가 가능. 운영 환경에서 daily_prices 누적되면 자연 해소 |

---

## 5. v0.2 후보 작업 (Backlog)

본 릴리스 시점에 결정된 v0.2 후보. 명시적 진입 요청 전까지 손대지 않는다.

### 5.1 분석 / 점수 보강

- 캔들 패턴 (망치형 / 장악형 / 도지 등) → `technical_score` 산식 보강
- ATR 변동성 컴포넌트 → `technical_score` / risk 산식 보강
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현재 `DummyScoreProducer`)
- AI / LLM 기반 점수 producer (현재 placeholder ai_score)

### 5.2 데이터 / 운영

- KIS 실서버 (`KIS_USE_PAPER=false`) 본격 운영 검증 1회 + 결과 기록
- KIS rate limit / 429 대응 정책 (현재 잡 PARTIAL 로 격리만 됨)
- News / 공시 수집 파이프라인 (`news_items` / disclosures)
- Market regime 산출 잡 (`market_regimes`)

### 5.3 의사결정 / 매매 (장기)

- Strategy 모듈 (장기 / 중기 / 단기 관리, SIGNAL / PAPER 모드)
- Backtest 엔진 (walk-forward 검증, 그리드 서치 튜닝)
- MockBroker / ReplayBroker / SimulationBroker, 가상 증권사 서버
- 전용 ML 모델 (Market Regime / Strategy Selection / Risk Prediction)
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 — `BrokerInterface` 구체 구현 +
  RiskEngine 게이트 + 휴먼 in the loop. **이 항목 진입 시 별도 보안 / 감사
  세션이 선행되어야 함**

### 5.4 프론트엔드 / DevOps

- React / Next.js PC 대시보드 프론트엔드 (현재 13 GET API 만 노출)
- 운영 배포 자동화 (Docker Compose 외, CI/CD, 비밀 매니저 통합)
- 모니터링 / 알람 (Prometheus / Grafana / Sentry 등)

### 5.5 문서 / 거버넌스

- v0.2 진입 시 새 `RELEASE_NOTES_v0.2.md` 작성
- 자동매매 진입 전 별도 보안 / 컴플라이언스 체크리스트 (실 주문은 별도
  사용자 승인 절차)

---

## 6. 운영 / 인수자 가이드

- 새 세션 / QA 인수자는 [`README.md`](./README.md) §7 "실행 순서 (권장)" 표를 그대로 따라간다.
- mock seed → 통합 시나리오 → pytest 회귀 → KIS 실 키 검증 순서.
- 실 KIS 키 운영 검증은 [`KIS_OPS_CHECKLIST.md`](./KIS_OPS_CHECKLIST.md) 9단계 체크리스트 사용.

---

## 7. 비밀 / 보안

- 본 릴리스 노트에 KIS 앱키 / 시크릿 / 계좌번호 / 텔레그램 봇 토큰 / chat_id
  평문이 일체 기록되지 않았다. 모든 비밀 참조는 마스킹 형태 (예:
  `5015****1-01`) 로만 표기.
- `.env` 파일은 gitignore + ACL 좁히기 적용 후 커밋 이력 0건.
- `LOG_TO_FILE=false` 가 검증 환경에서 강제되어 KIS 액세스 토큰이 디스크에
  남지 않음.
- 운영 환경에서 실 키 사용 시 `SECURITY.md` 와 `KIS_OPS_CHECKLIST.md` 의
  비밀 처리 항목을 그대로 따른다.

---

**이 문서로 v0.1 백엔드 마감을 선언한다.** 다음 cycle (v0.2) 진입은
사용자의 명시적 요청이 있을 때 시작한다.
