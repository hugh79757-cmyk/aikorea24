---
phase: 03-landing-zone-orchestrator
plan: 01
subsystem: infra
tags:
  - pipeline
  - orchestrator
  - cli
  - d1
  - sqlite
  - python

requires:
  - phase: 02-infrastructure-portability
    provides: PipelineStepResult, PipelineRun dataclasses; d1_query; log_step context manager; PipelineLogger; project_root
provides:
  - PipelineStep protocol for step contract
  - PipelineOrchestrator class for sequential step execution with timing
  - D1 pipeline_runs table migration for run history persistence
  - CLI entry point (python -m pipeline) with run/status commands
affects:
  - 03-landing-zone-orchestrator plans (02, 03, 04) that will register real steps

tech-stack:
  added: []
  patterns:
    - Protocol-based structural subtyping (typing.Protocol) for step interface
    - Import-at-call-site pattern for d1_query to avoid init-time failure
    - Single-quote escaping for SQL injection defense on error messages
    - argparse nargs=? with default for dual-command CLI dispatch

key-files:
  created:
    - pipeline/orchestrator.py (PipelineStep protocol + PipelineOrchestrator class, 144 lines)
    - pipeline/__main__.py (CLI entry point with run/status subcommands, 123 lines)
    - pipeline/__init__.py (package re-exports, 6 lines)
    - pipeline/migrations/20260630_create_pipeline_runs.sql (D1 table schema, 16 lines)
  modified: []

key-decisions:
  - "d1_query imported at call site (inside _record_to_d1) rather than module level to prevent init-time failure when D1 is unavailable"
  - "Step registration is explicit (register() method) rather than decorator-based for clarity"
  - "CLI uses argparse with nargs='?' positional for default-to-run behavior"
  - "PipelineStep uses typing.Protocol (structural typing) instead of ABC for zero-coupling step implementations"

patterns-established:
  - "PipelineStep Protocol: any object with a name: str and run() -> int is a valid step"
  - "Best-effort D1 recording: pipeline continues even if D1 write fails, only logs a warning"
  - "Per-step timing via log_step() context manager wrapping time.monotonic()"

requirements-completed:
  - DIR-04
  - OBS-02
  - OBS-03
  - OBS-04
  - OBS-05

duration: 2min
completed: 2026-06-30
---

# Phase 03 Plan 01: Pipeline Orchestrator Core Summary

**PipelineStep Protocol, PipelineOrchestrator class with per-step timing and D1 recording, D1 migration for pipeline_runs table, and CLI entry point (python -m pipeline {run|status})**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-30T14:17:36Z
- **Completed:** 2026-06-30T14:19:09Z
- **Tasks:** 3 (all auto, no checkpoints)
- **Files created:** 4

## Accomplishments

- **PipelineStep Protocol** (`@runtime_checkable`) defines the contract for all pipeline steps: `name: str` attribute + `run() -> int` method (0 = success, nonzero = failure).
- **PipelineOrchestrator class** with `register()`, `run(dry_run=True)`, `_record_to_d1()`, and `_print_summary()` — wraps each step in `log_step()` for automatic timing, catches exceptions, records to D1 best-effort, and prints formatted summary with emoji icons.
- **D1 migration** (`pipeline/migrations/20260630_create_pipeline_runs.sql`) creates the `pipeline_runs` table with run_id, step_name, status, duration_seconds, error_message, and timestamps plus two indexes.
- **CLI entry point** (`python -m pipeline`) supports `run` (default), `status`, `--dry-run`, and `--runs N` flags with argparse.

## Task Commits

Each task was committed atomically:

| # | Task | Commit | Description |
|---|------|--------|-------------|
| 1 | Create migration + orchestrator | `08166ce` | `feat(03-landing-zone-orchestrator): create pipeline_runs migration and orchestrator module` |
| 2 | Create CLI entry point | `42d3929` | `feat(03-landing-zone-orchestrator): create CLI entry point (python -m pipeline)` |
| 3 | Create pipeline/__init__.py | `a9464b0` | `feat(03-landing-zone-orchestrator): create pipeline package re-exports` |

## Files Created

- `pipeline/orchestrator.py` — PipelineStep Protocol + PipelineOrchestrator (144 lines, Korean comments)
- `pipeline/__main__.py` — CLI entry point with cmd_run, cmd_status, main() (123 lines, Korean comments)
- `pipeline/__init__.py` — Package re-exports (PipelineStep, PipelineOrchestrator)
- `pipeline/migrations/20260630_create_pipeline_runs.sql` — D1 table schema with indexes

## Decisions Made

- **Import-at-call-site for d1_query**: Imported inside `_record_to_d1()` method rather than at module top-level to prevent import cascade failures when wrangler/npx is unavailable.
- **Explicit step registration**: Using `register(step)` method over decorator-based registration for simplicity and ease of testing.
- **Argparse nargs='?' pattern**: `command` positional arg defaults to `'run'` so both `python -m pipeline` and `python -m pipeline run` work identically.
- **Best-effort D1 writes**: Pipeline never halts on D1 write failures — only logs a warning via `_log.warning()`.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Threat Surface Scan

No threat flags — all threat model mitigations implemented:

| Threat | Component | Mitigation | Status |
|--------|-----------|------------|--------|
| T-03-01 | D1 SQL injection | Step names hardcoded; run_id machine-generated; error_message escaped (`'` → `''`); --runs is argparse int-coerced | ✅ |
| T-03-02 | CLI argparse | argparse --runs accepts int only; no shell injection | ✅ |
| T-03-03 | Log output | get_pipeline_logger / get_scrubbed_logger both use ScrubLogFilter | ✅ |
| T-03-04 | pip installs | No new pip packages; stdlib only | ✅ |

## User Setup Required

Migration SQL needs to be applied to D1:
```bash
npx wrangler d1 execute aikorea24-db --remote --file pipeline/migrations/20260630_create_pipeline_runs.sql
```

## Next Phase Readiness

- Orchestrator core complete and verified — all imports work, CLI runs without errors, all 103 existing tests pass.
- Ready for Plan 02: Register the first real pipeline steps (fetch_articles, generate_pitches, write_thread, validate, publish).
- Remaining steps: threads dedup fix (THR-01), Strangler Fig wrappers (DIR-01/DIR-02), characterization tests (TST-01).

---

## Self-Check: PASSED

- ✅ `pipeline/orchestrator.py` exists (144 lines, PipelineStep + PipelineOrchestrator)
- ✅ `pipeline/__main__.py` exists (123 lines, CLI entry point)
- ✅ `pipeline/__init__.py` exists (6 lines, re-exports)
- ✅ `pipeline/migrations/20260630_create_pipeline_runs.sql` exists (16 lines, DDL)
- ✅ `.planning/phases/03-landing-zone-orchestrator/03-01-SUMMARY.md` exists
- ✅ Commit 08166ce: orchestrator + migration
- ✅ Commit 42d3929: CLI entry point
- ✅ Commit a9464b0: package re-exports
- ✅ Commit f0dc781: metadata (SUMMARY + STATE + ROADMAP)
- ✅ `from pipeline.orchestrator import PipelineStep, PipelineOrchestrator` succeeds
- ✅ `from pipeline import PipelineStep, PipelineOrchestrator` succeeds
- ✅ `python -m pipeline status` prints "No pipeline runs recorded yet."
- ✅ `python -m pipeline run --dry-run` prints summary with no errors
- ✅ Migration SQL contains CREATE TABLE pipeline_runs
- ✅ All 103 existing tests pass (yesterday's characterization tests unaffected)

*Phase: 03-landing-zone-orchestrator*
*Completed: 2026-06-30*
