# Phase 39-01 SUMMARY — Compass 2-pass Korean Article Writing Pipeline

Status: EXECUTED (Task 1 + Task 2)
Date: 2026-09-21

## What was done

Phase 39 was planned but never executed — the 4 most recent commits
(ce1dec4e, 8f82f3a3, 578ce948, de7aae59) are the *original* Compass build,
not the replan fixes. The 5 dry-run issues (REQ-39-06..10) and the two
required test files were absent from code. This run applied the plan.

### Task 1 — 5 writing-logic prompt fixes (`pipeline/threads/compass.py`)

| REQ | Issue | Change |
|-----|-------|--------|
| 39-06 | H2 order reversed | `_build_pass2_user_prompt()` and `_build_blog_pass2_user_prompt()` now map `h2_flow[i]` → slot_i explicitly and forbid reordering |
| 39-07 | Info density / repetition | Both Pass 2 prompts add a per-section anti-repetition rule |
| 39-08 | No competitors in slot2_compare | `_build_pass1_user_prompt()` slot2_compare now requires competitor names (KT, SK, 네이버, 카카오) + differentiation |
| 39-09 | Promotional tone | `build_blog_system_prompt()` adds banned-phrase list + reader-perspective rule |
| 39-10 | intro_style pattern non-compliance | `_build_pass1_user_prompt()` intro_style now lists all 5 patterns with concrete examples, rendered from `INTRO_STYLE_EXAMPLES` + `INTRO_STYLE_PREFIXES` |

### Task 2 — Expansion

- `H2_FLOW_PRESETS["business"]` replaced with slot-aligned headings
  (팩트/비교/맥락/전망/요약).
- `INTRO_STYLE_EXAMPLES` dict added (5 patterns, one example each).
- `INTRO_STYLE_PREFIXES` dict added; `_build_pass1_user_prompt()` now
  renders the intro_style block from these dicts (no dead data).
- `tests/test_compass_generation.py`: `test_intro_style_examples_defined`.

### New test files

- `tests/test_compass_slot_h2_alignment.py` — 4 tests: prompt rule
  presence (blog + thread), positive H2→slot alignment, negative
  reversed-order detection.
- `tests/test_compass_no_repetition.py` — 4 tests: prompt rule presence,
  unique sections pass, repeated numeric token caught, repeated Korean
  noun caught.

## Verification

```
19 passed in 0.72s   # 4 target files, -m unit
175 passed, 2 failed # full -m unit suite
```

The 2 failures (`test_pitch.py::TestGetPitchesCrawlFail`,
`test_write_thread_validation.py::TestHookBodyEntityConsistency`) are
**pre-existing**: they fail identically on a clean tree (verified via
`git stash`). Not caused by this change.

Plan checks:
- `git check-ignore --no-index` on the 3 paths → exit 1 (all tracked).
- `from pipeline.threads.compass import ...` → imports intact, 5 styles,
  business preset present.
- `git diff --name-only` → only `pipeline/threads/compass.py` and test
  files touched. `fact_gate.py`, `writer.py`, `pitch.py` untouched.

## Residual

- `INTRO_STYLES` still has 5 string values; `INTRO_STYLE_EXAMPLES` is the
  authoritative example source. `INTRO_STYLE_PREFIXES` is a derived
  rendering helper — could be inlined if the split ever feels redundant.
- Rotation persistence (`_load_compass_rotation` / `_save_compass_rotation`)
  is unchanged from the original build.