# PLAN — Phase 26: Mobile Readability Follow-up

## Goal
Fix 3 design QA issues from 7day-starter.astro 모바일 가독성 개선:
1. **명도비 일관성**: text-gray-300/md:text-gray-400 브레이크포인트 분기 제거 → `text-gray-300` 통일 (13.1:1)
2. **gray-600 접근성 위반**: `text-gray-600` → `text-gray-400` (2.5:1 → 7.6:1)
3. **커리큘럼 카드 line-height**: 텍스트 줄바꿈 시 `leading-relaxed` 적용

## Research Findings

| 색상 | 배경 #0A0E1A 대비 | WCAG |
|------|-------------------|------|
| gray-600 (#4B5563) | **2.5:1** ❌ | AA도 실패 |
| gray-500 (#6B7280) | 4.0:1 ⚠️ | AA 본문 실패 |
| gray-400 (#9CA3AF) | 7.6:1 ✅ | AAA |
| gray-300 (#D1D5DB) | 13.1:1 ✅ | AAA |

- `-mx-4` 풀블리드: 모든 섹션이 `px-4`로 통일되어 있음 → 정상
- 커리큘럼 카드: `text-sm` (14px)에 line-height 미지정 → Tailwind 기본값 ~1.43

## Tasks

- [ ] 1. Contrast unification — replace `text-gray-300 md:text-gray-400` → `text-gray-300`
- [ ] 2. gray-600 → gray-400 for privacy notice (`text-xs text-gray-600` → `text-xs text-gray-400`)
- [ ] 3. Add `leading-relaxed` to curriculum card descriptions
- [ ] 4. Add `leading-snug` to curriculum card titles
- [ ] 5. Verify: build pass
- [ ] 6. Commit: "fix(courses): 일관된 명도비 + line-height + 접근성 개선"
