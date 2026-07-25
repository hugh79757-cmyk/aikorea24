# Quick Task: Fix Blog Deploy Condition Bug

## Description
`blog_draft_generator.py` 배포 로직(6단계)이 `if generated:` 조건으로만 실행되어, "이미 연결됨"으로 스킵된 기존 생성 글들이 배포되지 않는 버그 수정.

## Root Cause
- 오전 실행: 6개 글 생성 → `deep_dive_url` DB 저장 → `generated` 리스트에 담김 → 배포 실행
- 저녁 재실행: 같은 글들 "이미 연결됨"으로 스킵 → `generated = []` → **배포 안 함**
- 결과: 로컬에 파일은 있으나 라이브에 미배포 상태 (현재 19건 누적)

## Fix Plan
`blog_draft_generator.py` 배포 조건 수정:
- **Before**: `if generated:` (신규 생성만)
- **After**: `if generated or untracked_blog_files:` (신규 + 미커밋 블로그 파일 모두)

## Files to Modify
- `scripts/blog_draft_generator.py` (라인 587 근처)

## Acceptance Criteria
1. 미커밋 블로그 파일(`src/content/blog/2026-07-23-*`, `2026-07-24-*`, `2026-07-25-*`) 감지 시 배포 실행
2. 기존 `generated` 로직 유지 (신규 생성 시 즉시 배포)
3. 중복 배포 방지 (Cloudflare Pages가 동일 빌드 무시)