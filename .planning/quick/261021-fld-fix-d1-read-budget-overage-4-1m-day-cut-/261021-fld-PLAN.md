---
phase: 261021-fld-fix-d1-read-budget-overage
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/pages/index.astro
  - src/components/home/ToolsSection.astro
  - src/pages/global.astro
  - sql/
  - scripts/run_pipeline.py
  - scripts/run_pipeline_with_notify.py
  - scripts/build_watchdog.py
  - scripts/cfnew.py
  - docs/state.md
autonomous: true
requirements:
  - AIK24-D1-READ-01
  - AIK24-PIPE-ALERT-01
  - AIK24-BW-01
  - AIK24-D1-ALERT-02
estimate:
  tasks: 5
  confidence: high

must_haves:
  truths:
    - "D1 일일 읽기가 4,195,200행(83.9%)에 이르렀던 원인을 코드 수준에서 제거한다 — 서빙측(SSR) 페이지뷰당 수천 행 읽기가 근본원인이다."
    - "aikorea24 홈 1,733행/뷰 → 9행/뷰, /global/ 19,218행/뷰 → 인덱스 사용으로 축소 (계측으로 확인)"
    - "emdash /posts COUNT(*) 1,513행/뷰 → 캐시 경유로 요청당 읽기 대폭 감소 (계측으로 확인)"
    - "流水线이 브리핑 0건을 성공으로 보고하지 않는다 — 0건이면 errors 에 들어가 exit code 가 0 이 아니다, 텔레그램 문구도 실건수를 말한다"
    - "D1 50/70/90% 경보 채널(muse-cli)이 실제 전달된다 — 10-18 이후 62회 실패 상태 해소"
    - "build-watchdog 가 실제로 존재하는 산출물(Astro 7 SSR 구조)을 검사한다 — 'dist/index.html 없음' 상태로 ok 를 내지 않는다"
    - "80% 가드에 의한 새벽 잡 차단은 읽기 절감 후 재발하지 않는다"
  artifacts:
    - "src/pages/index.astro · src/components/home/ToolsSection.astro — UNION ALL 분기별 LIMIT + 인덱스"
    - "src/pages/global.astro — news(category, created_at DESC) 인덱스 사용"
    - "src/pages/posts/index.astro (emdash) — COUNT 캐시"
    - "scripts/verify_pagination_click.mjs 는 이전 quick task 산출물 — 본 건과 무관"
    - "scripts/run_pipeline.py · scripts/run_pipeline_with_notify.py — 실산출 브리핑 건수 보고"
    - "scripts/build_watchdog.py — Astro 7 산출물 경로 검사"
    - "scripts/cfnew.py — muse-cli 절대경로 해석"
    - "docs/state.md — 작업 스테이트먼트"
  key_links:
    - "SSR Worker(env.DB) → D1 rowsRead 과금: 로컬 가드(check_quota)는 cfnew.sql() 경로에만 걸려 있어 서빙 경로는 무방비였다"
    - "홈 UNION ALL + ORDER BY id DESC LIMIT 1 → 각 분기 전체 스캔 → 브랜치별 ORDER BY updated_at DESC LIMIT + 인덱스로 9행/뷰"
    - "emdash COUNT(*) 1,513행 → 인덱스만으로는 줄지 않음(인덱스 엔트리 전량 읽기) → 캐시가 유일한 레버"
---

<objective>
D1 일일 읽기 한도 초과(2026-10-20 UTC 4,195,200행 = 83.9%, 한도 5,000,000)를 근본원인부터 해결한다.

Purpose: 2026-10-21 새벽 D1 가드가 80% 임계에서 `news-unified`(05:30)과 `tools-collector`(06:00)를 차단해 뉴스 수집이 0건이 되고, 07:00 파이프라인이 브리핑 0건을 만들었다. 가드가 막은 것은 증상이고, 진짜 원인은 **SSR Worker가 페이지뷰마다 수천 행을 읽는 것**이다(3일 교차검증: 91.2% / 98.6% / 92.3%).

Output:
1. aikorea24 홈 + /global/ 서빙 읽기 축소 (SQL + 인덱스 + 마이그레이션)
2. emdash /posts COUNT 캐시화
3. 가짜 성공 알림 수정 (실산출 브리핑 건수 보고)
4. muse-cli 경보 채널 복구
5. build-watchdog 산출물 검사 경로 수정
6. D+3 재측정 실행 + 최종 계측 + 기록 + 커밋
</objective>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@docs/d1-budget.md
@docs/d1-remeasure-plan-20261021.md

# 기준선 — D+3 재측정 (2026-10-21 실행, 읽기 전용 GraphQL 조회)

    UTC 일자            읽기       한도%
    2026-10-16     2,744,804     54.9%
    2026-10-17     2,107,481     42.1%
    2026-10-18     2,957,586     59.2%
    2026-10-19     3,494,156     69.9%
    2026-10-20     4,195,200     83.9%   ← 한도 초과 임계(80%) 돌파
    2026-10-21       386,330      7.7%   (진행 중)

DB별(10-20): aikorea24-db 2,055,775 · aikorea24-emdash-db 2,137,095 · taiwan-news-db 2,330
단가(10-20): aikorea24-db 281.3행/요청 · emdash-db 841.4행/요청

# 근본 원인 (읽기 전용 조사로 확정)

| 소비원 | 단가 | 근거 |
|---|---|---|
| aikorea24 홈 `/` | 1,733행/뷰 | 671(briefings) + 1,062(ToolsSection UNION ALL). `meta.rows_read` 실측. 분 단위 히스토그램에서 1,733의 정수배가 47~81% 설명 |
| emdash `/posts` COUNT(*) | 1,513행/뷰 | `SELECT COUNT(*) FROM ec_posts ...` 실측 rows_read 1,513 = 게시물 1,512건 인덱스 엔트리 전량 |
| aikorea24 `/global/` | 19,218행/뷰 | EXPLAIN: SEARCH news USING INDEX idx_news_category + TEMP B-TREE |
| aikorea24 `/briefing/` | 846행/뷰 | 746+100 |
| 로컬 스크립트(REST) | 32만행/일 | 10-20 03:19Z·03:39Z 2분 집중 229,645행 = PIPE-05 개발 중 N+1(커밋 b666d7e7 10:53 수정) → 일회성 |

# 가드 공백 [구조]

`check_quota()`는 `cfnew.sql()`(로컬 스크립트 경로)에만 걸려 있다. **Worker SSR(env.DB) 경로는 가드를 통과하지 못한다** — 근본원인 경로가 가드 밖에 있음.
</context>

<tasks>

<task type="auto">
  <name>Task 1: aikorea24 홈 + /global/ 서빙 읽기 축소 (SQL + 인덱스 + 마이그레이션)</name>
  <files>src/pages/index.astro, src/components/home/ToolsSection.astro, src/pages/global.astro, sql/</files>
  <action>
  홈: `src/components/home/ToolsSection.astro:26` + `src/pages/index.astro:26` 의 `UNION ALL` 각 분기가 `ORDER BY id DESC LIMIT 1` 로 끝나 분기 전체 스캔이 강제된다. 각 분기를 `ORDER BY updated_at DESC LIMIT 8` 로 감싸고, 인덱스 `idx_briefings_status_id(status,id)` · `tool_submissions(status,updated_at)` 를 추가한다. 조사 단계에서 수정안 쿼리를 직접 실행해 **1,733 → 9행/뷰** 를 이미 계측 검증했다.
  /global/: `src/pages/global.astro:11` — `CREATE INDEX idx_news_category_created ON news(category, created_at DESC)` 적용 후 TEMP B-TREE 제거를 EXPLAIN QUERY PLAN 으로 확인.
  마이그레이션: 저장소의 기존 관례(sql/ 디렉터리 + schema.sql)를 먼저 읽고 같은 방식으로 `CREATE INDEX IF NOT EXISTS` 를 넣은 뒤 원격 D1(aikorea24-db / 3f4cedde-eabc-4d7c-b459-f6abe8733767 / 계정 7eb1b8cd178de269758ec94b2e03330b)에 적용. 토큰은 `~/.env.common` 의 `CF_MIGRATE_TOKEN` 을 환경변수로만 읽어 사용하고 값은 출력·기록하지 않는다(세션 주입 CLOUDFLARE_API_TOKEN 은 다른 계정이라 auth 10000 — 사용 금지).
  배포는 프로젝트의 `scripts/deploy.sh` 사용. 커밋은 오케스트레이터가 중앙 처리하므로 여기서는 하지 않는다.
  </action>
  <verify>
    <automated>npm run build && npm run typecheck 2&gt;&amp; | tail -5 ; wrangler d1 execute aikorea24-db --remote --command "EXPLAIN QUERY PLAN &lt;홈 쿼리&gt;" ; git status --porcelain</automated>
  </verify>
  <done>
  - 홈 쿼리 rows_read 1,733 → 9, /global/ 쿼리 TEMP B-TREE 제거 — 계측표로 남김
  - 인덱스 3종이 원격 D1에 존재(스키마 확인)
  - build 성공, typecheck 오류 delta 0, 배포 Version ID 확보
  </done>
</task>

<task type="auto">
  <name>Task 2: emdash /posts COUNT(*) 캐시화</name>
  <files>~/projects2/aikorea24emdash/src/pages/posts/index.astro</files>
  <action>
  `SELECT COUNT(*) AS c FROM ec_posts WHERE status='published' AND deleted_at IS NULL` 가 요청당 1,513행을 읽는다. 인덱스만으로는 줄지 않으므로 캐시가 유일한 레버. (a) 모듈 TTL 캐시 / (b) 사전집계 카운터 테이블 / (c) Cache API 중 저장소 관례에 맞는 방식을 택하고, 발행 시 무효화 경로를 확인해 staleness bound를 명시한다. 같은 COUNT 패턴이 category/tag/index 에도 있는지 grep 으로 확인해 함께 처리.
  주의: 같은 파일에 이미 적용된 `.pagination { position: relative; z-index: 10; }` (AIK24-EMDASH-16) 과 그 한국어 주석을 반드시 보존한다.
  </action>
  <verify>
    <automated>cd ~/projects2/aikorea24emdash &amp;&amp; npm run build &amp;&amp; npm run typecheck 2&gt;&amp; | tail -5 ; git diff --stat</automated>
  </verify>
  <done>
  - before/after rows_read 계측표 존재(따뜻한 캐시 / 차가운 캐시)
  - 라이브 "전체 N편" 카운트가 정상 표시
  - 배포 Version ID 확보
  </done>
</task>

<task type="auto">
  <name>Task 3: 가짜 성공 알림 · muse-cli 경보 복구 · build-watchdog 산출물 경로</name>
  <files>scripts/run_pipeline.py, scripts/run_pipeline_with_notify.py, scripts/build_watchdog.py, scripts/cfnew.py</files>
  <action>
  (a) run_pipeline.py — 실제 저장된 브리핑 수를 선정 수와 분리해 집계하고, 0건이면 summary["errors"] 에 넣어 exit code 를 0이 아니게 만든다(기존 exit code 관례를 따름). run_pipeline_with_notify.py — 성공 문구에 실건수를 넣고 0건일 때 발행 완료라고 하지 않는다.
  (b) cfnew.py:140 — `muse-cli` 호출을 shutil.which() → 알려진 절대경로 순으로 해석. "실패해도 무시" 동작은 유지하되 무엇을 찾았는지 메시지에 남긴다.
  (c) build_watchdog.py — Astro 7 SSR 구조에서 실제로 존재하는 산출물(dist/client/index.html, dist/server/index.mjs)을 검사. 산출물이 없으면 fail 처리.
  </action>
  <verify>
    <automated>npm test 2&gt;&amp; | tail -5 ; npm run typecheck 2&gt;&amp; | tail -5 ; git diff --stat</automated>
  </verify>
  <done>
  - 3개 수정 모두 diff 로 확인 가능, 테스트/타입체크 회귀 없음
  - muse-cli 해석이 실제 바이너리 경로를 찾는 것을 확인
  </done>
</task>

<task type="auto">
  <name>Task 4: 스케줄 이동 여부 결정 + D+3 재측정</name>
  <files>launchd/*.plist (조건부)</files>
  <action>
  D+3 재측정 2개 명령은 **이 태스크 시작 전에 이미 실행 완료**했다(`--history 6 --by-db`, `--unit 6`, 기준선 위 표 참조). 결과를 문서에 반영한다.
  스케줄: `news-unified` 05:30 → 07:30 으로 옮기면 **07:00 파이프라인보다 뒤에 수집이 돌아간다** = 새 뉴스가 파이프라인에 반영되지 않는 역전이 생긴다. 읽기 절감으로 80% 게이트가 더 이상 걸리지 않게 되면 스케줄을 옮길 필요도, 해롭지도 않다. → **읽기 절감 후 1~2일 실측으로 게이트 재발 여부를 확인한 뒤, 재발하면 그때만 이동한다**를 기본으로 하고, 즉시 이동이 필요하면 플래시백 Plist 병합(plutil -insert) 방식으로 05:30 → 06:40(UTC 자정 +40분, 07:00 파이프라인 이전) 로 옮긴다. 어떤 선택을 하든 07:00 파이프라인이 06:40 수집 이후에 도는 순서를 깨지 않아야 한다.
  </action>
  <verify>
    <automated>python3 scripts/d1_usage_report.py --history 6 --by-db 2&gt;&amp; | tail -12 ; launchctl list | grep -i aikorea24</automated>
  </verify>
  <done>
  - 스케줄 결정 근거가 문서에 남음(읽기 절감으로 충분 / 또는 이동 필요 + 그 시각)
  - 07:00 파이프라인 선후 순서가 깨지지 않음을 명시
  </done>
</task>

<task type="auto">
  <name>Task 5: 최종 검증 + 기록 + 커밋</name>
  <files>docs/state.md, .planning/STATE.md</files>
  <action>
  최종 계측(읽기 전용): `python3 scripts/d1_usage_report.py --history 6 --by-db` 를 다시 돌려 10-21 UTC 일의 합계 추이를 확인한다. 같은 시간대(10-20 83.9% 구간) 대비 감소 여부를 산출한다.
  `docs/state.md` 는 이 저장소에 `scripts/state_prepend.py` 가 **있다**(global AGENTS.md §6) — 반드시 `python3 scripts/state_prepend.py --report <파일>` 로만 추가한다. `open(p,'w').write(...)` 직접쓰기 금지(2026-10-14 6,550줄 · 2026-10-17 2,805줄 소실 사고).
  보고 형식: 3분법([검증됨]/[부분검증]/[검증불가]) + 근거 + 산출 근거가 붙은 숫자 + [PRODUCTION CODE]/[TEST CODE]/[CONFIG] 구분 + 잔존 위험.
  커밋: 오케스트레이터가 중앙 처리. 00:00 UTC 지나서 읽기 잔여가 있으면 다음 날 게이트 재발 가능성도 잔존 위험에 명시.
  </action>
  <verify>
    <automated>python3 scripts/d1_usage_report.py --history 6 --by-db 2&gt;&amp; | tail -10 ; git log --oneline -3 ; git status --porcelain</automated>
  </verify>
  <done>
  - 절감 전/후 계측표와 근거가 docs/state.md 에 있음
  - 잔존 위험 섹션 존재
  - 커밋 존재, 워킹 트리 clean(잡이 만든 로그 변경 제외)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| 트래픽 → SSR Worker → D1 | 크롤러·사용자 요청 1건이 D1 과금 행을 수천 행까지 늘린다. 가드(`check_quota`)는 이 경로에 없음 |
| 로컬 스크립트 → D1 | `cfnew.sql()` 경로만 가드 대상. 측정·리포팅 쿼리도 예산을 먹는다 |
| ad-network / 스케줄러 → 파이프라인 | 가드가 잡을 중단시키면 산출 0건이 조용히 나오고, 성공 알림까지 "발행 완료"로 나간다 |

## Threat Register

| ID | Category | Severity | Disposition | Mitigation |
|---|---|---|---|---|
| T-01 | Denial of Service (가드 오작동) | high | mitigate | 읽기 절감으로 80% 게이트 미도달. 스케줄 이동은 수집→파이프라인 순서를 깨지 않는 시각으로만 |
| T-02 | Information Disclosure (과잉 조회) | medium | mitigate | 페이지당 rows_read 계측(1,733→9 등)을 빌드/배포 게이트로 삼음 |
| T-03 | Tampering (가짜 성공) | high | mitigate | 브리핑 0건이면 errors + 비정상 exit + 텔레그램 실건수 문구 |
| T-04 | Repudiation (증거 부재) | medium | mitigate | 계측표를 커밋된 문서와 회귀 스크립트에 남김 |
| T-05 | Elevation of Privilege (가드 우회) | medium | accept | Worker SSR 가드 봉합은 전 경로 진입점 변경(고위험)이라 이번 범위 밖 — 잔존 위험으로 명시 |
| T-06 | Tampering (보고서 은폐) | medium | mitigate | 3분법 분류 강제, 숫자 산출 근거 명시, 잔존 위험 섹션 필수 |

## Policy guardrails

- 수익 구조 변경 금지(광고·publisher id·발행 모드 무변경)
- 가드 우회·임계값 하향 금지(한도 5,000,000 유지)
- 브리핑 0건 상태를 성공으로 보고하는 코드 금지
</threat_model>

<verification>
1. `npm run build` + `npm run typecheck` (aikorea24, emdash 양쪽) — 신규 오류 0
2. Task 1·2 계측표 — before/after rows_read 실측값
3. Task 3 세 수정 — diff + 테스트 결과
4. `python3 scripts/d1_usage_report.py --history 6 --by-db` — 절감 확인
5. `docs/state.md` 가 `scripts/state_prepend.py` 로만 갱신되었음(라인 수 감소 없음)
6. `git status --porcelain` — 미커밋 변경 없음(스케줄 잡이 만든 로그 파일 제외)
</verification>

<success_criteria>
- D1 일일 읽기가 80% 게이트 미도달로 내려간다(절감 전/후 계측 근거 있음)
- 파이프라인이 브리핑 0건을 성공으로 보고하지 않는다
- D1 3단계 경보 채널이 실제 전달된다
- build-watchdog 가 실제로 존재하는 산출물을 검사한다
- 수집→파이프라인 실행 순서가 깨지지 않는다
- 커밋된 회귀·계측 근거와 잔존 위험이 docs/state.md 에 남는다
</success_criteria>

<output>
Create `.planning/quick/261021-fld-fix-d1-read-budget-overage-4-1m-day-cut-/261021-fld-SUMMARY.md` when done
</output>
