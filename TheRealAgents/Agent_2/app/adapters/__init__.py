"""
Adapters — source connectors for Jack's browser-based scouting.

All adapters use Playwright browser automation for human-like browsing.
RSS adapter kept as-is (HTTP works fine for RSS).

NO Reddit — Alex handles Reddit. Jack focuses on browser-heavy sources.

Usage:
    from app.adapters import get_web_search, get_hn, get_rss, get_stackoverflow, get_devto, get_youtube, get_producthunt, get_indiehackers
    from app.adapters import start_browser, stop_browser
"""

from .browser_manager import get_browser_manager
from .browser_web_search_adapter import BrowserSearchAdapter
from .browser_hn_adapter import BrowserHNAdapter
from .rss_adapter import RSSAdapter
from .browser_stackoverflow_adapter import BrowserStackOverflowAdapter
from .browser_devto_adapter import BrowserDevToAdapter
from .browser_youtube_adapter import BrowserYouTubeAdapter
from .browser_indiehackers_adapter import BrowserIndieHackersAdapter
from .browser_producthunt_adapter import BrowserProductHuntAdapter


def start_browser():
    """Start the shared browser instance."""
    browser = get_browser_manager()
    browser.start()
    return browser


def stop_browser():
    """Shutdown the browser."""
    browser = get_browser_manager()
    browser.close()


def get_web_search(cursor_file: str = None) -> BrowserSearchAdapter:
    return BrowserSearchAdapter(cursor_file=cursor_file)


def get_hn(cursor_file: str = None) -> BrowserHNAdapter:
    return BrowserHNAdapter(cursor_file=cursor_file)


def get_rss(cursor_file: str = None) -> RSSAdapter:
    return RSSAdapter(cursor_file=cursor_file)


def get_stackoverflow(cursor_file: str = None) -> BrowserStackOverflowAdapter:
    return BrowserStackOverflowAdapter(cursor_file=cursor_file)


def get_devto(cursor_file: str = None) -> BrowserDevToAdapter:
    return BrowserDevToAdapter(cursor_file=cursor_file)


def get_youtube(api_key: str, cursor_file: str = None) -> BrowserYouTubeAdapter:
    return BrowserYouTubeAdapter(cursor_file=cursor_file)


def get_indiehackers(cursor_file: str = None) -> BrowserIndieHackersAdapter:
    return BrowserIndieHackersAdapter(cursor_file=cursor_file)


def get_producthunt(cursor_file: str = None) -> BrowserProductHuntAdapter:
    return BrowserProductHuntAdapter(cursor_file=cursor_file)
