# AMD Fireworks 크레딧 신청 + opencode Fireworks 프로바이더 설정

## 한 일
1. AMD AI Developer Program → Cloud Credit 신청서(account.amd.com) 제출 (제품: Fireworks AI)
2. opencode 전역 설정(~/.config/opencode/opencode.json)에 fireworks 프로바이더 + 모델 8개 추가

## 결과

### [검증됨] AMD 크레딧 신청 제출
- 근거: 제출 후 URL 이동 확인 `account.amd.com/en/member/ai-dev-program/cloud-credits/thank-you.html` (title: Thank You)
- 입력값: Product Needed = Fireworks AI, Affiliation = Company, Profile 1 = https://aikorea24.kr, 사용계획 문구 기입
- AMD 응답: "3 business days 내 활성화 안내 이메일 발송" / 수요 과다 시 지연, 5영업일 초과 시 devcloudrequests@amd.com 문의

### [검증됨] opencode fireworks 프로바이더 등록
- 근거: `opencode models` 출력에 `fireworks/...` 8건 전부 표시 (exit 0)
- 수정 파일: `~/.config/opencode/opencode.json` — 기존 provider 25개 보존, fireworks 추가로 총 26개
- 백업: `opencode.json.bak-fireworks-<timestamp>` 생성 후 편집
- 구조: package `@opencode-ai/ai/providers/openai-compatible`, baseURL `https://api.fireworks.ai/inference/v1` (Fireworks 공식 OpenAI 호환 엔드포인트), credential은 `env: FIREWORKS_API_KEY`
- 모델 8개: kimi-k3p1-pro / deepseek-v4p1-flash-1017 / glm-5p3(-flash) / minimax-m3 / qwen3-coder-480b / kimi-k2p7-code / gpt-oss-120b

### [검증불가] 실제 API 호출
- 원인: Fireworks 계정이 `CREDIT_DEPLETED` 상태로 정지 → API 키 생성 차단 (대시보드에서 "Failed to create API Key: account is suspended due to CREDIT_DEPLETED" 실측)
- 복구 계획: Fireworks Billing(app.fireworks.ai/account/billing)에 결제 수단 등록 → 계정 활성화 → API 키 생성 → `FIREWORKS_API_KEY` 환경변수 설정 후 실제 호출 1회 테스트

## 잔존 위험
1. **Fireworks 계정 정지(CREDIT_DEPLETED)** — 결제 수단 등록 전에는 API 키 생성·사용 불가. AMD 크레딧 프로모 코드도 결제 수단 등록이 선행 조건으로 보임
2. **AMD 이메일 미수신** — 3영업일 대기, 미수신 시 devcloudrequests@amd.com 문의 필요
3. **환경변수 미설정** — `FIREWORKS_API_KEY`가 아직 없어 opencode에서 fireworks 모델 선택 시 인증 실패 예정 ([검증불가] 항목 1과 동일 원인)
4. **모델 컨텍스트 상한**은 Fireworks 모델 카탈로그 공개값 기준으로 기입 — 일부 모델(예: deepseek-v4-pro)은 미포함(공개값 부재)

## 다음 행동
1. 사용자: Fireworks Billing에 결제 수단 등록 (agent가 대신 진행 불가 — 결제 정보 직접 입력 필요)
2. AMD 이메일 도착 확인 → 프로모 코드 Fireworks에서 리디emption (90일 이내)
3. API 키 생성 후 `export FIREWORKS_API_KEY=...` → opencode에서 fireworks 모델 1개 선택 테스트
