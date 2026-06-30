# STRUCTURE.md

> Directory structure and organization analysis.
> Last updated: 2026-06-30
> Mapped by: gsd-codebase-mapper (arch focus)

## Overview

```
aikorea24/
├── src/                  # Astro frontend source (TypeScript + Astro components)
├── scripts/              # Python automation pipeline & utilities
├── public/               # Static assets (served as-is)
├── content/              # Root-level blog content (legacy/minimal)
├── config/               # External configuration (JSON)
├── tests/                # Python test suite (pytest)
├── sql/                  # Additional SQL schemas
├── docs/                 # Project documentation
├── dist/                 # Build output (gitignored)
├── node_modules/         # npm dependencies (gitignored)
├── .wrangler/            # Cloudflare Wrangler cache (gitignored)
├── .astro/               # Astro generated types (gitignored)
├── .venv/                # Python virtual environment (gitignored)
├── .planning/            # GSD codebase mapping output (planning documents)
├── package.json          # npm dependencies & scripts
├── astro.config.mjs      # Astro framework configuration
├── wrangler.toml         # Cloudflare Workers/Pages configuration
├── tsconfig.json         # TypeScript configuration
├── tailwind.config.mjs   # Tailwind CSS configuration
├── schema.sql            # D1 database schema (users, news, briefings, etc.)
├── tailwind.config.js    # Tailwind config (legacy fallback)
├── pytest.ini            # Pytest configuration
└── .gitignore            # Git ignore rules
```

## Directory Purposes

### `src/` — Frontend Source (Astro + TypeScript)
The main application source code. Organized into pages, layouts, components, content collections, libraries, and styles.

**Structure:**
```
src/
├── pages/                   # Route definitions (file-based routing)
│   ├── index.astro          # Homepage
│   ├── about.astro          # About page
│   ├── contact.astro        # Contact page
│   ├── pricing.astro        # Pricing/subscription page
│   ├── privacy.astro        # Privacy policy
│   ├── terms.astro          # Terms of service
│   ├── news.astro           # News page
│   ├── global.astro         # Global AI news page
│   ├── 404.astro            # Custom 404 page
│   ├── blog/                # Blog section
│   │   ├── [...page].astro  # Paginated blog list (SSG)
│   │   ├── [...id].astro    # Individual blog post (SSG)
│   │   ├── category/        # Category-filtered blog pages
│   │   └── _backup/         # Backup of older versions
│   ├── tools/               # AI tools directory
│   │   ├── index.astro      # Tool listing with categories
│   │   ├── [id].astro       # Individual tool page
│   │   ├── submit.astro     # Tool submission form
│   │   ├── task/            # Task-based tool search
│   │   ├── finder/          # Tool recommendation quiz
│   │   └── _backup/         # Backup of older versions
│   ├── glossary/            # AI terminology dictionary
│   │   ├── index.astro      # Glossary listing
│   │   └── [...id].astro    # Individual term page
│   ├── chronicle/           # AI history timeline
│   │   ├── index.astro      # Chronicle listing
│   │   └── [...id].astro    # Individual chronicle entry
│   ├── briefing/            # Daily AI news briefing
│   │   ├── index.astro      # Briefing archive
│   │   └── [date].astro     # Briefing by date
│   ├── community/           # Community board
│   │   ├── index.astro      # Post listing
│   │   ├── [id].astro       # Individual post + comments
│   │   ├── write.astro      # Post creation form
│   │   └── review.astro     # Post review (admin)
│   ├── network/             # RSS feed network hub
│   │   └── index.astro      # Network feed aggregator
│   ├── auth/                # Authentication pages
│   │   └── consent.astro    # OAuth consent
│   ├── admin/               # Admin dashboard
│   │   ├── index.astro      # Admin main
│   │   └── event.astro      # Event management
│   ├── event/               # Event pages
│   │   ├── index.astro      # Event listing
│   │   └── download.astro   # Event download
│   ├── payments/            # Payment pages
│   │   ├── success.astro    # Payment success
│   │   └── fail.astro       # Payment failure
│   ├── compare/             # Tool comparison
│   ├── aikeep24/            # AI Keep 24 sub-project
│   ├── keyword-guide/       # Keyword guide pages
│   ├── api/                 # REST API endpoints (TypeScript)
│   │   ├── search.ts        # Blog search index
│   │   ├── subscribe.ts     # Brevo email subscription
│   │   ├── auth/            # Authentication APIs
│   │   │   ├── login.ts     # Google OAuth redirect
│   │   │   ├── logout.ts    # Session clear
│   │   │   ├── kakao.ts     # Kakao OAuth (unused?)
│   │   │   └── callback/    # OAuth callbacks
│   │   │       ├── google.ts # Google token exchange
│   │   │       └── kakao.ts # Kakao token exchange
│   │   ├── news/            # News data APIs
│   │   │   ├── latest.ts    # Latest news (5 items)
│   │   │   ├── global.ts    # Global AI news
│   │   │   ├── policy.ts    # Policy news
│   │   │   ├── benefits.ts  # Benefits news
│   │   │   └── senior.ts    # Senior news
│   │   ├── briefing/        # Briefing CRUD APIs
│   │   │   ├── latest.ts    # Latest published briefing
│   │   │   ├── news.ts      # Briefing news items
│   │   │   ├── publish.ts   # Publish briefing
│   │   │   ├── update.ts    # Update briefing
│   │   │   ├── deepdive.ts  # Deep dive articles
│   │   │   └── send-email.ts# Email briefing
│   │   ├── network/         # Network feed APIs
│   │   │   ├── feeds.ts     # Get all feeds
│   │   │   └── refresh.ts   # Refresh feed cache
│   │   ├── posts/           # Community post APIs
│   │   │   └── index.ts     # Post CRUD
│   │   ├── tools/           # Tool APIs
│   │   │   └── vote.ts      # Tool voting
│   │   └── admin/           # Admin APIs
│   │       └── grant.ts     # Grant membership
│   ├── sitemap*.xml.ts      # Sitemap generation (8 files)
│   └── rss.xml.ts           # RSS feed generation
│
├── layouts/
│   └── Layout.astro         # Main layout (nav, footer, search, theme, auth)
│
├── components/
│   ├── SEOHead.astro        # Head metadata + JSON-LD structured data
│   └── home/                # Homepage section components
│       ├── HeroSection.astro
│       ├── BriefingSection.astro
│       ├── LatestBlog.astro
│       ├── LatestNews.astro
│       ├── CourseSection.astro
│       ├── ContentHub.astro
│       ├── SubProjects.astro
│       ├── OpenSourceBanner.astro
│       ├── SubscribeBanner.astro
│       ├── CtaSection.astro
│       ├── DonationBanner.astro
│       ├── WelfareSection.astro
│       ├── PolicyBriefing.astro
│       ├── GlobalNews.astro
│       └── GrantSection.astro
│
├── lib/
│   ├── auth.ts              # Session sign/verify, membership, plan definitions
│   └── sitemap.ts           # Sitemap XML builder utilities
│
├── config/
│   └── tasks.ts             # Task controlled vocabulary (TypeScript mirror of Python)
│
├── styles/
│   └── global.css           # Tailwind directives + CSS custom properties + dark mode
│
├── content/                 # Astro Content Collections (Markdown data)
│   ├── blog/                # 545+ blog posts (.md)
│   ├── tools/               # 119 tool entries (.md)
│   ├── glossary/            # 55 glossary terms (.md)
│   ├── chronicle/           # 47 chronicle entries (.md)
│   └── keywords/            # Keyword data (empty dir)
│
├── content.config.ts        # Collection schemas (Zod validation)
├── middleware.ts            # Request middleware (security + session init)
├── navigation.ts            # Legacy/partial navigation config (unused?)
├── env.d.ts                 # TypeScript env type declarations (D1, R2)
└── types.d.ts               # Shared TypeScript interfaces (legacy from starter)
```

### `scripts/` — Python Automation Pipeline
The automation engine that runs daily to produce content.

| File | Purpose |
|------|---------|
| `run_pipeline.py` | Orchestrator — sequential execution of all steps |
| `auto_news_selector.py` | RSS crawling + 2-pass cascade impact scoring |
| `auto_briefing.py` | Briefing generation via MiMo API + D1 write |
| `auto_deep_article.py` | Long-form deep-dive article generation |
| `auto_thumbnail.py` | Thumbnail image generation |
| `auto_email_sender.py` | Email dispatch via Brevo API |
| `keyword_updater.py` | Naver Search Ads API keyword sync |
| `outline_generator.py` | Article outline creation |
| `blog_draft_generator.py` | Blog draft generation |
| `task_config.py` | Task controlled vocabulary (shared with `src/config/tasks.ts`) |
| `tools_collector.py` | AI tool data collection |
| `briefing_scorer.py` | Scoring/scoring logic for news |
| `briefing_dedup.py` | Deduplication utilities |
| `crawl_test.py` | RSS crawl testing |
| `backfill_*.py` | Data backfill utilities |
| `fix_ph_urls.py` | URL fix utilities |
| `generate_thumbnails.py` | Standalone thumbnail generation |
| `dynamic_seed_generator.py` | Dynamic seed keyword generation |
| `deploy.sh` | Build + Cloudflare Pages deploy |
| `seeds.json` | Seed keywords for Naver search |
| `run_pipeline_with_notify.py` | Pipeline with notification wrapper |
| `test_*.py` / `test_*.sh` | Ad-hoc test scripts |

**Subdirectories:**
| Directory | Purpose |
|-----------|---------|
| `logs/` | Pipeline execution logs (`.log` files) |
| `threads/` | Thread/social media posting pipeline |
| `thread_topics/` | Topic/outline generation pipeline |
| `migrations/` | Data migration scripts |
| `outlines/` | Generated article outlines (per date) |

### `public/` — Static Assets
Served at root path (`/`), not processed by Astro.

| File/Dir | Purpose |
|----------|---------|
| `_redirects` | Cloudflare Pages redirect rules |
| `favicon.ico`, `favicon.svg`, `favicon.png` | Site favicons |
| `apple-touch-icon.png` | iOS home screen icon |
| `og-default.jpeg`, `og-default.png` | Default OG images |
| `OG-1.webp` | Open Graph image |
| `robots.txt` | Crawler instructions |
| `ads.txt` | Ad network authorization |
| `llms.txt` | LLM crawler instructions |
| `sitemap-index.xml` | Sitemap index (appears here after build) |
| `google19c9f22fef174123.html` | Google Search Console verification |
| `blog-thumbnails/` | Auto-generated blog thumbnail images |
| `images/` | General images |
| `icons/` | Icon set |
| `aikeep24-pro/` | Sub-project static files |

### `content/` — Root-Level Content
Legacy/blog content at root level. Contains a single `.md` file. The main content lives under `src/content/`.

### `config/` — External Configuration

| File | Purpose |
|------|---------|
| `crawlable_sources.json` | RSS source definitions (21 crawlable, 15 RSS-only) |
| `entity_tiers.json` | Entity importance tiers for news scoring |
| `impact_weights.json` | Impact scoring weights configuration |

### `sql/` — Database Schema Files

| File | Purpose |
|------|---------|
| `network_schema.sql` | Network feed tables (`network_feeds`, `network_cache`) + seed data (34 feeds) |
| `persona_migration.sql` | Persona-related schema migration |

### `tests/` — Python Test Suite

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures (sample weights, tiers, mock articles, D1 monkeypatch) |
| `fixtures/` | Test fixture data (JSON files) |
| `test_auto_news_selector_dry_run.py` | Tests for news selector |
| `test_briefing_scorer.py` | Tests for briefing scorer |
| `test_cascade_2pass.py` | Tests for 2-pass cascade scoring |

### Root Configuration Files

| File | Purpose |
|------|---------|
| `package.json` | npm dependencies (Astro, Tailwind, Cloudflare adapter, MDX, RSS, sitemap) |
| `astro.config.mjs` | Astro v5 config: SSR mode, Cloudflare adapter, Tailwind + MDX integrations |
| `wrangler.toml` | Cloudflare: D1 binding (`DB`), R2 binding (`R2`), Pages output dir |
| `tsconfig.json` | TypeScript strict mode, extends `astro/tsconfigs/strict` |
| `tailwind.config.mjs` | Tailwind CSS configuration |
| `schema.sql` | Main D1 schema: users, posts, comments, news, briefings, briefing_items |
| `pytest.ini` | Pytest configuration for Python tests |

## Naming Conventions

**Files:**
- **Astro components/pages:** `PascalCase.astro` (e.g., `HeroSection.astro`, `Layout.astro`) with some `kebab-case.astro` exceptions (e.g., `news.astro`)
- **API routes:** `kebab-case.ts` (e.g., `send-email.ts`, `subscribe.ts`)
- **Lib files:** `kebab-case.ts` (e.g., `auth.ts`, `sitemap.ts`)
- **Config files:** `kebab-case.ts` or `kebab-case.json` (e.g., `tasks.ts`, `crawlable_sources.json`)
- **Blog content:** Korean-slug style `.md` files (hyphen-separated Korean text, e.g., `ai-koding-dogu-bigyo.md`)
- **Python scripts:** `snake_case.py` (e.g., `auto_news_selector.py`, `run_pipeline.py`)

**Directories:**
- **All directories** use `kebab-case` (e.g., `blog/`, `glossary/`, `community/`, `thread_topics/`, `auto_briefing/`)
- Exception: `__pycache__/` (Python standard)

**Components:**
- Astro components use `PascalCase` for file names: `HeroSection.astro`, `SEOHead.astro`, `Layout.astro`

**Tests:**
- Python tests: `test_*.py` prefix convention (e.g., `test_auto_news_selector_dry_run.py`)

## Where to Add New Code

**New Page:**
- Route file: `src/pages/<section>/<page>.astro`
- Layout wrapper: `Layout.astro` import
- New content collection entry: `src/content/<collection>/<slug>.md`

**New API Endpoint:**
- File: `src/pages/api/<section>/<endpoint>.ts`
- Pattern: `export const GET: APIRoute = async ({ locals }) => { ... }`
- D1 access: `(locals as any).runtime.env.DB`

**New Homepage Section:**
- Component: `src/components/home/<Name>Section.astro`
- Import in `src/pages/index.astro`

**New Python Pipeline Step:**
- Script: `scripts/<name>.py`
- Import in `scripts/run_pipeline.py` as a new `step_*()` function

**New Automation:**
- Python scripts: `scripts/`
- Associated config: `config/` directory
- Logs: `scripts/logs/`

**New Tests:**
- Frontend: Not yet established (no frontend test framework)
- Python pipeline: `tests/test_<name>.py` with fixtures in `tests/fixtures/`

## Key Files Reference

| File | Purpose | Notes |
|------|---------|-------|
| `src/pages/index.astro` | Homepage — imports 12+ home section components, fetches briefing + blog data | Entry point for visitors |
| `src/layouts/Layout.astro` | Global shell with nav, footer, search, theme toggle, auth, ads | 346 lines, single largest template |
| `src/middleware.ts` | Security headers (CSP, HSTS), session init, request sanitization | Runs on every request |
| `src/content.config.ts` | Collection schemas for blog, tools, glossary, chronicle, keywords | Zod validation |
| `src/lib/auth.ts` | HMAC session token functions, membership plans, D1 user queries | No JWT dependency |
| `src/env.d.ts` | D1 + R2 type declarations | Must match `wrangler.toml` bindings |
| `schema.sql` | D1 tables: users, posts, comments, news, briefings, briefing_items | Source of truth for D1 schema |
| `wrangler.toml` | CF config: D1 binding `DB`, R2 binding `R2`, Pages output | Deployment config |
| `astro.config.mjs` | SSR mode, Cloudflare adapter, trailing slashes | Framework config |
| `scripts/run_pipeline.py` | Daily automation orchestrator (news → briefing → articles → thumbnails → email → deploy) | 335 lines |
| `scripts/auto_news_selector.py` | RSS crawling, 2-pass cascade scoring, D1 news insertion | 490 lines, most complex script |
| `scripts/auto_briefing.py` | MiMo API briefing generation, D1 write | 265 lines |
| `scripts/keyword_updater.py` | Naver keyword sync, grade/intent generation | 550 lines |
| `config/crawlable_sources.json` | 21 crawlable + 15 RSS-only sources for news | Pipeline data source config |
| `tests/conftest.py` | Pytest fixtures: mock articles, D1 monkeypatch, scoring weights | Test infrastructure |
| `public/_redirects` | Cloudflare Pages redirect rules | Static redirects |

---

*Structure analysis: 2026-06-30*
