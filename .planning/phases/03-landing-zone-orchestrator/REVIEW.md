---
phase: 03-landing-zone-orchestrator
reviewed: 2026-06-30T22:00:00Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - pipeline/orchestrator.py
  - pipeline/__main__.py
  - pipeline/__init__.py
  - pipeline/steps/__init__.py
  - pipeline/steps/step_run_threads.py
  - pipeline/threads/__init__.py
  - pipeline/migrations/20260630_create_pipeline_runs.sql
  - pipeline/infra/d1_client.py
  - pipeline/infra/models.py
  - scripts/threads/main_v3.py
  - scripts/threads/threads-publisher.plist.template
  - scripts/install_launchd.sh
  - scripts/deploy.sh
findings:
  critical: 1
  warning: 6
  info: 6
  total: 13
status: issues_found
---

# Phase 3: Code Review Report — Landing Zone & Orchestrator

**Reviewed:** 2026-06-30T22:00:00Z
**Depth:** deep
**Files Reviewed:** 13
**Status:** issues_found

## Summary

The Phase 3 implementation introduces the pipeline orchestration framework (PipelineStep protocol, PipelineOrchestrator, D1 recording, subprocess-based step wrappers, launchd integration, and characterization tests). The architecture is sound (Strangler Fig pattern), but several concrete defects were identified:

1. **Critical:** `cmd_run()` registers zero steps — the orchestrator pipeline does nothing when invoked.
2. **Critical-adjacent:** `--once` flag in `main_v3.py` is parsed but completely ignored (vestigial from daemon removal), misleading callers.
3. SQL injection surface in D1 query construction despite explicit safety claims.
4. Several error-handling gaps (unbound `start` variable, misleading D1 failure messages, missing path validation).
5. Shell-script quoting vulnerability in `install_launchd.sh`.

The 13 added/modified tests pass, but they import from `validator.py` which has a machine-specific path in its `__main__` block — this doesn't affect test hermeticity but signals incomplete cleanup.

---

## Critical Issues

### CR-01: Orchestrator pipeline runs with zero registered steps — no-op execution

**File:** `pipeline/__main__.py:78-89`
**Issue:** `cmd_run()` creates a `PipelineOrchestrator` but registers zero steps:

```python
def cmd_run(dry_run: bool = False) -> None:
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    # Steps registered here — uncomment when pipeline/steps/ exists
    # orchestrator.register(StepFetchArticles())
    # orchestrator.register(StepGeneratePitches())
    # orchestrator.register(StepWriteThread())
    # orchestrator.register(StepValidate())
    # orchestrator.register(StepPublish())

    results = orchestrator.run(dry_run=dry_run)
    sys.exit(0 if all(r.success for r in results) else 1)
```

`orchestrator.run()` iterates over an empty `_steps` list, returns an empty `results` list, and `all()` on an empty iterable returns `True` (vacuous truth). The pipeline exits with code 0 having done literally nothing.

Meanwhile, `pipeline/steps/__init__.py` already exports `StepRunThreads`, but nothing in `__main__.py` imports it. The pipeline entry point as shipped is a no-op.

**Fix:** Import and register the available step:

```python
def cmd_run(dry_run: bool = False) -> None:
    from pipeline.orchestrator import PipelineOrchestrator
    from pipeline.steps import StepRunThreads

    orchestrator = PipelineOrchestrator()
    orchestrator.register(StepRunThreads())
    results = orchestrator.run(dry_run=dry_run)
    sys.exit(0 if all(r.success for r in results) else 1)
```

---

## Warnings

### WR-01: `--once` flag parsed but completely ignored in `main_v3.py`

**File:** `scripts/threads/main_v3.py:328-336`
**Issue:** The `--once` argument is declared in argparse but `args.once` is never read:

```python
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='...')
    parser.add_argument('--once', action='store_true', help='1회 실행 (launchd 전용 — 단일 스케줄러)')
    args = parser.parse_args()

    run_v3(dry_run=args.dry_run)  # --once ignored!
```

The `--once` flag was retained when `--daemon` was removed (THR-01), but it no longer controls any behavior. `step_run_threads.py` calls `main_v3.py --once` believing it's requesting single-run mode. The plist template also includes `--once`. While the runtime behavior happens to be correct (every invocation runs once), this is misleading:

1. If someone runs `main_v3.py` without `--once`, the behavior is identical.
2. The flag clutters the public API with dead code.
3. If a future developer tries to add a daemon/loop mode, the flag semantics are ambiguous.

**Fix:** Either wire the flag (make it do something meaningful, e.g., validate it's always set in production) or remove it entirely:

```python
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='발행 없이 글만 생성')
    args = parser.parse_args()
    run_v3(dry_run=args.dry_run)
```

And update `step_run_threads.py` and the plist template to stop passing `--once`.

---

### WR-02: SQL injection vulnerability in `_record_to_d1` despite anti-injection claim

**File:** `pipeline/orchestrator.py:105-128`
**Issue:** Line 109 claims "SQL 인젝션 방지: error_message 내 작은따옴표는 두 배로 이스케이프", but the implementation only escapes single quotes in `error_message`. The `run_id` and `step_name` fields are interpolated directly without ANY escaping:

```python
sql = (
    f"INSERT INTO pipeline_runs "
    f"(run_id, step_name, status, duration_seconds, error_message, started_at, completed_at) "
    f"VALUES ("
    f"'{result.run_id}', '{result.step_name}', '{status}', "
    #    ^ NOT escaped        ^ NOT escaped
    f"{result.duration_seconds:.3f}, {error_sql}, "
    f"datetime('now'), datetime('now')"
    f")"
)
```

Currently all three values are internally controlled (not user-supplied), so exploitation is not immediately possible. However:
- The comment creates a false sense of security.
- If `run_id` or `step_name` ever becomes user-facing (e.g., CLI argument, config file), this becomes exploitable.
- The partial escaping (only `error_message`) suggests incomplete understanding of the threat model.

**Fix:** Apply parameterized queries or escape ALL interpolated string values consistently. If the `d1_query` API doesn't support parameterized queries (it ignores `params` — see WR-03), use `repr()` or a dedicated escape function:

```python
def _sql_escape(value: str) -> str:
    """Escape a string for safe SQL interpolation."""
    return "'" + value.replace("'", "''") + "'"

# Then use:
sql = (
    f"INSERT INTO pipeline_runs ... VALUES ("
    f"{_sql_escape(result.run_id)}, {_sql_escape(result.step_name)}, "
    f"'{status}', {result.duration_seconds:.3f}, {error_sql}, ..."
)
```

---

### WR-03: `d1_query()` accepts `params` argument but silently ignores it

**File:** `pipeline/infra/d1_client.py:27-32`
**Issue:** The function signature declares `params: Optional[dict] = None` but the implementation immediately discards it:

```python
def d1_query(
    sql: str,
    params: Optional[dict] = None,
    retries: int = 2,
) -> list[dict]:
    _ = params  # unused — silently discarded
```

This is a misleading API that:
1. Suggests parameterized query support where none exists.
2. Tempts callers into passing unsanitized parameters (see WR-02).
3. Adds noise to the function signature for no benefit.

**Fix:** Remove the `params` parameter entirely. If parameterized queries are desired in the future, implement them properly (e.g., construct the D1 binding's parameterized query format):

```python
def d1_query(sql: str, retries: int = 2) -> list[dict]:
    ...
```

---

### WR-04: `cmd_status` conflates "no data" with "query failed"

**File:** `pipeline/__main__.py:39-43`
**Issue:** `cmd_status` treats an empty `d1_query()` result as "no pipeline runs":

```python
rows = d1_query(sql)
if not rows:
    print("No pipeline runs recorded yet.")
    return
```

But `d1_query()` returns `[]` on BOTH "query succeeded with zero rows" AND "query failed" (network error, timeout, wrangler not found). From `d1_client.py`:

```python
def d1_query(...) -> list[dict]:
    ...
    for attempt in range(retries):
        ...
        if r.returncode != 0:
            ...
            continue
        return _parse_result(r.stdout)
    return []   # <-- returns [] on total failure
```

When D1 is unreachable, the user sees a misleading "No pipeline runs" message instead of an error alert.

**Fix:** Distinguish failure from empty results. Either log the `last_error` and print a warning, or return a separate error indicator:

```python
rows = d1_query(sql)
if rows is None:
    print("Error: D1 query failed. Check pipeline/infra/d1_client.py configuration.")
    return
if not rows:
    print("No pipeline runs recorded yet.")
    return
```

(Requires changing `d1_query` to return `None` on failure vs `[]` on empty results.)

---

### WR-05: Shell variable expansion in double-quoted Python string — quoting vulnerability

**File:** `scripts/install_launchd.sh:28-46`
**Issue:** Shell variables are expanded inside a double-quoted inline Python script. If any path contains a single quote (`'`), the Python string literal breaks:

```bash
python3 -c "
from string import Template
...
result = Template(template_content).safe_substitute(
    VENV_PYTHON='$PROJECT_DIR/.venv/bin/python3',
    PROJECT_DIR='$PROJECT_DIR',
    SCRIPT_PATH='$PROJECT_DIR/pipeline/__main__.py',
    LOG_DIR='$PROJECT_DIR/scripts/threads/logs',
)
...
"
```

If `$PROJECT_DIR` (derived from `"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`) contains a single quote character — unlikely but possible with unusual directory names — the Python string assignment `'$PROJECT_DIR/...'` would break, potentially causing code injection or silent failure.

**Fix:** Use a heredoc with quoted delimiter to prevent shell expansion, or pass variables via environment:

```bash
python3 - << 'PYEOF'
import os
from string import Template

project_dir = os.environ['PROJECT_DIR']
template_path = os.environ['TEMPLATE']
plist_dest = os.environ['PLIST_DEST']

with open(template_path) as f:
    template_content = f.read()

result = Template(template_content).safe_substitute(
    VENV_PYTHON=f'{project_dir}/.venv/bin/python3',
    PROJECT_DIR=project_dir,
    SCRIPT_PATH=f'{project_dir}/pipeline/__main__.py',
    LOG_DIR=f'{project_dir}/scripts/threads/logs',
)

with open(plist_dest, 'w') as f:
    f.write(result)
print(f'plist generated: {plist_dest}')
PYEOF
```

And set `PROJECT_DIR`, `TEMPLATE`, `PLIST_DEST` as environment variables before the Python call.

---

### WR-06: `--runs` argument silently accepted by `run` command

**File:** `pipeline/__main__.py:102-107`
**Issue:** The `--runs` argument is defined at the top-level parser but only consumed by `cmd_status`. Running `python -m pipeline run --runs 10` silently accepts the flag and ignores it:

```python
parser.add_argument(
    "--runs",
    type=int,
    default=5,
    help="Number of runs to show (status command)",
)
```

This can confuse users who expect `--runs` to limit something during execution. It should either:
- Be scoped to the `status` subcommand via subparsers, or
- Be defined with `dest` pointing to a status-specific namespace, or
- Show a warning when passed with `run`.

**Fix:** Use argparse subparsers to scope arguments per command:

```python
parser = argparse.ArgumentParser(description="aikorea24 Pipeline CLI")
subparsers = parser.add_subparsers(dest="command")

run_parser = subparsers.add_parser("run", help="Run the pipeline")
run_parser.add_argument("--dry-run", action="store_true", ...)

status_parser = subparsers.add_parser("status", help="Show run history")
status_parser.add_argument("--runs", type=int, default=5, ...)
```

---

## Info

### IN-01: `start` variable potentially unbound in `except` handler

**File:** `pipeline/orchestrator.py:88-93`
**Issue:** Inside the `try` block, `start = time.monotonic()` is defined inside `with log_step(...)`. If the `with` statement's `__enter__` phase raises an exception (e.g., if the logger's `extra` attribute is somehow missing), `start` would be unbound when the `except` handler references it:

```python
try:
    with log_step(self._log, step.name):
        start = time.monotonic()   # never reached if __enter__ raises
        ...
except Exception as e:
    elapsed = time.monotonic() - start  # UnboundLocalError if start never assigned
```

While practically impossible with the current `PipelineLogger` implementation (which always has `extra`), this is a defensive coding gap. An `UnboundLocalError` here would mask the original exception.

**Fix:** Initialize `start = 0.0` before the try block, or set `elapsed = 0.0` in the except handler without referencing `start`:

```python
start = time.monotonic()  # move outside the with block
try:
    with log_step(self._log, step.name):
        if dry_run:
            ...
        else:
            exit_code = step.run()
    elapsed = time.monotonic() - start
except Exception as e:
    elapsed = time.monotonic() - start  # now always safe
```

But be aware: moving `start` outside `with log_step` means the timer starts before the log_step overhead rather than after. The original intent was to time only the step body. A more precise fix keeps `start` in the `try` but ensures it's assigned:

```python
start = 0.0  # default
try:
    ...
```

---

### IN-02: Virtual environment and script paths not validated before subprocess call

**File:** `pipeline/steps/step_run_threads.py:29-35`
**Issue:** `VENV_PYTHON` and `OLD_SCRIPT` paths are computed but never checked for existence before being used in `subprocess.run`:

```python
result = subprocess.run(
    [VENV_PYTHON, OLD_SCRIPT, "--once"],
    ...
)
```

If the virtual environment is missing, `.venv/bin/python3` doesn't exist, or `main_v3.py` was moved, the error from `subprocess` (e.g., `FileNotFoundError`) is caught by the generic `except Exception` handler, producing a less useful error message.

**Fix:** Validate path existence in `run()` or lazily during class construction:

```python
def __init__(self):
    if not Path(VENV_PYTHON).exists():
        raise FileNotFoundError(f"Virtual environment python not found: {VENV_PYTHON}")
    if not Path(OLD_SCRIPT).exists():
        raise FileNotFoundError(f"Script not found: {OLD_SCRIPT}")
```

---

### IN-03: `StepRunThreads` exported but never imported in `__main__.py`

**File:** `pipeline/steps/__init__.py:4-6` and `pipeline/__main__.py:78-89`
**Issue:** The `steps` package exports `StepRunThreads`, and `step_run_threads.py` has a working standalone mode (`if __name__ == "__main__":`), but `cmd_run()` in `__main__.py` does not import or register it. The step exists as a ready-to-use component but is disconnected from the pipeline entry point.

**Fix:** Import and register `StepRunThreads` in `cmd_run()` (see CR-01 for the code).

---

### IN-04: `__all__` in `pipeline/__init__.py` references protocol class that is not a concrete export

**File:** `pipeline/__init__.py:4`
**Issue:** The package exports `PipelineStep` (a `Protocol`) at the top level. Protocols are typing constructs, typically not re-exported from package public APIs. Downstream code should type-annotate with `PipelineStep` from `orchestrator` directly.

**Fix:** This is a style choice, but consider whether `PipelineStep` needs to be part of the public API surface at the package level. If consumers only use `PipelineOrchestrator`, the protocol import is noise.

---

### IN-05: `test_characterization_pure_functions.py` imports `validate_thread` from `validator.py` which has a machine-specific path

**File:** `scripts/threads/validator.py:73`
**Issue:** The `if __name__ == "__main__"` block in `validator.py` contains a hardcoded user-specific path:

```python
if __name__ == '__main__':
    import glob
    drafts = sorted(glob.glob('/Users/twinssn/Projects/aikorea24/scripts/threads/logs/drafts/*.txt'))
```

This does not affect test execution (the block only runs when `validator.py` is invoked directly), but it's a leftover from development that will cause confusing errors on any other machine. The test files themselves are clean.

**Fix:** Remove the `__main__` block or make it path-relative:

```python
if __name__ == '__main__':
    import glob
    from pathlib import Path
    drafts_dir = Path(__file__).parent / 'logs' / 'drafts'
    drafts = sorted(glob.glob(str(drafts_dir / '*.txt')))
```

---

### IN-06: Commented-out code persists in committed `cmd_run`

**File:** `pipeline/__main__.py:82-86`
**Issue:** Five lines of commented-out step registrations remain in the committed code:

```python
    # Steps registered here — uncomment when pipeline/steps/ exists
    # orchestrator.register(StepFetchArticles())
    # orchestrator.register(StepGeneratePitches())
    # orchestrator.register(StepWriteThread())
    # orchestrator.register(StepValidate())
    # orchestrator.register(StepPublish())
```

These reference step classes that do not yet exist (`StepFetchArticles`, `StepGeneratePitches`, etc.), creating dead code and stale references. Either remove them or replace with a TODO comment pointing to the issue tracker.

**Fix:** Remove the commented-out block and register the one step that exists:

```python
    orchestrator.register(StepRunThreads())
```

---

## Structural Findings (fallow)

*No structural pre-pass was provided for this review phase.*

---

_Reviewed: 2026-06-30T22:00:00Z_
_Reviewer: gsd-code-reviewer (deep mode)_
_Depth: deep_
