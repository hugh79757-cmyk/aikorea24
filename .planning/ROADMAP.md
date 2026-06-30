# Roadmap: AI코리아24 (aikorea24.kr) — Pipeline Refactoring

## Overview

Brownfield refactoring of the Python automation pipeline from a monolithic, security-bleeding codebase with 16+ duplicated scripts into a modular, portable, and observable pipeline. Uses Strangler Fig migration: fix security first, build shared infrastructure, wire old files incrementally, restructure, split monoliths last. Zero new external dependencies — Python 3.14 stdlib only.

## Phases

- [x] **Phase 1: Security Hardening** — Eliminate active security issues (plaintext API keys, fragmented env loading) (completed 2026-06-30)
- [ ] **Phase 2: Infrastructure & Portability** — Create shared infra modules, wire old files, remove hardcoded paths
- [ ] **Phase 3: Landing Zone & Orchestrator** — Directory restructuring, pipeline orchestrator, Threads stabilization, portability
- [ ] **Phase 4: Monolith Splitting** — Split writer_v3.py (1,013 lines) and narrative_pitcher.py (581 lines) into focused modules
- [ ] **Phase 5: Dead Code Removal & Final Polish** — Remove dead code, failure notifications, bulletin board verification

## Phase Details

### Phase 1: Security Hardening
**Goal**: All active security issues are eliminated — no plaintext API keys in committed files, env loading consolidated into a single secure module, and secrets in git history documented for remediation.
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, OBS-07, TST-05
**Success Criteria** (what must be TRUE):
   1. `threads-publisher.plist` contains zero API keys or secrets — all env vars delegated to `.env`
   2. A comprehensive env var source-map document exists, covering all 5+ sources across the project
   3. Single `env_loader.py` module exists (Strangler Fig — old `load_env()` copies remain for incremental wiring in Phase 2)
  4. Secrets in git history are flagged for remediation (key rotation or git filter-branch decision recorded)
  5. Log output is verified to redact API keys and sensitive values (no keys in logs)
**Plans**: 1 plan

Plans:
- [x] 02-PLAN.md — Plist hardening, env consolidation (env_loader.py), log scrubbing, test mocks, git history cleanup

### Phase 2: Infrastructure & Portability
**Goal**: All shared infrastructure modules exist in `pipeline/infra/` and are used by all old files — no more duplicated utility code, no more hardcoded project paths.
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: INF-01, INF-02, INF-03, INF-04, INF-05, INF-06, POR-01, OBS-01
**Success Criteria** (what must be TRUE):
  1. `pipeline/infra/` contains all 6 modules (config, env_loader, d1_client, logger, models, retry) — all stdlib only
  2. All 11+ hardcoded `PROJECT_DIR` paths replaced with `project_root()` from `config.py`
  3. All old files import from `pipeline.infra.*` instead of defining their own `load_env()`, `d1_query()`, `load_posted()` copies
  4. `conftest.py` has abstracted mock targets so tests don't hit real D1/API endpoints
  5. Pipeline runs successfully with zero regressions after infra wiring
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Infra Foundation: create config.py, models.py, retry.py, d1_client.py, extend logger with PipelineLogger
- [ ] 02-02-PLAN.md — Batch Wiring: wire all 20+ scripts with project_root(), EnvConfig(), d1_client.d1_query(), PipelineLogger

### Phase 3: Landing Zone & Orchestrator
**Goal**: Pipeline has a proper directory structure, formal orchestrator with per-step monitoring, Threads dual-scheduling race condition resolved, and the pipeline can be cloned and run on any machine.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: POR-02, POR-03, POR-04, DIR-01, DIR-02, DIR-03, DIR-04, DIR-05, TST-01, OBS-02, OBS-03, OBS-04, OBS-05, THR-01, THR-02
**Success Criteria** (what must be TRUE):
  1. `pipeline/steps/` and `pipeline/threads/` directories exist with all step scripts organized in place
  2. `pipeline/orchestrator.py` with `PipelineStep` protocol and `PipelineOrchestrator` class runs all steps with per-step timing and exit code propagation
  3. Run history stored in D1 (`pipeline_runs` table) — every step's status, duration, timestamp recorded
  4. CLI command `python -m pipeline status` shows last N runs and per-step health at a glance
  5. Plist is generated from template via `install_launchd.sh` — zero hardcoded paths or secrets in plist
  6. `deploy.sh` resolves paths relative to its location and sources only project `.env` (no cross-project dependency)
  7. Threads publishing has no dual-scheduling race condition — single mechanism (launchd XOR internal `schedule`)
  8. Characterization tests exist for pure functions before any monolith refactoring begins
**Plans**: 5 plans

Plans:
- [ ] 03-01-PLAN.md — Orchestrator + D1 recording + CLI (core infrastructure)
- [ ] 03-02-PLAN.md — Directory restructuring + Strangler Fig step wrappers
- [ ] 03-03-PLAN.md — Plist templating + install_launchd.sh + deploy.sh portability
- [ ] 03-04-PLAN.md — Threads dual-scheduling fix (remove --daemon)
- [ ] 03-05-PLAN.md — Characterization tests for pure functions

### Phase 4: Monolith Splitting
**Goal**: The two largest monoliths (`writer_v3.py` at 1,013 lines and `narrative_pitcher.py` at 581 lines) are split into focused, independently testable modules.
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07, TST-02, TST-03, TST-04
**Success Criteria** (what must be TRUE):
  1. Dependency graph of `writer_v3.py` internal function calls is documented before any splitting
  2. Card/year/keyword validation is extracted into `pipeline/threads/validator.py` with characterization tests
  3. Article fetching and link validation is extracted into `pipeline/threads/crawler.py` with tests
  4. Format builders are extracted into `pipeline/threads/writer.py` with tests
  5. Pitch logic and pitch evaluation are extracted into `pipeline/threads/pitch.py` and `pipeline/threads/pitch_evaluator.py`
  6. Unit tests exist for all Threads pipeline modules (validator, crawler, writer, pitch) and the orchestrator
**Plans**: TBD

### Phase 5: Dead Code Removal & Final Polish
**Goal**: Pipeline is fully clean — no dead code, no backup files, no abandoned scripts. Failure notifications work. Bulletin board verified reliable.
**Mode**: mvp
**Depends on**: Phase 4
**Requirements**: DED-01, DED-02, DED-03, DED-04, OBS-06, BRD-01
**Success Criteria** (what must be TRUE):
  1. No backup files (`backup_*.txt`, `.bak` files) remain in the repository
  2. No abandoned scripts remain (`patch_*.py`, `test_*.py`, `spotlight_*.sh`, `quick_check.sh`)
  3. `format_selector.py` is removed after confirming its functionality exists in new modules
  4. Old `threads/main_v3.py` is removed after confirming new structure works in production (shadow-run validated)
  5. Telegram alert fires correctly when a pipeline step fails or schedule is missed (fixed existing mechanism, not new setup)
  6. Community bulletin board (posts + comments) is verified working with refactored pipeline
**Plans**: TBD

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening | 1/1 | Complete   | 2026-06-30 |
| 2. Infrastructure & Portability | 0/2 | Not started | - |
| 3. Landing Zone & Orchestrator | 0/5 | Not started | - |
| 4. Monolith Splitting | 0/0 | Not started | - |
| 5. Dead Code Removal & Final Polish | 0/0 | Not started | - |
