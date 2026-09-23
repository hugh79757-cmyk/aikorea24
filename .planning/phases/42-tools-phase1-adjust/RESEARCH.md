# RESEARCH — Phase 42: /tools Phase 1 스펙 정합 조정 (시니어 결정 6항 반영)

**Researched:** 2026-09-23
**Domain:** Astro 5 SSR + Cloudflare D1 schema migration + form/API adjust
**Confidence:** HIGH (all claims read from repo files this session; D1 row counts probed live)

## User Constraints (from CONTEXT.md)

### Locked decisions (시니어, 2026-09-23 — 재논의 없음)
1. **status**: `DEFAULT 'published'`, TEXT 유지, `'hidden'` 값 허용. index.astro 조회는 `WHERE status='published'`.
2. **price**: `price_model` (필수, 3택: 무료/Freemium/유료) + `price_detail` (선택, 자유텍스트). 카드 표시 = `price_detail || price_model`.
3. **description**: 200자 캡 유지. 실시간 카운터 UI (`42/200` 형식). 200자 초과 시 카운터 빨간색 + 제출 버튼 비활성화.
4. **카테고리**: 8개 (7 + 기타). "기타" 선택 시 "희망 카테고리" text input 표시. DB에 `category_custom TEXT` 컬럼 추가.
5. **Step 2 추가**: `screenshot_url TEXT` (URL 형식, 선택). 카페 링크 상수 분리: `const CAFE_URL = 'https://cafe.naver.com/gptdohye'`.
6. **범위**: Phase 2까지만. Phase 3(R2/my/PUT-DELETE) 착수 금지.

### Scope (실행 순서)
Step 0: `sql/001_tool_submissions.sql` 수정 (파일번호 유지) + ALTER TABLE 마이그레이션 (price → price_model+price_detail, category_custom, screenshot_url, 기존 행 price 값 보존 규칙 포함) → 스키마 보고 → 코드 진행. Step 1: submit.ts 검증. Step 2: submit.astro 폼. Step 3: index.astro WHERE + 표시 규칙. Step 4: [id].astro 표시 규칙 + 빌드/E2E curl 검증.

### Out of scope
Phase 3 일체 / 승인 프로세스 (published/hidden만) / 마크다운 도구·자동수집 파이프라인 / Phase 1-40 회귀 없음.

## Summary

Phase 41 구현 5개 파일 실측 완료. DDL(`sql/001_tool_submissions.sql:4-22`)은 `price TEXT` 단일, `category_custom`·`screenshot_url` 없음, `status DEFAULT 'published'`는 결정 1과 이미 일치. **Local + remote D1의 `tool_submissions` 행 수는 둘 다 0** (wrangler 4.110.0, profile hugh79757로 live probe) — price 값 보존 마이그레이션은 빈 테이블 대상이므로 규칙만 정의하면 되고 데이터 손실 리스크 없음. Tools 페이지 3종 전부 `prerender` 없음(전면 SSR, `astro.config` `output: 'server'` + `@astrojs/cloudflare ^12.6.12`) — SSR 가드/D1 패턴은 Phase 41 코드 그대로 재사용.

**Primary recommendation:** `sql/002_tools_phase1_adjust.sql` 신규 마이그레이션 파일로 `ADD COLUMN ×4 + price→price_model 백필 + DROP COLUMN price` 후 local/remote에 `d1 execute` 적용하고, 001 파일도 동일 최종 스키마로 갱신. 그 후 submit.ts → submit.astro → index.astro → [id].astro 순으로 조정.

## Current State Per File (with line numbers)

### 1. `sql/001_tool_submissions.sql` (24 lines)
- `:4-22` CREATE TABLE: `price TEXT` (`:12`), `status TEXT DEFAULT 'published'` (`:19`). `category_custom`, `screenshot_url`, `price_model`, `price_detail` 없음.
- `:23-24` 인덱스 2개 (slug, user_id) — price 참조 없음, DROP COLUMN price 시 인덱스 영향 없음.
- `sql/` 디렉토리: `001_tool_submissions.sql`, `network_schema.sql`, `persona_migration.sql` — 002 번호 비어 있음.

### 2. `src/pages/api/tools/submit.ts` (153 lines)
- 카테고리 화이트리스트 `:7-16` — 7개 + `기타`, 결정 4와 일치 (수정 불요, `category_custom` 검증만 추가).
- 필수 4종 검증 `:62-64`, description 200자 400 에러 `:67-69` (서버측 결정 3 일치).
- URL http(s) 검증 `:72-79` — `screenshot_url`에 동일 패턴 재사용 (선택값이므로 빈 문자열은 스킵).
- tasks 최대 5개 + TASKS 키 검증 `:88-101` (수정 불요).
- slug 중복 회피 md+D1 `:104-121` (수정 불요).
- INSERT `:125-143` — 컬럼 리스트 `:127`에 `price`, INSERT 값 `:136` `price?.trim() || null`. → `price_model` + `price_detail` + `category_custom` + `screenshot_url`로 교체 필요.
- 가격 select 현재값: `무료 / 무료 / 유료 / 유료` 3택 (submit.astro `:71-75`) → 결정 2의 3택은 `무료 / Freemium / 유료`. 기존값 `무료 / 유료` ≠ `Freemium` — 폼 옵션명 변경 + 백필 매핑 규칙 필요 (아래 마이그레이션 섹션).

### 3. `src/pages/tools/submit.astro` (313 lines)
- SSR 가드 `:6-11` (`verifySession` → `/auth/consent` 리다이렉트) — 유지.
- 카테고리 8개 `:14-23` (7 + 기타 📦) — 결정 4 일치. 기타 토글 input + `category_custom` payload 추가 필요.
- 가격 select `:71-75` — 라디오 + `price_detail` input으로 교체 (결정 2).
- description 카운터 **부분 존재**: `<span id="desc-count">` `:59`, input 리스너 `:185-187`에 길이 표시만. 빨간색 + `btn-submit` (`:121`) 비활성화 추가 필요. `maxlength="200"` (`:60`)는 붙여넣기 초과 시 조용히 절단하므로 JS 초과 판정이 진실 공급원.
- Step 2 선택 필드 `:82-123` — `screenshot_url` input을 여기에 추가 (결정 5).
- 카페 URL 하드코딩 2곳: `:155` (바로가기 링크), `:303` (공유 문구 템플릿). → 파일 상단 `<script>` 내 `const CAFE_URL` 분리, 단 공유 문구 문자열은 done-state 렌더 시점에 주입되므로 `dataset.shareText` (`:302-303`) 생성부에 상수 사용.
- 완료화면 가격 미리보기 `:293`,`:301` (`toolPrice`) — `price_detail || price_model` 표시로 변경.

### 4. `src/pages/tools/index.astro` (571 lines)
- D1 쿼리 `:13-15` — `WHERE status='published'` 없음 (결정 1 위반, 핵심 수정점). fail-soft try/catch `:10-20` 유지.
- 매핑 `:31-46` — `price: r.price ?? '—'` (`:38`) → `price_detail || price_model` 폴백 체인으로 교체. 쿼리 SELECT 리스트에 3개 컬럼 반영 필요 (SELECT * 미사용이므로 명시 추가).
- 가격 표시 4곳: `:197`,`:243` (md 카드),`:321` (`data-price` 필터 속성),`:361` (D1 카드). `matchFree` 필터 (`:511`)는 `data-price.includes('무료')` — price_model `Freemium`은 '무료' 미포함이므로 무료 필터에서 제외됨. 시니어 결정에 필터 규칙 언급 없음 → **동작 변경점**: Freemium 도구는 무료-only 필터에서 빠짐. planner가 CONTEXT에 없는 판단이 필요하면 senior 확인 (Open Question 1).

### 5. `src/pages/tools/[id].astro` (489 lines)
- D1 fallback 쿼리 `:28-30` — status 조건 없음. CONTEXT Step 4는 "[id] 동일 표시 규칙 + 숨김 섹션 유지"만 요구하고 hidden 직접 접근 차단 요구 없음 → status 필터 추가하지 않음 (직접 URL 접근은 허용). planner 확인용으로 명시.
- 매핑 `:47-63` — `price: row.price ?? '—'` (`:53`) → 동일 폴백 체인. `body: detail_markdown || description` (`:62`) 유지.
- 가격 표시 `:178` (상세),`:335` (연관 도구) — `:335`는 md 도구용으로 D1 변경 영향 없음.
- D1 렌더: `Content: null` (`:68`) + `body` 원시 텍스트 — screenshot_url 표시 위치는 planner 재량 (Step 2 선택 필드이므로 상세에 노출 권장).

## ALTER TABLE Migration Path (local + remote D1)

### Verified preconditions (live probe this session)
- Local `SELECT COUNT(*) FROM tool_submissions` → **0 rows** (wrangler 4.110.0, profile hugh79757).
- Remote 동일 쿼리 → **0 rows**.
- `wrangler.toml:5-8`: `binding="DB"`, `database_name="aikorea24-db"`, id `bec650ce-...`.
- D1 = SQLite 기반. `ADD COLUMN` 지원. `DROP COLUMN`은 SQLite 3.35+에서 지원, D1도 지원 — price 인덱스 없음이라 제약 없음. 그래도 0행 테이블이므로 실패 시 `DROP TABLE + 001 재적용` 폴백 가능 (데이터 손실 없음).

### Recommended migration file: `sql/002_tools_phase1_adjust.sql`
```sql
-- Phase 42: price → price_model + price_detail, category_custom + screenshot_url
ALTER TABLE tool_submissions ADD COLUMN price_model TEXT;
ALTER TABLE tool_submissions ADD COLUMN price_detail TEXT;
ALTER TABLE tool_submissions ADD COLUMN category_custom TEXT;
ALTER TABLE tool_submissions ADD COLUMN screenshot_url TEXT;
-- 기존 price 값 보존 (현재 0행이나 규칙으로 유지):
-- '무료' → price_model='무료' / '유료' → '유료' / 그 외(예: '무료 / 유료') → price_model='Freemium', price_detail=원값
UPDATE tool_submissions SET price_model = CASE
  WHEN price = '무료' THEN '무료'
  WHEN price = '유료' THEN '유료'
  WHEN price IS NOT NULL AND TRIM(price) != '' THEN 'Freemium'
  ELSE NULL END,
  price_detail = CASE
  WHEN price = '무료' OR price = '유료' THEN NULL
  ELSE price END
WHERE price_model IS NULL;
ALTER TABLE tool_submissions DROP COLUMN price;
```

### Apply commands (AGENTS.md §Cloudflare Auth: `env -u CLOUDFLARE_API_TOKEN` 필수)
```bash
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --local --file=sql/002_tools_phase1_adjust.sql
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --file=sql/002_tools_phase1_adjust.sql
# verify both:
env -u CLOUDFLARE_API_TOKEN /opt/homebrew/bin/wrangler d1 execute aikorea24-db --remote --command="PRAGMA table_info(tool_submissions);"
```
### 001 file update
`sql/001_tool_submissions.sql:12` `price TEXT,` → `price_model TEXT, price_detail TEXT,` + `:10-11` 근처에 `category_custom TEXT,`·`screenshot_url TEXT,` 추가. 신규 환경 `d1 execute --file=sql/001...` 한 번으로 최종 스키마 구성되도록 002와 일치시킬 것.

### Pitfall: D1 batch/DDL
- D1 `d1 execute --file`은 세미콜론 분리 다중문 지원 — 위 파일 그대로 적용 가능.
- `DROP COLUMN`이 D1에서 거부되면 폴백: price 컬럼 방치 + 코드에서 무시 (읽기 쿼리가 명시 컬럼 리스트이므로 잔류 컬럼 무해). planner는 DROP 실패를 치명 오류로扱지 말 것.

## Astro SSR Patterns to Reuse (from Phase 41, no new research needed)
| Pattern | Source | Reuse in Phase 42 |
|---|---|---|
| SSR 가드 + `/auth/consent` 리다이렉트 | submit.astro:6-11 | 유지 (수정 없음) |
| API 401/400 JSON + try/catch 500 | submit.ts:30-55, :149-152 | 새 필드 검증 에러도 동일 400 형식 |
| URL http(s) 검증 | submit.ts:72-79 | screenshot_url에 동일 함수형 패턴 (빈값 허용 분기 추가) |
| D1 fail-soft (catch → 빈 배열) | index.astro:10-20, [id].astro:25-34 | WHERE 추가 후에도 try/catch 유지 |
| desc 200 서버 캡 | submit.ts:67-69 | 유지 (클라이언트 비활성화는 우회 가능하므로 서버 검증 삭제 금지) |
| slug md+D1 중복 회피 | submit.ts:104-121 | 유지 |

## Risks
1. **`Freemium` 무료 필터 제외** (index.astro:511 `includes('무료')`) — 기존 `무료 / 유료` 값은 포함됐으나 `Freemium`은 제외. 시니어 결정에 필터 언급 없음. → Open Question으로 senior 확인 권장.
2. **[id].astro hidden 직접 접근 허용 여부** — CONTEXT가 index WHERE만 요구. 현행 유지(허용) 권장, senior 이견 없으면 그대로.
3. **price_model 필수 + price_detail 선택 INSERT NOT NULL** — `price_model TEXT NOT NULL`로 할지, 코드 검증만으로 할지. 0행이므로 NOT NULL 제약 추가 가능하나, D1 ALTER는 컬럼 제약 변경 불가 → NOT NULL 원하면 테이블 재건. 권장: 제약 없이 코드 검증만 (Phase 41 방식과 일관).
4. **클라이언트 200자 비활성화 우회** — 서버 400이 진실 공급원, 둘 다 유지해야 함 (AGENTS.md 3중 방어 원칙과 일관).

## Environment Availability
| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| wrangler + hugh79757 profile | D1 migrate | ✓ (live probe) | 4.110.0 | — |
| D1 local tool_submissions | verify | ✓ | 0 rows | — |
| D1 remote tool_submissions | verify | ✓ | 0 rows | — |
| Astro SSR (output server) | all pages | ✓ | astro ^5.17.1, adapter ^12.6.12 | — |

## Open Questions (RESOLVED — decided in 42-02 plan, senior to confirm in review)
1. **Freemium + 무료 필터** → Q1→42-02 Task 2 LOCKED CHOICE: matchFree unchanged (Freemium excluded from 무료-only filter).
2. **[id].astro hidden 직접 접근** → Q2→42-02 Task 3 LOCKED CHOICE: 허용 유지 (no status filter on detail query).

## Project Constraints (from AGENTS.md)
- wrangler 호출 시 `env -u CLOUDFLARE_API_TOKEN` 필수 (OAuth profile 우선 적용 목적).
- 증분 수정, 기존 동작 테스트 회귀 금지 (본 phase는 신규 컬럼 추가 위주, 기존 쿼리 SELECT 리스트만 확장).
- 작업 로그: `/Users/twinssn/Desktop/메모 Hugh/logs/YYYYMMDD.md` append (executor/planner 몫).

## Sources
- Repo files read this session: `sql/001_tool_submissions.sql`, `src/pages/api/tools/submit.ts`, `src/pages/tools/submit.astro`, `src/pages/tools/index.astro` (:1-60 + grep), `src/pages/tools/[id].astro` (:1-80 + grep), `wrangler.toml`, `package.json`, `astro.config`, `.planning/phases/41-tools-user-submit/RESEARCH.md`.
- Live probes: wrangler d1 execute local + remote COUNT(*) (0 rows both), grep prerender (0 hits).
- Prior research reused: Phase 41 RESEARCH §2-4 (SSR patterns, TASKS, auth) — 재검증 없이 인용, 변경 없음.

## Metadata
- Confidence: HIGH (전수 실측 + live DB probe). Freemium 필터·hidden 직접접근 2건만 senior 확인 필요.
- Valid until: 2026-10-23 (D1/astro 안정 스택).
