#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — yt-dlp + rotating searches
NO API. NO downloads. Just comments. Fixed version.
"""
import subprocess, json, sqlite3, os, time, random, hashlib
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
YT_DLP = '/home/dario/.local/bin/yt-dlp'

PRODUCTS = [
    'shopify', 'stripe', 'notion', 'klaviyo', 'hubspot',
    'quickbooks', 'godaddy', 'salesforce', 'wordpress',
    'zendesk', 'mailchimp', 'canva', 'clickfunnels',
    'gohighlevel', 'wix', 'squarespace', 'webflow',
    'freshbooks', 'xero', 'zoho', 'monday', 'airtable',
    'asana', 'trello', 'slack', 'teams', 'zoom',
]

SEARCH_TEMPLATES = [
    "{product} sucks", "{product} problems", "{product} review",
    "{product} alternative", "why I quit {product}", "why I left {product}",
    "{product} vs", "{product} too expensive", "{product} complaint",
    "{product} worst feature", "{product} bad experience", "{product} honest review",
    "{product} don't buy", "{product} regret", "{product} nightmare",
    "{product} customer service", "{product} support terrible",
    "{product} cancel subscription", "{product} refund",
    "{product} broken features", "{product} bugs",
    "{product} alternatives 2025", "stop using {product}",
    "{product} vs competitors", "{product} is dead",
    "{product} pricing too high", "{product} review honest",
    "{product} worst product", "{product} hate",
    "{product} disappointed", "{product} waste of money",
    "{product} slow performance", "{product} crash",
]

def search_videos(query, n=3):
    try:
        cmd = [YT_DLP, f'ytsearch{n}:{query}', '--print-json', '--flat-playlist', '--no-warnings', '--quiet']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        videos = []
        for line in r.stdout.strip().split('\n'):
            if not line: continue
            try:
                d = json.loads(line)
                if d.get('id') and d.get('title'):
                    videos.append({'id': d['id'], 'title': d['title'][:150]})
            except: pass
        return videos
    except:
        return []

def get_comments(video_id, max_c=500):
    url = f'https://www.youtube.com/watch?v={video_id}'
    try:
        cmd = [YT_DLP, '--skip-download', '--write-comments', '--dump-json', url, '--no-warnings', '--quiet']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        comments = []
        for line in r.stdout.strip().split('\n'):
            if not line: continue
            try:
                d = json.loads(line)
                raw = d.get('comments', [])
                for c in raw:
                    text = c.get('text', '')
                    if len(text) > 15:
                        cid = c.get('id', '')
                        comments.append({
                            'url': f'https://www.youtube.com/watch?v={video_id}&lc={cid}',
                            'text': text[:3000],
                            'author': c.get('author', 'anonymous'),
                        })
                        if len(comments) >= max_c:
                            return comments
            except: pass
        return comments
    except:
        return []

def insert_signal(conn, source, url, product, author, title, content):
    c = conn.cursor()
    now = datetime.now(tz=timezone.utc).isoformat()
    unique_url = f"{url}#{hashlib.sha256(content.encode()).hexdigest()[:8]}"
    pain = 'general'
    try:
        c.execute(
            'INSERT INTO signals (source, source_url, subreddit, author, title, content, '
            'created_at, collected_at, vertical, product_category, pain_category, display_category, '
            'signal_type, urgency_score, specificity_score, buyer_intent, quality_tier, category, '
            'sentiment, competitor_mentions, metadata, is_processed, synthesized, '
            'confidence, product_vertical, actionability, urgency) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (source, unique_url, product, author[:100], title[:200], content[:5000],
             now, now, product, product, pain, 'complaint', 'user_feedback',
             0.5, 0.5, 0.5, 'medium', '', 'negative', '[]', '{}',
             0, 0, 0.5, product, 0.5, 0.5)
        )
        return c.rowcount > 0
    except Exception as e:
        return False

conn = sqlite3.connect(DB)
total_before = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'=== YOUTUBE COMMENT FARM ===')
print(f'DB: {DB}')
print(f'Existing: {total_before}\n')

saved = 0
qcount = 0
used = set()

for product in PRODUCTS:
    available = [t for t in SEARCH_TEMPLATES if f'{product}_{t}' not in used]
    if not available:
        continue
    
    picks = random.sample(available, min(4, len(available)))
    for template in picks:
        q = template.format(product=product)
        used.add(f'{product}_{template}')
        qcount += 1
        
        vids = search_videos(q, n=3)
        print(f'[{qcount}] "{q}" -> {len(vids)} vids', flush=True)
        
        for v in vids:
            time.sleep(0.3)
            comments = get_comments(v['id'], max_c=200)
            for cm in comments:
                ok = insert_signal(conn, 'YouTube', cm['url'], product, cm['author'], v['title'][:150], cm['text'])
                if ok:
                    saved += 1
            print(f'  +{len(comments)} comments', flush=True)
            time.sleep(0.5)
        
        if qcount % 50 == 0:
            conn.commit()
            total = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
            print(f'  ⚡ CHECKPOINT: {total} signals in DB\n')
        
        time.sleep(1)
    
    conn.commit()
    total = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    print(f'\n--- {product} DONE: {total} total signals ({saved} saved this session) ---\n')

conn.commit()
total_final = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
print(f'\n🏁 COMPLETE: {total_final} signals in DB')
conn.close()