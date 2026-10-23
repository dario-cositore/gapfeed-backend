# Changelog

What changed, when, and why.

---

## 2026-05-14

| Change | Impact |
|--------|--------|
| Rebranded from TuXo to GapFeed | All 213 HTML files, agent configs, shared modules updated |
| 5-agent architecture fully operational | Alex Chen (Scout), Maya Patel (Classifier), Sam Zhang (Monitor), Luna Hart (Marketing), Jamie Rivera (Briefs) |
| Competitor intelligence pipeline launched | 3-layer architecture: mention resolver → cluster context builder → gap detector |
| Signals processed: 189,000+ | Across 12 sources with cross-source correlation |
| Public repo prepared | Sanitized and documented for GitHub release |

## 2026-04-07

| Change | Impact |
|--------|--------|
| Voice spec created for TTS integration (Elitza profile) | Foundation for voice-based output and podcast-style gap summaries |
| Pattern-based "Other" classifier work began | Zero-cost solution for the signal backlog |
| Documentation project created (`thegapfeedproject/`) | Public-facing project story, challenges, and sponsorship ask |

## 2026-04-06

| Change | Impact |
|--------|--------|
| Server DB cleared and refilled with 20K+ verified signals | Clean slate, no duplicates, schema-correct data |
| Pattern-matching clustering: 154 → 242 gaps (+88 gaps) | Recovered thousands of signals from the "Other" pile |
| Pushed 39,509 signals + 242 gaps to production server | Live production data updated |
| 3,303 orphan signal gap_ids fixed | Database integrity restored |
| 353 empty-content signals removed | No junk data in production |

## 2026-04-05

| Change | Impact |
|--------|--------|
| Multi-source extractors built: YouTube, HN, GitHub, G2, Reddit | 16 data sources feeding the pipeline |
| Pipeline rebuilt: sequential, not agents | No more competing processes, no more duplicates |
| 164,403 signals pulled from server for local processing | Full dataset available locally for re-clustering |
| G2 signals cleaned: 56 negative-only reviews with real URLs | High-quality, verified pain signals |
| Elitza V2 brain system initialized (port 9998) | Autonomous intelligence layer |
| Memory system structure created (daily files, MEMORY.md, brain/) | Knowledge persistence across sessions |
| Gemini 3.1 tested: perfect accuracy at lower cost | Chosen as primary classifier |
| Staging DB initialized with exact server schema (31 columns) | Local → Server data flow now works correctly |
| Autonomous Alex loop created (runs every 4 hours) | Continuous signal collection |

## 2026-04-04

| Change | Impact |
|--------|--------|
| Initial GapFeed setup with 6-agent architecture | Foundation laid (later abandoned for pipeline approach) |
| Outbound outreach Campaign 1 created | 5 emails sent to Intel, Baratza, Sony, Fellow, Samsung |
| Batch 2 prepped (7 more leads) | Shopify, Stripe, PayPal, Google Cloud, Anthropic, Cloudflare, OpenAI |
| Newsletter via Buttondown configured | Email content distribution ready |
| Gapfeed.com live on Cloudflare Pages | Public showroom deployed |
| 169 gaps identified, 50+ from initial clustering | First round of market intelligence |
| Blog posts published: "We Paid $50/Rerank Call" + "Gemini Benchmarks" | SEO and authority building |
| Trending products tracked: VisaJourney (37), Shopify (19), Freelance (15) | Early signal of where demand concentrates |

---

## Architecture Decisions

### Why 5 Agents Instead of a Single Pipeline

We evolved from a single-pipeline approach to a 5-agent architecture. Each agent has a dedicated role, its own LLM model optimized for its task, and independent checkpoint/restore capability:

- **Alex Chen** (Scout) — 12 API sources, 1s cycle, `mimo-v2-flash` for speed
- **Maya Patel** (Classifier) — LLM classification + gap detection, `gpt-oss-120b` for throughput
- **Sam Zhang** (Monitor) — Health checks + Telegram alerts, `mimo-v2-flash`
- **Luna Hart** (Marketing) — Social + blog + trends, `deepseek-v3.2` for creative quality
- **Jamie Rivera** (Briefs) — On-demand brief synthesis, `mimo-v2-flash`

Agents coordinate through the shared MySQL database, not direct communication. This means any agent can crash without affecting the others, and each can be restarted independently from its last checkpoint.

### Why Local Execution Over Server

The server kills processes that exceed memory limits. Extraction and clustering are memory-heavy. Running locally (on a machine with real resources) and pushing clean results to the server solved the kill problem entirely.

### Why Multiple LLM Models

We tested 13+ models across 100+ workflows. Different agents have different needs:
- Maya needs throughput (50+ classifications/cycle) → `gpt-oss-120b`
- Luna needs creative quality → `deepseek-v3.2`
- Everyone else needs cost-effective reliability → `mimo-v2-flash`

---

## Signal Growth Timeline

| Date | Signals | Gaps | Notes |
|------|---------|------|-------|
| 2026-04-03 | ~167,453 | 352 | Initial messy server dump (many duplicates, junk content) |
| 2026-04-04 | ~50,000 | 169 | Cleaned and re-clustered |
| 2026-04-05 | ~24,885 | 154 | Fresh pipeline, quality-gated extraction |
| 2026-04-06 | 39,509 | 242 | Pattern clustering added 88 gaps |
| 2026-04-07 | 39,509 | 252+ | Ongoing "Other" recovery work |
| 2026-03-29 | 189,000+ | 30+ | 5-agent architecture, competitor intelligence pipeline |

---

Built by Dario Cositore
Project site: [gapfeed.com](https://gapfeed.com)
GitHub: [github.com/dario-cositore/gapfeed](https://github.com/dario-cositore/gapfeed)