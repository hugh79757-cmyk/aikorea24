# RESEARCH — Phase 41: /tools 사용자 직접 등록 기능 (1차 초벌)

**Researched:** 2026-09-23
**Scope:** Phase 0+1+2 only (Phase 3 deferred — R2 업로드, /my/tools, PUT/DELETE 제외)
**Locked constraints (from CONTEXT.md):** 마크다운 수정 금지·D1 tool_submissions만 사용 / API는 vote.ts·reviews.ts 패턴 + `(locals as any).runtime?.env?.DB` / 기존 Tailwind 클래스 유지 / 카페 URL https://cafe.naver.com/gptdohye / MAKER 배지 Phase 2-2 지정 클래스 / 에러처리 필수

## 1. D1 users 실제 스키마 (Phase 0 핵심)

### 1.1 발견된 DDL 전체

**A. `schema.sql:2-9` — users 베이스 (유일한 users CREATE TABLE):**
```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  google_id TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
```
`posts.user_id INTEGER NOT NULL REFERENCES users(id)` (`schema.sql:14`), persona 테이블들도 `user_id INTEGER` (`sql/persona_migration.sql:9,27,38`).

**B. `sql/persona_migration.sql:1-4` — 카카오 확장:**
```sql
ALTER TABLE users ADD COLUMN kakao_id TEXT;
ALTER TABLE users ADD COLUMN provider TEXT DEFAULT 'google';
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_kakao ON users(kakao_id) WHERE kakao_id IS NOT NULL;
```

**C. `scripts/migrations/20260710_add_admin_role.sql:2` — role 추가:**
```sql
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'member';
```

**D. membership 컬럼 — 마이그레이션 파일 없음 (리스크):**
- `src/lib/auth.ts:56-58`의 `getUserMembership()`이 `SELECT membership, membership_expires, purchased_posts FROM users` 조회, `SOP.md:173-175`에 컬럼 정의 언급(`membership TEXT DEFAULT 'free'`, `membership_expires TEXT`, `purchased_posts TEXT DEFAULT '[]'`).
- 그러나 `scripts/migrations/`에는 3개 파일만 존재(`20260630_add_impact_score_columns.sql`, `20260710_add_course_system.sql`, `20260710_add_admin_role.sql`) — membership ADD COLUMN 파일 없음. D1 원격에 out-of-band 적용된 것으로 추정. **Phase 1에서 tool_submissions는 membership 컬럼에 의존하지 않으므로 블로커 아님.**

### 1.2 callback/google.ts INSERT·SELECT vs 스키마 매칭 판정

`src/pages/api/auth/callback/google.ts:38-44`:
```ts
await db.prepare(
  `INSERT OR IGNORE INTO users (google_id, email, name, avatar) VALUES (?, ?, ?, ?)`
).bind(user.id, user.email, user.name, user.picture).run();

const dbUser = await db.prepare(
  `SELECT id, name, email, avatar, role FROM users WHERE google_id = ?`
).bind(user.id).first();
```
- INSERT 4컬럼 → `schema.sql` 베이스와 정확히 일치 (kakao_id/provider/role은 DEFAULT·NULL 허용이므로 INSERT 생략 가능).
- SELECT의 `role` → C번 마이그레이션(`20260710_add_admin_role.sql`)과 일치. **불일치 없음 — CONTEXT의 "kakao형 vs google_id+role 불일치" 우려는 해소됨.** schema.sql이 kakao형이 아니라 google 베이스이며, kakao 확장은 persona_migration으로 별도 존재.
- 참고 `src/pages/api/auth/callback/kakao.ts:44-66`: `SELECT id, name, email, avatar FROM users WHERE kakao_id = ?` (role 미조회 — 카카오 로그인 세션에는 role 없음, `getSessionUser`의 role은 optional이므로 동작), 신규 INSERT는 `(kakao_id, google_id, email, name, avatar, provider)`에 `google_id=''` 바인드 (`kakao.ts:60-61`).

### 1.3 Phase 1 결론: user_id 타입

**`user_id INTEGER NOT NULL REFERENCES users(id)` 사용.** 근거: posts·persona_posts·persona_likes 전부 INTEGER FK 패턴이며, google.ts SELECT가 `id`(INTEGER)를 세션에 담음. (vote.ts는 예외적으로 `user_email TEXT` 키 사용 — 3절 참조. tool_submissions는 posts 패턴을 따를 것.)

## 2. 파일 전수 읽기 결과

### 2.1 `src/pages/tools/[id].astro` (416줄, `export const prerender = true;` :2)
- 정적 경로: `getStaticPaths()`가 `getCollection('tools')` 전량 매핑 (`:7-13`). **Phase 2 D1 fallback 추가 시 `prerender` 유지 + D1 조회는 클라이언트 fetch 또는 `getStaticPaths` 외 분기로 처리해야 함** (현재 구조는 빌드 시점 컬렉션만 커버).
- 렌더: `const { Content } = await render(tool)` (`:18`) — 마크다운 바디 렌더 경로. D1 도구에 `detail_markdown` 있으면 동일 `<Content/>` 대신 원시 마크다운 렌더 필요 (Phase 2에서 astro `marked` 또는 동등 처리 — 기존 의존성 확인 필요).
- `toolIndex = tool.data.index || 0` (`:37`) — 리뷰/투표 조인 키. **D1 등록 도구는 `index`가 없으므로 vote용 `tool_id`는 slug 문자열, reviews용 `tool_index`는 별도 할당 필요** (4절·7절 참조).
- 투표/리뷰 클라이언트 fetch: `/api/tools/vote?tool_id=${TOOL_ID}` (`:278`), `/api/tools/reviews?tool_index=${TOOL_INDEX}` (`:295`). 리뷰 링크도 `toolIndex` 쿼리 (`:144`, `:217`).
- 섹션 숨김 패턴 (Phase 2 "없는 섹션 숨김"에 재사용): `{tool.data.koreanSupport && tool.data.useCases && ... && (...)}` (`:153`), `{taskLinks.length > 0 && (...)}` (`:174`), `{tool.data.relatedPost && (...)}` (`:187`).
- task 필터: `(tool.data.tasks ?? []).filter((s) => ALL_TASKS[s])` (`:32`) — **tasks.ts에 없는 슬러그는 조용히 탈락** (5.3 참조).

### 2.2 `src/pages/tools/index.astro` (523줄, `prerender = true` :2)
- 정렬: `order ?? 99` 오름차순 (`:6-7`). 최신등록: `updated` 내림차순 상위 6 (`:9-12`). 인기: `koreanSupport` 상위 8 (`:14-17`).
- 카테고리 8개 하드코딩 (`:19-28`): `all(전체 🔥) / 글쓰기·챗봇✍️ / 이미지 생성🎨 / 영상·음성🎬 / 업무·생산성📊 / 코딩·개발💻 / 디자인🖼️ / 번역·학습🌐`. **Phase 1은 이 8개 대분류 고정 사용 (CONTEXT locked).**
- 카드 렌더 (`:264-319`): 상단 그라데이션 바 `h-0.5 bg-gradient-to-r ${accent}` (`:284`, catAccent 맵 `:30-38`), KR 뱃지 (`:291-295`), 난이도 뱃지 `difficultyColor/difficultyLabel` (`:41-51`), 가격 `price || '—'` (`:313`). NEW 뱃지(최신 섹션용, `:145-147`):
```html
<span class="... bg-emerald-100 text-emerald-700 rounded-full border border-emerald-200 ... dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/20">NEW</span>
```
- 필터 data 속성 (`:271-281`): `data-cat/name/tags/desc/price/korean/difficulty/order/updated/review`. 정렬 select: 추천순(이름순·최신순·⭐리뷰순) (`:255-260`). 페이지네이션 `PAGE_SIZE = 24` (`:375`).
- 제출 진입 버튼: `/tools/submit/` 링크 (`:90-94`) — 이미 존재.

### 2.3 `src/pages/api/tools/vote.ts` (83줄) — Phase 1 submit API의 템플릿
- DB 접근: `const db = (locals as any).runtime?.env?.DB;` (`:5`) + `if (!db) 500 'DB 없음'` (`:6`).
- 인증: `cookies.get('session')` 없으면 401 `'로그인 필요'` (`:8-9`), `verifySession(session, (locals as any).sessionSecret)` 실패 시 401 `'세션 오류'` (`:12-20`).
- POST 토글 패턴 (`:26-49`): SELECT 존재 확인 → 있으면 DELETE(취소) / 없으면 INSERT → COUNT 재조회 반환 `{voted, count}`.
- GET (`:56-83`): DB 없으면 `{count:0, voted:false}` 200 — **읽기계는 실패해도 200 폴백** (Phase 2 D1 합성 시 동일 태도 권장).

### 2.4 `src/pages/api/tools/reviews.ts` (30줄, GET only)
```ts
const reviewResult = await db.prepare(`
  SELECT p.*, u.name as author, u.avatar
  FROM posts p
  JOIN users u ON p.user_id = u.id
  WHERE p.tool_id = ? AND p.category = 'review'
  ORDER BY p.created_at DESC
  LIMIT 10
`).bind(parseInt(toolIndex)).all();
```
- 리뷰 = posts 테이블(`category='review'`, `tool_id` 정수 FK) + users JOIN. 평균 평점 서버 계산, 에러 시 `{reviews:[], avgRating:0}` 200 폴백 (`:26-29`).

### 2.5 `src/config/tasks.ts` (102줄)
- `TASKS: Record<string, TaskInfo>` (`:10`), `{title, kw}` (`:5-8`), `TASK_SLUGS`/`TASK_COUNT` export (`:101-102`). 섹션: 문서·텍스트 15 / 이미지·디자인 11 / 영상·음성 10 / 업무·생산성 10 / 코딩·개발 7 / 학습·리서치 6 / 마케팅·SNS 8 / 전문분야 6.
- Python 미러 `scripts/task_config.py`와 동기화 필수 (파일頭 주석 `:1-3`). **Phase 1 submit 폼의 tasks 선택지는 이 파일의 키만 사용.**
- 주의: `chatgpt-work.md`의 `tasks: ["문서-작성", ...]` 중 `"문서-작성"` 키는 tasks.ts에 없음 → `[id].astro:32` 필터에서 탈락. **Phase 1에서 tasks 옵션은 tasks.ts 키 기준으로만 제공할 것.**

### 2.6 `src/env.d.ts` (14줄)
```ts
interface Env { DB: D1Database; R2: R2Bucket; }
type Runtime = import('@astrojs/cloudflare').Runtime<Env>;
declare namespace App { interface Locals extends Runtime { sessionSecret: string; } }
```
- DB 바인딩명 `DB`, R2 바인딩 `R2` (Phase 3용, 현재 미사용). `wrangler.toml:5-8`에서 `binding="DB" / database_name="aikorea24-db"`.

### 2.7 `src/lib/auth.ts` (111줄) — 세션 함수 시그니처
```ts
signSession(data: Record<string, any>, secret: string): Promise<string>   // :12 — payloadB64.sigB64 HMAC-SHA256
verifySession(signedSession: string, secret: string): Promise<Record<string, any> | null>  // :22
getSessionUser(cookies: any, secret: string): Promise<{ id: number; email: string; name: string; role?: string } | null>  // :42-48 (email+name 없으면 null)
isOwner(user: { role?: string } | null): boolean  // :50-52 (role==='owner')
```
- `sessionSecret` 주입: `src/middleware.ts:18` `context.locals.sessionSecret = runtime?.env?.SESSION_SECRET || ''` (미설정 시 warn만, 차단 없음 `:19-21`).
- 로그인 시작점: `GET /api/auth/login` → Google OAuth (`src/pages/api/auth/login.ts:3-32`, `redirect_to`를 state로 전달 `:12-16`).

## 3. vote/reviews D1 테이블 + 전 DB.prepare 목록

### 3.1 테이블 실체 판정
| 테이블 | DDL in repo | 사용처 | 비고 |
|---|---|---|---|
| `tool_votes` | ❌ 없음 (repo 전체 grep 0건) | vote.ts 7개 쿼리 | D1 원격에 수동 생성된 것으로 추정. 스키마는 쿼리에서 역추정: `(id, tool_id TEXT, user_email TEXT)` |
| `posts`(+`tool_id`,`rating`) | ⚠️ 부분 — `schema.sql:12-22` 베이스에는 `tool_id`·`rating`·`author_email/name`·`access_level`·`price`·`preview_content` 없음 | reviews.ts SELECT, `api/posts/index.ts:91` INSERT | D1 원격이 repo 스키마보다 앞서 있음. tool_submissions 설계 시 posts 확장 컬럼명과 충돌 피할 것 |
| `tool_submissions` | ❌ 없음 (신규 작성 대상) | — | Phase 1에서 `sql/001_tool_submissions.sql` 신규 |
| `tools` | ❌ 없음 (REASONIX.md:453 제안 스니펫만 존재, 미적용) | — | 이번 페이즈 사용 안 함 |

### 3.2 전 DB.prepare 호출 (verbatim)
vote.ts:
- `'SELECT id FROM tool_votes WHERE tool_id = ? AND user_email = ?'` (POST 존재확인 `:28`, GET voted확인 `:75`)
- `'DELETE FROM tool_votes WHERE tool_id = ? AND user_email = ?'` (`:34`)
- `'SELECT COUNT(*) as cnt FROM tool_votes WHERE tool_id = ?'` (`:37`,`:46`,`:65`)
- `'INSERT INTO tool_votes (tool_id, user_email) VALUES (?, ?)'` (`:43`)
reviews.ts:
- `SELECT p.*, u.name as author, u.avatar FROM posts p JOIN users u ON p.user_id = u.id WHERE p.tool_id = ? AND p.category = 'review' ORDER BY p.created_at DESC LIMIT 10` + `.bind(parseInt(toolIndex))` (`:12-19`)
참고 posts 작성 (`api/posts/index.ts:91`): `INSERT INTO posts (title, content, author_email, author_name, category, access_level, price, preview_content, user_id, tool_id, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` + `SELECT id FROM users WHERE email = ?` (`:70`)로 user_id 역조회.

## 4. 로그인 체크 패턴 (3종 — 코드 스니펫)

**A. 서버 .astro (가드+리다이렉트) — `src/pages/community/write.astro:5-11`:** Phase 1 submit.astro SSR 개편의 템플릿
```astro
let currentUser = null;
const session = Astro.cookies.get('session')?.value;
if (session) currentUser = await verifySession(session, Astro.locals.sessionSecret);
if (!currentUser) {
  return Astro.redirect('/auth/consent');
}
```
동일 패턴: `community/review.astro:6-7`, `event/index.astro:6-7`, `[id]/edit.astro:9-13`, `Layout.astro:31-32`(리다이렉트 없이 currentUser만).

**B. 서버 API (401 JSON) — `src/pages/api/posts/index.ts:51-65`:** Phase 1 POST /api/tools/submit의 템플릿
```ts
const session = cookies.get('session')?.value;
if (!session) {
  return new Response(JSON.stringify({ error: '로그인이 필요합니다.' }), { status: 401 });
}
let user: { email: string; name: string } | null;
try { user = await verifySession(session, sessionSecret); }
catch { return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 }); }
if (!user) {
  return new Response(JSON.stringify({ error: '유효하지 않은 세션입니다.' }), { status: 401 });
}
// users 테이블에서 user_id 조회
const userRow = await db.prepare('SELECT id FROM users WHERE email = ?').bind(user.email).first();
```
(vote.ts도 동일 구조, 메시지만 `'로그인 필요'`/`'세션 오류'`.)

**C. 클라이언트 (쿠키 존재 확인) — `src/pages/tools/[id].astro:338-349`:**
```js
const isLoggedIn = document.cookie.includes('session=');
if (!isLoggedIn) { window.location.href = '/api/auth/login'; return; }
```
- ⚠️ 불일치: A는 미로그인 시 `/auth/consent`로, C는 `/api/auth/login`으로 보냄. **Phase 1 submit.astro는 A 패턴(서버 가드 → `/auth/consent`)을 따르고, fetch 실패(401) 시 메시지만 표시할 것.**

## 5. slug 패턴 + 카테고리 대조

### 5.1 `src/content/tools/*.md` 파일명 5예 (glob 확인)
`bolt.md` / `grok.md` / `runway.md` / `vrew.md` / `chatgpt-work.md` (+ 장문 예: `rynnworld-4d-4d-embodied-world-models-for-robotic.md`, `vidu-s1-a-real-time-interactive-video-generation.md`)
- 패턴: 소문자 kebab-case 영문 위주, `[id].astro`의 `tool.id` = 파일명 그대로. 한글 슬러그 없음. 자동수집 산물은 50자 내외 절단형도 존재.
- **Phase 1 slug 자동생성 규칙 제안: 영문명 소문자화+비영숫자→하이픈, 한글명이거나 빈 결과면 `tool-<epoch>` 폴백, D1+md 양쪽 중복 시 숫자 접미사.**

### 5.2 카테고리: index.astro(8 고정) vs submit.astro(동적)
- index.astro: 8개 하드코딩 (2.2 참조).
- submit.astro (`:6-7`,`:30-33`): `getCollection('tools')`에서 unique 추출 + `기타` 옵션 — md 카테고리 전체가 노출되어 8대분류와 불일치 가능.
- 샘플 md frontmatter (`chatgpt-work.md:1-15`): `name/description/category/price/koreanSupport/difficulty/url/useCases/tags/featured/order/tasks/updated` — content sche-ma (`src/content.config.ts:19-37`)와 일치. `index` 필드는 스키마에 없음 (`[id].astro:37`의 `data.index`는 리뷰용 관습값, md에 직접 기재).
- **Phase 1 locked: submit 폼 카테고리 select는 index.astro 8개 중 `전체` 제외 7개 + `기타`로 고정.**

## 6. sql/ 마이그레이션 넘버링

- `sql/` : `network_schema.sql`, `persona_migration.sql` — **번호 없음**, 00X prefix 미사용.
- `scripts/migrations/` : 날짜 prefix 3개 (`20260630_add_impact_score_columns.sql`, `20260710_add_course_system.sql`, `20260710_add_admin_role.sql`) — **현행 최대 `20260710`**.
- 루트 `migrations/` 디렉토리 없음. wrangler.toml에 migrations 설정 없음 (수동 `d1 execute` 운용으로 추정).
- **다음 파일명: CONTEXT 지정 `sql/001_tool_submissions.sql`** (sql/ 내 번호 충돌 없음. 적용 명령: `wrangler d1 execute aikorea24-db --remote --file=sql/001_tool_submissions.sql`).

## 7. Planner용 추가 확정 사항 (Phase 1·2 설계 입력)

- `POST /api/tools/submit` 미존재 확인: `src/pages/api/tools/`에 `vote.ts`·`reviews.ts`만 존재. submit.astro 폼(`action="/api/tools/submit" method="POST"`, `:14`)은 현재 404 — 신규 작성 필요.
- submit.astro는 `prerender = true` (`:1`) + 정적 폼 — **Phase 1에서 prerender 제거(SSR 전환) 필수**, 그렇지 않으면 서버 가드·D1 INSERT 불가.
- D1 도구 식별자 충돌 방지: md `tool.id`(파일명)와 D1 `slug` 네임스페이스 공유 가정 시, INSERT 전 `getCollection('tools')` slug 목록과 D1 slug 중복을 동시 체크해야 함 (상세 페이지 `/tools/[id]`가 md 우선이므로 D1 slug가 md와 겹치면 D1 행이 영원히 가려짐).
- vote 키가 `tool_id TEXT`이므로 D1 등록 도구도 slug 문자열로 투표 가능 (스키마 변경 불요). reviews는 `tool_id INTEGER` + posts 경유이므로 D1 도구의 리뷰는 Phase 2 범위 밖 — `[id].astro` D1 fallback에서는 리뷰 섹션 숨김 처리 권장.
- MAKER 배지 스타일 (CONTEXT "Phase 2-2 지정 클래스"): CONTEXT에 클래스 원문 없음 — Phase 2-2 계획 시점에 purple 계열로 지정 예정. 본 RESEARCH 시점 미확정 → planner는 Phase 2-2에 플레이스홀더 배지 태스크를 둘 것.
- TASKS 73개 여부: tasks.ts 실측 결과 섹션별 합계 73 (15+11+10+10+7+6+8+6) — CONTEXT 수치와 일치.

## Open Questions
1. `tool_votes`·posts 확장컬럼(`tool_id`,`rating` 등)의 D1 원격 실스키마 — repo에 DDL 없음. Phase 1ormal 동작에는 불요하나, 원격 `sqlite_master` 덤프 1회로 확정 권장 (`wrangler d1 execute aikorea24-db --remote --command="SELECT sql FROM sqlite_master WHERE name IN ('users','posts','tool_votes');"`).
2. membership 컬럼 3종의 원격 존재 여부 — 동일 덤프로 확인 가능. 없어도 Phase 1·2 블로커 아님 (auth.ts 함수는 호출 시에만 실패).
3. D1 `detail_markdown` 렌더 방식 — 현재 `render(tool)`은 content collection 전용. D1 마크다운 렌더용 라이브러리(astro 내장 `marked` 등) 의존성 확인은 Phase 2-3 계획 시.
