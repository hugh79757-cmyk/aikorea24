---
date: 2026-08-13
type: fix
status: complete
---

# Decouple Tools Collector from Instagram - Summary

## Problem
`tools_collector.py` was importing `slugify` from `pipeline.instagram.utils`, which triggered a chain of imports:
- `pipeline.instagram.__init__` → `pipeline.instagram.tts_generator` → `edge_tts` (missing)

This caused `tools_collector.py` to fail with `ModuleNotFoundError: No module named 'edge_tts'`.

## Root Cause
`pipeline/instagram/utils.py` contains `slugify` (a simple utility), but importing it triggers the full Instagram `__init__.py` which imports TTS, video rendering, and other Instagram-specific modules including `edge_tts`.

## Solution
1. Created `pipeline/infra/utils.py` — shared utility module with `slugify` and `ensure_dir`
   - No Instagram dependencies
   - No optional dependencies (edge_tts, playwright, etc.)
   
2. Updated `scripts/tools_collector.py` line 25:
   - Before: `from pipeline.instagram.utils import slugify`
   - After: `from pipeline.infra.utils import slugify`

3. `pipeline/instagram/utils.py` left unchanged — Instagram code still uses its own utils (no issues for Instagram itself)

## Verification
- ✅ `python3 scripts/tools_collector.py --help` → works
- ✅ `python3 scripts/tools_collector.py --collect --dry-run` → works, collects 8 tools
- ✅ No `pipeline.instagram` imports remain in `tools_collector.py`
- ✅ `pipeline.infra.utils.slugify` works correctly: `slugify('테스트 도구-Ai')` → `'테스트-도구-Ai'`

## Impact
- **tools_collector.py**: Can now run without edge_tts installed
- **Instagram pipeline**: Unaffected (still uses its own utils)
- **Tools page updates**: Can resume via launchd daily at 06:00

## Note
In스타그램 파이프라인은 별도 활성화 작업이 필요하며, 현재는 비활성화 상태 유지.
