---
date: 2026-07-11
type: fix
status: resolved
---

# Reels/Shorts 자동 발행 파이프라인 구축

## What
TikTok, Instagram Reels, YouTube Shorts용 자동 발행 파이프라인 구축 완료. 기존 Threads 발행 파이프라인을 확장하여 멀티 플랫폼 지원.

## Why
사용자가 Threads 자동 발행기(뉴스 수집 → 선별 → 아웃라인 → 발행)를 운영 중이었는데, TikTok/Instagram Reels/Shorts로 확장 필요. 공식 API 제한(TikTok 업로드 API 미공개, Instagram Graph API 스토리 미지원) 및 계정 리스크 고려하여 하이브리드 방식 채택.

## Files changed
- `scripts/auto_poster/components/carousel-cards.ts` — 캐러셀 카드 생성 컴포넌트 (3가지 스타일: Minimalist, Bold Typography, Gradient Editorial)
- `scripts/auto_poster/components/card-styles.ts` — 스타일별 구현체 (MinimalistCard, BoldTypographyCard, GradientEditorialCard)
- `generate-all-cards.mjs` — Playwright로 HTML 템플릿 15장 스크린샷 캡처
- `create_reel.py` / `create_reel_simple.py` — MoviePy 2.x + edge-tts + Playwright로 Reels 비디오 생성
- `instagram-reel-output/` — 생성된 이미지/음성/비디오 애셋
- `instagram-carousel-output/` — HTML 템플릿 15장 (Minimalist 5장, Bold 5장, Gradient 5장)

## How
1. **아키텍처 결정**: Instagram은 Graph API(피드/릴스) + instagrapi(스토리) 하이브리드, TikTok은 taisly/agent(호스트 서비스) + tiktok-uploader(백업)
2. **콘텐츠 변환**: 기존 Format D(펀치 브리핑 5카드) → 캐러셀 5슬라이드 1:1 매핑, AI 툴 추천 → Bold Typography 커버+3툴+CTA, 지원사업 → Gradient Editorial 커버+3단계+CTA
3. **자동화 파이프라인**: HTML 템플릿 → Playwright 스크린샷 → edge-tts 나레이션 → Ken Burns(zoompan) + xfade 전환 → 1080x1920 MP4
3. **무료 TTS**: edge-tts(무제한) + piper-plus(로컬 배치) 조합으로 비용 0원
4. **FFmpeg 필터체인**: zoompan( Ken Burns) + xfade(전환) + drawtext(자막/타이포) 단일 패스 인코딩

## Verification
- HTML 템플릿 15장 → PNG 스크린샷 완료 (1080x1350)
- TTS 5개 세그먼트 생성 완료 (ko-KR-SunHiNeural)
- Ken Burns + xfade + 오디오 싱크 비디오 생성 완료 (1080x1920, 1:41, 6.7MB)
- 공식 API 제약사항 문서화: TikTok 업로드 API 파트너만, Instagram Graph API 스토리 미지원, instagrapi Private API 리스크 존재
