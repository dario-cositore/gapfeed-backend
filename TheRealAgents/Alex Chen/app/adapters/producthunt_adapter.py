"""
Product Hunt adapter â€” finds pain signals in product launches and discussions.

Uses Product Hunt RSS feeds (free, no API key, no auth).
RSS URLs: https://www.producthunt.com/feed?category=slug

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
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

# Product Hunt RSS base URL
PH_RSS_BASE = "https://www.producthunt.com/feed"
RATE_LIMIT_DELAY = 2.0

# Pain-focused categories
CATEGORIES = [
    # General (all launches)
    "featured",
    # Specific categories that surface pain signals
    "developer-tools",
    "design-tools",
    "productivity",
    "marketing",
    "analytics",
    "project-management",
    "ai",
    "open-source",
    "saas",
    "no-code",
    # Trending topics
    "gaming",
    "fintech",
    "health-fitness",
    "social-media",
    "education",
]


class ProductHuntAdapter:
    """Product Hunt RSS source adapter with pain-focused categories."""

    PAIN_QUERIES = [
        # Comment-level pain patterns (for later browser scraping)
        "alternative to",
        "better than",
        "waste of money",
        "disappointed",
        "frustrating",
        "overpriced",
        "missing feature",
        "not worth it",
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
            logger.warning(f"Failed to save Product Hunt cursors: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _parse_rss(self, xml_text: str, category: str) -> list[dict]:
        """Parse RSS/Atom XML into signal dicts."""
        signals = []

        try:
            root = ET.fromstring(xml_text)

            # Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            # Try Atom first (Product Hunt uses Atom)
            items = root.findall('.//atom:entry', ns)
            if items:
                for item in items:
                    title = item.findtext('atom:title', '', ns)
                    # Atom link is in a <link> element
                    link_el = item.find('atom:link', ns)
                    link = link_el.get('href', '') if link_el is not None else ''
                    pub_date = item.findtext('atom:published', '', ns) or item.findtext('atom:updated', '', ns)
                    description = item.findtext('atom:content', '', ns) or item.findtext('atom:summary', '', ns)
                    author_el = item.find('atom:author', ns)
                    creator = ''
                    if author_el is not None:
                        creator = author_el.findtext('atom:name', '', ns) or author_el.findtext('atom:uri', '', ns)

                    if not link or link in self.seen_urls:
                        continue

                    created_at = pub_date if pub_date else ''

                    # PH tagline often contains the pain signal
                    tagline = ''
                    if description and 'â€”' in description:
                        parts = description.split('â€”', 1)
                        tagline = parts[1].strip() if len(parts) > 1 else description[:500]
                    else:
                        tagline = description[:500] if description else title

                    signal = {
                        'source_type': 'producthunt',
                        'source_url': link,
                        'title': title,
                        'body': tagline[:2000],
                        'author_handle': creator if creator else 'unknown',
                        'created_at': created_at,
                        'platform_id': link,
                        'source_subtype': 'launch',
                        'platform_metadata': {
                            'category': category,
                            'tagline': tagline,
                        }
                    }
                    signals.append(signal)
                    self.seen_urls.add(link)
            else:
                # Try RSS 2.0 format
                items = root.findall('.//item')
                for item in items:
                    title = item.findtext('title', '')
                    link = item.findtext('link', '')
                    pub_date = item.findtext('pubDate', '')
                    description = item.findtext('description', '')
                    creator = item.findtext('{http://purl.org/dc/elements/1.1/}creator', '')

                    if not link or link in self.seen_urls:
                        continue

                    created_at = ''
                    if pub_date:
                        try:
                            dt = parsedate_to_datetime(pub_date)
                            created_at = dt.isoformat()
                        except Exception:
                            created_at = pub_date

                    tagline = ''
                    if description and 'â€”' in description:
                        parts = description.split('â€”', 1)
                        tagline = parts[1].strip() if len(parts) > 1 else description[:500]
                    else:
                        tagline = description[:500] if description else title

                    signal = {
                        'source_type': 'producthunt',
                        'source_url': link,
                        'title': title,
                        'body': tagline[:2000],
                        'author_handle': creator if creator else 'unknown',
                        'created_at': created_at,
                        'platform_id': link,
                        'source_subtype': 'launch',
                        'platform_metadata': {
                            'category': category,
                            'tagline': tagline,
                        }
                    }
                    signals.append(signal)
                    self.seen_urls.add(link)

            if signals:
                self._save_seen()

        except ET.ParseError as e:
            logger.error(f"Product Hunt RSS parse error: {e}")

        return signals

    def fetch_category(self, category: str) -> list[dict]:
        """Fetch RSS feed for a category."""
        self._rate_limit()

        try:
            url = f"{PH_RSS_BASE}?category={category}"
            resp = self.session.get(url, timeout=15)

            if resp.status_code != 200:
                logger.warning(f"Product Hunt returned {resp.status_code} for: {category}")
                return []

            signals = self._parse_rss(resp.text, category)
            logger.info(f"Product Hunt {category}: {len(signals)} new launches")
            return signals

        except Exception as e:
            logger.error(f"Product Hunt fetch failed for {category}: {e}")
            return []

    def scout(self, max_results: int = 50) -> list[dict]:
        """Run a full scout cycle across categories."""
        import random
        all_signals = []

        # Use 5 random categories per cycle
        categories = random.sample(CATEGORIES, min(5, len(CATEGORIES)))

        for category in categories:
            if len(all_signals) >= max_results:
                break
            signals = self.fetch_category(category)
            all_signals.extend(signals)
            time.sleep(1)

        logger.info(f"Product Hunt scout complete: {len(all_signals)} new launches")
        return all_signals[:max_results]


def get_producthunt(cursor_file: str = None) -> ProductHuntAdapter:
    """Factory function."""
    return ProductHuntAdapter(cursor_file=cursor_file)

