"""Configuration loader for Agent_3."""

import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent

def load_config() -> dict:
    """Load configuration from config/base.json."""
    config_path = AGENT_ROOT / 'config' / 'base.json'
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Resolve relative paths
    for key in ['memory_dir', 'state_dir', 'logs_dir']:
        if key in config.get('paths', {}):
            config['paths'][key] = str(AGENT_ROOT / config['paths'][key])
    
    return config
