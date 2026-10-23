# GapFeed

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Autonomous AI agents that scan the internet 24/7 to discover **market gaps** — underserved problems, frustrated users, and unmet needs — then turn them into actionable product opportunities.

**"Product Hunt, but for problems instead of products."**

## What It Does

GapFeed monitors **Reddit, Hacker News, YouTube, GitHub, and 8+ other sources** to detect:

- **Product gaps** — problems people complain about that no tool solves well
- **Market signals** — rising demand, competitor weaknesses, pricing friction
- **Buyer intent** — people actively searching for solutions that don't exist yet

The system runs **5 autonomous agents** processing **189,000+ signals** and maintains a database of **30+ verified market gaps** across categories like DevTools, E-commerce, Legal, Finance, and Productivity.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Data Sources (12)                    │
│  Reddit · HN · YouTube · GitHub · DDG · RSS     │
│  Stack Overflow · Dev.to · Google News · PH      │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           Signal Ingestion (Alex Chen)           │
│  Scraper farms · Rate limiters · Dedup           │
│  Cross-source correlation · Query ledger         │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│        Analysis Pipeline (Maya Patel)            │
│  LLM classification · Gap detection              │
│  Competitor intelligence · Sentiment scoring     │
│  Mention resolution · Cluster context            │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│         Output & Delivery                        │
│  Static HTML pages · SEO · Sitemap              │
│  Web dashboard · API · Social media             │
│  Telegram alerts · Analytics                    │
└─────────────────────────────────────────────────┘
```

### Agent Squad

| Agent | Role | Model | Cycle |
|-------|------|-------|-------|
| **Alex Chen** | Scout — 12 API sources | `xiaomi/mimo-v2-flash` | 1s |
| **Maya Patel** | Classifier + Gap Detector | `openai/gpt-oss-120b` | 30s |
| **Sam Zhang** | System Monitor + Alerts | `xiaomi/mimo-v2-flash` | 5 min |
| **Luna Hart** | Marketing + Social + Blog | `deepseek/deepseek-v3.2` | 1 hour |
| **Jamie Rivera** | Brief Synthesizer (on-demand) | `xiaomi/mimo-v2-flash` | On-demand |

### Key Components

| Component | Description |
|-----------|-------------|
| `scripts/` | 83 processing scripts — scrapers, classifiers, exporters |
| `src/engines/` | Core ML/NLP engines — gap detection, competitor scoring, mention resolution |
| `shared/` | Shared modules — LLM client, analytics, remote DB, signals DB |
| `api/` | PHP API layer — REST endpoints, webhooks, tracking |
| `data/pristine_gaps/` | 30 verified market gap definitions (JSON) |
| `tools/` | Utility tools — signal ingestion, synthesis, swarm orchestration |
| `docs/MASTER.md` | Single source of truth — full architecture, decisions, agent specs |

## Getting Started

### Prerequisites

```bash
Python 3.11+
pip install -r requirements.txt
```

### Environment Variables

Copy the example config and fill in your values:

```bash
cp config/.env.example config/.env
# Edit config/.env with your API keys
```

Required variables: `LLM_CLASSIFIER_API_KEY`, `GITHUB_TOKEN`, `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID`, `GOOGLE_API_KEY`

### Quick Start

```bash
# Run the full signal ingestion + analysis pipeline
python scripts/gapfeed_engine.py

# Analyze a single URL for gaps
python scripts/_analyze.py --url "https://example.com"

# Export gap data to JSON
python scripts/export_local_to_astro.py

# Run tests
python -m pytest tests/
```

## Data Flow

1. **Scrapers** fetch posts, comments, threads from 12 sources
2. **Filters** remove noise, keep signal-only content
3. **LLM classifiers** tag each signal with category, urgency, intent
4. **Clustering engines** group related signals into candidate gaps
5. **Competitor analysis** checks existing solutions against each gap
6. **Final scoring** produces ranked list with actionable insights

## Tech Stack

- **Language:** Python 3.11+
- **LLM:** Multiple models via OpenRouter (per-agent optimization)
- **Database:** MySQL 8.0 (production) + SQLite (local backup)
- **Frontend:** Astro + vanilla JS (static, SEO-friendly)
- **API:** PHP 8 on IONOS (MySQL proxy with Bearer auth)
- **Deploy:** SFTP via paramiko
- **Social:** Typefully API v2 (X + LinkedIn)
- **Monitoring:** Telegram Bot API

## Documentation

- [`docs/MASTER.md`](docs/MASTER.md) — Single source of truth (1122 lines, all design decisions, agent specs, data schema)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Technical architecture overview
- [`data/thegapfeedproject/`](data/thegapfeedproject/) — Project vision, status, challenges, sponsorship

## Related Projects

- **Elitza** — Agent profile marketplace ([elitza.life](https://elitza.life))
- **OpenConnect** — Browser extension for MCP connector generation

## License

MIT