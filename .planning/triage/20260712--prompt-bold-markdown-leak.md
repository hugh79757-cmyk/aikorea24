---
date: 2026-07-12
type: fix
status: resolved
---

# 프롬프트 내 ** 볼드 마크다운 누출 수정

## What
Threads 발행글 첫 문장에 `** **`(볼드 마크다운) 기호가 노출됨. `볼드 금지` 규칙이 system prompt에 명시되어 있음에도 출력에 볼드가 따라 나옴.

## Why
원인: `style_examples.md` 4개 예시 첫 문장에 `**내용**` 볼드 마크다운이 포함되어 있었음. LLM이 "볼드 금지" 규칙보다 few-shot 예시를 우선시하여 출력에도 `**`를 생성.

## Files changed
- `scripts/threads/v3/style_examples.md` — 4개 예시 첫 문장 `** **` 제거
- `pipeline/threads/writer.py:119` — system prompt 지시문 `**첫 줄 = ...**` → `첫 줄 = ...`
- `pipeline/threads/writer.py:658,661-664` — user prompt 예시 `**"..."**` → `"..."` 4개
- `pipeline/threads/writer.py:385` — `_cleanup_source_attribution()`에 `re.sub(r'\*\*', '')` 방어적 제거 추가

## How
1. style_examples.md 4개 first sentence에서 볼드 마크다운 제거
2. system prompt stanza1 가이드에서 `**` 제거 (지시문 강조 용도였던 `**`가 출력 예시로 오인됨)
3. user prompt 변환 예시 3개에서 `**` 제거
4. `_cleanup_source_attribution()`에 `**` 방어적 제거 추가 (LLM이 남겨도 최종 제거)

## Verification
- `python3 -m py_compile pipeline/threads/writer.py` ✅
- `python3 -m py_compile scripts/threads/v3/writer_v3.py` ✅
- 40/41 writer 테스트 통과 (1 pre-existing 실패 — humanize 제거로 인한 test fixture 불일치)
