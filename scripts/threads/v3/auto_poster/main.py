#!/usr/bin/env python3
"""
Instagram Carousel + Shorts/Reels 자동화 메인 엔트리포인트

Usage:
    python -m scripts.threads.v3.auto_poster.main --mode carousel --cards card1.txt card2.txt ...
    python -m scripts.threads.v3.auto_poster.main --mode reels --cards card1.txt card2.txt ...
    python -m scripts.threads.v3.auto_poster.main --mode both --cards card1.txt card2.txt ...
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, "/Users/twinssn/Projects/aikorea24")

from scripts.threads.v3.auto_poster.orchestrator import run_carousel_job, run_reels_job


def parse_args():
    parser = argparse.ArgumentParser(
        description="Instagram Carousel + Shorts/Reels 자동화",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Carousel만 생성
  python -m scripts.threads.v3.auto_poster.main --mode carousel --cards cards/*.txt
  
  # Reels만 생성
  python -m scripts.threads.v3.auto_poster.main --mode reels --cards cards/*.txt
  
  # 둘 다 생성 (기본)
  python -m scripts.threads.v3.auto_poster.main --mode both --cards cards/*.txt
        """
    )
    parser.add_argument(
        "--mode",
        choices=["carousel", "reels", "both"],
        default="both",
        help="생성 모드 (기본: both)",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        required=True,
        help="Format D 카드 텍스트 파일 경로들 (6개 필요)",
    )
    parser.add_argument(
        "--output-dir",
        default="instagram-reel-output",
        help="출력 디렉토리",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 발행 없이 테스트 실행",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력",
    )
    return parser.parse_args()


async def run_carousel_job(cards: list[str], output_dir: str = "instagram-reel-output") -> dict:
    """Carousel 작업 실행"""
    from scripts.threads.v3.auto_poster.content_converter import convert_format_d_to_carousel
    from scripts.threads.v3.auto_poster.html_to_png import render_cards_to_png
    from scripts.threads.v3.auto_poster.tts_generator import generate_narration_batch
    from scripts.threads.v3.auto_poster.video_builder import build_reel_from_images
    
    print("📋 1단계: Format D → Carousel 슬라이드 변환")
    carousel_data = convert_format_d_to_carousel(cards)
    print(f"  ✅ {len(cards)}카드 → {len(carousel_data)}슬라이드 변환")
    
    print("🎨 2단계: HTML → PNG 이미지 생성")
    png_paths = await render_cards_to_png(carousel_data)
    print(f"  ✅ {len(png_paths)}개 이미지 생성")
    
    print("🎤 3단계: TTS 나레이션 생성")
    # 카드에서 나레이션 텍스트 추출
    narration_texts = [slide.body for slide in carousel_data]
    audio_paths, srt_paths = await generate_narration_batch(carousel_data)
    print(f"  ✅ {len(audio_paths)}개 오디오 + SRT 생성")
    
    print("🎬 4단계: FFmpeg 비디오 생성 (Ken Burns + 전환 + 자막)")
    output_path = f"/Users/twinssn/Projects/aikorea24/instagram-reel-output/carousel_{int(__import__('time').time())}.mp4"
    video_path = build_reel_from_slides(
        slide_images=[f"/Users/twinssn/Projects/aikorea24/cards/slide_{i+1}.png" for i in range(7)],
        narration_files=[f"tts/narration_{i+1}.mp3" for i in range(7)],
        srt_files=[f"tts/narration_{i+1}.srt" for i in range(7)],
        output_path=Path("/Users/twinssn/Projects/aikorea24") / Path(output_dir) / f"carousel_{int(__import__('time').time())}.mp4"
    )
    print(f"  ✅ 비디오 생성: {output_path}")
    
    return {"video_path": output_path, "slide_count": 7}


async def run_reels_job(cards: list[str]) -> dict:
    """Reels 작업 실행"""
    from scripts.threads.v3.auto_poster.content_converter import convert_format_d_to_reel_script
    from scripts.threads.v3.auto_poster.video_builder import build_reel_from_scenes
    from scripts.threads.v3.auto_poster.tts_generator import generate_narration_batch
    
    print("📋 1단계: Format D → Reels 씬 대본 변환")
    scenes = convert_format_d_to_reel_script(cards)
    print(f"  ✅ {len(cards)}카드 → {len(scenes)}씬 변환")
    
    print("🎨 2단계: 씬별 이미지 생성 (Playwright)")
    # TODO: Reels용 HTML 템플릿 렌더링
    
    print("🎤 3단계: TTS 나레이션 생성")
    narration_texts = [scene.text for scene in scenes]
    audio_paths, srt_paths = await generate_narration_batch(narration_texts)
    
    print("🎬 4단계: FFmpeg 비디오 생성 (Ken Burns + 전환 + 자막)")
    output_path = build_reel_from_scenes(scenes)
    
    return {"video_path": output_path, "scene_count": len(scenes)}


async def run_both_jobs(cards: list[str]) -> dict:
    """Carousel + Reels 둘 다 생성"""
    carousel_result = await run_carousel_job(cards)
    reels_result = await run_reels_job(cards)
    return {"carousel": carousel_result, "reels": reels_result}


async def main():
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Instagram Carousel + Shorts/Reels 자동화",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["carousel", "reels", "both"],
        default="both",
        help="생성 모드 (기본: both)",
    )
    parser.add_argument(
        "--cards",
        nargs="+",
        required=True,
        help="Format D 카드 텍스트 파일 경로들 (6개 필요)",
    )
    parser.add_argument(
        "--output-dir",
        default="instagram-reel-output",
        help="출력 디렉토리",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 발행 없이 테스트 실행",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력",
    )
    
    args = parser.parse_args()
    
    # 카드 파일 읽기
    cards = []
    for card_path in args.cards:
        with open(card_path, "r") as f:
            cards.append(f.read().strip())
    
    if len(cards) != 6:
        print(f"❌ Format D 카드는 정확히 6개여야 합니다. 현재: {len(cards)}개")
        sys.exit(1)
    
    print(f"🚀 Instagram Carousel + Shorts/Reels 자동화 시작")
    print(f"📝 모드: {args.mode}")
    print(f"📝 카드 수: {len(cards)}개")
    
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        if args.mode in ("carousel", "both"):
            print("\n🎞️ Carousel 생성 중...")
            carousel_result = await run_carousel_job(cards)
            print(f"✅ Carousel 완료: {carosel_result.get('video_path', 'N/A')}")
        
        if args.mode in ("reels", "both"):
            print("\n🎬 Reels 생성 중...")
            reels_result = await run_reels_job(cards)
            print(f"✅ Reels 완료: {reels_result.get('video_path', 'N/A')}")
        
        print("\n🎉 모든 작업 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())