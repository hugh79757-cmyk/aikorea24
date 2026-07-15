---
date: 2026-07-15
type: feat
status: resolved
---

# Pexels 썸네일 blog-draft 통합

## What
`auto_thumbnail.py`의 Pexels 검색 기반 썸네일 생성 기능을 pipeline → `blog_draft_generator.py` 내부로 이전.

## Why
- pipeline 시절: `step_thumbnails`가 pipeline slug로 썸네일 생성
- blog-draft로 블로그 생성 주체가 변경되면서 slug 불일치 발생
- 7/14 triage: slug 불일치로 인해 `--skip-thumbnails`로 비활성화
- **7/15 결정**: Pexels 이미지 품질이 placeholder 대비 월등히 좋으므로, blog-draft 내부에서 직접 Pexels 썸네일을 생성하도록 통합
- slug가 blog-draft 내에서 결정되므로 불일치 문제 원천 해소

## How
- `blog_draft_generator.py`에 `from auto_thumbnail import process_thumbnail` 추가
- `sys.path`에 `scripts/` 디렉토리 추가 (`_script_dir`)
- `_add_image_to_frontmatter()` 함수: 저장된 `.md`의 `draft: false` 뒤에 `image:` 필드 삽입
- 메인 루프: `save_draft()` 직후 `process_thumbnail()` 호출 → 이미지 생성 → frontmatter 주입
- `_save_file()`의 기존 조건부 image 로직(lines 307-308)과 충돌 없음

## Flow
1. 블로그 `.md` 저장 (`save_draft`)
2. `process_thumbnail(link, slug, title, description)` → DeepSeek 키워드 → Pexels 검색 → 다운로드 → 800x800 WebP
3. `public/images/{slug}/thumbnail.webp` 저장
4. `_add_image_to_frontmatter()` → `.md` frontmatter에 `image: /images/{slug}/thumbnail.webp` 추가

## Files changed
- `scripts/blog_draft_generator.py`: import + 썸네일 생성 + frontmatter 주입
- `.planning/triage/20260714--auto-thumbnail-deactivation.md`: 방향 전환 반영

## Backfill
오늘(7/15) 블로그 6개에 Pexels 썸네일 수동 생성 + frontmatter image 필드 추가:
| # | 기사 | 키워드 | 용량 |
|---|------|--------|------|
| 1 | 영국 중앙은행 AI 협력 | robot chess | 42KB |
| 2 | OpenAI 하드웨어 스피커 | ai speaker | 16KB |
| 3 | 애플 iOS 27 시리 AI | apple beta | 19KB |
| 4 | 메타 의료휴직 소송 | justice statue | 39KB |
| 5 | JP모건 AI 일자리 감소 | skyscraper | 72KB |
| 6 | 딥시크 70억 추가자금 | robot toy | 21KB |

## Verification
- ✅ `process_thumbnail()` 정상 작동 (DeepSeek → Pexels → WebP)
- ✅ frontmatter `image:` 필드 정확한 위치에 삽입
- ✅ Astro build 완료
- ✅ Cloudflare Pages 배포 완료
- ✅ `public/images/`는 gitignore 유지 (build 시 wrangler가 업로드)
