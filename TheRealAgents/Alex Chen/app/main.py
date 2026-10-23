"""
Alex Chen — General Pain Signal Scout
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

ALEX_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ALEX_ROOT))

from app.config import load_config
from app.orchestrator import AlexOrchestrator


def setup_logging(config: dict):
    """Configure logging."""
    logs_dir = Path(config['paths']['logs_dir'])
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_format = '[%(asctime)s] [Alex Chen] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(log_format, date_format))

    # File handler
    file_handler = logging.FileHandler(logs_dir / 'alex.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Error file handler
    error_handler = logging.FileHandler(logs_dir / 'alex_err.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.addHandler(error_handler)

    # Quiet noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description='Alex Chen — General Pain Signal Scout')
    parser.add_argument('--once', action='store_true', help='Run one round and exit')
    parser.add_argument('--config', type=str, default='prod', help='Config environment (base + env override)')
    parser.add_argument('--interval', type=int, help='Override sleep between rounds (seconds)')
    parser.add_argument('--no-llm', action='store_true', help='Skip LLM enrichment (rules only)')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    if args.interval:
        config['round']['sleep_between_rounds'] = args.interval
    if args.no_llm:
        config['enrichment']['skip_llm'] = True

    # Setup logging
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Alex Chen — General Pain Signal Scout")
    logger.info("=" * 60)

    # Create orchestrator
    orchestrator = AlexOrchestrator(config=config)

    if args.once:
        logger.info("Running single round...")
        orchestrator._run_round()
        logger.info("Single round complete.")
    else:
        orchestrator.start()


if __name__ == '__main__':
    main()
