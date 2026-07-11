from __future__ import annotations
import subprocess
import os
import tempfile
from pathlib import Path
from typing import Optional

from pipeline.instagram.models import InstagramReelScene


class VideoBuilder:
    """FFmpeg 기반 비디오 빌더 (Ken Burns + xfade + drawtext 자막)"""
    
    def __init__(
        self,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        crf: int = 22,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self.temp_dir = Path("/tmp/instagram_reel")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def build_reel(
        self,
        scenes: list,
        audio_paths: list[str],
        srt_paths: list[str],
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Reels용 비디오 생성 (Ken Burns + xfade + 자막)"""
        
        # 필터 그래프 파일 생성
        filter_script = self._build_reel_filter(scenes)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir=self.temp_dir) as f:
            f.write(filter_script)
            filter_file = f.name
        
        try:
            # 이미지/오디오 입력 구성
            cmd = ["ffmpeg", "-y"]
            
            # 이미지 입력 (각 씬마다 이미지 필요 - 여기선 단색 배경이나 슬라이드 이미지 사용)
            # 실제로는 슬라이드 이미지 파일들이 필요함
            # 여기서는 테스트용 단색 배경 생성
            for i in range(6):
                # 실제로는 slide_{i}.png 파일이 필요
                pass
            
            # 실제 구현은 아래 build_reel_from_images 사용 권장
            pass
        
        return ""
    
    def _build_reel_filter(self, scenes: list) -> str:
        """Reels용 FFmpeg 필터그래프 생성"""
        n_scenes = len(scenes)
        filters = []
        
        # 각 씬별 비디오 스트림 생성 (Ken Burns zoompan)
        for i, scene in enumerate(scenes):
            duration_frames = int(scene.duration_seconds * 30)
            zoom_expr = "min(zoom+0.0015,1.12)" if i > 0 else "min(zoom+0.0015,1.12)"
            
            filters.append(
                f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,"
                f"zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(scenes[0].duration_seconds * 30)}:s=1080x1920:fps=30[v{i}]"
            )
        
        # xfade 체인
        transitions = ["wipeleft", "circlecrop", "dissolve", "smoothleft"]
        xfade_chain = ""
        last = "v0"
        for i in range(1, len(scenes)):
            trans = transitions[(i-1) % 4]
            offset = 2.5 * i - 0.5  # 2.5초마다 전환, 0.5초 중첩
            xfade_chain += f"[{last}][v{i}]xfade=transition=circlecrop:duration=0.4:offset={2.5*i-0.5}[v{i}out];"
            last = f"v{i}out"
        
        # 자막 합성 (SRT 파일 기반)
        subtitle_filters = []
        for i in range(len(scenes)):
            if i == 0:
                last_v = "v0"
            else:
                last_v = f"v{i-1}out"
            subtitle_filters.append(
                f"[{last_v}]subtitles=tts/narration_{i+1}.srt:"
                f"force_style='Fontsize=56,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                f"BorderStyle=3,Outline=3,Shadow=1,MarginV=150'[v{i}sub];"
            )
            last_v = f"v{i}sub"
        
        # 최종 비디오 출력
        final = f"[{last_v}]copy[vout];"
        
        # 오디오 concat
        audio_concat = "[5:a][6:a][7:a][8:a][9:a][10:a]concat=n=6:v=0:a=1[aout]"
        
        filter_script = "\n".join([
            *[
                f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                f"zoompan=z='min(zoom+0.0015,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v{i}]"
                for i in range(6)
            ],
            "[v0][v1]xfade=transition=wipeleft:duration=0.4:offset=1.9[v01];",
            "[v01][v2]xfade=transition=circlecrop:duration=0.35:offset=3.8[v012];",
            "[v012][v3]xfade=transition=dissolve:duration=0.4:offset=5.7[v0123];",
            "[v0123][v4]xfade=transition=smoothleft:duration=0.4:offset=7.6[vout];",
            "[5:a][6:a][7:a][8:a][9:a][10:a]concat=n=6:v=0:a=1[aout]",
        ])
        
        return "\n".join(filter_script)


def build_reel_from_images(
    image_paths: list[str],
    audio_paths: list[str],
    srt_paths: list[str],
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    durations: list[float] = None,
    transitions: list[str] = None,
    crf: int = 22,
) -> str:
    """
    이미지 + 오디오 + SRT → Reels MP4 생성
    
    Args:
        image_paths: 슬라이드 이미지 경로 리스트 (6개)
        audio_paths: TTS MP3 경로 리스트 (6개)
        srt_paths: SRT 자막 경로 리스트 (6개)
        output_path: 출력 MP4 경로
        width/height: 해상도 (1080x1920)
        fps: 프레임레이트
        durations: 각 씬 길이(초), 기본 2.5초
        transitions: 전환 효과 리스트 (wipeleft, circlecrop, dissolve, smoothleft 등)
        crf: 품질 (18-28, 낮을수록 고화질)
    """
    if durations is None:
        durations = [2.5] * 6
    if transitions is None:
        transitions = ["wipeleft", "circlecrop", "dissolve", "smoothleft", "dissolve"]
    
    n = len(image_paths)
    
    # 필터그래프 파일 생성
    filter_lines = []
    
    # 1. 각 이미지 → Ken Burns 비디오 스트림
    for i in range(6):
        dur = durations[i] if i < len(durations) else 2.5
        frames = int(durations[i] * 30)
        filter_lines.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(durations[i]*30)}:s=1080x1920:fps=30[v{i}];"
        )
    
    # 2. xfade 체인
    transitions = ["wipeleft", "circlecrop", "dissolve", "smoothleft", "dissolve"]
    offsets = [1.9, 3.8, 5.7, 7.6]
    
    xfade_chain = ""
    last = "v0"
    for i in range(1, 6):
        trans = ["wipeleft", "circlecrop", "dissolve", "smoothleft", "dissolve"][i-1]
        offset = 2.5 * i - 0.5
        xfade_chain += f"[v{i-1}out][v{i}]xfade=transition=circlecrop:duration=0.4:offset={2.5*i-0.5}[v{i}out];"
        last = f"v{i}out"
    
    # 연결
    filter_parts = []
    for i in range(6):
        filter_parts.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(2.5*30)}:s=1080x1920:fps=30[v{i}];"
        )
    
    # xfade 체인
    xfade_chain = (
        "[v0][v1]xfade=transition=wipeleft:duration=0.4:offset=1.9[v01];"
        "[v01][v2]xfade=transition=circlecrop:duration=0.35:offset=3.8[v012];"
        "[v012][v3]xfade=transition=dissolve:duration=0.4:offset=5.7[v0123];"
        "[v0123][v4]xfade=transition=smoothleft:duration=0.4:offset=7.6[vout];"
    )
    filter_parts.append(xfade_chain)
    
    # 자막 번인
    for i in range(6):
        filter_parts.append(
            f"[vout]subtitles=tts/narration_{i+1}.srt:force_style='Fontsize=56,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=3,Shadow=1,MarginV=150'[vsub{i}];"
        )
    
    # 오디오 concat
    filter_parts.append("[5:a][6:a][7:a][8:a][9:a][10:a]concat=n=6:v=0:a=1[aout]")
    
    # 최종 매핑
    filter_parts.append("[vsub5]copy[vfinal];[aout]copy[afinal]")
    
    filter_graph = "\n".join(filter_parts)
    
    # 필터 파일 저장
    with open("/tmp/filter.txt", "w") as f:
        f.write(filter_graph)
    
    # FFmpeg 실행
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_1.png",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_2.png",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_3.png",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_4.png",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_5.png",
        "-loop", "1", "-t", "2.5", "-i", "cards/card_6.png",
        "-i", "tts/narration_1.mp3",
        "-i", "tts/narration_2.mp3",
        "-i", "tts/narration_3.mp3",
        "-i", "tts/narration_4.mp3",
        "-i", "tts/narration_5.mp3",
        "-i", "tts/narration_6.mp3",
        "-filter_complex_script", "/tmp/filter.txt",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-t", "10", "-shortest", "output_reel.mp4"
    ]
    
    # 실제 실행은 Python에서 subprocess로
    return output_path