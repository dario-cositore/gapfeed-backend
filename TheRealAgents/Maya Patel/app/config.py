"""
Configuration loader for Maya Patel.

Loads from config/base.json, overrides with config/prod.json or config/dev.json.
Environment variables can override any config key.
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Maya root: 2 levels up from this file (app/config.py -> app/ -> Maya Patel/)
_MAYA_DEPTH = Path(__file__).resolve()
for _ in range(2):
    _MAYA_DEPTH = _MAYA_DEPTH.parent
MAYA_ROOT = _MAYA_DEPTH
CONFIG_DIR = MAYA_ROOT / 'config'

DEFAULT_CONFIG = {
    'agent': 'Maya Patel',
    'role': 'Signal Classifier',
    'vertical': 'general',
    'always_on': True,

    'cycle': {
        'sleep_between_cycles': 30,
        'batch_size': 10,
        'max_llm_calls_per_cycle': 10,
        'max_cycle_minutes': 10,
    },

    'classification': {
        'min_text_length': 50,
        'confidence_threshold': 0.4,
        'enable_llm': True,
    },

    'rate_limits': {
        'llm_calls_per_hour': 100,
    },

    'memory': {
        'checkpoint_enabled': True,
        'stats_log_interval': 10,
    },

    'llm': {
        'model': 'mimo-v2.6-flash',
        'timeout': 120,
        'temperature': 0.1,
        'max_tokens': 10000,
    },

    'paths': {
        'memory_dir': str(MAYA_ROOT / 'memory'),
        'state_dir': str(MAYA_ROOT / 'state'),
        'logs_dir': str(MAYA_ROOT / 'logs'),
    },

    'gap_detection': {
        'enabled': True,
        'run_every_n_cycles': 3,
        'batch_size': 500,
        'min_cluster_size': 2,
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
    1. Environment variables (MAYA_*)
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

    # Environment variable overrides (MAYA_CYCLE__SLEEP_BETWEEN_CYCLES -> cycle.sleep_between_cycles)
    for key, value in os.environ.items():
        if not key.startswith('MAYA_'):
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
