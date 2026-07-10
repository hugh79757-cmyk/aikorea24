# Phase 18 — 체류 퍼널 재설계

## 변경 사항 요약

### Task 1: 메인 페이지 히어로 순서 변경
- `src/pages/index.astro`: `HeroSection`이 `BriefingSection`보다 먼저 렌더링되도록 순서 변경
- 신규 방문자의 첫 인상이 뉴스 브리핑 → "AI 시작하기" 히어로로 변경
- Hero copy 확인 및 필요시 수정 (7일 강좌 CTA 연계)

### Task 2: 블로그 본문 하단 CTA 3종 추가
- `src/pages/blog/[...id].astro`: 본문 아래, "함께 읽으면 좋은 글" 위에 3개 CTA 카드 추가
  - 📚 **7일 강좌 무료 신청** → `/courses/7day-starter/`
  - 📬 **매일 아침 AI 브리핑** → `/subscribe/`
  - 📖 **AI 용어 알아보기** → `/glossary/`
- 350+개 prerendered 블로그 글에 일괄 적용 (템플릿 1회 수정)

## 영향 범위
- **수정 파일**: 최대 3개 (`index.astro`, `[...id].astro`, `HeroSection.astro`)
- **신규 파일**: 없음 (inline HTML/Tailwind)
- **DB 변경**: 없음
- **의존성 변경**: 없음

## 검증 결과
- (Pending — Plan 확인 후 실행)
