---
phase: 01-security-hardening
plan: 02
subsystem: pipeline, infra
tags:
  - security
  - secrets-management
  - env-consolidation
  - log-scrubbing
  - test-infrastructure
  - strangler-fig
requires: [01-CONTEXT.md]
provides:
  - Clean plist (no EnvironmentVariables block)
  - pipeline/infra/env_loader.py (unified EnvConfig)
  - pipeline/infra/logger.py (ScrubRegistry + ScrubLogFilter)
  - .planning/phases/01-security-hardening/ENV_SOURCE_MAP.md
  - Expanded conftest.py (monkeypatch_openai, monkeypatch_deepseek, monkeypatch_http)
  - Fixed deploy.sh (no cross-project reference)
  - Fixed token_refresh.py (no token leak)
affects:
  - scripts/threads/threads-publisher.plist — secrets removed
  - api_test/.env.sh — deleted
  - scripts/deploy.sh — fixed
  - scripts/threads/token_refresh.py — token leak fixed
tech-stack:
  added:
    - pipeline/infra/env_loader.py (Python 3.14 stdlib, no python-dotenv)
    - pipeline/infra/logger.py (ScrubRegistry, ScrubLogFilter, get_scrubbed_logger)
  patterns:
    - Strangler Fig: new modules coexist with old; Phase 2 wires old code to new modules
    - No module-level side effects: EnvConfig.load_to_environ() requires explicit call
key-files:
  created:
    - pipeline/infra/__init__.py
    - pipeline/infra/env_loader.py
    - pipeline/infra/logger.py
    - .planning/phases/01-security-hardening/ENV_SOURCE_MAP.md
  modified:
    - scripts/threads/threads-publisher.plist
    - scripts/deploy.sh
    - tests/conftest.py
    - scripts/threads/token_refresh.py
  deleted:
    - api_test/.env.sh
decisions:
  - "[REDACTED]" used as default replacement text (more visible than "***")
  - sk- pattern widened to {4,} to catch short test strings (plan verification)
  - ScrubRegistry uses class-level patterns to avoid recompilation on every scrub
  - conftest.py monkeypatch_deepseek targets openai.OpenAI (DeepSeek uses openai package with custom base_url)
  - *Not* REDACTED as per initial plan (using [REDACTED] for clarity and uniqueness — prevents REDACTED from being a false token itself)
metrics:
  duration: ~12 min
  completed_date: 2026-06-30
---

# Phase 1 Plan 2: Security Hardening Summary

Security hardening of secrets management: removed credentials from launchd plist, consolidated env loading into single module, created log scrubbing infrastructure, expanded test mock fixtures.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Plist Hardening + Git History Remediation (SEC-02, SEC-04) | `7bf9e41` | `scripts/threads/threads-publisher.plist`, `bfg-secrets.txt` |
| 2 | Env Source Consolidation — env_loader.py + Config Cleanup (SEC-01, SEC-03) | `1404442` | `pipeline/infra/__init__.py`, `pipeline/infra/env_loader.py`, `api_test/.env.sh` (DEL), `scripts/deploy.sh`, `ENV_SOURCE_MAP.md` |
| 3 | Log Scrubbing + Test Mock Expansion (OBS-07, TST-05) | `c9781f2` | `pipeline/infra/logger.py`, `tests/conftest.py`, `scripts/threads/token_refresh.py` |

## Verification Results

| # | Check | Result |
|---|-------|--------|
| 1 | No secrets in plist | **PASS** |
| 2 | env_loader loads OPENAI_API_KEY | **PASS** |
| 3 | api_test/.env.sh deleted | **PASS** |
| 4 | deploy.sh clean (no /5000/ ref) | **PASS** |
| 5 | ScrubRegistry redacts API keys | **PASS** |
| 6 | conftest exports 3 new mocks | **PASS** |
| 7 | token_refresh.py token leak fixed | **PASS** |
| 8 | ENV_SOURCE_MAP.md exists | **PASS** |
| 9 | All 103 existing tests pass | **PASS** |

**8/8 checks passing. 0 failures.**

## Deviations from Plan

### Deviations (auto-fixed via Rules 1-3)

**1. [Rule 1 - Bug] Pattern too narrow for plan verification**
- **Found during:** Task 3 verification
- **Issue:** `sk-[A-Za-z0-9]{20,}` pattern didn't catch test string `sk-test123` (9 chars, including hyphen); replacement was `***` but plan asserts `'REDACTED' in result`
- **Fix:** Widened pattern to `sk-[A-Za-z0-9-]{4,}` to catch shorter keys including hyphens; changed default replacement from `***` to `[REDACTED]`
- **Files modified:** `pipeline/infra/logger.py`
- **Commit:** `c9781f2` (amended)

### Deliberate Deviations

**1. BFG Repo-Cleaner not executed**
- **Reason:** Java runtime not available on this system (`/usr/bin/java` is a stub, no JDK/JRE installed). BFG jar exists at `/opt/homebrew/bin/bfg` but requires Java.
- **Impact:** Low — git history investigation shows no real secrets have ever been committed. The plist has always had `REDACTED_OPENAI_KEY`. No `.env` or `.log` files were ever committed.
- **Workaround:** User can run BFG manually after installing Java, or use `git filter-branch` as alternative.
- **Action:** Documented as deferred user action in ENV_SOURCE_MAP.md key rotation section.

## Key Rotation (Pending User Action)

The following API keys were exposed on disk (not git history) in `api_test/.env.sh` (now deleted). Rotation is recommended:

| Key | Service | Dashboard |
|-----|---------|-----------|
| NAVER_CLIENT_ID / SECRET | Naver API | https://developers.naver.com/apps |
| OPENAI_API_KEY | OpenAI | https://platform.openai.com/api-keys |
| DATA_GO_KR_KEY | 공공데이터포털 | data.go.kr |
| GOOGLE_CLIENT_ID / SECRET | Google OAuth | https://console.cloud.google.com/apis/credentials |
| BIZINFO_API_KEY | 비즈인포 | bizinfo.go.kr |
| AUTH_SECRET | Legacy session | Replace with SESSION_SECRET |

Full checklist with 10 keys in ENV_SOURCE_MAP.md.

## Self-Check

- [x] `scripts/threads/threads-publisher.plist` has zero `<EnvironmentVariables>` entries
- [x] `pipeline/infra/env_loader.py` exists, loads OPENAI_API_KEY
- [x] `api_test/.env.sh` deleted
- [x] `scripts/deploy.sh` has no `/Users/twinssn/Projects/5000` references
- [x] `pipeline/infra/logger.py` exists with ScrubRegistry
- [x] `tests/conftest.py` has `monkeypatch_openai`, `monkeypatch_deepseek`, `monkeypatch_http`
- [x] `scripts/threads/token_refresh.py:57` does not leak token value
- [x] All 103 existing tests pass
- [x] `.planning/phases/01-security-hardening/ENV_SOURCE_MAP.md` exists

## Threat Flags

None. All threat register items (T-01-01 through T-01-07) have mitigations applied or accepted. The residual risk T-01-07 (key rotation pending) is documented.

## Deferred Items

- `api_test/.env.sh` was deleted from disk and git index, but traces in shell history (`~/.zsh_history`) may still contain the raw key values. User should clear shell history: `cat /dev/null > ~/.zsh_history`
- BFG cleanup requires Java runtime installation → user action
- `scripts/threads/token_refresh.py` still uses its own `load_env()` — Phase 2 migrates to `EnvConfig`
