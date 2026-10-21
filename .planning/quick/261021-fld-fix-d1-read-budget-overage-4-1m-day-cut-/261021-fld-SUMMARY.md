---
status: complete
quick_id: 261021-fld
slug: fix-d1-read-budget-overage-4-1m-day-cut-
date: 2026-10-21
commits:
  - 24b64ee1
  - 31a32e19
  - dbdbf8b
deploy_versions:
  aikorea24: db104a18-057b-4cf1-b478-2325f9fa8538
  aikorea24emdash: 9e6001ce-7d52-4710-b288-599342477697
files_modified:
  - src/pages/index.astro
  - src/components/home/ToolsSection.astro
  - src/pages/global.astro
  - schema.sql
  - sql/007_d1_read_reduction.sql
  - scripts/d1_read_measure.py
  - scripts/run_pipeline.py
  - scripts/run_pipeline_with_notify.py
  - scripts/build_watchdog.py
  - scripts/cfnew.py
  - docs/state.md
  - ~/projects2/aikorea24emdash/src/pages/posts/index.astro
  - ~/projects2/aikorea24emdash/src/lib/post-count.ts
  - ~/projects2/aikorea24emdash/src/middleware.ts
  - ~/projects2/aikorea24emdash/migrations/0001_app_post_counts.sql
---

# 261021-fld — D1 읽기 한도 초과 근본원인 해결

## 한 일

D1 일일 읽기 한도 초과(2026-10-20 UTC 4,195,200행 = 83.9%, 한도 5,000,000)의 **근본원인을 규명하고
코드 수준에서 제거**했다. 파이프라인이 원인이 아님을 실측으로 규명한 뒤, 서빙측(SSR) 페이지뷰당
수천 행 읽기를 인덱스·SQL·캐시로 축소했다. 함께 지목된 가짜 성공 알림·무의미 빌드 검사·muse-cli
경보 단절도 수정했다.

## 결과

### 근본원인 [검증됨]

**파이프라인이 아니라 SSR Worker가 페이지뷰마다 수천 행을 읽는 것이 원인**이었다.
10-20 UTC 4,195,200행 중 **92.3%가 Worker 요청이 있었던 분에 발생**(3일 교차검증 91.2% / 98.6% / 92.3%).
과금 단위는 질의 수가 아니라 **rows read** — `COUNT(*)` 1건이 읽은 행수만큼 청구된다.

**가드 공백 [구조]**: `check_quota()`는 `cfnew.sql()`(로컬 스크립트 경로)에만 걸려 있고,
**Worker SSR(`env.DB`) 경로는 가드를 통과한다** — 근본원인이 발생한 경로가 가드 밖에 있었다.

### D+3 재측정 (실행 완료, 읽기 전용)

```
UTC 일자            읽기       한도%          DB별(10-20)
2026-10-16     2,744,804     54.9%          aikorea24-db      2,055,775
2026-10-17     2,107,481     42.1%          emdash-db         2,137,095
2026-10-18     2,957,586     59.2%          taiwan-news-db        2,330
2026-10-19     3,494,156     69.9%
2026-10-20     4,195,200     83.9%   ← 80% 임계 돌파
2026-10-21       386,330      7.7%   (진행 중)
```

### 절감 실측 [검증됨] — 원격 D1 동일 시점 계측

| 쿼리 | before | after | 절감 | 근거 |
|---|---:|---:|---:|---|
| aikorea24 홈 `briefings` | 671 | **1** | -99.9% | `idx_briefings_status_id(status,id)` — temp b-tree 소멸 |
| aikorea24 홈 `ToolsSection` UNION ALL | 1,062 | **52** | -95.1% | 분기별 `ORDER BY updated_at DESC, id ASC LIMIT` |
| **aikorea24 홈 합계** | **1,733** | **53** | **-96.9%** | |
| aikorea24 `/global/` news | 19,218 | **50** | -99.7% | `idx_news_category_created(category, created_at DESC)` |
| emdash `/posts` 총계수 | 1,513 | **0** | -100% | 트리거 카운터 + 모듈 TTL 캐시 60초 |

- **출력 불변성 [검증됨]**: 도구 8건·`/global/` 50건이 원소·순서까지 완전 동일(불일치 0건).
  라이브 배포본 재확인 — 홈 카드 8개 슬러그 순서 100% 일치, `/global/` 50건 제목 순서 불일치 0건.
- **대조군 [검증됨]**: 옛 인덱스 경로(`idx_news_category`)를 같은 DB에서 재실행 → 19,218행 재현
  = 절감이 새 인덱스·SQL 때문임을 증명.
- **라이브 GraphQL 배포 전/후 비교** (배포 04:19Z 기준): 671→1, 1,055→52, 19,218→50 행/호출.
- **emdash 라이브 실측**: `x-post-count-rows-read: 0`, `x-post-count: 1512`, `source: hit` (3/3 요청).

### 마이그레이션 [검증됨]

- `sql/007_d1_read_reduction.sql` → 원격 D1 `aikorea24-db` 적용, **4.94초**.
  인덱스 3종 확인: `idx_briefings_status_id` · `idx_tool_submissions_status_updated` · `idx_news_category_created`.
  `CREATE INDEX` 뿐이라 비파괴적. 옛 인덱스는 유지(삭제 안 함 — 파괴적이라 승인 없이 하지 않음).
- `migrations/0001_app_post_counts.sql` → 원격 D1 `aikorea24-emdash-db` 적용.
  카운터 행 `posts.published = 1512`, 트리거 3종(`_ai`/`_au`/`_ad`) 확인. 초기화 비용 1회 1,513행.

### 부가 수정 [검증됨]

| 항목 | before | after |
|---|---|---|
| `AIK24-PIPE-ALERT-01` | 브리핑 0건인데 exit 0 + "✅ 에러 없음" + 텔레그램 "Briefing published" | 선정 수와 **실제 저장 수 분리**(`생성 브리핑: N건`), 0건이면 기존 `summary["errors"]` 구조에 넣어 기존 exit 1 규약 발동, 텔레그램 실건수 표기 |
| `AIK24-BW-01` | `dist/index.html` 검사 → 15회 연속 "dist/index.html 없음" 무의미 통과 | `dist/server/entry.mjs` + `dist/client/` 실제 산출물 검사, 없으면 FAIL + 알림 + exit 1 |
| `AIK24-D1-ALERT-02` | `muse-cli` 절대경로 없이 호출 → 2026-10-18 이후 62회 실패, D1 50/70/90% 경보 **한 번도 미전달** | `shutil.which()` → `~/.local/bin` → uv 경로 순 해석. "실패해도 무시" 동작 유지 |

### 검증 [검증됨]

- pytest before/after 동일: **894 passed, 1 failed, 14 skipped** (실패 1건은 수정 전에도 동일 실패한
  환경 이슈 `wrangler 오류 (rc=127): env: node: No such file or directory`).
- `astro check` 에러 963건 before → 963건 after (**차분 0**, 에러 라인 집합 diff 0줄).
- `py_compile` 5/5 통과.
- 브리핑 0건 판정 기준은 `auto_briefing.save_briefing()`가 돌려주는 `briefing_id` 유무(추정 아님).
- 2026-10-21 실제 DB 확인(rows_read 5): `briefings` 테이블에 오늘 행 없음 → 사고 케이스确실히 실패.

### 예상 일 절감 [부분검증]

홈 1,336뷰/일 × 1,680행 + `/global/` 30뷰/일 × 19,168행 ≈ **2,816,000행/일**.
10-20 실소모 4,195,200행 대비 **약 67% 감소** → 한도 기준 83.9% → 약 27% 수준.
애널리틱스 `limit:200` 절단 가능성으로 **하한 추정치**이며, 하루 단위 확정값은 10-22 UTC 자정 이후
`python3 scripts/d1_usage_report.py --history 6 --by-db` 로 확인한다.

## 산출물 / 커밋

| 저장소 | 커밋 | 내용 |
|---|---|---|
| aikorea24 | `24b64ee1` | D1 읽기 절감(인덱스 3종 + SQL + 마이그레이션 + 계측 도구) — 배포 `db104a18` |
| aikorea24 | `31a32e19` | 가짜 성공 알림 · build-watchdog · muse-cli — pytest 동일 |
| aikorea24emdash | `dbdbf8b` | 총계수 카운터 + TTL 캐시 + 미들웨어 무효화 — 배포 `9e6001ce` |

## 잔존 위험

1. **구 인덱스 잔존** — `idx_briefings_status_date` · `idx_news_category` 유지. news INSERT마다 유지 비용
   1건 증가. 절감폭(19,168행/뷰) 대비 미미하지만 DROP 은 파괴적이라 승인 없이 하지 않음.
2. **[부분검증] 동률 정렬 가정** — 도구 롤링 동률 순서를 `(updated_at DESC, id ASC)` 로 재현했으나
   SQLite 정렬 안정성은 명시적 보장이 아니라 구현 세부. 현재 데이터는 완전 일치, 향후 동률 증가 시
   순서가 달라질 수 있음.
3. **[미해결] 새 인덱스 삭제 시 회귀** — `idx_briefings_status_id` · `idx_news_category_created` 가 사라지면
   671행 / 19,218행으로 되돌아감. 회귀 테스트 없음(코드에 주석으로만 표시).
4. **[미해결] 다른 SSR 페이지 미감소** — `/briefing/`(846행/뷰) · `/tools/` · `/tools/[id]/` · `/network/` 는
   이번 범위 밖. 남은 여유 0~175만행 구간에 영향.
5. **[검증불가] 경로별 읽기 귀속** — GraphQL D1 어댑터에 `query`/`path` 차원이 없어 어떤 페이지가
   얼마나 읽는지 서버측 귀속이 안 됨. UA·경로 계측 계층 도입 필요.
6. **[검증불가] 일일 합계 대시보드 미갱신 확인** — 분석 지연으로 10-21 UTC 일 합계는 미확인. 10-22
   KST 오전 `python3 scripts/d1_usage_report.py` 로 확인.
7. **[부분검증] 일일 뷰 수** — 샘플링 보정 + `limit:200` 절단 기반 하한 추정치.
8. **Worker SSR 가드 공백 미봉합** — `check_quota()` 는 여전히 로컬 스크립트 경로에만 걸림. 전 경로
   진입점 변경이라 고위험으로 이번 범위 밖.
9. **[부분검증] 같은 날 재실행 시 exit 1** — 하루 1회 발행 정책으로 이미 발행했으면 신규 0건 → 실패로 보임.
   자동 실행은 07:00 1회/일이므로 반복 발동 없음, 수동 재실행에서만 해당.
10. **가드 간섭 경보 [검증됨]** — `AIK24-D1-ALERT-02` 검증 중 muse-cli 가 실제 실행되어 muse.ai 기본채팅으로
    검증 메시지 1건이 전송됨(seq 50471). 텔레그램·메일 0건, 코드·저장소 영향 없음.
11. **스케줄 이동 미실시** — 05:30 수집 → 07:00 파이프라인 선후 순서를 깨지 않기 위해 보류. 절감으로
    게이트가 미도달하면 불필요하며, 재발 시 06:40(파이프라인 이전)으로 이동.

## 다음 행동

- 10-22 KST 오전 `python3 scripts/d1_usage_report.py --history 6 --by-db` 로 10-21 UTC 일 합계 확인
  (절감 반영값).
- 07:00 파이프라인 로그에서 `생성 브리핑: N건` 표기 확인, 07:10 워치독에서
  `dist/server/entry.mjs mtime=…` 확인, 30분 주기 D1 리포트에서 muse 경보 발송 확인.
- `/briefing/`(846행/뷰) 잔여 소비원 조사 착수 여부 결정.
