# Fireworks API 키 생성 + opencode 연동 완료

## 한 일
1. Fireworks API 키 생성 (계정 정지 해제 확인 포함)
2. opencode `fireworks` 프로바이더에 키 반영 + 실제 모델 호출 테스트

## 결과

### [검증됨] 계정 정지 해제 (카드 등록 효과)
- 근거: 이전 실패 오류(`account is suspended due to CREDIT_DEPLETED`) 상태에서 API 키 생성 재시도 → 성공. 키 ID `key_i4QdDSUCS`, 이름 `opencode`, 만료 2027-11-16

### [검증됨] Fireworks API 직접 호출
- 근거: `curl .../inference/v1/chat/completions` (model: glm-5p3-flash) → **HTTP 200**, `chatcmpl-7dab68f3...` 수신. 사용량 prompt 17 / completion 10 토큰

### [검증됨] opencode 통합 호출
- 근거: `opencode run -m "fireworks/accounts/fireworks/models/glm-5p3-flash" "Reply with exactly: PONG"` → 응답 `PONG`, exit 0

### [CONFIG] 설정 변경
- 파일: `~/.config/opencode/opencode.json`
- 변경: `providers.fireworks.settings.apiKey` 추가 (기존 `xiaomi-token-plan-sgp`와 동일 패턴 — settings.apiKey 직접 기입)
- 키 위치: 해당 파일 내 (600 권한 유지). state.md에는 키 값 기록 안 함
- 백업: `opencode.json.bak-fireworks-20261116-101829` (키 주입 전 + provider 추가 전 원본)
- 임시 키 파일(`.fw_key`)은 shred으로 삭제 완료

### [검증됨] 기존 설정 보존
- 근거: 수정 후 JSON 파싱 OK, provider 총 26개 (기존 25 + fireworks) 유지 확인

## 잔존 위험
1. **크레딧 잔액 미확인** — 카드 등록으로 정지는 풀렸으나 $50 AMD 크레딧은 아직 미발금(금요일 11/20 배포 예상). 현재 소액 잔액으로 테스트가 성공한 것이므로, 잔액 소진 시 동일 오류 재발 가능
2. **API 키는 평문 저장** — opencode.json 내 보관. 파일 권한 600 유지 중이나, 해당 파일을 커밋·동기화하는 경로가 있으면 노출 위험
3. **크레딧 충전 여부 미결정** — 사용자가 "충전 안 됨" 언급. AMD 코드 도착 전 소비분은 실제 과금 대상일 수 있음 (Fireworks 선불제, 잔액 0이면 사용 일시정지)

## 다음 행동
1. 11/20(금) AMD 이메일 확인 → 프로모 코드 Fireworks Billing에서 등록 (90일 이내)
2. 등록 후 잔액 $50 반영 확인 + `opencode models`에서 fireworks 모델 8개 사용 가능 상태 재확인
3. 잔액 상태는 `app.fireworks.ai/account/billing`에서 수시 확인
