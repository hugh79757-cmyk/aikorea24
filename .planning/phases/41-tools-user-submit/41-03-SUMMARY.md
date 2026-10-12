# Phase 41 Plan 03: Phase 2 MVP (Completion + List Merge + Detail Fallback) Summary

**One-liner:** 제출 즉시 완료화면(MAKER 미리보기+카페 퍼널) → 목록 최상단 MAKER 노출 → D1 slug 상세 렌더, E2E 실증됨

## Frontmatter

- phase: 41-tools-user-submit
- plan: 03
- status: complete
- tasks: 3/3
- commits: 0727f9e4, 467c8ebf, 68f5b4d3
- plan_head_before: 47ffc4126bbb721fd71d687e0907462f909b40dd
- duration: ~20min
- files: src/pages/tools/submit.astro, src/pages/tools/index.astro, src/pages/tools/[id].astro (3 modified, markdown untouched)

## 생성/수정 파일

- [수정] `src/pages/tools/submit.astro` — 201 성공 시 폼→완료화면 교체: index 카드 클래스 재사용 미리보기(gradient bar/name/desc/category/price) + MAKER 배지 verbatim + 카페 공유문구 복사버튼(clipboard: 이름+URL+한줄설명+`https://cafe.naver.com/gptdohye 에서 더 많은 AI 활용법을 확인하세요`) + 카페 바로가기(target _blank, locked URL) + `done-link` → /tools/{slug}. 401/400/네트워크 에러 경로 41-02 그대로 유지.
- [수정] `src/pages/tools/index.astro` — `prerender` 제거(SSR), D1 tool_submissions 전행 조회(try/catch fail-soft 빈배열, 200 유지) → D1 created_at DESC 상단 + md 기존 order順 합성. D1→카드 매핑(price/koreanSupport/difficulty/tags/useCases/order:-1/updated:created_at일자). MAKER 배지 verbatim 2곳(그리드 카드 + 최신등록 섹션). data-* 필터 attrs 동일 템플릿이라 D1 자동 포함, PAGE_SIZE 페이지네이션 합성 리스트 기준.
- [수정] `src/pages/tools/[id].astro` — `prerender` 제거(SSR, getStaticPaths는 pre-render 목록용 유지). props→md 재조회→D1 slug 조회 3단 fallback, miss → 404 Response. D1 렌더: MAKER verbatim, detail_markdown else description 단락 렌더(Astro 보간 escape, 줄바꿈 보존), meta(category/price/url/korean/difficulty), tasks ALL_TASKS 필터, useCases/tags/tasks/relatedPost 빈 섹션 기존 조건식으로 자동숨김, 리뷰 섹션+CTA+뱃지 D1 숨김(스크립트 loadReviewData 스킵). 투표 버튼은 slug TEXT 키 그대로 동작.

## 동작확인

- [검증됨] `npm run build` 3회 통과 (Task별 각 1회, `[build] Complete!`).
- [검증됨] MAKER 클래스 3파일 verbatim 일치 — 근거: plan 지정 `bg-purple-100 text-purple-700 ... dark:border-purple-500/20` 문자열 submit/index/[id] 전수 grep 일치.
- [검증됨] 목록 E2E (local D1 테스트행 `phase41-e2e-test` 삽입 후 astro dev :4321): `/tools/` 200 + `MAKER` 1건 + `E2E 테스트툴` 노출 + 첫 카드가 D1행. 근거: curl 3종.
- [검증됨] 상세 E2E: `/tools/phase41-e2e-test/` 200 + MAKER + 본문 첫줄 렌더 + useCases 칩 + `id="reviews-section"` 0건(숨김). md `/tools/chatgpt-work/` 200 + reviews div 1건(유지). 미지정 slug 404. 근거: curl http_code 200/200/404 + 본문 grep.
- [검증됨] D1 카드 필터 attrs — 근거: `data-cat="코딩·개발"` curl 확인.
- [검증됨] 비로그인 `/tools/submit/` → 302 `/auth/consent` (패턴 A 유지). 근거: curl redirect_url.
- [검증됨] md 도구·collector untouched — 근거: `git diff HEAD -- src/content/tools/ scripts/tools_collector.py` 빈 출력.
- [검증됨] 테스트 잔해 전량 정리 — 근거: local `SELECT count(*)` 0건 + 임시 users 테이블 DROP.
- [부분검증] 브라우저 실조작 미실시 (완료화면 복사버튼 clipboard + Step 플로우는 코드리뷰 수준). 제한: 실세션 제출→완료 클릭테스트 없음 (41-02와 동일 사유: astro dev 세션 미주입, pages-dev 우회는 41-02에서 이미 검증된 POST 경로라 중복 생략).

## 미해결이슈

1. `.wrangler/state/...sqlite` tracked 파일이 로컬 D1 검증으로 수정됨 — 커밋하지 않고 둠 (41-02와 동일, 로컬 dev 상태).
2. astro dev에 SESSION_SECRET 미주입이라 로그인 제출 E2E는 dev에서 불가 — 41-02가 pages-dev로 POST 201 검증済, 본 plan은 GET계 + 빌드로 커버.

## 다음메모 (Phase 3 입력)

- Phase 2 MVP 완성: 제출→목록 MAKER→상세 접근 실증됨. Phase 3(R2 업로드, 로고/스크린샷, /my/tools + PUT/DELETE)는 범위 미확정 — 리뷰 후 계획.
- D1 slug가 md와 겹치면 md 우선으로 가려짐 — submit API dedup 로직이 방지 중, 현행 유지.
- D1 리뷰는 posts INTEGER FK 구조상 불가 — 리뷰 섹션 숨김 유지, Phase 3에서 별도 설계 필요시 논의.

## Deviations

None — plan executed exactly as written.

## Self-Check: PASSED

- 근거: 3개 파일 전부 `git log` 커밋 존재(0727f9e4/467c8ebf/68f5b4d3), `git diff --diff-filter=D` 빈 출력(삭제 없음), SUMMARY 본 파일 작성됨.
