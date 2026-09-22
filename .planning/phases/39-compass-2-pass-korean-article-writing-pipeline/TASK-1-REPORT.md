# TASK-1-REPORT: Compass writeArticle end-to-end with G4 gate

## What Was Implemented

### New Files
1. **`pipeline/threads/compass.py`** — Compass 2-pass writing system
   - `INTRO_STYLES`: 5 rotation patterns (self_identity_call, number_shock, reversal, contrast, conflicting_fact)
   - `H2_FLOW_PRESETS`: 5 category presets (tech, business, society, culture, science) modeled on contrast SLOT_PLAN
   - `write_compass_article(pitch, all_articles)`: Pass 1 (compass JSON) → G4 fact-gate → Pass 2 (body draft) → validator chain
   - `build_system_prompt_compass()`: formal tone (~습니다/~합니다), Naver HTML tag whitelist
   - Returns `(compass_dict, {"cards": [...], "link": "..."})` tuple

2. **`pipeline/threads/fact_gate.py`** — G4 2-layer fact gate
   - `check_slot3(slot3_context, crawled_body)`: Layer 1 (substring/n-gram with Korean stem matching) + Layer 2 (LLM ruling)
   - Blocks if either layer fails

### Modified Files
3. **`pipeline/threads/writer.py`** — Additive `compass` branch at line 443-448
4. **`pipeline/threads/pitch.py`** — 6 compass field label patterns appended to LEAKED_PROMPT_PATTERNS

### Test Files
5. **`tests/test_compass_generation.py`** — TestCompassFields (9 fields), TestRotation (5 distinct intro_styles)
6. **`tests/test_fact_gate.py`** — TestFactGate (block unsupported, allow supported, empty inputs, LLM override)
7. **`tests/test_compass_draft_compliance.py`** — TestToneFormal (~습니다/~합니다), TestNoLeak (no compass labels)

## Test Results

```
11 passed in 2.57s
```

All 11 tests pass with `-m unit -x`:
- `test_compass_has_all_9_fields` ✅
- `test_compass_returns_tuple_format` ✅
- `test_5_distinct_intro_styles` ✅
- `test_blocks_unsupported_claims` ✅
- `test_allows_supported_claims` ✅
- `test_blocks_empty_slot3` ✅
- `test_blocks_empty_body` ✅
- `test_llm_layer_override` ✅
- `test_formal_endings_present` ✅
- `test_no_compass_labels_in_draft` ✅
- `test_leaked_cards_rejected` ✅

Existing `test_write_thread_validation.py` not regressed (1 pre-existing failure unrelated to this work).

## Files Changed
| File | Type | Lines |
|------|------|-------|
| `pipeline/threads/compass.py` | NEW | ~280 |
| `pipeline/threads/fact_gate.py` | NEW | ~120 |
| `pipeline/threads/writer.py` | ADDITIVE | +6 |
| `pipeline/threads/pitch.py` | ADDITIVE | +6 |
| `tests/test_compass_generation.py` | NEW | ~160 |
| `tests/test_fact_gate.py` | NEW | ~90 |
| `tests/test_compass_draft_compliance.py` | NEW | ~170 |

## Self-Review Findings

### [검증됨] compass.py has all 9 required fields
- category, slot1_fact, slot2_compare, slot3_context, slot4_outlook, intro_style, h2_flow, tone, table_plan
- 근거: test_compass_has_all_9_fields 통과, grep로 필드 존재 확인

### [검증됨] intro_style rotates across 5 distinct patterns
- 근거: test_5_distinct_intro_styles 통과, 5개 고유 스타일 확인

### [검증됨] G4 blocks unsupported claims
- Layer 1: Korean stem matching (strips particles 은/는/이/가/을/를 before comparing)
- Layer 2: LLM ruling via chat_completion
- 근거: test_blocks_unsupported_claims, test_llm_layer_override 통과

### [검증됨] Draft uses formal tone
- 근거: test_formal_endings_present 통과 (~습니다/~합니다 종결어미 3개 이상)

### [검증됨] No compass label leakage
- 6 patterns added to LEAKED_PROMPT_PATTERNS in pitch.py
- Additional in-module check in write_compass_article
- 근거: test_no_compass_labels_in_draft, test_leaked_cards_rejected 통과

### [부분검증] writer.py additive branch
- compass branch follows same pattern as contrast branch (lazy import, None→empty normalization)
- 근거: existing test_write_thread_validation.py not regressed (1 pre-existing failure unrelated)
- 제한: No integration test exercising the full write_thread→compass path through writer.py

### [부분검증] fact_gate Layer 1 stem matching
- Korean particle stripping covers common suffixes but edge cases possible
- 근거: unit tests pass with test data
- 제한: No exhaustive Korean morphology test coverage

## Commit
- `ce1dec4e` feat(39): compass 2-pass writing pipeline + G4 fact-gate

## Residual Risks
1. **writer.py compass branch not integration-tested through write_thread()** — only unit-tested via direct write_compass_article call. Full E2E through writer.py needs orchestrator wiring (future phase).
2. **fact_gate Layer 1 Korean stem matching is heuristic** — uncommon particles or compound suffixes may slip through. Layer 2 LLM serves as safety net.
3. **compass rotation counter (persisted in posted.json)** not implemented — plan mentions it but D-03 specifies it as future work. Current rotation is via INTRO_STYLES list cycling in tests only.
4. **`test_hook_entity_quote_marked_accepted`** — pre-existing failure in test_write_thread_validation.py (unrelated to this work).
