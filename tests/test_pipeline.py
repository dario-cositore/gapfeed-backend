"""
gapfeed - Quick Test Script

Tests the core pipeline: init DB -> scan Reddit -> generate brief.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.signals_db import init_db, get_signal_count
from src.sources.reddit import scan_subreddit
from shared.signals_db import bulk_insert_signals
from src.engine.lookup import generate_brief


def main():
    print("=" * 60)
    print("gapfeed - Core Pipeline Test")
    print("=" * 60)
    
    # Step 1: Initialize database
    print("\n[1/4] Initializing database...")
    init_db()
    print("  Database ready.")
    
    # Step 2: Check current signals
    print("\n[2/4] Checking signal corpus...")
    counts = get_signal_count()
    print(f"  Total signals: {counts.get('total', 0)}")
    
    # Step 3: Scan if corpus is empty
    if counts.get('total', 0) < 50:
        print("\n[3/4] Corpus needs signals. Scanning Reddit...")
        print("  Scanning r/BuyItForLife...")
        signals = scan_subreddit('BuyItForLife', limit=5)
        if signals:
            inserted = bulk_insert_signals(signals)
            print(f"  Inserted {inserted} signals from r/BuyItForLife")
        
        print("  Scanning r/Cooking...")
        signals = scan_subreddit('Cooking', limit=5)
        if signals:
            inserted = bulk_insert_signals(signals)
            print(f"  Inserted {inserted} signals from r/Cooking")
        
        counts = get_signal_count()
        print(f"  Corpus now has {counts.get('total', 0)} signals")
    else:
        print("\n[3/4] Corpus has signals, skipping scan.")
    
    # Step 4: Generate a test brief
    print("\n[4/4] Generating test brief...")
    brief = generate_brief("coffee mug", max_signals=100)
    
    print(f"\n{'=' * 60}")
    print(f"BRIEF RESULT")
    print(f"{'=' * 60}")
    print(f"Query: {brief['query']}")
    print(f"Signals: {brief['signal_count']}")
    print(f"Quality: {brief['quality']}")
    print(f"Cached: {brief['cached']}")
    print(f"\n{brief['brief'][:1000]}...")
    
    # Save brief to file
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'data', 'briefs'), exist_ok=True)
    brief_path = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'briefs',
        f"test_brief_{brief['query'].replace(' ', '_')}.md"
    )
    with open(brief_path, 'w', encoding='utf-8') as f:
        f.write(brief['brief'])
    print(f"\nBrief saved to: {brief_path}")
    
    print("\n" + "=" * 60)
    print("Pipeline test complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()

