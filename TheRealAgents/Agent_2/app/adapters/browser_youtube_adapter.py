"""
Browser YouTube Adapter — searches YouTube via real browser.

Uses browser to search YouTube and parse video results.
Falls back to API when available.
"""

import time
import logging
import json
import random
from pathlib import Path
from datetime import datetime, timezone

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)

PAIN_QUERIES = [
    "frustrating software alternatives",
    "better tool for small business",
    "free alternative to expensive software",
    "simple CRM for freelancers",
    "lightweight project management",
    "no code automation tools",
    "open source business tools",
    "solo entrepreneur tools",
]


class BrowserYouTubeAdapter:
    """YouTube adapter using Playwright browser."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_ids = self._load_cursors()

    def _load_cursors(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_ids', []))
        except Exception:
            pass
        return set()

    def _save_cursors(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'seen_ids': list(self.seen_ids)[-5000]}, f)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def get_query_rotation(self) -> list[str]:
        return PAIN_QUERIES

    def search_videos(self, query: str, limit: int = 10) -> list[dict]:
        """Search YouTube for videos via browser."""
        page = self.browser.new_page()
        signals = []
        try:
            url = f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
            self.browser.human_delay(2, 5)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(2, 4)
            self.browser.human_scroll(page, 500, 1000)
            self.browser.human_delay(1, 2)

            videos = page.evaluate('''() => {
                const videos = [];
                const items = document.querySelectorAll('ytd-video-renderer, ytd-rich-item-renderer');
                items.forEach(item => {
                    const titleEl = item.querySelector('#video-title');
                    const channelEl = item.querySelector('#channel-name a, .ytd-channel-name a');
                    const descEl = item.querySelector('#description-text, .ytd-video-renderer #description');
                    const metaEl = item.querySelector('#metadata-line span');
                    const linkEl = item.querySelector('a#thumbnail, a#video-title-link');
                    
                    if (titleEl) {
                        const href = titleEl.href || (linkEl ? linkEl.href : '');
                        const videoId = href.includes('v=') ? href.split('v=')[1].split('&')[0] : '';
                        videos.push({
                            title: titleEl.textContent.trim(),
                            url: href,
                            video_id: videoId,
                            channel: channelEl ? channelEl.textContent.trim() : '',
                            description: descEl ? descEl.textContent.trim().substring(0, 500) : '',
                            meta: metaEl ? metaEl.textContent.trim() : '',
                        });
                    }
                });
                return videos;
            }''')

            for video in videos[:limit]:
                vid_id = video.get('video_id', '')
                if vid_id and vid_id in self.seen_ids:
                    continue
                if vid_id:
                    self.seen_ids.add(vid_id)

                signal = {
                    'title': video.get('title', ''),
                    'body': video.get('description', '') or video.get('title', ''),
                    'url': video.get('url', ''),
                    'source_url': video.get('url', ''),
                    'source': 'youtube',
                    'platform_metadata': {
                        'platform': 'youtube',
                        'video_id': vid_id,
                        'channel': video.get('channel', ''),
                        'search_query': query,
                        'meta': video.get('meta', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            self._save_cursors()
            logger.info(f"YouTube '{query}': {len(signals)} videos via browser")
            return signals

        except Exception as e:
            logger.error(f"Browser YouTube search failed: {e}")
            return []
        finally:
            page.close()

    def scout(self, limit_per_query: int = 5) -> list[dict]:
        """Scout YouTube with pain queries."""
        all_signals = []
        queries = random.sample(PAIN_QUERIES, min(2, len(PAIN_QUERIES)))

        for query in queries:
            results = self.search_videos(query, limit=limit_per_query)
            all_signals.extend(results)
            self.browser.human_delay(3, 7)

        return all_signals
