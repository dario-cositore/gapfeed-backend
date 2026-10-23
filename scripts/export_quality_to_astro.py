#!/usr/bin/env python3
"""
Export ONLY quality gaps from local SQLite to Astro site.
Filters out low-quality auto-generated gaps from April 6th failure.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def is_quality_gap(gap):
    """Check if a gap meets quality criteria."""
    desc = gap.get('description', '')
    if not desc or len(desc) < 100:
        return False
    
    cat = gap.get('category', '')
    if cat in ['missing', 'bug', 'uncategorized', 'other']:
        return False
    
    comp = gap.get('competitors', '[]')
    if not comp or comp == '[]':
        return False
    
    quotes = gap.get('sample_quotes', '[]')
    if not quotes or quotes == '[]':
        return False
    
    title = gap.get('title', '')
    if ' — ' in title and title.endswith('Issues'):
        return False
    
    return True

def export_quality_gaps():
    """Export only quality gaps."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get all active gaps
        cursor.execute("""
            SELECT 
                id, title, slug, description, evidence_count, heat_score,
                category, source_types, signal_ids, sample_quotes,
                competitors, gap_validity, opportunity_score, status,
                created_at, updated_at
            FROM gaps
            WHERE status = 'active'
            ORDER BY heat_score DESC
        """)
        all_gaps = [dict(row) for row in cursor.fetchall()]
        
        # Filter for quality gaps
        quality_gaps = [g for g in all_gaps if is_quality_gap(g)]
        
        # Get stats
        cursor.execute("SELECT COUNT(*) as count FROM signals")
        signals_total = cursor.fetchone()[0]
        
        # Get source distribution
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM signals
            GROUP BY source
            ORDER BY count DESC
            LIMIT 20
        """)
        source_dist = [dict(row) for row in cursor.fetchall()]
        
        # Get sentiment breakdown
        cursor.execute("""
            SELECT sentiment, COUNT(*) as count
            FROM signals
            GROUP BY sentiment
        """)
        sentiment_breakdown = [dict(row) for row in cursor.fetchall()]
        
        # Get buyer intent distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN buyer_intent >= 0.7 THEN 'high'
                    WHEN buyer_intent >= 0.4 THEN 'medium'
                    ELSE 'low'
                END as bucket,
                COUNT(*) as count
            FROM signals
            GROUP BY bucket
        """)
        buyer_intent_dist = [dict(row) for row in cursor.fetchall()]
        
        # Prepare data structure
        data = {
            'gaps': quality_gaps,
            'source_distribution': source_dist,
            'sentiment_breakdown': sentiment_breakdown,
            'buyer_intent_distribution': buyer_intent_dist,
            'stats': {
                'signals': signals_total,
                'gaps': len(quality_gaps)
            },
            'total_signals_all': signals_total,
            'total_gaps': len(quality_gaps),
            'exported_at': datetime.now().isoformat()
        }
        
        # Save to Astro's public data directory
        output_path = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"=== QUALITY GAP EXPORT ===")
        print(f"Total active gaps in DB: {len(all_gaps)}")
        print(f"Quality gaps exported: {len(quality_gaps)}")
        print(f"Low quality filtered out: {len(all_gaps) - len(quality_gaps)}")
        print(f"Quality percentage: {len(quality_gaps)/len(all_gaps)*100:.1f}%")
        print(f"Signals exported: {signals_total}")
        print(f"Exported to: {output_path}")
        print()
        
        # Show sample quality gaps
        print("Sample quality gaps:")
        for gap in quality_gaps[:5]:
            print(f"  • {gap['title'][:60]}...")
            print(f"    Category: {gap['category']}, Heat: {gap['heat_score']}")
            
    finally:
        conn.close()

if __name__ == '__main__':
    export_quality_gaps()
