---
phase: 01-security-hardening
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/threads/threads-publisher.plist
  - pipeline/infra/__init__.py
  - pipeline/infra/env_loader.py
  - pipeline/infra/logger.py
  - api_test/.env.sh
   - scripts/deploy.sh
   - scripts/threads/token_refresh.py
   - tests/conftest.py
   - .planning/phases/01-security-hardening/ENV_SOURCE_MAP.md
autonomous: true
requirements: [SEC-01, SEC-02, SEC-03, SEC-04, OBS-07, TST-05]
user_setup: []
must_haves:
  truths:
    - "No API keys or secrets exist in threads-publisher.plist — all env vars delegated to .env chain"
    - "All env sources across the project are documented in a single source-map document"
    - "pipeline/infra/env_loader.py exists and is the single env-loading entry point"
    - "api_test/.env.sh is removed from the filesystem"
    - "deploy.sh sources only project .env, not cross-project /Users/twinssn/Projects/5000/.env"
    - "Log output redacts API keys, tokens, and PII via ScrubRegistry"
    - "conftest.py provides mock fixtures for OpenAI, DeepSeek, and HTTP requests"
    - "Secrets in git history are flagged for remediation and keys are rotated"
  artifacts:
    - path: "scripts/threads/threads-publisher.plist"
      provides: "Clean plist with no EnvironmentVariables block"
      grep_absent: "EnvironmentVariables"
    - path: "pipeline/infra/env_loader.py"
      provides: "Unified EnvConfig with .env → ~/.env.common priority"
      exports: ["EnvConfig"]
    - path: "pipeline/infra/logger.py"
      provides: "Logging with ScrubRegistry secret redaction"
      exports: ["ScrubRegistry", "get_scrubbed_logger"]
    - path: ".planning/phases/01-security-hardening/ENV_SOURCE_MAP.md"
      provides: "Documentation of all env sources, their contents, and transformation status"
    - path: "scripts/deploy.sh"
      provides: "Deploy script scoped to project .env only"
      grep_absent: "5000/\\.env"
    - path: "tests/conftest.py"
      provides: "Mock fixtures for OpenAI, DeepSeek, HTTP"
      grep_contains: "monkeypatch_openai|monkeypatch_deepseek|monkeypatch_http"
  key_links:
    - from: "pipeline/infra/env_loader.py"
      to: ".env"
      via: "EnvConfig._load_file()"
      pattern: "EnvConfig.*\\.env"
    - from: "pipeline/infra/env_loader.py"
      to: "~/.env.common"
      via: "EnvConfig._load_file()"
      pattern: "env\\.common"
    - from: "pipeline/infra/logger.py"
      to: "ScrubRegistry.scrub()"
      via: "logging Handler emit() or filter"
      pattern: "ScrubRegistry"
    - from: "tests/conftest.py"
      to: "monkeypatch.setattr"
      via: "fixture functions"
      pattern: "monkeypatch\\.setattr"
---

<objective>
Hardening of secrets management across the aikorea24 Python pipeline: remove credentials from launchd plist, consolidate env loading into a single module, remediate git history, scrub secrets from logs, and expand test mock infrastructure.

Purpose: Eliminate all active security issues where API keys are exposed in committed files, configuration is fragmented across 5+ sources, and secrets can leak into log output.

Output: Cleaned plist, unified env_loader.py, env source-map document, log scrubbing infrastructure (logger.py with ScrubRegistry), deleted shadow config (api_test/.env.sh), repaired deploy.sh, expanded test mock fixtures in conftest.py.
</objective>

<execution_context>
@/Users/twinssn/.config/opencode/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/twinssn/Projects/aikorea24/.planning/PROJECT.md
@/Users/twinssn/Projects/aikorea24/.planning/ROADMAP.md
@/Users/twinssn/Projects/aikorea24/.planning/STATE.md
@/Users/twinssn/Projects/aikorea24/.planning/phases/01-security-hardening/01-CONTEXT.md
@/Users/twinssn/Projects/aikorea24/.planning/codebase/CONCERNS.md
@/Users/twinssn/Projects/aikorea24/.planning/codebase/CONVENTIONS.md
@/Users/twinssn/Projects/aikorea24/scripts/threads/threads-publisher.plist
@/Users/twinssn/Projects/aikorea24/scripts/deploy.sh
@/Users/twinssn/Projects/aikorea24/tests/conftest.py
@/Users/twinssn/Projects/aikorea24/api_test/.env.sh
@/Users/twinssn/Projects/aikorea24/.env
@/Users/twinssn/Users/twinssn/.env.common

<interfaces>
Existing patterns and contracts the executor must use:

From tests/conftest.py (monkeypatch_d1 pattern — template for new mocks):
```python
@pytest.fixture
def monkeypatch_d1(monkeypatch):
    """Mock d1_query to return empty results (prevents real D1 calls)"""
    def mock_d1(sql, retries=2):
        return []
    monkeypatch.setattr("auto_news_selector.d1_query", mock_d1)
    return mock_d1
```

From scripts/deploy.sh (current env sourcing — must be replaced):
```bash
# Current (broken):
if [ -f /Users/twinssn/Projects/5000/.env ]; then
  export $(grep -E '^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)' /Users/twinssn/Projects/5000/.env | xargs)
fi
```

From .env (project root) — currently sources ~/.env.common at top via shell:
```
# 공통 환경변수 로드 (Telegram 토큰 등)
source /Users/twinssn/.env.common 2>/dev/null || true
```

Current ~/.env.common contains: OPENAI_API_KEY, OPENAI_MODEL, CLOVA_API_KEY, UPSTAGE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CLOUDFLARE_* tokens, BLOGDEX_API_URL, R2_* credentials, DART_API_KEY, etc.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Plist Hardening + Git History Remediation (SEC-02, SEC-04)</name>
  <files>
    scripts/threads/threads-publisher.plist
  </files>
  <action>
    Per D-03: Remove the entire `<EnvironmentVariables>` block from `scripts/threads/threads-publisher.plist`. The block spans lines 21-27 (from `<key>EnvironmentVariables</key>` through the closing `</dict>`). After removal, the plist should only contain path configuration (ProgramArguments, WorkingDirectory, StandardOutPath, etc.) — no secrets.

    Per D-01: Run BFG Repo-Cleaner on the repository to scrub API keys and secrets from git history. BFG is preferred over git filter-branch per user decision. Steps:
    1. Create a `bfg-secrets.txt` file listing patterns to remove (refer to .env, api_test/.env.sh, .env.bak.telegram for exact key values — note that the plist already has REDACTED_OPENAI_KEY placeholder, not a real key)
    2. Run `java -jar bfg.jar --replace-text bfg-secrets.txt .git`
    3. Run `git reflog expire --expire=now --all && git gc --prune=now --aggressive`
    4. Force push with `git push --force`

    Per D-02: After BFG cleanup completes, document that the user must rotate all affected API keys (OPENAI_API_KEY, DEEPSEEK_API_TOKEN, NAVER_CLIENT_ID/SECRET, etc.) by visiting each service dashboard. This is a user action — the executor documents the key list and marks key rotation as pending.

    Important finding: Investigation shows `.env`, `api_test/.env.sh`, and `.env.bak.telegram` have never been committed to git. The plist has always contained `REDACTED_OPENAI_KEY` (not a real key). However, log files (`.log`) may have captured keys in output — include these in the BFG scope. If BFG finds nothing to replace, document this finding and proceed with the env source map creation (making clear the exposure risk is from non-repo files on disk, not from git history).
  </action>
  <verify>
    <automated>
      grep 'EnvironmentVariables' scripts/threads/threads-publisher.plist && echo "FAIL: EnvironmentVariables still present" || echo "PASS: EnvironmentVariables removed"
      git log --all --oneline scripts/threads/threads-publisher.plist 2>/dev/null | head -3
    </automated>
  </verify>
  <done>
    — scripts/threads/threads-publisher.plist has zero EnvironmentVariables entries
    — BFG cleanup completed (no real keys found in git history, OR keys removed)
    — Key rotation checklist documented for user action
  </done>
</task>

<task type="auto">
  <name>Task 2: Env Source Consolidation — env_loader.py + Config Cleanup (SEC-01, SEC-03)</name>
  <files>
    pipeline/infra/__init__.py
    pipeline/infra/env_loader.py
    api_test/.env.sh (DELETE)
    scripts/deploy.sh
    .planning/phases/01-security-hardening/ENV_SOURCE_MAP.md
  </files>
  <action>
    Create `pipeline/infra/` package directory and `env_loader.py` module (Strangler Fig pattern per D-08). This is the canonical env loading module for all Python scripts.

    **pipeline/infra/__init__.py**: Empty file, marks the directory as a Python package.

    **pipeline/infra/env_loader.py**: Create with these exact behaviors:
    - Class `EnvConfig` with constructor that:
      - Accepts optional `project_dir` parameter (defaults to deriving from module path: `Path(__file__).resolve().parent.parent.parent`)
      - Step 1: Loads `~/.env.common` as fallback (setdefault semantics — only sets keys not already present)
      - Step 2: Loads project `.env` with highest priority (overrides common values)
    - File parsing method:
      - Skips blank lines and lines starting with `#`
      - Skips lines starting with `source` (shell directive, not a variable)
      - Strips `export ` prefix if present
      - Strips surrounding quotes from values
      - Handles `KEY=VALUE` format only
    - Method `get(key, default=None)`: Returns the value for a key
    - Method `getint(key, default=0)`: Returns int value
    - Method `getbool(key, default=False)`: Returns bool value from "true"/"1"/"yes" strings
    - Method `load_to_environ()`: Syncs all loaded vars into `os.environ` for backward compatibility
    - **Do NOT call `load_to_environ()` at module level** — avoid side effects on import (this is the key fix for the module-level side-effect problem documented in CONCERNS.md)
    - Include comprehensive docstring and type annotations for all methods
    - Python 3.14 stdlib only — no third-party imports (no `python-dotenv`)

    **api_test/.env.sh**: Delete this file per D-06. It is a shadow config that duplicates environment variables already defined in `.env`. The new env_loader.py replaces it entirely.

    **scripts/deploy.sh**: Fix per D-07. Replace the cross-project `.env` sourcing with project-local sourcing:
    ```bash
    # Before:
    if [ -f /Users/twinssn/Projects/5000/.env ]; then
      export $(grep -E '^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)' /Users/twinssn/Projects/5000/.env | xargs)
    else
      echo "[ERROR] .env 파일 없음: /Users/twinssn/Projects/5000/.env"
      exit 1
    fi

    # After:
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    if [ -f "$PROJECT_DIR/.env" ]; then
      source "$PROJECT_DIR/.env"
    else
      echo "[ERROR] .env 파일 없음: $PROJECT_DIR/.env"
      exit 1
    fi
    ```
    Note: `deploy.sh` sources the `.env` file which itself has `source ~/.env.common 2>/dev/null || true` at the top. This is fine for shell context — the env_loader.py handles it separately for Python scripts per D-04/D-05.

    **ENV_SOURCE_MAP.md**: Create at `.planning/phases/01-security-hardening/ENV_SOURCE_MAP.md`. Document all env sources discovered during this phase:

    | Source | Status | Contents | Consumer |
    |--------|--------|----------|----------|
    | `~/.env.common` | Canonical | Shared secrets (API keys, cloud tokens, DB creds) | env_loader.py fallback |
    | `.env` (project root) | Active — project-specific | Overrides, project settings, thread tokens | env_loader.py primary |
    | `scripts/threads/threads-publisher.plist` | CLEANED | Path config only — no secrets | launchd |
    | `api_test/.env.sh` | DELETED | Shadow config — removed per D-06 | — |
    | `.env.bak.telegram` | Review — gitignored, not committed | Telegram + Cloudflare creds | Review for complete key inventory |
    | `scripts/deploy.sh` | FIXED | Cross-project dep removed | Cloudflare deploy |

    Include a section documenting all known env var names discovered across these sources with their purpose and which source they primarily live in.
  </action>
  <verify>
    <automated>
      python3 -c "import sys; sys.path.insert(0, '.'); from pipeline.infra.env_loader import EnvConfig; c = EnvConfig(); k = c.get('OPENAI_API_KEY'); assert k is not None and len(k) > 0, 'OPENAI_API_KEY not loaded'; print(f'PASS: env_loader loads keys ({len(k)} chars)')"
      test ! -f api_test/.env.sh && echo "PASS: api_test/.env.sh deleted" || echo "FAIL: api_test/.env.sh still exists"
      grep -c '/Users/twinssn/Projects/5000' scripts/deploy.sh && echo "FAIL: cross-project ref still in deploy.sh" || echo "PASS: deploy.sh cleaned"
      test -f .planning/phases/01-security-hardening/ENV_SOURCE_MAP.md && echo "PASS: ENV_SOURCE_MAP.md exists" || echo "FAIL: ENV_SOURCE_MAP.md missing"
      python3 -c "import sys; sys.path.insert(0, '.'); from pipeline.infra.env_loader import EnvConfig" 2>&1 || true
    </automated>
  </verify>
  <done>
    — pipeline/infra/__init__.py and env_loader.py exist and loadable
    — EnvConfig loads OPENAI_API_KEY from .env or ~/.env.common
    — api_test/.env.sh is deleted from filesystem
    — deploy.sh has no reference to /Users/twinssn/Projects/5000/.env
    — ENV_SOURCE_MAP.md exists with all 6+ sources documented
  </done>
</task>

<task type="auto">
  <name>Task 3: Log Scrubbing + Test Mock Expansion (OBS-07, TST-05)</name>
  <files>
    pipeline/infra/logger.py
    tests/conftest.py
  </files>
  <action>
    **pipeline/infra/logger.py**: Create log scrubbing module with ScrubRegistry per D-09, D-10, D-11.

    ScrubRegistry class:
    - Static `_patterns: list[re.Pattern]` — compiled regex patterns
    - `@classmethod add_pattern(cls, name: str, pattern: str, replacement: str = '***')` — add a named scrub pattern
    - `@classmethod scrub(cls, text: str) -> str` — apply all patterns to text, return scrubbed version
    - `@classmethod from_env_names(cls, names: list[str])` — convenience: create patterns from env var names (matches `KEY=value` patterns)

    Initialize with comprehensive patterns (D-09):
    - Env var values: patterns derived from all known env var names (OPENAI_API_KEY, DEEPSEEK_API_TOKEN, NAVER_CLIENT_SECRET, etc.)
    - Bearer token headers: `Bearer\s+[\w-]+`
    - JWT tokens: `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
    - Email addresses: `[\w.+-]+@[\w-]+\.[\w.-]+` (PII per D-09)
    - `sk-...` style keys: `sk-[A-Za-z0-9]{20,}`
    - `ghp_` GitHub tokens
    - Any value after known secret env var names (line-specific: `KEY=VALUE` → `KEY=***`)

    Utility functions:
    - `get_scrubbed_logger(name: str) -> logging.Logger` — creates a logger with a filter/handler that applies ScrubRegistry.scrub() to all LogRecords. The filter wraps the message through scrub() before emitting.
    - `scrub_print(*args, **kwargs)` — drop-in replacement for `print()` that scrubs output (for backward compat during Strangler Fig transition, e.g. patching known print leaks like `token_refresh.py:57`). Avoids `logging` module where scripts use `print()`.

    Per D-10: Scrubbing happens at logger level (the filter intercepts all logging.LogRecord messages). Per D-11: The initial pattern list is built from known env var names, expandable via `add_pattern()`.

    **tests/conftest.py**: Expand with three new mock fixtures per D-16, D-17.

    Add at the end of `tests/conftest.py` (after the `monkeypatch_d1` fixture):

    1. `monkeypatch_openai(monkeypatch)` fixture:
    ```python
    @pytest.fixture
    def monkeypatch_openai(monkeypatch):
        """Mock OpenAI chat completions to return controlled responses"""
        class MockResponse:
            def __init__(self, content="Mocked response"):
                self.choices = [type('obj', (object,), {'message': type('obj', (object,), {'content': content})})()]
        def mock_create(*args, **kwargs):
            return MockResponse()
        monkeypatch.setattr("openai.resources.chat.completions.Completions.create", mock_create)
        return mock_create
    ```

    2. `monkeypatch_deepseek(monkeypatch)` fixture:
    Same pattern as OpenAI mock but targeting the DeepSeek API client import path.
    ```python
    @pytest.fixture
    def monkeypatch_deepseek(monkeypatch):
        """Mock DeepSeek API calls — target depends on actual import pattern in codebase"""
        from unittest.mock import MagicMock
        # Check actual import: if scripts use `from openai import OpenAI` with DEEPSEEK_BASE_URL
        mock = MagicMock()
        mock.chat.completions.create.return_value.choices[0].message.content = "Mocked DeepSeek response"
        monkeypatch.setattr("openai.OpenAI", lambda **kwargs: mock)
        return mock
    ```
    Note: Investigate the actual DeepSeek import path in `scripts/threads/v3/model_router.py` before finalizing the monkeypatch target — it may use `openai` package with custom base_url, not a separate `deepseek` package.

    3. `monkeypatch_http(monkeypatch)` fixture:
    ```python
    @pytest.fixture
    def monkeypatch_http(monkeypatch):
        """Mock HTTP requests (RSS feeds, web crawling) — target requests.get and urllib.request"""
        class MockResponse:
            def __init__(self, text="", status_code=200):
                self.text = text
                self.status_code = status_code
            def read(self):
                return self.text.encode()
        def mock_get(*args, **kwargs):
            from xml.etree.ElementTree import tostring
            return MockResponse(text="<rss><channel><item><title>Test</title></item></channel></rss>")
        monkeypatch.setattr("requests.get", mock_get)
        monkeypatch.setattr("urllib.request.urlopen", lambda url, **kwargs: MockResponse())
        return mock_get
    ```

    Each fixture should follow the existing conftest.py pattern: inherit `monkeypatch` parameter from pytest, use `monkeypatch.setattr()`, return the mock function for optional assertions in tests.

    Add docstrings (in Korean, following existing pattern) explaining what each mock replaces and when to use it.

    **scripts/threads/token_refresh.py:57**: Fix known token leak per CONCERNS.md. Line 57 currently prints the first 40 characters of the Threads access token:
    ```python
    print(f'  🔑 {new_token[:40]}...')  # BEFORE — leaks token prefix
    ```
    Replace with confirmation that avoids exposing the token value:
    ```python
    print(f'  🔑 토큰 갱신 완료 ({len(new_token)}자)')  # AFTER — confirms length only
    ```
  </action>
  <verify>
    <automated>
      python3 -c "import sys; sys.path.insert(0, '.'); from pipeline.infra.logger import ScrubRegistry; result = ScrubRegistry.scrub('My key is sk-test1234567890abcdefghij'); assert 'sk-test' not in result, 'API key not redacted'; print('PASS: ScrubRegistry redacts API keys')"
      python3 -c "import sys; sys.path.insert(0, '.'); from pipeline.infra.logger import ScrubRegistry; result = ScrubRegistry.scrub('Contact: user@example.com'); assert 'user@example.com' not in result, 'Email not redacted'; print('PASS: ScrubRegistry redacts emails')"
      python3 -c "
import sys; sys.path.insert(0, 'scripts'); sys.path.insert(0, '.')
# Verify conftest loads without error and exports new fixtures
exec(open('tests/conftest.py').read())
import pytest
# Verify the fixture names are registered
import conftest
assert hasattr(conftest, 'monkeypatch_openai') or 'monkeypatch_openai' in dir(conftest), 'monkeypatch_openai not found'
print('PASS: conftest exports new mock fixtures')
"
      pytest tests/ -x -q 2>&1 | tail -5
      grep -q 'new_token\[:40\]' scripts/threads/token_refresh.py && echo "FAIL: token leak still present" || echo "PASS: token leak fixed"
    </automated>
  </verify>
  <done>
    — pipeline/infra/logger.py exists with ScrubRegistry class and pattern-based redaction
    — API keys, JWT tokens, emails, and PII are all redacted by ScrubRegistry.scrub()
    — conftest.py has monkeypatch_openai, monkeypatch_deepseek, monkeypatch_http fixtures
    - All existing tests still pass after conftest expansion
    - token_refresh.py no longer prints token value on line 57
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| plist → launchd | launchd reads environment variables from plist at process start |
| git history → public | Secrets in git history are exposed if repo is made public |
| env file → Python process | .env files loaded by env_loader.py into process memory |
| logger → log file | Log output may contain secrets if not scrubbed |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | scripts/threads/threads-publisher.plist | mitigate | Remove entire EnvironmentVariables block (D-03). Plist holds no secrets after this phase. |
| T-01-02 | Information Disclosure | git history | mitigate | BFG Repo-Cleaner to purge secrets from history (D-01). Force push to rewrite history. |
| T-01-03 | Information Disclosure | log output | mitigate | ScrubRegistry at logger level (D-10). All log output passes through pattern-based redaction for API keys, JWT, emails, PII. |
| T-01-04 | Tampering | api_test/.env.sh | mitigate | Delete shadow config file (D-06). Eliminate untracked copy of secrets outside canonical sources. |
| T-01-05 | Elevation of Privilege | deploy.sh cross-project ref | mitigate | Decouple deploy.sh from /Users/twinssn/Projects/5000/.env (D-07). Each project authenticates independently. |
| T-01-06 | Information Disclosure | pipeline/infra/env_loader.py module-level side effects | mitigate | EnvConfig does NOT call load_to_environ() at module level — avoids loading secrets on import. |
| T-01-07 | Information Disclosure | API keys after remediation | accept | Keys were previously exposed in git history (even if REDACTED in current plist). Post-remediation, all keys rotated (D-02) and BFG-cleansed. Residual risk: user must complete key rotation for complete closure. |
</threat_model>

<verification>
## Phase Completion Checklist

- [ ] scripts/threads/threads-publisher.plist has zero EnvironmentVariables entries (Task 1)
- [ ] BFG repo-cleaner has been run against the repository (Task 1)
- [ ] Key rotation documented and pending user action (Task 1)
- [ ] pipeline/infra/env_loader.py exists with EnvConfig class (Task 2)
- [ ] api_test/.env.sh is deleted from disk (Task 2)
- [ ] deploy.sh has zero cross-project references (Task 2)
- [ ] ENV_SOURCE_MAP.md documents all 6+ env sources (Task 2)
- [ ] pipeline/infra/logger.py exists with ScrubRegistry (Task 3)
- [ ] conftest.py has monkeypatch_openai, monkeypatch_deepseek, monkeypatch_http (Task 3)
- [ ] token_refresh.py line 57 does not expose token value (Task 3)
- [ ] All existing pytest tests still pass (Task 3)
- [ ] token_refresh.py does not print token value on line 57 (Task 3)

## Automated Verification
```bash
# Verify no secrets in plist
grep -q 'EnvironmentVariables' scripts/threads/threads-publisher.plist && echo "FAIL" || echo "PASS"

# Verify env_loader loads correctly
python3 -c "from pipeline.infra.env_loader import EnvConfig; assert EnvConfig().get('OPENAI_API_KEY')"

# Verify shadow config deleted
test -f api_test/.env.sh && echo "FAIL" || echo "PASS"

# Verify deploy.sh is clean
grep -q '/Users/twinssn/Projects/5000' scripts/deploy.sh && echo "FAIL" || echo "PASS"

# Verify log scrubbing
python3 -c "from pipeline.infra.logger import ScrubRegistry; assert 'REDACTED' in ScrubRegistry.scrub('sk-test123')"

# Verify conftest mocks
python3 -c "import conftest; assert any('openai' in f for f in dir(conftest))"

# Verify token leak fixed
grep -q 'new_token\[:40\]' scripts/threads/token_refresh.py && echo "FAIL" || echo "PASS"

# All tests pass
pytest tests/ -x -q
```
</verification>

<success_criteria>
1. scripts/threads/threads-publisher.plist contains zero API keys or secrets — all env vars delegated to .env chain
2. ENV_SOURCE_MAP.md exists covering all 6+ env sources across the project
3. pipeline/infra/env_loader.py exists; zero env loading relies on it yet (Strangler Fig — Phase 2 wires old files)
4. Secrets in git history are flagged for remediation (BFG completed, key rotation documented)
5. Log output is verified to redact API keys, JWT tokens, emails, and PII via ScrubRegistry
6. conftest.py provides mock fixtures for OpenAI, DeepSeek, and HTTP requests
7. `token_refresh.py:57` no longer prints token value — replaced with length-only confirmation
8. All existing tests pass after changes
</success_criteria>

<output>
Create `.planning/phases/01-security-hardening/02-SUMMARY.md` when done
</output>
