#!/usr/bin/env python3
"""
NON-REDDIT PAIN FARM — Hacker News Comments
Uses HN's public API to extract real pain points from discussions
"""
import json, urllib.request, ssl, sqlite3, time, re
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def fetch_hn_items(tag='front_page', max_results=50):
    """Fetch items from HN API"""
    url = f'https://hn.algolia.com/api/v1/search?tags={tag}&hitsPerPage={max_results}'
    ctx = ssl.create_default_context()
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        data = json.loads(resp.read().decode())
        return data.get('hits', [])
    except Exception as e:
        print(f'  API error: {e}')
        return []

def fetch_hn_comments(item_id):
    """Fetch comments for an item"""
    url = f'https://hn.algolia.com/api/v1/search?tags=comment,story_{item_id}&hitsPerPage=100'
    ctx = ssl.create_default_context()
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        data = json.loads(resp.read().decode())
        return data.get('hits', [])
    except Exception as e:
        return []

def extract_pain_from_text(text):
    """Extract pain points from comment text"""
    pain_patterns = [
        r'(sucks|hate|terrible|awful|broken|failed|wont|cannot|can\'t|doesn\'t work)',
        r'(problem|issue|bug|error|failed|crash)',
        r'(too expensive|overpriced|cost|pricing)',
        r'(slow|lag|performance|speed)',
        r'(missing|lack|need|wish)',
    ]
    
    pain_score = 0
    for pattern in pain_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            pain_score += 1
    
    return pain_score

def save_to_db(signals):
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
                s.get('product', 'HN'),
                s.get('author', 'Anonymous'),
                s['title'],
                s['content'],
                s.get('created', ''),
                datetime.now(tz=timezone.utc).isoformat(),
                s.get('product', 'hn').lower(),
                'high' if s['pain_score'] >= 3 else 'medium'
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
    print('=' * 70)
    print('NON-REDDIT PAIN FARM — Hacker News Comments')
    print('=' * 70)
    print('Fetching posts and comments from HN API...')
    print()
    
    # Fetch top posts
    print('Fetching top HN posts...')
    posts = fetch_hn_items('front_page', 30)
    print(f'Found {len(posts)} posts')
    
    all_signals = []
    
    for post in posts[:20]:  # Process first 20 posts
        post_id = post.get('objectID', '')
        post_title = post.get('title', '')
        post_url = post.get('url', f'https://news.ycombinator.com/item?id={post_id}')
        
        if not post_id:
            continue
        
        # Fetch comments for this post
        comments = fetch_hn_comments(post_id)
        
        if not comments:
            continue
        
        print(f'\nPost: {post_title[:60]}...')
        print(f'  Comments: {len(comments)}')
        
        # Extract pain points from comments
        pain_count = 0
        for comment in comments:
            text = comment.get('comment_text', '')
            if not text or len(text) < 30:
                continue
            
            # Calculate pain score
            pain_score = extract_pain_from_text(text)
            
            if pain_score >= 2:  # At least 2 pain indicators
                author = comment.get('author', '')
                comment_id = comment.get('objectID', '')
                created = comment.get('created_at_i', 0)
                
                signal = {
                    'source': 'HN Comment',
                    'url': f'https://news.ycombinator.com/item?id={post_id}&comment={comment_id}',
                    'product': post_title[:30],
                    'author': author,
                    'title': f'HN Pain Point: {post_title[:50]}',
                    'content': text[:1500],
                    'created': datetime.fromtimestamp(created).isoformat() if created else '',
                    'pain_score': pain_score,
                }
                
                all_signals.append(signal)
                pain_count += 1
        
        if pain_count > 0:
            print(f'  Pain signals: {pain_count}')
        
        time.sleep(0.5)  # Rate limit
    
    # Save all signals
    saved, total = save_to_db(all_signals)
    
    print(f'\n' + '=' * 70)
    print(f'COMPLETE')
    print(f'Total pain signals found: {len(all_signals)}')
    print(f'Total signals saved: {saved}')
    print(f'DB total: {total}')
    print('=' * 70)

if __name__ == '__main__':
    main()
