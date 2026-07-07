---
date: 2026-07-07
type: fix
status: resolved
---

# Hook 검증: 첫 카드 전체 → 첫 줄만 검사

## What
`validate_card_structure()`에서 hook(첫 번째 카드)을 검증할 때 카드 전체 텍스트를 대상으로 문장 종결 개수(>10)를 검사하여 "카드 경계 붙음 의심" 오류가 발생하던 문제를 수정. 첫 줄만 hook으로 간주하도록 변경.

## Why
- Phase 15에서 JSON 배열 파싱으로 전환 후, 첫 카드에 3개 stanza(11문장)가 자연스럽게 들어가게 됨
- 기존 로직: `hook = cards[0].strip()` → 전체 카드 텍스트에서 `~했음.` 등 종결어미 11개 검출 → threshold 10 초과 → 실패
- ThreadForge는 `role: "hook"` 필드로 첫 번째 객체만 hook으로 명시적 분리 → 같은 문제 없음

## Files changed
- `pipeline/threads/validator.py` (line 282-289)

## How
```python
# Before
hook = cards[0].strip()
enders_count = len(re.findall(r'(?:~임\.|~했음\.|~있음\.|~됨\.|~함\.|[.!?])', hook))

# After
hook = cards[0].strip()
hook_first_line = hook.split('\n')[0]
enders_count = len(re.findall(r'(?:~임\.|~했음\.|~있음\.|~됨\.|~함\.|[.!?])', hook_first_line))
```

## Verification
- 08:33 실행: `✅ 쓰레드: 6개 조각` → 발행 성공 (6개 카드 정상 발행)
- 08:59 실행: `✅ 쓰레드: 6개 조각` → 검증 통과 (DNS 장애로 발행만 실패, 코드 무관)