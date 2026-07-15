---
date: 2026-07-15
type: config
status: resolved
---

# Blog Schedule 15분 지연

## What
블로그 발행 스케줄을 브리핑 발행 후 15분으로 지연 적용.

## Why
- 브리핑 발행 후 딥링크(블로그 URL) 연결까지 시간 확보 필요
- 기존: 브리핑 07:00 → 블로그 07:00 (동시 실행)
- 변경: 브리핑 06:00 → 블로그 06:15 (15분 지연)

## Files changed
- `kr.aikorea24.blog-draft.plist` — 07:00 → 06:15/20:15
- `scripts/blog-draft.plist.template` — 템플릿 신규 생성
- `CHANGES.md`, `.continue-here.md`, `.planning/STATE.md`, `.planning/triage/INDEX.md`

## How
1. LaunchAgents 파일 수정 (UTC 기준)
2. Launchd unload/load 재로드
3. 템플릿 파일로 백업

## Verification
- `launchctl list | grep blog` 확인
- 파일 기록 확인
- 4개 커밋 완료