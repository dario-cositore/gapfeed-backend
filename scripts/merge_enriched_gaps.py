#!/usr/bin/env python3
"""
Merge enriched gaps with database gaps for Astro website.
- Enriched gaps (91) override database versions
- Remaining database gaps (293) are included as-is
- No duplicates
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
ENRICHED_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/data/enriched_gaps_final.json'
OUTPUT_PATH = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'

def merge_gaps():
    # Load enriched gaps
    with open(ENRICHED_PATH, 'r') as f:
        enriched_gaps = json.load(f)
    
    enriched_ids = {g['id'] for g in enriched_gaps}
    print(f"Enriched gaps loaded: {len(enriched_gaps)}")
    
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
    print(f"Database gaps loaded: {len(db_gaps)}")
    
    # Build merged list
    merged_gaps = []
    used_ids = set()
    
    # Add enriched gaps first (they override)
    for gap in enriched_gaps:
        merged_gaps.append(gap)
        used_ids.add(gap['id'])
    
    # Add non-enriched database gaps
    for gap in db_gaps:
        if gap['id'] not in used_ids:
            merged_gaps.append(gap)
            used_ids.add(gap['id'])
    
    print(f"\\nMerged gaps total: {len(merged_gaps)}")
    print(f"  - From enriched: {len(enriched_gaps)}")
    print(f"  - From database (non-enriched): {len(merged_gaps) - len(enriched_gaps)}")
    
    # Get stats
    cursor.execute("SELECT COUNT(*) FROM signals")
    signals_total = cursor.fetchone()[0]
    
    # Sort by heat_score
    merged_gaps.sort(key=lambda x: x.get('heat_score', 0), reverse=True)
    
    # Prepare final data
    data = {
        'gaps': merged_gaps,
        'stats': {'signals': signals_total, 'gaps': len(merged_gaps)},
        'total_signals_all': signals_total,
        'total_gaps': len(merged_gaps),
        'exported_at': datetime.now().isoformat(),
        'enriched_count': len(enriched_gaps),
        'source': 'merged_enriched_database'
    }
    
    # Save
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\\n✅ Saved merged gaps to: {OUTPUT_PATH}")
    print(f"   Total gaps exported: {len(merged_gaps)}")
    
    # Verify no duplicates
    ids = [g['id'] for g in merged_gaps]
    if len(ids) == len(set(ids)):
        print(f"   ✅ No duplicates found")
    else:
        print(f"   ⚠️  WARNING: Duplicates detected!")
        duplicates = [id for id in ids if ids.count(id) > 1]
        print(f"   Duplicate IDs: {set(duplicates)}")
    
    conn.close()

if __name__ == '__main__':
    merge_gaps()
