# Testing Patterns

**Analysis Date:** 2026-06-30

## Overview

Testing exists only in the **Python** portion of the codebase (pipelines and backend scripts). The **TypeScript/Astro** frontend has **no test files at all** — no test runner configured, no test files found (`*.test.*`, `*.spec.*`).

Two testing locations exist:
1. `tests/` — **pytest unit tests** for pipeline modules (`auto_news_selector`, `briefing_scorer`)
2. `api_test/` — **Ad-hoc integration test scripts** (run directly with `python3`)

## Test Framework

**Python (unit tests):**
- **Framework:** pytest
- **Version:** Not pinned (no `requirements.txt` for dev deps)
- **Config file:** `pytest.ini` at project root

```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests that don't need external services
    integration: Tests that need D1 DB or network (not run by default)
strict_markers = true
pythonpath = scripts
```

- **Run command:**
```bash
pytest                          # Run all unit tests
pytest -m integration           # Run integration tests (requires network/D1)
pytest -v                       # Verbose mode
pytest tests/test_briefing_scorer.py  # Run single file
```

**Python (ad-hoc integration):**
- **No framework:** Run directly with `python3`
```bash
python3 api_test/test_all_apis.py
```

## Test Structure

### Python Unit Tests (`tests/`)

**Location:** `tests/` directory, separate from source code (`scripts/`).

**Naming:**
- Test files: `test_<module_name>.py` (e.g., `test_briefing_scorer.py`, `test_cascade_2pass.py`)
- Test classes: `Test<ComponentName>` (e.g., `TestAmountParsing`, `TestEntityTier`)
- Test methods: `test_<scenario>` (e.g., `test_usd_billion`, `test_light_mode_all_fields_present`)

**Organization:**

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures (sample_weights, sample_tiers, mock_articles, monkeypatch_d1)
├── fixtures/
│   ├── articles_20.json     # 20 test articles for top-N selection tests
│   └── recent_briefings_7d.json  # 7-day briefing history for dedup tests
├── test_auto_news_selector_dry_run.py   # Tests for auto_news_selector module
├── test_briefing_scorer.py              # Tests for briefing_scorer module
└── test_cascade_2pass.py                # Integration tests for the cascade scoring pipeline
```

**Suite Organization Pattern:**
- Tests organized by **class per component/feature** within each file
- Classes group related test scenarios together
- Each test method covers a single assertion or scenario

Example from `tests/test_briefing_scorer.py`:
```python
class TestAmountParsing:
    def test_usd_billion(self):
        text = "Nvidia announced a $10 billion deal"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 10_000_000_000
        assert any("$10 billion" in f["raw"] for f in found)

    def test_no_amount(self):
        text = "New product launch announcement"
        found, amounts = _parse_amounts(text)
        assert amounts["usd_max"] == 0
        assert amounts["krw_max"] == 0
```

### Python Ad-Hoc Tests (`api_test/`)

**Location:** `api_test/` directory.

**Naming:** `test_<feature>.py` (e.g., `test_all_apis.py`)

**Structure:** Script-style, no classes. Sequential test blocks, each wrapped in `try/except` with manual status logging. Results accumulated into a JSON report.

## Test Types

### Unit Tests
- **Location:** `tests/`
- **Scope:** Individual functions in `scripts/briefing_scorer.py` and `scripts/auto_news_selector.py`
- **Pattern:** Class-based grouping with `pytest` fixtures
- **Markers:** `unit` (default — no external services needed)

### Integration Tests
- **Location:** `tests/` (marked `@pytest.mark.integration` — but this marker is not actually used in any test file yet)
- **Scope:** D1 database access, network crawling — currently untested
- **Note:** The `integration` marker is defined in `pytest.ini` but no tests currently use `@pytest.mark.integration` decoration

### Manual Integration Tests
- **Location:** `api_test/`
- **Scope:** External API connectivity (Naver Search, Google Trends, OpenAI, gov APIs, web crawling, image generation)
- **Pattern:** Sequential script with `log()` function, `try/except` per API call, JSON report output
- **No assertions — manual review required**

## Mocking

**Framework:** `pytest.monkeypatch` (built-in pytest fixture)

**Pattern:**
- `monkeypatch.setattr()` replaces module-level functions with test doubles
- Mock functions return controlled data to avoid real network/D1 calls

Example from `tests/conftest.py`:
```python
@pytest.fixture
def monkeypatch_d1(monkeypatch):
    """Mock d1_query to return empty results (prevents real D1 calls)"""
    def mock_d1(sql, retries=2):
        return []
    monkeypatch.setattr("auto_news_selector.d1_query", mock_d1)
    return mock_d1
```

**What to Mock:**
- External API calls (`requests.get`)
- D1 database queries (`d1_query()`)
- Network-dependent operations

**What NOT to Mock:**
- Pure computation functions (`_parse_amounts`, `_score_financial_impact`)
- String parsing and regex operations

## Fixtures and Factories

**Location:** `tests/conftest.py` (shared), `tests/fixtures/` (JSON data files)

**Common Fixtures:**

| Fixture | Purpose | Source File |
|---------|---------|-------------|
| `sample_weights` | Complete impact scoring weights dict | `conftest.py` (lines 14-55) |
| `sample_tiers` | Entity tier config with tier1/tier2/tier3 | `conftest.py` (lines 58-64) |
| `mock_articles_20` | 20 pre-built articles from JSON file or fallback | `conftest.py` (lines 67-73, 85-123) |
| `mock_recent_briefings` | 7-day briefing history from JSON or fallback | `conftest.py` (lines 76-82) |
| `monkeypatch_d1` | Mocks D1 queries to return empty results | `conftest.py` (lines 127-131) |

**Fallback Pattern:**
Fixtures check for JSON fixture files first, generate default data in-memory as fallback:
```python
@pytest.fixture
def mock_articles_20():
    path = FIXTURES_DIR / "articles_20.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return _default_articles_20()
```

**Factory Function:** `_default_articles_20()` in `conftest.py` generates 20 structured test articles with varied tiers, amounts, clusters, and sources.

## Coverage

- **Tool:** Not configured (no `pytest-cov` or `.coveragerc` detected)
- **Target:** None
- **Current:** Unknown (no coverage reports generated)
- **Exclusions:** N/A

## Test Utilities

- **Built-in:** `pytest.monkeypatch` for mocking
- **Built-in:** `pytest.approx` — not used (uses direct `==` comparison, even for floats — see USDKRW conversion tests)
- **Built-in:** `tmp_path` fixture — used in one test for log file testing
- **No factory libraries** (no `factory_boy`, `model_bakery`)
- **No mocking libraries** (no `unittest.mock`, `pytest-mock` — only `monkeypatch`)

## CI Integration

- **CI Platform:** Not detected (no `.github/workflows/`, `.gitlab-ci.yml`, or similar)
- **Test Command:** No CI test step found
- **Parallelism:** Not configured
- **Pre-commit hooks:** Not detected

## Testing Patterns

### Pattern 1: Class-Based Test Organization
- **Description:** Tests are grouped into classes by component/feature being tested. Class names follow `Test<Component>` convention.
- **Example file:** `tests/test_briefing_scorer.py`
- **Fixture access:** Accessed via method parameters (injected by pytest)

```python
class TestFinancialImpact:
    def test_over_10b(self, sample_weights):
        score = _score_financial_impact({"usd_max": 50_000_000_000, "krw_max": 0}, sample_weights)
        assert score == 25
```

### Pattern 2: Parametrized Edge Cases
- **Description:** `@pytest.mark.parametrize` used for testing multiple input variations of the same function.
- **Example file:** `tests/test_cascade_2pass.py` (lines 151-166)

```python
@pytest.mark.parametrize("text, expected_min_usd", [
    ("$10 billion investment", 10_000_000_000),
    ("$10bn raise", 10_000_000_000),
    ("$1 trillion market", 1_000_000_000_000),
    ("$500m funding", 500_000_000),
])
def test_various_amount_formats(self, text, expected_min_usd):
    found, amounts = _parse_amounts(text)
    if expected_min_usd > 0:
        assert amounts["usd_max"] >= expected_min_usd * 0.99
```

### Pattern 3: Single-Assert Tests
- **Description:** Each test method verifies one specific behavior with one primary assertion. When multiple assertions are needed, they check related properties of the same result.
- **Example file:** `tests/test_briefing_scorer.py`

### Pattern 4: Real Function Import (No Patching for Pure Functions)
- **Description:** Pure functions are imported directly from the module under test. Mocking is used only for I/O-bound operations (network, database).
- **Example file:** `tests/test_briefing_scorer.py`

```python
from briefing_scorer import (
    score_article,
    _parse_amounts,
    _match_entity_tiers,
    _score_financial_impact,
)
```

### Pattern 5: Sequential Integration Test Script
- **Description:** Manual integration tests in `api_test/` follow a sequential script pattern: section header, try/except block, `log()` call with emoji status, and JSON results aggregation.
- **Example file:** `api_test/test_all_apis.py`

```python
results = []
def log(api_name, status, detail=""):
    emoji = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
    results.append({"api": api_name, "status": status, "detail": detail})
    print(f"{emoji} [{api_name}] {status} - {detail}")
```

## Gaps

- **No TypeScript/JavaScript tests:** The entire `src/` directory has zero test coverage. Astro components, API endpoints (`src/pages/api/`), auth logic, middleware, sitemap generators are all untested.
- **No E2E tests:** No Playwright, Cypress, or browser testing.
- **No coverage reporting:** Cannot measure what is or isn't tested.
- **No CI integration:** Tests must be run manually.
- **Integration marker unused:** `integration` marker defined in `pytest.ini` but never applied to any test.

---

*Testing analysis: 2026-06-30*
