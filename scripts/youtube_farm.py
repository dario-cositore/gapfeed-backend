#!/usr/bin/env python3
"""
YOUTUBE COMMENT FARM — Phase 1: Search + Extract
No videos, JUST comments. Exact hyperlinks. Pain extraction.
"""
import json, os, sys, time, subprocess, sqlite3
from datetime import datetime, timezone

DB_PATH = '/home/dario/gapfeed/code/data/gapfeed_unified.db'
OR_KEY = open('/home/dario/.el_api').read().strip()

# 20 TARGET PRODUCTS — each gets 5 search queries
PRODUCTS = {
    'Shopify': ['shopify sucks', 'shopify problems', 'shopify alternative', 'shopify vs woocommerce', 'why I left shopify'],
    'Stripe': ['stripe payment issues', 'stripe problems', 'stripe vs paypal', 'stripe account frozen', 'stripe alternative'],
    'Klaviyo': ['klaviyo review', 'klaviyo vs mailchimp', 'klaviyo problems', 'klaviyo alternative', 'klaviyo too expensive'],
    'Notion': ['notion problems', 'notion sucks', 'notion vs airtable', 'notion too slow', 'notion alternative 2025'],
    'QuickBooks': ['quickbooks problems', 'quickbooks sucks', 'quickbooks vs xero', 'quickbooks too expensive', 'quickbooks customer service'],
    'Zendesk': ['zendesk alternative', 'zendesk sucks', 'zendesk too expensive', 'zendesk problems', 'zendesk review'],
    'GoDaddy': ['godaddy sucks', 'godaddy alternative', 'godaddy problems', 'godaddy review', 'why I left godaddy'],
    'WordPress': ['wordpress sucks', 'wordpress too slow', 'wordpress alternative', 'wordpress security issues', 'wordpress plugin problems'],
    'Squarespace': ['squarespace sucks', 'squarespace vs wix', 'squarespace problems', 'squarespace seo', 'squarespace review'],
    'Mailchimp': ['mailchimp too expensive', 'mailchimp alternative', 'mailchimp sucks', 'mailchimp problems', 'mailchimp review'],
    'Xero': ['xero vs quickbooks', 'xero problems', 'xero sucks', 'xero review', 'xero alternative'],
    'ClickFunnels': ['clickfunnels sucks', 'clickfunnels alternative', 'clickfunnels review', 'clickfunnels worth it', 'clickfunnels problems'],
    'GoHighLevel': ['gohighlevel review', 'gohighlevel problems', 'gohighlevel sucks', 'gohighlevel alternative', 'go high level review'],
    'HubSpot': ['hubspot too expensive', 'hubspot vs salesforce', 'hubspot problems', 'hubspot CRM', 'hubspot review'],
    'Canva': ['canva vs adobe', 'canva sucks', 'canva problems', 'canva pro worth it', 'canva review'],
    'FreshBooks': ['freshbooks problems', 'freshbooks vs quickbooks', 'freshbooks sucks', 'freshbooks review', 'freshbooks too expensive'],
    'WooCommerce': ['woocommerce problems', 'woocommerce sucks', 'woocommerce vs shopify', 'woocommerce review', 'woocommerce too hard'],
    'Zapier': ['zapier too expensive', 'zapier alternative', 'zapier sucks', 'zapier vs make', 'zapier review'],
    'Slack': ['slack problems', 'slack too expensive', 'slack vs teams', 'slack sucks', 'slack productivity'],
    'Salesforce': ['salesforce too expensive', 'salesforce sucks', 'salesforce alternative', 'salesforce review', 'salesforce crm problems'],
}

def search_youtube(query, max_results=10):
    """Search YouTube, return video IDs + metadata."""
    cmd = [
        'python3', '-m', 'yt_dlp',
        f'ytsearch{max_results}:{query}',
        '--flat-playlist',
        '--print', '%(id)s | %(title)s | %(view_count)s | %(channel)s',
        '--no-warnings',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        videos = []
        for line in result.stdout.strip().split('\n'):
            parts = line.strip().split(' | ', 3)
            if len(parts) >= 4:
                videos.append({
                    'video_id': parts[0],
                    'title': parts[1],
                    'views': parts[2],
                    'channel': parts[3],
                    'search_query': query,
                    'search_url': f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
                })
        return videos
    except Exception as e:
        print(f'  Search error: {e}')
        return []

def extract_comments(video_id, video_title, max_comments=500):
    """Extract comments from a video WITHOUT downloading it."""
    cmd = [
        'python3', '-m', 'yt_dlp',
        f'https://www.youtube.com/watch?v={video_id}',
        '--skip-download',
        '--write-comments',
        '--output', f'/tmp/yt_comments/{video_id}.info.json',
        '--no-warnings',
        '--quiet',
    ]
    os.makedirs('/tmp/yt_comments', exist_ok=True)
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        json_path = f'/tmp/yt_comments/{video_id}.info.json'
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
            
            comments_raw = data.get('automatic_captions') if False else data.get('comments', [])
            
            comments = []
            for c in comments_raw[:max_comments]:
                comment_id = c.get('id', '')
                text = c.get('text', '') or c.get('description', '')
                author = c.get('author', '')
                timestamp = c.get('timestamp') or c.get('published_time') or 0
                likes = c.get('like_count', 0)
                replies = c.get('replies', {}) or {}
                reply_count = len(replies.get('replies', [])) if isinstance(replies, dict) else 0
                
                # Exact comment URL
                comment_url = f'https://www.youtube.com/watch?v={video_id}&lc={comment_id}' if comment_id else f'https://www.youtube.com/watch?v={video_id}'
                
                if text and len(text) > 20:
                    comments.append({
                        'video_id': video_id,
                        'video_title': video_title,
                        'comment_id': comment_id,
                        'comment_url': comment_url,
                        'text': text[:1000],
                        'author': author,
                        'timestamp': timestamp,
                        'likes': likes,
                        'reply_count': reply_count,
                        'product': '',  # Will be set by caller
                        'search_query': ''
                    })
            
            return comments
        return []
    except Exception as e:
        print(f'  Comment error for {video_id}: {str(e)[:60]}')
        return []

def save_comments(comments):
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
                c['product'],  # subreddit field = product name
                c['author'],
                f"{c['video_title'][:80]} — @{c['author']}",
                c['text'][:2000],
                datetime.fromtimestamp(c['timestamp'], tz=timezone.utc).isoformat() if c['timestamp'] else '',
                datetime.now(tz=timezone.utc).isoformat(),
                c['product'].lower(),
                'high' if c['likes'] > 10 else 'medium'
            ))
            saved += 1
        except: pass
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# ============================================================
# MAIN: Search + Extract for one product (incremental)
# ============================================================
def run_product_batch(product_name, queries):
    """Process queries for one product."""
    print(f'\n=== {product_name} ({len(queries)} queries) ===')
    
    all_comments = []
    
    for q_idx, query in enumerate(queries):
        print(f'  [{q_idx+1}/{len(queries)}] Searching: "{query}"')
        videos = search_youtube(query, max_results=5)
        if not videos:
            print(f'    No results')
            continue
        print(f'    Found {len(videos)} videos')
        
        for v_idx, v in enumerate(videos):
            print(f'    [{v_idx+1}] {v["title"][:60]} ({v["views"]} views)')
            comments = extract_comments(v['video_id'], v['title'], max_comments=200)
            for c in comments:
                c['product'] = product_name
                c['search_query'] = query
            all_comments.extend(comments)
            print(f'       {len(comments)} comments')
            time.sleep(1)  # Rate limit between videos
        
        time.sleep(2)  # Between queries
    
    if all_comments:
        saved, total = save_comments(all_comments)
        print(f'  SAVED {saved}/{len(all_comments)} comments (DB total: {total})')
    else:
        print(f'  No comments extracted')
    
    return saved if all_comments else 0

# Run one product at a time
if __name__ == '__main__':
    import sys
    
    # Check if specific product was requested
    if len(sys.argv) > 1:
        product = sys.argv[1]
        queries = PRODUCTS.get(product, [f'{product} review', f'{product} problems', f'{product} alternative'])
        saved = run_product_batch(product, queries)
        print(f'\n{product}: {saved} comments saved')
    else:
        print('Usage: python3 youtube_farm.py [product_name]')
        print('Products:', ', '.join(list(PRODUCTS.keys())[:10]))
