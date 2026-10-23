"""
RSS adapter — reads RSS/Atom feeds for news and context.

Used during the READ phase to understand what's happening in the world.
Not for finding individual pain signals, but for detecting events
(outages, policy changes, pricing changes, layoffs) that create pain.

Supports:
- Standard RSS 2.0
- Atom feeds
- JSON feeds (rare but exists)
"""

import time
import logging
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

USER_AGENT = "TuXo:PainSignalScout/1.0 (feed reader)"
RATE_LIMIT_DELAY = 1.0


class RSSAdapter:
    """RSS/Atom feed reader for world context."""

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.seen_guids = self._load_seen_guids()

    def _load_seen_guids(self) -> set:
        if not self.cursor_file:
            return set()
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_guids', []))
        except Exception:
            pass
        return set()

    def _save_seen_guids(self):
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            guids_list = list(self.seen_guids)[-5000:]
            with open(p, 'w') as f:
                json.dump({'seen_guids': guids_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save RSS seen GUIDs: {e}")

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def fetch_feed(self, feed_url: str, limit: int = 20) -> list[dict]:
        """
        Fetch and parse an RSS/Atom feed.

        Returns list of raw signal dicts (context signals, not pain signals).
        """
        self._rate_limit()

        try:
            resp = self.session.get(feed_url, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"RSS feed returned {resp.status_code}: {feed_url}")
                return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"RSS feed failed: {e}")
            return []

        # Detect feed type
        content = resp.text
        items = []

        try:
            root = ET.fromstring(content)

            # RSS 2.0
            if root.tag == 'rss' or root.find('.//channel') is not None:
                items = self._parse_rss(root, limit)
            # Atom
            elif root.tag.endswith('feed') or '{http://www.w3.org/2005/Atom}' in root.tag:
                items = self._parse_atom(root, feed_url, limit)
            else:
                logger.warning(f"Unknown feed format: {root.tag}")
                return []

        except ET.ParseError as e:
            logger.error(f"Failed to parse feed XML: {e}")
            return []

        # Filter out already-seen items
        new_items = []
        for item in items:
            guid = item.get('platform_metadata', {}).get('guid', '')
            if guid and guid in self.seen_guids:
                continue
            if guid:
                self.seen_guids.add(guid)
            new_items.append(item)

        self._save_seen_guids()
        logger.info(f"RSS feed {feed_url}: {len(new_items)} new items (of {len(items)} total)")
        return new_items

    def _parse_rss(self, root: ET.Element, limit: int) -> list[dict]:
        """Parse RSS 2.0 feed."""
        items = []
        channel = root.find('channel')
        if channel is None:
            return []

        feed_title = self._text(channel.find('title'))

        for item in channel.findall('item')[:limit]:
            guid = self._text(item.find('guid')) or self._text(item.find('link')) or ''
            title = self._text(item.find('title'))
            link = self._text(item.find('link'))
            description = self._text(item.find('description'))
            pub_date = self._text(item.find('pubDate'))

            if not title:
                continue

            # Clean HTML from description
            description = self._strip_html(description)

            signal = {
                'raw_signal_id': f"sig_rss_{hashlib.md5(guid.encode()).hexdigest()[:12]}" if guid else f"sig_rss_{hashlib.md5(title.encode()).hexdigest()[:12]}",
                'source_type': 'rss',
                'source_subtype': 'article',
                'author_handle': self._text(item.find('author')),
                'source_url': link or '',
                'title': title,
                'body': description[:1000],
                'created_at': self._parse_date(pub_date),
                'platform_metadata': {
                    'guid': guid,
                    'feed_title': feed_title,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }
            items.append(signal)

        return items

    def _parse_atom(self, root: ET.Element, feed_url: str, limit: int) -> list[dict]:
        """Parse Atom feed."""
        ns = '{http://www.w3.org/2005/Atom}'
        items = []

        feed_title = self._text(root.find(f'{ns}title')) or feed_url

        for entry in root.findall(f'{ns}entry')[:limit]:
            guid = self._text(entry.find(f'{ns}id')) or ''
            title = self._text(entry.find(f'{ns}title'))

            # Link can be in attribute
            link_el = entry.find(f'{ns}link')
            link = link_el.get('href', '') if link_el is not None else ''

            summary = self._text(entry.find(f'{ns}summary')) or self._text(entry.find(f'{ns}content'))
            updated = self._text(entry.find(f'{ns}updated'))

            if not title:
                continue

            summary = self._strip_html(summary or '')

            author_el = entry.find(f'{ns}author')
            author = self._text(author_el.find(f'{ns}name')) if author_el is not None else None

            signal = {
                'raw_signal_id': f"sig_rss_{hashlib.md5(guid.encode()).hexdigest()[:12]}" if guid else f"sig_rss_{hashlib.md5(title.encode()).hexdigest()[:12]}",
                'source_type': 'rss',
                'source_subtype': 'article',
                'author_handle': author,
                'source_url': link,
                'title': title,
                'body': summary[:1000],
                'created_at': self._parse_date(updated),
                'platform_metadata': {
                    'guid': guid,
                    'feed_title': feed_title,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }
            items.append(signal)

        return items

    def _text(self, element: Optional[ET.Element]) -> Optional[str]:
        """Safely extract text from XML element."""
        if element is not None and element.text:
            return element.text.strip()
        return None

    def _strip_html(self, text: str) -> str:
        """Basic HTML tag removal."""
        import re
        return re.sub(r'<[^>]+>', '', text).strip()

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse various date formats to ISO."""
        if not date_str:
            return None
        try:
            # RFC 2822 (RSS standard)
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).isoformat()
        except Exception:
            pass
        try:
            # ISO 8601 (Atom standard)
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).isoformat()
        except Exception:
            return date_str

    def fetch_multiple(self, feeds: list[str], limit_per_feed: int = 10) -> list[dict]:
        """Fetch multiple feeds and combine results."""
        all_items = []
        for feed_url in feeds:
            items = self.fetch_feed(feed_url, limit=limit_per_feed)
            all_items.extend(items)
            time.sleep(0.5)
        return all_items

    def get_default_feeds(self) -> dict[str, list[str]]:
        """
        Default feeds for world context.
        Organized by category for the READ phase.
        """
        return {
            'tech_news': [
                'https://feeds.arstechnica.com/arstechnica/index',
                'https://www.theverge.com/rss/index.xml',
                'https://techcrunch.com/feed/',
            ],
            'saas_industry': [
                'https://www.mostlymetrics.com/feed',
                'https://thebusinessofsaas.substack.com/feed',
            ],
            'outage_status': [
                'https://status.aws.amazon.com/rss/all.rss',
                'https://www.cloudflarestatus.com/history.rss',
            ],
            'regulatory': [
                'https://www.federalregister.gov/blog/feed',
            ],
            'startup': [
                'https://news.ycombinator.com/rss',
            ],
        }
