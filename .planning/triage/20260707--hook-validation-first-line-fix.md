---
date: 2026-07-07
type: fix
status: resolved
---

# Hook Validation First Line Fix

## What
`validate_card_structure()`의 hook 검증이 첫 번째 카드 **전체**를 대상으로 문장 종결 개수를 세어 10개 초과 시 차단했음. 첫 카드에 3개 stanza(11문장)가 자연스럽게 들어가면 무조건 실패.

## Why
ThreadForge는 `role: "hook"` 별도 필드로 관리하지만, AI Korea는 평평한 배열 `["card1", "card2", ...]` 방식이라 `cards[0]` 전체를 hook으로 간주함. Threshold 10이 너무 낮았음.

## Files changed
- `pipeline/threads/validator.py` (라인 282-289)

## How
`hook = cards[0].strip()` → `hook_first_line = hook.split('\n')[0]`로 변경하여 첫 줄만 검사하도록 수정. ThreadForge의 `role: hook` 개념과 정렬.

## Verification
- 08:33 실행: hook 검증 통과 → 발행 성공 ✅
- 08:59 실행: hook 검증 통과 → 6카드 생성 성공 (DNS 장애로 발행 실패, 코드 문제 아님)