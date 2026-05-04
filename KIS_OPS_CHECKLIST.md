# KIS_OPS_CHECKLIST.md

운영 환경에서 v0.1 백엔드를 **실 한국투자증권(KIS) 키 + 실 텔레그램 봇**으로
한 번 검증하기 전에 따라야 할 체크리스트.

> v0.1은 read-only 분석 / 알림 시스템이다. 실거래 자동매매, 실 주문 API 실행은
> v0.1 범위 밖이며 본 체크리스트도 주문 검증을 포함하지 않는다.
> `BrokerInterface` 는 placeholder 로만 존재해야 한다.

---

## 0. 사전 합의

- [ ] 검증 대상 환경이 운영 / 스테이징 / 로컬 중 어디인지 명확히 합의
- [ ] 검증 시점이 한국 증시 **장중 / 장후 / 휴장**인지 기록 (장중에는 KIS rate
      limit 영향이 큼)
- [ ] 검증 시작 / 종료 예정 시각을 기록 (이후 PROJECT_STATUS.md §2 에 결과 기재)

---

## 1. 자격증명 / 비밀 관리

- [ ] `.env` 파일이 `.gitignore` 에 포함되어 있는지 확인 (`git check-ignore .env` 가 결과를 출력)
- [ ] `.env` 가 커밋 대상이 아닌지 확인 (`git status` 에 `.env` 가 untracked 인 채로 남아 있어야 정상)
- [ ] `.env` 에 다음 키 채움 — **앱 키 / 시크릿 / 계좌번호는 운영 담당자가 직접 입력하고
      Claude / Codex 에게는 보여주지 않는다**:
  - `KIS_APP_KEY=...`
  - `KIS_APP_SECRET=...`
  - `KIS_ACCOUNT_NO=...`
  - (선택) `KIS_BASE_URL=...` — 모의 vs 실서버 분기
  - `TELEGRAM_BOT_TOKEN=...` (선택, §5 단계까지는 false)
  - `TELEGRAM_CHAT_ID=...` (마스킹된 값을 운영자만 알 것)
- [ ] `.env.example` 만 git 에 커밋되어 있는지 확인 — 실제 값이 들어간 적이 없어야 함
- [ ] 로그 / 응답 본문에 KIS 키가 평문으로 노출되지 않는지 확인:
      `grep -RE "KIS_APP_(KEY|SECRET)" logs/` 결과 0 줄
- [ ] `/api/settings` 응답에서 `kis_app_key` / `kis_app_secret` / `account_number` /
      `telegram_bot_token` / `telegram_chat_id` 가 모두 마스킹된 형태로만 노출되는지 확인

---

## 2. 안전 플래그 (v0.1 강제 OFF)

다음 플래그가 모두 `false` 인 상태에서만 KIS 검증을 시작한다. 하나라도 `true`
이면 **즉시 중단**.

- [ ] `FEATURE_REAL_ORDER_EXECUTION=false`
- [ ] `FEATURE_FULL_AUTO=false`
- [ ] `FEATURE_AUTO_TRADING_APPROVAL=false` (있는 경우)
- [ ] 코드 검색: `grep -nE "BrokerInterface\(.*\)\.place_order|order_execute" app/` 결과 0 줄
- [ ] `app/broker/` 디렉터리가 placeholder 인터페이스만 포함하는지 (실 주문 구현체 없음) 확인

---

## 3. 1단계 — KIS read-only 키 인증만 검증

이 단계에서는 **시세 조회만** 한다. 시총 상위 / 일봉 / 현재가 — 모두 read 전용.

- [ ] `TELEGRAM_ENABLED=false` 유지
- [ ] `SCHEDULER_ENABLED=false` 유지 (수동 트리거만)
- [ ] 토큰 발급 1회 수동 호출 (Python REPL 또는 `INTEGRATION_RUNBOOK.md` §3.1 패턴
      변형) 후 `KisClient` 가 정상적으로 토큰을 캐시하는지 확인
- [ ] `collect_market_close_data` 잡을 mock provider 없이 1회 수동 실행 →
      `result_summary["market_cap_status"]` 가 `SUCCESS`, `daily_failure_count` 가 0 또는 의도된 값인지
- [ ] `market_cap_rankings` / `daily_prices` / `stocks` / `stock_universe_members` 4개 테이블에
      당일자 행이 정상 적재되었는지 확인
- [ ] `job_runs` 행에 `status="SUCCESS"`, `error_message` null, `result_summary` 정상 기록
- [ ] **이 단계에서 텔레그램은 절대 발송되지 않아야 한다** — `notification_logs` 에
      `status="DRY_RUN"` 또는 `"DISABLED"` 만 있어야 함

---

## 4. 2단계 — 분석 / 추천 / 보유점검 read-only 검증

KIS 데이터를 시드 / 1단계 결과 기준으로 사용해 v0.1 엔진들을 1회 동작시킨다.

- [ ] `calculate_technical_indicators` 잡 1회 수동 실행 → 5/20/60/120 MA, RSI14,
      MACD, volume_ratio_20d, breakout, ma_alignment 가 의미 있는 값으로 채워졌는지 spot-check
- [ ] `RecommendationEngine` 1회 호출 → `recommendation_runs` / `recommendations` /
      `data_snapshots` / `decision_logs` 4개 테이블 정합성 확인 (1 run, N recs, 각 rec 마다
      snapshot_id 와 decision_log 1건)
- [ ] 활성 보유 종목이 있다면 `run_pre_market_holding_check` 1회 호출 →
      `holding_checks` 행 + alert / decision / risk_level 정합성 확인
- [ ] `update_recommendation_results` 잡 1회 호출 → `recommendation_results` 가
      `(recommendation_id, days_after)` 별로 멱등 upsert 되었는지 확인 (재실행해도 row 수 불변)

---

## 5. 3단계 — 텔레그램 dry-run → 실 발송 1회

- [ ] `TELEGRAM_ENABLED=false` 인 상태에서 `send_recommendation_report` 1회 →
      `notification_logs.status="DRY_RUN"`, `sent_at IS NULL` 확인
- [ ] 봇 토큰 / chat_id 가 채워진 별도 `.env.local` (또는 동등) 환경에서
      `TELEGRAM_ENABLED=true` 로 1회만 발송:
  - [ ] 발송 채널이 **검증용 비공개 채팅방 / 본인 chat_id** 인지 재확인 (운영 단톡방에 잘못 보내지 않도록)
  - [ ] `notification_logs.status="SUCCESS"`, `sent_at` 기록, `recommendation_runs.telegram_sent=True` 갱신 확인
  - [ ] 메시지 본문에 KIS 토큰 / 계좌번호 / 봇 토큰이 포함되지 않았는지 육안 확인
- [ ] 검증 완료 직후 `TELEGRAM_ENABLED=false` 로 되돌리고 다시 발송이 일어나지 않는지 확인

---

## 6. 4단계 — 스케줄러 ON 24시간 시범 운행

- [ ] `SCHEDULER_ENABLED=true` 로 켜고 1일 (또는 1주기) 동안 cron 트리거가 의도한 시간에
      실행되는지 `job_runs` 로 확인:
  - 18:00 `collect_market_close_data` (장후)
  - 18:30 `calculate_technical_indicators`
  - 06:00 `send_recommendation_report`
  - 08:30 `run_pre_market_holding_check`
  - 16:30 `run_post_market_holding_check`
  - 17:00 `update_recommendation_results`
- [ ] APScheduler `misfire_grace_time` 안에서 빠진 실행이 자동 보강되는지 확인
- [ ] 실패 / PARTIAL 잡이 발생하면 `job_runs.error_message` 와 `notification_logs` 로 원인 추적
- [ ] 24시간 후 정지 시 `notification_logs` / `decision_logs` 가 비정상 폭증하지 않는지 행 수 확인

---

## 7. 회귀 / 기록

- [ ] `.\.venv\bin\python.exe -m pytest -q` → **296 passed** 유지 (시범 운행 후에도 회귀 0건)
- [ ] 검증 결과 (잡별 SUCCESS/PARTIAL 분포, notification_logs 건수, 발견된 이슈)를
      `PROJECT_STATUS.md` §2 "v0.1 통합 실행 결과" 아래 새 하위 절로 기록
- [ ] 실 키 발견 / 의심 시 즉시 키 회전 후 `.env` 갱신, git history 에 노출되지 않았는지 재확인

---

## 8. 즉시 중단(Abort) 조건

다음 중 하나라도 발생하면 **검증을 즉시 중단**하고 운영자에게 보고한다.

- KIS 응답에 비정상 주문 / 체결 흔적이 보임 (v0.1은 절대 주문하지 않으므로 이상 신호)
- `notification_logs` 에 운영 단톡방 / 미합의 채널로 발송된 로그가 보임
- `job_runs.error_message` 에 KIS 키 / 토큰이 평문으로 포함됨
- `BrokerInterface` 호출 흔적이 로그에 보임 (placeholder 외 실제 구현체 없음 검증)
- 회귀 테스트 296 passed 가 깨짐

---

## 9. 본 체크리스트가 다루지 않는 범위 (v0.1 외)

다음은 v0.2 이후로 미뤄둔 항목이라 이번 검증 범위에 포함하지 않는다.

- 캔들 패턴 / ATR 변동성 컴포넌트 → `technical_score` 산식 보강
- 실 News / Supply / Fundamental / Earnings 파이프라인 (현 v0.1은 `DummyScoreProducer` placeholder)
- Strategy 모듈 / Backtest 엔진 / MockBroker / SimulationBroker
- APPROVAL / SMALL_AUTO / FULL_AUTO 모드 (실 주문)
- React / Next.js 대시보드 프론트엔드
