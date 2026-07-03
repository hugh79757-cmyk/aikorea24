# Phase 7: Crawl Failure Exclusion — Research

**Researched:** 2026-07-03
**Domain:** Threads pipeline retry logic, article exclusion mechanism
**Confidence:** HIGH

## Summary

When `get_pitches()` in `pipeline/threads/pitch.py` fails to crawl a selected article's URL, it returns `[]`. The caller `main_v3.py` retries up to 5 times with backoff, but the same `article_id` keeps getting re-selected by the LLM because there is no exclusion mechanism. This creates a loop where all 5 retries fail on the same article.

The root cause: there is **no feedback path** from `get_pitches()` back to `main_v3.py` that identifies WHICH article_id failed the crawl. Each retry calls `get_articles()` (same article pool) + `get_pitches()` (same shuffle, same LLM prompt) → LLM re-selects the same article → crawl fails again.

The fix requires three things: (1) `get_pitches()` must inform the caller which article_id(s) caused the crawl failure, (2) `main_v3.py` must track failed article_ids across retries, and (3) `get_pitches()` must filter out previously-failed articles before sending to the LLM.

**Primary recommendation:** Option A with Option C as a supporting enhancement. Change `get_pitches()` to return a tuple `(pitches: list, failed_ids: set)`, have `main_v3.py` accumulate failed IDs across retries and pass them as `exclude_ids`. This is the most Pythonic, explicit, and testable approach. Additionally, extend `log_failed_crawl()` in `crawler.py` to include `article_id` so the existing `failed_crawls.json` becomes usable for cross-session exclusion.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Article crawl attempt | `pipeline/threads/crawler.py` | — | Already owns `fetch_article_body()` + `log_failed_crawl()` |
| Crawl failure exclusion logic | `pipeline/threads/pitch.py` | — | `get_pitches()` owns the article selection flow; exclusion filtering happens before LLM batch processing |
| Retry orchestration + failed ID accumulation | `scripts/threads/main_v3.py` | — | Owns the retry loop; state must live across retry iterations |
| Failed crawl persistence | `pipeline/threads/crawler.py` | — | Already owns `failed_crawls.json`; only needs `article_id` added to schema |
| Re-export wrapper | `scripts/threads/v3/narrative_pitcher.py` | — | Must update its `get_pitches` re-export signature |

## Standard Stack

### Core
This phase uses no new libraries. All changes are in existing Python code.

| Module | Version | Purpose | Why Standard |
|--------|---------|---------|--------------|
| Python stdlib `json`, `os` | 3.14 | File I/O for failed_crawls.json | Already used project-wide |

### Supporting
| Module | Version | Purpose | When to Use |
|--------|---------|---------|-------------|
| `logging` or `print` | 3.14 | Log excluded article count | On each retry with exclusion |

No new dependencies required. The fix is pure Python stdlib.

## Package Legitimacy Audit

> Not applicable — no external packages are installed in this phase.

## Architecture Patterns

### System Architecture Diagram

```
main_v3.py retry loop (max 5)
     │
     ├── get_articles()  ─────── D1 DB (same pool each retry)
     │
     ├── get_pitches(articles, exclude_ids=failed_set)
     │       │
     │       ├── Filter shuffled articles: remove exclude_ids
     │       ├── Batch → LLM → parse pitches
     │       ├── Select TOP pitch
     │       ├── Crawl TOP article URL
     │       │    ├── Success → regenerate pitch → return ([pitch], set())
     │       │    └── Failure → return ([], {failed_article_id})
     │       └─▶ main_v3 receives (pitches, failed_ids)
     │               ├── pitches truthy → proceed to write_thread
     │               └── pitches falsy → failed_set.update(failed_ids) → retry
     │
     └── After final retry → send_telegram failure alert
```

**Data flow for the exclusion mechanism (new):**

```
main_v3.retry[1]: get_pitches(exclude_ids=set()) → crawl article #123 fails → returns ([], {123})
main_v3: failed_set = {123}
main_v3.retry[2]: get_pitches(exclude_ids={123}) → article #123 filtered out → LLM selects #456
                     → crawl #456 succeeds → returns ([pitch], set())
main_v3: publishes pitch
```

### Pattern 1: Failed-Article Feedback Loop
**What:** A closed feedback loop where `get_pitches()` returns both the results and the IDs of articles that failed crawl, so the caller can exclude them on retry.
**When to use:** Any retry scenario where a downstream step (crawl, API call) can fail on a specific input item that needs exclusion on retry.
**Example:**

```python
# In main_v3.py:
failed_article_ids: set[str] = set()

for attempt in range(1, max_retries + 1):
    articles = get_articles()
    pitches, failed_ids = get_pitches(articles, exclude_ids=failed_article_ids)
    
    if pitches:
        # success path
        break
    
    failed_article_ids.update(failed_ids)
    # retry with backoff
```

### Anti-Patterns to Avoid
- **Silent failure swallowing:** Returning `[]` without communicating WHICH article failed makes the caller blind. Always surface the failing ID.
- **Persisting transient failures to `posted_ids`:** Don't add failed article_ids to `posted.json` → they'd be permanently excluded, even if the URL later becomes crawlable. Use session-scoped or time-scoped exclusion.
- **Module-level mutable state for exclusion:** A bare global `_failed_article_ids` set in `pitch.py` is invisible to tests and creates order-dependent behavior. Pass state explicitly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Crawl failure logging | Custom log format | `failed_crawls.json` (already exists in `crawler.py`) | Already handles dedup, serialization, and persistence |
| Article exclusion mechanism | New standalone exclusion file | `exclude_ids` parameter to `get_pitches()` | Minimal API surface; no new files; explicit data flow |

**Key insight:** `failed_crawls.json` already exists as a log but nobody reads it for exclusion. The simplest fix adds a read path. DON'T create a new persistence mechanism when one already exists.

## Common Pitfalls

### Pitfall 1: URL-query-parameter mismatch in failed_crawls.json
**What goes wrong:** The same article URL with different `utm_source` parameters appears as multiple failed entries in `failed_crawls.json`. Without normalization, URL→article_id mapping fails.
**Why it happens:** `failed_crawls.json` stores raw URLs with query params; `normalize_url()` in `db_reader.py` strips them. The two don't align.
**How to avoid:** Use `normalize_url()` from `db_reader.py` both when writing and reading failed crawl entries. Better yet, store the `article_id` directly in `failed_crawls.json` alongside the URL.
**Warning signs:** Multiple entries in `failed_crawls.json` pointing to essentially the same article.

### Pitfall 2: LLM re-selecting nearly-identical articles after exclusion
**What goes wrong:** Excluding one article_id doesn't prevent the LLM from selecting a different article on the same topic from the same source with the same paywall.
**Why it happens:** `failed_crawls.json` entries are per-URL, not per-domain or per-source. If ft.com/abc fails, ft.com/def will still be in the pool.
**How to avoid:** This is out of scope for Phase 7 — the exclusion is per-article, not per-source. Document as a known limitation.
**Warning signs:** A single source (e.g., FT, Fast Company) causes repeated failures across different article_ids.

### Pitfall 3: Test regressions from tuple return type change
**What goes wrong:** `get_pitches()` currently returns `list`. Changing to `tuple[list, set]` breaks all existing callers and tests that destructure the return value.
**Why it happens:** Every caller and test that does `if pitches:` or `pitches[0]` will get a tuple instead of a list — booleans on tuples are truthy even for empty results.
**How to avoid:** Update ALL callers and tests in the same commit. Run the full test suite. See the `TestGetPitchesCrawlFail` class in `tests/test_pitch.py` as the primary test surface.
**Warning signs:** `test_pitch.py::TestGetPitchesCrawlFail::test_discards_when_crawl_fails` asserts `result == []` — this MUST be updated to `result == ([], set())`.

## Code Examples

### Example 1: Updated `get_pitches()` signature and crawl-failure return

Source: `pipeline/threads/pitch.py` line 437, lines 592–615

```python
def get_pitches(articles, max_articles=600, batch_size=200, exclude_ids=None):
    """배치 처리. exclude_ids: 크롤링 실패한 article_id set (재시도 시 제외용).
    Returns: (pitches: list, failed_ids: set)
    """
    # ... existing setup ...

    selected = articles[:max_articles]
    shuffled = selected.copy()
    random.shuffle(shuffled)
    
    # NEW: Filter out previously-failed articles
    if exclude_ids:
        before = len(shuffled)
        shuffled = [a for a in shuffled if str(a.get('id', '')) not in exclude_ids]
        if len(shuffled) < before:
            _log(f'  🚫 제외: {before - len(shuffled)}개 기사 (크롤링 실패 이력)')
    
    if not shuffled:
        _log('  ❌ 모든 기사가 제외됨 (크롤링 실패 이력)')
        return [], set()
    
    # ... batching, LLM calls (unchanged) ...

    # LINE 586-601: Crawl failure returns with the failed article_id
    if not article_url:
        _log(f'  ⚠️ 기사 {article_id_str}의 URL을 찾을 수 없음 → 피치 폐기')
        return [], {article_id_str} if article_id_str else set()

    _log(f'  📰 피치 기사 원문 크롤링: {article_url[:60]}...')
    crawled_body = fetch_article_body(article_url, source='', title=article_title)

    if not crawled_body:
        _log(f'  ⚠️ 크롤링 실패 → 피치 폐기')
        return [], {article_id_str} if article_id_str else set()

    # ... regeneration (unchanged) ...
    
    if regenerated:
        regenerated['crawled_body'] = crawled_body
        _log(f'  ✅ 크롤링 기반 피치 재생성 완료')
        return [regenerated], set()
    else:
        _log(f'  ⚠️ 피치 재생성 실패 → 피치 폐기')
        return [], {article_id_str} if article_id_str else set()
```

### Example 2: Updated `main_v3.py` retry loop

Source: `scripts/threads/main_v3.py` lines 107–291

```python
def run_v3(dry_run=False):
    max_retries = 5
    retry_delays = [60, 120, 300, 600]
    failed_article_ids: set[str] = set()   # NEW: accumulate across retries

    for attempt in range(1, max_retries + 1):
        # ... backoff (unchanged) ...

        articles = get_articles()
        if not articles:
            # ... unchanged ...
            continue

        from v3.narrative_pitcher import get_pitches
        briefing_articles = [a for a in articles if a.get('priority') == 1]
        pitches = []
        failed_ids: set[str] = set()

        # UPDATED: pass exclude_ids, unpack tuple
        if briefing_articles:
            pitches, failed_ids = get_pitches(
                briefing_articles,
                max_articles=len(briefing_articles),
                batch_size=len(briefing_articles),
                exclude_ids=failed_article_ids,
            )

        if not pitches:
            pitches, failed_ids = get_pitches(
                articles,
                max_articles=600,
                exclude_ids=failed_article_ids,
            )

        failed_article_ids.update(failed_ids)   # NEW: accumulate

        if not pitches:
            log(f'  ❌ 흥미로운 이야기 발견 실패 (시도 {attempt}/{max_retries})')
            if failed_ids:
                log(f'     크롤링 실패 기사: {failed_ids}')
            continue

        # ... rest unchanged (write_thread, publish, etc.) ...
```

### Example 3: Extend `failed_crawls.json` entry with `article_id`

Source: `pipeline/threads/crawler.py` lines 26–41

```python
def log_failed_crawl(url, source, title, status, article_id=""):
    """크롤링 실패한 URL을 failed_crawls.json에 기록"""
    data = {"failed": [], "updated_at": ""}
    if os.path.exists(FAILED_CRAWLS_FILE):
        try:
            with open(FAILED_CRAWLS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass
    now = datetime.now().isoformat()
    # NEW: include article_id for cross-reference
    entry = {
        "url": url,
        "source": source,
        "title": title,
        "status": status,
        "article_id": article_id,    # <-- NEW FIELD
        "failed_at": now,
    }
    data['failed'] = [e for e in data['failed'] if e.get('url') != url]
    data['failed'].append(entry)
    data['updated_at'] = now
    with open(FAILED_CRAWLS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

## Solution Options

### Option A (RECOMMENDED): Tuple return + exclude_ids parameter

**How it works:**
1. Change `get_pitches()` return type from `list` to `tuple[list, set]` — always returns `(pitches, failed_ids)`
2. Add `exclude_ids: Optional[set] = None` parameter — filter excluded article_ids from shuffled list before batching
3. In `main_v3.py`, maintain `failed_article_ids: set[str] = set()` before retry loop, pass it to `get_pitches()`, accumulate failed IDs on each retry

**Files to modify:**

| File | Lines | Change |
|------|-------|--------|
| `pipeline/threads/pitch.py` | 437 | `get_pitches()` signature: add `exclude_ids=None` parameter |
| `pipeline/threads/pitch.py` | 449–451 | Insert exclusion filter: remove articles whose ID is in `exclude_ids` |
| `pipeline/threads/pitch.py` | 524–615 | Change all `return []` to `return ([], failed_set)` with appropriate failed_ids |
| `scripts/threads/main_v3.py` | 108 | Add `failed_article_ids: set[str] = set()` |
| `scripts/threads/main_v3.py` | 138, 149 | Unpack tuple: `pitches, failed_ids = get_pitches(...)` |
| `scripts/threads/main_v3.py` | 138, 149 | Pass `exclude_ids=failed_article_ids` |
| `scripts/threads/main_v3.py` | 153 (after) | Add `failed_article_ids.update(failed_ids)` |
| `scripts/threads/v3/narrative_pitcher.py` | 19 | Update re-export to include new signature |
| `tests/test_pitch.py` | 246–298 | Update all 4 tests in `TestGetPitchesCrawlFail` — expect `([], set())` not `[]` |
| `pipeline/threads/pitch.py` | 605–615 | Also return `article_id_str` on `_regenerate_pitch_from_crawl` failure |

**Pros:**
- Explicit data flow: main_v3 controls what gets excluded, nothing is hidden
- No new files or persistence mechanism
- Sessions-scoped: exclusion resets on process restart (correct for transient failures)
- Easy to test: mock `fetch_article_body` to return `""`, assert `([], {article_id})`
- All changes are in 3 files (pitch.py, main_v3.py, narrative_pitcher.py) + tests

**Cons:**
- Breaking API change to `get_pitches()` — must update ALL callers and tests in one commit
- `narrative_pitcher.py` `__main__` block (line 28–41) needs update too (rarely used)

---

### Option B: Persist failed IDs to `posted.json` with `status: failed_crawl`

**How it works:**
1. When crawl fails in `get_pitches()`, write `{article_id, status: "failed_crawl", timestamp}` to `posted.json` under a new key `failed_crawl_ids`
2. In `db_reader.py::get_articles()`, treat `failed_crawl_ids` as additional exclusion criteria alongside `posted_ids`
3. Add a cleanup mechanism: exclude only failures from the last N hours (since transient failures may resolve)

**Files to modify:**

| File | Lines | Change |
|------|-------|--------|
| `pipeline/threads/pitch.py` | 592–601 | Write failed article_id to `posted.json` `failed_crawl_ids` |
| `scripts/threads/db_reader.py` | 164–197 | Add `failed_crawl_ids` check in `is_already_posted()` or `get_articles()` |
| `scripts/threads/db_reader.py` | ~240–357 | Filter out recently-failed article_ids from article pool |
| `scripts/threads/posted.json` | — | Add `failed_crawl_ids` key (runtime — no code change needed) |
| `pipeline/threads/crawler.py` | 26–41 | Add article_id to `log_failed_crawl()` |

**Pros:**
- Persists across process restarts (URLs like FT.com paywall are permanently uncrawlable)
- Uses existing `posted.json` read path — every retry already loads it via `load_posted()`
- No API change to `get_pitches()` — no callers need updating

**Cons:**
- `posted.json` is overloaded: "already posted" and "crawl failed" are semantically different states
- Need TTL cleanup logic — transient failures (network blip) shouldn't permanently exclude articles
- More files modified (pitch.py + db_reader.py + posted.json structure)
- Mixes concern: `db_reader` (article loading) now needs to know about crawl failures (article processing concern)
- TTL mechanism adds complexity (±4 more lines of code for timestamp comparison)

---

### Option C: Read `failed_crawls.json` in `get_pitches()` for URL-based exclusion

**How it works:**
1. `failed_crawls.json` ALREADY exists and tracks failed crawl URLs — populated by `crawler.py::log_failed_crawl()`
2. In `get_pitches()`, load `failed_crawls.json` and build a `set()` of failed URLs (normalized via `normalize_url()`) that are less than N hours old
3. Before batching, filter out articles whose URL matches a failed URL
4. No changes to `main_v3.py` or return type

**Files to modify:**

| File | Lines | Change |
|------|-------|--------|
| `pipeline/threads/pitch.py` | 437–451 | Load `failed_crawls.json`, build failed URL set, filter shuffled articles |
| `pipeline/threads/crawler.py` | 26–41 | Add `article_id` to `log_failed_crawl()` entry for cross-reference |
| `pipeline/threads/pitch.py` | 597 | Pass `article_id` to `fetch_article_body()` or `log_failed_crawl()` |

**Pros:**
- Zero API changes — `get_pitches()` signature unchanged, no callers updated
- Uses existing infrastructure (`failed_crawls.json` already exists)
- Persists across restarts (no in-memory state to lose)
- Already has retry dedup (`.json` entries dedup by URL on write)

**Cons:**
- `failed_crawls.json` has URLs, not article_ids — need URL→article_id mapping via `id_to_link` reverse lookup
- URL normalization needed: raw URLs in `failed_crawls.json` have query params, article `link` may differ
- Temporal: `failed_crawls.json` accumulates forever — need a TTL filter (e.g., only exclude failures < 24 hours old)
- Implicit: `main_v3.py` has no visibility into what's being excluded; debugging harder
- `failed_crawls.json` has entries from `writer.py` too (not just `get_pitches()`)

---

### Comparison Table

| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| **API change to get_pitches()** | Yes (return tuple) | No | No |
| **Files modified** | 4 + tests | 3 + posted.json | 2 |
| **State persistence** | Session only | Permanent (needs TTL) | Persistent w/ TTL |
| **Explicit data flow** | ✅ Explicit | ⚠️ Implicit (via JSON) | ⚠️ Implicit (via file) |
| **Test complexity** | Low (mock fetch) | Medium (mock json I/O) | Medium (mock file I/O) |
| **Risk of over-exclusion** | None (session resets) | High (no TTL = permanent) | Low (with TTL) |
| **Debuggability** | High (log shows excluded IDs) | Medium | Low (silent file read) |
| **Works for writer.py failures too** | No | No | Yes (file is shared) |

## Recommended Approach

### Option A (tuple return + exclude_ids) — RECOMMENDED

**Rationale:**
- **Explicit beats implicit.** The caller (`main_v3.py`) explicitly controls what gets excluded and can log it. No hidden file reads.
- **Correct scoping.** Crawl failures within a single run (minutes apart) are likely transient — the URL won't fix itself in 10 minutes. Session-scoped exclusion is the right default.
- **No persistence baggage.** Option B requires TTL management and pollutes `posted.json`. Option C requires URL normalization against `failed_crawls.json` which has different URL formats.
- **Testability.** The changed function has a deterministic input/output contract. Unit tests for `TestGetPitchesCrawlFail` need minimal updates.
- **Minimum files touched.** All changes are in the pitch.caller axis (pitch.py → narrative_pitcher.py → main_v3.py). No changes to db_reader.py, dedup.py, or posted.json structure.

**As a supporting enhancement** (not required for the fix, but recommended), extend `log_failed_crawl()` in `crawler.py` to accept and store `article_id` alongside the URL. This makes `failed_crawls.json` usable for cross-session exclusion in a future phase without changing the core fix.

### Implementation order:
1. `pipeline/threads/pitch.py` — Modify `get_pitches()` signature, add exclusion filter, change return values
2. `scripts/threads/v3/narrative_pitcher.py` — Update re-export to pass through `exclude_ids`
3. `scripts/threads/main_v3.py` — Add `failed_article_ids` tracking, unpack tuples, pass `exclude_ids`
4. `tests/test_pitch.py` — Update `TestGetPitchesCrawlFail` to expect tuple returns
5. `pipeline/threads/crawler.py` — (Optional enhancement) Add `article_id` to `log_failed_crawl()`

## Files to Modify (Exact References)

### Must modify (core fix):

| File | Line(s) | What |
|------|---------|------|
| `pipeline/threads/pitch.py` | 437 | `get_pitches(articles, max_articles=600, batch_size=200, exclude_ids=None)` |
| `pipeline/threads/pitch.py` | 449–452 | Insert exclusion filter after `shuffled.copy()` |
| `pipeline/threads/pitch.py` | 524 | Change `return []` → `return ([], set())` |
| `pipeline/threads/pitch.py` | 539 | Change `return []` → `return ([], set())` |
| `pipeline/threads/pitch.py` | 568 | Change `return []` → `return ([], set())` |
| `pipeline/threads/pitch.py` | 574 | Change `return []` → `return ([], set())` |
| `pipeline/threads/pitch.py` | 593 | Change `return []` → `return ([], {article_id_str})` |
| `pipeline/threads/pitch.py` | 601 | Change `return []` → `return ([], {article_id_str})` |
| `pipeline/threads/pitch.py` | 615 | Change `return []` → `return ([], {article_id_str})` |
| `scripts/threads/v3/narrative_pitcher.py` | 19 | Update `get_pitches` re-export to include `exclude_ids` parameter |
| `scripts/threads/main_v3.py` | 108 | Add `failed_article_ids: set[str] = set()` |
| `scripts/threads/main_v3.py` | 138 | `pitches = get_pitches(...)` → `pitches, failed_ids = get_pitches(..., exclude_ids=failed_article_ids)` |
| `scripts/threads/main_v3.py` | 149 | Same as line 138 |
| `scripts/threads/main_v3.py` | ~153 | Add `failed_article_ids.update(failed_ids)` after `get_pitches()` calls |
| `tests/test_pitch.py` | 267 | `assert result == []` → `assert result == ([], set())` |
| `tests/test_pitch.py` | 275 | Same |
| `tests/test_pitch.py` | 286 | Same |
| `tests/test_pitch.py` | 297–298 | `assert len(result) == 1` → unpack tuple; `assert result[0]["hook"]` → `assert result[0][0]["hook"]` |

### Should modify (enhancement):

| File | Line(s) | What |
|------|---------|------|
| `pipeline/threads/crawler.py` | 26 | `log_failed_crawl(url, source, title, status, article_id="")` |
| `pipeline/threads/crawler.py` | 36 | Add `"article_id": article_id` to entry dict |
| `pipeline/threads/crawler.py` | 81 | Pass `article_id` to `log_failed_crawl()` |
| `pipeline/threads/writer.py` | 526 | Pass `article_id=""` to `log_failed_crawl()` (backward compat) |

### Do NOT modify:

| File | Reason |
|------|--------|
| `scripts/threads/db_reader.py` | Article loading is correct — exclusion happens at the pitch level, not the article pool level |
| `scripts/threads/dedup.py` | No dedup changes needed |
| `scripts/threads/posted.json` | Structure unchanged — no new keys |
| `pipeline/threads/pitch_evaluator.py` | Evaluation logic unchanged |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RSS description fallback on crawl failure | `return []` on crawl failure | 2026-07-03 (CHANGES.md) | Eliminated low-quality pitches but created retry loop |
| No exclusion mechanism | Must add `exclude_ids` parameter | This phase | Prevents re-selection of failed articles |

**Deprecated/outdated:**
- The old RSS fallback path (removed in the 2026-07-03 change) would have shielded the user from this bug by publishing a low-quality pitch instead of retrying. The `return []` change is correct, but it exposed the missing exclusion mechanism.

## Assumptions Log

> No claims tagged `[ASSUMED]` — all findings in this research are verified against the actual source code on disk.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None — all findings verified via code reading | — | — |

## Open Questions

1. **Should `failed_crawls.json` also be consumed for cross-session exclusion?**
   - What we know: `failed_crawls.json` already exists with URL/source/title/status. It's written by `crawler.py::log_failed_crawl()` and by `writer.py`.
   - What's unclear: Whether permanently paywalled URLs (FT.com, WSJ) should be excluded across sessions. The `failed_crawls.json` has entries from 10+ days ago.
   - Recommendation: Document this as a future enhancement. For the core fix, session-scoped exclusion (Option A) handles the retry loop. Cross-session exclusion can be added later by reading `failed_crawls.json` + normalizing URLs + building an exclusion set.

2. **What about the `writer.py` crawl failures?**
   - What we know: `writer.py` also calls `fetch_article_body()` and `log_failed_crawl()`, but the writer failure path is different — if writer can't crawl any article, it calls `_log('⚠️ 모든 기사 크롤링 불가 → 스킵')` and returns `None`. This writes to `failed_crawls.json` but doesn't cause a retry loop.
   - What's unclear: Should writer failures also feed into the exclusion set? Currently writer calls `log_failed_crawl()` but doesn't return the article_id to any retry loop.
   - Recommendation: Out of scope for this phase. Writer failures don't cause retry loops — they just skip the article and continue.

3. **Should narrative_pitcher.py `__main__` block be updated?**
   - What we know: `narrative_pitcher.py` has a `if __name__ == '__main__':` block (line 28–41) that calls `get_pitches()` and expects a list return.
   - What's unclear: Whether this is still actively used for testing.
   - Recommendation: Update it with the new tuple signature for consistency, even though it's dev-only code.

## Environment Availability

> Skip — phase has no external dependencies (code/config-only changes). No tools, services, runtimes, or CLIs beyond the existing Python 3.14 environment.

## Validation Architecture

> Skipped — `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`.

## Security Domain

> Skipped — `security_enforcement` is not relevant to this phase. No secrets, auth, or access control changes. The phase modifies only article exclusion logic in the pipeline. No input from untrusted sources, no cryptographic operations, no session management.

## Sources

### Primary (HIGH confidence)
- Source code files read and analyzed: `pipeline/threads/pitch.py`, `scripts/threads/main_v3.py`, `scripts/threads/v3/narrative_pitcher.py`, `scripts/threads/dedup.py`, `scripts/threads/db_reader.py`, `pipeline/threads/crawler.py`, `tests/test_pitch.py`
- Runtime data files: `scripts/threads/posted.json` (5,885 lines), `scripts/threads/logs/failed_crawls.json` (28 failed entries)

### Secondary (MEDIUM confidence)
- `CHANGES.md` (2026-07-03 entry confirms the RSS fallback removal that created this problem)
- `.planning/ROADMAP.md` (phase structure and history)
- `.planning/REQUIREMENTS.md` (requirements traceability)

### Tertiary (LOW confidence)
- None — all findings verified against actual source code on disk

## Metadata

**Confidence breakdown:**
- Problem analysis: HIGH — exact code paths verified via reading source files line by line
- Solution options: HIGH — all options are based on the actual codebase state
- Pitfalls: HIGH — derived from existing code structure and documented anti-patterns
- Implementation plan: HIGH — exact line numbers verified against current source

**Research date:** 2026-07-03
**Valid until:** 2026-08-03 (stable — no fast-moving dependencies)

---

## RESEARCH COMPLETE

**Phase:** 7 - Crawl Failure Exclusion
**Confidence:** HIGH

### Key Findings
1. **Root cause confirmed:** `get_pitches()` returns `[]` on crawl failure with no indication of WHICH article_id failed. `main_v3.py` retries blindly, and the LLM re-selects the same article because it's still in the article pool.
2. **Three return paths return `[]` without article_id info:** lines 593 (URL not found), 601 (crawl fails), 615 (regeneration fails). All three have `article_id_str` available at that point.
3. **`failed_crawls.json` already exists** with 28 entries but nobody reads it for exclusion. It's purely a diagnostic log.
4. **`fetch_article_body()` in `crawler.py` already writes to `failed_crawls.json`** — the crawl failure is already recorded, just not consumed by `get_pitches()`.
5. **The fix is low-risk and focused:** changes are in 3 files (pitch.py, main_v3.py, narrative_pitcher.py) + tests, with no new dependencies.

### File Created
`.planning/phases/07-crawl-failure-exclusion/07-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Problem Analysis | HIGH | Verified via line-by-line reading of all 4 relevant files |
| Solution Design | HIGH | All options are based on the actual call graph and data flow |
| Implementation | HIGH | Exact file paths and line numbers verified against current source |
| Pitfalls | HIGH | Based on actual code structure; no speculation |

### Open Questions
- None blocking. Cross-session exclusion from `failed_crawls.json` is a future enhancement, not needed for this fix.

### Ready for Planning
Research complete. Planner can now create PLAN.md for Phase 7 implementation.
