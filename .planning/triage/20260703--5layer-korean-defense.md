---
date: 2026-07-03
type: fix
status: resolved
---

# 5-Layer Korean Language Defense Framework

## What
Systematic 5-layer prevention framework enforcing Korean language output in `pipeline/threads/pitch.py`. LLM was outputting English despite "반드시 한국어로" prompt; JSON mode (`response_format`) actually worsened English bias on DeepSeek V4 Flash.

## Why
- Single "반드시 한국어로" prompt insufficient — LLM switches language when JSON mode, format requirements, or English proper nouns mix in
- No output validation existed before saving/publishing
- JSON fallback path and text path had inconsistent sanitization
- Production bug: English hooks were being published without detection

## Files changed
- `pipeline/threads/pitch.py`

## How
| Layer | Component | Change |
|-------|-----------|--------|
| 1. Prompt Shield | SYSTEM_PROMPT + `_regenerate_pitch_from_crawl` | Added `[언어 규칙 - 최우선]` section with Good/Bad examples. "반드시 한국어로 작성", emphasis markers reserved for language rules only |
| 2. Output Guard | `validate_korean_output()` new | Korean char ratio check (threshold 15%), Latin sentence pattern detection, first-char Korean check |
| 3. Sanitizer | `normalize_output()` new | Common pipeline for JSON + fallback paths → `clean_leaked_prompt()` → `[:100]/[:200]` truncation → `_lang_valid` metadata |
| 4. Publish Gate | `get_pitches()` + `save_pitch_to_history()` | `_lang_valid` + `_lang_reason` meta fields logged on publish. `normalize_output` gates all saves |
| 5. JSON Mode Hybrid | `response_format` removed | Text-first → JSON fallback. Avoids DeepSeek V4 Flash English bias from `response_format='json_object'` |

Also added `detect_prompt_leak()` to Layer 2 as secondary defense — catches prompt leakage even when JSON mode is stripped.

## Verification
- `py_compile` ✅
- `pytest` 17/17 ✅
- Manual Korean validation edge cases: "AI 기반 B2B SaaS 스타트업 XYZ가 Series A 투자 유치" → 37.9% Korean ✅; "OpenAI의 ChatGPT가 GPT-5 출시와 함께 Enterprise 시장 공략" → 31.4% ✅
- 15% threshold confirmed safe — only pure English sentences (0% Korean) trigger rejection
