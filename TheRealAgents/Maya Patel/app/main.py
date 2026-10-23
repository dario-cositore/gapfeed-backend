"""
Maya Patel — Signal Classifier
Entry point: python -m app.main

Usage:
    python -m app.main                    # Start daemon
    python -m app.main --once             # Run one cycle and exit
    python -m app.main --config dev.json  # Use dev config
    python -m app.main --interval 60      # Override sleep interval
    python -m app.main --no-llm           # Rule-based only (no LLM)
"""

import argparse
import logging
import sys
from pathlib import Path

MAYA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MAYA_ROOT))

from app.config import load_config
from app.orchestrator import MayaOrchestrator


def setup_logging(config: dict):
    """Configure logging."""
    logs_dir = Path(config['paths']['logs_dir'])
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_format = '[%(asctime)s] [Maya Patel] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(log_format, date_format))

    # File handler
    file_handler = logging.FileHandler(logs_dir / 'maya.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Error file handler
    error_handler = logging.FileHandler(logs_dir / 'maya_err.log', encoding='utf-8')
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
    parser = argparse.ArgumentParser(description='Maya Patel — Signal Classifier')
    parser.add_argument('--once', action='store_true', help='Run one cycle and exit')
    parser.add_argument('--config', type=str, default='prod', help='Config environment (base + env override)')
    parser.add_argument('--interval', type=int, help='Override sleep between cycles (seconds)')
    parser.add_argument('--no-llm', action='store_true', help='Skip LLM classification (rules only)')
    parser.add_argument('--batch-size', type=int, help='Override batch size per cycle')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    if args.interval:
        config['cycle']['sleep_between_cycles'] = args.interval
    if args.no_llm:
        config['classification']['enable_llm'] = False
    if args.batch_size:
        config['cycle']['batch_size'] = args.batch_size

    # Setup logging
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Maya Patel — Signal Classifier")
    logger.info("=" * 60)

    # Create orchestrator
    orchestrator = MayaOrchestrator(config=config)

    if args.once:
        logger.info("Running single cycle...")
        orchestrator._run_cycle()
        logger.info("Single cycle complete.")
    else:
        orchestrator.start()


if __name__ == '__main__':
    main()
