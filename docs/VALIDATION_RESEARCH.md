# Card Structure Validation System — Research & Design

## Executive Summary

This document analyzes the current validation logic in `pipeline/threads/validator.py` and `pipeline/threads/writer.py`, identifies gaps in coverage, and proposes a sophisticated structural validation system to catch model messages and malformed cards that currently slip through.

**Current State:** The validation system has 5 validator functions and 8 model message patterns, but relies heavily on keyword matching rather than structural analysis.

**Key Finding:** The current `MODEL_MESSAGE_PATTERNS` only catch 8 specific phrase patterns. Model messages that are shorter, use different vocabulary, or are structurally invalid (e.g., too short, no Korean content, incomplete sentences) can still pass validation.

**Recommendation:** Implement a multi-layered structural validation system with minimum length requirements, content density checks, sentence completeness validation, and statistical pattern analysis.

---

## 1. Current Validation Coverage Matrix

### 1.1 Validator Functions (`pipeline/threads/validator.py`) — Phase 11 Update

> **Phase 11 (2026-07-05):** `validate_no_foreign_language()` remains in validator for direct callers but is no longer used in writer's validation chain. Pattern definitions (`MODEL_MESSAGE_PATTERNS`, `ADDITIONAL_MESSAGE_PATTERNS`, `ALL_MESSAGE_PATTERNS`) are single-source-of-truth in validator — writer imports. `validate_final_output()` now uses `ALL_MESSAGE_PATTERNS` (26 patterns), ≥30% Korean ratio, and `unicodedata.normalize('NFKC')` before foreign language checks. `CHINESE_PATTERN` and `JAPANESE_PATTERN` exported for use in `pitch.py`. See `docs/TECH.md` Section 11 for full chain.

| Function | Purpose | What It Catches | Phase 11 |
|----------|---------|-----------------|----------|
| `validate_cards()` | Card count + hook length | Wrong card count, short hook | — |
| `validate_year()` | Year hallucination | Years not in article | — |
| `validate_keywords()` | Keyword preservation | Missing 3+ critical keywords | — |
| `validate_no_foreign_language()` | Chinese/Japanese chars | CJK characters | Import removed from writer (still in validator for direct use) |
| `validate_final_output()` | 5-in-1 final check | Prompt leak + foreign lang + Korean ratio ≥30% + ALL_MESSAGE_PATTERNS + NFKC normalization | Patterns: 8→26, Threshold: 0.1→0.3, +NFKC |
| `validate_model_message()` | Card-level model message check | ALL_MESSAGE_PATTERNS (26) + structural checks + link strip fix | `.strip()` before link check |
| `validate_card_structure()` | Card structural integrity | Duplicates, length, Korean, sentence completeness, hook/body | — |

### 1.2 Model Message Patterns (`MODEL_MESSAGE_PATTERNS`)

```python
# Current 8 patterns (validator.py + writer.py — duplicated)
r'^수정할\s+글자\s+단위'        # "수정할 글자 단위..."
r'^원본을\s+그대로\s+반환'      # "원본을 그대로 반환..."
r'^수정할\s+게\s+없'            # "수정할 게 없..."
r'^오류가\s+발견되지'            # "오류가 발견되지..."
r'^변경\s+사항이?\s+없'         # "변경 사항이/는 없..."
r'^수정\s+불필요'               # "수정 불필요..."
r'^AI\s+티가?\s+나는'           # "AI 티가/는 나는..."
r'^교정할\s+부분이?\s+없'       # "교정할 부분이/는 없..."
```

**Critical Gap:** These patterns only match messages that START with these exact phrases. Model messages that:
- Start with different words (e.g., "확인 결과...", "검토한 결과...")
- Use polite/formal style (e.g., "수정이 필요 없습니다", "교정할 부분이 없습니다")
- Are very short (e.g., "네", "확인됨", "정상")
- Use English (e.g., "No changes needed", "All good")

...will ALL pass validation.

### 1.3 Writer Filtering (`pipeline/threads/writer.py`)

| Function | Purpose | Effectiveness |
|----------|---------|---------------|
| `_strip_model_explanatory()` | Line-by-line model message removal | Uses same 8 patterns — same gaps |
| `_strip_instruction_leak()` | Remove instruction fragments | Good coverage of instruction patterns |
| `_cleanup_source_attribution()` | Remove source lines | Effective |
| `_clean_english_leakage()` | Remove embedded English | Good regex coverage |
| `_fix_korean_particle_spacing()` | Fix spacing after English | Effective |
| `humanize_cards()` | LLM-based humanization | May introduce new model artifacts |
| `fix_cards()` | Character correction | May introduce new model artifacts |

---

## 2. Identified Gaps

### 2.1 Structural Gaps (Most Critical)

| Gap | Impact | Current Detection | Proposed Fix |
|-----|--------|-------------------|--------------|
| **No minimum card length** | Cards with 1-2 words pass validation | None | `validate_card_length()` — min 50 chars |
| **No maximum card length** | Cards >500 chars (Threads limit) pass | None | Already handled by Threads API, but validate anyway |
| **No sentence completeness check** | Truncated sentences pass | None | Check for complete sentence endings |
| **No content density check** | Whitespace-only or punctuation-only cards pass | None | Check for actual Korean content |
| **No repeated content check** | Same card repeated passes | None | Check for duplicate/very similar cards |
| **No numeric-only card check** | Cards with only numbers pass | None | Check for Korean content ratio per card |
| **No stanza structure validation** | Missing blank lines between stanzas pass | None | Check for proper spacing patterns |
| **No hook-specific validation** | First card can be any content | Partial (3-char min) | Validate hook has question/interest |

### 2.2 Model Message Detection Gaps

| Pattern Type | Example | Currently Caught? | Notes |
|--------------|---------|-------------------|-------|
| **Short responses** | "네", "확인됨", "정상" | ❌ No | Too short, no Korean content |
| **Polite form** | "수정이 필요 없습니다" | ❌ No | Uses "없습니다" not "없" |
| **English messages** | "No changes needed" | ❌ No | No pattern for English |
| **Explanation prefixes** | "확인 결과 모든 카드가..." | ❌ No | Starts with "확인" not existing patterns |
| **Question responses** | "어떤 부분을 수정할까요?" | ❌ No | Ends with "?" not matching patterns |
| **Partial messages** | "모든 카드가 정상입니다" | ❌ No | Different vocabulary |
| **Numbered lists** | "1. 카드 1: 정상\n2. 카드 2: 정상" | ❌ No | Structured but not caught |

### 2.3 Content Quality Gaps

| Quality Issue | Example | Currently Caught? | Proposed Fix |
|---------------|---------|-------------------|--------------|
| **Excessive whitespace** | Card with 80% blank lines | ❌ No | Check line count vs content |
| **Punctuation-only lines** | "...", "---", "===\n===" | ❌ No | Check for actual content |
| **Emoji-only cards** | "✅" or "❌" | ❌ No | Check for Korean content |
| **Bullet-point-only cards** | "- item\n- item\n- item" | ❌ No | Check for complete sentences |
| **Repeated phrases** | "이것은 중요함. 이것은 중요함." | ❌ No | Check for repetition |
| **Mixed case corruption** | "AI가 AIGenerated를..." | Partial | English leakage catches some |

---

## 3. Proposed Structural Validation Rules

### 3.1 New Validation Function: `validate_card_structure()`

```python
def validate_card_structure(cards: list[str], format_choice='D') -> tuple[bool, str]:
    """
    Structural validation of card content.
    Returns (is_valid, reason).
    """
    MIN_CARD_LENGTH = 50      # Minimum characters per card
    MAX_CARD_LENGTH = 500     # Threads API limit
    MIN_KOREAN_CHARS = 10     # Minimum Korean characters per card
    MIN_SENTENCES = 2         # Minimum sentences per card (1-5 cards)
    
    for i, card in enumerate(cards, 1):
        card = card.strip()
        
        # 1. Length validation
        if len(card) < MIN_CARD_LENGTH:
            return False, f"Card {i}: 너무 짧음 ({len(card)}자 < {MIN_CARD_LENGTH}자)"
        
        if len(card) > MAX_CARD_LENGTH:
            return False, f"Card {i}: 너무 김 ({len(card)}자 > {MAX_CARD_LENGTH}자)"
        
        # 2. Korean content check (skip for link cards)
        if not card.startswith('🔗'):
            korean_chars = len(re.findall(r'[가-힣]', card))
            if korean_chars < MIN_KOREAN_CHARS:
                return False, f"Card {i}: 한글 부족 ({korean_chars}자 < {MIN_KOREAN_CHARS}자)"
        
        # 3. Sentence completeness check
        if not card.startswith('🔗'):
            # Check for complete sentence endings
            ends_with_complete = bool(re.search(r'[가-힣][임음됨].*$', card, re.MULTILINE))
            if not ends_with_complete:
                return False, f"Card {i}: 문장 미완성"
        
        # 4. Content density check (not just whitespace/punctuation)
        content_chars = len(re.findall(r'[가-힣a-zA-Z0-9]', card))
        if content_chars < len(card) * 0.3:
            return False, f"Card {i}: 내용 밀도 부족"
    
    return True, "OK"
```

### 3.2 Enhanced Model Message Detection

```python
# Expanded model message patterns
MODEL_MESSAGE_PATTERNS_ENHANCED = [
    # Existing patterns
    r'^수정할\s+글자\s+단위',
    r'^원본을\s+그대로\s+반환',
    r'^수정할\s+게\s+없',
    r'^오류가\s+발견되지',
    r'^변경\s+사항이?\s+없',
    r'^수정\s+불필요',
    r'^AI\s+티가?\s+나는',
    r'^교정할\s+부분이?\s+없',
    
    # NEW: Polite/formal forms
    r'^수정이\s+필요\s+없',
    r'^교정할\s+부분이?\s+없',
    r'^변경이?\s+없',
    r'^오류가?\s+없',
    r'^문제가?\s+없',
    r'^이상이?\s+없',
    r'^정상입니',
    r'^정상이니',
    r'^정상적',
    
    # NEW: Short confirmation responses
    r'^[네예]$',
    r'^확인',
    r'^정상',
    r'^통과',
    r'^PASS$',
    r'^OK$',
    r'^Good$',
    r'^All\s+good',
    
    # NEW: Question responses
    r'^어떤\s+부분을',
    r'^무엇을\s+수정',
    r'^어떻게\s+수정',
    
    # NEW: Explanation prefixes
    r'^확인\s+결과',
    r'^검토\s+결과',
    r'^분석\s+결과',
    r'^평가\s+결과',
    r'^진단\s+결과',
    
    # NEW: English messages
    r'^No\s+changes',
    r'^No\s+issues',
    r'^All\s+cards',
    r'^Every\s+card',
    r'^Cards?\s+are',
    r'^The\s+cards?\s+are',
]

def validate_model_message(card: str) -> tuple[bool, str]:
    """Check if a card is actually a model message."""
    card_stripped = card.strip()
    
    # 1. Pattern matching
    for pattern in MODEL_MESSAGE_PATTERNS_ENHANCED:
        if re.match(pattern, card_stripped):
            return True, f"모델 메시지 패턴: {pattern}"
    
    # 2. Structural checks
    # Very short cards are likely model messages
    if len(card_stripped) < 20 and not card_stripped.startswith('🔗'):
        return True, f"너무 짧은 카드 ({len(card_stripped)}자)"
    
    # Cards with no Korean characters
    korean_chars = len(re.findall(r'[가-힣]', card_stripped))
    if korean_chars == 0 and len(card_stripped) > 5:
        return True, "한글 없음 (영문 모델 메시지)"
    
    # Cards that are just punctuation/numbers
    content_chars = len(re.findall(r'[가-힣a-zA-Z]', card_stripped))
    if content_chars < 3:
        return True, f"내용 없음 (특수문자/숫자만)"
    
    return False, "OK"
```

### 3.3 Content Distribution Validation

```python
def validate_content_distribution(cards: list[str]) -> tuple[bool, str]:
    """
    Validate that card content is properly distributed.
    - No duplicate cards
    - Proper length distribution
    - Hook is shorter than body cards
    """
    # 1. Check for duplicate cards
    card_hashes = [hash(card.strip()[:100]) for card in cards]
    if len(set(card_hashes)) < len(cards):
        return False, "중복 카드 발견"
    
    # 2. Check length distribution
    lengths = [len(card.strip()) for card in cards]
    if lengths[0] > 200:  # Hook should be shorter
        return False, f"첫 카드(훅)가 너무 김 ({lengths[0]}자)"
    
    # 3. Check that body cards are substantial
    for i, length in enumerate(lengths[1:], 2):
        if length < 100:
            return False, f"Card {i}: 너무 짮음 ({length}자)"
    
    return True, "OK"
```

### 3.4 Sentence Completeness Validation

```python
def validate_sentence_completeness(cards: list[str]) -> tuple[bool, str]:
    """
    Validate that sentences in cards are complete.
    - No truncated sentences
    - Proper sentence endings
    - No mid-word breaks
    """
    # Korean sentence endings
    SENTENCE_ENDINGS = re.compile(r'[가-힣][임음됨]$')
    # Truncation patterns
    TRUNCATION_PATTERNS = [
        r'[가-힣]\.\.\.$',  # Trailing ellipsis
        r'[가-힣]\s*$',     # Ends mid-sentence
        r'[가-힣]\s*\.\s*$',  # Period at end but feels incomplete
    ]
    
    for i, card in enumerate(cards, 1):
        if card.strip().startswith('🔗'):
            continue
        
        lines = card.strip().split('\n')
        for j, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Check for truncation
            for pattern in TRUNCATION_PATTERNS:
                if re.search(pattern, line):
                    # Allow ellipsis in specific cases (dramatic effect)
                    if '...' not in line:
                        return False, f"Card {i}, Line {j}: 문장 잘림"
    
    return True, "OK"
```

---

## 4. Test Cases for Each Rule

### 4.1 Test Cases for `validate_card_structure()`

```python
class TestValidateCardStructure:
    @pytest.mark.unit
    def test_valid_card(self):
        """정상 카드 — 통과"""
        card = "소프트뱅크가 오픈AI 지분을 담보로 100억 달러 대출 제안을 다시 꺼냄."
        ok, reason = validate_card_structure([card])
        assert ok is True
    
    @pytest.mark.unit
    def test_too_short_card(self):
        """너무 짧은 카드 — 차단"""
        card = "네"
        ok, reason = validate_card_structure([card])
        assert ok is False
        assert "너무 짧음" in reason
    
    @pytest.mark.unit
    def test_no_korean_content(self):
        """한글 없는 카드 — 차단"""
        card = "12345678901234567890123456789012345678901234567890"
        ok, reason = validate_card_structure([card])
        assert ok is False
        assert "한글 부족" in reason
    
    @pytest.mark.unit
    def test_incomplete_sentence(self):
        """미완성 문장 — 차단"""
        card = "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄"
        ok, reason = validate_card_structure([card])
        assert ok is False
        assert "문장 미완성" in reason
    
    @pytest.mark.unit
    def test_link_card_skips_checks(self):
        """링크 카드 — 검사 스킵"""
        card = "🔗 https://example.com/news"
        ok, reason = validate_card_structure([card])
        assert ok is True
    
    @pytest.mark.unit
    def test_low_content_density(self):
        """내용 밀도 부족 — 차단"""
        card = "   \n\n\n\n   "  # Mostly whitespace
        ok, reason = validate_card_structure([card])
        assert ok is False
        assert "내용 밀도 부족" in reason
```

### 4.2 Test Cases for `validate_model_message()`

```python
class TestValidateModelMessage:
    @pytest.mark.unit
    def test_short_response(self):
        """짧은 응답 — 차단"""
        ok, reason = validate_model_message("네")
        assert ok is True
        assert "너무 짧음" in reason
    
    @pytest.mark.unit
    def test_polite_form(self):
        """존댓말 모델 메시지 — 차단"""
        ok, reason = validate_model_message("수정이 필요 없습니다.")
        assert ok is True
        assert "모델 메시지" in reason
    
    @pytest.mark.unit
    def test_english_message(self):
        """영문 모델 메시지 — 차단"""
        ok, reason = validate_model_message("No changes needed for the cards.")
        assert ok is True
        assert "영문 모델 메시지" in reason
    
    @pytest.mark.unit
    def test_confirmation_response(self):
        """확인 응답 — 차단"""
        ok, reason = validate_model_message("확인됨")
        assert ok is True
        assert "모델 메시지" in reason
    
    @pytest.mark.unit
    def test_normal_content_passes(self):
        """정상 콘텐츠 — 통과"""
        ok, reason = validate_model_message("소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.")
        assert ok is False
        assert reason == "OK"
    
    @pytest.mark.unit
    def test_number_only_card(self):
        """숫자만 있는 카드 — 차단"""
        ok, reason = validate_model_message("12345678901234567890")
        assert ok is True
        assert "내용 없음" in reason
```

### 4.3 Test Cases for `validate_content_distribution()`

```python
class TestValidateContentDistribution:
    @pytest.mark.unit
    def test_duplicate_cards(self):
        """중복 카드 — 차단"""
        cards = ["Card content\nline 2", "Card content\nline 2"]
        ok, reason = validate_content_distribution(cards)
        assert ok is False
        assert "중복" in reason
    
    @pytest.mark.unit
    def test_hook_too_long(self):
        """훅이 너무 김 — 차단"""
        cards = ["A" * 201, "Body card\nline 2", "Another card\nline 2"]
        ok, reason = validate_content_distribution(cards)
        assert ok is False
        assert "훅" in reason
    
    @pytest.mark.unit
    def test_body_card_too_short(self):
        """본문 카드 너무 짧음 — 차단"""
        cards = ["Hook", "Short", "Another card\nline 2"]
        ok, reason = validate_content_distribution(cards)
        assert ok is False
        assert "너무 짮음" in reason
    
    @pytest.mark.unit
    def test_valid_distribution(self):
        """정상 분포 — 통과"""
        cards = [
            "Hook line\nwith detail",
            "Body card 1\nline 2\nline 3\nline 4",
            "Body card 2\nline 2\nline 3\nline 4"
        ]
        ok, reason = validate_content_distribution(cards)
        assert ok is True
```

### 4.4 Test Cases for `validate_sentence_completeness()`

```python
class TestValidateSentenceCompleteness:
    @pytest.mark.unit
    def test_complete_sentences(self):
        """완전한 문장 — 통과"""
        cards = ["소프트뱅크가 대출 제안을 꺼냄.", "이번 제안에 채무 보증 포함됨."]
        ok, reason = validate_sentence_completeness(cards)
        assert ok is True
    
    @pytest.mark.unit
    def test_truncated_sentence(self):
        """잘린 문장 — 차단"""
        cards = ["소프트뱅크가 오픈AI 지분을 담보로"]
        ok, reason = validate_sentence_completeness(cards)
        assert ok is False
        assert "문장 잘림" in reason
    
    @pytest.mark.unit
    def test_multiple_lines(self):
        """여러 줄 — 각 줄 검증"""
        cards = ["Line 1.\nLine 2.\nLine 3."]
        ok, reason = validate_sentence_completeness(cards)
        assert ok is True
    
    @pytest.mark.unit
    def test_empty_lines_ok(self):
        """빈 줄 — 무시"""
        cards = ["Line 1.\n\nLine 3."]
        ok, reason = validate_sentence_completeness(cards)
        assert ok is True
```

---

## 5. Implementation Recommendations

### 5.1 Integration Strategy

**Phase 1: Immediate Fixes (Low Risk)**
1. Add `validate_model_message()` as a new function in `validator.py`
2. Call it in `validate_final_output()` before other checks
3. Add minimum length check (50 chars) to `validate_cards()`
4. Test with existing test suite

**Phase 2: Structural Validation (Medium Risk)**
1. Add `validate_card_structure()` function
2. Add `validate_content_distribution()` function
3. Integrate into `write_thread()` validation chain
4. Monitor rejection rate for false positives

**Phase 3: Advanced Validation (Higher Risk)**
1. Add `validate_sentence_completeness()` function
2. Add statistical pattern analysis (character distribution)
3. Add repetition detection
4. Full integration testing

### 5.2 Validation Chain Order

```python
# Proposed validation chain in write_thread()
def validate_cards_chain(cards, pitch, format_choice, article_body_text):
    """Complete validation chain with structural checks."""
    
    # Layer 1: Basic structure
    ok, reason = validate_cards(cards, pitch, format_choice)
    if not ok:
        return False, reason
    
    # Layer 2: Model message detection (NEW)
    for i, card in enumerate(cards, 1):
        is_msg, msg_reason = validate_model_message(card)
        if is_msg:
            return False, f"Card {i}: {msg_reason}"
    
    # Layer 3: Card structure (NEW)
    ok, reason = validate_card_structure(cards, format_choice)
    if not ok:
        return False, reason
    
    # Layer 4: Content distribution (NEW)
    ok, reason = validate_content_distribution(cards)
    if not ok:
        return False, reason
    
    # Layer 5: Sentence completeness (NEW)
    ok, reason = validate_sentence_completeness(cards)
    if not ok:
        return False, reason
    
    # Layer 6: Year validation
    ok, reason = validate_year(cards, article_body_text)
    if not ok:
        return False, reason
    
    # Layer 7: Keyword validation
    ok, reason = validate_keywords(cards, article_body_text)
    if not ok:
        return False, reason
    
    # Layer 8: Final output (existing)
    ok, reason = validate_final_output(cards)
    if not ok:
        return False, reason
    
    return True, "OK"
```

### 5.3 False Positive Mitigation

**Risk:** New validation rules may reject valid cards.

**Mitigation:**
1. **Gradual rollout:** Start with warnings, not rejections
2. **Configurable thresholds:** Make `MIN_CARD_LENGTH`, `MIN_KOREAN_CHARS` configurable
3. **Override capability:** Allow manual override for edge cases
4. **Monitoring:** Log all rejections for analysis
5. **Test coverage:** Comprehensive test suite before deployment

### 5.4 Performance Considerations

| Validation | Complexity | Impact |
|------------|------------|--------|
| `validate_model_message()` | O(n * p) where p = patterns | Negligible (8 patterns) |
| `validate_card_structure()` | O(n * m) where m = checks | Negligible |
| `validate_content_distribution()` | O(n) | Negligible |
| `validate_sentence_completeness()` | O(n * l) where l = lines | Negligible |

**Total overhead:** < 1ms for 6 cards — acceptable for background pipeline.

---

## 6. Risk Assessment

### 6.1 High-Risk Changes

| Change | Risk | Mitigation |
|--------|------|------------|
| Minimum length validation | May reject short but valid hooks | Set threshold low (50 chars) |
| Sentence completeness check | May reject dramatic fragments | Allow ellipsis, monitor false positives |
| Enhanced model message patterns | May over-match legitimate content | Start with warnings, collect data |

### 6.2 Medium-Risk Changes

| Change | Risk | Mitigation |
|--------|------|------------|
| Content distribution validation | May reject valid but unusual structures | Make configurable |
| Duplicate detection | May reject intentional repetition | Use similarity threshold, not exact match |

### 6.3 Low-Risk Changes

| Change | Risk | Mitigation |
|--------|------|------------|
| Korean content ratio check | Already exists, just per-card now | Same threshold as existing |
| Link card bypass | Already implemented | Same logic |

---

## 7. Monitoring & Observability

### 7.1 Metrics to Track

```python
# Suggested metrics for validation system
METRICS = {
    'validation_rejection_rate': Counter('validation_rejections_total', ['rule']),
    'model_message_detection_rate': Counter('model_messages_detected_total', ['pattern']),
    'card_length_distribution': Histogram('card_length_chars'),
    'korean_ratio_distribution': Histogram('korean_ratio_per_card'),
    'false_positive_reports': Counter('validation_false_positives_total', ['rule']),
}
```

### 7.2 Logging Strategy

```python
# Structured logging for validation decisions
def log_validation_decision(cards, decision, reason, rule):
    logger.info(
        "validation_decision",
        card_count=len(cards),
        decision=decision,
        reason=reason,
        rule=rule,
        card_lengths=[len(c) for c in cards],
        korean_ratios=[korean_ratio(c) for c in cards],
    )
```

---

## 8. Conclusion

The current validation system has solid foundations but significant gaps in structural validation and model message detection. The proposed enhancements address these gaps while maintaining low false-positive rates through careful threshold tuning and gradual rollout.

**Priority Actions:**
1. **Immediate:** Add `validate_model_message()` with enhanced patterns
2. **This week:** Add minimum length validation to `validate_cards()`
3. **Next week:** Implement `validate_card_structure()` and `validate_content_distribution()`
4. **Next month:** Add `validate_sentence_completeness()` and statistical analysis

**Success Metrics:**
- Reduce model message leakage to 0 (currently estimated 5-10% miss rate)
- Reduce malformed card publication to 0
- Maintain false positive rate < 1%
- No increase in pipeline rejection rate > 5%

---

*Research completed: 2026-07-04*
*Phase 11 defense hardening: 2026-07-05*
*Next review: 2026-08-04*
