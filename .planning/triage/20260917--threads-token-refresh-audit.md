---
date: 2026-09-17
type: debug
status: resolved
---

# 쓰레드 토큰 자동 갱신 정상 확인 — launchd_error.log 190 에러는 stale 오진

## What

"토큰 만료 자동 갱신이 안 되나? 갱신 시간을 조정해야 하나?" 질문에 대한 진단.
결론: **자동 갱신 정상 작동 중. 조정 불필요.** 코드 변경 없음.

## Why

`scripts/threads/logs/launchd_error.log`에 `token_refresh: [validate] HTTP 400 /
code=190 type=OAuthException` 가 01:01·03:01·05:00·07:00·08:00에 반복 기록되어
있어 갱신 실패로 보였음. 조사 결과 이 로그 파일의 **mtime = 9월 14일 08:00** —
3일 전 정지 시점 이후 새 출력이 없음. 전체 35줄 내용도 모두 09-14 이전 것:

1. `ModuleNotFoundError: No module named 'pipeline'` (main_v3.py:11) 2건
2. `TypeError: 'int' object is not iterable` (pitch.py:595) traceback
3. 위 190 에러 5건

즉 **stale 로그**이며 현재 상태와 무관. 09-14 발행이 4건으로 급감한 것과 시기 일치.

## Files changed

- 없음 (진단 전용, 코드 변경 0)

## How (현재 동작 구조 — 조사 결과)

- launchd `~/Library/LaunchAgents/kr.aikorea24.threads-token-refresh.plist`:
  `daily` 인자 + `StartCalendarInterval Hour=0, Minute=30` (매일 00:30).
  `.venv/bin/python3 scripts/threads/token_refresh.py daily`. 로드됨.
- `RENEWAL_MARGIN_DAYS = 7` — 만료 D-7 이내면 갱신 (선제 갱신).
- `run_daily()` 분기: validate → NETWORK_ERROR면 보류 / TOKEN_VALID 아니면
  사용자 재인증 필요(return 2) / 잔여 >= 7일이면 보류(return 0) / 아니면
  `renew_token()`.
- Write-back 완비: `update_env_atomically(new_token)` — `.env`의
  `THREADS_ACCESS_TOKEN`만 원자 교체(tempfile + `os.replace`), 백업
  `.env.bak*`는 0600 권한 + git 미추적. 성공 검증 후에만 교체
  (`if vstate == TOKEN_VALID and update_env_atomically(new_tok)`).
  실패 시 `.env` 미변경 + `[refresh] 실패 상태=%s — .env 미변경` 로그.
- `validate_token(token, user_id)` — `GET
  https://{THREADS_API_HOST}/v1.0/{user_id}?fields=id,username`
  → 200=TOKEN_VALID, code 190/expired=TOKEN_EXPIRED,
  permission=PERMISSION_DENIED, 그 외 TOKEN_INVALID.
- 발행 직전 검증: `publisher.py:95` `validate_token(access_token, user_id)`.
- 토큰 소스 단일화: `publisher.py:42 load_env()` →
  `EnvConfig().get("THREADS_ACCESS_TOKEN")` (프로젝트 `.env`).

## Verification

- `scripts/threads/logs/token_refresh_error.log` 최근 15줄 전부
  `[daily] 만료 여유 충분(2026-10-17T08:34:45) — 갱신 보류` = 정상 판단.
- `launchctl list` 에 `kr.aikorea24.threads-token-refresh` 로드 확인.
- `launchd_error.log` mtime = 9월 14 08:00 (stale 확인).
- 참고: `launchd.log` mtime 9월 17 22:04, 6.9MB — 정상 갱신 중.

## 잔존 위험

- 실제 만료 D-7(2026-10-10) 시점의 자동 갱신 실행은 미확인 (만료 30일 잔여).
  확인 방법: 10-10경 `scripts/threads/logs/token_refresh_error.log`에
  갱신 실행 라인이 찍히는지 확인.
- 갱신 실패 시 `return 2` = 사용자 수동 재인증 필요. 자동 복구 불가 경로.
- launchd `ProgramArguments`에 `-u` 플래그가 없어 stdout 버퍼링 →
  `launchd.log`는 프로세스 종료 시점에야 기록됨. 실시간 확인은
  `scripts/threads/logs/YYYY-MM-DD.log` 사용.
