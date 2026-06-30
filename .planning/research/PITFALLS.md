# Domain Pitfalls: Python Automation Pipeline Refactoring

**Project:** aikorea24.kr — Korean AI news pipeline (Python monolith)
**Researched:** 2026-06-30
**Mode:** Ecosystem (pitfalls dimension)
**Downstream consumer:** Roadmap planning — each pitfall maps to a phase that should address it

> **Before reading:** This is not generic refactoring advice. Every pitfall below is grounded in the specific structure of this project's codebase (16+ Python scripts, 2× 1000+ line modules, hardcoded paths in every file, module-level side effects, launchd scheduling with embedded secrets, zero test coverage in core pipeline).

---

## CRITICAL PITFALLS

Mistakes that cause pipeline outages, data corruption, or security incidents.

---

### Pitfall 1: Refactoring Without Characterization Tests First

**What goes wrong:** You split `writer_v3.py` (1,013 lines) into modules. The new code passes type checks and imports cleanly. But the threads that get published now have subtly different card formatting, different keyword validation, or different error fallback behavior. You don't notice until a reader complains about broken Korean phrasing.

**Why it happens:** The project has zero test coverage for `writer_v3.py`, `narrative_pitcher.py` (581 lines), `publisher.py`, `db_reader.py`, and `main_v3.py`. Only 3 test files exist (`test_crawl_sources.py`, `test_email_send.py`, `test_model.py`), none covering the core Threads pipeline. You cannot safely refactor code whose behavior you can't measure.

**Consequences:**
- Silent behavior drift: same inputs → different outputs after refactoring
- Korean-language-specific regressions (year hallucination validation, keyword truncation, English leakage detection)
- LLM cost changes if prompt structure accidentally changes
- Trust erosion: readers notice quality changes, maintainer loses confidence in the pipeline

**Prevention (concrete steps):**

1. **Write characterization tests first** — Before touching a single line of `writer_v3.py`, capture its current output for known inputs:
   ```python
   # tests/test_writer_characterization.py
   def test_write_thread_characterization():
       """Capture current output shape — do NOT assert correctness yet."""
       from scripts.threads.v3.writer_v3 import write_thread
       result = write_thread(sample_article, format_choice='D')
       # Snapshot: card count, structure, keywords present
       assert len(result) == EXPECTED_CARD_COUNT  # starts as known value
       assert all(isinstance(c, str) for c in result)
       # Save full output for diff comparison
   ```

2. **Use snapshot/approval testing** — `pytest-snapshot` or `syrupy` to freeze current outputs. After refactoring, review diffs deliberately.

3. **Start with pure functions** — `validate_keywords()`, `validate_year()`, `validate_cards()`, `is_duplicate_pitch()` are all pure functions with clear inputs/outputs. These are trivial to characterize-test and give the highest safety-per-test-line ratio.

4. **Do not refactor until at least the pure functions are under test.** The refactoring will introduce bugs — the question is whether you catch them before deploy.

**Phase mapping:** Should be the FIRST phase (before any code changes). Phase "REF-04: modularize pipeline" MUST require characterization tests as a prerequisite. Add to definition of done for all refactoring tasks.

**Warning signs:**
- You're making structural changes to a file that has no `test_` file in the repository
- You can't name the 3 most important behaviors that must be preserved
- PR description says "same behavior, just moved code" without test evidence

---

### Pitfall 2: Breaking the Running Pipeline Mid-Refactoring (No Rollback Plan)

**What goes wrong:** You extract `d1_query()` into a shared module. Three scripts import the new module. The extraction has a subtle difference — the retry timing changed from `time.sleep(5)` to `time.sleep(3)`. Or the regex for JSON extraction from `npx wrangler` output stopped matching when the output format varied. The 2-hour launchd cron fires, the pipeline errors on the first D1 query, and the day's news never gets processed.

**Why it happens:** The pipeline runs every 2 hours via launchd (`threads-publisher.plist`). There is no staging environment. Changes are made directly on the production machine. There is no CI/CD, no canary, no rollback button. A broken import means a broken pipeline for 2+ hours until the next fix.

**Consequences:**
- Missed news cycle (2+ hours of downtime minimum)
- The `main_v3.py` error handling catches broad exceptions but logs to a file that's checked "when something feels wrong"
- Telegram alerts exist but only for explicit `send_telegram()` calls — not all failure modes are wired
- If the pipeline partially runs (articles fetched but thread not published), `posted.json` state becomes inconsistent

**Prevention:**

1. **Parallel-run pattern** — Leave the old pipeline running while building the new one in a separate directory:
   ```
   scripts/
     threads/         # OLD — keep running during refactoring
     threads_v4/      # NEW — build alongside
     shared/           # Extracted modules used by both
   ```
   Only switch the launchd plist to point at the new entry point after it has proven itself.

2. **Shadow execution** — Run the new pipeline in `--dry-run` mode for 3+ cycles while the old pipeline keeps publishing. Compare outputs. Only cut over when behavior parity is confirmed.

3. **Rollback script** — Before making any changes, create a one-command rollback:
   ```bash
   # rollback.sh — restore previous pipeline state
   git checkout HEAD~1 -- scripts/threads/
   # or use symlink swap:
   ln -sfn /path/to/threads_old /path/to/threads_active
   ```

4. **Launchd plist is a deployment artifact** — The plist at `scripts/threads/threads-publisher.plist` is NOT just documentation. It IS the deployment configuration. Any refactoring that changes entry points, venv paths, or environment variables must update the plist. Keep an old-version plist as rollback.

**Phase mapping:** Every phase must include "rollback plan" in its definition of done. Phase "REF-01: remove hardcoded paths" should start with creating the shadow/parallel-run structure.

**Warning signs:**
- You can't answer "how do I undo this change in 30 seconds?"
- You're editing files that are currently loaded by the running Python process
- The last `git log` for the files you're changing is `git commit --allow-empty`

---

### Pitfall 3: Consolidating `load_env()` Without Accounting for Behavioral Differences

**What goes wrong:** You create `scripts/env_loader.py` with a single `load_env()` function. You replace all 5+ copies with `from env_loader import load_env`. But:
- `publisher.py` version returned `envs` dict (callers used `envs['KEY']`)
- `model_router.py` version used `os.environ.setdefault()` (doesn't overwrite existing)
- `narrative_pitcher.py` version called `load_env()` at module level (side effect on import)

**Why it happens:** The 5+ copies of `load_env()` are NOT identical. They have subtle behavioral differences. The `publisher.py` version returns the env dict explicitly — some callers depend on this return value. The `db_reader.py` variant is structured differently. Consolidating them into one function changes behavior for callers that relied on the differences.

**Consequences:**
- Environment variables missing in production because the consolidated version doesn't set defaults the same way
- Scripts that previously got env vars via return value now get them via `os.environ` — but the `chat_id` fallback logic in `send_telegram()` checks `os.environ.get()` which may not be populated the same way
- **Security regression:** If the unified `load_env()` is stricter about which files it reads, a previously-working API key stops loading

**Prevention:**

1. **Audit every copy before consolidating.** For each of the 5+ `load_env()` implementations, document:
   - What files does it read? (`.env`, `~/.env.common`, `api_test/.env.sh`)
   - In what order?
   - Does it use `os.environ[key] = value` or `os.environ.setdefault(key, value)`?
   - Does it return a dict?
   - When is it called — at module level or inside a function?

2. **Create the unified version as a superset** — The union of all behaviors, with explicit configuration:
   ```python
   # env_loader.py
   def load_env(return_dict=False, module_level=False):
       """Single source of truth for env loading.
       
       Args:
           return_dict: If True, return env dict (backward compat for publisher.py)
           module_level: If True, log a deprecation warning (discourage module-level calls)
       """
   ```

3. **Migration path** — Do NOT replace all callers at once. Ship the shared module, then migrate one caller at a time, running the pipeline between each migration.

**Phase mapping:** Phase "SEC-02" (centralized secrets management) is where this lives. Split it into sub-steps: (a) audit all copies, (b) create superset version, (c) migrate one by one with testing between each.

**Warning signs:**
- You see "extract common utility" and assume all copies are identical
- You're deleting old `load_env()` functions before the new one is proven in production
- You can't list every file that defines `load_env` from memory

---

### Pitfall 4: Launchd Plist as a Hidden Security and Portability Landmine

**What goes wrong:** You spend days refactoring Python code to remove hardcoded paths, centralize config, and make the pipeline portable. You clone the repo on a new machine and nothing works. Then you check the launchd plist and find:

- `ProgramArguments` contains `/Users/twinssn/Projects/aikorea24/.venv/bin/python3` (hardcoded absolute path to the venv)
- `WorkingDirectory` is hardcoded to the same
- `EnvironmentVariables` has `OPENAI_API_KEY` in PLAINTEXT (committed to git!)
- `PATH` includes `/Users/twinssn/Projects/aikorea24/.venv/bin` (hardcoded)

**Why it happens:** The plist is treated as "infrastructure" separate from "code." The refactoring focuses on Python files. The plist is ignored because "it's just a config file." But the plist IS the production runner — it's what macOS launchd executes. If the plist is wrong, the entire refactored pipeline is unreachable from cron.

**Consequences:**
- **API key exposure in git:** `OPENAI_API_KEY=REDACTED_OPENAI_KEY` is in plaintext in a committed file. This is a severe security violation. The current "REDACTED" string in the plist suggests someone already noticed and manually edited the file — but the original plaintext key is in git history.
- **Zero portability:** The plist references a fixed absolute path to a `.venv` that doesn't exist on any other machine.
- **Python version coupling:** If the refactoring requires a different Python version or venv location, the plist breaks silently.
- **New machine setup requires manual plist editing** — exactly the same problem as hardcoded `PROJECT_DIR` in Python code.

**Prevention:**

1. **Template-ize the plist before refactoring Python code.** Create a `scripts/install_launchd.sh` that generates the plist from environment variables or a config file:
   ```bash
   # install_launchd.sh — generate plist from template
   PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
   VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python3"
   sed "s|{{PROJECT_DIR}}|${PROJECT_DIR}|g; s|{{VENV_PYTHON}}|${VENV_PYTHON}|g" \
       templates/threads-publisher.plist.template > ~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist
   ```

2. **Remove secrets from plist** — Environment variables in plist files are visible to any process that can read the plist (including `launchctl list` output). Use `--env` file or have the Python script source its own `.env`.

3. **Add the plist template to `.gitignore` patterns that catch secrets.** If the template contains placeholders (safe), the generated plist should be gitignored.

4. **Create a `launchd/` directory** with the template, installer script, and uninstaller script. Treat it as a first-class deployment artifact, not an afterthought.

**Phase mapping:** Phase "SEC-01" (security audit) should flag the plist API key. Phase "INF-01" (portability) MUST include launchd template creation. Should be done before or concurrent with "REF-01" (hardcoded paths).

**Warning signs:**
- You search the codebase for "OPENAI_API_KEY" and only find it in Python files (missing the plist)
- The plist hasn't been touched in the same git commits that refactor pipeline code
- "The pipeline runs on my machine" fails on `git clone` + fresh setup

---

## MODERATE PITFALLS

Mistakes that cause developer frustration, wasted time, or subtle bugs.

---

### Pitfall 5: Circular Imports When Splitting `writer_v3.py`

**What goes wrong:** You split `writer_v3.py` (1,013 lines) into `prompt_builder.py`, `crawler.py`, `humanizer.py`, `card_validator.py`, `card_fixer.py`, `assembler.py`. Then you discover that:
- `assembler.py` imports from `card_validator.py`
- `card_validator.py` imports from `humanizer.py` (to check humanization patterns)
- `humanizer.py` imports from `assembler.py` (to use card structure definitions)

Python raises `ImportError: cannot import name 'validate_card_structure' from partially initialized module 'assembler'`.

**Why it happens:** The monolith's internal dependencies are not cleanly layered. Functions call each other freely across concerns. When you separate by "topic" (files for prompts, crawling, validation), you discover that concerns are interleaved — validation functions call card builders, card builders call validation functions. The monolith hid these cycles because everything was in one namespace.

**Consequences:**
- Refactoring stalls while you untangle dependency cycles
- You resort to lazy imports (import inside functions) which PEP 8 discourages and which defer error reporting to runtime
- You create a `utils.py` dumping ground that recreates the monolith problem at module level
- Tests become harder to write because each module requires partial imports or mocking

**Prevention:**

1. **Map the dependency graph BEFORE splitting.** Use `pydeps` or `snakefood` to generate an import graph of `writer_v3.py`'s internal functions:
   ```bash
   pydeps scripts/threads/v3/writer_v3.py --show-deps > writer_v3_deps.svg
   ```
   Identify clusters of functions that form natural modules without cross-dependencies.

2. **Apply the Dependency Inversion Principle** — If module A needs something from module B and vice versa, extract the shared interface into a third module that both import:
   ```
   BAD:
     assembler.py ←→ card_validator.py (circular)
   
   GOOD:
     assembler.py ──→ shared_types.py ←── card_validator.py
     assembler.py ←── card_validator.py (one-way only)
   ```

3. **Select the seam before splitting** — Identify the ONE function that can be extracted cleanly (no internal dependencies). Extract it first. Test. Then extract the next. Do NOT attempt to split the entire file in one session.

4. **Use `TYPE_CHECKING` for type-only circular imports** — This is Python's sanctioned escape hatch:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   
   if TYPE_CHECKING:
       from .assembler import CardStructure  # never loaded at runtime
   ```

**Phase mapping:** Phase "REF-04" (modularize pipeline) must start with `pydeps` analysis, not code editing. Include "resolved circular dependencies" in the definition of done for each module split.

**Warning signs:**
- You're creating more than 3 new files in a single refactoring session
- You start with "let's just move this function to a new file" without checking what it imports
- You get `ImportError` on the first test run after splitting
- You add `import X` inside a function body (lazy import) to make it work

---

### Pitfall 6: Removing Dead Code That's Actually Load-Bearing

**What goes wrong:** You delete `format_selector.py` and the format dispatch logic in `writer_v3.py` because "only D format is used now." Three weeks later, a reader reports that threads are missing their final card. Investigation reveals that the format dispatch was being used as a data-flow control mechanism — it set `NUM_CARDS` which controlled how many articles were included. The D-format branch assumed a specific card count that the underlying pipeline didn't always satisfy.

Or: You delete `backup_*.txt` files and `.bak` files, not realizing one of them contains a manually-edited analysis that the pipeline's `dedup.py` references by path (not caught because the path was hardcoded in a rarely-executed branch).

**Why it happens:** Dead code is rarely "dead" in a codebase without tests. It's usually "code whose purpose is not immediately obvious." Code that appears dead may be:
- A backup of a configuration that the pipeline regenerates but needs as seed
- A format path that handles an edge case (e.g., "no related articles found")
- A fallback that only executes when the primary path fails (exceptions, network errors)

**Consequences:**
- Pipeline fails silently on edge cases that were previously handled
- "It worked on my machine" — because the edge case doesn't trigger in development
- Costly debugging session tracing through git history to find what was deleted
- Restoring from git history is easy, but the trust in the refactoring process is damaged

**Prevention:**

1. **Confirm dead code with logs, not inspection.** Add a log line to suspicious "dead" code paths and run the pipeline for 1 week. If the log never fires, the code is safe to remove:
   ```python
   logger.debug(f"DEPRECATED PATH: {format_choice} format — remove if not seen for 7 days")
   ```

2. **Use `warnings.warn("Deprecated", DeprecationWarning)`** for code you suspect is dead. Run with `-Wd` to see active deprecations.

3. **Backup files (`.bak`, `backup_*.txt`)** — These should NOT be deleted from git history blindly. First check:
   - Are any of them referenced by code paths? (grep for filenames)
   - Do they contain configuration or analysis data not stored elsewhere?
   - Were they created by the user manually? (If yes, ask before deleting)

4. **Mark `format_selector.py` as deprecated but functional first.** Remove the callers, then remove the module. Not the other way around.

**Phase mapping:** Phase "REF-03" (remove dead code) should be done LAST among refactoring phases, after all other behavioral changes are complete and tested. This ensures you're deleting code whose replacement is proven.

**Warning signs:**
- "This code is never called" — verified by grep, but not by runtime log
- Dead code removal is grouped in the same commit as behavioral changes
- You're deleting files because "they look old" rather than because you've confirmed they're unreferenced
- Old backup files contain user-curated data (e.g., manually edited keyword lists)

---

### Pitfall 7: Replacing Module-Level Side Effects Without Updating All Callers

**What goes wrong:** You fix the module-level `load_env()` call in `model_router.py:42` — moving it from module scope to inside functions that need it. Now `from scripts.threads.v3.model_router import chat_completion` no longer loads environment variables. But `writer_v3.py` was relying on that side effect: it imported `model_router` and implicitly got env vars loaded. When `writer_v3.py` runs, `os.environ.get("OPENAI_API_KEY")` returns `None` because no one explicitly called `load_env()`.

**Why it happens:** Module-level side effects create invisible coupling. `model_router.py` calls `load_env()` at import time. Every file that imports `model_router` transitively gets env loading for free. When you remove the side effect, you break the implicit contract that "importing model_router sets up your environment."

**Consequences:**
- API calls fail with authentication errors (missing keys)
- The error manifests not in the import chain but at API call time, making debugging harder
- You fix one file (add explicit `load_env()` call) but miss another
- Tests that import modules transitively start failing because env vars aren't loaded

**Prevention:**

1. **Map the side-effect dependency chain** before touching any module. For each file that has module-level `load_env()`:
   ```bash
   # Find all module-level side effects
   grep -n "load_env()" scripts/threads/v3/*.py | grep -v "def \|if __name__"
   ```
   Then trace every importer of those files:
   ```bash
   grep -r "from.*model_router\|import.*model_router" scripts/
   ```

2. **Replace side effects ONE CALLER AT A TIME.** Strategy:
   - Step 1: Add explicit `load_env()` call to every `main()` function (the entry points)
   - Step 2: Remove module-level `load_env()` from ONE module
   - Step 3: Run the pipeline — if it works, move to next module
   - Step 4: Only when all module-level calls are removed, add a linting rule banning them

3. **Add a deprecation warning** to the module-level `load_env()`:
   ```python
   # In model_router.py
   import warnings
   warnings.warn(
       "load_env() at module level is deprecated. Call explicitly in main().",
       DeprecationWarning,
       stacklevel=2
   )
   load_env()  # keep temporarily for backward compat
   ```

4. **Create a startup checklist module** that entry points call:
   ```python
   # scripts/pipeline_setup.py — single place for all initialization
   def initialize_pipeline():
       load_env()
       setup_logging()
       validate_config()
   ```

**Phase mapping:** Phase "REF-02" (consolidate utilities) should handle this. The deprecation warning approach allows gradual migration across multiple commits.

**Warning signs:**
- You search for `load_env()` and find calls at indentation level 0 (module level)
- Removing a line of code from file A breaks file C (with file B being the middle importer)
- Tests pass in isolation (`pytest test_x.py`) but fail when run as a suite (`pytest`)
- You can't explain "what happens when this module is imported" without reading the file

---

### Pitfall 8: Breaking the `run_pipeline.py` Orchestrator's Import-at-Runtime Pattern

**What goes wrong:** `run_pipeline.py` uses `import auto_news_selector` INSIDE functions (lines 38-40), not at the top of the file. This is deliberate: the orchestrator imports pipeline steps only when they're needed. A refactoring that moves all imports to the top of the file (as PEP 8 conventionally recommends) changes behavior — now ALL pipeline modules are imported on startup, triggering ALL their module-level side effects. The pipeline crashes before running a single step.

**Why it happens:** PEP 8 says "imports should be at the top of the file." A well-meaning refactoring "fixes" the import style without understanding why the original author placed them inside functions. The original pattern was likely a workaround for module-level side effects in the imported modules.

**Consequences:**
- `run_pipeline.py --skip-news --skip-briefing` now still imports those modules (waste, possible errors)
- If an imported module's `load_env()` at module level fails (e.g., file not found), the entire orchestrator crashes before parsing CLI arguments
- Error messages confusing: "ModuleNotFoundError" on startup when the user asked for a subset of pipeline steps

**Prevention:**

1. **Document the import-at-runtime pattern explicitly** — Add a comment at the top of `run_pipeline.py`:
   ```python
   # NOTE: Pipeline modules use import-at-runtime to avoid triggering
   # module-level side effects (load_env, d1_query) on startup.
   # Do NOT move these to module-level imports without fixing the side effects first.
   ```

2. **Don't "fix" this until all module-level side effects are eliminated.** The delayed imports are a symptom, not a cause. Fix the root issue (module-level side effects) first, then consolidate imports.

3. **If fixing early, use lazy module pattern:**
   ```python
   # Allow module-level import without triggering side effects
   import importlib
   
   _auto_news_selector = None
   def get_news_selector():
       global _auto_news_selector
       if _auto_news_selector is None:
           _auto_news_selector = importlib.import_module('auto_news_selector')
       return _auto_news_selector
   ```

**Phase mapping:** Documented in "REF-04" (modularization). Do NOT touch `run_pipeline.py` import style until "REF-02" (module-level side effects) is fully resolved.

**Warning signs:**
- Your refactoring task includes "fix imports to be PEP 8 compliant"
- You move `import` statements from inside functions to the top of the file
- You renamed files without updating the dynamic import paths in `run_pipeline.py`

---

### Pitfall 9: The `schedule` + launchd Dual-Scheduling Race Condition

**What goes wrong:** The pipeline has TWO schedulers:
1. **launchd** fires `main_v3.py --once` every 2 hours
2. **Internal `schedule` library** runs `run_v3()` every 2 hours and `reset_posted_daily()` at midnight (lines 329-335)

If the launchd timer fires while a previous `--once` run is still executing, or if launchd fires the internal scheduler mode and the script stays running, two pipeline instances execute simultaneously. They share `posted.json`, `failed_crawls.json`, and D1 database access. Race conditions corrupt shared state.

**Why it happens:** The two scheduling mechanisms are redundant but neither defends against the other. The `--once` flag prevents the internal scheduler from starting, but doesn't prevent launchd from starting a new instance while the current one runs. The internal `schedule` loop (when used without `--once`) blocks forever and prevents the process from exiting — but launchd's `KeepAlive=false` means it won't restart a running process, so this path is actually safer than `--once`.

**Consequences:**
- Two pipeline instances write to `posted.json` simultaneously → JSON corruption (truncated file, duplicate entries)
- D1 writes from two processes → foreign key violations or duplicate articles
- LLM API double-billing (two processes generating threads from the same articles)
- `failed_crawls.json` gets interleaved writes (partial lines, mixed content)

**Prevention:**

1. **File-level locking** — Use `portalocker` or a PID file to prevent concurrent execution:
   ```python
   # In main_v3.py startup
   import fcntl
   LOCK_FILE = os.path.join(THREADS_DIR, '.pipeline.lock')
   with open(LOCK_FILE, 'w') as f:
       try:
           fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
       except BlockingIOError:
           log("Another pipeline instance is running. Exiting.")
           sys.exit(0)
   ```

2. **Choose one scheduler** — Either use launchd exclusively (with `--once` and lock) or the internal scheduler exclusively (without launchd). Dual scheduling is a bug, not a feature.

3. **Atomic file writes** — `posted.json` writes should use write-to-temp-then-rename pattern:
   ```python
   def save_posted(data):
       tmp = POSTED_FILE + '.tmp'
       with open(tmp, 'w', encoding='utf-8') as f:
           json.dump(data, f, ensure_ascii=False)
       os.replace(tmp, POSTED_FILE)  # atomic on Unix
   ```

4. **Add `flock` to all file operations** if dual scheduling must remain during refactoring.

**Phase mapping:** Phase "MON-01" (pipeline monitoring) should add locking and concurrent-execution detection. Phase "REF-04" (modularization) should resolve the scheduling ambiguity — choose one mechanism.

**Warning signs:**
- `ps aux | grep python` shows two pipeline processes running
- `posted.json` has been truncated (file size is 0 or partial JSON)
- Pipeline logs show overlapping timestamps from parallel runs
- "The pipeline ran twice today" but only one run was expected

---

### Pitfall 10: Incomplete `.env` Migration Creates Shadow Configurations

**What goes wrong:** You consolidate all environment variables into a single `.env` file and create a shared `env_loader.py`. But:
- The load order matters: files later in the list override earlier ones
- The old `api_test/.env.sh` is gitignored but still loaded by the old `load_env()` copies
- `deploy.sh` loads Cloudflare credentials from `/Users/twinssn/Projects/5000/.env` (a different project!)
- The launchd plist has its own `EnvironmentVariables` dict that bypasses all `.env` files
- Token refresh in `publisher.py` writes back to `.env` — mutating the config file at runtime

After refactoring, some scripts use the new shared loader while others still have old copies. The result: a script that previously worked because it loaded from `api_test/.env.sh` now silently gets empty values. Or: the token refresh writes to the old `.env` format but the new loader reads a different format.

**Why it happens:** Environment configuration is fragmented across 4+ locations (multiple `.env` copies, `~/.env.common`, `api_test/.env.sh`, plist, shell scripts). No single source of truth exists. The refactoring creates a new "source of truth" but doesn't verify that all consumers are migrated to it.

**Consequences:**
- API calls fail mysteriously — some keys work, others don't
- `OPENAI_API_KEY` loaded from plist overrides the `.env` value (or vice versa)
- After token refresh, new token is written to `.env` but `env_loader.py` reads from `~/.env.common` → token not found
- Debugging requires checking 5 different places where env vars might be set

**Prevention:**

1. **Audit ALL env var sources BEFORE refactoring.** Create a comprehensive map:
   ```
   Variable            | Sources                              | Winner
   OPENAI_API_KEY      | .env, ~/.env.common, plist           | plist (last loaded)
   THREADS_ACCESS_TOKEN| .env, publisher.py (writes)          | publisher.py (mutable!)
   CLOUDFLARE_API_TOKEN| /Users/.../5000/.env (deploy.sh)     | cross-project (fragile!)
   SESSION_SECRET      | src/middleware.ts, Cloudflare Worker | runtime binding
   ```

2. **Single entry point for all env loading** — `scripts/env_loader.py` is only part of the fix. The `deploy.sh` must also be updated to load from this project's `.env`. The launchd plist must delegate to `.env` instead of inlining variables. The token refresh must write to the same location that `env_loader.py` reads.

3. **Add validation on startup** — `env_loader.py` should validate that ALL expected variables are present:
   ```python
   REQUIRED_VARS = ['OPENAI_API_KEY', 'THREADS_ACCESS_TOKEN', 'THREADS_USER_ID']
   MISSING = [v for v in REQUIRED_VARS if v not in os.environ]
   if MISSING:
       raise RuntimeError(f"Missing required env vars: {MISSING}")
   ```

4. **Remove `api_test/.env.sh` from rotation** — It's gitignored (shadow file) and adds confusion without benefit.

5. **Phase the migration** — Collect all sources first, then switch consumers one by one:
   - Phase A: `env_loader.py` reads ALL sources (union) and logs where each var came from
   - Phase B: Move vars from plist to `.env` (keep plist for PATH only)
   - Phase C: Remove `~/.env.common` after migrating its contents to `.env`
   - Phase D: Fix `deploy.sh` to use project `.env`
   - Phase E: Remove old `load_env()` copies

**Phase mapping:** Split across "SEC-01" (audit all sources), "SEC-02" (centralized secrets), "REF-01" (fix deploy.sh cross-project dependency). MUST include validation step.

**Warning signs:**
- The same environment variable is set in 3+ different places
- You find `source` commands in shell scripts pointing to unrelated project directories
- `.env` file is modified by the pipeline itself (token refresh)
- `env` command shows variables that don't exist in any `.env` file

---

### Pitfall 11: Breaking the Briefly-Tested Briefing Pipeline

**What goes wrong:** The briefing pipeline (`auto_news_selector.py`, `auto_briefing.py`, `briefing_scorer.py`) has some test coverage — it's the only part of the system with actual tests (`conftest.py` with `monkeypatch_d1` fixture). Refactoring the shared `d1_query()` function or the path resolution breaks tests that assumed the old function signatures or import paths. The test fixtures reference old module layouts. After refactoring, the briefing tests fail — and since they were the only tests, the entire test suite becomes red.

**Why it happens:** The existing tests are coupled to the current module structure. `conftest.py` patches `scripts.threads.db_reader.d1_query` specifically. If `d1_query` moves to `scripts.d1_client`, the mock path breaks. The tests were written for the old structure and don't follow the refactored imports.

**Consequences:**
- Test suite goes from "mostly passing" to "all red"
- No safety net for the rest of the refactoring
- Tendency to delete the tests "because they're broken anyway" (losing the only test coverage)
- Briefing pipeline regression goes undetected

**Prevention:**

1. **Abstract the mock target** — Create a test helper that patches the d1_query function regardless of its module location:
   ```python
   # tests/conftest.py
   import scripts.d1_client as d1_target
   
   @pytest.fixture
   def mock_d1():
       with mock.patch.object(d1_target, 'execute_query') as mock_q:
           mock_q.return_value = []
           yield mock_q
   ```
   This way, even if the import path changes, the test helper is the single point of update.

2. **Fix tests BEFORE refactoring the code they test.** When you move `d1_query` to a new module, update the test mock path in the same commit — not a later cleanup.

3. **Keep the old import path working during transition** — Use a deprecation shim:
   ```python
   # In new scripts/d1_client.py
   def execute_query(sql, params=None):
       # ... implementation ...
   
   # In old scripts/threads/db_reader.py
   from scripts.d1_client import execute_query as d1_query
   import warnings
   warnings.warn("d1_query is moved to scripts.d1_client", DeprecationWarning)
   ```
   This allows old tests (and old code) to keep working while you migrate to the new path.

**Phase mapping:** Phase "REF-02" (consolidate d1_query) must include test migration as a mandatory subtask. Definition of done: "all existing tests pass with zero modifications."

**Warning signs:**
- The test file contains hardcoded import paths to the exact module being refactored
- "I'll fix the tests after the refactoring" is in the plan
- `conftest.py` uses `mock.patch('scripts.threads.db_reader.X')` where X is being moved

---

### Pitfall 12: Adding Type Annotations as a Refactoring Prerequisite

**What goes wrong:** As a "prerequisite" to refactoring, you add type annotations to all functions in `writer_v3.py`. This changes 1,013 lines into 1,300 lines with type annotations. The actual refactoring gets delayed because:
- Type annotations reveal hidden complexity (ambiguous return types, Union types, Any usage)
- You spend time debugging type errors instead of structural improvements
- The diff becomes 70% type annotations, 30% actual refactoring — harder to review

**Why it happens:** Type annotations are a best practice. A well-meaning plan includes "add type hints" as a first phase. But in a 1,000+ line untyped monolith, adding types IS a refactoring effort itself — it requires understanding every function's contract, which is exactly the same effort as the structural refactoring.

**Consequences:**
- Refactoring scope doubles (structural + type annotation)
- The diff is enormous, making review impossible
- Type annotation errors mask actual refactoring bugs
- Motivation drops because "refactoring" becomes "adding types to 100 functions"

**Prevention:**

1. **Do NOT add types before refactoring.** Add types AFTER refactoring, when modules are smaller and functions have clearer contracts. A 100-line module is trivial to annotate; a 1,000-line module is painful.

2. **If types are desired, use gradual typing:**
   - Add types only to new files created during the split
   - Add types only to the public interface of each module (exported functions)
   - Leave internal helper functions untyped until the module is stable

3. **Use `pyright` or `mypy` in `--check` mode only on the new modules** — don't try to make the entire existing codebase pass static analysis in one go.

4. **Aim for "no type errors in new/refactored code"** not "100% annotated codebase."

**Phase mapping:** Type annotations belong AFTER "REF-04" (modularization) is complete, as a separate optional phase. Do not combine with structural changes.

**Warning signs:**
- The refactoring plan says "Phase 1: add type hints to all functions"
- You're using `Any` more than 3 times in the first 50 type annotations
- The diff shows more type annotations than logic changes
- You're considering `cast()` to satisfy the type checker during refactoring

---

## MINOR PITFALLS

Mistakes that cause annoyance, wasted effort, or reduced code quality.

---

### Pitfall 13: Forgetting `posted.json` When Refactoring File I/O

**What goes wrong:** You consolidate `load_posted()` and `save_posted()` into a shared module. But `posted.json` has a complex schema migration path — `publisher.py` has a simplified version that doesn't handle the `posted_urls → posted_links` migration. The shared module uses the `db_reader.py` version (full migration). After refactoring, new entries have the correct schema, but old entries are re-migrated on every load (harmless but wasteful).

The REAL danger: the `publisher.py` version writes to `posted.json` during token refresh (a side effect of checking for posted threads). If the refactored version changes HOW it writes (different atomicity, different encoding, different path), and a write collision happens between two pipeline instances, the entire `posted.json` gets truncated.

**Prevention:**
1. Consolidate `load_posted()` FIRST (just the read path), verify it produces identical results to both old versions
2. Then consolidate `save_posted()` with the writer's atomic-rename pattern
3. Add a schema validation that catches incompatible writes
4. Both old and new writers should produce the same JSON structure — verify with a diff

**Phase mapping:** Sub-task of "REF-02" (consolidate utilities). Must include a file-format compatibility test.

---

### Pitfall 14: Refactoring Path Resolution Without Fixing `deploy.sh`

**What goes wrong:** You replace all `PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'` with a shared `scripts/_paths.py` that uses `Path(__file__).resolve().parent.parent`. Now all Python scripts are portable. But `deploy.sh` still does:
```bash
source /Users/twinssn/Projects/5000/.env
```
This is a hardcoded path to a DIFFERENT project. If that project moves, deployment breaks. The Astro build commands in `deploy.sh` may also reference absolute paths.

**Prevention:**
1. Include `deploy.sh` in the path-refactoring scope — not just Python files
2. Replace the cross-project `.env` source with this project's own `.env`
3. Make `deploy.sh` resolve paths relative to its own location: `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
4. Test deploy.sh portability by running it from a symlink or different working directory

**Phase mapping:** Phase "REF-01" (remove hardcoded paths) MUST include shell scripts, not just Python files.

---

### Pitfall 15: The `.bak` File Culling That Erases Work

**What goes wrong:** You run `find . -name '*.bak' -delete` to clean up 100+ backup files. But some `.bak` files contain manual edits that were never merged back to the source files (the developer created the `.bak` as a checkpoint, made experimental changes, and the `.bak` is the only copy of working code). You discover this when trying to restore a deleted feature.

**Prevention:**
1. Before deletion, check: does the `.bak` have a corresponding source file with fewer lines? (indicates the `.bak` may have additions)
2. Check git history of the `.bak` — if it was committed, it has a reason (even if forgotten)
3. Move `.bak` files to an `archived/` directory instead of deleting — gives a grace period before permanent removal
4. Add `*.bak` to `.gitignore` so NEW backups aren't committed. Old ones in git history stay but can be cleaned later with `git filter-branch` if desired

**Phase mapping:** Phase "REF-03" (remove dead code). Move before delete. Add gitignore first.

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| **SEC-01**: Security audit | Pitfall 4 (plist secrets), Pitfall 10 (shadow config) | Audit ALL env sources including plist and deploy.sh before any code changes |
| **SEC-02**: Centralized secrets | Pitfall 3 (load_env differences), Pitfall 10 (incomplete migration) | Superset-first approach; migrate one consumer at a time |
| **REF-01**: Remove hardcoded paths | Pitfall 4 (plist paths), Pitfall 14 (deploy.sh), Pitfall 2 (breaking running system) | Create parallel directory structure FIRST; template-ize plist |
| **REF-02**: Consolidate utilities | Pitfall 3 (load_env), Pitfall 5 (circular imports), Pitfall 7 (side effects), Pitfall 11 (test breakage), Pitfall 13 (posted.json schema) | Characterization tests before extraction; dependency graph before splitting |
| **REF-03**: Remove dead code | Pitfall 6 (load-bearing dead code), Pitfall 15 (bak file data loss) | Log-before-remove confirmation; archive before delete |
| **REF-04**: Modularize pipeline | Pitfall 1 (no tests), Pitfall 5 (circular imports), Pitfall 7 (side effects), Pitfall 8 (import style), Pitfall 12 (premature typing) | pydeps first; single-module-at-a-time; no type annotations during structural changes |
| **MON-01**: Pipeline monitoring | Pitfall 9 (dual scheduling race), Pitfall 2 (no rollback) | File locking; single scheduler decision; alert on lock contention |
| **INF-01**: Portability | Pitfall 4 (plist), Pitfall 14 (deploy.sh) | Template-ize ALL deployment artifacts; create install script |

---

## Sources

| Source | Finding | Confidence |
|--------|---------|------------|
| Codebase analysis (CONCERNS.md, 325 lines) | All pitfall triggers validated against actual code patterns | HIGH |
| `scripts/threads/threads-publisher.plist` | Hardcoded OPENAI_API_KEY in plaintext, hardcoded paths | HIGH (verified in file) |
| `scripts/run_pipeline.py` (import-at-runtime pattern) | Deliberate import-in-function design confirmed | HIGH (verified in file) |
| Acquaint Softtech — "Python Monolith to Microservices" (2026-06) | Microservices trap: technical boundaries instead of business boundaries | MEDIUM (blog, supported by AWS prescriptive guidance) |
| CDGTLMDA — "AI-Powered Monolith Refactoring" (2025-06) | 23 import errors from hidden dependencies; dependency graph prerequisite | MEDIUM (case study, single source) |
| DEV Community — "Modularity Anti-Pattern" (2026-02) | Over-modularization causing illusion of structure, import bloat | LOW (contrarian take, but valid for solo dev context) |
| Understand Legacy Code — characterization testing | Feathers' "legacy code = code without tests" applied | HIGH (established methodology) |
| CircleCI — Migration strategies (2025-04) | Strangler Fig pattern, incremental vs big-bang | HIGH (established pattern) |
| Thoughtworks — Strangler Fig (2025-05) | Shadow operations, parallel run, seam identification | HIGH (established pattern) |
| Facebook Cinder — Lazy imports research | Module-level import side effects as top issue | HIGH (production experience) |
| Martin Fowler — Parallel Change | Parallel run validation before cutover | HIGH (established pattern) |

---

## Open Questions / Needs Deeper Research

1. **`deploy.sh` cross-project dependency** — Need to verify exactly which variables come from `/Users/twinssn/Projects/5000/.env` and whether they exist elsewhere. Current understanding based on CONCERNS.md line 77.

2. **`schedule` library vs launchd contention** — The exact concurrency failure mode needs runtime verification. `ps aux` during pipeline execution would confirm whether `--once` always prevents the internal scheduler from starting.

3. **`posted.json` write patterns** — Need to audit all writers to confirm no raw `open()` + `write()` patterns exist (race condition vulnerability). Currently only `db_reader.py` and `publisher.py` are documented as writers.

4. **Test migration complexity** — Need to read `conftest.py` to understand the existing mock infrastructure before designing the migration strategy for Pitfall 11.
