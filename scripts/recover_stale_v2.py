#!/usr/bin/env python3
"""
Stale Recovery Pipeline - Gemini 3.1 Processing
Processes 35K stale signals, promotes verified pain to primary DB
"""
import sqlite3, re, requests, time
from datetime import datetime, timezone

STALE_DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
LIVE_DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

live = sqlite3.connect(LIVE_DB)
live_c = live.cursor()

# Get existing URLs to avoid dupes
existing = set(r[0] for r in live.execute('SELECT source_url FROM signals WHERE source_url != ""'))
print(f'Live DB has {len(existing):,} unique URLs')

# Get stale signals with content
stale = sqlite3.connect(STALE_DB)
pending = stale.execute('SELECT * FROM signals WHERE length(content) >= 100').fetchall()
filtered = [r for r in pending if r[2] not in existing]  # r[2] = source_url
print(f'Processing {len(filtered):,} new signals from stale DB...')
print()

# Process in batches
BATCH = 25
processed = 0
promoted = 0
dropped = 0
dupes = 0

for start in range(0, len(filtered), BATCH):
    batch = filtered[start:start+BATCH]
    
    # Build numbered list for the prompt
    lines = []
    for i, row in enumerate(batch):
        content = row[7][:200].replace('"', "'")
        lines.append(f'{i+1}. "{content}..."')
    numbered = '\n'.join(lines)
    
    prompt = f'''Rate each comment 0.0 or 1.0 for whether it expresses a real customer pain/complaint about a product or service.
1.0 = real pain, complaint, or negative experience
0.0 = neutral, positive, or irrelevant

{numbered}

Return ONLY a JSON array of numbers like [0.0, 1.0, 0.0]. No other text.'''

    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'google/gemini-2.5-flash-lite',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.0,
                'max_tokens': 200,
                'response_format': {'type': 'json_object'}
            },
            timeout=25
        )

        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            arr = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
            if arr:
                scores = [float(x.strip()) for x in arr.group(1).split(',') if x.strip()]
                for i, row in enumerate(batch):
                    if scores[i] >= 0.9:
                        live_c.execute('INSERT INTO signals VALUES ({})'.format(','.join(['?'] * 31)), row)
                        promoted += 1
                    else:
                        dropped += 1
                live.commit()
        else:
            print(f'API error {r.status_code}')
            time.sleep(2)

    except Exception as e:
        print(f'Error: {e}')
        time.sleep(2)
        continue

    processed += len(batch)
    print(f'  {processed:,}/{len(filtered):,} | Pain: {promoted:,} | Not: {dropped:,}')

    time.sleep(0.5)

print(f'\nDone! Promoted {promoted:,} signals to live DB')
print(f'Live DB now has {live.execute("SELECT COUNT(*) FROM signals").fetchone()[0]:,} total signals')
