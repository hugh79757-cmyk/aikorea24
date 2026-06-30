# Technology Stack: Python Pipeline Restructuring

**Project:** AI코리아24 (aikorea24.kr) — Python Pipeline Modularization
**Researched:** 2026-06-30

## Verdict: No New Dependencies

The recommended architecture requires **zero new external dependencies**. All infrastructure modules use Python 3.14 standard library:

| Module | Stdlib Packages Used | Why Not a Third-Party Lib |
|--------|--------------------|---------------------------|
| `config.py` | `pathlib`, `functools.lru_cache` | Path resolution is trivial; `python-dotenv` not needed (simple parser is 10 lines) |
| `env_loader.py` | `os`, `pathlib`, `functools.lru_cache`, `dataclasses` | lru_cache provides singleton caching with no dependency |
| `d1_client.py` | `subprocess`, `json`, `re`, `time` | Currently shells out to `npx wrangler`; refactoring to use Cloudflare API directly is FUTURE work |
| `logger.py` | `logging`, `datetime`, `pathlib` | Python's `logging` module with TimedRotatingFileHandler |
| `models.py` | `dataclasses`, `datetime` | Python 3.7+ dataclasses are cleaner than namedtuple |
| `retry.py` | `time`, `functools` | 15-line decorator; `tenacity` would be overkill |

## Existing Dependencies (Will Be Preserved)

### Core Pipeline

| Library | Version | Used In | Purpose |
|---------|---------|---------|---------|
| Python | 3.14 | All scripts | Pipeline runtime; already installed |
| requests | latest | auto_briefing, auto_thumbnail, threads | HTTP calls to MiMo API, Threads API, Brevo API |
| beautifulsoup4 | latest | auto_deep_article, writer_v3 | HTML parsing for article crawling |
| lxml | latest | writer_v3 | BeautifulSoup backend for HTML parsing |

### Threads Pipeline Only

| Library | Version | Used In | Purpose |
|---------|---------|---------|---------|
| openai | latest | model_router | OpenAI API calls (GPT-4o-mini) |
| schedule | latest | main_v3 (daemon mode) | 2-hour interval scheduling |
| urllib (stdlib) | — | db_reader, writer_v3 | URL validation, RSS source fallback |

## Infrastructure Choices

| Decision | Choice | Why Not Alternative |
|----------|--------|-------------------|
| Config format | `.env` + Python dataclasses | YAML (PyYAML dependency), TOML (tomllib in 3.11+, but adds learning curve). Current codebase already uses `.env` |
| D1 access method | `subprocess` + `npx wrangler d1 execute` (KEPT) | This is the current approach and it works. The Cloudflare API SDK (`cloudflare` package) would be cleaner but requires API token setup and changes all query patterns. Deferred to post-refactoring |
| Logging approach | Python `logging` module with `TimedRotatingFileHandler` | Current approach: `print()` with timestamps. Adding structured logging via stdlib is an improvement without new deps |
| Type system | `dataclasses` + inline type hints | No `pydantic` (adds dependency, overkill for this use case). No `attrs` (stdlib dataclasses suffice). Mypy/pyright for optional static analysis |
| Testing | `pytest` (already installed) | Already in `tests/conftest.py`. No change needed |

## Alternatives Explicitly Rejected

| Technology | Why Considered | Why Rejected |
|-----------|---------------|--------------|
| **Apache Airflow** | Popular pipeline orchestrator | Overkill for 6-step sequential pipeline running on local cron. Adds 500MB+ dependencies, requires a database, has a web UI we don't need |
| **Prefect** | Modern Pythonic orchestration | Same overkill. The pipeline has no complex dependencies, no retry policies beyond simple try/except, no need for a server |
| **Kedro** | Modular data pipeline framework | Designed for data science projects with catalog-based datasets. Our data flow is simpler (D1 ↔ API ↔ filesystem) |
| **Dagster** | Asset-based orchestration | Would require defining software-defined assets for every D1 table. Too much abstraction for this use case |
| **python-dotenv** | .env file loading | Our custom parser is 10 lines and handles `export` prefix and quoted values. Adding a dependency for this is unnecessary |
| **Click** | CLI framework | Current `argparse` usage is adequate for `--skip-*` flags. Click would be nice but not worth the churn |
| **Pydantic Settings** | Typed env loading | Adds `pydantic` dependency (~5MB). Our `EnvConfig` dataclass does the same thing with stdlib |
| **Rich** | Beautiful logging | Adds visual polish but introduces a dependency. Structured logging via stdlib is sufficient |
| **Typer** | Modern CLI | Same as Click — `argparse` is adequate and has zero dependencies |

## Installation

No changes to installation. Pipeline continues running in the existing `.venv`:

```bash
# No new packages needed
.venv/bin/pip list | grep -E "requests|beautifulsoup|lxml|openai|schedule|pytest"
```

## Sources

- Codebase analysis of `scripts/` (direct file review) — HIGH confidence
- Python 3.14 standard library documentation — HIGH confidence
- Cloudflare D1 wrangler CLI usage in 3 files — HIGH confidence
