---
gsd_state_version: 1.1
milestone: v2.0-complete
milestone_name: Course System + Pipeline Live
status: phase_38_complete
stopped_at: Phase 38 Threads 자가개선 루프 구현 완료 (2026-09-02) — 3 plans 전부 완료 (커밋 227bbcc). 라이브 검증: 발행 3건 views 311/194/77 프로브 일치. 부트스트랩 기간 (~30 posts 축적, 약 10-14일) 후 주입 시작. 미커밋 잔존: 19개 tool MD 카테고리 수정
last_updated: 2026-09-02T22:45:00.000Z
last_activity: 2026-09-02
progress:
  total_phases: 38
  completed_phases: 38
  total_plans: 64
  completed_plans: 64
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.
**Current focus:** Phase 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환 (Execution Complete)

## Current Position

Phase: 38 — Threads 자가개선 (Self-Improvement) 루프
Status: ✅ Complete (2026-09-02, 커밋 227bbcc) — 3/3 plans (측정/수집·분석/주입)
Last activity: 2026-09-02T22:45

Progress: [██████████████████████████████████████] 100% (38/38 phases, 64/64 plans)

### Phase 38 구현 결과 (2026-09-02)
- **38-01 측정**: `performance_log.py` + main_v3 발행 성공 블록 연결 (append-only, try/except) — API 0 call
- **38-02 수집/분석**: `collect_insights()` 5지표 + **net_replies 모델 정정** (insights replies는 자기 카드 체인 포함 → root 직접 답글 외부 카운트로 변경, 라이브 검증), `analyze()` 30일 ≥30 posts 문턱, launchd `kr.aikorea24.threads-insights` 일 06:10 등록
- **38-03 주입**: pitch.py `_top_topics_hint()` — report 존재 시에만 "참고용, 강제 아님" 상위 3토픽 주입 (없으면 기존 동작)
- **라이브 검증**: 09-01 발행 3건 views 311/194/77 = 프로브값 일치 / test 5/5 / 전체 스위트 기준선 동일 (회귀 0)
- **다음 관찰 포인트**: ① 09-03 00:00 발행 로그 `📊 성과 로그 기록 완료` ② 09-03 06:10 insights_collector.log ③ ~09-13 30 posts 축적 후 첫 report 생성

### Blog Deployment Automation
- **blog_draft_generator.py**에 6단계 배포 추가:
  - `npm run build` → 빌드
  - `wrangler pages deploy` → auth profile 사용 (CLOUDFLARE_API_TOKEN 우회)
  - 생성된 블로그가 있을 때만 자동 배포 실행

### Course System Status
- **프레임**: 오케스트레이터 — "코드를 쓰는 사람에서, AI를 지휘하는 사람으로"
- **타겟**: AI로 혼자 무언가를 만드는 사람 (개인사업자 + 직장인 부업러 + 프리랜서 + 1인 창작자)
- **로드맵**: "코드를 쓰는 사람에서, AI를 지휘하는 사람으로. 21일."
- **분기**: 선형 분기 (완강 → 다음 강좌 오픈), slug 브랜드 통일 안 함

| 강좌 | slug | day | 상태 |
|------|------|-----|------|
| 첫 AI, 7일 | 7day-starter | 0~7 (8개) | ✅ 시드 완료 + 과목명 업데이트 |
| 0원 인프라, 7일 | 7day-infra | 8~14 (7개) | ✅ 시드 완료 |
| 무료 에이전트, 7일 | 7day-agent | 15~21 (7개) | ✅ 시드 완료 |

### Phase 17-02 Details (HTML → PNG Image Generator)
- **Goal**: HTML 템플릿 기반 Instagram Carousel(1080×1350) + Reels(1080×1920) PNG 생성
- **Plans**: 1/1 complete
- **Files created**:
  - `pipeline/instagram/html_renderer.py` — 렌더링 + Playwright 캡처 오케스트레이션
  - `pipeline/instagram/utils.py` — ensure_dir, slugify, timestamp_kst, create_run_directory
  - `pipeline/instagram/templates/carousel_slide.html` — 1080×1350 다크 테마 템플릿
  - `pipeline/instagram/templates/reel_cover.html` — 1080×1920 세로형 템플릿
  - `pipeline/instagram/__init__.py` — 16개 public API export
- **Key functions**: render_full_carousel(), batch_render_carousel(), render_reel_cover(), capture_html_to_png()
- **Decision**: string.Template (stdlib) over Jinja2, Playwright CLI subprocess over Python API

### Phase 19 Details (MVP-3: 자동 발송) — Coded, Deferred
- **Goal**: 7일 강좌 자동 이메일 발송
- **Plans**: 3/3 complete (코드 완료)
- **Files created**:
  - `src/pages/api/courses/send-daily.ts` (272 lines)
  - `src/pages/api/courses/templates/lesson-email.ts` (99 lines)
  - `src/pages/api/courses/track.ts` (84 lines)
  - `scripts/send_course_emails.sh` (43 lines)
  - `scripts/course-email-sender.plist.template` (32 lines)
  - `scripts/install_course_sender.sh` (50 lines)
- **Decision**: Workers API for send logic, Brevo transactional for email, launchd for schedule
- **NOTE**: launchd plist NOT installed, day 0 immediate send hook NOT implemented — 모든 콘텐츠 준비 후 마지막에 활성화 예정

### Phase 15 Details (Vectorize + D1 fix + Writer fallback + Hook fix)
- **Goal**: Vectorize 의미적 중복제거 도입, failed_crawls TTL 적용, 카드 JSON 배열 전환, D1 link dedup 버그 수정, Writer fallback 복구, hook 검증 버그 수정.
- **Key changes**:
  1. `pipeline/infra/vectorize_client.py` — 신규: OpenAI text-embedding-3-small (1536d) + Cloudflare Vectorize REST API 클라이언트
  2. `api_test/news_collector.py` — D1 save loss fix (`get_existing()` link 전범위 조회), Vectorize auto-index
  3. `pipeline/threads/writer.py` — 4단계 JSON 파싱 복구, sequential fallback (DeepSeek → GPT-4o-mini)
  4. `pipeline/threads/validator.py` — Hook 검증 수정: `cards[0]` 전체 → 첫 줄만 검사
  5. `scripts/threads/main_v3.py` — Vectorize 인덱싱 통합
  6. `scripts/threads/migrate_to_vectorize.py` — 신규: 283개 기사 벡터 마이그레이션
- **Verification**: 2회 연속 dry-run 성공 (6카드), 1회 실제 발행 성공

### Phase 13 Details (Card Separation Fix & Validation Hardening)
- (Previous phase details retained; see git history for full record)

### Phase 11 Details (Defense Mechanism Hardening)
- **Goal**: Harden defense against prompt injection and foreign characters — improve maintainability, consistency, comprehensiveness
- **Key changes**: 
  - Pattern consolidation: `MODEL_MESSAGE_PATTERNS` → single source in validator (removed from writer)
  - `validate_final_output()` now uses `ALL_MESSAGE_PATTERNS` (26 patterns, up from 8)
  - Korean ratio threshold aligned to ≥30% across all validators (was 10% in final_output)
  - Unicode NFKC normalization added before foreign language detection
  - Foreign language patterns consolidated to validator.py (removed from pitch.py)
  - LLM system prompt strengthened — explicit foreign language prohibition
  - New E2E tests: `tests/test_write_thread_validation.py` (6 tests)
  - Dead imports removed, link card .strip() check fixed
- **Verification**: All 270 tests pass (262 existing + 8 new), 0 failures — pre-existing freshness test fixed

## Performance Metrics

**Velocity:**

- Total plans completed: 22
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 1 | - | - |
| 03 | 5 | - | - |
| 04 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-security-hardening P02 | 12min | - tasks | - files |
| Phase 03-landing-zone-orchestrator P01 | 2min | 3 tasks | 4 files |
| Phase 03-landing-zone-orchestrator P05 | 8min | 2 tasks | 2 files |
| Phase 03-landing-zone-orchestrator P03 | 2min | 3 tasks | 3 files |
| Phase 04-monolith-splitting 04-01 | 10min | 5 tasks | 6 files |
| Phase 04-monolith-splitting 04-04 | 2min | 1 task | 1 file |
| Phase 04-monolith-splitting 04-02 | 8min | 4 tasks | 6 files |
| Phase 04-monolith-splitting 04-03 | 5min | 3 tasks | 3 files |
| Phase 07-crawl-failure-exclusion 07-01 | 12min | 3 tasks | 6 files |

| Phase 11-defense-hardening 11-01 | 15min | 11 tasks | 10 files |
| Phase 12-writer-instability-fix 12-01 | 4min | 4 tasks | 3 files |
| Phase 12-writer-instability-fix 12-02 | 3min | 4 tasks (1 no-op) | 2 files |
| Phase 13-card-separation-fix 13-01 | — | 4 tasks | 3 files |
| Phase 13-card-separation-fix 13-02 | 1min | 4 tasks | 3 files |
| Phase 13-card-separation-fix 13-03 | 2min | 6 tasks | 4 files |
| Phase 17-instagram-carousel 17-02 | 8min | 3 tasks | 5 files |
| Phase 17-instagram-carousel 17-06 | 5min | 1 task | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 11]: Unicode NFKC normalization for foreign language detection upstream of regex
- [Phase 11]: Single source of truth for all patterns (MODEL_MESSAGE_PATTERNS, ADDITIONAL_MESSAGE_PATTERNS, CHINESE_PATTERN, JAPANESE_PATTERN) — validator.py
- [Phase 11]: Korean ratio threshold 30% uniform across all 3 validation functions
- [Phase 11]: E2E validation chain tests (test_write_thread_validation.py) cover LLM response → validation → retry flow
- [Phase 13]: `\n\n` split 유지, `_repair_truncated_cards()` 강화로 보완 (return to `---` rejected: too many card count failures)
- [Phase 13]: `sentence_enders`에 `\u3002`(중국어 마침표) 추가 — MiMo v2.5 특성 반영
- [Phase 13]: `_remove_duplicate_links()` 추가 — `\n\n` split의 중복 링크 문제 해결
- [Phase 13]: Persistent failed article tracking (failed_articles.py) — article 38290 infinite retry loop 해결
- [Phase 15]: Vectorize REST API 도입 — Cloudflare Vectorize로 의미적 중복제거 추가 (보조 레이어)
- [Phase 15]: failed_crawls.json TTL 24시간 적용 — 영구 제외로 인한 기사 풀 고갈 해결
- [Phase 15]: 카드 분할 JSON 배열 전환 — delimiter 충돌 근본 해결, fallback 제거
- [Phase 28-05]: generate_draft() 기사 조립부에 원문 URL·매체·발행일 포함 — LLM이 URL을 임의 생성하지 않고 시스템 보유 URL만 Markdown 링크로 사용하도록 프롬프트에 명시
- [Phase 28-05]: 조건 분기 규칙 도입: has_numeric + has_comparison 4가지 조합 + content_type 5종 → 표·섹션 조건부 강제
- [Phase 28-05]: title 한글 우선 규칙: 영문 비율 40% 초과 시 검수 fail (제품명은 프롬프트 지침으로 한글 번역 유도)
- [Phase 28-05]: 발행 전 자동 검수 게이트 5종 구현: heuristic 4종(출처 없는 숫자·첫 120자 결론·표 무결성·제목 언어) + LLM 일반론 판정 1종 → validate_draft_quality()로 통합, main() 생성 루프에 연결
- [Phase 28-05]: auto_deep_article.py 표 사용 금지 규칙 삭제 + 조건 분기·출처·독자행동·관련 허브 섹션 요구 추가 → generate_draft와 프롬프트 일관성 확보

### Key Decisions (Phase 17)

- [Phase 17] **커뮤니티 게이트웨이 패턴**: 강좌 콘텐츠는 `posts`에 저장, 이메일은 티저 + 커뮤니티 링크만 발송
- [Phase 17] **visibility 3종**: `public`(기존), `members`(로그인+강좌 무관), `premium`(추후 유료)
- [Phase 17] **Brevo 유지**: 기존 Brevo 인프라 그대로 사용, Cloudflare Email Service 전환 안 함
- [Phase 17] **Brevo 태그 체계**: `course-enrolled-7day-starter`, `course-completed-7day-starter` 등
- [Phase 17] **MVP 분할**: 4개로 나눠 순차 검증 (등록 → 게이트 → 발송 → 완강)
- [Phase 17] **시작 정책**: 등록 후 첫 18:00에 1일차 발송
- [Phase 17] **발송 방식**: Brevo Automation 대신 Workers + Brevo 트랜잭셔널 API 조합
- [Phase 17-02] **HTML 렌더러**: string.Template + Playwright CLI 조합 ($0 비용)
- [Phase 17-02] **배치 렌더링**: 순차 처리로 슬라이드 순서 보장, 부분 실패 허용
- [Phase 17-06] **Instagram PipelineStep**: Lazy imports로 환경 변수 의존성 처리, dry_run 모드 지원
- [Phase 17-06] **launchd 스케줄**: 캐러셀 08:00 + 릴스 19:00 KST 별도 에이전트

### Phase 25 Details (커뮤니티 레슨 순차 해금)
- **Goal**: 커뮤니티에서 강좌 레슨을 이메일 드립 진도(`days_sent`)와 동일하게 하나씩 잠금 해제
- **Plans**: 1/1 complete (RESEARCH.md + PLAN.md in `.planning/phases/25-community-lesson-unlock/`)
- **Files changed**:
  - `src/pages/community/[id].astro` — 게이트 재작성 + 잠금 카드 UI
- **Key changes**:
  1. 강의 레슨 판별: `category==='강의'` → **`course_lessons` 매핑 존재 여부** (시드가 `category='free'`로 저장해 분기 불일치 bug 수정, 데이터 안 건드림)
  2. 순차 해금: 등록 사용자 `days_sent >= day_number` 이면 전체 본문, 아니면 잠금 (이메일 드립 미러)
  3. 3상태 잠금 UI: 비로그인(로그인+신청 CTA) / 로그인+미등록(수강생 전용) / 로그인+등록+대기(잠금 해제 전 안내)
- **Verification**: `npm run build` 통과. 런타임 상태 확인은 D1 필요(크론 OFF → days_sent=0 유지, 운영 반영해도 전 레슨 잠금 상태)
- **Decision**: 해금 기준 = days_sent (사용자 확정, 크론 OFF 수용). auto-enroll 없음(강좌 폼/뉴스레터 폼 이미 분리). day 0 고아 레슨·랜딩 커리큘럼 불일치는 별도 이슈.

### Pending Todos

None.

### Blockers/Concerns

| Issue | Status | Workaround |
|-------|--------|------------|
| (2026-07-16 블로그 6건 미배포 → ✅ 7/20 수동 배포 완료) | | |

### Quick Tasks Completed

| Date | Slug | Description |
|------|------|-------------|
| 2026-07-26 | fix-blog-deploy-condition | blog_draft_generator.py 배포 조건 수정: `generated`만 체크 → `generated or untracked_blog_files`로 확대. 미커밋 블로그 6건(7/25-007~012) 감지 시 배포 실행 |
| 2026-08-13 | fix-stale-skip-deep-docs | run_pipeline.py --skip-deep 제거(9fa7b05) 후 stale 문서화 수정: TECHNICAL.md, SKILLS/01-daily-news-pipeline.md, SKILLS/04-deep-article-generator.md에서 --skip-deep/--no-skip-deep 참조 제거 |
| 2026-08-13 | decouple-tools-collector-instagram | tools_collector.py에서 pipeline.instagram.utils.slugify → pipeline.infra.utils.slugify로 변경. edge_tts import 연쇄 문제 해결, 인스타그램 의존성 분리. pipeline/infra/utils.py 신규 생성 |
| 2026-08-26 | verify-publish-isolation | 실발행 2시간 검증 + 테스트 발행 차단 검증 — launchd 12슬롯(홀수시) PASS, 11:01 실발행 6ID 성공, contrast dry-run posted 미터치 + drafts/contrast 분리 PASS (880 vs 15) |
| 2026-08-28 | pipeline-docs | TECH.md에 Section 13 (Abbductive Reasoning Pipeline) + Section 14 (Weekly Contrast Deep Dive Pipeline) 추가. 12개 모듈 시그니처, 환각 방어 3중 레이어, 발행 게이트, 4주 관측 지표 문서화 |
| 2026-08-29 | weekly-contrast-thumb-leak | 심층분석 2건 썸네일/릭/중복섹션 수정 + 깊이 보강. 루트픽스: deep_dive_writer.py 출력형식을 병렬나열→통합분석 4섹션으로 개편, max_tokens 4000→6000, A측/B측/대비 금지. weekly_blog_publisher.py에 generate_thumbnails 연동. 2건 재생성(001 LLM, 002 수동복원-폐기회피) + 썸네일 + 배포 완료 |
| 2026-09-01 | threads-d1-alert | Threads 파이프라인 D1 장애(HTTP 500/7500, 12:00~) 시 빈 기사 5회 재시도 소진 경로에 send_telegram 추가 (84850ac). 기존에는 조용히 return → 수 시간 무알림 스킵. 토큰 유효 확인, 할당량 아님(403 아님) 판정 |

### Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Architecture | ThreadForge 마이그레이션 검토 | 보류 | 2026-07-06 |
| Cost | GPT-4o 사용 중단 → MiMo v2.5 전환 | ✅ 완료 | 2026-07-06 |

## Session Continuity

Current session: 2026-08-27T03:53:00.000Z
Stopped at: Phase 37 Threads Contrast Pivot + Kicker7 운영화 — contrast 5모듈(1795L) + person_gate + kicker7_writer, writer/validator/pitch/main_v3 확장, auto_news_selector route_person_stories, 39 contrast tests pass, dry-run graceful drop verified, 18 blog drafts untracked (미커밋)
Next: untracked 분류 커밋 (code vs drafts), STAR hook test triage, TECH.md Phase37 반영, kicker7 live 배포 :30 launchd 확인

---
phase_37: 2026-08-26~27 Threads Contrast Pivot + Kicker7 (blog→Threads 7→5 pivot, D untouched)
  status: complete (impl done, dry-run verified, publish blocked, kicker7 live 1건 k7_46941 published root 17866975854642583, 4건 HOLD)
  plans: 3/3 (37-01 Foundation, 37-02 Writer, 37-03 Orchestrator dry-run)
  tests: 39 new (21 extractor +8 background +10 writer/orch) = 39 pass / 전체 336/338 pass (2 pre-existing: retention_from_env, hook STAR)
  guard: --format contrast only with --dry-run, orchestrator never calls publisher, writer.py D path untouched, kicker7 별도 launchd :30
  artifacts: contrast 5모듈 + person_gate + kicker7_writer (1795L), scripts/threads 3개, phase37 docs 5개, blog drafts 18건
