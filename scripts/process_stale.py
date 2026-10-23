#!/usr/bin/env python3
"""Process stale DB signals, classify with Gemini, promote pain to staging."""
import sqlite3, json, requests, re, time, sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

STALE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

print(f"[{time.strftime('%H:%M:%S')}] Starting stale processing...")

# Setup resilient HTTP session
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retry))

st = sqlite3.connect(STALE)
lv = sqlite3.connect(LIVE)

# Existing URLs in staging
existing_urls = set(r[0] for r in lv.execute('SELECT source_url FROM signals WHERE source_url != ""'))
print(f"Staging has {len(existing_urls):,} URLs")

# Get new signals from stale (skip id column)
st_cols = [c[1] for c in st.execute('PRAGMA table_info(signals)').fetchall()]
cols_csv = ','.join(st_cols[1:])

placeholders = ','.join(['?'] * min(len(existing_urls), 5000))
query = f'''
    SELECT {cols_csv} FROM signals 
    WHERE length(content) >= 100 
    AND source_url IS NOT NULL 
    AND source_url != ''
    AND source_url NOT IN ({placeholders})
'''
pending = st.execute(query, list(existing_urls)[:5000]).fetchall()
print(f"New signals to classify: {len(pending):,}")

# Staging insert setup (skip auto-increment id)
lv_cols = [c[1] for c in lv.execute('PRAGMA table_info(signals)').fetchall()]
col_names = ','.join(lv_cols[1:])
vals = ','.join(['?'] * len(lv_cols[1:]))

proc = 0
promoted = 0
rejected = 0
api_errors = 0
limit = min(len(pending), 500)  # Process 500 per run

print(f"Processing {limit} signals...")
start_time = time.time()

for idx in range(limit):
    row = pending[idx]
    text = row[7][:200].replace('"', '\\"')
    prompt = f'Is this customer pain/complaint? Return 1.0 or 0.0 only: "{text}"'
    
    try:
        r = session.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'google/gemini-2.5-flash-lite',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.0,
                'max_tokens': 5
            },
            timeout=15
        )
        
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            m = re.search(r'([01]\.?0*)', content)
            score = float(m.group(1)) if m else 0.0
            
            if score >= 0.5:
                try:
                    lv.execute(f'INSERT INTO signals ({col_names}) VALUES ({vals})', row)
                    promoted += 1
                except:
                    pass
            else:
                rejected += 1
        elif r.status_code == 429:
            print(f"  Rate limited, sleeping 10s...")
            time.sleep(10)
            api_errors += 1
            continue
        else:
            api_errors += 1
            rejected += 1  # Count as noise to move on
    
    except Exception as e:
        api_errors += 1
        if api_errors < 5:
            print(f"  Error: {e}")
    
    proc += 1
    
    if proc % 50 == 0:
        elapsed = time.time() - start_time
        rate = proc / elapsed
        eta = (limit - proc) / rate if rate > 0 else 0
        print(f"  [{proc}/{limit}] Pain: {promoted} | Noise: {rejected} | Errors: {api_errors} | Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
    
    time.sleep(0.2)

lv.commit()
elapsed = time.time() - start_time
print(f"\n{'='*50}")
print(f"[{time.strftime('%H:%M:%S')}] BATCH COMPLETE")
print(f"{'='*50}")
print(f"Processed:  {proc}")
print(f"Pain:       {promoted}")
print(f"Noise:      {rejected}")
print(f"API Errors: {api_errors}")
print(f"Time:       {elapsed:.0f}s ({proc/elapsed:.1f}/s)")
print(f"Staging now: {lv.execute('SELECT COUNT(*) FROM signals').fetchone()[0]:,} total")
print(f"Staging high: {lv.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = \"high\"').fetchone()[0]:,}")

st.close()
lv.close()
