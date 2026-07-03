---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Phase 07 execution complete — crawl failure exclusion (exclude_ids + tuple return)
last_updated: 2026-07-03T15:10:00.000Z
last_activity: 2026-07-03
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 22
  completed_plans: 22
  percent: 100.0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.
**Current focus:** Phase 7 — crawl failure exclusion

## Current Position

Phase: 7 (crawl-failure-exclusion)
Plan: 07-01-PLAN.md
Status: Complete
Last activity: 2026-07-03

Progress: [████████████████] 100%

### Phase 7 Details (Crawl Failure Exclusion)
- **Problem**: `get_pitches()` crawl failure returned `[]` with no exclusion mechanism — same article re-selected up to 5 times, wasting LLM API calls
- **Fix**: `get_pitches()` now returns `(list, set)` tuple; `exclude_ids` parameter filters out previously failed articles; `main_v3.py` accumulates failed IDs across retries
- **Key changes**: `pitch.py` — 7 return paths changed to tuples, exclusion filter after shuffle; `main_v3.py` — `failed_article_ids` tracking with accumulation pattern; `crawler.py` — `article_id` param in `log_failed_crawl()`
- **Verification**: All 34 `test_pitch.py` tests pass (4 crawl-fail tests with tuple assertions); 196/197 full suite pass (1 pre-existing failure)

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Project Init]: Security-first prioritization — fix plist API key exposure before any refactoring
- [Project Init]: Strangler Fig migration strategy — not greenfield rewrite
- [Project Init]: Zero new external dependencies — Python 3.14 stdlib suffices for all infra modules
- [Project Init]: No orchestration framework — simple `PipelineStep` protocol + `PipelineOrchestrator` class (50 lines)
- [Project Init]: Coarse granularity (5 phases), YOLO mode, Vertical MVP structure
- [Phase 1]: BFG cleanup for git history + key rotation
- [Phase 1]: .env (priority) → ~/.env.common (fallback) — plist env vars removed
- [Phase 1]: Logger-level comprehensive scrubbing with ScrubRegistry
- [Phase 1]: Failure-only Telegram alerts with step name + error detail
- [Phase 1]: Heartbeat monitor (30min check, 3h miss threshold)
- [Phase ?]: BFG not executed — Java runtime unavailable; git history already clean (no real keys ever committed)
- [Phase ?]: ScrubRegistry uses [REDACTED] replacement (more visible than ***)

### Pending Todos

None yet.

### Blockers/Concerns

- **BFG cleanup + key rotation**: SEC-04 — decided to use BFG then rotate keys. Execute at start of Phase 1.
- ~~**Telegram alerts not firing**: OBS-06 — existing Telegram infra works but `run_pipeline_with_notify.py` wraps the wrong entry point. Fix: make orchestrator fire failure-only alerts.~~ **RESOLVED in Phase 5** — `PipelineOrchestrator._send_telegram_failure()` added, `run_pipeline_with_notify.py` removed.
- **Parallel-run safety**: Pipeline runs every 2 hours via launchd with no staging environment. Every phase must keep the existing pipeline running during transition.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-03T16:00:00.000Z
Stopped at: Phase 7 completed — crawl failure exclusion (exclude_ids + tuple return)
Resume file: None
Next: Project milestone v1.0 complete with all 7 phases. Consider monitoring dashboard, reader analytics, or operational maintenance.
