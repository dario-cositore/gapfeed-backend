#!/usr/bin/env python3
"""
GitHub issues farm - public API, no blocking
"""
import requests, json, time, sqlite3
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

# Developer pain terms
PAIN_TERMS = ['error', 'bug', 'crash', 'fails', 'broken', 'cant', 'issue', 
              'problem', 'exception', 'failed', 'unhandled', 'segmentation',
              'deadlock', 'memory leak', 'slow', 'performance', 'timeout',
              'regression', 'breaking', 'deprecated', 'missing', 'not working']

REPOS = [
    'shopify/shopify-api-js',
    'stripe/stripe-dotnet',
    'notionhq/notion-sdk-js',
    'hubspot/hubspot-api-js',
    'salesforce/salesforce-mobile-sdk',
    'quickbooks/quickbooks',
    'webflow/webflow-js',
    'wix/wix-code',
    'squarespace/squarespace-sdk',
]

conn = sqlite3.connect(DB)
saved = 0

for repo in REPOS:
    print(f'\n[{repo}]')
    
    for term in PAIN_TERMS[:5]:
        url = f'https://api.github.com/search/issues?q=repo:{repo}+{term}+is:issue+created:>=2024-01-01&per_page=50'
        try:
            r = requests.get(url, timeout=15, headers={'User-Agent': 'gapfeed-bot'})
            if r.status_code != 200:
                continue
                
            data = r.json()
            issues = data.get('items', [])
            
            print(f'  {term}: {len(issues)}')
            
            for issue in issues:
                title = issue.get('title', '')
                body = issue.get('body', '') or ''
                url = issue.get('html_url', '')
                created = issue.get('created_at', '')
                author = issue.get('user', {}).get('login', 'anonymous')
                
                content = f"{title}\n\n{body}"[:3000]
                product = repo.split('/')[0]
                
                try:
                    conn.execute('''INSERT INTO signals (
                        source, source_url, author, title, content,
                        created_at, collected_at, vertical, product_category,
                        quality_tier, sentiment, product_vertical
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (
                        'GitHub Issue', url, author, title[:200], content,
                        created, datetime.now(tz=timezone.utc).isoformat(),
                        product, product, 'high', 'negative', product
                    ))
                    conn.commit()
                    saved += 1
                except:
                    pass
        except Exception as e:
            print(f'  Error: {e}')

print(f'\n✅ GitHub issues saved: {saved}')
total = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'Total in DB: {total:,}')

conn.close()
