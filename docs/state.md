## 2026-10-14 13:12 AIK24-EMDASH-05 완료 — EmDash CMS git 저장소화 + /posts 페이지네이션 → SSOT/프로젝트/aikorea24/지시서/2026-10-14-1312-AIK24-EMDASH-05-완료보고.md (완료 — verify 요청)

### 한 일
- 작업 1 [PRODUCTION CODE 밖 / 저장소]: `~/projects2/aikorea24emdash` git 저장소화. `.gitignore` 6줄 → 커밋 `5aa38bd`(83개 파일 추적, node_modules 0) → GitHub private `hugh79757-cmyk/aikorea24-emdash` 생성·푸시.
- 작업 2 [PRODUCTION CODE]: `src/pages/posts/index.astro` 단독 — `?page=N` 페이지네이션(12편/페이지), 카운트 쿼리, 404 판정, 페이지네이션 UI, canonical, 그리고 canonical 절대 URL 수정.
- 커밋 `36f9aa5`, `origin/main` 푸시 완료.

### 결과
- [검증됨] 완료기준 1: `/posts`·`?page=1` → 200 / 12편 / `전체 1481편 · 1/124페이지`.
- [검증됨] 완료기준 2: `?page=2` → 200 / 12편, **page1∩page2 카드 href 교집합 0건**.
- [검증됨] 완료기준 3: `?page=124` → 200 / **5편** (123×12+5=1481 일치).
- [검증됨] 완료기준 4: `?page=125` → **404** / 0편.
- [검증됨] 완료기준 5: `?page=abc`·`?page=0` → 200 / 12편 / 1/124페이지(page=1 동일).
- [검증됨] 완료기준 6: `<nav class="pagination" aria-label="페이지네이션">` 렌더. page=1 → 「« 이전」이 `<span class="pg disabled" aria-disabled="true">`, page=124 → 「다음 »」동일. 현재 페이지 `<span class="pg current" aria-current="page">`. 간격 생략은 `<span class="pg-gap">…`.
- [검증됨] 완료기준 7: `/posts` **5회 연속 200**.
- [검증됨] 완료기준 8: `npm run typecheck` 6 errors — 전부 기존 파일(`og-image.ts` 3, `sanitize.ts` 1, `src/pages/index.astro` 2). `posts/index.astro` 신규 0건.
- [검증됨] 지시서 §7 canonical: `/posts` → `https://emdash.aikorea24.kr/posts`, `?page=2` → `…/posts?page=2`, `?page=124` → `…?page=124`. `robots="noindex, follow"` 유지.
- [검증됨] 배포 Version ID: 1차 `75124e5a-7c5f-49ca-be13-178939797363`, canonical 수정 후 **`361bacea-a1dc-4eb8-bf20-d0d17d6ea41c`**.

### 지시서 대비 차이 / 버그
- canonical 이 첫 배포에서 **미출력** → 원인 확정: `emdash/dist/page/index.mjs` `resolvePageMetadata()` 의 `if (!isSafeHref(c.href)) continue;` 가 **상대 href 를 link contribution 에서 버린다**. `robots` 는 meta 라 살아남었던 것. → 절대 URL 로 변경해 해소.
- 카드 "N분 소요" 복원 안 함(지시서 범위 밖 준수).

### 잔존 위험
1. **목록 12편 + 124페이지 구성** — UI 진입은 `/?page=N` 이며 카드에서 다른 페이지로 가는 링크는 없다(뒤로/앞으로만). 1,481편 전체 도달 가능하나 탐색성 약함.
2. `/posts` 는 `robots="noindex, follow"` 이므로 검색 노출 대상이 아님(기존 정책 유지).
3. `/category/{term}` 은 여전히 404(Astro 카테고리 페이지 삭제 후 대체 없음).
4. 콘솔 엣지 캐시 규칙 미적용 — 에이전트 토큰에 `Zone Rulesets:Edit` 스코프 없음([검증불가], 대표님 직접).
5. typecheck 6건은 기존부터 있던 문제(이번 작업 무관).

### 다음 행동
- 대표님: 콘솔 캐시 규칙 생성(`/tmp/cache_ruleset.json`), 카테고리 페이지 대체안 결정.

