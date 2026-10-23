#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — Lightweight innertube API
No yt-dlp. Direct HTTP requests. Zero video downloads.
Returns exact comment URLs.
"""
import json, sys, time, urllib.request, urllib.parse, ssl, sqlite3, re
from datetime import datetime, timezone

DB_PATH = '/home/dario/gapfeed/code/data/gapfeed_unified.db'

INNERTUBE_KEY = "os.environ.get('GOOGLE_API_KEY', '')"

SEARCH_URL = 'https://www.youtube.com/youtubei/v1/search?key={}&prettyPrint=false'
COMMENTS_URL = 'https://www.youtube.com/youtubei/v1/next?key={}&prettyPrint=false'

INNERTUBE_CONTEXT = {
    'client': {
        'clientName': 'WEB',
        'clientVersion': '2.20240326.00.00',
    }
}

def search_videos(query, max_results=10):
    """Search YouTube via innertube API."""
    body = json.dumps({
        'context': INNERTUBE_CONTEXT,
        'query': query,
    }).encode()
    
    url = SEARCH_URL.format(INNERTUBE_KEY)
    req = urllib.request.Request(url, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context())
        data = json.loads(resp.read().decode())
        
        videos = []
        contents = data.get('contents',{}).get('twoColumnSearchResultsRenderer',{})
        contents = contents.get('primaryContents',{}).get('sectionListRenderer',{}).get('contents',[])
        
        for section in contents:
            items = section.get('itemSectionRenderer',{}).get('contents',[])
            for item in items:
                vr = item.get('videoRenderer', {})
                vid = vr.get('videoId', '')
                title = ''
                for run in vr.get('title',{}).get('runs',[]):
                    title += run.get('text','')
                views = ''
                for t in vr.get('viewCountText',{}).get('simpleText','').split():
                    if t.replace(',','').replace('.','').isdigit():
                        views = t
                    elif 'K' in t or 'M' in t or 'B' in t:
                        views = t
                channel = vr.get('ownerText',{}).get('runs',[{}])[0].get('text','')
                if vid and title:
                    videos.append({
                        'video_id': vid,
                        'title': title[:100],
                        'views': views,
                        'channel': channel[:50],
                        'search_query': query,
                        'video_url': f'https://www.youtube.com/watch?v={vid}'
                    })
                    if len(videos) >= max_results:
                        return videos
        return videos
    except Exception as e:
        print(f'  Search error: {e}')
        return []

def extract_comments(video_id, max_comments=200):
    """Extract comments via YouTube innertube API - NO VIDEO DOWNLOAD."""
    body = json.dumps({
        'context': INNERTUBE_CONTEXT,
        'videoId': video_id,
    }).encode()
    
    url = COMMENTS_URL.format(INNERTUBE_KEY)
    req = urllib.request.Request(url, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'})
    
    comments = []
    seen_ids = set()
    
    try:
        resp = urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context())
        data = json.loads(resp.read().decode())
        
        # Parse comments from the response
        threads = []
        
        # Navigate to comments
        contents = data.get('contents',{}).get('twoColumnWatchNextResults',{}).get('results',{}).get('results',{}).get('contents',[])
        for c in contents:
            if 'commentsEntryPointHeaderRenderer' in c:
                threads = c.get('commentsEntryPointHeaderRenderer',{}).get('commentCount',{}).get('.accessibility',{}).get('accessibilityData',{}).get('label','').split()
        
        # Get the actual comment threads
        contents2 = contents
        for c1 in contents:
            if 'itemSectionRenderer' in c1:
                isr = c1.get('itemSectionRenderer',{}).get('contents',[])
                for item in isr:
                    t = item.get('commentThreadRenderer',{})
                    if t:
                        threads.append(t)
        
        # Try alternate path
        if not threads:
            cws = data.get('onResponseReceivedEndpoints',[])
            for ep in cws:
                reload = ep.get('reloadContinuationItemsCommand',{})
                for ci in reload.get('continuationItems',[]):
                    t = ci.get('commentThreadRenderer',{})
                    if t:
                        threads.append(t)
                    continuation = ci.get('continuationItemRenderer',{})
                    if continuation:
                        cont_token = continuation.get('continuationEndpoint',{}).get('continuationCommand',{}).get('token','')
        
        for thread in threads:
            if len(comments) >= max_comments:
                break
            cr = thread.get('comment',{}).get('commentRenderer',{})
            if not cr:
                continue
            
            comment_id = cr.get('commentId', '')
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            
            text = ''
            for run in cr.get('contentText',{}).get('runs',[]):
                text += run.get('text', '')
            if not text:
                text = cr.get('contentText',{}).get('simpleText', '')
            
            author = cr.get('authorText',{}).get('simpleText', '')
            published = cr.get('publishedTimeText',{}).get('simpleText', '')
            vote_count = cr.get('voteCount',{}).get('simpleText', '')
            reply_count = cr.get('replyCount', 0)
            
            comment_url = f'https://www.youtube.com/watch?v={video_id}&lc={comment_id}'
            
            if text and len(text) > 15:
                comments.append({
                    'video_id': video_id,
                    'video_url': f'https://www.youtube.com/watch?v={video_id}',
                    'comment_id': comment_id,
                    'comment_url': comment_url,
                    'text': text[:1000],
                    'author': author,
                    'published': published,
                    'likes': vote_count,
                    'reply_count': reply_count
                })
        
        return comments
    except urllib.error.HTTPError as e:
        print(f'  Comments error: {e.code}')
        return []
    except Exception as e:
        print(f'  Comments error: {str(e)[:70]}')
        return []

def save_comments(comments, product_name):
    """Save comments to signals table."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
                product_name,
                c['author'],
                f"Video: {c['video_id'][:15]} — @{c['author'][:30]}",
                c['text'][:2000],
                '',
                datetime.now(tz=timezone.utc).isoformat(),
                product_name.lower().replace(' ','-'),
                'high' if 'k' in c.get('likes','0').lower() else 'medium'
            ))
            saved += 1
        except: pass
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# ============================================================
# PRODUCTS
# ============================================================
PRODUCTS = [
    ('Shopify', ['shopify sucks', 'shopify problems', 'shopify alternative', 'shopify vs woocommerce', 'why i left shopify']),
    ('Stripe', ['stripe payment issues', 'stripe account frozen', 'stripe alternative', 'stripe problems', 'stripe vs paypal']),
    ('Klaviyo', ['klaviyo review', 'klaviyo vs mailchimp', 'klaviyo alternative', 'klaviyo too expensive', 'klaviyo problems']),
    ('Notion', ['notion problems', 'notion sucks', 'notion vs airtable', 'notion too slow', 'notion alternative']),
    ('QuickBooks', ['quickbooks problems', 'quickbooks vs xero', 'quickbooks sucks', 'quickbooks too expensive', 'quickbooks alternative']),
]

if __name__ == '__main__':
    if len(sys.argv) > 1:
        product = sys.argv[1]
        queries = [q for p, qs in PRODUCTS if p.lower() == product.lower() for q in qs]
        if not queries:
            queries = [f'{product} review', f'{product} problems', f'{product} alternative']
    else:
        # Default first product
        print('Usage: python3 yt_farm.py <product>')
        print('Available:', ', '.join(p[0] for p in PRODUCTS))
        sys.exit(0)
    
    print(f'=== YouTube Comment Farm: {product} ===')
    total_saved = 0
    
    for q_idx, query in enumerate(queries):
        print(f'\n[{q_idx+1}/{len(queries)}] Searching: "{query}"')
        time.sleep(1)
        videos = search_videos(query, max_results=5)
        print(f'  Found {len(videos)} videos')
        
        product_comments = []
        for v in videos:
            print(f'  {v["title"][:55]} ({v["views"]})')
            time.sleep(0.5)
            comments = extract_comments(v['video_id'], max_comments=100)
            product_comments.extend(comments)
            print(f'    {len(comments)} comments')
        
        if product_comments:
            saved, total = save_comments(product_comments, product)
            print(f'  SAVED {saved} (DB: {total})')
            total_saved += saved
        time.sleep(1)
    
    print(f'\n=== {product} COMPLETE ===')
    print(f'Total saved: {total_saved}')
