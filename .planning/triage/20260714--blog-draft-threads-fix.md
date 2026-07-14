---
date: 2026-07-14
type: fix
status: resolved
---

# blog-draft pipeline + thread-topic-finder 복구

## What
브리핑→블로그 연결(`deep_dive_url`) 및 쓰레드 발행 중단 문제 해결.

## Why
**blog-draft (3가지 문제)**:
1. `ModuleNotFoundError: No module named 'pipeline'` — launchd 환경 sys.path 미설정
2. D1 API token 만료로 뉴스 조회 실패 (`CLOUDFLARE_API_TOKEN`)
3. 키워드 매칭 방식이라 브리핑 기사 6개 중 1개만 연결됨

**thread-topic-finder (2가지 문제)**:
1. plist 경로가 `scripts/thread_topic_finder.py`로 되어 있으나 파일이 `scripts/thread_topics/`로 이동됨
2. 동일한 D1 API token 만료 문제

**slug 케이스 문제**:
- Astro가 content collection ID를 lowercase로 정규화하지만, `deep_dive_url`은 대소문자 유지하여 404

## Files changed
- `scripts/blog_draft_generator.py` — sys.path 추가, get_today_articles() → get_briefing_articles()로 변경, wrangler CLI 전환, slug lowercase, 종료 시 validate_blog_posts 호출
- `scripts/thread_topics/thread_topic_finder.py` — sys.path 추가, wrangler CLI 전환
- `scripts/run_pipeline.py` — `--skip-deep` default=True (심층글 불필요)
- `scripts/run_pipeline_with_notify.py` — `--skip-deep`, `--skip-thumbnails` 명시
- `scripts/validate_blog_posts.py` — 중복 ID 검사 추가
- `~/Library/LaunchAgents/kr.aikorea24.blog-draft.plist` — `source` 제거, 07:00 실행, Cloudflare env var 제거
- `~/Library/LaunchAgents/kr.aikorea24.thread-topic-finder.plist` — 경로 수정, `source` 제거, Cloudflare env var 제거
- `docs/TECH.md` — 파이프라인 흐름도 업데이트

## How
1. blog-draft: 브리핑 기사 직접 조회 → 6개 전부 블로그 생성 + deep_dive_url 연결
2. wrangler CLI로 D1 쿼리 전환 (OAuth profile hugh79757 사용)
3. slug lowercase 처리 (Astro 정규화와 일치)
4. plist에서 `source .env.common` 제거 (bash 문법 오류) → Python 내 load_env()로 대체

## Verification
- blog-draft 실행: 10개 블로그 생성 + deep_dive_url 6개 연결 ✅
- deep-dive 링크: `aikorea24.kr/blog/...` 200 OK ✅
- thread-topic-finder 실행: 5개 글감 생성 ✅
- threads-publisher: 12:15 정상 발행 완료 ✅
