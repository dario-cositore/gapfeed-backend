#!/usr/bin/env python3
"""
PULSE REVIEW SCRAPER — Get more review data from G2/Capterra/TrustPilot
"""
import subprocess, os, json, sqlite3, time
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
SCRAPER_DIR = '/home/dario/Elitza/shady_tools/Pulse-Review-Scraper'

# Products to scrape
PRODUCTS = [
    'Shopify', 'Stripe', 'Notion', 'Klaviyo', 'HubSpot',
    'QuickBooks', 'GoDaddy', 'Salesforce', 'WordPress',
    'Zendesk', 'Mailchimp', 'Canva', 'ClickFunnels',
    'GoHighLevel', 'Wix', 'Squarespace', 'Webflow',
]

def run_pulse_scraper(company, source='G2'):
    """Run the Pulse-Review-Scraper"""
    scraper_script = os.path.join(SCRAPER_DIR, 'review_scraper.py')
    
    if not os.path.exists(scraper_script):
        print(f'  Scraper not found at {scraper_script}')
        return []
    
    # Date range (last 6 months)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = '2024-01-01'
    
    cmd = [
        'python3', scraper_script,
        '--company', company,
        '--start-date', start_date,
        '--end-date', end_date,
        '--source', source,
        '--output', f'/tmp/{company}_{source}_reviews.json',
    ]
    
    try:
        print(f'    Running {source} scraper for {company}...')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f'    Scraper error: {result.stderr[:100]}')
            return []
        
        # Check for output file
        output_file = f'/tmp/{company}_{source}_reviews.json'
        if os.path.exists(output_file):
            with open(output_file) as f:
                data = json.load(f)
            print(f'    Got {len(data)} reviews')
            return data
        
    except Exception as e:
        print(f'    Error: {str(e)[:60]}')
    
    return []

def process_reviews(reviews, product, source):
    """Process reviews and extract pain signals"""
    signals = []
    
    for review in reviews:
        text = review.get('review', '') or review.get('description', '') or review.get('title', '')
        if len(text) < 30:
            continue
        
        # Check for pain indicators
        pain_words = ['sucks', 'terrible', 'awful', 'broken', 'crash', 'expensive', 'slow', 'hate', 'worst', 'garbage']
        pain_score = sum(1 for word in pain_words if word in text.lower())
        
        if pain_score < 1:
            continue
        
        pain_level = 'high' if pain_score >= 2 else 'medium'
        
        # Create signal
        signals.append({
            'source': f'{source} Review',
            'url': f'https://www.g2.com/products/{product.lower()}/reviews',
            'product': product,
            'author': review.get('reviewer', 'Anonymous'),
            'text': text[:1500],
            'rating': review.get('rating', '0'),
            'pain_level': pain_level,
        })
    
    return signals

def save_signals(signals):
    """Save signals to database"""
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
    for s in signals:
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                s['source'],
                s['url'],
                s['product'],
                s['author'],
                f'{s["product"]} Review Pain Point',
                s['text'],
                '',
                datetime.now(tz=timezone.utc).isoformat(),
                s['product'].lower().replace(' ', '-'),
                s['pain_level']
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
    print('PULSE REVIEW SCRAPER — Extracting Reviews')
    print('=' * 70)
    print(f'Target: {len(PRODUCTS)} products')
    print('=' * 70)
    
    total_saved = 0
    
    for product in PRODUCTS:
        print(f'\n>>> {product}')
        
        # Try G2 first
        reviews = run_pulse_scraper(product, 'G2')
        
        if not reviews:
            # Try Capterra
            reviews = run_pulse_scraper(product, 'Capterra')
        
        if reviews:
            signals = process_reviews(reviews, product, 'G2' if reviews else 'Capterra')
            saved, total = save_signals(signals)
            total_saved += saved
            print(f'  Saved {saved} pain signals (DB: {total})')
        else:
            print(f'  No reviews found')
        
        time.sleep(2)
    
    print(f'\n' + '=' * 70)
    print(f'COMPLETE: {total_saved} review-based pain signals saved')
    print('=' * 70)

if __name__ == '__main__':
    main()
