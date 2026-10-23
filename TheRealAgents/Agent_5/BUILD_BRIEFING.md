# Agent_5 Build Briefing

## Agent Identity
- Name: Agent_5
- Role: Marketing & Community Manager
- Personality: Warm, strategic, authentic, data-driven, proactive
- Voice: Direct, human, never uses em dashes, always real data

## Directory
`C:\Users\cosit\.openclaw\workspace\tuxo\TheRealAgents\Agent_5\`

## Existing Files
- SPEC.md - Full specification (read this first!)
- config/base.json - Agent configuration
- app/main.py - Entry point
- app/orchestrator.py - State machine with 7 states
- app/__init__.py
- memory/ - JSON files for audience, content_log, trends, blog_log
- state/current.json

## APIs to Use

### Typefully API
- Base: https://api.typefully.com/v2
- Auth: Bearer {API_KEY}
- Social Set ID: 292721
- API Key: ${TYPEFULLY_API_KEY}
- Endpoints:
  - GET /social-sets/{id}/drafts?limit=50 - List drafts
  - POST /social-sets/{id}/drafts - Create draft
  - PATCH /social-sets/{id}/drafts/{draft_id} - Update draft
  - DELETE /social-sets/{id}/drafts/{draft_id} - Delete draft
- Create body: {"platforms": {"x": {"enabled": true, "posts": [{"text": "..."}]}}, "publish_at": "ISO8601", "draft_title": "..."}
- LinkedIn: always single post (no threads)
- X: supports threads (multiple posts array)

### TuXo API
- Base: https://gapfeed.com/api/db.php
- Auth: Bearer ${GAPFEED_API_KEY}
- Actions: ?action=stats, ?action=gaps, ?action=signals

### LLM
- Model: xiaomi/mimo-v2-flash (via openrouter)
- Max tokens: 2000
- Temperature: 0.7

### Existing social scripts
- C:\Users\cosit\.openclaw\workspace\tuxo\social\_post_loader.py - Post cleaning utility
- C:\Users\cosit\.openclaw\workspace\tuxo\social\typefully_helper.py - Typefully helper functions

## Real Data
- Dario's resume: OpenAI/Google/Meta/Scale AI evaluator, 30+ team lead, 45% conversion
- TuXo: 6,408+ signals, 53+ gaps, 7 sources
- MiMo-V2-Flash: Intelligence Index 41.5, $0.09/M tokens
- Blog articles: 13 existing posts on dariocositore.com

## Rules
- NEVER use em dashes in any output
- Always use real data, never fabricate
- Keep files clean and well-documented
- Follow existing agent patterns (Agent_1, Agent_6, etc.)
- Each module should be self-contained and testable
