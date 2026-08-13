---
date: 2026-08-13
type: fix
status: in-progress
---

# Decouple Tools Collector from Instagram

## Problem
`tools_collector.py` imports `slugify` from `pipeline.instagram.utils`, which triggers:
- `pipeline.instagram.__init__` → `pipeline.instagram.tts_generator` → `edge_tts` (missing)

Result: `ModuleNotFoundError: No module named 'edge_tts'` → tools_collector fails daily at 06:00.

## Root Cause
- `pipeline/instagram/utils.py` contains `slugify` (simple utility function)
- But importing it triggers Instagram `__init__.py` which imports TTS, video rendering, etc.
- `edge_tts` is a dependency of `tts_generator.py`, not needed by `slugify`

## Solution
1. Create `pipeline/infra/utils.py` — shared utility module
   - Contains `slugify`, `ensure_dir`
   - No Instagram dependencies
   - No optional dependencies (edge_tts, playwright, etc.)
   
2. Update `scripts/tools_collector.py` line 25:
   - `from pipeline.instagram.utils import slugify` → `from pipeline.infra.utils import slugify`
   
3. Leave `pipeline/instagram/utils.py` unchanged (Instagram code still uses it)

## Files Changed
- **New**: `pipeline/infra/utils.py`
- **Modified**: `scripts/tools_collector.py` (line 25)

## Verification
- `python3 scripts/tools_collector.py --help` → should work
- `python3 scripts/tools_collector.py --collect --dry-run` → should collect tools without error
- `grep -n "pipeline.instagram" scripts/tools_collector.py` → should return no results
