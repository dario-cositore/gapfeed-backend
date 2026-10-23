"""
Browser DevTo Adapter — fetches Dev.to articles via real browser.
"""

import time
import logging
import json
import random
from pathlib import Path
from datetime import datetime, timezone

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)

TAG_ROTATION = [
    'productivity', 'webdev', 'beginners', 'javascript', 'python',
    'devops', 'opensource', 'discuss', 'career', 'tutorial',
    'ai', 'machinelearning', 'startup', 'saas', 'testing',
]


class BrowserDevToAdapter:
    """Dev.to adapter using Playwright browser."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_urls = self._load_cursors()

    def _load_cursors(self) -> set:
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

    def _save_cursors(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, 'w') as f:
                json.dump({'seen_urls': list(self.seen_urls)[-5000]}, f)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def get_tag_rotation(self) -> list[str]:
        return TAG_ROTATION

    def fetch_recent(self, tag: str = None, limit: int = 30) -> list[dict]:
        """Fetch recent Dev.to articles, optionally filtered by tag."""
        page = self.browser.new_page()
        signals = []
        try:
            if tag:
                url = f'https://dev.to/t/{tag}?sort=latest'
            else:
                url = 'https://dev.to/latest'

            self.browser.human_delay(1, 3)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 2)
            self.browser.human_scroll(page, 400, 800)

            articles = page.evaluate('''() => {
                const articles = [];
                const items = document.querySelectorAll('.crayons-story, .substories .crayons-story');
                items.forEach(item => {
                    const titleEl = item.querySelector('.crayons-story__title a, h2 a');
                    const bodyEl = item.querySelector('.crayons-story__body');
                    const tagEls = item.querySelectorAll('.crayons-tag');
                    const timeEl = item.querySelector('time');
                    const authorEl = item.querySelector('.crayons-story__secondary a');
                    
                    if (titleEl) {
                        articles.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            body: bodyEl ? bodyEl.textContent.trim().substring(0, 500) : '',
                            tags: Array.from(tagEls).map(t => t.textContent.trim()),
                            date: timeEl ? timeEl.getAttribute('datetime') : '',
                            author: authorEl ? authorEl.textContent.trim() : '',
                        });
                    }
                });
                return articles;
            }''')

            for article in articles[:limit]:
                url = article.get('url', '')
                if url in self.seen_urls:
                    continue
                self.seen_urls.add(url)

                signal = {
                    'title': article.get('title', ''),
                    'body': article.get('body', '') or article.get('title', ''),
                    'url': url,
                    'source_url': url,
                    'source': 'devto',
                    'platform_metadata': {
                        'platform': 'devto',
                        'tag': tag or 'general',
                        'tags': article.get('tags', []),
                        'author': article.get('author', ''),
                        'created_utc': article.get('date', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            self._save_cursors()
            logger.info(f"Dev.to {tag or 'latest'}: {len(signals)} new articles via browser")
            return signals

        except Exception as e:
            logger.error(f"Browser Dev.to fetch failed: {e}")
            return []
        finally:
            page.close()

    def fetch_latest(self, limit: int = 30) -> list[dict]:
        """Fetch latest articles from Dev.to."""
        return self.fetch_recent(tag=None, limit=limit)
