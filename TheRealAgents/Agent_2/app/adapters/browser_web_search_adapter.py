"""
Browser Web Search Adapter — finds pain signals via real browser automation.

Uses Playwright to visit Brave Search like a human: type queries, scroll results,
parse HTML from the rendered page.

OPTIMIZED for 100k+ signals/day:
- Brave Search (not DDG - DDG blocks headless browsers)
- Massive query bank (300+ queries)
- Fast sequential searches with minimal delays
- Batch processing
"""

import time
import logging
import json
import random
from pathlib import Path
from typing import Optional

from app.adapters.browser_manager import get_browser_manager
from app.adapters.query_bank import PAIN_QUERIES, TRENDING_QUERIES, NICHE_QUERIES, FORUM_QUERIES, get_query_count

logger = logging.getLogger(__name__)


class BrowserSearchAdapter:
    """Web search adapter using Playwright browser with Brave Search."""

    def __init__(self, cursor_file: str = None):
        self.browser = get_browser_manager()
        self.cursor_file = cursor_file
        self.seen_urls = self._load_seen_urls()

    def _load_seen_urls(self) -> set:
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

    def _save_seen_urls(self):
        if not self.cursor_file:
            return
        try:
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            urls_list = list(self.seen_urls)[-50000:]
            with open(p, 'w') as f:
                json.dump({'seen_urls': urls_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save seen URLs: {e}")

    def search_brave(self, query: str, max_results: int = 25) -> list[dict]:
        """
        Search Brave via real browser. Returns list of {title, url, snippet}.
        Brave doesn't block headless browsers like DDG/Google do.
        """
        page = self.browser.new_page()
        try:
            self.browser.human_delay(0.3, 1.0)
            encoded_query = query.replace(' ', '+')
            page.goto(f'https://search.brave.com/search?q={encoded_query}',
                      wait_until='domcontentloaded', timeout=15000)
            self.browser.human_delay(0.5, 1.5)

            # Scroll to load more results
            self.browser.human_scroll(page, 300, 600)
            self.browser.human_delay(0.3, 0.8)

            # Parse results from Brave's HTML structure
            results = page.evaluate('''() => {
                const results = [];
                document.querySelectorAll('[data-type="web"]').forEach(item => {
                    const linkEl = item.querySelector('a[href]');
                    const titleEl = item.querySelector('.heading-serpresult, .snippet-title, a[href] span');
                    const snippetEl = item.querySelector('.snippet-description, .snippet-content');
                    if (linkEl && linkEl.href && !linkEl.href.includes('brave.com')) {
                        results.push({
                            title: titleEl ? titleEl.textContent.trim() : linkEl.textContent.trim(),
                            url: linkEl.href,
                            snippet: snippetEl ? snippetEl.textContent.trim() : '',
                        });
                    }
                });
                // Fallback: grab any result links
                if (results.length === 0) {
                    document.querySelectorAll('.snippet a[href], .result a[href]').forEach(a => {
                        if (a.href && !a.href.includes('brave.com') && a.textContent.trim().length > 3) {
                            results.push({
                                title: a.textContent.trim().substring(0, 200),
                                url: a.href,
                                snippet: '',
                            });
                        }
                    });
                }
                return results;
            }''')

            filtered = []
            for r in results[:max_results]:
                url = r.get('url', '')
                if url and url not in self.seen_urls and not url.startswith('https://search.brave.com'):
                    self.seen_urls.add(url)
                    filtered.append({
                        'title': r.get('title', ''),
                        'url': url,
                        'snippet': r.get('snippet', ''),
                        'source': 'web_search',
                        'source_url': url,
                    })

            logger.info(f"Brave search '{query}': {len(results)} results, {len(filtered)} new")
            return filtered

        except Exception as e:
            logger.error(f"Brave search failed for '{query}': {e}")
            return []
        finally:
            page.close()

    def _build_signal(self, result: dict, query: str) -> dict:
        """Convert a search result into a raw signal dict."""
        return {
            'title': result['title'],
            'body': result.get('snippet', ''),
            'url': result['url'],
            'source_url': result['url'],
            'source': 'web_search',
            'platform_metadata': {
                'search_query': query,
                'platform': 'brave',
            },
            'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }

    def search_pain_patterns(self, queries_per_round: int = 25) -> list[dict]:
        """
        Run pain-focused searches using browser automation.
        MASSIVE query bank, sequential fast execution.
        Returns raw signal dicts ready for normalization.
        """
        # Pick queries from each category
        pain_n = min(queries_per_round // 2, len(PAIN_QUERIES))
        trending_n = min(queries_per_round // 6, len(TRENDING_QUERIES))
        niche_n = min(queries_per_round // 6, len(NICHE_QUERIES))
        forum_n = min(queries_per_round // 6, len(FORUM_QUERIES))

        selected = []
        if pain_n > 0:
            selected.extend(random.sample(PAIN_QUERIES, pain_n))
        if trending_n > 0:
            selected.extend(random.sample(TRENDING_QUERIES, trending_n))
        if niche_n > 0:
            selected.extend(random.sample(NICHE_QUERIES, niche_n))
        if forum_n > 0:
            selected.extend(random.sample(FORUM_QUERIES, forum_n))
        random.shuffle(selected)

        logger.info(f"Running {len(selected)} Brave searches "
                    f"(pain={pain_n}, trending={trending_n}, niche={niche_n}, forum={forum_n})")

        all_signals = []
        for query in selected:
            try:
                results = self.search_brave(query, max_results=15)
                for r in results:
                    signal = self._build_signal(r, query)
                    all_signals.append(signal)
                logger.info(f"Query '{query}': {len(results)} new results")
            except Exception as e:
                logger.error(f"Query '{query}' failed: {e}")

        self._save_seen_urls()
        logger.info(f"Total signals from {len(selected)} queries: {len(all_signals)}")
        return all_signals

    def fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content via browser (bypasses Cloudflare/Vercel)."""
        page = self.browser.new_page()
        try:
            self.browser.human_delay(0.3, 0.8)
            page.goto(url, wait_until='domcontentloaded', timeout=12000)
            self.browser.human_scroll(page, 200, 500)
            self.browser.human_delay(0.3, 0.8)
            text = page.evaluate('() => document.body.innerText')
            return text[:5000] if text else None
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
        finally:
            page.close()
