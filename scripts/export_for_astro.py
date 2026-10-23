#!/usr/bin/env python3
"""
Export fresh gap data from pristine MySQL DB for Astro site.
"""

import os
import pymysql
import json
from datetime import datetime

# Pristine DB connection (IONOS hosting)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', ''),
    'user': os.environ.get('DB_USER', ''),
    'password': os.environ.get('DB_PASS', ''),
    'database': os.environ.get('DB_NAME', ''),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    """Create MySQL connection."""
    return pymysql.connect(**DB_CONFIG)

def export_gaps_for_astro():
    """Export gaps in the format Astro expects."""
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
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
            gaps = cursor.fetchall()
            
            # Get stats
            cursor.execute("SELECT COUNT(*) as count FROM signals")
            signals_total = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM gaps WHERE status = 'active'")
            gaps_total = cursor.fetchone()['count']
            
            # Get source distribution
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM signals
                GROUP BY source
                ORDER BY count DESC
                LIMIT 20
            """)
            source_dist = cursor.fetchall()
            
            # Get sentiment breakdown
            cursor.execute("""
                SELECT sentiment, COUNT(*) as count
                FROM signals
                GROUP BY sentiment
            """)
            sentiment_breakdown = cursor.fetchall()
            
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
            buyer_intent_dist = cursor.fetchall()
            
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
            print(f"   Gaps: {gaps_total}")
            print(f"   Signals: {signals_total}")
            
    finally:
        conn.close()

if __name__ == '__main__':
    export_gaps_for_astro()
