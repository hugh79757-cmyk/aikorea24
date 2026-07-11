---
phase: 17
plan: 05
subsystem: instagram-publisher
tags: [instagram, graph-api, carousel, reels, publishing, urllib]
requires: [17-02, 17-03, 17-04]
provides: [instagram_publisher, config]
affects: [pipeline/instagram/]
tech-stack:
  added: [urllib.request, json, time]
  patterns: [multipart-upload, exponential-backoff, rate-limiting]
key-files:
  created:
    - pipeline/instagram/instagram_publisher.py
    - pipeline/instagram/config.py
  modified:
    - pipeline/instagram/__init__.py
decisions:
  - "API version v25.0 (user override from plan's v22.0)"
  - "urllib.request only — no requests library per threat model T-17-05-SC"
  - "Multipart upload via raw boundary construction (no toolbelt dependency)"
  - "Rate limit log in instagram_publish_log.json (7-day auto-cleanup)"
  - "TokenManager env-only — no token_info.json per threat model"
metrics:
  duration: "~30min"
  completed: "2026-07-11"
  tasks_completed: 3
  files_created: 2
  files_modified: 1
---

# Phase 17 Plan 05: Instagram Graph API Publisher Summary

Instagram Graph API client for Carousel and Reels auto-publishing — urllib-only multipart upload, rate limiting, exponential backoff, token management.

## What Was Built

### Task 1: config.py + Carousel Publisher

**pipeline/instagram/config.py** — API configuration loaded from env vars:
- `API_VERSION` = "v25.0" (user-verified current stable)
- `GRAPH_API_BASE` = "https://graph.facebook.com"
- `INSTAGRAM_ACCOUNT_ID`, `ACCESS_TOKEN` from env
- `DEFAULT_HASHTAGS` = ["AI뉴스", "인공지능", "AI코리아24", "AI트렌드"]
- `CAROUSEL_CAPTION_TEMPLATE`, `REEL_CAPTION_TEMPLATE`
- `MAX_PUBLISH_PER_HOUR` = 2, `RETRY_DELAYS_SECONDS` = [60, 300, 900]

**pipeline/instagram/instagram_publisher.py** — Core publishing functions:
- `_api_request()` — urllib.request HTTP transport with JSON/multipart support
- `_build_multipart_body()` — raw multipart/form-data construction (stdlib only)
- `create_carousel_item_media()` — upload single PNG → carousel item container
- `create_carousel_container()` — create CAROUSEL parent from child IDs
- `publish_container()` — publish any container by creation_id
- `publish_carousel()` — full pipeline: upload → container → publish

### Task 2: Reels Publisher + Caption + Validation

- `create_reel_container()` — upload MP4 → REELS container
- `publish_reel()` — full pipeline: upload → status poll → publish
- `_generate_caption()` — template-based with `#`-prefixed hashtags
- `_check_publishing_status()` — poll container status (FINISHED/EXPIRED/IN_PROGRESS)
- `_validate_media_file()` — PNG/JPG <10MB, MP4 <250MB, existence check

### Task 3: TokenManager + Rate Limiting + Error Recovery

- `TokenManager` class — env-based token, expiry detection (codes 10/190), 55-day refresh check
- `_check_rate_limit()` — daily log file, 7-day auto-cleanup
- `_retry_with_backoff()` — exponential backoff, retryable (rate_limit/server) vs fatal (190/4xx) distinction
- `verify_publishing()` — GET media metadata after publish

## Deviations from Plan

### Auto-fixed Issues

**1. API version override (Rule 2 — user instruction)**
- **Found during:** Task 1 implementation
- **Issue:** Plan specifies v22.0 but user instructs v25.0 (current as of 2026-07)
- **Fix:** Used `API_VERSION = "v25.0"` in config.py
- **Files modified:** pipeline/instagram/config.py
- **Commit:** pending (orchestrator)

**2. Multipart upload — direct urllib implementation (Rule 3 — blocking issue)**
- **Found during:** Task 1
- **Issue:** Plan describes multipart upload but no multipart library available with urllib-only constraint
- **Fix:** Implemented `_build_multipart_body()` from scratch using boundary construction
- **Files modified:** pipeline/instagram/instagram_publisher.py
- **Commit:** pending (orchestrator)

None — plan executed exactly as written (with v25.0 override).

## Known Stubs

None — all functions are fully implemented with real Graph API logic.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-17-05-01 | instagram_publisher.py | Access token loaded from env only, no file storage |
| T-17-05-02 | instagram_publisher.py | Rate limit enforced via _check_rate_limit() daily log |
| T-17-05-03 | instagram_publisher.py | Token expiry detected by TokenManager.is_token_expired() |
| T-17-05-04 | instagram_publisher.py | Multipart boundary set correctly, _validate_media_file checks types |
| T-17-05-SC | instagram_publisher.py | urllib.request only — no requests library imported |

## Self-Check: PASSED

- [x] `python3 -m py_compile pipeline/instagram/config.py` — PASS
- [x] `python3 -m py_compile pipeline/instagram/instagram_publisher.py` — PASS
- [x] `from pipeline.instagram.instagram_publisher import publish_carousel, publish_reel, TokenManager` — PASS
- [x] `_generate_caption()` produces `#`-prefixed hashtags — PASS
- [x] `_validate_media_file()` checks PNG/MP4 + size limits — PASS
- [x] All 16 publisher functions + 13 config exports import clean — PASS
- [x] No `requests` library imported — PASS (urllib-only confirmed)
- [x] instagram_publisher.py = 665 LOC (min 180) — PASS
