#!/usr/bin/env python3
"""
Agent_5 - Marketing & Community Manager
Entry point for the agent.
"""
import sys
import os
import json
import time
import logging
import atexit
from datetime import datetime

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'latest.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('LunaHart')

LOCK_FILE = os.path.join(os.path.dirname(__file__), '..', 'state', '.lock')

def acquire_lock():
    """Singleton lock - prevents duplicate instances."""
    lock_dir = os.path.dirname(LOCK_FILE)
    os.makedirs(lock_dir, exist_ok=True)

    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if old process is still alive
            try:
                os.kill(old_pid, 0)  # Signal 0 = just check if exists
                logger.error(f"Another Agent_5 instance is running (PID {old_pid}). Exiting.")
                sys.exit(1)
            except (OSError, ProcessLookupError):
                # Old process is dead, stale lock
                logger.warning(f"Stale lock file (PID {old_pid} dead). Taking over.")
                os.remove(LOCK_FILE)
        except (ValueError, FileNotFoundError):
            os.remove(LOCK_FILE)

    # Write our PID
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

    # Register cleanup on exit
    atexit.register(release_lock)
    logger.info(f"Lock acquired (PID {os.getpid()})")

def release_lock():
    """Remove lock file on exit."""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                pid = f.read().strip()
            if pid == str(os.getpid()):
                os.remove(LOCK_FILE)
    except Exception:
        pass

def load_config():
    """Load agent configuration."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'base.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Main entry point."""
    acquire_lock()

    logger.info("=== Agent_5 starting ===")
    logger.info("Role: Marketing & Community Manager")
    logger.info("Personality: Warm, strategic, authentic, data-driven")

    config = load_config()
    logger.info(f"Config loaded: {config['agent']}")

    # Import orchestrator
    from orchestrator import Orchestrator

    # Create and start orchestrator
    orch = Orchestrator(config, logger)
    orch.run()

if __name__ == "__main__":
    main()
