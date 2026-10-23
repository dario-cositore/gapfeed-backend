"""
Adapters — source connectors for Alex's scouting.

Usage:
    from app.adapters import get_reddit, get_web_search, get_hn, get_rss, get_stackoverflow, get_devto, get_youtube
"""

from .reddit_adapter import RedditAdapter
from .web_search_adapter import WebSearchAdapter
from .hn_adapter import HackerNewsAdapter
from .rss_adapter import RSSAdapter
from .stackoverflow_adapter import StackOverflowAdapter
from .devto_adapter import DevToAdapter
from .youtube_adapter import YouTubeAdapter


def get_reddit(cursor_file: str = None) -> RedditAdapter:
    return RedditAdapter(cursor_file=cursor_file)


def get_web_search(cursor_file: str = None) -> WebSearchAdapter:
    return WebSearchAdapter(cursor_file=cursor_file)


def get_hn(cursor_file: str = None) -> HackerNewsAdapter:
    return HackerNewsAdapter(cursor_file=cursor_file)


def get_rss(cursor_file: str = None) -> RSSAdapter:
    return RSSAdapter(cursor_file=cursor_file)


def get_stackoverflow(cursor_file: str = None) -> StackOverflowAdapter:
    return StackOverflowAdapter(cursor_file=cursor_file)


def get_devto(cursor_file: str = None) -> DevToAdapter:
    return DevToAdapter(cursor_file=cursor_file)


def get_youtube(api_key: str, cursor_file: str = None) -> YouTubeAdapter:
    return YouTubeAdapter(api_key=api_key, cursor_file=cursor_file)
