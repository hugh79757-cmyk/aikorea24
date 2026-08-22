---
date: 2026-08-22
type: fix
status: resolved
---

# TITLE: prefix가 본문에 남는 버그 수정

## What
블로그 포스트에 `TITLE: AI 붐의 총아로...` 라인이 본문에 그대로 노출되는 버그 수정

## Why
`blog_draft_generator.py` `_save_file()`에서 GPT 출력에 `---` 구분자 없을 때 TITLE: 라인 제거 로직 누락

## Files changed
- `scripts/blog_draft_generator.py` (else 분기 추가, line 445-447)

## How
`---` 구분자 파싱 실패 시 `re.sub(r"^TITLE:\s*[^\n]+\n*", "", content)`로 TITLE: 라인 자동 제거

## Verification
기존 005 포스트에서 TITLE: 라인 제거 확인, 커밋 `a3f1f80`
