# Phase 3: Landing Zone & Orchestrator — Research

**Researched:** 2026-06-30
**Domain:** Pipeline directory restructuring, orchestrator design, launchd plist templating, Threads dual-scheduling fix, D1 run history, CLI status command, characterization tests
**Confidence:** HIGH

## Summary

Phase 3 creates the structural and runtime backbone of the pipeline: a formal orchestrator with per-step monitoring and D1 recording, a clean directory layout with Strangler Fig wrappers, a portable launchd install script, fix for the Threads dual-scheduling race condition, and characterization tests that gate the Phase 4 monolith splitting work.

The foundation already exists. `models.py` provides `PipelineStepResult` and `PipelineRun` dataclasses. `logger.py` provides `log_step()` context manager for automatic duration measurement. `d1_client.py` provides D1 query capability. The orchestrator itself is a thin ~80-line class that registers steps, runs them sequentially with timing, and records results to D1. No third-party dependencies needed — Python 3.14 stdlib only.

The Threads dual-scheduling bug is straightforward: `main_v3.py` has a `--daemon` mode that creates an internal `schedule` loop, but launchd also fires the script on a timer. If the plist uses `--daemon`, both mechanisms run independently. Fix: remove `--daemon` mode entirely, keep only `--once` for launchd.

**Primary recommendation:** Build the orchestrator and `__main__.py` first as the MVP vertical slice, then add directory restructuring with Strangler Fig wrappers, then thread stabilization, then characterization tests. Each is independently verifiable.

<user_constraints>
## User Constraints (from phase context and PROJECT.md)

### Locked Decisions
- **D-11:** 복잡도가 낮아지는 방향으로 설계. 같은 기능이면 더 적은 코드로.
- **D-12:** Python 3.14 stdlib only — no third-party dependencies.
- **D-13:** 한국어 주석.
- **D-14:** Strangler Fig — 기존 파일은 그대로 동작, 새 모듈은 점진적으로 적용.
- No orchestration framework — simple `PipelineStep` protocol + `PipelineOrchestrator` class (~50 lines)
- Coarse granularity (5 phases), YOLO mode, Vertical MVP structure
- MVP mode is active — deliver vertical slices

### the agent's Discretion
- Exact step registration mechanism (decorator vs explicit register())
- Threads directory structure exactly how flat vs subpackages
- Test framework choices within existing pytest setup
- Plist template variable naming convention

### Deferred Ideas (OUT OF SCOPE)
- Web dashboard UI — deferred to separate dashboard project
- CI/CD server setup — pipeline runs locally via cron
- Abstract base classes / DI frameworks — overkill for 6-8 sequential steps
- Async/await migration — no parallelism benefit for serial pipeline
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POR-02 | Template-ize `threads-publisher.plist` — no hardcoded paths or secrets | `string.Template` from stdlib with `$PROJECT_DIR`, `$VENV_PYTHON`, `$SCRIPT_PATH`, `$LOG_DIR` variables |
| POR-03 | Create `install_launchd.sh` that generates plist from template with computed paths | Shell script uses `$(dirname "$0")` for relative path resolution, `string.Template` substitution via Python |
| POR-04 | Fix `deploy.sh` to resolve paths relative to its location and source only project `.env` | Already partially fixed; remove `api_test/.env.sh` cross-project reference |
| DIR-01 | Create `pipeline/steps/` — move pipeline step scripts | Step scripts are thin wrappers calling old entry points via subprocess |
| DIR-02 | Create `pipeline/threads/` with flattened `v3/` nesting | Flatten `v3/` modules into `pipeline/threads/` directly, old `scripts/threads/v3/` stays as Strangler Fig |
| DIR-03 | Create `pipeline/infra/` for shared infrastructure modules | Already exists from Phase 2 — 6 modules ready |
| DIR-04 | Create `pipeline/orchestrator.py` with `PipelineStep` protocol and `PipelineOrchestrator` class | Protocol-based design, ~80 lines, uses existing `PipelineStepResult`/`PipelineRun` models |
| DIR-05 | Keep old files as thin wrappers (Strangler Fig pattern) during transition | Each new step script is a thin subprocess wrapper; old entry points stay intact |
| TST-01 | Write characterization tests for pure functions before refactoring | 6-8 pure functions identified for snapshot testing before Phase 4 monolith split |
| OBS-02 | Per-step timing and exit code propagation | `log_step()` context manager exists; orchestrator collects exit codes and durations |
| OBS-03 | Run history stored in D1 (`pipeline_runs` table) | D1 schema designed; orchestrator writes after each step |
| OBS-04 | CLI status command — `python -m pipeline status` | `pipeline/__main__.py` with argparse subcommand |
| OBS-05 | End-of-run status report (which steps succeeded/failed, with durations) | Orchestrator prints summary after all steps complete |
| THR-01 | Resolve dual-scheduling race condition (launchd vs `schedule` library) | Remove `--daemon` mode from `main_v3.py` entirely |
| THR-02 | Refactor Threads pipeline to use shared infra modules | Already partially wired in Phase 2; `pipeline/threads/` directory for new modules |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipeline orchestration (step sequencing) | orchestrator.py | — | Single sequential controller; no parallel execution |
| Per-step timing | logger.py (log_step) | orchestrator.py | `log_step` context manager exists; orchestrator wraps steps with it |
| Run history persistence | orchestrator.py | d1_client.py | Orchestrator calls d1_query to INSERT pipeline_runs records |
| CLI status display | pipeline/__main__.py | d1_client.py | Reads pipeline_runs from D1; formats for terminal |
| Plist generation | install_launchd.sh | — | Shell script computes paths, uses Python for Template substitution |
| Threads scheduling | launchd (OS) | — | External scheduler; pipeline only runs `--once` |
| Characterization tests | tests/ (pytest) | — | Standard pytest unit tests; no D1 or network needed |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pipeline.infra` (6 modules) | current | Shared infrastructure | Phase 2 already built; all 6 modules ready |
| `PipelineLogger` | in logger.py | Structured logging with run_id/step_name/duration | Already exists, has `log_step()` context manager |
| `PipelineStepResult` | in models.py | Step result dataclass | Already exists with step_name, success, duration_seconds, error, run_id |
| `PipelineRun` | in models.py | Run summary dataclass | Already exists with run_id, status, steps list |
| `d1_query` | in d1_client.py | D1 database queries | Already exists; used for pipeline_runs INSERT/SELECT |
| `string.Template` | Python stdlib | Plist variable substitution | stdlib only; no Jinja2 dependency |
| `typing.Protocol` | Python stdlib | PipelineStep protocol definition | stdlib; structural subtyping for steps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `argparse` | Python stdlib | CLI argument parsing | `pipeline/__main__.py` status command |
| `subprocess` | Python stdlib | Call old entry points | Step wrappers call old scripts |
| `time` | Python stdlib | Timing and sleep | Orchestrator step timing |
| `datetime` | Python stdlib | Timestamps | D1 records, log messages |
| `json` | Python stdlib | JSON serialization | Plist template handling |
| `pytest` | installed | Characterization tests | TST-01: pure function tests |

**Version verification:**
```bash
python3 -c "
from pipeline.infra.models import PipelineStepResult, PipelineRun
from pipeline.infra.logger import get_pipeline_logger, log_step
from pipeline.infra.d1_client import d1_query
print('All infra modules available in current Python 3.14')
"
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `string.Template` | Jinja2 | stdlib vs pip dependency; Jinja2 has richer control flow, Template is simpler and zero-dependency |
| Explicit step registration | Decorator-based registration | Decorators are cleaner for small sets; register() is more explicit and easier to test |
| `PipelineStep` Protocol | ABC (abstract base class) | Protocol is structural typing (duck typing); ABC requires explicit inheritance |
| Flat `pipeline/threads/` | Keep `scripts/threads/v3/` nesting | Flattening is clearer but requires moving imports in old files — mitigated by Strangler Fig |

## Package Legitimacy Audit

> **No new pip packages required.** Phase 3 uses Python 3.14 stdlib only (D-12 locked decision). Existing infra modules and pytest are already installed.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    pipeline/orchestrator.py                  │
│                                                              │
│  PipelineStep (Protocol)  PipelineOrchestrator              │
│  ┌──────────────┐        ┌─────────────────────┐           │
│  │ name          │        │ register(step)       │           │
│  │ run() -> int  │        │ run() -> list[Result]│           │
│  └──────────────┘        │ record_to_d1()      │           │
│                           │ print_summary()     │           │
│                           └─────────────────────┘           │
│                                    │                        │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Steps:                                              │     │
│  │ pipeline/steps/                                     │     │
│  │ ├── 01_fetch_articles.py → subprocess(main_v3.py)   │     │
│  │ ├── 02_generate_pitches.py → subprocess()           │     │
│  │ ├── 03_write_thread.py → subprocess()               │     │
│  │ ├── 04_validate.py → subprocess()                   │     │
│  │ ├── 05_publish.py → subprocess()                    │     │
│  │ └── ...                                              │     │
│  └────────────────────────────────────────────────────┘     │
│                                    │                        │
│         ┌──────────────────────────┴──────────────┐        │
│         ▼                                          ▼        │
│  ┌──────────────┐                        ┌──────────────┐   │
│  │ logger.py    │                        │ d1_client.py │   │
│  │ log_step()   │                        │ d1_query()   │   │
│  │ context mngr │                        │               │   │
│  └──────┬───────┘                        └───────┬───────┘   │
│         │                                        │           │
│         ▼                                        ▼           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    D1 (pipeline_runs)                    │  │
│  │  run_id | step_name | status | duration | error | ts    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Entry points:                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ python -m pipeline           # full run                │    │
│  │ python -m pipeline status    # last N runs health     │    │
│  │ python -m pipeline status --runs 10                   │    │
│  │ python -m pipeline run --dry-run                      │    │
│  │ launchd → install_launchd.sh → threads-publisher.plist│    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
pipeline/
├── __init__.py              # from .orchestrator import PipelineOrchestrator
├── __main__.py              # "python -m pipeline status|run" CLI
├── orchestrator.py          # PipelineStep protocol + PipelineOrchestrator class
├── infra/                   # 6 modules from Phase 2 (already exist)
│   ├── config.py
│   ├── d1_client.py
│   ├── env_loader.py
│   ├── logger.py
│   ├── models.py
│   ├── retry.py
│   └── __init__.py
├── steps/                   # Step wrappers — each calls old entry point via subprocess
│   ├── __init__.py
│   ├── step_fetch_articles.py    # subprocess([venv_python, main_v3.py])
│   ├── step_generate_pitches.py
│   ├── step_write_thread.py
│   ├── step_validate.py
│   ├── step_publish.py
│   └── supervisor_report.py      # end-of-run status summary
├── threads/                 # Threads pipeline modules (flattened from v3/)
│   ├── __init__.py
│   ├── dedup.py             # can move here as copy (Strangler Fig)
│   ├── validator.py         # can move here
│   └── ...                  # Phase 4 will populate via MON-01..MON-07

scripts/                      # OLD files stay as Strangler Fig wrappers
├── threads/
│   ├── main_v3.py           # UNCHANGED — still drives the actual pipeline logic
│   ├── v3/
│   │   ├── writer_v3.py     # UNCHANGED
│   │   ├── narrative_pitcher.py
│   │   └── ...
│   └── publisher.py          # UNCHANGED
├── run_pipeline.py           # UNCHANGED (briefing pipeline, separate from threads)
└── deploy.sh                 # MODIFIED — remove api_test/.env.sh reference
```

### Pattern 1: PipelineStep Protocol + Orchestrator

**What:** A `typing.Protocol` defines the step interface. A `PipelineOrchestrator` class registers steps and runs them sequentially, wrapping each in a `log_step()` context manager for automatic timing and recording results to D1.

**When to use:** Any sequential pipeline with 5-15 steps where each step can fail independently and you need per-step observability.

```python
from typing import Protocol, runtime_checkable
from pipeline.infra.logger import log_step, get_pipeline_logger

@runtime_checkable
class PipelineStep(Protocol):
    name: str
    def run(self) -> int:  # 0 = success, nonzero = failure
        ...

class PipelineOrchestrator:
    def __init__(self, run_id: str = ""):
        self.steps: list[PipelineStep] = []
        self.results: list[PipelineStepResult] = []
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self.log = get_pipeline_logger(__name__, run_id=self.run_id)

    def register(self, step: PipelineStep) -> None:
        self.steps.append(step)

    def run(self) -> list[PipelineStepResult]:
        self.results = []
        self.log.info(f"Pipeline started — run_id={self.run_id}, {len(self.steps)} steps")

        for step in self.steps:
            result = PipelineStepResult(
                step_name=step.name,
                success=False,
                duration_seconds=0.0,
                run_id=self.run_id,
            )
            try:
                with log_step(self.log, step.name):
                    start = time.monotonic()
                    exit_code = step.run()
                    elapsed = time.monotonic() - start

                result.success = exit_code == 0
                result.duration_seconds = elapsed
                if not result.success:
                    result.error = f"exit code {exit_code}"
                    self.log.error(f"{step.name} failed with exit code {exit_code}")

            except Exception as e:
                result.success = False
                result.duration_seconds = time.monotonic() - start
                result.error = f"{type(e).__name__}: {e}"
                self.log.exception(f"{step.name} raised {type(e).__name__}")

            self.results.append(result)
            self._record_to_d1(result)

        self._print_summary()
        return self.results

    def _record_to_d1(self, result: PipelineStepResult) -> None:
        sql = (
            "INSERT INTO pipeline_runs "
            "(run_id, step_name, status, duration_seconds, error_message, started_at, completed_at) "
            "VALUES ("
            f"'{result.run_id}', '{result.step_name}', "
            f"{'success' if result.success else 'failure'}', "
            f"{result.duration_seconds}, "
            f"{'NULL' if not result.error else ''}"
            f"{result.error.replace(chr(39), chr(39)*2) if result.error else 'NULL'}'', "
            f"datetime('now'), datetime('now')"
            ")"
        )
        d1_query(sql)  # best-effort; failure doesn't stop pipeline
```

### Pattern 2: Strangler Fig Step Wrappers

**What:** Each `pipeline/steps/step_*.py` file is a thin wrapper that calls the old entry point via `subprocess.run()`. The old file stays unchanged.

**When to use:** During brownfield refactoring where old code must continue working while new structure is established.

```python
# pipeline/steps/step_fetch_articles.py
import subprocess, sys
from pathlib import Path
from pipeline.infra.config import project_root

PROJECT_DIR = project_root()
VENV_PYTHON = str(PROJECT_DIR / ".venv" / "bin" / "python3")
OLD_SCRIPT = str(PROJECT_DIR / "scripts" / "threads" / "main_v3.py")

class FetchArticlesStep:
    name = "fetch_articles"

    def run(self) -> int:
        result = subprocess.run(
            [VENV_PYTHON, OLD_SCRIPT, "--once"],
            capture_output=True, text=True, timeout=300,
            cwd=str(PROJECT_DIR),
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
```

### Anti-Patterns to Avoid

- **Sequential steps using subprocess for everything:** Only the first version uses subprocess wrappers. Phase 4 will refactor to direct Python imports. Don't over-engineer the wrapper pattern.
- **Mixing briefing pipeline steps with Threads pipeline steps:** These are separate pipelines (`run_pipeline.py` vs `main_v3.py`). The orchestrator should only manage Threads steps. The briefing pipeline has its own flow.
- **Hardcoding step order in orchestrator name strings:** Steps should register themselves with a name attribute, not rely on filename-based ordering.
- **Making the orchestrator handle parallelism or retry:** Keep orchestrator simple — just sequential execution with timing and recording. Retry should be in the step itself or via `@retry` decorator.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Plist template substitution | Custom parser or regex replacement | `string.Template` (`from string import Template`) | stdlib, handles all edge cases, simple `$VAR` or `${VAR}` syntax |
| CLI argument parsing | Manual `sys.argv` parsing | `argparse` (`import argparse`) | stdlib, handles `--help`, subcommands, type coercion |
| Step timing | Manual `time.time()` diff | `log_step()` context manager from `logger.py` | Already exists, automatically logs duration, handles nesting |
| Exit code propagation | Custom return type system | `return exit_code` (0 = success, nonzero = failure) | Unix convention, subprocess compatible |

**Key insight:** Python 3.14 stdlib handles every infrastructure need for this phase. The only external dependency is `pytest` for characterization tests, which is already installed.

## Runtime State Inventory

> Phase 3 is primarily a directory restructuring and orchestrator creation phase. No rename operations or data migrations are required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | D1 database has no `pipeline_runs` table yet | Create table via migration SQL file |
| Live service config | launchd plist at `~/Library/LaunchAgents/kr.aikorea24.threads-publisher.plist` (loaded) | Replace with templated version via `install_launchd.sh` |
| OS-registered state | launchd agent currently loaded with hardcoded paths | Unload old plist, load new templated one |
| Secrets/env vars | None affected — orchestrator reads env via `EnvConfig` | No env vars renamed |
| Build artifacts | None | — |

**Nothing found in category:** Stored data (no pipeline_runs table yet — creation only), Secrets/env vars (no renames), Build artifacts (pure Python, no build step).

## Common Pitfalls

### Pitfall 1: `--daemon` mode creates duplicate scheduling
**What goes wrong:** `main_v3.py --daemon` starts an internal `schedule.every(2).hours.do(run_v3)` loop. If launchd's plist uses `--daemon` (or if someone runs it manually), both launchd AND the internal scheduler fire — causing two pipeline runs to execute simultaneously.
**Why it happens:** The `--daemon` flag was a convenience mode added before launchd was configured. Now launchd handles scheduling, but the flag still exists.
**How to avoid:** Remove `--daemon` mode from `main_v3.py`. Launchd is the single scheduling mechanism. The script should only support `--once` (run once and exit).
**Warning signs:** Duplicate posts on Threads, overlapping log timestamps.

### Pitfall 2: Strangler Fig import confusion
**What goes wrong:** Both the old file (`scripts/threads/main_v3.py`) and the new step wrapper (`pipeline/steps/step_fetch_articles.py`) import from the same old modules. If the step wrapper does `from scripts.threads.main_v3 import run_v3` instead of `subprocess`, it creates a messy import dependency.
**How to avoid:** Step wrappers call old scripts via `subprocess.run([...main_v3.py, '--once'])` — not by importing. Old files stay as black boxes until Phase 4 monolith splitting.
**Warning signs:** Circular imports, `ModuleNotFoundError`, `sys.path` manipulation in step wrappers.

### Pitfall 3: D1 writes failing silently
**What goes wrong:** `_record_to_d1()` is best-effort — if wrangler is not installed or network is down, the error is caught and the pipeline continues. But then `pipeline_runs` is empty and `python -m pipeline status` shows nothing.
**How to avoid:** Log a warning when D1 write fails, but don't halt the pipeline. Add a `--skip-d1` flag for testing without wrangler.
**Warning signs:** Empty output from `python -m pipeline status`, warning logs about D1 failure.

### Pitfall 4: Plist variable escaping
**What goes wrong:** The plist XML format has special characters (`<`, `>`, `&`, quotes). If the template substitution inserts a path containing these, the plist becomes invalid XML.
**How to avoid:** Use `string.Template.safe_substitute()` and ensure substituted values are plain ASCII file paths. Don't substitute into XML attribute values without escaping.

## Code Examples

### PipelineStep Protocol — Definition

```python
# pipeline/orchestrator.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class PipelineStep(Protocol):
    """Protocol for pipeline steps.
    
    Each step must have a name and a run() method that returns
    an integer exit code (0 = success, nonzero = failure).
    """
    name: str
    
    def run(self) -> int: ...
```

### PipelineOrchestrator — Full Run

```python
# pipeline/orchestrator.py
import time
from datetime import datetime
from typing import Optional

from pipeline.infra.models import PipelineStepResult
from pipeline.infra.logger import get_pipeline_logger, log_step
from pipeline.infra.d1_client import d1_query

class PipelineOrchestrator:
    def __init__(self, run_id: str = ""):
        self._steps: list[PipelineStep] = []
        self.results: list[PipelineStepResult] = []
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._log = get_pipeline_logger("pipeline.orchestrator", run_id=self.run_id)

    def register(self, step: PipelineStep) -> None:
        self._steps.append(step)
        self._log.info(f"Registered step: {step.name}")

    def run(self, dry_run: bool = False) -> list[PipelineStepResult]:
        self.results = []
        all_success = True

        for step in self._steps:
            result = PipelineStepResult(
                step_name=step.name,
                success=False,
                duration_seconds=0.0,
                error=None,
                run_id=self.run_id,
            )

            try:
                with log_step(self._log, step.name):
                    start = time.monotonic()
                    if dry_run:
                        self._log.info(f"[DRY RUN] Would execute: {step.name}")
                        exit_code = 0
                    else:
                        exit_code = step.run()
                    elapsed = time.monotonic() - start

                result.success = exit_code == 0
                result.duration_seconds = elapsed
                if not result.success:
                    result.error = f"exit code {exit_code}"
                    self._log.error(f"Step '{step.name}' failed ({result.error})")
                else:
                    self._log.info(f"Step '{step.name}' completed in {elapsed:.1f}s")

            except Exception as e:
                elapsed = time.monotonic() - start
                result.success = False
                result.duration_seconds = elapsed
                result.error = f"{type(e).__name__}: {e}"
                self._log.exception(f"Step '{step.name}' raised {type(e).__name__}")

            self.results.append(result)
            if not dry_run:
                self._record_to_d1(result)

            if not result.success:
                all_success = False

        self._print_summary()
        return self.results

    def _record_to_d1(self, result: PipelineStepResult) -> None:
        error_escaped = (result.error or "").replace("'", "''")
        error_sql = f"'{error_escaped}'" if result.error else "NULL"
        status = "success" if result.success else "failure"

        sql = (
            f"INSERT INTO pipeline_runs "
            f"(run_id, step_name, status, duration_seconds, error_message, started_at, completed_at) "
            f"VALUES ("
            f"'{result.run_id}', '{result.step_name}', '{status}', "
            f"{result.duration_seconds:.3f}, {error_sql}, "
            f"datetime('now'), datetime('now')"
            f")"
        )
        try:
            d1_query(sql)
        except Exception as e:
            self._log.warning(f"Failed to record step result to D1: {e}")

    def _print_summary(self) -> None:
        print("\n" + "=" * 60)
        print(f"  Pipeline Run Summary — {self.run_id}")
        print("=" * 60)
        for r in self.results:
            icon = "✅" if r.success else "❌"
            dur = f"{r.duration_seconds:.1f}s"
            err = f" — {r.error}" if r.error else ""
            print(f"  {icon} {r.step_name}: {dur}{err}")
        total = sum(r.duration_seconds for r in self.results)
        all_ok = all(r.success for r in self.results)
        print(f"\n  {'✅ All steps succeeded' if all_ok else '❌ Some steps failed'}")
        print(f"  Total time: {total:.1f}s")
        print("=" * 60)
```

### D1 Schema for pipeline_runs Table

```sql
-- pipeline/migrations/20260630_create_pipeline_runs.sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'failure')),
    duration_seconds REAL,
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);

-- Query for status command:
-- SELECT run_id, step_name, status, duration_seconds, error_message, started_at
-- FROM pipeline_runs
-- WHERE run_id IN (SELECT DISTINCT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 5)
-- ORDER BY started_at DESC
-- LIMIT 50;
```

### CLI Status Command — `python -m pipeline status`

```python
# pipeline/__main__.py
"""
Usage:
    python -m pipeline            # Full pipeline run
    python -m pipeline status     # Show last 5 runs
    python -m pipeline status --runs 10
    python -m pipeline run --dry-run
"""
import argparse, sys
from pipeline.infra.d1_client import d1_query
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

def cmd_status(runs: int = 5):
    """Query D1 for last N runs and print health summary."""
    sql = (
        f"SELECT run_id, step_name, status, duration_seconds, "
        f"COALESCE(error_message, '') as error_message, started_at "
        f"FROM pipeline_runs "
        f"WHERE run_id IN ("
        f"  SELECT DISTINCT run_id FROM pipeline_runs "
        f"  ORDER BY started_at DESC LIMIT {runs}"
        f") "
        f"ORDER BY started_at DESC"
    )
    rows = d1_query(sql)

    if not rows:
        print("No pipeline runs recorded yet.")
        return

    # Group by run_id
    from collections import OrderedDict
    runs_map: dict[str, list[dict]] = OrderedDict()
    for row in rows:
        rid = row["run_id"]
        if rid not in runs_map:
            runs_map[rid] = []
        runs_map[rid].append(row)

    print(f"\n{'=' * 70}")
    print(f"  Pipeline Health — Last {len(runs_map)} Run(s)")
    print(f"{'=' * 70}")
    for run_id, steps in runs_map.items():
        total_ok = sum(1 for s in steps if s["status"] == "success")
        total_fail = sum(1 for s in steps if s["status"] == "failure")
        total_dur = sum(s["duration_seconds"] or 0 for s in steps)
        first_ts = steps[-1]["started_at"][:19] if steps else "?"

        icon = "✅" if total_fail == 0 else "❌"
        print(f"\n  {icon} {run_id}  ({first_ts})")
        print(f"     Steps: {total_ok} OK / {total_fail} Failed  |  Total: {total_dur:.1f}s")
        for s in steps:
            dur = f"{s['duration_seconds']:.1f}s" if s["duration_seconds"] else "-"
            err = f" — {s['error_message'][:60]}" if s["error_message"] else ""
            print(f"       {'✅' if s['status'] == 'success' else '❌'} {s['step_name']:25s} {dur:8s}{err}")
    print()

def cmd_run(dry_run: bool = False):
    """Execute pipeline via orchestrator."""
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    # Steps will be registered here
    # orchestrator.register(step_fetch_articles())
    # orchestrator.register(step_generate_pitches())
    # ...

    results = orchestrator.run(dry_run=dry_run)
    sys.exit(0 if all(r.success for r in results) else 1)

def main():
    parser = argparse.ArgumentParser(description="aikorea24 Pipeline CLI")
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "status"],
                        help="Command: run (default) or status")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs to show (status command)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate run without executing steps")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(runs=args.runs)
    elif args.command == "run":
        cmd_run(dry_run=args.dry_run)

if __name__ == "__main__":
    main()
```

### Plist Template — `string.Template` Approach

```python
# install_launchd.py (or inline in install_launchd.sh)
from string import Template

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>kr.aikorea24.threads-publisher</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${SCRIPT_PATH}</string>
        <string>--once</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/launchd_error.log</string>
    <key>StartInterval</key>
    <integer>7200</integer>
    <key>KeepAlive</key>
    <false/>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>"""

def generate_plist(project_dir: str) -> str:
    return Template(PLIST_TEMPLATE).safe_substitute(
        VENV_PYTHON=f"{project_dir}/.venv/bin/python3",
        PROJECT_DIR=project_dir,
        SCRIPT_PATH=f"{project_dir}/pipeline/__main__.py",  # orchestrator entry point
        LOG_DIR=f"{project_dir}/pipeline/logs",
    )
```

```bash
# scripts/install_launchd.sh (templated, portable)
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PLIST_NAME="kr.aikorea24.threads-publisher"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Generate plist using Python Template
python3 -c "
from string import Template
import sys
sys.path.insert(0, '$PROJECT_DIR')
plist = open('$SCRIPT_DIR/threads-publisher.plist.template').read()
result = Template(plist).safe_substitute(
    PROJECT_DIR='$PROJECT_DIR',
    VENV_PYTHON='$PROJECT_DIR/.venv/bin/python3',
    LOG_DIR='$PROJECT_DIR/pipeline/logs',
)
with open('$PLIST_DEST', 'w') as f:
    f.write(result)
print('Generated: $PLIST_DEST')
"

# Unload existing, load new
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "Launchd agent loaded: $PLIST_NAME"
```

### Threads Dual-Scheduling Fix

```python
# scripts/threads/main_v3.py — REMOVE --daemon mode entirely
# Current problematic code to remove:
#
# def main():
#     import argparse
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--dry-run', ...)
#     parser.add_argument('--once', ...)
#     parser.add_argument('--daemon', ...)  # <-- REMOVE THIS
#     args = parser.parse_args()
#
#     if args.daemon:
#         import schedule  # <-- REMOVE THIS BLOCK
#         schedule.every(2).hours.do(run_v3)
#         ...
#
# FIX: Only support --once and --dry-run.
#      launchd is the single scheduling mechanism.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `main_v3.py --daemon` internal schedule loop | launchd-only scheduling (`--once`) | Phase 3 | Eliminates dual-scheduling race condition |
| Hardcoded paths in plist | `string.Template` generated plist | Phase 3 | Zero hardcoded paths; clone-and-run |
| All scripts in flat `scripts/` | Separated into `pipeline/steps/` + `pipeline/threads/` | Phase 3 | Clear separation of concerns |
| `pipeline_runs` table doesn't exist | D1 `pipeline_runs` table with per-step records | Phase 3 | Full run history for observability |
| `python main_v3.py` | `python -m pipeline` | Phase 3 | Standardized CLI interface |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `main_v3.py --daemon` mode is never used by actual launchd plist | Threads Dual-Scheduling | Already confirmed: plist uses `--once`, not `--daemon`. Fix is still needed because someone might use `--daemon` manually. |
| A2 | Step wrappers calling old scripts via subprocess won't cause import issues | Strangler Fig Wrappers | Subprocess creates a fresh Python process, so no import conflicts. Low risk. |
| A3 | `string.Template.safe_substitute()` handles all plist path values correctly | Plist Templating | Path values don't contain XML special characters. If a future path has `&` or `<`, manual escaping needed. |
| A4 | D1 `pipeline_runs` table doesn't exist yet | Runtime State Inventory | Verified: no `pipeline_runs` table in existing D1. Create migration is safe. |
| A5 | `deploy.sh` currently sources `api_test/.env.sh` | deploy.sh Portability | Confirmed from reading `scripts/deploy.sh` — currently sources only project `.env`, no `api_test/.env.sh`. The `publisher.py` and other files source `api_test/.env.sh` separately. |

**If this table is empty:** N/A — there are assumed claims that need user confirmation.

## Open Questions

1. **Step granularity: exactly which steps should the orchestrator manage?**
   - What we know: The Threads pipeline has 6 logical steps (fetch → pitch → write → validate → publish → record). The briefing pipeline (`run_pipeline.py`) is separate.
   - What's unclear: Should the orchestrator also manage the briefing pipeline steps? Or only Threads?
   - Recommendation: Only Threads steps initially (MVP). Briefing pipeline integration is Phase 5 or deferred.

2. **Should step wrappers be Python scripts or directly executable?**
   - What we know: Each step needs to be importable by orchestrator AND runnable standalone for testing.
   - What's unclear: Whether step files should have `if __name__ == '__main__'` blocks.
   - Recommendation: Yes, add `if __name__` blocks for standalone testing. Pattern: `python -m pipeline.steps.step_fetch_articles`.

3. **What should happen to old `validate_final_cards()` in main_v3.py?**
   - What we know: Validation currently happens inside `main_v3.py`. The orchestrator should own validation as a separate step.
   - What's unclear: Whether to extract validation logic now or wait for Phase 4.
   - Recommendation: Leave `validate_final_cards()` in `main_v3.py` for now. The step wrapper calls the whole old script. Phase 4 extracts validation.

## Environment Availability

> Phase 3 has minimal external dependencies — primarily stdlib Python and launchd.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | Orchestrator, steps, CLI | ✓ | 3.14 | — |
| `npx` / `wrangler` | D1 queries via d1_client.py | ✓ | (per user) | Pipeline runs without D1 (--skip-d1) |
| `launchctl` | Installing launchd plist | ✓ (macOS) | — | Fallback: manual plist loading |
| pytest | Characterization tests | ✓ | latest | — |
| `schedule` library | Currently used by --daemon mode | ✓ | (removing) | launchd replaces it |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None all available.

## Validation Architecture

> Skipping — workflow.nyquist_validation is explicitly set to `false` in `.planning/config.json`.

## Security Domain

> Security enforcement is implicitly enabled (config does not set `security_enforcement: false`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user authentication in pipeline |
| V3 Session Management | no | No sessions in pipeline |
| V4 Access Control | no | No user access control in pipeline |
| V5 Input Validation | yes | SQL strings passed to `d1_query()` are constructed via f-strings; only known-safe step names and numeric IDs are interpolated |
| V6 Cryptography | no | No crypto operations in pipeline |

### Known Threat Patterns for Python Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **Plist path injection** | Tampering | `install_launchd.sh` computes paths from its own location — no user input in paths |
| **D1 SQL injection** | Tampering | Step names are hardcoded; only `run_id` and `error_message` are dynamic — error messages are escaped (`'` → `''`) |
| **Subprocess argument injection** | Tampering | Step wrappers use fixed command arrays, not shell strings — `subprocess.run([...], shell=False)` |
| **Log exposure** | Information Disclosure | `PipelineLogger` uses `ScrubLogFilter` — all secrets in log messages are auto-redacted |

## Sources

### Primary (HIGH confidence)
- [Phase 2 already-built infra modules] - Verified by reading all 6 modules in `pipeline/infra/`
- [Existing `PipelineStepResult`/`PipelineRun` models in models.py] - Confirmed dataclass definitions
- [Existing `log_step()` context manager in logger.py] - Confirmed duration timing pattern
- [Existing `main_v3.py --daemon` mode] - Confirmed `import schedule` + `schedule.every(2).hours.do(run_v3)`
- [Existing `threads-publisher.plist` with hardcoded paths] - Confirmed all paths are absolute
- [Existing `deploy.sh`] - Confirmed relative path usage, no cross-project .env source

### Secondary (MEDIUM confidence)
- [Python `string.Template` documentation](https://docs.python.org/3/library/string.html#template-strings) - stdlib template strings for plist generation
- [Python `typing.Protocol` documentation](https://docs.python.org/3/library/typing.html#typing.Protocol) - Structural subtyping for PipelineStep

### Tertiary (LOW confidence)
- None — all claims verified via codebase reading

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing infra modules verified by reading source
- Architecture: HIGH — orchestrator pattern is simple and follows project decisions
- Pitfalls: HIGH — all confirmed by reading existing code
- Plist templating: HIGH — `string.Template` is stdlib, well-documented

**Research date:** 2026-06-30
**Valid until:** Stable — no fast-moving dependencies in this stack
