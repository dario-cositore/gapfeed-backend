#!/usr/bin/env python3
"""Process stale DB with better error handling."""
import sqlite3, requests, re, time, json

STALE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

st = sqlite3.connect(STALE)
lv = sqlite3.connect(LIVE)

# Get existing URLs
existing = set(r[0] for r in lv.execute('SELECT source_url FROM signals WHERE source_url != ""'))
print(f"Staging has {len(existing):,} URLs")

# Setup columns
st_cols = [c[1] for c in st.execute('PRAGMA table_info(signals)').fetchall()]
cols_csv = ','.join(st_cols[1:])  # Skip id

# Get new signals
pending = st.execute(f'''
    SELECT {cols_csv} FROM signals 
    WHERE length(content) >= 100 
    AND source_url IS NOT NULL 
    AND source_url != ''
    AND source_url NOT IN ({','.join(['?']*min(len(existing), 5000))})
    LIMIT 1000
''', list(existing)[:5000]).fetchall()

print(f"New signals to process: {len(pending):,}")

lv_cols = [c[1] for c in lv.execute('PRAGMA table_info(signals)').fetchall()]
col_names = ','.join(lv_cols[1:])
vals = ','.join(['?'] * len(lv_cols[1:]))

# Process with retry logic
promoted = 0
rejected = 0
api_errors = 0

for idx, row in enumerate(pending):
    text = row[6][:200].replace('"', '\\"')  # Content at index 6 after skipping id
    
    # Retry loop
    for attempt in range(3):
        try:
            r = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': 'google/gemini-2.5-flash-lite',
                    'messages': [{'role': 'user', 'content': f'Is this customer pain/complaint? "{text}" Return 1.0 for YES, 0.0 for NO:'}],
                    'temperature': 0.0, 'max_tokens': 10
                },
                timeout=20
            )
            
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                m = re.search(r'([01]\.?[0]?)', content)
                
                if m:
                    match = m.group(1)
                    if match in ['1', '1.0', '1.00']:
                        score = 1.0
                    elif match in ['0', '0.0', '0.00']:
                        score = 0.0
                    else:
                        score = 0.0
                else:
                    score = 0.0
                
                if score >= 0.5:
                    try:
                        lv.execute(f'INSERT INTO signals ({col_names}) VALUES ({vals})', row)
                        promoted += 1
                    except Exception as e:
                        if promoted < 5:
                            print(f"  Insert error: {e}")
                else:
                    rejected += 1
                
                break  # Success, exit retry loop
            else:
                print(f"  API error {r.status_code}, retrying...")
                time.sleep(5)
                
        except Exception as e:
            if attempt == 2:
                api_errors += 1
                rejected += 1  # Count as noise if we can't classify
                print(f"  Failed after 3 attempts: {type(e).__name__}")
            time.sleep(5)
    
    if (idx + 1) % 25 == 0:
        print(f"  [{idx+1}/{len(pending)}] Promoted: {promoted} | Rejected: {rejected} | Errors: {api_errors}")
    
    time.sleep(0.3)

lv.commit()

print(f'\n=== COMPLETE ===')
print(f'Processed: {len(pending)}')
print(f'Promoted:  {promoted}')
print(f'Rejected:  {rejected}')
print(f'Errors:    {api_errors}')
print(f'\nStaging now: {lv.execute("SELECT COUNT(*) FROM signals").fetchone()[0]:,} total')
print(f'Staging high: {lv.execute("SELECT COUNT(*) FROM signals WHERE quality_tier = \"high\"").fetchone()[0]:,}')

st.close()
lv.close()
