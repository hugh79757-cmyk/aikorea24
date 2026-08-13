---
date: 2026-08-13
type: fix
status: in-progress
---

# Fix Stale --skip-deep Documentation

## Problem
`run_pipeline.py --skip-deep` fails with "unrecognized arguments: --skip-deep" because:
1. Commit 9fa7b05 (2026-08-13) removed `--skip-deep` argument as dead code removal
2. Documentation still references `--skip-deep` in multiple files

## Root Cause
- `scripts/run_pipeline.py`: `--skip-deep` removed (deep articles now via blog_draft_generator.py)
- `docs/TECHNICAL.md`: line 344 references `--skip-deep`
- `docs/SKILLS/01-daily-news-pipeline.md`: lines 95, 107 reference `--skip-deep`
- `docs/SKILLS/04-deep-article-generator.md`: lines 50, 213 reference `--skip-deep`
- `CHANGES.md`: has references to `--skip-deep`

## Solution
Update documentation to remove `--skip-deep` references. Current valid args:
- --skip-news, --skip-briefing, --skip-thumbnails, --skip-email, --skip-deploy
- --date, --dry-run

## Files to Update
1. docs/TECHNICAL.md - remove --skip-deep reference
2. docs/SKILLS/01-daily-news-pipeline.md - remove --skip-deep references
3. docs/SKILLS/04-deep-article-generator.md - remove --skip-deep references
4. CHANGES.md - update references if needed

## Verification
- grep for skip-deep in docs/ should return no results (or only historical context)
- run_pipeline.py --help should show correct args
