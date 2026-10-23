#!/usr/bin/env python3
"""
COHERE RERANK PASS — after keyword filter, before save
Uses: openrouter/cohere/rerank-4-fast (or cohere/rerank-4-fast)
Scores existing signals, upgrades quality based on real pain relevance
"""
import os, sqlite3, requests, json, time
from datetime import datetime, timezone

DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
API_KEY_FILE = '/home/dario/Elitza/secrets/openrouter.key'

# API key from env, or key file (never hardcoded)
API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
if not API_KEY:
    try:
        API_KEY = open(API_KEY_FILE).read().strip()
    except OSError:
        raise SystemExit('Set OPENROUTER_API_KEY env var or create ' + API_KEY_FILE)

RERANKER_URL = 'https://openrouter.ai/api/v1/rerank'
RERANKER_MODEL = 'cohere/rerank-4-fast'

QUERY = 'Is this a real customer pain/complaint about a product or service?'

THRESHOLD = 0.65

conn = sqlite3.connect(DB)
c = conn.cursor()

# Get all signals that passed keyword filter (quality != 'low')
pending = c.execute("""
    SELECT id, content FROM signals 
    WHERE quality_tier != 'low' 
    AND metadata = '{}'
    ORDER BY id ASC
""").fetchall()

print(f'Signals to rerank: {len(pending)}')
print(f'Threshold: {THRESHOLD}')
print()

processed = 0
upgraded = 0
downgraded = 0
scores = []

# Process in batches of 10 for efficiency
batch_size = 10
for i in range(0, len(pending), batch_size):
    batch = pending[i:i+batch_size]
    docs = [row[1][:1000] for row in batch]
    ids = [row[0] for row in batch]
    
    try:
        payload = {
            'model': RERANKER_MODEL,
            'query': QUERY,
            'documents': docs,
            'top_n': len(docs)
        }
        
        r = requests.post(
            RERANKER_URL,
            json=payload,
            headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
            timeout=30
        )
        
        if r.status_code == 200:
            results = r.json().get('results', [])
            for idx, result in enumerate(results):
                score = result.get('relevance_score', 0)
                sid = ids[idx]
                scores.append(score)
                
                if score >= THRESHOLD:
                    c.execute('''UPDATE signals SET 
                        quality_tier = 'high',
                        confidence = ?,
                        metadata = json_set(metadata, '$.rerank_score', ?)
                        WHERE id = ?''', (round(score, 3), round(score, 3), sid))
                    upgraded += 1
                else:
                    c.execute('''UPDATE signals SET 
                        quality_tier = 'low',
                        metadata = json_set(metadata, '$.rerank_score', ?)
                        WHERE id = ?''', (round(score, 3), sid))
                    downgraded += 1
                
                processed += 1
        else:
            print(f'  API error: {r.status_code} - {r.text[:100]}')
            # Skip batch, don't count as errors
            
    except Exception as e:
        print(f'  Error on batch {i}: {e}')
    
    # Commit every batch for safety
    conn.commit()
    
    if processed % 50 == 0:
        print(f'  Processed: {processed}/{len(pending)} | Upgraded: {upgraded} | Downgraded: {downgraded}')
    
    time.sleep(0.5)  # Rate limit

conn.commit()

print(f'\n=== RERANK COMPLETE ===')
print(f'Processed: {processed}')
print(f'Upgraded to high: {upgraded}')
print(f'Downgraded to low: {downgraded}')

if scores:
    print(f'Avg score: {sum(scores)/len(scores):.3f}')
    print(f'Max: {max(scores):.3f}, Min: {min(scores):.3f}')
    
    high_scores = [s for s in scores if s >= THRESHOLD]
    print(f'Signals >= {THRESHOLD}: {len(high_scores)} ({len(high_scores)/len(scores)*100:.1f}%)')

# Final state
total = c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
high = c.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = "high"').fetchone()[0]
low = c.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = "low"').fetchone()[0]
print(f'\nDB: {total} total | {high} high ({high/total*100:.0f}%) | {low} low')

conn.close()
print('✅ Done')
