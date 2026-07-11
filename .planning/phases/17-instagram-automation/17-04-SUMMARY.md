---
phase: 17-instagram-carousel-shorts
plan: 04
subsystem: instagram
tags: [tts, edge-tts, srt, subtitles, korean-audio, ffmpeg]
dependency_graph:
  requires: [17-01]
  provides: [TTSGenerator, batch_generate_tts, generate_tts, generate_srt, generate_reel_audio]
  affects: [pipeline.instagram]
tech_stack:
  added: [edge-tts]
  patterns: [async-gather, concat-demuxer, retry-with-backoff]
key_files:
  created:
    - pipeline/instagram/tts_generator.py
  modified:
    - pipeline/instagram/__init__.py
decisions:
  - "edge-tts save_sync for single TTS, asyncio.gather for batch parallel"
  - "Duplicated _split_korean_caption from content_converter for module independence"
  - "FFmpeg concat demuxer over pipe concat for reliability"
  - "TTSGenerator class wraps module-level functions for OOP interface"
metrics:
  duration: 5min
  completed: 2026-07-11
  tasks: 3
  files: 2
---

# Phase 17 Plan 04: TTS + SRT 자막 생성기 Summary

edge-tts(MS Edge 무료 TTS) 기반 한국어 TTS 음성 생성 + SRT 자막 파일 자동 생성 파이프라인.

## What Was Built

1. **tts_generator.py** (500 LOC) — TTS + SRT 생성 모듈
   - `generate_tts()`: edge-tts로 한국어 MP3 생성 (동기 래퍼, 재시도 1회)
   - `generate_srt()`: 단일 씬 SRT 엔트리 생성 (밀리초 정확도 타임코드)
   - `generate_subtitle_pack()`: 다중 씬 → 단일 SRT 병합 (누적 타임코드)
   - `generate_reel_audio()`: 다중 씬 → 병렬 TTS → 병합 MP3 + SRT
   - `_concatenate_audio()`: FFmpeg concat demuxer로 MP3 병합
   - `_validate_srt_timing()`: SRT ↔ 오디오 타임코드 일관성 검증
   - `adjust_reel_timing()`: 실제 오디오 길이에 맞춘 씬 duration 재분배 (1.5~6.0초 클램프)
   - `_format_srt_timestamp()`: 초 → SRT 타임코드 변환 (00:00:01,500)
   - `_split_korean_caption()`: 한국어 캡션 단어 단위 분할 (18자 제한)
   - `_get_audio_duration()`: ffprobe 오디오 길이 측정
   - `validate_tts()`: TTS 출력 품질 검증 (파일 존재, 길이, 크기)
   - `estimate_duration()`: 한국어 TTS 예상 길이 추정 (4.5 음절/초)
   - `TTSGenerator` 클래스: async generate_tts, generate_tts_with_srt, batch_generate
   - `batch_generate_tts()`: 여러 씬 병렬 TTS 생성

2. **__init__.py** — TTSGenerator, batch_generate_tts export 추가

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _generate_tts_async 타입 수정**
- **Found during:** Task 1 verification
- **Issue:** `_generate_tts_async`에서 `output_path`가 `str`로 전달될 때 `.name` 속성 오류
- **Fix:** 매개변수 타입을 `str | Path`로 확장, 함수 내에서 `Path(output_path)` 변환
- **Files modified:** pipeline/instagram/tts_generator.py
- **Commit:** 8a62315

## Verification Results

- [x] `python3 -m py_compile pipeline/instagram/tts_generator.py` — OK
- [x] `from pipeline.instagram.tts_generator import TTSGenerator` — OK
- [x] `from pipeline.instagram import TTSGenerator, batch_generate_tts` — OK
- [x] `_get_audio_duration()` ffprobe fallback → 0.0 — OK
- [x] `estimate_duration('틱톡이 감원한다던 667명의 정체')` → 2.7s — OK
- [x] `validate_tts()` on real TTS → valid=True, duration=1.9s — OK
- [x] `_format_srt_timestamp(1.5)` → "00:00:01,500" — OK
- [x] `generate_srt()` 타임코드 정확성 — OK
- [x] `generate_subtitle_pack()` 씬 타임코드 누적 — OK
- [x] `adjust_reel_timing()` 총 길이 재분배 + 클램프 — OK
- [x] `_concatenate_audio()` 더미 MP3 병합 — OK

## Known Stubs

None — all functions are fully implemented.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-17-04-01 | tts_generator.py | edge-tts 네트워크 실패 → 재시도 1회 + 명확한 에러 |
| T-17-04-02 | tts_generator.py | SRT 타임코드 검증 → _validate_srt_timing() |
| T-17-04-03 | tts_generator.py | 씬 duration 클램프 → 1.5~6.0초 범위 제한 |

## Self-Check: PASSED
