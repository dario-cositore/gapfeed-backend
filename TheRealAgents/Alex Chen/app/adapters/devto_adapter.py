"""
Dev.to adapter — fetches articles via the public Dev.to API (Forem).

Free, no auth needed, generous rate limits.
Great for developer pain: tool frustrations, workflow complaints, "I built X because Y sucks".

Cursor-based: tracks last article ID to avoid re-scanning.
"""

import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEVTO_API = "https://dev.to/api"
RATE_LIMIT_DELAY = 1.0


class DevToAdapter:
    """Dev.to source adapter with cursoring."""

    # Tags most likely to surface pain signals
    PAIN_TAGS = [
        'productivity', 'opensource', 'startup',
        'saas', 'api', 'webdev', 'javascript',
        'python', 'devops', 'testing',
        'ux', 'tutorial', 'showdev',
    ]

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
        """Load last seen article ID."""
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

    def _save_cursor(self, article_id: int):
        """Persist last seen ID."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'last_seen_id': article_id}, f)
        except Exception as e:
            logger.warning(f"Failed to save Dev.to cursor: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: dict = None, max_retries: int = 3) -> Optional[list]:
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(
                    f"{DEVTO_API}/{endpoint}",
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    backoff = 10 * (attempt + 1)
                    logger.warning(f"Dev.to rate limited, waiting {backoff}s")
                    time.sleep(backoff)
                    continue
                logger.warning(f"Dev.to returned {resp.status_code}")
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"Dev.to request failed (attempt {attempt+1}): {e}")
                time.sleep(3)
        return None

    def fetch_recent(self, tag: str = None, limit: int = 30) -> list[dict]:
        """
        Fetch recent articles, optionally filtered by tag.

        Returns raw signal dicts.
        """
        logger.info(f"Fetching {limit} Dev.to articles (tag={tag})")

        params = {
            'page': 1,
            'per_page': min(limit, 30),  # Dev.to max is 30 per page
        }
        if tag:
            params['tag'] = tag

        items = self._request('articles', params)
        if not items:
            return []

        signals = []
        max_id = self.last_seen_id or 0

        for item in items:
            article_id = item.get('id', 0)

            # Skip already seen
            if self.last_seen_id and article_id <= self.last_seen_id:
                continue

            signal = self._item_to_signal(item)
            if signal:
                signals.append(signal)

            max_id = max(max_id, article_id)

        if max_id > (self.last_seen_id or 0):
            self.last_seen_id = max_id
            self._save_cursor(max_id)

        logger.info(f"Fetched {len(signals)} Dev.to articles (tag={tag})")
        return signals

    def fetch_latest(self, limit: int = 30) -> list[dict]:
        """Fetch the latest articles across all tags (highest volume)."""
        return self.fetch_recent(limit=limit)

    def _item_to_signal(self, item: dict) -> Optional[dict]:
        """Convert Dev.to article to raw signal dict."""
        article_id = item.get('id')
        title = item.get('title', '')
        description = item.get('description', '') or ''
        body = item.get('body_markdown', '') or description
        url = item.get('url', '')
        author_name = item.get('user', {}).get('name', '')
        tags = item.get('tag_list', [])
        positive_reactions = item.get('positive_reactions_count', 0)
        comments_count = item.get('comments_count', 0)
        reading_time = item.get('reading_time_minutes', 0)
        published_at = item.get('published_at', '')

        if not title:
            return None

        return {
            'raw_signal_id': f"sig_devto_{article_id}",
            'source_type': 'devto',
            'source_subtype': 'article',
            'author_handle': author_name if author_name else None,
            'source_url': url,
            'title': title,
            'body': body[:1500],  # truncate long articles
            'created_at': published_at,
            'platform_metadata': {
                'positive_reactions': positive_reactions,
                'comments_count': comments_count,
                'reading_time_minutes': reading_time,
                'tags': tags,
                'article_id': article_id,
            },
            'language': 'en',
            'geo_hint': None,
            'product_mentions': tags,
            'money_mentions': [],
        }

    def get_tag_rotation(self) -> list[str]:
        """Return tags to rotate through for scouting."""
        return self.PAIN_TAGS
