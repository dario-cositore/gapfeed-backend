#!/usr/bin/env python3
"""
GEMINI 3.1 FLASH LITE - Robust classification
"""
import sqlite3, requests, json, time, re
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

def get_pending_signals(limit=5000):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    signals = c.execute("""
        SELECT id, content FROM signals 
        WHERE (quality_tier != 'low' OR quality_tier IS NULL)
        AND (metadata IS NULL OR json_extract(metadata, '$.gemini_score') IS NULL)
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return signals

def update_signal(sid, score, conn):
    c = conn.cursor()
    if score >= 0.9:
        c.execute('''UPDATE signals SET 
            quality_tier = 'high', 
            confidence = 0.95,
            metadata = json_set('{}', '$.gemini_score', ?),
            pain_category = 'validated'
            WHERE id = ?''', (score, sid))
        return 'pain'
    else:
        c.execute('''UPDATE signals SET 
            quality_tier = 'low',
            metadata = json_set('{}', '$.gemini_score', ?)
            WHERE id = ?''', (score, sid))
        return 'not'
    return None

def main():
    conn = sqlite3.connect(DB)
    
    total_processed = 0
    total_pain = 0
    total_not = 0
    
    while True:
        pending = get_pending_signals(limit=100)
        if not pending:
            print(f'No more signals to classify!')
            break
        
        batch_ids = [row[0] for row in pending]
        batch_texts = [row[1][:800] for row in pending]
        
        numbered = '\n'.join([f'{i+1}. "{text}"' for i, text in enumerate(batch_texts)])
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
                timeout=30
            )
            
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                arr_match = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
                if arr_match:
                    scores = [float(x.strip()) for x in arr_match.group(1).split(',') if x.strip()]
                    
                    batch_pain = 0
                    batch_not = 0
                    
                    for i, score in enumerate(scores):
                        if i < len(batch_ids):
                            result = update_signal(batch_ids[i], score, conn)
                            if result == 'pain':
                                batch_pain += 1
                                total_pain += 1
                            else:
                                batch_not += 1
                                total_not += 1
                    
                    total_processed += len(batch_ids)
                    conn.commit()
                    
                    print(f'Processed: {total_processed} | Pain: {total_pain} | Not: {total_not} | Rate: {total_pain/max(1,total_processed)*100:.1f}%')
                else:
                    print(f'Parse error: {content[:100]}')
            else:
                print(f'API error {r.status_code}: {r.text[:100]}')
                time.sleep(2)
        except Exception as e:
            print(f'Exception: {e}')
            time.sleep(2)
            continue
        
        time.sleep(0.5)
    
    conn.close()
    print(f'\n=== COMPLETE ===')
    print(f'Total processed: {total_processed}')
    print(f'Pain: {total_pain} ({total_pain/max(1,total_processed)*100:.1f}%)')
    print(f'Not: {total_not}')

if __name__ == '__main__':
    main()
