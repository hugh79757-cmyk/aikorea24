# Requirements: AI코리아24 (aikorea24.kr)

**Defined:** 2026-06-30
**Core Value:** Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.

## v1 Requirements

### Security

- [ ] **SEC-01**: Audit all env var sources (`.env`, `~/.env.common`, `api_test/.env.sh`, plist `EnvironmentVariables`, `deploy.sh` cross-project source) and produce a comprehensive variable-source map
- [ ] **SEC-02**: Remove plaintext API keys from committed launchd plist; delegate all secrets to `.env`
- [ ] **SEC-03**: Consolidate all env loading into a single `env_loader.py` module — remove all 5+ duplicated `load_env()` implementations
- [ ] **SEC-04**: Flag and document secrets in git history for remediation (git filter-branch or key rotation)

### Infrastructure

- [ ] **INF-01**: Create `pipeline/infra/config.py` — `project_root()` replaces 11 hardcoded `PROJECT_DIR` paths
- [ ] **INF-02**: Create `pipeline/infra/env_loader.py` — centralized `EnvConfig` dataclass replacing all env loading copies
- [ ] **INF-03**: Create `pipeline/infra/d1_client.py` — consistent D1 query wrapper with unified retry/timeout behavior
- [ ] **INF-04**: Create `pipeline/infra/logger.py` — structured logging with timestamps, levels, file rotation
- [ ] **INF-05**: Create `pipeline/infra/models.py` — typed dataclasses for pipeline data contracts
- [ ] **INF-06**: Create `pipeline/infra/retry.py` — consistent retry decorator with exponential backoff

### Portability

- [ ] **POR-01**: Remove all 11+ hardcoded `PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'` paths — replace with relative `project_root()`
- [ ] **POR-02**: Template-ize `threads-publisher.plist` — no hardcoded paths, no secrets in plist file
- [ ] **POR-03**: Create `scripts/install_launchd.sh` that generates plist from template with computed paths
- [ ] **POR-04**: Fix `deploy.sh` to resolve paths relative to its location and source only project `.env`

### Directory Restructuring

- [ ] **DIR-01**: Create `pipeline/steps/` — move pipeline step scripts into this directory
- [ ] **DIR-02**: Create `pipeline/threads/` with flattened `v3/` nesting
- [ ] **DIR-03**: Create `pipeline/infra/` for shared infrastructure modules
- [ ] **DIR-04**: Create `pipeline/orchestrator.py` with `PipelineStep` protocol and `PipelineOrchestrator` class
- [ ] **DIR-05**: Keep old files as thin wrappers (Strangler Fig pattern) during transition

### Monolith Splitting

- [ ] **MON-01**: Write characterization tests for pure functions in `writer_v3.py` before any changes
- [ ] **MON-02**: Generate dependency graph of `writer_v3.py` internal function calls before splitting
- [ ] **MON-03**: Extract card/year/keyword validation from `writer_v3.py` into `pipeline/threads/validator.py`
- [ ] **MON-04**: Extract article fetching and link validation from `writer_v3.py` into `pipeline/threads/crawler.py`
- [ ] **MON-05**: Extract format builders from `writer_v3.py` into `pipeline/threads/writer.py`
- [ ] **MON-06**: Extract pitch logic from `narrative_pitcher.py` into `pipeline/threads/pitch.py`
- [ ] **MON-07**: Extract pitch evaluation from `narrative_pitcher.py` into `pipeline/threads/pitch_evaluator.py`

### Testing

- [ ] **TST-01**: Write characterization tests for all functions before refactoring (per Strangler Fig)
- [ ] **TST-02**: Add unit tests for all extracted modules (news_selector, briefing, deep_article, etc.)
- [ ] **TST-03**: Add unit tests for all Threads pipeline modules (validator, crawler, writer, pitch)
- [ ] **TST-04**: Add unit tests for the orchestrator (per-step isolation, retry, skip behavior)
- [ ] **TST-05**: Update `conftest.py` with abstracted mock targets

### Dead Code Removal

- [ ] **DED-01**: Remove backup files (`backup_*.txt`, `.bak` files) after confirming no longer needed
- [ ] **DED-02**: Remove abandoned scripts (`patch_*.py`, `test_*.py`, `spotlight_*.sh`, `quick_check.sh`)
- [ ] **DED-03**: Remove `format_selector.py` after confirming its functionality exists in new modules
- [ ] **DED-04**: Remove old `threads/main_v3.py` after confirming new structure works in production

### Observability

- [ ] **OBS-01**: Structured logging for all pipeline steps (timestamps, severity, run_id, step name, duration)
- [ ] **OBS-02**: Per-step timing and exit code propagation in orchestrator
- [ ] **OBS-03**: Run history stored in D1 (`pipeline_runs` table) — each step's status, duration, timestamp
- [ ] **OBS-04**: CLI status command — `python -m pipeline status` shows last N runs, per-step health, failures at a glance
- [ ] **OBS-05**: End-of-run status report (which steps succeeded/failed, with durations)
- [ ] **OBS-06**: Fix existing Telegram alert — ensure notification fires when pipeline step fails or schedule is missed (infra exists but alerts aren't arriving)
- [ ] **OBS-07**: Log secret scrubbing — redact API keys from log output

### Threads Auto-Publishing

- [ ] **THR-01**: Stabilize Threads publishing pipeline — resolve dual-scheduling race condition (launchd vs `schedule` library)
- [ ] **THR-02**: Refactor Threads pipeline to use shared infra modules

### Bulletin Board

- [ ] **BRD-01**: Verify community bulletin board (posts + comments) works reliably with refactored pipeline

## v2 Requirements

- **GRD-01**: Gradual typing for new modules (optional, after modules stable)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Frontend UI redesign | Not requested, existing design works |
| Mobile app | Web-first, no mobile plans |
| Multi-language support | Core audience is Korean |
| New feature development | Focus is refactoring existing code |
| Web dashboard UI | Deferred to separate dashboard project |
| CI/CD server setup | Pipeline runs locally via cron |
| Abstract base classes / DI frameworks | Research consensus — overkill for 6 sequential steps |
| Async/await migration | No parallelism benefit for serial pipeline |
| Full type annotation coverage | Deferred to v2 (gradual typing) |
| Orchestration framework (Airflow/Prefect) | Massive overkill for single-machine cron pipeline |

## Traceability

### Phase 1 — Security Hardening

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Pending |
| TST-05 | Phase 1 | Pending |
| OBS-07 | Phase 1 | Pending |

### Phase 2 — Infrastructure & Portability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INF-01 | Phase 2 | Pending |
| INF-02 | Phase 2 | Pending |
| INF-03 | Phase 2 | Pending |
| INF-04 | Phase 2 | Pending |
| INF-05 | Phase 2 | Pending |
| INF-06 | Phase 2 | Pending |
| POR-01 | Phase 2 | Pending |
| OBS-01 | Phase 2 | Pending |

### Phase 3 — Landing Zone & Orchestrator

| Requirement | Phase | Status |
|-------------|-------|--------|
| POR-02 | Phase 3 | Pending |
| POR-03 | Phase 3 | Pending |
| POR-04 | Phase 3 | Pending |
| DIR-01 | Phase 3 | Pending |
| DIR-02 | Phase 3 | Pending |
| DIR-03 | Phase 3 | Pending |
| DIR-04 | Phase 3 | Pending |
| DIR-05 | Phase 3 | Pending |
| TST-01 | Phase 3 | Pending |
| OBS-02 | Phase 3 | Pending |
| OBS-03 | Phase 3 | Pending |
| OBS-04 | Phase 3 | Pending |
| OBS-05 | Phase 3 | Pending |
| THR-01 | Phase 3 | Pending |
| THR-02 | Phase 3 | Pending |

### Phase 4 — Monolith Splitting

| Requirement | Phase | Status |
|-------------|-------|--------|
| MON-01 | Phase 4 | Pending |
| MON-02 | Phase 4 | Pending |
| MON-03 | Phase 4 | Pending |
| MON-04 | Phase 4 | Pending |
| MON-05 | Phase 4 | Pending |
| MON-06 | Phase 4 | Pending |
| MON-07 | Phase 4 | Pending |
| TST-02 | Phase 4 | Pending |
| TST-03 | Phase 4 | Pending |
| TST-04 | Phase 4 | Pending |

### Phase 5 — Dead Code Removal & Final Polish

| Requirement | Phase | Status |
|-------------|-------|--------|
| DED-01 | Phase 5 | Pending |
| DED-02 | Phase 5 | Pending |
| DED-03 | Phase 5 | Pending |
| DED-04 | Phase 5 | Pending |
| OBS-06 | Phase 5 | Pending |
| BRD-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0 ✓

---

*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after roadmap creation*
