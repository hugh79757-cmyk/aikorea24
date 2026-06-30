# Phase 5: Dead Code Removal & Final Polish — Research

**Researched:** 2026-06-30
**Domain:** Dead code removal, pipeline polish, Telegram notification fix, bulletin board verification
**Confidence:** HIGH

## Summary

Phase 5 is the final cleanup phase for the aikorea24 pipeline. The project has accumulated significant dead weight across multiple layers: 14 `backup_*.txt` files in the project root, 44 `.bak` files scattered throughout the codebase, standalone scripts that no longer serve a purpose, dead functions in the newly extracted pipeline modules, a broken Telegram notification wrapper, and a `--once` flag that is parsed but never used.

**Primary recommendation:** Split into 3 plans: (1) File cleanup — remove all backup files and abandoned scripts; (2) Dead code removal in pipeline modules + Telegram fix; (3) Bulletin board verification + final verification sweep.

---

## User Constraints

*No CONTEXT.md exists for Phase 5 yet. No locked decisions prior to this research.*

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DED-01 | No backup files (`backup_*.txt`, `.bak` files) remain in the repository | 14 backup_*.txt + 44 .bak files found (Section: Backup/Abandoned File Inventory) |
| DED-02 | No abandoned scripts remain (`patch_*.py`, `test_*.py`, `spotlight_*.sh`, `quick_check.sh`) | 18+ scripts identified (Section: Abandoned Script Inventory) |
| DED-03 | `format_selector.py` is removed after confirming functionality exists in new modules | Returns 'D' always; call site in `writer.py:write_thread()` confirmed (Section: format_selector.py Assessment) |
| DED-04 | Old `main_v3.py` is removed after confirming new structure works in production | Still primary entry point — removal is deferred, not yet safe (Section: main_v3.py Assessment) |
| OBS-06 | Telegram alert fires when pipeline step fails or schedule is missed | `run_pipeline_with_notify.py` wraps wrong entry point; orchestrator has zero Telegram integration (Section: Telegram Alert Status) |
| BRD-01 | Community bulletin board (posts + comments) verified working with refactored pipeline | Board exists in Astro, uses D1; no Python pipeline integration. Verification is a manual check (Section: Bulletin Board Status) |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipeline execution | Backend (Python) | — | `pipeline/orchestrator.py` + `StepRunThreads` |
| Telegram alerts | Backend (Python) | — | Needs integration into orchestrator, not `run_pipeline_with_notify.py` |
| Bulletin board (posts + comments) | Browser / CDN (Astro) | D1 Database | Entirely frontend + API in Astro; separate from Python pipeline |
| Threads publishing | Backend (Python) | — | `scripts/threads/main_v3.py` + `publisher.py` |
| Dead code detection | Codebase (analysis) | — | Static analysis — no runtime component |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3.14 | 3.14 | Pipeline runtime | Existing project constraint |
| Astro | — | Bulletin board frontend | Existing project framework |

### Supporting
No new libraries needed. Phase 5 is removal-only with zero new external dependencies (confirms project constraint).

### Alternatives Considered
No alternatives — this phase is purely removal and verification.

---

## Backup/Abandoned File Inventory

### backup\_\*.txt (14 files — all in project root)

Each is a timestamped backup from early 2026. All safe to delete:

| File | Size (approx) | Date |
|------|--------------|------|
| `backup_20260212_174254.txt` | — | 2026-02-12 |
| `backup_20260213_084152.txt` | — | 2026-02-13 |
| `backup_20260213_114840.txt` | — | 2026-02-13 |
| `backup_20260215_103711.txt` | — | 2026-02-15 |
| `backup_20260216_162817.txt` | — | 2026-02-16 |
| `backup_20260221_102430.txt` | — | 2026-02-21 |
| `backup_20260222_071737.txt` | — | 2026-02-22 |
| `backup_20260222_095838.txt` | — | 2026-02-22 |
| `backup_20260224_080523.txt` | — | 2026-02-24 |
| `backup_20260225_084412.txt` | — | 2026-02-25 |
| `backup_20260226_075903.txt` | — | 2026-02-26 |
| `backup_20260228_134606.txt` | — | 2026-02-28 |
| `backup_20260304_095648.txt` | — | 2026-03-04 |
| `backup_20260312_103452.txt` | — | 2026-03-12 |

### \*.bak files (44 files)

Organized by location:

**Root level (6 files):**
`SOP.md.bak`, `AGENTS.md.bak`, `wrangler.toml.bak`, `README.md.bak`, `CHANGELOG.md.bak`, `astro.config.mjs.bak`

**src/pages/ (17 files):**
Backups of Astro components:
- `src/pages/community/[id].astro.bak`
- `src/pages/chronicle/[...id].astro.bak`
- `src/pages/glossary/[...id].astro.bak`
- `src/pages/news.astro.bak`
- `src/pages/briefing/index.astro.bak`
- `src/pages/briefing/[date].astro.bak`
- `src/pages/blog/category/[cat].astro.bak`
- `src/pages/blog/_backup/[...id].astro.bak`
- `src/pages/blog/_backup/[...page].astro.bak`
- `src/pages/index.astro.bak`
- `src/pages/admin/index.astro.bak`
- `src/pages/tools/[id].astro.bak`
- `src/pages/tools/_backup/index.astro.bak`
- `src/pages/api/briefing/send-email.ts.bak`
- `src/pages/api/briefing/news.ts.bak`
- `src/components/SEOHead.astro.bak`
- `src/components/home/OpenSourceBanner.astro.bak`
- `src/components/home/LatestBlog.astro.bak`
- `src/components/home/SubProjects.astro.bak`

**src/ level (2 files):**
`src/content.config.ts.bak`, `src/layouts/Layout.astro.bak`, `src/env.d.ts.bak`

**Python pipeline backups (11 files):**
- `scripts/threads/v3/narrative_pitcher.py.bak` through `.bak4` (4 sequential backups)
- `scripts/threads/v3/writer_v3.py.bak`, `.bak2`
- `scripts/threads/v3/pitch_evaluator.py.bak`
- `scripts/threads/writer.py.bak`
- `scripts/threads/db_reader.py.bak`
- `scripts/threads/scorer.py.bak`
- `scripts/dynamic_seed_generator.py.bak`

**Other (3 files):**
- `scripts/seeds.json.bak`
- `public/OG-1.webp.bak`
- `src/content/blog/2026-06-11-004-중국이-chatgpt로-미국-ai-여론을-조작했다-openai-위협.md.bak`
- `scripts/threads/v3/narrative_pitcher.py.bak2` through `.bak4`
- `naver_blog/cookie_monitor.py.bak`

---

## Abandoned Script Inventory

### patch\_\*.py (2 files)
| File | Description | Verdict |
|------|-------------|---------|
| `patch_footer.py` | One-off migration tool | REMOVE |
| `patch_existing.py` | One-off migration tool | REMOVE |

### test\_\*.py outside tests/ (3 files)
| File | Description | Verdict |
|------|-------------|---------|
| `scripts/test_crawl_sources.py` | Ad-hoc crawl test | REMOVE (one-off) |
| `scripts/test_email_send.py` | Ad-hoc email test | REMOVE (one-off) |
| `scripts/threads/v3/test_model.py` | Model test script | REMOVE (ad-hoc, not pytest) |

### spotlight\_\*.sh (4 files)
| File | Description | Verdict |
|------|-------------|---------|
| `spotlight_exclude.sh` | macOS Spotlight exclusion | REMOVE |
| `spotlight_verify.sh` | Spotlight verification | REMOVE |
| `spotlight_check2.sh` | Spotlight check variant | REMOVE |
| `spotlight_check.sh` | Spotlight check | REMOVE |

### quick_check.sh (1 file)
| File | Description | Verdict |
|------|-------------|---------|
| `quick_check.sh` | One-off health check | REMOVE |

### Standalone Python utilities (no callers in current pipeline)

| File | Description | Verdict |
|------|-------------|---------|
| `scripts/threads/scorer.py` | Legacy scoring — not imported by any current code | REMOVE |
| `scripts/threads/enricher.py` | Cluster enrichment — only imported by archived scripts | REMOVE |
| `scripts/threads/validator.py` | Standalone 8-card validator — duplicates `pipeline/threads/validator.py` | REMOVE |
| `scripts/threads/backfill_meta.py` | One-time posted_article_meta backfill | REMOVE |
| `scripts/threads/run_dry.py` | Debug dry-run loop wrapper | REMOVE |

### Shell scripts (abandoned)

| File | Description | Verdict |
|------|-------------|---------|
| `scripts/threads/run_loop.sh` | Debug dry-run loop | REMOVE |

### Archived scripts (6 files)

| File | Description | Verdict |
|------|-------------|---------|
| `scripts/threads/archived/main.py` | v1 main | REMOVE |
| `scripts/threads/archived/main_v2.py` | v2 main | REMOVE |
| `scripts/threads/archived/scorer_v2.py` | v2 scorer | REMOVE |
| `scripts/threads/archived/writer.py` | v1 writer | REMOVE |
| `scripts/threads/archived/writer_v2.py` | v2 writer | REMOVE |
| `scripts/threads/archived/db_reader_v2.py` | v2 db_reader | REMOVE |

### Prompts (already cleaned in Phase 3 but legacy remains)

| File | Description | Verdict |
|------|-------------|---------|
| `scripts/threads/prompts/prompt_00_selector.md` | Format A/B/C/D selector guide — no longer applies (only D exists) | REMOVE (format_selector.py also simplified to always return D) |
| `scripts/threads/prompts/prompt_rules.md` | General writing rules — already inlined in `build_system_prompt_D()` | REMOVE |
| `scripts/threads/prompts_legacy/prompt_rules.md` | Legacy rules | REMOVE |
| `scripts/threads/prompts_legacy/prompt_00_selector.md` | Legacy selector | REMOVE |

### Generated plist (replaced by template)

| File | Description | Verdict |
|------|-------------|---------|
| `scripts/threads/threads-publisher.plist` | Hard-coded plist (generated). Template exists at `.template` | REMOVE |

---

## format\_selector.py Assessment

**File:** `scripts/threads/v3/format_selector.py` (26 lines)

**What it does:**
- Exports `select_format(pitch, all_articles)` function
- Since 2026-06-29 (A/B/C format removal), it **always returns** `('D', 'D 형식 고정')` — no LLM call, no logic

**Call sites:**
- `pipeline/threads/writer.py:write_thread()` — line 522-526:
  ```python
  from v3.format_selector import select_format
  if not format_choice or format_choice != 'D':
      fmt, reason = select_format(pitch, all_articles)
      format_choice = fmt
  ```

**Verdict:** The function's return value is constant. The import and call can be replaced with a simple `format_choice = 'D'` in `write_thread()`. Once that's done, `format_selector.py` can be safely removed.

**Risk:** None. The function always returns `'D'`, and the caller's `if` block would never select anything else since only format D exists.

---

## main\_v3.py Assessment

**File:** `scripts/threads/main_v3.py` (345 lines)

**What it does:** Primary pipeline entry point. Called by `StepRunThreads` → `subprocess.run([VENV_PYTHON, OLD_SCRIPT, "--once"])`.

**Dead code identified:**

| Item | Lines | Description | Verdict |
|------|-------|-------------|---------|
| `--once` flag | 333 | Parsed but never checked in `run_v3()` | REMOVE the flag |
| `load_env()` function | 102-124 | Redundant — `EnvConfig().load_to_environ()` already called at module init | REMOVE |
| `reset_posted_daily()` | 126-137 | Never called from anywhere in codebase | REMOVE |
| `send_telegram()` function | 31-47 | Used but should be integrated into orchestrator instead | DEFER removal (fix alert mechanism first, see Telegram section) |
| `validate_final_cards()` function | 49-100 | Used — called in `run_v3()` at line 205 | KEEP |
| `db_reader` import pattern | 153 | Imports from `db_reader` (scripts/threads), not `pipeline.infra.d1_client` | KEEP (Strangler Fig) |

**Key question — Can main_v3.py be removed?**

**NO — not yet.** The `StepRunThreads` step still calls `main_v3.py --once` as a subprocess. The pipeline runs via launchd every 2 hours. Removing `main_v3.py` would require:
1. Wrapping its functionality directly into the orchestrator step (no subprocess)
2. Confirming the new structure works in production (shadow-run validated per DED-04)

The Strangler Fig strategy means `main_v3.py` stays until the orchestrator fully absorbs it. Phase 5 should:
- Fix the `--once` dead flag
- Remove `load_env()` (already redundant with `EnvConfig`)
- Remove `reset_posted_daily()` (dead code)
- But keep the file itself — removal is a deferred goal for a future phase

---

## Telegram Alert Status

### Current state (broken)

Three separate Telegram mechanisms exist:

**1. `run_pipeline_with_notify.py`** — PRODUCTION USE, BROKEN
- Wraps `run_pipeline.py` (the briefing pipeline: news → briefing → thumbnails → email → deploy)
- **Problem:** The launchd pipeline actually runs `main_v3.py` (Threads publishing), NOT `run_pipeline.py`. So this wrapper watches the wrong pipeline.
- Confirmed by `install_launchd.sh`: the plist template generates `SCRIPT_PATH='$PROJECT_DIR/pipeline/__main__.py'`, which runs `StepRunThreads` → `main_v3.py`
- The `run_pipeline_with_notify.py` file is never invoked by any launchd job

**2. `main_v3.py.send_telegram()`** — PRODUCTION USE, WORKS FOR THREADS
- Inline function sends Telegram on: validation failure, publish failure, max retries exceeded, unexpected exceptions
- This is the only mechanism that actually fires for the Threads pipeline
- **Limitation:** Only covers the Threads step; the orchestrator runs outside this scope

**3. Orchestrator (`pipeline/orchestrator.py`)** — NO TELEGRAM INTEGRATION
- The `PipelineOrchestrator.run()` method records results to D1 but does NOT send Telegram alerts
- When `StepRunThreads` fails (exit code != 0 or exception), the orchestrator just prints to stdout/stderr
- No heartbeat/missed-schedule detection exists anywhere

### What needs to happen (per STATE.md: OBS-06)

The design decision from Phase 1 was:
- **Failure-only Telegram alerts** with step name + error detail
- **Heartbeat monitor** (30min check, 3h miss threshold)

These were intended for the orchestrator, but never implemented there. The fix is:
1. Add Telegram notification to `PipelineOrchestrator` — fire on step failure with step name + error
2. Add heartbeat check to `PipelineOrchestrator` or `__main__.py` — query `pipeline_runs` table, detect missed schedule
3. Remove `run_pipeline_with_notify.py` (wrong approach — wraps wrong entry point)
4. Keep `main_v3.py.send_telegram()` for Threads-specific failures (belt + suspenders)

---

## Bulletin Board Status

### Current implementation

**Frontend (Astro):** `src/pages/community/`
- `index.astro` — Post listing with pagination + category filter
- `[id].astro` — Individual post view (with comments)
- `write.astro` — Create new post
- `review.astro` — Submit tool review

**API:** `src/pages/api/posts/index.ts`
- `GET` — List posts with pagination and comment counts
- `POST` — Create post (requires auth session)

**Database (D1):** Uses `posts` and `comments` tables. SQL queries embedded in the API route.

### Relationship to pipeline

The bulletin board is **entirely independent** of the Python pipeline:
- Astro pages + D1 queries → no Python involvement
- The refactored pipeline (Phase 3-4) moved Python code around but did not touch the community system
- The only connection is `src/pages/api/briefing/send-email.ts` which links to `/community/` in an email template

### BRD-01 verification approach

Since the board has no dependency on the pipeline, BRD-01 is about **verifying it still works after the pipeline refactoring**. This is a manual/integration check:
1. Verify D1 `posts` and `comments` tables exist and are queryable
2. Confirm the API endpoint returns posts correctly
3. Confirm the Astro pages render without errors
4. No pipeline code changes should affect this

---

## Dead Code Inventory in Pipeline Modules

### In `pipeline/threads/writer.py`

| Function | Lines | Status | Reason |
|----------|-------|--------|--------|
| `_FORMAT_COMMON_RULES(examples)` | 198-255 | **DEAD** — defined but never called anywhere | Formerly used by `build_system_prompt_A/B/C()` which were removed in Phase 3. The common rules are now inlined in `build_system_prompt_D()`. Remove function + its comment. |
| `_clean_english_leakage(text)` | 433-436 | **ALIVE** — called from `fix_cards()` | Keep |
| `_fix_korean_particle_spacing(text)` | 440-442 | **ALIVE** — called from `fix_cards()` | Keep |
| `_cleanup_source_attribution(cards)` | 418-430 | **ALIVE** — called from `write_thread()` | Keep |
| `_strip_instruction_leak(text)` | 274-290 | **ALIVE** — called from `humanize_cards()` | Keep |
| `INSTRUCTION_PATTERNS` | 262-271 | **ALIVE** — used by `_strip_instruction_leak()` and `validate_final_cards()` | Keep |

### In `pipeline/threads/validator.py`

| Function | Lines | Status | Reason |
|----------|-------|--------|--------|
| `validate_cards(cards, pitch, format_choice)` | 22-30 | **ALIVE** — called from `write_thread()` | Keep |
| `validate_year(cards, article_body_text)` | 33-59 | **ALIVE** | Keep |
| `validate_keywords(cards, article_body_text)` | 62-104 | **ALIVE** | Keep |
| `validate_thread(content)` | 107-158 | **DEAD** — defined but never called by pipeline code | Legacy 8-card format validator from pre-D-only era. Only imported by `tests/test_validator.py` and `tests/test_characterization_pure_functions.py`. Remove the function; update tests that import it (or delete the test cases). |

### In `scripts/threads/main_v3.py`

| Item | Lines | Status | Reason |
|------|-------|--------|--------|
| `--once` flag | 333 | **DEAD** — parsed but never used in `run_v3()` | Remove the flag argument entirely |
| `load_env()` | 102-124 | **DEAD** — redundant with `EnvConfig.load_to_environ()` | Remove function; module-level `EnvConfig` already loads env |
| `reset_posted_daily()` | 126-137 | **DEAD** — never called | Remove function |
| `send_telegram()` | 31-47 | **ALIVE** — used in run_v3 for failure alerts | Keep until orchestrator handles Telegram |

### In `scripts/threads/v3/format_selector.py`

| Function | Lines | Status | Reason |
|----------|-------|--------|--------|
| `select_format(pitch, all_articles)` | 23-26 | **ALIVE** (will be removed) | Used in `writer.py:write_thread()`. Always returns D. After inlining, remove file. |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Send Telegram alerts | HTTP request from scratch | `urllib.request` (stdlib) or `requests` | Already exists — just fix the wrong entry point. No need to build a new Telegram module. |
| Bulletin board | Python CRUD API | Existing Astro + D1 | Already works — just verify. |

---

## Common Pitfalls

### Pitfall 1: Deleting a file that's still imported at runtime
**What goes wrong:** Removing `main_v3.py` while `StepRunThreads` still calls it via subprocess → pipeline breaks silently at next launchd run.
**How to avoid:** Before removing any file, grep for its import + usage + subprocess calls. Files called via `subprocess.run()` won't show in import searches.
**Warning signs:** Tests pass but night fails.

### Pitfall 2: Deleting test-covered code without updating tests
**What goes wrong:** Removing `validate_thread()` from `validator.py` causes `test_characterization_pure_functions.py` and `test_validator.py` to fail.
**How to avoid:** After removing a function, run `pytest -x` to catch broken imports. Remove or disable the corresponding test cases.
**Warning signs:** `ImportError` on test run.

### Pitfall 3: Breaking the launchd pipeline by touching `main_v3.py`
**What goes wrong:** The production pipeline runs via `launchd` → `pipeline/__main__.py` → `StepRunThreads` → `main_v3.py --once`. If `main_v3.py` is modified incorrectly, the pipeline fails silently (launchd just exits with error code, no human notice).
**How to avoid:** After changes to `main_v3.py`, run `python -m pipeline run --dry-run` and verify output. Install the updated plist and verify with `launchctl list`.
**Warning signs:** No Threads posts for 2+ hours.

### Pitfall 4: Removing `run_pipeline_with_notify.py` before the orchestrator has Telegram
**What goes wrong:** The file is broken, but it's the only Telegram wrapper that exists for the briefing pipeline. Removing it without replacing the functionality loses the only notification mechanism for the briefing pipeline.
**How to avoid:** First add Telegram to the orchestrator, then remove `run_pipeline_with_notify.py`.

---

## Code Examples

### Pattern: Inline format selection in write_thread()

Current (line 521-529 in `pipeline/threads/writer.py`):
```python
from v3.format_selector import select_format

if not format_choice or format_choice != 'D':
    fmt, reason = select_format(pitch, all_articles)
    format_choice = fmt
    _log(f'  🎯 형식 선택: {format_choice} — {FORMAT_LABELS[format_choice]} ({reason})')
```

After (safe to inline since only 'D' exists):
```python
# Only format 'D' exists since A/B/C were removed
if not format_choice:
    format_choice = 'D'
_log(f'  🎯 형식: {format_choice} — {FORMAT_LABELS[format_choice]}')
```

### Pattern: Add Telegram to PipelineOrchestrator

```python
def _send_telegram_failure(self, result: PipelineStepResult) -> None:
    """Send failure-only Telegram alert."""
    import os, json, urllib.request
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return
    
    message = (
        f"❌ <b>Pipeline step failed</b>\n"
        f"Step: {result.step_name}\n"
        f"Error: {result.error or 'exit code != 0'}\n"
        f"Duration: {result.duration_seconds:.1f}s\n"
        f"Run: {result.run_id}"
    )
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass  # Best-effort
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| A/B/C/D 4 format system | D-only format | 2026-06-29 | `_FORMAT_COMMON_RULES()` now dead. `format_selector.py` always returns D. Prompt files A/B/C deleted. |
| `--daemon` internal scheduler | launchd-only scheduling | Phase 3 (2026-06-30) | `--daemon` flag and `schedule` library dependency removed. |
| Monolithic writer_v3.py (1,013 lines) | `pipeline/threads/writer.py` (stratified) | Phase 4 (2026-06-30) | Old `scripts/threads/v3/writer_v3.py` is now a thin re-export wrapper. |
| `run_pipeline_with_notify.py` wraps `run_pipeline.py` | Should wrap orchestrator | Phase 5 (this) | Wrong entry point — wraps briefing pipeline, not Threads pipeline. |

**Deprecated/outdated:**
- `_FORMAT_COMMON_RULES()`: Only made sense when multiple formats existed. With D-only, its rules are now fully inlined in `build_system_prompt_D()`. Remove.
- `validate_thread()`: Validated 8-card format (A/B). With D-only (5 cards), this function validates the wrong thing. Remove.
- `format_selector.py`: Always returns D. Remove after inlining.
- `load_env()` in `main_v3.py`: Redundant with `EnvConfig.load_to_environ()` at module init. Remove.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_FORMAT_COMMON_RULES()` in `pipeline/threads/writer.py` is never called by any code path | Dead Code Inventory | Low — verified by grep. Only exported by old wrapper, never imported. |
| A2 | `validate_thread()` in `pipeline/threads/validator.py` is never called by pipeline code | Dead Code Inventory | Medium — tests still import it. Removing the function will break tests. |
| A3 | `run_pipeline_with_notify.py` is not used by any launchd job | Telegram Alert Status | Medium — if a secondary launchd job calls it, removing it would break alerts for the briefing pipeline. |
| A4 | Bulletin board works independently of pipeline refactoring | Bulletin Board Status | Low — board is pure Astro/D1 with no Python dependency. |

---

## Open Questions (RESOLVED)

1. **[RESOLVED] What launchd jobs are currently loaded?**
   - What we know: `install_launchd.sh` generates `kr.aikorea24.threads-publisher` plist from template, uses `pipeline/__main__.py` as script path
   - What's unclear: Are there any other launchd jobs (e.g., for `run_pipeline_with_notify.py` or the briefing pipeline)?
   - Recommendation: Run `launchctl list | grep aikorea24` to confirm all loaded jobs before removing any files

2. **[RESOLVED] Should we add a heartbeat monitor in this phase?**
   - What we know: A heartbeat monitor was designed in Phase 1 (30min check, 3h miss threshold) but never implemented
   - What's unclear: Is this in scope for Phase 5 (OBS-06 mentions "schedule is missed") or deferred?
   - Recommendation: The requirement says "fixed existing mechanism, not new setup" — so fix the existing mechanism (orchestrator Telegram integration). Heartbeat is a new feature; defer.

3. **[RESOLVED] Is `scripts/threads/token_refresh.py` still useful?**
   - What we know: It refreshes Threads API access tokens. Standalone script, not imported.
   - What's unclear: Is this an operational tool that should stay, or was it a one-time utility?
   - Recommendation: Keep it — token refresh is an operational need that may recur. Not dead code.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All changes | ✓ | 3.14 | — |
| pytest | Test execution | ✓ | — | — |
| `launchctl` | Plist verification | ✓ | macOS | — |
| wrangler | D1 queries | ✓ | — | — |

**Step 2.6: PASSED** — all required tools available.

---

## Validation Architecture

> `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. This section is skipped.

---

## Security Domain

No new security concerns — Phase 5 is removal-only. No new packages installed. No new API integrations.

### Applicable ASVS Categories — None new

All security work was completed in Phase 1 (secret scrubbing, env consolidation, plist hardening).

---

## Proposed Plan Structure

### Plan 05-01: File Cleanup — Remove Backup Files and Abandoned Scripts

**Tasks:**
1. Remove all 14 `backup_*.txt` files from project root
2. Remove all 44 `.bak` files across the project
3. Remove abandoned scripts: `patch_*.py`, `spotlight_*.sh`, `quick_check.sh`
4. Remove test scripts outside `tests/`: `scripts/test_crawl_sources.py`, `scripts/test_email_send.py`, `scripts/threads/v3/test_model.py`
5. Remove standalone dead utilities: `scripts/threads/scorer.py`, `enricher.py`, `validator.py`, `backfill_meta.py`, `run_dry.py`
6. Remove shell scripts: `scripts/threads/run_loop.sh`
7. Remove `scripts/threads/archived/` directory (6 files)
8. Remove old generated plist: `scripts/threads/threads-publisher.plist`
9. Remove legacy prompt files: `prompts/prompt_00_selector.md`, `prompts/prompt_rules.md`, `prompts_legacy/`
10. Remove `scripts/threads/scorer.py.bak`, `scripts/dynamic_seed_generator.py.bak`, `scripts/threads/db_reader.py.bak`
11. Remove `scripts/seeds.json.bak`, `api_test/` backup files

### Plan 05-02: Dead Code Removal + Telegram Fix

**Tasks:**
1. Remove `_FORMAT_COMMON_RULES()` from `pipeline/threads/writer.py` (dead, never called)
2. Remove `validate_thread()` from `pipeline/threads/validator.py` (dead); update tests
3. Remove format_selector.py: inline `select_format()` to return 'D' in `writer.py:write_thread()`
4. In `main_v3.py`: remove `--once` flag parsing, `load_env()`, `reset_posted_daily()` (dead)
5. Add Telegram failure notification to `PipelineOrchestrator` (on step failure)
6. Remove `run_pipeline_with_notify.py` (wrong entry point — replace with orchestrator integration)
7. Verify 173+ tests still pass after changes
8. Run `python -m pipeline run --dry-run` to verify orchestrator still works

### Plan 05-03: Bulletin Board Verification + Final Sweep

**Tasks:**
1. Verify D1 `posts` and `comments` tables exist
2. Verify `GET /api/posts` endpoint returns correct data
3. Verify community pages render without errors (`/community/`, `/community/[id]`)
4. Run full `pytest` suite — ensure 173+ tests pass
5. Run `python -m pipeline status` to verify D1 pipeline_runs table health
6. Run `python -m pipeline run --dry-run` to verify orchestrator
7. Launchd plist verification: ensure installed plist matches template
8. Verify `install_launchd.sh` can regenerate plist correctly

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase grep] — All grep-based findings in this research were performed against the actual codebase
- [VERIFIED: file inspection] — All file contents read directly from disk

### Secondary (MEDIUM confidence)
- [CITED: CHANGES.md] — Phase 3 WR-01 (`--once` dead flag) noted in changelog
- [CITED: STATE.md] — "Telegram alerts not firing" noted in blockers

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All existing libraries, no new additions
- Architecture: HIGH — File relationships verified by grep
- Pitfalls: HIGH — Based on Python + launchd production experience
- Backup/abandoned file inventory: HIGH — All files physically present on disk

**Research date:** 2026-06-30
**Valid until:** Stable — no fast-moving dependencies
