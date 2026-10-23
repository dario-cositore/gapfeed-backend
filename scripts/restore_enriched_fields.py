#!/usr/bin/env python3
import json, sqlite3, datetime

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
ENRICHED = '/home/dario/.openclaw/workspace/3. gapfeed/data/enriched_gaps_final.json'
OUTPUT = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'

# Load enriched gaps
with open(ENRICHED, 'r') as f:
    enriched_gaps = json.load(f)

# Get original slugs from database
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute('SELECT id, slug FROM gaps')
original_slugs = {row['id']: row['slug'] for row in cursor.fetchall()}
conn.close()

# Fix slugs only (keep original field names)
for gap in enriched_gaps:
    gap_id = gap['id']
    if gap_id in original_slugs:
        gap['slug'] = original_slugs[gap_id]

    # Remove why_now if it exists (keep the_opportunity)
    if 'why_now' in gap:
        del gap['why_now']

# Get signal count
conn = sqlite3.connect(DB)
signals = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
conn.close()

# Save
data = {
    'gaps': enriched_gaps,
    'stats': {'signals': signals, 'gaps': len(enriched_gaps)},
    'total_signals_all': signals,
    'total_gaps': len(enriched_gaps),
    'exported_at': datetime.datetime.now().isoformat(),
    'source': 'enriched_original_fields'
}

with open(OUTPUT, 'w') as f:
    json.dump(data, f, indent=2, default=str)

print(f'Enriched gaps: {len(enriched_gaps)}')
print(f'Slugs fixed: {len(enriched_gaps)}')
print(f'Restored original fields (the_opportunity kept, why_now removed)')
print(f'Output: {OUTPUT}')
