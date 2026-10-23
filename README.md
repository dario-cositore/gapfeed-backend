# GapFeed

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Autonomous AI agents that scan the internet around the clock to discover **market gaps** - underserved problems, frustrated users, and unmet needs - then turn them into actionable product opportunities.

**"Product Hunt, but for problems instead of products."**

## What Is GapFeed?

GapFeed listens to real human pain. It pulls signals from Reddit, Hacker News, YouTube, GitHub, and a dozen more sources. LLM agents classify and cluster those signals into candidate market gaps. The system then writes SEO-ready gap pages so the world's first AI-native problem feed can go live.

The end result: a growing, evidence-based list of problems that products could solve, ranked by real demand.

## The Problem

Most product feedback is scattered. Complaints live in Reddit threads, GitHub issues, YouTube comments, and niche forums - invisible to product teams. Meanwhile the tools that could solve those problems never get built.

## What GapFeed Does

1. **Ingests** signals from 12+ sources.
2. **Classifies** each signal with an LLM into category, urgency, and intent.
3. **Clusters** related signals into candidate gaps.
4. **Scores** gaps by heat, confidence, and market size.
5. **Publishes** gap pages with descriptions, opportunities, alternatives, and monetization angles.

## How It Works

1. **Scrapers** fetch posts, comments, and threads from the configured sources.
2. **Filters** remove noise and keep signal-only content.
3. **LLM classifiers** tag each signal with category and urgency.
4. **Clustering engines** group related signals into candidate gaps.
5. **Competitor analysis** checks existing solutions against each gap.
6. **Final scoring** produces a ranked list with actionable insights.

## Architecture

```
+---------------------------+
|      Data Sources (12)   |
|  Reddit · HN · YouTube    |
|  GitHub · DDG · RSS      |
|  SO · Dev.to · GNews · PH|
+-------------+-------------+
              |
+-------------v-------------+
|   Signal Ingestion     |
|  Alex Chen             |
|  Scraper farms         |
|  Rate limiters         |
|  Dedup                 |
|  Cross-source corr.   |
+-------------^-------------+
              |
+-------------v-------------+
|   Analysis Pipeline    |
|  Maya Patel            |
|  LLM classification    |
|  Gap detection         |
+-------------^-------------+
              |
+-------------v-------------+
|     Output + Delivery |
|  Static pages · SEO    |
|  Sitemap · API         |
+------------------+------+
```

### Agent Squad

| Agent | Role | Model | Cycle |
|-------|------|-------|-------|
| **Alex Chen** | Scout, ingests from 12 sources | `mimo-v2.6-flash` | 1s |
| **Maya Patel** | Classifier and gap detector | `mimo-v2.6-flash` | 30s |
| **Sam Zhang** | System monitor and alerts | `mimo-v2.6-flash` | 5 min |
| **Luna Hart** | Marketing, social, blog | `mimo-v2.6-flash` | 1 hour |
| **Jamie Rivera** | Brief synthesizer, on demand | `mimo-v2.6-flash` | On demand |

### Key Components

| Component | Description |
|-----------|-------------|
| `scripts/` | Processing scripts: scrapers, classifiers, exporters, SEO scripts |
| `src/engines/` | Core engines: gap detection, competitor scoring, mention resolution |
| `shared/` | Shared modules: LLM client, analytics, remote DB, signals DB |
| `api/` | PHP API layer: REST endpoints, webhooks, tracking |
| `data/pristine_gaps/` | Verified market gap definitions in JSON |
| `tools/` | Utility tools: signal ingestion, synthesis, swarm orchestration |
| `docs/MASTER.md` | Single source of truth: architecture, decisions, agent specs, data schema |

## Tech Stack

- **Language:** Python 3.11
- **LLM:** Xiaomi Mimo (`mimo-v2.6-flash`) via an OpenAI-compatible endpoint, with an Anthropic-compatible endpoint
- **Database:** MySQL 8.0 in production, SQLite for local backups
- **API:** PHP 8 on IONOS, MySQL proxy with bearer auth
- **Deploy:** SFTP via paramiko
- **Social:** Typefully API v2 for X and LinkedIn
- **Monitoring:** Telegram Bot API

## Cost Model

All agents run on the Xiaomi Mimo token plan using the `mimo-v2.6-flash` model. No paid LLM tier is required. Optional daily and per-call cost caps are supported.

## Getting Started

```bash
git clone <this-repo>
cd gapfeed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure credentials (gitignored, chmod 600)
#   code/config/secrets.env  ->
#   MIMO_API_KEY, MIMO_OPENAI_BASE_URL, MIMO_ANTHROPIC_BASE_URL,
#   GAPFEED_API_KEY, DB_HOST, DB_USER, DB_PASS, DB_NAME,
#   SFTP_*, TELEGRAM_*, TYPEFULLY_*, ...

# Run the full signal ingestion + analysis pipeline
python scripts/gapfeed_engine.py

# Export gap data to JSON
python scripts/export_local_to_astro.py

# Run tests
python -m pytest tests/
```

## Repository Structure

```
gapfeed/
├── api/                 # PHP API layer (db.php, track.php)
├── config/              # Source configs (scout.json, sources.json)
├── content/             # Content assets
├── data/                # Pristine gap definitions, analytics, project notes
├── docs/                # Architecture, master plan, roadmap
├── scripts/             # Scrapers, classifiers, exporters, SEO scripts
├── shared/              # Shared modules (LLM, DB, analytics)
├── src/                 # Engines (gap detection, scoring, resolution)
├── tests/               # Test suite
├── TheRealAgents/       # The agent fleet
├── tools/               # Ingestion, synthesis, swarm tools
├── requirements.txt
├── runtime.txt
└── Procfile
```

## Documentation

- [`docs/MASTER.md`](docs/MASTER.md) - Single source of truth: full architecture, decisions, agent specs, data schema
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - Technical architecture overview
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - Forward plan

## Related

- **Elitza** - Agent profile marketplace at elitza.life
- **OpenConnect** - Browser extension for MCP connector generation

## License

MIT
