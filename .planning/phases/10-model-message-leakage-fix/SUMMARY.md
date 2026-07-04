# SUMMARY.md — Phase 10: Model Message Leakage Fix

## Overview

**Status:** Planned
**Created:** 2026-07-04
**Duration:** 50 min (estimated)
**Files:** 3 (writer.py, validator.py, test_writer.py)

## Problem

AI models (MiMo, GPT-4o-mini, DeepSeek) occasionally return explanatory messages that get included as content cards in published Threads posts. This structural issue has occurred repeatedly with different models.

## Solution

Add robust filtering of model explanatory messages before card splitting in `fix_cards()` and `humanize_cards()`, plus validation detection in `validate_final_output()`.

## Key Changes

### New Function
- `_strip_model_explanatory(result: str) -> str` — Filters model messages using regex patterns

### Modified Functions
- `fix_cards()` — Add filter before `split('---')`
- `humanize_cards()` — Add filter before `split('---')`
- `validate_final_output()` — Detect model messages in cards

### New Tests
- `TestStripModelExplanatory` — 4 test cases
- Integration tests for `fix_cards()` and `humanize_cards()`

## Verification

- All 227 existing tests pass
- New tests cover all message patterns
- No false positives on legitimate content

## Next Steps

1. Execute tasks in order
2. Run full test suite
3. Deploy to production
4. Monitor for new message patterns
