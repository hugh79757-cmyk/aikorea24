---
status: complete
completed_at: 2026-07-26T11:00:00+09:00
---

# Quick Task: fix-blog-prompt-truncation

## Summary
Fixed blog post frontmatter `description` field truncation that was cutting sentences mid-word at exactly 250 characters.

## Root Cause
In `_save_file()` function (line 323), description extraction used hard character limit:
```python
desc_raw = re.sub(r"[#*>\n\s]+", " ", desc_raw)[:250].strip()  # Hard 250-char cut
```

This caused descriptions like:
- "배경에는 디" (mid-word "디지털")
- "자율성과" (mid-word "자율성과")
- "보고서를 인용하" (mid-word "보고서를 인용하고")

## Fix Applied
1. **Added `_truncate_at_sentence_boundary(text, max_len)` helper** (lines 299-340):
   - Searches backward from `max_len` for Korean sentence enders
   - Patterns: `.`, `!`, `?`, `다`, `요`, `함`, `습니다`, `입니다`, `했습니다`, `임`, `음`, `이다`, `한다`, `했다`
   - Falls back to word boundary (space) if no sentence ender found

2. **Modified `_save_file()`** (line 359):
   ```python
   desc_raw = _truncate_at_sentence_boundary(desc_raw, 250)  # Sentence-aware truncation
   ```

## Verification
```python
# Test case - actual blog content
Input: "디지털 시대의 역설... 배경에는 디지털 기술에 대한 피로감이 자리잡고 있습니다. 특히 대기업이 주도하는..."
Max: 250
Output: "디지털 시대의 역설... 깊은 성찰을 요구합니다." (222 chars, ends with "요구합니다.")

# All existing tests pass: 275/277 (2 pre-existing failures)
```

## Files Changed
- `scripts/blog_draft_generator.py` — Added helper + updated `_save_file()`

## Effect
Future blog posts will have complete sentences in frontmatter `description` field.