"""
Sam Zhang daemon launcher.
Starts Sam as a background process that auto-restarts on crash.
"""

import subprocess
import sys
import time
import logging
from pathlib import Path

SAM_DIR = Path(__file__).resolve().parent
LOGS_DIR = SAM_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / 'launcher.log'

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [Launcher] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

MAX_RESTARTS = 10
RESTART_DELAY = 10


def start_sam():
    """Start Sam and auto-restart on crash."""
    restarts = 0

    while restarts < MAX_RESTARTS:
        logger.info(f"Starting Sam Zhang (attempt {restarts + 1}/{MAX_RESTARTS})...")

        try:
            proc = subprocess.Popen(
                [sys.executable, '-m', 'app.main'],
                cwd=str(SAM_DIR),
                stdout=open(LOGS_DIR / 'sam.log', 'a', encoding='utf-8'),
                stderr=open(LOGS_DIR / 'sam_err.log', 'a', encoding='utf-8'),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )

            proc.wait()
            exit_code = proc.returncode

            if exit_code == 0:
                logger.info("Sam exited cleanly. Restarting...")
            else:
                logger.warning(f"Sam crashed with exit code {exit_code}")
                restarts += 1

        except KeyboardInterrupt:
            logger.info("Launcher interrupted. Stopping Sam...")
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
            break
        except Exception as e:
            logger.error(f"Launcher error: {e}")
            restarts += 1

        if restarts < MAX_RESTARTS:
            logger.info(f"Restarting in {RESTART_DELAY}s...")
            time.sleep(RESTART_DELAY)

    if restarts >= MAX_RESTARTS:
        logger.error(f"Max restarts ({MAX_RESTARTS}) reached. Launcher stopping.")


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Sam Zhang Daemon Launcher")
    logger.info(f"Working dir: {SAM_DIR}")
    logger.info("=" * 50)
    start_sam()
