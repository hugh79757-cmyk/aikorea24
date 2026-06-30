# Plan 05-02 Summary: Dead Code Removal + Telegram Fix

**Status:** ✅ Complete
**Wave:** 1

## Changes

### Removed Dead Functions
| File | Function Removed | Impact |
|------|-----------------|--------|
| `pipeline/threads/writer.py` | `_FORMAT_COMMON_RULES()` | Dead since D-only format |
| `pipeline/threads/validator.py` | `validate_thread()` | Legacy 8-card validator |

### Inlined Format Selection
| File | Change |
|------|--------|
| `pipeline/threads/writer.py` | `from v3.format_selector import select_format` → `format_choice = 'D'` |

### Removed Dead Code from main_v3.py
| Item | Action |
|------|--------|
| `load_env()` function | Removed (redundant with EnvConfig) |
| `reset_posted_daily()` | Removed (never called) |
| `--once` flag | Removed from argparse (was parsed but never checked) |

### Removed Files
| File | Reason |
|------|--------|
| `scripts/threads/v3/format_selector.py` | Inlined in writer.py |
| `scripts/threads/validator.py` | Standalone duplicate |
| `scripts/run_pipeline_with_notify.py` | Replaced by orchestrator Telegram |

### Added Features
| Feature | File | Details |
|---------|------|---------|
| Telegram failure notification | `pipeline/orchestrator.py` | `_send_telegram_failure()` fires on step failure + exception |

### Updated Files
| File | Change |
|------|--------|
| `scripts/threads/v3/writer_v3.py` | Removed `_FORMAT_COMMON_RULES` re-export |
| `pipeline/steps/step_run_threads.py` | Removed `--once` from subprocess call |
| `tests/test_validator.py` | Removed `TestValidateThread` class (2 tests) |
| `tests/test_characterization_pure_functions.py` | Removed 3 validate_thread test classes |

## Verification
- ✅ Tests: 167 passed, 1 pre-existing failure (5 validate_thread tests removed)
- ✅ Pipeline dry-run: All steps succeeded
- ✅ All imports resolve (writer, validator, orchestrator, pitch)
