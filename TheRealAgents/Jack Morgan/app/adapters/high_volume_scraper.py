"""
High-volume API scraper for Jack Morgan.

NO search engines (they all block headless browsers).
Uses APIs and RSS feeds that don't have bot detection.

Target: 100k+ signals/day
"""

import time
import logging
import json
import random
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

USER_AGENT = "TuXo:PainSignalScout/2.0 (research)"

# === REDDIT (unlimited, no auth needed) ===
# Use old.reddit.com JSON API - returns JSON directly
REDDIT_SUBREDDITS = [
    # Business & Startups
    'entrepreneur', 'startups', 'smallbusiness', 'sideproject', 'SaaS',
    'freelance', 'solopreneur', 'microsaas', 'indiehackers', 'growmybusiness',
    'businessideas', 'startup_ideas', 'ecommerce', 'dropshipping', 'passive_income',
    
    # Developer tools
    'webdev', 'programming', 'learnprogramming', 'devops', 'selfhosted',
    'homelab', 'linux', 'python', 'javascript', 'reactjs', 'node',
    'docker', 'kubernetes', 'aws', 'cloudcomputing', 'cscareerquestions',
    
    # Productivity & Tools
    'productivity', 'NotionSo', 'todoist', 'obsidianmd', 'logseq',
    'PKMS', 'secondbrain', 'quantifiedself', 'getdisciplined', 'gtd',
    
    # Design & Creative
    'design', 'UI_Design', 'UXDesign', 'web_design', 'graphic_design',
    'FigmaDesign', 'AdobeIllustrator', 'blender', 'IndieDev',
    
    # Marketing & Growth
    'marketing', 'digital_marketing', 'SEO', 'content_marketing',
    'emailmarketing', 'socialmedia', 'copywriting', 'growthhacking',
    
    # Specific niches
    'realestate', 'personalfinance', 'investing', 'cryptocurrency',
    'fitness', 'nutrition', 'meditation', 'productivity',
    'cooking', 'photography', 'musicproduction', 'podcasting',
    'teaching', 'onlinecourses', 'tutoring', 'education',
    
    # Pain-focused
    'mildlyinfuriating', 'assholedesign', 'crappydesign', 'softwaregore',
    'techsupport', 'sysadmin', 'ITCareerQuestions', 'networking',
]

# === HIGH-VOLUME RSS FEEDS ===
RSS_FEEDS = {
    'tech_news': [
        'https://feeds.feedburner.com/TechCrunch/',
        'https://www.wired.com/feed/rss',
        'https://arstechnica.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://news.ycombinator.com/rss',
        'https://dev.to/feed',
        'https://medium.com/feed/tag/programming',
        'https://medium.com/feed/tag/startup',
    ],
    'product_updates': [
        'https://www.producthunt.com/feed',
        'https://angelogladding.com/feed.xml',
        'https://blog.indiehackers.com/feed',
    ],
    'developer_blogs': [
        'https://blog.github.com/feed/',
        'https://engineering.fb.com/feed/',
        'https://netflixtechblog.com/feed',
        'https://uber.com/blog/engineering/feed',
        'https://eng.uber.com/feed/',
        'https://blog.cloudflare.com/rss/',
    ],
}


class HighVolumeScraper:
    """High-volume API scraper for Jack Morgan."""

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json, text/xml, application/rss+xml',
        })
        self.cursor_file = cursor_file
        self.seen_urls = self._load_seen()

    def _load_seen(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    return set(json.load(f).get('seen_urls', []))
        except Exception:
            pass
        return set()

    def _save_seen(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'seen_urls': list(self.seen_urls)[-50000:]}, f)
        except Exception as e:
            logger.warning(f"Failed to save seen URLs: {e}")

    def _make_signal(self, title: str, body: str, url: str, source: str,
                     metadata: dict = None) -> Optional[dict]:
        if not url or url in self.seen_urls:
            return None
        self.seen_urls.add(url)
        return {
            'title': title or '',
            'body': (body or '')[:2000],
            'url': url,
            'source_url': url,
            'source': source,
            'platform_metadata': metadata or {},
            'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    # ==================== REDDIT ====================

    def fetch_reddit_subreddit(self, subreddit: str, sort: str = 'new',
                                limit: int = 100) -> list[dict]:
        """Fetch posts from a subreddit via JSON API (no auth needed)."""
        signals = []
        try:
            url = f'https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}'
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                logger.debug(f"Reddit r/{subreddit} returned {resp.status_code}")
                return signals

            data = resp.json()
            posts = data.get('data', {}).get('children', [])

            for post in posts:
                p = post.get('data', {})
                signal = self._make_signal(
                    title=p.get('title', ''),
                    body=p.get('selftext', '')[:1500],
                    url=f"https://reddit.com{p.get('permalink', '')}",
                    source='reddit',
                    metadata={
                        'subreddit': subreddit,
                        'score': p.get('score', 0),
                        'comments': p.get('num_comments', 0),
                        'platform': 'reddit',
                    }
                )
                if signal:
                    signals.append(signal)

            logger.info(f"Reddit r/{subreddit}: {len(signals)} new signals")
        except Exception as e:
            logger.error(f"Reddit r/{subreddit} failed: {e}")

        return signals

    def fetch_reddit_batch(self, subs_per_round: int = 15) -> list[dict]:
        """Fetch from multiple subreddits in one batch."""
        selected = random.sample(REDDIT_SUBREDDITS, min(subs_per_round, len(REDDIT_SUBREDDITS)))
        all_signals = []

        for sub in selected:
            signals = self.fetch_reddit_subreddit(sub, limit=100)
            all_signals.extend(signals)
            time.sleep(0.5)  # Rate limit: Reddit allows 100/min without auth

        logger.info(f"Reddit batch ({len(selected)} subs): {len(all_signals)} total signals")
        return all_signals

    # ==================== HACKER NEWS ====================

    def fetch_hn(self, limit: int = 200) -> list[dict]:
        """Fetch top/new stories from HN Firebase API (unlimited)."""
        signals = []
        try:
            # Get top story IDs
            resp = self.session.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
            story_ids = resp.json()[:limit]

            for sid in story_ids[:50]:  # Fetch details for first 50
                try:
                    item_resp = self.session.get(
                        f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=5)
                    item = item_resp.json()
                    if not item or item.get('type') != 'story':
                        continue

                    signal = self._make_signal(
                        title=item.get('title', ''),
                        body=item.get('text', '') or '',
                        url=item.get('url', f"https://news.ycombinator.com/item?id={sid}"),
                        source='hackernews',
                        metadata={
                            'score': item.get('score', 0),
                            'comments': item.get('descendants', 0),
                            'by': item.get('by', ''),
                            'platform': 'hackernews',
                        }
                    )
                    if signal:
                        signals.append(signal)
                except Exception:
                    continue

            logger.info(f"HN: {len(signals)} new signals")
        except Exception as e:
            logger.error(f"HN failed: {e}")

        return signals

    # ==================== DEV.TO ====================

    def fetch_devto(self, tags: list[str] = None, limit: int = 30) -> list[dict]:
        """Fetch articles from Dev.to REST API (no auth needed, 3000/hour)."""
        signals = []
        if not tags:
            tags = ['productivity', 'startup', 'saas', 'opensource', 'webdev',
                    'javascript', 'python', 'tutorial', 'beginners', 'discuss']

        tag = random.choice(tags)
        try:
            url = f'https://dev.to/api/articles?tag={tag}&top=7&per_page={limit}'
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return signals

            articles = resp.json()
            for article in articles:
                signal = self._make_signal(
                    title=article.get('title', ''),
                    body=article.get('description', '')[:1000],
                    url=article.get('url', ''),
                    source='devto',
                    metadata={
                        'tag': tag,
                        'reactions': article.get('positive_reactions_count', 0),
                        'comments': article.get('comments_count', 0),
                        'platform': 'devto',
                    }
                )
                if signal:
                    signals.append(signal)

            logger.info(f"Dev.to tag={tag}: {len(signals)} new signals")
        except Exception as e:
            logger.error(f"Dev.to failed: {e}")

        return signals

    # ==================== STACK OVERFLOW ====================

    def fetch_stackoverflow(self, tags: list[str] = None, limit: int = 30) -> list[dict]:
        """Fetch questions from Stack Overflow API (300/day free)."""
        signals = []
        if not tags:
            tags = ['python', 'javascript', 'react', 'node.js', 'docker',
                    'aws', 'sql', 'api', 'git', 'linux']

        tag = random.choice(tags)
        try:
            url = f'https://api.stackexchange.com/2.3/questions?order=desc&sort=activity&tagged={tag}&site=stackoverflow&pagesize={limit}'
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return signals

            data = resp.json()
            for q in data.get('items', []):
                signal = self._make_signal(
                    title=q.get('title', ''),
                    body=q.get('tags', ''),
                    url=q.get('link', ''),
                    source='stackoverflow',
                    metadata={
                        'tag': tag,
                        'score': q.get('score', 0),
                        'answers': q.get('answer_count', 0),
                        'views': q.get('view_count', 0),
                        'platform': 'stackoverflow',
                    }
                )
                if signal:
                    signals.append(signal)

            logger.info(f"SO tag={tag}: {len(signals)} new signals")
        except Exception as e:
            logger.error(f"SO failed: {e}")

        return signals

    # ==================== GITHUB ====================

    def fetch_github_issues(self, topics: list[str] = None, limit: int = 30) -> list[dict]:
        """Search GitHub issues/discussions (no auth needed for public)."""
        signals = []
        if not topics:
            topics = ['tool+request', 'feature+request', 'bug+report',
                      'looking+for', 'need+help', 'alternative+to']

        topic = random.choice(topics)
        try:
            url = f'https://api.github.com/search/issues?q={topic}+in:title&sort=created&order=desc&per_page={limit}'
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return signals

            data = resp.json()
            for item in data.get('items', []):
                signal = self._make_signal(
                    title=item.get('title', ''),
                    body=(item.get('body', '') or '')[:1000],
                    url=item.get('html_url', ''),
                    source='github',
                    metadata={
                        'query': topic,
                        'comments': item.get('comments', 0),
                        'state': item.get('state', ''),
                        'platform': 'github',
                    }
                )
                if signal:
                    signals.append(signal)

            logger.info(f"GitHub search '{topic}': {len(signals)} new signals")
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")

        return signals

    # ==================== RSS ====================

    def fetch_rss(self, category: str = None, limit: int = 30) -> list[dict]:
        """Fetch from RSS feeds."""
        import xml.etree.ElementTree as ET
        signals = []

        if category:
            feeds = {category: RSS_FEEDS.get(category, [])}
        else:
            feeds = RSS_FEEDS

        for cat, urls in feeds.items():
            for feed_url in urls[:2]:  # 2 feeds per category
                try:
                    resp = self.session.get(feed_url, timeout=10)
                    if resp.status_code != 200:
                        continue

                    root = ET.fromstring(resp.content)

                    # RSS 2.0
                    items = root.findall('.//item')
                    if not items:
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        items = root.findall('.//atom:entry', ns)

                    for item in items[:limit]:
                        title = item.findtext('title', '')
                        link = item.findtext('link', '')
                        desc = item.findtext('description', '')

                        signal = self._make_signal(
                            title=title,
                            body=desc[:1000],
                            url=link,
                            source=f'rss_{cat}',
                            metadata={'feed': feed_url, 'platform': 'rss'}
                        )
                        if signal:
                            signals.append(signal)

                except ET.ParseError:
                    logger.debug(f"RSS parse failed for {feed_url}")
                except Exception as e:
                    logger.error(f"RSS {feed_url} failed: {e}")

        logger.info(f"RSS ({category or 'all'}): {len(signals)} new signals")
        return signals

    # ==================== FULL ROUND ====================

    def scout_round(self, reddit_subs: int = 15, devto_tags: int = 1,
                    so_tags: int = 1, github_searches: int = 1,
                    rss_categories: int = 2) -> list[dict]:
        """
        One full scouting round. Combines all sources for maximum throughput.
        Expected: 1500-3000 signals per round.
        """
        all_signals = []

        # Reddit (highest volume)
        reddit_signals = self.fetch_reddit_batch(subs_per_round=reddit_subs)
        all_signals.extend(reddit_signals)

        # HN
        hn_signals = self.fetch_hn(limit=100)
        all_signals.extend(hn_signals)

        # Dev.to
        for _ in range(devto_tags):
            devto_signals = self.fetch_devto(limit=30)
            all_signals.extend(devto_signals)

        # Stack Overflow
        for _ in range(so_tags):
            so_signals = self.fetch_stackoverflow(limit=30)
            all_signals.extend(so_signals)

        # GitHub
        for _ in range(github_searches):
            gh_signals = self.fetch_github_issues(limit=30)
            all_signals.extend(gh_signals)

        # RSS
        for _ in range(rss_categories):
            rss_signals = self.fetch_rss(limit=20)
            all_signals.extend(rss_signals)

        self._save_seen()
        logger.info(f"Scout round complete: {len(all_signals)} total signals")
        return all_signals
