#!/usr/bin/env python3
"""
G2 SCRAPER RUNNER — Generate more review data
Run G2 scraper on multiple products to get more pain signals
"""
import subprocess, json, os, time, sqlite3
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

# Products to scrape
PRODUCTS = [
    'Shopify', 'Stripe', 'Notion', 'Klaviyo', 'HubSpot',
    'QuickBooks', 'GoDaddy', 'Salesforce', 'WordPress',
    'Zendesk', 'Mailchimp', 'Canva', 'ClickFunnels',
    'GoHighLevel', 'Wix', 'Squarespace', 'Webflow',
]

def run_g2_scraper(product, start_date='2024-01-01', end_date='2024-12-31'):
    """Run G2 scraper on a product"""
    scraper_dir = '/home/dario/Elitza/shady_tools/g2_cap_scrapper'
    scraper_script = os.path.join(scraper_dir, 'main.py')
    
    if not os.path.exists(scraper_script):
        print(f'  Scraper not found')
        return None
    
    # Change to scraper directory
    original_dir = os.getcwd()
    os.chdir(scraper_dir)
    
    try:
        # Run the scraper
        cmd = [
            'python3', scraper_script,
            '--g2', product,
            '--start', start_date,
            '--end', end_date,
            '--output', f'json/{product.lower()}_g2_auto.json',
        ]
        
        # But the script is interactive, so let's try direct import
        # Actually, let's just run the scraper function directly
        cmd = [
            'python3', '-c',
            f'''
import sys
sys.path.insert(0, "{scraper_dir}/utils")
from g2_scrapper import scrape_g2_reviews
from datetime import datetime

reviews = scrape_g2_reviews("{product}", datetime(2024,1,1), datetime(2024,12,31))
print(f"Found {{len(reviews)}} reviews")
with open("{scraper_dir}/json/{product.lower()}_g2_auto.json", "w") as f:
    import json
    json.dump(reviews, f)
'''
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(f'  Output: {result.stdout[:200]}')
        
        # Check for output file
        output_file = f'{scraper_dir}/json/{product.lower()}_g2_auto.json'
        if os.path.exists(output_file):
            with open(output_file) as f:
                data = json.load(f)
            print(f'  Scraped {len(data)} reviews')
            return data
        
    except Exception as e:
        print(f'  Error: {str(e)[:60]}')
        return None
    finally:
        os.chdir(original_dir)
    
    return None

def save_to_db(reviews, product):
    """Save reviews to database"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            source_url TEXT UNIQUE,
            subreddit TEXT,
            author TEXT,
            title TEXT,
            content TEXT,
            created_at TEXT,
            collected_at TEXT,
            vertical TEXT,
            quality_tier TEXT
        )
    ''')
    
    saved = 0
    for review in reviews:
        text = review.get('review', '') or review.get('title', '')
        if len(text) < 20:
            continue
        
        url = f'https://www.g2.com/products/{product.lower()}/reviews#review-{hash(str(review)) % 1000000}'
        
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'G2 Review',
                url,
                product,
                'Anonymous',
                f'{product} G2 Review',
                text[:1500],
                '',
                datetime.now(tz=timezone.utc).isoformat(),
                product.lower().replace(' ', '-'),
                'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

def main():
    print('=' * 70)
    print('G2 SCRAPER RUNNER')
    print('=' * 70)
    print(f'Target: {len(PRODUCTS)} products')
    print('=' * 70)
    
    total_saved = 0
    
    for product in PRODUCTS:
        print(f'\n>>> {product}')
        
        # Try to scrape
        reviews = run_g2_scraper(product)
        
        if reviews:
            saved, total = save_to_db(reviews, product)
            total_saved += saved
            print(f'  Saved {saved} reviews (DB: {total})')
        else:
            print(f'  Scraping failed or no reviews')
    
    print(f'\n' + '=' * 70)
    print(f'Total reviews saved: {total_saved}')
    print('=' * 70)

if __name__ == '__main__':
    main()
