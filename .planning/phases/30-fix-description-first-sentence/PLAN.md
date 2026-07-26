# Phase 30: 블로그 description을 본문 첫 문장으로 변경

## Objective
블로그 발행 시 frontmatter `description` 필드가 본문 내용의 **첫 번째 문장**이 되도록 수정.

## Root Cause
`blog_draft_generator.py`의 `_save_file()`에서 description 추출 시 250자 하드컷 후 한국어 종결어미에서 자르지만:
1. **한국어 종결어미 패턴 불완전** - `합니다`, `있습니다`, `였습니다`, `됩니다` 등 누락
2. **잘못된 자르기 로직** - 250자 윈도우의 **마지막** 종결어미를 찾아서 첫 문장이 아닌 중간 문장에서 잘림

## Solution
1. **Extended Korean ending patterns** - Added 15+ missing verb endings
2. **Created `_extract_first_sentence()`** - New function that:
   - Strips markdown headings, prefixes, markdown syntax
   - Finds FIRST Korean sentence ending
   - Falls back to boundary truncation if needed
   - Max length 300 chars (safety cap)

## Files Changed
- `scripts/blog_draft_generator.py`

## Verification
- All existing tests pass (275/277, 2 pre-existing failures unrelated)
- Manual testing confirms first sentence extraction works correctly