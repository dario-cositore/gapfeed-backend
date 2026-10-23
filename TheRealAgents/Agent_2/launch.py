"""
Agent_2 daemon launcher.
Starts Jack as a background process that survives terminal close.
Uses Playwright browser for human-like web scraping.
Logs to logs/launcher.log.
"""

import subprocess
import sys
import time
import logging
from pathlib import Path

JACK_DIR = Path(__file__).resolve().parent
TUXO_DIR = JACK_DIR.parent.parent
LOGS_DIR = JACK_DIR / 'logs'
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
RESTART_DELAY = 15  # seconds between restarts (longer for browser)


def ensure_playwright():
    """Ensure Playwright and Chromium are installed."""
    try:
        import playwright
        logger.info("Playwright is installed")
    except ImportError:
        logger.info("Installing Playwright...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], check=True)
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True)
        logger.info("Playwright installed")


def start_jack():
    """Start Jack and auto-restart on crash."""
    ensure_playwright()
    restarts = 0

    while restarts < MAX_RESTARTS:
        logger.info(f"Starting Agent_2 (attempt {restarts + 1}/{MAX_RESTARTS})...")

        try:
            proc = subprocess.Popen(
                [sys.executable, '-m', 'app.main'],
                cwd=str(JACK_DIR),
                stdout=open(LOGS_DIR / 'jack.log', 'a', encoding='utf-8'),
                stderr=open(LOGS_DIR / 'jack_err.log', 'a', encoding='utf-8'),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )

            proc.wait()
            exit_code = proc.returncode

            if exit_code == 0:
                logger.info("Jack exited cleanly (code 0). Restarting...")
            else:
                logger.warning(f"Jack crashed with exit code {exit_code}")
                restarts += 1

        except KeyboardInterrupt:
            logger.info("Launcher interrupted by user. Stopping Jack...")
            try:
                proc.terminate()
                proc.wait(timeout=15)
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
    logger.info("Agent_2 Daemon Launcher")
    logger.info(f"Working dir: {JACK_DIR}")
    logger.info(f"Max restarts: {MAX_RESTARTS}")
    logger.info("=" * 50)
    start_jack()
