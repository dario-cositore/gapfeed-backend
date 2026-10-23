"""
Stack Overflow adapter — fetches questions via the public Stack Exchange API.

Free, 300 requests/day without auth (10,000 with key, but not needed).
Great for developer pain: tool frustrations, missing features, workarounds.

Cursor-based: tracks last question date to avoid re-scanning.
"""

import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SO_API = "https://api.stackexchange.com/2.3"
RATE_LIMIT_DELAY = 3.0  # SO API is generous but has daily quota


class StackOverflowAdapter:
    """Stack Overflow source adapter with cursoring."""

    # Tags most likely to surface pain signals and unmet needs
    PAIN_TAGS = [
        'saas', 'startup', 'software-as-a-service',
        'project-management', 'invoicing', 'crm',
        'e-commerce', 'fintech', 'api',
        'automation', 'workflow', 'integration',
        'user-experience', 'accessibility',
        'performance', 'security',
    ]

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TuXo:PainSignalScout/1.0',
            'Accept-Encoding': 'gzip',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.last_seen_date = self._load_cursor()

    def _load_cursor(self) -> Optional[int]:
        """Load last seen question date (unix timestamp)."""
        if not self.cursor_file:
            return None
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return data.get('last_seen_date')
        except Exception:
            pass
        return None

    def _save_cursor(self, date_ts: int):
        """Persist last seen date."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'last_seen_date': date_ts}, f)
        except Exception as e:
            logger.warning(f"Failed to save SO cursor: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: dict = None, max_retries: int = 3) -> Optional[dict]:
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(
                    f"{SO_API}/{endpoint}",
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Check for API errors
                    if data.get('error_id'):
                        logger.warning(f"SO API error: {data.get('error_message')}")
                        return None
                    return data
                if resp.status_code == 429:
                    backoff = 10 * (attempt + 1)
                    logger.warning(f"SO rate limited, waiting {backoff}s")
                    time.sleep(backoff)
                    continue
                logger.warning(f"SO returned {resp.status_code}")
                return None
            except requests.exceptions.RequestException as e:
                logger.warning(f"SO request failed (attempt {attempt+1}): {e}")
                time.sleep(3)
        return None

    def fetch_recent_questions(self, tag: str = None, limit: int = 30) -> list[dict]:
        """
        Fetch recent questions, optionally filtered by tag.

        Returns raw signal dicts.
        """
        logger.info(f"Fetching {limit} SO questions (tag={tag})")

        params = {
            'order': 'desc',
            'sort': 'creation',
            'pagesize': min(limit, 100),
            'site': 'stackoverflow',
            'filter': 'withbody',  # includes question body
        }
        if tag:
            params['tagged'] = tag

        # If we have a cursor, only fetch questions newer than last seen
        if self.last_seen_date:
            params['min'] = self.last_seen_date

        data = self._request('questions', params)
        if not data:
            return []

        items = data.get('items', [])
        signals = []
        max_date = self.last_seen_date or 0

        for item in items:
            if item.get('is_answered') is False and item.get('answer_count', 0) == 0:
                # Unanswered questions are more likely to be pain/unmet needs
                signal = self._item_to_signal(item, subtype='unanswered')
            else:
                signal = self._item_to_signal(item, subtype='question')

            if signal:
                signals.append(signal)

            creation_date = item.get('creation_date', 0)
            max_date = max(max_date, creation_date)

        if max_date > (self.last_seen_date or 0):
            self.last_seen_date = max_date
            self._save_cursor(max_date)

        logger.info(f"Fetched {len(signals)} SO questions (tag={tag})")
        return signals

    def fetch_unanswered(self, tag: str = None, limit: int = 30) -> list[dict]:
        """Fetch unanswered questions (strongest pain signals on SO)."""
        logger.info(f"Fetching {limit} unanswered SO questions (tag={tag})")

        params = {
            'order': 'desc',
            'sort': 'creation',
            'pagesize': min(limit, 100),
            'site': 'stackoverflow',
            'filter': 'withbody',
        }
        if tag:
            params['tagged'] = tag

        data = self._request('questions/unanswered', params)
        if not data:
            return []

        items = data.get('items', [])
        signals = []

        for item in items:
            signal = self._item_to_signal(item, subtype='unanswered')
            if signal:
                signals.append(signal)

        logger.info(f"Fetched {len(signals)} unanswered SO questions")
        return signals

    def _item_to_signal(self, item: dict, subtype: str = 'question') -> Optional[dict]:
        """Convert SO question to raw signal dict."""
        question_id = item.get('question_id')
        title = item.get('title', '')
        body = item.get('body', '') or ''
        # Strip HTML tags from body (SO returns HTML)
        import re
        body = re.sub(r'<[^>]+>', ' ', body)
        body = re.sub(r'\s+', ' ', body).strip()

        tags = item.get('tags', [])
        score = item.get('score', 0)
        answer_count = item.get('answer_count', 0)
        view_count = item.get('view_count', 0)
        owner = item.get('owner', {})
        author = owner.get('display_name', '')
        created_utc = item.get('creation_date', 0)

        created_at = None
        if created_utc:
            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

        if not title:
            return None

        return {
            'raw_signal_id': f"sig_so_{question_id}",
            'source_type': 'stackoverflow',
            'source_subtype': subtype,
            'author_handle': author if author else None,
            'source_url': f"https://stackoverflow.com/questions/{question_id}",
            'title': title,
            'body': body[:1000],  # truncate long bodies
            'created_at': created_at,
            'platform_metadata': {
                'score': score,
                'answer_count': answer_count,
                'view_count': view_count,
                'tags': tags,
                'question_id': question_id,
            },
            'language': 'en',
            'geo_hint': None,
            'product_mentions': tags,
            'money_mentions': [],
        }

    def get_tag_rotation(self) -> list[str]:
        """Return tags to rotate through for scouting."""
        return self.PAIN_TAGS
