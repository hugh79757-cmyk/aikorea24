# ARCHITECTURE.md

> Architecture analysis of AI코리아24 (aikorea24.kr).
> Last updated: 2026-06-30
> Mapped by: gsd-codebase-mapper (arch focus)

## Overview

AI코리아24 is a Korean-language AI news curation, tool discovery, and educational portal. It follows a **server-rendered hybrid architecture** combining static content collections with dynamic API endpoints backed by Cloudflare D1 (SQLite). The site presents AI news briefings, tool reviews, a glossary, a chronicle/timeline, community features, and an RSS-driven network hub — all served via Cloudflare Pages with an Astro SSR adapter.

The project has two distinct subsystems:
1. **Frontend Web App** (Astro v5 + Tailwind CSS) — the public website
2. **Python Automation Pipeline** — daily cron-driven workflows for news selection, briefing generation, article writing, thumbnail creation, and email dispatch

## Architectural Pattern

- **Pattern:** Hybrid SSR + Static Generation
- **Rendering:** `output: 'server'` (SSR) via `@astrojs/cloudflare`; blog/chronicle/tools/glossary content collections use `export const prerender = true` for per-route static generation at build time. API routes (`/api/`) always render dynamically.
- **Key characteristic:** Content-driven site with two-tier data — local Markdown files (blog posts, tools, glossary, chronicle) in `src/content/` for static pages, and Cloudflare D1 (SQLite) for dynamic data (news, briefings, users, community posts, network feeds). Python automation scripts bridge external news sources into D1, then generate content into `src/content/blog/`.

## System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                  Presentation Layer (Astro SSR)              │
│  Layouts → Pages → Components (`.astro` files)              │
│  `src/layouts/Layout.astro`  `src/pages/`  `src/components/`│
├─────────────────────────────────────────────────────────────┤
│                  API Layer (Astro API Routes)                │
│  `src/pages/api/*.ts` — REST endpoints for dynamic data      │
│  Middleware: `src/middleware.ts` (security + session init)   │
├──────────────────────┬──────────────────────────────────────┤
│   Content Layer      │    Data Access Layer (D1)            │
│  (Astro Collections) │  Cloudflare D1 SQLite via wrangler   │
│  `src/content/`      │  Tables: users, news, briefings,     │
│  blog/ tools/        │  briefing_items, posts, comments,    │
│  glossary/ chronicle/│  network_feeds, network_cache        │
│  keywords/           │                                      │
├──────────────────────┴──────────────────────────────────────┤
│                  Infrastructure Layer                        │
│  Cloudflare Pages + Workers + D1 + R2                       │
│  `wrangler.toml`, `astro.config.mjs`, `scripts/deploy.sh`    │
└─────────────────────────────────────────────────────────────┘
```

### 1. Presentation Layer — `src/`

- **Location:** `src/layouts/Layout.astro` — main layout with dark mode, search modal, nav, footer, Google AdSense, share button
- **Pages:** `src/pages/` — 35+ Astro pages organized by section (blog, tools, glossary, chronicle, community, admin, network, briefing, event, auth, etc.)
- **Components:** `src/components/home/` — 18 home page sections (HeroSection, BriefingSection, LatestBlog, CourseSection, etc.)
- **Routing:** Astro file-based routing; Blog uses `[...page].astro` for pagination and `[...id].astro` for detail pages (both pre-rendered). API routes use `.ts` ends.

### 2. API Layer — `src/pages/api/`

- **Location:** `src/pages/api/`
- **Auth APIs:** `auth/login.ts`, `auth/logout.ts`, `auth/kakao.ts`, `auth/callback/google.ts` — Google OAuth 2.0 with custom HMAC session signing
- **News APIs:** `news/latest.ts`, `news/global.ts`, `news/policy.ts`, `news/benefits.ts`, `news/senior.ts` — D1-backed news queries
- **Briefing APIs:** `briefing/latest.ts`, `briefing/news.ts`, `briefing/publish.ts`, `briefing/update.ts`, `briefing/deepdive.ts`, `briefing/send-email.ts` — briefing CRUD + email dispatch
- **Utility APIs:** `search.ts` (blog search index), `subscribe.ts` (Brevo email subscription), `network/feeds.ts`, `network/refresh.ts`, `tools/vote.ts`, `admin/grant.ts`, `posts/index.ts`

### 3. Data Access Layer — Cloudflare D1

- **Location:** `wrangler.toml` (binding `DB`), `schema.sql`, `sql/network_schema.sql`
- **Tables:** `users`, `posts`, `comments`, `news`, `briefings`, `briefing_items`, `network_feeds`, `network_cache`
- **Access patterns:** D1 bound to Astro runtime via `context.locals.runtime.env.DB`. Python scripts use `wrangler d1 execute` CLI or Cloudflare API for D1 access.

### 4. Content Layer — Astro Collections

- **Location:** `src/content.config.ts`, `src/content/`
- **Collections:** blog (545+ MD files), tools (119 MD files), glossary (55 MD files), chronicle (47 MD files), keywords (0 files)
- **Schema:** Zod-validated frontmatter per collection type

### 5. Automation Pipeline Layer — Python

- **Location:** `scripts/`
- **Key scripts:**
  - `run_pipeline.py` — orchestrator that runs the daily news pipeline
  - `auto_news_selector.py` — 2-pass impact scoring, RSS crawling, D1 news ingestion
  - `auto_briefing.py` — generates briefing text using MiMo API, writes to D1
  - `auto_deep_article.py` — generates deep-dive blog posts → writes MD to `src/content/blog/`
  - `auto_thumbnail.py` — generates thumbnail images
  - `auto_email_sender.py` — sends briefing emails via Brevo API
  - `keyword_updater.py` — Naver search volume sync, keyword grade/intent generation
  - `outline_generator.py` (in `scripts/thread_topics/`) — generates article outlines
  - `blog_draft_generator.py` — blog draft creation
  - `deploy.sh` — build + wrangler pages deploy

## Data Flow

### Primary Request Path (Visitor browsing)

```
Browser → Cloudflare Pages → Astro SSR Worker
  ├─ Static pre-rendered route? → Serve cached HTML from CF edge
  └─ Dynamic route?
       ├─ API route (/api/*) → D1 query → JSON response
       └─ SSR page (e.g. /network/) → locals.runtime.env.DB → D1 → render HTML
```

### Daily Pipeline Data Flow

```
External RSS feeds (21+ sources)
  → `auto_news_selector.py` crawls & scores (2-pass cascade)
  → D1 `news` table (inserted)
  → `auto_briefing.py` selects top articles, generates commentary via MiMo API
  → D1 `briefings` + `briefing_items` tables (inserted)
  → `auto_deep_article.py` generates long-form posts via MiMo API
  → `src/content/blog/` (new .md files written)
  → `auto_thumbnail.py` generates OG images
  → `public/blog-thumbnails/` (image files written)
  → `auto_email_sender.py` sends email via Brevo API
  → `scripts/deploy.sh` → `npm run build` → `wrangler pages deploy`
```

### Auth Data Flow

```
User clicks "로그인"
  → `/api/auth/login/` → redirects to Google OAuth
  → Google auth callback → `/api/auth/callback/google/`
  → Exchange code for token → fetch userinfo
  → D1: INSERT OR IGNORE into users
  → `signSession()` creates HMAC-signed JWT-like token
  → Cookie `session` set (httpOnly, 7-day expiry)
  → Redirect to `/`
  → Middleware `src/middleware.ts` reads SESSION_SECRET from env
  → `Layout.astro` verifies session cookie on every page
```

## Key Abstractions

### Layout Component (`Layout.astro`)
- **Location:** `src/layouts/Layout.astro`
- **Purpose:** Global shell with nav, footer, dark mode, search modal, Google AdSense, share button, session-based auth UI
- **Used by:** Every `.astro` page via `<Layout title={...}>` wrapping
- **Props:** `title`, `description`, `image`, `type`, `publishedDate`, `modifiedDate`, `tags`, `category`, `noindex`

### SEOHead Component
- **Location:** `src/components/SEOHead.astro`
- **Purpose:** Generates all `<head>` metadata — Open Graph, Twitter cards, JSON-LD structured data (WebSite, Organization, BlogPosting, BreadcrumbList), Google Analytics, sitemap link
- **Used by:** `Layout.astro`

### Astro Content Collections
- **Location:** `src/content.config.ts`
- **Purpose:** Five Zod-validated content collections (blog, tools, glossary, chronicle, keywords) loaded from local `.md` files via `glob()` loader
- **Used by:** Static pages (`/blog/`, `/tools/`, `/glossary/`, `/chronicle/`) for render-time data; API route `src/pages/api/search.ts` for search index

### Session Auth (`lib/auth.ts`)
- **Location:** `src/lib/auth.ts`
- **Purpose:** HMAC-SHA256 session signing/verification, D1 membership queries, subscription plan definitions
- **Used by:** Layout.astro (session verification), API routes (auth checks)

### D1 Database Runtime Binding
- **Location:** `src/env.d.ts` (type `Env { DB: D1Database; R2: R2Bucket }`)
- **Purpose:** Type-safe D1 access via `(Astro.locals as any).runtime.env.DB`
- **Used by:** All API routes, SSR pages with dynamic data (`/network/`, `/briefing/`, `/community/`)

### Pipeline Orchestrator (`run_pipeline.py`)
- **Location:** `scripts/run_pipeline.py`
- **Purpose:** Sequential execution of news selection → briefing → deep articles → thumbnails → email → deploy
- **Features:** Skip flags (`--skip-news`, `--skip-briefing`, etc.), date param, dry-run mode, per-step error handling

## Entry Points

| Entry Point | Purpose | File |
|-------------|---------|------|
| Homepage | Main landing with briefing, hero, blog posts, courses | `src/pages/index.astro` |
| Blog List | Paginated blog index (static, SSG) | `src/pages/blog/[...page].astro` |
| Blog Post | Individual article with related posts | `src/pages/blog/[...id].astro` |
| Tools Directory | AI tool catalog with category filters | `src/pages/tools/index.astro` |
| Tool Detail | Individual tool page | `src/pages/tools/[id].astro` |
| Glossary | AI term dictionary (55 terms) | `src/pages/glossary/index.astro` |
| Glossary Detail | Term detail page | `src/pages/glossary/[...id].astro` |
| AI Chronicle | Timeline of AI events | `src/pages/chronicle/index.astro` |
| Briefing | Daily AI news briefing | `src/pages/briefing/[date].astro` |
| Community | Community board (CRUD) | `src/pages/community/index.astro` |
| Network Hub | RSS feed aggregation portal | `src/pages/network/index.astro` |
| API: Search | Blog search index (JSON) | `src/pages/api/search.ts` |
| API: Briefing | News briefing JSON endpoint | `src/pages/api/briefing/latest.ts` |
| API: News Latest | Latest 5 news items | `src/pages/api/news/latest.ts` |
| API: Subscribe | Brevo email subscription | `src/pages/api/subscribe.ts` |
| API: Auth Login | Google OAuth initiation | `src/pages/api/auth/login.ts` |
| API: Auth Callback | Google OAuth token exchange | `src/pages/api/auth/callback/google.ts` |
| Middleware | Security headers + session init | `src/middleware.ts` |

## Module Boundaries

### Frontend Modules (Astro)

| Module | Boundaries | Depends On |
|--------|-----------|------------|
| `pages/` | Route definitions, page-level data fetching | `layouts/`, `components/`, `lib/` |
| `layouts/` | Shared page shells | `components/`, `lib/` |
| `components/` | Reusable UI sections | None (leaf nodes) |
| `lib/` | Utility functions (auth, sitemap) | None |
| `config/` | Controlled vocabularies (tasks) | None |
| `content/` | Markdown data files | None |
| `styles/` | Global CSS (Tailwind + custom themes) | None |

### Automation Modules (Python)

| Module | Boundaries | Depends On |
|--------|-----------|------------|
| `run_pipeline.py` | Orchestration | All `auto_*` scripts |
| `auto_news_selector.py` | RSS crawling + scoring | D1, `config/crawlable_sources.json`, `config/entity_tiers.json`, `config/impact_weights.json` |
| `auto_briefing.py` | Briefing generation + D1 write | MiMo API, `auto_news_selector` |
| `auto_deep_article.py` | Long-form article generation | MiMo API, D1 |
| `auto_thumbnail.py` | Thumbnail image generation | D1, image API |
| `auto_email_sender.py` | Email dispatch | Brevo API |
| `keyword_updater.py` | Naver keyword sync | Naver Search Ads API, D1 |
| `task_config.py` | Task controlled vocabulary | None (shared with `src/config/tasks.ts`) |
| `blog_draft_generator.py` | Draft post creation | MiMo API |
| `outline_generator.py` | Article outline creation | D1 news data |
| `deploy.sh` | Build + deploy | npm, wrangler |

## Routing

- **Framework:** Astro file-based routing under `src/pages/`
- **SSR mode:** `output: 'server'` in `astro.config.mjs` means all routes go through the Cloudflare Worker
- **Static routes:** Blog list (`[...page].astro`), blog detail (`[...id].astro`), tools, glossary, chronicle use `export const prerender = true` for static generation at build time
- **Dynamic routes:** API routes (`/api/*`), network hub (`/network/`), community pages render on each request
- **Trailing slashes:** `trailingSlash: 'always'` — all URLs end with `/`
- **Middleware:** `src/middleware.ts` runs on every request — sets security headers (CSP, HSTS, X-Frame-Options), validates session secret, handles trailing dash redirects, blocks malicious patterns
- **Sitemaps:** Multi-sitemap architecture (`sitemap.xml.ts` as index, separate sitemaps for blog, briefing, chronicle, glossary, tools, pages)

## State Management

- **No client-side state library** (no React/Vue state management)
- **Server state:** D1 database for dynamic content (news, briefings, users, community posts)
- **Session state:** HMAC-signed cookie (`session`) containing user email/name/avatar
- **Content state:** Local Markdown files in `src/content/` — read-only at runtime, written by automation scripts pre-deploy
- **Client state:** Minimal — `localStorage` for theme preference (`dark`/`light`), `sessionStorage` for blog scroll position
- **Search state:** Client-side fetch of `/api/search/` → in-memory filter on user input

## Error Handling Strategy

- **API routes:** Try/catch blocks in each route handler, returning `{ error: "message" }` JSON with appropriate HTTP status codes
- **Page routes:** Try/catch for D1 operations in SSR pages (e.g., `src/pages/index.astro` briefing fetch), fallback to null/empty state
- **Middleware:** Returns 410 Gone for malicious paths, 301 redirect for trailing dashes
- **Auth:** `verifySession()` returns `null` on any failure (invalid HMAC, expired, malformed)
- **Pipeline:** Python scripts log to `scripts/*.log` files; `run_pipeline.py` catches exceptions per step and continues
- **No centralized error handler** — each route/file handles its own errors independently

## Cross-Cutting Concerns

**Logging:**
- Frontend: `console.log`, `console.warn` in middleware and API routes
- Pipeline: Python `print()` with timestamps → log files in `scripts/logs/`

**Validation:**
- Content collections: Zod schemas in `src/content.config.ts`
- API inputs: Manual checks (e.g., email format in `subscribe.ts`)
- No shared validation library

**Authentication:**
- Google OAuth 2.0 (OpenID Connect) for login
- Custom HMAC-SHA256 session tokens (no JWT library)
- Session stored in httpOnly cookie, verified on every page load
- Membership levels (`free`, `basic`, `premium`) in D1 `users` table

**SEO:**
- Per-page meta tags via `SEOHead.astro`
- JSON-LD structured data (WebSite, Organization, BlogPosting, BreadcrumbList)
- Multi-sitemap XML generation
- RSS feed at `/rss.xml`
- Google Analytics (G-MMCZ9G2YZ6)
- Google AdSense integration
- Naver site verification
- `robots.txt`, `ads.txt`, `llms.txt`

**CI/CD:**
- No CI server — deploy triggered manually via `bash scripts/deploy.sh`
- Deploy script: `npm run build` → `wrangler pages deploy dist --project-name aikorea24 --branch main`
- Pipeline runs locally via cron (managed by launchd or similar)

---

*Architecture analysis: 2026-06-30*
