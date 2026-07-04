# CONTEXT.md — Phase 10-1: Card Structure Validation

## Problem

Phase 10 added regex-based pattern filtering for model messages, but this approach has inherent limitations:
- Only catches known patterns (8 specific phrases)
- Misses variant expressions, short responses, English messages
- No structural validation of card content
- Models can generate new message patterns not in the list

**Example**: Model outputs "네" or "No changes needed" — both pass current validation.

## Impact

- Model messages can still slip through (estimated 5-10% miss rate)
- Structural anomalies (truncated sentences, whitespace-only cards) can be published
- No defense against new/unknown message patterns

## Scope

### In Scope
- `pipeline/threads/validator.py` — New structural validation functions
- `pipeline/threads/writer.py` — Integration into validation chain
- `tests/test_validator.py` — New test cases
- `tests/test_writer.py` — Integration tests

### Out of Scope
- Model prompt optimization
- Performance optimization
- Other pipeline modules

## Requirements

1. **REQ-01**: Cards must be at least 20 characters
2. **REQ-02**: Cards must contain at least 30% Korean characters (link cards exempt)
3. **REQ-03**: Cards must end with complete sentences
4. **REQ-04**: Cards must have sufficient content density (50% non-whitespace)
5. **REQ-05**: No duplicate cards allowed
6. **REQ-06**: Hook card must be 30-100 characters
7. **REQ-07**: Body cards must be 50-500 characters
8. **REQ-08**: Model messages must be detected and rejected
9. **REQ-09**: All existing tests must pass
10. **REQ-10**: False positive rate must be < 1%

## Constraints

- Must not break existing functionality
- Must be backward compatible
- Must handle edge cases (link cards, short hooks, etc.)
- Must work with all models (MiMo, GPT-4o-mini, DeepSeek)
- Must have low false positive rate (< 1%)

## Assumptions

- Model messages are typically short (< 20 chars)
- Real content is primarily Korean (> 30%)
- Real content ends with Korean sentence endings
- Link cards are exempt from most validations
- Current card count validation provides secondary defense

## Success Criteria

- Zero model messages in published posts
- Zero malformed cards in published posts
- All existing tests pass
- New tests cover all structural validation rules
- False positive rate < 1%
