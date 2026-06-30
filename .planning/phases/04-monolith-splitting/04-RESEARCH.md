# Phase 4: Monolith Splitting — Research

**Researched:** 2026-06-30
**Domain:** Python refactoring, modular extraction, Strangler Fig migration, test-driven monolith decomposition
**Confidence:** HIGH

## Summary

Phase 4 splits the two largest monoliths — `writer_v3.py` (1,018 lines) and `narrative_pitcher.py` (589 lines) — into focused, independently testable modules under `pipeline/threads/`. This research maps every internal function call within both monoliths, identifies clear extraction boundaries, defines public APIs for each extracted module, and specifies the Strangler Fig wiring that keeps the pipeline running during transition.

**Key findings:**

1. **writer_v3.py** contains four clearly separable concern groups: (a) card/year/keyword validation (pure functions), (b) article crawling and link validation (network-dependent), (c) format-building, post-processing, and LLM-based fixing (writer core), and (d) `write_thread()` — the orchestrator that ties them together.

2. **narrative_pitcher.py** imports `fetch_article_body` from `writer_v3` (line 9) — this is the critical cross-module dependency that must be broken first. The pitch logic (JSON parsing, dedup, history) is separable from pitch evaluation (LLM-based quality gate).

3. **Strangler Fig pattern:** New modules go under `pipeline/threads/`. Old files re-import from new locations. Old import paths (`from v3.writer_v3 import fetch_article_body`) continue working via re-exports. The pipeline never breaks.

4. **MVP vertical slice:** Extract validator.py (pure functions, zero dependencies) → verify tests → extract crawler.py → wire into writer_v3.py. This is the thinnest end-to-end slice that proves the pattern.

5. **No new pip dependencies** — the project uses `openai`, `beautifulsoup4`, `lxml` which are already installed in the venv. All extraction is pure code restructuring.

### Primary recommendation
Extract in dependency order: `validator.py` (zero dependencies) → `crawler.py` (network only) → `pitch_evaluator.py` (LLM only) → `pitch.py` (depends on dedup/db_reader) → `writer.py` (depends on validator, crawler, model_router). Each extraction is a Strangler Fig step: create new module → import from it in old file → keep old import paths alive → verify tests pass.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Card/year/keyword validation | Library/Utils | — | Pure functions, no I/O, no network, no LLM. Belongs in shared utility module. |
| Article crawling | Infrastructure | — | Network I/O via HTTP/BeautifulSoup. Isolated from business logic. |
| Format building / system prompts | Domain | — | LLM prompt construction with file-backed style examples. Writer-specific. |
| LLM interaction (chat_completion) | Infrastructure | — | Model routing between GPT-4o-mini, DeepSeek, MiMo. Cross-cutting concern. |
| Pitch evaluation (LLM quality gate) | Domain | — | Domain-specific LLM call — rates pitch quality. Narrow interface. |
| Pitch dedup / history management | Domain | Data | File-based posted.json I/O + pure comparison logic. |
| Orchestration (write_thread, get_pitches) | Application | — | Composes domain + infrastructure modules. Owned by new extracted modules. |
| Final card validation (validate_final_cards) | Application | — | Pre-publish gate in main_v3.py. Uses INSTRUCTION_PATTERNS from writer. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | 1.109.1 | LLM API client (GPT-4o-mini, DeepSeek, MiMo via OpenAI-compatible API) | Already in venv; project-standard LLM router |
| beautifulsoup4 | 4.15.0 | HTML parsing for article crawling | Already in venv; needed by crawler module |
| lxml | 6.1.1 | Fast HTML/XML parser for BeautifulSoup | Already in venv; bs4 default parser |
| Python 3.14 stdlib | 3.14.5 | `json`, `re`, `datetime`, `collections`, `urllib`, `subprocess`, `pathlib` | All extraction uses only stdlib beyond the three above |

### Installation
No new packages required. All dependencies are already installed in the project venv:
```bash
# Verify existing packages
python3 -c "import openai, bs4, lxml; print('All dependencies available')"
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| requests + BeautifulSoup | httpx | Same capability; requests already installed. No reason to change. |
| lxml | html.parser (stdlib) | lxml is faster and more robust. Already installed. |

## Package Legitimacy Audit

> Phase 4 installs no new packages. The three existing packages below were verified on PyPI.

| Package | Registry | Age | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-------------|-----------|-------------|
| openai | PyPI | 4+ yrs | github.com/openai/openai-python | [OK] | Pre-existing — no new install |
| beautifulsoup4 | PyPI | 16+ yrs | crummy.com/software/BeautifulSoup | [OK] | Pre-existing — no new install |
| lxml | PyPI | 15+ yrs | lxml.de | [OK] | Pre-existing — no new install |

*Note: slopcheck defaults to npm registry and incorrectly flagged `lxml` and `beautifulsoup4` as npm packages. Cross-ecosystem verification with `pip show` confirmed all three are legitimate PyPI packages. No new packages are added in this phase.*

## Dependency Graph: writer_v3.py (1,018 lines)

### Internal Function Map

```
writer_v3.py module-level:
├── load_style_examples() → str                          [FILE I/O]
│   └── Called by: build_system_prompt_D()
│
├── build_system_prompt_D() → str                        [PURE]
│   └── Calls: load_style_examples()
│   └── Called by: write_thread() (via FORMAT_BUILDERS)
│
├── _FORMAT_COMMON_RULES(examples) → str                 [PURE]
│   └── UNUSED — dead code (was used by A/B/C format builders, now removed)
│
├── log_failed_crawl(url, source, title, status) → None  [FILE I/O]
│   └── Called by: fetch_article_body(), write_thread()
│
├── fetch_article_body(url, source, title) → str         [NETWORK + BEAUTIFULSOUP]
│   ├── Calls: log(), log_failed_crawl()
│   ├── Uses: requests.get, BeautifulSoup
│   ├── Called by: write_thread(), narrative_pitcher.get_pitches() [CROSS-MODULE!]
│   └── Imported by: narrative_pitcher.py (line 9)
│
├── _strip_instruction_leak(text) → str                  [PURE]
│   └── Called by: humanize_cards()
│
├── humanize_cards(cards) → list[str]                    [LLM]
│   ├── Calls: chat_completion (from v3.model_router), _strip_instruction_leak()
│   └── Called by: fix_cards()
│
├── _cleanup_source_attribution(cards) → list[str]       [PURE]
│   └── Called by: write_thread()
│
├── _clean_english_leakage(text) → str                   [PURE]
│   └── Called by: fix_cards()
│
├── _fix_korean_particle_spacing(text) → str             [PURE]
│   └── Called by: fix_cards()
│
├── fix_cards(cards) → list[str]                         [LLM + PURE]
│   ├── Calls: _clean_english_leakage(), _fix_korean_particle_spacing(),
│   │          humanize_cards(), chat_completion (from v3.model_router)
│   └── Called by: write_thread()
│
├── write_thread(pitch, all_articles, format_choice)     [ORCHESTRATOR — LLM + NETWORK]
│   ├── Calls: chat_completion (from v3.model_router),
│   │          select_format (from v3.format_selector),
│   │          fetch_article_body(), log_failed_crawl(),
│   │          parse_cards(), fix_cards(), _cleanup_source_attribution(),
│   │          validate_cards(), validate_year(), validate_keywords(),
│   │          assemble_final(), db_reader.validate_link(),
│   │          FORMAT_BUILDERS, FORMAT_LABELS
│   └── Called by: main_v3.run_v3()
│   └── NOTE: Recursive fallback to self with format_choice='D'
│
├── parse_cards(text, format_choice) → list[str]         [PURE]
│   └── Called by: write_thread()
│
├── validate_cards(cards, pitch, format_choice) → bool   [PURE]
│   └── Called by: write_thread()
│
├── validate_year(cards, article_body_text) → bool       [PURE]
│   └── Called by: write_thread()
│
├── validate_keywords(cards, article_body_text) → bool   [PURE]
│   └── Called by: write_thread()
│
├── assemble_final(cards, articles, primary_url,          [PURE + NETWORK]
│                  crawled_urls, format_choice) → list
│   ├── Calls: db_reader.validate_link()
│   └── Called by: write_thread()
│
├── save_draft(cards, pitch) → str                       [FILE I/O]
│   └── Called by: write_thread() (via main_v3.run_v3()), __main__
│
└── __main__                                              [SCRIPT]
    ├── Calls: db_reader.get_articles(), narrative_pitcher.get_pitches()
    │          write_thread(), save_draft()
```

### External Imports in writer_v3.py
| Import Source | Target | Where Used |
|---|---|---|
| `v3.model_router` | `chat_completion` | humanize_cards(), fix_cards(), write_thread() |
| `v3.format_selector` | `select_format` | write_thread() |
| `v3.narrative_pitcher` | `get_pitches` | __main__ only |
| `db_reader` | `validate_link` | write_thread(), assemble_final() |
| `db_reader` | `get_articles` | __main__ only |
| `requests` | `.get` | fetch_article_body() |
| `bs4` | `BeautifulSoup` | fetch_article_body() |
| `pipeline.infra` | `project_root` | Module-level |
| `pipeline.infra.logger` | `get_scrubbed_logger` | Module-level |

## Dependency Graph: narrative_pitcher.py (589 lines)

### Internal Function Map

```
narrative_pitcher.py module-level:
├── load_env() → None                                     [FILE I/O]
│   └── Called at module level (script-style)
│
├── fill_article_ids(pitch, articles_text) → dict         [PURE]
│   └── Called by: parse_pitches_from_text() (internal, fallback path)
│
├── parse_pitches_from_text(text, articles_text=None)     [PURE]
│   └── Called by: get_pitches(), parse_top_pitch(), _regenerate_pitch_from_crawl()
│
├── parse_top_pitch(text, fallback_pitches) → dict        [PURE]
│   ├── Calls: parse_pitches_from_text()
│   └── Called by: (unused directly — fallback path in get_pitches is manual)
│
├── load_pitch_history() → list                           [FILE I/O]
│   └── Called by: get_pitches()
│
├── is_duplicate_pitch(pitch, history, posted) → bool     [PURE(ish)]
│   ├── Calls: db_reader.normalize_url(), dedup.is_same_topic()
│   └── Called by: get_pitches()
│
├── save_pitch_to_history(pitch) → None                   [FILE I/O]
│   └── Called by: main_v3.run_v3()
│
├── get_pitches(articles, max_articles, batch_size)        [ORCHESTRATOR — LLM + NETWORK]
│   ├── Calls: chat_completion (from v3.model_router) [LLM],
│   │          parse_pitches_from_text() [PURE],
│   │          pitch_evaluator.filter_pitches() [LLM],
│   │          fetch_article_body() [NETWORK — imported from writer_v3!],
│   │          _regenerate_pitch_from_crawl() [LLM],
│   │          is_duplicate_pitch() [PURE],
│   │          load_pitch_history(), db_reader.load_posted() [FILE I/O]
│   └── Called by: main_v3.run_v3()
│
├── _regenerate_pitch_from_crawl(body, article_id,        [LLM]
│          article_url, article_title, original_pitch) → dict
│   ├── Calls: chat_completion (from v3.model_router), parse_pitches_from_text()
│   └── Called by: get_pitches()
│
└── __main__                                              [SCRIPT]
    └── Calls: db_reader.get_articles(), get_pitches()
```

### External Imports in narrative_pitcher.py
| Import Source | Target | Where Used |
|---|---|---|
| **`v3.writer_v3`** | **`fetch_article_body`** | **get_pitches()** — CRITICAL CROSS-DEPENDENCY |
| `v3.model_router` | `chat_completion` | get_pitches(), _regenerate_pitch_from_crawl() |
| `v3.pitch_evaluator` | `filter_pitches` | get_pitches() |
| `db_reader` | `normalize_url` | Module-level import |
| `db_reader` | `load_posted` | get_pitches() |
| `dedup` | `is_same_topic, article_keywords, article_entities` | Module-level import |
| `pipeline.infra` | `project_root` | Module-level |
| `pipeline.infra.env_loader` | `EnvConfig` | Module-level |
| `pipeline.infra.logger` | `get_scrubbed_logger` | Module-level |

### pitch_evaluator.py (94 lines) — Function Map
```
pitch_evaluator.py:
├── evaluate_pitch(pitch) → (bool, int, str)              [LLM]
│   ├── Calls: chat_completion (from v3.model_router)
│   └── Called by: filter_pitches()
│
└── filter_pitches(pitches) → dict or None                [PURE orchestration]
    └── Calls: evaluate_pitch()
```

## Module Boundaries & Interfaces

### Extracted Module 1: `pipeline/threads/validator.py`

**Public API:**

```python
def validate_cards(cards: list[str], pitch: dict, format_choice: str = 'D') -> bool
    """Validate card count (+/- tolerance) and hook line existence.
    Returns True if valid, False otherwise."""
    # Source: writer_v3.py validate_cards() — pure function, same logic

def validate_year(cards: list[str], article_body_text: str) -> bool
    """Validate that years in thread body exist in article body.
    Excludes hook line (1st card, 1st line). Current year always allowed.
    Returns True if valid, False if hallucinated year detected."""
    # Source: writer_v3.py validate_year() — pure function, same logic

def validate_keywords(cards: list[str], article_body_text: str) -> bool
    """Validate that article keywords aren't truncated/missing in thread.
    Returns True if valid or couldn't validate."""
    # Source: writer_v3.py validate_keywords() — pure function, same logic

def validate_thread(content: str) -> tuple[bool, list[str]]
    """Legacy 8-card thread validation. Returns (passed, failure_reasons)."""
    # Source: scripts/threads/validator.py validate_thread() — pure function
```

**Dependencies:** `re`, `datetime`, `collections.Counter` (all stdlib)
**Dependents:** `writer_v3.py write_thread()`, `main_v3.py validate_final_cards()` (indirect via INSTRUCTION_PATTERNS)
**Tests:** 3 validation functions × normal/edge/failure cases = 6-9 test functions. Plus `test_validate_thread` from V1 format (2 tests).

### Extracted Module 2: `pipeline/threads/crawler.py`

**Public API:**

```python
def fetch_article_body(url: str, source: str = '', title: str = '') -> str
    """Fetch and extract article body text via HTTP+BeautifulSoup.
    2 retries with 3s delay. Logs failures to failed_crawls.json.
    Returns extracted text or empty string on failure."""
    # Source: writer_v3.py fetch_article_body()

def log_failed_crawl(url: str, source: str, title: str, status: str) -> None
    """Record failed crawl to failed_crawls.json with dedup."""
    # Source: writer_v3.py log_failed_crawl()

# Internal (no longer exported):
#   _log() — internal logging, uses the project logger
```

**Dependencies:** `requests`, `bs4.BeautifulSoup`, `pipeline.infra.logger`, `pipeline.infra.project_root`, `json`, `os`, `time`, `datetime`
**Dependents:** `writer_v3.py write_thread()`, `narrative_pitcher.py get_pitches()` (imports from v3.writer_v3)
**Tests:** 3-4 test functions (mocked HTTP, retry behavior, failure logging)

### Extracted Module 3: `pipeline/threads/writer.py`

**Public API:**

```python
def build_system_prompt_D() -> str
    """Build the format D system prompt with style examples."""
    # Source: writer_v3.py build_system_prompt_D()

def parse_cards(text: str, format_choice: str = 'D') -> list[str]
    """Parse --- separated cards with D format stanza merging."""
    # Source: writer_v3.py parse_cards()

def fix_cards(cards: list[str]) -> list[str]
    """Full fix pipeline: english leakage → particle spacing → humanize → LLM fix."""
    # Source: writer_v3.py fix_cards()

def humanize_cards(cards: list[str]) -> list[str]
    """LLM-based AI-tic replacement (translation, filler, exaggeration patterns)."""
    # Source: writer_v3.py humanize_cards()

def assemble_final(cards: list[str], articles: list[dict],
                   primary_url: str = None, crawled_urls: list[str] = None,
                   format_choice: str = 'D') -> list[str]
    """Append source URL to last card, validate URL accessibility."""
    # Source: writer_v3.py assemble_final()

def save_draft(cards: list[str], pitch: dict) -> str
    """Save thread draft to logs/drafts/ directory. Returns filepath."""
    # Source: writer_v3.py save_draft()

def cleanup_source_attribution(cards: list[str]) -> list[str]
    """Remove '출처:' patterns and year hallucination (2000) from cards."""
    # Source: writer_v3.py _cleanup_source_attribution()

def clean_english_leakage(text: str) -> str
    """Remove English text that leaked into Korean output without spaces."""
    # Source: writer_v3.py _clean_english_leakage()

def fix_korean_particle_spacing(text: str) -> str
    """Add space between English capitalized word and Korean particle."""
    # Source: writer_v3.py _fix_korean_particle_spacing()

def strip_instruction_leak(text: str) -> str
    """Remove prompt instruction text leaked into LLM output."""
    # Source: writer_v3.py _strip_instruction_leak()

# THE ORCHESTRATOR:
def write_thread(pitch: dict, all_articles: list[dict],
                 format_choice: str = None) -> list[str]
    """Main thread writing pipeline: format select → crawl → LLM → validate → assemble.
    This is THE function that orchestrates crawler, validator, and writer modules."""
    # Source: writer_v3.py write_thread()
```

**Dependencies:** `v3.model_router.chat_completion`, `v3.format_selector.select_format`, `pipeline.threads.crawler.fetch_article_body`, `pipeline.threads.crawler.log_failed_crawl`, `pipeline.threads.validator.*`, `db_reader.validate_link`, `pipeline.infra.logger`, `re`, `json`, `datetime`, `os`, `time`
**Dependents:** `main_v3.py run_v3()`

### Extracted Module 4: `pipeline/threads/pitch.py`

**Public API:**

```python
def fill_article_ids(pitch: dict, articles_text: list[str]) -> dict
    """Auto-match article IDs to pitch by keyword scoring."""
    # Source: narrative_pitcher.py fill_article_ids()

def parse_pitches_from_text(text: str) -> list[dict]
    """Extract pitch JSON blocks from LLM response. Supports 3 schemas."""
    # Source: narrative_pitcher.py parse_pitches_from_text()

def parse_top_pitch(text: str, fallback_pitches: list[dict]) -> dict | None
    """Parse LLM response for top pitch with fallback chain."""
    # Source: narrative_pitcher.py parse_top_pitch()

def load_pitch_history() -> list[dict]
    """Load posted.json pitch history."""
    # Source: narrative_pitcher.py load_pitch_history()

def is_duplicate_pitch(pitch: dict, history: list[dict],
                       posted: dict | None = None) -> bool
    """4-phase dedup: exact match → hook/narrative → article id overlap → semantic."""
    # Source: narrative_pitcher.py is_duplicate_pitch()

def save_pitch_to_history(pitch: dict) -> None
    """Save pitch to posted.json with entity extraction."""
    # Source: narrative_pitcher.py save_pitch_to_history()

# THE ORCHESTRATOR:
def get_pitches(articles: list[dict], max_articles: int = 600,
                batch_size: int = 200) -> list[dict]
    """Full pitch pipeline: batch articles → LLM → parse → dedup → evaluate → crawl → regenerate.
    Returns list with 1 pitch or empty list."""
    # Source: narrative_pitcher.py get_pitches()
```

**Dependencies:** `v3.model_router.chat_completion`, `pipeline.threads.crawler.fetch_article_body`, `pipeline.threads.pitch_evaluator.filter_pitches`, `db_reader.normalize_url`, `db_reader.load_posted`, `dedup.is_same_topic`, `random`, `re`, `json`, `datetime`, `os`
**Dependents:** `main_v3.py run_v3()`

### Extracted Module 5: `pipeline/threads/pitch_evaluator.py`

**Public API:**

```python
def evaluate_pitch(pitch: dict) -> tuple[bool, int, str]
    """LLM-based pitch quality evaluation (0-5 score, 3+ passes).
    Direction mismatch (criterion 3) causes hard fail regardless of score."""
    # Source: v3/pitch_evaluator.py evaluate_pitch()

def filter_pitches(pitches: list[dict]) -> dict | None
    """Iterate candidate pitches, return first that passes quality gate."""
    # Source: v3/pitch_evaluator.py filter_pitches()
```

**Dependencies:** `v3.model_router.chat_completion`, `pipeline.infra.logger`, `json`, `re`, `datetime`, `os`
**Dependents:** `pipeline/threads/pitch.py get_pitches()`

### Module Dependency Graph (after extraction)

```
main_v3.py
  └── writes v3.writer_v3 (via __main__)      ──→ [Strangler Fig re-exports]
  └── writes v3.narrative_pitcher (via __main__)

v3.writer_v3 (shrinks to thin re-export wrapper)
  ├── import from pipeline.threads.writer → write_thread()
  ├── import from pipeline.threads.crawler → fetch_article_body()
  ├── import from pipeline.threads.validator → validate_cards(), validate_year(), validate_keywords()
  └── re-exports fetch_article_body for narrative_pitcher

v3.narrative_pitcher (shrinks to thin re-export wrapper)
  ├── import from pipeline.threads.pitch → get_pitches()
  ├── import from pipeline.threads.pitch_evaluator → evaluate_pitch(), filter_pitches()
  └── import from pipeline.threads.crawler → fetch_article_body() (instead of v3.writer_v3)

pipeline.threads.writer
  ├── import from pipeline.threads.crawler → fetch_article_body()
  ├── import from pipeline.threads.validator → validate_cards(), validate_year(), validate_keywords()
  ├── import from v3.model_router → chat_completion()
  ├── import from v3.format_selector → select_format()
  └── import from db_reader → validate_link()

pipeline.threads.pitch
  ├── import from pipeline.threads.crawler → fetch_article_body()
  ├── import from pipeline.threads.pitch_evaluator → filter_pitches()
  ├── import from v3.model_router → chat_completion()
  ├── import from db_reader → normalize_url(), load_posted()
  └── import from dedup → is_same_topic()

pipeline.threads.crawler
  └── import from pipeline.infra → logger, project_root

pipeline.threads.validator
  └── stdlib only (re, datetime, collections)

pipeline.threads.pitch_evaluator
  ├── import from v3.model_router → chat_completion()
  └── import from pipeline.infra → logger
```

## Integration Strategy

### Strangler Fig Pattern

Each extraction follows the same 4-step sequence:

```
Step 1: CREATE new module in pipeline/threads/
Step 2: IMPORT from new module in old file (replace inline definitions)
Step 3: RE-EXPORT from old file for dependent modules
Step 4: VERIFY old import paths still work → run tests
```

**Real example — validator extraction:**

```python
# Step 1: Create pipeline/threads/validator.py
# pipeline/threads/validator.py contains validate_cards(), validate_year(), validate_keywords()

# Step 2: writer_v3.py replaces inline definitions with imports
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords

# Step 3: writer_v3.py re-exports for any module that imports from v3.writer_v3
# (No external module imports these specifically, so no re-export needed)

# Step 4: Tests pass ✓
```

**Real example — crawler extraction (cross-module dependency):**

```python
# Step 1: Create pipeline/threads/crawler.py with fetch_article_body(), log_failed_crawl()

# Step 2: writer_v3.py replaces inline definitions
from pipeline.threads.crawler import fetch_article_body, log_failed_crawl

# Step 3: narrative_pitcher.py imports fetch_article_body from v3.writer_v3
# We keep the re-export in writer_v3.py so the old import still works:
# writer_v3.py: from pipeline.threads.crawler import fetch_article_body (replaces def)
# narrative_pitcher.py: from v3.writer_v3 import fetch_article_body (STILL WORKS!)

# Step 4: Tests pass ✓
```

**Final state of old wrapper files:**
```python
# scripts/threads/v3/writer_v3.py — thin re-export wrapper
from pipeline.threads.crawler import fetch_article_body, log_failed_crawl
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords
from pipeline.threads.writer import (write_thread, save_draft, parse_cards,
    fix_cards, assemble_final, humanize_cards, ...)
# Keep module-level constants and LOAD_STYLE_EXAMPLES for backward compat
from pipeline.threads.writer import (FORMAT_LABELS, FORMAT_CARD_COUNTS,
    FORMAT_CARD_COUNT_TOLERANCE, FORMAT_BUILDERS, INSTRUCTION_PATTERNS,
    STYLE_EXAMPLES_PATH, load_style_examples)
```

```python
# scripts/threads/v3/narrative_pitcher.py — thin re-export wrapper
from pipeline.threads.pitch import (get_pitches, fill_article_ids,
    parse_pitches_from_text, parse_top_pitch, load_pitch_history,
    is_duplicate_pitch, save_pitch_to_history, _regenerate_pitch_from_crawl)
from pipeline.threads.pitch_evaluator import evaluate_pitch, filter_pitches
from pipeline.threads.crawler import fetch_article_body
```

### Can Old Files Import From pipeline/threads/* Directly?

**Yes.** The `pipeline/threads/__init__.py` package marker already exists. Python's import system resolves `pipeline.threads.writer` regardless of where the importing file lives, as long as `pipeline/` is on `sys.path`.

The `sys.path.insert(0, ...)` in `main_v3.py` adds `PROJECT_DIR` to the path, so `from pipeline.threads.writer import write_thread` will work from anywhere.

**Key constraint:** The old scripts run via `main_v3.py` which does `sys.path.insert(0, PROJECT_DIR)`. This is already in place from Phase 3.

## Orchestrator Integration

### Current State (Phase 3)
```
pipeline/__main__.py
  └── PipelineOrchestrator
        └── StepRunThreads
              └── subprocess: .venv/bin/python3 scripts/threads/main_v3.py --once
                    └── main_v3.run_v3()
                          ├── db_reader.get_articles()
                          ├── narrative_pitcher.get_pitches()
                          ├── writer_v3.write_thread()
                          └── publisher.publish_thread_chain()
```

### Phase 4 State (no subprocess change — old entry point wraps new modules)
```
pipeline/__main__.py  (UNCHANGED)
  └── PipelineOrchestrator
        └── StepRunThreads  (UNCHANGED)
              └── subprocess: .venv/bin/python3 scripts/threads/main_v3.py --once
                    └── main_v3.run_v3()
                          ├── db_reader.get_articles()  (UNCHANGED)
                          ├── narrative_pitcher.get_pitches()  (THIN WRAPPER)
                          │     └── pipeline.threads.pitch.get_pitches()
                          │           └── pipeline.threads.pitch_evaluator.filter_pitches()
                          │           └── pipeline.threads.crawler.fetch_article_body()
                          ├── writer_v3.write_thread()  (THIN WRAPPER)
                          │     └── pipeline.threads.writer.write_thread()
                          │           └── pipeline.threads.crawler.fetch_article_body()
                          │           └── pipeline.threads.validator.validate_*
                          └── publisher.publish_thread_chain()  (UNCHANGED)
```

**Why NOT change the subprocess wrapper in Phase 4:**
- `StepRunThreads` is a working Strangler Fig wrapper (created in Phase 3)
- Changing it to direct import would require migrating env loading, sys.path setup, and error handling
- The subprocess boundary is harmless — the pipeline runs every 2 hours, 600s overhead is negligible
- Phase 5 (dead code removal) is the right time to make `StepRunThreads` import new modules directly

## Test Strategy

### Existing Tests (13 characterization tests from Phase 3)
| Test File | Tests | Purpose |
|---|---|---|
| `test_characterization_validate_final_cards.py` | 8 | validate_final_cards() edge cases |
| `test_characterization_pure_functions.py` | 5 | validate_thread() + validate_final_cards() edge |

These serve as the **regression gate** — they must pass unchanged at every step of Phase 4.

### New Tests for Extracted Modules

**validator.py tests (4-6 new test functions):**

```python
# tests/test_validator.py
class TestValidateCards:
    def test_valid_card_count(self): ...
    def test_invalid_card_count_too_few(self): ...
    def test_invalid_card_count_too_many(self): ...
    def test_first_line_too_short(self): ...

class TestValidateYear:
    def test_year_valid(self): ...
    def test_year_hallucinated(self): ...
    def test_current_year_allowed(self): ...
    def test_no_year_in_thread_passes(self): ...

class TestValidateKeywords:
    def test_keywords_match(self): ...
    def test_keywords_truncated(self): ...
    def test_few_keywords_no_fail(self): ...
```

**crawler.py tests (3-4 new test functions, using monkeypatch_http):**

```python
# tests/test_crawler.py
class TestFetchArticleBody:
    def test_successful_crawl(self, monkeypatch_http): ...
    def test_retry_on_failure(self, monkeypatch): ...
    def test_all_attempts_fail(self, monkeypatch): ...
```

**writer.py tests (5-7 new test functions):**

```python
# tests/test_writer.py
class TestParseCards:
    def test_normal_parse(self): ...
    def test_d_format_stanza_merge(self): ...

class TestCleanFunctions:
    def test_english_leakage_cleanup(self): ...
    def test_particle_spacing_fix(self): ...
    def test_instruction_leak_removal(self): ...

class TestAssembleFinal:
    def test_url_appended(self, monkeypatch): ...  # mock validate_link
```

**pitch.py tests (4-5 new test functions):**

```python
# tests/test_pitch.py
class TestParsePitches:
    def test_standard_schema(self): ...
    def test_diffusiongemma_schema(self): ...
    def test_pitch_id_schema(self): ...

class TestDedup:
    def test_exact_match_duplicate(self): ...
    def test_no_match(self): ...

class TestHistory:
    def test_save_and_load(self, tmp_path): ...
```

**pitch_evaluator.py tests (2-3 new test functions):**

```python
# tests/test_pitch_evaluator.py
class TestEvaluatePitch:
    def test_passes_quality_gate(self, monkeypatch): ...
    def test_fails_direction_mismatch(self, monkeypatch): ...
```

### Total New Tests: 18-25 test functions across 5 new test files
### How the existing 13 characterization tests act as a regression gate:

```bash
# Run all tests before any extraction
pytest tests/ -m "unit" --tb=short  # 13 + 103 briefing tests = 116 current

# After each extraction step:
# 1. Run new module tests
pytest tests/test_validator.py -m "unit" --tb=short
# 2. Run ALL existing tests (regression gate)
pytest tests/ -m "unit" --tb=short
# 3. Run old __main__ entry with --dry-run (smoke test)
python3 scripts/threads/main_v3.py --dry-run
```

## Phase 4 MVP Vertical Slice

### What
Extract **validator.py** (pure functions) and **crawler.py** (network, standalone) from writer_v3.py, wire them via Strangler Fig, verify the pipeline still works end-to-end via dry-run.

### Why This Slice

| Criterion | Validator | Crawler | Writer | Pitch | PitchEval |
|---|---|---|---|---|---|
| Zero new dependencies | ✅ | ✅ (requests installed) | ❌ (model_router) | ❌ | ❌ |
| Easy to test | ✅ (pure) | ✅ (mock HTTP) | ❌ (LLM) | ❌ | ❌ |
| Breaks cross-dep first | — | ✅ (fetch_article_body is imported by narrative_pitcher) | — | — | — |
| Proves Strangler Fig wiring | ✅ | ✅ | — | — | — |

### Extraction Sequence (ordered by dependency risk)

1. **validator.py** — Zero dependencies, pure functions. Extract, test, verify. (Low risk, high confidence.)
2. **crawler.py** — Network I/O but standalone. No LLM. Breaks the `narrative_pitcher ← writer_v3.fetch_article_body` cross-dependency. (Medium risk — need mocked HTTP tests.)
3. **pitch_evaluator.py** — Already exists as standalone `scripts/threads/v3/pitch_evaluator.py`. Copy to `pipeline/threads/pitch_evaluator.py`. (Low risk, existing code.)
4. **pitch.py** — Depends on dedup, db_reader, model_router, crawler. Extract after crawler is done. (Medium risk — many internal dependencies.)
5. **writer.py** — Largest extraction. Contains write_thread() orchestrator that ties validator + crawler + model_router together. (Highest risk — do last.)

### Acceptance Criteria for Each Slice

| Slice | Must Be True |
|---|---|
| 1. Validator extracted | All 13 existing tests pass. New validator tests pass. writer_v3.py imports from pipeline.threads.validator. |
| 2. Crawler extracted | `from pipeline.threads.crawler import fetch_article_body` works. narrative_pitcher.py still imports fetch_article_body from v3.writer_v3 (re-export). Pipeline dry-run succeeds. |
| 3. Pitch evaluator extracted | pipeline.threads.pitch_evaluator imported by pitch.py. Old v3/pitch_evaluator.py still works (re-export). |
| 4. Pitch extracted | pipeline.threads.pitch.get_pitches() callable from narrative_pitcher.py. Pipeline dry-run succeeds. |
| 5. Writer extracted | pipeline.threads.writer.write_thread() callable from writer_v3.py. Old writer_v3.py is now a thin wrapper (~50 lines). Pipeline dry-run succeeds. All 116+ tests pass. |

## Common Pitfalls

### Pitfall 1: Breaking the narrative_pitcher ← writer_v3 CROSS-IMPORT
**What goes wrong:** `narrative_pitcher.py` line 9 imports `fetch_article_body` from `v3.writer_v3`. If we delete the inline `def fetch_article_body` from writer_v3.py without adding a re-export, narrative_pitcher.py breaks.
**Why it happens:** The cross-module dependency is invisible during writer_v3.py refactoring — it's a downstream consumer in a different file.
**How to avoid:** Always follow the 4-step Strangler Fig pattern: CREATE → IMPORT → RE-EXPORT → VERIFY. The re-export step keeps old import paths alive.
**Warning signs:** `ImportError: cannot import name 'fetch_article_body' from 'v3.writer_v3'`

### Pitfall 2: Losing module-level constants
**What goes wrong:** `main_v3.py validate_final_cards()` imports `INSTRUCTION_PATTERNS` from `v3.writer_v3` (line 51). If we move INSTRUCTION_PATTERNS to a new module without re-export, this breaks.
**Why it happens:** Module-level constants are scattered and their consumers are non-obvious.
**How to avoid:** Before any extraction, audit ALL module-level names and identify their consumers. Use `grep -r "from.*v3.*writer_v3.*import" *.py` to find all consumers.
**Warning signs:** `ImportError` in validate_final_cards — tests fail.

### Pitfall 3: Import path resolution failures
**What goes wrong:** New modules in `pipeline/threads/` import from `v3.model_router`, but the sys.path manipulation in `model_router.py` itself (`sys.path.insert(0, ...)`) runs at module level and may not be active when the new module is imported first.
**Why it happens:** Import ordering matters when modules do path manipulation at load time. `model_router.py` does `sys.path.insert(0, ...)` at the module level after loading env vars.
**How to avoid:** Make `pipeline/threads/writer.py` and `pipeline/threads/pitch.py` import `chat_completion` from `v3.model_router` as a function-level (lazy) import, not a module-level import. The existing modules already do this:
```python
def write_thread(...):
    from v3.model_router import chat_completion  # Already a lazy import!
```

### Pitfall 4: Losing INSTRUCTION_PATTERNS re-export for main_v3.py
**What goes wrong:** `main_v3.py` line 51: `from v3.writer_v3 import INSTRUCTION_PATTERNS`. This is used in `validate_final_cards()` which is a separate test file with characterization tests.
**How to avoid:** Keep INSTRUCTION_PATTERNS in writer_v3.py wrapper OR add re-export. The characterization test file also has a fallback definition (lines 19-31 of the test file), so even if the import breaks, tests still compile.
**Warning signs:** `test_characterization_validate_final_cards.py` test suite failure.

### Pitfall 5: __main__ blocks in extracted code
**What goes wrong:** If we copy-paste functions and accidentally include the `if __name__ == '__main__':` block, the module may execute side effects on import.
**How to avoid:** Never include `if __name__ == '__main__':` blocks in extracted library modules. They belong in the old entry point files.

## Code Examples

### Strangler Fig Extraction Pattern

```python
# === OLD: scripts/threads/v3/writer_v3.py (inline definition) ===
def validate_cards(cards, pitch, format_choice='D'):
    lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 6))
    if not cards or len(cards) < lo or len(cards) > hi:
        return False
    first_line = cards[0].strip().split('\n')[0].strip()
    if len(first_line) < 3:
        return False
    return True

# === STEP 1: Create pipeline/threads/validator.py ===
"""pipeline/threads/validator.py — Card, year, keyword validation."""
import re
from datetime import datetime
from collections import Counter

def validate_cards(cards, pitch, format_choice='D'):
    lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 6))
    if not cards or len(cards) < lo or len(cards) > hi:
        return False
    first_line = cards[0].strip().split('\n')[0].strip()
    if len(first_line) < 3:
        return False
    return True

# === STEP 2: Update writer_v3.py to import ===
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords

# === STEP 3: Re-export if needed (not needed for validator — no external importers) ===

# === STEP 4: Verify ===
# Run: pytest tests/ -m "unit" --tb=short
# Run: python3 scripts/threads/main_v3.py --dry-run
```

### Lazy Import Pattern (for model_router dependency)

```python
# pipeline/threads/writer.py — lazy import to avoid load-order issues
def write_thread(pitch, all_articles, format_choice=None):
    from v3.model_router import chat_completion  # Lazy: loaded when called
    from v3.format_selector import select_format
    # ... function body ...
```

### New Module Testing Pattern

```python
# tests/test_validator.py
"""Tests for pipeline.threads.validator — pure functions, no mocking needed."""
import pytest
from pipeline.threads.validator import validate_cards, validate_year, validate_keywords

class TestValidateCards:
    def test_valid_card_count(self):
        cards = ["Card one\nline 2", "Card two"]
        pitch = {"hook": "Test hook"}
        assert validate_cards(cards, pitch) is True

    def test_invalid_card_count_too_few(self):
        cards = []  # Only 0 cards
        pitch = {"hook": "Test"}
        assert validate_cards(cards, pitch) is False

    def test_first_line_too_short(self):
        cards = ["AB"]  # First line < 3 chars
        pitch = {"hook": "Test"}
        assert validate_cards(cards, pitch) is False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| All functions in 1,018-line writer_v3.py | Split into validator, crawler, writer modules under pipeline/threads/ | Phase 4 | Independent testing, focused modules, clear interfaces |
| narrative_pitcher imports fetch_article_body from writer_v3 | Both import from pipeline/threads/crawler | Phase 4 | Breaks circular dependency, shared infrastructure |
| Old script files are thick monoliths | Old files become thin re-export wrappers | Phase 4 | Strangler Fig transition without breaking pipeline |
| Tests only characterize existing behavior | Tests validate extracted module APIs | Phase 4 | Unit testing becomes practical without LLM/network mocking |

**Deprecated/outdated:**
- `_FORMAT_COMMON_RULES()`: Dead code from A/B/C format era. Exists in writer_v3.py but is never called. Should not be extracted — leave it in old file for Phase 5 removal.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `model_router.chat_completion` lazy imports will work correctly from pipeline/threads/ modules | Integration Strategy | Runtime ImportError if module-level sys.path manipulation is required |
| A2 | No other module outside the audited set imports from v3.writer_v3 | Dependency Graph | Missing a consumer causes breakage in unexpected places |
| A3 | Characterization tests (13 existing) adequately cover validate_final_cards and validate_thread behavior | Test Strategy | Regression not caught if tests have gaps |

**A1 mitigation:** Test each lazy import path explicitly after extraction by running `python3 -c "from pipeline.threads.writer import write_thread; write_thread(...)"`.
**A2 mitigation:** Run comprehensive grep before each extraction: `grep -r "from v3.writer_v3 import" scripts/ --include="*.py"`.
**A3 mitigation:** Add new unit tests alongside characterization tests. The characterization tests are a minimum bar, not a comprehensive spec.

## Open Questions

1. **Should model_router.py move to pipeline/infra/ during Phase 4?**
   - What we know: `chat_completion` is used by writer, pitch, and pitch_evaluator. It's an infrastructure-level concern (model routing, API key management).
   - What's unclear: Moving it creates a new import path that all new modules must use. This may confuse automated testing if multiple sys.path manipulations interact.
   - Recommendation: Keep in `scripts/threads/v3/model_router.py` for Phase 4. Move to `pipeline/infra/model_router.py` in Phase 5 (dead code removal) when all consumers are under `pipeline/` and the migration is clean. Add a forward-compatibility import in Phase 4: `from pipeline.infra.model_router import chat_completion` if model_router is moved.

2. **Should `korean-particles-spacing` for 2-char English abbreviations be relaxed?**
   - What we know: `_fix_korean_particle_spacing` adds spaces between ANY capitalized English word and a following Korean particle. This transforms "AI가" → "AI 가", "CEO가" → "CEO 가".
   - What's unclear: The existing characterization tests don't test this behavior. The main_v3.py validation was relaxed in 2026-06-29 to allow English+particle patterns.
   - Recommendation: Keep existing behavior unchanged. Characterize before extracting.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All extracted modules | ✓ | 3.14.5 | — |
| openai (PyPI) | model_router (LLM calls) | ✓ | 1.109.1 | — |
| beautifulsoup4 (PyPI) | crawler (HTML parsing) | ✓ | 4.15.0 | — |
| lxml (PyPI) | crawler (HTML parser backend) | ✓ | 6.1.1 | — |
| npx + wrangler | db_reader (D1 queries) | ✓ | 11.6.2 | — |

**Missing dependencies with no fallback:** None — all required packages are installed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pytest.ini (unit/integration markers) |
| Quick run command | `pytest tests/test_validator.py -m "unit" -x --tb=short` |
| Full suite command | `pytest tests/ -m "unit" --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-03 | Card/year/keyword validation extracted | unit | `pytest tests/test_validator.py -m "unit" -x --tb=short` | ❌ Wave 0 |
| MON-04 | Article fetching and link validation extracted | unit | `pytest tests/test_crawler.py -m "unit" -x --tb=short` | ❌ Wave 0 |
| MON-05 | Format builders extracted into writer.py | unit | `pytest tests/test_writer.py -m "unit" -x --tb=short` | ❌ Wave 0 |
| MON-06 | Pitch logic extracted into pitch.py | unit | `pytest tests/test_pitch.py -m "unit" -x --tb=short` | ❌ Wave 0 |
| MON-07 | Pitch evaluation extracted into pitch_evaluator.py | unit | `pytest tests/test_pitch_evaluator.py -m "unit" -x --tb=short` | ❌ Wave 0 |
| TST-02 | Unit tests for all extracted modules | unit | `pytest tests/test_validator.py tests/test_crawler.py tests/test_writer.py tests/test_pitch.py tests/test_pitch_evaluator.py -m "unit" --tb=short` | ❌ Wave 0 |
| TST-03 | Unit tests for all Threads pipeline modules | unit | Same as TST-02 | ❌ Wave 0 |
| TST-04 | Unit tests for orchestrator | unit | `pytest tests/test_orchestrator.py -m "unit" -x --tb=short` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_{extracted_module}.py -m "unit" -x --tb=short`
- **Per wave merge:** `pytest tests/ -m "unit" --tb=short` (116+ tests)
- **Phase gate:** Full suite green + dry-run pipeline success before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_validator.py` — covers MON-03 (validate_cards, validate_year, validate_keywords, validate_thread)
- [ ] `tests/test_crawler.py` — covers MON-04 (fetch_article_body, log_failed_crawl)
- [ ] `tests/test_writer.py` — covers MON-05 (parse_cards, clean_*, assemble_final, save_draft)
- [ ] `tests/test_pitch.py` — covers MON-06 (parse_pitches_from_text, is_duplicate_pitch, load/save history)
- [ ] `tests/test_pitch_evaluator.py` — covers MON-07 (evaluate_pitch, filter_pitches)
- [ ] `tests/test_orchestrator.py` — covers TST-04 (per-step isolation, retry, skip behavior)

## Security Domain

> `security_enforcement` not explicitly set — treat as enabled per default.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Yes | validate_cards/validate_year/validate_keywords validate LLM output before publishing |
| V6 Cryptography | No | No cryptographic operations in monolith splitting |
| V8 File & Resources | Yes | save_draft writes to scripts/threads/logs/drafts/ — path construction uses os.path.join (safe) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via article text | Tampering | validate_year and validate_keywords act as output validation gates — reject hallucinated content |
| Path traversal in save_draft | Tampering | Uses `pitch.get('hook','')` sanitized with `re.sub(r'[^a-zA-Z0-9가-힣]', '', ...)` before joining path |
| URL validation bypass | Spoofing | assemble_final calls db_reader.validate_link which checks HTTP 2xx status — fails closed |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase audit] — Complete function dependency maps for writer_v3.py and narrative_pitcher.py derived from full file reads
- [VERIFIED: pip show] — openai 1.109.1, beautifulsoup4 4.15.0, lxml 6.1.1 confirmed installed in .venv
- [VERIFIED: codebase] — pipeline/orchestrator.py PipelineStep protocol + PipelineOrchestrator class confirmed
- [VERIFIED: codebase] — pipeline/steps/step_run_threads.py subprocess wrapper confirmed
- [VERIFIED: codebase] — test_characterization_validate_final_cards.py (8 tests) and test_characterization_pure_functions.py (5 tests) confirmed

### Secondary (MEDIUM confidence)
- [ASSUMED] — model_router.py lazy imports work from pipeline/threads/ modules. Based on existing lazy import pattern (already used in writer_v3.py line 368/550/606, narrative_pitcher.py line 333).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via `pip show` and code audit
- Architecture: HIGH — complete function maps derived from full file reads
- Pitfalls: HIGH — based on specific code structures observed
- Integration strategy: HIGH — Strangler Fig pattern already proven in Phase 2-3

**Research date:** 2026-06-30
**Valid until:** No expiry (stable codebase — no dependency updates needed for extraction)
