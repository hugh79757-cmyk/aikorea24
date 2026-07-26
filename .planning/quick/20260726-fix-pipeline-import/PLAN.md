# Quick Task: Add Defensive sys.path.insert for pipeline Import

## Description
Add a defensive `sys.path.insert(0, ...)` at the very top of `blog_draft_generator.py` (before any imports) to ensure the `pipeline` module is always importable in launchd environment. This prevents `ModuleNotFoundError: No module named 'pipeline'` when the script runs via launchd.

## Root Cause
The launchd job `kr.aikorea24.blog-draft` runs the script with a minimal environment where PYTHONPATH is not set. The current sys.path.insert happens AFTER the `from pipeline.infra.env_loader import EnvConfig` import, causing import failures in launchd logs.

## Files to Modify
- `scripts/blog_draft_generator.py` - Add sys.path.insert at line 1-2 (before any imports)

## Plan
1. Add `import sys, os` at very top
2. Add `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` before any pipeline imports
3. Keep existing sys.path.insert lines (they can stay as additional safety)

## Acceptance Criteria
- Script runs without ModuleNotFoundError when executed directly: `python3 scripts/blog_draft_generator.py`
- Script runs without ModuleNotFoundError when executed via launchd (simulated)
- Existing imports still work
- Syntax check passes: `python3 -m py_compile scripts/blog_draft_generator.py`