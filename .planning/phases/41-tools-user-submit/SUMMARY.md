# SUMMARY — Phase 41 plan set (/tools 사용자 직접 등록, 1차 초벌)

Planned: 2026-09-23. 3 plans, tracer-ordered, junior executes in order, senior gate after 41-01.

- 41-01-PLAN.md (wave 1, Phase 0, read-only, no code): D1 remote dump (users/posts/tool_votes/tool_submissions), file reads ([id]/index/submit/vote/reviews/tasks/env/auth/middleware/callbacks/config/wrangler), login-pattern lock (A for page, B for API). Output: 41-01-REPORT.md. Senior gate.
- 41-02-PLAN.md (wave 2, Phase 1 backbone, depends 41-01): sql/001_tool_submissions.sql (user_id per report, expect INTEGER per RESEARCH §1.3) + local/remote apply; POST /api/tools/submit (vote.ts pattern, 401/400/slug kebab + md+D1 dup + numeric suffix per RESEARCH §5.1+§7, URL check, description 200자, D1 INSERT); submit.astro SSR (drop prerender, guard A → /auth/consent, 2-step form 5필수/7선택+tasks≤5, 7+기타 categories, fetch POST). Done = form→D1.
- 41-03-PLAN.md (wave 3, Phase 2 MVP, depends 41-02): completion view (preview+MAKER, cafe template copy, https://cafe.naver.com/gptdohye, /tools/{slug}); index D1 merge (status 무관, MAKER purple exact classes defined in plan, newest top); [id] D1 fallback (md first, detail_markdown else description, hide missing, reviews hidden). Done = submit→list→detail.

Notes: RESEARCH has no §10 — slug rule cited as §5.1+§7. MAKER exact classes defined in 41-03 Task 2 (RESEARCH left placeholder). Phase 3 deferred, untouched. Markdown tools + collector untouched all plans. Report format per CONTEXT each plan.
