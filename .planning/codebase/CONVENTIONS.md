# Coding Conventions

**Analysis Date:** 2026-06-30

## Overview

This project uses two distinct coding environments: **TypeScript (Astro/Cloudflare)** for the frontend/API layer, and **Python** for backend data pipelines, scraping, and automation scripts. Conventions differ between the two stacks.

## Language & Runtime

**TypeScript:**
- **Language:** TypeScript (strict mode via `astro/tsconfigs/strict`)
- **Runtime:** Node.js via Astro SSR on Cloudflare Workers
- **Module system:** ESM (`"type": "module"` in `package.json`)
- **Package Manager:** npm (`package-lock.json` present)

**Python:**
- **Language:** Python 3.10+
- **Runtime:** CPython (shebang `#!/usr/bin/env python3` on executable scripts)
- **Dependencies:** pip (`api_test/requirements.txt`)

## Code Style

**TypeScript (`src/`):**
- **Formatter:** Not detected (no `.prettierrc` or `eslint.config.*`)
- **Linter:** Not detected (no `.eslintrc*`)
- **Quotes:** Single quotes (`'`) for strings
- **Semicolons:** Not used (omitted on all statements)
- **Indentation:** 2 spaces
- **Trailing commas:** Yes (used everywhere — objects, arrays, function params)
- **JSX/HTML in Astro:** Inline `<script>` and `<style>` tags use no indentation convention

**Python (`scripts/`, `tests/`, `api_test/`):**
- **Formatter/Linter:** Not detected (no `.flake8`, `pyproject.toml`, or `ruff.toml` found)
- **Quotes:** Double quotes (`"`) preferred, single quotes used for short strings
- **Semicolons:** Not used
- **Indentation:** 4 spaces
- **Line length:** Inconsistent (some lines exceed 100 chars)
- **Trailing commas:** Rarely used

## Naming Conventions

**TypeScript (`src/`):**

| Category | Convention | Example |
|----------|-----------|---------|
| Variables | camelCase | `currentUser`, `sessionSecret` |
| Functions | camelCase | `signSession()`, `getSessionUser()` |
| Classes | Not used | — |
| Files/Dirs | kebab-case | `SEOHead.astro`, `auth.ts`, `user-profile.ts` |
| Astro Components | PascalCase (in filename) | `HeroSection.astro`, `Layout.astro` |
| Types/Interfaces | PascalCase | `Post`, `TaskInfo`, `SitemapEntry` |
| Constants | UPPER_SNAKE_CASE | `SECURITY_HEADERS`, `PLANS`, `SHORT_SLUGS` |
| Env variables | UPPER_SNAKE_CASE | `SESSION_SECRET` |
| CSS classes | kebab-case | `.bg-primary`, `.animate-pulse-slow` |
| API routes | kebab-case | `/api/auth/logout`, `/api/search/` |

**Python (`scripts/`, `tests/`):**

| Category | Convention | Example |
|----------|-----------|---------|
| Variables | snake_case | `recent_posts`, `current_user` |
| Functions | snake_case | `load_weights()`, `score_article()` |
| Classes | PascalCase | `TestAmountParsing`, `TestCascadeLightScore` |
| Files | snake_case | `auto_news_selector.py`, `briefing_scorer.py` |
| Constants | UPPER_SNAKE_CASE | `PROJECT_DIR`, `WEIGHTS_PATH`, `MIMO_BASE_URL` |
| Test methods | snake_case | `test_light_score_produces_financial()` |
| Test classes | PascalCase | `TestEntityTier`, `TestConfigLoad` |
| Private functions | prefixed with `_` | `_parse_amounts()`, `_score_financial_impact()` |

## Code Patterns

### Pattern 1: Astro Component with Inline Props Interface (TypeScript)
- **Description:** Every Astro component defines a `Props` interface at the top of the frontmatter (`---` block), then destructures `Astro.props` with defaults.
- **Example:** `src/components/SEOHead.astro`, `src/layouts/Layout.astro`
- **Usage:** All Astro `.astro` files follow this pattern.

```astro
---
interface Props {
  title: string;
  description: string;
  image?: string;
  noindex?: boolean;
}

const {
  title,
  description,
  image = '/og-default.jpeg',
  noindex = false,
} = Astro.props;
---
```

### Pattern 2: Module-Level Constants with UPPER_SNAKE_CASE (Python)
- **Description:** Configuration paths and project roots defined at module level, using `os.path` or `pathlib`.
- **Example:** `scripts/briefing_scorer.py` (lines 22-24), `scripts/auto_briefing.py` (lines 11-12)
- **Usage:** All Python scripts use file-scoped uppercase constants for paths.

```python
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_PATH = os.path.join(PROJECT_DIR, "config", "impact_weights.json")
```

### Pattern 3: Docstring as Module Header (Python)
- **Description:** Every Python script starts with a module-level docstring describing its purpose, usage, and dependencies.
- **Example:** `scripts/briefing_scorer.py` (lines 1-12), `scripts/auto_news_selector.py` (lines 1-9)
- **Usage:** All scripts in `scripts/` and integration tests in `api_test/`.

### Pattern 4: Pipeline Logging Function (Python)
- **Description:** A simple `log()` function prints timestamped messages to stdout. Used in all pipeline scripts.
- **Example:** `scripts/auto_briefing.py` (lines 30-32)
- **Usage:** For pipeline output; NOT used in library modules like `briefing_scorer.py`.

```python
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
```

### Pattern 5: Cloudflare D1 Access via `wrangler d1 execute` (Python)
- **Description:** Python scripts access Cloudflare D1 database by shelling out to `npx wrangler d1 execute` with raw SQL strings. Used in pipeline scripts that don't have direct D1 bindings.
- **Example:** `scripts/auto_news_selector.py` (lines 38-52), `scripts/auto_briefing.py` (lines 34-45)
- **Usage:** Backend data pipeline scripts. Returns parsed JSON results.

### Pattern 6: Content Collections with Zod Schemas (TypeScript)
- **Description:** Content types (`blog`, `tools`, `keywords`, `chronicle`, `glossary`) defined via Astro's `defineCollection` with Zod schema validation.
- **Example:** `src/content.config.ts` (all 96 lines)
- **Usage:** All structured content in `src/content/` subdirectories.

### Pattern 7: Dynamic Data Fetching in Astro Pages (TypeScript)
- **Description:** Pages fetch data from D1/D1 at render time using `Astro.locals.runtime.env.DB`. Error handling with try/catch returning null fallback.
- **Example:** `src/pages/index.astro` (lines 25-47)
- **Usage:** SSR pages that need database data at request time.

## Error Handling

**TypeScript (`src/`):**
- **Pattern:** `try/catch` with `console.error()` logging, returning null or fallback values
- **Logging:** `console.error()`, `console.warn()` — no structured logger
- **User-facing errors:** Errors silently swallowed; null/empty UI shown instead
- **Async errors:** Wrapped in try/catch at the API route/page level
- **No custom error classes** detected

Example from `src/pages/index.astro`:
```typescript
try {
  const runtime = (Astro.locals as any).runtime;
  const db = runtime?.env?.DB;
  if (db) {
    briefing = await db.prepare("SELECT * FROM briefings ...").first();
  }
} catch (e) {
  console.error('Briefing fetch error:', e);
}
```

**Python (`scripts/`, `tests/`):**
- **Pattern:** `try/except` with fallback return values (empty list, None, or 0)
- **Logging:** `print()` calls via `log()` helper function (no Python logging module)
- **No custom exception classes** detected
- **External API errors:** Caught broadly with `except Exception`
- **JSON parsing:** Silent `try/except` with empty defaults

Example from `scripts/auto_news_selector.py`:
```python
try:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR)
    if r.returncode != 0:
        log(f"  D1 반환코드 {r.returncode}, 재시도 ({attempt+1}/{retries})")
        continue
    m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', r.stdout)
    if m:
        return json.loads(m.group(1))
    return []
except Exception as e:
    log(f"  D1 오류: {e}, 재시도 ({attempt+1}/{retries})")
```

## Imports

**TypeScript (`src/`):**
- **Order:**
  1. Astro built-ins (`astro:middleware`, `astro:content`)
  2. Internal relative imports (`../components/...`, `./utils/...`)
- **Absolute vs relative:** Relative imports only (e.g., `'../components/SEOHead.astro'`)
- **Barrel files:** Not used (no `index.ts` re-exports)
- **Path aliases:** Not configured (no `paths` in `tsconfig.json`)
- **Astro components imported with .astro extension** explicitly

**Python (`scripts/`, `tests/`):**
- **Order:**
  1. Standard library (`json`, `os`, `sys`, `re`, `datetime`)
  2. Third-party (`requests`, `pytest`, `bs4`)
  3. Local imports (`from briefing_scorer import ...`)
- **Local imports:** Direct module name (since `scripts/` is added to `sys.path`)
- **Dynamic `sys.path`** manipulation at module top: `sys.path.insert(0, str(Path(__file__).parent))`

## Async Patterns

**TypeScript:**
- **Async/await** used exclusively (no raw `.then()` or callbacks)
- **Error handling:** Try/catch wrapping all `await` calls
- **Top-level await** used in Astro frontmatter (`---` blocks) and API route handlers
- **Promise utilities:** None observed (`Promise.all` not used)

**Python:**
- **Synchronous** (no `asyncio` usage detected)
- **Network calls** via `requests` library (blocking)
- **Subprocess** via `subprocess.run()` (blocking)

## TypeScript Usage

- **Strict mode:** Enabled (`extends: "astro/tsconfigs/strict"` in `tsconfig.json`)
- **`any` usage:** Common for runtime objects (`(Astro.locals as any).runtime`) and database results. Not discouraged.
- **Interface vs type:** `interface` used for all complex types (e.g., `Post`, `TaskInfo`, `SitemapEntry`). `type` not used for object types.
- **Inline type assertions:** `as HTMLInputElement`, `as any`
- **Optional properties:** `?` suffixed consistently (`image?: string`)
- **Generics:** Minimal usage (`Record<string, string>`, `Array<MetaDataImage>`)

## Comments & Documentation

**TypeScript:**
- **JSDoc:** Optional — used only in `src/types.d.ts` for type descriptions. Not used on functions.
- **Inline comments:** Korean comments explain non-obvious logic (e.g., `// 세션에서 유저 정보 추출 (HMAC 검증 포함)` in `src/lib/auth.ts:41`)
- **TODO/FIXME:** Not found in the TypeScript source

**Python:**
- **Docstrings:** Required at module level (every script has one). Optional at function level — used in some (e.g., `briefing_scorer.py`), not in others.
- **Section comments:** Heavy use of `# ====` section dividers (`scripts/keyword_updater.py`)
- **Korean comments:** Used in pipeline scripts for Korean-language explanations
- **TODO/FIXME:** Not found in the Python source

## Synchronization Convention

- **Task vocabulary** (controlled vocabulary) must be kept in sync between TypeScript (`src/config/tasks.ts`) and Python (`scripts/task_config.py`). Comment at top of `src/config/tasks.ts` (line 3) explicitly warns: `// 두 파일이 항상 동기화되어야 함`

---

*Convention analysis: 2026-06-30*
