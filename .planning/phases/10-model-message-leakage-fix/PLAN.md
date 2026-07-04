# PLAN.md — Phase 10: Model Message Leakage Fix

## Goal

Eliminate model explanatory messages from published Threads posts by adding robust filtering before card splitting.

**Mode:** ad-hoc
**Depends on:** Phase 8 (Validation Gap Closure)
**Requirements:** REQ-01, REQ-02, REQ-03, REQ-04, REQ-05

## Success Criteria

1. `fix_cards()` filters model messages before splitting by `---`
2. `humanize_cards()` filters model messages before splitting by `---`
3. `validate_final_output()` detects model messages in cards
4. All existing 227 tests pass
5. New tests cover all message patterns
6. No false positives on legitimate content

## Tasks

### Task 1: Create Model Message Detection Utility

**File:** `pipeline/threads/writer.py`

**Actions:**
1. Add `MODEL_MESSAGE_PATTERNS` list (lines ~200):
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

2. Add `_strip_model_explanatory(result: str) -> str` function:
```python
def _strip_model_explanatory(result: str) -> str:
    """Remove model explanatory messages from response."""
    lines = result.split('\n')
    filtered = []
    for line in lines:
        is_message = False
        for pattern in MODEL_MESSAGE_PATTERNS:
            if re.match(pattern, line.strip()):
                is_message = True
                break
        if not is_message:
            filtered.append(line)
    return '\n'.join(filtered)
```

**Estimate:** 10 min
**Files:** 1

---

### Task 2: Apply Filter to `fix_cards()`

**File:** `pipeline/threads/writer.py`

**Actions:**
1. Locate `fix_cards()` function (line 383)
2. Find model result parsing (line 422-423)
3. Add filter before splitting:
```python
if result:
    result = _strip_model_explanatory(result)  # ADD THIS
    fixed = [c.strip() for c in result.split('---') if c.strip()]
```

**Estimate:** 5 min
**Files:** 1

---

### Task 3: Apply Filter to `humanize_cards()`

**File:** `pipeline/threads/writer.py`

**Actions:**
1. Locate `humanize_cards()` function (line 235)
2. Find model result parsing (line 340-341)
3. Add filter before splitting:
```python
result = _strip_instruction_leak(result)
result = _strip_model_explanatory(result)  # ADD THIS
fixed = [c.strip() for c in result.split('---') if c.strip()]
```

**Estimate:** 5 min
**Files:** 1

---

### Task 4: Add Validation Detection

**File:** `pipeline/threads/validator.py`

**Actions:**
1. Import `_strip_model_explanatory` from writer (or move patterns to validator)
2. Add to `validate_final_output()` (line 130):
```python
def validate_final_output(cards: list[str]) -> tuple[bool, str]:
    for i, card in enumerate(cards, 1):
        # Existing checks...
        
        # Model message detection
        for pattern in MODEL_MESSAGE_PATTERNS:
            if re.match(pattern, card.strip()):
                return False, f"Card {i}: 모델 메시지 탐지"
    
    return True, "OK"
```

**Estimate:** 10 min
**Files:** 1

---

### Task 5: Write Tests

**File:** `tests/test_writer.py`

**Actions:**
1. Add test class `TestStripModelExplanatory`:
```python
class TestStripModelExplanatory:
    def test_message_with_separator(self):
        result = "수정할 글자 단위 오류가 발견되지 않았습니다.\n---\n카드1\n---\n카드2"
        filtered = _strip_model_explanatory(result)
        assert "수정할" not in filtered
        assert "카드1" in filtered
    
    def test_message_without_separator(self):
        result = "원본을 그대로 반환합니다."
        filtered = _strip_model_explanatory(result)
        assert len(filtered) == 0
    
    def test_no_message(self):
        result = "카드1\n---\n카드2"
        filtered = _strip_model_explanatory(result)
        assert filtered == result
    
    def test_multiple_messages(self):
        result = "수정할 게 없습니다.\n---\n원본을 그대로 반환합니다.\n---\n카드1"
        filtered = _strip_model_explanatory(result)
        assert "수정할" not in filtered
        assert "원본을" not in filtered
```

2. Add test cases for `fix_cards()` and `humanize_cards()` with model messages

**Estimate:** 15 min
**Files:** 1

---

### Task 6: Run Tests and Verify

**Actions:**
1. Run full test suite: `.venv/bin/python3 -m pytest tests/ -v --tb=short`
2. Verify all 227 existing tests pass
3. Verify new tests pass
4. Run syntax check on modified files

**Estimate:** 5 min
**Files:** 0

---

## Verification

### Success Criteria Check

| Criteria | Method | Expected |
|----------|--------|----------|
| fix_cards filters messages | Unit test | Pass |
| humanize_cards filters messages | Unit test | Pass |
| validate_final_output detects messages | Unit test | Pass |
| All existing tests pass | pytest | 227/227 |
| No false positives | Manual review | None |

### Test Commands

```bash
# Unit tests
.venv/bin/python3 -m pytest tests/test_writer.py -v

# Full suite
.venv/bin/python3 -m pytest tests/ -v

# Syntax check
.venv/bin/python3 -m py_compile pipeline/threads/writer.py
.venv/bin/python3 -m py_compile pipeline/threads/validator.py
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positive on legitimate content | High | Careful pattern design, extensive testing |
| Missed message patterns | Medium | Comprehensive pattern list, easy to extend |
| Breaking existing tests | Low | Run full suite, incremental changes |

## Estimated Duration

- Task 1: 10 min
- Task 2: 5 min
- Task 3: 5 min
- Task 4: 10 min
- Task 5: 15 min
- Task 6: 5 min

**Total: 50 min**

## Dependencies

- Phase 8 (Validation Gap Closure) — completed
- No external dependencies
