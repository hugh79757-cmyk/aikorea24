---
date: 2026-08-22
type: feat
status: resolved
---

# 블로그 포스트 첫 문단 뒤 브리핑 페이지 링크 자동 주입

## What
블로그 포스트 발행 시 첫 문단 뒤에 해당 기사의 브리핑 페이지 URL 자동 삽입

## Why
각 글의 출처 링크 부재. 원문 기사 직접 연결보다 aikorea24 브리핑 페이지로 안내해야체류시간 상승

## Files changed
- `scripts/blog_draft_generator.py` (save_draft + _save_file 수정)
- `src/content/blog/2026-08-22-005-...md` (기존 포스트 링크 추가)

## How
1. `save_draft()`에서 DB 조회: `briefing_items` + `briefings` JOIN → `date`, `sort_order`
2. URL 형식: `https://aikorea24.kr/briefing/{date}/#item-{sort_order}`
3. `_save_file()`에서첫 문단 뒤 `[기사원문보기](url)` 삽입

## Verification
005 포스트 브리핑 URL 확인, 배포 완료 (커밋 `5cb0b17`)
