# INTEGRATIONS.md

> External integrations and service dependencies of aikorea24.kr.
> Last updated: 2026-06-30
> Mapped by: gsd-codebase-mapper (tech focus)

## Overview

aikorea24.kr integrates with ~15 external services across AI/LLM APIs, news aggregation, authentication, email delivery, social media publishing, and monitoring. The most critical integrations are:

1. **Cloudflare ecosystem** (D1 database, R2 storage, Workers runtime)
2. **OpenAI** (GPT-4o-mini — primary AI model for content generation)
3. **Brevo** (email marketing — newsletter subscriptions and daily email delivery)
4. **Google & Kakao OAuth** (user authentication)
5. **50+ RSS feeds** (global and Korean news sources)

## Cloudflare Ecosystem

### Cloudflare D1 (Database)
- **Type:** SQLite-compatible serverless database
- **Purpose:** Primary data store — users, posts, comments, news, briefings, briefing_items, tools, access_grants
- **Access Pattern (Website):** D1 binding via `runtime.env.DB` in Astro API routes (`wrangler.toml` binding name: `DB`)
- **Access Pattern (Pipeline):** Shell subprocess executing `npx wrangler d1 execute aikorea24-db --remote --command <sql>`
- **Configuration:** `wrangler.toml` — `database_id: "bec650ce-f732-46bc-87c0-bd76ed17e42a"`
- **Schema:** Defined in `schema.sql` (8 tables), `sql/network_schema.sql`, `sql/persona_migration.sql`

### Cloudflare R2 (File Storage)
- **Type:** S3-compatible object storage
- **Purpose:** File storage (bucket `aikorea24-files`)
- **Access Pattern:** R2 binding via `runtime.env.R2`
- **Configuration:** `wrangler.toml` — `binding = "R2"`, `bucket_name = "aikorea24-files"`

### Cloudflare Workers / Pages
- **Purpose:** SSR hosting via `@astrojs/cloudflare` adapter (output mode `server`)
- **Deployment:** `wrangler pages deploy` via `scripts/deploy.sh`
- **Build output:** `./dist` directory

## AI / LLM Services

### OpenAI (GPT-4o-mini) — Primary AI Model
- **Purpose:** Content generation, Korean translation, article commenting, thread writing, metadata generation, blog drafts
- **Auth Method:** API key (`OPENAI_API_KEY` from `~/.env.common` or `.env`)
- **Models used:** `gpt-4o-mini` (primary), older GPT-4 models referenced in comments
- **SDK:** `openai>=1.30.0` (Python), `openai` npm package not used (website uses no AI at runtime)
- **Files:**
  - `scripts/threads/v3/model_router.py` — Main router, 1st priority
  - `api_test/news_collector.py` — Translation (`batch_translate`)
  - `scripts/blog_draft_generator.py` — Blog draft creation
  - `scripts/keyword_updater.py` — Keyword analysis
  - `scripts/dynamic_seed_generator.py` — Seed expansion
  - `scripts/thread_topics/thread_topic_finder.py` — Topic discovery
  - `scripts/thread_topics/outline_generator.py` — Outline generation
  - `scripts/tools_collector.py` — Tool metadata generation

### DeepSeek (V4 Flash) — Secondary AI Model
- **Purpose:** Fallback when OpenAI is unavailable
- **Auth Method:** API token (`DEEPSEEK_API_TOKEN`)
- **Base URL:** `https://api.deepseek.com/v1` (configurable via `DEEPSEEK_BASE_URL`)
- **Model:** `deepseek-v4-flash`
- **SDK:** OpenAI-compatible API (uses `openai` Python SDK with custom base URL)
- **Files:**
  - `scripts/threads/v3/model_router.py` — 2nd priority fallback
  - `scripts/tools_collector.py` — Tool metadata generation via OpenRouter (uses `deepseek/deepseek-v4-flash`)

### MiMo (v2.5) — Tertiary AI Model
- **Purpose:** Fallback when both OpenAI and DeepSeek are unavailable. Also used for comment generation in briefing pipeline.
- **Auth Method:** API key (`MIMO_API_KEY` from `~/.env.common`)
- **Base URL:** `https://api.xiaomimimo.com/v1`
- **Model:** `mimo-v2.5`
- **SDK:** OpenAI-compatible API (uses `openai` Python SDK with custom base URL)
- **Files:**
  - `scripts/auto_briefing.py` — Primary comment generation for briefings
  - `scripts/auto_deep_article.py` — Deep article generation
  - `scripts/threads/v3/model_router.py` — 3rd priority fallback

### OpenRouter (DeepSeek through OpenRouter)
- **Purpose:** Alternative API gateway used by `tools_collector.py` for DeepSeek access
- **Auth Method:** API key (`OPENROUTER_API_KEY`)
- **Base URL:** `https://openrouter.ai/api/v1`
- **Model:** `deepseek/deepseek-v4-flash`
- **File:** `scripts/tools_collector.py` (line 925-940)

## Authentication

### Google OAuth 2.0
- **Provider:** Google Identity Platform
- **Type:** OAuth 2.0 with OpenID Connect (`openid email profile` scopes)
- **Auth Endpoint:** `https://accounts.google.com/o/oauth2/v2/auth`
- **Token Endpoint:** `https://oauth2.googleapis.com/token`
- **User Info:** `https://www.googleapis.com/oauth2/v2/userinfo`
- **Configuration:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (Cloudflare secrets)
- **Callback:** `https://aikorea24.kr/api/auth/callback/google`
- **Files:**
  - `src/pages/api/auth/login.ts` — Redirect to Google login
  - `src/pages/api/auth/callback/google.ts` — Token exchange + session creation

### Kakao OAuth
- **Provider:** Kakao Identity Platform
- **Type:** OAuth 2.0
- **Auth Endpoint:** `https://kauth.kakao.com/oauth/authorize`
- **Token Endpoint:** `https://kauth.kakao.com/oauth/token`
- **User Info:** `https://kapi.kakao.com/v2/user/me`
- **Scopes:** `profile_nickname profile_image account_email`
- **Configuration:** `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET` (Cloudflare secrets)
- **Callback:** `https://aikorea24.kr/api/auth/callback/kakao`
- **Files:**
  - `src/pages/api/auth/kakao.ts` — Redirect to Kakao login
  - `src/pages/api/auth/callback/kakao.ts` — Token exchange + session creation

### Session Management
- **Method:** HMAC-SHA256 signed session tokens (custom implementation, no Passport or Auth.js)
- **Secret:** `SESSION_SECRET` environment variable
- **Cookie:** `session` — `httpOnly`, `secure` in production, `sameSite: lax`, 7-day expiry
- **File:** `src/lib/auth.ts`

## Email / Notification

### Brevo (formerly Sendinblue)
- **Purpose:** Newsletter subscription management + daily briefing email delivery
- **Auth Method:** API key (`BREVO_API_KEY` — Cloudflare secret)
- **API Base:** `https://api.brevo.com/v3`
- **Endpoints used:**
  - `POST /contacts` — Subscribe new email to list (`src/pages/api/subscribe.ts`)
  - `GET /contacts` — List subscribers with pagination (`src/pages/api/briefing/send-email.ts`)
  - `POST /smtp/email` — Send transactional email (`src/pages/api/briefing/send-email.ts`, `scripts/auto_email_sender.py`)
- **Sender:** `info@aikorea24.kr` (name: "AI코리아24")
- **List ID:** Configured via `BREVO_LIST_ID` (default: 2)
- **Delivery:** Batch sending (100 recipients per API call)
- **Files:**
  - `src/pages/api/subscribe.ts` — Public subscription endpoint
  - `src/pages/api/briefing/send-email.ts` — Admin-initiated email broadcast
  - `scripts/auto_email_sender.py` — Python-based email pipeline

### Telegram Bot
- **Purpose:** Pipeline status notifications, error alerts, publishing confirmations
- **Auth Method:** Bot token (`TELEGRAM_BOT_TOKEN`) + Chat ID (`TELEGRAM_CHAT_ID`)
- **API:** `https://api.telegram.org/bot{token}/sendMessage`
- **Format:** HTML parse mode
- **Usage across 8 scripts:**
  - `scripts/run_pipeline_with_notify.py` — Pipeline success/failure notifications
  - `scripts/blog_draft_generator.py` — Blog draft results
  - `scripts/keyword_updater.py` — Keyword update results
  - `scripts/dynamic_seed_generator.py` — Seed generation results
  - `scripts/tools_collector.py` — Tool collection results
  - `scripts/threads/main_v3.py` — Thread publishing status
  - `scripts/thread_topics/thread_topic_finder.py` — Topic discovery results
  - `scripts/thread_topics/outline_generator.py` — Outline generation results
  - `naver_blog/cookie_monitor.py` — Cookie expiry alerts

## News Aggregation (RSS / API)

### Global RSS Sources (50+ feeds)
Collected via `api_test/news_collector.py` and `config/crawlable_sources.json`:

**Major tech/AI publications:**
- TechCrunch AI, The Verge AI, Wired AI, Ars Technica AI, ZDNET AI
- MIT Technology Review, VentureBeat AI, The Decoder, MarkTechPost
- Google AI Blog, OpenAI Blog, GitHub Blog, HuggingFace Blog
- NVIDIA Newsroom, Nature ML

**General news with AI filtering:**
- BBC Technology, CNN Technology, CNBC Tech, NYT Technology
- Washington Post Technology, The Guardian AI, Financial Times AI
- Reuters (with Google News fallback), Bloomberg, Business Insider
- The Next Web, City AM, Axios, Politico EU, SCMP China Tech

**AI-specific feeds (relaxed filtering):**
- NYT AI Spotlight, The Guardian AI, Fast Company AI

**Additional sources (2026-06 additions):**
- Herald Scotland, Guardian US News, The National News, NL Times
- SEC Press Releases, Al Jazeera (via Google News), Anthropic News (via Google News)
- Memphis Flyer

**Korean sources (via RSS):**
- AI타임스, 전자신문, IT조선, 인공지능신문, 디지털투데이, GeekNews

### Naver Open API
- **Purpose:** Korean news search supplement
- **Auth Method:** `NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET` (from `.env`)
- **Endpoint:** `https://openapi.naver.com/v1/search/news.json`
- **Files:** `api_test/news_collector.py` (`fetch_naver`)

### Korean Government Data Portal (data.go.kr)
- **Purpose:** MSIT (Ministry of Science and ICT) press releases and business announcements
- **Auth Method:** `DATA_GO_KR_KEY` (Service Key)
- **Endpoints:**
  - `http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList` — Business announcements
  - `http://apis.data.go.kr/1721000/msitpressreleaseinfo/pressReleaseList` — Press releases
- **Files:** `api_test/news_collector.py` (`fetch_msit_announce`, `fetch_msit_press`)

### Bizinfo (기업마당) API
- **Purpose:** Small business AI grant/support program discovery
- **Auth Method:** `BIZINFO_API_KEY`
- **Endpoint:** `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do`
- **Files:** `api_test/news_collector.py` (`fetch_bizinfo_grants`)

### Hacker News (Algolia API)
- **Purpose:** AI-related Hacker News story discovery
- **Endpoint:** `https://hn.algolia.com/api/v1/search` — query `AI+artificial+intelligence`, tag `story`
- **Files:** `api_test/news_collector.py` (`fetch_hackernews_ai`)

### Google News RSS
- **Purpose:** Fallback URL discovery when primary links fail validation
- **Endpoint:** `https://news.google.com/rss/search?q={query}`
- **Files:** `api_test/news_collector.py` (`find_fallback_url`)

## Content Publishing

### Product Hunt RSS
- **Purpose:** AI tool discovery for the tools directory
- **Feed URL:** `https://www.producthunt.com/feed`
- **Filtering:** Title keyword matching (AI, GPT, LLM, etc.) + reject patterns
- **Files:** `scripts/tools_collector.py`

### HuggingFace Papers
- **Purpose:** AI research paper discovery
- **URL:** `https://huggingface.co/papers`
- **Files:** `scripts/tools_collector.py`

### Futurepedia / AIxploria / Toolpilot
- **Purpose:** Additional AI tool discovery sources
- **URLs:** Sitemap-based scraping from `futurepedia.io`, `aixploria.com`, `toolpilot.ai`
- **Files:** `scripts/tools_collector.py`

### Naver Blog (Playwright automation)
- **Purpose:** Automated blog post publishing to Naver Blog
- **Auth:** Cookie-based session (acquired via `login.py`, stored in `cookies.json`)
- **Blog ID:** `oksoon5705-`
- **Limits:** 3 posts/day maximum enforced
- **Method:** Requests-based API calls to `blog.naver.com` with session cookies
- **Files:**
  - `naver_blog/publish.py` — Core publishing logic
  - `naver_blog/auto_publish.py` — Daily scheduling with rate limiting
  - `naver_blog/publish_blog.py` — Blog post content formatting
  - `naver_blog/publish_briefing.py` — Briefing-to-blog format conversion
  - `naver_blog/login.py` — Credential login for cookie acquisition
  - `naver_blog/cookie_monitor.py` — Cookie health monitoring

### RSS Feeds (Outgoing)
The website generates multiple RSS feeds for content syndication:

| Feed | File |
|------|------|
| Main site RSS | `src/pages/rss.xml.ts` |
| Blog RSS | `src/pages/sitemap-blog.xml.ts` |
| Briefing RSS | `src/pages/sitemap-briefing.xml.ts` |
| Chronicle RSS | `src/pages/sitemap-chronicle.xml.ts` |
| Glossary RSS | `src/pages/sitemap-glossary.xml.ts` |
| Tools RSS | `src/pages/sitemap-tools.xml.ts` |
| Pages RSS | `src/pages/sitemap-pages.xml.ts` |

## Webhooks

- **Incoming:** None detected
- **Outgoing:** None detected (no webhook callbacks to external services)

## Environment Configuration

### Cloudflare Secrets (production, set via wrangler dashboard or CLI)
| Variable | Purpose | Used By |
|----------|---------|---------|
| `SESSION_SECRET` | HMAC session signing key | `src/lib/auth.ts` |
| `GOOGLE_CLIENT_ID` | Google OAuth client | `src/pages/api/auth/*.ts` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | `src/pages/api/auth/callback/google.ts` |
| `KAKAO_CLIENT_ID` | Kakao OAuth client | `src/pages/api/auth/*.ts` |
| `KAKAO_CLIENT_SECRET` | Kakao OAuth secret | `src/pages/api/auth/callback/kakao.ts` |
| `BREVO_API_KEY` | Brevo email API key | `src/pages/api/subscribe.ts`, `src/pages/api/briefing/send-email.ts` |
| `BREVO_LIST_ID` | Brevo mailing list ID | `src/pages/api/subscribe.ts` |

### Local/Environment Variables (Python pipelines)
Loaded from `~/.env.common`, `./.env`, or `api_test/.env.sh`:
| Variable | Purpose | Source |
|----------|---------|--------|
| `OPENAI_API_KEY` | OpenAI API access | `~/.env.common` |
| `MIMO_API_KEY` | MiMo API access | `~/.env.common` |
| `DEEPSEEK_API_TOKEN` | DeepSeek API access | `~/.env.common` |
| `NAVER_CLIENT_ID` | Naver Open API client | `.env` |
| `NAVER_CLIENT_SECRET` | Naver Open API secret | `.env` |
| `DATA_GO_KR_KEY` | Government data portal key | `.env` |
| `BIZINFO_API_KEY` | Bizinfo (기업마당) API key | `.env` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | `.env` |
| `TELEGRAM_CHAT_ID` | Telegram chat target | `.env` |
| `OPENROUTER_API_KEY` | OpenRouter API access | `.env` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API (deployment) | `/Users/twinssn/Projects/5000/.env` |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account (deployment) | `/Users/twinssn/Projects/5000/.env` |

## Integration Health & Reliability Notes

### Model Fallback Chain
The AI model system implements a cascade fallback: **OpenAI → DeepSeek → MiMo**. This is handled centrally in `scripts/threads/v3/model_router.py`. The briefing pipeline (`scripts/auto_briefing.py`) uses MiMo directly rather than through the router.

### RSS Feed Reliability
Multiple RSS feeds are known to be unstable:
- **403 Forbidden (permanent):** Financial Times AI, VentureBeat AI, Axios, NYT Technology, NL Times
- **404 Not Found:** AI타임스, 디지털투데이, OpenAI Blog, Ben's Bites, Interconnects AI
- **Parsing errors:** 전자신문, Nature ML
- **Connection timeout:** 인공지능신문

These failures are handled gracefully (logged, source skipped). The system has a Google News RSS fallback for Reuters.

### Brevo Email Reliability
- Batch sending with 100 recipients per API call
- No retry logic on individual batch failures
- No rate limiting detection
- All contacts fetched before sending (pagination up to max)

### Naver Blog Cookie Expiry
- Sessions expire periodically and require re-login via `login.py`
- `cookie_monitor.py` checks cookie health and sends Telegram alert on expiry

### API Key Management
- Keys loaded from multiple locations (`~/.env.common` → `.env` → `api_test/.env.sh`)
- `common_env_loader.py` provides fallback loading
- Cloudflare secrets set separately via dashboard/CLI (not in git)

---

*Integration audit: 2026-06-30*
