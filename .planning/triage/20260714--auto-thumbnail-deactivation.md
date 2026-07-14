---
date: 2026-07-14
type: config
status: resolved
---

# auto_thumbnail (Pexels) 비활성화

## What
`scripts/auto_thumbnail.py`의 Pexels 검색 기반 썸네일 생성 기능을 비활성화.
`run_pipeline.py`의 `step_thumbnails` 호출을 제거 (notify script에 `--skip-thumbnails` 추가).

## Why
blog-draft(`blog_draft_generator.py`)로 블로그 생성 주체가 변경되면서 slug 불일치 발생:
- 심층글(pipeline) 시절: `step_thumbnails`가 심층글과 같은 slug를 사용 → 썸네일 일치
- blog-draft: AI가 생성한 SEO 제목을 slug로 사용 → pipeline이 생성한 썸네일 slug와 불일치
- blog-draft 내에서 Pexels 썸네일을 생성할 수도 있으나, Pexels 의존성(API 키, 중복 관리, 저작권) 대비 효과 미미하여 사용하지 않기로 결정

## Files changed
- `scripts/run_pipeline_with_notify.py`: `--skip-thumbnails` 추가
- `scripts/blog_draft_generator.py`: `_generate_thumbnail` 함수 제거 (비활성화)

## Verification
파이프라인 실행 시 step_thumbnails가 skip되어 로그에 표시됨.
blog-draft 실행 시 썸네일 생성 없이 블로그 글만 생성됨.
