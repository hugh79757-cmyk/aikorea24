# Architecture Patterns — Modular Python Pipeline

**Project:** AI코리아24 (aikorea24.kr)
**Researched:** 2026-06-30
**Mode:** Ecosystem (Architecture dimension)
**Overall confidence:** HIGH (analysis based on thorough codebase reverse-engineering)

## Executive Summary

The existing Python automation pipeline is a **monolithic sequential orchestrator** with 10+ standalone scripts that each duplicate the same infrastructure code (`PROJECT_DIR`, `load_env()`, `d1_query()`, `log()`). Data passes between steps via a mix of in-memory Python objects, D1 database writes, and filesystem artifacts — with no formal contract between steps. The architecture has been validated by production use but is fragile, non-portable, and difficult to extend.

**The recommended target architecture** is a **Pipe & Filter pattern** with three layers:

1. **Infrastructure Layer** — shared modules for env loading, D1 access, configuration, and structured logging
2. **Step Layer** — independent filter modules, each owning one transformation (news selection → briefing → deep article → thumbnail → email → deploy)
3. **Orchestration Layer** — a coordinator that wires steps together, manages skip/dry-run flags, and collects per-step results

This is NOT a greenfield rewrite. The recommended approach is the **Strangler Fig pattern**: add shared infrastructure modules first (with zero behavioral change), then migrate each step file to import from shared modules, then finally restructure the directory layout.

---

## Current Architecture (As-Is)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      run_pipeline.py (Orchestrator)                  │
│  Sequential: news → briefing → deep_article → thumbnail → email →  │
│  deploy. Each step is a try/except block.                           │
│  Data flow: Python dicts in memory + D1 writes + filesystem writes   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  scripts/                                                           │
│  ├── auto_news_selector.py   490 lines  duplicate: PROJECT_DIR,     │
│  │                                        d1_query(), log()         │
│  ├── auto_briefing.py        265 lines  duplicate: PROJECT_DIR,     │
│  │                                        d1_query() (named d1_ex.) │
│  ├── auto_deep_article.py               duplicate: PROJECT_DIR,     │
│  ├── auto_thumbnail.py                  duplicate: PROJECT_DIR      │
│  ├── auto_email_sender.py               duplicate: PROJECT_DIR      │
│  └── threads/                                                      │
│      ├── main_v3.py                     duplicate: PROJECT_DIR,     │
│      │                                        load_env()            │
│      ├── db_reader.py         363 lines  duplicate: PROJECT_DIR,     │
│      │                                        d1_query(), load_env() │
│      ├── publisher.py         252 lines  duplicate: PROJECT_DIR,     │
│      │                                        load_env(),            │
│      │                                        load_posted()          │
│      └── v3/                                                       │
│          ├── writer_v3.py     1013 lines duplicate: PROJECT_DIR,    │
│          │                                  load_posted()            │
│          ├── narrative_pitcher.py 581 lines duplicate: load_env()   │
│          ├── model_router.py             duplicate: load_env()      │
│          └── format_selector.py          dead code (no-op)          │
└─────────────────────────────────────────────────────────────────────┘
```

### Current Pain Points (from codebase analysis)

| Problem | Files Affected | Consequence |
|---------|---------------|-------------|
| Hardcoded `PROJECT_DIR` | 11+ files | Zero portability |
| Duplicated `load_env()` | 5+ files | Inconsistent env sources |
| Duplicated `d1_query()` | 3 files | Different retry/timeout behavior |
| Duplicated `load_posted()` | 2 files | Schema drift risk |
| Module-level side effects | `model_router.py`, `narrative_pitcher.py` | Breaks testability |
| 1013-line monolith | `writer_v3.py` | Single change risks unrelated logic |
| Bare `except:` blocks | 6+ locations | Silently swallows KeyboardInterrupt |
| No type annotations | All 4,000+ lines | Poor IDE support, hard refactoring |
| Cross-project .env dependency | `deploy.sh` | Silent deploy breakage |

---

## Recommended Architecture (To-Be)

### Pattern: Pipe & Filter with Strangler Fig Migration

```
┌─────────────────────────────────────────────────────────┐
│                  CLI Entry Points                        │
│  run_pipeline.py  run_threads.py  (thin wrappers)       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │           orchestrator.py (Coordinator)            │   │
│  │  ● Defines PipelineStep protocol                  │   │
│  │  ● Manages skip flags / dry-run / date param      │   │
│  │  ● Collects per-step results + metrics            │   │
│  │  ● Sends final summary + notifications            │   │
│  └──────┬──────────────┬──────────────┬──────────────┘   │
│         │              │              │                  │
│         ▼              ▼              ▼                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Step 1  │  │  Step 2  │  │  Step 3  │  ...        │
│  │  news    │──▶ briefing──▶  deep     │              │
│  │ selector │  │          │  │ article  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│         │              │              │                  │
│         ▼              ▼              ▼                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Infrastructure Layer (shared)            │   │
│  │  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌────────┐  │   │
│  │  │config   │ │d1_client │ │logger  │ │env_ldr │  │   │
│  │  │.py      │ │.py       │ │.py     │ │.py     │  │   │
│  │  └─────────┘ └──────────┘ └────────┘ └────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│                  External Services                       │
│  Cloudflare D1  MiMo API  Brevo API  Threads API  R2   │
└─────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With | Status |
|-----------|---------------|-------------------|--------|
| **`infra/config.py`** | Project path resolution, global settings | All steps | **Create new** |
| **`infra/env_loader.py`** | Load env from `.env` + `~/.env.common`, expose as typed dataclass | All steps | **Create new** |
| **`infra/d1_client.py`** | Wranger D1 execute wrapper, consistent retry, typed queries | Steps that read/write D1 | **Create new** |
| **`infra/logger.py`** | Structured logging with timestamps, log levels, file rotation | All steps | **Create new** |
| **`infra/models.py`** | Typed dataclasses for pipeline data (NewsArticle, Briefing, etc.) | Steps, orchestrator | **Create new** |
| **`steps/news_selector.py`** | RSS crawling, 2-pass impact scoring, D1 news insertion | d1_client, config | **Migrate from auto_news_selector.py** |
| **`steps/briefing.py`** | Top article selection, MiMo commentary, D1 briefing write | d1_client, env_loader | **Migrate from auto_briefing.py** |
| **`steps/deep_article.py`** | Article crawling, MiMo deep-dive generation, MD file write | d1_client, env_loader | **Migrate from auto_deep_article.py** |
| **`steps/thumbnail.py`** | OG thumbnail generation via image API, R2/fs write | config, logger | **Migrate from auto_thumbnail.py** |
| **`steps/email_sender.py`** | Brevo email dispatch for daily briefing | env_loader, logger | **Migrate from auto_email_sender.py** |
| **`steps/deploy.py`** | npm build + wrangler pages deploy | config, logger | **Migrate from deploy.sh** |
| **`orchestrator.py`** | Step registration, sequential execution, result aggregation, summary | All steps, infra | **Create new** |
| **`threads/db_reader.py`** | D1 article loading with 3-tier priority + dedup | d1_client, config | **Refactor** (extract shared infra) |
| **`threads/pitch.py`** | Pitch generation + evaluation (extracted from narrative_pitcher) | model_router, d1_client | **Split from monolith** |
| **`threads/writer.py`** | Thread card generation (extracted from writer_v3) | model_router, config | **Split from monolith** |
| **`threads/validator.py`** | Card validation, year check, keyword check | config | **Extract from writer_v3** |
| **`threads/publisher.py`** | Threads API publish + token refresh | env_loader, config | **Refactor** (extract shared infra) |
| **`threads/dedup.py`** | Jaccard similarity, entity overlap, posted.json management | config | **Keep and standardize** |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Shared infra in `pipeline/infra/`, not top-level** | Prevents namespace pollution; clear boundary between infrastructure and business logic |
| **No abstract base class for steps initially** | Over-engineering for 6 synchronous steps with known order. Use a simple `PipelineStep` protocol (duck typing) instead |
| **Step modules remain largely as-is during migration** | The refactoring goal is to extract duplication, not rewrite logic. Each step's internal algorithm stays untouched |
| **D1 as canonical state, not temp files** | D1 already tracks news, briefings, briefing_items. Adding pipeline_run_status, step_attempts columns is cleaner than JSON files |
| **Env vars loaded once at startup, not per-step** | Current module-level `load_env()` calls cause side effects on import. Lazy singleton pattern fixes this |
| **No new external dependencies** | Stick to stdlib + existing deps (requests, BeautifulSoup). Avoid Airflow/Prefect/Kedro — overkill for local cron pipeline |

---

## Data Flow

### Typed Data Pipeline (Formalized)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  NEWS SELECTION                      BRIEFING                                 │
│                                                                                │
│  RSS Feeds ──▶ news_selector() ──▶ D1 news table                               │
│                     │                    │                                     │
│                     ▼                    ▼                                     │
│               List[NewsArticle]    List[NewsArticle]  (top scored)              │
│                     │                    │                                     │
│                     └────────┬───────────┘                                     │
│                              ▼                                                 │
│                       BriefingInput                                            │
│                         │                                                      │
│                         ▼                                                      │
│  ┌──────────────── BRIEFING ──────────────────┐                                │
│  │  briefing.generate(data) → BriefingResult   │                                │
│  │  ● Writes to D1 briefings + briefing_items  │                                │
│  │  ● Returns briefing_id                      │                                │
│  └──────────────────────────────────────────────┘                              │
│                         │                                                      │
│                         ▼                                                      │
│  ┌──────────── DEEP ARTICLE ──────────────────┐                                │
│  │  deep_article.generate(articles, id) →      │                                │
│  │  List[DeepArticleResult]                    │                                │
│  │  ● Crawls URLs                              │                                │
│  │  ● Calls MiMo for generation                │                                │
│  │  ● Writes .md to src/content/blog/           │                                │
│  │  ● Updates briefing_items.deep_dive_url     │                                │
│  └──────────────────────────────────────────────┘                              │
│                         │                                                      │
│                         ▼                                                      │
│  ┌──────────── THUMBNAIL ────────────────────┐                                │
│  │  thumbnail.generate(articles) → List[str]   │                                │
│  │  ● Generates images                        │                                │
│  │  ● Writes to public/blog-thumbnails/        │                                │
│  └──────────────────────────────────────────────┘                              │
│                         │                                                      │
│                         ▼                                                      │
│  ┌──────────── EMAIL ────────────────────────┐                                │
│  │  email.send() → bool                       │                                │
│  │  ● Reads today's briefing from D1          │                                │
│  │  ● Sends via Brevo API                     │                                │
│  └──────────────────────────────────────────────┘                              │
│                         │                                                      │
│                         ▼                                                      │
│  ┌──────────── DEPLOY ───────────────────────┐                                │
│  │  deploy.run() → bool                       │                                │
│  │  ● npm run build + wrangler pages deploy   │                                │
│  └──────────────────────────────────────────────┘                              │
│                                                                                │
│  LEGEND:                                                                       │
│  ──▶ Data passed in memory (typed objects)                                     │
│  ──▶ Side effect (D1 write, file write, API call)                             │
│  ──▶ Data read from D1 (not passed in memory)                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### What passes in memory vs. what goes through D1

| Data | Passed in memory? | Stored in D1? | Why |
|------|-------------------|---------------|-----|
| Selected news articles | YES (`list[NewsArticle]`) | YES (news table, written by selector) | In-memory for downstream steps to avoid re-querying |
| Briefing ID | YES (`int`) | YES (briefings table) | Passed to deep_article for `deep_dive_url` linking |
| Deep article file paths | YES (`list[DeepArticleResult]`) | NO (blog .md files on fs) | Only needed for summary log |
| Thumbnail paths | YES (`list[str]`) | NO (static files) | Only needed for summary log |
| Email result | NO | NO | Side-effect only; success/fail in orchestration metrics |
| Deploy result | NO | NO | Side-effect only |
| Pipeline run status | NO | **SHOULD ADD** `pipeline_runs` table | Currently tracked only via summary dict — should persist for monitoring |

### Typed Data Contracts

```python
# pipeline/infra/models.py — NEW (currently: ad-hoc dicts everywhere)

@dataclass
class NewsArticle:
    id: int
    title: str
    link: str
    source: str
    description: str
    published_at: datetime
    score: float = 0.0
    category: str | None = None

@dataclass
class BriefingInput:
    articles: list[NewsArticle]
    date: str  # YYYY-MM-DD

@dataclass
class BriefingResult:
    briefing_id: int
    article_count: int

@dataclass
class DeepArticleResult:
    title: str
    filepath: str
    blog_url: str | None

@dataclass
class PipelineRunResult:
    step_name: str
    success: bool
    duration_seconds: float
    error: str | None = None
    data: dict | None = None
```

---

## Orchestration Patterns

### Recommended: Sequential with Per-Step Isolation

This is what the existing `run_pipeline.py` does. Formalize it rather than replace it.

```python
# pipeline/orchestrator.py — NEW

from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import traceback

@dataclass
class PipelineStep:
    name: str
    fn: Callable
    skip_flag: bool = False
    requires: list[str] = field(default_factory=list)
    is_critical: bool = False  # If True, failure aborts pipeline

class PipelineOrchestrator:
    """Sequential step executor with isolation, metrics, and summary."""
    
    def __init__(self, dry_run: bool = False, date: str | None = None):
        self.dry_run = dry_run
        self.date = date or datetime.now().strftime("%Y-%m-%d")
        self.steps: dict[str, PipelineStep] = {}
        self.results: dict[str, PipelineRunResult] = {}
        self._context: dict = {}
    
    def add_step(self, step: PipelineStep):
        self.steps[step.name] = step
    
    def run(self):
        for name, step in self.steps.values():
            if step.skip_flag:
                self.results[name] = PipelineRunResult(
                    step_name=name, success=True, duration_seconds=0.0
                )
                continue
            # Check requirements
            for req in step.requires:
                if req not in self.results or not self.results[req].success:
                    self._log(f"Skipping {name}: required step {req} failed")
                    continue
            # Execute with isolation
            start = datetime.now()
            try:
                if self.dry_run:
                    self._log(f"[DRY-RUN] Would execute: {name}")
                    result_data = step.fn(dry_run=True, context=self._context)
                else:
                    result_data = step.fn(context=self._context)
                self.results[name] = PipelineRunResult(
                    step_name=name, success=True,
                    duration_seconds=(datetime.now() - start).total_seconds(),
                    data=result_data
                )
            except Exception as e:
                self.results[name] = PipelineRunResult(
                    step_name=name, success=False,
                    duration_seconds=(datetime.now() - start).total_seconds(),
                    error=f"{type(e).__name__}: {e}"
                )
                if step.is_critical:
                    raise  # Abort pipeline
        return self.summary()
```

### Why Not DAG / Event-Driven / Message Queue?

| Pattern | Verdict | Reason |
|---------|---------|--------|
| **Sequential (current)** | ✅ **Keep** | 6 steps with known linear order. No branching. No parallelism needed. Over-engineering would add complexity without benefit |
| **DAG / Dependency Graph** | ❌ | Would be appropriate if steps had complex dependencies or could run in parallel. Currently step N depends on step N-1 |
| **Event-Driven / Pub-Sub** | ❌ | Would be appropriate for real-time processing or multi-consumer scenarios. Pipeline runs once daily |
| **Message Queue (Redis/SQS)** | ❌ | Adds infrastructure dependency. Pipeline is local cron — no need for queue durability |

### Exception: Threads Pipeline

The Threads pipeline (`main_v3.py`) IS a DAG-like pattern — it has branching (pitch evaluation, format selection, writer) and retry with fallback model chain. This should remain a self-contained module with its own internal orchestrator, NOT folded into the daily pipeline orchestrator.

---

## Configuration Management

### Three-Layer Config Pattern

```
Layer 1: Environment Variables (secrets, env-specific)
  └── Loaded by env_loader.py from:
      ├── ~/.env.common           (shared across projects — API keys)
      └── .env                    (project-specific — DB IDs, paths)

Layer 2: Pipeline Settings (behavioral flags)
  └── Defined in pipeline/config.py:
      ├── PROJECT_DIR (computed, not hardcoded)
      ├── Default skip flags
      ├── Step timeout values
      └── Log paths (computed from PROJECT_DIR)

Layer 3: CLI Overrides (per-run flags)
  └── Parsed by run_pipeline.py:
      ├── --skip-news, --skip-briefing, ...
      ├── --date YYYY-MM-DD
      └── --dry-run
```

### Env Loader Design

```python
# pipeline/infra/env_loader.py — NEW (replaces 5+ duplicate implementations)

import os
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass, field

@dataclass(frozen=True)
class EnvConfig:
    mimo_api_key: str = ""
    threads_access_token: str = ""
    threads_user_id: str = ""
    brevo_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    cloudflare_api_token: str = ""

@lru_cache(maxsize=1)
def load_env() -> EnvConfig:
    """Load environment once, cache forever. No module-level side effects."""
    _load_dotenv(os.path.expanduser("~/.env.common"))
    _load_dotenv(".env")
    return EnvConfig(
        mimo_api_key=os.getenv("MIMO_API_KEY", ""),
        threads_access_token=os.getenv("THREADS_ACCESS_TOKEN", ""),
        threads_user_id=os.getenv("THREADS_USER_ID", ""),
        brevo_api_key=os.getenv("BREVO_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN", ""),
    )

def _load_dotenv(path: str | Path):
    """Simple .env parser without python-dotenv dependency."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("source"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
```

### Config Path Resolution

```python
# pipeline/infra/config.py — NEW (replaces 11+ hardcoded PROJECT_DIR)

from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def project_root() -> Path:
    """Find project root by walking up from this file."""
    # Strategy: look for scripts/run_pipeline.py or wrangler.toml
    current = Path(__file__).resolve().parent  # pipeline/infra/
    for _ in range(5):  # max 5 levels up
        current = current.parent
        if (current / "scripts").is_dir() or (current / "wrangler.toml").is_file():
            return current
    raise RuntimeError("Could not find project root")

# Computed paths — single source of truth
SCRIPTS_DIR = project_root() / "scripts"
CONTENT_DIR = project_root() / "src" / "content"
BLOG_DIR = CONTENT_DIR / "blog"
THUMBNAILS_DIR = project_root() / "public" / "blog-thumbnails"
LOGS_DIR = SCRIPTS_DIR / "logs"
THREADS_DIR = SCRIPTS_DIR / "threads"
CONFIG_DIR = project_root() / "config"
```

---

## Error Handling

### Per-Step Isolation (Existing Pattern, Formalized)

| Aspect | Current | Target |
|--------|---------|--------|
| Catch scope | Bare `except:` in 6+ places | Always `except Exception:` (never bare) |
| Error propagation | Continues silently | Logs error + stores in result dict |
| Critical steps | All treated equally | Configurable: `is_critical=True` aborts pipeline |
| Retry | Inconsistent (0-2 retries, different delays) | Consistent `retry()` decorator in infra |

### Retry Decorator

```python
# pipeline/infra/retry.py — NEW

import time
import functools

def retry(max_attempts=3, delay=2.0, backoff=2.0, allowed=(ConnectionError, TimeoutError)):
    """Retry a function with exponential backoff for transient failures."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except allowed as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        sleep_time = delay * (backoff ** attempt)
                        time.sleep(sleep_time)
                except Exception:
                    raise  # Don't retry unexpected errors
            raise last_error  # Re-raise if all attempts failed
        return wrapper
    return decorator
```

### Graceful Degradation Rules

| Step | Should It Fail Pipeline? | If It Fails... |
|------|-------------------------|----------------|
| News selection | ⚠️ Critical — nothing downstream can run | Pipeline aborts |
| Briefing | ⚠️ Critical — email depends on it | Pipeline aborts |
| Deep article | ✅ Non-critical | Log error, continue to thumbnail |
| Thumbnail | ✅ Non-critical | Log error, continue to email |
| Email | ❌ Don't fail — can retry later | Log error, continue to deploy (email can be sent manually) |
| Deploy | ✅ Non-critical | Log error, exit (deploy can be triggered manually) |

---

## Recommended Directory Tree

### Target Structure

```
scripts/
├── __init__.py
│
├── pipeline/                          # ← NEW: modular pipeline package
│   ├── __init__.py
│   │
│   ├── infra/                         # Shared infrastructure (no business logic)
│   │   ├── __init__.py
│   │   ├── config.py                  # Project path resolution, computed paths
│   │   ├── env_loader.py              # Centralized env loading, EnvConfig dataclass
│   │   ├── d1_client.py               # Typed D1 client with consistent retry
│   │   ├── logger.py                  # Structured logging with levels + file rotation
│   │   ├── models.py                  # Typed dataclasses for pipeline data contracts
│   │   └── retry.py                   # Retry decorator for transient failures
│   │
│   ├── steps/                         # Business logic — one module per pipeline step
│   │   ├── __init__.py
│   │   ├── news_selector.py           # MIGRATED from auto_news_selector.py
│   │   ├── briefing.py                # MIGRATED from auto_briefing.py
│   │   ├── deep_article.py            # MIGRATED from auto_deep_article.py
│   │   ├── thumbnail.py               # MIGRATED from auto_thumbnail.py
│   │   ├── email_sender.py            # MIGRATED from auto_email_sender.py
│   │   └── deploy.py                  # MIGRATED from deploy.sh (Python wrapper)
│   │
│   ├── threads/                       # Threads pipeline (self-contained DAG)
│   │   ├── __init__.py
│   │   ├── config.py                  # Threads-specific config (paths, limits)
│   │   ├── db_reader.py               # REFACTORED: uses infra/d1_client
│   │   ├── dedup.py                   # KEPT: semantic dedup logic
│   │   ├── pitch.py                   # SPLIT from narrative_pitcher.py
│   │   ├── pitch_evaluator.py         # KEPT: evaluation gate
│   │   ├── writer.py                  # SPLIT from writer_v3.py (card generation)
│   │   ├── validator.py               # EXTRACTED from writer_v3 (validate_cards/year/keywords)
│   │   ├── publisher.py               # REFACTORED: uses infra/env_loader
│   │   ├── model_router.py            # REFACTORED: no module-level side effects
│   │   └── prompts/                   # KEPT: prompt files
│   │
│   └── orchestrator.py               # Pipeline coordinator — wires steps together
│
├── run_pipeline.py                    # ← KEPT as thin CLI wrapper
│                                      #   imports pipeline.orchestrator
│                                      #   registers steps, parses args, calls run()
│
├── run_threads.py                     # ← REFACTORED from main_v3.py
│                                      #   thin CLI wrapper for threads pipeline
│
│── auto_news_selector.py              # ← KEPT during migration (deleted after migration)
│── auto_briefing.py                   # ← KEPT during migration
│── auto_deep_article.py               # ← KEPT during migration
│── auto_thumbnail.py                  # ← KEPT during migration
│── auto_email_sender.py               # ← KEPT during migration
│── deploy.sh                          # ← KEPT during migration
│
├── tasks/                             # STANDALONE — unrelated to daily pipeline
│   ├── task_config.py                 # KEPT
│   ├── keyword_updater.py             # KEPT
│   ├── tools_collector.py             # KEPT
│   ├── outline_generator.py           # KEPT
│   ├── blog_draft_generator.py        # KEPT
│   └── tools_sync.mjs                 # KEPT
│
├── threads/                           # ← REMOVED after migration
│   ├── main_v3.py                     #     (replaced by run_threads.py)
│   ├── db_reader.py                   #     (moved to pipeline/threads/)
│   ├── publisher.py                   #     (moved to pipeline/threads/)
│   ├── v3/writer_v3.py               #     (split into writer.py + validator.py)
│   └── v3/narrative_pitcher.py        #     (split into pitch.py + pitch_evaluator.py)
│
├── tests/                             # ← EXPANDED
│   ├── conftest.py                    #     KEPT: monkeypatch_d1 fixture
│   ├── test_news_selector.py          #     NEW
│   ├── test_briefing.py               #     NEW
│   ├── test_orchestrator.py           #     NEW
│   └── test_threads/                  #     EXPANDED
│       ├── test_dedup.py
│       ├── test_validator.py
│       ├── test_pitch.py
│       └── test_writer.py
│
├── config/                            # KEPT
│   ├── crawlable_sources.json
│   ├── entity_tiers.json
│   └── impact_weights.json
│
└── logs/                              # KEPT
```

### Key Structural Decisions

1. **`pipeline/steps/` NOT `pipeline/steps/daily/`** — only one pipeline type uses steps. No need for sub-namespace.

2. **`pipeline/threads/` NOT `pipeline/threads/v3/`** — the `v3/` segment was a legacy convention after A/B/C format experiments. Clean it up now. Current code IS the "v3" logic.

3. **Standalone scripts stay in `tasks/`** — `keyword_updater.py`, `tools_collector.py`, `outline_generator.py` are standalone utilities with no integration with the daily pipeline. They just need shared infra (env_loader, d1_client) but their logic is unrelated.

4. **Old files deleted only after full migration** — The "Strangler Fig" approach means old files stay until their pipeline/threads/ equivalent is verified in production. Old files use the shared infra modules but are NOT deleted until the new structure handles every use case.

---

## Migration Strategy (Build Order)

### Phase 1: Infrastructure Layer (Zero Behavioral Change)
*Add shared modules. Old files continue working unchanged.*

| Step | What | Files | Old Files Affected |
|------|------|-------|-------------------|
| 1.1 | Create `pipeline/infra/config.py` with `project_root()` | NEW | None (no imports yet) |
| 1.2 | Create `pipeline/infra/env_loader.py` with `load_env()` | NEW | None |
| 1.3 | Create `pipeline/infra/d1_client.py` with `D1Client` | NEW | None |
| 1.4 | Create `pipeline/infra/logger.py` with `get_logger()` | NEW | None |
| 1.5 | Create `pipeline/infra/models.py` with dataclasses | NEW | None |
| 1.6 | Create `pipeline/infra/retry.py` | NEW | None |

**Verification:** Run `python3 -c "from pipeline.infra import config; print(config.project_root())"` — should print correct path.

### Phase 2: Wire Old Files to Shared Infra (Low Risk)
*Each old file: remove its duplicate PROJECT_DIR/load_env/d1_query, import from infra instead.*

| Step | File to Update | Remove | Add Import |
|------|---------------|--------|------------|
| 2.1 | `auto_news_selector.py` | `PROJECT_DIR`, own `d1_query()`, own `log()` | `from pipeline.infra.config import ...` |
| 2.2 | `auto_briefing.py` | `PROJECT_DIR`, own `d1_execute()`, own `log()` | Same |
| 2.3 | `auto_deep_article.py` | `PROJECT_DIR` | Same |
| 2.4 | `auto_thumbnail.py` | `PROJECT_DIR` | Same |
| 2.5 | `auto_email_sender.py` | `PROJECT_DIR` | Same |
| 2.6 | `threads/db_reader.py` | `PROJECT_DIR`, own `d1_query()`, own `log()` | Same |
| 2.7 | `threads/publisher.py` | `PROJECT_DIR`, own `load_env()`, own `load_posted()` | Same |
| 2.8 | `threads/v3/writer_v3.py` | `PROJECT_DIR`, own `log()` | Same |
| 2.9 | `threads/v3/narrative_pitcher.py` | own `load_env()` (module-level side effect) | Same |
| 2.10 | `threads/v3/model_router.py` | own `load_env()` (module-level side effect) | Same |
| 2.11 | `deploy.sh` | `source /other/project/.env` | Source from `~/.env.common` |

**Verification:** Run existing `run_pipeline.py --dry-run` — should produce same output as before.

### Phase 3: Restructure Directory (Medium Risk)
*Move files to new structure. Old files become thin wrappers or are deleted.*

| Step | What | Risk | Notes |
|------|------|------|-------|
| 3.1 | Create `run_pipeline.py` as thin CLI wrapper for `pipeline.orchestrator` | Low | Wrap `run_pipeline.main()` |
| 3.2 | Create `run_threads.py` as thin wrapper | Low | Wrap `pipeline.threads.main()` |
| 3.3 | Create `pipeline/orchestrator.py` | Low | New file, no migration |
| 3.4 | Move `auto_news_selector.py` → `pipeline/steps/news_selector.py` | Medium | Update imports in other files |
| 3.5 | Move `auto_briefing.py` → `pipeline/steps/briefing.py` | Medium | Same |
| 3.6 | Move `auto_deep_article.py` → `pipeline/steps/deep_article.py` | Medium | Same |
| 3.7 | Move `auto_thumbnail.py` → `pipeline/steps/thumbnail.py` | Low | Standalone, no cross-imports |
| 3.8 | Move `auto_email_sender.py` → `pipeline/steps/email_sender.py` | Low | Standalone |
| 3.9 | Create `pipeline/steps/deploy.py` (Python, not bash) | Low | New file; deprecate `deploy.sh` |
| 3.10 | Move `threads/` files to `pipeline/threads/` | Medium | Update all imports |
| 3.11 | Remove `v3/` nesting — flatten to `pipeline/threads/` | Medium | Update all imports |

**Verification:** Run full pipeline in dry-run mode. Compare outputs with previous.

### Phase 4: Split Monoliths (High Risk)
*Break apart writer_v3.py and narrative_pitcher.py. Requires careful testing.*

| Step | What | Depends On |
|------|------|-----------|
| 4.1 | Extract `validate_cards()`, `validate_year()`, `validate_keywords()` from writer_v3 → `pipeline/threads/validator.py` | Phase 3 complete |
| 4.2 | Extract `fetch_article_body()`, link validation from writer_v3 → `pipeline/threads/crawler.py` | Phase 3 |
| 4.3 | Keep `write_thread()`, card assembly, format builders in `pipeline/threads/writer.py` | Phase 4.1, 4.2 |
| 4.4 | Extract pitch generation from narrative_pitcher → `pipeline/threads/pitch.py` | Phase 3 |
| 4.5 | Keep pitch evaluation in `pipeline/threads/pitch_evaluator.py` | Phase 4.4 |
| 4.6 | Remove dead `format_selector.py` | Phase 3 |

**Verification:** Run Threads pipeline with `--dry-run` — must produce same cards as before.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Instead |
|-------------|---------|---------|
| **Monolithic orchestrator with all step logic inline** | Single-file changes risk entire pipeline | Each step is a separate module with single responsibility |
| **Module-level side effects** | Importing a module triggers env I/O, breaks tests | Lazy loading: `load_env()` called once, cached via `@lru_cache` |
| **Bare `except:`** | Catches `KeyboardInterrupt`, `SystemExit` | Always `except Exception:` |
| **Cross-project environment dependency** | If other project moves/deleted, this breaks | All env loading within this project |
| **Greenfield rewrite** | Would take months, introduce new bugs | Strangler Fig: add infra, migrate file by file |
| **Over-abstraction** | Abstract base classes, factory patterns for 6 linear steps | Simple function with dataclass input/output |
| **Shared mutable state** | Step modifies global dict, next step depends on internal side effect | Explicit data contracts: each step receives + returns typed objects |
| **Filesystem as state** | JSON files grow unbounded, schema drift | Use D1 for persistent state; files only for artifacts |

---

## Scalability Considerations

| Concern | Current (N users/day) | After Refactoring | Notes |
|---------|----------------------|-------------------|-------|
| Pipeline run time | ~15-30 min | Same (bottleneck is LLM calls, not architecture) | Architecture change doesn't reduce API calls |
| Adding new steps | Modify orchestrator + add import | Register new step with `orchestrator.add_step()` | Lower barrier to add steps |
| Debugging failures | Search through log files | Per-step result objects with structured error data | Easier to identify failure point |
| Running on new machine | Sed-replace all PROJECT_DIR | `git clone && pip install` | Single env config |
| Testability | Near zero (module-level side effects) | All steps accept explicit config; env is lazily loaded | Mock D1 client, test in isolation |
| Multiple environments | Hardcoded to production | Change `.env` file; paths are computed from project root | Config-driven environments |

---

## Sources

- Codebase reverse-engineering of `scripts/run_pipeline.py`, `auto_news_selector.py`, `auto_briefing.py`, `auto_deep_article.py`, `auto_thumbnail.py`, `auto_email_sender.py`, `scripts/threads/db_reader.py`, `publisher.py`, `v3/writer_v3.py`, `v3/narrative_pitcher.py`, `v3/model_router.py` — HIGH confidence (direct file analysis)
- `CONCERNS.md` — HIGH confidence (same codebase audit)
- `ARCHITECTURE.md` (current) — HIGH confidence (existing documentation)
- Pipe & Filter pattern: [Data Pipeline Design Patterns](https://www.startdataengineering.com/post/code-patterns) — MEDIUM confidence (web source, aligns with codebase evidence)
- Strangler Fig pattern: Industry standard for incremental migration — HIGH confidence (well-established pattern)
- Config-driven development with Pydantic/dataclasses: [Best practices for configurations in Python-based pipelines](https://belux.micropole.com/blog/python/blog-best-practices-for-configurations-in-python-based-pipelines) — MEDIUM confidence
