# GapFeed - Architecture Document

_Last updated: 2026-03-29_

This is the technical architecture companion to [MASTER.md](MASTER.md). For design decisions, data schema, and agent details, see MASTER.md.

---

## 1. Vision

**GapFeed = Market Gap Discovery Feed**

Not search, not social listening. Scans the internet 24/7, clusters signals into gaps (unsolved problems). "Product Hunt, but for problems instead of products."

- **Free only** - no login, no paywall, no pricing tiers
- Revenue model: behavioral intent data farming (searches, clicks, exploration patterns)
- SEO play: every gap gets a permanent, indexable page

---

## 2. Domain and URLs

- **GapFeed product**: `gapfeed.com` (.com, .it, .info, .srl all acquired)
- **Dario's site**: `dariocositore.com` (IONOS hosting, blog + personal)
- **GitHub repo**: `github.com/dario-cositore/gapfeed` (public)
- **API server**: `https://gapfeed.com/api/db.php` (PHP, IONOS)

### URL Structure

| URL | Served by |
|-----|-----------|
| `gapfeed.com/` | GapFeed main page (SPA, sidebar) |
| `gapfeed.com/gap/{slug}.html` | Static gap detail pages |
| `gapfeed.com/about.html` | About page |
| `gapfeed.com/privacy.html` | Privacy policy |
| `gapfeed.com/terms.html` | Terms of service |
| `gapfeed.com/api/db.php` | PHP API (MySQL proxy, Bearer auth) |
| `gapfeed.com/api/track.php` | Analytics tracking |

---

## 3. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Agents** | Python 3.11+ | Core language for all agent logic |
| **LLM** | Multiple via OpenRouter | Cost/performance tradeoffs per agent |
| **Database** | MySQL 8.0 (IONOS, primary) + SQLite (local backup) | MySQL for production, SQLite for local dev |
| **Frontend** | Astro + vanilla JS | Static site, fast, SEO-friendly |
| **API** | PHP 8 (IONOS) | MySQL proxy with Bearer auth |
| **Deploy** | SFTP via paramiko | IONOS hosting |
| **Social** | Typefully API v2 | X + LinkedIn scheduling |
| **Monitoring** | Telegram Bot API | Alert notifications |

### LLM Model Assignments

| Agent | Primary Model | Fallback | Why |
|-------|--------------|----------|-----|
| **Agent_6** (Classifier) | `openai/gpt-oss-120b` | - | 50+ classifications/cycle, need speed |
| **Agent_5** (Marketing) | `deepseek/deepseek-v3.2` | `xiaomi/mimo-v2-flash` | Creative writing, quality matters |
| **Agent_1** (Scout) | `xiaomi/mimo-v2-flash` | - | Default, good enough for signal enrichment |
| **Agent_7** (Monitor) | `xiaomi/mimo-v2-flash` | - | Default, health checks don't need premium |
| **Agent_4** (Briefs) | `xiaomi/mimo-v2-flash` | - | Default, on-demand briefs |
| **Gap descriptions** | `google/gemini-3-flash-preview` | - | Best quality/cost for gap writing |

---

## 4. Data Flow

```
Agent_1 (12 API sources, 1s sleep)
    ↓ MySQL signals table
Agent_6 (classify + gap detect, 30s)
    ↓ MySQL signals table (classified fields updated)
    ↓ MySQL gaps table (new/updated gaps)
    ↓ [every 3 cycles] Page Generator
    ↓   - generates static HTML for all gaps (FAQ, related, Schema.org)
    ↓   - regenerates sitemap.xml
    ↓   - deploys to IONOS via SFTP
    ↓
Agent_7 (health check, 5 min)
    ↓ memory/reports/
    ↓ Telegram alerts if issues found
    ↓
Agent_5 (marketing, 1 hour)
    ↓ trends from Reddit/HN/X/LI
    ↓ content plan via LLM reasoning
    ↓ generated posts via deepseek-v3.2
    ↓ scheduled drafts in Typefully (T+1 only)
    ↓ engagement tracking + learning
    ↓
Agent_4 (on-demand only)
    ↓ generates briefs from classified signals
```

---

## 5. Database Schema

### MySQL (IONOS - Primary)

**signals** (26 columns) — Raw pain signals from all sources

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
| product_category | VARCHAR | Product area classification |
| pain_category | VARCHAR | Pain type |
| signal_type | VARCHAR | question, complaint, request |
| location | VARCHAR | Geographic signal |
| urgency_score | DECIMAL | 0-1 urgency rating |
| specificity_score | DECIMAL | 0-1 specificity rating |
| buyer_intent | DECIMAL | 0-1 willingness to pay |
| quality_tier | VARCHAR | gold, silver, bronze, noise |
| sentiment | VARCHAR | positive, negative, neutral |
| competitor_mentions | JSON | Competitor names extracted by Maya |
| metadata | JSON | Business size, profile info |
| gap_id | INT | FK to gaps table |
| category | VARCHAR | Gap category |
| is_processed | INT | 0/1 processed flag |
| synthesized | INT | 0/1 synthesis flag |

**gaps** (17 columns) — Detected market gaps

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Primary key |
| title | VARCHAR | Gap title |
| slug | VARCHAR | URL slug |
| description | TEXT | LLM-generated, evidence-based |
| evidence_count | INT | Number of supporting signals |
| heat_score | DECIMAL | 0-1 popularity/urgency |
| category | VARCHAR | Gap category |
| source_types | JSON | Which sources contributed |
| signal_ids | JSON | Linked signal IDs |
| sample_quotes | JSON | Actual user quotes with source URLs |
| competitors | JSON | Competitor intelligence (failed_tools, substitutes, why_now, etc.) |
| gap_validity | VARCHAR | unvalidated, validated, saturated, wide_open |
| opportunity_score | DECIMAL | Demand / threat ratio |
| last_validated_at | DATETIME | Last competitor validation run |
| status | VARCHAR | active, stale, solved, archived |
| created_at | DATETIME | First detected |
| updated_at | DATETIME | Last updated |

### SQLite (Local Backup)
- `data/signals.db` — local backup, agents use as fallback

---

## 6. Competitor Intelligence Pipeline

Three-layer architecture for evidence-based gap descriptions without external API calls:

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

**Key principle:** Competitors are a stored feature of the signal/cluster graph, not a live lookup. No external searches, no rate limits.

### Mention Resolver (`src/engines/mention_resolver.py`)
- 100+ alias mappings for common SaaS tools, platforms, substitutes
- Resolves to canonical entities: Shopify, PayPal, Stripe, etc.
- Classifies entity types: competitor, substitute, platform, tool
- Current coverage: 68% of gold signals have at least one resolved mention

### Cluster Context Builder (`src/engines/cluster_context_builder.py`)
- Aggregates resolved mentions across a signal cluster
- Produces: top competitors, substitutes, pain phrases, affected personas
- Computes confidence score based on data richness
- Formats into LLM-readable evidence block

### Gap Detector (rewired 2026-03-29)
- Builds cluster context BEFORE calling LLM
- LLM prompt enforces: only use competitor names from evidence
- If no named competitors: frames gap around substitutes (Excel, manual work, etc.)
- No external API calls. Pipeline never blocks on rate limits.

---

## 7. Hosting & Deployment

### IONOS Hosting
- **SFTP**: `<IONOS_WEBSPACE>.webspace-host.com:22`
- **Domains**: dariocositore.com + gapfeed.com (both 217.160.0.71)
- **Production path**: `/gapfeed.com/`
- **PHP API**: `api/db.php` (MySQL proxy, Bearer auth)
- **Deploy**: SFTP via paramiko (index.html, gap pages, about/privacy/terms)
- **SSL**: Active on gapfeed.com (IONOS managed)
- **SPF**: `v=spf1 include:_spf-eu.ionos.com ~all`

### MySQL (IONOS)
- **Host**: `dbXXXXXXX.hosting-data.io:3306` (IONOS network only)
- **PHP API**: `https://gapfeed.com/api/db.php`
- **Client**: `shared/remote_db.py` — `RemoteDB()` class

---

## 8. SEO Strategy

- Title: "GapFeed - Market Gap Intelligence"
- Meta description: includes "what to build next", "unsolved problems", "market gaps"
- Meta keywords: "what should I build, what to build with AI, startup ideas"
- OG tags for social sharing (og-image.png, 1200x630)
- Twitter cards (summary_large_image)
- Schema.org JSON-LD: WebSite + Organization + WebApplication (main page)
- Schema.org per gap: TechArticle + BreadcrumbList + FAQPage
- Sitemap: 100+ URLs (gap pages + about + privacy + terms + feed)
- Gap pages are static HTML with sidebar, centered at 780px
- Real `<a href>` links from feed to gap pages (Google crawlable)
- `.htaccess` for clean URL rewriting
- Internal links: 8 related gaps per page
- FAQ sections for Google rich snippets
- Google Search Console: submitted

---

## 9. Project Structure

```
gapfeed/
├── scripts/           # 83 processing scripts — scrapers, classifiers, exporters
│   ├── generate_pages/    # Static HTML page generator (gap, index, SEO)
│   ├── gapfeed_engine.py  # Main pipeline orchestrator
│   ├── enrich_gaps_sonnet.py  # LLM gap enrichment
│   └── ...                # 80+ more
├── shared/            # Shared modules
│   ├── llm_client.py      # LLM client with auto-fallback
│   ├── remote_db.py       # MySQL remote DB client
│   ├── signals_db.py      # SQLite local DB client
│   ├── analytics.py       # Analytics aggregation
│   └── competitor_lookup.py  # Competitor data lookup
├── src/engines/       # Core ML/NLP engines
│   ├── gap_detector.py         # Gap detection algorithm
│   ├── gap_llm.py              # LLM integration for gap writing
│   ├── mention_resolver.py     # Entity mention resolution
│   ├── cluster_context_builder.py  # Signal clustering
│   └── competitor_scorer.py    # Competitor scoring
├── api/               # PHP API layer
│   ├── db.php             # Main API (MySQL proxy)
│   └── track.php          # Analytics tracking
├── data/
│   ├── pristine_gaps/      # 30 verified market gap JSON files
│   ├── thegapfeedproject/  # Project docs (VISION, STATUS, ARCHITECTURE)
│   └── analytics/          # Daily analytics JSON
├── docs/
│   ├── MASTER.md           # Single source of truth (1122 lines)
│   ├── ARCHITECTURE.md     # This file
│   └── GapFeed-Master-Plan.html  # Generated PDF-ready HTML
├── content/blog/      # Blog post markdown files
├── tools/             # Utility tools
│   ├── ingest_signal.py    # Signal ingestion
│   ├── synthesize_gap.py   # Gap synthesis
│   ├── swarm_engine.py     # Swarm orchestration
│   └── understand_signals.py  # Signal analysis
├── tests/             # Test suite
├── Procfile           # Deployment config
├── requirements.txt   # Python dependencies
└── runtime.txt        # Python runtime version
```

---

## 10. Related Projects

- **Elitza** — Agent profile marketplace ([elitza.life](https://elitza.life))
- **OpenConnect** — Browser extension for MCP connector generation
- **D'Alessio** — U.S. Immigration Law firm (case study: <$100K/mo to ~$400K/mo using AI-powered ops)