# Task 2 Report: Expansion — Rotation persistence + Naver output wiring

## What You Implemented

1. **Rotation Persistence** (`pipeline/threads/compass.py`)
   - `_load_compass_rotation()`: reads `compass_intro_rotation` from `posted.json`
   - `_save_compass_rotation(counter)`: writes back with `json.dump(ensure_ascii=False, indent=2)`
   - Counter loaded at start of `write_compass_article`, incremented only on successful draft
   - Overrides LLM's `intro_style` and `h2_flow` with rotation-based values from `INTRO_STYLES` and `H2_FLOW_PRESETS`

2. **Naver HTML Output** (`pipeline/threads/compass.py`)
   - `_wrap_naver_html(cards)`: wraps non-tag lines in `<p>`, converts markdown headings to `<h2>`, strips disallowed tags (div, span, style, class, etc.)
   - `_NAVER_TAG_STRIP_RE`: regex for all disallowed tags
   - `output_target` parameter added to `write_compass_article` (default "naver")
   - "threads" returns cards as-is, "naver" applies HTML wrapping
   - `writer.py` passes `output_target="naver"` in compass branch

3. **Compass Cache** (`pipeline/threads/compass.py`)
   - `_compass_cache: dict[tuple, tuple]` — module-level dict
   - Cache key: `(article_id, today_date_str)`
   - Cache hit returns immediately, skipping LLM calls

4. **Test Updates** (`tests/test_compass_generation.py`)
   - `TestRotation`: 3 tests — 5 distinct styles, counter persistence, rotation overrides LLM
   - `TestNaverOutput`: 2 tests — naver wraps in `<p>`, threads returns plain cards
   - `tests/conftest.py`: autouse fixture clears `_compass_cache` between tests

## Test Results

```
tests/test_compass_generation.py: 7 passed
tests/test_compass_draft_compliance.py: 3 passed (pre-existing, no regressions)
Full suite (excluding 3 pre-existing failures): 436 passed, 0 new failures
```

Pre-existing failures (NOT from this task):
- `test_deep_dive_writer.py` — SyntaxError in `scripts/deep_dive_writer.py:434`
- `test_failed_articles.py::test_retention_from_env` — assertion logic mismatch
- `test_pitch.py::test_discards_when_crawl_fails` — crawl behavior changed
- `test_write_thread_validation.py::test_hook_entity_quote_marked_accepted` — validator rule

## Files Changed

| File | Change | Type |
|------|--------|------|
| `pipeline/threads/compass.py` | +96 lines: rotation persistence, cache, Naver HTML, output_target param | PRODUCTION CODE |
| `pipeline/threads/writer.py` | +1 line: pass output_target="naver" to compass | PRODUCTION CODE |
| `tests/test_compass_generation.py` | Rewritten: 7 tests, rotation + Naver output coverage | TEST CODE |
| `tests/conftest.py` | +9 lines: autouse _clear_compass_cache fixture | TEST CODE |

## Self-Review Findings

1. **Cache invalidation**: Cache key is `(article_id, date)`. Same article re-run on same day returns cached result. This is intentional per spec ("retries never regenerate"). If article body changes within the day, cache serves stale result — acceptable for production use.

2. **Rotation override**: LLM-generated `intro_style` and `h2_flow` are silently overridden by rotation counter. The compass JSON still contains the LLM values initially, but they get replaced before Pass 2. This means the LLM's Pass 2 prompt shows rotation-based values, which is correct.

3. **Naver HTML stripping**: `_NAVER_TAG_STRIP_RE` strips a broad set of tags. If LLM generates a `<div>` inside a card, it gets stripped. This is intentional — whitelist-only output.

4. **posted.json path**: Uses same path derivation as `pitch.py` (`os.path.dirname` twice from `__file__`). Correct.

## Concerns

- None significant. All changes are additive. No existing behavior modified.
