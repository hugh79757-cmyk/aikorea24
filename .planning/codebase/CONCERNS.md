# Codebase Concerns

> Areas of concern, technical debt, and potential issues in the codebase.
> Last updated: 2026-06-30
> Mapped by: gsd-codebase-mapper (concerns focus)

## Overview

The **aikorea24.kr** codebase is a dual-system project: an Astro/Cloudflare website (`src/`) and a Python pipeline (`scripts/`) for automated news collection, AI-powered content generation (Threads threads + blog briefings), and social media publishing. It shows signs of rapid, iterative development with significant accumulated technical debt — particularly around code duplication, hardcoded paths, massive single-file modules, and an explosion of backup/clutter files.

**Risk distribution by area:**
- **Python pipeline**: HIGH — massive single files, duplicated code, fragile orchestration
- **Astro frontend**: LOW-MEDIUM — relatively clean but with deployment/debugging issues
- **Infrastructure/deploy**: MEDIUM — cross-project dependency, stale configs
- **Testing**: MEDIUM — uneven coverage (only briefing pipeline tested)
- **Security**: LOW-MEDIUM — auth gaps, token exposure in logs

---

## Technical Debt

### Hardcoded Project Paths Across All Python Files
- **Severity:** High
- **Location:** `scripts/threads/main_v3.py` (line 11), `scripts/threads/db_reader.py` (line 12, 47), `scripts/threads/v3/writer_v3.py` (line 14), `scripts/threads/v3/narrative_pitcher.py` (line 11), `scripts/threads/v3/model_router.py` (line 11), `scripts/threads/publisher.py` (line 11), `scripts/briefing_scorer.py` (line 22), `scripts/auto_news_selector.py` (line 19), `scripts/auto_briefing.py` (line 12), `scripts/run_pipeline.py` (line 19), and more.
- **Description:** Every Python script defines `PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'` at module level. This makes the entire codebase non-portable — it cannot be cloned and run on another machine without editing every file.
- **Impact:** Zero portability. CI/CD on any other machine requires sed-replacing all paths. Blocks team collaboration.
- **Suggested fix:** Extract `PROJECT_DIR` into a single shared config module (e.g., `scripts/config.py`) or use `os.path.dirname(os.path.dirname(__file__))` relative resolution as done in `briefing_scorer.py:22`. Remove all hardcoded paths.

### `load_env()` Duplicated Across 5+ Files
- **Severity:** High
- **Location:** `scripts/threads/main_v3.py` (line 94), `scripts/threads/db_reader.py` (none, but env loading implicit), `scripts/threads/v3/narrative_pitcher.py` (line 25), `scripts/threads/v3/model_router.py` (line 15), `scripts/threads/publisher.py` (line 23)
- **Description:** The exact same `load_env()` function — reading from `~/.env.common`, `.env`, and `api_test/.env.sh` — is copy-pasted in at least 5 files with minor variations. Some files call it at module level (side effect on import), others call it lazily.
- **Impact:** Changes to env loading logic (e.g., adding a new env source) must be replicated across all files. Inconsistencies exist — `publisher.py` returns `envs` dict, while others use `os.environ.setdefault()`. Module-level side effects in `model_router.py:42` and `narrative_pitcher.py:51` cause env loading even on import.
- **Suggested fix:** Create a single `scripts/env_loader.py` module used by all other scripts via import.

### `load_posted()` / `save_posted()` Duplicated
- **Severity:** Medium
- **Location:** `scripts/threads/db_reader.py` (line 99), `scripts/threads/publisher.py` (line 49)
- **Description:** The JSON file I/O + migration logic for `posted.json` is duplicated in `db_reader.py` and `publisher.py`. `publisher.py` has a simpler version that lacks the `posted_urls` → `posted_links` migration and type normalization.
- **Impact:** Changes to posted.json schema must be updated in both files. `publisher.py` version creates entries that may not match the schema expected by `db_reader.py`.
- **Suggested fix:** Import from `db_reader` in `publisher.py` instead of redefining.

### D1 Query Logic Duplicated (npx wrangler CLI)
- **Severity:** Medium
- **Location:** `scripts/threads/db_reader.py` (line 127), `scripts/auto_news_selector.py` (line 38), `scripts/auto_briefing.py` (line 34)
- **Description:** Three independent implementations of `d1_query()` that shell out to `npx wrangler d1 execute --remote --command`. Each has slightly different retry/error handling:
  - `db_reader.py`: 2 retries, 5s delay, 120s timeout, regex-based JSON extraction
  - `auto_news_selector.py`: 2 retries, no delay, 60s timeout, same regex extraction
  - `auto_briefing.py`: no retries, 60s timeout (named `d1_execute`)
- **Impact:** Each pipeline step has different failure behavior. Debugging D1 issues requires checking 3 different query wrappers.
- **Suggested fix:** Create a shared `scripts/d1_client.py` module.

### Massive Single Modules (1,013 + 581 lines)
- **Severity:** High
- **Location:** `scripts/threads/v3/writer_v3.py` (1,013 lines), `scripts/threads/v3/narrative_pitcher.py` (581 lines)
- **Description:** `writer_v3.py` bundles prompt construction (~160 lines of prompt strings), crawling, humanization (10-class AI-tone taxonomy), fix_cards (2 LLM calls), keyword validation, year hallucination detection, card assembly, and more — all in one file. `narrative_pitcher.py` has similar sprawl.
- **Impact:** Extremely difficult to reason about. Changes to one concern (e.g., keyword validation regex) risk breaking unrelated concerns (card assembly, crawling). Single-file changes cause large git diffs.
- **Suggested fix:** Split into modules: `prompt_builder.py`, `crawler.py`, `humanizer.py`, `card_validator.py`, `card_fixer.py`, `assembler.py`

### 16 Backup Files + 100+ `.bak` Files
- **Severity:** Medium
- **Location:** Root `backup_*.txt` (16 files), 100+ `.bak` files across `scripts/`, `src/`, `api_test/`
- **Description:** Root directory has 16 timestamped backup_YYYYMMDD_HHMMSS.txt files totaling unknown but significant size. The codebase has over 100 `.bak` files scattered through every directory — some in active source dirs like `scripts/threads/v3/narrative_pitcher.py.bak` through `.bak4`, `writer_v3.py.bak`, `writer_v3.py.bak2`. Admin index page alone has 5 `.bak` files.
- **Impact:** Repository bloat. Increases clone size, confuses developer navigation. Some `.bak` files are in directories that are actively worked on, creating risk of editing the wrong file.
- **Suggested fix:** Remove all `.bak*` files and backup_*.txt from git. Add stricter gitignore patterns. Use git for history instead of manual backups.

### `format_selector.py` Is Now a No-Op Wrapper
- **Severity:** Low
- **Location:** `scripts/threads/v3/format_selector.py` (22 lines total)
- **Description:** After A/B/C format removal, `select_format()` unconditionally returns `('D', 'D 형식 고정')`. But it still maintains the full interface, logging, and is called from `writer_v3.py:604-606` with a fallback path.
- **Impact:** Dead code path. The `format_choice` parameter and `FORMAT_BUILDERS`/`FORMAT_LABELS`/`FORMAT_CARD_COUNTS` dictionaries in writer_v3.py now only hold 'D' entries but the full dispatch machinery remains.
- **Suggested fix:** Remove `format_selector.py`. Remove format dispatch logic from `write_thread()`. Inline only D-format code.

### `deploy.sh` References Wrong Project's `.env`
- **Severity:** High
- **Location:** `scripts/deploy.sh` (line 26-27)
- **Description:** Deploy script loads `CLOUDFLARE_API_TOKEN` from `/Users/twinssn/Projects/5000/.env` — a completely different project. If that project is deleted, moved, or its .env changes, deployment breaks.
- **Impact:** Deployment pipeline is coupled to a separate project's configuration. Breaks silently if that project's env changes.
- **Suggested fix:** Source Cloudflare credentials from the current project's `.env` or `~/.env.common`.

### Duplicated LLM Call on JSON Parse Failure in `narrative_pitcher.py`
- **Severity:** Low-Medium
- **Location:** `scripts/threads/v3/narrative_pitcher.py` (lines 375-398)
- **Description:** When the first GPT call's output fails JSON parsing, the code makes a second identical LLM call with the exact same prompt. This doubles cost and latency for parse failures.
- **Impact:** Wastes OpenAI API credits. Adds ~5-10s latency on failures.
- **Suggested fix:** Retry with `temperature=0.3` and/or `response_format={ "type": "json_object" }` instead of duplicating the same call.

---

## Security Concerns

### `SESSION_SECRET` Falls Back to Empty String Silently
- **Severity:** High
- **Location:** `src/middleware.ts` (lines 17-20)
- **Description:** `context.locals.sessionSecret` is set to `runtime?.env?.SESSION_SECRET || ''`. If SESSION_SECRET is missing, it silently falls back to empty string with only a `console.warn`. HMAC-signed sessions in `src/lib/auth.ts:6` will throw `Error('SESSION_SECRET is not configured')` when actually used.
- **Risk:** Admin API routes (`src/pages/api/admin/grant.ts`) use `verifySession()` which catches all errors and returns `false` — so an unconfigured SESSION_SECRET means ALL admin access is denied. Worse, the `/api/admin/grant.ts` returns `500` with `db_unavailable` masking the real issue.
- **Current mitigation:** HMAC signature verification will fail on empty secret, effectively blocking access.
- **Recommendations:** Fail fast during startup if SESSION_SECRET is unset. Use a validation middleware that returns 500 immediately.

### Threads Access Token Logged in Output
- **Severity:** Medium
- **Location:** `scripts/threads/token_refresh.py` (line 57)
- **Description:** After refreshing the Threads API token, `print(f'  🔑 {new_token[:40]}...')` outputs the first 40 characters of the access token to stdout. If logs are captured or shared, this leaks partial credentials.
- **Risk:** Partial token exposure. 40/160+ characters is sufficient for token fingerprinting and potential abuse.
- **Current mitigation:** Only first 40 chars, and output goes to local console.
- **Recommendations:** Remove token from console output entirely. Only log "Token refreshed successfully (expires N days)".

### API Endpoints Leak Internal Error Details in DEV
- **Severity:** Medium
- **Location:** `src/pages/api/admin/grant.ts` (lines 56, 120), and likely other API routes
- **Description:** Error responses use `import.meta.env.DEV ? e.message : 'Internal Server Error'`, leaking stack traces and internal details when deployed in development mode.
- **Risk:** If a Cloudflare Worker is accidentally deployed with `NODE_ENV=development`, internal error messages (SQL, variable values, paths) become visible to API callers.
- **Current mitigation:** Production deployments use `NODE_ENV=production` which masks details.
- **Recommendations:** Use `import.meta.env.PROD` check instead. Never expose raw error messages.

### D1 Database ID Hardcoded in `wrangler.toml`
- **Severity:** Low-Medium
- **Location:** `wrangler.toml` (line 8)
- **Description:** `database_id = "bec650ce-f732-46bc-87c0-bd76ed17e42a"` is hardcoded in plaintext in a committed config file.
- **Risk:** Anyone with repo access has the D1 database ID. While D1 requires auth to access, the ID itself is an attack surface for enumeration.
- **Recommendations:** Use `wrangler.toml` with environment-specific values or secret bindings.

### `.env` Parsing Loaded from Multiple Sources
- **Severity:** Low
- **Location:** All Python `load_env()` implementations across 5+ files
- **Description:** The duplicated `load_env()` reads from `~/.env.common`, `.env`, AND `api_test/.env.sh`. The `.env.sh` file is gitignored now but has a history in the repo.
- **Risk:** Historical exposure of env vars in git. The loading of `.env.sh` is a legacy pattern that should be removed.
- **Recommendations:** Remove `api_test/.env.sh` from env loading. Only use `.env` and optionally `~/.env.common`.

---

## Performance Issues

### 2-3 LLM Calls Per Write Operation
- **Severity:** High
- **Location:** `scripts/threads/v3/writer_v3.py` — `write_thread()` (line 597), `humanize_cards()` (line 357), `fix_cards()` (line 531)
- **Description:** Every Threads write triggers a cascade of LLM calls:
  1. LLM call for initial thread generation (`write_thread`, ~5s)
  2. LLM call for humanization (`humanize_cards`, ~5s)
  3. LLM call for fix_cards (`fix_cards`, ~5s) — but `fix_cards()` already calls `humanize_cards()` internally (line 540), so humanization runs *twice*
- **Impact:** ~15-20 seconds per thread generation. If a thread fails validation, the entire 2-attempt cycle runs, doubling cost. Each pipeline run costs ~$0.10-0.20 in GPT-4o-mini API fees.
- **Suggested fix:** Remove the redundant `humanize_cards()` call inside `fix_cards()` (it's already called at line 540). Merge humanization and fix into a single LLM call with combined instructions. Consider eliminating `fix_cards` entirely since the model outputs are already post-processed with regex cleanup.

### Serial Crawling with Sequential `validate_link()` Calls
- **Severity:** Medium
- **Location:** `scripts/threads/v3/writer_v3.py` (lines 668-689), `scripts/threads/db_reader.py` (line 58)
- **Description:** For each related article, the pipeline first calls `validate_link()` (a synchronous HTTP GET) and then `fetch_article_body()` (another synchronous GET). These run sequentially in a loop.
- **Impact:** If 5 related articles need crawling, minimum latency is 5×(8s+15s) = ~115 seconds before writing even begins.
- **Suggested fix:** Use `concurrent.futures.ThreadPoolExecutor` to crawl articles in parallel. Or better, pre-crawl and store article bodies in D1.

### `narrative_pitcher` Processes Batches Serially
- **Severity:** Medium
- **Location:** `scripts/threads/v3/narrative_pitcher.py` (lines 354-403)
- **Description:** Each batch of 200 articles is sent to GPT sequentially in a `for` loop. With 600 articles max, that's 3 sequential GPT calls before pitch evaluation even begins.
- **Impact:** ~30-45 seconds of serial LLM API latency.
- **Suggested fix:** Use `asyncio` or `ThreadPoolExecutor` to process batches in parallel.

### No Caching Layer
- **Severity:** Medium
- **Location:** Entire system
- **Description:** Every pipeline run issues fresh D1 queries. Every thread generation makes fresh LLM calls. No Redis, no in-memory cache, no query result caching.
- **Impact:** Repeated runs of the pipeline (e.g., during debugging, dry-run) are as expensive as production runs. The daemon mode re-fetches the same articles every 2 hours.
- **Suggested fix:** Add a simple JSON-based cache for D1 query results with a configurable TTL. Use `functools.lru_cache` for pure functions.

### `failed_crawls.json` Grows Unbounded
- **Severity:** Low
- **Location:** `scripts/threads/v3/writer_v3.py` (line 266-282)
- **Description:** Every crawl failure appends to `failed_crawls.json` but no pruning mechanism exists. Duplicate URLs are deduplicated but new failures keep accumulating.
- **Impact:** File grows indefinitely, adding I/O overhead on each write.
- **Suggested fix:** Prune entries older than 30 days on each write. Or keep only the last 100 failures.

---

## Fragile Areas

### `writer_v3.py` — 1013-Line Monolith
- **Location:** `scripts/threads/v3/writer_v3.py`
- **Why fragile:** Single file contains prompt engineering (hardcoded Korean text strings), web crawling logic, LLM orchestration (3 separate calls), complex regex-based validation (year hallucination, keyword truncation, English leakage), card assembly, and draft saving. Any change to one concern risks breaking others.
- **Dependencies:** Called by `main_v3.py:187`. Calls `model_router.chat_completion`, `db_reader.validate_link`, `format_selector.select_format`. Its internal `validate_keywords` has hardcoded Korean stopword list.
- **Test coverage:** ZERO — no unit tests exist for any function in this file.
- **Safe modification:** Always add tests first. Split concerns before making functional changes.

### `narrative_pitcher.py` — Complex Orchestration with Fallbacks Within Fallbacks
- **Location:** `scripts/threads/v3/narrative_pitcher.py`
- **Why fragile:** Three-tier fallback chain (GPT-4o-mini → DeepSeek → MiMo). Batch processing with random shuffling (non-deterministic). JSON parsing across 3 different output schemas. Pitch dedup with 4-phase checking. Re-generation of pitch from crawled body (separate LLM call). The `get_pitches()` function is 258 lines.
- **Dependencies:** Calls `model_router.chat_completion`, `db_reader.normalize_url`, `dedup.is_same_topic`, `writer_v3.fetch_article_body`. Imports from `v3.model_router` which has its own module-level side effects.
- **Test coverage:** ZERO — no unit tests.
- **Safe modification:** Add tests before refactoring. Preserve the dedup order (Phase 1→2→3→4) as it's order-dependent.

### D1 Queries via `npx wrangler` CLI — Shell-Out Pattern
- **Location:** `scripts/threads/db_reader.py` (line 127-156), `scripts/auto_news_selector.py` (line 38-50)
- **Why fragile:** Spawning a subprocess (`npx`) for every query is slow (~1-2s per query), dependent on Node.js/npx being installed, fails silently in environments without wrangler configured, and shell output parsing (regex on stdout) is brittle.
- **Dependencies:** Requires `npx`, `wrangler`, Node.js, and Cloudflare login to be configured on the machine.
- **Test coverage:** Mocked in conftest.py via `monkeypatch_d1` fixture.

### `publisher.py` — Direct `.env` File Mutation
- **Location:** `scripts/threads/publisher.py` (lines 74-82)
- **Why fragile:** Token refresh rewrites `.env` file by reading lines, finding the `THREADS_ACCESS_TOKEN=` line, replacing it inline, and writing the file back. This is a fragile text manipulation that breaks if:
  - The line has `export ` prefix (sometimes present, sometimes not)
  - The line has quotes around the value
  - Multiple definitions exist
  - The file is concurrently modified (daemon race condition)
- **Dependencies:** Threads API availability, network connectivity.
- **Test coverage:** ZERO.

### Deploy Script — Cross-Project Dependency
- **Location:** `scripts/deploy.sh`
- **Why fragile:** Sources Cloudflare credentials from `/Users/twinssn/Projects/5000/.env` — a completely separate project. If that project's directory structure changes, or the env vars are renamed, deployment silently fails.
- **Dependencies:** Existence and validity of `~/Projects/5000/.env`.
- **Safe modification:** Move Cloudflare credentials into this project's `~/.env.common` or a project-specific .env.

---

## Code Quality

### Bare `except:` Blocks Throughout Python Code
- **Severity:** Medium
- **Location:** `scripts/threads/db_reader.py` (line 23 - `load_crawlable_sources`), `scripts/threads/v3/narrative_pitcher.py` (line 172 - `parse_pitches_from_text`, line 320 - `save_pitch_to_history`), `scripts/threads/v3/writer_v3.py` (line 35 - `load_style_examples`)
- **Issue:** Multiple bare `except:` blocks that catch ALL exceptions (including `KeyboardInterrupt`, `SystemExit`). This silently swallows critical errors that should propagate.
- **Severity:** Medium — causes silent failures during debugging and operation.

### No Type Annotations in Python Pipeline
- **Severity:** Low-Medium
- **Location:** All files in `scripts/` except `tests/`
- **Issue:** Zero type annotations across ~4,000 lines of Python code. Function signatures like `def get_articles():` provide no hint about return types. Dictionaries used as ad-hoc structs with string keys everywhere.
- **Impact:** Poor IDE support, difficult refactoring, easy to pass wrong data shapes at runtime.

### Inconsistent JSON Output Parsing (3 Schemas)
- **Severity:** Low
- **Location:** `scripts/threads/v3/narrative_pitcher.py` (lines 136-173, `parse_pitches_from_text`)
- **Issue:** The function handles 3 different JSON schemas from what may be different models (GPT-4o-mini, DeepSeek, MiMo). Schema 2 (DiffusionGemma) and Schema 3 (pitch_id-based) silently produce truncated hook text (only 18 chars) and missing twist/emotion data.
- **Impact:** Different models produce different-quality pitches that get handled inconsistently.

### Hardcoded Personal Information in SEO Component
- **Severity:** Low
- **Location:** `src/components/SEOHead.astro` (lines 52-66, 77)
- **Issue:** Personal name ("조진연"), full address ("호암로 256, 107-1804, 의정부시, 경기도"), and personal email are hardcoded in JSON-LD structured data.
- **Impact:** Privacy concern if repo is made public. Address baked into every page's HTML source.

### Module-Level Side Effects on Import
- **Severity:** Low
- **Location:** `scripts/threads/v3/model_router.py` (line 42 - `load_env()`), `scripts/threads/v3/narrative_pitcher.py` (line 51 - `load_env()`)
- **Issue:** `load_env()` is called at module level, meaning importing these modules triggers file I/O (.env reading, printing to stdout). This breaks testability and causes side effects during import.
- **Impact:** Pytest with `pythonpath = scripts` in `pytest.ini` triggers env loading on every test import.

### `posted.json` Grows Without Bounds
- **Severity:** Low
- **Location:** `scripts/threads/posted.json`, `db_reader.py` (line 99-121)
- **Issue:** `pitch_history` array and `posted_article_meta` dictionary grow with every pipeline run. The `last_reset` field is updated daily but no compaction/archival is done.
- **Impact:** Over months, `posted.json` will grow to megabytes, slowing down every read/write. Semantic Jaccard comparisons against growing `posted_article_meta` become slower over time.
- **Suggested fix:** Implement a sliding window — keep only last 30 days of history/meta, archive older entries.

---

## Missing Features / Gaps

### No Tests for Threads Pipeline
- **Gap:** Zero test coverage for `writer_v3.py` (1,013 lines), `narrative_pitcher.py` (581 lines), `publisher.py` (252 lines), `db_reader.py` (363 lines), `format_selector.py`, `pitch_evaluator.py`
- **Impact:** No safety net for the core content generation pipeline. Changes to prompt templates, validation logic, or crawling behavior cannot be regression-tested.
- **Priority:** High

### `live` Mode for Briefing Scorer Not Activated
- **Gap:** `BRIEFING_SCORER_MODE=live` exists in code but is documented as "Week 4" activation. Currently operates in `dry_run` (tagging only) or `shadow` (tagging + logging) mode.
- **Issue:** The full 2-Pass impact scoring system is not yet in production. Legacy round-robin still used for article selection.
- **Tracking:** `docs/TECH.md` section 8.2, `CHANGES.md` entry 2026-06-30.

### `failed_crawls.json` Never Pruned
- **Gap:** `scripts/threads/v3/writer_v3.py` creates `failed_crawls.json` and appends entries, but no cleanup mechanism exists.
- **Impact:** File grows unbounded.

### `posted.json` History/Meta Compaction
- **Gap:** No archival/pruning strategy for `pitch_history` and `posted_article_meta` in `posted.json`.
- **Impact:** Performance degradation over time and unbounded file growth.

---

## Dependencies & Version Issues

### Stale `wrangler.toml` Compatibility Date
- **Issue:** `compatibility_date = "2024-12-01"` in `wrangler.toml` (line 2)
- **Impact:** Running on a ~7-month-old Workers runtime. Missing newer APIs, bug fixes, and performance improvements.
- **Suggested fix:** Update to current date `2025-07-01` and test for regressions.

### GPT-4o-mini Only — 4o Upgrade Never Done
- **Issue:** Every pipeline step (pitch, evaluation, writing, humanization, fixing) uses `gpt-4o-mini`. The `model_router.py` has infrastructure for GPT-4o but it's never used. The `CHANGES.md` (2026-06-29) lists "4o 전환 검토 필요" as unresolved.
- **Impact:** Models use the cheaper/mini variant for all tasks including complex creative writing. Previous A/B/C format experiments concluded 4o-mini was the limiting factor.
- **Suggested fix:** Evaluate selectively upgrading writing and humanization steps to GPT-4o (higher quality, higher cost).

### `package.json` Dependencies Unpinned
- **Issue:** All dependencies use `^` ranges (e.g., `"astro": "^5.17.1"`). While not a direct bug, it means builds are non-reproducible — `npm install` may pull different patch/minor versions.
- **Impact:** CI and local builds could differ. Use `npm ci` with `package-lock.json` checked in (it exists).

---

## Recommendations

Priority-ordered list:

1. **[HIGH] Remove hardcoded paths** — Extract `PROJECT_DIR` to a shared `scripts/_paths.py` module. This is the single most impactful change for codebase portability and maintainability. Affects every Python file.

2. **[HIGH] Add tests for Threads pipeline** — `writer_v3.py` and `narrative_pitcher.py` have zero test coverage despite being the core revenue-generating pipeline. Start with `validate_cards()`, `validate_year()`, `validate_keywords()` and `is_duplicate_pitch()` — these are pure functions that are easy to unit test.

3. **[HIGH] Remove all `.bak` and `backup_*.txt` files from git** — Add stricter `.gitignore` patterns and clean up the repository. Consider using `git filter-branch` or BFG Repo-Cleaner if history size is an issue (there's already an `aikorea24.bfg-report/` directory suggesting this was attempted).

4. **[HIGH] Split `writer_v3.py` (1,013 lines) into focused modules** — Suggested split: prompt engineering, crawling, humanization, validation, card assembly. This reduces regression risk for future changes.

5. **[MEDIUM] Consolidate `load_env()` into a single module** — Create `scripts/env_loader.py` and import everywhere. Eliminate module-level side effects.

6. **[MEDIUM] Consolidate `d1_query()` into shared module** — Create `scripts/d1_client.py` with consistent retry/timeout behavior. Use by all pipeline scripts.

7. **[MEDIUM] Fix `deploy.sh` to source credentials from this project** — Remove the cross-project dependency on `/Users/twinssn/Projects/5000/.env`.

8. **[MEDIUM] Eliminate redundant LLM calls** — Remove the double `humanize_cards()` call in `fix_cards()`. Consider merging humanization and fixing into a single optimized prompt.

9. **[MEDIUM] Increase coverage for the Briefing pipeline** — Only 3 test files exist for ~1,200 lines of scoring/selection code. Add tests for edge cases in `_two_pass_selection()` and `cluster_by_topic()`.

10. **[LOW] Remove dead format selector code** — After A/B/C format removal, `format_selector.py` and format dispatch in `writer_v3.py` are dead weight.

11. **[LOW] Add posted.json compaction** — Implement sliding window (keep 30 days) for `pitch_history` and `posted_article_meta`.

12. **[LOW] Update `wrangler.toml` compatibility_date** — Update to the current Workers runtime and test for regressions.

---

*Concerns audit: 2026-06-30*
