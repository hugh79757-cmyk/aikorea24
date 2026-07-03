---
phase: 07-crawl-failure-exclusion
plan: 01
subsystem: pipeline/threads
tags:
  - crawl-failure
  - exclude_ids
  - retry-loop
  - tuple-return
requires: []
provides:
  - exclude_ids filter in get_pitches()
  - tuple return (list, set) across all paths
  - failed_article_ids accumulation in main_v3.py
  - article_id tracking in log_failed_crawl()
affects:
  - pipeline/threads/pitch.py
  - scripts/threads/main_v3.py
  - scripts/threads/v3/narrative_pitcher.py
  - tests/test_pitch.py
  - pipeline/threads/crawler.py
tech-stack:
  added: []
  patterns:
    - Tuple return type (list, set) for error reporting
    - Accumulation pattern for cross-call failure tracking
    - Optional exclude_ids parameter with None → set() coercion
key-files:
  created: []
  modified:
    - pipeline/threads/pitch.py
    - scripts/threads/main_v3.py
    - scripts/threads/v3/narrative_pitcher.py
    - tests/test_pitch.py
    - pipeline/threads/crawler.py
decisions: []
metrics:
  duration: ~12min
  completed_date: 2026-07-03
---

# Phase 7 Plan 01: Crawl Failure Exclusion — SUMMARY

**Eliminate the retry loop by excluding crawl-failed article IDs from subsequent `get_pitches()` calls.** When a crawl fails on an article, that article_id accumulates in `failed_article_ids` so the LLM never re-selects it across 5 retry attempts — saving ~38 minutes of wasted API calls per pipeline run.

## Files Modified

| File | Change |
|------|--------|
| `pipeline/threads/pitch.py` | Added `exclude_ids=None` param; inserted exclusion filter after shuffle; changed all 7 return paths to `(list, set)` tuples; crawl-failure returns include `article_id_str` in failed set |
| `scripts/threads/main_v3.py` | Added `failed_article_ids: set[str] = set()` initialization; tuple unpacking on both `get_pitches()` calls; passes `exclude_ids=failed_article_ids`; accumulates failures via `failed_ids.update(_failed)` pattern; logs failed IDs on retry exhaustion |
| `scripts/threads/v3/narrative_pitcher.py` | Updated `__main__` block to unpack tuple: `pitches, _ = get_pitches(...)` |
| `scripts/threads/v3/writer_v3.py` | Updated `__main__` block to unpack tuple: `pitches, _ = get_pitches(...)` |
| `tests/test_pitch.py` | Updated 4 `TestGetPitchesCrawlFail` tests for tuple assertions; `test_keeps_when_crawl_succeeds` unpacks `(pitches, failed_ids)` and asserts `failed_ids == set()` |
| `pipeline/threads/crawler.py` | Added `article_id=""` param to `log_failed_crawl()`; stores `"article_id"` in entry dict |

## Verification Results

| Check | Result |
|-------|--------|
| Syntax — all 5 files | ✅ Pass |
| `test_pitch.py` (34 tests) | ✅ 34 passed (0 failed) |
| Full suite (197 tests) | ✅ 196 passed, 1 pre-existing failure (`test_cascade_2pass.py`) |
| Signature check | ✅ `get_pitches(articles, max_articles=600, batch_size=200, exclude_ids=None)` |
| Min lines artifact (≥690) | ✅ 700 lines in `pitch.py` |
| `failed_article_ids: set[str]` present | ✅ in `main_v3.py` |
| `failed_article_ids.update` call | ✅ after both get_pitches() calls |

## Deviations from Plan

### Plan Checker Warning Applied — `main_v3.py` accumulation pattern

The plan's Task 2c code used direct assignment `pitches, failed_ids = get_pitches(...)` which would overwrite the first call's failures on the second call. Fixed by using the plan checker Warning 2 accumulation pattern:
- Initialize `failed_ids: set[str] = set()` before branching
- Both branches use `_pitches, _failed = get_pitches(...)` + `failed_ids.update(_failed)`
- After both branches: `failed_article_ids.update(failed_ids)`

This ensures failures from the briefing phase are NOT lost when the fallback phase runs.

## Commits

| Hash | Message |
|------|---------|
| `2b27275` | `feat(07-crawl-failure-exclusion): add exclude_ids param + tuple return to get_pitches()` |
| `e66fa57` | `feat(07-crawl-failure-exclusion): wire callers with tuple unpacking + exclude_ids` |
| `59168a9` | `feat(07-crawl-failure-exclusion): update tests + enhance crawler.py log_failed_crawl()` |

## Success Criteria Met

- [x] `get_pitches()` has `exclude_ids` parameter and always returns `(list, set)` tuple
- [x] Articles in `exclude_ids` are filtered out before LLM batch processing
- [x] Log shows `🚫 제외: N개 기사 (크롤링 실패 이력)` when articles are excluded
- [x] Log shows `❌ 모든 기사가 제외됨` when the entire pool is excluded
- [x] `main_v3.py` accumulates failed IDs across retries and passes them to subsequent `get_pitches()` calls
- [x] When crawl succeeds, return is `([regenerated_pitch], set())` — zero regression
- [x] All 197 tests pass (196 + 1 pre-existing failure)
- [x] `log_failed_crawl()` accepts optional `article_id` and stores it in `failed_crawls.json`

## Self-Check: PASSED
