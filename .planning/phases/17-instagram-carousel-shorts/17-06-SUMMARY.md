---
phase: 17-instagram-carousel-shorts
plan: 06
subsystem: pipeline
tags: [instagram, pipeline, launchd, scheduling]
requires: [17-01, 17-02, 17-03, 17-04, 17-05]
provides: [StepRunInstagramCarousel, StepRunInstagramReel, instagram-publisher.plist.template]
affects: [pipeline/steps/__init__.py]
tech-stack:
  added: [launchd, string.Template]
  patterns: [PipelineStep protocol, lazy imports, StartCalendarInterval]
key-files:
  created:
    - pipeline/instagram/step_instagram.py
    - scripts/instagram-publisher.plist.template
    - scripts/install_instagram_launchd.sh
  modified:
    - pipeline/steps/__init__.py
decisions:
  - "Two separate launchd agents (carousel 08:00, reel 19:00) instead of single interval"
  - "Lazy imports for all pipeline modules (env var dependency)"
metrics:
  duration: "5m"
  completed: "2026-07-11"
  tasks: "1/1"
  files: "4"
---

# Phase 17 Plan 06: Instagram PipelineStep + Launchd Scheduling Summary

PipelineStep classes for Instagram carousel/reel generation + launchd scheduling for daily automated execution (08:00 KST carousel, 19:00 KST reels).

## What Was Built

### StepRunInstagramCarousel (136 LOC)
- Loads latest Format D cards from D1
- Converts cards to carousel slides via `convert_format_d_to_carousel()`
- Renders slides as PNG via `render_full_carousel()`
- Publishes carousel via `publish_carousel()` (lazy import)
- Supports `dry_run=True` to skip actual publish

### StepRunInstagramReel (136 LOC)
- Loads latest Format D cards from D1
- Converts cards to carousel slides (for PNG rendering) + reel scenes (for TTS/video)
- Renders slides as PNG via `batch_render_carousel()`
- Generates TTS audio via `generate_reel_audio()`
- Renders reel video via `render_reel_video()`
- Publishes reel via `publish_reel()` (lazy import)
- Supports `dry_run=True` to skip TTS + video + publish

### Launchd Scheduling
- `scripts/instagram-publisher.plist.template` with StartCalendarInterval
- `scripts/install_instagram_launchd.sh` generates two plist files:
  - `kr.aikorea24.instagram-carousel.plist` — daily 08:00 KST
  - `kr.aikorea24.instagram-reel.plist` — daily 19:00 KST

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

## Known Stubs

None — all data sources are wired to D1 queries.

## Verification Gates

1. ✅ `python3 -m py_compile pipeline/instagram/step_instagram.py` — passes
2. ✅ `python3 -m py_compile pipeline/steps/__init__.py` — passes
3. ✅ PipelineStep protocol compliance verified
4. ✅ `carousel = StepRunInstagramCarousel(dry_run=True); assert hasattr(carousel, 'name'); assert callable(carousel.run)`
5. ✅ `from pipeline.steps import StepRunInstagramCarousel, StepRunInstagramReel`

## Self-Check

- [x] `pipeline/instagram/step_instagram.py` exists (136 LOC)
- [x] `pipeline/steps/__init__.py` updated with exports
- [x] `scripts/instagram-publisher.plist.template` exists
- [x] `scripts/install_instagram_launchd.sh` exists and executable
- [x] Commit `78ea289` exists
