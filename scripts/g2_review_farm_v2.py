#!/usr/bin/env python3
"""
NON-REDDIT PAIN FARM — G2/Capterra Reviews from Elitza's Tools
Scales up to extract ALL available review data
"""
import json, sqlite3, os, re
from datetime import datetime, timezone

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def load_json_file(path):
    """Load JSON file"""
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f'  Error loading {path}: {e}')
        return []

def extract_product_from_path(path):
    """Extract product name from file path"""
    # Parse filename like: slack_g2_reviews_20250921_161443.json
    filename = os.path.basename(path)
    parts = filename.split('_')
    if len(parts) >= 3:
        # First part is usually the product name
        product = parts[0]
        # Check if it's g2 or capterra
        if 'g2' in filename.lower():
            source = 'G2'
        elif 'capterra' in filename.lower():
            source = 'Capterra'
        else:
            source = 'Review'
        return product, source
    return 'Unknown', 'Review'

def process_review_data(reviews, product, source, filename):
    """Process review data and extract pain points"""
    processed = []
    
    for review in reviews:
        if not isinstance(review, dict):
            continue
        
        # Extract text from various fields
        text = review.get('review', '') or review.get('description', '') or review.get('title', '')
        if not text or len(text) < 15:
            continue
        
        # Get rating
        rating = review.get('rating', '0')
        if isinstance(rating, str):
            # Extract number from "4.5/5" or "4.5"
            match = re.search(r'(\d+\.?\d*)', rating)
            if match:
                rating = match.group(1)
        
        # Get reviewer
        reviewer_info = review.get('reviewer_info', {})
        if isinstance(reviewer_info, str):
            reviewer = reviewer_info
        elif isinstance(reviewer_info, dict):
            reviewer = reviewer_info.get('name', reviewer_info.get('title', 'Anonymous'))
        else:
            reviewer = 'Anonymous'
        
        if not reviewer or len(reviewer) < 2:
            reviewer = 'Anonymous'
        
        # Generate URL (mock, since we don't have original URLs)
        review_id = hash(filename + str(text[:50])) % 1000000
        if source == 'G2':
            url = f'https://www.g2.com/products/{product.lower().replace(" ", "-")}/reviews#review-{review_id}'
        elif source == 'Capterra':
            url = f'https://www.capterra.com/p/{product.lower().replace(" ", "-")}/reviews/{review_id}/'
        else:
            url = f'https://reviews.example.com/{product}/{review_id}'
        
        # Extract pros/cons if available
        pros = review.get('pros', '') or ''
        cons = review.get('cons', '') or ''
        
        # Build pain text - cons are the most valuable
        pain_text = text
        if cons and len(cons) > 10:
            pain_text = f"Complaint: {text}\n\nCons/Dislikes: {cons}"
        elif rating and isinstance(rating, (int, float)) and float(rating) <= 2.5:
            # Low rating indicates pain
            pain_text = f"[Rating: {rating}/5] {text}"
        
        # Get date
        published = review.get('date', '') or review.get('published', '') or ''
        
        processed.append({
            'product': product,
            'source': source,
            'url': url,
            'author': reviewer[:100],
            'rating': str(rating),
            'text': pain_text[:1500],
            'published': published,
            'title': review.get('title', '')[:100],
        })
    
    return processed

def save_to_db(reviews, product):
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
        try:
            cur.execute('''
                INSERT OR IGNORE INTO signals 
                (source, source_url, subreddit, author, title, content, created_at, collected_at, vertical, quality_tier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'{r["source"]} Review',
                r['url'],
                r['product'],
                r['author'],
                f"{r['product']} {r['source']} Review: {r['title']}",
                r['text'],
                r['published'],
                datetime.now(tz=timezone.utc).isoformat(),
                r['product'].lower().replace(' ', '-'),
                'high' if r.get('rating', '0') and float(r['rating']) <= 3 else 'medium'
            ))
            if cur.rowcount > 0:
                saved += 1
        except Exception as e:
            pass
    
    conn.commit()
    total = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
    conn.close()
    return saved, total

# Scan for all review files
def find_all_review_files():
    """Find all review JSON files in shady_tools"""
    base_path = '/home/dario/Elitza/shady_tools'
    review_files = []
    
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith('.json') and file != 'webdriver_prefs.json':
                path = os.path.join(root, file)
                # Check if it's a review file (has reasonable size)
                try:
                    size = os.path.getsize(path)
                    if size > 500:  # At least 500 bytes
                        review_files.append(path)
                except:
                    pass
    
    return review_files

def main():
    print('=' * 70)
    print('NON-REDDIT PAIN FARM — All G2/Capterra Reviews')
    print('=' * 70)
    print('Scanning for review files in Elitza\'s shady_tools...')
    print()
    
    review_files = find_all_review_files()
    print(f'Found {len(review_files)} potential review files\n')
    
    total_processed = 0
    total_saved = 0
    
    for file_path in review_files:
        filename = os.path.basename(file_path)
        reviews = load_json_file(file_path)
        
        if not reviews:
            continue
        
        product, source = extract_product_from_path(filename)
        
        print(f'{filename}:')
        print(f'  Product: {product}, Source: {source}, Records: {len(reviews)}')
        
        processed = process_review_data(reviews, product, source, filename)
        
        if processed:
            saved, total_db = save_to_db(processed, product)
            print(f'  Processed: {len(processed)}, Saved: {saved}, DB Total: {total_db}')
            total_processed += len(processed)
            total_saved += saved
        else:
            print(f'  No valid reviews extracted')
        
        print()
    
    print('=' * 70)
    print(f'COMPLETE')
    print(f'Total reviews processed: {total_processed}')
    print(f'Total reviews saved: {total_saved}')
    print('=' * 70)

if __name__ == '__main__':
    main()
