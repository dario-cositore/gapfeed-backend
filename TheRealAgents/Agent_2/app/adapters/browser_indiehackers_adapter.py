"""
Browser Indie Hackers Adapter — fetches signals via real browser automation.

Renders JavaScript content on Indie Hackers site using Playwright.
"""

import time
import logging
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from app.adapters.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class BrowserIndieHackersAdapter(BrowserManager):
    """Indie Hackers adapter using Playwright via shared BrowserManager."""

    ADAPTER_NAME = 'indiehackers'
    BASE_URL = 'https://www.indiehackers.com/'
    PAGES_TO_SCOUT = {
        'homepage': 'https://www.indiehackers.com/',
        'forum': 'https://www.indiehackers.com/forum',
        'products': 'https://www.indiehackers.com/products',
    }

    def __init__(self, cursor_file: str = None):
        super().__init__()
        self.cursor_file = cursor_file or str(
            Path(__file__).resolve().parent.parent / 'state' / 'cursors' / 'browser_indiehackers.json'
        )
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
            logger.warning(f"Failed to save IH cursors: {e}")

    def fetch_page(self, url: str, page_type: str = 'unknown') -> list[dict]:
        """Navigate to URL, handle cookies/scrolling, extract signals."""
        page = self.new_page()
        signals = []

        try:
            self.human_delay(2, 5)
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            self.human_delay(1, 3)

            # Handle cookie consent
            try:
                self.accept_cookies(page)
            except Exception:
                pass

            # Scroll to load content
            for _ in range(3):
                self.human_scroll(page, 300, 700)
                self.human_delay(0.5, 1.5)

            # Extract posts via JS
            posts = page.evaluate('''() => {
                let items = [];
                const containers = document.querySelectorAll('article, [class*="post"], [class*="topic"], [class*="product"], [class*="thread"]');
                
                containers.forEach(item => {
                    const titleEl = item.querySelector('h2 a, h3 a, a[class*="title"], a[class*="heading"]');
                    if (!titleEl || !titleEl.href) return;

                    const authorEl = item.querySelector('[class*="author"], [class*="user"], [rel="author"]');
                    const snippetEl = item.querySelector('[class*="snippet"], [class*="description"], [class*="body"], p');
                    const votesEl = item.querySelector('[class*="vote"], [class*="upvote"], [class*="like"]');
                    const commentsEl = item.querySelector('[class*="comment"], [class*="reply"], [class*="response"]');
                    const dateEl = item.querySelector('time, [class*="date"], [class*="time"]');

                    items.push({
                        title: (titleEl.innerText || titleEl.textContent || '').trim(),
                        url: titleEl.href,
                        description: snippetEl ? (snippetEl.innerText || '').trim().substring(0, 500) : '',
                        author: authorEl ? (authorEl.innerText || '').trim() : 'unknown',
                        upvotes: votesEl ? parseInt(votesEl.innerText.replace(/[^0-9]/g, '')) || 0 : 0,
                        comments: commentsEl ? parseInt(commentsEl.innerText.replace(/[^0-9]/g, '')) || 0 : 0,
                        created_at: dateEl ? (dateEl.getAttribute('datetime') || dateEl.textContent.trim()) : '',
                    });
                });
                return items;
            }''')

            for post in posts:
                post_url = post.get('url', '')
                if not post_url or post_url in self.seen_urls:
                    continue

                signal = {
                    'source': 'indiehackers',
                    'url': post_url,
                    'title': post.get('title', 'Untitled'),
                    'content': post.get('description', post.get('title', ''))[:2000],
                    'author': post.get('author', 'unknown'),
                    'created_at': post.get('created_at', datetime.now(timezone.utc).isoformat()),
                    'platform_id': post_url,
                    'signal_type': 'post',
                    'metadata': {
                        'upvotes': post.get('upvotes', 0),
                        'comments': post.get('comments', 0),
                        'page_type': page_type,
                    }
                }
                signals.append(signal)
                self.seen_urls.add(post_url)

            if signals:
                self._save_seen()

            logger.info(f"Indie Hackers: fetched {len(signals)} new signals from {page_type}")
            return signals

        except Exception as e:
            logger.error(f"Browser IH fetch failed for {url}: {e}")
            return []
        finally:
            page.close()

    def scout(self, max_results: int = 30) -> list[dict]:
        """Scout main IH pages for new signals."""
        all_signals = []
        self.start()

        pages = list(self.PAGES_TO_SCOUT.items())
        random.shuffle(pages)

        for page_name, url in pages:
            if len(all_signals) >= max_results:
                break

            new_signals = self.fetch_page(url, page_type=page_name)
            all_signals.extend(new_signals[:max_results - len(all_signals)])
            self.human_delay(random.uniform(3, 7))

        logger.info(f"Indie Hackers scout complete: {len(all_signals)} total signals")
        return all_signals[:max_results]
