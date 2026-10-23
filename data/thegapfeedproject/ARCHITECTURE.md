# How GapFeed Works — Architecture Overview

## The Signal Pipeline

GapFeed runs a 4-stage autonomous pipeline that runs continuously:

```
EXTRACT → CLUSTER → CLASSIFY → PUBLISH
```

---

### Stage 1: Extract

We pull user complaints from 16+ sources. Each source has its own extractor:

| Source | What We Pull | Method |
|--------|-------------|--------|
| Reddit | Negative comment threads | reddit API + Pushshift archive |
| YouTube | Comments on product review videos | yt-dlp + API |
| G2 Crowd | 1-3 star reviews | G2 API |
| Hacker News | "Ask HN" / pain threads | Firebase HN API |
| GitHub Issues | Open/closed issues across repos | GitHub API |
| Product Hunt | Negative reviews on launches | PH API |
| Trustpilot | Low-star reviews (in progress) | Trustpilot API |
| App Store (planned) | 1-3 star reviews | App Store API |
| Amazon (planned) | Low-star product reviews | Amazon scraping |

Each extractor normalizes output into a common signal format:
- `content` — the user's complaint (quote)
- `source` — where it came from
- `url` — direct link to original post
- `date` — when the signal was published
- `product` — which product is mentioned (if known)
- `category` — product category (if known)

---

### Stage 2: Cluster

Raw signals feed into a clustering engine that groups related complaints into gaps. We use a two-tier approach:

1. **Pattern-based clustering (zero LLM cost)** — Regex matching on product names, subreddit context, and keyword co-occurrence. Handles the obvious cases.
2. **LLM-assisted clustering** — Gemini 2.5 Flash Lite groups borderline signals and refines pattern-based clusters. Used sparingly to save compute.

Output: A gap page with:
- Gap name (e.g., "Notion LLM Integration Issues")
- Signal count (e.g., 342 signals)
- Pain score (0.0–1.0)
- Opportunity score (0.0–1.0)
- Category and product assignment

---

### Stage 3: Classify

Each clustered gap goes through a quality gate:

- **Gemini verification** — LLM confirms the gap represents real user pain (not spam, not isolated complaints)
- **Duplicate detection** — Merges near-identical gaps
- **Enrichment** — Adds real user quotes, source URLs, and signal metadata

Only verified gaps reach the publish stage. We don't publish noise.

---

### Stage 4: Publish

Verified gaps generate static HTML pages at [gapfeed.com](https://gapfeed.com), hosted on Cloudflare Pages. Each page includes:
- Gap summary and scores
- Top user quotes with source links
- Product and category metadata
- Mobile-optimized layout

---

## Infrastructure

```
┌──────────────────────────────────────┐
│          EXTRACTORS (Local)           │
│  YouTube · G2 · Reddit · HN · GH      │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       STAGING DB (SQLite)             │
│  /data/gapfeed_new.db                 │
│  Primary classification area          │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│     CLUSTERING + GEMINI VERIFY        │
│  Pattern matching → LLM refinement    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│       SERVER DB (Production)          │
│  Clean, verified, ready to show       │
│  (gapfeed.sqlite)                     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   STATIC SITE GENERATOR → PUBLISH     │
│  Cloudflare Pages → gapfeed.com       │
└──────────────────────────────────────┘
```

**Why local staging?** Our server hardware is constrained. Heavy extraction and classification runs locally (unlimited compute), then we push only clean, verified data to the production server. This avoids process kills, keeps costs down, and separates concerns.

---

## Why This Architecture

We tried a distributed multi-agent approach (5+ agents running simultaneously). It broke. Agents competed for resources, created duplicate signals, and made debugging impossible.

The current pipeline is:
- **Sequential** — each stage completes before the next starts
- **Reproducible** — any stage can be restarted independently
- **Cost-efficient** — LLM calls only where they matter

No magic. Just clean data flow.

---

Built by Dario Cositore
Project site: [gapfeed.com](https://github.com/dario-cositore/gapfeed)