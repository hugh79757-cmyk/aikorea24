# Phase 27: 인프라 안정화 — 썸네일복구 + 배포 retry + 링크 연결

## Objective
블로그 발행 파이프라인의 3가지 인프라 안정성 문제를 해결한다:
1. **썸네일 미삽입 버그**: 7/21 이후 발행된 블로그에 image: 필드가 frontmatter에 누락됨
2. **deploy.sh retry 로직**: 일시적 네트워크 장애 시 재시도 부재로 배포 실패
3. **링크 연결/일시적 네트워크 장애 대응**: 브리핑 기사 링크 연결 실패 시 fallback/retry

## Context
- `scripts/blog_draft_generator.py`는 save_draft() 시점에 os.path.exists(thumbnail_file)로 image_line을 결정하지만, 이 시점에 썸네일이 아직 생성되지 않음
- 이후 process_thumbnail()으로 썸네일 생성 → _add_image_to_frontmatter()로 frontmatter에 image: 필드 추가 시도
- 그러나 _add_image_to_frontmatter()는 `"draft: false\n---"` 패턴으로 replace 시도하는데, 실제 frontmatter는 `"draft: false\n\n---"` (빈 줄 있음) → 매칭 실패
- deploy.sh는 현재 retry 로직 없이 단일 시도 (set -e 사용)
- 링크 연결 실패 시 fallback/재시도 메커니즘 부재
- ROADMAP.md 차트: Phase 26까지 있음

## Task List
- [ ] Task 1: 썸네일 미삽입 버그 수정 — _add_image_to_frontmatter()의 replace 패턴 수정
  - replace("draft: false\n---") → replace("draft: false\n\n---") 또는 regex 사용
  - 기존 7/21~7/23 발행 글에 image: 필드 일괄 복구 (public/images/에 썸네일 있음)
- [ ] Task 2: deploy.sh retry 로직 추가
  - step 2 (wrangler deploy) 주위에 3회 retry + 지연 시간
  - set -e 유지, if 조건문으로 실패 시 재시도
- [ ] Task 3: 링크 연결 장애 대응
  - deep_dive_url 업데이트 실패 시 retry/fallback
  - 일시적 네트워크 장애 로깅 개선
