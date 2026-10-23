#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — Direct innertube API, zero dependencies
"""
import json, urllib.request, urllib.parse, ssl, sqlite3, time, sys
from datetime import datetime, timezone
import re

DB = '/home/dario/gapfeed/code/data/gapfeed_unified.db'
KEY = "os.environ.get('GOOGLE_API_KEY', '')"

def api_call(path, body):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        f'https://www.youtube.com/youtubei/v1/{path}?key={KEY}',
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        method='POST'
    )
    r = urllib.request.urlopen(req, timeout=15, context=ctx)
    return json.loads(r.read().decode())

def search_videos(query, n=5):
    try:
        data = api_call('search', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'query': query,
        })
        videos = []
        results = data.get('contents',{}).get('twoColumnSearchResultsRenderer',{}).get('primaryContents',{}).get('sectionListRenderer',{}).get('contents',[])
        for s in results:
            for item in s.get('itemSectionRenderer',{}).get('contents',[]):
                vr = item.get('videoRenderer', {})
                vid = vr.get('videoId','')
                title = ''.join(r.get('text','') for r in vr.get('title',{}).get('runs',[]))
                views = vr.get('viewCountText',{}).get('simpleText','')
                channel = vr.get('ownerText',{}).get('runs',[{}])[0].get('text','')
                if vid:
                    videos.append({'id': vid, 'title': title[:100], 'views': views, 'channel': channel[:50]})
                if len(videos) >= n:
                    return videos
        return videos
    except Exception as e:
        print(f'  Search fail: {e}')
        return []

def get_comments(video_id, max_c=200):
    try:
        data = api_call('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'videoId': video_id,
        })
        
        # Find the comments section
        contents = data.get('contents',{}).get('twoColumnWatchNextResults',{}).get('results',{}).get('results',{}).get('contents',[])
        
        # Find comment thread
        continuation = None
        for c in contents:
            if 'itemSectionRenderer' in c:
                isr = c.get('itemSectionRenderer',{}).get('contents',[])
                # Check for comments
                for item in isr:
                    continuation = item.get('continuationItemRenderer',{})
                    if continuation:
                        break
                # Also check for actual comment threads in first render
                for item in isr:
                    tr = item.get('commentThreadRenderer',{})
                    if not tr:
                        continue
                    cr = tr.get('comment',{}).get('commentRenderer',{})
                    if not cr:
                        continue
                    yield cr, tr
        
        if not continuation:
            return
        
        # Get continuation token
        cont_token = continuation.get('continuationEndpoint',{}).get('continuationCommand',{}).get('token','')
        if not cont_token:
            return
            
        # Fetch comments via continuation
        cont_data = api_call('next', {
            'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20231018.00.00'}},
            'continuation': cont_token,
        })
        
        count = 0
        endpoints = cont_data.get('onResponseReceivedEndpoints',[])
        for ep in endpoints:
            items = ep.get('appendContinuationItemsAction',{}).get('continuationItems',[])
            for item in items:
                tr = item.get('commentThreadRenderer',{})
                if not tr:
                    continue
                cr = tr.get('comment',{}).get('commentRenderer',{})
                if not cr:
                    continue
                yield cr, tr
                count += 1
                if count >= max_c:
                    return
                
                # Check for next continuation
                for sub_item in tr.get('replies',{}).get('commentRepliesRenderer',{}).get('contents',[]):
                    cont = sub_item.get('continuationItemRenderer',{})
                    if cont:
                        cont_token = cont.get('continuationEndpoint',{}).get('continuationCommand',{}).get('token','')
                        if cont_token:
                            break
    except Exception as e:
        pass

def save_comms(comments, product):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    saved = 0
    for c in comments:
        try:
            cur.execute('INSERT OR IGNORE INTO signals (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier) VALUES (?,?,?,?,?,?,?,?,?,?)',
                ('YouTube', c['url'], product, c['author'], c.get('video_title','')[:80], c['text'][:2000], '', datetime.now(tz=timezone.utc).isoformat(), product.lower().replace(' ','-'), 'medium'))
            saved += 1
        except: pass
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# PRODUCT -> queries
PRODUCTS = {
    'Shopify': ['shopify sucks', 'shopify problems', 'shopify vs', 'why i left shopify', 'shopify alternative'],
    'Stripe': ['stripe payments problems', 'stripe frozen account', 'stripe vs', 'stripe sucks', 'stripe alternative'],
    'Notion': ['notion problems', 'notion sucks', 'notion vs airtable', 'notion too slow', 'notion cringe'],
    'Klaviyo': ['klaviyo review', 'klaviyo vs', 'klaviyo too expensive', 'klaviyo sucks', 'klaviyo problems'],
    'GoDaddy': ['godaddy sucks', 'godaddy review', 'why I left godaddy', 'godaddy alternative', 'godaddy problems'],
    'QuickBooks': ['quickbooks problems', 'quickbooks vs xero', 'quickbooks sucks', 'quickbooks review', 'quickbooks alternative'],
    'Zendesk': ['zendesk sucks', 'zendesk vs', 'zendesk too expensive', 'zendesk review', 'zendesk alternative'],
    'Wix': ['wix sucks', 'wix vs', 'wix review', 'wix problems', 'wix alternative'],
    'Squarespace': ['squarespace sucks', 'squarespace vs', 'squarespace review', 'squarespace problems', 'squarespace alternative'],
    'Webflow': ['webflow sucks', 'webflow review', 'webflow vs', 'webflow problems', 'webflow alternative'],
}

def run_product(name, queries):
    print(f'\n=== {name} ===')
    all_comments = []
    for q in queries:
        print(f'  Query: "{q}"')
        vids = search_videos(q, n=3)
        print(f'    Found {len(vids)} videos')
        for v in vids:
            vid_id = v['id']
            for cr, tr in get_comments(vid_id, 100):
                comment_id = cr.get('commentId','')
                text = ''
                for run in cr.get('contentText',{}).get('runs',[]): text += run.get('text','')
                if not text: text = cr.get('contentText',{}).get('simpleText','')
                author = cr.get('authorText',{}).get('simpleText','')
                likes = cr.get('voteCount',{}).get('simpleText','0')
                published = cr.get('publishedTimeText',{}).get('simpleText','')
                url = f'https://www.youtube.com/watch?v={vid_id}&lc={comment_id}'
                if text and len(text) > 15:
                    all_comments.append({
                        'url': url, 'author': author, 'text': text[:1000],
                        'likes': likes, 'published': published,
                        'video_id': vid_id, 'video_title': v['title']
                    })
            time.sleep(1)
    print(f'  Extracted {len(all_comments)} comments')
    if all_comments:
        saved, total = save_comms(all_comments, name)
        print(f'  SAVED {saved} (DB: {total})')
    time.sleep(1)
    return len(all_comments)

if __name__ == '__main__':
    print('=== YOUTUBE COMMENT FARM ===')
    print(f'Starting: {datetime.now().strftime("%H:%M:%S")}')
    print(f'Targets: {len(PRODUCTS)} products × {len(next(iter(PRODUCTS.values())))} queries = {len(PRODUCTS)*5} queries')
    print(f'Searches per query: 3 videos × ~150 comments = ~2250 comments per product')
    print(f'Expected total: ~45,000 comments\n')
    
    total = 0
    for name, queries in PRODUCTS.items():
        total += run_product(name, queries)
        print(f'  Running total: {total}')
    
    print(f'\n=== COMPLETE: {total} comments ===')
