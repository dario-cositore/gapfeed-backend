"""
Configuration loader for Jamie Rivera.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Jamie root: 2 levels up from this file
MAYA_DEPTH = Path(__file__).resolve()
for _ in range(2):
    MAYA_DEPTH = MAYA_DEPTH.parent
JAMIE_ROOT = MAYA_DEPTH
CONFIG_DIR = JAMIE_ROOT / 'config'

DEFAULT_CONFIG = {
    'agent': 'Jamie Rivera',
    'role': 'Brief Synthesizer (On-Demand)',
    'vertical': 'general',
    'synthesis': {
        'batch_size': 50,
        'max_signals': 500,
        'include_wants': True,
        'min_urgency': 0.0,
        'top_complaints': 10,
        'top_wants': 10,
    },
    'llm': {
        'model': 'mimo-v2.6-flash',
        'timeout': 120,
        'temperature': 0.1,
        'max_tokens': 8000,
    },
    'paths': {
        'memory_dir': str(JAMIE_ROOT / 'memory'),
        'state_dir': str(JAMIE_ROOT / 'state'),
        'logs_dir': str(JAMIE_ROOT / 'logs'),
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
    
    return config
