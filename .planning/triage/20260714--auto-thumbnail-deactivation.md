---
date: 2026-07-14
type: config
status: resolved
---

# auto_thumbnail (Pexels) → blog-draft 내부 통합

## What
`scripts/auto_thumbnail.py`의 Pexels 검색 기반 썸네일 생성 기능을 **pipeline → blog-draft로 이동**.

## 배경
- pipeline 시절: `step_thumbnails`가 pipeline slug로 썸네일 생성 → blog-draft로 블로그 생성 주체가 바뀌면서 slug 불일치 발생
- 2026-07-14: slug 불일치로 인해 pipeline의 `step_thumbnails` 호출을 중단 (`--skip-thumbnails`)
- **2026-07-15 결정**: Pexels 이미지 품질이 placeholder 대비 월등히 좋으므로, blog-draft 내부에서 직접 Pexels 썸네일을 생성하도록 통합하기로 결정

## 해결 방안
- `blog_draft_generator.py`가 블로그 `.md` 저장 직후, 같은 slug로 `process_thumbnail()` 호출
- `_save_file()`에 기존에 있던 조건부 image 삽입 로직(`lines 307-308`) 활용
- slug가 blog-draft 내에서 결정되므로 불일치 문제가 원천 해소됨
- Pexels API 키/중복 관리/저작권은 그대로 유지 (`auto_thumbnail.py`의 기존 로직 재사용)

## Files changed
- `scripts/run_pipeline_with_notify.py`: `--skip-thumbnails` 유지 (pipeline에서는 계속 스킵)
- `scripts/blog_draft_generator.py`: `process_thumbnail` import + thumbnail 생성 + frontmatter `image` 필드 주입 추가
- `scripts/auto_thumbnail.py`: 변경 없음 (재사용)

## Verification
blog-draft 실행 시:
1. 블로그 `.md` 저장
2. `public/images/{slug}/thumbnail.webp` 생성 (Pexels)
3. `.md` frontmatter에 `image: /images/{slug}/thumbnail.webp` 자동 추가
4. `SEOHead.astro`가 `image` 필드를 읽어 OG image로 렌더링
