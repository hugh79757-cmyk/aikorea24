# Phase 18 — 체류 퍼널 재설계 (Retention Funnel Redesign)

> **Mode**: vertical (MVP slice: Priority 1 + 2)
> **Depends on**: Phase 17 완료 (강좌 MVP-1~3, community gate, enrollment)
> **기존 ROADMAP 정의 변경**: "MVP-2 커뮤니티 게이트" → "체류 퍼널 재설계" (게이트는 이미 완료)

---

## Goal

모든 신규 방문자의 **첫 10초**와 **블로그 글 읽은 후**에 "다음 액션"을 만들어 체류 시간을 늘린다.

---

## Task Breakdown

### Task 1: 메인 페이지 히어로 순서 변경 + 카피 개선

| 항목 | 내용 |
|------|------|
| **파일** | `src/pages/index.astro` (순서 변경) + `src/components/home/HeroSection.astro` (카피 개선) |
| **변경** | (1) `BriefingSection`과 `HeroSection` 렌더링 순서 스왑 (2) 히어로 카피에 강좌 CTA 통합 |
| **작업량** | 2개 파일, ~10 line |
| **위험도** | 낮음 |

#### 1-a: 순서 변경
- 현재 (line 59-60):
  ```
  <BriefingSection briefing={briefing} items={briefingItems} />
  <HeroSection />
  ```
- 변경:
  ```
  <HeroSection />
  <BriefingSection briefing={briefing} items={briefingItems} />
  ```

#### 1-b: Hero 카피 개선
- 현재 헤드라인: "AI, 누구나 쓸 수 있습니다"
- 현재 CTA: "블로그 보기" / "더 알아보기"
- 변경안:
  - 헤드라인 유지 또는 "AI, 처음이세요? 7일면 충분합니다" 톤으로 강화
  - CTA 버튼 3개로 확장: "7일 강좌 시작하기" (emerald, 1순위) + "블로그 보기" (blue, 2순위) + "더 알아보기" (outline, 3순위)
  - "7일 강좌 시작하기" → `/courses/7day-starter/`

#### HeroSection.astro 변경안 상세
```astro
<div class="flex flex-col sm:flex-row justify-center gap-4">
  <a href="/courses/7day-starter/"
     class="group bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold px-8 py-4 rounded-xl hover:shadow-[0_0_40px_rgba(16,185,129,0.4)] transition-all duration-500 hover:-translate-y-1">
    7일 강좌 시작하기 <span class="inline-block ml-1 group-hover:translate-x-1 transition-transform">→</span>
  </a>
  <a href="/blog"
     class="group bg-gradient-to-r from-blue-500 to-purple-600 text-white font-semibold px-8 py-4 rounded-xl hover:shadow-[0_0_40px_rgba(99,102,241,0.4)] transition-all duration-500 hover:-translate-y-1">
    블로그 보기 <span class="inline-block ml-1 group-hover:translate-x-1 transition-transform">→</span>
  </a>
  <a href="/about"
     class="bg-white/[0.07] backdrop-blur-md border border-gray-300 dark:border-white/[0.15] font-semibold px-8 py-4 rounded-xl hover:bg-white/[0.12] transition-all duration-500 hover:-translate-y-1 text-gray-700 dark:text-white">
    더 알아보기
  </a>
</div>
```

### Task 2: 블로그 본문 하단 CTA 3종 추가

| 항목 | 내용 |
|------|------|
| **파일** | `src/pages/blog/[...id].astro` |
| **변경** | 본문(`prose-body`) div 종료 후, "함께 읽으면 좋은 글" 섹션 전에 3개 CTA 카드 삽입 |
| **작업량** | ~30 lines HTML/Tailwind |
| **위험도** | 낮음 (정적 템플릿, 350+개 prerendered 글에 일괄 적용) |

#### CTA 디자인

각 CTA는 rounded-xl 카드로, 3열 그리드 (모바일 1열):

```
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-10 mb-6">
  <!-- CTA 1: 강좌 -->
  <div class="p-5 rounded-xl bg-gradient-to-br from-emerald-900/30 to-teal-900/20 border border-emerald-700/30 text-center">
    <div class="text-2xl mb-2">📚</div>
    <h3 class="text-sm font-bold text-white mb-1">7일 강좌 무료 신청</h3>
    <p class="text-xs text-gray-400 mb-3">AI, 어디서부터 시작할지 모르겠다면?</p>
    <a href="/courses/7day-starter/" class="inline-block bg-gradient-to-r from-emerald-600 to-teal-600 text-white px-4 py-2 rounded-lg text-xs font-semibold hover:from-emerald-500 hover:to-teal-500 transition-all">
      강좌 신청하기 →
    </a>
  </div>

  <!-- CTA 2: 브리핑 구독 -->
  <div class="p-5 rounded-xl bg-gradient-to-br from-blue-900/30 to-purple-900/20 border border-blue-700/30 text-center">
    <div class="text-2xl mb-2">📬</div>
    <h3 class="text-sm font-bold text-white mb-1">매일 아침 AI 브리핑</h3>
    <p class="text-xs text-gray-400 mb-3">선별된 AI 뉴스를 이메일로 받아보세요</p>
    <a href="/subscribe/" class="inline-block bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-2 rounded-lg text-xs font-semibold hover:from-blue-500 hover:to-purple-500 transition-all">
      구독하기 →
    </a>
  </div>

  <!-- CTA 3: 용어사전 -->
  <div class="p-5 rounded-xl bg-gradient-to-br from-amber-900/30 to-orange-900/20 border border-amber-700/30 text-center">
    <div class="text-2xl mb-2">📖</div>
    <h3 class="text-sm font-bold text-white mb-1">AI 용어 알아보기</h3>
    <p class="text-xs text-gray-400 mb-3">이 글에서 나온 핵심 용어를 설명합니다</p>
    <a href="/glossary/" class="inline-block bg-gradient-to-r from-amber-600 to-orange-600 text-white px-4 py-2 rounded-lg text-xs font-semibold hover:from-amber-500 hover:to-orange-500 transition-all">
      용어사전 가기 →
    </a>
  </div>
</div>
```

### Task 3: `/subscribe/` 독립 페이지 생성

| 항목 | 내용 |
|------|------|
| **파일** | `src/pages/subscribe.astro` (신규) |
| **변경** | 메인 페이지 `SubscribeBanner.astro`의 구독 폼을 독립 페이지로 분리 |
| **작업량** | ~40 lines Astro (기존 SubscribeBanner 재사용) |
| **위험도** | 낮음 |

#### 상세
- `src/pages/subscribe.astro` 신규 생성
- `SubscribeBanner.astro` 인라인 폼 + 스크립트를 그대로 가져와서 독립 페이지 구성
- 메인 페이지의 `SubscribeBanner.astro`는 유지 (중복 제거하지 않음)
- `SubscribeBanner.astro`를 import해서 재사용하는 방안도 가능하나, 독립 페이지에 맞는 헤더/푸터/레이아웃 구성 필요
- 권장: `src/layouts/Layout.astro`를 import하고, body에 `SubscribeBanner` 컴포넌트 배치 + 부가 설명 텍스트 추가

##### SubscribeBanner 재사용 시 예상 구조
```astro
---
import Layout from '../layouts/Layout.astro';
import SubscribeBanner from '../components/home/SubscribeBanner.astro';
---
<Layout title="AI 브리핑 구독 - AI코리아24" description="매일 아침 선별된 AI 뉴스를 이메일로 받아보세요">
  <main class="min-h-screen bg-white dark:bg-[#0A0E1A] py-20 px-4">
    <div class="max-w-2xl mx-auto text-center mb-8">
      <h1 class="text-3xl font-bold mb-4">📬 AI 브리핑 구독</h1>
      <p class="text-gray-500 dark:text-gray-400">
        매일 아침, 직접 선별한 AI 뉴스와 인사이트를 이메일로 보내드립니다.<br/>
        스팸은 없습니다. 언제든 구독을 취소할 수 있습니다.
      </p>
    </div>
    <SubscribeBanner />
  </main>
</Layout>
```

#### 알아둘 점
- `SubscribeBanner.astro`의 `<script>` 블록은 `id="top-subscribe"` / `id="top-email"`를 참조
- 독립 페이지에서도 같은 ID를 사용하므로 정상 동작 (단, 한 페이지에 두 개의 SubscribeBanner가 있으면 ID 중복 주의 — 현재는 메인 페이지만 있으므로 문제 없음)
- `trailingSlash: 'always'` 설정 — `/subscribe/` 접속 시 정상 라우팅

---

## Dependency Graph

```
Task 1 (index swap + hero copy) ──┐
Task 3 (/subscribe/ page) ────────┼── (independent) ──▶ Build + Deploy
Task 2 (blog CTA) ────────────────┘
```

모든 태스크는 독립적 → 병렬 실행 가능.

---

## Rollback Plan

| 변경 | 롤백 |
|------|------|
| `index.astro` line swap | 원래 순서로 되돌리기 (git checkout) |
| `HeroSection.astro` CTA 변경 | 원래 CTA 블록으로 복원 |
| `subscribe.astro` 신규 생성 | 파일 삭제 |
| `[...id].astro` CTA 추가 | `<div class="grid ...">` 블록 제거 |

---

## Verification

1. **Local dev**: `npm run dev` → 메인 페이지 히어로가 브리핑보다 위에 오는지 확인
2. **Local dev**: 아무 블로그 글 (e.g., `/blog/2026-07-01-vibe-코딩-...`) 열어서 CTA 3개가 본문 아래, 관련글 위에 표시되는지 확인
3. **Local dev**: `/subscribe/` 접속 → 구독 폼 정상 표시 확인
4. **Build**: `npm run build` 에러 없이 통과
5. **Links**: `/courses/7day-starter/`, `/subscribe/`, `/glossary/` 각각 정상 연결
6. **Deploy**: Cloudflare Pages 배포 성공
