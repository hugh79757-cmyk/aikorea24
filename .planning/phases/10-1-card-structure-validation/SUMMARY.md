# SUMMARY.md — Phase 10-1: Card Structure Validation

## Overview

**Status:** Planned
**Created:** 2026-07-04
**Duration:** 90 min (estimated)
**Files:** 3 (validator.py, writer.py, test_validator.py)

## Problem

Phase 10 added regex-based pattern filtering for model messages, but this approach has inherent limitations:
- Only catches known patterns (8 specific phrases)
- Misses variant expressions, short responses, English messages
- No structural validation of card content
- Models can generate new message patterns not in the list

## Solution

Add structural validation to catch model messages that slip through regex filtering, ensuring zero model messages and malformed cards in published posts.

## Key Changes

### New Functions in `validator.py`
- `validate_model_message(card: str) -> bool` — Enhanced model message detection
- `validate_card_structure(cards: list[str]) -> tuple[bool, str]` — Structural validation

### New Patterns
- `ADDITIONAL_MESSAGE_PATTERNS` — 20+ new patterns for polite forms, short responses, English messages

### Validation Rules
1. Minimum card length (20 chars)
2. Korean content requirement (30%)
3. Sentence completeness check
4. Content density check (50% non-whitespace)
5. Duplicate detection
6. Hook length validation (30-100 chars)
7. Body card length validation (50-500 chars)

### Integration
- Updated `write_thread()` validation chain in `writer.py`
- Added structural validation before final output validation

### New Tests
- `TestValidateModelMessage` — 6 test cases
- `TestValidateCardStructure` — 5 test cases
- `TestValidateContentDistribution` — 2 test cases

## Verification

- All 241 existing tests pass
- New tests cover all structural validation rules
- False positive rate < 1%

## Next Steps

1. Execute tasks in order
2. Run full test suite
3. Deploy to production
4. Monitor false positive rate
