# CONTEXT — Phase 41: /tools 사용자 직접 등록 기능 구현 (1차 초벌)

## Goal
사용자가 /tools에 AI 툴을 직접 등록 → D1 저장 → 즉시 게시 → MAKER 배지 노출 → 네이버 카페 유도.
기존 마크다운 기반 도구(src/content/tools/*.md)와 자동수집(tools_collector.py)은 절대 건드리지 않음. 사용자 등록은 D1에만.

## Scope (junior execution order, senior gate each phase)
- Phase 0 (precondition, read-only): D1 users 실제 스키마 확정 (schema.sql kakao형 vs callback/google.ts google_id+role 불일치 해소), 미확인 파일 읽기 ([id].astro, index.astro, vote.ts, reviews.ts, tasks.ts), vote/reviews D1 테이블 추출, 로그인 감지 패턴 + env.d.ts. → 보고 후 senior 리뷰 대기.
- Phase 1 (backbone): sql/00X_tool_submissions.sql (user_id 타입은 Phase 0 결과에 맞춤), POST /api/tools/submit (로그인 필수 401, 필수필드 400, slug 자동생성+중복시 숫자, URL 검증, description 200자, D1 INSERT), submit.astro 개편 (prerender 제거/SSR, 비로그인시 로그인 유도, 2스텝 폼: Step1 필수 5필드 / Step2 선택 7필드+tasks 최대5, fetch POST, Tailwind 다크모드 유지, 반응형). 완료기준: 폼→D1 저장.
- Phase 2 (MVP 완성): 완료화면 (카드 미리보기+MAKER, 카페 템플릿 복사, 카페 바로가기 https://cafe.naver.com/gptdohye, 내 도구 페이지 이동), index.astro에 D1 도구 합성 (status 무관 즉시표시, MAKER 배지 purple 스타일 지정, 상단 최신순), [id].astro D1 fallback (md 우선, 없으면 slug 조회, detail_markdown 렌더 else description, 없는 섹션 숨김). 완료기준: 제출→목록 MAKER 노출→상세 접근.
- Phase 3 (deferred, Phase 2 리뷰 후 범위확정): R2 업로드 API, 로고/스크린샷 필드, /my/tools + PUT/DELETE. 지금 계획하지 않음.

## Locked decisions
- 마크다운 파일 수정 금지. D1 tool_submissions만 사용.
- API: vote.ts/reviews.ts 패턴, D1 접근 (locals as any).runtime?.env?.DB 패턴.
- Astro: 기존 submit/index Tailwind 클래스 패턴 유지.
- 에러처리 필수 (DB 실패, 세션 만료 → 사용자 친화 메시지).
- 카페 URL: https://cafe.naver.com/gptdohye (게시판은 별도 생성 예정, 지금은 메인 URL).
- MAKER 배지 HTML (Phase 2-2 지정 클래스 그대로).
- 각 페이즈 완료 보고 양식: 생성/수정 파일, 동작확인, 미해결이슈, 다음메모.

## Known risks (from prior codebase investigation)
- POST /api/tools/submit 미구현 (404 상태) — 신규 작성 필요.
- users 스키마 불일치 — Phase 0에서 실측 후 user_id 타입 결정.
- profile/dashboard/my 페이지 없음, functions/ 없음.
- 카테고리: index.astro 8개 하드코딩 vs submit.astro 동적 카테고리 — Phase 1에서 8개 대분류 고정 사용.
- TASKS 73개(src/config/tasks.ts).
- 업로드 API 없음, R2 바인딩만 존재 — Phase 3로 연기.
- [id].astro 렌더링/vote·reviews 스키마/로그인패턴은 Phase 0에서 확정.

## Out of scope
- 승인 프로세스 (1차는 즉시 게시).
- Phase 3 이미지/마이페이지 (리뷰 후).
- ROADMAP 기존 Phase 1-40 회귀 없음.
