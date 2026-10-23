# GapFeed Roadmap

_Created: 2026-03-30 01:19 CET_
_Author: Elitza (with Dario's vision + competitive analysis input)_

---

## The Vision

**GapFeed is where serious founders start when they ask: "Where is money already flowing toward unsolved pain?"**

We don't generate ideas. We listen at scale.

Every day we scan comments, reviews, and discussions across 16 sources. We cluster real user pain into gaps, attach the actual comments (with clickable permalinks), surface which tools are failing, what substitutes people use, and how much friction they tolerate.

**Core promise:** Verifiable market gaps with receipts. Most idea tools guess or hallucinate. We show the data.

---

## What Makes Us Different

### The Technical Moat

**1. Comment Hunter Pipeline (Agent_2)**
- 10 sources: Reddit comments, YouTube comments, HN threads, Dev.to, SO, Trustpilot reviews, Chrome Web Store reviews, G2, Capterra, blog comments
- Every signal has a clickable permalink to the exact comment/review
- DDG + Yandex search with automatic fallback
- 33,500 signals/day tested yield
- This is the "receipts" that nobody else has

**2. Multi-Agent Intelligence (The Squad)**
- Agent_1: 12 API sources, legal, clean, the fallback
- Agent_2: Comment hunter, volume play, stealth
- Agent_6: LLM classification with pain categories, urgency, buyer intent
- Morgan Blake: Brief synthesizer (on-demand)
- Agent_7: System monitor with Telegram alerts
- Agent_5: Content engine, social presence, blog

**3. Query Performance Ledger**
- Tracks which queries produce the best signals
- 30-day decay, biases toward proven winners
- System gets smarter over time, not just bigger

**4. Cross-Source Correlation**
- Same pain on 2+ sources = 2x urgency boost
- Same pain on 3+ sources = 3x urgency boost
- Catches trends before they're obvious

**5. Competitor Intelligence Pipeline**
- Persistent entity registry (50+ entities, 1818+ mentions)
- Competitor scoring: frequency, authors, negativity, recency, relevance
- Substitutes as first-class data (Excel, manual work, WhatsApp)
- Evidence-only rule: no invented competitor names

### The Data Moat

- 16 sources active (8 comment + 4 review + 4 search engines)
- ~48,000 signals/day combined (Alex + Jack)
- Every signal verifiable via permalink
- Behavioral intent data from gap exploration patterns
- Query ledger learns what works

### The Trust Moat

- Every quote links to the exact comment
- No hallucinated competitor names
- No AI-generated product strategies
- Show the data, let founders connect the dots

---

## Competitive Landscape

### Direct Competitors

| Product | What They Do | Why We're Better |
|---------|-------------|-----------------|
| StartupIdeasDB / BigIdeasDB | Large database of scraped problems + AI blueprints and build guides | We emphasize live feed, real-time heat trends, sparklines, and direct permalinks to source comments/reviews. Less "AI tells you what to build." |
| ProblemHunt / GapHunt | Manual/semi-curated problems, community-oriented | We're automated 24/7, 16 sources, not manual |
| AI Idea Generators | One-shot LLM prompts | We have continuous scanning, real signals, no hallucination |

### Adjacent (Not Competitors)

| Product | What They Do | Why Different |
|---------|-------------|--------------|
| Canny / Featurebase | Customer feedback for existing products | They help companies prioritize features. We discover new markets. |
| Product Hunt | Launch new products | We find problems. They showcase solutions. |

### Our Position

We're not an idea generator. We're not a feedback tool. We're a **pain discovery engine** that shows founders what's broken with receipts.

---

## Roadmap

### Phase 1: Foundation (Q1 2026 - DONE)

- Signal discovery from 16 sources
- LLM classification pipeline (Maya)
- Gap clustering with competitor intelligence
- Free public feed on gapfeed.com
- Comment hunter pipeline (Agent_2)
- Query performance ledger
- Cross-source correlation
- Social content engine (Agent_5)

### Phase 2: Polish & Quality (Q2 2026 - NOW)

**Goal:** Make the data trustworthy and the experience polished.

**Data Quality:**
- Reach 200+ high-quality gaps with balanced sentiment
- Improve gap validity scoring
- Finish data hygiene (staleness detection, archive)
- Optimize Agent_2 yield (verify 33k/day at scale)
- Review scraping at scale (Trustpilot, Chrome Store)

**Visual Polish:**
- Complete Arc Theme implementation
- Self-hosted Outfit + DM Sans fonts
- Better mobile layout
- Improved gap detail pages with competitor cards
- Graphs page: gap velocity charts, category heat maps

**Growth:**
- Launch Weekly Top Gaps newsletter (email signup, no login)
- Agent_5 social content at scale (X threads, LinkedIn, blog)
- SEO hardening for "what should I build" keywords

**Success Metrics:**
- 150-300 gaps (feed feels alive, not sparse)
- 5,000+ monthly visitors
- Strong SEO traction on gap-related keywords
- Positive feedback on gap quality
- Newsletter signup rate >3%

### Phase 3: Verifiable Pain Reports + Signal Evolution (Q3 2026)

**Goal:** Make every gap actionable, and evolve beyond pure complaint-tracking.

**The Shift:** As AI makes building software trivial, the question changes from "what's broken?" to "what's about to break?" and "what do people secretly want but can't articulate?" We need to detect the second-order effects that create new markets.

**Pain Reports (NOT Build Blueprints):**
- Every gap gets a detailed pain report:
  - Real quotes with permalinks (the receipts)
  - Competitor failure analysis (what's broken, why)
  - What users currently pay (pricing data from reviews)
  - What they'd switch to (from comment analysis)
- Morgan Blake generates these on-demand
- NO "MVP scope" or "monetization angles" (LLMs can't do this well)

**Desire Signals (NEW):**
- Current pipeline only tracks *complaints*. Next-gen signals are *desire patterns*.
- People gravitating toward something because of how it feels, not because something is broken.
- Detection method: positive engagement signals (saves, shares, return visits, "I switched to X and love it" patterns)
- New signal type: `desire_signal` alongside existing pain signals
- Maps emotional resonance, not feature gaps
- Source: positive reviews, "I finally found X" comments, recommendation threads

**Rebound Detection (NEW):**
- Perfect solutions create new bizarre problems. Track these second-order effects.
- Example: frictionless dating apps created loneliness. Frictionless banking created gambling.
- Detection method: signals where people praise a tool AND express a negative side effect
  - "I love DoorDash but I never leave my house anymore"
  - "AI writes all my code, now I can't think without it"
  - "Remote work is amazing, but I haven't spoken to a human in 3 days"
- New signal type: `rebound_signal` - catches the negative consequence of a solved problem
- These are the HIGHEST VALUE gaps because they represent markets nobody sees yet
- In 2026, most builders focus on fixing pain. Rebound gaps are where the next unicorns hide.

**Why This Matters:**
Other gap tools find "people complaining about X." We find "X was solved so well it created Y." That's a fundamentally different and more valuable insight. The founder who sees the rebound effect before anyone else builds the solution to a problem that doesn't exist yet but will be massive.

**Personalization Without Login:**
- Saved gaps via local storage (no account needed)
- URL-based watchlists (shareable)
- Smart search: pain + category + trend + source

**Alerts:**
- Email alerts for rising gaps (rate-limited free tier)
- No login required (just email)
- "This gap heated up 3x this week"

**Source Expansion:**
- Add 2-3 more high-signal sources (Quora, niche forums)
- Deepen review scraping (more products, more categories)
- Chrome Web Store: expand beyond current test set

**Success Metrics:**
- 20%+ gaps have full pain reports
- Newsletter open rate >35%
- Alert signup rate >5%
- 10,000+ monthly visitors
- First 100 desire_signal and rebound_signal detections
- Let founders connect the dots from the data

**Personalization Without Login:**
- Saved gaps via local storage (no account needed)
- URL-based watchlists (shareable)
- Smart search: pain + category + trend + source

**Alerts:**
- Email alerts for rising gaps (rate-limited free tier)
- No login required (just email)
- "This gap heated up 3x this week"

**Source Expansion:**
- Add 2-3 more high-signal sources (Quora, niche forums)
- Deepen review scraping (more products, more categories)
- Chrome Web Store: expand beyond current test set

**Success Metrics:**
- 20%+ gaps have full pain reports
- Newsletter open rate >35%
- Alert signup rate >5%
- 10,000+ monthly visitors

### Phase 4: Validation & Revenue (Q4 2026)

**Goal:** Prove value, start monetizing without betraying the free core.

**Validation Layer:**
- Cross-reference gaps with public revenue signals:
  - Pricing page scraping
  - Funding data (Crunchbase, PitchBook public data)
  - Job postings for similar tools
  - App store install counts (where available)
- "This gap has revenue validation" badge on gaps

**Failed Competitors Dashboard:**
- Track tools that tried to solve a gap and failed
- What they did wrong (from reviews and comments)
- Lessons for the next builder

**Monetization (Light):**
- Pro tier (email only, no password):
  - More frequent alerts (hourly vs daily)
  - Advanced pain reports
  - CSV/data export
  - API access (rate-limited)
- Behavioral intent data products:
  - "Top 50 rising pains in dev tools this quarter"
  - Sold to VCs, accelerators, enterprise product teams
  - Aggregated and anonymized

**What We Don't Do:**
- No paywall on the public feed (ever)
- No community submissions (moderation nightmare)
- No "build this" recommendations (hallucination territory)
- No founder matching (separate product, not now)

**Success Metrics:**
- Clear path to sustainability
- First paying customers
- Behavioral data volume sufficient for data products
- 20,000+ monthly visitors

### Phase 5: Scale + Next-Gen Signals (2027+)

**Vertical Expansion:**
- Deep verticals: indie SaaS, dev tools, consumer, healthcare, fintech
- Each vertical gets dedicated agents and sources
- Vertical-specific gap scoring

**Physical Friction Vertical (NEW):**
- Current sources are all digital (Reddit, GitHub, web). Physical-world failures will be the richest data.
- New sources: hardware forums, logistics communities, supply chain discussions, manufacturing subreddits, IoT/robotics communities
- These capture where software has to talk to the physical world: warehousing, bio-tech sensors, hardware devices, grid energy, logistics
- The "atom bugs" - where digital solutions fail in the real world - are unsolved by AI-generated code because they require atoms, not bits

**Agent Telemetry (NEW):**
- As AI agents become the "users" (not humans), pain moves to the protocol/infrastructure layer
- Detection method: analyze where AI agents hit friction, fail to negotiate API calls, or produce errors
- Source: public API error logs, agent-to-agent protocol discussions, MCP/A2A community forums
- This is the furthest horizon but worth tracking now
- By 2027, the gap between "what agents can do" and "what agents struggle with" will be the richest market signal

**Enterprise:**
- Custom vertical scans for VCs and accelerators
- White-labeled gap intelligence
- Private feeds with custom sources

**Premium Content:**
- "Gap of the Month" deep dives
- Category trend reports
- State of Market Gaps quarterly reports

---

## Revenue Streams (Prioritized)

1. **Behavioral Intent Data** (Q4 2026) - Aggregated exploration patterns sold to VCs/accelerators
2. **Pro Tier** (Q4 2026) - Alerts, API, exports, advanced reports
3. **Data Products** (2027) - Quarterly reports, category deep-dives
4. **Enterprise** (2027+) - Custom scans, white-label, private feeds
5. **Partnerships** (2027+) - Sponsored spotlights for validated gaps (clearly labeled)

**Rule:** Core feed stays free forever. Monetization layers on top, never gates the data.

---

## What We Won't Do

- **Auto-generated product strategies.** LLMs hallucinate. We show data, founders decide.
- **Community submissions.** Moderation nightmare, spam magnet. Not before 2027.
- **Login wall on the feed.** Friction kills the "default starting point" positioning.
- **AI idea generation.** We're not a toy. We're an intelligence platform.
- **Everything at once.** One phase at a time, prove each before moving on.

---

## The Questions We Answer

**Original:** "What should I build?"
**Better:** "Where is money already flowing toward unsolved pain?"
**Next:** "What breaks when everything works perfectly?"

The first question is about fixing what's broken (complaints).
The second is about where demand exists (pain + revenue).
The third is about what nobody sees yet (rebound effects + desire patterns).

We answer all three:
1. Find the gap (what's broken)
2. Find the existing solution (what they use now)
3. Find why it sucks (reviews, comments)
4. Find the price point (what they pay)
5. Find the rebound (what the perfect solution broke)
6. Let the founder decide what to build

We provide steps 1-5. The founder does step 6.

---

## Summary

GapFeed is a signal evolution engine, not an idea generator. Our moat is:
- 16 sources with verifiable permalinks
- 48k signals/day from real people
- Competitor intelligence with evidence
- Query ledger that gets smarter over time
- Desire and rebound signal detection (nobody else does this)
- Free feed that drives SEO and behavioral data

The roadmap is: Polish (Q2) -> Pain Reports + Signal Evolution (Q3) -> Validation & Revenue (Q4) -> Scale + Next-Gen Signals (2027+).

Every phase makes the data deeper, not the product broader. And every phase moves us closer to detecting what nobody else can see: the second-order effects that create new markets.
