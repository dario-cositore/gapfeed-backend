"""
Browser HN Adapter — fetches Hacker News via real browser.

Uses the HN website directly instead of the API.
"""

import time
import logging
import json
import random
from pathlib import Path
from datetime import datetime, timezone

from app.adapters.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)


class BrowserHNAdapter:
    """Hacker News adapter using Playwright browser."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_ids = self._load_cursors()

    def _load_cursors(self) -> set:
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

    def _save_cursors(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            ids_list = list(self.seen_ids)[-5000:]
            with open(p, 'w') as f:
                json.dump({'seen_ids': ids_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save cursors: {e}")

    def fetch_top_stories(self, limit: int = 30) -> list[dict]:
        """Fetch top HN stories via browser."""
        page = self.browser.new_page()
        signals = []
        try:
            self.browser.human_delay(1, 3)
            page.goto('https://news.ycombinator.com/', wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 2)
            self.browser.human_scroll(page, 300, 600)

            stories = page.evaluate('''() => {
                const stories = [];
                const rows = document.querySelectorAll('.athing');
                rows.forEach(row => {
                    const titleEl = row.querySelector('.titleline > a');
                    const siteEl = row.querySelector('.sitebit a');
                    const id = row.id;
                    // Get metadata from next sibling row
                    const metaRow = row.nextElementSibling;
                    const scoreEl = metaRow ? metaRow.querySelector('.score') : null;
                    const authorEl = metaRow ? metaRow.querySelector('.hnuser') : null;
                    const ageEl = metaRow ? metaRow.querySelector('.age a') : null;
                    const commentsEl = metaRow ? metaRow.querySelector('a:last-child') : null;
                    
                    if (titleEl) {
                        stories.push({
                            id: id,
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            site: siteEl ? siteEl.textContent.trim() : '',
                            score: scoreEl ? scoreEl.textContent.trim() : '0 points',
                            author: authorEl ? authorEl.textContent.trim() : '',
                            age: ageEl ? ageEl.textContent.trim() : '',
                            hn_url: ageEl ? ageEl.href : '',
                            comments: commentsEl ? commentsEl.textContent.trim() : '',
                        });
                    }
                });
                return stories;
            }''')

            for story in stories[:limit]:
                story_id = story.get('id', '')
                if story_id in self.seen_ids:
                    continue
                self.seen_ids.add(story_id)

                # Parse score
                score_str = story.get('score', '0')
                try:
                    score = int(''.join(filter(str.isdigit, score_str)))
                except ValueError:
                    score = 0

                signal = {
                    'title': story.get('title', ''),
                    'body': story.get('title', ''),
                    'url': story.get('url', '') or f"https://news.ycombinator.com/item?id={story_id}",
                    'source_url': f"https://news.ycombinator.com/item?id={story_id}",
                    'source': 'hackernews',
                    'platform_metadata': {
                        'platform': 'hackernews',
                        'hn_id': story_id,
                        'score': score,
                        'author': story.get('author', ''),
                        'site': story.get('site', ''),
                        'comments': story.get('comments', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            self._save_cursors()
            logger.info(f"HN top: {len(signals)} new stories via browser")
            return signals

        except Exception as e:
            logger.error(f"Browser HN fetch failed: {e}")
            return []
        finally:
            page.close()

    def search_stories(self, query: str, limit: int = 20) -> list[dict]:
        """Search HN via the Algolia search interface."""
        page = self.browser.new_page()
        signals = []
        try:
            url = f'https://hn.algolia.com/?q={query}&sort=byDate'
            self.browser.human_delay(2, 4)
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(1, 3)
            self.browser.human_scroll(page, 300, 600)

            stories = page.evaluate('''() => {
                const stories = [];
                const items = document.querySelectorAll('.Story');
                items.forEach(item => {
                    const titleEl = item.querySelector('.Story_title a');
                    const authorEl = item.querySelector('.Story_meta a');
                    const pointsEl = item.querySelector('.Story_meta span');
                    if (titleEl) {
                        stories.push({
                            title: titleEl.textContent.trim(),
                            url: titleEl.href || '',
                            author: authorEl ? authorEl.textContent.trim() : '',
                            meta: pointsEl ? pointsEl.textContent.trim() : '',
                        });
                    }
                });
                return stories;
            }''')

            for story in stories[:limit]:
                signal = {
                    'title': story.get('title', ''),
                    'body': story.get('title', ''),
                    'url': story.get('url', ''),
                    'source_url': story.get('url', ''),
                    'source': 'hackernews',
                    'platform_metadata': {
                        'platform': 'hackernews',
                        'search_query': query,
                        'author': story.get('author', ''),
                    },
                    'collected_at': datetime.now(timezone.utc).isoformat(),
                }
                signals.append(signal)

            return signals

        except Exception as e:
            logger.error(f"Browser HN search failed: {e}")
            return []
        finally:
            page.close()

    def get_pain_queries(self) -> list[str]:
        """Return pain-focused search queries for HN."""
        return [
            "frustrating tool",
            "why is there no",
            "looking for alternative",
            "I wish there was",
            "open source replacement",
            "better than",
            "simple tool for",
            "lightweight alternative",
        ]
