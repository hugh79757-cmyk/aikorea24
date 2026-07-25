---
gsd_state_version: 1.1
milestone: v2.0-complete
milestone_name: Course System + Pipeline Live
status: all_plans_complete
stopped_at: 완료 — pipeline-path-bug 수정 + Telegram 중앙화 리팩터 + 7/18 블로그 12건 배포 (2026-07-20)
last_updated: 2026-07-20T21:00:00.000Z
last_activity: 2026-07-20
progress:
  total_phases: 26
  completed_phases: 26
  total_plans: 49
  completed_plans: 49
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.
**Current focus:** Phase 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환 (Execution Complete)

## Current Position

Phase: All Phases Complete (1-26)
Status: ✅ 코드 완료, 배포 자동화 추가 (blog_draft_generator.py 6단계 배포)
Last activity: 2026-07-16T07:00

Progress: [████████████████████████████████████████████████████] 100%

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

### Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Architecture | ThreadForge 마이그레이션 검토 | 보류 | 2026-07-06 |
| Cost | GPT-4o 사용 중단 → MiMo v2.5 전환 | ✅ 완료 | 2026-07-06 |

## Session Continuity

Current session: 2026-07-20T19:00:00.000Z
Stopped at: pipeline-path-bug 수정 + Telegram 중앙화 리팩터 + 7/18 블로그 12건 배포 완료
Next: 내일 아침 파이프라인 정상 실행 확인
