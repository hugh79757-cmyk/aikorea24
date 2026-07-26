---
status: complete
completed_at: 2026-07-26T10:22:00+09:00
---

# Phase 29: 블로그 description 백필 — 문장 경계 기준 재자르기

## Summary
기존 826개 블로그 포스트 중 **1개** 파일에서 description 필드에 trailing space가 있어 문장이 제대로 끝나지 않던 것을 수정.

## What Was Done
- Created `scripts/backfill_descriptions.py` using existing `_truncate_at_sentence_boundary()` function
- Fixed trailing space in description: `"...승인받았습니다. "` → `"...승인받았습니다."`

## Verification
- `--dry-run`: 1 file identified for fix
- `--apply`: 1 file modified
- Re-run `--dry-run`: 0 changes (idempotent)

## Files Changed
- `scripts/backfill_descriptions.py` (new)
- `src/content/blog/2026-06-13-002-금융-ai-감시-강화-미국-은행-규제당국-전수조사와.md` (description fixed)