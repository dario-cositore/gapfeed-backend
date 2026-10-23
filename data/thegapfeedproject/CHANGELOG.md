# Changelog

All notable changes to GapFeed.

## 2026-04-07

### Added
- Pattern-based keyword clustering for "Other/Other" signal classification (zero LLM cost)
- Voice specification for TTS integration (Elitza voice profile)
- Documentation site (`thegapfeedproject/` directory)

### Changed
- Switched all classification to `google/gemini-2.5-flash-lite` (50% cost reduction vs Gemini 3.1, same accuracy)
- Killed all legacy server agents (Alex, Maya, Sam, Jack, Morgan, Luna) — replaced with single pipeline
- Moved signal extraction from server to local execution (avoids server overload and process killing)

### Fixed
- Schema mismatch when copying from staging to server DB (30 values → 31 columns; now using explicit column names)
- 3,303 orphan signal gap_ids reassigned during cleanup
- 353 empty-content signals removed

---

## 2026-04-06

### Added
- Server DB cleared and refilled with 20,026 verified signals, 154 gaps
- Pattern-matching clustering: went from 154 → 242 gaps, 33,041 signals clustered (88 new gaps created)
- Push to production: server now has 39,509 signals, 242 gaps

### Changed
- Pipeline architecture: Extraction → Clustering → Quality Gate (sequential, not parallel agents)
- Staging DB (`gapfeed_new.db`) as primary classification area; Server DB as production showroom
- Gap template with pulsing animation, mobile/desktop-friendly icons

### Infrastructure
- Server outage began (192.168.1.91 unreachable since April 4)
- MailerSend trial limit hit on unique recipient cap

---

## 2026-04-05

### Added
- Multi-source extractors: YouTube (`yt_farm.py`), HN (`hn_pain_farm.py`), GitHub (`github_farm.py`), G2 (`g2_farm_local.py`)
- Elitza V2 with brain system at 127.0.0.1:9998
- Memory structure: daily files, MEMORY.md, brain/, cortex.db
- 164,403 signals pulled from server for local processing
- Gap enrichment: real quotes, categories, cleaned slugs
- Autonomous Alex loop (runs every 4 hours)
- Pipeline successful run: 24,885 new signals in 1 hour
- G2 signals cleaned and re-extracted (56 negative-only reviews with real URLs)
- Exact server schema mapped (31 columns, signals table)
- Local schema-matched DB initialized

### Testing
- LLM model evaluation across 5 models tested
- Gemini 3.1 achieved perfect separation on pain signal classification
- Qwen 3.5 vs Gemini comparison showed only 67% agreement

---

## 2026-04-04

### Added
- Initial GapFeed setup with 5-agent architecture (Alex, Maya, Sam, Jack, Morgan)
- Outbound outreach Campaign 1 (5 emails: Intel, Baratza, Sony, Fellow, Samsung)
- Batch 2 prepped (7 leads: Shopify, Stripe, PayPal, Google Cloud, Anthropic, Cloudflare, OpenAI)
- Newsletter infrastructure via Buttondown
- 6 cron jobs including content growth cycle every 4 hours
- Gapfeed.com live on Cloudflare Pages
- 169 gaps identified, 50+ from initial clustering

### Website content
- Blog posts: "We Paid $50/Rerank Call. Gemini Does It Better" + "Gemini Flash Lite Crushed Benchmarks"
- Trending products tracked: VisaJourney (37), Shopify (19), Freelance (15), DACA (11), Notion (6)

---

## Technical Notes

### Why we moved away from agents
The multi-agent approach was ambitious but fragile. Agents ran simultaneously, competed for resources, created duplicates, and were hard to debug. A single sequential pipeline is faster, more reliable, and uses fraction the compute.

### Why we moved extraction local
The server can't handle heavy concurrent processes. It kills them. Running extraction locally avoids the kill, and we push clean results to server.

### Why Gemini
We tested everything. Gemini 2.5 Flash Lite gives us the accuracy of GPT-4 level models at a fraction of the cost. The tradeoff is we're dependent on having API access. That's the sponsorship ask.

---

Built by Dario Cositore
Intelligence Lead: Elitza Petrova
