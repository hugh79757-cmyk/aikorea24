---
phase: 39-compass-2-pass-korean-article-writing-pipeline
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pipeline/threads/compass.py
  - tests/test_compass_generation.py
  - tests/test_compass_draft_compliance.py
  - tests/test_compass_slot_h2_alignment.py
  - tests/test_compass_no_repetition.py
autonomous: true
requirements:
  - REQ-39-01
  - REQ-39-02
  - REQ-39-03
  - REQ-39-04
  - REQ-39-05
  - REQ-39-06
  - REQ-39-07
  - REQ-39-08
  - REQ-39-09
  - REQ-39-10
user_setup: []
estimate:
  tokens: 45000
  raw_tokens: 28000
  tasks: 2
  confidence: med
must_haves:
  truths:
    - "Pass 1 emits a JSON compass containing all 9 fields: category, slot1_fact, slot2_compare, slot3_context, slot4_outlook, intro_style, h2_flow, tone, table_plan"
    - "G4 fact-gate blocks slot3_context claims whose key nouns and numbers do not appear in the crawled source body"
    - "G4 fact-gate allows slot3_context claims whose key nouns and numbers do appear in the crawled source body"
    - "intro_style rotates across 5 consecutive compass generations (5 distinct values)"
    - "Pass 2 draft body follows the compass h2_flow heading order (REQ-39-06)"
    - "Pass 2 draft body uses formal Korean tone (~습니다/~합니다), not banmal (~임/~했음)"
    - "No compass field labels (slot1_fact:, slot2_compare:, slot3_context:, slot4_outlook:, h2_flow:, intro_style:) leak into the draft body"
    - "writeArticle returns the Pass 1 compass alongside the draft body for inspection"
    - "slot2_compare in compass contains concrete competitor names (REQ-39-08)"
    - "H2 sections do not repeat facts already stated in another section (REQ-39-07)"
    - "Draft avoids promotional tone — no marketing copy, reader-perspective only (REQ-39-09)"
    - "intro_style each pattern has a concrete example in the prompt so LLM follows it exactly (REQ-39-10)"
    - "h2_flow[0] covers slot1_fact, h2_flow[1] covers slot2_compare, h2_flow[2] covers slot3_context, h2_flow[3] covers slot4_outlook (REQ-39-06)"
  artifacts:
    - pipeline/threads/compass.py
    - tests/test_compass_generation.py
    - tests/test_compass_draft_compliance.py
    - tests/test_compass_slot_h2_alignment.py
    - tests/test_compass_no_repetition.py
  key_links:
    - write_thread(format_choice="compass") -> compass.write_compass_article() -> G4 gate -> Pass 2 draft -> validator chain
    - write_compass_article() returns (compass_dict, cards_list, link_str) — compass exposed for inspection
    - rotation counter persisted in posted.json across runs
    - slot3 claim tokens matched against crawled_body substring
---

## Review Dispositions Ledger

### Round 1 — pre-plan

No external REVIEWS.md snapshot exists for Phase 39. This ledger is seeded from the
planner's own source-audit (CONTEXT.md stated requirements + 39-RESEARCH.md findings).
No review concern is deferred; every requirement item maps to a task below.

### Round 2 — replan (2026-09-21)

User reviewed live dry-run output ("전력부터 냉각·GPU까지…GS, AI 데이터센터 밸류체인 강화")
and identified 5 writing-logic failures. These are prompt-quality issues — the compass JSON
schema (9 fields) and structural code (write_compass_article, G4 gate, rotation) are correct.
The failures are in Pass 1 prompt (what LLM puts in slot2_compare, intro_style, h2_flow)
and Pass 2 prompt (H2 ordering, info density, tone).

### Review Feedback Addressed

| Concern | Severity | How Addressed |
|---------|----------|---------------|
| slot3 hallucination bypasses all existing gates (RESEARCH Pitfall 1) | HIGH | Task 1: G4 two-layer gate (substring match + LLM ruling) in fact_gate.py; test_fact_gate.py blocks unsupported claims |
| Pattern repetition across runs (RESEARCH Pitfall 2) | HIGH | Task 1: rotation counter persisted in posted.json; test_compass_generation.py asserts 5 distinct intro_style values |
| Compass field leak into published output (RESEARCH Pitfall 3) | MEDIUM | Task 1: extended LEAKED_PROMPT_PATTERNS for slot1_fact/h2_flow/intro_style; test_compass_draft_compliance.py asserts no leak |
| Tone mismatch Threads vs Naver (RESEARCH Pitfall 4) | MEDIUM | Task 1: separate build_system_prompt_compass() with formal tone + HTML tag whitelist; test asserts ~습니다/~합니다 |
| Cost blowup from 2-pass (RESEARCH Pitfall 5) | LOW | Task 1: compass cache keyed by (article_id, date) to avoid regenerating on retry |
| Issue 1: H2 순서 뒤집힘 (REQ-39-06) | HIGH | Task 1: Pass 2 prompt adds "slot 순서대로 H2를 작성하세요. h2_flow[0]은 slot1, [1]은 slot2, [2]은 slot3, [3]은 slot4" + new test |
| Issue 2: 정보 밀도 저하 (REQ-39-07) | HIGH | Task 1: Pass 2 prompt adds "각 H2 섹션은 compass의 해당 슬롯만 포함. 다른 섹션에서 이미 언급한 수치·사실 반복 금지" + new test |
| Issue 3: 비교 슬롯에 경쟁사 부재 (REQ-39-08) | HIGH | Task 1: Pass 1 prompt adds "slot2_compare에는 구체적 경쟁사명(KT, SK, 네이버 등) 포함 필수" |
| Issue 4: 홍보성 톤 (REQ-39-09) | MEDIUM | Task 1: Pass 2 system prompt adds "기업 홍보·광고성 표현 금지" + banned phrases list |
| Issue 5: intro_style 미준수 (REQ-39-10) | MEDIUM | Task 2: INTRO_STYLES dict expanded with example strings; Pass 1 prompt shows each pattern's example |

### Review Feedback Deferred

| Concern | Reason |
|---------|--------|
| None | All stated requirements from CONTEXT.md are covered by Plan 01 |

## Objective

Fix 5 writing-logic issues identified from live dry-run of the compass blog mode.
The compass JSON schema (9 fields) and structural code (write_compass_article, G4 gate,
rotation) are correct. Failures are in Pass 1 prompt (slot2_compare competitor inclusion,
intro_style example clarity) and Pass 2 prompt (H2 ordering enforcement, anti-repetition,
anti-PR tone). Only prompt text and H2 preset definitions change — no structural code changes.

**Purpose:** Ensure compass blog output follows reader-perspective writing (fact → compare →
context → outlook), contains concrete competitors, avoids repetition and promotional tone,
and respects intro_style pattern definitions.

**Output:** Updated `pipeline/threads/compass.py` (prompts + presets only), two new test files,
updates to existing test files for backward compat.

## Execution Context

@/Users/twinssn/.config/opencode/gsd-core/workflows/execute-plan.md
@/Users/twinssn/.config/opencode/gsd-core/templates/summary.md

## Context

@/Users/twinssn/Projects/aikorea24/.planning/PROJECT.md
@/Users/twinssn/Projects/aikorea24/.planning/ROADMAP.md
@/Users/twinssn/Projects/aikorea24/.planning/STATE.md
@/Users/twinssn/Projects/aikorea24/.planning/phases/39-compass-2-pass-korean-article-writing-pipeline/CONTEXT.md
@/Users/twinssn/Projects/aikorea24/.planning/phases/39-compass-2-pass-korean-article-writing-pipeline/39-RESEARCH.md
@/Users/twinssn/Projects/aikorea24/pipeline/threads/compass.py
@/Users/twinssn/Projects/aikorea24/tests/test_compass_generation.py
@/Users/twinssn/Projects/aikorea24/tests/test_compass_draft_compliance.py

## Threat Model

No external review concerns apply to this plan beyond the source-audit items already
addressed in the ledger above. All five RESEARCH pitfalls plus five replan issues are
covered by task actions in this plan.

## Tasks

<task type="tracer">
  <name>Tracer: Fix Pass 1 + Pass 2 prompts for 5 writing-logic issues</name>
  <files>
    pipeline/threads/compass.py
    tests/test_compass_slot_h2_alignment.py
    tests/test_compass_no_repetition.py
  </files>
  <action>
Modify compass.py prompt functions only. No structural code changes. All 5 issues addressed:

**Issue 1 + REQ-39-06 (H2 순서 고정):** In `_build_blog_pass2_user_prompt()` (line 219-232),
add after "컴퍼스의 h2_flow 순서를 따르세요." this line:
"각 H2 섹션은 compass의 슬롯 순서를 반드시 따르세요. h2_flow[0]은 slot1_fact 내용,
h2_flow[1]은 slot2_compare 내용, h2_flow[2]은 slot3_context 내용, h2_flow[3]은
slot4_outlook 내용을 다루세요. 절대 순서를 바꾸지 마세요."

**Issue 2 + REQ-39-07 (정보 밀도):** In `_build_blog_pass2_user_prompt()` (line 219-232),
add after the slot ordering rule:
"섹션별 중복 금지: 각 H2 섹션은 compass의 해당 슬롯 정보만 포함하세요. 다른 섹션에서
이미 언급한 수치·사실·키워드를 반복하면 안 됩니다. 예: '2.4GW'가 한 섹션에 나왔으면
다른 섹션에서 다시 언급하지 마세요."

**Issue 3 + REQ-39-08 (경쟁사 포함):** In `_build_pass1_user_prompt()` (line 168-202),
change the slot2_compare description from:
"- slot2_compare: 비교/대비 포인트 (한 줄)" to:
"- slot2_compare: 경쟁사명(KT, SK, 네이버, 카카오 등 해당 산업 주요 플레이어)과
경쟁 구도 + 이 기사 대상 기업의 차별점을 포함한 비교 포인트 (한 줄)"

**Issue 4 + REQ-39-09 (홍보성 톤 금지):** In `build_blog_system_prompt()` (line 235-253),
add after "모든 문장은 '~합니다/~입니다/~했습니다' 체로 통일. 반말 절대 금지.":
"기업 홍보·광고성 표현 절대 금지. 다음 표현 사용 금지: '비약적 성장', '도약합니다',
'성공적으로 구축합니다', '확보합니다', '선도합니다', '추진합니다'. 대신 팩트를
독자 관점에서 전달하세요: 기업이 무엇을 했는지, 수치는 무엇인지, 결과가 어떻게
변했는지."

**Issue 5 + REQ-39-10 (intro_style 예시):** In `_build_pass1_user_prompt()` (line 168-202),
change the intro_style line from:
"- intro_style: self_identity_call/number_shock/reversal/contrast/conflicting_fact 중 택1" to:
"- intro_style: 다음 5개 패턴 중 택1. 반드시 예시와 같은 형태로 시작하세요.
  * self_identity_call: \"~의 핵심은 ~입니다\" (예: \"이 기술의 핵심은 데이터 처리 속도입니다\")
  * number_shock: 숫자로 시작 (예: \"2.4GW. 이것이 GS그룹이 짓는 데이터센터의 규모입니다\")
  * reversal: 예상과 반전되는 사실로 시작 (예: \"전력 회사가 데이터센터를 짓습니다. 놀라운 일이 아닙니다\")
  * contrast: A와 B를 대비하며 시작 (예: \"SK는 이미 데이터센터를 운영 중입니다. GS는 이제 시작합니다\")
  * conflicting_fact: 서로 모순되는 사실로 시작 (예: \"GS그룹은 전력 회사입니다. 하지만 데이터센터의 핵심은 전력이 아닙니다\")"

**New test file: tests/test_compass_slot_h2_alignment.py**
Create test that verifies H2 order matches slot order:
- Mock compass with known slot values and h2_flow
- Mock Pass 2 response with H2 headings that follow slot order
- Assert each H2 section contains content from the correct slot
- Test negative case: H2 in wrong order should fail

**New test file: tests/test_compass_no_repetition.py**
Create test that verifies no factual repetition across sections:
- Mock compass with distinct slot values
- Mock Pass 2 response where a number (e.g. "2.4GW") appears in multiple sections
- Assert that detect_repetition() or equivalent logic catches duplicate facts
- Test positive case: sections with unique content should pass

NOTE: fact_gate.py, writer.py, and pitch.py are NOT modified. Only compass.py prompts
and presets change. All existing 15 tests must continue to pass unchanged.
  </action>
  <verify>
    <automated>python -m pytest tests/test_compass_generation.py tests/test_compass_draft_compliance.py tests/test_compass_slot_h2_alignment.py tests/test_compass_no_repetition.py -m unit -x</automated>
    <fails_when>non-zero exit, or "0 passed" in the summary line, or any existing test that was previously passing now fails</fails_when>
  </verify>
  <done>
    All prompt changes applied to compass.py. Two new test files created and passing.
    Existing 15 tests still pass (backward compat). Pass 1 prompt forces slot2_compare
    to include competitor names and intro_style to show pattern examples. Pass 2 prompt
    enforces H2-to-slot mapping, anti-repetition, and anti-PR tone. H2_FLOW_PRESETS
    business category updated with concrete headings.
  </done>
</task>

<task type="auto">
  <name>Expansion: H2 presets update + intro_style example definitions</name>
  <files>
    pipeline/threads/compass.py
    tests/test_compass_generation.py
  </files>
  <action>
Update H2_FLOW_PRESETS and INTRO_STYLES definitions in compass.py.

**H2_FLOW_PRESETS business category (line 36-42):** Replace current:
"business": [
    "시장 배경과 규모",
    "핵심 비즈니스 모델",
    "경쟁 구도와 주요 플레이어",
    "실적과 수치",
    "향후 전략과 전망",
]
With:
"business": [
    "팩트: 핵심 사건과 수치",
    "비교: 경쟁사 대비 차별점",
    "맥락: 시장 트렌드와 배경",
    "전망: 향후 변수와 전망",
    "요약: 핵심 포인트 정리",
]
Reason: Current headings are vague ("시장 배경과 규모") and don't map to slots.
New headings explicitly reference slot semantics (팩트/비교/맥락/전망) so LLM
naturally follows slot order. REQ-39-06, REQ-39-10.

**INTRO_STYLES (line 20-26):** Keep same 5 string values but add a parallel dict
INTRO_STYLE_EXAMPLES with one-line Korean examples for each pattern:
INTRO_STYLE_EXAMPLES = {
    "self_identity_call": "~의 핵심은 ~입니다 (예: 이 기술의 핵심은 처리 속도입니다)",
    "number_shock": "숫자로 시작 (예: 2.4GW. 이것이 프로젝트 규모입니다)",
    "reversal": "예상과 반전되는 사실 (예: 전력 회사가 데이터센터를 짓습니다)",
    "contrast": "A와 B 대비 (예: SK는 이미 운영 중입니다. GS는 이제 시작합니다)",
    "conflicting_fact": "모순되는 사실 (예: GS는 전력 회사지만 데이터센터의 핵심은 전력이 아닙니다)",
}
This dict is referenced in _build_pass1_user_prompt() (modified in Task 1) to
generate the intro_style section of the prompt. REQ-39-10.

**Existing test updates:** In tests/test_compass_generation.py, add one test
`test_intro_style_examples_defined` that asserts INTRO_STYLE_EXAMPLES has entries
for all 5 INTRO_STYLES values. This is a trivial assertion test (< 5% context).

Do NOT modify test_compass_draft_compliance.py, test_fact_gate.py, fact_gate.py,
writer.py, or pitch.py.
  </action>
  <verify>
    <automated>python -m pytest tests/test_compass_generation.py tests/test_compass_slot_h2_alignment.py tests/test_compass_no_repetition.py -m unit -x</automated>
    <fails_when>non-zero exit, or "0 passed" in the summary line, or test_intro_style_examples_defined fails</fails_when>
  </verify>
  <done>
    H2_FLOW_PRESETS["business"] updated with slot-aligned headings.
    INTRO_STYLE_EXAMPLES dict added with 5 pattern examples.
    Existing rotation tests still pass. New example definition test passes.
  </done>
</task>

</tasks>

## Verification

## Phase-Level Checks

1. `python -m pytest tests/test_compass_generation.py tests/test_compass_draft_compliance.py tests/test_compass_slot_h2_alignment.py tests/test_compass_no_repetition.py -m unit -x` passes (all new + existing unit tests green).
2. `python -m pytest -m unit` shows no new failures vs the pre-existing baseline (unit test baseline is 0 failures; 16 integration failures exist separately and are not checked here).
3. `git check-ignore --no-index pipeline/threads/compass.py tests/test_compass_slot_h2_alignment.py tests/test_compass_no_repetition.py` exits non-zero (all paths are tracked source, not gitignored).
4. `python -c "from pipeline.threads.compass import write_compass_article, INTRO_STYLES, H2_FLOW_PRESETS; assert len(INTRO_STYLES) == 5; assert 'business' in H2_FLOW_PRESETS"` confirms imports intact.
5. No changes to fact_gate.py, writer.py, pitch.py — verified by `git diff --name-only` showing only compass.py and test files.

## Success Criteria

1. Pass 1 compass JSON: slot2_compare contains competitor names (not just "비교 포인트").
2. Pass 2 blog draft: H2 headings follow slot order (fact→compare→context→outlook), not reversed.
3. Pass 2 blog draft: no number/keyword repeated in multiple H2 sections.
4. Pass 2 blog draft: no promotional phrases ("비약적 성장", "도약합니다", etc.).
5. intro_style: each of the 5 patterns has a concrete example in the prompt.
6. All 15 existing tests pass unchanged (backward compat).
7. 2 new test files created and passing.

## Output

Create the Phase 39-01 SUMMARY at
`.planning/phases/39-compass-2-pass-korean-article-writing-pipeline/39-01-SUMMARY.md`
when this plan is executed.
