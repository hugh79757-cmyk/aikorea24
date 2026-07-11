from __future__ import annotations
import asyncio
from pathlib import Path
import edge_tts
import random

# ──────────────────────────────────────────────
# TTS Generator
# ──────────────────────────────────────────────
class TTSGenerator:
    """edge-tts를 사용한 MP3 + SRT 동시 생성"""
    
    VOICES = [
        "ko-KR-SunHiNeural",      # 여성, 자연스러움 (기본)
        "ko-KR-InJoonNeural",     # 남성, 차분함
        "ko-KR-BongJinNeural",    # 남성, 밝음
    ]
    
    def __init__(self, voice: str = "ko-KR-SunHiNeural", output_dir: str = "tts"):
        self.voice = voice
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate(self, text: str, output_name: str) -> tuple[Path, Path]:
        """
        텍스트 → MP3 + SRT 동시 생성
        
        Returns:
            (mp3_path, srt_path)
        """
        mp3_path = self.output_dir / f"{output_name}.mp3"
        srt_path = self.output_dir / f"{output_name}.srt"
        
        communicate = edge_tts.Communicate(text, self.voice)
        
        # MP3 + SRT 동시 저장
        await communicate.save(str(mp3_path), str(srt_path))
        
        # SRT 검증
        if not srt_path.exists() or srt_path.stat().st_size == 0:
            raise RuntimeError(f"SRT 생성 실패: {srt_path}")
        
        return mp3_path, srt_path
    
    async def generate_batch(self, texts: list[str], prefix: str = "narration") -> list[tuple[Path, Path]]:
        """배치 TTS 생성 (병렬 처리)"""
        tasks = [
            self.generate(text, f"{prefix}_{i+1}")
            for i, text in enumerate(texts)
        ]
        results = await asyncio.gather(*tasks)
        return results
    
    @staticmethod
    def random_voice() -> str:
        """랜덤 보이스 선택 (다양성 확보)"""
        return random.choice(TTSGenerator.VOICES)


# ──────────────────────────────────────────────
# SRT 유틸리티
# ──────────────────────────────────────────────
def parse_srt_duration(srt_path: Path) -> float:
    """SRT 파일에서 총 길이(초) 계산"""
    import re
    content = srt_path.read_text(encoding="utf-8")
    # 마지막 타임코드 파싱
    times = re.findall(r'(\d{2}:\d{2}:\d{2},\d{3})', content)
    if not times:
        return 0.0
    last = times[-1]
    h, m, s_ms = last.split(':')
    s, ms = s_ms.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def validate_srt_timing(srt_path: Path, expected_duration: float, tolerance: float = 0.5) -> bool:
    """SRT 타임코드가 예상 길이와 일치하는지 검증"""
    actual = parse_srt_duration(Path(srt_path))
    return abs(actual - expected_duration) <= 0.5


# ──────────────────────────────────────────────
# 배치 생성 헬퍼
# ──────────────────────────────────────────────
async def generate_narration_batch(
    texts: list[str],
    output_dir: str = "tts",
    voice: str = "ko-KR-SunHiNeural",
) -> list[tuple[Path, Path]]:
    """나레이션 배치 생성 편의 함수"""
    generator = TTSGenerator(voice=voice, output_dir=output_dir)
    return await generator.generate_batch(texts)


# ──────────────────────────────────────────────
# CLI 진입점 (테스트용)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python tts_generator.py '텍스트 내용' [output_name]")
            sys.exit(1)
        
        text = sys.argv[1]
        name = sys.argv[2] if len(sys.argv) > 2 else "narration"
        
        generator = TTSGenerator()
        mp3, srt = await generator.generate(text, name)
        print(f"✅ MP3: {mp3}")
        print(f"✅ SRT: {srt}")
    
    asyncio.run(main())