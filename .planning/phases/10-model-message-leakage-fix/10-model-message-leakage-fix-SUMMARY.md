# Phase 10 Plan: Model Message Leakage Fix Summary

## One-Liner
Regex-based filter + validation guard for AI model explanatory messages in Threads card pipeline.

## Tasks Completed

| # | Task | Files Modified | Status |
|---|------|---------------|--------|
| 1 | Create `_strip_model_explanatory()` + `MODEL_MESSAGE_PATTERNS` | `pipeline/threads/writer.py` | ✅ |
| 2 | Apply filter to `fix_cards()` | `pipeline/threads/writer.py` | ✅ |
| 3 | Apply filter to `humanize_cards()` | `pipeline/threads/writer.py` | ✅ |
| 4 | Add model message detection to `validate_final_output()` | `pipeline/threads/validator.py` | ✅ |
| 5 | Write tests (`TestStripModelExplanatory` + integration) | `tests/test_writer.py` | ✅ |
| 6 | Run tests and verify | — | ✅ |

## Key Decisions
- Duplicate `MODEL_MESSAGE_PATTERNS` in both writer.py and validator.py to avoid circular import between the two modules.
- Patterns match the start of the line (`re.match`) to avoid false positives on legitimate content containing these phrases mid-sentence.
- Filter placed after `_strip_instruction_leak()` in `humanize_cards()` and after model call in `fix_cards()` to clean output before `---` splitting.

## Test Results
- **Before:** 227 passed, 1 pre-existing failure (`test_cascade_2pass`)
- **After:** 241 passed, 1 pre-existing failure (unchanged)
- **New tests:** 14 (10 unit for `_strip_model_explanatory`, 2 integration for fix/humanize, 2 for validate)

## Files Changed
- `pipeline/threads/writer.py` — Added `MODEL_MESSAGE_PATTERNS`, `_strip_model_explanatory()`, filters in `fix_cards()` and `humanize_cards()`
- `pipeline/threads/validator.py` — Added `MODEL_MESSAGE_PATTERNS`, model message check in `validate_final_output()`
- `tests/test_writer.py` — Added `TestStripModelExplanatory`, `TestFixCardsModelMessage`, `TestHumanizeCardsModelMessage`, `TestValidateFinalOutputModelMessage`

## Deviations from Plan
None — plan executed exactly as written.

## Self-Check: PASSED
- writer.py syntax: OK
- validator.py syntax: OK
- 241/241 tests pass (1 pre-existing skip)
- 0 false positives in legitimate content test
