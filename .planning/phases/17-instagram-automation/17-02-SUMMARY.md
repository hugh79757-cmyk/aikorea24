---
phase: 17-instagram-carousel-shorts
plan: 02
subsystem: instagram
tags: [html-renderer, playwright, png-generation, carousel, reels]
dependency_graph:
  requires: [17-01]
  provides: [html_renderer, utils, carousel_slide.html, reel_cover.html]
  affects: [pipeline.instagram]
tech_stack:
  added: [playwright-cli, string-template]
  patterns: [subprocess-capture, template-substitution]
key_files:
  created:
    - pipeline/instagram/html_renderer.py
    - pipeline/instagram/utils.py
    - pipeline/instagram/templates/carousel_slide.html
    - pipeline/instagram/templates/reel_cover.html
  modified:
    - pipeline/instagram/__init__.py
decisions:
  - "string.Template over Jinja2 for stdlib-only convention"
  - "Playwright CLI subprocess over Python API for simplicity"
  - "Sequential batch rendering to preserve slide order"
metrics:
  duration: 8min
  completed: 2026-07-11
  tasks: 3
  files: 5
---

# Phase 17 Plan 02: HTML → PNG Image Generator Summary

HTML 템플릿 기반 Instagram Carousel(1080×1350) + Reels(1080×1920) PNG 생성 파이프라인. string.Template으로 슬라이드 데이터를 HTML에 주입하고 Playwright CLI로 캡처.

## What Was Built

1. **carousel_slide.html** — Carousel 슬라이드 템플릿 (1080×1350, 4:5)
   - 다크 테마 (#0D1117), Pretendard 폰트 CDN
   - CSS 변수 기반 그라데이션 배경 (slide type별)
   - $emoji_prefix, $highlight_number, $title, $body, $bg_class, $subtitle 치환

2. **reel_cover.html** — Reels 커버 템플릿 (1080×1920, 9:16)
   - 동일 디자인 시스템, 세로형 레이아웃
   - 하단 브랜딩 바 (AI코리아24 · AI 뉴스)

3. **html_renderer.py** — 렌더링 + 캡처 오케스트레이션
   - `render_carousel_slides()`: 슬라이드 리스트 → PNG 경로 리스트
   - `render_reel_cover()`: 단일 슬라이드 → Reels 커버 PNG
   - `render_reel_thumbnail()`: 첫 슬라이드 기반 썸네일
   - `batch_render_carousel()`: 순차 렌더링 + 진행률 로그 + 부분 실패 허용
   - `render_carousel_cover()`: 커버 이미지 생성
   - `render_full_carousel()`: 단일 호출로 전체 캐러셀 생성 (커버 + N개 슬라이드)
   - `capture_html_to_png()`: Playwright CLI 캡처 (30s 타임아웃, 1회 재시도)

4. **utils.py** — 공유 유틸리티
   - `ensure_dir()`, `slugify()`, `timestamp_kst()`, `date_str_kst()`
   - `get_playwright_path()`, `create_run_directory()`, `cleanup_old_html()`
   - `ensure_output_dir()` — carousel/reel별 출력 디렉토리

5. **__init__.py** — 새 public API export 추가 (16개 심볼)

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- [x] `python3 -m py_compile pipeline/instagram/html_renderer.py` — OK
- [x] `python3 -m py_compile pipeline/instagram/utils.py` — OK
- [x] `python3 -m py_compile pipeline/instagram/__init__.py` — OK
- [x] `from pipeline.instagram import render_carousel_slides, ...` — all 16 exports OK
- [x] string.Template substitution on both HTML templates — OK
- [x] Function signatures match plan specification

## Known Stubs

None — all functions are fully implemented.

## Threat Flags

None — local file system operations only, no network endpoints.

## Self-Check: PASSED
