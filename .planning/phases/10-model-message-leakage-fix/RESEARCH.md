# RESEARCH.md — Phase 10: Model Message Leakage Fix

## Problem Statement

AI models (MiMo, GPT-4o-mini, DeepSeek) occasionally return explanatory messages instead of just the requested content. These messages get included as cards in published Threads posts.

**Example**: Model returns "수정할 글자 단위 오류가 발견되지 않았습니다. 원본을 그대로 반환합니다." which becomes card 1/6.

## Root Cause

**Structural vulnerability**: Code trusts model to follow "return original if no changes" instruction, but models sometimes add explanatory preamble.

## Vulnerability Analysis

### Critical: `fix_cards()` (writer.py:383-439)

| Aspect | Details |
|--------|---------|
| Location | `pipeline/threads/writer.py:416-421` |
| Model | MiMo (character correction) |
| Prompt | "수정할 게 없으면 원본을 그대로 반환할 것" |
| Current Filter | None — only checks card count |
| Risk | 🔴 Critical |

**Attack vector**:
```
Model returns:
수정할 글자 단위 오류가 발견되지 않았습니다. 원본을 그대로 반환합니다.
---
(카드1)
---
(카드2)
...
```
→ 메시지가 card 0이 됨 → 발행됨

### Medium: `humanize_cards()` (writer.py:235-353)

| Aspect | Details |
|--------|---------|
| Location | `pipeline/threads/writer.py:330-335` |
| Model | MiMo (humanization) |
| Current Filter | `_strip_instruction_leak()` only |
| Risk | 🟡 Medium |

**Missing filters**:
- "수정할 내용이 없습니다"
- "원본을 그대로 반환합니다"
- "AI 티가 나는 패턴이 발견되지 않았습니다"

### Low: `write_thread()` (writer.py:465-677)

| Aspect | Details |
|--------|---------|
| Location | `pipeline/threads/writer.py:601-606` |
| Current Filter | `parse_cards()` + validation chain |
| Risk | 🟢 Low |

**Why LOW**: Multiple validation layers catch issues.

## Existing Defenses

| Filter | Location | Catches | Misses |
|--------|----------|---------|--------|
| `_strip_instruction_leak()` | writer.py:216-232 | Prompt labels | Model messages |
| `detect_prompt_leak()` | pitch.py:46-59 | System fragments | Model messages |
| `validate_final_output()` | validator.py:130-157 | Prompt leak, language | Model messages |

## Recommended Fix

### New Function: `_strip_model_explanatory(result: str) -> str`

**Purpose**: Remove model explanatory messages before splitting by `---`.

**Patterns to detect**:
```python
MODEL_MESSAGE_PATTERNS = [
    r'^수정할\s+글자\s+단위',
    r'^원본을\s+그대로\s+반환',
    r'^수정할\s+게\s+없',
    r'^오류가\s+발견되지',
    r'^변경\s+사항이?\s+없',
    r'^수정\s+불필요',
    r'^AI\s+티가?\s+나는',
    r'^교정할\s+부분이?\s+없',
]
```

### Fix Locations

1. **`fix_cards()` line 422** — Add `_strip_model_explanatory(result)` before `split('---')`
2. **`humanize_cards()` line 340** — Add `_strip_model_explanatory(result)` before `split('---')`

### Validation Enhancement

Add to `validate_final_output()`:
```python
# Model message detection
for card in cards:
    if _is_model_message(card):
        return False, f"Card {i}: 모델 메시지 탐지"
```

## Test Cases

1. Model returns message + `---` + original cards → message filtered
2. Model returns message without `---` → treated as single card → card count mismatch → original retained
3. Model returns only original cards → no change
4. Multiple messages → all filtered
5. Edge case: message contains `---` → split correctly

## Success Criteria

1. `fix_cards()` filters model messages before splitting
2. `humanize_cards()` filters model messages before splitting
3. `validate_final_output()` detects model messages in cards
4. All existing tests pass
5. New tests cover all message patterns
6. No false positives on legitimate content
