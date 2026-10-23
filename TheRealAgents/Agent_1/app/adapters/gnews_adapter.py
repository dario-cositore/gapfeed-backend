"""
Google News adapter — finds pain signals in news articles.

Uses Google News RSS (free, no API key, no auth).
RSS URLs: https://news.google.com/rss/search?q=query&hl=en-US&gl=US&ceid=US:en

Cursor-based: tracks last-seen URLs to avoid re-processing.
"""

import time
import logging
import json
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from typing import Optional

logger = logging.getLogger(__name__)

# Google News RSS base URL
GNEWS_RSS_BASE = "https://news.google.com/rss/search"
RATE_LIMIT_DELAY = 2.0  # seconds between requests


class GoogleNewsAdapter:
    """Google News RSS source adapter with pain-focused queries."""

    # Pain-focused search queries (expanded 165-query set)
    PAIN_QUERIES = [
        # Frustration & Annoyance
        '"so frustrating" software',
        '"drives me crazy" tool',
        '"infuriatingly bad" app',
        '"hate this" software',
        '"why is it so hard" tool',
        '"wastes so much time" technology',
        '"total nightmare" experience',
        '"endless frustration" software',
        '"this is broken" app',

        # Alternative Seeking
        '"alternative to" software',
        '"open source alternative" tool',
        '"better replacement" technology',
        '"switched from" "because" review',
        '"tired of" looking for',
        '"need something better" tool',

        # Missing Features
        '"missing feature" software',
        '"wish it had" tool',
        '"desperately needs" app',
        '"why doesn\'t it have" feature',
        '"no way to" accomplish',
        '"can\'t believe it doesn\'t" tool',

        # Performance
        '"so slow" software complaint',
        '"keeps crashing" app',
        '"terrible performance" tool',
        '"unreliable" technology',
        '"buggy mess" software',

        # UX Pain
        '"terrible UI" software',
        '"confusing interface" tool',
        '"impossible to use" app',
        '"horrible user experience" technology',

        # Pricing
        '"way too expensive" software',
        '"overpriced" technology tool',
        '"subscription fatigue" software',
        '"hidden fees" complaint',
        '"not worth the money" tool',

        # Security & Privacy
        '"security nightmare" software',
        '"privacy concerns" technology',
        '"data breach" software company',
        '"trust issues" app',

        # General Pain Signals
        '"struggling with" software tool',
        '"biggest pain point" technology',
        '"why is there no tool for"',
        '"no good solution yet"',
        '"this shouldn\'t be this hard" software',
        '"desperate for a better way"',
        '"complete waste of time" tool',
        '"needs to exist" software',

        # Market Gaps
        '"market gap" startup idea',
        '"untapped market" technology',
        '"nobody is solving" problem',
        '"unmet need" software industry',
        '"pain point" startup opportunity',
    ]

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; TuXo/1.0)',
            'Accept': 'application/rss+xml, application/xml, text/xml',
        })
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
            logger.warning(f"Failed to save GNews cursors: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search Google News RSS for a query."""
        self._rate_limit()

        try:
            url = f"{GNEWS_RSS_BASE}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            resp = self.session.get(url, timeout=15)

            if resp.status_code != 200:
                logger.warning(f"Google News returned {resp.status_code} for: {query}")
                return []

            return self._parse_rss(resp.text, max_results)

        except Exception as e:
            logger.error(f"Google News search failed for '{query}': {e}")
            return []

    def _parse_rss(self, xml_text: str, max_results: int) -> list[dict]:
        """Parse RSS XML into signal dicts."""
        signals = []

        try:
            root = ET.fromstring(xml_text)
            items = root.findall('.//item')

            for item in items[:max_results]:
                title = item.findtext('title', '')
                link = item.findtext('link', '')
                pub_date = item.findtext('pubDate', '')
                description = item.findtext('description', '')
                source = item.findtext('source', '')

                if not link or link in self.seen_urls:
                    continue

                # Parse date
                created_at = ''
                if pub_date:
                    try:
                        # RFC 822 format: "Mon, 28 Mar 2026 19:00:00 GMT"
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        created_at = dt.isoformat()
                    except Exception:
                        created_at = pub_date

                signal = {
                    'source_type': 'google_news',
                    'source_url': link,
                    'title': title,
                    'body': description[:2000] if description else title,
                    'author_handle': source if source else 'unknown',
                    'created_at': created_at,
                    'source_subtype': 'article',
                    'platform_metadata': {
                        'source_publisher': source,
                        'published_date': pub_date,
                    }
                }
                signals.append(signal)
                self.seen_urls.add(link)

            if signals:
                self._save_seen()

        except ET.ParseError as e:
            logger.error(f"RSS parse error: {e}")

        return signals

    def scout(self, max_results: int = 50) -> list[dict]:
        """Run a full scout cycle across pain queries."""
        import random
        all_signals = []

        # Use 8 random queries per cycle
        queries = random.sample(self.PAIN_QUERIES, min(8, len(self.PAIN_QUERIES)))

        for query in queries:
            if len(all_signals) >= max_results:
                break
            remaining = max_results - len(all_signals)
            signals = self.search(query, max_results=min(remaining, 10))
            all_signals.extend(signals)
            time.sleep(1)

        logger.info(f"Google News scout complete: {len(all_signals)} new articles")
        return all_signals[:max_results]


def get_google_news(cursor_file: str = None) -> GoogleNewsAdapter:
    """Factory function."""
    return GoogleNewsAdapter(cursor_file=cursor_file)
