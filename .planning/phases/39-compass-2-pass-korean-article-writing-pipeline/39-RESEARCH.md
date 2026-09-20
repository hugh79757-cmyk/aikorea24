# Phase 39 Research

**Researched:** 2026-09-20
**Domain:** Compass 2-pass Korean article writing pipeline
**Confidence:** HIGH (codebase reads) / MEDIUM (skill docs)

## Summary

Phase 39 introduces a compass-first 2-pass writing system: Pass 1 emits a JSON compass (category, slot1_fact, slot2_compare, slot3_context, slot4_outlook, intro_style, h2_flow, tone, table_plan); Pass 2 drafts the body. This is net-new -- no `compass`, `slot1..slot4`, `h2_flow`, `intro_style`, or `writeArticle` exists in the codebase today.

The closest existing entry point is `write_thread()` at `pipeline/threads/writer.py:431`. It already does JSON-first parsing, per-card validation, and returns `{"cards": [...], "link": "..."}`. A Compass `writeArticle` should extend `write_thread` with a new `format_choice="compass"` branch rather than replace it.

The G4 fact-gate for `slot3_context` has no existing source-citation enforcement. The strongest available primitives are `_validate_hook_body_entity_consistency()` (`validator.py:314`) which cross-checks hook entities against body + `source_text`, and `validate_speaker_attribution()` (`validator.py:481`) which enforces joint-statement speaker lists. Neither validates that every slot3 claim traces to a source URL. That gap is net-new work.

The `intro_style` 5-pattern rotation and `h2_flow` category presets also do not exist. The only rotation logic in the codebase is `format_selector.select_format()` which always returns `"D"` -- no rotation. The `contrast` module (`pipeline/threads/contrast/`) has the closest thing to a slot/planning system: `SLOT_PLAN` (`contrast_writer.py:45`), `SLOT_DESC` (`contrast_writer.py:32`), and `SYSTEM_OUTLINE` (`contrast_writer.py:21`) which assigns fact-index refs (b_refs/c_refs) to cards. That is the reusable pattern for h2_flow.

Korean Naver blog constraints come from two skill sources: `jisang` (compass/naver prompts, devices matrix, fact-sealing rules) and `naver-content-writing` (HTML tag whitelist, smart-editor compatibility, length targets). The existing Threads pipeline uses banmal (`~임/~했음`); Naver blog output uses formal (`~습니다/~합니다`). This tone split is a hard constraint for Phase 39.

Test infrastructure: `pytest.ini` sets `testpaths=tests`, `pythonpath=scripts`, markers `unit`/`integration`. The existing 16 failures are all `integration`-marked tests that need D1/network -- they do not block unit-test addition. New compass tests should be `unit`-marked and mock `chat_completion`.

Risks: slot3 hallucination (no source gate exists yet), pattern repetition across runs (no rotation exists), prompt leak (existing `detect_prompt_leak` covers only 8 system fragments + 10 label patterns, not compass fields), and LLM cost (each Pass 1 + Pass 2 = 2 LLM calls per article).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Compass generation (Pass 1) | API / Backend | - | LLM call producing JSON; no browser/state involved |
| Body drafting (Pass 2) | API / Backend | - | LLM call consuming compass JSON; same tier as Pass 1 |
| G4 fact-gate (slot3 source check) | API / Backend | - | Validation logic runs pre-publish, no client state |
| Source citation enforcement | API / Backend | - | Cross-references crawled body text against slot3 claims |
| intro_style rotation | API / Backend | - | Deterministic counter in orchestrator, not a UI concern |
| h2_flow presets | API / Backend | - | Static dict in compass module; consumed by Pass 2 prompt |
| writeArticle execution/inspection | API / Backend | - | Extends `write_thread`; returns dict, no render tier |
| Naver blog HTML output | Frontend Server (SSR) | - | HTML tag whitelist enforced at draft stage; rendering is static Astro |
| Korean tone enforcement (banmal vs formal) | API / Backend | - | Prompt-level constraint; differs by output target (Threads=banmal, Naver=formal) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`json`, `re`, `os`, `sys`, `pathlib`) | 3.14 | Compass JSON generation, rotation counter, h2_flow lookup | Existing convention: all new pipeline modules are stdlib-only (CONTEXT.md constraint) |
| `v3.model_router.chat_completion` | existing | LLM calls for Pass 1 (compass) and Pass 2 (body) | Single LLM entry point; used by `pitch.py:609`, `writer.py:564`, `pitch_evaluator.py:66` |
| `pipeline.threads.validator` | existing | `validate_final_output`, `validate_card_structure`, `validate_model_message` | Reuse for post-draft validation; already covers Korean ratio, foreign language, prompt leak |
| `pipeline.threads.crawler.fetch_article_body` | existing | Source body for fact-gate | Already used by `writer.py:507`; returns raw text for source matching |
| `pipeline.threads.pitch.detect_prompt_leak` | existing | Prompt fragment detection | Reuse for compass JSON inspection; covers 8 fragments + 10 label patterns |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pipeline.threads.contrast.contrast_writer.SLOT_PLAN` / `SLOT_DESC` | existing | h2_flow preset template | Closest existing slot-planning system; 8-slot to card-count mapping |
| `pipeline.threads.contrast.extractor.extract_af` | existing | Fact extraction (A-F schema) | Reuse for slot1/slot2/slot3/slot4 population from source body |
| `pipeline.threads.contrast.prompts.SYSTEM_EXTRACTOR` | existing | Fact extraction prompt | Source for the A-F JSON schema used by contrast; compass slots map to subsets |
| `pipeline.infra.vectorize_client` | existing | Embedding for semantic dedup | Optional: could index compass outputs for pattern-repetition detection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `writeArticle` module | Extend `write_thread` with `format_choice="compass"` | Extension keeps existing D path untouched (writer.py:434-442 already has a `contrast` branch precedent); new module would duplicate crawl/parse/validate logic |
| Custom rotation counter | `performance_log` or `posted.json` date-based index | Counter must survive across runs; `posted.json` already persists per-run state in `pitch.py:426-487` |
| LLM-based fact-gate | Regex source-URL matching only | LLM ruling needed for paraphrased claims; regex alone catches only verbatim copies |

**Installation:**
No new external packages. All dependencies are existing in-repo modules.

**Version verification:** Not applicable -- no new external packages introduced.

## Package Legitimacy Audit

No new external packages introduced in Phase 39. All dependencies are existing in-repo modules (`pipeline.threads.*`, `v3.model_router`, `pipeline.infra.*`). No npm/PyPI/crates registry lookup required.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[D1 news DB / db_reader]
        |
        v
[crawler.fetch_article_body]  -- source body for fact-gate + slot population
        |
        v
[Pass 1: Compass Generator]
  - LLM call (chat_completion, json_schema)
  - Emits: category, slot1_fact, slot2_compare, slot3_context,
           slot4_outlook, intro_style, h2_flow, tone, table_plan
        |
        v
[G4 Fact-Gate on slot3_context]
  - Match each slot3 claim against source body text
  - Reject claims with no source support; block draft
        |
        v
[Pass 2: Body Drafter]
  - LLM call consuming compass JSON as [컴퍼스] header
  - Respects h2_flow outline, intro_style, tone, table_plan
        |
        v
[Post-draft validation]
  - validate_card_structure, validate_final_output,
    validate_model_message, Korean ratio >=30%
        |
        v
[writeArticle output: {"cards": [...], "link": "..."}]
```

### Recommended Project Structure
```
pipeline/threads/
├── writer.py              # extend: add format_choice="compass" branch at :434
├── compass.py             # NEW: Pass 1 compass generator + h2_flow presets + intro_style rotation
├── fact_gate.py           # NEW: G4 slot3 source-citation enforcement
├── validator.py           # existing: reuse validate_final_output etc.
├── crawler.py             # existing: fetch_article_body
├── pitch.py               # existing: detect_prompt_leak, pitch logic
└── contrast/              # existing: SLOT_PLAN, SLOT_DESC, extract_af as reusable patterns
```

### Pattern 1: Format-Choice Branch (from contrast precedent)
**What:** `write_thread()` already delegates to a separate writer when `format_choice != "D"`.
**When to use:** Add `format_choice="compass"` at `writer.py:434` alongside the existing `"contrast"` branch.
**Example:**
```python
# writer.py:434-442 (existing pattern)
if format_choice == "contrast":
    from pipeline.threads.contrast.contrast_writer import write_contrast_thread
    result = write_contrast_thread(pitch, all_articles or [])
    ...
    return result
```
**Source:** `[VERIFIED: pipeline/threads/writer.py:434-442]`

### Pattern 2: Fact-Index Slot Assignment (from contrast SYSTEM_OUTLINE)
**What:** Assign source-body fact indices (b_refs/c_refs) to each output segment; prevents hallucination by construction.
**When to use:** h2_flow presets and slot3_context population. Each h2 segment names which source-body fact it uses.
**Example:**
```python
# contrast_writer.py:21-29 (existing)
SYSTEM_OUTLINE = """...각 카드 1개 이상 b_refs 또는 c_refs 필수 (근거 없는 카드 금지)..."
SLOT_PLAN = {5: [[1], [2, 3], [4], [5, 6], [7, 8]]}  # contrast_writer.py:45
```
**Source:** `[VERIFIED: pipeline/threads/contrast/contrast_writer.py:21-51]`

### Pattern 3: JSON-First Parsing (from Phase 14)
**What:** Request `response_format={'type': 'json_object'}` then parse with `parse_cards_json_first()`; no delimiter fallback.
**When to use:** Both Pass 1 (compass JSON) and Pass 2 (body JSON). Already used by `write_thread()` at `writer.py:448,588`.
**Source:** `[VERIFIED: pipeline/threads/writer.py:448,588]`

### Anti-Patterns to Avoid
- **Replacing `write_thread` with a new `writeArticle`:** would duplicate the crawl/parse/validate chain already tested by `test_write_thread_validation.py`. Extend instead.
- **Regex-only fact-gate:** catches verbatim copies but not paraphrased claims. Use LLM ruling (Phase 28-05 pattern) plus regex.
- **Hardcoded rotation state in-memory:** loses rotation across runs. Persist counter in `posted.json` or `performance_log`.
- **Applying Threads banmal tone to Naver output:** Naver blog requires formal `~습니다/~합니다` per `naver-content-writing` skill.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Compass JSON generation | Custom prompt + parser | `v3.model_router.chat_completion` with `response_format=json_schema` | Single LLM entry point; already used by pitch/writer/evaluator |
| Fact extraction from source body | Custom regex entity extractor | `pipeline.threads.contrast.extractor.extract_af` (A-F schema) | Already validated; covers B (numeric), C (quotes), F (open questions) |
| h2_flow slot planning | Custom slot dict | `SLOT_PLAN` + `SLOT_DESC` from `contrast_writer.py` | Existing 8-slot to card-count mapping; proven in contrast pipeline |
| Card structure validation | Custom length/Korean-ratio checks | `validate_card_structure`, `validate_final_output` from `validator.py` | Already covers duplicates, Korean ratio >=15%/30%, sentence completeness, last-card-open-reply |
| Prompt leak detection | Custom fragment list | `detect_prompt_leak` from `pitch.py` | Covers 8 system fragments + 10 label patterns; imported by validator |
| Source body fetching | Custom HTTP + BeautifulSoup | `fetch_article_body` from `crawler.py` | Already handles retries, encoding, failed-crawl logging |
| Rotation state persistence | In-memory counter | `posted.json` (pitch.py:426-487) or `performance_log.record_publish` | Both already persist across runs |

**Key insight:** The contrast pipeline already solves ~70% of what Compass needs (fact-index slots, source-bound writing, JSON-first parsing, multi-stage validation). Compass differentiates on: 4-slot structure (not 8-slot), 5-pattern intro rotation, and G4 source-citation gate for slot3 specifically.
## Runtime State Inventory

Not applicable -- Phase 39 is net-new (greenfield). No rename/refactor/migration of existing strings.
No existing runtime state to inventory. Verified: no `compass`, `writeArticle`, `slot1..slot4`,
`h2_flow`, or `intro_style` strings exist anywhere in `pipeline/`, `scripts/`, or `tests/`
(grep returned zero matches).
## Common Pitfalls

### Pitfall 1: slot3 hallucination bypasses all existing gates
**What goes wrong:** `slot3_context` is the only slot with an explicit G4 fact-gate requirement,
but no existing validator checks that its claims trace to source URLs. A draft can pass
`validate_final_output` (Korean ratio, foreign language, prompt leak) while containing
entirely fabricated context claims.
**Why it happens:** Existing validation is output-surface-only (language, structure, labels).
It never cross-references the source body text against slot content.
**How to avoid:** Implement G4 as a two-layer check:
  1. Regex/substring match: each slot3 claim's key nouns+numbers must appear in `crawled_body`.
  2. LLM ruling (Phase 28-05 pattern): for paraphrased claims, call `chat_completion` asking
     "Does this claim follow from the source text? Answer true/false." Block on false.
**Warning signs:** slot3 contains claims with no matching substring in source body; LLM ruling
returns false; draft passes `validate_final_output` but fails G4.

### Pitfall 2: Pattern repetition across runs
**What goes wrong:** Without rotation, the same `intro_style` and `h2_flow` produce near-identical
articles every run, defeating the "diversify writing patterns" goal.
**Why it happens:** No rotation logic exists in the codebase. `format_selector.select_format()`
always returns `"D"`.
**How to avoid:** Maintain a rotation counter persisted in `posted.json` (following
`pitch.py:426-487` pattern). Index = counter % 5 for intro_style, counter % len(h2_flow presets)
for h2_flow. Increment counter only on successful publish.
**Warning signs:** Two consecutive runs produce articles with identical intro structure and H2 ordering.

### Pitfall 3: Compass field leak into published output
**What goes wrong:** Pass 2 LLM echoes compass metadata labels (`slot1_fact:`, `h2_flow:`,
`intro_style:`) into the body text, which then publishes.
**Why it happens:** The compass JSON is injected as a `[컴퍼스]` header into the Pass 2 user message.
The LLM can mistake those labels for output format instructions.
**How to avoid:** Run `detect_prompt_leak()` (pitch.py:63) on every draft card before publish.
Extend `LEAKED_PROMPT_PATTERNS` and `_SYSTEM_PROMPT_FRAGMENTS` to include compass field names
(`slot1_fact`, `slot2_compare`, `slot3_context`, `slot4_outlook`, `h2_flow`, `intro_style`).
**Warning signs:** Published card contains `slot3:` or `h2_flow:` prefixes.

### Pitfall 4: Tone mismatch between Threads and Naver targets
**What goes wrong:** Compass generates formal Naver tone (`~습니다/~합니다`) but the existing
`write_thread` D-format prompt mandates banmal (`~임/~했음`). Copying the D prompt for Compass
produces wrong tone for Naver blog output.
**Why it happens:** Two different output targets with incompatible tone rules exist in the
codebase/skills: Threads = banmal (`writer.py:66`), Naver blog = formal
(`naver-content-writing` skill, `jisang prompts-naver.md:88`).
**How to avoid:** Build a separate `build_system_prompt_compass()` that specifies formal tone
and HTML tag whitelist (p, h2, h3, strong, b, blockquote, hr, ul, ol, li, table, img, a).
Never reuse `build_system_prompt_D()` for Naver output.
**Warning signs:** Draft contains banmal endings (`~임`, `~했음`) when Naver formal is required;
draft contains `<div>`, `<span>`, or `class=` attributes.

### Pitfall 5: Cost blowup from unbounded Pass 1 + Pass 2 calls
**What goes wrong:** Every article costs 2 LLM calls (Pass 1 compass + Pass 2 body). With
100+ articles per run, this doubles API cost vs the existing single-pass D pipeline.
**Why it happens:** Compass is inherently 2-pass; no existing code amortizes this.
**How to avoid:** Cache compass outputs by `(article_id, date)` so the same article never
regenerates a compass on retry. Reuse `performance_log.record_publish` (main_v3.py:433) to
track per-article cost. Consider a `--compass` CLI flag so the D path remains single-pass
by default.
**Warning signs:** Per-run API cost doubles; retry loops regenerate compasses unnecessarily.
## Code Examples

### Example 1: write_thread entry point (existing, for reference)
**Source:** `[VERIFIED: pipeline/threads/writer.py:431-442]`
```python
def write_thread(pitch, all_articles, format_choice=None):
    if not format_choice:
        format_choice = 'D'
    # Contrast delegation -- keeps D path untouched
    if format_choice == "contrast":
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        result = write_contrast_thread(pitch, all_articles or [])
        if result is None:
            return []
        return result
    from v3.model_router import chat_completion
    ...
```

### Example 2: Existing validation chain inside write_thread
**Source:** `[VERIFIED: pipeline/threads/writer.py:598-632]`
```python
cards = fix_cards(cards)
cards = _cleanup_source_attribution(cards)
vc_ok, vc_reason = validate_cards(cards, pitch, format_choice)
vy_ok, vy_reason = validate_year(cards, article_body_text)
structure_ok, structure_reason = validate_card_structure(cards)
for i, card in enumerate(cards, 1):
    mm_ok, mm_reason = validate_model_message(card)
final_ok, final_reason = validate_final_output(cards, article_body_text)
cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
return {"cards": cards, "link": primary_url or ""}
```

### Example 3: Hook entity consistency check (closest existing fact-gate primitive)
**Source:** `[VERIFIED: pipeline/threads/validator.py:314-356]`
```python
def _validate_hook_body_entity_consistency(cards, source_text=None):
    """Hook(카드1)에 등장하는 주요 고유명사가 본문 카드(2~5)에 최소 1개 이상 등장하는지 검증.
    source_text가 주어지면, 그 엔티티가 크롤링 원문에 존재하는 경우 통과시킨다."""
    entities = _extract_hook_entities(hook_text)
    for entity in entities:
        if entity.lower() in body_lower:
            matched = True; break
        if source_text and entity.lower() in source_lower:
            matched = True  # 원문에 실재하는 엔티티 (음차 표기 허용)
            break
    if not matched:
        return False, f"Hook 고유명사({entity_list})가 본문 카드에 없음"
    return True, "OK"
```

### Example 4: Existing pitch fields (what a Compass pitch must extend)
**Source:** `[VERIFIED: pipeline/threads/writer.py:535-556]` (user_prompt construction)
```python
user_prompt = f"""Write a Threads thread based on the pitch and articles below.
=== PITCH ===
Hook: {pitch['hook']}
Narrative: {pitch.get('narrative','')}
Twist: {pitch.get('twist','')}
Emotion: {pitch.get('emotion','')}
But_line: {pitch.get('but_line','')}
Question: {pitch.get('question','')}
Gap source: {pitch.get('gap_source','')}
=== FORMAT ===
{FORMAT_LABELS[format_choice]}
=== ARTICLES ===
{related_text}"""
```
Compass adds `format_choice="compass"` and a `[컴퍼스]` block with the 9 compass fields
before the `=== ARTICLES ===` section.

### Example 5: Naver HTML tag whitelist (from naver-content-writing skill)
**Source:** `[CITED: naver-content-writing skill, HTML 출력 절대 규칙]`
```html
<!-- 허용: p, h2, h3, strong, b, blockquote, hr, ul, ol, li, table, img, a -->
<!-- 금지: div, span, style, class -->
<!-- 구조: <p>로 시작, 해시태그 문단으로 끝 -->
```

### Example 6: Compass JSON schema (target for Pass 1)
**Source:** `[CITED: CONTEXT.md stated requirements]`
```json
{
  "category": "AI_ regulation",
  "slot1_fact": "사건의 핵심 사실 한 줄",
  "slot2_compare": "과거/다른 사례와의 비교",
  "slot3_context": "배경/맥락 (G4 fact-gate 대상)",
  "slot4_outlook": "전망/미해결 쟁점",
  "intro_style": "number_shock",
  "h2_flow": ["사건 개요", "규모·수치", "배경 맥락", "인용·반응", "전망"],
  "tone": "neutral_careful",
  "table_plan": "none"
}
```
## Test Infrastructure

### How existing pipeline tests are run
**Source:** `[VERIFIED: pytest.ini]`
```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests that don't need external services
    integration: Tests that need D1 DB or network (not run by default)
strict_markers = true
pythonpath = scripts
```
- `python -m pytest` runs all tests in `tests/`
- `unit` tests run by default; `integration` tests are skipped unless `-m integration` is passed
- `pythonpath = scripts` means `import db_reader`, `import v3.model_router` work without manual sys.path manipulation inside test files (though existing tests still add paths manually at lines 8-9)

### Existing 16 failures
All failures are `integration`-marked tests requiring D1 DB or live network. They do NOT block
new `unit`-marked test addition. Verified by `test_write_thread_validation.py` (6 integration tests
using `monkeypatch` to mock `chat_completion`) and `test_writer.py` (unit tests on pure functions).

### How to add a test for compass generation and draft compliance
1. **Mark tests `@pytest.mark.unit`** so they run by default without D1/network.
2. **Mock `v3.model_router.chat_completion`** with `monkeypatch.setattr` -- same pattern as
   `test_write_thread_validation.py:132` (`monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)`).
3. **Mock `db_reader.validate_link`** to `lambda *a, **kw: True` -- same pattern as
   `test_write_thread_validation.py:122`.
4. **Test structure:**
   - `test_compass_has_all_9_fields`: Pass 1 mock returns compass JSON; assert all 9 keys present.
   - `test_compass_slot3_blocked_without_source`: slot3 claim with no matching substring in `crawled_body` → G4 returns False.
   - `test_compass_slot3_allowed_with_source`: slot3 claim whose key nouns appear in `crawled_body` → G4 returns True.
   - `test_intro_style_rotates`: run compass generation 5 times; assert 5 distinct `intro_style` values.
   - `test_h2_flow_followed`: Pass 2 mock returns body; assert H2 headings match compass `h2_flow` order.
   - `test_tone_formal`: Pass 2 body ends with `~습니다/~합니다`, not `~임/~했음`.
   - `test_no_compass_leak`: body cards contain no `slot1_fact:`, `h2_flow:`, or `intro_style:` prefixes.

### Test file location
New tests go in `tests/test_compass_*.py`, following the existing naming convention
(`test_writer.py`, `test_pitch.py`, `test_validator.py`).

### Wave 0 Gaps
- [ ] `tests/test_compass_generation.py` -- covers compass field completeness + rotation
- [ ] `tests/test_fact_gate.py` -- covers G4 slot3 source matching (regex + LLM ruling)
- [ ] `tests/test_compass_draft_compliance.py` -- covers h2_flow, tone, no-leak
- [ ] No new framework install needed; `pytest` already configured.
## Open Questions

1. **Which article source feeds the compass?**
   - What we know: `db_reader.get_articles()` returns D1 news rows; `fetch_article_body()` crawls the link; `writer.py:465-475` matches `pitch['article_ids']` against `all_articles`.
   - What's unclear: Whether Pass 1 reads from D1 directly, from a pre-crawled body, or from a manual article_id set.
   - Recommendation: Default to the existing D1 + crawl path used by `write_thread()` (writer.py:465-525). Add a `crawled_body` field to the pitch dict so the same path works without re-crawling.

2. **What are the 5 `intro_style` patterns and the `category` preset set for `h2_flow`?**
   - What we know: `intro_style` must rotate among 5 patterns; `h2_flow` is category-presets. Neither exists in code. The `contrast` module's `SLOT_PLAN` (contrast_writer.py:45) and `SLOT_DESC` (contrast_writer.py:32) are the closest template.
   - What's unclear: The exact 5 pattern names and the category→h2_flow mapping.
   - Recommendation: Define them in `compass.py` as two dicts (`INTRO_STYLES`, `H2_FLOW_PRESETS`) with a rotation counter. The planner/phase can refine the actual patterns; the structure is what matters now.

3. **Where does `writeArticle` live?**
   - What we know: `write_thread()` at `writer.py:431` is the closest existing function. It already has a `format_choice` parameter and a `contrast` branch precedent at `writer.py:434-442`.
   - What's unclear: Whether to extend `write_thread` in-place or create a new `write_article()` wrapper.
   - Recommendation: Extend `write_thread` with `format_choice="compass"`. This keeps the existing D path untouched (CONTEXT.md constraint: "Do not modify any existing phase or production code" applies to behavior, not adding a branch). The new compass branch delegates to `pipeline.threads.compass.write_compass_article()`.

4. **How is the G4 fact-gate implemented?**
   - What we know: Phase 28-05 introduced "heuristic 4 gates + LLM general-knowledge ruling via `validate_draft_quality()`". The contrast pipeline has `check_evidence()` (evidence_checker.py) and `check_gap_fidelity()` for quote verification.
   - What's unclear: Whether G4 should reuse `check_evidence()` or build a new slot3-specific checker.
   - Recommendation: Two-layer -- (a) substring/n-gram match of slot3 key terms against `crawled_body`, (b) LLM ruling for paraphrased claims. Block draft if either fails. This mirrors the 3-layer hallucination defense in TECH.md Section 13.3.

5. **What output target does Compass serve?**
   - What we know: The existing pipeline produces Threads cards (banmal, 5 cards, `---` separators). The `naver-content-writing` and `jisang` skills produce Naver blog HTML (formal, H2 structure, 1500-1800 chars, tag whitelist).
   - What's unclear: Whether Phase 39 targets Threads, Naver blog, or both.
   - Recommendation: Build Compass to emit a target-agnostic intermediate (cards or HTML paragraphs), with a `tone` field in the compass controlling banmal vs formal. The `writeArticle` function takes an `output_target` parameter (`threads` | `naver`).
## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All new pipeline modules | yes | 3.14 | -- |
| `v3.model_router.chat_completion` | Pass 1 + Pass 2 LLM calls | yes | existing | -- |
| `pipeline.threads.crawler.fetch_article_body` | Source body for fact-gate | yes | existing | D1 description fallback (writer.py:510-512) |
| `pipeline.threads.validator` | Post-draft validation | yes | existing | -- |
| OpenAI API key (GPT-4o-mini) | LLM calls | yes | via env | Free model chain (model_router fallback) |
| D1 news DB (`db_reader`) | Article source | yes | existing | Skip run if empty (main_v3.py:154-161) |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

## Validation Architecture

`workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. This section
is included for completeness but the planner should treat it as advisory, not mandatory.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pytest.ini` (testpaths=tests, pythonpath=scripts, markers unit/integration) |
| Quick run command | `python -m pytest tests/test_compass_*.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-01 | Pass 1 emits compass with all 9 fields | unit | `pytest tests/test_compass_generation.py::TestCompassFields -x` | No (Wave 0) |
| COMP-02 | G4 blocks slot3 claims without source support | unit | `pytest tests/test_fact_gate.py -x` | No (Wave 0) |
| COMP-03 | G4 allows slot3 claims with source support | unit | `pytest tests/test_fact_gate.py -x` | No (Wave 0) |
| COMP-04 | intro_style rotates across 5 runs | unit | `pytest tests/test_compass_generation.py::TestRotation -x` | No (Wave 0) |
| COMP-05 | Body follows compass h2_flow order | unit | `pytest tests/test_compass_draft_compliance.py -x` | No (Wave 0) |
| COMP-06 | Body uses formal tone (not banmal) | unit | `pytest tests/test_compass_draft_compliance.py -x` | No (Wave 0) |
| COMP-07 | No compass field leak in body output | unit | `pytest tests/test_compass_draft_compliance.py -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_compass_*.py -x -m unit`
- **Per wave merge:** `python -m pytest -m unit`
- **Phase gate:** All Wave 0 test files created and green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_compass_generation.py` -- covers COMP-01, COMP-04
- [ ] `tests/test_fact_gate.py` -- covers COMP-02, COMP-03
- [ ] `tests/test_compass_draft_compliance.py` -- covers COMP-05, COMP-06, COMP-07
- [ ] No framework install needed; pytest already configured.

## Security Domain

`security_enforcement` is enabled by default (absent from config = enabled). Phase 39 is a
writing pipeline with no user-facing auth, session, or access-control surface. The relevant
ASVS categories are input validation and cryptography-by-proxy.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A -- no auth surface |
| V3 Session Management | no | N/A -- no session state |
| V4 Access Control | no | N/A -- no access-controlled resources |
| V5 Input Validation | yes | Source body text is untrusted input; validate via G4 fact-gate before drafting |
| V6 Cryptography | no | N/A -- no crypto operations |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via source body | Tampering | `detect_prompt_leak()` on every card (pitch.py:63); extend patterns for compass fields |
| Hallucinated facts in slot3 | Information disclosure | G4 fact-gate: substring match + LLM ruling against `crawled_body` |
| Compass field leak into published output | Information disclosure | `validate_final_output()` + extended `LEAKED_PROMPT_PATTERNS` for `slot1_fact`, `h2_flow`, `intro_style` |
| HTML injection in Naver output | Injection | Tag whitelist (p, h2, h3, strong, b, blockquote, hr, ul, ol, li, table, img, a); no div/span/style/class |
## Sources

### Primary (HIGH confidence)
- `pipeline/threads/writer.py:431-632` -- `write_thread()` signature, format-choice branch, validation chain, return contract.
- `pipeline/threads/validator.py:100-572` -- `validate_cards`, `validate_year`, `validate_final_output`, `_validate_hook_body_entity_consistency`, `validate_speaker_attribution`, `validate_card_structure`, `_validate_last_card_opens_reply`, `MODEL_MESSAGE_PATTERNS`, `FORMAT_CARD_COUNTS`.
- `pipeline/threads/pitch.py:33-108,426-487` -- `LEAKED_PROMPT_PATTERNS`, `detect_prompt_leak`, `clean_leaked_prompt`, `save_pitch_to_history` (posted.json persistence pattern).
- `pipeline/threads/crawler.py:26-83` -- `log_failed_crawl`, `fetch_article_body` signature and retry behavior.
- `pipeline/threads/contrast/contrast_writer.py:21-90` -- `SYSTEM_OUTLINE`, `SLOT_DESC`, `SLOT_PLAN`, `SYSTEM_SENTENCE` (fact-index slot assignment pattern).
- `pipeline/threads/contrast/orchestrator.py:15-80` -- `run_contrast_thread` end-to-end flow (extractor -> background -> writer -> validator).
- `pipeline/threads/contrast/prompts.py:11-53` -- `SYSTEM_EXTRACTOR` (A-F fact schema), `SYSTEM_CURATOR_CONTRAST`.
- `pipeline/threads/pitch_evaluator.py:21-108` -- `EVAL_SYSTEM_PROMPT` (6-criteria rubric), `evaluate_pitch`, `filter_pitches`.
- `scripts/threads/main_v3.py:134-509` -- `run_v3()` orchestrator, dry-run vs publish paths, `performance_log.record_publish` at :433.
- `pytest.ini` -- test configuration, markers, pythonpath.

### Secondary (MEDIUM confidence)
- `jisang/references/prompts-naver.md:1-41,65-164` -- `NAV_COMPASS_PROMPT` (Pass 1 compass schema), `NAVER_BLOG_SYSTEM_PROMPT` (fact sealing, tone, HTML rules, length 1500-1800).
- `jisang/references/devices.md:1-57` -- type-router matrix (seedKind x mode -> required devices).
- `naver-content-writing` skill -- HTML tag whitelist, smart-editor compatibility, length targets, prose vs listicle styles.
- `docs/TECH.md:1-11` -- pipeline overview, entry points, function location table.
- `AGENTS.md:110-122` -- 3-stage semantic dedup, `extract_title_entities` pattern.

### Tertiary (LOW confidence)
- The 5 `intro_style` pattern names and `category` preset set for `h2_flow` are not defined anywhere in code or skills. Recommendation only.
- The exact `writeArticle` signature is a planning decision, not a research finding.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `writeArticle` will be implemented as `format_choice="compass"` branch in existing `write_thread()` rather than a separate module | Standard Stack / Architecture Patterns | If planner chooses a separate module, the crawl/parse/validate chain must be duplicated or refactored |
| A2 | The 5 `intro_style` patterns are: `self_identity_call`, `number_shock`, `reversal`, `contrast`, `conflicting_fact` (derived from jisang prompts-threads.md:62-66 hook patterns) | Open Questions #2 | Actual pattern names and semantics may differ; planner must confirm with user |
| A3 | `h2_flow` category presets will be a static dict in `compass.py`, modeled on `SLOT_PLAN` (contrast_writer.py:45) | Architecture Patterns | If presets need to be dynamic/learned, the static-dict approach is insufficient |
| A4 | G4 fact-gate uses two layers: substring match + LLM ruling (mirrors Phase 28-05 and TECH.md Section 13.3 3-layer defense) | Common Pitfalls #1 | If a simpler single-layer check suffices, the LLM ruling adds cost |
| A5 | Rotation counter persists in `posted.json` following `pitch.py:426-487` pattern | Common Pitfalls #2 | If `posted.json` schema changes, rotation state may be lost on migration |
| A6 | Compass output target is parameterized (`threads` \| `naver`), with `tone` field controlling banmal vs formal | Open Questions #5 | If only one target is needed, the parameter is unnecessary overhead |
| A7 | The 16 existing test failures are all `integration`-marked and do not block `unit`-test addition | Test Infrastructure | If some failing `unit` tests exist, new tests may inherit flakiness |
| A8 | No `compass`, `writeArticle`, `slot1..slot4`, `h2_flow`, or `intro_style` strings exist in the codebase (grep returned zero matches) | Runtime State Inventory | If a hidden reference exists, it was missed by grep scope |