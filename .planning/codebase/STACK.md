# STACK.md

> Technology stack analysis of aikorea24.kr — an AI news curation platform.
> Last updated: 2026-06-30
> Mapped by: gsd-codebase-mapper (tech focus)

## Overview

aikorea24.kr is a Korean-language AI news curation and publishing platform. It uses **Astro 5** with **Cloudflare Workers** runtime (server-side rendered), a **Tailwind CSS** frontend, **Cloudflare D1** for structured data, and **Cloudflare R2** for file storage. Content pipelines run in **Python 3.14** with multiple AI model integrations (OpenAI, DeepSeek, MiMo) for content generation and translation.

The project has two distinct layers:
1. **Website** — Astro SSR on Cloudflare Workers with D1/R2 bindings
2. **Pipeline** — Python automation scripts (news collection, briefing generation, publishing)

## Languages

| Language   | Version   | Usage                              |
|------------|-----------|-------------------------------------|
| TypeScript | ~5.7      | Astro website, API routes, auth    |
| Python     | 3.14      | Pipeline scripts, news collection, content generation |
| Node.js    | 22.x (inferred) | Build tooling, wrangler CLI   |

## Runtime & Platform

- **Runtime:** Node.js (build/dev), Python 3.14 (pipelines), Cloudflare Workers (production)
- **Platform:** Cloudflare Pages + Workers (via `@astrojs/cloudflare` adapter)
- **Deployment:** Wrangler CLI via `scripts/deploy.sh`
- **Package Manager:** npm (with `package-lock.json`)

## Frameworks & Libraries

### Core Framework
- **Framework:** Astro 5.17.1
- **Adapter:** `@astrojs/cloudflare` 12.6.12 — SSR on Cloudflare Workers
- **Output mode:** `server` (server-side rendered)
- **Site URL:** `https://aikorea24.kr`

### Content & Data
- **Content collections:** Astro content API (`src/content/`) with Zod schema validation
  - Collections: `blog`, `tools`, `keywords`, `chronicle`, `glossary`
- **MDX:** `@astrojs/mdx` 4.3.13 for rich content pages
- **RSS:** `@astrojs/rss` 4.0.15 for blog/briefing/chronicle RSS feeds
- **Sitemap:** `@astrojs/sitemap` 3.7.0 with per-section sitemap generation

### UI / Styling
- **CSS Framework:** Tailwind CSS 3.4.19 (`@astrojs/tailwind` 6.0.2)
- **Typography:** `@tailwindcss/typography` 0.5.19 (prose styling)
- **Font:** Pretendard Variable (Korean system font stack)
- **Dark mode:** `class`-based dark mode via `darkMode: 'class'`

### Backend / API
- **Cloudflare Runtime:** `@astrojs/cloudflare` provides `Runtime<Env>` with `DB` (D1) and `R2` bindings
- **Auth:** Custom HMAC-SHA256 session tokens (`src/lib/auth.ts`) — no external auth SDK
- **API Routing:** Astro file-based API routes (`src/pages/api/**/*.ts`)

### Database
- **Primary:** Cloudflare D1 (SQLite-compatible, `wrangler.toml` binding `DB`)
- **File Storage:** Cloudflare R2 (`wrangler.toml` binding `R2`, bucket `aikorea24-files`)

### Scripting / AI
- **OpenAI SDK:** `openai>=1.30.0` (Python) — GPT-4o-mini for content generation, translation
- **Alternate models:** DeepSeek V4 Flash (fallback), MiMo v2.5 (tertiary fallback)
- **Scraping:** `beautifulsoup4`, `requests`, `feedparser`, `Pillow` for image processing
- **Web automation:** `playwright` for Naver blog auto-publishing

### Testing
- **Python tests:** pytest (`pytest.ini` configured with `testpaths = tests`)
- **Markers:** `unit` (no external services), `integration` (needs D1/network)

## Configuration Files

| File | Purpose |
|------|---------|
| `package.json` | Node.js dependencies and scripts |
| `astro.config.mjs` | Astro framework configuration (adapter, integrations, output mode) |
| `wrangler.toml` | Cloudflare Workers config (D1, R2 bindings, build output) |
| `tsconfig.json` | TypeScript config (extends `astro/tsconfigs/strict`) |
| `tailwind.config.mjs` | Tailwind CSS configuration (content paths, fonts, dark mode) |
| `pytest.ini` | Python test configuration |
| `config/crawlable_sources.json` | RSS feed sources classified by crawlability |
| `config/entity_tiers.json` | Entity impact tier definitions for scoring |
| `config/impact_weights.json` | Weight configuration for article scoring |
| `scripts/task_config.py` | Controlled vocabulary for AI tool tasks (40 task types) |
| `schema.sql` | Main database schema (users, posts, comments, news, briefings) |
| `sql/network_schema.sql` | Network/relationship schema extension |
| `sql/persona_migration.sql` | Persona feature migration |

## Dependencies

### Production dependencies (Node.js — `package.json`)

| Package | Version | Purpose |
|---------|---------|---------|
| `astro` | ^5.17.1 | Static site generator / SSR framework |
| `@astrojs/cloudflare` | ^12.6.12 | Cloudflare Workers adapter |
| `@astrojs/mdx` | ^4.3.13 | MDX content support |
| `@astrojs/rss` | ^4.0.15 | RSS feed generation |
| `@astrojs/sitemap` | ^3.7.0 | Sitemap generation |
| `@astrojs/tailwind` | ^6.0.2 | Tailwind CSS integration |
| `tailwindcss` | ^3.4.19 | Utility CSS framework |
| `@tailwindcss/typography` | ^0.5.19 | Prose styling |

### Python dependencies (pipelines)

**`api_test/requirements.txt`** (news collection pipeline):
- `requests>=2.31.0` — HTTP client for API calls and RSS fetching
- `pytrends>=4.9.0` — Google Trends data
- `openai>=1.30.0` — OpenAI API client (GPT-4o-mini)
- `beautifulsoup4>=4.12.0` — HTML parsing
- `Pillow>=10.0.0` — Image processing
- `python-dotenv>=1.0.0` — Environment variable loading

**`naver_blog/requirements.txt`** (blog publishing):
- `requests` — HTTP client
- `playwright` — Browser automation for Naver blog

### Environment variable dependencies (not read from files)

Keys loaded from `~/.env.common`, `.env`, or `api_test/.env.sh`:
- `OPENAI_API_KEY` — OpenAI API
- `MIMO_API_KEY` — MiMo API (xiaomimimo.com)
- `DEEPSEEK_API_TOKEN` — DeepSeek API
- `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — Naver Open API
- `DATA_GO_KR_KEY` — Korean government data portal
- `BIZINFO_API_KEY` — Bizinfo (기업마당) API
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Telegram bot
- `BREVO_API_KEY` / `BREVO_LIST_ID` — Brevo email (Cloudflare secrets)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Google OAuth (Cloudflare secrets)
- `KAKAO_CLIENT_ID` / `KAKAO_CLIENT_SECRET` — Kakao OAuth (Cloudflare secrets)
- `SESSION_SECRET` — HMAC session signing (Cloudflare secrets)
- `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` — Deployment

## Build & Deploy

- **Build command:** `npm run build` — runs `astro build` then patches `_routes.json`
- **Deploy command:** `npm run deploy` — runs `bash scripts/deploy.sh`
- **Deploy process:**
  1. Build: `astro build` → outputs to `./dist`
  2. Post-build: Node script patches `dist/_routes.json` to include blog/chronicle routes in Worker
  3. Deploy: `wrangler pages deploy dist --project-name aikorea24 --branch main --commit-dirty=true`
- **CI/CD:** Manual deployment via `scripts/deploy.sh` (no automated CI pipeline detected)

## Scripts

### npm scripts (`package.json`)

| Command | Purpose |
|---------|---------|
| `npm run dev` | Start Astro dev server |
| `npm run build` | Production build with route patching |
| `npm run preview` | Preview production build |
| `npm run astro` | Direct Astro CLI access |
| `npm run deploy` | Full build + deploy pipeline |

### Python pipeline scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `run_pipeline.py` | Orchestrator: news → briefing → deep articles → thumbnails → email → deploy |
| `run_pipeline_with_notify.py` | Same as above + Telegram notifications on completion/failure |
| `news_collector.py` (in `api_test/`) | RSS/API news collection from 50+ global + Korean sources |
| `auto_news_selector.py` | 2-pass impact scoring for article selection |
| `auto_briefing.py` | Briefing generation with MiMo AI comments |
| `auto_deep_article.py` | Deep article generation from news items |
| `auto_thumbnail.py` | og:image extraction and thumbnail generation |
| `auto_email_sender.py` | Brevo email sending for daily briefing |
| `tools_collector.py` | AI tool discovery (Product Hunt RSS, Futurepedia, HuggingFace) |
| `blog_draft_generator.py` | Blog post draft generation with OpenAI |
| `dynamic_seed_generator.py` | Keyword seed expansion for content strategy |
| `keyword_updater.py` | Keyword performance tracking and updating |
| `threads/main_v3.py` | Threads (Twitter-style) narrative generation pipeline |
| `threads/v3/model_router.py` | AI model routing (OpenAI → DeepSeek → MiMo fallback chain) |
| `thread_topics/thread_topic_finder.py` | Thread topic discovery from news clusters |
| `thread_topics/outline_generator.py` | Outline generation for thread topics |

### Naver Blog publishing scripts (`naver_blog/`)

| Script | Purpose |
|--------|---------|
| `auto_publish.py` | Daily 3-post auto-publishing with rate limiting |
| `publish.py` | Naver blog post publish via requests |
| `publish_blog.py` | Blog post HTML generation |
| `publish_briefing.py` | Briefing-to-blog-format conversion |
| `login.py` | Naver login session management |
| `cookie_monitor.py` | Cookie expiry monitoring + Telegram alerts |
| `login.py` | Naver credential-based login for cookie acquisition |

---

*Stack analysis: 2026-06-30*
