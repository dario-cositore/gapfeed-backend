"""
Browser Manager — shared Playwright browser instance with stealth settings.

Creates a single Chromium browser that all adapters share.
Simulates human browsing behavior to avoid bot detection.
"""

import logging
import random
import time
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

STEALTH_JS = """
// Override webdriver detection
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Override languages
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});

// Override plugins (real Chrome has plugins)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            {name: 'Native Client', filename: 'internal-nacl-plugin'},
        ];
        plugins.length = 3;
        return plugins;
    }
});

// Chrome runtime
window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}};

// Permission query override
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters);
"""


class BrowserManager:
    """Manages a shared Playwright browser instance with human-like behavior."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        self._started = False

    def start(self):
        """Launch browser with stealth settings."""
        if self._started:
            return

        logger.info("Launching stealth browser...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
            ]
        )

        # Create persistent context
        ua = random.choice(USER_AGENTS)
        self._context = self._browser.new_context(
            viewport={
                'width': random.randint(1280, 1920),
                'height': random.randint(720, 1080)
            },
            user_agent=ua,
            locale='en-US',
            timezone_id='America/New_York',
            java_script_enabled=True,
        )

        # Inject stealth scripts
        self._context.add_init_script(STEALTH_JS)

        self._started = True
        logger.info(f"Browser ready (UA: {ua[:50]}...)")

    def new_page(self) -> Page:
        """Create a new page with stealth settings."""
        if not self._started:
            self.start()
        return self._context.new_page()

    def human_delay(self, min_s: float = 1.0, max_s: float = 4.0):
        """Random delay like a human reading/thinking."""
        time.sleep(random.uniform(min_s, max_s))

    def human_type(self, page: Page, selector: str, text: str):
        """Type with random delays between keystrokes."""
        page.click(selector)
        time.sleep(random.uniform(0.2, 0.5))
        for char in text:
            page.keyboard.type(char)
            time.sleep(random.uniform(0.05, 0.18))

    def human_scroll(self, page: Page, min_px: int = 200, max_px: int = 600):
        """Scroll like a human reading content."""
        amount = random.randint(min_px, max_px)
        page.evaluate(f'window.scrollBy(0, {amount})')
        time.sleep(random.uniform(0.5, 2.0))

    def human_scroll_top(self, page: Page):
        """Scroll back to top."""
        page.evaluate('window.scrollTo(0, 0)')
        time.sleep(random.uniform(0.3, 0.8))

    def accept_cookies(self, page: Page):
        """Try to accept cookie banners if present."""
        selectors = [
            'button:has-text("Accept")',
            'button:has-text("I agree")',
            'button:has-text("OK")',
            'button:has-text("Got it")',
            '#onetrust-accept-btn-handler',
            '[data-testid="cookie-accept"]',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    time.sleep(random.uniform(0.5, 1.5))
                    btn.click()
                    logger.info(f"Accepted cookies via: {sel}")
                    time.sleep(random.uniform(0.5, 1.0))
                    return True
            except Exception:
                continue
        return False

    def close(self):
        """Clean shutdown of browser."""
        logger.info("Closing browser...")
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser close error: {e}")
        self._started = False
        logger.info("Browser closed")


# Global singleton
_browser_manager = None


def get_browser_manager() -> BrowserManager:
    """Get or create the global browser manager."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
