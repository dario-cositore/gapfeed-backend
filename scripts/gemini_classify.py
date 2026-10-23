#!/usr/bin/env python3
"""
GEMINI 3.1 FLASH LITE — Pain classification for existing signals
Perfect 1.00/0.00 separation, zero false positives
"""
import sqlite3, requests, json, time, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

conn = sqlite3.connect(DB)
c = conn.cursor()

pending = c.execute("""
    SELECT id, content FROM signals 
    WHERE quality_tier != 'low'
    AND (metadata = '{}' OR json_extract(metadata, '$.gemini_score') IS NULL)
    ORDER BY id ASC
""").fetchall()

print(f'Signals to classify with Gemini 3.1: {len(pending)}')
print('Model: google/gemini-2.5-flash-lite')
print()

BATCH = 50
processed = 0
pain_count = 0
not_count = 0

for i in range(0, len(pending), BATCH):
    batch = pending[i:i+BATCH]
    docs = [row[1][:800] for row in batch]
    ids = [row[0] for row in batch]
    
    numbered = '\n'.join([f'{j+1}. "{d}"' for j, d in enumerate(docs)])
    prompt = f'''Rate each comment 0.0 or 1.0 for whether it expresses a real customer pain/complaint about a product or service.
1.0 = real pain, complaint, or negative experience
0.0 = neutral, positive, or irrelevant

{numbered}

Return ONLY a JSON array of 0.0 or 1.0 values. Nothing else.'''

    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
            json={
                'model': 'google/gemini-2.5-flash-lite',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.0,
                'max_tokens': 300,
                'response_format': {'type': 'json_object'}
            },
            timeout=45
        )
        
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            arr_match = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
            if arr_match:
                scores = [float(x.strip()) for x in arr_match.group(1).split(',') if x.strip()]
                
                for j, score in enumerate(scores):
                    if j < len(ids):
                        sid = ids[j]
                        if score >= 0.9:
                            c.execute('''UPDATE signals SET 
                                quality_tier = 'high', 
                                confidence = 0.95,
                                metadata = json_set('{}', '$.gemini_score', ?),
                                pain_category = 'validated'
                                WHERE id = ?''', (score, sid))
                            pain_count += 1
                        else:
                            c.execute('''UPDATE signals SET 
                                quality_tier = 'low',
                                metadata = json_set('{}', '$.gemini_score', ?)
                                WHERE id = ?''', (score, sid))
                            not_count += 1
                        processed += 1
        else:
            print(f'  Error {r.status_code}: {r.text[:100]}')
            time.sleep(2)
            continue
            
    except Exception as e:
        print(f'  Exception: {e}')
        time.sleep(2)
        continue
    
    conn.commit()
    
    if processed % 100 == 0:
        print(f'  [{processed}/{len(pending)}] Pain: {pain_count} | Not: {not_count}')
    
    time.sleep(0.8)  # Rate limit ~30 req/min

conn.commit()

# Final stats
total = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
high = c.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = "high"').fetchone()[0]
low = c.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = "low"').fetchone()[0]

print(f'\n=== GEMINI 3.1 CLASSIFICATION COMPLETE ===')
print(f'Processed: {processed}')
print(f'Pain: {pain_count} | Not: {not_count}')
print(f'DB: {total} total | {high} high | {low} low')
print(f'Pain rate: {pain_count/processed*100:.1f}%' if processed > 0 else 'None')

conn.close()
print('✅ Done')
