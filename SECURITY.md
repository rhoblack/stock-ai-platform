# SECURITY.md

## 1. 보안 목표

이 프로젝트는 주식 데이터, 계좌 관련 설정, API 키, 텔레그램 토큰을 다룰 수 있다.

v0.1은 실거래 주문을 하지 않지만, 초기부터 보안 원칙을 지켜야 한다.

## 2. 민감정보

민감정보로 간주하는 항목:

- 한국투자증권 app key
- 한국투자증권 app secret
- 한국투자증권 access token
- 한국투자증권 refresh token
- 계좌번호
- 계좌 상품 코드
- Telegram bot token
- Telegram chat ID
- OpenAI API key
- 로컬 LLM 인증 정보
- DB 비밀번호

## 3. 저장 원칙

- 민감정보는 코드에 하드코딩하지 않는다.
- `.env` 또는 안전한 설정 시스템을 사용한다.
- `.env.example`에는 placeholder만 둔다.
- 실제 `.env`는 Git에 커밋하지 않는다.
- 로그에 민감정보를 출력하지 않는다.
- 테스트 코드에 실제 키를 넣지 않는다.

## 4. Git 관리

`.gitignore`에 포함해야 할 항목:

```text
.env
.env.local
*.db
*.sqlite
logs/
__pycache__/
.pytest_cache/
node_modules/
dist/
build/
```

## 5. 로그 마스킹

로그 출력 시 다음 값은 마스킹한다.

```text
KIS_APP_KEY
KIS_APP_SECRET
KIS_ACCOUNT_NO
access_token
refresh_token
TELEGRAM_BOT_TOKEN
OPENAI_API_KEY
DATABASE_URL
```

예:

```text
KIS_APP_KEY=abcd********
```

## 6. v0.1 주문 보안 원칙

v0.1에서는 다음을 금지한다.

- 실제 주문 API 호출
- 실거래 자동매매
- FULL_AUTO 모드
- 실계좌 주문 테스트
- 주문 승인 API

미래 주문 관련 코드는 placeholder 또는 interface로만 존재해야 한다.

## 7. 향후 실거래 전 필수 조건

v1.0에서 소액 자동매매를 고려하기 전 반드시 필요:

- 승인 모드 우선
- 비상정지 버튼
- 일일 손실 제한
- 종목당 투자 한도
- 전략별 자금 한도
- 주문 로그 저장
- 실거래/모의투자 환경 분리
- API 키 암호화 저장
- 보안 리뷰
- 충분한 가상매매 검증

## 8. 텔레그램 보안

- 허용된 chat_id에만 발송
- 텔레그램 메시지에 계좌번호 노출 금지
- 평가금액 등 민감정보 표시 여부는 설정으로 제어
- 토큰은 환경변수에서 읽기

## 9. API 보안

대시보드 API는 로컬 개발 단계에서도 다음을 고려한다.

- CORS 제한
- 인증 추가 준비
- 민감정보 응답 금지
- 설정 API에서 secret 값 마스킹
- 에러 응답에 내부 stack trace 노출 금지

## 10. 보안 체크리스트

- [ ] `.env`가 Git에 커밋되지 않는가?
- [ ] `.env.example`만 커밋되는가?
- [ ] 로그에 토큰/키/계좌번호가 없는가?
- [ ] 테스트에 실제 키가 없는가?
- [ ] v0.1에 주문 실행 코드가 없는가?
- [ ] Telegram token이 코드에 없는가?
- [ ] DB URL이 문서에 실제 값으로 노출되지 않는가?
