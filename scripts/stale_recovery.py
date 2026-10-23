#!/usr/bin/env python3
"""
STALE RECOVERY PIPELINE
Run Gemini 3.1 on every signal from the server DB that has 100+ chars content.
Promote verified pain → primary local DB.
"""
import sqlite3, re, requests, time
from datetime import datetime, timezone

STALE_DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
LIVE_DB = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

live_conn = sqlite3.connect(LIVE_DB)
live_c = live_conn.cursor()

# Get existing URLs to avoid dupes
existing = set()
for r in live_conn.execute('SELECT DISTINCT source_url FROM signals WHERE source_url != ""'):
    existing.add(r[0])
print(f'Live DB has {len(existing):,} unique URLs')

# Process signals from stale DB that have content
stale_conn = sqlite3.connect(STALE_DB)
pending = stale_conn.execute('''
    SELECT id, source, source_url, platform_id, subreddit, author, title, content,
           created_at, collected_at, vertical, product_category, pain_category,
           display_category, signal_type, location, urgency_score, specificity_score,
           buyer_intent, quality_tier, gap_id, category, sentiment, competitor_mentions,
           metadata, is_processed, synthesized, confidence, actionability, urgency,
           product_vertical
    FROM signals WHERE length(content) >= 100
    ORDER BY id ASC
''').fetchall()

print(f'Stale signals with content >=100: {len(pending):,}')
filtered = [r for r in pending if r[2] not in existing or r[2].strip() == '']
print(f'New signals (not in live DB): {len(filtered):,}')
print()

# Process in batches of 25
BATCH = 25
total_processed = 0
total_promoted = 0
total_dropped = 0
total_dupes = 0

for start in range(0, len(filtered), BATCH):
    batch = filtered[start:start+BATCH]
    
    docs = [r[7][:800] for r in batch]  # content
    numbered = '\n'.join([f'{i+1}. "{d}"' for i, d in enumerate(docs)])
    prompt = f'''Rate each comment 0.0 or 1.0 for whether it expresses a real customer pain/complaint.
1.0 = real pain, complaint, negative experience
0.0 = neutral, positive, irrelevant

{numbered}

Return ONLY a JSON array of numbers.'''
    
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
        
        if r.status_code != 200:
            time.sleep(2)
            continue
            
        content = r.json()['choices'][0]['message']['content']
        arr = re.search(r'\[([01.,\s]+)\]', content, re.DOTALL)
        if not arr:
            time.sleep(0.3)
            continue
        
        scores = [float(x.strip()) for x in arr.group(1).split(',') if x.strip()]
        
        for i, row in enumerate(batch):
            if i >= len(scores):
                total_dupes += 1
                continue
                
            url = row[2] or ''
            if url in existing:
                total_dupes += 1
                continue
            
            if scores[i] >= 0.9:
                now = datetime.now(tz=timezone.utc).isoformat()
                try:
                    live_c.execute('''INSERT INTO signals (
                        source, source_url, platform_id, subreddit, author, title, content,
                        created_at, collected_at, vertical, product_category, pain_category,
                        display_category, signal_type, location, urgency_score, specificity_score,
                        buyer_intent, quality_tier, gap_id, category, sentiment, competitor_mentions,
                        metadata, is_processed, synthesized, confidence, actionability, urgency,
                        product_vertical
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', row)
                    total_promoted += 1
                    existing.add(url)
                except Exception as e:
                    total_dupes += 1
            else:
                total_dropped += 1
        
        total_processed += len(batch)
        live_conn.commit()
        
        if total_processed % 100 == 0:
            print(f'  Processed: {total_processed:,} | Promoted: {total_promoted:,} | Dropped: {total_dropped:,} | Dupes: {total_dupes:,}')
    
    except Exception as e:
        time.sleep(2)
        continue
    
    time.sleep(0.5)

live_conn.commit()

# Final stats
total = live_conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
high = live_conn.execute('SELECT COUNT(*) FROM signals WHERE quality_tier = "high"').fetchone()[0]
print(f'\n=== RECOVERY COMPLETE ===')
print(f'Processed: {total_processed:,}')
print(f'Promoted:  {total_promoted:,}')
print(f'Dropped:   {total_dropped:,}')
print(f'Dupes:     {total_dupes:,}')
print(f'\nLive DB: {total:,} total | {high:,} Gemini-verified high quality')

live_conn.close()
stale_conn.close()
print('✅ Done')
