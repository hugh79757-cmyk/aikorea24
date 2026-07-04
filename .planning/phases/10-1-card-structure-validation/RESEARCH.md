# RESEARCH.md — Phase 10-1: Card Structure Validation

## Problem Statement

Regex-based pattern filtering (Phase 10) catches known model messages but misses:
- Short responses ("네", "확인됨")
- Polite forms ("수정이 필요 없습니다")
- English messages
- Structural anomalies (truncated sentences, whitespace-only cards)

**Goal**: Add structural validation to catch messages that slip through regex filtering.

## Current Validation Coverage

| Validator | What It Catches | What It Misses |
|-----------|-----------------|----------------|
| `validate_cards()` | Card count, first line length | Card content validity |
| `validate_year()` | Year fabrication | Non-year content issues |
| `validate_keywords()` | Missing keywords | Structural issues |
| `validate_no_foreign_language()` | Chinese, Japanese | Model messages |
| `validate_final_output()` | Prompt leak, language, Korean ratio | Structural anomalies |
| `_strip_model_explanatory()` | 8 specific phrases | New/variant phrases |

## Critical Gaps Identified

### Structural Gaps (Most Critical)

1. **No minimum card length** — Cards with 1-2 words pass validation
2. **No sentence completeness** — Truncated sentences pass
3. **No content density** — Whitespace-only cards pass
4. **No duplicate detection** — Same card can appear twice
5. **No hook-specific validation** — First card can be any content

### Model Message Detection Gaps

1. **Only 8 phrase patterns** — Misses variant expressions
2. **No structural checks** — Short messages pass
3. **No Korean content requirement** — English messages pass
4. **No content character threshold** — Symbol-heavy cards pass

## Proposed Structural Validation Rules

### Rule 1: Minimum Card Length

```python
MIN_CARD_LENGTH = 20  # characters

def validate_card_length(card: str) -> bool:
    """Cards must be at least 20 characters."""
    return len(card.strip()) >= MIN_CARD_LENGTH
```

**Rationale**: Model messages are typically short (< 20 chars). Real content cards are longer.

### Rule 2: Korean Content Requirement

```python
MIN_KOREAN_RATIO = 0.3  # 30% Korean characters

def validate_korean_content(card: str) -> bool:
    """Cards must contain at least 30% Korean characters."""
    # Skip link cards
    if card.strip().startswith('🔗'):
        return True
    
    korean_chars = len(re.findall(r'[가-힣]', card))
    total_chars = len(card.strip())
    
    if total_chars == 0:
        return False
    
    return korean_chars / total_chars >= MIN_KOREAN_RATIO
```

**Rationale**: Real content is primarily Korean. Model messages are often English or mixed.

### Rule 3: Sentence Completeness

```python
def validate_sentence_completeness(card: str) -> bool:
    """Cards should end with complete sentences."""
    card = card.strip()
    
    # Link cards are exempt
    if card.startswith('🔗'):
        return True
    
    # Check if ends with sentence terminator
    sentence_enders = ['.', '!', '?', '음', '임', '됨', '했음', '있음', '없음']
    if not any(card.endswith(ender) for ender in sentence_enders):
        # Check if ends with ellipsis (acceptable)
        if not card.endswith('...') and not card.endswith('…'):
            return False
    
    return True
```

**Rationale**: Model messages often end abruptly or with periods. Real content ends with Korean sentence endings.

### Rule 4: Content Density

```python
MIN_CONTENT_RATIO = 0.5  # 50% non-whitespace characters

def validate_content_density(card: str) -> bool:
    """Cards must have sufficient content density."""
    card = card.strip()
    
    if len(card) == 0:
        return False
    
    # Count non-whitespace characters
    content_chars = len(re.findall(r'\S', card))
    total_chars = len(card)
    
    return content_chars / total_chars >= MIN_CONTENT_RATIO
```

**Rationale**: Model messages often have excessive whitespace or formatting.

### Rule 5: Duplicate Detection

```python
def validate_no_duplicates(cards: list[str]) -> bool:
    """No two cards should be identical."""
    seen = set()
    for card in cards:
        normalized = card.strip().lower()
        if normalized in seen:
            return False
        seen.add(normalized)
    return True
```

**Rationale**: Model sometimes repeats the same content.

### Rule 6: Hook Length Validation

```python
HOOK_MIN_LENGTH = 30
HOOK_MAX_LENGTH = 100

def validate_hook_length(card: str) -> bool:
    """First card (hook) must be 30-100 characters."""
    return HOOK_MIN_LENGTH <= len(card.strip()) <= HOOK_MAX_LENGTH
```

**Rationale**: Hooks that are too short or too long indicate issues.

### Rule 7: Body Card Length

```python
BODY_MIN_LENGTH = 50
BODY_MAX_LENGTH = 500

def validate_body_length(card: str) -> bool:
    """Body cards must be 50-500 characters."""
    return BODY_MIN_LENGTH <= len(card.strip()) <= BODY_MAX_LENGTH
```

**Rationale**: Body cards should have substantial content.

## Enhanced Model Message Patterns

### Current Patterns (8)
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

### Proposed Additional Patterns (20+)

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

## Test Cases

### Test Class 1: TestValidateCardStructure

```python
class TestValidateCardStructure:
    def test_valid_card(self):
        card = "Mia Taylor는 투표 용지를 촬영해 Claude에게 물었음."
        assert validate_card_structure(card) == True
    
    def test_short_card(self):
        card = "네"
        assert validate_card_structure(card) == False
    
    def test_no_korean(self):
        card = "No changes needed."
        assert validate_card_structure(card) == False
    
    def test_link_card(self):
        card = "🔗 https://example.com"
        assert validate_card_structure(card) == True
    
    def test_empty_card(self):
        card = ""
        assert validate_card_structure(card) == False
```

### Test Class 2: TestValidateModelMessage

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
```

### Test Class 3: TestValidateContentDistribution

```python
class TestValidateContentDistribution:
    def test_no_duplicates(self):
        cards = ["카드1", "카드2", "카드3"]
        assert validate_content_distribution(cards) == True
    
    def test_with_duplicates(self):
        cards = ["카드1", "카드1", "카드2"]
        assert validate_content_distribution(cards) == False
    
    def test_valid_lengths(self):
        cards = ["hook" * 10, "body" * 20, "body" * 20]
        assert validate_content_distribution(cards) == True
```

## Implementation Strategy

### Phase 1: Immediate (This Session)

1. Add `validate_model_message()` to `validator.py`
2. Add minimum length check (20 chars) to `validate_cards()`
3. Add Korean content ratio check per card
4. Run existing tests

### Phase 2: Short-term (Next Session)

1. Add `validate_card_structure()` function
2. Add `validate_content_distribution()` function
3. Integrate into `write_thread()` validation chain
4. Add comprehensive tests

### Phase 3: Medium-term (Next Week)

1. Add `validate_sentence_completeness()` function
2. Add statistical pattern analysis
3. Full integration testing
4. Monitor false positive rate

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Minimum length rejects valid hooks | High | Set threshold low (20 chars) |
| Korean ratio rejects legitimate content | Medium | Set threshold low (30%) |
| Sentence completeness rejects valid content | Medium | Exempt link cards, allow ellipsis |
| Content density rejects formatted content | Low | Set threshold low (50%) |
| Duplicate detection false positives | Low | Normalize before comparison |

## Success Metrics

- Model message leakage: 0 (currently estimated 5-10% miss rate)
- Malformed card publication: 0
- False positive rate: < 1%
- Pipeline rejection rate increase: < 5%

## Monitoring Strategy

1. Log all validation failures
2. Track false positive rate weekly
3. Review new model message patterns monthly
4. Update patterns as needed
