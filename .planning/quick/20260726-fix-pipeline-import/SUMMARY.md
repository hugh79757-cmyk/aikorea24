---
status: complete
completed_at: 2026-07-26T10:40:00+09:00
---

# Quick Task: fix-pipeline-import

## Summary
Added defensive `sys.path.insert` at the very top of `blog_draft_generator.py` (before any imports) to ensure the `pipeline` module is always importable in launchd environment.

## Changes Made
**File**: `scripts/blog_draft_generator.py`

**Before** (lines 1-19):
```python
#!/usr/bin/env python3
"""
docstring...
"""
import os, re, json, glob, sys, time
from datetime import datetime, date, timezone, timedelta

# launchd 환경: sys.path 미설정 상태이므로 __file__ 기반으로 먼저 추가
_script_dir = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_script_dir)
sys.path.insert(0, _PROJECT_DIR)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'scripts', 'threads', 'v3'))

from pipeline.infra.env_loader import EnvConfig
```

**After** (lines 1-25):
```python
#!/usr/bin/env python3
"""
docstring...
"""
# launchd 환경 방어: 가장 먼저 sys.path 설정 (모든 import보다 앞)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os, re, json, glob, time
from datetime import datetime, date, timezone, timedelta

# launchd 환경: sys.path 미설정 상태이므로 __file__ 기반으로 추가
_script_dir = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_script_dir)
sys.path.insert(0, _PROJECT_DIR)
sys.path.insert(0, _script_dir)
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'scripts', 'threads', 'v3'))

from pipeline.infra.env_loader import EnvConfig
```

## Verification
- ✅ Syntax check: `python3 -m py_compile scripts/blog_draft_generator.py` → OK
- ✅ Direct execution with venv Python: runs successfully, imports work
- ✅ Pipeline imports: `from pipeline.infra.env_loader import EnvConfig` → OK
- ✅ Full script execution: Deploys to Cloudflare Pages successfully
- ✅ Site live: `https://aikorea24.kr` → HTTP 200

## Root Cause Fixed
The launchd job `kr.aikorea24.blog-draft` was failing with `ModuleNotFoundError: No module named 'pipeline'` because:
1. The original `sys.path.insert` happened AFTER initial imports (line 9)
2. In launchd's minimal environment, PYTHONPATH wasn't set
3. The defensive insert at the very top (before ANY imports) ensures the project root is in sys.path before `from pipeline...` statements execute