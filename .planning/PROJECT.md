# AI코리아24 (aikorea24.kr)

## What This Is

Korean-language AI news curation and publishing platform. Aggregates news from 50+ RSS sources, generates daily AI-powered briefings and deep-dive articles, publishes to blog and social media (Threads/X), sends email newsletters, and hosts a community bulletin board. Built with Astro 5 SSR on Cloudflare Workers with a Python automation pipeline.

## Core Value

Reliable, automated Korean AI news publishing pipeline — from news collection to reader delivery — that runs without manual intervention.

## Requirements

### Validated

- ✓ RSS news aggregation with 2-pass impact scoring — existing
- ✓ AI-powered daily briefing generation (MiMo API) — existing
- ✓ Deep-dive blog article generation and publishing — existing
- ✓ OG thumbnail generation — existing
- ✓ Threads (X/Twitter) auto-publishing — existing
- ✓ Email newsletter subscription via Brevo — existing
- ✓ Daily briefing email dispatch — existing
- ✓ Google OAuth login with HMAC session — existing
- ✓ Community bulletin board (posts + comments) — existing
- ✓ Blog content management (545+ posts) — existing
- ✓ AI tools directory (119 entries) — existing
- ✓ AI glossary (55 terms) — existing
- ✓ AI chronicle/timeline — existing
- ✓ Network hub (RSS feed aggregation) — existing
- ✓ Site search functionality — existing
- ✓ Naver keyword search volume sync — existing
- ✓ SEO infrastructure (JSON-LD, sitemaps, RSS) — existing
- ✓ Google AdSense integration — existing
- ✓ Dark mode, responsive design — existing

### Active

- [ ] **SEC-01**: Full security audit — API key exposure in logs/source, env file consolidation, auth gap analysis
- [ ] **SEC-02**: Centralized secrets management (single `.env` loader, remove hardcoded keys)
- [ ] **REF-01**: Remove all hardcoded `PROJECT_DIR` paths across Python scripts
- [ ] **REF-02**: Consolidate duplicated `load_env()`, `d1_query()`, `load_posted()` into single modules
- [ ] **REF-03**: Remove dead code and backup files
- [ ] **REF-04**: Unify Python pipeline into modular structure with shared config
- [ ] **OBS-01**: Pipeline observability — structured logging, per-step timing, run history stored in D1
- [ ] **OBS-02**: CLI status command — `python -m pipeline status` for at-a-glance pipeline health
- [ ] **OBS-03**: Telegram alert on pipeline failure or missed schedule
- [ ] **THR-01**: Stabilize Threads auto-publishing pipeline
- [ ] **BRD-01**: Bulletin board management stability
- [ ] **INF-01**: Pipeline portability — allow clone-and-run on any machine

### Out of Scope

- Frontend UI redesign — not requested, existing design works
- Mobile app — web-first, no mobile plans
- Multi-language support beyond Korean — core audience is Korean
- New feature development beyond stabilization — focus is refactoring existing
- Web dashboard UI — deferred to separate dashboard project
- CI/CD server setup — pipeline runs locally via cron

## Context

Initial project built rapidly with significant technical debt. Python pipeline has massive single-file modules, hardcoded paths, duplicated utility functions, and fragile orchestration. The Astro frontend is relatively clean. This phase focuses on structural stabilization, security hardening, and making the pipeline observable and maintainable.

## Constraints

- **Budget**: Personal project — prefer free-tier services, avoid cost increases
- **Stack**: Cloudflare ecosystem (D1, R2, Workers) must be preserved
- **Language**: Korean content, Korean comments in code
- **Runtime**: Python 3.14 pipelines run locally via cron (launchd)
- **No downtime**: Existing deployment must remain functional during refactoring

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Security-first prioritization | User identified access control and key exposure as top concern | — Pending |
| Full rebuild of Python pipeline | Existing code too fragmented for incremental cleanup | — Pending |
| Preserve Astro/Cloudflare frontend | Relatively clean, lower priority for refactoring | — Pending |
| CLI status + Telegram alert instead of web dashboard | Already have separate dashboard project; don't expand scope | — Pending |

---

*Last updated: 2026-06-30 after adding observability requirements*
