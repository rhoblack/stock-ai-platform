# RELEASE_NOTES_v0.4

## v0.4 Analyst & Theme Intelligence 마감

v0.4는 증권사 애널리스트 리포트와 테마/시그널 데이터를 추천 판단의 보조 근거로
저장, 계산, 표시하는 사이클이다. v0.1 이후 유지해 온 read-only 원칙은 그대로
유지했다. 자동매매, 실주문, POST 트리거, 실제 외부 수집은 포함하지 않는다.

- 최종 태그 예정: `v0.4-final`
- 인수 일자: 2026-05-05 (Asia/Seoul)
- 직전 누적 태그: `v0.4-frontend-reports` (Phase D)

## Phase A — DB 모델 6종 + Repository

- `AnalystReport`
- `ReportTheme`
- `ThemeStockMapping`
- `ReportSignalEvent`
- `ReportConsensusSnapshot`
- `ReportScoreLog`

6개 ORM 모델과 Repository를 추가했다. 기업/산업/테마/원자재/매크로/전략 리포트를
단일 `analyst_reports` 테이블에서 `report_type`으로 구분하고, 테마와 종목 매핑,
변화 시그널 이벤트, 일별 컨센서스, 점수 계산 이력을 별도 테이블로 보관한다.

## Phase B — CSV Import Pipeline + Consensus Snapshot Job

- `scripts/import_analyst_reports.py` CLI 추가
- 기본 dry-run, `--commit` 명시 시 DB 적재
- 35 컬럼 CSV를 report/theme/mapping/signal event로 분해
- forbidden body column 검증으로 원문 전문 저장 차단
- `update_report_consensus_snapshots` scheduler job 추가
- COMPANY 리포트 기반 일별 컨센서스 스냅샷 upsert

CSV import와 컨센서스 갱신은 모두 로컬/운영자 주도 흐름이다. 자동 크롤링이나
실시간 외부 수집은 없다.

## Phase C — report_score + theme_signal_score

- `app/analysis/report_score_calculator.py` 추가
- `report_score`: 목표가 upside, rating 평균, recency bonus 기반
- `theme_signal_score`: 테마 매핑 방향, 시그널 이벤트 방향, risk warning 기반
- 두 점수 모두 RecommendationEngine에 보조 점수로만 통합
- 기존 ScoringEngine 본 weight 변경 없음
- 보조 가산은 각 점수별 ±5점 cap
- `report_score_logs`와 `decision_logs.rule_result_json["report_evidence"]`에 근거 저장

## Phase D — Dashboard 표시

- `GET /api/stocks/{symbol}.analyst_reports` 응답 추가
- read-only `GET /api/stocks/{symbol}/reports` 추가
- StockDetail:
  - Analyst Consensus 카드
  - Recent Reports 카드
  - Related Themes 카드
  - Signal Events 카드
- Recommendations:
  - `report_score` 컬럼
  - `theme_signal_score` 컬럼
  - `report_evidence` 요약
  - null fallback `—`

`source_file_path`는 API schema, 프런트 타입, 화면, e2e fixture에 포함하지 않는다.

## 테스트 결과

Phase D 인수 시점 + Phase E 마감 직전 재확인 모두 동일한 4 게이트 baseline:

- backend pytest: **382 passed**
- frontend vitest: **60 passed**
- frontend build: **통과** (`tsc --noEmit && vite build`)
- Playwright e2e: **9 passed** (chromium + page.route mock)

Phase E 재확인 일자: 2026-05-05 (Asia/Seoul). Phase D → Phase E 사이 코드/테스트
변경 0건이라 회귀 없이 동일 게이트 그대로 통과.

테스트는 모두 mock/fixture 기반이다. KIS API 실제 호출, 텔레그램 실제 발송, 주문
실행은 없다.

## 저작권·보안 정책

- 리포트 원문 전문 저장 금지
- PDF BLOB 저장 금지
- 리포트 자동 크롤링 없음
- `source_file_path` API/프론트/e2e 미노출
- 운영자가 직접 작성한 짧은 `summary`만 저장
- 비밀값, 계좌번호, 토큰, 원본 파일 경로는 외부 응답에 노출하지 않음

## 제외 범위

- 자동매매
- 실주문
- POST 트리거
- 실 News/Fundamental 파이프라인
- 실시간 리포트/뉴스 크롤링
- HoldingCheckEngine 산식 변경
- ScoringEngine 본 weight 변경
- 리포트 원문 전문 저장/노출

## 알려진 한계

- CSV import는 stdlib `csv` 기반이다. Excel 직접 import는 아직 없다.
- 컨센서스는 수동 import된 리포트 데이터에 의존한다.
- `report_score`와 `theme_signal_score`는 추천 전용 보조 점수다. 보유점검에는 아직 통합하지 않았다.
- 리포트 요약 품질은 운영자가 입력한 CSV 품질에 의존한다.
- 인증/권한/사용자별 관심종목 기능은 없다.
- 운영 DB 마이그레이션은 별도 절차로 적용해야 한다.

## v0.5 후보

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
