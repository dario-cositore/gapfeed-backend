#!/usr/bin/env python3
"""
YOUTUBE COMMENT PAIN FARM — Using comment_scraper.py from Elitza's Tools
Extracts pain points from YouTube comments using yt-dlp
"""
import subprocess, json, sqlite3, time, os
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
SCRAPER_PATH = '/home/dario/Elitza/shady_tools/comment_scraper.py'

# Products to search
PRODUCTS = [
    'Shopify', 'Stripe', 'Notion', 'Klaviyo', 'HubSpot',
    'QuickBooks', 'GoDaddy', 'Salesforce', 'WordPress',
    'Zendesk', 'Mailchimp', 'Canva', 'ClickFunnels',
    'GoHighLevel', 'Wix', 'Squarespace', 'Webflow',
]

def find_youtube_videos(query, max_results=3):
    """Find YouTube videos using yt-dlp"""
    try:
        cmd = ['yt-dlp', f'ytsearch{max_results}:{query}', '--print-json', '--flat-playlist']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    if data.get('id') and data.get('title'):
                        videos.append({
                            'id': data['id'],
                            'title': data.get('title', '')[:100],
                            'url': data.get('webpage_url', ''),
                        })
                except:
                    pass
        
        return videos
    except Exception as e:
        print(f'  Search error: {e}')
        return []

def extract_comments(video_id, max_comments=200):
    """Extract comments from a YouTube video using yt-dlp"""
    url = f'https://www.youtube.com/watch?v={video_id}'
    
    try:
        cmd = [
            'yt-dlp',
            '--skip-download',
            '--write-comments',
            '--print-json',
            '--extractor-args', f'youtube:max_comments={max_comments}',
            url,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            return []
        
        # Parse JSON output
        comments = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    if 'comments' in data:
                        for c in data.get('comments', []):
                            text = c.get('text', '') or c.get('comment', '')
                            if text and len(text) > 20:
                                comments.append({
                                    'text': text[:2000],
                                    'author': c.get('author', 'Anonymous'),
                                    'likes': c.get('like_count', 0),
                                    'timestamp': c.get('timestamp', ''),
                                    'url': url,
                                })
                except:
                    pass
        
        return comments
    except Exception as e:
        print(f'  Extract error: {e}')
        return []

def classify_pain(text):
    """Classify if text contains pain"""
    pain_words = [
        'sucks', 'terrible', 'awful', 'broken', 'crash', 'expensive',
        'slow', 'hate', 'worst', 'garbage', 'trash', 'useless',
        'refund', 'cancel', 'never again', 'avoid', 'scam',
        'problem', 'issue', 'bug', 'error', 'fail',
    ]
    
    text_lower = text.lower()
    pain_score = sum(1 for word in pain_words if word in text_lower)
    
    if pain_score >= 2:
        return 'high', pain_score
    elif pain_score >= 1:
        return 'medium', pain_score
    else:
        return 'low', 0

def save_signals(comments, product):
    """Save pain signals to database"""
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
    for c in comments:
        pain_level, pain_score = classify_pain(c['text'])
        
        if pain_level == 'low':
            continue
        
        # Generate unique URL
        url_hash = hash(c['text'] + c['url']) % 1000000
        comment_url = f"{c['url']}&lc=extracted_{url_hash}"
        
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'YouTube Comment',
                comment_url,
                product,
                c['author'],
                f'{product} YouTube Pain Point',
                c['text'],
                c['timestamp'],
                datetime.now(tz=timezone.utc).isoformat(),
                product.lower().replace(' ', '-'),
                pain_level
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
    print('YOUTUBE COMMENT PAIN FARM — Using yt-dlp')
    print('=' * 70)
    print(f'Target: {len(PRODUCTS)} products')
    print('=' * 70)
    
    total_saved = 0
    
    for product in PRODUCTS:
        print(f'\n>>> {product}')
        
        # Search for complaint videos
        queries = [
            f'{product} sucks',
            f'{product} problems',
            f'{product} review',
            f'{product} alternative',
        ]
        
        all_comments = []
        
        for query in queries[:2]:  # 2 queries per product
            print(f'  Searching: "{query}"')
            videos = find_youtube_videos(query, max_results=2)
            print(f'    Found {len(videos)} videos')
            
            for v in videos:
                print(f'    Extracting: {v["title"][:50]}...')
                comments = extract_comments(v['id'], max_comments=100)
                print(f'      {len(comments)} comments')
                all_comments.extend(comments)
                time.sleep(1)  # Rate limit
        
        if all_comments:
            saved, total = save_signals(all_comments, product)
            total_saved += saved
            print(f'  Saved {saved} pain signals (DB: {total})')
        else:
            print(f'  No pain signals found')
        
        time.sleep(2)
    
    print(f'\n' + '=' * 70)
    print(f'COMPLETE: {total_saved} YouTube pain signals saved')
    print('=' * 70)

if __name__ == '__main__':
    main()
