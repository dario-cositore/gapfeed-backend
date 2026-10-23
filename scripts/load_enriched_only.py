#!/usr/bin/env python3
import json, sqlite3, datetime

ENRICHED = '/home/dario/.openclaw/workspace/3. gapfeed/data/enriched_gaps_final.json'
OUTPUT = '/home/dario/.openclaw/workspace/3. gapfeed/website/gapfeed.com/gapfeed-astro/public/data/data.json'
DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'

with open(ENRICHED, 'r') as f:
    gaps = json.load(f)

conn = sqlite3.connect(DB)
signals = conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
conn.close()

data = {
    'gaps': gaps,
    'stats': {'signals': signals, 'gaps': len(gaps)},
    'total_signals_all': signals,
    'total_gaps': len(gaps),
    'exported_at': datetime.datetime.now().isoformat(),
    'source': 'enriched_only'
}

with open(OUTPUT, 'w') as f:
    json.dump(data, f, indent=2, default=str)

print(f'Enriched only: {len(gaps)} gaps, {signals} signals')
