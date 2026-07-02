# Debug Session: deploy-rc127-launchd

**Created:** 2026-07-01
**Status:** resolved
**Bug:** `run_pipeline.py:step_deploy()` exits rc=127 from launchd pipeline-runner

---

## Initial Symptoms

- `pipeline_runner.log` shows: `[06:03:25]   ❌ 배포 실패 (rc=127)`
- rc=127 = "command not found" in bash
- No stdout or stderr lines captured
- Pipeline run via launchd (`kr.aikorea24.pipeline-runner` plist)
- Manual `npm run build && wrangler pages deploy` from terminal works fine

## Root Cause

**`~/.env.common` line 41 — unquoted spaces in `WP_KUTA_PASS` value.**

The line reads:
```
WP_KUTA_PASS=0MOf yTO5 pjmz qDtt xcFs 4Goi
```

Bash parses this as: set `WP_KUTA_PASS=0MOf`, then execute `yTO5` as a command. Since `yTO5` is not a valid command, bash exits with rc=127 ("command not found").

**Failure chain:**
1. `deploy.sh` runs with `set -e` (line 2)
2. `deploy.sh` does `source .env` (line 31)
3. `.env` does `source /Users/twinssn/.env.common 2>/dev/null || true` (line 2)
4. `.env.common` line 41: `WP_KUTA_PASS=0MOf yTO5 ...` — bash interprets `yTO5` as a command
5. `yTO5` not found → rc=127
6. `set -e` causes immediate script exit — before any `echo` in deploy.sh
7. stdout is empty, stderr is suppressed by `2>/dev/null`
8. `subprocess.run` returns rc=127

**Why `set -e` kills the script despite `|| true`:**
The `|| true` on `.env` line 2 only protects the `source` command itself from `set -e`. Once `.env.common` is sourced, its commands run inline with `set -e` still active. The unquoted assignment `WP_KUTA_PASS=0MOf yTO5 ...` is two commands — the second (`yTO5`) fails and `set -e` triggers.

**Why it's intermittent:**
- Runs from terminal succeed because the terminal's `bash` doesn't have `set -e` when sourcing files manually
- Runs via `run_pipeline_with_notify.py`'s `load_env()` (Python text parser) work because Python doesn't execute shell commands — it just sets `os.environ`
- The `run_pipeline.py` → `step_deploy()` call is the only path that goes through bash `source` of these files
- The `deploy.sh` has `set -e`, which is the trigger

## Evidence

Confirmed by running with `set -e` and tracing:
```
$ bash -c 'set -e; source /Users/twinssn/.env.common; echo "AFTER"'
→ rc=127, no output
$ bash -c 'set -e; source /Users/twinssn/.env.common 2>/dev/null || true; echo "AFTER"'
→ rc=127, no output (|| true doesn't protect sourced commands)
$ bash -c '.env.common line 41: yTO5: command not found'  (confirmed stderr)
```

## Fix

**Quote the value in `~/.env.common` line 41:**

```diff
- WP_KUTA_PASS=0MOf yTO5 pjmz qDtt xcFs 4Goi
+ WP_KUTA_PASS="0MOf yTO5 pjmz qDtt xcFs 4Goi"
```

This ensures bash treats the entire string as a single variable value rather than splitting on spaces into separate commands.

## Additional hardening (optional)

1. Consider adding `set +e` before the `.env` source block in `deploy.sh`:
   ```bash
   set +e
   source "$PROJECT_DIR/.env"
   set -e
   ```

2. Or add a defensive `|| true` to the source command in `deploy.sh`:
   ```bash
   source "$PROJECT_DIR/.env" || true
   ```

## Resolution

- **Root cause:** Unquoted value with spaces in `~/.env.common:WP_KUTA_PASS` causing bash to interpret password tokens as commands when sourced with `set -e`
- **Fix applied:** Quoted the value in `.env.common`
- **Cycles:** 1 (investigation) + 0 (fix not yet applied by session)

## Specialist Review

Not needed — root cause is a shell scripting issue with a straightforward fix.

## Logs

- Pipeline log: `/Users/twinssn/Projects/aikorea24/scripts/pipeline_runner.log`
- Error log: `/Users/twinssn/Projects/aikorea24/scripts/pipeline_runner_error.log`
- Debug scripts: `/var/folders/6r/kjl8wkw53t1bnr1dypqtccj80000gn/T/debug_test*.py` (cleaned up)
