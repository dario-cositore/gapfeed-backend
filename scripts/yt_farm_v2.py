#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — Local, no server
Uses innertube API directly, gets exact comment URLs
"""
import json, urllib.request, urllib.parse, ssl, sqlite3, time, sys
from datetime import datetime, timezone

# YouTube innertube API key
KEY = "os.environ.get('GOOGLE_API_KEY', '')"

# Database path
DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def api(path, body, timeout=30):
    """Make YouTube innertube API call"""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        f'https://www.youtube.com/youtubei/v1/{path}?key={KEY}',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
        method='POST'
    )
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return json.loads(r.read().decode())

def search_videos(query, n=10):
    """Search YouTube for videos"""
    try:
        d = api('search', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'query': query,
            'params': 'EgIQAQ%3D%3D'  # Video type filter
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

def get_comments(video_id, max_comments=200):
    """Extract comments with exact URLs"""
    comments = []
    seen = set()
    
    try:
        # First request to get the continuation token
        d = api('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'videoId': video_id,
        }, timeout=30)
        
        # Find continuation token
        contents = d.get('contents', {}).get('twoColumnWatchNextResults', {}).get('results', {}).get('results', {}).get('contents', [])
        
        continuation_token = None
        for c in contents:
            isr = c.get('itemSectionRenderer', {})
            if not isr:
                continue
            for item in isr.get('contents', []):
                if 'continuationItemRenderer' in item:
                    cont = item['continuationItemRenderer']
                    ce = cont.get('continuationEndpoint', {})
                    continuation_token = ce.get('continuationCommand', {}).get('token', '')
                    break
            if continuation_token:
                break
        
        if not continuation_token:
            # Check onResponseReceivedEndpoints
            for ep in d.get('onResponseReceivedEndpoints', []):
                if 'reloadContinuationItemsCommand' in ep:
                    items = ep['reloadContinuationItemsCommand'].get('continuationItems', [])
                    for item in items:
                        if 'commentThreadRenderer' in item:
                            # Extract from first render
                            cr = item['commentThreadRenderer'].get('comment', {}).get('commentRenderer', {})
                            if cr:
                                yield cr, video_id
                        elif 'continuationItemRenderer' in item:
                            cont = item['continuationItemRenderer']
                            ce = cont.get('continuationEndpoint', {})
                            continuation_token = ce.get('continuationCommand', {}).get('token', '')
                            break
                if continuation_token:
                    break
        
        if not continuation_token:
            return
        
        # Now fetch comments using the continuation token
        count = 0
        while continuation_token and count < max_comments:
            try:
                cd = api('next', {
                    'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
                    'continuation': continuation_token,
                }, timeout=30)
                
                endpoints = cd.get('onResponseReceivedEndpoints', [])
                found_items = False
                
                for ep in endpoints:
                    # Check for append items
                    if 'appendContinuationItemsAction' in ep:
                        items = ep['appendContinuationItemsAction'].get('continuationItems', [])
                        for item in items:
                            if 'commentThreadRenderer' in item:
                                cr = item['commentThreadRenderer'].get('comment', {}).get('commentRenderer', {})
                                if cr and cr.get('commentId', '') not in seen:
                                    yield cr, video_id
                                    seen.add(cr.get('commentId', ''))
                                    count += 1
                                    found_items = True
                                    if count >= max_comments:
                                        return
                            elif 'continuationItemRenderer' in item:
                                cont = item['continuationItemRenderer']
                                ce = cont.get('continuationEndpoint', {})
                                continuation_token = ce.get('continuationCommand', {}).get('token', '')
                    
                    # Check for reload
                    if 'reloadContinuationItemsCommand' in ep:
                        items = ep['reloadContinuationItemsCommand'].get('continuationItems', [])
                        for item in items:
                            if 'commentThreadRenderer' in item:
                                cr = item['commentThreadRenderer'].get('comment', {}).get('commentRenderer', {})
                                if cr and cr.get('commentId', '') not in seen:
                                    yield cr, video_id
                                    seen.add(cr.get('commentId', ''))
                                    count += 1
                                    found_items = True
                                    if count >= max_comments:
                                        return
                            elif 'continuationItemRenderer' in item:
                                cont = item['continuationItemRenderer']
                                ce = cont.get('continuationEndpoint', {})
                                continuation_token = ce.get('continuationCommand', {}).get('token', '')
                
                if not found_items:
                    break
                    
            except Exception as e:
                print(f'    Comment fetch error: {str(e)[:50]}')
                break
                
    except Exception as e:
        print(f'    Initial request error: {str(e)[:60]}')

def extract_comment_data(cr, video_id):
    """Extract structured data from comment renderer"""
    comment_id = cr.get('commentId', '')
    text = ''
    for run in cr.get('contentText', {}).get('runs', []):
        text += run.get('text', '')
    if not text:
        text = cr.get('contentText', {}).get('simpleText', '')
    
    author = cr.get('authorText', {}).get('simpleText', '')
    likes = cr.get('voteCount', {}).get('simpleText', '0')
    published = cr.get('publishedTimeText', {}).get('simpleText', '')
    
    return {
        'video_id': video_id,
        'video_url': f'https://www.youtube.com/watch?v={video_id}',
        'comment_id': comment_id,
        'comment_url': f'https://www.youtube.com/watch?v={video_id}&lc={comment_id}',
        'text': text[:1500],
        'author': author[:100],
        'published': published,
        'likes': likes
    }

def save_to_db(comments, product):
    """Save comments to database"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            source_url TEXT,
            subreddit TEXT,
            author TEXT,
            title TEXT,
            content TEXT,
            created_at TEXT,
            collected_at TEXT,
            vertical TEXT,
            quality_tier TEXT,
            UNIQUE(source_url)
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

# Products and their search queries
PRODUCTS = {
    'Shopify': ['shopify sucks', 'shopify problems', 'shopify vs woocommerce', 'why i left shopify', 'shopify alternative'],
    'Stripe': ['stripe payments problems', 'stripe account frozen', 'stripe alternative', 'stripe sucks', 'stripe vs paypal'],
    'Notion': ['notion problems', 'notion sucks', 'notion vs airtable', 'notion too slow', 'notion alternative'],
    'Klaviyo': ['klaviyo review', 'klaviyo vs mailchimp', 'klaviyo too expensive', 'klaviyo sucks', 'klaviyo problems'],
    'GoDaddy': ['godaddy sucks', 'godaddy review', 'why i left godaddy', 'godaddy alternative', 'godaddy problems'],
    'QuickBooks': ['quickbooks problems', 'quickbooks vs xero', 'quickbooks sucks', 'quickbooks review', 'quickbooks alternative'],
    'Zendesk': ['zendesk sucks', 'zendesk vs', 'zendesk too expensive', 'zendesk review', 'zendesk alternative'],
    'Wix': ['wix sucks', 'wix vs', 'wix review', 'wix problems', 'wix alternative'],
    'Squarespace': ['squarespace sucks', 'squarespace vs', 'squarespace review', 'squarespace problems', 'squarespace alternative'],
    'Webflow': ['webflow sucks', 'webflow review', 'webflow vs', 'webflow problems', 'webflow alternative'],
}

def run_product(product_name, queries):
    """Process all queries for one product"""
    print(f'\n>>> {product_name}')
    all_comments = []
    
    for query in queries:
        print(f'  Query: "{query}"')
        time.sleep(1)
        
        videos = search_videos(query, n=5)
        print(f'    Found {len(videos)} videos')
        
        for v in videos:
            print(f'      "{v["title"][:50]}" ({v["views"]})', end='')
            time.sleep(0.5)
            
            comms_for_video = []
            for cr, vid_id in get_comments(v['id'], max_comments=150):
                data = extract_comment_data(cr, vid_id)
                if len(data['text']) > 30:
                    comms_for_video.append(data)
            
            if comms_for_video:
                print(f' +{len(comms_for_video)}', end='')
                all_comments.extend(comms_for_video)
            else:
                print(' +0', end='')
            
            if len(all_comments) >= 2000:  # Stop per product at 2000
                break
        print()
        
        if len(all_comments) >= 2000:
            break
    
    # Save all comments for this product
    if all_comments:
        saved, total = save_to_db(all_comments, product_name)
        print(f'  Saved {saved}/{len(all_comments)} comments (DB: {total})')
    else:
        print(f'  No comments extracted')
    
    return len(all_comments)

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('YOUTUBE COMMENT FARM — LOCAL MODE')
    print('=' * 60)
    print(f'Targets: {len(PRODUCTS)} products')
    print(f'Queries: 5 per product')
    print(f'Videos per query: 5')
    print(f'Max comments per video: 150')
    print(f'Expected: {len(PRODUCTS) * 5 * 5 * 150:,} comments\n')
    
    print(f'Started: {datetime.now().strftime("%H:%M:%S")}\n')
    
    grand_total = 0
    for name, queries in PRODUCTS.items():
        count = run_product(name, queries)
        grand_total += count
        
        # Progress marker
        print(f'  >>> Running total: {grand_total:,} comments')
        time.sleep(2)
    
    print(f'\n' + '=' * 60)
    print(f'COMPLETE')
    print(f'Total comments extracted: {grand_total:,}')
    print(f'Finished: {datetime.now().strftime("%H:%M:%S")}')
    print('=' * 60)
