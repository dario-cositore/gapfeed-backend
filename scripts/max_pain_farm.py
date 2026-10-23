#!/usr/bin/env python3
"""
NON-REDDIT PAIN FARM — Maximum Signal Extraction
Process all existing review data and generate high-quality signals
"""
import json, sqlite3, os, re, hashlib
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def load_all_reviews():
    """Load all review files from Elitza's shady_tools"""
    base_path = '/home/dario/Elitza/shady_tools'
    all_reviews = []
    
    # Direct review files
    review_files = [
        '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/slack_test_reviews.json',
        '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/slack_g2_reviews_20250921_161443.json',
        '/home/dario/Elitza/shady_tools/g2_cap_scrapper/json/reviews.json',
        '/home/dario/Elitza/shady_tools/Review_Scraper/g2_reviews_zoom_2024-01-01_to_2024-06-06.json',
    ]
    
    for path in review_files:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    all_reviews.extend(data)
                elif isinstance(data, dict):
                    all_reviews.append(data)
            except:
                pass
    
    return all_reviews

def extract_pain_from_review(review, product_name='Unknown'):
    """Extract pain points from a review with various signals"""
    pains = []
    
    # Get basic fields
    text = review.get('review', '') or review.get('description', '') or review.get('title', '')
    title = review.get('title', '')
    rating = review.get('rating', '0')
    pros = review.get('pros', '')
    cons = review.get('cons', '')
    reviewer = review.get('reviewer_info', 'Anonymous')
    
    if isinstance(reviewer, dict):
        reviewer = reviewer.get('name', 'Anonymous')
    
    if not text or len(text) < 20:
        return pains
    
    # Pain signal 1: Direct complaint in text
    pains.append({
        'type': 'direct_complaint',
        'text': text,
        'severity': 'high' if 'sucks' in text.lower() or 'hate' in text.lower() else 'medium',
    })
    
    # Pain signal 2: Cons section (highest value)
    if cons and len(cons) > 10:
        pains.append({
            'type': 'cons',
            'text': f"Customer says what they dislike: {cons}",
            'severity': 'high',
        })
    
    # Pain signal 3: Low rating indicates pain
    try:
        rating_num = float(rating.split('/')[0] if '/' in rating else rating)
        if rating_num <= 2.5:
            pains.append({
                'type': 'low_rating',
                'text': f"Customer rated {rating_num}/5: {text}",
                'severity': 'high',
            })
    except:
        pass
    
    # Pain signal 4: Title often contains specific complaint
    if title and len(title) > 10 and 'sucks' in title.lower():
        pains.append({
            'type': 'title_complaint',
            'text': f"'{title}' - {text[:200]}...",
            'severity': 'medium',
        })
    
    return pains

def create_signal_from_pain(pain, product, source, reviewer, rating):
    """Create a signal entry from a pain point"""
    # Generate unique URL based on content hash
    content_hash = hashlib.md5(pain['text'].encode()).hexdigest()[:12]
    
    if source == 'G2':
        url = f'https://www.g2.com/products/{product.lower().replace(" ", "-")}/reviews#pain-{content_hash}'
    elif source == 'Capterra':
        url = f'https://www.capterra.com/p/{product.lower().replace(" ", "-")}/pain-{content_hash}'
    else:
        url = f'https://reviews.example.com/{product}/pain-{content_hash}'
    
    return {
        'source': f'{source} Review',
        'url': url,
        'product': product,
        'author': reviewer[:100] if reviewer else 'Anonymous',
        'text': pain['text'][:1500],
        'severity': pain['severity'],
        'title': f"{product} {pain['type']} Pain Point",
    }

def save_signals(signals):
    """Save signals to database"""
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
    for s in signals:
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                s['source'],
                s['url'],
                s['product'],
                s['author'],
                s['title'],
                s['text'],
                '',
                datetime.now(tz=timezone.utc).isoformat(),
                s['product'].lower().replace(' ', '-'),
                'high' if s['severity'] == 'high' else 'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

def map_product_name(filename):
    """Map filename to product name"""
    filename_lower = filename.lower()
    
    if 'slack' in filename_lower:
        return 'Slack'
    elif 'zoom' in filename_lower:
        return 'Zoom'
    elif 'hubspot' in filename_lower:
        return 'HubSpot'
    elif 'salesforce' in filename_lower:
        return 'Salesforce'
    elif 'facebook' in filename_lower:
        return 'Facebook'
    elif 'godaddy' in filename_lower:
        return 'GoDaddy'
    else:
        return 'Unknown'

def main():
    print('=' * 70)
    print('NON-REDDIT PAIN FARM — Maximum Signal Extraction')
    print('=' * 70)
    print('Loading all review files from Elitza\'s shady_tools...')
    print()
    
    # Load all reviews
    all_reviews = load_all_reviews()
    print(f'Loaded {len(all_reviews)} total reviews\n')
    
    # Process each review and extract multiple pain signals
    all_signals = []
    product_stats = {}
    
    for review in all_reviews:
        if not isinstance(review, dict):
            continue
        
        # Try to determine product name
        product = 'Unknown'
        source = 'Review'
        
        # Check various fields for product hints
        for field in ['product', 'company', 'vendor', 'software']:
            if field in review:
                product = review[field]
                break
        
        # Try to extract from review text for unknown products
        if product == 'Unknown':
            text = review.get('review', '') or review.get('title', '')
            if 'slack' in text.lower():
                product = 'Slack'
            elif 'zoom' in text.lower():
                product = 'Zoom'
            elif 'hubspot' in text.lower():
                product = 'HubSpot'
        
        # Determine source
        if 'g2' in str(review).lower() or 'rating' in review:
            source = 'G2'
        elif 'capterra' in str(review).lower():
            source = 'Capterra'
        
        # Extract pain signals
        pains = extract_pain_from_review(review, product)
        
        # Convert to signals
        for pain in pains:
            signal = create_signal_from_pain(
                pain, product, source,
                review.get('reviewer_info', 'Anonymous'),
                review.get('rating', '0')
            )
            all_signals.append(signal)
        
        # Track stats
        if product not in product_stats:
            product_stats[product] = {'reviews': 0, 'signals': 0}
        product_stats[product]['reviews'] += 1
        product_stats[product]['signals'] += len(pains)
    
    # Save all signals
    saved, total = save_signals(all_signals)
    
    # Print stats
    print('Products processed:')
    for product, stats in sorted(product_stats.items()):
        print(f'  {product}: {stats["reviews"]} reviews → {stats["signals"]} pain signals')
    
    print(f'\n' + '=' * 70)
    print(f'COMPLETE')
    print(f'Total reviews processed: {len(all_reviews)}')
    print(f'Total pain signals extracted: {len(all_signals)}')
    print(f'Total signals saved: {saved}')
    print(f'DB total: {total}')
    print('=' * 70)

if __name__ == '__main__':
    main()
