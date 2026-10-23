#!/usr/bin/env python3
"""
Export fresh gap data from SQLite for Astro site.
Uses local database instead of MySQL.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/4. Backend/data/gapfeed_unified.db'
OUTPUT_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/2. Website/gapfeed.com/gapfeed-astro/public/data/data.json'

def is_quality_gap(gap):
    """Check if a gap meets quality criteria."""
    if not gap.get('description') or len(gap.get('description', '')) < 50:
        return False
    if gap.get('category') in ['uncategorized', 'bug', 'missing', 'missing_feature']:
        return False
    return True

def export_gaps_for_astro():
    """Export gaps in the format Astro expects."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        # Get quality active gaps
        cursor.execute("""
            SELECT 
                id, title, slug, description, evidence_count, heat_score,
                category, source_types, sample_quotes,
                competitors, gap_validity, opportunity_score, status,
                created_at, updated_at
            FROM gaps
            WHERE status = 'active'
            ORDER BY heat_score DESC
            LIMIT 50
        """)
        gaps_raw = [dict(row) for row in cursor.fetchall()]
        
        # Filter for quality
        gaps = [g for g in gaps_raw if is_quality_gap(g)]
        
        # Transform for Astro
        transformed = []
        for g in gaps:
            transformed.append({
                'id': g['id'],
                'title': g['title'],
                'slug': g['slug'],
                'category': g['category'],
                'signals': g.get('evidence_count', 0),
                'heat_score': int(g.get('heat_score', 0) * 100) if g.get('heat_score', 0) <= 1 else int(g.get('heat_score', 0)),
                'description': g.get('description', ''),
                'the_opportunity': g.get('description', '')[:200],
                'sample_quotes': g.get('sample_quotes', []),
                'competitors': g.get('competitors', []),
                'db_gap_id': g['id']
            })
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM signals")
        signals_total = cursor.fetchone()[0]
        
        # Get source distribution
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM signals
            GROUP BY source
            ORDER BY count DESC
            LIMIT 10
        """)
        source_dist = [dict(row) for row in cursor.fetchall()]
        
        # Get sentiment breakdown
        cursor.execute("""
            SELECT sentiment, COUNT(*) as count
            FROM signals
            GROUP BY sentiment
        """)
        sentiment = {row[0]: row[1] for row in cursor.fetchall()}
        
        data = {
            'gaps': transformed,
            'source_distribution': source_dist,
            'sentiment_breakdown': sentiment,
            'stats': {
                'signals': signals_total,
                'gaps': len(transformed)
            },
            'exported_at': datetime.now().isoformat()
        }
        
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Exported {len(transformed)} quality gaps")
        print(f"   Total signals: {signals_total:,}")
        
    finally:
        conn.close()

if __name__ == '__main__':
    export_gaps_for_astro()