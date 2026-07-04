# CONTEXT.md — Phase 11: Defense Mechanism Hardening

## Problem

The threads publishing pipeline's defense against model-generated explanatory messages and foreign characters shows inconsistencies and potential gaps:
- Duplicate pattern definitions risk maintenance drift.
- `validate_final_output()` uses a subset of patterns, missing ADDITIONAL_MESSAGE_PATTERNS.
- Korean ratio threshold in final_output is 10% vs 30% elsewhere.
- Dead code (`validate_no_foreign_language`) pollutes imports.
- Link card check inconsistency (strip vs no-strip).
- No end-to-end integration test for full validation chain.

These issues could allow model messages or non-Korean content to slip through, or cause false positives, and increase technical debt.

## Scope

### In Scope
- `pipeline/threads/validator.py`
- `pipeline/threads/writer.py`
- `pipeline/threads/pitch.py` (foreign language pattern consolidation)
- `tests/test_write_thread_validation.py` (new)
- `tests/test_validator.py` (new Unicode normalization tests)
- `docs/TECH.md` updates
- `docs/VALIDATION_RESEARCH.md` updates (if any)

### Out of Scope
- Changes to detection patterns (no new message patterns beyond consolidation)
- Modifications to other pipeline steps
- Performance tuning
- Changes to D1 schema or configuration
- Cyrillic/Unicode homoglyph detection (future work)

## Requirements

1. **REQ-01**: Consolidate `MODEL_MESSAGE_PATTERNS` to single source (import from validator in writer)
2. **REQ-02**: `validate_final_output()` must check all model message patterns (use `ALL_MESSAGE_PATTERNS`)
3. **REQ-03**: Korean ratio check in `validate_final_output()` must be ≥30% or removed (to align with other validators)
4. **REQ-04**: Fix link card check to use `.strip()` in `validate_model_message()`
5. **REQ-05**: Remove dead import of `validate_no_foreign_language` from writer
6. **REQ-06**: Add integration tests covering full `write_thread()` validation chain
7. **REQ-07**: All existing tests (262) must pass
8. **REQ-08**: Documentation must reflect final behavior
9. **REQ-09**: Apply Unicode NFKC normalization before foreign language detection in `validate_final_output()`
10. **REQ-10**: Consolidate `_CHINESE_PATTERN` and `_JAPANESE_PATTERN` from `pitch.py` into `validator.py`
11. **REQ-11**: Strengthen LLM system prompt (`build_system_prompt_D()`) with explicit foreign language prohibition warning

## Constraints

- Must not break existing functionality (backward compatible)
- Must work with current Python version (3.14)
- No new external dependencies
- Changes must be covered by tests

## Assumptions

- The 26 patterns in `ALL_MESSAGE_PATTERNS` are sufficient for current model outputs.
- Raising Korean ratio to 30% in final_output will not cause failures because cards already passed that threshold earlier.
- No circular import will be introduced by importing patterns from validator to writer.

## Success Criteria

- Zero regressions in existing test suite (262 pass)
- New integration tests pass
- All tasks implemented as specified
- CODE REVIEW passes with no high-severity findings
- Documentation updated
