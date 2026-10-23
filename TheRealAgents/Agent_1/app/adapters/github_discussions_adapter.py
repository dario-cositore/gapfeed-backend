"""
GitHub Discussions adapter â€” finds pain signals in GitHub repository discussions.

Uses GitHub GraphQL API (v4) since REST API doesn't support discussions.
Requires a GitHub token with read access.

Cursor-based: tracks last-seen discussion URLs.
"""

import time
import logging
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL = "https://api.github.com/graphql"
RATE_LIMIT_DELAY = 1.5

# Pain-focused search queries
SEARCH_QUERIES = [
    # Frustration & Annoyance
    'is:discussion "so frustrating"',
    'is:discussion "drives me crazy"',
    'is:discussion "this is broken"',
    'is:discussion "endless frustration"',
    'is:discussion "pain in the ass"',
    'is:discussion "infuriatingly bad"',

    # Alternative Seeking
    'is:discussion "alternative to"',
    'is:discussion "better replacement"',
    'is:discussion "open source alternative"',
    'is:discussion "switched from"',
    'is:discussion "replacement for"',
    'is:discussion "need something better"',

    # Missing Features
    'is:discussion "wish it had"',
    'is:discussion "missing feature"',
    'is:discussion "feature request"',
    'is:discussion "should support"',
    'is:discussion "no way to"',
    'is:discussion "desperately needs"',

    # Performance & Reliability
    'is:discussion "so slow"',
    'is:discussion "keeps crashing"',
    'is:discussion "terrible performance"',
    'is:discussion "buggy mess"',
    'is:discussion "unreliable"',

    # Usability & UX
    'is:discussion "impossible to use"',
    'is:discussion "confusing interface"',
    'is:discussion "terrible UI"',
    'is:discussion "horrible UX"',

    # Pricing & Value
    'is:discussion "way too expensive"',
    'is:discussion "overpriced"',
    'is:discussion "subscription fatigue"',
    'is:discussion "not worth the money"',

    # General Pain
    'is:discussion "struggling with"',
    'is:discussion "biggest pain point"',
    'is:discussion "anyone know how"',
    'is:discussion "no good solution"',
    'is:discussion "needs to exist"',
    'is:discussion "why is there no"',
    'is:discussion "pain point"',
    'is:discussion "frustrating"',

    # Market Gaps
    'is:discussion "market gap"',
    'is:discussion "untapped market"',
    'is:discussion "nobody is solving"',
    'is:discussion "business opportunity"',
]

# GraphQL query for searching discussions
SEARCH_DISCUSSIONS_QUERY = """
query SearchDiscussions($query: String!, $first: Int!, $after: String) {
  search(query: $query, type: DISCUSSION, first: $first, after: $after) {
    discussionCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Discussion {
        id
        title
        url
        bodyText
        body
        createdAt
        updatedAt
        upvoteCount
        category {
          name
          emoji
        }
        author {
          login
        }
        repository {
          nameWithOwner
          stargazerCount
        }
        comments(first: 3) {
          nodes {
            body
            author {
              login
            }
          }
        }
      }
    }
  }
  rateLimit {
    remaining
    cost
  }
}
"""


class GitHubDiscussionsAdapter:
    """GitHub Discussions source adapter using GraphQL API."""

    def __init__(self, token: str = None, cursor_file: str = None):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v4+json',
            'Content-Type': 'application/json',
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
            logger.warning(f"Failed to save GitHub Discussions cursors: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _graphql(self, query: str, variables: dict = None) -> Optional[dict]:
        self._rate_limit()
        try:
            resp = self.session.post(
                GITHUB_GRAPHQL,
                json={'query': query, 'variables': variables or {}},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'errors' in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return None
                return data
            if resp.status_code == 401:
                logger.error("GitHub token invalid or lacks permissions")
                return None
            logger.warning(f"GitHub GraphQL returned {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"GitHub GraphQL failed: {e}")
            return None

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search GitHub Discussions for a query."""
        data = self._graphql(SEARCH_DISCUSSIONS_QUERY, {
            'query': query,
            'first': min(max_results, 25),
        })

        if not data:
            return []

        search_data = data.get('data', {}).get('search', {})
        remaining = search_data.get('rateLimit', {}).get('remaining', 5000)
        logger.info(f"GitHub API remaining: {remaining}")

        signals = []
        for node in search_data.get('nodes', []):
            url = node.get('url', '')
            if not url or url in self.seen_urls:
                continue

            author = node.get('author', {}).get('login', 'unknown') if node.get('author') else 'unknown'
            repo = node.get('repository', {})
            repo_name = repo.get('nameWithOwner', '') if repo else ''
            stars = repo.get('stargazerCount', 0) if repo else 0
            category = node.get('category', {})
            cat_name = category.get('name', '') if category else ''

            # Get top comments for extra pain context
            top_comments = []
            for c in (node.get('comments', {}).get('nodes', []) or []):
                if c:
                    top_comments.append({
                        'body': c.get('body', '')[:500],
                        'author': c.get('author', {}).get('login', 'unknown') if c.get('author') else 'unknown',
                    })

            signal = {
                'source_type': 'github_discussions',
                'source_url': url,
                'title': node.get('title', ''),
                'body': (node.get('bodyText', '') or node.get('body', ''))[:2000],
                'author_handle': author,
                'created_at': node.get('createdAt', ''),
                'platform_id': url,
                'source_subtype': 'discussion',
                'platform_metadata': {
                    'repo': repo_name,
                    'stars': stars,
                    'category': cat_name,
                    'upvotes': node.get('upvoteCount', 0),
                    'comments_count': len(top_comments),
                    'top_comments': top_comments,
                }
            }
            signals.append(signal)
            self.seen_urls.add(url)

        if signals:
            self._save_seen()

        return signals

    def scout(self, max_results: int = 30) -> list[dict]:
        """Run a full scout cycle across pain queries."""
        import random
        all_signals = []

        # Use 5 random queries per cycle
        queries = random.sample(SEARCH_QUERIES, min(5, len(SEARCH_QUERIES)))

        for query in queries:
            if len(all_signals) >= max_results:
                break
            remaining = max_results - len(all_signals)
            signals = self.search(query, max_results=min(remaining, 10))
            all_signals.extend(signals)
            time.sleep(1)

        logger.info(f"GitHub Discussions scout complete: {len(all_signals)} new discussions")
        return all_signals[:max_results]


def get_github_discussions(token: str = None, cursor_file: str = None) -> GitHubDiscussionsAdapter:
    """Factory function."""
    return GitHubDiscussionsAdapter(token=token, cursor_file=cursor_file)

