#!/usr/bin/env python3
"""
Instagram Reel 자동 생성기 (간단 버전 - MoviePy 2.x 호환)
- 기존 HTML 템플릿 → 이미지 → 비디오
- moviepy 2.x + edge-tts + playwright 사용
"""

import asyncio
from pathlib import Path
# MoviePy 2.x imports
from moviepy import *
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
import edge_tts
from playwright.sync_api import sync_playwright

# ============================================
# 설정
# ============================================
WIDTH, HEIGHT = 1080, 1350  # Instagram Carousel/Reels
FPS = 30
CARD_DURATION = 5.0  # 각 카드 기본 길이 (초)
TRANSITION_DURATION = 0.8  # 트랜지션 길이
OUTPUT_DIR = Path("instagram-reel-output")
OUTPUT_DIR.mkdir(exist_ok=True)

# 사용된 이미지 파일들 (이미 생성됨)
IMAGE_FILES = [
    "instagram-carousel-output/minimalist-format-d-1.html",
    "instagram-carousel-output/minimalist-format-d-2.html", 
    "instagram-carousel-output/minimalist-format-d-3.html",
    "instagram-carousel-output/minimalist-format-d-4.html",
    "instagram-carousel-output/minimalist-format-d-5.html",
]

# 각 카드별 나레이션 텍스트 (edge-tts로 음성 생성)
NARRATIONS = [
    "틱톡이 감원한다던 667명의 정체. 약 300명이라던 공식 발표와 달리 내부 문서엔 2배 넘는 667명이 찍혀 있었습니다. 더블린 전체 직원의 40퍼센트입니다.",
    "잘리는 팀은 자살 챌린지 영상을 사람 눈으로 걸러내던 검수팀입니다. 더블린 전체 직원의 40퍼센트, ADSO 팀 전원이 대상입니다.",
    "그런데 반전이 있습니다. 익명의 틱톡 검수 직원이 이렇게 남겼습니다. '자살 챌린지 올리는 놈들은 알고리즘 피하는 데 도가 텄다. 유해 콘텐츠는 계속 변하기 때문에 AI도 사람이 계속 업데이트해줘야 한다. 사람 눈이 필요하다.' AI가 놓치는 걸 잡아내던 사람을 AI로 대체하겠다는 얘기였습니다.",
    "노조는 한 발 더 나갑니다. '테크 기업들은 AI를 최신 핑곗거리로 쓰고 있을 뿐이다. 노동자 권리를 무너뜨리고 괜찮은 일자리를 더 싼 나라로 빼돌리려는 것이다.' 아일랜드 공공지출부 장관도 경고했습니다. 'AI가 만드는 파괴적 영향이 얼마나 불확실한지 그대로 보여주는 사건이다.'",
    "정리하면, 아이들 노리는 콘텐츠를 사람 눈으로 거르던 더블린 검수팀 667명, 40퍼센트가 AI라는 이름으로 잘릴 위기입니다. 근데 그 AI는 아직도 그 콘텐츠를 놓치고 있습니다. 최악을 막아주던 사람이 사라진 자리에 그걸 자꾸 놓치는 AI가 들어올 때, 당신 피드는 더 안전해지는 걸까요, 아니면 그 반대일까요."
]

# ============================================
# 헬퍼 함수들
# ============================================
async def generate_tts(text: str, output_path: Path, voice: str = "ko-KR-SunHiNeural"):
    """edge-tts로 한국어 음성 생성"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
    print(f"  🎤 TTS 생성: {output_path.name}")

def html_to_image(html_path: Path, output_path: Path):
    """HTML을 이미지로 변환 (Playwright 사용)"""
    # 이미 PNG가 있으면 스킵
    if output_path.exists():
        return output_path
    
    # playwright로 렌더링
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(f"file://{html_path.absolute()}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(output_path), full_page=True)
        browser.close()
    
    print(f"  🖼️ 이미지 변환: {output_path.name}")
    return output_path

def create_video():
    """비디오 생성 메인 함수"""
    print("=" * 50)
    print("🎬 Instagram Reel 생성 시작 (MoviePy 2.x)")
    print("=" * 50)
    
    # 1. TTS 음성 파일 생성
    print("\n📢 1단계: 나레이션 음성 생성 (edge-tts)")
    tts_dir = OUTPUT_DIR / "tts"
    tts_dir.mkdir(exist_ok=True)
    
    audio_files = []
    for i, (narration, html_file) in enumerate(zip(NARRATIONS, IMAGE_FILES)):
        audio_path = tts_dir / f"narration_{i+1}.mp3"
        if not audio_path.exists():
            asyncio.run(generate_tts(narration, audio_path))
        audio_files.append(audio_path)
    
    # 2. HTML → 이미지 변환
    print("\n🖼️ 2단계: HTML → 이미지 변환 (Playwright)")
    image_dir = OUTPUT_DIR / "images"
    image_dir.mkdir(exist_ok=True)
    
    image_files = []
    for i, html_file in enumerate(IMAGE_FILES):
        html_path = Path(html_file)
        img_path = image_dir / f"card_{i+1}.png"
        html_to_image(html_path, img_path)
        image_files.append(img_path)
    
    # 3. 비디오 클립 조립
    print("\n🎞️ 3단계: 비디오 클립 조립 (moviepy 2.x)")
    
    clips = []
    for i, (img_path, audio_path) in enumerate(zip(image_files, audio_files)):
        print(f"  카드 {i+1} 처리 중...")
        
        # 이미지 클립
        img_clip = ImageClip(str(img_path)).with_duration(CARD_DURATION)
        
        # 오디오 클립
        audio_clip = AudioFileClip(str(audio_path))
        
        # 실제 길이: 오디오 길이 + 0.5초 (최소 CARD_DURATION)
        actual_duration = max(CARD_DURATION, audio_clip.duration + 0.5)
        img_clip = img_clip.with_duration(actual_duration)
        
        # 리사이즈 (1080x1350 강제)
        img_clip = img_clip.resized((WIDTH, HEIGHT))
        
        # 오디오 결합
        img_clip = img_clip.with_audio(audio_clip)
        
        # 트랜지션 (MoviePy 2.x: CrossFadeIn/CrossFadeOut 클래스 사용)
        if i > 0:
            img_clip = CrossFadeIn(TRANSITION_DURATION).apply(img_clip)
        if i < len(image_files) - 1:
            img_clip = CrossFadeOut(TRANSITION_DURATION).apply(img_clip)
        
        clips.append(img_clip)
        print(f"    ✅ 길이: {actual_duration:.1f}초")
    
    # 4. 전체 결합
    print("\n🔗 4단계: 전체 비디오 결합")
    final = concatenate_videoclips(clips, method="compose")
    
    # 5. 출력
    output_path = OUTPUT_DIR / "format-d-reel-final.mp4"
    print(f"\n💾 5단계: 비디오 저장")
    print(f"   경로: {output_path}")
    print(f"   해상도: {WIDTH}x{HEIGHT}")
    print(f"   길이: {final.duration:.1f}초")
    print(f"   FPS: {FPS}")
    
    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="5000k",
        threads=4,
        preset="medium"
    )
    
    print(f"\n✅ 완료! {output_path}")
    return output_path

if __name__ == "__main__":
    # 의존성 확인
    try:
        import edge_tts
        from moviepy import *
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"❌ 의존성 누락: {e}")
        print("설치: pip install --break-system-packages edge-tts moviepy playwright && playwright install chromium")
        exit(1)
    
    create_video()