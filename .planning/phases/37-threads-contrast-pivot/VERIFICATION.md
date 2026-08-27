# VERIFICATION — Phase 37: Threads Contrast Writing Pivot

**Date:** 2026-08-26
**Verifier:** gsd-plan-checker
**Result:** ✅ PASS (with 1 warning, 0 blockers)
**Plans checked:** PLAN.md (3 sub-plans: 37-01 Foundation, 37-02 Writer, 37-03 Orchestrator, 2 waves)

---

## Goal-Backward Trace

**CONTEXT Goal:** `docs/manual-blog/prompts/01-extractor + 02-curator` 7단락 대비 보도체를 **블로그가 아니라 Threads 5-card Format D** 파이프라인에 pivot. `blog_draft_generator.py` 신버전 구현 금지.

| Goal element | Plan coverage | Evidence |
|---|---|---|
| 7단락 → 5-card 압축 | ✅ Covered | Success Criteria #4 + Task 01-1 `CONTRAST_CARD_MAP` + Task 02-1 `build_system_prompt_contrast()` with fixed table C1:1+2 / C2:2+3 / C3:4+5 / C4:6 / C5:7 |
| 2-stage LLM chain (Extractor → Curator) | ✅ Covered | Task 01-2 `extract_af()` temp0.2 json_object + Task 02-1 `write_contrast_thread()` temp0.4-0.5 json_object, reuse `model_router.chat_completion` |
| 배경 기사 1건 (E 키워드 3개) | ✅ Covered | Success Criteria #2 + Task 01-3 `find_background()` D1 LIKE 30일 DESC + Vectorize fallback + graceful None |
| 교차검증 3매체 시뮬레이션 | ✅ Covered | Success Criteria #3 + Task 01-3 `find_cross_articles()` D1 LIKE description 재사용 2건, `fetch_article_body` seed only |
| 표면/근본 대비 논지 | ✅ Covered | Task 02-1 `SYSTEM_CURATOR_CONTRAST` + user_prompt `A-F JSON + related_text + FORMAT 대비 5카드` |
| Threads 제약 준수 | ✅ Covered | Success Criteria #4-6: 350-450 target / 500 hard limit + `validate_cards/card_structure/validate_final_output` chain + 한자/히라가나/한글비율/열린질문 |
| Out-of-scope fenced | ✅ Fenced | CONTEXT Scope `blog_draft_generator 신버전 안 함` — zero files touching it, Architecture reuse map only `pipeline/threads/*` + `scripts/threads/main_v3.py` |

**Verdict:** Goal fully decomposed into tasks. No gap.

---

## RESEARCH Incorporation

| Finding | Incorporated? | Where |
|---|---|---|
| Pattern 1: 2-step chain with typed A-F intermediate + B/C/E guard | ✅ | 01-2 `extract_af` + `_validate_af`, 02-1 bundle, 03-1 `run_contrast_thread` glue |
| Pattern 2: 7→5 mapping C1(1+2) C2(2+3) C3(4+5) C4(6) C5(7) | ✅ | 01-1 `SYSTEM_CURATOR_CONTRAST` + card map, 02-1 `FORMAT: 대비 5카드` description |
| Pattern 3: Background D1 LIKE + Vectorize fallback, no external API | ✅ | 01-3 `d1_query` LIKE `%kw%` + lazy `vectorize_client.query`, anti-pattern explicitly bans Brave/Tavily/Exa |
| Pattern 4: Reuse 3중 방어, only add 2-3 leak patterns | ✅ | 01-4 `LEAKED_PROMPT_PATTERNS` + `_SYSTEM_PROMPT_FRAGMENTS` → propagates to `detect_prompt_leak`/`validate_final_output` |
| Anti-pattern: no runtime .md load | ✅ | 01-1 "Must NOT `open(docs/manual-blog/...)` at runtime" → string constants |
| Anti-pattern: no crawler 3× (seed only) | ✅ | 01-3 cross uses description surrogate, crawler only for seed |
| Don't Hand-Roll: reuse `model_router`, `d1_client`, `project_root`, `logger` | ✅ | Tasks explicitly import each, `Ponytail skips` lists what NOT built |

---

## Success Criteria Measurability

| # | Criterion | Measurable | File/Test trace |
|---|---|---|---|
| 1 | Extractor A-F JSON, B>=1 C>=1 E==3 guard, drop without exception | ✅ | `contrast/extractor.py` + `tests/test_contrast_extractor.py` 8-10 cases (valid, B0→None, C0→None, E2→None, JSON garbage→None) |
| 2 | Background E 3 LIKE → Vectorize → graceful None | ✅ | `contrast/background_search.py` + `tests/test_contrast_background.py` mocked `d1_query`, Vectorize, quote escape |
| 3 | Cross 3-media simulated (1 crawl + 2 description) no external API | ✅ | `background_search.find_cross_articles()` + orchestrator glue |
| 4 | Curator 7→5 350-450 target 500 hard limit, regen 1 then drop | ✅ | `contrast/contrast_writer.py` `write_contrast_thread()` + `tests/test_contrast_writer.py` cases 1,2,4 |
| 5 | 3중 방어 leak patterns propagation | ✅ | `validator.py`/`pitch.py` +5L + `test_validator/pitch` regression + `detect_prompt_leak('상위 주제:')` assert |
| 6 | Threads constraints 5 cards 500자 한자0 한글비율 prompt-leak 0 | ✅ | `validate_cards`, `validate_final_output`, `validate_card_structure`, `validate_last_card_opens_reply` + writer test cases 2,3,5,6 |
| 7 | `main_v3 --format contrast` vs `D` dual, D untouched, 275+ tests green | ✅ | `scripts/threads/main_v3.py` argparse + branch + `tests/test_cascade_2pass` regression + `tests/ -q` full suite |

All 7 truths map 1:1 to files and pytest gates. No orphan criterion.

---

## Dependencies & Execution Order

```
Wave 1: 37-01 Foundation (prompts, extractor, background, validator patterns + 2 test files)
   ↓
Wave 2: 37-02 Writer  +  37-03 Orchestrator (parallel, both depend 37-01)
```

- `Depends on: Phase 15 (Vectorize+JSON) + Phase 16 (writer v2)` — verified exists (vectorize_client, JSON cards in repo).
- File ownership exclusive per wave (only `tests/` different files overlap) — no conflict.
- No circular, no forward reference, wave = max(deps)+1 correct.
- `model_router` import via `sys.path.insert(0, project_root)` preamble consistent with existing writer.py:155 — py_compile gate included.

**Status:** ✅ Valid.

---

## Constraints Compliance

| Constraint | Respected? | Evidence |
|---|---|---|
| 무료 LLM 폴백 체인 (`model_override=None` fixed) | ✅ | 01-2, 02-1 explicitly `model_override=None`, temp 0.2/0.4-0.7, thinking disabled |
| 500char/card + 3중 방어 유지 | ✅ | 02-1 target 350-450 + hard 500, chain `validate_cards`→`validate_year`→`validate_card_structure`→`validate_final_output` |
| `project_root()` DRY, no hardcoded PROJECT_DIR | ✅ | 01-2,02-1 import `project_root`, 01-3 `d1_query` handles `CLOUDFLARE_API_TOKEN` removal |
| stdlib only, no new deps | ✅ | Plan states stdlib only, reuse `pipeline.infra.*`, explicitly bans Brave/Tavily/Exa/new vector client |
| 기존 275+ tests green 유지 | ✅ | Each task has regression gate `pytest tests/test_validator -q`, `test_writer -q`, final `tests/ -q` |
| D1 LIKE only, no 외부 검색 API | ✅ | 01-3 D1 LIKE + Vectorize fallback only |
| No new LLM client / D1 wrapper | ✅ | Ponytail skips section: reuse only |

---

## Scope Fencing

- Out-of-scope `blog_draft_generator.py 신버전` — zero tasks touch it. Explicitly excluded in Goal, Architecture new boundary (only `writer.py` + `main_v3.py` modified).
- Input source: D1 news DB only (existing `d1_client`), not keywords.json new path — respected.
- Infra reuse 100%: `writer`/`validator`/`crawler`/`pitch`/`model_router`/`d1_client`/`config`/`logger` listed — no duplication.

**Status:** ✅ Fenced.

---

## Atomicity & Executability

| Sub-plan | Tasks | Files (new/mod) | Verify present? | Atomic? |
|---|---|---|---|---|
| 37-01 Foundation | 4 | 6 (prompts __init__ extractor background + validator/pitch) | ✅ each has `python -m py_compile` + `pytest test_contrast_extractor/background` + `detect_prompt_leak` assert | Yes — extractor+background testable without curator |
| 37-02 Writer | 2 | 2 (contrast_writer + writer.py 60L) | ✅ `FORMAT_BUILDERS['contrast']` assert + `test_contrast_writer` + `test_writer` regression | Yes — prompt→JSON parse→validator chain isolated |
| 37-03 Orchestrator | 3 | 3 (orchestrator + main_v3 40L + test e2e) | ✅ import check + `--help grep` + `test_contrast_writer` 8 cases + full `tests/ -q` + dry-run checklist | Yes — glue + CLI + E2E gate |

- Each task has `Files` + `Action` + `Verify` + `Done`.
- Verify commands are runnable (`py_compile`, `pytest -v -q`, `python -c assert`).
- Scope per plan: 37-01 ~30-40% context (borderline but acceptable), 37-02 ~20-30%, 37-03 ~20-30%, total ~1100L est. within budget.

---

## Issues

### WARNINGS (should fix, not blocking)

**W-1 [research_guard_drift] guards B/C threshold inconsistency**
- **Severity:** WARNING
- **Description:** RESEARCH.md Pattern 1 example guards `B>=2, C>=2`, but PLAN Task 01-2 uses `B>=1, C>=1` with Risk Mitigation justification ("Guard lowered to B>=1 to avoid <30% success"). Both are defensible; discrepancy should be explicit in RESEARCH Resolution notes.
- **Fix hint:** Either update RESEARCH.md to note relaxed guard as resolved decision, or keep Plan guard but add comment referencing risk row.

### INFO (observations, not required)

- **I-1:** Single aggregated `PLAN.md` with 3 plan sections rather than separate `37-01-PLAN.md` files. Project convention for threads pipeline phases is single-file multi-plan (also used in Phase 17 docs). Not a blocker; tooling `phase.list-plans` would expect split files but manual verification passed.
- **I-2:** `main_v3` seed selection for contrast dry-run simplified to `articles[0]` in 03-2; RESEARCH recommended pitch-flow-derived seed. Simplified path is acceptable for dry-run isolation; production path will use `get_pitches` seed. No change needed.
- **I-3:** Test file `tests/test_contrast_writer.py` ownership claimed by both 37-02 and 37-03 (one creates, one adds e2e). Plan notes "different files" but this one overlaps. In practice 37-02 creates writer unit, 37-03 adds e2e cases to same file — sequential append, not parallel conflict. Ensure coordination comment added.

---

## Overall Assessment

Plans are **goal-backward sound**: every CONTEXT element (7→5 pivot, 2-stage chain, D1-only background, simulated 3-media, 3중 방어, free chain, 500char) has implementing tasks with files and verification. RESEARCH findings are incorporated without hand-rolling. Success criteria are measurable and traceable to 3 new test files (~240L) plus regression gates. Dependencies valid (Wave1→Wave2 parallel, no file overlap). Constraints respected (stdlib, no new deps, `project_root` DRY, green tests). Scope fenced (blog_draft_generator excluded). Tasks atomic/executable with file+verify.

**Recommendation:** PASS — proceed to `/gsd-execute-phase 37`. Address W-1 with one-line comment in extractor.py guard docstring referencing risk decision.

---

## Verification Gates Checklist

- [x] Phase goal extracted from CONTEXT.md
- [x] PLAN.md loaded (3 sub-plans, 9 tasks)
- [x] RESEARCH.md loaded (8 open questions resolved, 4 patterns verified)
- [x] Requirement coverage checked (7 Success Criteria → 9 tasks, 0 gap)
- [x] Task completeness validated (Files+Action+Verify+Done per task)
- [x] Dependency graph verified (no cycles, Wave1→Wave2 correct)
- [x] Key links checked (prompts→extractor→background→writer→orchestrator→main_v3)
- [x] Scope assessed (4/2/3 tasks, ~8-10 files, within budget)
- [x] must_haves derivation verified (7 truths user-observable, artifacts map 1:1)
- [x] Context compliance checked (locked Decisions honored, Deferred Ideas excluded)
- [x] Cross-plan data contracts checked (ContrastBundle typed, description vs crawl body)
- [x] AGENTS.md compliance checked (stdlib, project_root, scrubbed logger)
- [x] Overall status determined: PASS
