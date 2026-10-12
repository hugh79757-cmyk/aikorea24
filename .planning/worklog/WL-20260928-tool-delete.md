# Worklog: WL-20260928-tool-delete

## Operation
Remove 3 unverifiable AI tool entries from `tools` (md + D1) and fix 1 empty url.

## Reason
4 tools had `url: ""` after the 2026-09-28 backfill. Investigation:
- `scrimba-explain` → real product (scrimba.com, 200) → FIX url
- `threadport` → threadport.com is a hat manufacturer (unrelated) → no real product
- `webbrain` → webbrain.com is "TheBrain" mind-map tool (unrelated) → no real product
- `gemini-omni-flash` → no real product found; Google brand-name risk → none

Deleting beats guessing a wrong URL (wrong link is worse than no link).

## Pre-Count
- md files: 4 present (threadport, webbrain, gemini-omni-flash, scrimba-explain)
- D1 tools rows matching: 3 to delete + 1 to fix
- D1 total: 400

## Backup
- `/tmp/tool_delete_backup_20260928_234609/` (all 4 md files)
- Prior git commit `41c526db`

## Execution
1. `git rm` threadport.md, webbrain.md, gemini-omni-flash.md
2. `perl -0pi` scrimba-explain.md `url: ""` → `url: "https://scrimba.com"`
3. D1: `DELETE FROM tools WHERE slug IN (...3); UPDATE tools SET url='https://scrimba.com' WHERE slug='scrimba-explain';` (rows_written 3 + 1)
4. build + deploy → `https://bd4b9056.aikorea24.pages.dev`

## Post-Verification
- D1: deleted_left=0, scrimba_url=https://scrimba.com, total 400→397 ✓
- Live `/tools/{threadport,webbrain,gemini-omni-flash}/` → 404 ✓
- Live `/tools/scrimba-explain/` → `href="https://scrimba.com"` ✓
- Commit `874a2854` ✓

## Commit
- `874a2854` chore(tools): remove 3 unverifiable entries, add scrimba url
