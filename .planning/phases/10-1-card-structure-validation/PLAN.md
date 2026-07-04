# PLAN.md — Phase 10-1: Card Structure Validation

## Goal

Add structural validation to catch model messages that slip through regex-based filtering, ensuring zero model messages and malformed cards in published posts.

**Mode:** ad-hoc
**Depends on:** Phase 10 (Model Message Leakage Fix)
**Requirements:** REQ-01 through REQ-10

## Success Criteria

1. Cards must be at least 20 characters (link cards exempt)
2. Cards must contain at least 30% Korean characters (link cards exempt)
3. Cards must end with complete sentences
4. Cards must have sufficient content density (50% non-whitespace)
5. No duplicate cards allowed
6. Hook card must be 30-100 characters
7. Body cards must be 50-500 characters
8. Model messages must be detected and rejected
9. All existing 241 tests pass
10. False positive rate < 1%

## Tasks

### Task 1: Add Enhanced Model Message Patterns

**File:** `pipeline/threads/validator.py`

**Actions:**
1. Add `ADDITIONAL_MESSAGE_PATTERNS` list after existing `MODEL_MESSAGE_PATTERNS`:
```python
ADDITIONAL_MESSAGE_PATTERNS = [
    # Polite forms
    r'^수정이?\s+필요\s+없',
    r'^교정할\s+부분이?\s+없',
    r'^변경\s+사항이?\s+없',
    
    # Short responses
    r'^네[,.]?\s*$',
    r'^확인[됨했]*[,.]?\s*$',
    r'^완료[됨했]*[,.]?\s*$',
    r'^통과[됨했]*[,.]?\s*$',
    
    # English messages
    r'^No\s+changes',
    r'^No\s+errors',
    r'^Returning\s+original',
    r'^Original\s+content',
    
    # Question responses
    r'^질문에\s+답변',
    r'^답변[입니다]*\s*:',
    
    # Explanation prefixes
    r'^이\s+텍스트는',
    r'^이\s+내용은',
    r'^이\s+카드는',
    r'^여기서는',
    
    # Meta commentary
    r'^참고[로事项]*:',
    r'^주의[사항]*:',
    r'^알림:',
]
```

2. Combine with existing patterns:
```python
ALL_MESSAGE_PATTERNS = MODEL_MESSAGE_PATTERNS + ADDITIONAL_MESSAGE_PATTERNS
```

**Estimate:** 10 min
**Files:** 1

---

### Task 2: Add `validate_model_message()` Function

**File:** `pipeline/threads/validator.py`

**Actions:**
1. Add new function after `validate_final_output()`:
```python
def validate_model_message(card: str) -> bool:
    """Check if card is a model message (returns False if message detected)."""
    card = card.strip()
    
    # Skip link cards
    if card.startswith('🔗'):
        return True
    
    # Check against all patterns
    for pattern in ALL_MESSAGE_PATTERNS:
        if re.match(pattern, card):
            return False
    
    # Structural checks
    # 1. Minimum length
    if len(card) < 20:
        return False
    
    # 2. Korean content requirement
    korean_chars = len(re.findall(r'[가-힣]', card))
    if len(card) > 0 and korean_chars / len(card) < 0.3:
        return False
    
    return True
```

**Estimate:** 15 min
**Files:** 1

---

### Task 3: Add `validate_card_structure()` Function

**File:** `pipeline/threads/validator.py`

**Actions:**
1. Add new function:
```python
def validate_card_structure(cards: list[str]) -> tuple[bool, str]:
    """Validate structural integrity of all cards."""
    if not cards:
        return False, "카드 없음"
    
    # 1. Check for duplicates
    seen = set()
    for i, card in enumerate(cards, 1):
        normalized = card.strip().lower()
        if normalized in seen:
            return False, f"Card {i}: 중복 카드"
        seen.add(normalized)
    
    # 2. Check each card
    for i, card in enumerate(cards, 1):
        card = card.strip()
        
        # Skip link cards for most checks
        if card.startswith('🔗'):
            continue
        
        # 3. Minimum length
        if len(card) < 20:
            return False, f"Card {i}: 너무 짧음 ({len(card)}자)"
        
        # 4. Korean content
        korean_chars = len(re.findall(r'[가-힣]', card))
        if len(card) > 0 and korean_chars / len(card) < 0.3:
            return False, f"Card {i}: 한글 비율 부족 ({korean_chars}/{len(card)})"
        
        # 5. Content density
        content_chars = len(re.findall(r'\S', card))
        if len(card) > 0 and content_chars / len(card) < 0.5:
            return False, f"Card {i}: 공백 과다"
        
        # 6. Sentence completeness (body cards only)
        if i > 1:  # Skip hook
            sentence_enders = ['.', '!', '?', '음', '임', '됨', '했음', '있음', '없음']
            if not any(card.endswith(ender) for ender in sentence_enders):
                if not card.endswith('...') and not card.endswith('…'):
                    return False, f"Card {i}: 문장 미완성"
    
    # 7. Hook length (first card)
    hook = cards[0].strip()
    if not hook.startswith('🔗'):
        if len(hook) < 30 or len(hook) > 100:
            return False, f"Hook 길이 비정상 ({len(hook)}자)"
    
    # 8. Body card length
    for i, card in enumerate(cards[2:], 3):  # Skip hook and link
        card = card.strip()
        if card.startswith('🔗'):
            continue
        if len(card) < 50 or len(card) > 500:
            return False, f"Card {i}: 길이 비정상 ({len(card)}자)"
    
    return True, "OK"
```

**Estimate:** 20 min
**Files:** 1

---

### Task 4: Integrate into Validation Chain

**File:** `pipeline/threads/writer.py`

**Actions:**
1. Import new validation functions:
```python
from pipeline.threads.validator import (
    validate_cards, validate_year, validate_keywords,
    validate_no_foreign_language, validate_final_output,
    validate_model_message, validate_card_structure
)
```

2. Update `write_thread()` validation chain (line ~623):
```python
# Existing validation
if validate_cards(cards, pitch, format_choice) and \
   validate_year(cards, article_body_text) and \
   validate_keywords(cards, article_body_text):
    
    # New structural validation
    structure_ok, structure_reason = validate_card_structure(cards)
    if not structure_ok:
        _log(f'⚠️ 카드 구조 검증 실패: {structure_reason} → 재시도')
        continue
    
    # Model message validation
    for i, card in enumerate(cards, 1):
        if not validate_model_message(card):
            _log(f'⚠️ Card {i}: 모델 메시지 탐지 → 재시도')
            continue
    
    # Final output validation
    final_ok, final_reason = validate_final_output(cards)
    if not final_ok:
        _log(f'⚠️ 최종 검증 실패: {final_reason} → 재시도')
        continue
    
    # Proceed with publishing
    ...
```

**Estimate:** 15 min
**Files:** 1

---

### Task 5: Write Tests

**File:** `tests/test_validator.py`

**Actions:**
1. Add test class `TestValidateModelMessage`:
```python
class TestValidateModelMessage:
    def test_known_message(self):
        card = "수정할 글자 단위 오류가 발견되지 않았습니다."
        assert validate_model_message(card) == False
    
    def test_polite_form(self):
        card = "수정이 필요 없습니다."
        assert validate_model_message(card) == False
    
    def test_short_response(self):
        card = "네"
        assert validate_model_message(card) == False
    
    def test_english_message(self):
        card = "No changes needed."
        assert validate_model_message(card) == False
    
    def test_valid_content(self):
        card = "Mia Taylor는 투표 용지를 촬영해 Claude에게 물었음."
        assert validate_model_message(card) == True
    
    def test_link_card(self):
        card = "🔗 https://example.com"
        assert validate_model_message(card) == True
```

2. Add test class `TestValidateCardStructure`:
```python
class TestValidateCardStructure:
    def test_valid_cards(self):
        cards = [
            "Mia Taylor는 투표 용지를 촬영해 Claude에게 물었음.",
            "그녀는 AI에게 '이곳에서 누구에게 투표해야 할까?'라고 물었음.",
            "Claude는 처음에 대답을 거부했음.",
        ]
        assert validate_card_structure(cards) == (True, "OK")
    
    def test_duplicate_cards(self):
        cards = ["카드1", "카드1", "카드2"]
        ok, reason = validate_card_structure(cards)
        assert ok == False
        assert "중복" in reason
    
    def test_short_card(self):
        cards = ["짧은", "두번째 카드입니다."]
        ok, reason = validate_card_structure(cards)
        assert ok == False
        assert "짧음" in reason
    
    def test_no_korean(self):
        cards = ["No Korean content here.", "Second card."]
        ok, reason = validate_card_structure(cards)
        assert ok == False
        assert "한글" in reason
    
    def test_link_card_exempt(self):
        cards = [
            "첫번째 카드입니다.",
            "🔗 https://example.com",
        ]
        assert validate_card_structure(cards) == (True, "OK")
```

3. Add test class `TestValidateContentDistribution`:
```python
class TestValidateContentDistribution:
    def test_no_duplicates(self):
        cards = ["카드1", "카드2", "카드3"]
        assert validate_content_distribution(cards) == True
    
    def test_with_duplicates(self):
        cards = ["카드1", "카드1", "카드2"]
        assert validate_content_distribution(cards) == False
```

**Estimate:** 20 min
**Files:** 1

---

### Task 6: Run Tests and Verify

**Actions:**
1. Run writer tests: `.venv/bin/python3 -m pytest tests/test_writer.py -v`
2. Run validator tests: `.venv/bin/python3 -m pytest tests/test_validator.py -v`
3. Run full test suite: `.venv/bin/python3 -m pytest tests/ -v --tb=short`
4. Verify all 241 existing tests pass
5. Verify new tests pass
6. Run syntax check on modified files

**Estimate:** 10 min
**Files:** 0

---

## Verification

### Success Criteria Check

| Criteria | Method | Expected |
|----------|--------|----------|
| Model messages rejected | Unit test | Pass |
| Structural validation works | Unit test | Pass |
| All existing tests pass | pytest | 241/241 |
| False positive rate < 1% | Manual review | None |

### Test Commands

```bash
# Unit tests
.venv/bin/python3 -m pytest tests/test_validator.py -v

# Full suite
.venv/bin/python3 -m pytest tests/ -v

# Syntax check
.venv/bin/python3 -m py_compile pipeline/threads/validator.py
.venv/bin/python3 -m py_compile pipeline/threads/writer.py
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Minimum length rejects valid hooks | High | Set threshold low (20 chars) |
| Korean ratio rejects legitimate content | Medium | Set threshold low (30%) |
| Sentence completeness rejects valid content | Medium | Exempt link cards, allow ellipsis |
| Content density rejects formatted content | Low | Set threshold low (50%) |
| Duplicate detection false positives | Low | Normalize before comparison |
| Performance impact | Low | Validation is lightweight |

## Estimated Duration

- Task 1: 10 min
- Task 2: 15 min
- Task 3: 20 min
- Task 4: 15 min
- Task 5: 20 min
- Task 6: 10 min

**Total: 90 min**

## Dependencies

- Phase 10 (Model Message Leakage Fix) — completed
- No external dependencies
