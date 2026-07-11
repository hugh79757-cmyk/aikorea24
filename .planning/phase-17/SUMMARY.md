# Phase 17 — SUMMARY.md

> **Phase:** 17 — Instagram Carousel + Shorts/Reels 자동화 파이프라인
> **Mode:** ad-hoc (MVP)
> **Status:** Planned
> **Created:** 2026-07-11

---

## 요약

기존 뉴스 파이프라인(Format D → Threads)을 확장하여 **Instagram Carousel(캐러셀) + Shorts/Reels(쇼츠/릴스)** 자동 생성/발행 파이프라인 구축.

- **비용**: $0/월 (무료 티어만)
- **기존 파이프라인 재사용**: Format D(펀치 브리핑 5카드) → 캐러셀/쇼츠 변환
- **자동화 레벨**: 완전 자동 (HTML→PNG→FFmpeg→Graph API→스케줄링)

---

## 구현 작업 분해 (7개 서브태스크)

| Task ID | 작업 | 핵심 내용 | 의존성 |
|---------|------|-----------|--------|
| 17-01 | **콘텐츠 변환기** | Format D(5카드) → Carousel 5~7장 / Shorts 15~30초 대본 변환 | Phase 16 완료 |
| 17-02 | **이미지 생성기** | HTML 템플릿 → Playwright 캡처 (1080×1350 / 1080×1920 PNG) | 17-01 |
| 17-03 | **비디오 렌더러** | FFmpeg: Ken Burns(zoompan) + xfade(전환) + drawtext(자막 바운스) | 17-02 |
| 17-04 | **TTS + 자막** | edge-tts(무료) + SRT 생성 + FFmpeg drawtext 바운스 애니메이션 | 17-03 |
| 17-05 | **Instagram 발행** | Graph API: Carousel Container → Publish / Reels Container → Publish | 17-04 |
| 17-06 | **스케줄러/오케스트레이터** | launchd 연동: 일 2회(캐러셀 08:00, Shorts 19:00) 자동 실행 | 17-05 |
| 17-07 | **테스트/검증** | 3일 드라이런 → 품질 체크 → 정식 운영 전환 | 17-06 |

---

## 핵심 기술 스택 (무료만)

| 레이어 | 도구 | 비용 |
|--------|------|------|
| 이미지 생성 | Playwright + HTML/CSS 템플릿 | 무료 |
| 비디오 렌더링 | FFmpeg (zoompan + xfade + drawtext) | 무료 |
| TTS + 자막 | edge-tts (MS Edge 무료) + SRT | 무료 |
| 자막 애니메이션 | FFmpeg drawtext + `sin(2*PI*t/0.5)` 바운스 | 무료 |
| 비디오 인코딩 | FFmpeg `-hwaccel videotoolbox` (macOS) | 무료 |
| Instagram 발행 | Meta Graph API (Carousel/Reels Container) | 무료 (비즈니스 계정) |
| 스케줄러 | launchd (macOS) / systemd (Linux) | 무료 |

---

## 적용 기법 (이미 검증 완료)

| 기법 | FFmpeg 구현 | 효과 |
|------|-------------|------|
| **Ken Burns** | `zoompan=z='min(zoom+0.0015,1.12)':d=75:s=1080x1920:fps=30` | 정적→시네마틱 줌/팬 |
| **전환 다양화** | `xfade=transition=wipeleft\|circlecrop\|dissolve\|smoothleft` | 지루함 방지 |
| **자막 바운스** | `drawtext` + `fontsize='56*(0.7+0.3*sin(2*PI*t/0.5))'` | 단어 강조 |
| **비트 싱크** | `aselect='gt(volume,0.5)'`로 오디오 피크에서 컷 | 리듬감 |
| **글리치 전환** | `tblend=all_mode=average:all_expr='if(gte(random(0),0.5),A,B)'` | 임팩트 |

---

## 검증 기준 (Definition of Done)

| 기준 | 검증 방법 |
|------|-----------|
| **Carousel 생성** | 5~7장 PNG(1080×1350) → FFmpeg MP4 변환 시 1080×1350, 30fps |
| **Shorts/Reels 생성** | 1080×1920, 15~30초, 30fps, H.264, AAC |
| **자막 품질** | SRT 타임코드 정확도 ±0.5초, 바운스 애니메이션 부드러움 |
| **Ken Burns** | 1.0x → 1.12x 줌 + 팬, 2.5초/슬라이드, 부드러운 ease-in-out |
| **전환 효과** | 4가지(wipeleft, circlecrop, dissolve, smoothleft) 랜덤 적용 |
| **Instagram 발행** | Graph API로 Carousel/Reels Container 생성 → Publish 성공 |
| **스케줄링** | launchd로 일 2회 자동 실행, 로그 기록 |
| **비용** | 월 $0 (무료 티어만 사용) |

---

## 위험 요소 및 완화

| 위험 | 확률 | 영향도 | 완화 방안 |
|------|------|--------|-----------|
| **glitch 전환 미지원** | 낮음 | 중간 | `circlecrop`/`dissolve`로 대체 |
| **Ken Burns 서브픽셀 흔들림** | 중간 | 중간 | `temp_scale_factor=4` 업스케일 기법 적용 |
| **자막 싱크 밀림** | 낮음 | 높음 | SRT 타임코드 ±0.5초 검증 필수 |
| **Graph API 레이트 리밋** | 낮음 | 중간 | 일 2회로 제한, 지수 백오프 |
| **비디오 용량 초과** | 낮음 | 중간 | CRF 20~23, 10초 미만 유지 |
| **TTS 품질 불만** | 중간 | 낮음 | edge-tts → ElevenLabs/Coqui 선택적 업그레이드 |

---

## 다음 단계

1. ✅ CONTEXT.md, RESEARCH.md, PLAN.md 작성 완료
2. 🔄 **다음**: `gsd-plan-checker`로 검증 → 승인 시 실행 착수
3. 실행 순서: 17-01 → 17-02 → 17-03 → 17-04 → 17-05 → 17-06 → 17-07
4. 예상 소요: ~10일 (2주)

---

> **참고**: Phase 17은 별도 마일스톤(v2.0 강좌 시스템 Phase 17)과 별개로, **SNS 콘텐츠 배포 채널 확장**을 위한 별도 ad-hoc Phase로 관리됩니다.