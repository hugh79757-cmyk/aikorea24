# build_reel.py — 10초 Reel 완전 자동화
import asyncio, edge_tts, subprocess, json
from pathlib import Path

CARDS = [
    {"img": "card_1.png", "text": "틱톡이 감원한다던 667명의 정체", "dur": 2.5},
    {"img": "card_2.png", "text": "자살 챌린지 영상 올리는 놈들은 알고리즘 피하는 데 도가 텄다", "dur": 2.5},
    {"img": "card_3.png", "text": "노조는 말한다: AI는 핑계일 뿐, 싼 나라로 일자리 빼돌리려는 것", "dur": 2.5},
    {"img": "card_4.png", "text": "장관도 경고했다: AI가 만드는 파괴적 영향, 불확실성 그대로 보여준다", "dur": 2.5},
    {"img": "card_5.png", "text": "최악을 막아주던 사람이 사라진 자리에 계속 놓치는 AI가 들어올 때", "dur": 2.5},
]

TRANSITIONS = ["wipeleft", "glitch", "circlecrop", "dissolve"]

async def gen_tts(text: str, out_mp3: Path, out_srt: Path):
    communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural")
    await communicate.save(str(out_mp3), str(out_srt))
    print(f"  🎤 TTS 생성: {out_mp3.name}")

async def main():
    # 1. TTS + SRT 병렬 생성
    print("\n📢 1단계: 나레이션 음성 생성 (edge-tts 무료)")
    tts_dir = Path("tts")
    tts_dir.mkdir(exist_ok=True)
    
    audio_files = []
    for i, c in enumerate(CARDS):
        audio_path = tts_dir / f"narration_{i+1}.mp3"
        srt_path = tts_dir / f"narration_{i+1}.srt"
        if not audio_path.exists():
            await gen_tts(c["text"], audio_path, srt_path)
        audio_files.append(audio_path)

    # 2. FFmpeg 필터그래프 동적 생성
    print("\n🎞️ 2단계: FFmpeg 필터그래프 생성")
    
    v_filters = []
    for i in range(5):
        v_filters.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"zoompan=z='if(gte(zoom,1.12),1.12,zoom+0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30[v{i}]"
        )
    
    # xfade 체인
    xfade_chain = ""
    last = "v0"
    for i in range(1, 5):
        trans = TRANSITIONS[i-1]
        offset = sum(c["dur"] for c in CARDS[:i]) - 0.5
        xfade_chain += f"[{last}][v{i}]xfade=transition={TRANSITIONS[i-1]}:duration=0.4:offset={offset:.1f}[v{i}out];"
        last = f"v{i}out"
    v_filters.append(f"{xfade_chain[:-1]}[vout]")

    # 자막 체인
    sub_chain = "[vout]"
    for i in range(1, 6):
        sub_chain += f"subtitles=tts/narration_{i}.srt:force_style='Fontsize=56,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=3,Shadow=1,MarginV=150'"
        if i < 5:
            sub_chain += f"[vsub{i}];[vsub{i}]"
    sub_chain += "[vfinal]"
    
    # 오디오 concat
    audio_inputs = "".join(f"[{4+i}:a]" for i in range(5))
    audio_concat = f"{audio_inputs}concat=n=5:v=0:a=1[aout]"
    
    filter_graph = ";".join(v_filters) + ";" + xfade_chain[:-1] + "[vout];" + sub_chain + ";" + audio_concat
    
    # 3. FFmpeg 실행
    print("\n🎬 3단계: FFmpeg 인코딩 (하드웨어 가속)")
    
    import sys
    if sys.platform == "darwin":
        hwaccel = "-hwaccel videotoolbox -c:v h264_videotoolbox"
    else:
        hwaccel = "-hwaccel auto -c:v h264_nvenc 2>/dev/null || -c:v libx264"
    
    cmd = [
        "ffmpeg", "-y",
        *[f"-loop 1 -t {c['dur']} -i cards/{c['img']}" for c in CARDS],
        *[f"-i tts/narration_{i}.mp3" for i in range(1,6)],
        "-filter_complex", filter_graph,
        "-map", "[vfinal]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox" if sys.platform=="darwin" else "libx264",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-shortest", "output_reel.mp4"
    ]
    
    print(f"명령어 실행 중...")
    result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\n✅ 완료! output_reel.mp4 생성됨")
    else:
        print(f"\n❌ 오류: {result.stderr[:500]}")

if __name__ == "__main__":
    asyncio.run(main())