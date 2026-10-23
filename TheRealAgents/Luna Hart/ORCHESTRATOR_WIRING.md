# Luna Hart Orchestrator Wiring Briefing

## Task
Wire up the orchestrator.py to actually call all the built modules. Right now the methods are stubs.

## Files to Modify
- `C:\Users\cosit\.openclaw\workspace\tuxo\TheRealAgents\Luna Hart\app\orchestrator.py`

## Modules Available (all built and tested)
- `app/social_manager.py` - SocialManager(config, logger) - Typefully API
- `app/analytics.py` - Analytics(config, logger) - TuXo stats
- `app/trend_scout.py` - TrendScout(config, logger) - Trend detection
- `app/content_engine.py` - ContentEngine(config, logger) - LLM generation
- `app/blog_manager.py` - BlogManager(config, logger) - Blog management
- `app/memory.py` - MemoryManager(memory_dir, logger) - Learning storage

## Shared LLM Client (USE THIS)
- Location: `C:\Users\cosit\.openclaw\workspace\tuxo\shared\llm_client.py`
- Import: `from shared.llm_client import llm_call`
- Function: `llm_call(prompt, system_prompt=None, max_tokens=5000, temperature=0.2, timeout=30)`
- Has auto-fallback from mimo-v2-flash to gemini-2.5-flash-lite on rate limits
- DO NOT duplicate the API key

## Config Structure (from config/base.json)
```json
{
  "agent": "Luna Hart",
  "cycle": {
    "sleep_between_cycles": 3600,
    "trend_scout_interval": 14400
  },
  "social": {
    "typefully_api_key": "${TYPEFULLY_API_KEY}",
    "social_set_id": 292721
  },
  "trends": {
    "sources": ["reddit", "hackernews", "x", "linkedin"],
    "subreddits": ["startups", "SaaS", "entrepreneur", "programming", "SideProject"],
    "alert_threshold": 0.7
  },
  "data": {
    "tuxo_api": "https://gapfeed.com/api/db.php",
    "tuxo_api_key": "${GAPFEED_API_KEY}"
  },
  "llm": {
    "model": "xiaomi/mimo-v2-flash",
    "max_tokens": 2000,
    "temperature": 0.7
  },
  "telegram": {
    "enabled": true,
"bot_token": "${TELEGRAM_BOT_TOKEN}",
    "chat_id": "${TELEGRAM_CHAT_ID}"
  }
}
```

## What Each Method Should Do

### scout_trends()
- Create TrendScout instance
- Call scout_all() to get trends from Reddit/HN
- Save trends to memory/trends.json
- Return list of trending topics

### analyze_data()
- Create Analytics instance
- Get TuXo stats (signal count, gap count)
- Get top posts from memory
- Return data context dict for content generation

### plan_content()
- Check what type of content to create based on:
  - Current trends
  - TuXo data
  - Last content created
  - Content schedule (week 1-4 phases)
- Return content plan dict

### create_content()
- Create ContentEngine instance
- Generate X post, LinkedIn post, or blog based on plan
- Use llm_call from shared client for generation
- Validate output (no em dashes, question ending, topic clarity)
- Return generated content

### schedule_posts()
- Create SocialManager instance
- Schedule posts in Typefully
- Handle X posts (can be threads) and LinkedIn posts (single only)
- Return success/failure

### check_engagement()
- Create Analytics instance
- Get post performance from memory
- Return engagement summary

### learn()
- Create MemoryManager instance
- Update audience insights
- Archive old posts
- Update trends accuracy

## Rules
- NO em dashes in code or comments
- Use shared LLM client (from shared.llm_client import llm_call)
- Handle errors gracefully with try/except
- Log all actions
- Update state after each step
- Use existing logger passed to __init__
