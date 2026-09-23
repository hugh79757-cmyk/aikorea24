# 41-01 REPORT — Phase 0 Read-Only Verification (Senior Gate)

**작성:** 2026-09-23 · **실행:** junior (read-only, 코드 변경 0건)
**목적:** RESEARCH.md 주장을 live repo + D1 remote 실측으로 확정, 41-02 진입可否 판정

---

## 1. D1 Remote 실측 (Task 1)

덤프 명령: `wrangler d1 execute aikorea24-db --remote --command="SELECT sql FROM sqlite_master WHERE name IN ('users','posts','tool_votes','tool_submissions');"` (profile hugh79757, APAC/SIN 응답)

### 1.1 테이블 존재 여부

| 테이블 | 원격 존재 | RESEARCH §3.1 예측 | 판정 |
|---|---|---|---|
| users | ✅ | ✅ 베이스 존재 | 일치 |
| posts | ✅ | ✅ 베이스 + 확장 | 일치 |
| tool_votes | ✅ | ✅ 추정 (DDL repo 없음) | 일치 — 실체 확정 |
| tool_submissions | ❌ | ❌ 신규 작성 대상 | 일치 — 41-02에서 신규 |

### 1.2 users 원격 DDL (verbatim)

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  google_id TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  avatar TEXT,
  created_at TEXT DEFAULT (datetime('now'))
, membership TEXT DEFAULT 'free', membership_expires TEXT, purchased_posts TEXT DEFAULT '[]', role TEXT DEFAULT 'member')
```

- RESEARCH §1.1 A(베이스) ✅ + C(role) ✅ + D(membership trio) ✅ — membership 3종 원격 존재 확정 (out-of-band 적용 추정 그대로).
- ⚠️ **B(kakao 확장) 불일치:** 원격에 `kakao_id`, `provider` 컬럼 없음. `idx_users_kakao` 인덱스 없음 (`sqlite_master LIKE '%kakao%'` 0건, `LIKE '%users%'`는 users + autoindex만). 즉 `sql/persona_migration.sql`은 원격 미적용.
- **영향:** `kakao.ts:44-66`의 `SELECT ... WHERE kakao_id = ?`, `INSERT (kakao_id, google_id, ..., provider)`, `UPDATE users SET kakao_id = ?`는 원격에서 **"no such column" 실패**. 카카오 로그인은 현재 원격에서 동작 불가. (Google 로그인은 정상 — 아래 1.4 참조.)
- 41-02 블로커 아님: submit API는 Google 세션(`google.ts` 경로, id INTEGER)만 사용. 카카오 수정은 본 Phase 범위 밖 → 미해결이슈로 이관.

### 1.3 posts 원격 DDL (verbatim)

```sql
CREATE TABLE posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT DEFAULT 'general',
  views INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')), access_level TEXT DEFAULT 'free', price INTEGER DEFAULT 0, preview_content TEXT, author_email TEXT DEFAULT '', author_name TEXT DEFAULT '익명', tool_id INTEGER, rating INTEGER DEFAULT 5, visibility TEXT DEFAULT 'public',
  FOREIGN KEY (user_id) REFERENCES users(id)
)
```

- RESEARCH §3.1 "⚠️ 부분" 예측과 일치. 확장 컬럼(`tool_id INTEGER`, `rating`, `author_email/name`, `access_level`, `price`, `preview_content`, `visibility`) 전부 원격 존재 확정.
- `tool_submissions` 설계 시 posts 확장 컬럼명과 충돌 피할 것 (동일 필드명은 D1 JOIN 시 alias — RESEARCH 권고 유지).

### 1.4 tool_votes 원격 DDL (verbatim)

```sql
CREATE TABLE tool_votes (id INTEGER PRIMARY KEY AUTOINCREMENT, tool_id TEXT NOT NULL, user_email TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now')), UNIQUE(tool_id, user_email))
```

- RESEARCH §3.1 역추정 `(id, tool_id TEXT, user_email TEXT)` 정확. UNIQUE 제약까지 확인.
- D1 등록 도구도 slug 문자열로 투표 가능 — 스키마 변경 불요 (RESEARCH §7 유지).

### 1.5 user_id 타입 verdict (41-02 설계 입력)

**`user_id INTEGER NOT NULL REFERENCES users(id)` 사용.** 근거:
- 원격 `users.id` = INTEGER PK AUTOINCREMENT (실측).
- 원격 `posts.user_id` = INTEGER NOT NULL + FK (실측).
- `google.ts` SELECT가 `id`(INTEGER)를 세션에 담음 (코드 확인, 변경 없음).
- RESEARCH §1.3 결론 유지 — 실측으로 확정됨.

---

## 2. 파일 실측 (Task 2)

`ls src/pages/tools/ src/pages/api/tools/` → tools/: `[id].astro, finder, index.astro, submit.astro, task` / api/tools/: `reviews.ts, vote.ts` (submit 미존재 = 404 상태 유지 ✅).
prerender grep → submit.astro:1, index.astro:1, [id].astro:1 (3파일 전부 `export const prerender = true;` :2 ✅).

| 파일 | 줄수 | 핵심 상태 (행번호) | RESEARCH 대비 |
|---|---|---|---|
| tools/[id].astro | 416 | prerender :2 / getStaticPaths :7-13 / render :18 / tasks 필터 :32 / toolIndex :37 / 섹션숨김 :153,:174,:187 / 리뷰링크 :144,:217 / vote fetch :278 / reviews fetch :295 / TOOL_ID wiring :270-273 / 쿠키체크 :338-349 / vote 클릭→/api/auth/login :349 | drift 없음 |
| tools/index.astro | 523 | prerender :2 / order 정렬 :6-7 / 최신 :9-12 / 인기 :14-17 / 카테고리 8개 :19-28 / catAccent :30-38 / difficulty :41-51 / 카드 :264-319 (그라데이션 :284, KR :291-295, 가격 :313) / data속성 :271-281 / 정렬select :255-260 / PAGE_SIZE=24 :375 / submit 링크 :90-94 | drift 없음 |
| tools/submit.astro | 55 | prerender :1 / 정적폼 action=/api/tools/submit :14 / 동적카테고리 :6-7,:30-33 / 기타옵션 :32 | drift 없음 — Phase 1에서 prerender 제거(SSR) 필수 유지 |
| api/tools/vote.ts | 83 | DB접근 :5-6 / 401 :8-9,:12-20 / 토글 :26-49 / GET 200폴백 :56-83 | drift 없음 |
| api/tools/reviews.ts | 30 | posts JOIN 쿼리 :12-19 + parseInt :19 / 200폴백 :26-29 | drift 없음 |
| config/tasks.ts | 102 | TASKS Record :10 / TASK_SLUGS/COUNT :101-102 / 키 실측 73개 (grep) | 73개 일치 ✅ |
| env.d.ts | 14 | Env{DB,D1Database;R2} + Locals.sessionSecret | drift 없음 |
| lib/auth.ts | 111 | signSession :12 / verifySession :22 / getSessionUser :42-48 / isOwner :50-52 / getUserMembership :55-58 | drift 없음 |
| middleware.ts | 48 | sessionSecret 주입 :18-21 (warn만, 차단없음) | drift 없음 |
| callback/google.ts | 58 | INSERT 4컬럼 :38-44 / SELECT id,name,email,avatar,role :48-50 | 스키마 매칭 ✅ (불일치 우려 해소 — RESEARCH §1.2 유지) |
| callback/kakao.ts | 79 | SELECT kakao_id :44 / INSERT 6컬럼 :60-61 / UPDATE kakao_id :56 | ⚠️ 원격 컬럼 부재로 실패 (1.2 참조 — 신규 발견, RESEARCH 당시 미확인) |
| content.config.ts | 96 | tools 스키마 :19-37 (name/desc/category/price/koreanSupport/difficulty/url/useCases/tags/featured/order/tasks/updated + priceModel/launchDate) / `index` 필드 없음 | drift 없음 |
| wrangler.toml | 18 | binding=DB / aikorea24-db :5-8 / R2 바인딩 / migrations 설정 없음 | drift 없음 |
| community/write.astro | — | 서버가드 :5-11 → /auth/consent | 패턴 A ✅ |
| api/posts/index.ts | — | 401 JSON :51-65 + user_id 역조회 :70 | 패턴 B ✅ |

**Drift 요약:** RESEARCH §2/§4/§5 대비 drift 0건. 유일한 신규 발견은 kakao 원격 미적용 (위 1.2) — 41-02 범위 밖.

---

## 3. 로그인 패턴 확정 (Task 3)

| 패턴 | 위치 | 동작 | 41-02 적용 |
|---|---|---|---|
| A 서버 .astro 가드 | community/write.astro:5-11 (+review/event/edit/Layout 동일) | 미로그인 → `Astro.redirect('/auth/consent')` | **submit.astro가 따름** (SSR 전환 후) |
| B 서버 API 401 JSON | api/posts/index.ts:51-65, vote.ts:8-20 | 미로그인/세션오류 → 401 JSON (메시지만) | **POST /api/tools/submit이 따름** (401 메시지만, 리다이렉트 없음) |
| C 클라이언트 쿠키체크 | [id].astro:338-349 | `document.cookie.includes('session=')` → `/api/auth/login` | submit 플로우에서 사용 안 함 (A/B로 커버) |

**Locked:** submit.astro = A, submit API = B, 401 시 메시지 표시만 (리다이렉트 금지). A→`/auth/consent` vs C→`/api/auth/login` 불일치는 기존 상태로 둠 (본 Phase 범위 밖).

---

## 생성/수정 파일

- 생성: `.planning/phases/41-tools-user-submit/41-01-REPORT.md` (본 파일). 코드 변경 0건.
- `git status --porcelain` 기준 repo 코드 diff 없음 (REPORT.md만 untracked).

## 동작확인

- [검증됨] D1 remote 테이블 존재 확인 쿼리 — 결과 users/posts/tool_votes 존재, tool_submissions 부재. 근거: wrangler remote 실행 결과 (APAC/SIN, size_after 16941056).
- [검증됨] D1 remote DDL 3종 전문 확보 — users/posts/tool_votes CREATE TABLE verbatim (위 1.2-1.4). 근거: sqlite_master 덤프 출력.
- [검증됨] kakao 컬럼 원격 부재 — `LIKE '%kakao%'` 0건. 근거: sqlite_master 2차 쿼리 (users + autoindex만 반환).
- [검증됨] 전 §2 파일 상태 + 행번호 — 14개 파일 wc/read/grep 실측, RESEARCH와 대조. 근거: 위 표 (줄수 416/523/55/83/30/102/14/111/48/58/79/96/18).
- [검증됨] TASKS 73개 — 근거: `grep -oE` 키 카운트 73.
- [검증됨] 3 로그인 패턴 코드 확인 — 근거: write.astro:5-11, posts/index.ts:51-65, [id].astro:338-349 스니펫.
- [검증불가] 카카오 로그인 원격 실패 — 실제 카카오 OAuth 플로우 미실행 (스키마 추론만). 복구: D1에 persona_migration 적용 후 카카오 로그인 1회 테스트 (별도 Phase).

## 미해결이슈

1. **카카오 로그인 원격 불가** (`kakao_id`/`provider` 컬럼 미적용): kakao.ts 전 쿼리 실패 예상. 41-02 블로커 아님 (Google 세션만 사용). 해결은 별도 Phase에서 `persona_migration.sql` 원격 적용 + 로그인 테스트.
2. MAKER 배지 클래스 미확정 (RESEARCH §7 유지 — Phase 2-2에서 purple 지정).
3. D1 `detail_markdown` 렌더 방식 미확정 (Phase 2-3에서 의존성 확인).

## 다음메모 (41-02 planner 입력)

- `sql/001_tool_submissions.sql` 신규 — `user_id INTEGER NOT NULL REFERENCES users(id)` (본 REPORT §1.5).
- POST /api/tools/submit 신규 — vote.ts 패턴 + 패턴 B 인증 (401 JSON), 필수필드 400, slug 자동생성+중복시 숫자 (md+D1 양쪽 중복 체크 — md 우선이므로 겹치면 가려짐), URL 검증, description 200자.
- submit.astro 개편 — prerender 제거(SSR), 패턴 A 가드, 2스텝 폼 (Step1 필수 5 / Step2 선택 7+tasks 최대5, tasks.ts 키만), fetch POST, Tailwind 다크모드 유지.
- 카테고리 select: index.astro 8개 중 `전체` 제외 7개 + `기타` 고정.
- 카페 URL: https://cafe.naver.com/gptdohye. 적용 명령: `wrangler d1 execute aikorea24-db --remote --file=sql/001_tool_submissions.sql`.
- 리뷰는 posts 경유 INTEGER이므로 D1 도구 리뷰는 Phase 2 범위 밖 — [id].astro fallback에서 리뷰 섹션 숨김.

## Go / No-Go

**GO for 41-02.** users/posts/tool_votes 실체 확정, user_id INTEGER 확정, 전 파일 drift 없음, 로그인 패턴 잠금 완료. 카카오 이슈는 41-02 범위 밖으로 격리됨.
