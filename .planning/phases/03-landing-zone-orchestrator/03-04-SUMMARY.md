# Plan 03-04 Summary: Threads Dual-Scheduling Fix

**Status:** Complete

## Changes
- Removed `--daemon` flag from `scripts/threads/main_v3.py` argparse
- Removed `import schedule` and all `schedule.every()` / `schedule.run_pending()` calls
- Kept `--once` and `--dry-run` as the only run modes
- Simplified `main()` body from 15 lines to 5
- Added doc comment noting the daemon removal (THR-01)

## Verification
- ✅ `grep -- --daemon scripts/threads/main_v3.py` returns only doc comment at line 329
- ✅ `grep "import schedule" scripts/threads/main_v3.py` returns empty
- ✅ `python3 -m py_compile scripts/threads/main_v3.py` passes
- ✅ `python3 scripts/threads/main_v3.py --help` shows only `--dry-run` and `--once`
- ✅ Human verification: approved
