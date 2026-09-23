---
phase: 42-tools-phase1-adjust
plan: 01
subsystem: database
tags: [d1, sqlite, astro-ssr, wrangler, tools-submit, migration]

# Dependency graph
requires:
  - phase: 41-tools-user-submit
    provides: tool_submissions DDL + submit.ts baseline (price TEXT 단일 컬럼, 153-line API)
provides:
  - 최종 스키마 진실원 (001: price_model/price_detail/category_custom/screenshot_url, price 제거)
  - 002 마이그레이션 local+remote 적용 증거 (DROP COLUMN 성공, 0행 무손실)
  - submit.ts 신규 필드 검증 + INSERT 교체 (42-02 프론트가 의존하는 API 계약)
affects: [42-02 submit/index/detail astro 조정, tools-listing, tools-detail]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 1231
  tasks: 2
  commits: 3
  plan_head_before: d662ad3a63f36a290a8c98d33c49b3bc879e0503

# Tech tracking
tech-stack:
  added: []
  patterns: [D1 ALTER TABLE migration with backfill CASE rule, server-400-as-source-of-truth kept]

key-files:
  created: [sql/002_tools_phase1_adjust.sql]
  modified: [sql/001_tool_submissions.sql, src/pages/api/tools/submit.ts]

key-decisions:
  - "DROP COLUMN price 성공 (local+remote) — fallback(잔류 무시) 불필요"
  - "price_model NOT NULL 제약 없음 — 코드 검증만 (RESEARCH Risk 3 권장 준수)"
  - "category_custom required 강제 없음 — 시니어 결정에 required 규칙 없음"

patterns-established:
  - "D1 마이그레이션: ADD COLUMN ×N + backfill UPDATE + DROP COLUMN 단일 파일, local→remote→PRAGMA verify 순"
  - "submit.ts 선택 URL 필드 패턴: empty-skip 분기 + url 필드 동일 http(s) 체크 재사용"

requirements-completed: [REQ-42-01, REQ-42-02, REQ-42-04, REQ-42-05, REQ-42-06]

coverage:
  - id: D1
    description: "신규 환경에서 001 파일 하나로 최종 스키마 구성 (price 없음, 4 신규 컬럼 있음)"
    requirement: "REQ-42-02"
    verification:
      - kind: other
        ref: "grep -cE '^\\s*price TEXT' sql/001_tool_submissions.sql → 0; grep price_model → 1 hit (price_model/price_detail lines)"
        status: pass
    human_judgment: false
  - id: D2
    description: "기존 local/remote D1의 price 값 보존 규칙 적용 (0행, DROP COLUMN 성공, 4 컬럼 PRAGMA 확인)"
    requirement: "REQ-42-02"
    verification:
      - kind: other
        ref: "wrangler d1 execute --local/--remote PRAGMA table_info → price_model/price_detail/category_custom/screenshot_url both; remote COUNT(*)=0"
        status: pass
    human_judgment: false
  - id: D3
    description: "POST /api/tools/submit price_model 3택 필수 + price_detail/category_custom/screenshot_url 처리, description 200 캡 유지"
    requirement: "REQ-42-02"
    verification:
      - kind: other
        ref: "npm run build → Complete; grep price_model submit.ts → 4; grep screenshot_url → 6; standalone price → 0 hits"
        status: pass
    human_judgment: false

# Metrics
duration: 4min
completed: 2026-09-23
status: complete
---

# Phase 42 Plan 01: DDL 정합 + API 검증 Summary

**001 최종 스키마 확정 + 002 마이그레이션 local/remote 적용(DROP COLUMN 성공) + submit.ts 4 신규 컬럼 검증·INSERT 교체, 빌드 통과**

## Performance

- **Duration:** 4min
- **Started:** 2026-09-23T04:54:28Z
- **Completed:** 2026-09-23T04:57:39Z
- **Tasks:** 2/2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- 001 CREATE TABLE 최종 스키마: `price TEXT` 제거 → `price_model/price_detail`, `category_custom`·`screenshot_url` 추가, `status DEFAULT 'published'` 유지
- 002 마이그레이션 신규 작성 (RESEARCH 권장 파일 verbatim) + local/remote 적용 성공 — DROP COLUMN price 양쪽 성공, fallback 불필요, 0행 무손실
- submit.ts: price_model 필수 3택(무료/Freemium/유료) 400 검증, price_detail/category_custom 선택 처리, screenshot_url 선택 http(s) 검증, INSERT 4 신규 컬럼 교체
- 기존 계약 유지: description 200자 400, ALLOWED_CATEGORIES 8개, tasks max-5+TASKS, slug md+D1 dedup 전부 untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: 001 최종 스키마 갱신 + 002 마이그레이션 작성·적용** - `1a490996` (feat)
2. **Task 2: submit.ts 신규 필드 검증 + INSERT 교체** - `7317345f` (feat)

**Plan metadata:** measured `git rev-list --count d662ad3a..HEAD` = 3 — 내역: 1a490996 + 7317345f (본 플랜 2건) + e9d1ccf7 (동일 브랜치 동시 작업 phase-40 compass 커밋, 본 플랜 범위 외)

## Files Created/Modified

- `sql/002_tools_phase1_adjust.sql` (created) - ADD COLUMN ×4 + price backfill CASE 규칙 + DROP COLUMN price
- `sql/001_tool_submissions.sql` (modified) - 최종 스키마로 갱신 (신규 환경 1파일 구성용)
- `src/pages/api/tools/submit.ts` (modified) - 신규 필드 검증 + INSERT 교체 (+27/-4)

## Decisions Made

- DROP COLUMN price 성공 → RESEARCH §Pitfall fallback(잔류 컬럼 무시) 미사용. local PRAGMA 20컬럼(price 없음·신규 4개 있음), remote 동일 + COUNT 0 확인
- price_model DB NOT NULL 제약 미적용 — RESEARCH Risk 3 권장(코드 검증만, Phase 41 방식 일관) 준수
- category_custom required 강제 안 함 — 시니어 결정은 "기타 선택 시 input 표시"만 명시, required 규칙 없음. required 강제 시 정당한 클라이언트가 400으로 막힐 수 있어 미적용

## Deviations from Plan

None - plan executed exactly as written. (DROP COLUMN 성공으로 plan 내 fallback 분기 미발동 — 분기 조건 자체가 발생하지 않은 것이므로 deviation 아님.)

## Issues Encountered

- **동일 브랜치 동시 커밋:** Task 1 커밋(1a490996)과 Task 2 커밋(7317345f) 사이에 타 세션의 phase-40 커밋 e9d1ccf7 (`pipeline/threads/fact_gate.py`, `scripts/threads/main_v3.py`)이 동일 브랜치(`agent/phase40-compass-diversification`)에 적재됨. 본 플랜 파일과 무관(`git diff --name-only 1a490996 e9d1ccf7` = pipeline 2파일만)하여 무시하고 Task 2를 그 위(`e9d1ccf7` 자식 `7317345f`)에 정상 커밋. 본 플랜 커밋은 sql 2 + submit.ts 1 파일만 포함 — 범위 침범 없음.
  - 근거: `git log --oneline d662ad3a..HEAD` = 7317345f / e9d1ccf7 / 1a490996; `git show --stat HEAD` = submit.ts 1파일; `git show --stat 1a490996` = sql 2파일

## Verification Output (근거)

- Local PRAGMA `"name"` 목록: id/user_id/slug/name/url/category/description/korean_support/difficulty/use_cases/tags/tasks/detail_markdown/status/created_at/updated_at/**price_model/price_detail/category_custom/screenshot_url** (price 없음)
- Remote PRAGMA: 동일 20컬럼. Remote `SELECT COUNT(*) → c: 0`
- Remote apply 응답: `Total queries executed: 6`, `changed_db: true`, `success: true` (DROP COLUMN 포함 6문 전부 성공)
- 001: `grep -c "price_model"` → 1 (price_model/price_detail 2줄), `grep -cE "^\s*price TEXT"` → 0
- submit.ts: `grep -c price_model` → 4, `grep -c screenshot_url` → 6, standalone `price` → 0 hits
- `npm run build` → `[build] Complete!` (Server built 10.03s)
- 가드: `git diff --stat HEAD~2 HEAD -- src/content/tools/ scripts/tools_collector.py` → empty. Phase 3 파일 미생성 (R2/my/PUT/DELETE 없음). `network_schema.sql`·`persona_migration.sql` untouched
- Stub 스캔: `grep -nE "TODO|FIXME|placeholder|coming soon|not available" submit.ts 002` → 0건

## User Setup Required

None - no external service configuration required.

## Threat Flags

None — 신규 입력 필드(screenshot_url)는 http(s) 화이트리스트 검증 적용, price_model은 3택 enum 검증. 새 네트워크 엔드포인트·인증 경로·스키마 신뢰경계 변경 없음 (동일 테이블 컬럼 교체).

## Next Phase Readiness

- 42-02 진행 가능: DDL 진실원 확정(local+remote 일치) + API가 신규 필드 수신 가능. 프론트(submit.astro 라디오/input, index/[id] `price_detail || price_model` 표시, `WHERE status='published'`)가 이 계약에 맞춰 구현하면 됨
- 주의: 동일 브랜치에 타 세션(phase-40) 작업이 병행 중 — 42-02 실행 전 `git log --oneline -5`로 HEAD 위치 재확인 권장

---
*Phase: 42-tools-phase1-adjust*
*Completed: 2026-09-23*

## Self-Check: PASSED

- SUMMARY file exists, 002 file exists, commits 1a490996 + 7317345f exist (all FOUND)
- No file deletions in plan commits; tools/collector guard empty; build Complete
