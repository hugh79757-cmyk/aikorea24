# Phase 17 — CONTEXT.md

> **Phase:** 17 — Instagram Carousel + Shorts/Reels 자동화 파이프라인
> **Mode:** ad-hoc (MVP)
> **Depends on:** Phase 16 (Writer prompt v2 완료), 기존 파이프라인 인프라
> **Created:** 2026-07-11

---

## 1. 목표 (Goal)

기존 뉴스 파이프라인(키워드 → D1 뉴스 → Pitch → Writer Format D → Threads 발행)을 확장하여, **Instagram Carousel(캐러셀) + Shorts/Reels(쇼츠/릴스)** 자동 생성/발행 파이프라인 구축.

- **비용**: $0/월 (무료 티어만 사용)
- **기존 파이프라인 재사용**: Format D(펀치 브리핑 5카드) → 캐러셀/쇼츠 변환
- **자동화 레벨**: 완전 자동 (HTML→PNG→FFmpeg→Graph API→스케줄링)

---

## 2. 요구사항 (Requirements)

| ID | 요구사항 | 상세 |
|----|----------|------|
| REQ-01 | **Instagram Carousel 생성** | 5~7장 슬라이드, 1080×1350(4:5), Ken Burns + 전환 + 자막 바운스 |
| REQ-02 | **Shorts/Reels 생성** | 9:16(1080×1920), 15~30초, Ken Burns + 자막 바운스 + 비트 싱크 컷 |
| REQ-03 | **콘텐츠 변환** | 기존 Format D(펀치 브리핑 5카드) → 캐러셀 5~7장 / Shorts 15~30초 대본 자동 변환 |
| REQ-04 | **자동 발행** | Instagram Graph API + Meta Business Suite 연동 (캐러셀/릴스 각각) |
| REQ-05 | **스케줄링** | 일 1회(캐러셀 오전 8시) + 일 1회(Shorts 오후 7시), 한국 시간 |
| REQ-06 | **무료 운영** | edge-tts + FFmpeg + Meta Graph API (무료 티어) |
| REQ-07 | **기존 파이프라인 연동** | Format D(펀치 브리핑 5카드) → 캐러셀/쇼츠 변환 파이프라인 추가 |

---

## 3. 기술 스택 (무료만 사용)

| 레이어 | 도구 | 비용 |
|--------|------|------|
| **이미지 생성** | Playwright + HTML/CSS 템플릿 | 무료 |
| **비디오 렌더링** | FFmpeg (zoompan + xfade + drawtext) | 무료 |
| **TTS + 자막** | edge-tts (MS Edge 무료) + SRT 생성 | 무료 |
| **자막 애니메이션** | FFmpeg drawtext + `sin(2*PI*t/0.5)` 바운스 | 무료 |
| **비디오 인코딩** | FFmpeg `-hwaccel videotoolbox` (macOS) / `nvenc` (Linux) | 무료 |
| **Instagram 발행** | Meta Graph API (Carousel/Reels Container) | 무료 (비즈니스 계정) |
| **스케줄러** | launchd (macOS) / systemd (Linux) | 무료 |

---

## 3. 콘텐츠 변환 매핑 (Format D → Carousel/Shorts)

| Format D 카드 | Carousel 슬라이드 | Shorts/Reels 씬 |
|---------------|-------------------|-----------------|
| **Card 1: Hook** | Slide 1: Hook (큰 숫자 + 한 줄) | Scene 1: Hook (0~2초) |
| **Card 2: Conflict A** | Slide 2: Conflict (문제 제기) | Scene 2: Conflict (2~5초) |
| **Card 3: Twist** | Slide 3: Twist (반전/핵심 인사이트) | Scene 3: Twist (5~10초) |
| **Card 4: Expansion** | Slide 4: Expansion (데이터/맥락) | Scene 4: Expansion (10~15초) |
| **Card 5: CTA/질문** | Slide 5: CTA + 질문 | Scene 5: CTA + 질문 (15~20초) |
| **Card 6: Link** | Slide 6~7: 링크 + 브랜딩 | Scene 6: 브랜딩 + 팔로우 유도 |

---

## 4. 적용할 기법 (이미 검증 완료)

| 기법 | FFmpeg 구현 | 효과 |
|------|-------------|------|
| **Ken Burns** | `zoompan=z='min(zoom+0.0015,1.12)':d=75:s=1080x1920:fps=30` | 정적→시네마틱 줌/팬 |
| **전환 다양화** | `xfade=transition=wipeleft\|circlecrop\|dissolve:smoothleft` | 지루함 방지 |
| **자막 바운스** | `drawtext` + `fontsize='56*(0.7+0.3*sin(2*PI*t/0.5))'` | 단어 강조 |
| **비트 싱크** | `aselect='gt(volume,0.5)'`로 오디오 피크에서 컷 | 리듬감 |
| **글리치 전환** | `tblend=all_mode=average:all_expr='if(gte(random(0),0.5),A,B)'` | 임팩트 |
| **자막 바운스** | `fontsize='56*(0.7+0.3*sin(2*PI*t/0.5))'` | 단어 강조 |

---

## 4. 성공 기준 (Definition of Done)

| 기준 | 검증 방법 |
|------|-----------|
| **Carousel 생성** | 5~7장 PNG(1080×1350) 생성 → FFmpeg로 MP4 변환 시 1080×1350, 30fps |
| **Shorts/Reels 생성** | 1080×1920, 15~30초, 30fps, H.264, AAC |
| **자막 품질** | SRT 타임코드 정확도 ±0.5초, 바운스 애니메이션 부드러움 |
| **Ken Burns** | 1.0x → 1.12x 줌 + 팬, 2.5초/슬라이드, 부드러운 ease-in-out |
| **전환 효과** | 4가지(wipeleft, circlecrop, dissolve, smoothleft) 랜덤 적용 |
| **Instagram 발행** | Graph API로 Carousel/Reels Container 생성 → Publish 성공 |
| **스케줄링** | launchd로 일 2회 자동 실행, 로그 기록 |
| **비용** | 월 $0 (무료 티어만 사용) |

---

## 5. 파일 구조 (예정)

```
/Users/twinssn/Projects/aikorea24/
├── instagram-carousel-output/      # HTML 템플릿 + PNG 캡처
├── instagram-reel-output/          # FFmpeg 출력 MP4
├── cards/                          # PNG 슬라이드 이미지
├── tts/                            # edge-tts MP3 + SRT
├── scripts/
│   ├── build_reel.py               # FFmpeg 단일 패스 생성기
│   ├── html_to_png.mjs             # Playwright 캡처
│   ├── instagram_publish.py        # Graph API 발행
│   └── scheduler.py                # launchd 연동 스케줄러
├── filter.txt                      # FFmpeg 필터그래프
└── template.html                   # Carousel/Reels HTML 템플릿
```

---

## 6. 위험 요소 및 완화

| 위험 | 확률 | 영향도 | 완화 방안 |
|------|------|--------|-----------|
| **glitch 전환 미지원** | 낮음 | 중간 | `circlecrop`/`dissolve`로 대체 |
| **Ken Burns 서브픽셀 흔들림** | 중간 | 중간 | `temp_scale_factor=4` 업스케일 기법 적용 |
| **자막 싱크 밀림** | 낮음 | 높음 | SRT 타임코드 ±0.5초 검증 필수 |
| **Graph API 레이트 리밋** | 낮음 | 중간 | 일 2회로 제한, 지수 백오프 |
| **비디오 용량 초과** | 낮음 | 중간 | CRF 20~23, 10초 미만 유지 |
| **TTS 품질 불만** | 중간 | 낮음 | edge-tts → ElevenLabs/Coqui 선택적 업그레이드 |

---

## 7. 다음 단계

1. **RESEARCH.md** 작성 (이미 완료된 조사 내용 정리)
2. **PLAN.md** 생성 (구체적 작업 분해)
3. **검증 루프** → PLAN.md 확정
4. **실행** (Phase 17-01 ~ 17-07 순차 실행)