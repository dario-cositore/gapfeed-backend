#!/usr/bin/env python3
"""Gemini extraction of 5000 Other/Other signals to find real products."""
import sqlite3, json, requests, re, time
from collections import defaultdict

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

print("Connecting to DB...")
conn = sqlite3.connect(LIVE, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")

other_signals = conn.execute('''
    SELECT s.id, s.source, s.source_url, s.title, s.content
    FROM signals s
    JOIN gaps g ON s.gap_id = g.id
    WHERE LOWER(g.title) = 'other -- other issues'
    AND s.content IS NOT NULL AND length(s.content) >= 30
    ORDER BY RANDOM()
    LIMIT 5000
''').fetchall()

existing = {}
for r in conn.execute('SELECT id, LOWER(title) FROM gaps'):
    existing[r[1]] = r[0]

print(f"Processing {len(other_signals):,} signals...")

t0 = time.time()
total_extracted = 0
new_clusters = defaultdict(list)
api_calls = 0
api_errors = 0
tokens_in = 0
tokens_out = 0

BATCH = 10
for start in range(0, len(other_signals), BATCH):
    batch = other_signals[start:start+BATCH]
    items = "\n".join([f'{i+1}. "{(r[3] or "").strip() + " " + (r[4] or "").strip()}"'[:300] for i, r in enumerate(batch)])
    
    prompt = f'''Extract product/service name and problem from each.
Return ONLY JSON array: [{{"product":"Name","problem":"pricing|support|bug|missing|complexity|billing|performance|other"}}, ...]

{items}

If no product mentioned use "other".'''

    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}'},
            json={
                'model': 'google/gemini-2.5-flash-lite',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.0, 'max_tokens': 200,
                'response_format': {'type': 'json_object'}
            },
            timeout=20
        )
        
        if r.status_code == 200:
            data = r.json()
            content = data['choices'][0]['message']['content']
            tokens_in += data.get('usage', {}).get('prompt_tokens', 0)
            tokens_out += data.get('usage', {}).get('completion_tokens', 0)
            api_calls += 1
            
            items_data = json.loads(content)
            if isinstance(items_data, list):
                for i, item in enumerate(items_data):
                    if i < len(batch) and isinstance(item, dict):
                        product = item.get('product', 'other').strip().lower() or 'other'
                        problem = item.get('problem', 'other').strip().lower() or 'other'
                        if problem not in ['pricing','support','bug','missing','complexity','billing','performance']:
                            problem = 'other'
                        new_clusters[f"{product}||{problem}"].append(batch[i][0])
                        total_extracted += 1
        else:
            api_errors += 1
    except Exception as e:
        api_errors += 1
    
    processed = min(start + BATCH, len(other_signals))
    if processed % 500 == 0:
        elapsed = time.time() - t0
        cost = (tokens_in * 0.078 + tokens_out * 0.3) / 10e6
        msg = (f"[{processed:,}/{len(other_signals):,}] Extracted: {total_extracted:,} | "
               f"Clusters: {len(new_clusters)} | Calls: {api_calls} | Errors: {api_errors} | "
               f"Cost: ${cost:.4f} | Time: {elapsed:.0f}s")
        print(msg)
        # Save checkpoint
        with open('/tmp/gemini_extraction_progress.json', 'w') as f:
            json.dump({
                'processed': processed,
                'extracted': total_extracted,
                'clusters': len(new_clusters),
                'cost': round(cost, 4),
                'time': round(elapsed, 0)
            }, f)
    
    time.sleep(0.3)

elapsed = time.time() - t0
cost = (tokens_in * 0.078 + tokens_out * 0.3) / 10e6
print(f"\nDone in {elapsed:.0f}s")
print(f"Extracted: {total_extracted:,} into {len(new_clusters)} clusters")
print(f"Cost: ${cost:.4f}")

# Create gaps and assign
new_gaps = 0
updated = 0
assigned = 0

for key, sids in sorted(new_clusters.items(), key=lambda x: len(x[1]), reverse=True):
    if len(sids) < 5:
        continue
    product, problem = key.split('||')
    pname = product.title() if product != 'other' else product
    ptitle = f"{pname} -- {problem.title() + ' Issues'}" if problem != 'other' else f"{pname} -- Other"
    pkey = ptitle.lower()
    
    if pkey in existing:
        gid = existing[pkey]
        updated += 1
    else:
        try:
            conn.execute(
                'INSERT INTO gaps (title, slug, evidence_count, heat_score, category, gap_validity, signal_ids, sample_quotes, source_types, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (ptitle, ptitle.lower().replace(' ','-').replace('_','-'), len(sids),
                 min(0.95, 0.3+len(sids)*0.005), problem, 'pending',
                 json.dumps(sids[:50]), '[]', '[]', time.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
            gid = conn.lastrowid
            existing[pkey] = gid
            new_gaps += 1
        except:
            continue
    
    for sid in sids:
        try:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gid, sid))
            assigned += 1
        except:
            pass
    if (new_gaps + updated) % 10 == 0:
        conn.commit()

conn.commit()
final_gaps = conn.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]
with_gap = conn.execute('SELECT COUNT(*) FROM signals WHERE gap_id IS NOT NULL').fetchone()[0]

print(f"\n{'='*60}")
print(f"NEW GAPS: {new_gaps}")
print(f"UPDATED: {updated}")
print(f"ASSIGNED: {assigned:,}")
print(f"TOTAL GAPS: {final_gaps}")
print(f"IN GAPS: {with_gap:,}")
print(f"COST: ${cost:.4f}")
print(f"{'='*60}")

if new_gaps > 0:
    print("\nTop new gaps:")
    for r in conn.execute('SELECT title, evidence_count, category FROM gaps WHERE created_at > datetime("now", "-1 hour") ORDER BY evidence_count DESC LIMIT 20'):
        print(f"  {r[0]:<55} {r[1]:>6} ({r[2]})")

conn.close()
