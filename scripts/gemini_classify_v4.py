#!/usr/bin/env python3
import sqlite3, requests, json, time, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

def process_batch(conn, batch_size=25):
    c = conn.cursor()
    c.execute('PRAGMA busy_timeout = 5000')
    
    pending = c.execute("""
        SELECT id, content FROM signals 
        WHERE (quality_tier != 'low' OR quality_tier IS NULL)
        AND (metadata = '{}' OR json_extract(metadata, '$.gemini_score') IS NULL)
        LIMIT ?
    """, (batch_size,)).fetchall()
    
    if not pending:
        return False
    
    ids = [row[0] for row in pending]
    texts = [row[1][:800] for row in pending]
    
    numbered = '\n'.join([f'{i+1}. "{t}"' for i, t in enumerate(texts)])
    prompt = f'''Rate each comment 0.0 or 1.0 for whether it expresses a real customer pain/complaint.
1.0 = real pain, complaint, negative experience
0.0 = neutral, positive, irrelevant

{numbered}

Return ONLY a JSON array of numbers like [0.0, 1.0, 0.0].'''
    
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
            arr_match = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
            if arr_match:
                scores = [float(x.strip()) for x in arr_match.group(1).split(',') if x.strip()]
                pain_count = 0
                
                for i, score in enumerate(scores):
                    if i < len(ids):
                        sid = ids[i]
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
                
                conn.commit()
                return pain_count
        else:
            print(f'API {r.status_code}: {r.text[:50]}')
    except Exception as e:
        print(f'Error: {e}')
    
    return 0

def main():
    conn = sqlite3.connect(DB)
    total_processed = 0
    total_pain = 0
    
    while True:
        pain = process_batch(conn, batch_size=25)
        if pain is False:
            print(f'Complete! Processed {total_processed} signals')
            break
        
        total_processed += 25
        total_pain += pain
        
        # Check remaining
        remaining = conn.execute("""
            SELECT COUNT(*) FROM signals 
            WHERE (quality_tier != 'low' OR quality_tier IS NULL)
            AND (metadata = '{}' OR json_extract(metadata, '$.gemini_score') IS NULL)
        """).fetchone()[0]
        
        print(f'Processed: {total_processed} | Pain: {total_pain} | Remaining: {remaining}')
        
        if remaining == 0:
            print(f'Complete! All signals classified.')
            break
    
    conn.close()

if __name__ == '__main__':
    main()
