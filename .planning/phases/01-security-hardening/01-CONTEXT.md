# Phase 1: Security Hardening — Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Security audit and remediation of the Python automation pipeline's secrets management. Deliverables: plist API key removal, unified env loader, log secret scrubbing, git history cleanup, abstracted test mock targets. No code behavior changes — security hardening only.

Requirements: SEC-01, SEC-02, SEC-03, SEC-04, OBS-07, TST-05
</domain>

<decisions>
## Implementation Decisions

### Git History Remediation (SEC-04)

- **D-01:** Use BFG Repo-Cleaner to remove original API keys from git history. The plist currently has `REDACTED_OPENAI_KEY` as placeholder, but the real key exists in prior commits.
- **D-02:** After BFG cleanup, rotate all affected API keys (the original keys were exposed in git history, even if now REDACTED).

### Plist Security Fix (SEC-02)

- **D-03:** Remove the entire `<EnvironmentVariables>` block from `scripts/threads/threads-publisher.plist`. The plist should only contain path configuration, never secrets.
- **D-04:** Python scripts will read all secrets through the env loader chain (project `.env` then `~/.env.common`). The plist no longer injects env vars.

### Env Source Consolidation (SEC-03, SEC-01)

- **D-05:** Priority order: project `.env` (highest priority) → `~/.env.common` (fallback). Project-specific settings go in `.env`; shared secrets stay in `~/.env.common`.
- **D-06:** Remove `api_test/.env.sh` — shadow config replaced by unified `env_loader.py`.
- **D-07:** Decouple `deploy.sh` from cross-project `.env` dependency (`/Users/twinssn/Projects/5000/.env`). Each project stands alone with its own `.env`.
- **D-08:** The unified `env_loader.py` will be created as `pipeline/infra/env_loader.py`, following the Strangler Fig pattern (old files keep working, new loader imported incrementally).

### Log Scrubbing (OBS-07)

- **D-09:** Comprehensive scrubbing — API keys, JWT/session tokens, user emails, and any PII.
- **D-10:** Scrubbing implemented at logger level (not env loader level). A `ScrubRegistry` with static pattern list intercepts all log output.
- **D-11:** Known env var names form the initial scrub patterns. Expandable via config.

### Telegram Alert Coverage (OBS-06)

- **D-12:** Failure-only alerts — no success notifications. Message includes which step failed, error details, and timestamp.
- **D-13:** Heartbeat monitor — a separate lightweight daemon checks pipeline log freshness every 30 minutes. If no activity for >3 hours, sends Telegram alert that pipeline missed its schedule.
- **D-14:** Existing `run_pipeline_with_notify.py` infrastructure will be refactored: failure detection moves into the orchestrator (`Phase 3`), and the notify wrapper becomes a thin failure-only event handler.
- **D-15:** The `threads-publisher.plist` currently runs `main_v3.py` directly (bypassing notify). After refactoring, all entry points go through the orchestrator with built-in failure alerting.

### Testing Infrastructure (TST-05)

- **D-16:** Expand `tests/conftest.py` mock targets — currently only `monkeypatch_d1` exists. Add mock fixtures for OpenAI API calls, DeepSeek API calls, and HTTP requests (RSS feeds).
- **D-17:** Abstracted mock targets should support both unit tests (isolated) and integration tests (with real API calls when env vars present).

### Canonical Ref: `~/.env.common`

- **D-18:** `~/.env.common` is the designated single source of truth for shared secrets. It stays in home directory (not moved to project). The project `.env` handles project-specific configuration only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### plist File
- `scripts/threads/threads-publisher.plist` — Contains hardcoded paths and currently has `EnvironmentVariables` with REDACTED API key. Must be stripped of all secrets in this phase.

### Env Sources
- `.env` — Project-level env configuration (highest priority after consolidation)
- `~/.env.common` — Shared secrets home directory file (fallback)
- `api_test/.env.sh` — Shadow config, to be removed
- `.env.bak.telegram` — Telegram config backup, review contents

### Existing Notification Infrastructure
- `scripts/run_pipeline_with_notify.py` — Current Telegram notification wrapper. Pattern reference for refactored failure alerts. Contains `send_telegram()` function and pipeline execution wrapper.
- `scripts/run_pipeline.py` — Core pipeline orchestrator (no notification). Currently runs cron steps.

### Test Infrastructure
- `tests/conftest.py` — Existing test configuration with `monkeypatch_d1` fixture and `sample_weights`/`sample_tiers` fixtures. Template for expanded mock targets.

### Project Docs
- `.planning/REQUIREMENTS.md` §SEC-01 through SEC-04, OBS-07, TST-05 — Full requirement definitions
- `.planning/PROJECT.md` — Project context and decision history
- `.planning/codebase/CONCERNS.md` — Hardcoded path and env duplication concerns
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py:monkeypatch_d1` — Existing D1 mock fixture. Pattern to replicate for OpenAI, DeepSeek, Telegram, and HTTP mocks.
- `scripts/run_pipeline_with_notify.py:send_telegram()` — Telegram sending function already works. Needs to be called only on failure (currently called on every run).
- `scripts/threads/threads-publisher.plist` — launchd plist template. Hardcoded paths and env vars must be stripped.

### Established Patterns
- **Strangler Fig migration** — New infrastructure modules (`pipeline/infra/`) coexist with old files. Old files import from new modules incrementally, no immediate rewrite.
- **Env loading in old files** — Every Python script currently has its own `load_env()` at module level or in main(). The new `env_loader.py` replaces all of these.

### Integration Points
- **plist → launchd** — The plist controls cron scheduling. After stripping env vars, the plist must be re-installed via `launchctl`.
- **Env loader → all Python scripts** — New `env_loader.py` will be imported by all pipeline scripts. Must handle all current env source patterns.
- **Logger → all Python scripts** — New logger with ScrubRegistry must not break existing `print()` calls during the Strangler Fig transition.

</code_context>

<specifics>
## Specific Ideas

- `~/.env.common` stays as the shared secrets file. Not moved into project.
- BFG Repo-Cleaner for git history, not git filter-branch. User prefers BFG.
- Telegram should only alert on failure, never on success. Current implementation alerts on every run — this must be inverted.
- "어떤 발행이 실패했는지와 원인을 함께" — failure message must include: failed step name, error details/summary, timestamp.
</specifics>

<deferred>
## Deferred Ideas

- Web dashboard for pipeline status — deferred to separate dashboard project
- Full env consolidation into project `.env` — user prefers `~/.env.common` pattern, no change needed
- Git filter-branch — rejected in favor of BFG
- Heartbeat monitor implementation details — to be designed in Phase 3 (orchestrator) but basic architecture decided: 30min check, 3hr miss threshold, Telegram alert

</deferred>

---

*Phase: 1-Security Hardening*
*Context gathered: 2026-06-30*
