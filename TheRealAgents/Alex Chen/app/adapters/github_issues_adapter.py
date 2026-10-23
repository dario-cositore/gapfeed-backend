"""
GitHub Issues adapter — finds pain signals in GitHub issues.

Uses GitHub Search API with token for higher rate limits (5000 req/hour).
"""

import time
import logging
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
RATE_LIMIT_DELAY = 1.5  # seconds between requests (conservative)


class GitHubIssuesAdapter:
    """GitHub Issues source adapter with pain-focused search."""

    # Pain-focused search queries (expanded set)
    PAIN_QUERIES = [
        # Frustration & Annoyance
        'is:issue is:open "so frustrating" sort:updated-desc',
        'is:issue is:open "drives me crazy" sort:updated-desc',
        'is:issue is:open "this is broken" sort:updated-desc',
        'is:issue is:open "extremely frustrating" sort:updated-desc',
        'is:issue is:open "endless frustration" sort:updated-desc',
        'is:issue is:open "infuriatingly bad" sort:updated-desc',

        # Alternative Seeking
        'is:issue is:open "alternative to" sort:updated-desc',
        'is:issue is:open "open source alternative" sort:updated-desc',
        'is:issue is:open "replacement for" sort:updated-desc',
        'is:issue is:open "better alternative" sort:updated-desc',
        'is:issue is:open "competitor to" sort:updated-desc',

        # Missing Features & Wishes
        'is:issue is:open "I wish" sort:updated-desc',
        'is:issue is:open "no way to" sort:updated-desc',
        'is:issue is:open "should support" sort:updated-desc',
        'is:issue is:open "missing feature" sort:updated-desc',
        'is:issue is:open "feature request" sort:created-desc',
        'is:issue is:open "enhancement" stars:>100 sort:updated-desc',
        'is:issue is:open "wish it had" sort:updated-desc',
        'is:issue is:open "desperately needs" sort:updated-desc',
        'is:issue is:open "why doesn\'t it have" sort:updated-desc',
        'is:issue is:open "can\'t believe it doesn\'t" sort:updated-desc',
        'is:issue is:open "please add support for" sort:updated-desc',
        'is:issue is:open "top requested feature" sort:updated-desc',

        # Performance & Reliability
        'is:issue is:open "so slow" sort:updated-desc',
        'is:issue is:open "keeps crashing" sort:updated-desc',
        'is:issue is:open "terrible performance" sort:updated-desc',
        'is:issue is:open "buggy mess" sort:updated-desc',
        'is:issue is:open "performance is garbage" sort:updated-desc',
        'is:issue is:open "constantly freezing" sort:updated-desc',
        'is:issue is:open "unreliable" sort:updated-desc',

        # Usability & UX
        'is:issue is:open "terrible UI" sort:updated-desc',
        'is:issue is:open "confusing interface" sort:updated-desc',
        'is:issue is:open "impossible to use" sort:updated-desc',
        'is:issue is:open "horrible UX" sort:updated-desc',
        'is:issue is:open "steep learning curve" sort:updated-desc',
        'is:issue is:open "non-intuitive" sort:updated-desc',

        # Integration & Compatibility
        'is:issue is:open "doesn\'t integrate with" sort:updated-desc',
        'is:issue is:open "compatibility issues" sort:updated-desc',
        'is:issue is:open "missing API support" sort:updated-desc',
        'is:issue is:open "can\'t connect to" sort:updated-desc',
        'is:issue is:open "no webhook support" sort:updated-desc',

        # Security & Privacy
        'is:issue is:open "security nightmare" sort:updated-desc',
        'is:issue is:open "privacy concerns" sort:updated-desc',
        'is:issue is:open "data breach" sort:updated-desc',
        'is:issue is:open "no 2FA" sort:updated-desc',
        'is:issue is:open "leaks data" sort:updated-desc',

        # General Pain Signals
        'is:issue is:open "pain point" sort:updated-desc',
        'is:issue is:open "why is there no" sort:updated-desc',
        'is:issue is:open "I need" sort:created-desc',
        'is:issue is:open "anyone know" sort:updated-desc',
        'is:issue is:open "workaround" sort:updated-desc',
        'is:issue is:open "broken" sort:updated-desc',
        'is:issue is:open "struggling with" sort:updated-desc',
        'is:issue is:open "biggest pain point" sort:updated-desc',
        'is:issue is:open "no good solution yet" sort:updated-desc',
        'is:issue is:open "this shouldn\'t be this hard" sort:updated-desc',
    ]

    def __init__(self, token: str = None, cursor_file: str = None):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'TuXo:PainSignalScout/1.0',
        })
        if token:
            self.session.headers['Authorization'] = f'token {token}'
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.seen_urls = self._load_seen()

    def _load_seen(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_urls', []))
        except Exception:
            pass
        return set()

    def _save_seen(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            urls = list(self.seen_urls)[-5000:]
            with open(p, 'w') as f:
                json.dump({'seen_urls': urls}, f)
        except Exception as e:
            logger.warning(f"Failed to save GitHub cursors: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        self._rate_limit()
        try:
            resp = self.session.get(
                f"{GITHUB_API}/{endpoint}",
                params=params or {},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403:
                logger.warning("GitHub API rate limited")
                time.sleep(60)
                return None
            logger.warning(f"GitHub returned {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"GitHub request failed: {e}")
            return None

    def search_issues(self, query: str, max_results: int = 30) -> list[dict]:
        """Search GitHub issues with a query."""
        data = self._request('search/issues', {
            'q': query,
            'per_page': min(max_results, 100),
            'sort': 'updated',
            'order': 'desc',
        })

        if not data:
            return []

        signals = []
        for item in data.get('items', []):
            url = item.get('html_url', '')
            if not url or url in self.seen_urls:
                continue

            repo = item.get('repository_url', '').split('repos/')[-1] if item.get('repository_url') else ''
            labels = [l.get('name', '') for l in item.get('labels', [])]

            signal = {
                'source_type': 'github',
                'source_url': url,
                'title': item.get('title', ''),
                'body': (item.get('body', '') or '')[:2000],
                'author_handle': item.get('user', {}).get('login', 'unknown'),
                'created_at': item.get('created_at', ''),
                'source_subtype': 'issue',
                'platform_metadata': {
                    'repo': repo,
                    'labels': labels,
                    'comments': item.get('comments', 0),
                    'state': item.get('state', ''),
                }
            }
            signals.append(signal)
            self.seen_urls.add(url)

        return signals

    def scout(self, max_results: int = 50) -> list[dict]:
        """Run a full scout cycle across pain queries."""
        import random
        all_signals = []
        queries = random.sample(self.PAIN_QUERIES, min(5, len(self.PAIN_QUERIES)))

        for query in queries:
            if len(all_signals) >= max_results:
                break
            remaining = max_results - len(all_signals)
            signals = self.search_issues(query, max_results=min(remaining, 10))
            all_signals.extend(signals)
            time.sleep(1)

        self._save_seen()
        logger.info(f"GitHub scout complete: {len(all_signals)} new issues")
        return all_signals[:max_results]


def get_github(token: str = None, cursor_file: str = None) -> GitHubIssuesAdapter:
    """Factory function."""
    return GitHubIssuesAdapter(token=token, cursor_file=cursor_file)
