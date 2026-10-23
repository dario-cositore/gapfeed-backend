"""
Reddit adapter — fetches posts from Reddit via public JSON API.

No authentication needed. Uses reddit.com/r/{sub}/json endpoint.
Respects rate limits (30 requests/minute max with delays).

Cursor-based: tracks last post ID per subreddit to avoid re-scanning.
"""

import time
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://www.reddit.com"
USER_AGENT = "TuXo:PainSignalScout/1.0 (research bot)"
RATE_LIMIT_DELAY = 2.0  # seconds between requests


class RedditAdapter:
    """Reddit source adapter with cursoring and rate limiting."""

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.cursors = self._load_cursors()

    def _load_cursors(self) -> dict:
        """Load cursors from file (last post ID per subreddit)."""
        if not self.cursor_file:
            return {}
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cursors: {e}")
        return {}

    def _save_cursors(self):
        """Persist cursors to file."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump(self.cursors, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, url: str, max_retries: int = 3) -> Optional[dict]:
        """Make a request with exponential backoff on rate limit."""
        for attempt in range(max_retries):
            self._rate_limit()
            try:
                resp = self.session.get(url, timeout=15)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 429:
                    # Rate limited — backoff
                    wait = min(60 * (2 ** attempt), 300)
                    logger.warning(f"Reddit 429 rate limited. Backing off {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    continue

                if resp.status_code == 403:
                    logger.error(f"Reddit 403 forbidden: {url}")
                    return None

                if resp.status_code == 404:
                    logger.warning(f"Reddit 404 not found: {url}")
                    return None

                logger.error(f"Reddit {resp.status_code}: {url}")
                return None

            except requests.exceptions.Timeout:
                logger.warning(f"Reddit timeout (attempt {attempt+1}): {url}")
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                logger.error(f"Reddit request failed: {e}")
                time.sleep(5)

        return None

    def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str = 'new',
        limit: int = 50,
        time_filter: str = 'day',
    ) -> list[dict]:
        """
        Fetch posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            sort: 'new', 'hot', 'rising', 'top'
            limit: Max posts to fetch (max 100)
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all' (for top sort)

        Returns:
            List of raw signal dicts ready for normalization.
        """
        clean_sub = subreddit.replace('r/', '').strip()
        limit = min(limit, 100)

        url = f"{BASE_URL}/r/{clean_sub}/{sort}.json?limit={limit}&raw_json=1"
        if sort == 'top':
            url += f"&t={time_filter}"

        # Add cursor (after parameter) if we have one
        after = self.cursors.get(clean_sub)
        if after:
            url += f"&after={after}"

        logger.info(f"Fetching r/{clean_sub}/{sort} (limit={limit})")
        data = self._request(url)

        if not data:
            logger.warning(f"No data returned for r/{clean_sub}")
            return []

        posts = data.get('data', {}).get('children', [])
        if not posts:
            logger.info(f"No posts in r/{clean_sub}")
            return []

        signals = []
        last_post_id = None

        for post_wrapper in posts:
            post = post_wrapper.get('data', {})
            if not post:
                continue

            # Skip stickied, mod posts, meta posts
            if post.get('stickied'):
                continue
            if post.get('distinguished') == 'moderator':
                continue

            # Extract fields
            post_id = post.get('id', '')
            title = post.get('title', '')
            selftext = post.get('selftext', '')
            author = post.get('author', '[deleted]')
            created_utc = post.get('created_utc', 0)
            score = post.get('score', 0)
            num_comments = post.get('num_comments', 0)
            permalink = post.get('permalink', '')
            url_link = post.get('url', '')

            # Build full URL
            source_url = f"https://www.reddit.com{permalink}" if permalink else url_link

            # Parse created time
            created_at = None
            if created_utc:
                created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

            # Skip deleted/deleted authors
            if author == '[deleted]' and not selftext:
                continue

            signal = {
                'raw_signal_id': f"sig_reddit_t3_{post_id}",
                'source_type': 'reddit',
                'source_subtype': 'post',
                'author_handle': author if author != '[deleted]' else None,
                'source_url': source_url,
                'title': title,
                'body': selftext,
                'created_at': created_at,
                'platform_metadata': {
                    'subreddit': clean_sub,
                    'score': score,
                    'comment_count': num_comments,
                    'post_id': post_id,
                    'flair': post.get('link_flair_text'),
                    'is_self': post.get('is_self', True),
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],  # Filled by extractors
                'money_mentions': [],    # Filled by extractors
            }

            signals.append(signal)
            last_post_id = f"t3_{post_id}"

        # Update cursor
        if last_post_id:
            self.cursors[clean_sub] = last_post_id
            self._save_cursors()

        logger.info(f"Fetched {len(signals)} posts from r/{clean_sub}")
        return signals

    def search_subreddit(
        self,
        subreddit: str,
        query: str,
        sort: str = 'relevance',
        time_filter: str = 'week',
        limit: int = 25,
    ) -> list[dict]:
        """
        Search within a subreddit for specific terms.

        Useful for targeted scouting when Alex has a specific pain pattern in mind.
        """
        clean_sub = subreddit.replace('r/', '').strip()
        limit = min(limit, 100)

        url = (f"{BASE_URL}/r/{clean_sub}/search.json"
               f"?q={query}&restrict_sr=on&sort={sort}&t={time_filter}&limit={limit}&raw_json=1")

        logger.info(f"Searching r/{clean_sub} for: {query}")
        data = self._request(url)

        if not data:
            return []

        posts = data.get('data', {}).get('children', [])
        signals = []

        for post_wrapper in posts:
            post = post_wrapper.get('data', {})
            if not post:
                continue

            post_id = post.get('id', '')
            created_utc = post.get('created_utc', 0)
            created_at = None
            if created_utc:
                created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()

            signal = {
                'raw_signal_id': f"sig_reddit_t3_{post_id}",
                'source_type': 'reddit',
                'source_subtype': 'post',
                'author_handle': post.get('author', '[deleted]') or None,
                'source_url': f"https://www.reddit.com{post.get('permalink', '')}",
                'title': post.get('title', ''),
                'body': post.get('selftext', ''),
                'created_at': created_at,
                'platform_metadata': {
                    'subreddit': clean_sub,
                    'score': post.get('score', 0),
                    'comment_count': post.get('num_comments', 0),
                    'post_id': post_id,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }

            signals.append(signal)

        logger.info(f"Search found {len(signals)} posts in r/{clean_sub} for: {query}")
        return signals

    def get_available_subreddits(self) -> list[str]:
        """Return list of known pain-rich subreddits (general)."""
        return [
            # Business / SaaS
            'entrepreneur', 'smallbusiness', 'SaaS', 'startups',
            'freelance', 'ecommerce', 'shopify',
            # Tech
            'technology', 'webdev', 'sysadmin', 'devops',
            'aws', 'azure', 'googlecloud', 'selfhosted', 'homelab',
            'programming', 'learnprogramming', 'cscareerquestions',
            # Consumer
            'personalfinance', 'legaladvice', 'povertyfinance',
            'jobs', 'careerguidance', 'recruitinghell',
            # Product complaints
            'mildlyinfuriating', 'assholedesign', 'CrappyDesign',
            'assistance', 'rant', 'ranting',
            # Home / Life
            'HomeImprovement', 'landlord', 'Tenant',
            'insurance', 'tax',
            # Emerging pain sources
            'antiwork', 'WorkReform', 'LateStageCapitalism',
            'Privacy', 'degoogle', 'linux', 'mac', 'windows',
            'apple', 'Android', 'iphone',
            'gaming', 'pcgaming', 'steam',
            'crypto', 'bitcoin', 'defi',
            'healthcare', 'medicine', 'nursing',
            'education', 'teachers', 'college',
            'travel', 'solotravel', 'digitalnomad',
            'fitness', 'nutrition', 'loseit',
            'dating', 'relationship_advice',
            'parenting', 'daddit', 'mommit',
            'pets', 'dogs', 'cats',
            'cars', 'mechanicadvice', 'whatcarshouldIbuy',
            'food', 'cooking', 'MealPrepSunday',
            'gardening', 'IndoorGarden',
            'DIY', 'woodworking', '3Dprinting',
            'photography', 'videography',
            'musicproduction', 'edmproduction',
            'writing', 'selfpublishing',
            'accounting', 'bookkeeping',
            'realestate', 'RealEstateInvesting',
            'dropshipping', 'FulfillmentByAmazon',
        ]
