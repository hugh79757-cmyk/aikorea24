"""
FFmpeg 기반 비디오 렌더러 — Ken Burns(zoompan) + xfade 전환 + drawtext 자막 애니메이션

정적 PNG 슬라이드를 시네마틱 비디오(Reels/Shorts)로 변환.
Carousel용 MP4(1080x1350, 4:5)와 Reels용 MP4(1080x1920, 9:16) 모두 지원.

의존성: ffmpeg/ffprobe (로컬 설치)
"""

from __future__ import annotations

import glob
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from pipeline.instagram.models import InstagramReelScene

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────

FFMPEG_PATH = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

SUPPORTED_TRANSITIONS = ["wipeleft", "circlecrop", "dissolve", "smoothleft"]
DEFAULT_TRANSITION = "dissolve"

# Ken Burns 파라미터
DEFAULT_ZOOM_SPEED = 0.0015
DEFAULT_MAX_ZOOM = 1.12
DEFAULT_FRAMES = 75  # 2.5초 @ 30fps

# 전환 기본값
DEFAULT_TRANSITION_DURATION = 0.5
DEFAULT_SLIDE_DURATION = 2.5

# 인코딩 기본값
DEFAULT_CRF = 20
DEFAULT_FPS = 30
DEFAULT_VIDEO_BITRATE = "libx264"
DEFAULT_AUDIO_BITRATE = "128k"
DEFAULT_PIX_FMT = "yuv420p"

# 자막 스타일
DEFAULT_FONT_SIZE = 56
SUBTITLE_MARGIN_BOTTOM = 120

# 필터 복잡도 임계값 (필터 그래프가 너무 길면 파일로 저장)
FILTER_SCRIPT_THRESHOLD = 2000

# FFmpeg 실행 타임아웃 (초)
FFMPEG_TIMEOUT = 120


# ──────────────────────────────────────────────
# Task 1: Ken Burns + xfade 필터 로직
# ──────────────────────────────────────────────

def build_ken_burns_filter(
    image_path: str,
    duration_frames: int = DEFAULT_FRAMES,
    output_size: str = "1080x1920",
    fps: int = DEFAULT_FPS,
    pan_direction: str = "center",
) -> str:
    """
    Ken Burns (zoompan) 필터 문자열 생성

    Args:
        image_path: 입력 이미지 경로
        duration_frames: 재생할 프레임 수 (75 = 2.5초 @ 30fps)
        output_size: 출력 해상도 (가로x세로)
        fps: 초당 프레임 수
        pan_direction: 팬 방향 ("center", "left", "right", "up", "down")

    Returns:
        FFmpeg zoompan 필터 문자열
    """
    zoom_expr = f"min(zoom+{DEFAULT_ZOOM_SPEED},{DEFAULT_MAX_ZOOM})"

    # 팬 방향에 따른 x/y 오프셋
    pan_offsets = {
        "center": ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        "left": ("iw/2-(iw/zoom/2)-50", "ih/2-(ih/zoom/2)"),
        "right": ("iw/2-(iw/zoom/2)+50", "ih/2-(ih/zoom/2)"),
        "up": ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)-50"),
        "down": ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)+50"),
    }
    x_expr, y_expr = pan_offsets.get(pan_direction, pan_offsets["center"])

    return (
        f"zoompan=z='{zoom_expr}'"
        f":x='{x_expr}'"
        f":y='{y_expr}'"
        f":d={duration_frames}"
        f":s={output_size}"
        f":fps={fps}"
    )


def is_supported_xfade(transition: str) -> bool:
    """xfade 전환 타입 지원 여부 확인"""
    return transition in SUPPORTED_TRANSITIONS


def build_xfade_filter(
    transition: str,
    duration: float = DEFAULT_TRANSITION_DURATION,
    offset: float = 2.0,
) -> str:
    """
    xfade 전환 필터 문자열 생성

    Args:
        transition: 전환 타입 (wipeleft, circlecrop, dissolve, smoothleft)
        duration: 전환 지속 시간 (초)
        offset: 전환 시작 시점 (초)

    Returns:
        FFmpeg xfade 필터 문자열
    """
    if not is_supported_xfade(transition):
        log.warning(
            "지원하지 않는 전환 '%s' → '%s'로 대체", transition, DEFAULT_TRANSITION
        )
        transition = DEFAULT_TRANSITION

    return f"xfade=transition={transition}:duration={duration}:offset={offset}"


def select_random_transitions(count: int) -> list[Optional[str]]:
    """
    랜덤 전환 타입 선택

    Args:
        count: 선택할 전환 수

    Returns:
        전환 타입 리스트 (첫 번째는 None — 첫 씬에는 전환 없음)
    """
    if count <= 0:
        return []

    transitions: list[Optional[str]] = [None]
    for _ in range(count - 1):
        transitions.append(random.choice(SUPPORTED_TRANSITIONS))
    return transitions


def build_scene_filter_chain(
    scenes: list[dict[str, Any]],
    output_size: str = "1080x1920",
    fps: int = DEFAULT_FPS,
) -> str:
    """
    여러 이미지/씬을 FFmpeg filter_complex 문자열로 변환

    Args:
        scenes: [{"image": str, "duration": float, "transition": str|None, "pan_direction": str}, ...]
        output_size: 출력 해상도
        fps: 초당 프레임 수

    Returns:
        완전한 filter_complex 문자열
    """
    if not scenes:
        return ""

    filter_parts: list[str] = []
    n = len(scenes)

    # 1단계: 각 이미지에 Ken Burns 적용
    for i, scene in enumerate(scenes):
        duration = scene.get("duration", DEFAULT_SLIDE_DURATION)
        pan_dir = scene.get("pan_direction", "center")
        duration_frames = int(duration * fps)

        kb = build_ken_burns_filter(
            scene["image"], duration_frames, output_size, fps, pan_dir
        )
        filter_parts.append(f"[{i}:v]scale={output_size}:force_original_aspect_ratio=increase,crop={output_size},{kb}[v{i}]")

    # 2단계: xfade 체인
    if n == 1:
        # 단일 씬: 전환 없이 바로 출력
        filter_parts.append(f"[v0]null[vout]")
    else:
        last_label = "v0"
        cumulative_offset = scenes[0].get("duration", DEFAULT_SLIDE_DURATION)

        for i in range(1, n):
            transition = scenes[i].get("transition")
            trans_duration = DEFAULT_TRANSITION_DURATION

            if transition is None:
                # 첫 씬 → 두 번째 씬: 전환 적용
                transition = random.choice(SUPPORTED_TRANSITIONS)

            xfade = build_xfade_filter(transition, trans_duration, cumulative_offset)
            out_label = f"v{i}out" if i < n - 1 else "vout"
            filter_parts.append(
                f"[{last_label}][v{i}]xfade=transition={transition}:duration={trans_duration}:offset={cumulative_offset:.3f}[{out_label}]"
            )
            last_label = out_label
            cumulative_offset += scenes[i].get("duration", DEFAULT_SLIDE_DURATION) - trans_duration

    return ";\n".join(filter_parts)


# ──────────────────────────────────────────────
# Task 2: drawtext 자막 애니메이션
# ──────────────────────────────────────────────

def _find_korean_font() -> Optional[str]:
    """
    한국어 폰트 탐색 (Pretendard 우선, Apple SD Gothic Neo 폴백)

    Returns:
        폰트 파일 경로. 없으면 None.
    """
    # Pretendard 탐색
    pretendard_patterns = [
        os.path.expanduser("~/Library/Fonts/Pretendard-Bold.otf"),
        os.path.expanduser("~/Library/Fonts/Pretendard-Medium.otf"),
        os.path.expanduser("~/Library/Fonts/Pretendard-Regular.otf"),
        os.path.expanduser("~/Library/Fonts/Pretendard-SemiBold.otf"),
    ]
    for pattern in pretendard_patterns:
        if os.path.isfile(pattern):
            return pattern

    # Pretendard glob 탐색
    pretendard_glob = glob.glob(os.path.expanduser("~/Library/Fonts/Pretendard-*.otf"))
    if pretendard_glob:
        return pretendard_glob[0]

    # macOS 기본 한국어 폰트
    apple_gothic = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    if os.path.isfile(apple_gothic):
        return apple_gothic

    return None


def build_drawtext_filter(
    text: str,
    fontfile: Optional[str],
    start_time: float,
    duration: float,
    style: str = "bounce",
    video_width: int = 1080,
    video_height: int = 1920,
    font_size: int = DEFAULT_FONT_SIZE,
) -> str:
    """
    단일 drawtext 필터 문자열 생성

    Args:
        text: 표시할 텍스트
        fontfile: 폰트 파일 경로 (None이면 기본 폰트 사용)
        start_time: 시작 시간 (초)
        duration: 표시 지속 시간 (초)
        style: 애니메이션 스타일 ("bounce", "fade", "slide-up")
        video_width: 비디오 가로 크기
        video_height: 비디오 세로 크기
        font_size: 기본 폰트 크기

    Returns:
        FFmpeg drawtext 필터 문자열
    """
    end_time = start_time + duration

    # 텍스트 이스케이프 (FFmpeg drawtext 특수문자 처리)
    escaped_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")

    # 공통 속성
    parts = ["drawtext"]
    parts.append(f"text='{escaped_text}'")
    parts.append("fontcolor=white")
    parts.append(f"borderw=3")
    parts.append("bordercolor=black@0.8")
    parts.append(f"x=(w-text_w)/2")

    # 폰트
    if fontfile:
        parts.append(f"fontfile='{fontfile}'")

    # 스타일별 애니메이션
    if style == "bounce":
        # 바운스: fontsize가 sin 주기로 변동 (0.5초 주기)
        parts.append(
            f"fontsize='{font_size}*(0.7+0.3*sin(2*PI*(t-{start_time})/0.5))'"
        )
        parts.append(f"y=h-text_h-{SUBTITLE_MARGIN_BOTTOM}")
    elif style == "fade":
        # 페이드 인/아웃
        parts.append(f"fontsize={font_size}")
        fade_in_end = start_time + 0.2
        fade_out_start = end_time - 0.2
        parts.append(
            f"alpha='if(between(t,{start_time},{fade_in_end}),(t-{start_time})/0.2,"
            f"if(between(t,{fade_out_start},{end_time}),({end_time}-t)/0.2,1))'"
        )
        parts.append(f"y=h-text_h-{SUBTITLE_MARGIN_BOTTOM}")
    elif style == "slide-up":
        # 슬라이드업: 위에서 아래로
        parts.append(f"fontsize={font_size}")
        parts.append(
            f"y='h-text_h-{SUBTITLE_MARGIN_BOTTOM}-50*(1-min(1,(t-{start_time})/0.3))'"
        )
    else:
        # 기본: 고정 크기
        parts.append(f"fontsize={font_size}")
        parts.append(f"y=h-text_h-{SUBTITLE_MARGIN_BOTTOM}")

    # 시간 제한
    parts.append(f"enable='between(t,{start_time:.3f},{end_time:.3f})'")

    return ":".join(parts)


def _parse_srt(srt_path: str) -> list[dict[str, Any]]:
    """
    SRT 파일 파싱

    Args:
        srt_path: SRT 파일 경로

    Returns:
        [{"index": int, "start": float, "end": float, "text": str}, ...]
    """
    content = Path(srt_path).read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = []

    # SRT 엔트리 블록 분리 (빈 줄 기준)
    blocks = re.split(r"\n\s*\n", content.strip())

    time_pattern = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # 타임코드 줄 찾기
        time_match = None
        time_line_idx = -1
        for idx, line in enumerate(lines):
            time_match = time_pattern.search(line)
            if time_match:
                time_line_idx = idx
                break

        if not time_match or time_line_idx < 0:
            continue

        # 인덱스 (타임코드 줄 이전)
        try:
            index = int(lines[time_line_idx - 1]) if time_line_idx > 0 else len(entries) + 1
        except (ValueError, IndexError):
            index = len(entries) + 1

        # 타임코드 파싱
        g = time_match.groups()
        start = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
        end = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000

        # 텍스트 (타임코드 줄 이후)
        text_lines = lines[time_line_idx + 1 :]
        text = " ".join(line.strip() for line in text_lines if line.strip())

        if text:
            entries.append({
                "index": index,
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            })

    return entries


def build_subtitle_filter_from_srt(
    srt_path: str,
    fontfile: Optional[str] = None,
    video_height: int = 1920,
    bounce: bool = True,
) -> str:
    """
    SRT 파일을 파싱하여 drawtext 필터 체인 생성

    Args:
        srt_path: SRT 파일 경로
        fontfile: 폰트 파일 경로 (None이면 자동 탐색)
        video_height: 비디오 세로 크기
        bounce: 바운스 애니메이션 사용 여부

    Returns:
        세미콜론으로 구분된 drawtext 필터 체인
    """
    if fontfile is None:
        fontfile = _find_korean_font()

    entries = _parse_srt(srt_path)
    if not entries:
        return ""

    style = "bounce" if bounce else "fade"
    filters: list[str] = []

    for entry in entries:
        duration = entry["end"] - entry["start"]
        if duration <= 0:
            continue

        dt = build_drawtext_filter(
            text=entry["text"],
            fontfile=fontfile,
            start_time=entry["start"],
            duration=duration,
            style=style,
            video_height=video_height,
        )
        filters.append(dt)

    return ";".join(filters)


# ──────────────────────────────────────────────
# Task 3: FFmpeg 명령 빌더 + 렌더 파이프라인
# ──────────────────────────────────────────────

def _write_filter_file(filter_str: str) -> str:
    """
    필터 그래프를 임시 파일에 저장 (filter_complex_script용)

    Args:
        filter_str: FFmpeg filter_complex 문자열

    Returns:
        임시 파일 경로
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="fffilter_"
    )
    tmp.write(filter_str)
    tmp.close()
    return tmp.name


def get_video_duration(video_path: str) -> float:
    """
    ffprobe로 비디오 길이 측정 (초)

    Args:
        video_path: 비디오 파일 경로

    Returns:
        초 단위 길이. 실패 시 0.0.
    """
    try:
        result = subprocess.run(
            [
                FFPROBE_PATH, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0


def get_audio_duration(audio_path: str) -> float:
    """
    ffprobe로 오디오 길이 측정 (초)

    Args:
        audio_path: 오디오 파일 경로

    Returns:
        초 단위 길이. 실패 시 0.0.
    """
    return get_video_duration(audio_path)


def validate_rendered_video(
    video_path: str,
    expected_width: int,
    expected_height: int,
    max_duration: float = 35.0,
) -> dict[str, Any]:
    """
    렌더링된 비디오 검증 (해상도, 길이, 코덱)

    Args:
        video_path: 비디오 파일 경로
        expected_width: 예상 가로 크기
        expected_height: 예상 세로 크기
        max_duration: 최대 허용 길이 (초)

    Returns:
        {"valid": bool, "codec": str, "resolution": str, "duration": float, "size_mb": float}
    """
    path = Path(video_path)
    if not path.exists():
        return {
            "valid": False,
            "codec": "",
            "resolution": "",
            "duration": 0.0,
            "size_mb": 0.0,
            "error": "파일 없음",
        }

    size_mb = path.stat().st_size / (1024 * 1024)

    # ffprobe로 상세 정보 가져오기
    try:
        result = subprocess.run(
            [
                FFPROBE_PATH, "-v", "error",
                "-show_entries", "stream=width,height,codec_name",
                "-show_entries", "format=duration",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {
                "valid": False,
                "codec": "",
                "resolution": "",
                "duration": 0.0,
                "size_mb": size_mb,
                "error": f"ffprobe 실패: {result.stderr[:200]}",
            }

        import json
        info = json.loads(result.stdout)

        # 비디오 스트림 정보
        codec = ""
        width = 0
        height = 0
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                codec = stream.get("codec_name", "")
                width = stream.get("width", 0)
                height = stream.get("height", 0)
                break

        duration = float(info.get("format", {}).get("duration", 0))

        resolution = f"{width}x{height}"
        valid = (
            width == expected_width
            and height == expected_height
            and duration > 0
            and duration <= max_duration
            and codec in ("h264", "hevc")
        )

        return {
            "valid": valid,
            "codec": codec,
            "resolution": resolution,
            "duration": round(duration, 3),
            "size_mb": round(size_mb, 2),
            "error": None if valid else f"검증 실패: {resolution} (예상 {expected_width}x{expected_height}), {duration:.1f}s",
        }

    except (json.JSONDecodeError, ValueError, subprocess.TimeoutExpired):
        return {
            "valid": False,
            "codec": "",
            "resolution": "",
            "duration": 0.0,
            "size_mb": size_mb,
            "error": "ffprobe 출력 파싱 실패",
        }


def build_render_command(
    images: list[str],
    audio: Optional[str],
    subtitles_srt: Optional[str],
    output_path: str,
    output_size: str = "1080x1920",
    fps: int = DEFAULT_FPS,
    slide_duration: float = DEFAULT_SLIDE_DURATION,
    transition_duration: float = DEFAULT_TRANSITION_DURATION,
    hwaccel: bool = True,
) -> list[str]:
    """
    전체 FFmpeg 명령어 리스트 생성 (subprocess.run용)

    Args:
        images: 입력 이미지 경로 리스트
        audio: 오디오 파일 경로 (선택)
        subtitles_srt: SRT 자막 파일 경로 (선택)
        output_path: 출력 MP4 경로
        output_size: 출력 해상도 (가로x세로)
        fps: 초당 프레임 수
        slide_duration: 슬라이드 표시 시간 (초)
        transition_duration: 전환 지속 시간 (초)
        hwaccel: 하드웨어 가속 사용 여부

    Returns:
        FFmpeg 명령어 리스트
    """
    n = len(images)
    if n == 0:
        raise ValueError("이미지가 없습니다")

    cmd: list[str] = [FFMPEG_PATH, "-y"]

    # HW 가속
    if hwaccel:
        cmd.extend(["-hwaccel", "videotoolbox"])

    # 이미지 입력 (-loop 1 -t {duration} -i {image})
    for img in images:
        cmd.extend(["-loop", "1", "-t", str(slide_duration), "-i", str(img)])

    # 오디오 입력
    has_audio = audio is not None and Path(audio).exists()
    if has_audio:
        cmd.extend(["-i", str(audio)])

    # filter_complex 생성
    transitions = select_random_transitions(n)

    filter_parts: list[str] = []
    output_w, output_h = output_size.split("x")

    # 각 이미지에 Ken Burns 적용
    duration_frames = int(slide_duration * fps)
    for i in range(n):
        pan_dir = random.choice(["center", "left", "right", "up", "down"])
        kb = build_ken_burns_filter(
            images[i], duration_frames, output_size, fps, pan_dir
        )
        filter_parts.append(
            f"[{i}:v]scale={output_size}:force_original_aspect_ratio=increase,"
            f"crop={output_size},{kb}[v{i}]"
        )

    # xfade 체인
    if n == 1:
        filter_parts.append("[v0]null[vout]")
    else:
        last_label = "v0"
        cumulative_offset = slide_duration

        for i in range(1, n):
            trans = transitions[i] if transitions[i] else random.choice(SUPPORTED_TRANSITIONS)
            if not is_supported_xfade(trans):
                trans = DEFAULT_TRANSITION

            out_label = f"v{i}out" if i < n - 1 else "vout"
            filter_parts.append(
                f"[{last_label}][v{i}]xfade=transition={trans}"
                f":duration={transition_duration}:offset={cumulative_offset:.3f}"
                f"[{out_label}]"
            )
            last_label = out_label
            cumulative_offset += slide_duration - transition_duration

    # 자막 오버레이
    video_label = "vout"
    if subtitles_srt and Path(subtitles_srt).exists():
        fontfile = _find_korean_font()
        subtitle_filters = build_subtitle_filter_from_srt(
            subtitles_srt, fontfile, int(output_h)
        )
        if subtitle_filters:
            sub_label = "vsub"
            filter_parts.append(
                f"[{video_label}]{subtitle_filters}[{sub_label}]"
            )
            video_label = sub_label

    # 필터 그래프 합치기
    filter_complex = ";\n".join(filter_parts)

    # 필터 그래프가 너무 길면 파일로 저장
    if len(filter_complex) > FILTER_SCRIPT_THRESHOLD:
        filter_path = _write_filter_file(filter_complex)
        cmd.extend(["-filter_complex_script", filter_path])
    else:
        cmd.extend(["-filter_complex", filter_complex])

    # 출력 매핑
    cmd.extend(["-map", f"[{video_label}]"])
    if has_audio:
        cmd.extend(["-map", f"{n}:a"])

    # 인코딩 설정
    cmd.extend(["-c:v", "libx264", "-preset", "medium", f"-crf", str(DEFAULT_CRF)])
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", DEFAULT_AUDIO_BITRATE])

    cmd.extend(["-pix_fmt", DEFAULT_PIX_FMT, "-r", str(fps)])

    # 총 길이 제한 (오디오 없을 때만)
    if not has_audio:
        total_duration = slide_duration * n - transition_duration * (n - 1)
        cmd.extend(["-t", f"{total_duration:.3f}"])

    cmd.append(str(output_path))

    return cmd


def render_carousel_video(
    slides: list[Path],
    output_dir: str | Path,
    scenes: list[InstagramReelScene] | None = None,
) -> Path:
    """
    Carousel(1080x1350) 비디오 생성

    Args:
        slides: PNG 경로 리스트 (17-02 출력)
        output_dir: 출력 디렉토리
        scenes: 씬별 타이밍/전환 정보 (선택)

    Returns:
        출력 MP4 경로
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Carousel: 4:5 비율 (1080x1350)
    output_size = "1080x1350"
    output_filename = f"carousel_{Path(slides[0]).stem if slides else 'output'}.mp4"
    output_path = output_dir / output_filename

    # 씬별 타이밍 설정
    slide_durations: list[float] = []
    transitions_list: list[Optional[str]] = []

    if scenes:
        for scene in scenes:
            slide_durations.append(scene.duration_seconds)
            transitions_list.append(scene.transition_type)
    else:
        slide_durations = [DEFAULT_SLIDE_DURATION] * len(slides)
        transitions_list = select_random_transitions(len(slides))

    # FFmpeg 필터그래프 구성
    filter_parts: list[str] = []
    n = len(slides)

    for i in range(n):
        duration = slide_durations[i] if i < len(slide_durations) else DEFAULT_SLIDE_DURATION
        duration_frames = int(duration * DEFAULT_FPS)
        pan_dir = random.choice(["center", "left", "right", "up", "down"])

        kb = build_ken_burns_filter(
            str(slides[i]), duration_frames, output_size, DEFAULT_FPS, pan_dir
        )
        filter_parts.append(
            f"[{i}:v]scale={output_size}:force_original_aspect_ratio=increase,"
            f"crop={output_size},{kb}[v{i}]"
        )

    # xfade 체인
    if n == 1:
        filter_parts.append("[v0]null[vout]")
    else:
        last_label = "v0"
        cumulative_offset = slide_durations[0] if slide_durations else DEFAULT_SLIDE_DURATION

        for i in range(1, n):
            trans = transitions_list[i] if i < len(transitions_list) and transitions_list[i] else random.choice(SUPPORTED_TRANSITIONS)
            if not is_supported_xfade(trans):
                trans = DEFAULT_TRANSITION

            trans_dur = DEFAULT_TRANSITION_DURATION
            out_label = f"v{i}out" if i < n - 1 else "vout"
            filter_parts.append(
                f"[{last_label}][v{i}]xfade=transition={trans}"
                f":duration={trans_dur}:offset={cumulative_offset:.3f}"
                f"[{out_label}]"
            )
            last_label = out_label
            dur = slide_durations[i] if i < len(slide_durations) else DEFAULT_SLIDE_DURATION
            cumulative_offset += dur - trans_dur

    filter_complex = ";\n".join(filter_parts)

    # 필터 그래프 저장
    use_script = len(filter_complex) > FILTER_SCRIPT_THRESHOLD
    if use_script:
        filter_path = _write_filter_file(filter_complex)
    else:
        filter_path = None

    # FFmpeg 명령어 구성
    cmd: list[str] = [FFMPEG_PATH, "-y", "-hwaccel", "videotoolbox"]

    for slide in slides:
        cmd.extend(["-loop", "1", "-t", str(DEFAULT_SLIDE_DURATION), "-i", str(slide)])

    if use_script:
        cmd.extend(["-filter_complex_script", filter_path])
    else:
        cmd.extend(["-filter_complex", filter_complex])

    cmd.extend(["-map", "[vout]"])
    cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", str(DEFAULT_CRF)])
    cmd.extend(["-pix_fmt", DEFAULT_PIX_FMT, "-r", str(DEFAULT_FPS)])

    total_dur = sum(slide_durations) - DEFAULT_TRANSITION_DURATION * (n - 1)
    cmd.extend(["-t", f"{total_dur:.3f}"])
    cmd.append(str(output_path))

    # 실행
    log.info("Carousel 렌더링 시작: %s", output_path.name)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT
        )
        if result.returncode != 0:
            log.error("Carousel 렌더링 실패: %s", result.stderr[:500])
            raise RuntimeError(f"FFmpeg 실패: {result.stderr[:300]}")
    finally:
        if filter_path and os.path.exists(filter_path):
            os.unlink(filter_path)

    log.info("Carousel 렌더링 완료: %s", output_path)
    return output_path


def render_reel_video(
    slides: list[Path],
    audio: str,
    subtitles_srt: str,
    output_dir: str | Path,
    scenes: list[InstagramReelScene],
) -> Path:
    """
    Reels(1080x1920) 비디오 생성

    Args:
        slides: PNG 경로 리스트
        audio: TTS MP3 경로 (17-04 출력)
        subtitles_srt: SRT 경로 (17-04 출력)
        output_dir: 출력 디렉토리
        scenes: 씬별 타이밍/전환 정보

    Returns:
        출력 MP4 경로
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Reels: 9:16 비율 (1080x1920)
    output_size = "1080x1920"
    output_filename = f"reel_{Path(slides[0]).stem if slides else 'output'}.mp4"
    output_path = output_dir / output_filename

    # 오디오 길이 기반 타이밍
    audio_dur = get_audio_duration(audio)
    if audio_dur <= 0:
        audio_dur = sum(s.duration_seconds for s in scenes) or 15.0

    n = len(slides)

    # FFmpeg 필터그래프 구성
    filter_parts: list[str] = []

    # 씬별 duration 오디오에 맞게 재분배
    total_scene_dur = sum(s.duration_seconds for s in scenes) if scenes else audio_dur
    scale_factor = audio_dur / total_scene_dur if total_scene_dur > 0 else 1.0

    for i in range(n):
        scene = scenes[i] if i < len(scenes) else None
        duration = (scene.duration_seconds * scale_factor) if scene else audio_dur / n
        duration_frames = int(duration * DEFAULT_FPS)
        pan_dir = random.choice(["center", "left", "right", "up", "down"])

        kb = build_ken_burns_filter(
            str(slides[i]), duration_frames, output_size, DEFAULT_FPS, pan_dir
        )
        filter_parts.append(
            f"[{i}:v]scale={output_size}:force_original_aspect_ratio=increase,"
            f"crop={output_size},{kb}[v{i}]"
        )

    # xfade 체인
    if n == 1:
        filter_parts.append("[v0]null[vout]")
    else:
        last_label = "v0"
        cumulative_offset = (scenes[0].duration_seconds * scale_factor) if scenes else audio_dur / n

        for i in range(1, n):
            scene = scenes[i] if i < len(scenes) else None
            trans = scene.transition_type if scene and scene.transition_type else random.choice(SUPPORTED_TRANSITIONS)
            if not is_supported_xfade(trans):
                trans = DEFAULT_TRANSITION

            trans_dur = DEFAULT_TRANSITION_DURATION
            out_label = f"v{i}out" if i < n - 1 else "vout"
            filter_parts.append(
                f"[{last_label}][v{i}]xfade=transition={trans}"
                f":duration={trans_dur}:offset={cumulative_offset:.3f}"
                f"[{out_label}]"
            )
            last_label = out_label
            dur = (scene.duration_seconds * scale_factor) if scene else audio_dur / n
            cumulative_offset += dur - trans_dur

    video_label = "vout"

    # 자막 오버레이
    if subtitles_srt and Path(subtitles_srt).exists():
        fontfile = _find_korean_font()
        subtitle_filters = build_subtitle_filter_from_srt(
            subtitles_srt, fontfile, 1920
        )
        if subtitle_filters:
            sub_label = "vsub"
            filter_parts.append(f"[{video_label}]{subtitle_filters}[{sub_label}]")
            video_label = sub_label

    filter_complex = ";\n".join(filter_parts)

    # 필터 그래프 저장
    use_script = len(filter_complex) > FILTER_SCRIPT_THRESHOLD
    if use_script:
        filter_path = _write_filter_file(filter_complex)
    else:
        filter_path = None

    # FFmpeg 명령어 구성
    cmd: list[str] = [FFMPEG_PATH, "-y", "-hwaccel", "videotoolbox"]

    for slide in slides:
        cmd.extend(["-loop", "1", "-t", "30", "-i", str(slide)])

    cmd.extend(["-i", str(audio)])

    if use_script:
        cmd.extend(["-filter_complex_script", filter_path])
    else:
        cmd.extend(["-filter_complex", filter_complex])

    cmd.extend(["-map", f"[{video_label}]"])
    cmd.extend(["-map", f"{n}:a"])
    cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", str(DEFAULT_CRF)])
    cmd.extend(["-c:a", "aac", "-b:a", DEFAULT_AUDIO_BITRATE])
    cmd.extend(["-pix_fmt", DEFAULT_PIX_FMT, "-r", str(DEFAULT_FPS)])
    cmd.extend(["-shortest"])
    cmd.append(str(output_path))

    # 실행
    log.info("Reel 렌더링 시작: %s", output_path.name)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT * 2
        )
        if result.returncode != 0:
            log.error("Reel 렌더링 실패: %s", result.stderr[:500])
            raise RuntimeError(f"FFmpeg 실패: {result.stderr[:300]}")
    finally:
        if filter_path and os.path.exists(filter_path):
            os.unlink(filter_path)

    log.info("Reel 렌더링 완료: %s", output_path)
    return output_path


__all__ = [
    "build_ken_burns_filter",
    "build_xfade_filter",
    "is_supported_xfade",
    "select_random_transitions",
    "build_scene_filter_chain",
    "build_drawtext_filter",
    "build_subtitle_filter_from_srt",
    "_parse_srt",
    "_find_korean_font",
    "_write_filter_file",
    "build_render_command",
    "render_carousel_video",
    "render_reel_video",
    "validate_rendered_video",
    "get_video_duration",
    "get_audio_duration",
]
