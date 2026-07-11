#!/usr/bin/env python3
"""
Instagram Reels 비디오 생성기
- 이미지 시퀀스 + TTS 나레이션 + 크로스페이드 + BGM
- 출력: 1080x1920 (세로) MP4
"""

import os
import sys
from pathlib import Path

# 의존성 확인
try:
    from moviepy.editor import (
        ImageSequenceClip, AudioFileClip, CompositeAudioClip,
        concatenate_videoclips, VideoFileClip, ColorClip
    )
    from moviepy.video.fx.all import crossfadein, crossfadeout, resize
    import edge_tts
    import asyncio
except ImportError as e:
    print(f"❌ 의존성 누락: {e}")
    print("설치: pip install moviepy edge-tts")
    sys.exit(1)

# ============================================
# 설정
# ============================================
IMAGES_DIR = Path("/Users/twinssn/Projects/aikorea24/instagram-carousel-output")
OUTPUT_DIR = Path("/Users/twinssn/Projects/aikorea24/reels-output")
OUTPUT_DIR.mkdir(exist_ok=True)

# 비디오 설정
WIDTH, HEIGHT = 1080, 1920  # Instagram Reels 세로
FPS = 30
CARD_DURATION = 3.5  # 각 카드 표시 시간 (초)
TRANSITION_DURATION = 0.8  # 크로스페이드 길이 (초)

# 카드별 나레이션 스크립트 (한국어)
NARRATIONS = [
    "틱톡이 감원한다던 667명의 정체. 공식 발표는 약 300명, 내부 문서엔 2배 넘는 667명. 더블린 전체 직원의 40%가 잘릴 위기.",
    "충돌 A면: 자살 챌린지 영상 올리는 놈들은 알고리즘 피하는 데 도가 텄다. 유해 콘텐츠는 계속 바뀌기 때문에 AI도 사람이 계속 업데이트해줘야 한다. 사람 눈이 필요하다.",
    "반전: 근데 노조는 한 발 더 나갔다. 테크 기업들은 AI를 최신 핑곗거리로 쓰고 있을 뿐이다. 노동자 권리를 무너뜨리고 괜찮은 일자리를 더 싼 나라로 빼돌리려는 것이다.",
    "확장: 이게 왜 중요할까? 아일랜드 공공지출부 장관도 경고했다. AI가 만드는 파괴적 영향이 얼마나 불확실한지 그대로 보여주는 사건이다. AI가 제일 먼저 먹는 일자리는 창의직이 아니라 당신 피드에서 최악의 콘텐츠를 막아주던 안전 직군이다.",
    "정리: 최악을 막아주던 사람이 사라진 자리에 그걸 자꾸 놓치는 AI가 들어올 때, 당신 피드는 더 안전해지는 걸까 아니면 그 반대일까? 전체 기사는 aikorea24.kr에서."
]

# BGM 설정 (로컬 파일 필요 시 경로 지정)
BGM_PATH = None  # "assets/bgm.mp3" - 없으면 무음

# ============================================
# 유틸리티
# ============================================
async def generate_tts(text: str, output_path: Path, voice: str = "ko-KR-SunHiNeural"):
    """Edge TTS로 한국어 음성 생성"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
    print(f"  🎙️ TTS 생성: {output_path.name}")

def resize_to_reels(clip):
    """1080x1920 세로 비율로 리사이즈 (레터박스/필박스 처리)"""
    # 원본 비율 유지하며 1080 너비에 맞춤, 높이 1920 초과 시 크롭
    w, h = clip.size
    target_ratio = WIDTH / HEIGHT
    current_ratio = w / h
    
    if current_ratio > target_ratio:
        # 가로가 더 김 → 높이 기준 리사이즈
        new_h = HEIGHT
        new_w = int(h * target_ratio)
    else:
        # 세로가 더 김 → 너비 기준 리사이즈
        new_w = WIDTH
        new_h = int(w / target_ratio)
    
    clip = clip.resize((new_w, new_h))
    
    # 중앙 정렬로 1080x1920 캔버스에 배치
    bg = ColorClip((WIDTH, HEIGHT), color=(255, 255, 255), duration=clip.duration)
    x = (WIDTH - new_w) // 2
    y = (HEIGHT - new_h) // 2
    return CompositeVideoClip([bg, clip.set_position((x, y))])

# ============================================
# 메인 생성 함수
# ============================================
async def create_reel():
    print("🎬 Instagram Reels 비디오 생성 시작...")
    print(f"📁 이미지 폴더: {IMAGES_DIR}")
    print(f"📁 출력 폴더: {OUTPUT_DIR}")
    
    # 이미지 파일 수집 (정렬)
    image_files = sorted(IMAGES_DIR.glob("minimalist-format-d-*.png"))
    if not image_files:
        # HTML에서 캡처한 파일명 패턴도 시도
        image_files = sorted(IMAGES_DIR.glob("minimalist-format-d-*.png"))
    
    if not image_files:
        print("❌ 이미지 파일을 찾을 수 없습니다!")
        return
    
    # 처음 5개만 사용 (Format D 5카드)
    image_files = image_files[:5]
    print(f"📸 사용 이미지: {[f.name for f in image_files]}")
    
    # TTS 음성 생성
    print("\n🎙️ TTS 나레이션 생성 중...")
    tts_dir = OUTPUT_DIR / "tts"
    tts_dir.mkdir(exist_ok=True)
    
    audio_files = []
    for i, (img, narration) in enumerate(zip(image_files, NARRATIONS)):
        audio_path = tts_dir / f"narration_{i+1}.mp3"
        if not audio_path.exists():
            await generate_tts(narration, audio_path)
        audio_files.append(audio_path)
    
    # 비디오 클립 생성
    print("\n🎞️ 비디오 클립 조립 중...")
    
    clips = []
    for i, (img_path, audio_path) in enumerate(zip(image_files, audio_files)):
        # 이미지 클립
        img_clip = ImageSequenceClip([str(img_path)], durations=[CARD_DURATION])
        img_clip = resize_to_reels(img_clip)
        
        # 오디오 클립
        audio_clip = AudioFileClip(str(audio_path))
        
        # 오디오 길이에 맞춰 비디오 길이 조정 (최소 CARD_DURATION 보장)
        actual_duration = max(CARD_DURATION, audio_clip.duration + 0.5)
        img_clip = img_clip.set_duration(actual_duration)
        
        # 오디오 결합
        img_clip = img_clip.set_audio(audio_clip)
        
        # 크로스페이드 트랜지션 (첫 번째 제외)
        if i > 0:
            img_clip = img_clip.fx(crossfadein, TRANSITION_DURATION)
        if i < len(image_files) - 1:
            img_clip = img_clip.fx(crossfadeout, TRANSITION_DURATION)
        
        clips.append(img_clip)
        print(f"  ✅ 카드 {i+1}: {img_path.name} ({actual_duration:.1f}초)")
    
    # 전체 비디오 결합
    print("\n🔗 클립 결합 중...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    # BGM 추가 (있는 경우)
    if BGM_PATH and Path(BGM_PATH).exists():
        print("🎵 BGM 추가 중...")
        bgm = AudioFileClip(BGM_PATH).volumex(0.15)  # 볼륨 15%
        # 길이 맞춰 반복
        bgm_duration = final_video.duration
        if bgm.duration < bgm_duration:
            loops = int(bgm_duration / bgm.duration) + 1
            bgm = concatenate_audioclips([bgm] * loops).subclip(0, bgm_duration)
        else:
            bgm = bgm.subclip(0, bgm_duration)
        
        # 기존 오디오와 믹스
        final_audio = CompositeAudioClip([final_video.audio, bgm])
        final_video = final_video.set_audio(final_audio)
    
    # 출력
    output_path = OUTPUT_DIR / "format-d-reel-final.mp4"
    print(f"\n💾 비디오 저장 중: {output_path}")
    print(f"   해상도: {WIDTH}x{HEIGHT} | FPS: {FPS} | 길이: {final_video.duration:.1f}초")
    
    final_video.write_videofile(
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

# ============================================
# 실행
# ============================================
if __name__ == "__main__":
    asyncio.run(create_reel())