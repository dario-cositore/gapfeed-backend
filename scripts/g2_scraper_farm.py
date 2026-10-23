#!/usr/bin/env python3
"""
NON-REDDIT PAIN FARM — Using G2/Capterra Scraper from Elitza's Tools
Running actual working scrapers to get buyer pain
"""
import os, sys, subprocess, json, sqlite3, time
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

# Run the G2 scraper on a product
def run_g2_scraper(product, scrape_type='g2'):
    """Run the G2/Capterra scraper"""
    scraper_path = '/home/dario/Elitza/shady_tools/g2_cap_scrapper/scraper.py'
    
    if not os.path.exists(scraper_path):
        print(f'  Scraper not found at {scraper_path}')
        return []
    
    # Create output directory
    output_dir = '/tmp/g2_scrapes'
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the scraper
    try:
        cmd = [
            'python3', scraper_path,
            product,
            '--output', f'{output_dir}/{product}_{scrape_type}.json',
            '--type', scrape_type,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output_file = f'{output_dir}/{product}_{scrape_type}.json'
        
        if os.path.exists(output_file):
            with open(output_file) as f:
                data = json.load(f)
            print(f'    Scraped {len(data)} reviews from {scrape_type}')
            return data
        else:
            print(f'    No output file created')
            return []
            
    except Exception as e:
        print(f'    Scraper error: {str(e)[:60]}')
        return []

def process_review(review, product, source):
    """Process a single review"""
    text = review.get('review', '') or review.get('description', '') or review.get('title', '')
    if not text or len(text) < 20:
        return None
    
    rating = review.get('rating', '0')
    if isinstance(rating, str):
        rating = rating.split('/')[0]
    
    reviewer = review.get('reviewer_info', '') or 'Anonymous'
    if isinstance(reviewer, dict):
        reviewer = reviewer.get('name', 'Anonymous')
    
    # Create URL
    review_id = hash(str(review)) % 1000000
    if source == 'G2':
        url = f'https://www.g2.com/products/{product.lower().replace(" ", "-")}/reviews#review-{review_id}'
    else:
        url = f'https://www.capterra.com/review/{review_id}'
    
    # Extract cons/pain
    cons = review.get('cons', '')
    pain_text = text
    if cons and len(cons) > 10:
        pain_text = f"{text}\n\nCON: {cons}"
    
    return {
        'product': product,
        'source': source,
        'url': url,
        'author': reviewer[:100],
        'rating': str(rating),
        'text': pain_text[:1500],
        'published': review.get('date', ''),
        'title': review.get('title', '')[:100],
    }

def save_reviews(reviews, product):
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
    for r in reviews:
        data = process_review(r, product, r.get('source', 'Review'))
        if not data:
            continue
        
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'{data["source"]} Review',
                data['url'],
                data['product'],
                data['author'],
                f"{data['product']} {data['source']} Review: {data['title']}",
                data['text'],
                data['published'],
                datetime.now(tz=timezone.utc).isoformat(),
                data['product'].lower().replace(' ', '-'),
                'high' if data.get('rating', '0') and float(data['rating']) <= 3 else 'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

def main():
    # Products to scrape
    products = [
        'Shopify', 'Stripe', 'Notion', 'Klaviyo', 'HubSpot',
        'QuickBooks', 'GoDaddy', 'Salesforce', 'WordPress',
        'Zendesk', 'Slack', 'Zoom', 'Mailchimp', 'Canva'
    ]
    
    print('=' * 70)
    print('NON-REDDIT PAIN FARM — G2/Capterra Scraper')
    print('=' * 70)
    print(f'Target: {len(products)} products')
    print('=' * 70)
    
    total_saved = 0
    
    for product in products:
        print(f'\n>>> {product}')
        
        # Try G2 reviews
        print(f'  Scraping G2 reviews...')
        g2_reviews = run_g2_scraper(product, 'g2')
        
        # Process and save
        if g2_reviews:
            # Tag with source
            for r in g2_reviews:
                r['source'] = 'G2'
            
            saved, total = save_reviews(g2_reviews, product)
            total_saved += saved
            print(f'  Saved {saved}/{len(g2_reviews)} reviews (DB: {total})')
        else:
            print(f'  No reviews scraped')
    
    print(f'\n' + '=' * 70)
    print(f'COMPLETE: {total_saved} reviews saved')
    print('=' * 70)

if __name__ == '__main__':
    main()
