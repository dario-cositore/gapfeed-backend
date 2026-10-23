"""
Hacker News adapter — fetches stories from HN via the public API.

Free, unlimited, no auth. Uses the official Firebase API.
HN is great for tech pain: SaaS complaints, dev tool frustrations,
startup struggles, "Show HN" desperation.

Cursor-based: tracks last story ID to avoid re-scanning.
"""

import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"
RATE_LIMIT_DELAY = 0.5  # HN API is generous, but be polite


class HackerNewsAdapter:
    """Hacker News source adapter with cursoring."""

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TuXo:PainSignalScout/1.0',
            'Accept': 'application/json',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.last_seen_id = self._load_cursor()

    def _load_cursor(self) -> Optional[int]:
        """Load last seen story ID."""
        if not self.cursor_file:
            return None
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return data.get('last_seen_id')
        except Exception:
            pass
        return None

    def _save_cursor(self, story_id: int):
        """Persist last seen ID."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'last_seen_id': story_id}, f)
        except Exception as e:
            logger.warning(f"Failed to save HN cursor: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, url: str, max_retries: int = 3) -> Optional[dict]:
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"HN request failed (attempt {attempt+1}): {e}")
                time.sleep(3)
        return None

    def _fetch_item(self, item_id: int) -> Optional[dict]:
        """Fetch a single HN item."""
        return self._request(f"{HN_API}/item/{item_id}.json")

    def fetch_top_stories(self, limit: int = 30) -> list[dict]:
        """
        Fetch top stories from HN front page.

        Returns raw signal dicts for stories that look like pain/complaint/discussion.
        """
        logger.info(f"Fetching top {limit} HN stories")

        data = self._request(f"{HN_API}/topstories.json")
        if not data:
            return []

        story_ids = data[:limit]
        signals = []
        max_id_seen = self.last_seen_id or 0

        for story_id in story_ids:
            if self.last_seen_id and story_id <= self.last_seen_id:
                continue

            item = self._fetch_item(story_id)
            if not item:
                continue

            if item.get('type') != 'story':
                continue
            if item.get('dead') or item.get('deleted'):
                continue

            signal = self._item_to_signal(item)
            if signal:
                signals.append(signal)

            max_id_seen = max(max_id_seen, story_id)

        if max_id_seen > (self.last_seen_id or 0):
            self.last_seen_id = max_id_seen
            self._save_cursor(max_id_seen)

        logger.info(f"Fetched {len(signals)} new HN stories")
        return signals

    def fetch_new_stories(self, limit: int = 50) -> list[dict]:
        """Fetch newest stories (more noise, more volume)."""
        logger.info(f"Fetching {limit} new HN stories")

        data = self._request(f"{HN_API}/newstories.json")
        if not data:
            return []

        story_ids = data[:limit]
        signals = []
        max_id_seen = self.last_seen_id or 0

        for story_id in story_ids:
            if self.last_seen_id and story_id <= self.last_seen_id:
                continue

            item = self._fetch_item(story_id)
            if not item:
                continue

            if item.get('type') != 'story':
                continue
            if item.get('dead') or item.get('deleted'):
                continue

            signal = self._item_to_signal(item)
            if signal:
                signals.append(signal)

            max_id_seen = max(max_id_seen, story_id)

        if max_id_seen > (self.last_seen_id or 0):
            self.last_seen_id = max_id_seen
            self._save_cursor(max_id_seen)

        return signals

    def search_stories(self, query: str, limit: int = 20) -> list[dict]:
        """
        Search HN via Algolia API (unofficial but public).

        More targeted than fetching all top/new stories.
        """
        logger.info(f"Searching HN for: {query}")

        self._rate_limit()
        try:
            resp = self.session.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    'query': query,
                    'tags': 'story',
                    'hitsPerPage': limit,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            hits = data.get('hits', [])
            signals = []

            for hit in hits:
                created_str = hit.get('created_at', '')
                created_at = None
                if created_str:
                    try:
                        created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00')).isoformat()
                    except Exception:
                        created_at = created_str

                signal = {
                    'raw_signal_id': f"sig_hn_{hit.get('objectID', '')}",
                    'source_type': 'hackernews',
                    'source_subtype': 'story',
                    'author_handle': hit.get('author'),
                    'source_url': f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                    'title': hit.get('title', ''),
                    'body': hit.get('story_text', '') or '',
                    'created_at': created_at,
                    'platform_metadata': {
                        'points': hit.get('points', 0),
                        'num_comments': hit.get('num_comments', 0),
                        'story_id': hit.get('objectID'),
                    },
                    'language': 'en',
                    'geo_hint': None,
                    'product_mentions': [],
                    'money_mentions': [],
                }
                signals.append(signal)

            logger.info(f"HN search found {len(signals)} stories for: {query}")
            return signals

        except Exception as e:
            logger.error(f"HN search failed: {e}")
            return []

    def _item_to_signal(self, item: dict) -> Optional[dict]:
        """Convert HN item to raw signal dict."""
        story_id = item.get('id')
        title = item.get('title', '')
        text = item.get('text', '') or ''
        url = item.get('url', '')
        author = item.get('by', '')
        score = item.get('score', 0)
        num_comments = item.get('descendants', 0)
        created_utc = item.get('time', 0)

        created_at = None
        if created_utc:
            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

        # Build source URL
        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
        source_url = url if url else hn_url

        if not title:
            return None

        return {
            'raw_signal_id': f"sig_hn_{story_id}",
            'source_type': 'hackernews',
            'source_subtype': 'story',
            'author_handle': author if author else None,
            'source_url': source_url,
            'title': title,
            'body': text,
            'created_at': created_at,
            'platform_metadata': {
                'points': score,
                'num_comments': num_comments,
                'story_id': story_id,
                'hn_url': hn_url,
                'external_url': url,
            },
            'language': 'en',
            'geo_hint': None,
            'product_mentions': [],
            'money_mentions': [],
        }

    def get_pain_queries(self) -> list[str]:
        """Pre-built search queries for pain-focused HN scouting."""
        return [
            'alternative to',
            'switched from',
            'frustrated with',
            'worst experience',
            'not worth',
            'killed my',
            'lost my data',
            'shut down',
            'banned my account',
            'scam',
            'overpriced',
            'bait and switch',
        ]
