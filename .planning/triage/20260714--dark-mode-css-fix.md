---
date: 2026-07-14
type: fix
status: resolved
---

# 다크모드 CSS 변수 미로드 — `global.css` import 누락

## What
다크모드 토글(일출/일몰 아이콘)을 눌러도 배경색/글자색이 전혀 바뀌지 않음. Tailwind `dark:` variant로 적용된 헤더/카드는 정상 동작했지만, 페이지 전체 `body` 배경과 기본 글자색은 항상 검정(#0A0E1A)/회색이었음.

## Why
**근본 원인**: `src/styles/global.css`에 정의된 CSS 커스텀 프로퍼티(`--bg-primary`, `--text-primary` 등)가 브라우저에 전혀 로드되지 않음.
- `global.css`를 import하는 코드가 **어디에도 없었음**
- `@astrojs/tailwind` integration이 `applyBaseStyles: true`(기본값)로 `@tailwind base`를 자동 주입 → duplicate 방지를 위해 명시적 import를 생략한 것으로 추정되나, CSS 변수가 포함된 `@layer base` 블록 자체가 누락됨
- Playwright 확인 결과: `--bg-primary` = `""` (빈 문자열), body background 투명

## Files changed
- `src/layouts/Layout.astro` — `import '../styles/global.css'` 추가 (line 2)
- `astro.config.mjs` — `tailwind()` → `tailwind({ applyBaseStyles: false })` (line 14)
- `src/styles/global.css` — `@tailwind` directives 유지 (revert, 기존과 동일)

## How
1. `Layout.astro`에 global.css import 추가 — 모든 페이지가 Layout을 거치므로 한 번의 import로 전역 적용
2. `applyBaseStyles: false` 설정 — `global.css`가 직접 `@tailwind base/components/utilities`를 처리하도록 변경 (integration이 자동 주입하지 않음). 이 설정이 없으면 `@layer base` 구문이 `@tailwind base` 없이 사용되어 PostCSS 오류 발생.

## Verification
Playwright로 라이브 배포 사이트에서 light/dark 토글 전환 검증:

| 상태 | bodyBg | bodyColor | --bg-primary |
|------|--------|-----------|-------------|
| 다크모드 | rgb(10,14,26) 🟢 | rgb(226,232,240) 🟢 | #0A0E1A |
| 라이트모드 | rgb(255,255,255) 🟢 | rgb(15,23,42) 🟢 | #ffffff |

추가로 동일 세션에서 발견된 text visibility 이슈 7건도 함께 수정됨 (별도 triage: community/review h1, blog CTA headings, star rating, date spans, glass utility 등).
