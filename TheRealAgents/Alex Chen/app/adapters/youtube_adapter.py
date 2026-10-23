"""
YouTube adapter — fetches videos and comments via the YouTube Data API v3.

Uses API key (10,000 units/day free).
Search costs 100 units, video details cost 1 unit, comments cost 1 unit.
Budget carefully: ~100 searches/day + details/comments on results.

Cursor-based: tracks last search date to avoid re-scanning.
"""

import time
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

YT_API = "https://www.googleapis.com/youtube/v3"
RATE_LIMIT_DELAY = 0.5


class YouTubeAdapter:
    """YouTube source adapter with API key auth."""

    # Search queries that surface pain signals
    PAIN_QUERIES = [
        'frustrating software',
        'worst app experience',
        'why I stopped using',
        'I switched from',
        'software sucks',
        'tool alternatives',
        'better than {competitor}',
        'honest review',
        'disappointed with',
        'overpriced software',
    ]

    def __init__(self, api_key: str, cursor_file: str = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TuXo:PainSignalScout/1.0',
            'Accept': 'application/json',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.seen_video_ids = self._load_cursor()
        self.daily_quota_used = 0
        self.daily_quota_limit = 8000  # Conservative limit (10k max, leave buffer)
        self.quota_file = str(Path(cursor_file).parent / 'youtube_quota.json') if cursor_file else None
        self._load_quota()

    def _load_cursor(self) -> set:
        """Load seen video IDs."""
        if not self.cursor_file:
            return set()
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_video_ids', []))
        except Exception:
            pass
        return set()

    def _save_cursor(self):
        """Persist seen video IDs."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Keep only last 5000 IDs
            ids_list = list(self.seen_video_ids)[-5000:]
            with open(p, 'w') as f:
                json.dump({'seen_video_ids': ids_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save YouTube cursor: {e}")

    def _load_quota(self):
        """Load today's quota usage."""
        if not self.quota_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.quota_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                # Reset if different day
                if data.get('date') == datetime.now().strftime('%Y-%m-%d'):
                    self.daily_quota_used = data.get('used', 0)
                else:
                    self.daily_quota_used = 0
        except Exception:
            self.daily_quota_used = 0

    def _save_quota(self):
        """Save quota usage."""
        if not self.quota_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.quota_file)
            with open(p, 'w') as f:
                json.dump({
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'used': self.daily_quota_used,
                    'limit': self.daily_quota_limit,
                }, f)
        except Exception:
            pass

    def _check_quota(self, cost: int) -> bool:
        """Check if we have enough quota remaining."""
        if self.daily_quota_used + cost > self.daily_quota_limit:
            remaining = self.daily_quota_limit - self.daily_quota_used
            logger.warning(f"YouTube quota nearly exhausted ({self.daily_quota_used}/{self.daily_quota_limit}). Skipping.")
            return False
        return True

    def _use_quota(self, cost: int):
        """Track quota usage."""
        self.daily_quota_used += cost
        self._save_quota()

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: dict = None, max_retries: int = 3) -> Optional[dict]:
        if params is None:
            params = {}
        params['key'] = self.api_key

        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(
                    f"{YT_API}/{endpoint}",
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    backoff = 15 * (attempt + 1)
                    logger.warning(f"YouTube rate limited, waiting {backoff}s")
                    time.sleep(backoff)
                    continue
                if resp.status_code == 403:
                    logger.error("YouTube API quota exceeded or key invalid")
                    return None
                logger.warning(f"YouTube returned {resp.status_code}: {resp.text[:200]}")
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"YouTube request failed (attempt {attempt+1}): {e}")
                time.sleep(3)
        return None

    def search_videos(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search YouTube for videos matching a query.

        Returns raw signal dicts. Costs 100 API units per call.
        """
        logger.info(f"Searching YouTube for: {query} (limit={limit})")

        # Search for videos from the last 7 days
        after_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')

        data = self._request('search', {
            'q': query,
            'part': 'snippet',
            'type': 'video',
            'order': 'relevance',
            'maxResults': min(limit, 50),
            'publishedAfter': after_date,
        })

        if not data:
            return []

        self._use_quota(100)  # Search costs 100 units
        items = data.get('items', [])
        signals = []

        for item in items:
            video_id = item.get('id', {}).get('videoId', '')
            if not video_id or video_id in self.seen_video_ids:
                continue

            snippet = item.get('snippet', {})
            title = snippet.get('title', '')
            description = snippet.get('description', '')
            channel = snippet.get('channelTitle', '')
            published_at = snippet.get('publishedAt', '')

            self.seen_video_ids.add(video_id)

            signal = {
                'raw_signal_id': f"sig_yt_{video_id}",
                'source_type': 'youtube',
                'source_subtype': 'video',
                'author_handle': channel if channel else None,
                'source_url': f"https://www.youtube.com/watch?v={video_id}",
                'title': title,
                'body': description[:1000],
                'created_at': published_at,
                'platform_metadata': {
                    'video_id': video_id,
                    'channel': channel,
                    'query': query,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }
            signals.append(signal)

        self._save_cursor()
        logger.info(f"Found {len(signals)} YouTube videos for: {query}")
        return signals

    def fetch_video_comments(self, video_id: str, limit: int = 20) -> list[dict]:
        """
        Fetch top comments for a video. Costs 1 API unit.

        Comments are often where the real pain signals live.
        """
        data = self._request('commentThreads', {
            'videoId': video_id,
            'part': 'snippet',
            'order': 'relevance',
            'maxResults': min(limit, 100),
            'textFormat': 'plainText',
        })

        if not data:
            return []

        self._use_quota(1)  # Comments cost 1 unit
        items = data.get('items', [])
        signals = []

        for item in items:
            comment_snippet = item.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
            text = comment_snippet.get('textDisplay', '')
            author = comment_snippet.get('authorDisplayName', '')
            published_at = comment_snippet.get('publishedAt', '')
            like_count = comment_snippet.get('likeCount', 0)
            comment_id = item.get('id', '')

            if not text or len(text) < 20:
                continue

            signal = {
                'raw_signal_id': f"sig_yt_comment_{comment_id}",
                'source_type': 'youtube',
                'source_subtype': 'comment',
                'author_handle': author if author else None,
                'source_url': f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
                'title': '',
                'body': text[:500],
                'created_at': published_at,
                'platform_metadata': {
                    'video_id': video_id,
                    'comment_id': comment_id,
                    'like_count': like_count,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }
            signals.append(signal)

        return signals

    def scout(self, limit_per_query: int = 5) -> list[dict]:
        """
        Run a full scout cycle: search multiple queries, fetch comments on top results.

        Budget-conscious: uses ~300 API units max (out of 10,000 daily).
        Rotates through queries each round so all 10 get used over time.
        """
        import random
        all_signals = []

        # Rotate: pick 3 random queries instead of always the first 3
        queries = random.sample(self.PAIN_QUERIES, min(3, len(self.PAIN_QUERIES)))

        for query in queries:
            if not self._check_quota(100):
                break  # Stop if quota exhausted

            videos = self.search_videos(query, limit=limit_per_query)
            all_signals.extend(videos)

            # Fetch comments on top 2 videos per query = ~2 units
            for video in videos[:2]:
                if not self._check_quota(1):
                    break
                video_id = video.get('platform_metadata', {}).get('video_id')
                if video_id:
                    comments = self.fetch_video_comments(video_id, limit=10)
                    all_signals.extend(comments)

        logger.info(f"YouTube scout complete: {len(all_signals)} total signals (quota used: {self.daily_quota_used}/{self.daily_quota_limit})")
        return all_signals

    def get_query_rotation(self) -> list[str]:
        """Return queries to rotate through for scouting."""
        return self.PAIN_QUERIES
