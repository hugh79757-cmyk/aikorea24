---
date: 2026-08-13
type: fix
status: complete
---

# Fix Stale --skip-deep Documentation - Summary

## Problem
`run_pipeline.py --skip-deep` failed with "unrecognized arguments: --skip-deep" because the argument was removed in commit 9fa7b05 (2026-08-13) but documentation still referenced it.

## Root Cause
- Commit 9fa7b05 removed `--skip-deep` as part of dead code removal (auto_deep_article.py deprecated since 2026-07-12)
- Documentation in docs/TECHNICAL.md, docs/SKILLS/*.md still referenced the removed option

## Changes Made
1. **docs/TECHNICAL.md** (line 344): Replaced `--skip-deep` with `--skip-briefing`
2. **docs/SKILLS/01-daily-news-pipeline.md** (lines 95, 107): Removed `--no-skip-deep` and `--skip-deep` references, updated examples
3. **docs/SKILLS/04-deep-article-generator.md** (lines 50, 213): Added note about deep article deprecation, updated command references

## Verification
- ✅ `grep -rn "skip-deep" docs/` returns no results
- ✅ `python3 scripts/run_pipeline.py --help` shows correct options
- ✅ No remaining stale references in documentation

## Note
CHANGES.md historical entries (2026-07-12) retain `--skip-deep` references as they document what was done at that time. These are not errors but historical records.
