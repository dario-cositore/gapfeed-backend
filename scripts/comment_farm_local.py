#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — Working Version
Extracts comments with exact URLs, saves to database
"""
import json, urllib.request, urllib.parse, ssl, sqlite3, time, sys
from datetime import datetime, timezone

# YouTube innertube API key
KEY = "os.environ.get('GOOGLE_API_KEY', '')"

# Database path
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

def search_videos(query, n=10):
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
                views = vr.get('viewCountText', {}).get('simpleText', '')
                channel = vr.get('ownerText', {}).get('runs', [{}])[0].get('text', '')
                vids.append({'id': vid, 'title': title[:100], 'views': views, 'channel': channel[:50]})
                if len(vids) >= n:
                    return vids
        return vids
    except Exception as e:
        print(f'    Search error: {str(e)[:60]}')
        return []

def extract_comments(video_id, max_comments=200):
    """Extract comments from a video with exact URLs"""
    comments = []
    seen = set()
    
    try:
        # Get continuation token
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
        
        # Fetch comments using continuation token
        cd = api('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'continuation': continuation_token,
        })
        
        # Extract comments from response - look at endpoints after the first one
        count = 0
        for ep_idx, ep in enumerate(cd.get('onResponseReceivedEndpoints', [])):
            if ep_idx == 0:
                # First endpoint has header, skip it
                continue
            if 'reloadContinuationItemsCommand' in ep:
                items = ep['reloadContinuationItemsCommand'].get('continuationItems', [])
                for item in items:
                    if 'commentThreadRenderer' in item:
                        cr = item['commentThreadRenderer'].get('comment', {}).get('commentRenderer', {})
                        if not cr:
                            continue
                        
                        comment_id = cr.get('commentId', '')
                        if comment_id in seen:
                            continue
                        seen.add(comment_id)
                        
                        # Extract text
                        text = ''
                        for run in cr.get('contentText', {}).get('runs', []):
                            text += run.get('text', '')
                        if not text:
                            text = cr.get('contentText', {}).get('simpleText', '')
                        
                        if not text or len(text) < 20:
                            continue
                        
                        # Extract other fields
                        author = cr.get('authorText', {}).get('simpleText', '')
                        likes = cr.get('voteCount', {}).get('simpleText', '0')
                        published = cr.get('publishedTimeText', {}).get('simpleText', '')
                        
                        # Exact comment URL
                        comment_url = f'https://www.youtube.com/watch?v={video_id}&lc={comment_id}'
                        
                        comments.append({
                            'video_id': video_id,
                            'video_url': f'https://www.youtube.com/watch?v={video_id}',
                            'comment_id': comment_id,
                            'comment_url': comment_url,
                            'text': text[:1500],
                            'author': author[:100],
                            'likes': likes,
                            'published': published
                        })
                        
                        count += 1
                        if count >= max_comments:
                            return comments
    except Exception as e:
        print(f'    Error: {str(e)[:60]}')
    
    return comments

def save_to_db(comments, product):
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
                'high' if 'K' in c.get('likes', '0') else 'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# Products and search queries
PRODUCTS = {
    'Shopify': ['shopify sucks', 'shopify problems', 'shopify vs', 'why i left shopify', 'shopify alternative'],
    'Stripe': ['stripe problems', 'stripe frozen', 'stripe alternative', 'stripe sucks', 'stripe vs paypal'],
    'Notion': ['notion problems', 'notion sucks', 'notion vs', 'notion alternative', 'notion slow'],
    'Klaviyo': ['klaviyo review', 'klaviyo vs mailchimp', 'klaviyo too expensive', 'klaviyo sucks', 'klaviyo problems'],
    'GoDaddy': ['godaddy sucks', 'godaddy review', 'why i left godaddy', 'godaddy alternative', 'godaddy problems'],
    'QuickBooks': ['quickbooks problems', 'quickbooks vs xero', 'quickbooks sucks', 'quickbooks review', 'quickbooks alternative'],
    'Zendesk': ['zendesk sucks', 'zendesk vs', 'zendesk expensive', 'zendesk review', 'zendesk alternative'],
    'Wix': ['wix sucks', 'wix vs', 'wix review', 'wix problems', 'wix alternative'],
    'Squarespace': ['squarespace sucks', 'squarespace vs', 'squarespace review', 'squarespace problems', 'squarespace alternative'],
    'Webflow': ['webflow sucks', 'webflow review', 'webflow vs', 'webflow problems', 'webflow alternative'],
}

def run_product(product_name, queries):
    """Process all queries for one product"""
    print(f'\n>>> {product_name}')
    all_comments = []
    
    for query in queries:
        print(f'  Query: "{query}"', end='')
        sys.stdout.flush()
        time.sleep(1)
        
        videos = search_videos(query, n=5)
        print(f' -> {len(videos)} videos', end='')
        
        for v in videos:
            time.sleep(0.3)
            comms = extract_comments(v['id'], max_comments=100)
            if comms:
                print(f' +{len(comms)}', end='')
                all_comments.extend(comms)
            
            if len(all_comments) >= 5000:
                break
        
        if len(all_comments) >= 5000:
            break
        
        print()
    
    # Save all comments
    if all_comments:
        saved, total = save_to_db(all_comments, product_name)
        print(f'  SAVED {saved}/{len(all_comments)} comments (DB: {total})')
    else:
        print(f'  No comments extracted')
    
    return len(all_comments)

# Main execution
if __name__ == '__main__':
    print('=' * 60)
    print('YOUTUBE COMMENT FARM — Local Mode')
    print('=' * 60)
    print(f'Targets: {len(PRODUCTS)} products')
    print(f'Queries per: 5')
    print(f'Videos per: 5')
    print(f'Comments per video: up to 100')
    print(f'Expected: ~12,500+ comments')
    print('=' * 60)
    
    print(f'Started: {datetime.now().strftime("%H:%M:%S")}\n')
    
    grand_total = 0
    for name, queries in PRODUCTS.items():
        count = run_product(name, queries)
        grand_total += count
        
        print(f'  >>> Running total: {grand_total:,} comments')
        time.sleep(2)
    
    print(f'\n' + '=' * 60)
    print(f'COMPLETE')
    print(f'Total comments extracted: {grand_total:,}')
    print(f'Finished: {datetime.now().strftime("%H:%M:%S")}')
    print('=' * 60)
