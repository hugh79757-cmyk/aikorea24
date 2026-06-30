# Research Summary: aikorea24.kr Pipeline Refactoring

**Project:** AI코리아24 (aikorea24.kr)
**Domain:** Python automation pipeline restructuring
**Researched:** 2026-06-30
**Confidence:** HIGH (codebase-verified across all 4 research dimensions)

> Synthesized from 4 research dimensions: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

---

## Executive Summary

The aikorea24.kr Python pipeline is a **monolithic sequential orchestrator** with 16+ scripts duplicating the same infrastructure code (hardcoded `PROJECT_DIR` in 11 files, 5+ `load_env()` implementations, 3 `d1_query()` implementations, 2 `load_posted()` implementations). It works in production but is non-portable, untestable, and has a security incident waiting to happen (API keys in plaintext in a committed launchd plist). The Threads pipeline has two 1000+ line monoliths (`writer_v3.py` at 1,013 lines, `narrative_pitcher.py` at 581 lines) with module-level side effects that make testing impossible and import order fragile.

**The recommended approach is a Strangler Fig migration** — create shared infrastructure modules first (zero behavioral change), then wire each old file to import from shared modules, then restructure the directory layout, and finally split the monoliths. This is NOT a greenfield rewrite. The consensus across all 4 research documents is unanimous: no new external dependencies (Python 3.14 stdlib suffices), no orchestration framework (Airflow/Prefect/Kedro are all overkill), no async/await, no abstract base classes, no dependency injection framework. The entire refactoring is achievable with stdlib dataclasses, functools.lru_cache, and the logging module.

**The key risk is breaking the running production pipeline** — it runs every 2 hours via launchd with no staging environment, no CI/CD, and zero test coverage in the core pipeline. Mitigations include: parallel-run pattern (keep old directory running while building new one), characterization tests before touching any code, rollback scripts prepared before making changes, and shadow execution in `--dry-run` mode for 3+ cycles before cutover. The second critical risk is the plaintext API key in `threads-publisher.plist` — this must be the first thing fixed.

---

## Key Decisions

| Decision | Recommendation | Confidence | Sources |
|----------|---------------|------------|---------|
| Migration strategy | **Strangler Fig** — not greenfield rewrite | HIGH | STACK, ARCH, FEATURES, PITFALLS (unanimous) |
| New dependencies | **Zero** — Python 3.14 stdlib suffices for all infra modules | HIGH | STACK (explicit), ARCH (echoed), FEATURES (ditto) |
| Pipeline framework | **None** — no Airflow/Prefect/Kedro | HIGH | STACK (rejected list), ARCH (pattern analysis) |
| Orchestration | **Sequential** — keep current pattern, formalize with `PipelineStep` protocol | HIGH | ARCH (DAG/Event-driven rejected), FEATURES (anti-features) |
| Config format | `.env` + Python dataclasses — no YAML/TOML | HIGH | STACK (confirmed), ARCH (code example), FEATURES (anti-features) |
| D1 access | Keep `subprocess` + `npx wrangler d1 execute` — defer Cloudflare API SDK | HIGH | STACK (explicit), ARCH (acknowledged) |
| Type system | Gradual typing AFTER structural refactoring | HIGH | PITFALLS (Pitfall 12), ARCH (code examples use stdlib) |
| Test approach | Characterization tests BEFORE any code changes | HIGH | PITFALLS (Pitfall 1, critical), ARCH (zero coverage noted) |
| Parallel run safety | Keep old files running, build new structure alongside | HIGH | PITFALLS (Pitfall 2), ARCH (Strangler Fig) |
| Security priority | Fix plist API key exposure FIRST (before path refactoring) | HIGH | PITFALLS (Pitfall 4), PROJECT (SEC-01) |

## Recommended Stack

| Layer | Choice | Rationale | Alternatives Rejected |
|-------|--------|-----------|----------------------|
| **Runtime** | Python 3.14 | Already installed; no migration needed | — |
| **Config** | `pathlib` + `functools.lru_cache` + dataclasses | Stdlib only; project_root() walks up from file location | python-dotenv, PyYAML, Pydantic Settings |
| **Env loading** | Custom `_load_dotenv()` (10 lines) + `EnvConfig` frozen dataclass | Handles `export` prefix, quoted values, `setdefault` semantics | python-dotenv, Pydantic Settings |
| **D1 queries** | `subprocess` + `npx wrangler d1 execute` (KEPT) | Works today; Cloudflare API SDK deferred post-refactoring | cloudflare SDK (future) |
| **Logging** | Python `logging` with `TimedRotatingFileHandler` | Structured logging with zero deps | Rich (visual polish, adds dep) |
| **HTTP** | `requests` | Already installed; used for MiMo, Brevo, Threads APIs | httpx, aiohttp |
| **HTML parsing** | `beautifulsoup4` + `lxml` | Already installed; used for article crawling | — |
| **LLM** | `openai` library | Already installed; model_router uses GPT-4o-mini | — |
| **Testing** | `pytest` + `pytest-snapshot`/`syrupy` | Already has `conftest.py`; add snapshot testing for monolith characterization | — |
| **Pipeline orchestration** | Simple `PipelineStep` protocol + `PipelineOrchestrator` class | 50 lines of stdlib code; no framework needed | Airflow, Prefect, Kedro, Dagster, Celery |
| **Scheduling** | Single mechanism (choose launchd XOR internal `schedule`) | Dual scheduling causes race conditions (Pitfall 9) | Both running concurrently (CURRENT BUG) |

### Existing Dependencies (Preserved)

`requests`, `beautifulsoup4`, `lxml`, `openai`, `schedule`, `pytest` — all already in `.venv`. No changes to `requirements.txt`.

### Infrastructure Modules (All New, All Stdlib)

| Module | Purpose | Key Stdlib |
|--------|---------|------------|
| `pipeline/infra/config.py` | Project root resolution, computed paths | `pathlib`, `functools.lru_cache` |
| `pipeline/infra/env_loader.py` | Centralized env loading, `EnvConfig` dataclass | `os`, `pathlib`, `dataclasses`, `functools.lru_cache` |
| `pipeline/infra/d1_client.py` | Consistent D1 query wrapper with retry | `subprocess`, `json`, `re`, `time` |
| `pipeline/infra/logger.py` | Structured logging with levels + rotation | `logging`, `datetime`, `pathlib` |
| `pipeline/infra/models.py` | Typed data contracts (NewsArticle, BriefingResult, etc.) | `dataclasses`, `datetime` |
| `pipeline/infra/retry.py` | Retry decorator with exponential backoff | `time`, `functools` |

---

## Phase Recommendations

### Priority Ordering Rationale

The ordering is determined by **dependency chains** uncovered in research:

1. **Security audit must come first** — API keys in plaintext in a committed plist is an active incident, not a future concern. Fix this before any code changes.
2. **Shared infra modules must come before wiring** — old files can't import from `pipeline/infra/` if those modules don't exist yet.
3. **Old files must be wired before directory restructuring** — the Plist and deploy.sh must also be fixed.
4. **Monolith splitting must come last** — requires characterization tests (Phase 4 prerequisite), dependency graph analysis (Pitfall 5), and safe parallel-run validation.
5. **Dead code removal must be last** — can't safely delete code you haven't proven is dead via runtime observation.

| Priority | Phase | Rationale | Dependencies | Research Flag |
|----------|-------|-----------|-------------|---------------|
| **P0** | SEC-01: Security audit | API key in plist is active exposure. Must fix before any refactoring touches production code | None — audit only | Skip research (standard security audit) |
| **P1** | Phase 1: Infrastructure layer | Create `pipeline/infra/` modules — zero behavioral change, no old files touched | None | Skip research (pure stdlib, well-documented) |
| **P2** | Phase 2: Wire old files | Replace duplicate PROJECT_DIR/load_env/d1_query/log in 11+ old files with infra imports | Phase 1 (infra must exist) | **RESEARCH NEEDED** — each load_env copy has behavioral differences (Pitfall 3) |
| **P3** | INF-01: Portability + launchd fix | Template-ize plist, fix deploy.sh cross-project dep, remove secrets from plist | Phase 1 (config module), Phase 2 (env_loader) | **RESEARCH NEEDED** — deploy.sh cross-project dep needs verification |
| **P4** | Phase 3: Directory restructuring | Move files to `pipeline/steps/` and `pipeline/threads/`, flatten `v3/` nesting | Phase 2 (old files wired to infra) | Skip research (mechanical file moves, import updates) |
| **P5** | Phase 4: Monolith splitting | Split writer_v3.py and narrative_pitcher.py | Phase 3 (directory structure exists) | **RESEARCH NEEDED** — dependency graph analysis (Pitfall 5); characterization tests (Pitfall 1) |
| **P6** | Phase 5: Test addition | Add unit tests for all split modules | Phase 4 (functions extracted) | Skip research (standard pytest) |
| **P7** | Phase 6: Dead code removal | Delete old files, backup files, format_selector.py | Phase 5 (tested replacement exists) | **RESEARCH NEEDED** — runtime log confirmation of dead code (Pitfall 6) |
| **P8** | Phase 7: Gradual typing | Add type annotations to new modules | Phase 5 (modules stable) | Skip research (standard mypy/pyright) |

### Phase Details

#### SEC-01: Security Audit (P0 — Do First)

**Rationale:** Plaintext `OPENAI_API_KEY` in `scripts/threads/threads-publisher.plist` committed to git. Even if "REDACTED" now, the original key is in git history. This is an active security incident.

**Delivers:** 
- Audit of ALL env var sources (`.env`, `~/.env.common`, `api_test/.env.sh`, plist `EnvironmentVariables`, `deploy.sh` cross-project source)
- Comprehensive variable-source map (Pitfall 10)
- Flagged secrets in git history (needs git filter-branch or key rotation)
- Launchd plist API key removed; plist delegates to `.env`

**Addresses:** SEC-01 from PROJECT.md
**Avoids:** Pitfall 4 (plist secrets), Pitfall 10 (shadow config)

**Risk:** Low — audit only, no code changes

---

#### Phase 1: Infrastructure Layer (Zero Behavioral Change)

**Rationale:** Every refactoring step depends on shared infra modules existing. Creating them with zero behavioral change means old files continue running unchanged. This is the foundation of the Strangler Fig pattern.

**Delivers:**
- `pipeline/infra/config.py` — `project_root()` replaces 11 hardcoded `PROJECT_DIR`
- `pipeline/infra/env_loader.py` — `load_env()` replaces 5+ duplicate implementations
- `pipeline/infra/d1_client.py` — `D1Client` with consistent retry replaces 3 implementations
- `pipeline/infra/logger.py` — `get_logger()` with TimedRotatingFileHandler
- `pipeline/infra/models.py` — typed dataclasses (NewsArticle, BriefingResult, etc.)
- `pipeline/infra/retry.py` — consistent retry decorator

**Addresses:** FEATURES table stakes (portability, single env loader, consistent D1 client, structured logging, clear data contracts)
**Uses:** STACK recommendations (stdlib only, no new deps)
**Implements:** ARCHITECTURE infra layer
**Avoids:** Pitfall 3 (load_env consolidation — done first, before migration)
**Research flag:** Skip — pure Python stdlib, well-documented patterns

---

#### Phase 2: Wire Old Files to Shared Infra

**Rationale:** After infra modules exist, each old file is migrated one at a time to import from shared modules. This removes the duplication without changing behavior. Each migration is a small, reversible change.

**Delivers:**
- 11+ old files updated to import from `pipeline.infra.*` instead of their own copies
- `deploy.sh` updated to source from project `.env` (not cross-project)
- Launchd plist templated, secrets removed
- All `load_env()` copies removed; single `EnvConfig` used everywhere
- All `d1_query()` copies removed; single `D1Client` used everywhere

**Addresses:** FEATURES portability, FEATURES single env loader, FEATURES consistent D1 client
**Uses:** STACK infra modules
**Implements:** ARCHITECTURE "wire old files" step
**Avoids:** Pitfall 3 (audit before consolidate), Pitfall 7 (side effects — one caller at a time), Pitfall 11 (fix tests in same commit), Pitfall 13 (posted.json schema), Pitfall 14 (deploy.sh)

**Critical procedure from PITFALLS research:**
1. Before consolidating `load_env()`, audit ALL 5+ copies — document file sources, order, setdefault vs assignment, return values
2. Create the unified version as a SUPERSET of all behaviors (with backward-compat flags)
3. Migrate ONE caller at a time, running pipeline between each migration
4. Do NOT delete old `load_env()` until all callers migrated
5. Same procedure for `d1_query()` and `load_posted()`

**Research flag:** **Needs deeper research** — must read each `load_env()` copy to document behavioral differences before consolidating. See Pitfall 3.

---

#### INF-01: Portability + Launchd Fix

**Rationale:** Can interleave with Phase 2. The plist is the deployment artifact — until it's templated, the pipeline can't run on any machine but the current one. Cross-project `.env` dependency in `deploy.sh` is also a portability blocker.

**Delivers:**
- `scripts/install_launchd.sh` — generates plist from template with computed paths
- `templates/threads-publisher.plist.template` — no hardcoded paths, no secrets
- `deploy.sh` — resolves paths relative to its location, sources project `.env` only
- `api_test/.env.sh` — removed from rotation (shadow config)

**Addresses:** INF-01 from PROJECT.md, FEATURES portability
**Uses:** STACK config module
**Avoids:** Pitfall 4 (plist portability), Pitfall 14 (deploy.sh)
**Research flag:** **Needs deeper research** — need to verify exactly which vars come from `/Users/twinssn/Projects/5000/.env` and whether they exist elsewhere in this project.

---

#### Phase 3: Directory Restructuring

**Rationale:** After old files are wired to shared infra (no more hardcoded paths or duplicate utilities), the actual directory move is mechanical — update imports, move files, create `run_pipeline.py` as thin wrapper, create `pipeline/orchestrator.py`.

**Delivers:**
- `pipeline/steps/{news_selector,briefing,deep_article,thumbnail,email_sender,deploy}.py`
- `pipeline/threads/` with `v3/` nesting flattened
- `pipeline/orchestrator.py` with `PipelineStep` protocol and `PipelineOrchestrator` class
- `run_pipeline.py` as thin CLI wrapper
- `run_threads.py` replacing `main_v3.py`
- Old files kept as thin wrappers (Strangler Fig)

**Addresses:** FEATURES per-step isolation, FEATURES step addition, FEATURES graceful degradation, FEATURES pipeline monitoring
**Uses:** STACK infra modules, ARCHITECTURE component boundaries
**Implements:** ARCHITECTURE Pipe & Filter pattern
**Avoids:** Pitfall 8 (import-at-runtime pattern — document and preserve until module-level side effects resolved)

**Research flag:** Skip — mechanical file moves and import updates. Well-understood patterns.

---

#### Phase 4: Monolith Splitting (Highest Risk)

**Rationale:** `writer_v3.py` (1,013 lines) and `narrative_pitcher.py` (581 lines) are the riskiest refactoring targets. Must be preceded by characterization tests and dependency graph analysis.

**Delivers:**
- `pipeline/threads/validator.py` — extracted from `writer_v3` (card/year/keyword validation)
- `pipeline/threads/crawler.py` — extracted from `writer_v3` (article fetching, link validation)
- `pipeline/threads/writer.py` — remaining card assembly, format builders
- `pipeline/threads/pitch.py` — extracted from `narrative_pitcher`
- `pipeline/threads/pitch_evaluator.py` — evaluation gate (kept from narrative_pitcher)
- `format_selector.py` — marked deprecated (not deleted yet)

**Addresses:** FEATURES per-step unit testing, ARCHITECTURE component boundaries
**Implements:** ARCHITECTURE threads layer
**Avoids:** Pitfall 1 (characterization tests first — critical), Pitfall 5 (dependency graph before split), Pitfall 12 (no premature typing)

**Critical procedure from PITFALLS:**
1. Run `pydeps` to generate dependency graph BEFORE splitting (Pitfall 5)
2. Write characterization tests for pure functions first (Pitfall 1)
3. Extract ONE function at a time — do NOT attempt to split entire file in one session
4. Apply Dependency Inversion for circular dependencies (Pitfall 5)
5. Use `TYPE_CHECKING` for type-only circular imports
6. No type annotations during structural changes (Pitfall 12)

**Research flag:** **Needs deeper research** — dependency graph analysis of writer_v3.py internal function calls; characterization test design for 1,013-line monolith.

---

#### Phase 5: Test Addition

**Rationale:** After functions are extracted into small modules with clear contracts, adding tests is straightforward. This is the safety net for all future changes.

**Delivers:**
- `tests/test_news_selector.py`
- `tests/test_briefing.py`
- `tests/test_orchestrator.py`
- `tests/test_threads/test_{dedup,validator,pitch,writer}.py`
- Updated `conftest.py` with abstracted mock targets (Pitfall 11)

**Addresses:** FEATURES per-step unit testing
**Avoids:** Pitfall 11 (fix tests in same commit as code moves)
**Research flag:** Skip — standard pytest patterns.

---

#### Phase 6: Dead Code Removal (Last)

**Rationale:** Only safe after all replacements are tested in production. `format_selector.py`, old `threads/main_v3.py`, backup `.bak` files — confirm dead with runtime logging before removing.

**Addresses:** REF-03 from PROJECT.md
**Avoids:** Pitfall 6 (load-bearing dead code), Pitfall 15 (bak file data loss)
**Research flag:** **Needs deeper research** — add runtime logging to suspicious code paths, run pipeline for 7 days to confirm dead.

---

#### Phase 7: Gradual Typing (Optional)

**Rationale:** Only after modules are stable and small. Add types to new files and public interfaces only. No attempt to type the entire codebase.

**Avoids:** Pitfall 12 (premature typing scoping creep)
**Research flag:** Skip — standard mypy/pyright patterns.

---

## Table Stakes (Must Do)

From FEATURES.md — these are non-negotiable capabilities the refactoring must deliver:

| Capability | Current Status | How to Achieve | Phase |
|------------|---------------|----------------|-------|
| **Portability** — clone → deps → .env → run | ❌ 11 files hardcoded | `config.py` + `project_root()` | Phase 1 |
| **Single env loader** — one source order | ❌ 5+ implementations | `env_loader.py` + `EnvConfig` | Phase 1 |
| **Consistent D1 client** — same retry/timeout | ❌ 3 implementations | `d1_client.py` + `retry.py` | Phase 1 |
| **Per-step isolation** — one failure doesn't crash all | ✅ Existing try/except | Formalize with orchestrator | Phase 3 |
| **Structured logging** — timestamps, levels, format | ❌ `print()` everywhere | `logger.py` with TimedRotatingFileHandler | Phase 1 |
| **Clear data contracts** — typed inputs/outputs | ❌ ad-hoc dicts | `models.py` dataclasses | Phase 1 |
| **CLI consistency** — same flags before and after | ✅ Already works | Must not break | All phases |

## Differentiators (Architecture Capabilities)

From FEATURES.md — engineering capabilities unlocked by the new structure:

| Capability | Value | Complexity | Unlocked In |
|------------|-------|------------|-------------|
| Per-step unit testing | Each step testable in isolation | Medium | Phase 4 (functions extracted) |
| Pipeline monitoring | Per-step duration, success/failure stored | Low | Phase 3 (orchestrator collects results) |
| Step addition | New step = write function + register | Low | Phase 3 (orchestrator `add_step()`) |
| Environment isolation | Switch .env file for staging/dev | Low | Phase 1 (config computes paths) |
| Graceful degradation | Non-critical steps fail without abort | Low | Phase 3 (`is_critical` flag) |
| Migration path for monoliths | writer_v3 split into modules | High | Phase 4 |

## Anti-Features (Don't Do)

From FEATURES.md + ARCHITECTURE.md + STACK.md + PITFALLS.md — unanimous consensus:

| Anti-Feature | Why Avoid | Instead |
|--------------|-----------|---------|
| **Abstract PipelineStep base class** | 6 steps don't share enough interface | Duck-typed protocol |
| **Dependency injection framework** | Overkill; all steps need same things | Direct imports from infra |
| **Async/await** | No parallelism benefit for 6 serial steps | Synchronous requests/subprocess |
| **Pipeline run database** | Nice but not required | Log files + orchestrator summary |
| **Greenfield rewrite** | Highest risk; wastes months of effort | Strangler Fig migration |
| **YAML/TOML config file** | Another file to maintain | Keep CLI flags + .env + dataclasses |
| **Airflow/Prefect/Kedro/Dagster** | 500MB+ deps, DB required, web UI unneeded | 50-line orchestrator with stdlib |
| **Premature type annotations** | Doubles scope, masks refactoring bugs | Gradual typing after structural changes |

---

## Critical Pitfalls

From PITFALLS.md — ranked by severity with cross-phase prevention strategies:

### 🔴 Pitfall 1: Refactoring Without Characterization Tests First

**Risk:** Silent behavior drift in writer_v3.py and narrative_pitcher.py — Korean phrasing quality, card formatting, keyword validation all degrade without detection.

**Prevention:**
- Write characterization tests BEFORE touching any monolith code (Phase 4 prerequisite)
- Use snapshot/approval testing (`pytest-snapshot` or `syrupy`)
- Start with pure functions (validate_keywords, validate_year, validate_cards)
- Do NOT refactor until at least pure functions are under test

**Affects:** Phase 4 (monolith splitting)

---

### 🔴 Pitfall 2: Breaking the Running Pipeline Mid-Refactoring (No Rollback)

**Risk:** Pipeline runs every 2 hours via launchd. No staging environment, no CI/CD. A broken import = 2+ hours of downtime.

**Prevention:**
- Parallel-run pattern: keep old `scripts/threads/` running while building new structure
- Shadow execution: run new pipeline in `--dry-run` for 3+ cycles before cutover
- Rollback script: `git checkout HEAD~1 -- scripts/threads/` — create before making changes
- Launchd plist is a deployment artifact — keep old plist as rollback

**Affects:** ALL phases (especially Phase 2, Phase 3, Phase 4)

---

### 🔴 Pitfall 3: Consolidating `load_env()` Without Accounting for Behavioral Differences

**Risk:** The 5+ `load_env()` copies are NOT identical — different file sources, load orders, setdefault vs assignment, return dicts. Consolidating them as "identical" breaks env loading.

**Prevention:**
- Audit EVERY copy before consolidating (document: files read, order, setdefault vs `=`, return value, call timing)
- Create unified version as SUPERSET of all behaviors with backward-compat flags
- Migrate ONE caller at a time, running pipeline between each migration

**Affects:** Phase 2 (wire old files)

---

### 🟠 Pitfall 4: Launchd Plist as Hidden Security and Portability Landmine

**Risk:** API key in plaintext in committed plist. Hardcoded paths to venv. Zero portability. Cross-project `.env` dependency in deploy.sh.

**Prevention:**
- Template-ize the plist (create `install_launchd.sh`)
- Remove secrets from plist — delegate to `.env`
- Fix deploy.sh to use project's own `.env`, not cross-project
- Add plist template to `.gitignore` patterns that catch secrets

**Affects:** SEC-01, INF-01, Phase 2

---

### 🟠 Pitfall 5: Circular Imports When Splitting Monoliths

**Risk:** writer_v3.py's internal function dependencies are not cleanly layered. Splitting by topic reveals circular dependencies between validation, humanization, and card assembly modules.

**Prevention:**
- Map dependency graph with `pydeps` BEFORE splitting (Phase 4 prerequisite)
- Apply Dependency Inversion for circular dependencies
- Extract ONE function at a time, not the entire file at once
- Use `TYPE_CHECKING` for type-only circular imports

**Affects:** Phase 4 (monolith splitting)

---

### 🟠 Pitfall 10: Incomplete `.env` Migration Creates Shadow Configurations

**Risk:** Env loading is fragmented across `.env`, `~/.env.common`, `api_test/.env.sh`, plist `EnvironmentVariables`, `deploy.sh` (cross-project), and token refresh writes back to `.env`. After refactoring, some paths use old loader, others use new — inconsistent env state.

**Prevention:**
- Audit ALL 5+ env var sources before refactoring (create comprehensive map)
- Phase the migration: collect all sources → move to `.env` → remove plist vars → remove `~/.env.common` → fix deploy.sh → remove old load_env copies
- Add startup validation that ALL expected env vars are present

**Affects:** SEC-01, Phase 2, INF-01

---

## Open Questions (Gaps to Address)

| Gap | Affected Phase | How to Resolve |
|-----|---------------|----------------|
| **`deploy.sh` cross-project dependency** — which vars come from `/Users/twinssn/Projects/5000/.env`? | INF-01 | Read the target .env and check if vars exist in this project |
| **Dual-scheduling race condition** — does `--once` always prevent internal scheduler? | Phase 4 | `ps aux` during pipeline execution to confirm |
| **`posted.json` write patterns** — any raw `open()` + `write()` without atomic rename? | Phase 2 | Audit all writers (db_reader.py, publisher.py) for write patterns |
| **Existing `conftest.py` mock infrastructure** — how to design abstracted mock targets? | Phase 5 | Read conftest.py before designing test migration |
| **`format_selector.py` dead status** — is it truly no-op? | Phase 6 | Add runtime logging, run for 7 days to confirm |
| **`.bak` files with valuable content** — any manual edits not merged to source? | Phase 6 | Check file sizes vs source; review git history |
| **Shadow config at `api_test/.env.sh`** — what vars does it set? | SEC-01 | Compare contents with project `.env` |
| **Plist API key in git history** — can we remove with `git filter-branch`? | SEC-01 | Decide on key rotation vs history rewrite |

---

## Research Flags

| Phase | Flag | Why |
|-------|------|-----|
| **Phase 2** | 🔬 Research needed | Each `load_env()` copy has behavioral differences — must document before consolidate. See PITFALLS.md Pitfall 3. |
| **INF-01** | 🔬 Research needed | `deploy.sh` cross-project dep needs verification. Plist template design. |
| **Phase 4** | 🔬 Research needed | `pydeps` analysis of writer_v3.py internal dependencies. Characterization test design. See PITFALLS.md Pitfall 5. |
| **Phase 6** | 🔬 Research needed | Runtime log confirmation loop for dead code detection (7-day observation). |
| SEC-01 | ✅ Standard patterns | Security audit — well-documented methodology. |
| Phase 1 | ✅ Standard patterns | Pure stdlib modules — well-documented Python patterns. |
| Phase 3 | ✅ Standard patterns | Mechanical file moves + import updates. |
| Phase 5 | ✅ Standard patterns | Standard pytest approach. |
| Phase 7 | ✅ Standard patterns | Standard mypy/pyright gradual typing. |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | **HIGH** | Codebase analysis of all 16+ Python files confirms exact dependencies and their usage. Python 3.14 stdlib documentation verified. No third-party dependency ambiguity. |
| **Features** | **HIGH** | Direct codebase analysis (11 hardcoded paths, 5+ load_env, 3 d1_query, 2 load_posted) — all findings verified by file inspection. Feature dependencies derived from actual code structure. |
| **Architecture** | **HIGH** | Complete reverse-engineering of current architecture. All component boundaries, data flows, and pain points verified against actual files. Pipe & Filter + Strangler Fig patterns are well-established and match the codebase's actual structure. |
| **Pitfalls** | **HIGH** | Every pitfall is grounded in specific code patterns verified in the codebase. Plist secrets confirmed by file inspection. Import-at-runtime pattern confirmed by file inspection. Dual-scheduling confirmed by file inspection. Sources include both established methodology (Feathers, Fowler, Thoughtworks) and codebase-specific validation. |

**Overall confidence: HIGH**

All 4 research dimensions are grounded in direct codebase analysis rather than generic research. The architecture is simple (sequential pipeline, no framework), and the recommended approach (Strangler Fig with shared infra modules) is a well-established pattern for exactly this scenario. The risks are well-understood and each has a proven mitigation strategy.

---

## Sources

### Primary (HIGH confidence) — Codebase Analysis

| Source | Findings | Used In |
|--------|----------|---------|
| `scripts/run_pipeline.py` | Import-at-runtime pattern, orchestrator structure, CLI flags | STACK, ARCH, PITFALLS |
| `scripts/auto_news_selector.py` (490 lines) | Hardcoded PROJECT_DIR, duplicate d1_query, duplicate log | STACK, ARCH, PITFALLS |
| `scripts/auto_briefing.py` (265 lines) | Hardcoded PROJECT_DIR, duplicate d1_execute | STACK, ARCH |
| `scripts/auto_deep_article.py` | Hardcoded PROJECT_DIR | STACK |
| `scripts/auto_thumbnail.py` | Hardcoded PROJECT_DIR | STACK |
| `scripts/auto_email_sender.py` | Hardcoded PROJECT_DIR | STACK |
| `scripts/threads/main_v3.py` | Dual scheduling (schedule + launchd), module-level side effects | STACK, ARCH, PITFALLS |
| `scripts/threads/db_reader.py` (363 lines) | Hardcoded PROJECT_DIR, duplicate d1_query, duplicate load_posted | STACK, ARCH, PITFALLS |
| `scripts/threads/publisher.py` (252 lines) | Hardcoded PROJECT_DIR, duplicate load_env, token refresh writes to .env | STACK, ARCH, PITFALLS |
| `scripts/threads/v3/writer_v3.py` (1,013 lines) | Largest monolith, duplicate PROJECT_DIR, duplicate log, zero tests | ARCH, PITFALLS |
| `scripts/threads/v3/narrative_pitcher.py` (581 lines) | Module-level load_env side effect, zero tests | ARCH, PITFALLS |
| `scripts/threads/v3/model_router.py` | Module-level load_env side effect, implicit env loading contract | ARCH, PITFALLS |
| `scripts/threads/threads-publisher.plist` | **Plaintext API key**, hardcoded paths, hardcoded venv | PITFALLS (Pitfall 4) |
| `deploy.sh` | Cross-project `.env` dependency (5000/.env) | PITFALLS (Pitfall 14, 10) |
| `scripts/tests/conftest.py` | Existing mock infrastructure (monkeypatch_d1) | PITFALLS (Pitfall 11) |

### Secondary (MEDIUM-HIGH confidence) — Established Patterns

| Source | Findings | Used In |
|--------|----------|---------|
| Strangler Fig pattern (Thoughtworks, Martin Fowler) | Incremental migration, parallel run, shadow operations | ARCH, PITFALLS |
| Pipe & Filter pattern (Data Pipeline Design) | Sequential step architecture with typed contracts | ARCH |
| Characterization testing (Feathers, "Working Effectively with Legacy Code") | Legacy code = code without tests; snapshot testing before refactoring | PITFALLS (Pitfall 1) |
| Python stdlib docs (configparser, logging, dataclasses, functools) | All infra module implementations | STACK, ARCH |
| Cloudflare D1 + wrangler docs | D1 access patterns, execute command | STACK |

### Gaps for Validation

- `deploy.sh` cross-project dependency details (Pitfall 14)
- `api_test/.env.sh` contents (shadow config, Pitfall 10)
- `conftest.py` mock structure for test migration design (Pitfall 11)
- writer_v3.py internal dependency graph (Pitfall 5)

---

*Research completed: 2026-06-30*
*Ready for roadmap: yes*
