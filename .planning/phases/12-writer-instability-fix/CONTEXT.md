# CONTEXT.md — Phase 12: Writer Validation Instability Fix

## Problem

The Threads publishing pipeline spent 10 hours (2026-07-05 00:00~08:37) unable to publish due to a cascading failure pattern:

1. `fix_cards()` (MiMo spell check) returns 7-9 cards from 6-card input
2. Truncation breaks card boundaries — Hook length balloons to 136-349 chars
3. `validate_card_structure()` rejects the malformed output
4. Retries with lower temperature produce similar results
5. `main_v3.py` retries the same article 5 times → waste 18 min → 2h wait → repeat

## Scope

### In Scope
- `pipeline/threads/writer.py` — `fix_cards()`, `humanize_cards()`, `write_thread()` validation chain
- `pipeline/threads/validator.py` — `validate_card_structure()` Hook/Body length rules
- `scripts/threads/main_v3.py` — article fallback on write failure

### Out of Scope
- Model router changes (MiMo/DeepSeek priority)
- New LLM models or API keys
- D1 schema or configuration changes
- Briefing pipeline changes

## Constraints
- Must not break existing 270 tests
- No new external dependencies
- Backward compatible — existing `posted.json` format unchanged

## Requirements

1. **REQ-12-01**: `fix_cards()` must preserve card count and structure
2. **REQ-12-02**: When `fix_cards()` fails card structure, fall back without spell correction (not discard)
3. **REQ-12-03**: `humanize_cards()` must not discard content on card count mismatch
4. **REQ-12-04**: Main retry loop should skip failed article, not retry same one
5. **REQ-12-05**: All 270 existing tests pass

## Assumptions
- The root cause is `fix_cards()` `---` split instability, not model quality
- Card-level (not whole-text) processing in `fix_cards()` will stabilize output
- Skipping `fix_cards()` when it fails is safe (cards already passed earlier validation)
