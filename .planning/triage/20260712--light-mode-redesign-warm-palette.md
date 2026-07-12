---
date: 2026-07-12
type: fix
status: resolved
---

# 라이트 모드 리디자인 — 웜 페이퍼 팔레트

## What
라이트 모드의 차가운 회색 계열(#ffffff, #f8fafc, #475569)을 따뜻한 종이톤 팔레트로 전면 교체. 모든 페이지와 컴포넌트에 일관된 웜톤 디자인 시스템 적용.

## Why
- 기존 라이트 모드는 차갑고 밋밋한 Tailwind 기본 회색톤 사용
- `bg-gray-100`과 `bg-white`의 대비가 약해 섹션 구분이 모호함
- 가독성과 사이트 아이덴티티 모두 개선 필요

## Files changed
- `src/styles/global.css` — CSS 변수 전면 교체 + Tailwind utility 오버라이드 15개
- `src/layouts/Layout.astro` — 헤더/모바일메뉴/서치모달 bg를 CSS 변수로 전환
- `src/pages/index.astro` — wrapper `bg-white` → `var(--bg-primary)`
- `src/pages/news.astro` — 동일
- `src/pages/global.astro` — 동일
- `src/pages/subscribe.astro` — 동일
- `src/pages/aikeep24/index.astro` — 동일
- `src/pages/network/index.astro` — 동일

## How
1. CSS 변수 11개 재정의: `--bg-primary: #FBF9F6`, `--bg-secondary: #F2EFEA`, `--text-primary: #1A1714` 등
2. `html:not(.dark)` 선택자로 Tailwind 유틸리티 클래스 오버라이드 (58개 Astro 파일 수정 불필요)
3. `bg-gray-50/100/200` → `var(--bg-secondary/tertiary)`, `text-gray-900/700/600/500` → warm 계열
4. `hover:bg-gray-100/200`, `border-gray-200/300` 등 interactive 상태도 오버라이드
5. `prose` 라이트 모드 색상도 웜 팔레트에 맞춤
6. 6개 페이지 래퍼에서 `bg-white` 제거하고 CSS 변수 사용

## Key palette

| Role | Before | After |
|------|--------|-------|
| bg-primary | `#ffffff` | `#FBF9F6` |
| bg-secondary | `#f8fafc` | `#F2EFEA` |
| text-primary | `#0f172a` | `#1A1714` |
| text-secondary | `#475569` | `#6B6258` |
| border | `#e2e8f0` | `#DDD7D0` |

## Verification
- 모든 페이지 래퍼 `bg-white` 패턴 제거 확인 (grep 0 match)
- LSP diagnostics — biome 미설치로 skip (기존 상태)
- `git diff --stat`: 8 files changed, 76 insertions(+), 39 deletions(-)
- 라이트/다크 테마 토글 정상 동작 확인 (`:not(.dark)` 조건부 오버라이드)
