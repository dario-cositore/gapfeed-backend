#!/usr/bin/env python3
"""
HN PAIN FARM — Hacker News comments via Firebase API
Local execution, lightweight HTTP only, no blocking
"""
import requests, json, time, sqlite3, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

PAIN_WORDS = ['sucks', 'hate', 'terrible', 'broken', 'expensive', 'bad', 
              'issue', 'problem', 'bug', 'worse', 'worst', 'complaint',
              'slow', 'crash', 'refund', 'cancel', 'avoid', 'never',
              'disappointed', 'frustrating', 'horrible', 'nightmare',
              'annoying', 'trash', 'garbage', 'useless', 'fail', 'error']

PRODUCTS = [
    'shopify', 'stripe', 'notion', 'hubspot', 'salesforce',
    'quickbooks', 'wix', 'squarespace', 'zendesk', 'mailchimp',
    'monday', 'asana', 'trello', 'slack', 'teams', 'zoom',
    'asana', 'clickfunnels', 'webflow', 'canva'
]

conn = sqlite3.connect(DB)
c = conn.cursor()

saved_total = 0

for product in PRODUCTS:
    print(f'\n[{product.upper()}] Processing...')
    
    url = f'https://hn.algolia.com/api/v1/search?query={product}&tags=story&hitsPerPage=30&numericFilters=created_at_i>1704067200'
    r = requests.get(url, timeout=15)
    stories = r.json().get('hits', [])
    print(f'  Found {len(stories)} stories')
    
    stories_processed = 0
    for story in stories:
        story_id = story.get('objectID')
        if not story_id:
            continue
            
        # Get top comments (20 max)
        try:
            cr = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
            if cr.status_code == 200:
                item = cr.json()
                kids = item.get('kids', [])[:15]
                
                for kid in kids:
                    time.sleep(0.05)
                    try:
                        cc = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{kid}.json', timeout=10)
                        if cc.status_code == 200:
                            cmt = cc.json()
                            text = cmt.get('text', '')
                            if not text: continue
                            
                            clean = re.sub(r'<[^>]+>', '', text).strip()
                            if len(clean) < 30: continue
                            
                            lower = clean.lower()
                            if any(w in lower for w in PAIN_WORDS):
                                url = f'https://news.ycombinator.com/item?id={kid}'
                                post_date = datetime.fromtimestamp(cmt.get('time', 0), tz=timezone.utc).isoformat()
                                
                                try:
                                    c.execute('''INSERT INTO signals (
                                        source, source_url, author, content, created_at,
                                        collected_at, vertical, product_category,
                                        quality_tier, sentiment, product_vertical
                                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                                        'HN Comment', url, cmt.get('by', 'anonymous'),
                                        clean[:3000], post_date, 
                                        datetime.now(tz=timezone.utc).isoformat(),
                                        product, product, 'high', 'negative', product
                                    ))
                                    saved_total += 1
                                except:
                                    pass
                    except:
                        pass
                        
        except:
            pass
        
        stories_processed += 1
        
        # Checkpoint every 5 stories
        if stories_processed % 5 == 0:
            conn.commit()
            print(f'  Progress: {stories_processed}/{len(stories)}, Total saved: {saved_total}')

conn.commit()
print(f'\n✅ HN complete: {saved_total} pain signals saved')

# Update DB count
total = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'Total signals in DB: {total:,}')

conn.close()
