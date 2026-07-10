# Phase 18 — 체류 퍼널 재설계 (Retention Funnel Redesign)

## Current State Assessment

### Fact Corrections (from external report)
| Report Claim | Actual State |
|---|---|
| Email: "준비 중", 발송 불확실 | ✅ **정상 가동**, 주 2회 발송 (브리핑 + 툴 소개) |
| 브리핑 + 툴 소개: 미확인 | ✅ 뉴스 브리핑 + AI 툴 소개 이메일 발송 중 |
| 리드 자석: 없음 | ✅ "7일 강좌"로 해결 완료 (MVP-1~3) |
| 웰컴 시퀀스: 부재 | ✅ "7일 강좌가 웰컴 시퀀스 역할"로 대체 |
| 어필리에이트: 미확인 | ✅ 의사결정: 적용 안 함 (제외) |

### Remaining Leaks (this phase)
1. ⚠️ **블로그 본문 내 구독 CTA 부재** — 350+개 글, 읽고 나면 다음 액션 없음
2. ⚠️ **메인 첫 인상 = 뉴스 브리핑** — Threads/신규 방문자 이탈, about 타겟과 불일치
3. ⚠️ **84개 블로그 네트워크 유입 미활용** — 푸터 링크만으로 약함
4. ⚠️ **자산 간 고립** (/tools, /glossary, /chronicle) — 각 페이지가 "끝"

### Completed Foundation (MVP-1~3)
- ✅ 강좌 신청 → enrollment → 강의 글 접근 (D1 + API + 게이트)
- ✅ 커뮤니티 visibility 게이트 + 어드민 + 편집 UI
- ✅ 강의/일반 게이트 분기 + enrollment 검증

## Funnel Redesign: 5-Stage Retention Funnel

### Core Principle
Every page must offer a "next natural step." Currently most pages are dead ends.

| Stage | Old Goal | New Goal |
|-------|----------|----------|
| TOFU | Traffic acquisition | Prevent immediate bounce |
| MOFU | Subscription conversion | Drive return visits |
| BOFU | Purchase/monetization | Post-purchase community settling |
| Retention | Repurchase | Daily → Weekly → Community habituation |

## Priority Ranking (by retention impact)

| # | Task | Impact | Effort | ROI |
|---|------|--------|--------|-----|
| 1 | **Main page hero reorder** — BriefingSection ↓, HeroSection ↑ | All new visitors' first 10s | 1-2h | ★★★★★ |
| 2 | **Blog post-body CTA** — 3 CTA buttons at end of every post | 350+ posts × all readers | 3-5h | ★★★★ |
| 3 | **Lesson → Community CTA** — "Submit mission" at lesson bottom | Course graduates → community | 2-3h | ★★★ |
| 4 | **Cross-asset navigation** — tools/glossary/chronicle interlinks | Site-wide circulation | 1-2d | ★★★ |
| 5 | **Sub-project/network backflow** — banners on 84 external blogs | External traffic → main | 1-2d | ★★★ |
| 6 | **Comment notification email** — reply-triggered emails | Community re-engagement | 1-2d | ★★ |

## This Session Scope (Priorities 1 + 2)

### Priority 1: Main Page Hero Reorder
**Problem**: `BriefingSection` renders before `HeroSection` in `index.astro`. First impression = news briefing, not the value proposition.

**Solution**: Swap order — `HeroSection` first, `BriefingSection` second. Hero copy: "AI, 처음이세요? 7일면 충분합니다" + 강좌 신청 CTA.

### Priority 2: Blog Post-Body CTA
**Problem**: 350+ blog posts have no CTA after content. Reader finishes → leaves.

**Solution**: Insert 3 CTA buttons between content end and "함께 읽으면 좋은 글":
1. "7일 강좌 무료 신청" → `/courses/7day-starter/` (BOFU)
2. "매일 아침 AI 브리핑 받기" → email subscription (MOFU)
3. "이 글의 핵심 용어 알아보기" → glossary (site dwell)

## Architecture Decisions

- **Blog CTA**: Static HTML component inserted in `[...id].astro` template. Single file change covers 350+ posts (prerendered). No DB queries needed.
- **Hero reorder**: Simply swap two `<Component />` lines in `index.astro`. No CSS changes needed.
- **Glossary link**: Use `/glossary/` as generic entry point (tag-level matching is deferred to Priority 4).

## Files to Modify
- `src/pages/index.astro` — HeroSection/BriefingSection order swap
- `src/pages/blog/[...id].astro` — Add post-body CTA component after `</div>` closing prose-body

## Success Criteria
1. Main page hero copy visible before briefing section (screenshot)
2. Blog post body shows 3 CTA buttons below content, above related posts
3. All links resolve (강좌 → `/courses/7day-starter/`, 브리핑 → email subscribe, 용어 → `/glossary/`)
4. Build + deploy succeeds
