# Challenges — The Honest Version

If you're here, you probably want to know what's hard. Not the pitch deck version. The real one.

---

## 🔴 Unresolved

### 1. The "Other/Other" Backlog

Our clustering pipeline leaves signals without a clear product match in a bucket called "Other / Other Issues."

**Why it happens:** Some users don't name the product. Some complaints are about workflows, not tools. Some subreddits cover multiple industries. The initial classifier can't infer the product from context alone.

**Work in progress:** Pattern-based extraction using subreddit names, keyword co-occurrence, and source context. Zero LLM cost. Should recover thousands of signals into proper product gaps.

### 2. LLM Compute Dependency

Our classification pipeline uses 5 autonomous agents with optimized LLM models. The models cost money per call. We process hundreds of thousands of signals. We have zero revenue.

**The loop:** We need compute to produce good data. We need good data to attract users/partners. We need users/partners to earn revenue. We need revenue to pay for compute.

**The ask:** This is why we're seeking LLM sponsorship. See [SPONSORSHIP.md](SPONSORSHIP.md).

### 3. Source Diversity Bias

Our data is heavily skewed toward SaaS/B2B products. That's because Reddit, HN, and GitHub are SaaS-heavy platforms.

A founder in healthcare, real estate, education, or consumer goods will find less relevant data. We know this. We're actively adding:
- App Store reviews (1-3 star)
- Trustpilot reviews
- Amazon low-star reviews
- IndieHackers discussions
- Open platforms of professional experts

### 4. Agent_2 (Browser Scout) — Under Reconstruction

Browser-based search (DDG, Google, Brave) all block headless browsers with captchas. Playwright/Chromium processes leak memory (2+ GB per instance). Jack's role is being redefined — options include content deep-dive on URLs from Alex's signals, niche site specialist, or LLM classifier for signal enrichment.

---

## 🟡 Solved (but worth knowing)

### Multi-Agent Coordination

**What was tried:** Running 5+ agents simultaneously on underpowered hardware.
**What broke:** Agents competed for resources, created duplicate signals, interleaved logs made debugging impossible.
**What we did:** Each agent runs independently with its own cycle, checkpoint/restore capability, and dedicated LLM model. Agents coordinate through the shared database, not direct communication. Result: faster, cheaper, reliable.

### Database Schema Mismatch

**What was:** Staging DB had 30 columns. Server DB had 31 (extra `id` auto-increment). INSERT statements failed every time.
**What we did:** Switched to explicit column-name INSERTs that skip the auto-increment field. Fixed.

### Content Filter Blockages

**What was:** Upstream AI models (OpenRouter) blocked content for certain creative/dramatic work.
**What we did:** For non-gapfeed work, we switched to generating clean HTML instead of PDFs, bypassing both system limitations and content filters.

---

## The Honest Takeaway

GapFeed's core thesis is sound. The pipeline works. The data is real. We have 189,000+ signals, 30+ verified gaps, 5 autonomous agents, and a live website.

What holds us back isn't the idea — it's compute cost and infrastructure. Both are solvable with the right resources.

---

Built by Dario Cositore
Project site: [gapfeed.com](https://gapfeed.com)
GitHub: [github.com/dario-cositore/gapfeed](https://github.com/dario-cositore/gapfeed)