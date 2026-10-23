#!/usr/bin/env python3
"""
NON-REDDIT PAIN FARM — G2/Capterra/Trustpilot Reviews
These are ACTUAL buyer complaints from people who PAID for products.
"""
import json, sqlite3, os, time, random
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

# Paths to the working review data from Elitza's shady_tools
REVIEW_PATHS = {
    'Slack': {
        'G2': '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/slack_g2_reviews_20250921_161443.json',
        'Test': '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/slack_test_reviews.json',
    },
    'Zoom': {
        'G2': '/home/dario/Elitza/shady_tools/Review_Scraper/g2_reviews_zoom_2024-01-01_to_2024-06-06.json',
    },
    'HubSpot': {
        'G2': '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/hubspot_g2_reviews_20250921_162810.json',
    },
    'Facebook': {
        'G2': '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/facebook_g2_reviews_20250921_162810.json',
    },
}

def load_reviews(product, source):
    """Load reviews from a JSON file"""
    path = REVIEW_PATHS.get(product, {}).get(source, '')
    if not path or not os.path.exists(path):
        return []
    
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f'  Error loading {path}: {e}')
        return []

def extract_pain_from_review(review, product, source):
    """Extract pain points from a review"""
    # Get review text from various fields
    text = ''
    if 'review' in review:
        text = review['review']
    elif 'description' in review:
        text = review['description']
    elif 'title' in review and 'review' not in review:
        text = review['title']
    
    if not text or len(text) < 20:
        return None
    
    # Get rating
    rating = review.get('rating', '0')
    if isinstance(rating, str) and '/' in rating:
        rating = rating.split('/')[0]
    
    # Get pros and cons
    pros = review.get('pros', '')
    cons = review.get('cons', '')
    
    # Get reviewer info
    reviewer = review.get('reviewer_info', {}) or review.get('reviewer_name', 'Anonymous')
    if isinstance(reviewer, dict):
        reviewer = reviewer.get('name', 'Anonymous')
    
    # Create comment URL (G2 review permalink)
    review_id = review.get('id', hash(text) % 1000000)
    comment_url = f'https://www.g2.com/products/{product.lower().replace(" ", "-")}/reviews#review-{review_id}'
    
    # Extract pain from cons section or negative parts of review
    pain_text = text
    if cons and len(cons) > 10:
        pain_text = f"{text}\n\nCON: {cons}"
    elif rating and float(rating) <= 2.5:
        pain_text = text  # Low rating = likely pain
    
    return {
        'product': product,
        'source': source,
        'comment_url': comment_url,
        'author': reviewer,
        'rating': rating,
        'text': pain_text[:1500],
        'published': review.get('date', ''),
        'title': review.get('title', '')[:100],
        'pros': pros[:500],
        'cons': cons[:500],
    }

def save_reviews_to_db(reviews, product, source):
    """Save reviews to database"""
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
    for r in reviews:
        data = extract_pain_from_review(r, product, source)
        if not data:
            continue
        
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'{source} Review',
                data['comment_url'],
                product,
                data['author'],
                f"{product} {source} Review: {data['title']}",
                data['text'],
                data['published'],
                datetime.now(tz=timezone.utc).isoformat(),
                product.lower().replace(' ', '-'),
                'high' if data.get('rating', '0') and float(data['rating']) <= 3 else 'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

def process_product(product, sources):
    """Process all review sources for a product"""
    print(f'\n>>> {product}')
    all_reviews = []
    
    for source, path in sources.items():
        if not os.path.exists(path):
            print(f'  {source}: File not found')
            continue
        
        reviews = load_reviews(product, source)
        print(f'  {source}: {len(reviews)} reviews loaded')
        
        if reviews:
            all_reviews.extend(reviews)
    
    if all_reviews:
        saved, total = save_reviews_to_db(all_reviews, product, 'G2')
        print(f'  SAVED {saved}/{len(all_reviews)} reviews (DB: {total})')
    else:
        print(f'  No reviews found')
    
    return len(all_reviews)

# Main execution
if __name__ == '__main__':
    print('=' * 60)
    print('NON-REDDIT PAIN FARM — G2 Reviews')
    print('=' * 60)
    print('Loading existing review data from Elitza\'s shady_tools...')
    print()
    
    total_reviews = 0
    for product, sources in REVIEW_PATHS.items():
        count = process_product(product, sources)
        total_reviews += count
    
    print(f'\n' + '=' * 60)
    print(f'COMPLETE: {total_reviews} reviews extracted and saved')
    print('=' * 60)
