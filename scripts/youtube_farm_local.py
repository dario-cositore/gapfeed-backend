#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — yt-dlp + rotating searches
NO API. NO downloads. Just comments.
"""
import subprocess, json, sqlite3, os, time, random, hashlib
from datetime import datetime, timezone
import re

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
YT_DLP = '/home/dario/.local/bin/yt-dlp'

# Pain categories
PAIN_CATS = {
    'price': ['expensive', 'overpriced', 'too expensive', 'not worth', 'cost', 'pricing', 'subscription', 'monthly', 'fee'],
    'support': ['support', 'customer service', 'no response', 'ignore', 'ticket', 'no help'],
    'performance': ['slow', 'lag', 'crash', 'freezes', 'performance', 'timeout'],
    'complexity': ['complex', 'confusing', 'hard to use', 'difficult', 'complicated', 'learning curve'],
    'bug': ['bug', 'broken', 'doesn\'t work', 'error', 'glitch', 'not working'],
    'alternative': ['alternative', 'switching', 'switched', 'moving to', 'vs ', 'instead of', 'migrating'],
}

PRODUCTS = [
    'shopify', 'stripe', 'notion', 'klaviyo', 'hubspot',
    'quickbooks', 'godaddy', 'salesforce', 'wordpress',
    'zendesk', 'mailchimp', 'canva', 'clickfunnels',
    'gohighlevel', 'wix', 'squarespace', 'webflow',
    'freshbooks', 'xero', 'zoho', 'monday', 'airtable',
    'asana', 'trello', 'slack', 'teams', 'zoom',
]

# MASSIVE rotating search templates
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
    "{product} tutorial frustration", "{product} setup problems",
]

def search_videos(query, max_results=5):
    """Search YouTube using yt-dlp"""
    try:
        cmd = [YT_DLP, f'ytsearch{max_results}:{query}',
               '--print-json', '--flat-playlist',
               '--no-warnings', '--quiet']
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

def extract_comments(video_id, max_c=500):
    """Extract comments using yt-dlp — NO DOWNLOAD"""
    url = f'https://www.youtube.com/watch?v={video_id}'
    try:
        cmd = [YT_DLP, '--skip-download', '--write-comments',
               '--dump-json', url, '--no-warnings', '--quiet']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if not r.stdout.strip():
            return []
        
        # Last JSON line has comments
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
                            'likes': c.get('like_count', 0),
                        })
                        if len(comments) >= max_c:
                            return comments
            except: pass
        return comments
    except:
        return []

def get_conn():
    return sqlite3.connect(DB)

def insert_signal(conn, source, url, product, author, title, content, source_date=''):
    pain_matches = []
    text_lower = content.lower()
    for cat, kws in PAIN_CATS.items():
        if any(kw in text_lower for kw in kws):
            pain_matches.append(cat)
    
    pain = pain_matches[0] if pain_matches else 'general'
    sentiment = 'negative'
    quality = 'high' if len(pain_matches) >= 2 else 'medium'
    
    unique = hashlib.sha256(content.encode()).hexdigest()[:12]
    
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO signals (
            source, source_url, platform_id, subreddit, author, title,
            content, created_at, collected_at, vertical, product_category,
            pain_category, display_category, signal_type,
            urgency_score, specificity_score, buyer_intent, quality_tier,
            gap_id, category, sentiment, competitor_mentions, metadata,
            is_processed, synthesized, confidence, actionability, urgency,
            product_vertical
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            source, url, '', product, author[:100], title[:200],
            content[:5000], source_date, datetime.now(tz=timezone.utc).isoformat(),
            product, pain, 'complaint', 'user_feedback',
            0.5, 0.5, 0.5, quality, None, '', sentiment,
            '[]', '{}', 0, 0, 0.5, 0.5, 0.5, product
        ))
        return c.lastrowid
    except:
        return None

def main():
    conn = get_conn()
    c = conn.cursor()
    
    total_signals = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    print(f'=== YOUTUBE COMMENT FARM ===')
    print(f'DB: {DB}')
    print(f'Existing signals: {total_signals}')
    print()
    
    saved = 0
    queries_run = 0
    used_combos = set()
    
    for round_num in range(1, 21):  # 20 rounds
        for product in PRODUCTS:
            # Pick 3 random unique templates per product per round
            available = [t for t in SEARCH_TEMPLATES if (product + '_' + t) not in used_combos]
            if not available:
                continue
            
            picks = random.sample(available, min(3, len(available)))
            
            for template in picks:
                query = template.format(product=product)
                used_combos.add(product + '_' + template)
                queries_run += 1
                
                print(f'  [{queries_run}] "{query}"', end=' ', flush=True)
                
                videos = search_videos(query, max_results=3)
                if not videos:
                    print('0 vids', flush=True)
                    continue
                
                print(f'{len(videos)} vids', end='', flush=True)
                
                for v in videos:
                    time.sleep(0.3)
                    comments = extract_comments(v['id'], max_c=200)
                    for cm in comments:
                        sid = insert_signal(conn, 'YouTube Comment', cm['url'], product,
                                          cm['author'], v['title'][:150], cm['text'])
                        if sid:
                            saved += 1
                
                    print(f' +{len(comments)}', end='', flush=True)
                
                time.sleep(1)
                
                # Checkpoint every 50 queries
                if queries_run % 50 == 0:
                    conn.commit()
                    new_count = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
                    print(f'\n  ✅ Checkpoint: {new_count} signals ({saved} new)')
                
                print(flush=True)
        
        # Round complete
        conn.commit()
        new_count = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        print(f'\n--- Round {round_num} complete: {new_count} total signals ({len(used_combos)} unique queries) ---\n')
    
    conn.close()
    print(f'\n🏁 COMPLETE: {saved} new signals saved')

if __name__ == '__main__':
    main()
