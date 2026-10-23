#!/usr/bin/env python3
import requests, json, time, sqlite3, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

PAIN_WORDS = ['sucks', 'hate', 'terrible', 'broken', 'expensive', 'bad', 'issue', 'problem', 
              'bug', 'worse', 'worst', 'complaint', 'slow', 'crash', 'refund', 'cancel', 
              'avoid', 'never', 'disappointed', 'frustrating', 'horrible', 'nightmare',
              'annoying', 'trash', 'garbage', 'useless', 'fail', 'error', 'painful', 'useless']

PRODUCTS = ['shopify', 'stripe', 'notion', 'hubspot', 'salesforce', 'quickbooks', 'wix', 'squarespace']

conn = sqlite3.connect(DB)
saved = 0

for product in PRODUCTS:
    print(f'\n{product}:')
    
    # Get stories
    search = f'https://hn.algolia.com/api/v1/search?query={product}&tags=story&hitsPerPage=25'
    try:
        r = requests.get(search, timeout=15)
        stories = r.json().get('hits', [])
    except:
        continue
    
    print(f'  Stories: {len(stories)}')
    
    for i, story in enumerate(stories):
        if i % 5 == 0: print(f'    Story {i+1}/{len(stories)}')
        
        story_id = story.get('objectID')
        if not story_id:
            continue
            
        # Get comments
        try:
            cr = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', timeout=10)
            if cr.status_code != 200:
                continue
            item = cr.json()
            kids = item.get('kids', [])[:20]
        except:
            continue
            
        for kid in kids:
            time.sleep(0.05)
            try:
                cc = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{kid}.json', timeout=10)
                if cc.status_code != 200:
                    continue
                cmt = cc.json()
                text = cmt.get('text', '')
                if not text:
                    continue
                    
                clean = re.sub(r'<[^>]+>', '', text).strip()
                if len(clean) < 30:
                    continue
                    
                if any(w in clean.lower() for w in PAIN_WORDS):
                    url = f'https://news.ycombinator.com/item?id={kid}'
                    post_date = datetime.fromtimestamp(cmt.get('time', 0), tz=timezone.utc).isoformat()
                    
                    try:
                        conn.execute('''INSERT INTO signals (
                            source, source_url, author, content, created_at,
                            collected_at, vertical, product_category,
                            quality_tier, sentiment, product_vertical
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                            'HN Comment', url, cmt.get('by', 'anonymous'),
                            clean[:3000], post_date, 
                            datetime.now(tz=timezone.utc).isoformat(),
                            product, product, 'high', 'negative', product
                        ))
                        conn.commit()
                        saved += 1
                    except:
                        pass
            except:
                pass

print(f'\n✅ HN saved {saved} pain signals')
total = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'Total in DB: {total:,}')
conn.close()
