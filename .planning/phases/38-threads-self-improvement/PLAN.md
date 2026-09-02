# PLAN — Phase 38: Threads 자가개선 (Self-Improvement) 루프

**Phase:** 38-threads-self-improvement
**Goal:** 발행 성과(views/likes/net_replies) 측정 → 일 1회 insights 수집 → 30일 집계 → 피치 프롬프트 피드백 주입의 폐쇄 루프. 기존 발행 흐름 append-only 수정으로 회귀 0.
**Type:** execute (3 plans, 2 waves)
**Depends on:** Phase 37 (contrast pivot — main_v3 구조), D1 REST 폴백 quick task 20260901
**Constraints:** stdlib only, 기존 테스트 green, 토큰은 EnvConfig 경로만, 30 posts 미만 시 주입 스킵

---

## Goal (outcome)

발행 시마다 root_id+메타가 performance_log.json에 기록되고, 일 06:00 launchd가 지난 48h 발행건의 insights(views/likes/replies/reposts/quotes)를 수집·보정(net_replies)하여 갱신, 30일치 ≥30 posts 축적 시 포맷/토픽/2h-슬롯별 평균 views 집계 report 생성, pitch 생성 시 상위 토픽 3개가 프롬프트에 "참고용"으로 주입된다. 부트스트랩 기간(2~4주)엔 어떤 주입도 없이 발행은 기존 동작 그대로.

## Success Criteria (truths)

1. 발행 성공 시 `performance_log.json` posts에 `{root_id, posted_at, format, article_id, title, source, topic_tags, metrics:null}` 레코드 추가 — API 추가 호출 0건
2. `collect_insights()`가 metrics:null인 최근 발행건에 대해 insights GET 1건/포스트 호출, 5지표 저장, 자기 링크 답글 제외한 net_replies 보정 (18:00 포스트 기준 replies 5 → net_replies 4 회귀 기준선)
3. insights 조회 실패 시 `metrics.error` 기록 후 계속 — 발행/수집 어느 쪽도 중단 안 됨
4. `analyze()`는 최근 30일 posts ≥30건일 때만 `insights_report.json` 생성: 포맷별/토픽별/2h슬롯별 평균 views + engagement율((likes+net_replies)/views). 미만 시 파일 생성 없음
5. pitch.py가 insights_report.json 존재 시 상위 토픽 3개를 "참고용, 강제 아님" 문구로 프롬프트 주입 — dry-run 로그로 주입 확인 가능
6. 기존 발행 흐름 회귀 0: main_v3.py 수정은 발행 성공 블록 append-only ~5줄, run_v3 시그니처 불변, 22:00 슬롯 정상 발행
7. launchd `kr.aikorea24.threads-insights` 일 06:00 등록 — plist는 threads-publisher.plist 패턴 복제, 로그 scripts/threads/logs/insights_collector.log

## Architecture (reuse map)

```
[발행] main_v3.py ── 성공 블록 ──> performance_log.record_publish()   (API 0 call)
[수집] launchd 06:00 → insights_collector.py → performance_log.collect_insights()
        └─ GET /{root_id}/insights (12/일) + /{root_id}/replies (보정 필요분)
        └─ analyze() → insights_report.json (30 posts ≥ 시)
[적용] pitch.py generate 시작 → insights_report.json 읽기 → 프롬프트 주입 (없으면 스킵)
```

Reuse 100%: `publisher.load_env()` (토큰), `_log_api_based_publish` 패턴 (JSON append), threads-publisher.plist (launchd 템플릿), `pipeline.infra` EnvConfig. New: `scripts/threads/performance_log.py` (~80L), `insights_collector.py` (~15L wrapper), plist 1개. Modify: `main_v3.py` (+5L), `pipeline/threads/pitch.py` (+10L).

---

## Plan Table

| Plan | Wave | Depends | Files |
|------|------|---------|-------|
| 38-01 Measurement | 1 | none | `scripts/threads/performance_log.py` (신규), `main_v3.py` (+5L) |
| 38-02 Collector + Analyzer | 1 | none | `performance_log.py` 내 collect_insights/analyze (동일 파일), `insights_collector.py` (신규 wrapper), launchd plist |
| 38-03 Feedback Injection | 2 | 38-02 report 스키마 확정 | `pipeline/threads/pitch.py` (+10L) |

Wave 1: 38-01 + 38-02 병렬 (파일 분리 — 38-02는 performance_log.py 내 함수 추가, 38-01은 record_publish + main_v3 삽입. 동일 파일이므로 **순차** 38-01 → 38-02). Wave 2: 38-03 (report 스키마 의존).

---

## Plan 38-01 — Measurement: 발행 메타 기록

**Wave:** 1

### Tasks
1. `scripts/threads/performance_log.py` 신규 — `PERF_LOG = LOGS_DIR/performance_log.json`, `record_publish(root_id, posted_at, format, article_id, title, source, topic_tags=None)`: posts 배열 append + `_atomic save` (tmp→rename). 파일 없으면 `{"posts": []}` 초기화
2. `main_v3.py` 발행 성공 블록 (line ~429 `✅ 발행 완료` 직후, `_log_api_based_publish` 호출 인근)에 record_publish 호출 ~5줄 삽입 — try/except로 감싸 실패해도 발행 완료 로그 unaffected
3. 검증: `--dry-run`과 별개로 실발행 경로만 기록 (dry-run은 root_id 없으므로 스킵). 단, dry-run에서 record_publish 단위 테스트로 스키마 확인

### Tests
- `test_performance_log.py`: record_publish 2회 → posts 2건, 스키마 필드 전부 존재, 재로드 시 지속성

---

## Plan 38-02 — Collector + Analyzer: insights 수집·집계·launchd

**Wave:** 1 (38-01 완료 후 — 동일 파일 performance_log.py에 함수 추가)

### Tasks
1. `collect_insights(days=2)`: PERF_LOG에서 `metrics is None` + posted_at이 days일 내 포스트 필터 → `GET /v1.0/{root_id}/insights?metric=views,likes,replies,reposts,quotes` (urllib, load_env 토큰, timeout 30, 1회 재시도) → `metrics` 갱신. HTTP 에러 시 `metrics={'error': str}` 기록 후 계속
2. net_replies 보정: replies>0인 포스트에 `GET /{root_id}/replies?fields=id,text&limit=50` → username==aikorea24 (또는 텍스트 `🔗` prefix + url 패턴) 자기 답글 카운트 제외. replies edge 실패 시 `net_replies = replies - 1` (링크 답글 1개 가정 — 우리 파이프는 항상 링크 답글 1개) fallback. 링크 답글 없는 발행은 net_replies = replies
3. `analyze()`: 최근 30일 metrics 완비 포스트 ≥30건 검사 → 미만 시 return None (파일 생성 없음). 충분 시 `insights_report.json` 생성: `{generated_at, window_days:30, n_posts, by_format:{D:{avg_views,avg_likes,avg_net_replies,engagement_rate}}, by_topic:{...}, by_slot:{...}, top_topics:[3]}`. topic_tags 없는 구간은 source/제목 키워드 fallback (첫 30일은 topic_tags=null 다수 → by_source 병기)
4. `scripts/threads/insights_collector.py` wrapper (~15L): collect_insights(days=2) → analyze() → 종료. 로그 print
5. launchd plist `kr.aikorea24.threads-insights.plist` 신규 (threads-publisher.plist 복제 패턴): StartCalendarInterval Hour=6 Minute=0, 로그 `scripts/threads/logs/insights_collector.log` / `_error.log`, `launchctl load` 등록
6. 회귀 기준선: 수동 실행 시 2026-09-01 발행 2건(views 311/194)이 metrics에 기록되는지 — 프로브 값과 일치 확인

### Tests
- `test_performance_log.py` 확장: metrics 갱신 (mock urlopen), net_replies 보정 (replies 5 → 4), analyze 문턱 (29 posts → report 없음, 30 → 있음)

---

## Plan 38-03 — Feedback Injection: 피치 프롬프트 주입

**Wave:** 2 (38-02의 insights_report.json 스키마 확정 후)

### Tasks
1. `pipeline/threads/pitch.py` — pitch 생성 진입부 (피치 이력 로드 인근, line ~520)에서 insights_report.json 존재 + top_topics 비었으면 주입 라인 구성: `"📌 최근 30일 반응 상위 토픽 (참고용, 강제 아님): {t1}, {t2}, {t3}"` → 사용자/시스템 프롬프트에 append (기존 프롬프트 변경 아님 — 추가만)
2. 주입 라인이 LLM 출력으로 leak되지 않도록 `_SYSTEM_PROMPT_FRAGMENTS`에 주입 문구 prefix 추가 검토 (기존 3중 방어 재사용) — leak 시 1차 방어가 차단하는지 테스트로 확인
3. 검증: insights_report.json 수동 fixture 생성 → `--dry-run` 실행 → 로그/피치에 상위 토픽 주입 확인 + 생성 카드에 토픽 문구 미노출 확인

### Tests
- 기존 pitch 테스트 회귀 (275+ green 유지) + 신규: report 없을 때 주입 0건 확인

---

## Execution Order

1. Wave 1: 38-01 Measurement → 38-02 Collector (순차 — 동일 파일)
2. Wave 2: 38-03 Feedback (독립 파일, report fixture로 병행 가능하나 스키마 확정 후 안전)

## Rollback

- main_v3.py 삽입 5줄 제거 → 원복 (append-only라 원복 = 삭제)
- performance_log.json/insights_report.json은 발행에 무관한 부산물 → 삭제로 완전 롤백
- launchd unload + plist 제거
- pitch.py 주입은 report 파일 없으면 자동 무력화 (파일 삭제만으로 비활성)

## Out of Scope (YAGNI)

- 통계 검정/A-B 훅 클러스터링/contrast 가중치/발행 슬롯 변경 — 30일 데이터 후 별도 phase
- posted.json 스키마 병합 — 성과 데이터는 독립 파일 유지
