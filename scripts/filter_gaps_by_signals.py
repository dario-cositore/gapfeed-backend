#!/usr/bin/env python3
"""
Filter gaps to only include those with ≥ 30 signal evidence for Astro website.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
ENRICHED_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/data/enriched_gaps_final.json'
OUTPUT_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'

def filter_gaps():
    # Load enriched gaps
    with open(ENRICHED_PATH, 'r') as f:
        enriched_gaps = json.load(f)
    
    # Load database gaps
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, slug, description, evidence_count, heat_score,
               category, source_types, signal_ids, sample_quotes,
               competitors, gap_validity, opportunity_score, status,
               created_at, updated_at
        FROM gaps
        WHERE status = 'active'
    """)
    
    db_gaps = [dict(row) for row in cursor.fetchall()]
    
    # Build merged list with enriched overrides
    enriched_ids = {g['id'] for g in enriched_gaps}
    merged_gaps = []
    
    # Add enriched gaps
    for gap in enriched_gaps:
        merged_gaps.append(gap)
    
    # Add non-enriched database gaps
    for gap in db_gaps:
        if gap['id'] not in enriched_ids:
            merged_gaps.append(gap)
    
    # Filter by signal count (≥ 30)
    filtered_gaps = [g for g in merged_gaps if g.get('evidence_count', 0) >= 30]
    
    # Sort by heat_score
    filtered_gaps.sort(key=lambda x: x.get('heat_score', 0), reverse=True)
    
    # Get stats
    cursor.execute("SELECT COUNT(*) FROM signals")
    signals_total = cursor.fetchone()[0]
    
    # Prepare final data
    data = {
        'gaps': filtered_gaps,
        'stats': {'signals': signals_total, 'gaps': len(filtered_gaps)},
        'total_signals_all': signals_total,
        'total_gaps': len(filtered_gaps),
        'exported_at': datetime.now().isoformat(),
        'filter': 'evidence_count >= 30',
        'original_count': len(merged_gaps),
        'filtered_count': len(filtered_gaps),
        'removed_count': len(merged_gaps) - len(filtered_gaps)
    }
    
    # Save
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"=== GAP FILTER REPORT ===")
    print(f"Original gaps: {len(merged_gaps)}")
    print(f"Filtered (≥30 signals): {len(filtered_gaps)}")
    print(f"Removed (<30 signals): {len(merged_gaps) - len(filtered_gaps)}")
    print(f"\\n✅ Saved filtered gaps to: {OUTPUT_PATH}")
    
    # Show sample of filtered gaps
    print(f"\\nSample filtered gaps:")
    for gap in filtered_gaps[:5]:
        print(f"  {gap['id']}: \"{gap.get('title', '')[:60]}...\" ({gap.get('evidence_count', 0)} signals)")
    
    conn.close()

if __name__ == '__main__':
    filter_gaps()
