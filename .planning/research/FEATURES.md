# Feature Landscape: Modular Python Pipeline

**Domain:** Python automation pipeline restructuring
**Researched:** 2026-06-30

This document describes what the refactored architecture enables — not user-facing features, but engineering capabilities that the new structure provides.

---

## Table Stakes (Must Have From Refactoring)

These are non-negotiable capabilities that the restructured pipeline must provide. Missing any of these means the refactoring failed.

| Feature | Why Expected | Complexity | Current Status |
|---------|--------------|------------|----------------|
| **Portability** | Clone repo → install deps → configure .env → run. No path editing | Low | FAIL: 11 files have hardcoded `/Users/twinssn/Projects/aikorea24` |
| **Single env loader** | One function, one source order, one EnvConfig dataclass | Low | FAIL: 5+ implementations with different source orders |
| **Consistent D1 client** | Same retry/timeout behavior for all D1 queries | Low | FAIL: 3 implementations (0-2 retries, different delays) |
| **Per-step isolation** | One step failure doesn't crash the entire pipeline | Low | PASS: existing orchestrator has try/except per step |
| **Structured logging** | Timestamps, log levels, consistent format across all steps | Low | FAIL: `print()` with different formats in every file |
| **Clear data contracts** | Step inputs/outputs are typed dataclasses, not ad-hoc dicts | Medium | FAIL: dicts with string keys everywhere |
| **CLI consistency** | `run_pipeline.py --skip-* --date --dry-run` works identically before and after | Low | PASS: CLI already works; must not break |

## Architecture Capabilities (What the New Structure Unlocks)

These are engineering capabilities that the new architecture enables. They are NOT required for "PASS" but are the reason for refactoring.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-step unit testing** | Each step can be tested in isolation by importing its module and calling its function with test data | Medium | Depends on removing module-level side effects and extracting pure functions from monoliths |
| **Pipeline monitoring** | Per-step duration, success/failure, error messages stored as structured data for alerting | Low | Orchestrator already collects summary dict; formalizing into `PipelineRunResult` is trivial |
| **Step addition** | New pipeline step = write a function + register with orchestrator. No grep-and-replace needed | Low | Orchestrator's `add_step()` pattern |
| **Environment isolation** | Change .env file to switch from production to staging/dev environment | Low | Config module computes paths relative to project root, not hardcoded |
| **Graceful degradation** | Non-critical steps (thumbnails, email, deploy) can fail without aborting; critical steps (news, briefing) abort | Low | `is_critical` flag on PipelineStep |
| **Migration path for monoliths** | `writer_v3.py` (1013 lines) can be split into validator, crawler, writer modules without rewriting | High | Requires careful extraction of pure functions first |

## Anti-Features (What to Explicitly NOT Build)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Abstract PipelineStep base class** | 6 steps don't share enough interface to warrant an ABC. Would add ceremony without benefit | Use simple `PipelineStep` protocol (duck typing) or just `Callable` |
| **Dependency injection framework** | All steps need the same things: config, D1 client, logger. Direct import is simpler and more debuggable | Direct imports from `pipeline.infra` modules |
| **Async/await** | Pipeline steps are I/O-bound (HTTP calls, subprocess). Async would add complexity with no parallelism benefit for 6 serial steps | Synchronous with `requests` and `subprocess` |
| **Pipeline run database** | Tracking every run in D1 (`pipeline_runs` table) is nice but not required for MVP | Log files + orchestrator summary dict |
| **Greenfield rewrite** | Highest-risk approach. Wastes months of effort. Discards edge case knowledge | Strangler Fig migration |
| **Configuration file (YAML/TOML)** | Another file to maintain. Current argparse + .env is adequate for the complexity level | Keep CLI flags + .env + Python config dataclass |

## Feature Dependencies

```
Shared infra modules (Phase 1)
    ├── enables: Portability (immediate)
    ├── enables: Consistent D1 client (immediate)
    └── enables: Single env loader (immediate)

Old files wired to infra (Phase 2)
    ├── enables: Removing duplication (immediate)
    └── enables: Old files become thin wrappers

Directory restructuring (Phase 3)
    ├── enables: Clean import paths
    └── enables: Clear separation of concerns

Monolith splitting (Phase 4)
    ├── requires: Phase 3 (directory structure exists)
    ├── enables: Per-function unit testing
    └── enables: Independent module development

Test addition (Phase 5)
    └── requires: Phase 4 (functions extracted)
        └── enables: Safety net for future changes
```

## MVP Recommendation

**Phase 1 + Phase 2 only** is the Minimum Viable Improvement:

1. Create `pipeline/infra/config.py` — single source of `project_root()` — removes 11 hardcoded paths
2. Create `pipeline/infra/env_loader.py` — single `load_env()` — replaces 5+ duplicate implementations
3. Create `pipeline/infra/d1_client.py` — consistent D1 query wrapper — standardizes retry behavior
4. Create `pipeline/infra/logger.py` — structured logging
5. Create `pipeline/infra/models.py` — typed data contracts
6. Wire all 11 old files to use these modules instead of their own copies

This delivers 80% of the value (portability, consistency, maintainability) with 20% of the effort (no restructuring, no splitting, no test addition).

## Sources

- Codebase analysis: 11 files with hardcoded paths, 5+ load_env implementations, 3 d1_query implementations — HIGH confidence
- Architecture patterns from data pipeline design literature: Pipe & Filter, Strangler Fig, YAGNI — MEDIUM confidence
