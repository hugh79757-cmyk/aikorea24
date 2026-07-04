# PLAN.md — Phase 11: Defense Mechanism Hardening

## Goal

Refine and harden the defense mechanisms against prompt injection and foreign character leakage to improve maintainability, consistency, and comprehensiveness.

**Mode:** ad-hoc
**Depends on:** Phase 10-1 (Card Structure Validation)
**Requirements:** REQ-01–REQ-08

## Success Criteria

1. Pattern definitions consolidated: writer imports from validator
2. `validate_final_output()` uses `ALL_MESSAGE_PATTERNS`
3. Korean ratio threshold in `validate_final_output()` is ≥30%
4. Link card check in `validate_model_message()` uses `.strip()`
5. Dead import `validate_no_foreign_language` removed from writer
6. New integration test `test_write_thread_validation.py` added and passing
7. All existing 262 tests pass
8. Unicode NFKC normalization applied before foreign language detection
9. Foreign language patterns (`CHINESE_PATTERN`, `JAPANESE_PATTERN`) consolidated to validator.py
10. LLM system prompt strengthened against foreign language output
11. Documentation (`docs/TECH.md`) updated

## Tasks

### Task 1: Consolidate Model Message Patterns

**Files:**
- `pipeline/threads/writer.py`

**Actions:**

1. Remove the local definition of `MODEL_MESSAGE_PATTERNS` (lines 216-225).
2. Add import:
   ```python
   from pipeline.threads.validator import MODEL_MESSAGE_PATTERNS
   ```
   (place near other imports from validator)
3. Verify `_strip_model_explanatory()` uses `MODEL_MESSAGE_PATTERNS` directly (no code change needed).

**Estimate:** 5 min
**Files:** 1

---

### Task 2: Unify Model Message Patterns in Final Output

**File:** `pipeline/threads/validator.py`

**Actions:**

At line 199 in `validate_final_output()`, replace:
```python
for pattern in MODEL_MESSAGE_PATTERNS:
```
with:
```python
for pattern in ALL_MESSAGE_PATTERNS:
```

**Estimate:** 2 min
**Files:** 1

---

### Task 3: Align Korean Ratio Threshold

**File:** `pipeline/threads/validator.py`

**Actions:**

In `validate_final_output()` lines 193-196:
```python
korean = len(_KOREAN_PATTERN.findall(card))
total = len(card.strip())
if total > 10 and korean < total * 0.1:
    return False, ...
```
Change multiplier `0.1` → `0.3`.

Alternatively, if you choose removal, delete the entire conditional block (lines 192-196) because cards already pass the stricter check in `validate_model_message()`.

**Recommendation**: Raise to 0.3 for defense-in-depth.

**Estimate:** 2 min
**Files:** 1

---

### Task 4: Fix Link Card Check

**File:** `pipeline/threads/validator.py`

**Actions:**

In `validate_model_message()` at line 210, change:
```python
if card.startswith('🔗'):
```
to:
```python
if card.strip().startswith('🔗'):
```

**Estimate:** 1 min
**Files:** 1

---

### Task 5: Remove Dead Import in Writer

**File:** `pipeline/threads/writer.py`

**Actions:**

At line 10, remove `validate_no_foreign_language` from import list:
```python
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords, validate_final_output, validate_model_message, validate_card_structure
```
(do not import `validate_no_foreign_language`)

**Estimate:** 1 min
**Files:** 1

---

### Task 6: Add Integration Tests

**New File:** `tests/test_write_thread_validation.py`

**Actions:**

Create comprehensive test cases covering:
- Retry when first response contains Chinese characters
- Retry when first response contains polite ADDITIONAL pattern (e.g., "네")
- Retry when first response contains prompt label leak (e.g., "상식(A):")
- Success on second attempt after cleaning
- Successful write without issues
- Ensure that link cards with leading/trailing whitespace are handled correctly

Use `unittest.mock.patch` to replace `chat_completion` with controlled responses.

**Skeleton:**

```python
import pytest
from unittest.mock import patch
from pipeline.threads.writer import write_thread

@pytest.fixture
def sample_pitch():
    return {...}  # minimal valid pitch data

def test_chinese_char_retry(sample_pitch):
    # First response: card with Chinese char, second: valid
    with patch('pipeline.threads.writer.chat_completion') as mock_chat:
        mock_chat.side_effect = [make_response(chinese_card), make_response(valid_cards)]
        cards = write_thread(...)
        assert cards is not None
        assert mock_chat.call_count == 2

# similar for other scenarios
```

**Estimate:** 20 min
**Files:** 1 new

---

### Task 7: Update Documentation

**Files:**
- `docs/TECH.md` — Section on validation
- `docs/VALIDATION_RESEARCH.md` (if exists) — note changes

**Actions:**

1. In `docs/TECH.md`, update the validation chain description to reflect:
   - Unified pattern set (ALL_MESSAGE_PATTERNS)
   - Korean ratio thresholds harmonized to ≥30%
   - Link card strip fix
2. Remove mention of `validate_no_foreign_language` as active component.
3. Note that `_strip_model_explanatory()` uses pattern from validator.

**Estimate:** 10 min
**Files:** 2

---

### Task 8: Full Test Suite & Verification

**Actions:**

1. Run full test suite: `.venv/bin/python3 -m pytest tests/ -v`
2. Ensure all 262+ tests pass, including the new integration tests.
3. Run dry-run of threads pipeline: `scripts/threads/main_v3.py --dry-run` to ensure no runtime regressions.

**Estimate:** 10 min (excluding test run time ~25s)

---

### Task 9: Commit & Push

**Actions:**

1. Stage changes: `git add .`
2. Commit with message: `feat(11): defense hardening — pattern consolidation, threshold alignment, integration tests`
3. Push to origin/main: `git push origin main`

**Files:** multiple

### Task 9: Unicode Normalization for Foreign Language Defense

**Files:**
- `pipeline/threads/validator.py`
- `tests/test_validator.py`

**Actions:**

1. Add `import unicodedata` at top of `validator.py`.
2. In `validate_final_output()`, normalize card text before inspection:
   ```python
   card_normalized = unicodedata.normalize('NFKC', card)
   ```
   Apply to Chinese/Japanese detection and Korean ratio checks.
3. Add test case to `TestValidateFinalOutput`:
   - Fullwidth characters (e.g., `＿`, `！`, `Ａ`) → normalized → Korean ratio correct
   - Normalization before Chinese detection

**Estimate:** 10 min
**Files:** 2

---

### Task 10: Consolidate Foreign Language Patterns

**Files:**
- `pipeline/threads/validator.py`
- `pipeline/threads/pitch.py`

**Actions:**

1. Export `_CHINESE_PATTERN` and `_JAPANESE_PATTERN` from `validator.py` (remove underscore prefix for public use):
   ```python
   CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')
   JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')
   ```
2. In `pitch.py`, remove local `_CHINESE_PATTERN` definition (line 69) and import from validator:
   ```python
   from pipeline.threads.validator import CHINESE_PATTERN
   ```
3. Update `validate_korean_output()` to use imported `CHINESE_PATTERN`.

**Estimate:** 10 min
**Files:** 2

---

### Task 11: Strengthen LLM Prompt Against Foreign Language

**File:** `pipeline/threads/writer.py`

**Actions:**

In `build_system_prompt_D()`, enhance the Chinese/foreign language prohibition (line 78):

Current:
```
- 중국어(한자) 사용 절대 금지. 한자는 한국어로 번역하라. 예: 新加坡금융관리국
```

Replace with:
```
- 중국어(한자) 사용 절대 금지. 한자 1글자라도 출력 시 발행이 차단된다. 반드시 한국어로 번역하라. 예: 新加坡금융관리국(X) → 싱가포르금융관리국(O)
- 일본어(히라가나·가타카나) 사용 절대 금지. 모든 외국어는 한국어로만 작성하라.
- 고유명사는 영어 원문 유지. 중국어·일본어·한자·특수 유니코드 문자 절대 금지.
```

**Estimate:** 5 min
**Files:** 1

---

## Verification Checklist

Before marking phase complete, ensure:
- [ ] All code changes applied exactly as specified
- [ ] No existing tests fail
- [ ] New tests exist and pass
- [ ] Documentation updated
- [ ] `grep validate_no_foreign_language pipeline/threads/writer.py` returns no matches
- [ ] `grep MODEL_MESSAGE_PATTERNS pipeline/threads/writer.py` shows only import, no local definition
- [ ] `grep ALL_MESSAGE_PATTERNS pipeline/threads/validator.py` confirms usage in final_output
- [ ] `grep unicodedata pipeline/threads/validator.py` confirms NFKC normalization
- [ ] `grep "from pipeline.threads.validator import" pipeline/threads/pitch.py` confirms CHINESE_PATTERN import
- [ ] `grep "중국어(한자) 사용 절대 금지. 한자 1글자라도" pipeline/threads/writer.py` confirms strengthened prompt
- [ ] `git diff` shows expected changes
