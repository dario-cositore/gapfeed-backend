#!/usr/bin/env python3
"""
Export gap data from LOCAL SQLite database for Astro site.
This pulls from gapfeed_unified.db which should sync with pristine DB.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

def export_gaps_for_astro():
    """Export gaps in the format Astro expects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get gaps with all necessary fields
        cursor.execute("""
            SELECT 
                id, title, slug, description, evidence_count, heat_score,
                category, source_types, signal_ids, sample_quotes,
                competitors, gap_validity, opportunity_score, status,
                created_at, updated_at
            FROM gaps
            WHERE status = 'active'
            ORDER BY heat_score DESC
            LIMIT 100
        """)
        gaps = [dict(row) for row in cursor.fetchall()]
        
        # Sanitize slugs (replace problematic characters)
        for gap in gaps:
            if gap.get('slug'):
                slug = gap['slug']
                slug = slug.replace('&', 'and')  # Replace & with 'and'
                slug = slug.replace('/', '-')    # Replace / with - for URL safety
                gap['slug'] = slug
        
        # Get stats
        cursor.execute("SELECT COUNT(*) as count FROM signals")
        signals_total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) as count FROM gaps WHERE status = 'active'")
        gaps_total = cursor.fetchone()[0]
        
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
            'gaps': gaps,
            'source_distribution': source_dist,
            'sentiment_breakdown': sentiment_breakdown,
            'buyer_intent_distribution': buyer_intent_dist,
            'stats': {
                'signals': signals_total,
                'gaps': gaps_total
            },
            'total_signals_all': signals_total,
            'total_gaps': gaps_total,
            'exported_at': datetime.now().isoformat()
        }
        
        # Save to Astro's public data directory
        output_path = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Exported {len(gaps)} gaps and {signals_total} signals to {output_path}")
        print(f"   Gaps (active): {gaps_total}")
        print(f"   Signals: {signals_total}")
        print(f"   Exported at: {datetime.now()}")
            
    finally:
        conn.close()

if __name__ == '__main__':
    export_gaps_for_astro()
