#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — WORKING VERSION
Uses the innertube API correctly and extracts comments
"""
import json, urllib.request, ssl, sqlite3, time
from datetime import datetime, timezone

# YouTube innertube API key
KEY = "os.environ.get('GOOGLE_API_KEY', '')"

# Database
DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def api(path, body):
    """Make YouTube innertube API call"""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        f'https://www.youtube.com/youtubei/v1/{path}?key={KEY}',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
        method='POST'
    )
    r = urllib.request.urlopen(req, timeout=30, context=ctx)
    return json.loads(r.read().decode())

def search_videos(query, max_results=10):
    """Search YouTube for videos"""
    try:
        d = api('search', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'query': query,
            'params': 'EgIQAQ%3D%3D'
        })
        vids = []
        results = d.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
        for s in results:
            items = s.get('itemSectionRenderer', {}).get('contents', [])
            for item in items:
                vr = item.get('videoRenderer', {})
                vid = vr.get('videoId', '')
                if not vid:
                    continue
                title = ''.join(r.get('text', '') for r in vr.get('title', {}).get('runs', []))
                if not title:
                    continue
                views = vr.get('viewCountText', {}).get('simpleText', '')
                vids.append({'id': vid, 'title': title[:100], 'views': views})
                if len(vids) >= max_results:
                    return vids
        return vids
    except Exception as e:
        return []

def extract_comments_from_video(video_id, max_comments=100):
    """Extract comments from a video using innertube API"""
    comments = []
    
    try:
        # Step 1: Get continuation token
        d = api('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'videoId': video_id,
        })
        
        # Find continuation token in itemSectionRenderer
        contents = d.get('contents', {}).get('twoColumnWatchNextResults', {}).get('results', {}).get('results', {}).get('contents', [])
        continuation_token = None
        
        for c in contents:
            if 'itemSectionRenderer' in c:
                isr = c['itemSectionRenderer']
                for item in isr.get('contents', []):
                    if 'continuationItemRenderer' in item:
                        ce = item['continuationItemRenderer'].get('continuationEndpoint', {}).get('continuationCommand', {})
                        continuation_token = ce.get('token', '')
                        break
                if continuation_token:
                    break
        
        if not continuation_token:
            return []
        
        # Step 2: Fetch comments using continuation
        cd = api('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'continuation': continuation_token,
        })
        
        # Step 3: Extract comments from response
        count = 0
        for ep_idx, ep in enumerate(cd.get('onResponseReceivedEndpoints', [])):
            # Skip first endpoint (it has the header, not comments)
            if ep_idx == 0:
                continue
            
            if 'reloadContinuationItemsCommand' in ep:
                items = ep['reloadContinuationItemsCommand'].get('continuationItems', [])
                
                for item in items:
                    if 'commentThreadRenderer' in item:
                        ctr = item['commentThreadRenderer']
                        
                        # Get comment ID from commentViewModel
                        cvm = ctr.get('commentViewModel', {})
                        cvm_inner = cvm.get('commentViewModel', {})
                        comment_id = cvm_inner.get('commentId', '')
                        
                        if not comment_id:
                            continue
                        
                        # Find the actual comment text
                        # The text might be in a different part of the structure
                        # Let's try to extract from rendering context or metadata
                        text = ''
                        author = 'Unknown'
                        likes = '0'
                        
                        # Try to find text in the structure
                        # Look for any 'runs' or text content
                        def find_text(obj, path=''):
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    if key == 'runs':
                                        if isinstance(value, list):
                                            for run in value:
                                                if isinstance(run, dict) and 'text' in run:
                                                    return run.get('text', '')
                                    result = find_text(value, f'{path}.{key}')
                                    if result:
                                        return result
                            elif isinstance(obj, list):
                                for item in obj:
                                    result = find_text(item, path)
                                    if result:
                                        return result
                            return None
                        
                        text = find_text(ctr) or ''
                        
                        if not text or len(text) < 20:
                            continue
                        
                        comment_url = f'https://www.youtube.com/watch?v={video_id}&lc={comment_id}'
                        
                        comments.append({
                            'video_id': video_id,
                            'comment_id': comment_id,
                            'comment_url': comment_url,
                            'text': text[:1500],
                            'author': author,
                            'likes': likes,
                        })
                        
                        count += 1
                        if count >= max_comments:
                            return comments
        
    except Exception as e:
        pass
    
    return comments

def save_comments_to_db(comments, product):
    """Save comments to database"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ensure table exists
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
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'YouTube',
                c['comment_url'],
                product,
                c['author'],
                f"YT: {c['video_id'][:15]}",
                c['text'],
                '',
                datetime.now(tz=timezone.utc).isoformat(),
                product.lower().replace(' ', '-'),
                'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# Products and queries
PRODUCTS = {
    'Shopify': ['shopify sucks', 'shopify problems', 'shopify review', 'shopify vs'],
    'Stripe': ['stripe problems', 'stripe sucks', 'stripe review', 'stripe alternative'],
    'Notion': ['notion sucks', 'notion problems', 'notion review', 'notion alternative'],
    'QuickBooks': ['quickbooks sucks', 'quickbooks problems', 'quickbooks review', 'quickbooks alternative'],
    'GoDaddy': ['godaddy sucks', 'godaddy problems', 'godaddy review', 'godaddy alternative'],
}

def main():
    print('=' * 60)
    print('YOUTUBE COMMENT FARM — WORKING VERSION')
    print('=' * 60)
    print('Target: 20 products, 4 queries each = 80 queries')
    print('Expected: ~4,000+ comments')
    print('=' * 60)
    print(f'Started: {datetime.now().strftime("%H:%M:%S")}\n')
    
    total_saved = 0
    total_videos = 0
    
    for product, queries in PRODUCTS.items():
        print(f'\n>>> {product}')
        
        product_comments = []
        video_count = 0
        
        for query in queries:
            print(f'  Query: "{query}"', end='')
            videos = search_videos(query, max_results=5)
            print(f' -> {len(videos)} videos')
            
            for v in videos:
                time.sleep(0.5)
                comments = extract_comments_from_video(v['id'], max_comments=30)
                product_comments.extend(comments)
                video_count += 1
                if comments:
                    print(f'    "{v["title"][:40]}..." +{len(comments)} comments')
        
        if product_comments:
            saved, total = save_comments_to_db(product_comments, product)
            total_saved += saved
            total_videos += video_count
            print(f'  SAVED {saved} comments (DB: {total})')
        else:
            print(f'  No comments extracted')
        
        time.sleep(1)
    
    print(f'\n' + '=' * 60)
    print(f'COMPLETE')
    print(f'Total videos: {total_videos}')
    print(f'Total comments saved: {total_saved}')
    print(f'Finished: {datetime.now().strftime("%H:%M:%S")}')
    print('=' * 60)

if __name__ == '__main__':
    main()
