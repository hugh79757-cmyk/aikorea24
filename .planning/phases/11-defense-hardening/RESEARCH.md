# RESEARCH.md — Phase 11: Defense Mechanism Hardening

## Problem Statement

The threads publishing pipeline occasionally experiences:
- **Prompt injection/tricking**: Model explanatory messages or instruction-like text appearing in published cards (e.g., "네", "확인", "No changes needed", "이 텍스트는...")
- **Foreign character leakage**: Chinese characters appearing in published content despite detection logic.

The system implements a 3-layer defense (1차: pitch generation, 2차: thread writing, 3차: pre-publish). However, several inconsistencies and gaps reduce its effectiveness.

## Existing Defense Mechanisms

### Pattern-Based Detection
- `LEAKED_PROMPT_PATTERNS` (3): label leaks like "상식(A):", "실제(B):"
- `MODEL_MESSAGE_PATTERNS` (8): simplistic model messages
- `ADDITIONAL_MESSAGE_PATTERNS` (18): polite forms, short responses, English messages, meta commentary
- Combined as `ALL_MESSAGE_PATTERNS` (26 total)

### Foreign Language Detection
- Chinese: `[\u4e00-\u9fff]`
- Japanese: `[\u3040-\u309f\u30a0-\u30ff]`

### Key Validation Functions
| Function | File | Checks | Thresholds |
|----------|------|--------|------------|
| validate_korean_output() | pitch.py | prompt leak, Chinese, Korean ratio, English | Korean ≥15% |
| validate_model_message() | validator.py | patterns, length, Korean ratio | Korean ≥30%, length ≥20, link exempt |
| validate_card_structure() | validator.py | duplicates, length, Korean ratio, density, sentence completeness, hook/body lengths | Korean ≥30% |
| validate_final_output() | validator.py | prompt leak, Chinese/Japanese, Korean ratio, MODEL patterns only | Korean ≥10%, link exempt for Korean only |

### Validation Chain (writer.py652-669)
1. `validate_cards()` — count, first line
2. `validate_year()` — year consistency
3. `validate_keywords()` — keyword coverage
4. `validate_card_structure()` — structural checks
5. Per-card `validate_model_message()` — patterns (ALL), length, Korean ≥30%
6. `validate_final_output()` — prompt leak, foreign, Korean ≥10%, MODEL patterns

## Identified Issues

### 1. Pattern Coverage Inconsistency
- `validate_final_output()` uses only `MODEL_MESSAGE_PATTERNS` (8), not `ALL_MESSAGE_PATTERNS` (26)
- `validate_model_message()` uses ALL, catching polite forms and English messages earlier.
- **Risk**: If `validate_model_message()` were bypassed, final output would miss 18 additional patterns.
- **Recommendation**: Have `validate_final_output()` also use `ALL_MESSAGE_PATTERNS`.

### 2. Duplicate Pattern Definitions
- `MODEL_MESSAGE_PATTERNS` defined identically in `validator.py` and `writer.py:216-225`
- `_strip_model_explanatory()` in writer uses local copy.
- **Risk**: Maintenance drift; one could be updated and the other not.
- **Recommendation**: Remove duplicate from writer; import from validator.

### 3. Dead Code
- `validate_no_foreign_language` imported in writer (`writer.py:10`) but never called. Function exists for testing only.
- **Risk**: Confusion; stale import.
- **Recommendation**: Remove import from writer.

### 4. Korean Ratio Threshold Inconsistency
- `validate_model_message()` / `validate_card_structure()`: ≥30%
- `validate_final_output()`: ≥10% (if total>10)
- **Observation**: Cards already passed 30% earlier, so final_output's check is redundant and weaker. Should be ≥30% for consistency or removed.
- **Recommendation**: Raise final_output threshold to 30% or eliminate it.

### 5. Link Card Check Inconsistency
- `validate_model_message()` uses `card.startswith('🔗')` without `.strip()` (line 210)
- Others use `.strip()`.
- **Risk**: Minor—cards are stripped upstream, but inconsistency could cause false negatives if upstream changes.
- **Recommendation**: Use `.strip()`.

### 6. Test Coverage Gap
- No end-to-end integration test for `write_thread()` validation chain.
- Individual validators tested, but not the combined flow with LLM response and retries.
- **Recommendation**: Add `tests/test_write_thread_validation.py`.

## Proposed Changes

1. **Pattern Consolidation**
   - Remove `MODEL_MESSAGE_PATTERNS` from `writer.py`.
   - In `writer.py`, add `from pipeline.threads.validator import MODEL_MESSAGE_PATTERNS`.
   - Update `_strip_model_explanatory()` to use imported patterns.

2. **Unify final_output patterns**
   - In `validator.py:validate_final_output()`, replace loop over `MODEL_MESSAGE_PATTERNS` with `ALL_MESSAGE_PATTERNS`.

3. **Raise Korean ratio in final_output**
   - Change threshold from `0.1` to `0.3` or remove the check entirely as redundant.
   - Keep link exemption.

4. **Fix link card handling**
   - In `validator.py:validate_model_message()`, change `card.startswith('🔗')` to `card.strip().startswith('🔗')`.

5. **Remove dead import**
   - In `writer.py` line 10, delete `validate_no_foreign_language` from import list.
   - Optionally mark `validate_no_foreign_language()` in validator as deprecated (but keep for tests).

6. **Add integration tests**
   - Create `tests/test_write_thread_validation.py` with scenarios:
     - LLM responds with Chinese char → failure after retries
     - LLM responds with polite ADDITIONAL pattern → failure then retry succeeds
     - LLM responds with prompt leak → detection and retry
     - LLM responds with valid cards → success

7. **Documentation updates**
   - Update `docs/TECH.md` to reflect the unified thresholds and pattern usage.
   - Update `AGENTS.md` if any changes to 3-layer defense description.

## Expected Outcomes

- All 262 existing tests must continue to pass.
- New tests cover the full validation chain.
- Consistent pattern sets across all stages.
- Reduced maintenance burden (no duplicate patterns).
- Clearer, more maintainable defense logic.

## Dependencies

- Phase 10-1 (Card Structure Validation) must be complete.
- No external dependencies; uses existing modules only.

## Risks & Mitigations

- **Risk**: Changing thresholds might cause new failures.  
  **Mitigation**: Since cards already pass 30% threshold earlier, raising final_output to 30% should be harmless. Run full test suite.
- **Risk**: Consolidated patterns might break `_strip_model_explanatory()` if import introduces circular dependency.  
  **Mitigation**: Check imports—validator imports pitch, writer imports validator; pitch does not import writer, so no cycle.
