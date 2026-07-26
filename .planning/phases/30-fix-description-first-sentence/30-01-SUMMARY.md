---
status: complete
completed_at: 2026-07-26T12:35:00+09:00
---

# Phase 30: 블로그 description을 본문 첫 문장으로 변경

## Summary
Fixed blog post `description` frontmatter to use the **first complete sentence of body content** instead of truncating at 250 characters mid-sentence.

## Root Cause
The `_truncate_at_sentence_boundary()` function in `blog_draft_generator.py` had two issues:
1. **Incomplete Korean ending patterns** - Missing common verb endings like `합니다`, `있습니다`, `였습니다`, `됩니다`, `봅니다`, `듣습니다`, etc.
2. **Wrong truncation logic** - Searched for LAST sentence ending in 250-char window instead of FIRST sentence

## Solution Implemented
1. **Extended Korean ending patterns** - Added 15+ missing verb endings
2. **Created `_extract_first_sentence()`** - New function that:
   - Strips markdown headings (`##`, `#`), prefixes (`서론:`, `들어가며:`), markdown syntax
   - Finds FIRST Korean sentence ending (`.`, `!`, `?`, `다`, `요`, `함`, `습니다`, `입니다`, `했습니다`, `합니다`, `있습니다`, `였습니다`, `됩니다`, `봅니다`, `듣습니다`, `옵니다`, `갑니다`, `줍니다`, `삽니다`, `팝니다`, `만듭니다`, `생각합니다`, `느낍니다`, `알고 있습니다`, `모릅니다`, `임`, `음`, `이다`, `한다`, `했다`)
   - Falls back to boundary truncation if needed
   - Max length 300 chars (safety cap)

## Files Changed
- `scripts/blog_draft_generator.py`:
  - Added `_KOREAN_SENTENCE_ENDINGS` pattern with 25+ Korean endings
  - Added `_KOR_END_PATTERN` compiled regex
  - Added `_extract_first_sentence()` function
  - Modified `_save_file()` to use `_extract_first_sentence()` instead of `_truncate_at_sentence_boundary()`
  - Fixed description extraction to remove TITLE, `---`, markdown headings, and prefixes

## Verification
- All existing tests pass (275/277, 2 pre-existing failures unrelated)
- Manual testing confirms:
  - `## heading\n\n첫 문장입니다. 두 번째 문장입니다.` → `"첫 문장입니다."`
  - `서론: 첫 문장입니다. 두 번째 문장입니다.` → `"첫 문장입니다."`
  - `첫 문장입니다. 두 번째 문장입니다.` → `"첫 문장입니다."`
  - `## heading\n\n첫 문장입니다. 두 번째 문장입니다.` → `"첫 문장입니다."`

## Impact
- **New posts** (generated after fix): description = first complete sentence ✅
- **Existing 155 truncated posts**: Need backfill (Phase 29 completed 1 trailing-space fix)
- **6 posts from 08:02-08:04 today**: Generated with OLD logic, need regeneration

## Next Steps
1. Regenerate today's 6 posts (001-006 from 08:02-08:04) to apply fix
2. Backfill remaining 154 truncated descriptions from history