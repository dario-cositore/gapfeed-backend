"""
Configuration loader for Agent_7.
"""
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Sam root: 2 levels up from this file
_DEPTH = Path(__file__).resolve()
for _ in range(2):
    _DEPTH = _DEPTH.parent
SAM_ROOT = _DEPTH
CONFIG_DIR = SAM_ROOT / 'config'

DEFAULT_CONFIG = {
    'agent': 'Agent_7',
    'role': 'System Monitor',
    'vertical': 'general',

    'cycle': {
        'sleep_between_cycles': 300,
        'alert_threshold_stale_minutes': 30,
    },

    'monitors': {
        'agents': {
            'enabled': True,
            'expected_agents': ['Agent_1', 'Agent_6'],
            'check_logs': True,
            'log_max_age_minutes': 15,
        },
        'server': {
            'enabled': True,
            'url': 'https://gapfeed.com/api/stats',
            'timeout': 15,
        },
        'database': {
            'enabled': True,
            'api_url': 'https://gapfeed.com/api/db.php',
            'api_key': '${GAPFEED_API_KEY}',
        },
        'system': {
            'enabled': True,
            'check_disk': True,
            'check_processes': True,
        },
    },

    'llm': {
        'model': 'mimo-v2.6-flash',
        'timeout': 30,
        'temperature': 0.2,
        'max_tokens': 2000,
        'enabled': True,
    },

    'paths': {
        'memory_dir': str(SAM_ROOT / 'memory'),
        'state_dir': str(SAM_ROOT / 'state'),
        'logs_dir': str(SAM_ROOT / 'logs'),
    },

    'api_keys': {},
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(env: str = 'prod') -> dict:
    config = DEFAULT_CONFIG.copy()

    base_path = CONFIG_DIR / 'base.json'
    if base_path.exists():
        try:
            with open(base_path) as f:
                config = _deep_merge(config, json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load base.json: {e}")

    env_path = CONFIG_DIR / f'{env}.json'
    if env_path.exists():
        try:
            with open(env_path) as f:
                config = _deep_merge(config, json.load(f))
        except Exception as e:
            logger.warning(f"Failed to load {env}.json: {e}")

    # Env var overrides
    for key, value in os.environ.items():
        if not key.startswith('SAM_'):
            continue
        parts = key[3:].lower().split('__')
        d = config
        for part in parts[:-1]:
            d = d.setdefault(part, {})
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
