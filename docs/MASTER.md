# GapFeed - Master Architecture & Decisions
_Last updated: 2026-03-29 20:30 CET_

This is the single source of truth for all design decisions, data architecture, and operational logic.
Update this document whenever something changes. If it's not here, it doesn't exist.

---

## 0. Rebrand (2026-03-29)

**GapFeed rebranded to GapFeed on 2026-03-29.**

- Old domain: `gapfeed.com` (now redirects to gapfeed.com)
- New domain: `gapfeed.com` (.com, .it, .info, .srl all acquired)
- All 213 HTML files rebranded: GapFeed -> GapFeed, gapfeed.com -> gapfeed.com
- All agent configs updated to gapfeed.com
- Shared modules (`remote_db.py`, `llm_client.py`) updated
- Agent_7 now monitors `gapfeed.com/api/db.php` instead of `gapfeed.com`
- Agent_5 API endpoint updated to gapfeed.com
- Sitemap, robots.txt, all canonical URLs updated
- Email: `hello@gapfeed.com` (privacy/terms pages)
- DNS: A record points to 217.160.0.71, MX via IONOS
- SPF: `v=spf1 include:_spf-eu.ionos.com ~all`
- SSL: Active on gapfeed.com (IONOS managed)
- IONOS folder: `/gapfeed.com/` (renamed from `/gapfeed.com/`)

**Redirect chain:**
- `gapfeed.com` -> `gapfeed.com` (301 redirect, set up in IONOS)
- `gapfeed.info/it/srl` -> `gapfeed.com` (redirect)
- `gapfeed.com/srl/store` -> `gapfeed.com` (redirect)

---

## 1. Product Vision

**GapFeed = Market Gap Discovery Feed**

Not search, not social listening. Scans the internet 24/7, clusters signals into gaps (unsolved problems).
"Product Hunt, but for problems instead of products."

- **Free only** - no login, no paywall, no pricing tiers
- Revenue model: behavioral intent data farming (searches, clicks, exploration patterns)
- SEO play: every gap gets a permanent, indexable page
- Future consideration: premium features (alerts, API access, deeper analysis) but not planned yet

---

## 2. Design System (FINAL - Arc Theme)

### Colors
```css
--bg: #111113;
--text: #ededf0;
--text-2: #a0a0a8;
--text-3: #606068;
--accent: #4f9cf7;        /* Arc blue */
--accent-dim: #4f9cf715;
--accent-border: #4f9cf730;
--green: #4ade80;
--green-dim: #4ade8015;
--border: rgba(255,255,255,0.06);
--border-top: rgba(255,255,255,0.1);
```

### Typography
- **Headings:** `font-family: 'Outfit', sans-serif` - weight 600, tracking -0.01em
- **Body:** `font-family: 'DM Sans', sans-serif` - size 14.5px, tracking 0
- **Gap title:** 28px
- **Section heading:** 15px
- **Nav item:** 13px
- **Nav label:** 11px, weight 500
- **Logo:** `gapFeed` - lowercase, "Feed" in accent color, `font-weight: 700`
- Old: Previous branding (deprecated)
- **Fonts:** Self-hosted (Outfit + DM Sans + Inter for gap pages, woff2 format)
- **Gap pages:** Inter font (self-hosted, removed Google CDN)
- Old: "Self-host fonts later for Lighthouse optimization" -> DONE

### Layout
- **Sidebar:** 240px fixed left, full height
- **Content:** `max-width: 780px; margin: 0 auto` (gap detail pages)
- **Content:** `max-width: 1000px; margin: 0 auto` (feed/graphs pages)
- **Topbar:** 48px sticky, centered content
- **Mobile:** sidebar hidden below 768px, hamburger toggle

### Tags (Color-coded)
- **Category tags:** accent blue (`--accent`), used for gap categories
- **Source tags:** green (`--green`), used for source attribution
- **Signal count tags:** grey (`--text-3`), shows evidence count
- **Trend tags:** green (rising), amber (stable), red (cold) - based on heat_score

### Feed Pagination
- 10 gaps per page with arrow navigation
- Page selector buttons at bottom
- Time filters: All / Trending / This Week / This Month

### Loading States
- Skeleton placeholders with shimmer animation
- CSS keyframe animation: `background-position` sweep
- Applied to: feed items, stat cards, charts, sidebar items

### Category Grouping
- Categories are dynamic, derived from gaps in the database (not hardcoded)
- Sidebar shows categories with signal counts, click to filter
- Categories auto-populate based on what the agents discover
- Current categories depend on which verticals are active (general, immigration, etc.)
- Click category to filter feed

### Sparklines in Feed
- Each gap has a mini sparkline showing heat_score trend
- Green line = rising (heat >= 0.7)
- Amber line = stable (heat 0.3-0.7)
- Red line = declining (heat < 0.3)
- Inline SVG, 50x20px

### Card Style (NO backdrop-filter)
```css
border: 1px solid var(--border);
border-top-color: var(--border-top);
border-radius: 14px;
background: rgba(255,255,255,0.025);
box-shadow: 0 1px 3px rgba(0,0,0,0.25), 0 4px 12px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.05);
```

### Search Bar
- Collapsed: 160px, shows "Search gaps..." + ⌘K
- Expanded: 380px, smooth cubic-bezier transition, accent glow border
- `⌘K` to open, `Esc` to close, click away to collapse

### Em Dashes
- NEVER use em dashes (-) or en dashes (–) anywhere in user-facing content
- Regular hyphens (-) only
- This applies to: HTML, SEO meta, JSON-LD, generated pages

---

## 3. Page Architecture

| Page Type | URL Pattern | Content Width | Notes |
|-----------|------------|---------------|-------|
| Feed | `/` | 1000px | Gap list with pagination, sparklines, time filters |
| Graphs | `#graphs` | 1000px | Live intelligence: stats, charts, sentiment, uptime |
| Gap Detail | `/gap/{slug}.html` | 780px | Static HTML, sidebar, SEO-optimized, canonical URL |
| About | `/about.html` | 780px | Static HTML, dark theme, sidebar nav |
| Privacy | `/privacy.html` | 780px | Static HTML, contact: hello@gapfeed.com |
| Terms | `/terms.html` | 780px | Static HTML, contact: hello@gapfeed.com |

### Page Navigation
- Main feed is SPA (index.html)
- Gap detail pages are static HTML (generated from DB data, separate files)
- About/Privacy/Terms are static HTML with sidebar navigation
- Feed gap links use real `<a href="/gap/{slug}.html">` (crawlable by Google)
- `.htaccess` enables clean URLs (removes .html extension)

### Feed Tabs
- **All** - all gaps sorted by evidence count
- **Trending** - gaps with heat_score >= 0.5, sorted by momentum
- **This Week** - gaps created in last 7 days
- **This Month** - gaps created in last 30 days

### Sidebar Navigation
- **Top:** Feed, Graphs
- **Categories:** Dynamic groups with colored dots, click to filter
- **Sources:** Dynamic list with signal counts, click to filter
- **Bottom:** About, Privacy, Terms
- Active state: `rgba(255,255,255,0.08)` background

### Search
- Real-time filtering as you type
- Shows top 8 matching gaps in dropdown
- Searches title, description, category
- `Cmd+K` / `Ctrl+K` to open, `Esc` to close

### SEO
- Title: "GapFeed - Market Gap Intelligence"
- Meta description: includes "what to build next", "unsolved problems", "market gaps"
- Meta keywords: "what should I build, what to build with AI, startup ideas"
- OG tags for social sharing (og-image.png, 1200x630)
- Twitter cards (summary_large_image)
- Canonical URL: https://gapfeed.com/
- Robots meta: index, follow
- Google Analytics: G-FXVLBGRXX8
- Schema.org JSON-LD: WebSite + Organization + WebApplication (main page)
- Schema.org per gap: TechArticle + BreadcrumbList + FAQPage
- Sitemap: 103+ URLs (99 gap + about + privacy + terms + feed)
- Gap pages are static HTML with sidebar, centered at 780px
- Real `<a href>` links from feed to gap pages (Google crawlable)
- `.htaccess` for clean URL rewriting
- Internal links: 8 related gaps per page
- FAQ sections for Google rich snippets
- Social sharing buttons on gap pages (X, LinkedIn)
- Google Search Console: submitted (Dario)
- Bing Webmaster: pending (issues with service)

---

## 4. Database Schema

### MySQL (IONOS - Primary)

**signals** (26 columns)
| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| source | VARCHAR | Platform (reddit, hn, ddg, etc.) |
| source_url | VARCHAR | Original URL |
| platform_id | VARCHAR | Unique platform ID for dedup |
| subreddit | VARCHAR | Reddit subreddit name |
| author | VARCHAR | Original author |
| title | VARCHAR | Signal title |
| content | TEXT | Full signal content |
| created_at | DATETIME | When signal was posted |
| collected_at | DATETIME | When we collected it |
| vertical | VARCHAR | Business vertical |
| product_category | VARCHAR | Product area classification (e.g. "ecommerce_shopify") |
| pain_category | VARCHAR | Pain type (account_issues, payment_problems, etc.) |
| signal_type | VARCHAR | question, complaint, request |
| location | VARCHAR | Geographic signal |
| urgency_score | DECIMAL | 0-1 urgency rating |
| specificity_score | DECIMAL | 0-1 specificity rating |
| buyer_intent | DECIMAL | 0-1 willingness to pay |
| quality_tier | VARCHAR | Signal quality: gold, silver, bronze, noise |
| sentiment | VARCHAR | positive, negative, neutral |
| competitor_mentions | JSON | Competitor names extracted by Maya |
| metadata | JSON | Business size, profile info |
| gap_id | INT | FK to gaps table (assigned during gap detection) |
| category | VARCHAR | Gap category (from pain_category at link time) |
| is_processed | INT | 0/1 processed flag |
| synthesized | INT | 0/1 synthesis flag |

**gaps** (17 columns)
| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| title | VARCHAR | Gap title |
| slug | VARCHAR | URL slug |
| description | TEXT | Gap description (LLM-generated, evidence-based) |
| evidence_count | INT | Number of supporting signals |
| heat_score | DECIMAL | 0-1 popularity/urgency |
| category | VARCHAR | Gap category |
| source_types | JSON | Which sources contributed |
| signal_ids | JSON | Linked signal IDs |
| sample_quotes | JSON | Actual user quotes with {text, source, url} |
| competitors | JSON | Competitor intelligence: failed_tools, substitutes, why_now, top_competitors, top_substitutes, who_is_affected, context_confidence |
| gap_validity | VARCHAR | unvalidated, validated, saturated, wide_open |
| opportunity_score | DECIMAL | GapFeed opportunity score (demand / threat) |
| last_validated_at | DATETIME | Last competitor validation run |
| status | VARCHAR | active, stale, solved, archived |
| created_at | DATETIME | First detected |
| updated_at | DATETIME | Last updated |

**scan_log** - source scan history (timestamps, signals found/new)

**analytics** - daily aggregation tables (see section 6)

### Competitor Intelligence Pipeline (Phase 1 - 2026-03-29)

The gap description rewrite system uses a three-layer architecture to produce evidence-based gap descriptions without external API calls.

**Architecture:**
```
signals (Maya classified)
  ↓
mention_resolver.py (normalize raw mentions to canonical entities)
  ↓
cluster_context_builder.py (aggregate per cluster: competitors, substitutes, pain phrases)
  ↓
gap_detector.py (send structured evidence to LLM, receive structured gap)
  ↓
MySQL gaps.competitors (JSON field)
```

**Key principle:** Competitors are a stored feature of the signal/cluster graph, not a live lookup. No DDG, no web searches, no rate limits.

**1. Mention Resolver (`src/engines/mention_resolver.py`)**
- 100+ alias mappings for common SaaS tools, platforms, substitutes
- Three data sources: `product_category` (e.g. "ecommerce_shopify"), `competitor_mentions` (JSON array), content scanning
- Resolves to canonical entities: Shopify, PayPal, Stripe, etc.
- Classifies entity types: competitor, substitute, platform, tool
- Current coverage: 68% of gold signals have at least one resolved mention
- Example: "ecommerce_shopify" → ("Shopify", "competitor"), "using Excel" → ("Spreadsheets", "substitute")

**2. Cluster Context Builder (`src/engines/cluster_context_builder.py`)**
- Aggregates resolved mentions across a signal cluster (grouped by pain_category)
- Produces structured context object:
  - `competitors`: top named tools with mention_count, author_count, negative_rate, sample_pain_phrases
  - `substitutes`: workarounds people use (spreadsheets, manual work, email, WhatsApp)
  - `pain_phrases`: representative user complaints (ranked by urgency)
  - `who_is_affected`: extracted personas (freelancers, ecommerce merchants, developers, etc.)
  - `money_mentions` and `time_mentions`: extracted from signal text
  - `confidence`: 0-1 score based on data richness
- Formats into LLM-readable evidence block (replaces raw signal dump)

**3. Gap Detector (rewired 2026-03-29)**
- Builds cluster context BEFORE calling LLM (replaces DDG dependency)
- LLM prompt now requires structured output: `failed_tools`, `substitutes`, `why_now`
- Rule: "ONLY use competitor names from provided evidence. Do not invent names."
- If no named competitors: frames gap around substitutes (Excel, manual work, etc.)
- Stores full competitor data in `gaps.competitors` JSON column
- No external API calls. Pipeline never blocks on rate limits.

**Gap Description Format (enforced by prompt):**
1. WHO is affected and WHAT the specific pain is (with numbers)
2. WHICH tools they use and WHY those fail (named from evidence)
3. WHAT they resort to instead (substitutes)
4. WHY NOW (trend, behavior shift, market change)

**What changed from old pipeline:**
- Before: Gap detector called DDG for competitor lookup → rate limited → pipeline blocked
- After: All evidence comes from Maya's extracted data, pre-aggregated per cluster
- Substitutes (Excel, manual work, WhatsApp) now captured as first-class competitor data
- Gap descriptions are grounded in real user signals, not LLM hallucination

### SQLite (Local Backup)
- `data/signals.db` - local backup, agents still use this as fallback

---

## 5. The Squad (Agents)

All agents live in `TheRealAgents/{Agent Name}/` with the same structure:
```
{Agent Name}/
  config/base.json    # Agent configuration
  launch.py           # Entry point
  app/
    orchestrator.py   # Main state machine loop
    adapters/         # Source integrations
    classifier/       # LLM classification (Maya only)
    pipeline/         # Processing pipeline
    models/           # Data models
    monitors/         # Health checks (Sam only)
    synthesizer/      # Brief generation (Jamie only)
  logs/               # Runtime logs
  memory/             # Agent memory/state
  state/              # Cursors, checkpoints
```

### Per-Agent LLM Configuration
Each agent uses a model that fits its job. Shared fallback chain via `shared/llm_client.py`:
```
Primary → Fallback (auto-switch on rate limit)
```

| Agent | Primary Model | Fallback | Why |
|-------|--------------|----------|-----|
| **Agent_6** | `openai/gpt-oss-120b` | - | 50+ classifications/cycle, need 1k tok/s speed |
| **Agent_5** | `deepseek/deepseek-v3.2` | `xiaomi/mimo-v2-flash` | Creative writing, quality matters |
| **Agent_1** | `xiaomi/mimo-v2-flash` | - | Default, good enough for signal enrichment |
| **Agent_2** | `xiaomi/mimo-v2-flash` | - | Default, same as Alex |
| **Agent_7** | `xiaomi/mimo-v2-flash` | - | Default, health checks don't need premium |
| **Agent_4** | `xiaomi/mimo-v2-flash` | - | Default, on-demand briefs |
| **Shared default** | `xiaomi/mimo-v2-flash` | `google/gemini-2.5-flash-lite` | Auto-fallback for all agents |
| **Gap descriptions** | `google/gemini-3-flash-preview` | - | Dedicated: best quality/cost for gap writing |

**Note:** Maya uses a completely different model for speed. Luna uses a different model for quality. Everyone else shares the same default.

### Agent_1 - Scout
- **Role:** Discovers pain signals from 12 sources in parallel
- **Model:** `xiaomi/mimo-v2-flash`
- **Cycle:** 1s sleep between rounds, up to 1500 raw signals/round, 15 LLM calls/round

**State Machine:**
```
LOAD_STATE → READ → PLAN → SCOUT → NORMALIZE → VALIDATE → DEDUP
  → CORRELATE → ENRICH → STORE → LEDGER → REFLECT → SCHEDULE_NEXT → IDLE
```

**Sources (all in parallel via ThreadPoolExecutor):**
1. **Reddit** - 60+ subreddits, pain-focused queries, cursor-based pagination
2. **Web Search** - DuckDuckGo, 165 pain queries in 10 categories, rotating user agents (8 UAs), proxy support ready
3. **Hacker News** - HN Algolia API, searches for complaints/requests
4. **RSS Feeds** - parses RSS from tech blogs, forums
5. **Stack Overflow** - searches for frustration patterns, tag rotation
6. **Dev.to** - searches developer blog posts for pain signals
7. **YouTube** - quota-managed (8k/10k daily limit), 3 queries/cycle, auto-stop at quota
8. **Indie Hackers** - browser adapter via Agent_2 (Playwright), homepage/forum/products
9. **GitHub Issues** - 58 pain queries, GitHub API with token auth
10. **Google News** - RSS feeds, 52 pain queries, free
11. **GitHub Discussions** - GraphQL API, 42 pain queries
12. **Product Hunt** - Atom/RSS feeds, 15 categories, free

**Total: ~317 unique pain queries across all sources**

**Intelligent PLAN Phase (NEW):**
- Pulls trending topics from HN + RSS every round
- **QueryGenerator** (`app/query_generator.py`) - LLM generates 20 dynamic queries combining trends with pain patterns
- Uses `xiaomi/mimo-v2-flash` (tested vs deepseek-v3.2, mimo wins on speed: 3s vs 12s)
- 1-hour cache, fallback to random pain seeds if LLM fails
- Dynamic queries passed to web search adapter via `search_with_queries()` method

**Query Performance Ledger (NEW):**
- **QueryLedger** (`app/query_ledger.py`) - Tracks per-query: runs, signals, high-relevance, gaps created
- Decay factor (30-day half-life) - old winners lose weight
- Gaps created = +10 score points (the goal)
- Weighted sampling biases toward proven winners
- Every round Alex gets smarter

**Cross-Source Correlation (NEW):**
- **correlate_cross_source()** in `pipeline/dedupe.py`
- Groups signals by content similarity (first 200 chars)
- If same pain on 2+ sources within 48h: 2x urgency boost
- If same pain on 3+ sources: 3x urgency boost
- Runs after DEDUP, before ENRICH
- Modifies signals in-place with cross_source metadata

**Anti-Detection:**
- DDG: 8 rotating user agents, rotates every 5 requests
- HN: Human-like headers
- Reddit: Token auth
- All: Rate limiting, random delays, cursor dedup

**Pipeline (per signal):**
- **Normalize** - clean text, extract metadata, deduplicate internal fields
- **Validate** - check minimum quality (text length, relevance)
- **Dedup** - SimHash-based deduplication to avoid duplicate signals
- **Correlate** - cross-source urgency boost (2-3x when same pain on multiple sources)
- **Enrich** - LLM-based enrichment: extract pain category, urgency, specificity
- **Compliance** - filter out PII, profanity, spam
- **Store** - write to MySQL via RemoteDB, log to scan_log
- **Ledger** - record query outcomes for performance tracking
- **Reflect** - generate round summary, update source stats

**Key Features:**
- Lazy component initialization (only loads adapters that are enabled)
- Cursor files per source (remembers where it left off)
- Dedup checker with SimHash for near-duplicate detection
- Compliance filter for PII/profanity
- Memory review to detect staleness and adjust strategy
- Query performance ledger with decay (30-day half-life)
- Dynamic query generation from trending topics
- Cross-source correlation amplifier

### Agent_6 - Classifier + Gap Detector
- **Role:** Classifies raw signals and detects market gaps
- **Model:** `openai/gpt-oss-120b` (switched from xiaomi/mimo-v2-flash for better score distribution)
- **Cycle:** 30s sleep, batch size 20 fetch, 7 signals per LLM call, 50 max LLM calls/cycle, 3 parallel batches

**State Machine:**
```
LOAD_STATE → FETCH_SIGNALS → PRE_CLASSIFY → LLM_CLASSIFY → SCORE → WRITE_BACK → GAP_DETECT → SLEEP
```

**Classification Pipeline:**
1. **Fetch** - pull 20 unprocessed signals from MySQL (min 50 chars text)
2. **Pre-Classify** - rule-based filtering:
   - Detect noise (spam, off-topic, too short) - catches ~65% of signals
   - Extract product mentions, pain keywords
   - Pre-score urgency, specificity, buyer_intent (rule-based)
   - Separate noise from needs-LLM
3. **LLM Classify** - batch classification with parallel processing:
   - Batch size: 7 signals per LLM call (sweet spot from testing)
   - Parallel: 3 concurrent batches via ThreadPoolExecutor
   - Budget: each signal counts against max_llm_calls (not each batch)
   - Model: `openai/gpt-oss-120b` (tested against qwen3-235b, qwen-turbo, glm-4.7-flash)
   - Pain category, urgency (0-1), specificity (0-1), buyer intent (0-1), sentiment, signal type
   - Varied score distribution (urgency 0.2-0.9, intent high/medium/low mix)
4. **Score** - confidence scoring (compares LLM output to pre-classification rules)
5. **Write Back** - push classifications to MySQL signals table

**Model Testing (2026-03-27):**
| Model | Time (10 signals) | Urgency Range | Intent Spread | Verdict |
|-------|------------------|---------------|---------------|---------|
| gpt-oss-120b | 13.5s | 0.2-0.9 | balanced | Winner |
| qwen3-235b | 8.1s | 0.65-0.95 | mostly high | Fast but biased |
| qwen-turbo | 5.3s | 0.3-0.9 | skewed high | Good for pre-filter |
| qwen3.5-flash | 27.1s | 0.2-0.9 | balanced | Too slow |
| glm-4.7-flash | 40.8s | FAILED | FAILED | Dead |

**Throughput:**
- 20 signals per 30s cycle
- Pre-filter catches ~65% as noise
- ~35% need LLM classification
- 3 parallel batches = ~21 signals classified simultaneously
- Estimated: 2,400-4,000 signals/hour (up from ~50/hour before)

**Gap Detection (runs every 3 cycles, rewired 2026-03-29):**
- Clusters signals by pain_category (pre-clustering)
- Builds cluster market context via `cluster_context_builder.py`:
  - Resolves competitor/product mentions via `mention_resolver.py`
  - Aggregates: top competitors, substitutes, pain phrases, affected personas
  - Computes confidence score based on data richness
- Sends structured evidence to LLM (replaces raw signal dump)
- LLM prompt enforces: only use competitor names from evidence, name substitutes, explain why now
- Creates/updates gaps table with:
  - title, slug, description (evidence-based, names specific tools)
  - evidence_count (number of supporting signals)
  - heat_score (aggregate urgency + buyer intent)
  - sample_quotes (actual user words with source URLs)
  - competitors JSON (failed_tools, substitutes, why_now, top_competitors, top_substitutes, who_is_affected, context_confidence)
- Page Generator runs after gap detection (generates static HTML, sitemap, deploys to IONOS)
- No external API calls (DDG removed from pipeline)

**Known Issue (FIXED):** LLM was scoring all signals as urgency=1.0, sentiment=negative. Fixed with few-shot examples. Current distribution: urgency avg 0.42 (range 0.1-0.9), sentiment 74% negative / 24% neutral / 2% positive. Two PHP bugs also fixed: empty(0) is_processed filter, Maya reprocessing loop.

### Agent_4 - Brief Synthesizer
- **Role:** Generates analytical briefs on demand
- **Model:** Configurable (typically `xiaomi/mimo-v2-flash`)
- **Mode:** ON-DEMAND only (not continuous)

**Flow:**
```
FETCH_SIGNALS(query, vertical, max_signals) → GENERATE_BRIEF → RETURN
```

**Synthesis:**
1. Fetch signals matching query from MySQL
2. Group by pain category
3. Extract top complaints (max 10)
4. Extract top wants/needs (max 10)
5. Generate summary (LLM)
6. Return structured brief with signal_count, quotes, categories

**Usage:** `python orchestrator.py "search query" --vertical general --no-llm`

### Agent_7 - System Monitor
- **Role:** Health checks, diagnostics, and alerts
- **Model:** `xiaomi/mimo-v2-flash` (switched from gpt-oss-120b for consistency)
- **Cycle:** 300s (5 min) between checks

**State Machine:**
```
CHECK_AGENTS → CHECK_SERVER → CHECK_DB → CHECK_SYSTEM → DIAGNOSE → REPORT → NOTIFY → SLEEP
```

**Monitors:**
1. **Agents** - checks if Agent_1 and Agent_6 are running (log freshness within 15 min)
2. **Server** - pings `https://gapfeed.com/api/db.php?action=stats` with API key (15s timeout)
3. **Database** - pings PHP API for connectivity
4. **System** - disk space, process count

**Telegram Notification (NOTIFY step):**
- Sends via Telegram Bot API on critical alerts only
- 15-minute cooldown between notifications (no spam)
- Format: alert timestamp + issues list + LLM diagnosis
- Bot token: `${TELEGRAM_BOT_TOKEN}` (env var)
- Dario chat ID: `${TELEGRAM_CHAT_ID}` (env var)
- Config: `config/base.json` -> telegram section

**LLM Diagnosis:** When alerts fire, Sam uses LLM to analyze and suggest fixes. Provides root cause, fix recommendation, and urgency.

**Reporting:** Writes JSON reports to `memory/` and state to `state/`. Alerts logged as warnings.

### Agent_2 - Browser Scout (UNDER RECONSTRUCTION)
- **Role:** Browser-based signal discovery (stealth Playwright)
- **Model:** `xiaomi/mimo-v2-flash`
- **Status:** UNDER RECONSTRUCTION as of 2026-03-29

**Known issues (2026-03-29):**
- DDG, Google, and Brave Search all block headless browsers with captchas
- Browser-based search approach is non-viable for high volume
- Playwright/Chromium processes leak memory (2+ GB per instance)
- Current code is a mix of old browser adapters and new API scraper
- Jack was temporarily disabled due to memory leaks

**What was tried:**
1. Browser-based web search (DDG, Google, Brave) - all blocked by captchas
2. High-volume API scraper (Reddit JSON, HN Firebase, Dev.to REST) - duplicates Alex
3. Query bank (300+ queries) - useless without working search engine

**Decision pending:** Jack's role needs redefinition. Options:
- Kill Jack, expand Alex's sources
- Jack = content deep-dive (visits URLs from Alex's signals)
- Jack = niche site specialist (Product Hunt, Indie Hackers via browser)
- Jack = LLM classifier (enriches Alex's raw signals)

**Same state machine as Agent_1** but uses Playwright browser adapters instead of API adapters.

**Browser Adapters (same sources as Alex, browser-rendered):**
- `browser_reddit_adapter.py` - navigates Reddit, scrolls, extracts posts
- `browser_hn_adapter.py` - navigates HN, extracts stories
- `browser_stackoverflow_adapter.py` - searches SO for pain patterns
- `browser_devto_adapter.py` - scrapes Dev.to blog posts
- `browser_web_search_adapter.py` - uses DuckDuckGo via browser
- `browser_youtube_adapter.py` - searches YouTube via browser
- `rss_adapter.py` - shared RSS parser (non-browser)

**Stealth Specs:**
- Random 2-8s delays between requests
- Human-like typing (20-80ms per character)
- Smooth scrolling (variable speed)
- Hidden `navigator.webdriver`
- Cookie acceptance automation (tries `button:has-text("OK")`)
- Captcha detection (log and skip, no solving)
- Shared browser instance across adapters (lazy init)
- Clean shutdown on SIGTERM/SIGINT (closes browser)

**Why Browser Instead of API:**
- Reddit API has rate limits and requires auth
- Some sources don't have clean APIs
- Browser can access content behind JS rendering
- Stealth techniques avoid basic bot detection

### Agent_5 - Marketing & Community Manager
- **Role:** Manages blog, social media, trend scouting, and community engagement
- **Model:** `deepseek/deepseek-v3.2` (primary), `xiaomi/mimo-v2-flash` (fallback)
- **Cycle:** 3600s (1 hour) between cycles, 14400s (4 hours) for trend scouting

**Location:** `TheRealAgents/Agent_5/`

**State Machine (v3 - 2026-03-29):**
```
SCOUT_TRENDS → SYNC_PERFORMANCE → ANALYZE_DATA → PLAN_CONTENT → CREATE_CONTENT
  → CREATE_DRAFTS → CHECK_ENGAGEMENT → LEARN
```

**State Machine Details:**

**Modules (10 files in app/):**
- `main.py` - Entry point, loads config, starts orchestrator
- `orchestrator.py` - Main state machine with 8 states
- `social_manager.py` - Typefully API v2 integration (create/update/delete/schedule drafts)
- `analytics.py` - GapFeed API stats + engagement tracking
- `trend_scout.py` - Reddit/HN/X/LI trending topic detection
- `content_engine.py` - LLM content generation (X posts, threads, LinkedIn, blog outlines)
- `blog_manager.py` - Blog post creation + SFTP deploy to IONOS
- `memory.py` - Long-term learning (audience insights, content log, trends, blog log)
- `performance_tracker.py` - Manual feedback loop for published post analytics (Typefully v2 has no analytics API)
- `callback_handler.py` - Telegram callback handler for blog/social draft approvals
- `__init__.py` - Package initialization

**State Machine Details:**

1. **SCOUT_TRENDS** - Creates TrendScout, scans Reddit/HN/X/LI for trending topics, saves to `memory/trends.json`
2. **SYNC_PERFORMANCE** - Syncs published posts from Typefully, runs PerformanceTracker for feedback analysis
3. **ANALYZE_DATA** - Creates Analytics, pulls GapFeed stats (signal count, gap count), gets top posts from memory, injects performance recommendations
4. **PLAN_CONTENT** - Uses LLM to analyze trends + data + performance insights, decides content type (x_post, x_thread, linkedin_post, blog_post), topic, style
5. **CREATE_CONTENT** - Creates ContentEngine, generates content based on plan, validates output (no em dashes, question ending, length limits). For blog_post: saves outline to pending_approval.json + sends Telegram notification
6. **CREATE_DRAFTS** - Creates SocialManager, checks T+1 available slots on Typefully, creates drafts for approval, sends Telegram notifications. T+1 only scheduling.
7. **CHECK_ENGAGEMENT** - Creates Analytics + MemoryManager, gets top performing posts, generates engagement summary
8. **LEARN** - Creates MemoryManager, archives posts older than 30 days, gets audience insights, saves all memory files

**LLM Configuration:**
- Primary: `deepseek/deepseek-v3.2` (best creative writing quality)
- Fallback: `xiaomi/mimo-v2-flash` (auto-fallback via shared LLM client)
- Max tokens: 2000, Temperature: 0.7
- Uses shared `llm_client.py` for all LLM calls with auto-fallback

**Content Validation Rules:**
- No em dashes (auto-sanitized before output)
- X posts must end with a question mark, under 280 chars
- LinkedIn posts must end with engagement question, under 3000 chars
- Blog posts must output valid JSON with title, meta_description, sections

**Memory Files:**
- `memory/audience.json` - Audience insights and preferences
- `memory/content_log.json` - All posts with engagement metrics
- `memory/trends.json` - Tracked trends and predictions
- `memory/blog_log.json` - Blog post history

**Config:** `config/base.json`
```json
{
  "agent": "Agent_5",
  "cycle": {
    "sleep_between_cycles": 3600,
    "trend_scout_interval": 14400
  },
  "social": {
    "typefully_api_key": "${TYPEFULLY_API_KEY}",
    "social_set_id": 292721
  },
  "data": {
    "gapfeed_api": "https://gapfeed.com/api/db.php",
    "gapfeed_api_key": "gapfeed-api-key-2026-secure"
  },
  "llm": {
    "primary": "deepseek/deepseek-v3.2",
    "fallback": "xiaomi/mimo-v2-flash",
    "max_tokens": 2000,
    "temperature": 0.7
  },
  "telegram": {
    "enabled": true,
    "bot_token": "${TELEGRAM_BOT_TOKEN}",
    "chat_id": "${TELEGRAM_CHAT_ID}"
  }
}
```

**Integration Points:**
- Typefully API: creates/schedules drafts for X and LinkedIn
- GapFeed API: pulls live stats for content context
- Shared LLM client: auto-fallback on rate limits
- Blog (dariocositore.com): SFTP deploy via paramiko
- Other agents: can receive data from Agent_6 (gaps), Agent_1 (signals)

**Current Status:** Fully built, 28 tests passing, orchestrator wired, running

**Typefully API v2 Format (2026-03-29):**
Typefully changed its API payload format. New structure:
```json
{
  "platforms": {
    "x": {
      "enabled": true,
      "posts": [{"text": "post content here"}]
    }
  },
  "publish_at": "2026-03-30T09:00:00.000Z"
}
```
- `content` field no longer valid (use `platforms.{name}.posts[].text`)
- `schedule_time` no longer valid (use `publish_at`)
- `platforms` must be a dict with per-platform config (not a list)
- Response uses `results` instead of `data`
- Response uses `scheduled_date` instead of `schedule_time`
- Thread support: multiple items in `posts` array

**T+1 Only Scheduling (2026-03-29):**
- Posts are ONLY scheduled for T+1 (tomorrow), never T+2
- Data freshness matters: every post reflects data less than 24 hours old
- Before creating drafts, Luna checks Typefully for existing T+1 drafts
- If tomorrow is full, Luna skips and waits until T+1 rolls forward
- Max posts per day controlled by `social.max_posts_per_day` (default 4)
- Posting slots: X at 10:00, 18:00 CET; LinkedIn at 09:30 CET

**Approval System:**
- Luna creates drafts only, never schedules directly
- Sends Telegram notification with draft preview + topic + reasoning
- Social drafts: Dario approves via Telegram callback buttons
- Blog drafts: outline saved to `memory/pending_approval.json`, Telegram notification with Approve/Reject buttons
- 4-hour minimum gap between posts (configurable via `post_gap_hours`)
- Viral override: if trend score >= 0.8, can post even with short gap (still needs approval)
- Approved drafts are scheduled in Typefully automatically
- Pending drafts stored in `memory/pending_approval.json`

**Blog Approval Flow (2026-03-29):**
- PLAN_CONTENT chooses `blog_post` type
- CREATE_CONTENT generates outline via LLM, saves to `pending_approval.json`
- Sends Telegram notification with title, meta description, section summary
- Dario taps Approve/Reject via Telegram callback buttons
- Approved: `callback_handler` updates status -> `_check_approved_drafts` picks it up
- BlogManager creates HTML -> SFTP deploys to IONOS (dariocositore.com/blog/)

**Performance Tracker (2026-03-29):**
- `performance_tracker.py` - Manual feedback loop for published post analytics
- Typefully v2 API has no analytics endpoint, so feedback is manual
- Dario can submit feedback via Telegram (engagement, topic, platform)
- Tracks: post topic, platform, style, hours since publish, engagement score
- Recommendations: focus topics, avoid topics, best posting hours, best format
- Requires 3+ feedback entries before generating recommendations
- SYNC_PERFORMANCE state runs every cycle to sync published posts

### Data Flow (Full Pipeline)
````
Agent_1 (12 API sources, 1s sleep)
    ↓ MySQL signals table
Agent_2 (7 browser sources, 5s sleep)
    ↓ MySQL signals table
    ↓
Agent_6 (classify + gap detect, 30s)
    ↓ MySQL signals table (classified fields updated)
    ↓ MySQL gaps table (new/updated gaps)
    ↓ [every 3 cycles] Page Generator
    ↓   - generates static HTML for all gaps (FAQ, related, Schema.org)
    ↓   - regenerates sitemap.xml (129 URLs)
    ↓   - deploys gap/ + categories/ + sources/ + sitemap.xml to IONOS
    ↓
Agent_7 (health check, 5 min)
    ↓ memory/reports/
    ↓ alerts if issues found
    ↓
Agent_5 (marketing, 1 hour)
    ↓ trends from Reddit/HN/X/LI
    ↓ content plan via LLM reasoning
    ↓ generated posts via deepseek-v3.2
    ↓ scheduled drafts in Typefully
    ↓ engagement tracking + learning
    ↓
Agent_4 (on-demand only)
    ↓ generates briefs from classified signals
    ↓
Frontend (server.py on port 5002)
    ↓ serves data to API consumers
    ↓
Website (gapfeed.com - sidebar prototype as index.html)
    ↓ deployed to IONOS via SFTP
    ↓ Google crawls via Search Console sitemap submission
    ↓
Blog (dariocositore.com)
    ↓ blog posts deployed via SFTP
    ↓ Agent_5 manages content
    ↓
Social (X + LinkedIn via Typefully)
    ↓ scheduled posts and threads
    ↓ Agent_5 manages campaigns
````

---

## 6. Analytics Infrastructure

### Data Collection
- Analytics tables in MySQL (daily aggregation)
- Triggered by `aggregate_analytics` action in `api/db.php`
- Aggregation script: `scripts/aggregate_analytics.py`
- Windows Task Scheduler: `GapFeed-Analytics-Daily` at 2:00 AM Rome
- Output: `data/analytics/YYYY-MM-DD.json`

### Aggregated Metrics
- Signal count by source
- Gap growth rate
- Top gaps by heat_score
- Source performance
- Category distribution
- Buyer intent distribution

---

## 7. Data Hygiene & Lifecycle

### Signals
| Age | State | Purpose |
|-----|-------|---------|
| 0-7 days | Hot | Active references, most relevant |
| 7-30 days | Warm | Gap validation, trending |
| 30-90 days | Cold | Historical trend data only |
| 90+ days | Archive | Move to archive table, remove from active queries |

### Gaps
| State | Trigger | Action |
|-------|---------|--------|
| Active | Receiving signals, heat rising/stable | Normal operation |
| Stale | No new signals in 14 days, heat declining | Mark stale |
| Solved | Product exists in market | Mark solved |
| Archived | 60 days stale | Move to archive table |

### Briefs
| Age | Action |
|-----|--------|
| 0-7 days | Current, serve directly |
| 7-30 days | Regenerate if signals changed |
| 30+ days | Delete, regenerate on next request |

### Maintenance Schedule
| Cycle | Action |
|-------|--------|
| Daily | Nothing (data too fresh) |
| Weekly | Check stale gaps, refresh briefs, archive old briefs |
| Monthly | Move signals >90 days to archive, compact stale gaps |
| Quarterly | Full audit, vacuum archive table |

### Cleanup Script (TODO)
- Script: `scripts/cleanup_hygiene.py`
- Runs alongside analytics cron (weekly instead of daily)
- Checks gap staleness, archives old signals, cleans briefs

---

## 8. Live Data Visualizations (Graphs Page)

### Design Decisions (2026-03-27)
- Graphs page added as sidebar item below Feed
- Content width: 1000px (wider to accommodate charts)
- Charts use inline SVG (no Chart.js dependency)
- Target audience: indie hackers, founders, PMs, VCs
- Four key questions the graphs answer:
  1. Is this problem real? (signal volume badge)
  2. Is it growing? (sparkline velocity)
  3. Would people pay? (buyer intent score)
  4. What are they saying? (real quotes, timestamped)

### Visualizations Built (Prototype)
1. **Stat cards row** - 4 cards: signals scanned, active gaps, buyer intent %, sources active
2. **Source distribution** - horizontal bar chart (Reddit, HN, DDG, SO, Dev.to, RSS)
3. **Fastest Growing Gaps** - top 5 by velocity with sparklines showing trend direction (green=rising, amber=stable, red=declining)
4. **Sentiment donut** - negative/neutral/positive breakdown
5. **Buyer intent donut** - high/medium/low distribution
6. **Source uptime grid** - 7-day heatmap, green=scanned, red=missed

### API Endpoints (LIVE)
| Endpoint | Returns | Status |
|----------|---------|--------|
| `signal_count` | Total signals | LIVE |
| `source_distribution` | Signals by source with percentages | LIVE |
| `sentiment_breakdown` | Sentiment counts + percentages | LIVE |
| `buyer_intent_distribution` | Intent buckets (high/med/low) | LIVE |
| `top_gaps_velocity` | Top 10 gaps by evidence_count | LIVE |
| `uptime` | Scan log grouped by 12h windows | LIVE |
| `stats` | Signals + gaps count | LIVE |
| `get_gaps` | Paginated gap list | LIVE |

### Prototype Status
- **Deployed:** `https://gapfeed.com/` (main page, sidebar IS the site)
- **Wired to:** all 8 API endpoints, live data
- **Features:** pagination, search, category grouping, sparklines, tag colors, time filters, page switching
- **Pages:** Feed, Graphs, Gap Detail, About, Privacy, Terms
- **SEO:** Twitter cards, Schema.org (WebSite + Organization + WebApplication), robots meta, canonical, OG image tag, 76 URL sitemap
- **404 page:** Custom funny 404 with sad face at gapfeed.com/anything

### Known Issues
- Sentiment still skewed toward negative (74%), expected to settle around 60-70% as Maya processes diverse sources

---

## 9. Hosting & Deployment

### IONOS Hosting
- **SFTP:** `<SFTP_USER>@<IONOS_WEBSPACE>.webspace-host.com:22`
- **Domains:** dariocositore.com + gapfeed.com (both 217.160.0.71)
- **Production path:** `/gapfeed.com/` (renamed from `/gapfeed.com/` on 2026-03-29)
- **PHP API:** `api/db.php` (MySQL proxy, Bearer auth)
- **Deploy:** SFTP via paramiko (index.html, gap pages, about/privacy/terms)
- **Custom 404:** `404.html` with .htaccess ErrorDocument
- **.htaccess:** Clean URL rewriting, gzip compression, security headers

### MySQL (IONOS)
- **Host:** `dbXXXXXXX.hosting-data.io:3306` (IONOS network only)
- **PHP API:** `https://gapfeed.com/api/db.php` (Bearer: `gapfeed-api-key-2026-secure`)
- **Client:** `shared/remote_db.py` - `RemoteDB()` class

### Local
- **Server:** `ui/server.py` on port 5002
- **Agents:** `TheRealAgents/` - each in own folder with logs/

---

## 10. Pending Work

### Completed (2026-03-27)
- [x] signal_count API fix (db.php vertical filter bug)
- [x] Chart API endpoints (5 new actions in db.php)
- [x] Maya scoring fix (few-shot examples, urgency avg 0.42, sentiment 74/24/2)
- [x] Agent_7 Telegram notifications (NOTIFY step added)
- [x] db.php deployed to IONOS
- [x] Prototype wired to live API (8 endpoints, 46KB)
- [x] Maya upgraded to gpt-oss-120b with parallel batch classification
- [x] Feed pagination, search, category grouping, sparklines, tag colors
- [x] SEO optimization ("what should I build" / "what to build with AI")
- [x] Privacy/Terms/About pages

### Completed (2026-03-29)
- [x] Agent_5 performance feedback loop (performance_tracker.py, 28 tests passing)
- [x] Agent_5 blog approval flow (Telegram callback with Approve/Reject, SFTP deploy)
- [x] Agent_5 T+1 only scheduling (data freshness, never past tomorrow)
- [x] Typefully API v2 format migration (platforms dict, posts[].text, publish_at)
- [x] Agent_5 state machine: SCHEDULE_POSTS -> CREATE_DRAFTS, added SYNC_PERFORMANCE
- [x] Agent_5 singleton lock (PID-based lock file, prevents duplicate instances)
- [x] Gap description rewrite Phase 1 (competitor intelligence pipeline, no DDG)
- [x] mention_resolver.py - 100+ alias mappings, canonical entity resolution
- [x] cluster_context_builder.py - per-cluster market context aggregation
- [x] gap_detector.py rewired - structured evidence instead of raw signal dump
- [x] DB migration: signals.gap_id + signals.category columns
- [x] DB migration: gaps.competitors JSON column (insert_gap + update_gap)
- [x] PHP API deployed with competitor support
- [x] HEARTBEAT.md updated with Agent_5 singleton lock rules

### Phase 2 - Competitor Intelligence (Completed 2026-03-29)
- [x] competitor_entities table (canonical names, aliases, entity_type, verticals, active, stats)
- [x] signal_entity_mentions table (signal_id, entity_id, raw_mention, mention_type, confidence, sentiment, context_span)
- [x] Backfill: 1910 signals processed, 50 entities created, 1818 mentions persisted
- [x] PHP API endpoints: upsert_entity, update_entity_stats, get_entities, insert_mention, insert_mentions_bulk, get_cluster_entities
- [x] cluster_context_builder queries DB first, merges with in-memory resolution
- [x] mention_resolver.py feeds into DB (alias map + product_category + content scan)

### Phase 3 - Competitor Intelligence (Completed 2026-03-29)
- [x] Competitor scoring: 0.35*frequency + 0.25*distinct_authors + 0.20*negative_rate + 0.10*recency + 0.10*cluster_relevance
- [x] Threat classification: dominant_hated, dominant_neutral, weak, irrelevant
- [x] Opportunity signal: high/moderate/low/open based on dominant_hated count
- [x] cluster_context_builder uses scoring to add threat_assessment + top_scored to LLM evidence
- [x] PHP analytics endpoints: top_competitors_by_category, substitute_analytics, entity_heatmap
- [x] Maya pipeline integration: writer.py persists entity mentions on every classification (fire-and-forget)

### Phase 4 - Competitor Intelligence (Future)
- [ ] Async enrichment for low-confidence clusters (background DDG as optional enhancer)
- [ ] Analytics dashboard: "top failed competitors by category", "which substitutes dominate pre-SaaS"
- [ ] Real-time entity trend detection via heatmap endpoint

### Completed (2026-03-28)
- [x] Sidebar prototype deployed as main page at gapfeed.com (replaced old index.html)
- [x] SEO: Twitter cards, Schema.org JSON-LD (WebSite + Organization + WebApplication), robots meta tag
- [x] Sitemap regenerated with 76 URLs (46 gap pages, 25 categories, 2 sources, 3 static)
- [x] robots.txt updated (blocks /api/, /admin/, declares sitemap)
- [x] Source normalization fix for quote display (normalizeSource() maps www.reddit.com -> reddit, etc.)
- [x] Custom 404 page with sad face joke, deployed with .htaccess ErrorDocument
- [x] Gap pages, categories, sources all deployed to IONOS
- [x] Agents restarted (Agent_6 and Agent_7 died silently, revived with correct working directory)
- [x] Google Analytics tag (G-FXVLBGRXX8) added to main page
- [x] Google Search Console set up and sitemap submitted (Dario)
- [x] OG image created and deployed (og-image.png, 1200x630)
- [x] Gap page auto-generation wired into Maya's pipeline (page_generator.py)
- [x] Auto-sitemap regeneration after new pages (129 URLs)
- [x] Auto-deploy to IONOS via SFTP after page generation
- [x] Internal links between related gaps (8 per page, "Related Market Gaps" section)
- [x] FAQ sections on gap pages (for Google rich snippets)
- [x] Social sharing buttons on gap pages (X, LinkedIn, Copy link)
- [x] Social sharing in sidebar SPA gap detail view
- [x] Share tweets tagged @DarioCositore
- [x] Agent_5 agent fully built (9 modules, 11 tests passing)
- [x] Agent_5 orchestrator wired (7 states, all functional)
- [x] Agent_5 uses shared LLM client with deepseek-v3.2 as primary
- [x] 32 social media posts created and scheduled in Typefully
- [x] Phase 1 social content strategy (ramp-up: 6→8→10→8 posts/week)
- [x] Telegram model alias fix (added `pro -> openrouter/xiaomi/mimo-v2-pro`)
- [x] Alex expanded to 12 sources (added Google News, GitHub Issues, GitHub Discussions, Product Hunt)
- [x] DDG rotating user agents (8 UAs) for anti-detection
- [x] YouTube quota management (8k/10k daily, auto-stop)
- [x] Intelligent PLAN phase (LLM dynamic queries from trends)
- [x] Query performance ledger (tracks wins, decay factor)
- [x] Cross-source correlation (2-3x urgency boost for multi-source pain)
- [x] Quote filter for gap pages (rejects metadata noise, truncated fragments)
- [x] Quotes stored as objects {text, source, url} with source links
- [x] Self-hosted Inter font (woff2, removed Google CDN)
- [x] Feedback button in header (speech bubble icon, links to @DarioCositore)
- [x] Feedback link in footer

### Live Stats (2026-03-29 20:30 CET)
- **Signals:** 11,322
- **Gaps:** 53+
- **Static pages:** 99 gap + about + privacy + terms = 103 pages
- **Sitemap URLs:** 103+
- **Domain:** gapfeed.com (rebranded from gapfeed.com)
- **Sources:** 12 (Reddit, DDG, HN, SO, Dev.to, RSS, YouTube, Indie Hackers, GitHub Issues, Google News, GitHub Discussions, Product Hunt)
- **Agents:** Agent_1, Agent_6, Agent_7, Agent_5 running
- **Agent_2:** Paused (under reconstruction, search engine blocking)
- **Server:** UP on port 5002
- **API:** gapfeed.com/api/db.php (11,322 signals confirmed)
- **Social:** 32 posts scheduled in Typefully (Mar 30 - Apr 24)
- **Blog:** dariocositore.com live with 3 posts

### High Priority
- [ ] Self-host Outfit + DM Sans fonts (Lighthouse optimization)
- [ ] Newsletter / "Weekly Top Gaps" email (high retention + growth driver)
- [ ] News adapter for Alex (Google News, Product Hunt, Indie Hackers)
- [ ] Add more sources: GitHub issues, Quora
- [ ] Test Agent_5 with live data (first cycle run)
- [ ] Wire Agent_5 into OpenClaw as background agent

### Medium Priority
- [ ] Mobile responsive testing with live data
- [ ] Searchbar intelligent search (categories, direct pain, similar pains)
- [ ] Data hygiene cleanup script
- [ ] RSS feed parse error fix (Agent_2)
- [ ] Blog / Insights section (SEO + thought leadership)

### Low Priority
- [ ] Gap staleness detection logic
- [ ] Archive table schema
- [ ] Quarterly audit automation

### Current Limitations
- Only 12 sources active (Reddit, HN, DDG, SO, Dev.to, RSS, YouTube, Indie Hackers, GitHub Issues, Google News, GitHub Discussions, Product Hunt)
- Gap count still small (53) - needs more signal volume
- Sentiment bias: 74% negative (expected to settle at 60-70%)
- Categories are raw (auto-generated, not pre-defined groups)
- No mobile-optimized layout yet
- Bing Webmaster Tools not set up (service issues)

---

## 11. Key Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-03-27 | Arc theme chosen for design | Outfit + DM Sans fonts, #4f9cf7 accent |
| 2026-03-27 | Free product only | No login, no paywall, behavioral data farming |
| 2026-03-27 | tuXo logo with accent-colored X | Lowercase, 1.15em size, font-weight 700 |
| 2026-03-27 | Context-aware content width | Feed 1000px, gap detail 780px (TODO) |
| 2026-03-27 | Data hygiene cycles | Hot/Warm/Cold/Archive based on age |
| 2026-03-27 | No em dashes in user-facing content | Hyphens only, SEO and design consistency |
| 2026-03-27 | Step 3.5 Flash for compaction | Free model, saves OpenRouter credits |
| 2026-03-27 | Graphs page as sidebar item below Feed | 1000px width, inline SVG charts, no framework |
| 2026-03-27 | Velocity shown as sparklines not numbers | Humans read shapes faster than numbers |
| 2026-03-27 | User flow: Graphs → category filter → gap detail → quotes | Drill-down funnel design |
| 2026-03-27 | Free product, no login, no paywall | Revenue via behavioral intent data farming |
| 2026-03-27 | gpt-oss-120b for Maya classification | Better score distribution than qwen models |
| 2026-03-27 | Batch size 7 signals per LLM call | Sweet spot: 1.76s/signal vs 1.1s single |
| 2026-03-27 | Parallel batches (3 concurrent) | ThreadPoolExecutor for classification |
| 2026-03-27 | Category grouping (41 -> 7 groups) | Sidebar usability, cleaner feed |
| 2026-03-27 | SEO keywords: "what should I build" | Primary organic traffic target |
| 2026-03-27 | Right sidebar for ads (300px) | Monetization placeholder |
| 2026-03-27 | Hash-based page routing | SPA with show/hide, no server needed |
| 2026-03-28 | Sidebar prototype replaces main page | sidebar-prototype.html deployed as index.html on gapfeed.com |
| 2026-03-28 | SEO hardening: Twitter + Schema.org + sitemap | 76 URL sitemap, 3 JSON-LD blocks, robots meta |
| 2026-03-28 | Source normalization for quote icons | normalizeSource() maps domains to canonical keys (reddit, hn, etc.) |
| 2026-03-28 | Custom 404 page | Funny sad face, same design palette, .htaccess ErrorDocument |
| 2026-03-28 | Agent launch requires correct WorkingDirectory | Start-Process without -WorkingDirectory causes silent crash |
| 2026-03-28 | Auto gap page generation in Maya pipeline | page_generator.py called after gap detection every 3 cycles |
| 2026-03-28 | Auto sitemap + auto deploy after page gen | 129 URLs, deploys gap/categories/sources/sitemap to IONOS |
| 2026-03-28 | Google Analytics G-FXVLBGRXX8 | Added to main page head section |
| 2026-03-28 | OG image (og-image.png) | 1200x630 branded, deployed to IONOS root |
| 2026-03-28 | Agent_5 agent created | Marketing/community manager AI for blog + social + trends |
| 2026-03-28 | Agent_5 uses deepseek-v3.2 | Best creative writing quality, primary model for content |
| 2026-03-28 | Per-agent LLM config | Each agent uses what fits its job: Maya=gpt-oss-120b (speed), Luna=deepseek-v3.2 (quality), rest=mimo-v2-flash (default) |
| 2026-03-28 | Telegram model alias fix | Added `pro -> openrouter/xiaomi/mimo-v2-pro` alias, was missing from configured models |
| 2026-03-28 | 32 social posts scheduled in Typefully | Phase 1 content for full month (Mar 30 - Apr 24), ramp-up strategy |
| 2026-03-28 | Alex expanded to 12 sources | Added Google News, GitHub Issues, GitHub Discussions, Product Hunt |
| 2026-03-28 | DDG rotating user agents (8 UAs) | Rotates every 5 requests, proxy support ready |
| 2026-03-28 | YouTube quota management | 8k/10k daily limit, auto-stop, file persistence, re-enabled |
| 2026-03-28 | ~317 unique pain queries across sources | Dario's 165-query set + per-source expansions |
| 2026-03-28 | Intelligent PLAN phase (Option A) | QueryGenerator: LLM generates dynamic queries from trends |
| 2026-03-28 | Query performance ledger (Option D) | QueryLedger: tracks wins, decay factor, biases toward proven queries |
| 2026-03-28 | Cross-source correlation (Option C) | 2-3x urgency boost when same pain on multiple sources |
| 2026-03-28 | mimo-v2-flash for query generation | Tested vs deepseek-v3.2, mimo wins on speed (3s vs 12s) |
| 2026-03-28 | Alex sleep 3s -> 1s, max signals 500 -> 1500 | Scale-up for 12 sources |
| 2026-03-28 | Quote filter for gap pages | is_clean_quote() rejects metadata noise, truncated quotes, short fragments |
| 2026-03-28 | Quotes as objects {text, source, url} | Maya stores quotes with source URLs for SEO linking |
| 2026-03-28 | Source links on quote cards | Platform links (reddit.com, HN, SO) on every quote for SEO |
| 2026-03-28 | Self-hosted Inter font | Added woff2 files, removed Google Fonts CDN from gap pages |
| 2026-03-28 | Feedback button in header | Speech bubble icon next to search bar, links to @DarioCositore tweet |
| 2026-03-28 | Footer feedback link | "Feedback?" link in footer navigation |
| 2026-03-29 | T+1 only scheduling for Luna | Posts only for tomorrow, data freshness <24h, builds trust reputation |
| 2026-03-29 | Typefully API v2 migration | New format: platforms dict, posts[].text, publish_at field |
| 2026-03-29 | Blog approval via Telegram callbacks | Approve/Reject buttons, auto-deploy to IONOS on approval |
| 2026-03-29 | Manual performance feedback loop | Typefully v2 has no analytics API, Dario submits feedback via Telegram |
| 2026-03-29 | Agent_5 state rename: SCHEDULE_POSTS -> CREATE_DRAFTS | Better reflects approval-based flow |
| 2026-03-29 | Agent_5 singleton lock | PID-based lock file prevents duplicate instances from heartbeat restarts |
| 2026-03-29 | Competitor intelligence as upstream data layer | Move competitor discovery out of gap_detector, into mention_resolver + cluster_context_builder |
| 2026-03-29 | No DDG in gap pipeline | All competitor evidence from Maya's extracted data, zero external API calls |
| 2026-03-29 | Substitutes as first-class competitor data | Excel, manual work, WhatsApp = real market insight, not just SaaS brands |
| 2026-03-29 | Evidence-only LLM rule for gaps | "Only use competitor names from provided evidence. Do not invent names." |
| 2026-03-29 | Cluster context precomputed before LLM | Build market context artifact per cluster, then pass to LLM (not live discovery) |
| 2026-03-29 | Text sanitizer for gap descriptions | sanitize_text() strips AI tells: compound adjectives, em dashes, corporate phrases. Applied to all LLM output. |
| 2026-03-29 | Gap prompt rewritten for human voice | "Write like you're explaining to a friend over coffee" not "follow this sentence structure" |
| 2026-03-29 | Gemini 3 Flash for gap descriptions | Dedicated LLM (separate from shared client). Benchmarked 7 models: Gemini won on speed (3s), cost ($0.0016/call), and quality. GLM-5 and Kimi failed. |
| 2026-03-29 | Phase 2: Persistent entity registry | competitor_entities + signal_entity_mentions tables. 50 entities, 1818 mentions from backfill. DB-first resolution with in-memory fallback. |
| 2026-03-29 | Phase 3: Competitor scoring + Maya integration | Composite score (frequency/authors/negativity/recency/relevance). Threat levels: dominant_hated = opportunity. Maya persists mentions in real-time. Analytics endpoints live. |
| 2026-03-29 | Rebrand: GapFeed -> GapFeed | 213 HTML files rebranded, all agent configs + shared modules updated. gapfeed.com redirects to gapfeed.com. |
| 2026-03-29 | Gap page redesign (3 iterations) | Unified design with main site: sidebar, 780px centered, Outfit+DM Sans, blue accent. Static HTML with sidebar matching feed page. |
| 2026-03-29 | Static pages: about/privacy/terms at root | Separate HTML files with sidebar nav, dark theme, hello@gapfeed.com contact. Replaces SPA-based pages. |
| 2026-03-29 | Feed gap links use real URLs | `<a href="/gap/{slug}.html">` instead of JS onclick. Google crawlable. |
| 2026-03-29 | Agent_2 paused - search engines block headless | DDG, Google, Brave all captcha-block Playwright. Jack role pending redefinition. |
