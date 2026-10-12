---
phase: 42-tools-phase1-adjust
plan: 02
subsystem: tools-frontend
tags: [astro-ssr, d1, tools-submit, tools-listing, tools-detail, e2e]
requires:
  - phase: 42-tools-phase1-adjust
    provides: submit.ts new-field API contract (price_model 3택 + screenshot_url 검증)
provides:
  - submit/index/detail 프론트 6개 locked 결정 정합 (D-01..D-06 사용자 가시 절반)
  - E2E 8-case curl matrix green 증거 (pages-dev :4321 + 코드 assert)
affects: [tools-listing, tools-detail, senior-review-open-questions]
tech-stack:
  added: []
  patterns: [price display rule price_detail || price_model, published-only index WHERE, hidden-direct-allowed detail]
key-files:
  modified: [src/pages/tools/submit.astro, src/pages/tools/index.astro, src/pages/tools/[id].astro]
key-decisions:
  - "matchFree includes('무료') unchanged — Freemium 무료-only 필터 제외 (Open Q1 LOCKED, senior 확인용)"
  - "[id] status 필터 없음 — hidden 직접 URL 접근 허용 유지 (Open Q2 LOCKED, senior 확인용)"
  - "E2E 인증 케이스는 wrangler pages dev + .dev.vars + 임시 users (41-02 전례) — astro dev는 SESSION_SECRET 미주입으로 401만 가능"
actuals:
  tokens: 30000
  tasks: 3
  commits: 3
  plan_head_before: 4997f641af0ebdae7070985ae426d241a8fa1d6d
requirements-completed: [REQ-42-01, REQ-42-02, REQ-42-03, REQ-42-04, REQ-42-05, REQ-42-06]
status: complete
---

# Phase 42 Plan 02: 폼·목록·상세 프론트 조정 + 빌드/E2E Summary

**submit 라디오+토글+카운터, index published-only, detail 동일 표시 — 빌드 green + E2E 8-case matrix green (pages-dev :4321)**

## Performance

- **Duration:** ~15min
- **Started:** 2026-09-23T05:00:28Z
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments

- submit.astro: 가격 select → price_model 라디오(무료/Freemium/유료) + price_detail input, 기타→희망카테고리 토글(category_custom), screenshot_url input, desc N/200 카운터(초과 시 빨강+제출 비활성화), CAFE_URL 상수 1회 정의(cafe href JS 주입 + shareText), payload price_model/price_detail/category_custom/screenshot_url, 미리보기 price_detail||price_model
- index.astro: `WHERE status='published'` + SELECT price_model/price_detail, 표시 규칙 `price_detail || price_model`, data-price 동일 계산값(필터 일관), matchFree unchanged
- [id].astro: SELECT 4 신규 컬럼, 동일 표시 규칙 + screenshot_url 링크 행(있을 때만), status 필터 없음 유지
- E2E 8-case matrix 전부 green (아래 Verification Output), 테스트 잔해 전량 정리 (D1 0행, 임시 users DROP, .dev.vars 삭제)

## Task Commits

1. **Task 1: submit.astro 폼 조정** - `31bbed5d` (feat)
2. **Task 2: index.astro WHERE + 표시 규칙** - `2df90204` (feat)
3. **Task 3: [id].astro 표시 규칙 + 빌드/E2E** - `5bfb3082` (feat)

**Plan metadata:** measured `git rev-list --count 4997f641..HEAD` = 3 (본 플랜 3건, 범위 외 혼입 없음)

## Files Created/Modified

- `src/pages/tools/submit.astro` (modified, +60/-12) - 폼 교체 + 스크립트 계약 갱신
- `src/pages/tools/index.astro` (modified, +3/-3) - WHERE + 표시 규칙
- `src/pages/tools/[id].astro` (modified, +8/-2) - 표시 규칙 + 스크린샷 링크

## Decisions Made

- Open Q1 LOCKED: matchFree `includes('무료')` 그대로 — Freemium은 무료-only 필터에서 제외. 시니어 결정에 필터 규칙 언급 없고 최소변경 원칙. senior 리뷰 확인용으로 flag
- Open Q2 LOCKED: [id] 쿼리에 status 필터 추가 안 함 — hidden 행 직접 URL 접근 200 허용 유지. CONTEXT Step 4가 index WHERE만 요구. senior 리뷰 확인용으로 flag
- E2E 방식: 인증 필요 케이스(400×3, 201)는 `wrangler pages dev dist --port 4321 --compatibility-flag=nodejs_compat` + `.dev.vars`(SESSION_SECRET) + 임시 users 테이블 — 41-02 전례 동일. astro dev는 SESSION_SECRET 미주입이라 세션 검증 불가(401까지만)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] screenshot 링크가 상세에 미렌더 (잘못된 위치에 삽입)**
- **Found during:** Task 3 E2E detail assert
- **Issue:** `</div>\n    </div>` 2줄 매칭으로 삽입한 스크린샷 블록이 히어로가 아닌 한국어 활용법 useCases map 내부에 들어감 — korean_support=0 행에서 조건부로 가려져 E2E에서 링크 0건
- **Fix:** 블록을 map 내부에서 제거(원복) 후 히어로 종료 `</div>` + `<!-- 한국어 활용법 -->` 앵커로 정확히 재배치, rebuild 후 detail 재검증(스크린샷 보기 + e2e42.png 확인)
- **Files modified:** src/pages/tools/[id].astro
- **Commit:** 5bfb3082에 포함

**2. [Rule 3 - Blocking] pages dev 기동 실패 (nodejs_compat 누락) + API 경로 308**
- **Found during:** Task 3 E2E 서버 기동
- **Issue:** `wrangler pages dev dist`가 `Could not resolve "fs"`로 기동 불가 — worker가 nodejs_compat 필요. 또한 `/api/tools/submit` (슬래시 없음)은 308 리다이렉트
- **Fix:** `--compatibility-flag=nodejs_compat` 추가 기동 (정상 Ready), curl은 trailing-slash `/api/tools/submit/` 사용
- **Files modified:** 없음 (실행 플래그/호출 경로만)
- **Commit:** 해당 없음

## Verification Output (근거)

- `npm run build` → `[build] Complete!` (3회: Task별 각 1회, 최종 12:13 Server 32.19s)
- submit.astro: `grep -c CAFE_URL` → 3, `price_model` → 6, `category_custom` 1 (payload 키) + `f-category-custom` input, `screenshot_url` 1 (payload 키) + `f-screenshot-url` input. HTML fallback href 1건 잔류(SSR no-JS 대비, JS가 CAFE_URL로 통일 주입 — script 로직 내 하드코딩 0)
- index.astro: `WHERE status` → 1 (escaped `\'published\'`, SQL 전송 시 `='published'`), `price_model` → 3, matchFree `includes('무료')` unchanged (line 511)
- [id].astro: SELECT 4 신규 컬럼 1행, 표시 규칙 + screenshotUrl 매핑 + 조건부 링크 렌더
- E2E matrix (pages-dev :4321, 코드 assert 전부 일치):
  - CASE1 401 unauth POST → `401 {"error":"로그인이 필요합니다."}`
  - CASE2 400 bad price_model=WRONG → `400 {"error":"가격 모델을 선택해주세요. (무료/Freemium/유료)"}`
  - CASE3 400 screenshot_url=ftp:// → `400 {"error":"올바른 스크린샷 URL을 입력해주세요. (http:// 또는 https://)"}`
  - CASE4 400 desc 201자 → `400 {"error":"설명은 200자 이내로 입력해주세요."}`
  - CASE5 201 valid (Freemium + 월 9900원부터 + 기타/E2E42 희망 + screenshot) → `201 {"ok":true,"slug":"e2e42-freemium-widget"}`, D1 row 4 신규값 + status=published 확인
  - CASE6 list → 200 + MAKER 2건 + `월 9900원부터` + `data-price="월 9900원부터"`
  - CASE7 detail → 200 + MAKER 1 + 가격 2건 + `스크린샷 보기` + e2e42.png
  - CASE8 hidden 직접 접근 → 200 (Q2 locked 선택 문서화) + 목록 내 hidden slug 0건 (published-only 증거) + published slug 2건
  - CASE9 unknown slug → 404; md control `/tools/chatgpt-work/` → 200
- 가드: `git diff --stat -- src/content/tools/ scripts/tools_collector.py` → empty. Phase 3 파일 없음 (R2/my/PUT/DELETE 미생성)
- 정리: 테스트 slug 2건 삭제 (`e2e42-freemium-widget`, `e2e42-hidden-tool`), 임시 users DROP, `.dev.vars` 삭제, D1 `COUNT(*)=0` 확인. 서버 프로세스 kill

## Deleted Test Slugs (정리 완료)

- `e2e42-freemium-widget` (CASE5 201 생성 → 검증 후 DELETE)
- `e2e42-hidden-tool` (CASE8 직접 INSERT → 검증 후 DELETE)

## Open Questions for Senior Review (flag)

1. **Freemium + 무료 필터:** `matchFree` unchanged이므로 Freemium 도구는 무료-only 체크 시 제외. 의도된 동작인지 senior 확인
2. **hidden 직접 접근:** `[id]` status 필터 없음이므로 hidden 행 URL 직접 접근 시 200 렌더. 목록에서는 제외됨을 E2E로 입증. 정책 확인

## Threat Flags

None — 신규 입력(price_detail/category_custom/screenshot_url)은 submit.ts 서버 검증이 진실 공급원(42-01 완료). 클라이언트 변경은 선방어만. 새 네트워크 엔드포인트·인증 경로 없음.

## Next Phase Readiness

- 42-02 완료로 Phase 2 사용자 가시 절반 정합. 잔여: 시니어 리뷰 (Open Q 2건 + 42-01/02 전체). Phase 3(R2/my/PUT-DELETE) 착수 금지 유지 (D-06)
- 주의: `.wrangler/state/...sqlite` tracked 파일이 로컬 D1 검증으로 수정됨 — 커밋하지 않고 둠 (41-02 전례 동일)

---
*Phase: 42-tools-phase1-adjust*
*Completed: 2026-09-23*

## Self-Check: PASSED

- SUMMARY file exists (FOUND)
- Commits 31bbed5d + 2df90204 + 5bfb3082 exist (FOUND, `git log 4997f641..HEAD` 3건)
- No file deletions in plan commits; tools/collector guard empty; final build Complete
- D1 local COUNT 0, .dev.vars removed, pages-dev killed
