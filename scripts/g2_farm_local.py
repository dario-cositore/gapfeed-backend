#!/usr/bin/env python3
"""
G2 NEGATIVE REVIEW FARM — Local execution
Uses existing scraper to pull negative reviews for key products
"""
import subprocess, json, os, sqlite3
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
SCRAPER = '/home/dario/Elitza/shady_tools/Review_Scraper/scraper.py'

PRODUCTS = [
    'shopify', 'stripe', 'notion', 'klaviyo', 'hubspot',
    'quickbooks', 'godaddy', 'salesforce', 'wordpress',
    'zendesk', 'mailchimp', 'canva', 'clickfunnels',
    'gohighlevel', 'wix', 'squarespace', 'webflow',
    'freshbooks', 'xero', 'zoho', 'monday', 'airtable',
    'asana', 'trello', 'slack', 'teams', 'zoom',
]

conn = sqlite3.connect(DB)
c = conn.cursor()

for product in PRODUCTS[:5]:  # Start with first 5
    print(f'\n===== G2: {product.upper()} =====')
    
    output_file = f'/tmp/g2_{product}.json'
    
    # Run scraper
    cmd = [
        'python3', SCRAPER,
        '--source', 'g2',
        '--company', product,
        '--start', '2024-01-01',
        '--end', '2026-04-06',
        '--headless'
    ]
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and os.path.exists(output_file):
            with open(output_file, 'r') as f:
                reviews = json.load(f)
            
            neg_reviews = [r for r in reviews if r.get('rating', 5) <= 3]
            print(f'  Total reviews: {len(reviews)}')
            print(f'  Negative (≤3): {len(neg_reviews)}')
            
            # Insert into DB
            for rev in neg_reviews:
                title = rev.get('title', '')[:200]
                content = rev.get('content', '')[:5000]
                url = rev.get('url', '')
                rating = rev.get('rating', 0)
                date = rev.get('date', '')
                author = rev.get('author', 'anonymous')[:100]
                
                try:
                    c.execute('''INSERT INTO signals (
                        source, source_url, author, title, content,
                        created_at, collected_at, vertical, product_category,
                        pain_category, quality_tier, sentiment, product_vertical
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        'G2 Review', url, author, title, content,
                        date, datetime.now(tz=timezone.utc).isoformat(),
                        product, product, 'general', 'high', 'negative', product
                    ))
                except Exception as e:
                    pass
            
            conn.commit()
        else:
            print(f'  Error: {r.stderr[:100]}')
    except subprocess.TimeoutExpired:
        print(f'  Timeout for {product}')
    except Exception as e:
        print(f'  Exception: {e}')
    
    print(f'  ✅ Done with {product}')

conn.close()
print('\n🏁 G2 extraction complete')
