---
phase: 12-writer-instability-fix
plan: 01
name: Per-card humanize/fix + validator relax
type: execute
wave: 1
tags: [card-stability, humanize, fix-cards, validator, per-card-processing]
subsystem: pipeline/threads
requires: []
provides: [per-card-humanize, per-card-fix-cards, hook-boundary-check]
affects: [writer.py, validator.py, test_writer.py]
key-decisions:
  - Per-card LLM calls for humanize_cards and fix_cards eliminate card count instability as root cause
  - Hook max length raised from 250→350 with content boundary safety check as secondary defense
  - Len(card) < 10 skip guard in humanize_cards to avoid pointless LLM calls for trivial content
  - Tests updated to reflect per-card call patterns (12 total calls: 6 humanize + 6 MiMo)
  - Per-card always returns new list object (identity checks in tests changed to equality checks)
duration: 247s
completed: 2026-07-05
task_count: 4
file_count: 3
---

# Phase 12 Plan 01: Eliminate card count instability — per-card humanize/fix + validator relax

Converted both `humanize_cards()` and `fix_cards()` from the buggy `--- join → LLM → --- split` pattern to per-card individual processing, guaranteeing card count invariance by code structure. Relaxed hook length from 250→350 with content boundary safety check.

## Tasks Executed

| # | Task | Type | Commit | Result |
|---|------|------|--------|--------|
| 1 | Per-card `humanize_cards()` — eliminate count mismatch | feat | `f10b8a4` | ✅ |
| 2 | Per-card `fix_cards()` MiMo — eliminate card count explosion | feat | `43b4707` | ✅ |
| 3 | Relax hook length 250→350 + content boundary safety check | feat | `a322d43` | ✅ |
| 4 | Update tests for per-card processing patterns | test | `e030662` | ✅ |

## Key Changes

### `pipeline/threads/writer.py`
- **`humanize_cards()`**: Rewrote from `---` join/split pattern to per-card loop. Each card gets its own LLM call with a per-card prompt. Card count invariant by code structure. Short cards (< 10 chars) skip LLM gracefully. Per-card failure only affects that one card (falls back to original).
- **`fix_cards()`**: Replaced the MiMo spell-check section from `---` join/split with per-card loop. Each card gets its own MiMo call. No count checks, no truncation, no "카드 수 초과/부족" logs.
- No changes to `_clean_english_leakage`, `_fix_korean_particle_spacing`, `_strip_model_explanatory`, `_strip_instruction_leak`, or `parse_cards`.

### `pipeline/threads/validator.py`
- **Hook max length**: 250 → 350 chars
- **New content boundary check**: Counts sentence endings (`~임.`, `~했음.`, `~있음.`, `~됨.`, `~함.`, `.`, `!`, `?`) in hook. If > 2, flags as probable card boundary merge.

### `tests/test_writer.py`
- `test_returns_original_on_count_mismatch` → `test_returns_original_on_empty_response` (per-card failure test)
- `test_returns_original_on_humanize_mismatch` → `test_fix_cards_preserves_card_count` (6→6 invariant)
- `test_model_message_filtered`: Updated mock for 12 per-card calls (6 humanize + 6 MiMo)
- `test_preserves_on_count_match`: Updated to use per-card mock with properly long input cards
- `test_short_input`: Changed `is` identity check to `==` equality check (per-card always builds new list)

## Verification Results

```
82 passed in 0.29s
```

- `split('---')` in writer.py: 1 occurrence (only in `parse_cards`, as expected)
- `len(hook) > 350`: Present in validator.py
- `문장 종결 과다`: Present in validator.py

## Success Criteria

| Criterion | Status |
|-----------|--------|
| `humanize_cards()` returns exactly `len(input)` cards | ✅ Code invariant |
| `fix_cards()` returns exactly `len(input)` cards | ✅ Code invariant |
| No `---` join/split in `humanize_cards()` or `fix_cards()` | ✅ Only in `parse_cards()` |
| Hook content boundary check catches merged-card hooks | ✅ |
| All test_writer.py and test_validator.py tests pass | ✅ 82/82 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `test_preserves_on_count_match` with short input cards**
- **Issue:** The test used `"card 0"` through `"card 5"` (6 chars each) as input. The per-card `humanize_cards()` skips cards < 10 chars, so no LLM call was made and the mock was never invoked.
- **Fix:** Updated test to use longer input strings (exceeding 10 chars each) and a per-card mock (`call_count`-based sequential responses).
- **Files:** `tests/test_writer.py`

**2. [Rule 3 - Blocking] `test_short_input` identity check**
- **Issue:** Test used `result is cards` (identity check). Per-card processing always builds a new list, so identity fails even when content matches.
- **Fix:** Changed to `result == cards` (equality check). Identity preservation was an artifact of the old return-cards-directly pattern.
- **Files:** `tests/test_writer.py`

**3. [Rule 3 - Blocking] `test_returns_original_on_count_mismatch` identity check**
- **Issue:** Test used `result is cards`. Per-card always builds a new list.
- **Fix:** Replaced with planned `test_returns_original_on_empty_response` (returns None, checks equality).
- **Files:** `tests/test_writer.py`

## Threat Model Compliance

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-12-01 (DoS: 12× LLM calls) | mitigate — per-card failure isolation | ✅ Each card has own try/except |
| T-12-02 (Tampering: per-card response > 500 chars) | accept — final validation catches | ✅ No code change needed |
| T-12-03 (Spoofing: model message per-card) | mitigate — `_strip_model_explanatory` + `_strip_instruction_leak` per card | ✅ Applied per-card in both humanize and MiMo |
