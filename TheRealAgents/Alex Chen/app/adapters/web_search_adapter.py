"""
Web search adapter — finds pain signals across the entire internet.

Uses DuckDuckGo search (no API key needed, no auth).
Returns search results that Alex can then scrape/enrich.

Supports two modes:
1. General search: find pain patterns across the web
2. Targeted search: find specific complaints when Alex knows what to look for

Cursoring: tracks last-seen URLs per query to avoid re-processing.
"""

import time
import logging
import hashlib
import requests
import random
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger(__name__)

# DuckDuckGo HTML search (no API key needed)
DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"

# Rotating user agents to avoid fingerprinting
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]

RATE_LIMIT_DELAY = 3.0  # seconds between searches (DDG is stricter than Reddit)


class WebSearchAdapter:
    """Web search adapter using DuckDuckGo."""

    def __init__(self, cursor_file: str = None, proxies: list = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.last_request_time = 0
        self.cursor_file = cursor_file
        self.seen_urls = self._load_seen_urls()
        self.proxies = proxies or []  # List of proxy URLs like 'http://user:pass@host:port'
        self.request_count = 0

    def _rotate_identity(self):
        """Rotate user agent and proxy between requests."""
        self.request_count += 1
        # Rotate UA every 5 requests
        if self.request_count % 5 == 0:
            new_ua = random.choice(USER_AGENTS)
            self.session.headers['User-Agent'] = new_ua
        # Rotate proxy if available
        if self.proxies:
            proxy = random.choice(self.proxies)
            self.session.proxies = {'http': proxy, 'https': proxy}

    def _load_seen_urls(self) -> set:
        """Load previously seen URLs to avoid re-processing."""
        if not self.cursor_file:
            return set()
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    return set(data.get('seen_urls', []))
        except Exception:
            pass
        return set()

    def _save_seen_urls(self):
        """Persist seen URLs."""
        if not self.cursor_file:
            return
        try:
            import json
            from pathlib import Path
            p = Path(self.cursor_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Keep only last 10000 URLs to prevent file bloat
            urls_list = list(self.seen_urls)[-10000:]
            with open(p, 'w') as f:
                json.dump({'seen_urls': urls_list}, f)
        except Exception as e:
            logger.warning(f"Failed to save seen URLs: {e}")

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _search_ddg(self, query: str, max_results: int = 25) -> list[dict]:
        """
        Search DuckDuckGo HTML and parse results.

        Returns list of {title, url, snippet}.
        """
        self._rate_limit()
        self._rotate_identity()

        for attempt in range(3):
            try:
                resp = self.session.post(
                    DDG_SEARCH_URL,
                    data={
                        'q': query,
                        'b': '',  # start offset
                        'kl': '',  # region
                    },
                    timeout=10,
                )

                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"DDG rate limited, backing off {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error(f"DDG returned {resp.status_code}")
                    return []

                return self._parse_ddg_results(resp.text, max_results)

            except requests.exceptions.Timeout:
                logger.warning(f"DDG search timeout (attempt {attempt+1}/3)")
                time.sleep(5 * (attempt + 1))
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"DDG search failed: {e}")
                return []

        logger.warning("DDG search failed after 3 attempts")
        return []

    def _parse_ddg_results(self, html: str, max_results: int) -> list[dict]:
        """Parse DuckDuckGo HTML results page."""
        results = []
        try:
            from html.parser import HTMLParser

            class DDGParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.current = {}
                    self.in_title = False
                    self.in_snippet = False
                    self.capture_text = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    cls = attrs_dict.get('class', '')

                    # Result links
                    if tag == 'a' and 'result__a' in cls:
                        self.in_title = True
                        self.capture_text = ""
                        href = attrs_dict.get('href', '')
                        self.current = {'url': href, 'title': '', 'snippet': ''}

                    # Snippets
                    elif tag == 'a' and 'result__snippet' in cls:
                        self.in_snippet = True
                        self.capture_text = ""

                def handle_endtag(self, tag):
                    if tag == 'a':
                        if self.in_title:
                            self.current['title'] = self.capture_text.strip()
                            self.in_title = False
                        elif self.in_snippet:
                            self.current['snippet'] = self.capture_text.strip()
                            self.in_snippet = False
                            if self.current.get('url') and self.current.get('title'):
                                self.results.append(self.current)
                                self.current = {}

                def handle_data(self, data):
                    if self.in_title or self.in_snippet:
                        self.capture_text += data

            parser = DDGParser()
            parser.feed(html)
            results = parser.results[:max_results]

        except Exception as e:
            logger.error(f"Failed to parse DDG results: {e}")

        return results

    def search(self, query: str, max_results: int = 25) -> list[dict]:
        """
        Search the web for pain signals.

        Args:
            query: Search query (e.g., "stripe froze my account")
            max_results: Max results to return

        Returns:
            List of raw signal dicts ready for enrichment.
        """
        logger.info(f"Web search: {query}")

        raw_results = self._search_ddg(query, max_results)
        if not raw_results:
            return []

        signals = []
        for result in raw_results:
            url = result.get('url', '')
            title = result.get('title', '')
            snippet = result.get('snippet', '')

            if not url or not title:
                continue

            # Skip already-seen URLs
            url_hash = hashlib.md5(url.encode()).hexdigest()
            if url_hash in self.seen_urls:
                continue
            self.seen_urls.add(url_hash)

            # Skip non-content URLs
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            skip_domains = {
                'google.com', 'bing.com', 'yahoo.com', 'duckduckgo.com',
                'youtube.com', 'facebook.com', 'twitter.com', 'x.com',
                'pinterest.com', 'instagram.com',
            }
            if domain in skip_domains:
                continue

            # Extract created time hint from snippet (basic)
            created_at = datetime.now(timezone.utc).isoformat()

            signal = {
                'raw_signal_id': f"sig_web_{url_hash}",
                'source_type': 'web_search',
                'source_subtype': 'search_result',
                'author_handle': None,
                'source_url': url,
                'title': title,
                'body': snippet,
                'created_at': created_at,
                'platform_metadata': {
                    'search_query': query,
                    'domain': domain,
                },
                'language': 'en',
                'geo_hint': None,
                'product_mentions': [],
                'money_mentions': [],
            }

            signals.append(signal)

        self._save_seen_urls()
        logger.info(f"Web search found {len(signals)} new results for: {query}")
        return signals

    def search_pain_patterns(self, topic: str = None) -> list[dict]:
        """
        Search using pre-built pain-focused query patterns.

        If topic is provided, searches for that topic.
        Otherwise, uses rotating general pain patterns.
        """
        pain_queries = []

        if topic:
            pain_queries = [
                f'"{topic}" frustrated with',
                f'"{topic}" not working',
                f'"{topic}" worst experience',
                f'"{topic}" complaint forum',
                f'"{topic}" alternatives to',
            ]
        else:
            # Rotating general pain patterns - Dario's expanded 165-query set
            import random
            all_queries = [
                # 1. Frustration & Annoyance (25)
                'so frustrating forum',
                'drives me crazy site:reddit.com',
                'infuriatingly bad',
                'absolutely maddening',
                'hate this so much',
                'why is it so hard forum',
                'constantly frustrated site:reddit.com',
                'wastes so much time complaint',
                'makes me want to quit',
                'ridiculous how bad',
                'unbelievably annoying forum',
                'pure frustration site:reddit.com',
                'this sucks',
                'pain in the ass forum',
                'extremely frustrating site:reddit.com',
                'getting really tired of forum',
                'can\'t stand anymore site:reddit.com',
                'total nightmare experience',
                'keeps screwing me over',
                'why won\'t it just work forum',
                'so damn annoying site:reddit.com',
                'losing my mind over forum',
                'endless frustration complaint',
                'this is broken forum',
                'infuriatingly bad experience',

                # 2. Alternative Seeking (20)
                'alternative to forum',
                'better alternative recommendation',
                'open source alternative site:reddit.com',
                'free alternative to review',
                'best replacement for site:reddit.com',
                'what do people use instead of forum',
                'looking for alternative recommendation',
                'decent alternative site:reddit.com',
                'cheap alternative to forum',
                'modern alternative recommendation',
                'lighter alternative site:reddit.com',
                'self-hosted alternative forum',
                'privacy-focused alternative site:reddit.com',
                'anyone recommend alternative forum',
                'switched from to review',
                'tired of looking for forum',
                'replacement for site:reddit.com',
                'competitor to recommendation',
                'who uses something else forum',
                'need something better than site:reddit.com',

                # 3. Missing Features & Wishes (20)
                'missing feature complaint',
                'wish it had site:reddit.com',
                'desperately needs forum',
                'would love a feature for',
                'why doesn\'t it have forum',
                'sorely missing site:reddit.com',
                'big missing piece complaint',
                'feature request site:reddit.com',
                'needs an option to forum',
                'should really have complaint',
                'one thing it\'s missing site:reddit.com',
                'please add support for forum',
                'huge gap in complaint',
                'lacking basic feature site:reddit.com',
                'if only it could forum',
                'major missing functionality',
                'no way to complaint',
                'can\'t believe it doesn\'t forum',
                'wishlist item site:reddit.com',
                'top requested feature complaint',

                # 4. Performance & Reliability (15)
                'so slow complaint',
                'keeps crashing forum',
                'constantly freezing site:reddit.com',
                'terrible performance review',
                'lags like crazy forum',
                'unreliable as hell site:reddit.com',
                'always breaking complaint',
                'buggy mess forum',
                'falls over when site:reddit.com',
                'downtime issues complaint',
                'performance is garbage forum',
                'crashes every time site:reddit.com',
                'loading forever complaint',
                'keeps failing forum',
                'unstable complaint',

                # 5. Usability & UX Pain (15)
                'terrible UI complaint',
                'confusing interface forum',
                'horrible UX site:reddit.com',
                'impossible to use complaint',
                'clunky as hell forum',
                'non-intuitive site:reddit.com',
                'bad user experience complaint',
                'poorly designed forum',
                'navigation nightmare site:reddit.com',
                'can\'t figure out how complaint',
                'overly complicated forum',
                'steep learning curve site:reddit.com',
                'counterintuitive complaint',
                'frustrating workflow forum',
                'terrible mobile experience site:reddit.com',

                # 6. Pricing & Value Complaints (15)
                'way too expensive complaint',
                'overpriced for what it does forum',
                'not worth the money site:reddit.com',
                'pricing is ridiculous complaint',
                'nickel-and-diming forum',
                'hidden fees complaint site:reddit.com',
                'too pricey forum',
                'subscription fatigue site:reddit.com',
                'costs more than it should complaint',
                'terrible value forum',
                'price gouging site:reddit.com',
                'not worth it anymore complaint',
                'sudden price increase forum',
                'cheap but broken site:reddit.com',
                'paying for mediocrity complaint',

                # 7. Support & Service Issues (10)
                'terrible support complaint',
                'no response from support forum',
                'support is useless site:reddit.com',
                'horrible customer service complaint',
                'weeks to get help forum',
                'ignored my ticket site:reddit.com',
                'support ghosting complaint',
                'awful help desk forum',
                'can\'t get anyone to reply site:reddit.com',
                'support nightmare complaint',

                # 8. Integration & Compatibility (10)
                'doesn\'t integrate with complaint',
                'no integration for forum',
                'breaks with site:reddit.com',
                'compatibility issues complaint',
                'won\'t work with forum',
                'integration hell site:reddit.com',
                'missing API support complaint',
                'can\'t connect to forum',
                'sync problems site:reddit.com',
                'no webhook support complaint',

                # 9. Security, Trust & Privacy (10)
                'security nightmare complaint',
                'sketchy privacy forum',
                'data breach worries site:reddit.com',
                'doesn\'t feel secure complaint',
                'no 2FA forum',
                'suspicious permissions site:reddit.com',
                'trust issues complaint forum',
                'potential scam review',
                'leaks data site:reddit.com',
                'privacy concerns complaint',

                # 10. General High-Intent Pain Signals (25)
                'struggling with site:reddit.com',
                'how do I fix forum',
                'anyone else having problem site:reddit.com',
                'is there a way to complaint',
                'tired of dealing with forum',
                'constant headache site:reddit.com',
                'biggest pain point forum',
                'dealbreaker for me site:reddit.com',
                'game changer if forum',
                'solves my biggest problem site:reddit.com',
                'life-saver if it existed forum',
                'why is there no tool for site:reddit.com',
                'paying someone to do this complaint',
                'manual process sucks site:reddit.com',
                'automating this is impossible forum',
                'no good solution yet site:reddit.com',
                'still using spreadsheets for complaint',
                'this shouldn\'t be this hard forum',
                'desperate for a better way site:reddit.com',
                'anyone found a fix forum',
                'recurring nightmare site:reddit.com',
                'every time I try complaint',
                'complete waste of time forum',
                'needs to exist site:reddit.com',
            ]
            pain_queries = random.sample(all_queries, min(5, len(all_queries)))

        all_signals = []
        for query in pain_queries:
            signals = self.search(query, max_results=8)
            all_signals.extend(signals)
            time.sleep(2)  # Longer delay between queries to avoid DDG rate limits

        return all_signals

    def search_with_queries(self, queries: list[str], max_results: int = 8) -> list[dict]:
        """Search using a list of provided queries (e.g. from intelligent PLAN)."""
        all_signals = []
        for query in queries[:10]:  # Cap at 10 queries per call
            signals = self.search(query, max_results=max_results)
            all_signals.extend(signals)
            time.sleep(2)
        return all_signals

    def fetch_page_content(self, url: str) -> Optional[str]:
        """
        Fetch full page content from a URL.

        Used when Alex wants to read the full post/article for better enrichment.
        Returns text content or None if failed.
        """
        self._rate_limit()

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            # Basic HTML to text extraction
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
                    self.current_skip = 0

                def handle_starttag(self, tag, attrs):
                    if tag in self.skip_tags:
                        self.current_skip += 1

                def handle_endtag(self, tag):
                    if tag in self.skip_tags and self.current_skip > 0:
                        self.current_skip -= 1

                def handle_data(self, data):
                    if self.current_skip == 0:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            extractor = TextExtractor()
            extractor.feed(resp.text)
            content = '\n'.join(extractor.text_parts)

            # Limit to 5000 chars for enrichment
            return content[:5000]

        except Exception as e:
            logger.warning(f"Failed to fetch page content: {e}")
            return None
