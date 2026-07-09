---
date: 2026-07-09
type: fix
status: resolved
---

# DeepSeek 빈 응답 시 로그 없이 silent fallthrough

## What
`model_router.py`에서 DeepSeek API가 빈 응답(content=None 또는 빈 문자열)을 반환해도
아무 로그 없이 조용히 None 반환. write_thread에서 DeepSeek 실패 후 즉시 GPT-4o-mini로 fallback.
DeepSeek가 실패한 이유 추적 불가.

## Why
`resp.choices[0].message.content`가 None/empty일 때 아무 처리 없이 fallthrough.
`model_override='deepseek'`면 다음 모델(OpenAI) 블록 조건이 False여서 OpenAI로도 안 넘어감.

## Files changed
- `scripts/threads/v3/model_router.py` (DeepSeek empty response logging)
- `pipeline/threads/writer.py` (write_thread DeepSeek 1회 재시도 추가)

## How
1. model_router.py: 빈 응답 시 `[경고] DeepSeek 빈 응답 (content=None)` 로그 출력
2. writer.py: DeepSeek 1차 실패 시 1회 재시도 후 fallback

## Verification
`py_compile` 통과. 다음 dry-run에서 DeepSeek 빈 응답 시 로그 확인 가능.
