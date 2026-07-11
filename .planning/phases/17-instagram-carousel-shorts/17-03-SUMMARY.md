---
phase: 17-instagram-carousel-shorts
plan: 03
subsystem: instagram-pipeline
tags: [video-renderer, ffmpeg, ken-burns, xfade, drawtext, subprocess]
dependency_graph:
  requires: [17-01, 17-02, 17-04]
  provides: [video_renderer]
  affects: [pipeline.instagram]
tech_stack:
  added: [ffmpeg, subprocess]
  patterns: [filter_complex_script, zoompan, xfade, drawtext]
key_files:
  created: [pipeline/instagram/video_renderer.py]
  modified: [pipeline/instagram/__init__.py]
decisions:
  - "filter_complex_script for long filter graphs (shell escaping prevention)"
  - "Pretendard font priority with Apple SD Gothic Neo fallback"
  - "CRF 20 + libx264 medium preset for quality/size balance"
  - "HW acceleration via videotoolbox on macOS"
metrics:
  duration: "2026-07-11T14:00:00Z"
  completed: "2026-07-11T14:20:00Z"
  tasks_completed: 3
  files_created: 1
  files_modified: 1
---

# Phase 17 Plan 03: FFmpeg Video Renderer Summary

FFmpeg-based video renderer with Ken Burns zoompan, xfade transitions, and drawtext subtitle animation for Instagram Carousel (1080x1350) and Reels (1080x1920).

## Tasks Completed

| Task | Name | Status | Key Functions |
|------|------|--------|---------------|
| 1 | Ken Burns + xfade transition filter logic | Done | `build_ken_burns_filter`, `build_xfade_filter`, `select_random_transitions`, `is_supported_xfade`, `build_scene_filter_chain` |
| 2 | drawtext subtitle animation (bounce + timing) | Done | `build_drawtext_filter`, `build_subtitle_filter_from_srt`, `_parse_srt`, `_find_korean_font` |
| 3 | Full FFmpeg command + render pipeline | Done | `build_render_command`, `render_carousel_video`, `render_reel_video`, `validate_rendered_video`, `_write_filter_file` |

## Verification Results

| Check | Result |
|-------|--------|
| `python3 -m py_compile video_renderer.py` | PASS |
| Task 1: Ken Burns zoompan filter | PASS (zoompan, 0.0015, 1080x1920) |
| Task 1: xfade transition filter | PASS (xfade, wipeleft) |
| Task 1: is_supported_xfade | PASS (wipeleft=True, glitch=False) |
| Task 1: select_random_transitions | PASS (5 transitions, all valid) |
| Task 2: drawtext filter | PASS (drawtext, Hello World, enable) |
| Task 2: SRT parsing | PASS (2 entries, timing ±0.01s) |
| Task 3: build_render_command | PASS (33 tokens, -hwaccel present) |
| Task 3: _write_filter_file | PASS (temp file created) |
| Task 3: validate_rendered_video signature | PASS |
| Import: `from pipeline.instagram.video_renderer import ...` | PASS |

## Key Design Decisions

1. **filter_complex_script**: Long filter graphs (>2000 chars) written to temp files to avoid shell escaping issues
2. **Font fallback chain**: Pretendard-Bold.otf → Pretendard-*.otf → AppleSDGothicNeo.ttc
3. **Ken Burns zoom speed**: 0.0015/frame (1.0x → 1.12x in ~75 frames / 2.5s) — prevents sub-pixel jitter
4. **xfade fallback**: Unsupported transitions (e.g., "glitch") gracefully fall back to "dissolve"
5. **HW acceleration**: macOS videotoolbox via `-hwaccel videotoolbox` flag
6. **Timeout**: 120s for carousel, 240s for reel (longer due to audio)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-17-03-01 | video_renderer.py | FFmpeg subprocess timeout=120s to prevent DoS |
| T-17-03-02 | video_renderer.py | Filter graph >2000 chars → _write_filter_file |
| T-17-03-03 | video_renderer.py | stderr logged, no log scrubbing needed (local only) |

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `pipeline/instagram/video_renderer.py` | 759 | FFmpeg command builder + render pipeline |
| `pipeline/instagram/__init__.py` | 53 | Updated exports with video_renderer functions |

## Self-Check: PASSED

- video_renderer.py: FOUND (759 pure LOC, >200 min)
- __init__.py: FOUND
- SUMMARY.md: FOUND
- All 15 exports importable: PASS
