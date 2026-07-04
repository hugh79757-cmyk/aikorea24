# CONTEXT.md — Phase 10: Model Message Leakage Fix

## Problem

AI models occasionally return explanatory messages that get included as content cards in published Threads posts. This has happened repeatedly with different models (GPT-4o-mini, DeepSeek, MiMo), proving it's a structural issue, not model-specific.

## Impact

- Published posts contain model messages as first card
- User experience degraded
- Repeated fix attempts have failed (structural fix needed)

## Scope

### In Scope
- `pipeline/threads/writer.py` — `fix_cards()` and `humanize_cards()` functions
- `pipeline/threads/validator.py` — `validate_final_output()` function
- New utility function for model message detection
- Tests for all message patterns

### Out of Scope
- Model prompt optimization (not root cause)
- Other pipeline modules (pitch.py, etc.)
- Performance optimization

## Requirements

1. **REQ-01**: Model explanatory messages must be filtered before card splitting
2. **REQ-02**: Validation must detect model messages in final cards
3. **REQ-03**: No false positives on legitimate content
4. **REQ-04**: All existing tests must pass
5. **REQ-05**: New tests must cover all message patterns

## Constraints

- Must not break existing functionality
- Must be backward compatible
- Must handle edge cases (messages with `---`, multiple messages)
- Must work with all models (MiMo, GPT-4o-mini, DeepSeek)

## Assumptions

- Models will continue to occasionally add explanatory text
- Pattern-based filtering is sufficient (no ML-based detection needed)
- Current card count validation provides secondary defense

## Success Criteria

- Zero model messages in published posts
- All tests pass
- No false positives on legitimate content
