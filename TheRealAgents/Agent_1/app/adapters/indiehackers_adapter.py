"""
Indie Hackers adapter â€” fetches posts from Indie Hackers via RSS.

No authentication needed. Uses the public RSS feed.
"""

import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

FEED_URLS = [
    "https://feeds.feedburner.com/indiehackers/blog",
]

SEARCH_URLS = [
    "https://www.indiehackers.com/search?q={query}",
]

USER_AGENT = "TuXo:PainSignalScout/1.0 (research bot)"


class IndieHackersAdapter:
    """Indie Hackers source adapter via RSS."""

    def __init__(self, cursor_file: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/xml, application/rss+xml, text/xml',
        })
        self.cursor_file = cursor_file
        self.seen_urls = self._load_seen()

    def _load_seen(self) -> set:
        """Load seen URLs from cursor file."""
        if not self.cursor_file:
            return set()
        try:
            p = Path(self.cursor_file)
            if p.exists():
                import json
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_urls', []))
        except Exception:
            pass
        return set()

    def _save_seen(self):
        """Save seen URLs to cursor file."""
        if not self.cursor_file:
            return
        try:
            import json
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Keep last 5000 URLs to prevent file bloat
            urls = list(self.seen_urls)[-5000:]
            with open(p, 'w') as f:
                json.dump({'seen_urls': urls}, f)
        except Exception as e:
            logger.warning(f"Failed to save seen URLs: {e}")

    def fetch_feed(self, max_results: int = 30) -> list[dict]:
        """
        Fetch posts from Indie Hackers RSS feed.

        Returns list of signal dicts.
        """
        signals = []

        for feed_url in FEED_URLS:
            try:
                resp = self.session.get(feed_url, timeout=15)
                if resp.status_code != 200:
                    logger.debug(f"IH feed {feed_url} returned {resp.status_code}")
                    continue

                root = ET.fromstring(resp.content)

                # Handle RSS 2.0
                items = root.findall('.//item')
                if not items:
                    # Try Atom format
                    ns = {'atom': 'http://www.w3.org/2005/Atom'}
                    items = root.findall('.//atom:entry', ns)

                for item in items[:max_results]:
                    signal = self._parse_item(item)
                    if signal and signal['url'] not in self.seen_urls:
                        signals.append(signal)
                        self.seen_urls.add(signal['url'])

                if signals:
                    break  # Got results from this feed

            except Exception as e:
                logger.debug(f"IH feed {feed_url} failed: {e}")
                continue

        self._save_seen()
        logger.info(f"Indie Hackers: fetched {len(signals)} new posts")
        return signals

    def _parse_item(self, item) -> Optional[dict]:
        """Parse an RSS item into a signal dict."""
        try:
            # RSS 2.0
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            desc = item.findtext('description', '')
            pub_date = item.findtext('pubDate', '')
            creator = item.findtext('{http://purl.org/dc/elements/1.1/}creator', '')

            # Atom fallback
            if not title:
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                title = item.findtext('atom:title', '', ns)
                link_el = item.find('atom:link', ns)
                link = link_el.get('href', '') if link_el is not None else ''
                desc = item.findtext('atom:summary', '', ns)
                pub_date = item.findtext('atom:published', '', ns)
                creator = item.findtext('atom:author/atom:name', '', ns)

            if not title or not link:
                return None

            # Clean description (strip HTML tags)
            import re
            desc_clean = re.sub(r'<[^>]+>', '', desc).strip()

            # Parse date
            created_at = None
            if pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    created_at = parsedate_to_datetime(pub_date).isoformat()
                except Exception:
                    pass

            return {
                'source_type': 'indiehackers',
                'source_url': link,
                'title': title,
                'body': desc_clean[:2000],
                'author_handle': creator or 'unknown',
                'created_at': created_at or datetime.now(timezone.utc).isoformat(),
                'source_subtype': 'post',
                'platform_id': link,
                'platform_metadata': {
                    'source_type': 'rss',
                    'platform': 'indiehackers',
                }
            }
        except Exception as e:
            logger.debug(f"Failed to parse IH item: {e}")
            return None

    def scout(self, max_results: int = 30) -> list[dict]:
        """Main scout entry point. Fetches new posts."""
        return self.fetch_feed(max_results=max_results)


def get_indiehackers(cursor_file: str = None) -> IndieHackersAdapter:
    """Factory function."""
    return IndieHackersAdapter(cursor_file=cursor_file)

