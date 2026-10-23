#!/usr/bin/env python3
"""Launch script for Jake Morgan."""

import logging
import sys
from pathlib import Path

# Setup logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

log_file = log_dir / f'jake_{Path(__file__).stem}.log'

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [Jake Morgan] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        from app.orchestrator import JakeOrchestrator
        orchestrator = JakeOrchestrator()
        orchestrator.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
