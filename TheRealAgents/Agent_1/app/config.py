"""
Configuration loader for Agent_1.

Loads from config/base.json, overrides with config/prod.json or config/dev.json.
Environment variables can override any config key.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# File: tuxo/TheRealAgents/Agent_1/app/config.py
# Need: Agent_1 dir (2 levels up from __file__)
_DEPTH = Path(__file__).resolve()
for _ in range(2):
    _DEPTH = _DEPTH.parent
ALEX_ROOT = _DEPTH
CONFIG_DIR = ALEX_ROOT / 'config'

DEFAULT_CONFIG = {
    'agent': 'Agent_1',
    'role': 'General Pain Signal Scout',
    'vertical': 'general',
    'always_on': True,

    'round': {
        'sleep_between_rounds': 60,
        'max_raw_signals_per_round': 60,
        'max_llm_calls_per_round': 15,
        'max_round_minutes': 15,
        'min_marginal_yield': 0.08,
    },

    'enrichment': {
        'min_confidence': 0.5,
        'skip_llm_if_confidence_above': 0.7,
        'max_signals_per_round': 50,
    },

    'rate_limits': {
        'web_search_per_hour': 30,
        'reddit_requests_per_minute': 25,
        'hn_requests_per_minute': 60,
        'llm_calls_per_hour': 20,
    },

    'sources': {
        'web_search': True,
        'reddit': True,
        'hackernews': True,
        'rss': True,
    },

    'memory': {
        'review_interval': 10,
        'journal_max_lines': 3000,
        'checkpoint_enabled': True,
    },

    'llm': {
        'model': 'mimo-v2.6-flash',
        'timeout': 120,
        'temperature': 0.1,
        'max_tokens': 2000,
    },

    'paths': {
        'memory_dir': str(ALEX_ROOT / 'memory'),
        'state_dir': str(ALEX_ROOT / 'state'),
        'logs_dir': str(ALEX_ROOT / 'logs'),
    },

    'api_keys': {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(env: str = 'prod') -> dict:
    """
    Load configuration.

    Priority (highest wins):
    1. Environment variables (ALEX_*)
    2. config/{env}.json
    3. config/base.json
    4. DEFAULT_CONFIG
    """
    config = DEFAULT_CONFIG.copy()

    # Load base.json
    base_path = CONFIG_DIR / 'base.json'
    if base_path.exists():
        try:
            with open(base_path) as f:
                config = _deep_merge(config, json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load base.json: {e}")

    # Load env-specific config
    env_path = CONFIG_DIR / f'{env}.json'
    if env_path.exists():
        try:
            with open(env_path) as f:
                config = _deep_merge(config, json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load {env}.json: {e}")

    # Environment variable overrides (ALEX_ROUND__SLEEP_BETWEEN_ROUNDS → round.sleep_between_rounds)
    for key, value in os.environ.items():
        if not key.startswith('ALEX_'):
            continue
        parts = key[5:].lower().split('__')
        d = config
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        # Type coercion
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        d[parts[-1]] = value

    return config
