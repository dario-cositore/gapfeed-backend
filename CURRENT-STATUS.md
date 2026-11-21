# GapFeed — Current Status (2026-10-27)

Read this at the start of any new session, together with `/home/dario/AGENTS.md`.

## 1. Live site

- URL: https://gapfeed.com (Cloudflare Pages, project `gapfeed`, custom domain)
- Repo (private): https://github.com/dario-cositore/gapfeed (branch `main` = production)
- Stack: Astro 6 static site, Cloudflare Pages + Pages Functions
- Last deploy: commit `7de87dc` (manual `wrangler pages deploy dist`)

## 2. Current data (as of 2026-10-27)

- `website/gapfeed.com/gapfeed-astro/public/data/data.json`
- **Signals: 1,907** (857 high-quality)
- **Gaps: 62** (30 pristine + 32 newly clustered/enriched)
- Sitemap: 79 URLs
- Gap pages render full rich fields (the_gap, who_is_affected, existing_solutions, failed_tools, substitutes, opportunity, sample_quotes)

## 3. Monetization (live)

- PayPal donate: `https://www.paypal.com/donate/?business=dario@dariocositore.com&currency_code=USD`
  - Buttons in: Topbar, MobileHeader, sponsor page
- Ko-fi: https://ko-fi.com/L4L41WYHVU
- GitHub Sponsors: https://github.com/sponsors/dario-cositore
- Note: sponsor page copy says "1,907 signals / 62 gaps" (update if numbers change)

## 4. SEO (done)

- Sitemap regenerated (79 URLs, all gap pages)
- og.png (1200x630) + og:image / twitter:card in MainLayout
- WebSite JSON-LD on homepage, Dataset JSON-LD on gap pages
- robots.txt allows all, sitemap linked
- feed.js restored (homepage feed renders)

## 5. Backend (gapfeed-backend)

- Repo: https://github.com/dario-cositore/gapfeed-backend (public), `main`
- Path: `/home/dario/.openclaw/workspace/3. gapfeed/gapfeed`
- LLM: Xiaomi Mimo token plan (fixed subscription), endpoint `https://token-plan-ams.xiaomimimo.com/v1`, model `mimo-v2.6-flash`
- Secrets: `config/secrets.env` (gitignored, chmod 600). Template: `config/secrets.env.example`
- DB: `data/signals.db` (SQLite). Legacy path symlinked: `code/data/gapfeed_unified.db` -> `gapfeed/data/signals.db`
- Key scripts:
  - Farming: `scripts/hn_pain_farm.py`, `scripts/hn_algolia_farm.py` (in /tmp), `scripts/github_farm.py`, `/tmp/yt_api_farm.py` (YouTube Data API v3)
  - Clustering: `scripts/cluster_v3.py`
  - Enrichment: `scripts/enrich_gaps_sonnet.py` (now uses Mimo token plan)
  - LLM client: `shared/llm_client.py`

## 6. Credentials available

- Mimo token plan key: in `config/secrets.env` (tp-... key)
- Google API key (YouTube Data API v3): in `config/secrets.env` (AIza...)
- GitHub token: in `config/secrets.env` (ghp_...)
- PayPal: donate link uses dario@dariocositore.com (no API keys needed)

## 7. What we tried that did NOT work

- YouTube innertube scraper (`comment_farm_local.py`, `youtube_farm_v3.py`): returns 0 comments now (endpoint changed). Use official YouTube Data API v3 instead (`/tmp/yt_api_farm.py`).
- Reddit unauthenticated: blocked (403). Needs Reddit app credentials under Responsible Builder Policy.
- G2/Trustpilot review farms: need review JSON files that were in the deleted `code/` tree (gone).

## 8. Next steps (in priority order)

1. **Grow signal volume** — run `/tmp/yt_api_farm.py` again with rotated search queries (daily, within 10k unit quota). Each run adds ~500-900 signals.
2. **Re-cluster + re-enrich + ship** — after farming: `cluster_v3.py` -> `enrich_gaps_sonnet.py --limit N` -> merge into data.json -> build -> deploy. Script this as a repeatable loop.
3. **YouTube Data API quota** — 10k units/day. Search = 100 units, comments = 1. Current run used ~450 search + ~450 comment = ~900 units. Plenty of room for 3-4x daily runs.
4. **Reddit** — apply under Responsible Builder Policy, or skip. Not blocking.
5. **PayPal Smart Buttons** (optional) — if you want on-site checkout instead of donate link, wire a Cloudflare Function using PAYPAL_CLIENT_ID/SECRET env vars (same pattern as dariocositore.com).
6. **Backend cleanup** — `enrich_gaps_sonnet.py` still references deleted DB path via symlink; works but fragile. Consider updating paths to `data/signals.db` directly.
7. **Enrichment quality** — Mimo v2.6-flash is fast but generic. Consider a second pass with a stronger model for the top 10 gaps by heat score.
8. **Monitoring** — no automated alerts. Consider a cron that checks signal count and re-runs the pipeline weekly.

## 9. How to run the full pipeline

```bash
cd "/home/dario/.openclaw/workspace/3. gapfeed/gapfeed"
set -a; source config/secrets.env; set +a

# Farm
python /tmp/yt_api_farm.py          # YouTube (official API)
python scripts/github_farm.py       # GitHub Issues
python scripts/hn_pain_farm.py     # HN front page

# Cluster
python -c "import sqlite3; c=sqlite3.connect('data/signals.db'); c.execute('DELETE FROM gaps'); c.commit()"
python scripts/cluster_v3.py

# Enrich (Mimo token plan)
python scripts/enrich_gaps_sonnet.py --limit 50

# Export: merge enriched output into data.json (manual merge step)
# Then build + deploy
cd "/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro"
npm run build
wrangler pages deploy dist --project-name=gapfeed --branch=main
```

## 10. Key file locations

| What | Where |
|---|---|
| Live site repo | `/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro` |
| Backend repo | `/home/dario/.openclaw/workspace/3. gapfeed/gapfeed` |
| Signals DB | `gapfeed/data/signals.db` (symlinked from `code/data/gapfeed_unified.db`) |
| Site data | `gapfeed-astro/public/data/data.json` |
| Sitemap | `gapfeed-astro/public/sitemap.xml` |
| Secrets | `gapfeed/config/secrets.env` (gitignored) |
| Secrets template | `gapfeed/config/secrets.env.example` |
| YouTube farm | `/tmp/yt_api_farm.py` |
| Algolia farm | `/tmp/hn_algolia_farm.py` |
| This file | `/home/dario/.openclaw/workspace/3. gapfeed/CURRENT-STATUS.md` |
EOF
echo "written"