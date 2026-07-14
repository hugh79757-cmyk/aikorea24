---
date: 2026-07-14
type: fix
status: resolved
---

# 라이트모드 전환 시 텍스트 가시성 버그 수정

## What
라이트모드로 전환 시 `text-white` 하드코딩으로 인해 제목/헤딩이 흰 배경에 묻히는 문제 및 다크모드에서 `text-gray-600`이 너무 어두워 가독성이 떨어지는 문제 수정.

## Why
- 일부 heading 요소가 `text-white`로 하드코딩 → 라이트모드 흰 배경에서 텍스트가 안 보임
- 일부 보조 텍스트(date, visibility, star rating)가 `text-gray-600`만 있고 `dark:text-gray-400` 누락 → 다크모드에서 어두운 배경에 묻힘
- `.glass` utility 클래스가 CSS 변수가 아닌 하드코딩 `rgba(30,41,59,0.7)` 사용 → 라이트모드에서도 다크 배경 유지

## Files changed
- `src/pages/community/review.astro:30` — h1: `text-white` → `text-gray-900 dark:text-white`
- `src/pages/community/review.astro:54,71,84` — star rating: `text-gray-600` → +`dark:text-gray-400`
- `src/pages/blog/[...id].astro:218,228,238` — CTA h3: `text-white` → `text-gray-900 dark:text-white`
- `src/pages/news.astro:33` — date span: `text-gray-600` → +`dark:text-gray-400`
- `src/pages/global.astro:51` — date span: `text-gray-600` → +`dark:text-gray-400`
- `src/pages/community/index.astro:149` — visibility span: `text-gray-600` → +`dark:text-gray-400`
- `src/styles/global.css` — `.glass` utility: hardcoded → CSS vars (`var(--card-bg)` / `var(--card-border)`)

## How
1. 블로그 페이지(`/blog/`)는 이미 `text-gray-900 dark:text-white`로 **올바르게** 작성되어 있었음. 사용자 보고는 브라우저 캐시 or 다른 페이지 혼동으로 추정.
2. 커뮤니티 리뷰 페이지: h1 `text-white` → `text-gray-900 dark:text-white`
3. CTA 카드: `text-white` → `text-gray-900 dark:text-white` (반투명 배경 위)
4. 보조 텍스트 4개: `text-gray-600` → `text-gray-600 dark:text-gray-400`
5. `.glass` utility: CSS 변수 기반으로 전환하여 테마 대응

## Verification
Playwright로 dev 서버(`127.0.0.1:4321`)에서 light/dark computed style 직접 검증:
- 블로그 페이지: breadcrumb/h1 light=`#111827` / dark=`#ffffff` — 양쪽 정상 가시성
- 뉴스 페이지: date span light=`#4B5563`(gray-600) / dark=`#9CA3AF`(gray-400) — 양쪽 정상 가시성
- 스크린샷 캡처 완료, dev 서버 종료
