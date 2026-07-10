---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: phase_17_in_progress
stopped_at: Phase 17 — 강좌 시스템 MVP-1: 등록 흐름
last_updated: 2026-07-10T17:30:00.000Z
last_activity: 2026-07-10
progress:
  total_phases: 17
  completed_phases: 16
  total_plans: 36
  completed_plans: 36
  percent: 94
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.
**Current focus:** Phase 15 — Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환 (Execution Complete)

## Current Position

Phase: 18 (retention-funnel) — Complete
Plan: Priority 1+2 (히어로 순서 변경 + 블로그 CTA 3종) + CSP 차단 해결 + /subscribe/ 페이지
Status: Phase 18 완료, 배포 완료
Last activity: 2026-07-10

Progress: [████████████████████████] 100%

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

### Pending Todos

None.

### Blockers/Concerns

None.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Architecture | ThreadForge 마이그레이션 검토 | 대기 | 2026-07-06 |
| Cost | GPT-4o 사용 중단 → MiMo v2.5 전환 | 완료 | 2026-07-06 |
| Architecture | MVP-2 커뮤니티 게이트 | 대기 | 2026-07-10 |
| Architecture | MVP-3 자동 발송 | 대기 | 2026-07-10 |
| Architecture | MVP-4 완강 분기 | 대기 | 2026-07-10 |

## Session Continuity

Last session: 2026-07-10T09:00:00.000Z
Stopped at: Phase 17 MVP-1 시작 — D1 스키마 설계 중
Next: migration SQL → 시드 스크립트 → enroll API → 랜딩 페이지
