"""
Sam Zhang — System Monitor
Entry point: python -m app.main

Usage:
    python -m app.main                    # Start daemon
    python -m app.main --once             # Run one check and exit
    python -m app.main --interval 60      # Override cycle interval
"""

import argparse
import json
import logging
import sys
from pathlib import Path

SAM_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SAM_ROOT))

from app.config import load_config
from app.orchestrator import SamOrchestrator


def setup_logging(config: dict):
    logs_dir = Path(config['paths']['logs_dir'])
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_format = '[%(asctime)s] [Sam Zhang] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(log_format, date_format))
    # Prevent unicode crashes on Windows
    if hasattr(console.stream, 'reconfigure'):
        console.stream.reconfigure(encoding='utf-8')

    file_handler = logging.FileHandler(logs_dir / 'sam.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    error_handler = logging.FileHandler(logs_dir / 'sam_err.log', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, date_format))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.addHandler(error_handler)

    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description='Sam Zhang — System Monitor')
    parser.add_argument('--once', action='store_true', help='Run one check and exit')
    parser.add_argument('--config', type=str, default='prod', help='Config environment')
    parser.add_argument('--interval', type=int, help='Override cycle interval (seconds)')

    args = parser.parse_args()

    config = load_config(args.config)
    if args.interval:
        config['cycle']['sleep_between_cycles'] = args.interval

    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Sam Zhang — System Monitor")
    logger.info("=" * 60)

    orchestrator = SamOrchestrator(config=config)

    if args.once:
        logger.info("Running single check...")
        orchestrator._run_cycle()
        logger.info("Single check complete.")
    else:
        orchestrator.start()


if __name__ == '__main__':
    main()
