---
date: 2026-08-12
type: fix
status: resolved
---

# 홈피 및 이메일에서 영어 설명 제거

## What
aikorea24.kr 첫화면 홈피 브리핑과 이메일 발송에 영어 뉴스 설명(description/news_desc)이 그대로 노출되어 있던 문제를 해결.

## Why
- 홈피 브리핑 컴포넌트(`BriefingSection.astro`)가 `item.description`(영어 원문)을 그대로 렌더링
- 이메일 템플릿(`send-email.ts`)도 `news_desc`를 본문에 포함하고 있었음
- 개별 브리핑 페이지(`[date].astro`)만 수정되어 있었으나, 홈피와 이메일은 미수정 상태

## Files changed
- `src/components/home/BriefingSection.astro` — `item.description` 렌더링 제거
- `src/pages/api/briefing/send-email.ts` — `news_desc` 제거, 빈 코멘트/비한국어 코멘트 발송 차단 추가
- `src/pages/briefing/[date].astro` — 이전 세션에서 이미 수정됨 (재확인)

## How
1. 홈피 브리핑 컴포넌트에서 description 렌더링 라인 제거
2. 이메일 템플릿에서 news_desc 쿼리 및 HTML 생성 제거
3. 안전장치 추가: 코멘트가 비어있거나 한글이 없으면 이메일 발송을 400 오류로 차단

## Verification
- `npm run build` 통과
- `scripts/deploy.sh`로 배포
- curl/Playwright로 프로덕션 응답 확인: 영어 description 없음
- 안전장치 로직 단위 테스트 7개 케이스 모두 통과
