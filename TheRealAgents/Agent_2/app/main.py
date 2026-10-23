"""
Agent_2 — Browser-Based Pain Signal Scout
Entry point: python -m app.main

Usage:
    python -m app.main                    # Start daemon
    python -m app.main --once             # Run one round and exit
    python -m app.main --config dev.json  # Use dev config
"""

import argparse
import logging
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from app.config import load_config
from app.orchestrator import JackOrchestrator


def setup_logging(config: dict):
    """Configure logging."""
    logs_dir = Path(config['paths']['logs_dir'])
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_format = '[%(asctime)s] [Agent_2] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(log_format, date_format))

    file_handler = logging.FileHandler(logs_dir / 'jack.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    error_handler = logging.FileHandler(logs_dir / 'jack_err.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, date_format))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.addHandler(error_handler)

    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description='Agent_2 — Browser-Based Pain Signal Scout')
    parser.add_argument('--once', action='store_true', help='Run one round and exit')
    parser.add_argument('--config', type=str, default='base', help='Config environment (base + env override)')
    parser.add_argument('--interval', type=int, help='Override sleep between rounds (seconds)')
    parser.add_argument('--no-llm', action='store_true', help='Skip LLM enrichment (rules only)')

    args = parser.parse_args()

    config = load_config(args.config)

    if args.interval:
        config['round']['sleep_between_rounds'] = args.interval
    if args.no_llm:
        config['enrichment']['skip_llm'] = True

    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Agent_2 — Browser-Based Pain Signal Scout")
    logger.info("=" * 60)

    orchestrator = JackOrchestrator(config=config)

    if args.once:
        logger.info("Running single round...")
        orchestrator._run_round()
        logger.info("Single round complete.")
    else:
        orchestrator.start()


if __name__ == '__main__':
    main()
