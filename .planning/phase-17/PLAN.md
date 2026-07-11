# Phase 17 — PLAN.md

> **Phase:** 17 — Instagram Carousel + Shorts/Reels 자동화 파이프라인
> **Mode:** ad-hoc (MVP)
> **Depends on:** Phase 16 (Writer prompt v2 완료), 기존 파이프라인 인프라
> **Created:** 2026-07-11

---

## Goal

기존 뉴스 파이프라인(키워드 → D1 뉴스 → Pitch → Writer Format D → Threads 발행)을 확장하여, **Instagram Carousel(캐러셀) + Shorts/Reels(쇼츠/릴스)** 자동 생성/발행 파이프라인 구축.

- **비용**: $0/월 (무료 티어만 사용)
- **기존 파이프라인 재사용**: Format D(펀치 브리핑 5카드) → 캐러셀/쇼츠 변환
- **자동화 레벨**: 완전 자동 (HTML→PNG→FFmpeg→Graph API→스케줄링)

---

## Task 1: 콘텐츠 변환기 (Format D → Carousel/Shorts 대본)

**File:** `scripts/threads/v3/auto_poster/content_adapter.py`

**Changes:**
1.1 `ContentAdapter` 클래스 생성: Format D(5카드) → Carousel 5~7장 / Shorts 15~30초 대본 변환
1.2 카드별 매핑 로직:
   - Card 1(Hook) → Slide 1: 큰 숫자 + 한 줄 훅 / Scene 1: Hook (0~2초)
   - Card 2(Conflict) → Slide 2: Conflict / Scene 2: Conflict (2~5초)
   - Card 3(Twist) → Slide 3: Twist / Scene 3: Twist (5~10초)
   - Card 4(Expansion) → Slide 4: Expansion / Scene 4: Expansion (10~15초)
   - Card 5(CTA/질문) → Slide 5: CTA + 질문 / Scene 5: CTA (15~20초)
   - Card 6(Link) → Slide 6~7: 링크+브랜딩 / Scene 6: 브랜딩+팔로우 유도
1.3 Shorts용: 15~30초 내에 담기도록 텍스트 길이 자동 조절 (자막 읽기 속도 고려)
1.4 템플릿 변수 치환 시스템 (Jinja2)

**검증:** `py_compile` 통과, 단위 테스트 5개 이상 통과

---

## Task 2: HTML 템플릿 + Playwright 캡처 (HTML → PNG)

**File:** `scripts/threads/v3/auto_poster/html_to_png.py` (신규)
**File:** `scripts/threads/v3/auto_poster/templates/carousel.html` (신규)
**File:** `scripts/threads/v3/auto_poster/templates/reels.html` (신규)

**Changes:**
2.1 `CarouselTemplate` 클래스: 5~7장 슬라이드 HTML 생성 (1080×1350, 4:5)
2.2 `ReelsTemplate` 클래스: 세로형 1080×1920 HTML 생성
2.3 공통 스타일: Pretendard 폰트, 브랜드 컬러(#2563EB, #7C3AED, #14B8A6), 글래스모피즘 카드
2.4 Playwright 캡처: `html_to_png.py` 재사용/개선 → 고정 해상도(1080×1350 / 1080×1920) PNG 출력
2.3 배치 처리: 5~7장 병렬 캡처 → `cards/slide_1.png` ~ `cards/slide_7.png` 저장

**검증:** 생성된 PNG 해상도 확인 (1080×1350 / 1080×1920), 시각적 품질 확인

---

## Task 3: FFmpeg 비디오 렌더러 (이미지 → MP4)

**File:** `scripts/threads/v3/auto_poster/video_builder.py` (신규)

**Changes:**
3.1 `VideoBuilder` 클래스: FFmpeg 필터그래프 동적 생성
3.2 **Ken Burns** (zoompan):
   - `z='min(zoom+0.0015,1.12)'`: 1.0x → 1.12x 부드러운 줌인
   - `d=75` (2.5초 @ 30fps), `s=1080x1920` (Reels) / `1080x1350` (Carousel)
   - 센터 기준 팬: `x='iw/2-(iw/zoom/2)'`, `y='ih/2-(ih/zoom/2)'`
3.3 **전환 효과** (xfade 체인):
   - 4가지 전환: `wipeleft` → `circlecrop` → `dissolve` → `smoothleft`
   - `duration=0.4`, `offset` 누적 계산
3.4 **자막 바운스** (drawtext + SRT):
   - `subtitles=narration_1.srt:force_style='Fontsize=56*(0.7+0.3*sin(2*PI*t/0.5))'`
   - `enable='between(t,start,end)'`로 각 구간만 표시
   - `box=1:boxcolor=black@0.6:borderw=3` 배경 박스
3.5 **자막 바운스 애니메이션** (폰트 크기 easing):
   - `fontsize='56*(0.7+0.3*sin(2*PI*t/0.5))'` (sine-out pop)
   - 오버슈트 버전: `fontsize='56*(0.7+0.4*sin(2*PI*t/0.5))'`
3.6 **비트 싱크 컷** (선택): `librosa` onset detection → `aselect`/`select` 필터로 오디오 피크에서 컷
3.7 **오디오 합성**: 5개 TTS MP3 concat → AAC 128kbps
3.8 **출력 설정**: 1080×1920 (Reels) / 1080×1350 (Carousel), 30fps, H.264, CRF 20~23, `-shortest`

**검증:** 생성된 MP4 `ffprobe`로 검증 (1080×1920/1350, 30fps, 10~30초)

---

## Task 4: TTS + 자막 생성 (edge-tts)

**File:** `scripts/threads/v3/auto_poster/tts_generator.py` (신규)

**Changes:**
4.1 `TTSGenerator` 클래스: `edge-tts` 비동기 호출로 MP3 + SRT 동시 생성
4.2 음성: `ko-KR-SunHiNeural` (자연스러운 한국어 여성)
4.3 SRT 생성: `--write-subtitles` 옵션으로 타임코드 포함 SRT 자동 생성
4.4 배치 처리: 5개 세그먼트 병렬 생성 (`asyncio.gather`)
4.5 텍스트 길이 자동 조절: Shorts용 15~30자/세그먼트

**검증:** 생성된 MP3 재생 확인, SRT 타임코드 정확도 ±0.5초

---

## Task 5: Instagram Graph API 발행 (Carousel + Reels)

**File:** `scripts/threads/v3/auto_poster/instagram_publish.py` (신규)

**Changes:**
5.1 `InstagramPublisher` 클래스: Graph API 래퍼
5.2 **Carousel 발행**:
   - 각 슬라이드 이미지 → Media Container 생성 (`is_carousel_item=true`)
   - Parent Container 생성 (`media_type=CAROUSEL`, `children=[slide_ids]`)
   - Parent Publish
5.3 **Reels 발행**:
   - 비디오 → Media Container 생성 (`media_type=REELS`)
   - Publish
5.3 공통: 캡션, 해시태그, 위치 태그 지원
5.4 에러 처리: 레이트 리밋 시 지수 백오프, 토큰 갱신 로직
5.5 응답 로깅: `posted.json`에 media_id, permalink, timestamp 기록

**검증:** 테스트 계정으로 Carousel 1회 + Reels 1회 발행 성공

---

## Task 6: 스케줄러 + 오케스트레이터

**File:** `scripts/threads/v3/auto_poster/scheduler.py` (신규)
**File:** `scripts/threads/v3/auto_poster/orchestrator.py` (신규)

**Changes:**
6.1 `Scheduler`: `launchd` (macOS) / `systemd` (Linux) 플러그인 생성
   - Carousel: 매일 08:00 KST
   - Shorts/Reels: 매일 19:00 KST
   - `.plist` / `.service` 템플릿 생성 + `install_scheduler.sh`
6.2 `Orchestrator`: 전체 파이프라인 조율
   - 입력: Format D 결과(JSON) → 콘텐츠 변환 → 이미지 생성 → TTS → 비디오 → 발행
   - 상태 관리: D1 `sns_jobs` 테이블에 job_id, status, media_id, error 기록
   - 재시도: 지수 백오프 (1m, 2m, 4m, 8m, max 5회)
   - 알림: 실패 시 Telegram/Slack 알림
6.3 `main.py`: CLI 엔트리포인트 (`python -m auto_poster run --mode carousel|reels`)

**검증:** `launchd` 플리스트 설치 → `launchctl load` → 1회 실행 테스트

---

## Task 7: 통합 테스트 + 문서화

**File:** `scripts/threads/v3/auto_poster/test_integration.py` (신규)
**File:** `docs/auto_poster_guide.md` (신규)

**Changes:**
7.1 E2E 테스트: Format D JSON → Carousel MP4 + Reels MP4 → 발행 → 검증
7.2 품질 체크리스트: 해상도, 길이, 자막 싱크, Ken Burns 부드러움, 전환 자연스러움
7.3 운영 가이드: 설치, 설정(.env), 실행, 모니터링, 트러블슈팅
7.4 롤백 절차: 실패 시 이전 버전 복구, 발행 취소 API

**검증:** 3일간 드라이런 → 품질 체크 → 정식 운영 전환

---

## 검증 루프

1. `py_compile` 모든 Python 파일 통과
2. 단위 테스트: `pytest scripts/threads/v3/auto_poster/test_*.py -v`
3. 통합 테스트: `python -m auto_poster test --mode carousel --dry-run`
3. FFmpeg 필터그래프 문법 검증: `ffmpeg -filter_complex_script filter.txt -f null -`
4. Git 커밋: `feat: Phase 17 - Instagram Carousel + Shorts/Reels 자동화 파이프라인`
5. `STATE.md` 업데이트

---

## 파일 구조 (최종)

```
/Users/twinssn/Projects/aikorea24/
├── instagram-carousel-output/      # HTML 템플릿 + PNG 캡처
├── instagram-reel-output/          # FFmpeg 출력 MP4
├── cards/                          # PNG 슬라이드 이미지
├── tts/                            # edge-tts MP3 + SRT
├── scripts/
│   ├── build_reel.py               # FFmpeg 단일 패스 생성기 (기존)
│   ├── test_reel3.py               # 테스트용 단순 버전 (기존)
│   └── threads/
│       └── v3/
│           ├── auto_poster/        # ★ 신규: SNS 자동화 모듈
│           │   ├── __init__.py
│           │   ├── content_adapter.py
│           │   ├── html_to_png.py
│           │   ├── video_builder.py
│           │   ├── tts_generator.py
│           │   ├── instagram_publish.py
│           │   ├── scheduler.py
│           │   ├── orchestrator.py
│           │   ├── main.py
│           │   ├── templates/
│           │   │   ├── carousel.html
│           │   │   └── reels.html
│           │   └── test_*.py
│           └── auto_poster/        # 기존 (기존 build_reel.py 등)
└── .planning/phase-17/
    ├── CONTEXT.md
    ├── RESEARCH.md
    ├── PLAN.md (이 파일)
    └── SUMMARY.md
```