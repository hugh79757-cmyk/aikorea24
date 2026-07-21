---
date: 2026-07-21
type: debug
status: ongoing
---

# Korean blog slug 404 investigation (deep_dive_url encoding)

## What
Senior engineer review of Cloudflare `_redirects` Korean-slug 404 bug. Initial agent hypothesis (`${n.slug}` treated as wildcard) was rejected — `_redirects` has zero `/blog/YYYY-MM-DD-…` rules, and `${n.slug}` lines do not exist.

## Why
- All tested `https://ddbc9e8a.aikorea24.pages.dev/blog/2026-07-18-001-…/` URLs returned HTTP 200, so the report that "all Korean slug posts are 404" was not reproducible.
- Recon narrowed to two hypotheses: (1) trailing-slash mismatch (`run_pipeline.py` emits URLs without trailing slash), or (2) raw UTF-8 href encoding mismatch between generated URL and what Cloudflare Pages serves.

## Files changed
- `public/_redirects` — readonly inspection, no change
- `dist/_redirects` — readonly inspection, no change
- `src/content/blog/2026-07-18-001-…md` — readonly inspection
- `scripts/blog_draft_generator.py` — readonly inspection of `blog_url` construction
- `scripts/run_pipeline.py` — readonly inspection of `blog_url` construction

## How
1. Debug loop under strict instructions (no guesswork, evidence-only).
2. Fetched `/_redirects`, 404-header (`curl -sI`), directory listing.
3. Located `deep_dive_url` sources: `blog_draft_generator.py` line 280 and `run_pipeline.py` line 103.
4. Confirmed href injection path in `dist/_worker.js/pages/briefing/_date_.astro.mjs` — raw DB value passed straight into `href`, no encoding step.
5. Awaited exact 404 URL from 대표님 (Step 27 not yet answered).

## Verification
- [검증됨] `_redirects` advanced-trail hypothesis: `_redirects` has no `/blog/YYYY-MM-DD-*` rule; tested URL returned 200
- [검증불가] Root cause: requires 대표님-provided exact 404 URL + Network tab Request URL (Step 27 output)
- [부분검증] deep_dive_url encoding analysis: code shows raw UTF-8 in DB and unbuffered injection into href; trailing-slash present in `blog_draft_generator.py`, absent in `run_pipeline.py` (limitation: requires live request comparison to confirm)

## Residual risk
대표님의 404 URL이 확보되지 않은 상태 → 정확한 원인 분기 불가. 임의 테스트 금지로 확인 일시 중단.
