import os

# ==========================================
# GAPFEED CENTRAL CONFIGURATION
# ==========================================

# --- MODELS ---
FAST_MODEL = "mimo-v2.6-flash"
REASONING_MODEL = "mimo-v2.6-flash"

# --- PATHS ---
DB_PATH = "/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db"

# --- SECRETS ---
# OpenRouter API key — set via environment variable
# export OPENROUTER_API_KEY=sk-or-...
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")