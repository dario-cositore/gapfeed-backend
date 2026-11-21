# GapFeed - Project Notes (read me first, every session)

> **SUPERSEDED for current state:** read `CURRENT-STATUS.md` in this same folder first (updated 2026-10-27). This file is the 2026-10-17 sanitize-era note; still useful for folder structure/history.

_Last updated: 2026-10-17. Written by the OpenCode session after the big sanitize day._

This file is the continuity note for future sessions. Read this before touching anything.
The old source of truth `code/docs/MASTER.md` is from the TuXo/IONOS era (last touched May) and
partly outdated - this note + the structure below is the current truth.

---

## 1. What this project is

**GapFeed** = market gap discovery feed ("Product Hunt, but for problems instead of products").
Agents scan 12-16 sources, LLM-classify pain signals, cluster them into gaps, publish every gap
as an SEO page on **gapfeed.com**. Free product; monetization plan = behavioral intent data + Pro
tier later (see `code/docs/ROADMAP.md` - still valid vision-wise).

- Live site: https://gapfeed.com (Cloudflare Pages, connected to GitHub)
- Website repo (private): https://github.com/dario-cositore/gapfeed
- End goal: eventually publish a **separate, fully sanitized public repo** of the whole system so
  people can fork it - only after everything is polished. The website repo stays private.

---

## 2. Current folder structure (post-sanitize, 2026-10-17)

```
3. gapfeed/
├── code/                  # THE codebase. Fresh git (main branch, 3 clean commits, no remote yet)
│   ├── api/               # PHP MySQL proxy (db.php, track.php). Creds via config.local.php (gitignored)
│   ├── config/            # secrets.env = ALL real credentials (gitignored, chmod 600)
│   ├── TheRealAgents/     # 7 agents: Alex Chen, Maya Patel, Sam Zhang, Luna Hart,
│   │                      #   Jamie Rivera, Jack Morgan (paused), Jake Morgan
│   ├── scripts/ shared/ src/ tests/ tools/ content/ data/ docs/ memory/ reports/
│   └── data/gapfeed_unified.db   # 189MB live SQLite dataset (gitignored)
├── website/               # Astro site (git repo -> github.com/dario-cositore/gapfeed, Cloudflare Pages)
│   └── gapfeed.com/gapfeed-astro/
└── .git-backups/          # backend-history-2026-10-17.bundle (14MB OLD git history - contains
                           #   ALL the old secrets in plaintext. Keep private. Delete after rotations.)
```

Old folders (`4. Backend` with its dirty git, `4. Repo`, `.archive`, `1. Income`, `3. Sidecar`)
are GONE - quarantined to `/tmp/opencode/gapfeed-trash-2026-10-17/` (wiped on reboot).

---

## 3. What we did on 2026-10-17 (sanitize session)

1. **Reunified the split repo**: old `4. Repo` (newer code + agents, no .git) became the base of
   `code/`; merged in `4. Backend`'s `api/`, `config/`, `memory/`, `reports/`, the 189MB db, and
   blog posts missing from the Repo copy.
2. **Fresh git init** on `code/` (old history archived as bundle in `.git-backups/`). Old `.git`
   was 64MB with secrets + committed logs; new one is ~2MB.
3. **Scrubbed ALL secrets from working tree + git history**:
   - Python scripts/agents: all keys now via env vars (`OPENROUTER_API_KEY`, `GAPFEED_API_KEY`,
     `DB_*`, `SFTP_PASSWORD`, `IONOS_SFTP_*`, `TELEGRAM_*`, `TYPEFULLY_API_KEY`)
   - PHP `api/db.php` + `track.php`: creds moved to `api/config.local.php` (gitignored, chmod 600,
     deploy it to IONOS manually - it is NOT in git)
   - Docs (MASTER.md, ARCHITECTURE.md, GapFeed-Master-Plan.html): placeholders only
   - Killed: `config/agency.config.json` (dead agency pipeline, referenced by nothing),
     `db.php.bak/.tmp`, `docs/db_remote.php`, `db_verify.php`, `temp.js`, all agent logs
4. **Fixed bugs from a previous botched scrub** (May 14): 3 files had the literal string
   `os.environ.get("SFTP_PASSWORD", "")` as password VALUE (also syntax errors). All compile now.
5. **Stripped the GitHub PAT** (`ghp_Vg2o7...`) from the astro remote URL. Astro git history was
   verified clean (0 secrets).
6. **Verified**: final scans over 14 secret patterns = only `config/secrets.env` +
   `api/config.local.php` hold real values (both gitignored, chmod 600). Git-tracked = 100% clean.

## 4. DARIO'S PENDING ACTIONS (ask about these next session!)

- [ ] **REVOKE classic GitHub PAT `ghp_Vg2o7...`** (was embedded in astro remote URL for months)
- [ ] Decide on fine-grained `github_pat_11ADC...` (dead agency pipeline era, parked in secrets.env)
- [ ] Rotate when convenient (never left this machine, but old history sits in the bundle):
      3x OpenRouter keys, IONOS password (covers MySQL + SFTP + EMAIL), Telegram bot token,
      Typefully key. After rotation: update `code/config/secrets.env` + `api/config.local.php`,
      redeploy db.php/track.php to IONOS, then delete `.git-backups/` bundle.

## 5. Next session - the plan

1. **Website evaluation** (was about to start):
   - Astro still the right choice? Site is static + data.json driven, on Cloudflare Pages.
     Candidates: keep Astro, plain static + CF Workers, Next/OpenNext on CF, etc.
   - Astro repo has **uncommitted changes**: `public/data/data.json` (+634/-1645 lines, made ~May 14,
     never pushed - check if it matches live site) + modified package-lock.
   - Mystery `api-server/` in astro repo (untracked: Node server.js + own gapfeed.db) - Dario said
     KEEP for now, evaluate in this phase.
   - Astro repo also has agentic SEO stuff (functions/, middleware, webmcp) - newest work (Apr 27).
2. **Fix stale paths**: export scripts (`code/scripts/export_*_astro.py`,
   `export_pristine_to_astro.py`) point to old layout (`workspace/gapfeed/...`, `gapfeed_new.db`
   which was quarantined). Canonical paths now: db = `code/data/gapfeed_unified.db`,
   site = `website/gapfeed.com/gapfeed-astro/`. Decide the canonical data pipeline
   (pristine_gaps JSON vs unified DB) and write ONE clean export+deploy script (replaces the dead
   `update_astro_site.sh`).
3. **Update `code/docs/MASTER.md`** to current reality (Astro/Cloudflare era, not tuxo.it/IONOS
   static pages; env-based config; new folder layout). ARCHITECTURE.md is stale too.
4. **Decide the agents' future**: nothing runs on this machine (they were built for Dario's
   Windows box). Options: revive here as daemons, port to a scheduler, or slim down.
5. Jack Morgan still "under reconstruction" (search engines captcha-block headless browsers);
   Jake Morgan = gap validator. Roles need redefinition.
6. When everything is polished -> create the **public forkable repo** (fresh, sanitized history).

## 6. Random but important facts

- Working convention: quarantine trash to /tmp/opencode instead of rm (no trash-cli installed).
- Secrets convention: `config/secrets.env` (shell: `set -a; source config/secrets.env; set +a`),
  agents read env natively (`TheRealAgents/*/app/config.py` expands `${VAR}` in base.json).
- The 189MB db, node_modules, dist/, logs, agent state/memory are all gitignored in `code/`.
- Never use em dashes in user-facing GapFeed content (project-wide rule, hyphens only).
- Luna Hart posts only T+1 drafts via Typefully, Dario approves via Telegram callbacks.
- Old brand was "TuXo" (tuxo.it, redirects to gapfeed.com) - if you see tuxo references, that's why.
