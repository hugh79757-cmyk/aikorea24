# Phase 17 — RESEARCH.md

> **Phase:** 17 — Instagram Carousel + Shorts/Reels 자동화 파이프라인
> **Mode:** ad-hoc (MVP)
> **Research Date:** 2026-07-11

---

## 1. 무료 TTS 옵션 조사 결과

### 완전 무료 (로컬/오픈소스)
| 모델 | 한국어 | 속도 | 품질 | 라이선스 | 비고 |
|------|--------|------|------|----------|------|
| **edge-tts** | ✅ | 매우 빠름 | 자연스러움 | MIT | **현재 사용 중**, MS Edge 엔진 |
| **eSpeak NG** | ✅ | 초고속 | 로봇음 | GPL | 초경량, 임베디드용 |
| **Piper (piper1-gpl)** | ✅ | 빠름 | 좋음 | MIT | 라즈파이/엣지 최적화 |
| **Coqui TTS (XTTS v2)** | ✅ | 중간 | 매우 높음 | CPML | 화자 복제 가능 |
| **Coqui TTS (VITS)** | ✅ | 중간 | 높음 | CPML | 다국어 지원 |
| **Bark (Suno)** | ✅ | 느림 | 표현력 최상 | MIT | 웃음/음악/효과음 생성 |
| **StyleTTS2** | ✅ | 중간 | 인간급 | MIT | 스타일 전이 가능 |
| **VITS** | ✅ | 빠름 | 높음 | MIT | 파인튜닝 베이스라인 |

### 무료 티어 API
| 서비스 | 무료 제공량 | 한국어 | 품질 | 특징 |
|--------|------------|--------|------|------|
| **Microsoft Edge (edge-tts)** | **무제한** | ✅ 최상 | 자연스러움 | **현재 사용 중**, API 키 불필요 |
| **ElevenLabs** | 10k chars/월 | ✅ | **최상** | 감정 제어, 화자 복제 |
| **Google Cloud TTS** | 100만 chars/월 | ✅ | WaveNet 최상 | Neural2, Studio 음성 |
| **AWS Polly** | 500만 chars/월 (12개월) | ✅ | Neural 우수 | 실시간 스트리밍 지원 |
| **Azure Speech** | 50만 chars/월 | ✅ | Neural 최상 | 커스텀 음성 가능 |
| **Coqui Cloud** | 크레딧 기반 | ✅ | 높음 | 오픈소스 모델 호스팅 |

**결론**: **edge-tts(무제한 무료) + Piper/Coqui 로컬 백업** 조합이 최적. 한국어 자연스러움 + 비용 $0.

---

## 2. AI 이미지/비디오 생성 도구 조사

### 이미지 생성 (배경/썸네일/슬라이드용)
| 도구 | 한국어 프롬프트 | 품질 | 자동화 | 라이선스 | 비용 |
|------|----------------|------|--------|----------|------|
| **Flux.1 (Schnell/Dev)** | ✅ | **최상** | API/로컬 | Apache 2.0 | 로컬 무료 |
| **SDXL / SD 1.5** | ✅ | 상 | API/로컬 | OpenRAIL | 로컬 무료 |
| **SD 3** | ✅ | 최상 | API/로컬 | OpenRAIL | 로컬 무료 |
| **Pony Diffusion** | ✅ | 상 | 로컬 | OpenRAIL | 로컬 무료 |
| **Ideogram 2.0** | ✅ (텍스트 렌더링 최강) | 최상 | API | 비공개 | 유료 API |
| **DALL-E 3** | ✅ | 최상 | API | 비공개 | $0.04/장 |
| **Midjourney v6.1** | ✅ | 최상 | Discord/Web | 비공개 | $10/월 |
| **Recraft v3** | ✅ | 상 | API | 비공개 | 무료 티어 있음 |

**추천**: **Flux.1 (로컬) + Ideogram 2.0 (텍스트 포함 이미지 시 API)** 조합

### 비디오 생성 (Text-to-Video / Image-to-Video)
| 모델 | 유형 | 길이 | 품질 | 자동화 | 한국어 | 비용 |
|------|------|------|------|--------|--------|------|
| **MiniMax Hailuo 2.3** | T2V/I2V | 6초 | 상 | API 쉬움 | 무난 | **$0.02~0.05/초** |
| **Luma Dream Machine 1.6** | T2V/I2V | 5초 | 상 | API 제공 | 무난 | $0.30/생성 |
| **Kling 1.6** | T2V/I2V | 10초 | 최상 | API 복잡 | 좋음 | 비공개 베타 |
| **Runway Gen-3 Alpha** | T2V/I2V | 10초 | 최상 | API | 무난 | **$0.50+/초** |
| **Pika 1.5** | T2V/I2V | 5초 | 중상 | API | 무난 | $0.10~0.30 |
| **Stable Video Diffusion** | I2V | 4초 | 중 | 로컬/로컬 | - | **무료 (로컬)** |
| **Runway Gen-4** | T2V/I2V | 10초 | 최상 | API | 무난 | 비쌈 |

**무료/로컬 추천**: **Stable Video Diffusion (로컬) + FFmpeg Ken Burns** 조합
- 비용 $0, 품질은 Ken Burns + 전환 효과로 커버 가능

---

## 3. Reels/Shorts 전환/이펙트 기법 (FFmpeg)

### FFmpeg xfade 전환 효과 (지원되는 것들)
| 전환 타입 | 코드 | 설명 |
|----------|------|------|
| `fade` | 0 | 기본 페이드 |
| `wipeleft` / `wiperight` | 1/2 | 좌/우 와이프 |
| `wipeup` / `wipedown` | 3/4 | 상/하 와이프 |
| `slideleft` / `slideright` | 5/6 | 좌/우 슬라이드 |
| `slideup` / `slidedown` | 7/8 | 상/하 슬라이드 |
| `circlecrop` | 9 | 원형 크롭 |
| `dissolve` | 25 | 디졸브 |
| `pixelize` | 26 | 픽셀화 |
| `radial` | 14 | 방사형 |
| `smoothleft`/`smoothright` | 15/16 | 스무스 |
| `diagtl`/`diagtr`/`diagbl`/`diagbr` | 27~30 | 대각선 |
| `coverleft`/`coverright` | 50/51 | 커버 |
| `revealleft`/`revealright` | 54/55 | 리빌 |

**미지원**: `glitch`, `whip`, `zoom` 등 (커스텀 필터로 구현 필요)

### Ken Burns (zoompan) 최적화
```bash
# 서브픽셀 부드러움을 위한 업스케일 기법
# 1080x1920 출력 → 4x 업스케일(4320x7680) → zoompan → 다운스케일
zoompan=z='min(zoom+0.0015,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=75:s=1080x1920:fps=30
```

### 자막 바운스 (drawtext + easing)
```bash
# sine-out easing으로 팝 효과
fontsize='56*(0.7+0.3*sin(2*PI*t/0.5))'
# 팝-바운스 (오버슈트)
fontsize='56*(0.7+0.4*sin(2*PI*t/0.5))'  # 110% 오버슈트 후 정착
```

### 비트 싱크 컷 (오디오 피크 감지)
```bash
# librosa로 onset detection → 컷 포인트 리스트 생성 → FFmpeg select 필터
# select='gte(t,cut1)*lt(t,cut2)+gte(t,cut3)*lt(t,cut4)...'
```

---

## 4. Instagram Graph API 발행 플로우

### Carousel 발행 플로우
```
1. 각 슬라이드 이미지 → Media Container 생성 (is_carousel_item=true)
2. Carousel Parent Container 생성 (media_type=CAROUSEL, children=슬라이드 IDs)
3. Parent Container Publish
```

### Reels 발행 플로우
```
1. 비디오 파일 → Media Container 생성 (media_type=REELS)
2. Publish
```

### 필수 권한/설정
- **Instagram Business 계정** + **Meta Business Suite** 연결
- **필수 권한**: `instagram_content_publish`, `instagram_manage_insights`, `pages_read_engagement`
- **Access Token**: Long-lived (60일) → 주기적 갱신 필요

---

## 5. 비용 시뮬레이션 (월 100개 생성 기준)

| 구성 | 월 비용 | 비고 |
|------|---------|------|
| **완전 무료 (로컬 + FFmpeg + edge-tts)** | **$0** | GPU만 있으면 됨 |
| **Flux 로컬 + MiniMax API (비디오만)** | ~$20~50 | 비디오만 API |
| **Flux + Ideogram + MiniMax + ElevenLabs** | $100~300 | 풀 프리미엄 |
| **Runway Gen-4 + ElevenLabs + DALL-E 3** | $500+ | 풀 프리미엄 상용 |

**결론**: **완전 무료 로컬 파이프라인(FFmpeg + edge-tts + Flux 로컬) 구축 → 필요시 API 선택적 추가**가 최적.

---

## 6. 결론 및 추천 스택

### **MVP 스택 (비용 $0)**
```
HTML 템플릿 → Playwright → PNG(1080x1350/1920)
      ↓
edge-tts → MP3 + SRT
      ↓
FFmpeg (zoompan + xfade + drawtext + subtitles) → MP4
      ↓
Meta Graph API → Carousel/Reels 발행
      ↓
launchd (macOS) / systemd (Linux) → 일 2회 자동 실행
```

### **단계적 업그레이드 경로**
1. **1단계 (현재)**: FFmpeg Ken Burns + edge-tts + 기존 HTML 템플릿 → **완료**
2. **2단계**: Flux/SDXL 로컬로 배경 이미지 생성 자동화
3. **3단계**: MiniMax/Luma API로 히어로 컷만 AI 비디오 생성
4. **4단계**: ElevenLabs/Coqui XTTS로 TTS 품질 업그레이드

---

## 7. 참고 링크

- [FFmpeg xfade 문서](https://ffmpeg.org/ffmpeg-filters.html#xfade)
- [FFmpeg zoompan 문서](https://ffmpeg.org/ffmpeg-filters.html#zoompan)
- [FFmpeg drawtext 문서](https://ffmpeg.org/ffmpeg-filters.html#drawtext)
- [Instagram Graph API - Carousel](https://developers.facebook.com/docs/instagram-api/guides/carousel)
- [Instagram Graph API - Reels](https://developers.facebook.com/docs/instagram-api/guides/reels)
- [edge-tts GitHub](https://github.com/rany2/edge-tts)
- [Flux.1 GitHub](https://github.com/black-forest-labs/flux)
- [MiniMax API 문서](https://api.minimax.io/)
- [Luma Dream Machine API](https://docs.lumalabs.ai/)