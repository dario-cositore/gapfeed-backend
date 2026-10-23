import asyncio
from playwright.async_api import async_playwright

async def screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        
        await page.goto('https://gapfeed.com/sidebar-prototype.html', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Feed page
        await page.screenshot(path='/home/dario/.openclaw/workspace/3. gapfeed/docs/ss-feed.png')
        print('Feed screenshot done')
        
        # Click first gap
        first = page.locator('.feed-item').first
        if await first.count() > 0:
            await first.click()
            await page.wait_for_timeout(1500)
            await page.screenshot(path='/home/dario/.openclaw/workspace/3. gapfeed/docs/ss-gap.png')
            print('Gap screenshot done')
        
        # Graphs
        await page.click('[data-page="graphs"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='/home/dario/.openclaw/workspace/3. gapfeed/docs/ss-graphs.png')
        print('Graphs screenshot done')
        
        # Mobile
        await page.set_viewport_size({'width': 390, 'height': 844})
        await page.click('[data-page="feed"]')
        await page.wait_for_timeout(1500)
        await page.screenshot(path='/home/dario/.openclaw/workspace/3. gapfeed/docs/ss-mobile.png')
        print('Mobile screenshot done')
        
        await browser.close()
        print('All done')

asyncio.run(screenshots())
