---
phase: 14-delimiter-reconfiguration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pipeline/threads/writer.py
  - tests/test_writer.py
autonomous: true
requirements: [REQ-14-1, REQ-14-2, REQ-14-3, REQ-14-4, REQ-14-5]
user_setup: []

must_haves:
  truths:
    - "System prompt for format D includes explicit JSON output instruction with cards schema"
    - "write_thread() passes response_format with json_schema to chat_completion"
    - "parse_cards_json_first() successfully parses JSON responses with 'cards' array into list of strings"
    - "On JSON parse error or invalid structure, fallback to delimiter-based parse_cards() occurs"
    - "All validation (validate_card_structure, validate_final_output, etc.) applies to JSON-parsed cards identically"
    - "Fallback path behavior unchanged (maintains _repair_truncated_cards() for \\n\\n split)"
    - "All 287+ tests pass, including new JSON and fallback tests"
  artifacts:
    - path: "pipeline/threads/writer.py"
      provides: "JSON output instruction in build_system_prompt_D()"
      contains: "JSON object with 'cards' array"
    - path: "pipeline/threads/writer.py"
      provides: "JSON-first parsing in parse_cards_json_first()"
      contains: "def parse_cards_json_first(text, format_choice):"
    - path: "pipeline/threads/writer.py"
      provides: "response_format injection in write_thread()"
      contains: "chat_completion(..., response_format=json_schema)"
    - path: "tests/test_writer.py"
      provides: "TestParseCardsJSONFirst class"
      contains: "def test_json_parses_success"
    - path: "tests/test_writer.py"
      provides: "TestParseCardsFallback class"
      contains: "def test_fallback_on_json_error"
  key_links:
    - from: "build_system_prompt_D()"
      to: "LLM output generation"
      via: "prompt includes JSON schema specification"
    - from: "write_thread()"
      to: "chat_completion()"
      via: "response_format=json_schema parameter"
    - from: "parse_cards_json_first()"
      to: "parse_cards() fallback"
      via: "try JSON; except: return parse_cards(text, format_choice)"
    - from: "tests/test_writer.py"
      to: "parse_cards_json_first()"
      via: "mocked chat_completion returns JSON; verify parsing"

---

<objective>
Switch delimiter-based card separation to JSON-first parsing using structured output (`response_format`) while retaining delimiter fallback for resilience.

**Purpose:** The current delimiter-based approach is brittle because LLM uses `\n\n` internally for stanzas, causing delimiter collision and truncated cards that fail validation. JSON structured output eliminates collision by returning a `cards` array directly. This aligns with Phase 6's `response_format` adoption and industry best practices.

**Output:**
- `pipeline/threads/writer.py`: Updated format D system prompt, `write_thread()` passes JSON schema, `parse_cards_json_first()` wrapper added
- `tests/test_writer.py`: New tests for JSON parsing success, fallback behavior, and validation compatibility
- All 287+ tests pass, no regressions
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/14-delimiter-reconfiguration/14-RESEARCH.md

<interfaces>
<!-- Key types and contracts from codebase that the executor will need -->

From pipeline/threads/writer.py (existing):
- `FORMAT_CARD_COUNT_TOLERANCE: dict` — e.g., `{'D': (5, 5)}` (min, max)
- `def parse_cards(text, format_choice='D') -> List[str]` — existing delimiter-based parser
- `def write_thread(pitch, all_articles, format_choice=None) -> List[str]` — main entry point
- `def _repair_truncated_cards(cards: List[str]) -> List[str]` — used in fallback path

From pipeline/threads/validator.py:
- `def validate_card_structure(cards: List[str]) -> Tuple[bool, str]`

From scripts/threads/v3/model_router.py:
- `def chat_completion(messages, system_prompt=None, temperature=0.7, max_tokens=2000, model_override=None, deepseek_model=None, response_format=None) -> str`

</interfaces>

</context>

<tasks>

<task type="auto">
  <name>Task 1: writer.py — JSON-first parsing integration</name>
  <files>pipeline/threads/writer.py</files>
  <action>
    Make three coordinated changes to `pipeline/threads/writer.py`:

    1. **Update `build_system_prompt_D()`** (around line 48) to add explicit JSON output instruction at the end of the system prompt. Include the exact JSON schema example from RESEARCH.md (Section "System Prompt Fragment for JSON Output"). The prompt should still include stanza formatting instructions for content inside each card string; only the outer container changes to JSON.

    2. **Add `response_format` to `chat_completion` call** in `write_thread()` (around line 676-682). Define a `json_schema` dictionary (as in RESEARCH.md Pattern 1 example) before the `_try_model` function, and pass `response_format=json_schema` as a kwarg. The schema should enforce:
       - type object with required "cards" property
       - cards: array of strings, minItems=5, maxItems=7
       - strict: True
       - additionalProperties: False

    3. **Create `parse_cards_json_first(text, format_choice='D')`** function near `parse_cards()` (after line 517). Implementation:
       - try: `data = json.loads(text)`, `cards = data.get("cards", [])`
       - validate: `isinstance(cards, list)` and `lo <= len(cards) <= hi` using `FORMAT_CARD_COUNT_TOLERANCE[format_choice]`
       - ensure card link: if no card starts with '🔗', may append from metadata later (not needed here, write_thread will add link)
       - return `[c.strip() for c in cards if c.strip()]`
       - except (json.JSONDecodeError, TypeError, AttributeError, KeyError): fall back to `return parse_cards(text, format_choice)`

    4. **Replace `cards = parse_cards(content, format_choice)`** in `write_thread()` (line 706) with `cards = parse_cards_json_first(content, format_choice)`.

    5. Keep existing `parse_cards()` unchanged (used for fallback).

    Do NOT modify validator.py or any other module. Ensure imports: `import json` already present (line 2), so no change needed.
  </action>
  <verify>
    Automated checks:
    - `pytest tests/test_writer.py::TestBuildSystemPromptD -x` passes (existing test should still pass; may need update if it asserts on prompt content)
    - `pytest tests/test_writer.py::TestParseCards -x` passes (existing tests still pass because they call parse_cards directly, not parse_cards_json_first)
    - Run `pytest -x` and verify total test count >= 287 and all passing.
    - Additionally, manually grep to confirm: `grep -n "json_schema" pipeline/threads/writer.py` returns at least one match; `grep -n "parse_cards_json_first" pipeline/threads/writer.py` returns the new function.
  </verify>
  <done>
    - `build_system_prompt_D()` includes JSON output mandate
    - `write_thread()` calls `chat_completion` with `response_format=json_schema`
    - `parse_cards_json_first()` exists and uses try/except fallback to `parse_cards()`
    - `write_thread()` uses `parse_cards_json_first()` instead of direct `parse_cards()`
    - All existing writer tests pass
    - All 287+ tests pass overall
  </done>
</task>

<task type="auto">
  <name>Task 2: tests/test_writer.py — JSON parsing and fallback coverage</name>
  <files>tests/test_writer.py</files>
  <behavior>
    - Test 1: parse_cards_json_first parses valid JSON with 6 cards into list of strings
    - Test 2: parse_cards_json_first returns empty list if JSON has non-list cards
    - Test 3: parse_cards_json_first falls back to delimiter when JSON parse fails (malformed JSON)
    - Test 4: parse_cards_json_first falls back when cards count outside tolerance (4 cards for D format)
    - Test 5: parse_cards_json_first preserves link card handling (link card can be any position)
    - Existing tests for parse_cards remain unchanged and still pass
    - May need to adjust existing mock for chat_completion if tests call write_thread end-to-end; but most parse_cards_json_first tests will be unit tests calling the function directly.
  </behavior>
  <action>
    Extend `tests/test_writer.py` with comprehensive tests for the new JSON-first parsing:

    1. Add new test class `TestParseCardsJSONFirst` with methods:
       - `test_json_parses_valid`: input = `{"cards": ["card1 content", "card2 content", ...]}` with 6 items; assert returns list of 6 stripped strings.
       - `test_json_invalid_type`: input = `{"cards": "not a list"}`; assert returns empty list (fallback path results in empty because fallback parse_cards on non-delimiter returns empty? Actually fallback on invalid JSON would go to delimiter, but the string is not valid JSON but it's the original text? Wait: `parse_cards_json_first` receives the raw LLM response text. For this test, we'd simulate malformed JSON string, e.g., `"{\"cards\": \"string\"}"` (this is valid JSON but wrong type) or `"not json"`. We want to test that it gracefully falls back. However, fallback `parse_cards` expects delimiter text; if we give it a JSON-like string with no delimiters, parse_cards would return empty. That's fine; test that JSON parse error returns empty or fallback result.
       - `test_json_count_too_low`: JSON with 4 cards → should fallback to delimiter to attempt recovery? Actually the logic in parse_cards_json_first: after parsing JSON, validate count using lo/hi. If count < lo, we should fallback to delimiter as well (as if invalid). Add that fallback path.
       - `test_fallback_to_delimiter_on_parse_error`: input is delimiter text with `---`; ensure JSON parse fails and delimiter path returns correct cards.
       - `test_link_card_preserved`: JSON with one card starting with '🔗' should be retained (link card).

    2. Update any existing tests that call `write_thread` end-to-end and mock `chat_completion`. Those tests currently mock the LLM response as plain text with `---` delimiters. Need to adjust to return JSON format to exercise new code path. Search for tests like `test_write_thread_success` and modify the mock to return `{"cards": [...]}` instead of `---` separated. Use `unittest.mock.patch` on `v3.model_router.chat_completion` to return JSON string. Also ensure those tests still validate final output (existing assertions should still hold because final thread cards are same conceptual content).

    3. Add a test to verify that `parse_cards_json_first` falls back to `parse_cards` on JSON decode error (use `json.loads` side effect patching).

    4. Ensure tests are marked with `@pytest.mark.unit` appropriately.

    After writing tests, run `pytest -x` and confirm no failures and total count >= previous.
  </action>
  <verify>
    <automated>pytest tests/test_writer.py -x</automated>
    <automated>pytest -x</automated>
    Additionally, grep to confirm new tests exist: `grep -n "class TestParseCardsJSONFirst" tests/test_writer.py` returns match.
    And total test count: `pytest --collect-only -q | tail -1` shows count >= 287.
  </verify>
  <done>
    - `TestParseCardsJSONFirst` with 5+ test methods passes
    - Existing `TestParseCards` and other writer tests still pass (no regressions)
    - Any end-to-end `write_thread` tests updated to mock JSON response correctly
    - Overall test suite passes: 287+ tests, 0 failures
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM output → parser | Untrusted structured/delimited text crosses here |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-14-01 | Tampering | JSON parsing of LLM response | mitigate | Try/except block catches malformed JSON; fallback to delimiter parser ensures availability |
| T-14-02 | Denial of Service | Extremely large JSON payload | accept | LLM response limited by max_tokens=5000; parsing happens in-memory; no disk write before validation |
| T-14-03 | Spoofing | LLM returns wrong `cards` field type | mitigate | Type check (`isinstance(cards, list)`) before use; fallback on mismatch |
| T-14-SC | Supply Chain | npm/pip/cargo installs | N/A | No new packages installed; uses stdlib json only |

</threat_model>

<verification>
1. All tasks complete: parse_cards_json_first implemented and integrated, tests added.
2. Full test suite passes: `pytest -x` returns exit code 0, total tests >= 287.
3. Manual spot check: run a dry-run of the pipeline (`python -m pipeline run --dry-run`) and observe logs to confirm JSON path used (look for "JSON parsing succeeded" or similar log we might add? Not required but could add). The verification must be automated; dry-run not needed for acceptance. Automated tests suffice.
4. Code review: Ensure fallback path still contains `_repair_truncated_cards()` call (no regression from Phase 13).
</verification>

<success_criteria>
- Implementation: JSON-first parsing with fallback is in place and functional.
- Tests: 287+ tests pass, including new JSON and fallback tests (net increase of at least 3 new tests).
- Backward compatibility: Existing parser `parse_cards()` unchanged; old logs/tests still work.
- Performance: No significant token usage increase (JSON schema adds negligible overhead to prompt).
- Validation: All validation functions operate on cards regardless of source, with no degraded detection.
</success_criteria>

<output>
Create `.planning/phases/14-delimiter-reconfiguration/14-01-SUMMARY.md` when done.
</output>
