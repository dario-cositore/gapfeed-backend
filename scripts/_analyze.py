"""Detailed screenshots for comparison."""
from playwright.sync_api import sync_playwright
import os

out = "/home/dario/.openclaw/workspace/3. gapfeed/scripts/screenshots"
os.makedirs(out, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # GapFeed graphs page - Top 5 Fastest Growing
    print("Capturing graphs page...")
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:5002/#graphs", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(4000)
    page.screenshot(path=f"{out}/gapfeed-graphs-top5.png", full_page=False)
    
    # Scroll down on graphs to see the Top 5 section
    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{out}/gapfeed-graphs-top5-scrolled.png", full_page=False)
    
    # OpenRouter - get a closer look at their card style
    print("Capturing OpenRouter...")
    page2 = browser.new_page(viewport={"width": 1440, "height": 900})
    page2.goto("https://openrouter.ai/models", wait_until="networkidle", timeout=30000)
    page2.wait_for_timeout(3000)
    # Try to get their actual card HTML structure
    cards_html = page2.evaluate("""
        () => {
            const cards = document.querySelectorAll('[class*="model"]');
            let html = '';
            for (let i = 0; i < Math.min(3, cards.length); i++) {
                html += cards[i].outerHTML.substring(0, 500) + '\\n---\\n';
            }
            if (!html) {
                // Try different selectors
                const items = document.querySelectorAll('a[href*="/models/"]');
                for (let i = 0; i < Math.min(3, items.length); i++) {
                    html += items[i].outerHTML.substring(0, 800) + '\\n---\\n';
                }
            }
            return html || 'no cards found';
        }
    """)
    print(f"OpenRouter cards HTML:\n{cards_html[:2000]}")
    
    # Also grab the page structure
    structure = page2.evaluate("""
        () => {
            const main = document.querySelector('main') || document.querySelector('[class*="content"]') || document.body;
            const children = main.children;
            let result = '';
            for (let i = 0; i < Math.min(10, children.length); i++) {
                result += children[i].tagName + '.' + children[i].className.substring(0, 50) + ' > ' + children[i].children.length + ' children\n';
            }
            return result;
        }
    """)
    print(f"\nPage structure:\n{structure}")
    
    browser.close()
    print("\nDone")
