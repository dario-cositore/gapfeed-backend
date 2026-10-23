"""
Browser Product Hunt Adapter — fetches signals via real browser automation.

Product Hunt has bot protection, so we use Playwright to browse like a human.
Captures product launches, discussions, and pain signals from PH community.
"""

import time
import logging
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)


class BrowserProductHuntAdapter:
    """Product Hunt adapter using Playwright via shared BrowserManager."""

    ADAPTER_NAME = 'producthunt'
    BASE_URL = 'https://www.producthunt.com'
    PAGES_TO_SCOUT = {
        'today': 'https://www.producthunt.com/',
        'newest': 'https://www.producthunt.com/newest',
        'discussions': 'https://www.producthunt.com/discussions',
    }

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_ids = self._load_seen_ids()

    def _load_seen_ids(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_ids', []))
        except Exception:
            pass
        return set()

    def _save_seen_ids(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            ids_list = list(self.seen_ids)[-10000:]
            with open(p, 'w') as f:
                json.dump({'seen_ids': ids_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save seen IDs: {e}")

    def _parse_products(self, page) -> list[dict]:
        """Parse product cards from the current page."""
        try:
            products = page.evaluate('''() => {
                const products = [];
                // PH product cards
                document.querySelectorAll('[data-test="post-item"]').forEach(el => {
                    const titleEl = el.querySelector('a[href*="/posts/"] h3, [data-test="post-name"]');
                    const descEl = el.querySelector('[data-test="post-tagline"], .styles_tagline__ string');
                    const linkEl = el.querySelector('a[href*="/posts/"]');
                    const votesEl = el.querySelector('[data-test="vote-button"], .styles_count__ string');
                    if (titleEl) {
                        products.push({
                            title: titleEl.textContent.trim(),
                            description: descEl ? descEl.textContent.trim() : '',
                            url: linkEl ? linkEl.href : '',
                            votes: votesEl ? parseInt(votesEl.textContent) || 0 : 0,
                        });
                    }
                });
                // Fallback: any product links
                if (products.length === 0) {
                    document.querySelectorAll('a[href*="/posts/"]').forEach(a => {
                        if (a.textContent.trim().length > 3) {
                            products.push({
                                title: a.textContent.trim(),
                                description: '',
                                url: a.href,
                                votes: 0,
                            });
                        }
                    });
                }
                return products;
            }''')
            return products or []
        except Exception as e:
            logger.error(f"Failed to parse products: {e}")
            return []

    def fetch_latest(self, limit: int = 30) -> list[dict]:
        """Fetch latest products from Product Hunt."""
        all_signals = []

        for page_name, url in self.PAGES_TO_SCOUT.items():
            page = self.browser.new_page()
            try:
                self.browser.human_delay(1, 3)
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                self.browser.human_delay(1, 2)
                self.browser.accept_cookies(page)

                # Scroll to load more content
                for _ in range(3):
                    self.browser.human_scroll(page, 400, 800)
                    self.browser.human_delay(0.5, 1.5)

                products = self._parse_products(page)

                for product in products[:limit]:
                    product_id = product.get('url', '')
                    if product_id in self.seen_ids:
                        continue
                    self.seen_ids.add(product_id)

                    signal = {
                        'title': product.get('title', ''),
                        'body': product.get('description', ''),
                        'url': product.get('url', ''),
                        'source_url': product.get('url', ''),
                        'source': 'producthunt',
                        'platform_metadata': {
                            'page': page_name,
                            'votes': product.get('votes', 0),
                            'platform': 'producthunt',
                        },
                        'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    }
                    all_signals.append(signal)

                logger.info(f"ProductHunt {page_name}: {len(products)} products, {len(all_signals)} new signals")

            except Exception as e:
                logger.error(f"ProductHunt {page_name} failed: {e}")
            finally:
                page.close()

        self._save_seen_ids()
        return all_signals[:limit]

    def fetch_discussions(self, limit: int = 20) -> list[dict]:
        """Fetch PH discussions — community pain signals."""
        page = self.browser.new_page()
        all_signals = []
        try:
            self.browser.human_delay(1, 2)
            page.goto('https://www.producthunt.com/discussions', wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 2)

            for _ in range(3):
                self.browser.human_scroll(page, 300, 600)
                self.browser.human_delay(0.5, 1)

            discussions = page.evaluate('''() => {
                const items = [];
                document.querySelectorAll('a[href*="/discussions/"]').forEach(a => {
                    const title = a.textContent.trim();
                    if (title.length > 10) {
                        items.push({
                            title: title,
                            url: a.href,
                        });
                    }
                });
                return items;
            }''')

            for disc in (discussions or [])[:limit]:
                disc_id = disc.get('url', '')
                if disc_id in self.seen_ids:
                    continue
                self.seen_ids.add(disc_id)

                signal = {
                    'title': disc.get('title', ''),
                    'body': '',
                    'url': disc.get('url', ''),
                    'source_url': disc.get('url', ''),
                    'source': 'producthunt',
                    'platform_metadata': {
                        'page': 'discussions',
                        'platform': 'producthunt',
                    },
                    'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                }
                all_signals.append(signal)

            logger.info(f"ProductHunt discussions: {len(discussions or [])} found, {len(all_signals)} new")
        except Exception as e:
            logger.error(f"ProductHunt discussions failed: {e}")
        finally:
            page.close()

        self._save_seen_ids()
        return all_signals

    def get_tag_rotation(self) -> list[str]:
        """Return tags for rotation."""
        return [
            'developer-tools', 'artificial-intelligence', 'saas', 'open-source',
            'productivity', 'marketing', 'design-tools', 'no-code', 'analytics',
            'social-media', 'e-commerce', 'fintech', 'health', 'education',
        ]
