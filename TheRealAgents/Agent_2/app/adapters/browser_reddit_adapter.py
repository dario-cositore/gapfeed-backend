"""
Browser Reddit Adapter — fetches posts via real browser automation.

Browses subreddits like a human user. Parses rendered HTML instead of
relying on JSON API that can be rate-limited or blocked.
"""

import time
import logging
import json
import random
from pathlib import Path
from datetime import datetime, timezone

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)

SUBREDDITS = [
    'SaaS', 'startups', 'Entrepreneur', 'freelance', 'smallbusiness',
    'webdev', 'programming', 'selfhosted', 'ProductManagement',
    'devops', 'machinelearning', 'artificial', 'ChatGPT',
    'solopreneur', 'sideproject', 'growmybusiness', 'indiehackers',
    'juststart', 'ecommerce', 'dropship', 'remotework', 'digitalnomad',
    'sysadmin', 'dataengineering', 'analytics', 'marketing',
    'content_marketing', 'SEO', 'socialmedia', 'copywriting',
]


class BrowserRedditAdapter:
    """Reddit adapter using Playwright browser."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.cursors = self._load_cursors()

    def _load_cursors(self) -> dict:
        if not self.cursor_file:
            return {}
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_cursors(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump(self.cursors, f)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def get_available_subreddits(self) -> list[str]:
        return SUBREDDITS

    def fetch_subreddit_posts(self, subreddit: str, sort: str = 'new', limit: int = 30) -> list[dict]:
        """
        Fetch posts from a subreddit via browser.
        Returns list of raw signal dicts.
        """
        page = self.browser.new_page()
        signals = []
        try:
            url = f'https://old.reddit.com/r/{subreddit}/{sort}/'
            self.browser.human_delay(2, 5)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 3)

            # Accept cookies
            self.browser.accept_cookies(page)

            # Scroll to load posts
            self.browser.human_scroll(page, 400, 800)
            self.browser.human_delay(1, 2)

            # Parse posts from old.reddit.com (simpler HTML)
            posts = page.evaluate('''() => {
                const posts = [];
                const items = document.querySelectorAll('.thing.link');
                items.forEach(item => {
                    const titleEl = item.querySelector('a.title');
                    const authorEl = item.querySelector('.author');
                    const scoreEl = item.querySelector('.score.unvoted');
                    const commentsEl = item.querySelector('.comments');
                    const timeEl = item.querySelector('time');
                    const selftextEl = item.querySelector('.expando .md');
                    
                    if (titleEl) {
                        posts.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            author: authorEl ? authorEl.textContent.trim() : '',
                            score: scoreEl ? scoreEl.textContent.trim() : '0',
                            comments_url: commentsEl ? commentsEl.href : '',
                            comments_text: commentsEl ? commentsEl.textContent.trim() : '0 comments',
                            created: timeEl ? timeEl.getAttribute('datetime') : '',
                            selftext: selftextEl ? selftextEl.textContent.trim().substring(0, 1000) : '',
                        });
                    }
                });
                return posts;
            }''')

            cursor_key = f"r/{subreddit}"
            last_seen = self.cursors.get(cursor_key, '')

            for post in posts[:limit]:
                # Skip if we've seen this post
                post_id = post.get('url', '')
                if post_id == last_seen:
                    break

                # Parse comment count
                comments_str = post.get('comments_text', '0')
                try:
                    comment_count = int(''.join(filter(str.isdigit, comments_str.split('comment')[0] or '0')))
                except (ValueError, IndexError):
                    comment_count = 0

                signal = {
                    'title': post.get('title', ''),
                    'body': post.get('selftext', '') or post.get('title', ''),
                    'url': post.get('url', ''),
                    'source_url': post.get('comments_url', '') or post.get('url', ''),
                    'source': 'reddit',
                    'platform_metadata': {
                        'platform': 'reddit',
                        'subreddit': subreddit,
                        'author': post.get('author', ''),
                        'score': post.get('score', '0'),
                        'comment_count': comment_count,
                        'created_utc': post.get('created', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            # Update cursor
            if posts:
                self.cursors[cursor_key] = posts[0].get('url', '')
                self._save_cursors()

            logger.info(f"Reddit r/{subreddit}: {len(signals)} new posts via browser")
            return signals

        except Exception as e:
            logger.error(f"Browser Reddit fetch failed for r/{subreddit}: {e}")
            return []
        finally:
            page.close()

    def search_subreddit(self, subreddit: str, query: str, limit: int = 25) -> list[dict]:
        """Search within a subreddit via browser."""
        page = self.browser.new_page()
        signals = []
        try:
            url = f'https://old.reddit.com/r/{subreddit}/search?q={query}&restrict_sr=on&sort=new'
            self.browser.human_delay(2, 5)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 3)
            self.browser.human_scroll(page, 300, 600)

            posts = page.evaluate('''() => {
                const posts = [];
                const items = document.querySelectorAll('.thing.link, .search-result');
                items.forEach(item => {
                    const titleEl = item.querySelector('a.title, .search-title a');
                    const authorEl = item.querySelector('.author');
                    const selftextEl = item.querySelector('.expando .md, .search-result-body');
                    if (titleEl) {
                        posts.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            author: authorEl ? authorEl.textContent.trim() : '',
                            selftext: selftextEl ? selftextEl.textContent.trim().substring(0, 1000) : '',
                        });
                    }
                });
                return posts;
            }''')

            for post in posts[:limit]:
                signal = {
                    'title': post.get('title', ''),
                    'body': post.get('selftext', '') or post.get('title', ''),
                    'url': post.get('url', ''),
                    'source_url': post.get('url', ''),
                    'source': 'reddit',
                    'platform_metadata': {
                        'platform': 'reddit',
                        'subreddit': subreddit,
                        'search_query': query,
                        'author': post.get('author', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Browser Reddit search failed: {e}")
            return []
        finally:
            page.close()
