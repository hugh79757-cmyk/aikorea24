"""
TTS + SRT 자막 생성기 — edge-tts (MS Edge 무료 TTS)

한국어 뉴스 텍스트를 자연스러운 음성으로 변환하고,
정확한 타임코드가 포함된 SRT 자막 파일을 생성한다.

의존성: edge-tts, ffmpeg/ffprobe (오디오 길이 측정용)
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import edge_tts

from pipeline.instagram.models import InstagramReelScene

log = logging.getLogger(__name__)

DEFAULT_VOICE = "ko-KR-SunHiNeural"
DEFAULT_OUTPUT_DIR = Path("tts")
MAX_RETRY = 1

# 한국어 TTS 파라미터
KOREAN_SYLLABLES_PER_SEC = 4.5
MIN_SCENE_DURATION = 1.5
MAX_SCENE_DURATION = 6.0


# ──────────────────────────────────────────────
# 유틸리티 함수
# ──────────────────────────────────────────────

def estimate_duration(text: str) -> float:
    """한국어 TTS 예상 길이 추정 (초)"""
    if not text:
        return MIN_SCENE_DURATION

    english_words = len(re.findall(r'[a-zA-Z]+', text))
    korean_syllables = sum(
        1 for c in text if '\uac00' <= c <= '\ud7a3'
    )
    total_syllables = korean_syllables + english_words * 3
    duration = total_syllables / KOREAN_SYLLABLES_PER_SEC
    return round(max(MIN_SCENE_DURATION, min(MAX_SCENE_DURATION, duration)), 1)


def _get_audio_duration(audio_path: str | Path) -> float:
    """ffprobe로 오디오 실제 길이 측정 (초). 실패 시 0.0 반환."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0


def validate_tts(audio_path: str | Path, expected_text_len: int = 0) -> dict[str, Any]:
    """TTS 출력 품질 검증"""
    path = Path(audio_path)
    if not path.exists():
        return {"valid": False, "duration": 0.0, "size_kb": 0.0, "error": "파일 없음"}

    size_kb = path.stat().st_size / 1024
    if size_kb > 5120:
        return {"valid": False, "duration": 0.0, "size_kb": size_kb, "error": "파일 크기 초과 (5MB)"}

    duration = _get_audio_duration(path)
    if duration <= 0.0:
        return {"valid": False, "duration": duration, "size_kb": size_kb, "error": "duration 0"}

    return {"valid": True, "duration": duration, "size_kb": size_kb, "error": None}


# ──────────────────────────────────────────────
# SRT 자막 생성
# ──────────────────────────────────────────────

def _format_srt_timestamp(seconds: float) -> str:
    """초 → SRT 타임코드 형식 (00:00:01,500)"""
    seconds = max(0.0, min(seconds, 359999.999))
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_korean_caption(text: str, max_width: int = 18) -> list[str]:
    """한국어 캡션을 단어 단위로 분할 (한 줄 최대 max_width 문자)"""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word)
        added = current_len + word_len + (1 if current_len > 0 else 0)
        if added > max_width:
            if current:
                lines.append(' '.join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len = added

    if current:
        lines.append(' '.join(current))

    return lines if lines else [text]


def generate_srt(
    text: str,
    scene_duration: float,
    start_time: float = 0.0,
    caption_lines: list[str] | None = None,
    index: int = 1,
) -> str:
    """단일 씬의 SRT 엔트리 생성"""
    if not caption_lines:
        caption_lines = _split_korean_caption(text, 18)

    start_ts = _format_srt_timestamp(start_time)
    end_ts = _format_srt_timestamp(start_time + scene_duration)
    body = '\n'.join(caption_lines)

    return f"{index}\n{start_ts} --> {end_ts}\n{body}\n"


def generate_subtitle_pack(
    scenes: list[dict[str, Any]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """
    여러 씬의 자막을 단일 SRT 파일로 병합

    Args:
        scenes: [{"text": str, "estimated_duration": float, "caption_lines": list[str]}, ...]
        output_dir: SRT 파일 저장 디렉토리

    Returns:
        {"srt_path": str, "total_duration": float, "scene_timings": list[dict]}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / "reel_subtitles.srt"

    entries: list[str] = []
    scene_timings: list[dict[str, float]] = []
    current_time = 0.0

    for i, scene in enumerate(scenes):
        duration = scene.get("estimated_duration", 3.0)
        text = scene.get("text", "")
        caption_lines = scene.get("caption_lines")

        entry = generate_srt(
            text=text,
            scene_duration=duration,
            start_time=current_time,
            caption_lines=caption_lines,
            index=i + 1,
        )
        entries.append(entry)

        scene_timings.append({
            "start": round(current_time, 3),
            "end": round(current_time + duration, 3),
        })
        current_time += duration

    srt_content = '\n'.join(entries) + '\n'
    srt_path.write_text(srt_content, encoding="utf-8")

    return {
        "srt_path": str(srt_path),
        "total_duration": round(current_time, 3),
        "scene_timings": scene_timings,
    }


def generate_subtitle_filter_srt(srt_path: str, style: str = "bounce") -> str:
    """SRT 파일을 FFmpeg subtitles 필터 문자열로 변환"""
    return (
        f"subtitles={srt_path}:force_style='"
        f"FontName=AppleSDGothicNeo,FontSize=28,Alignment=2'"
    )


# ──────────────────────────────────────────────
# TTS 생성 (단일)
# ──────────────────────────────────────────────

async def _generate_tts_async(
    text: str,
    voice: str,
    output_path: str | Path,
) -> dict[str, Any]:
    """edge-tts로 단일 텍스트 → MP3 생성 (async)"""
    output_path = Path(output_path)
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))

    duration = _get_audio_duration(output_path)
    log.info("TTS 생성 완료: %s (%.1fs)", output_path.name, duration)
    return {
        "audio_path": str(output_path),
        "duration": duration,
        "text": text,
    }


def generate_tts(
    text: str,
    voice: str = DEFAULT_VOICE,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    텍스트를 MP3 음성으로 변환 (동기 래퍼)

    Args:
        text: TTS할 한국어 텍스트
        voice: edge-tts 음성 (기본: ko-KR-SunHiNeural)
        output_path: 출력 MP3 경로. None이면 임시 파일 생성

    Returns:
        {"audio_path": str, "duration": float, "text": str}
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".mp3"))
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1 + MAX_RETRY):
        try:
            return asyncio.run(
                _generate_tts_async(text, voice, output_path)
            )
        except Exception as exc:
            if attempt < MAX_RETRY:
                log.warning("TTS 재시도 (%d/%d): %s", attempt + 1, MAX_RETRY, exc)
                continue
            log.error("TTS 실패: %s", exc)
            raise RuntimeError(f"TTS 생성 실패: {exc}") from exc

    # unreachable but satisfies type checker
    raise RuntimeError("TTS 생성 실패")  # pragma: no cover


# ──────────────────────────────────────────────
# SRT 타임코드 검증
# ──────────────────────────────────────────────

def _validate_srt_timing(
    srt_path: str | Path,
    audio_path: str | Path,
    tolerance: float = 0.5,
) -> dict[str, Any]:
    """
    SRT ↔ 오디오 타임코드 일관성 검증

    Returns:
        {"valid": bool, "srt_end": float, "audio_duration": float, "diff": float}
    """
    audio_duration = _get_audio_duration(audio_path)
    content = Path(srt_path).read_text(encoding="utf-8")

    # 마지막 타임코드의 end 추출
    time_pattern = r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
    matches = re.findall(time_pattern, content)

    if not matches:
        return {
            "valid": False,
            "srt_end": 0.0,
            "audio_duration": audio_duration,
            "diff": audio_duration,
        }

    last_end_str = matches[-1][1]
    h, m, rest = last_end_str.split(':')
    s, ms = rest.split(',')
    srt_end = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    diff = abs(srt_end - audio_duration)
    valid = diff <= tolerance

    return {
        "valid": valid,
        "srt_end": round(srt_end, 3),
        "audio_duration": round(audio_duration, 3),
        "diff": round(diff, 3),
    }


# ──────────────────────────────────────────────
# 씬 duration 재조정
# ──────────────────────────────────────────────

def adjust_reel_timing(
    scenes: list[InstagramReelScene],
    audio_duration: float,
) -> list[InstagramReelScene]:
    """실제 오디오 길이에 맞춰 씬별 duration 재분배"""
    if not scenes:
        return scenes

    total_original = sum(s.duration_seconds for s in scenes)
    if total_original <= 0:
        return scenes

    adjusted: list[InstagramReelScene] = []
    remaining = audio_duration

    for i, scene in enumerate(scenes):
        ratio = scene.duration_seconds / total_original
        new_dur = audio_duration * ratio

        if i == len(scenes) - 1:
            new_dur = max(MIN_SCENE_DURATION, remaining)
        else:
            new_dur = max(MIN_SCENE_DURATION, min(MAX_SCENE_DURATION, new_dur))
            remaining -= new_dur

        new_scene = InstagramReelScene(
            scene_index=scene.scene_index,
            text=scene.text,
            slide_ref=scene.slide_ref,
            duration_seconds=round(new_dur, 3),
            transition_type=scene.transition_type,
            animation_style=scene.animation_style,
            caption_lines=list(scene.caption_lines) if scene.caption_lines else [],
        )
        adjusted.append(new_scene)

    return adjusted


# ──────────────────────────────────────────────
# 오디오 병합
# ──────────────────────────────────────────────

def _concatenate_audio(
    audio_paths: list[str | Path],
    output_path: str | Path,
) -> str:
    """
    여러 MP3 파일을 하나로 병합 (FFmpeg concat demuxer)

    Returns:
        출력 파일 경로
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False
    ) as concat_file:
        for ap in audio_paths:
            concat_file.write(f"file '{Path(ap).resolve()}'\n")
        concat_path = concat_file.name

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_path,
                "-c", "copy",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # fallback: pipe concat
            pipe_input = "|".join(str(Path(p).resolve()) for p in audio_paths)
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", f"concat:{pipe_input}",
                    "-acodec", "copy",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
    finally:
        Path(concat_path).unlink(missing_ok=True)

    return str(output_path)


# ──────────────────────────────────────────────
# 멀티 씬 TTS 생성
# ──────────────────────────────────────────────

async def _generate_scene_tts(
    scene: dict[str, Any],
    tts_dir: Path,
    voice: str,
) -> dict[str, Any]:
    """단일 씬의 TTS 생성"""
    idx = scene.get("scene_index", 0)
    text = scene.get("text", "")

    mp3_path = tts_dir / f"scene_{idx}.mp3"

    for attempt in range(1 + MAX_RETRY):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(mp3_path))
            duration = _get_audio_duration(mp3_path)
            log.info("씬 %d TTS 완료: %.1fs", idx, duration)
            return {
                "index": idx,
                "path": str(mp3_path),
                "duration": duration,
                "text": text,
            }
        except Exception as exc:
            if attempt < MAX_RETRY:
                log.warning("씬 %d TTS 재시도: %s", idx, exc)
                continue
            raise RuntimeError(f"씬 {idx} TTS 실패: {exc}") from exc

    raise RuntimeError("TTS 생성 실패")  # pragma: no cover


async def _batch_generate_tts(
    scenes: list[dict[str, Any]],
    tts_dir: Path,
    voice: str,
) -> list[dict[str, Any]]:
    """병렬 TTS 생성 (asyncio.gather)"""
    tasks = [
        _generate_scene_tts(scene, tts_dir, voice)
        for scene in scenes
    ]
    return await asyncio.gather(*tasks)


def batch_generate_tts(
    scenes: list[InstagramReelScene],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    voice: str = DEFAULT_VOICE,
) -> list[dict[str, Any]]:
    """
    여러 씬의 TTS를 병렬로 생성

    Args:
        scenes: InstagramReelScene 리스트
        output_dir: 출력 디렉토리
        voice: edge-tts 음성

    Returns:
        씬별 TTS 결과 리스트 [{"index": int, "path": str, "duration": float}]
    """
    tts_dir = Path(output_dir)
    tts_dir.mkdir(parents=True, exist_ok=True)

    scene_dicts = [
        {
            "scene_index": s.scene_index,
            "text": s.text,
        }
        for s in scenes
    ]

    return asyncio.run(
        _batch_generate_tts(scene_dicts, tts_dir, voice)
    )


def generate_reel_audio(
    scenes: list[dict[str, Any]],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    voice: str = DEFAULT_VOICE,
) -> dict[str, Any]:
    """
    다중 씬 → 단일 MP3 + SRT 병합

    Args:
        scenes: [{"text": str, "scene_index": int}, ...]
        output_dir: 출력 디렉토리
        voice: edge-tts 음성

    Returns:
        {
            "audio_path": str,
            "srt_path": str,
            "total_duration": float,
            "scene_audios": list[dict],
        }
    """
    out_dir = Path(output_dir)
    tts_dir = out_dir / "scenes"
    tts_dir.mkdir(parents=True, exist_ok=True)

    # 각 씬별 TTS 생성
    scene_results = asyncio.run(
        _batch_generate_tts(scenes, tts_dir, voice)
    )

    # 오디오 병합
    audio_paths = [s["path"] for s in scene_results]
    merged_path = out_dir / "reel_audio.mp3"
    if len(audio_paths) == 1:
        import shutil
        shutil.copy2(audio_paths[0], merged_path)
    elif len(audio_paths) > 1:
        _concatenate_audio(audio_paths, merged_path)

    # SRT 생성
    srt_scenes = [
        {
            "text": s["text"],
            "estimated_duration": s["duration"],
        }
        for s in scene_results
    ]
    srt_result = generate_subtitle_pack(srt_scenes, out_dir)

    total_duration = _get_audio_duration(merged_path)

    return {
        "audio_path": str(merged_path),
        "srt_path": srt_result["srt_path"],
        "total_duration": total_duration,
        "scene_audios": scene_results,
    }


__all__ = [
    "TTSGenerator",
    "batch_generate_tts",
    "generate_tts",
    "generate_srt",
    "generate_reel_audio",
    "generate_subtitle_pack",
    "validate_tts",
    "estimate_duration",
    "adjust_reel_timing",
    "_format_srt_timestamp",
    "_split_korean_caption",
    "_get_audio_duration",
    "_concatenate_audio",
    "_validate_srt_timing",
    "generate_subtitle_filter_srt",
]


# ──────────────────────────────────────────────
# TTSGenerator 클래스 (_plan.md 인터페이스)
# ──────────────────────────────────────────────

class TTSGenerator:
    """TTS + SRT 생성을 관리하는 클래스"""

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.voice = voice
        self.output_dir = Path(output_dir)

    async def generate_tts(
        self,
        text: str,
        output_mp3_path: str | Path,
        voice: str | None = None,
    ) -> dict[str, Any]:
        """단일 텍스트 → MP3"""
        return await _generate_tts_async(
            text, voice or self.voice, Path(output_mp3_path)
        )

    async def generate_tts_with_srt(
        self,
        text: str,
        output_mp3_path: str | Path,
        output_srt_path: str | Path,
        voice: str | None = None,
    ) -> dict[str, Any]:
        """단일 텍스트 → MP3 + SRT (edge-tts 네이티브 SRT 지원)"""
        v = voice or self.voice
        communicate = edge_tts.Communicate(text, v)
        await communicate.save(str(output_mp3_path), str(output_srt_path))

        duration = _get_audio_duration(output_mp3_path)
        log.info("TTS+SRT 생성: %s (%.1fs)", output_mp3_path, duration)
        return {
            "audio_path": str(output_mp3_path),
            "srt_path": str(output_srt_path),
            "duration": duration,
            "text": text,
        }

    async def batch_generate(
        self,
        scenes: list[InstagramReelScene],
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """여러 씬 병렬 TTS + 단일 병합 MP3 + SRT"""
        out = Path(output_dir) if output_dir else self.output_dir
        return generate_reel_audio(
            [
                {"text": s.text, "scene_index": s.scene_index}
                for s in scenes
            ],
            output_dir=out,
            voice=self.voice,
        )

    def estimate_duration(self, text: str) -> float:
        """한국어 TTS 예상 길이 추정 (초)"""
        return estimate_duration(text)

    def validate(self, audio_path: str | Path) -> dict[str, Any]:
        """TTS 출력 검증"""
        return validate_tts(audio_path)
