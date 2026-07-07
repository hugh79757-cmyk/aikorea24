# Roadmap: AI코리아24 (aikorea24.kr) — Pipeline Refactoring

## Overview

Brownfield refactoring of the Python automation pipeline from a monolithic, security-bleeding codebase with 16+ duplicated scripts into a modular, portable, and observable pipeline. Uses Strangler Fig migration: fix security first, build shared infrastructure, wire old files incrementally, restructure, split monoliths last. Zero new external dependencies — Python 3.14 stdlib only.

## Phases

- [x] **Phase 1: Security Hardening** — Eliminate active security issues (plaintext API keys, fragmented env loading) (completed 2026-06-30)
- [x] **Phase 2: Infrastructure & Portability** — Create shared infra modules, wire old files, remove hardcoded paths (completed 2026-06-30)
- [x] **Phase 3: Landing Zone & Orchestrator** — Directory restructuring, pipeline orchestrator, Threads stabilization, portability (completed 2026-06-30)
- [x] **Phase 4: Monolith Splitting** — Split writer_v3.py (1,013 lines) and narrative_pitcher.py (581 lines) into focused modules (completed 2026-06-30)
- [x] **Phase 5: Dead Code Removal & Final Polish** — Remove dead code, failure notifications, bulletin board verification (completed 2026-07-01)
- [x] **Phase 6: Prompt Leakage & Truncation Fix** — Eliminate prompt label leakage, fix aggressive truncation (completed 2026-07-03)
- [x] **Phase 7: Crawl Failure Exclusion** — Exclude crawl-failed article IDs from retry selection (completed 2026-07-03)
- [x] **Phase 8: Validation Gap Closure** — 3중 방어 체계: 프롬프트 노출 + 외국어 검증 통합 (completed 2026-07-04)
- [x] **Phase 9: Test Coverage Expansion** — writer/crawler/pitch 테스트 확장 + integration 테스트 (completed 2026-07-04)
- [x] **Phase 10: Model Message Leakage Fix** — 모델 설명 메시지 필터링으로 발행 카드 오염 방지 (completed 2026-07-04)
- [x] **Phase 10-1: Card Structure Validation** — 카드 구조 검증으로 모델 메시지/이상치 완전 차단 (completed 2026-07-04)
- [x] **Phase 11: Defense Mechanism Hardening** — 방어 메커니즘 강화: 패턴 통합, threshold 일관성, Unicode 정규화, 외국어 패턴 통합, E2E 테스트 (completed 2026-07-05)
- [x] **Phase 12: Writer Instability Fix** — fix_cards() 카드 구조 파괴 수정, humanize/retry graceful failure 처리 (completed 2026-07-05)
- [x] **Phase 13: Card Separation Fix & Validation Hardening** — `\n\n` split 안정화, 중국어 마침표(`。`) 인식, 중복 링크 제거, 영구 실패 기사 추적 (completed 2026-07-05)
- [x] **Phase 14: Delimiter Reconfiguration** — JSON-first parsing with `response_format`, fallback retained, delimiter collision eliminated (completed 2026-07-05)
- [x] **Phase 15: Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환** — Vectorize 의미적 중복제거, failed_crawls TTL, 카드 JSON 배열 전환 (completed 2026-07-07)

## Phase Details

### Phase 7: Crawl Failure Exclusion
**Goal:** When `get_pitches()` crawl fails on an article, that article_id is excluded from retry selection — eliminating the 5× retry loop without wasting LLM calls.
**Mode:** ad-hoc
**Depends on**: Phase 6
**Requirements**: RQMT-07-01, RQMT-07-02
**Success Criteria** (what must be TRUE):
  1. `get_pitches()` has `exclude_ids` parameter and returns `(list, set)` tuple — failed article_id surfaces to caller
  2. `main_v3.py` accumulates failed IDs across retries and passes `exclude_ids` — same article never re-selected
  3. When all articles excluded, returns `([], set())` with clear log message
  4. All 197 tests pass with no regressions
**Plans**: 1 plan

Plans:
- [x] 07-01-PLAN.md — Core API change (exclude_ids + tuple return), caller wiring, test updates, crawler enhancement

### Phase 8: Validation Gap Closure
**Goal:** 최종 카드 발행 전 프롬프트 노출/외국어 검증을 **3중 방어 체계**로 방어.
**Mode:** ad-hoc
**Depends on**: Phase 7
**Requirements**: REQ-08-01, REQ-08-02, REQ-08-03, REQ-08-04, REQ-08-05
**Success Criteria** (what must be TRUE):
  1. `validate_final_output()` 함수가 프롬프트 노출 + 외국어 + 한글 비율을 통합 검증
  2. **1차 방어**: 피치 생성 시 (`validate_korean_output` + `detect_prompt_leak`)
  3. **2차 방어**: 쓰레드 작성 후 (`validate_final_output` — 최종 카드 검증)
  4. **3차 방어**: 발행 직전 (`validate_cards` + `validate_final_output` 체이닝)
  5. `detect_prompt_leak()`가 `LEAKED_PROMPT_PATTERNS` + `_SYSTEM_PROMPT_FRAGMENTS` 모두 검사
  6. 모든 테스트 통과, 197개 이상
**Plans**: 1 plan

Plans:
- [ ] 08-01-PLAN.md — 3중 방어 체계 구축

### Phase 1: Security Hardening
**Goal**: All active security issues are eliminated — no plaintext API keys in committed files, env loading consolidated into a single secure module, and secrets in git history documented for remediation.
**Mode**: mvp
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, OBS-07, TST-05
**Success Criteria** (what must be TRUE):
   1. `threads-publisher.plist` contains zero API keys or secrets — all env vars delegated to `.env`
   2. A comprehensive env var source-map document exists, covering all 5+ sources across the project
   3. Single `env_loader.py` module exists (Strangler Fig — old `load_env()` copies remain for incremental wiring in Phase 2)
  4. Secrets in git history are flagged for remediation (key rotation or git filter-branch decision recorded)
  5. Log output is verified to redact API keys and sensitive values (no keys in logs)
**Plans**: 1 plan

Plans:
- [x] 02-PLAN.md — Plist hardening, env consolidation (env_loader.py), log scrubbing, test mocks, git history cleanup

### Phase 2: Infrastructure & Portability
**Goal**: All shared infrastructure modules exist in `pipeline/infra/` and are used by all old files — no more duplicated utility code, no more hardcoded project paths.
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: INF-01, INF-02, INF-03, INF-04, INF-05, INF-06, POR-01, OBS-01
**Success Criteria** (what must be TRUE):
  1. `pipeline/infra/` contains all 6 modules (config, env_loader, d1_client, logger, models, retry) — all stdlib only
  2. All 11+ hardcoded `PROJECT_DIR` paths replaced with `project_root()` from `config.py`
  3. All old files import from `pipeline.infra.*` instead of defining their own `load_env()`, `d1_query()`, `load_posted()` copies
  4. `conftest.py` has abstracted mock targets so tests don't hit real D1/API endpoints
  5. Pipeline runs successfully with zero regressions after infra wiring
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Infra Foundation: create config.py, models.py, retry.py, d1_client.py, extend logger with PipelineLogger
- [ ] 02-02-PLAN.md — Batch Wiring: wire all 20+ scripts with project_root(), EnvConfig(), d1_client.d1_query(), PipelineLogger

### Phase 3: Landing Zone & Orchestrator
**Goal**: Pipeline has a proper directory structure, formal orchestrator with per-step monitoring, Threads dual-scheduling race condition resolved, and the pipeline can be cloned and run on any machine.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: POR-02, POR-03, POR-04, DIR-01, DIR-02, DIR-03, DIR-04, DIR-05, TST-01, OBS-02, OBS-03, OBS-04, OBS-05, THR-01, THR-02
**Success Criteria** (what must be TRUE):
  1. `pipeline/steps/` and `pipeline/threads/` directories exist with all step scripts organized in place
  2. `pipeline/orchestrator.py` with `PipelineStep` protocol and `PipelineOrchestrator` class runs all steps with per-step timing and exit code propagation
  3. Run history stored in D1 (`pipeline_runs` table) — every step's status, duration, timestamp recorded
  4. CLI command `python -m pipeline status` shows last N runs and per-step health at a glance
  5. Plist is generated from template via `install_launchd.sh` — zero hardcoded paths or secrets in plist
  6. `deploy.sh` resolves paths relative to its location and sources only project `.env` (no cross-project dependency)
  7. Threads publishing has no dual-scheduling race condition — single mechanism (launchd XOR internal `schedule`)
  8. Characterization tests exist for pure functions before any monolith refactoring begins
**Plans**: 5 plans

Plans:
- [x] 03-01-PLAN.md — Orchestrator + D1 recording + CLI (core infrastructure)
- [x] 03-02-PLAN.md — Directory restructuring + Strangler Fig step wrappers
- [x] 03-03-PLAN.md — Plist templating + install_launchd.sh + deploy.sh portability
- [x] 03-04-PLAN.md — Threads dual-scheduling fix (remove --daemon)
- [x] 03-05-PLAN.md — Characterization tests for pure functions

### Phase 4: Monolith Splitting
**Goal**: The two largest monoliths (`writer_v3.py` at 1,013 lines and `narrative_pitcher.py` at 581 lines) are split into focused, independently testable modules.
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: MON-01, MON-02, MON-03, MON-04, MON-05, MON-06, MON-07, TST-02, TST-03, TST-04
**Success Criteria** (what must be TRUE):
  1. Dependency graph of `writer_v3.py` internal function calls is documented before any splitting
  2. Card/year/keyword validation is extracted into `pipeline/threads/validator.py` with characterization tests
  3. Article fetching and link validation is extracted into `pipeline/threads/crawler.py` with tests
  4. Format builders are extracted into `pipeline/threads/writer.py` with tests
  5. Pitch logic and pitch evaluation are extracted into `pipeline/threads/pitch.py` and `pipeline/threads/pitch_evaluator.py`
  6. Unit tests exist for all Threads pipeline modules (validator, crawler, writer, pitch) and the orchestrator
**Plans**: 4 plans

Plans:
- [x] 04-01-PLAN.md — validator + crawler extraction + tests (validator.py, crawler.py, Wave 1)
- [x] 04-02-PLAN.md — pitch + pitch_evaluator extraction + tests (pitch.py, pitch_evaluator.py, Wave 2)
- [x] 04-03-PLAN.md — writer extraction + tests (writer.py, Wave 2)
- [x] 04-04-PLAN.md — orchestrator unit tests (test_orchestrator.py, Wave 1)

### Phase 5: Dead Code Removal & Final Polish
**Goal**: Pipeline is fully clean — no dead code, no backup files, no abandoned scripts. Failure notifications work. Bulletin board verified reliable.
**Mode**: mvp
**Depends on**: Phase 4
**Requirements**: DED-01, DED-02, DED-03, DED-04, OBS-06, BRD-01
**Success Criteria** (what must be TRUE):
  1. No backup files (`backup_*.txt`, `.bak` files) remain in the repository
  2. No abandoned scripts remain (`patch_*.py`, `test_*.py`, `spotlight_*.sh`, `quick_check.sh`)
  3. `format_selector.py` is removed after confirming its functionality exists in new modules
  4. Old `threads/main_v3.py` is removed after confirming new structure works in production (shadow-run validated)
  5. Telegram alert fires correctly when a pipeline step fails or schedule is missed (fixed existing mechanism, not new setup)
  6. Community bulletin board (posts + comments) is verified working with refactored pipeline
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — File Cleanup: remove backup files, .bak files, abandoned scripts, standalone dead utilities
- [x] 05-02-PLAN.md — Dead Code in Pipeline + Telegram Fix: remove dead functions, inline format selection, orchestrator Telegram integration
- [x] 05-03-PLAN.md — Bulletin Board Verification + Final Sweep: D1 checks, API verification, full test suite, pipeline dry-run, plist verification

### Phase 6: Prompt Leakage & Truncation Fix (ad-hoc)
**Goal**: Eliminate prompt label leakage into `posted.json` history and remove aggressive title truncation that lost semantic context.
**Mode**: ad-hoc
**Depends on**: Phase 5
**Plans**: 1 plan
Plans:
- [x] PLAN.md — clean_leaked_prompt(), JSON structured output, truncation relaxation, posted.json cleanup

### Phase 10: Model Message Leakage Fix
**Goal:** 모델 설명 메시지가 발행 카드에 포함되는 구조적 취약점 수정.
**Mode:** ad-hoc
**Depends on**: Phase 8
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05
**Success Criteria** (what must be TRUE):
  1. `fix_cards()`가 `split('---')` 전에 모델 메시지 필터링
  2. `humanize_cards()`가 `split('---')` 전에 모델 메시지 필터링
  3. `validate_final_output()`가 카드에서 모델 메시지 탐지
  4. 기존 227개 테스트 모두 통과
  5. 새 테스트가 모든 메시지 패턴 커버
**Plans**: 1 plan

Plans:
- [x] PLAN.md — 모델 메시지 필터링 utility + fix_cards/humanize_cards 적용 + validation 검증

### Phase 10-1: Card Structure Validation
**Goal:** 카드 구조 검증으로 모델 메시지/이상치를 구조적으로 차단.
**Mode:** ad-hoc
**Depends on**: Phase 10
**Requirements**: REQ-01~REQ-10
**Success Criteria** (what must be TRUE):
  1. 카드 최소 길이 20자 검증
  2. 한글 비율 30% 이상 검증
  3. 문장 완성도 검증
  4. 콘텐츠 밀도 검증 (공백 50% 이하)
  5. 중복 카드 탐지
  6. Hook 길이 30~100자 검증
  7. Body 카드 길이 50~500자 검증
  8. 모델 메시지 탐지 (패턴 + 구조)
  9. 기존 241개 테스트 모두 통과
  10. 오판율 1% 미만
**Plans**: 1 plan

Plans:
- [x] PLAN.md — 구조 검증 함수 2개 + 향상된 패턴 20개 + 테스트 20개

### Phase 11: Defense Mechanism Hardening
**Goal:** 방어 메커니즘 강화: 패턴 통합, threshold 일관성, Unicode 정규화, 외국어 패턴 통합, E2E 테스트.
**Mode:** ad-hoc
**Depends on**: Phase 10-1
**Requirements**: REQ-01–REQ-11
**Success Criteria** (what must be TRUE):
  1. Pattern definitions consolidated (single source: validator.py)
  2. `validate_final_output()` uses `ALL_MESSAGE_PATTERNS` (26 patterns)
  3. Korean ratio ≥30% uniform across all validators
  4. Link card check uses `.strip()`
  5. Dead imports removed
  6. New E2E integration tests (test_write_thread_validation.py)
  7. All 270 tests pass (0 failures)
  8. Unicode NFKC normalization applied
  9. Foreign language patterns consolidated to validator.py
  10. LLM system prompt strengthened
  11. Documentation (TECH.md) updated
**Plans**: 1 plan

Plans:
- [x] PLAN.md — 11 tasks: pattern consolidation, threshold alignment, NFKC normalization, foreign language pattern consolidation, prompt strengthening, E2E tests, docs

### Phase 12: Writer Instability Fix
**Goal:** fix_cards() 카드 구조 파괴 수정 — per-card MiMo 교정, humanize/fix_cards graceful 실패 처리, 기사 실패 시 skip.
**Mode:** ad-hoc
**Depends on**: Phase 11
**Requirements**: REQ-12-01, REQ-12-02, REQ-12-03, REQ-12-04, REQ-12-05
**Success Criteria** (what must be TRUE):
  1. `fix_cards()` processes each card individually — never changes card count
  2. `humanize_cards()` applies non-structural regex fixes on card count mismatch
  3. Hook length validation accepts up to 350 chars + content boundary check
  4. `main_v3.py` skips failed article on write failure (no 5x retry of same article)
  5. All 270 existing tests pass
**Plans**: 2 plans

Plans:
- [x] 12-01-PLAN.md — Per-card fix_cards, graceful humanize failure, hook validation relax
- [x] 12-02-PLAN.md — Parallel model race + single-attempt write_thread + article skip on write failure

### Phase 13: Card Separation Fix & Validation Hardening
**Goal:** `\n\n` split 안정화 → `_repair_truncated_cards()` 강화, 중국어 마침표(`。`) 인식, 중복 링크 제거, 영구 실패 기사 추적.
**Mode:** ad-hoc
**Depends on**: Phase 12
**Requirements**: PH-13-01, PH-13-02, PH-13-03
**Success Criteria** (what must be TRUE):
   1. `failed_articles.py` 영구 저장 + main_v3 통합 → article 38290 영구 제외
   2. `sentence_enders`에 `\u3002`(중국어 마침표) 추가 → MiMo `。` 검증 통과
   3. `_remove_duplicate_links()` → 중복 `🔗` 카드 자동 제거
   4. `_repair_truncated_cards()` backward pass → 마지막 카드 불완결 병합
   5. All 287 existing tests pass
**Plans**: 3 plans

Plans:
- [x] 13-01-PLAN.md — Persistent failed article tracking (failed_articles.py + main_v3)
- [x] 13-02-PLAN.md — Validation fixes: `。` enders + duplicate link removal
- [x] 13-03-PLAN.md — Repair logic strengthening + tests + E2E verification

### Phase 14: Delimiter Reconfiguration
**Goal:** Switch from delimiter-based to JSON-first parsing using structured output to eliminate delimiter collision and truncated cards.
**Mode:** ad-hoc
**Depends on**: Phase 13
**Requirements**: REQ-14-1, REQ-14-2, REQ-14-3, REQ-14-4, REQ-14-5
**Success Criteria** (what must be TRUE):
   1. `build_system_prompt_D()` includes explicit JSON output instruction with cards schema
   2. `write_thread()` passes `response_format` with `json_schema` to `chat_completion`
   3. `parse_cards_json_first()` successfully parses JSON responses with 'cards' array
   4. On JSON parse error or invalid structure, fallback to `parse_cards()` occurs
   5. All validation (`validate_card_structure`, `validate_final_output`) applies identically
   6. Fallback path `_repair_truncated_cards()` still used for `\n\n` splits
   7. All 292 tests pass (≥5 new tests), 0 failures
**Plans**: 1 plan

Plans:
- [x] 14-PLAN.md — JSON-first parsing integration and tests

### Phase 15: Vectorize + 크롤링 실패 수정 + 카드 분할 JSON 전환
**Goal:** Vectorize 의미적 중복제거 도입, failed_crawls TTL 적용, 카드 JSON 배열 전환, D1 link dedup 버그 수정, Writer fallback 복구, hook 검증 버그 수정.
**Mode:** ad-hoc
**Depends on**: Phase 14
**Plans**: Phase 15 was executed as ad-hoc tasks (not structured plans)

Plans:
- [x] Vectorize index `aikorea24-dedup` 생성 (1536d, cosine)
- [x] D1 save loss fix (`get_existing()` link 전범위 조회)
- [x] Writer fallback: DeepSeek → GPT-4o-mini sequential
- [x] JSON 4단계 복구 파싱 (JSON → ```json → brace matching → delimiter)
- [x] Hook 검증 버그 수정: `cards[0]` 전체 → 첫 줄만 검사

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening | 1/1 | Complete   | 2026-06-30 |
| 2. Infrastructure & Portability | 2/2 | Complete   | 2026-06-30 |
| 3. Landing Zone & Orchestrator | 5/5 | Complete   | 2026-06-30 |
| 4. Monolith Splitting | 4/4 | Complete | 2026-06-30 |
| 5. Dead Code Removal & Final Polish | 3/3 | Complete | 2026-07-01 |
| 6. Prompt Leakage & Truncation Fix | 1/1 | Complete | 2026-07-03 |
| 7. Crawl Failure Exclusion | 1/1 | Complete | 2026-07-03 |
| 8. Validation Gap Closure | 1/1 | Complete | 2026-07-04 |
| 9. Test Coverage Expansion | 1/1 | Complete | 2026-07-04 |
| 10. Model Message Leakage Fix | 1/1 | Complete | 2026-07-04 |
| 10-1. Card Structure Validation | 1/1 | Complete | 2026-07-04 |
| 11. Defense Mechanism Hardening | 1/1 | Complete | 2026-07-05 |
| 12. Writer Instability Fix | 2/2 | Complete | 2026-07-05 |
| 13. Card Separation Fix & Validation Hardening | 3/3 | Complete | 2026-07-05 |
| 14. Delimiter Reconfiguration | 1/1 | Complete | 2026-07-05 |
| 15. Vectorize + Crawl Fix + JSON Cards | ad-hoc | Complete   | 2026-07-07 |
| **Total** | **34/34** | | |
