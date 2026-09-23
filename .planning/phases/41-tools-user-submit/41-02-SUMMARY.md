# Phase 41 Plan 02: Phase 1 Backbone (DDL + Submit API + SSR Form) Summary

**One-liner:** 로그인 유저 2스텝 폼 제출 → D1 tool_submissions 저장, 401/400 게이트 + slug 중복회피 라이브 검증됨

## Frontmatter

- phase: 41-tools-user-submit
- plan: 02
- status: complete
- tasks: 3/3
- commits: 9a86841b, b9886714, 47ffc412
- duration: ~25min
- files: sql/001_tool_submissions.sql (new), src/pages/api/tools/submit.ts (new), src/pages/tools/submit.astro (rewrite)

## 생성/수정 파일

- [생성] `sql/001_tool_submissions.sql` — tool_submissions DDL. user_id INTEGER NOT NULL REFERENCES users(id) (41-01-REPORT §1.5 실측 verdict). slug UNIQUE, status DEFAULT 'published' (즉시게시), idx slug/user. posts/tool_votes/users DDL untouched.
- [생성] `src/pages/api/tools/submit.ts` (153L) — vote.ts 패턴 + posts/index.ts 인증. 401 JSON만(리다이렉트 없음), 필수4종 400, description 200자 초과 400 (무음절단 없음), URL http(s) 검증, 카테고리 7+기타 화이트리스트, tasks TASKS 키 + 최대5 검증, slug kebab + md/D1 양쪽 중복시 숫자접미사, 201 {ok,slug}.
- [수정] `src/pages/tools/submit.astro` (55L→237L) — prerender 제거(SSR), 패턴 A 서버가드 → /auth/consent, 2스텝 fetch POST 폼 (Step1 필수5: 이름/URL/카테고리/설명200자카운터/가격, Step2 선택: 한국어지원/난이도/활용사례/태그/연관작업73키최대5/상세설명), 401 메시지 표시만, 성공 시 최소 완료훅(slug+링크). Tailwind 다크모드/반응형 유지.

## 동작확인

- [검증됨] D1 remote 테이블 존재 — 근거: `wrangler d1 execute --remote "SELECT name ... tool_submissions"` → 1행 반환.
- [검증됨] D1 local 테이블 DDL — 근거: sqlite_master 덤프에 user_id INTEGER + slug UNIQUE 확인.
- [검증됨] `npm run build` 통과 — 근거: `[build] Complete!` (server 15.81s).
- [검증됨] 401 무쿠키 `{"error":"로그인이 필요합니다."}` — 근거: pages-dev curl code:401.
- [검증됨] 401 쓰레기세션 `유효하지 않은 세션` — 근거: astro dev curl code:401.
- [검증됨] 400 필수누락/200자초과/불량tasks키(`문서-작성` RESEARCH §2.5 트랩 그대로 적중) — 근거: pages-dev curl 400 3종.
- [검증됨] 201 정상제출 slug `phase41-test-tool` + 중복제출 `phase41-test-tool-2` — 근거: pages-dev curl + D1 local SELECT 2행 확인.
- [검증됨] 비로그인 /tools/submit/ → 302 /auth/consent — 근거: curl redirect_url.
- [검증됨] md 도구·collector untouched — 근거: `git diff HEAD -- src/content/tools/ scripts/tools_collector.py` 빈 출력.
- [부분검증] 브라우저 실조작 미실시 (curl + 빌드로 대체, 폼 JS는 코드리뷰 수준). 제한: Step1→Step2 네비게이션 클릭테스트 없음.

## 미해결이슈

1. astro dev 로컬 D1에 users 테이블 없음 (`no such table: users`) — dev에서 로그인 플로우 E2E 불가. pages-dev(local D1 + .dev.vars SECRET)로 우회 검증함. 프로덕션 영향 없음.
2. `.wrangler/state/...sqlite` tracked 파일이 로컬 apply로 수정됨 — 커밋하지 않고 worktree에 둠 (로컬 dev 상태, remote 적용은 별도 완료).
3. astro dev runtime은 SESSION_SECRET 미주입 (미들웨어 warn 경로) — dev에서 세션 검증 불가, pages-dev로 우회. 프로덕션(Pages dashboard 변수) 영향 없음.

## 다음메모 (41-03 입력)

- backbone 완료, form→D1 저장 실증됨. 테스트 잔해 전량 정리됨 (제출 2행·테스트유저·임시users테이블·.dev.vars 삭제, tool_submissions 빈 테이블 유지 local/remote).
- 41-03 소유: 완료화면 전체본, index.astro D1 합성 + MAKER 배지, [id].astro D1 fallback.
- slug 네임스페이스 md 우선 공유 — D1 slug가 md와 겹치면 가려지므로 dedup 로직 유지할 것.

## Deviations

None — plan executed exactly as written. (테스트 스캐폴드 생성/삭제는 검증용 임시조치, 최종 diff 없음.)
