---
date: 2026-07-15
type: fix
status: resolved
---

# Pipeline 3 Bug Recovery + D1 Backfill

## What
파이프라인 3가지 버그 수정 및 D1 deep_dive_url 백필.

## Why

### Bug 1: `blog_url` NameError
`blog_draft_generator.py:save_draft()`에서 `blog_url` 변수 선언 누락 → `NameError` 발생 → `deep_dive_url`이 D1에 저장되지 않음.
- 원인: pipeline → blog-draft 이관 중 변수 누락
- 수정: `blog_url = f"https://aikorea24.kr/blog/{slug}/"` 변수 정의 추가

### Bug 2: Telegram API field name
`run_pipeline_with_notify.py`에서 Telegram API 필드명 `"message"` 사용 → 실제 API 스펙은 `"text"`.
- 증상: HTTP 400 Bad Request, 알림 미발송
- 수정: `"message"` → `"text"`

### Bug 3: deploy.sh wrangler auth
`scripts/deploy.sh`가 `npx wrangler` (로컬 v4.50.0) 사용 → auth profile 미지원 → `CLOUDFLARE_API_TOKEN` 필요.
- 근본 원인: brew wrangler (v4.110.0, auth profiles 지원)와 npx wrangler (v4.50.0, 미지원) 간 버전 차이
- 수정: `env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler` 사용

### D1 Backfill
6개 기사 `deep_dive_url`이 NULL 상태 → `sort_order` 기준 UPDATE 필요.
- 기존 UPDATE 로직이 slug 소문자로 정규화 (`slug.lower()`) — Astro content collection ID lowercase 정규화와 일치

## Files changed
- `scripts/blog_draft_generator.py`: `blog_url` 변수 추가
- `scripts/run_pipeline_with_notify.py`: Telegram `"message"` → `"text"`
- `scripts/deploy.sh`: npx → brew wrangler + env -u CLOUDFLARE_API_TOKEN
- `scripts/run_pipeline.py`: `--skip-deep` BooleanOptionalAction (기존)

## Verification
- ✅ D1: 6/6 `deep_dive_url` 정상 설정
- ✅ blog-draft 실행: 모두 "이미 연결됨" 스킵 정상
- ✅ Telegram: HTTP 400 사라짐, 알림 정상 발송
- ✅ deploy: `wrangler 4.110.0` (Active profile: hugh79757) → 배포 성공
