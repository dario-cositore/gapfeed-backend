#!/usr/bin/env python3
"""Extract products from Other/Other cluster — 500 signals, 10 per API call."""
import sqlite3, json, requests, re, time
from collections import defaultdict

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

conn = sqlite3.connect(LIVE, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")

signals = conn.execute('''
    SELECT s.id, s.title, s.content FROM signals s
    JOIN gaps g ON s.gap_id = g.id
    WHERE LOWER(g.title) = 'other -- other issues'
    AND length(s.content) >= 30 ORDER BY RANDOM() LIMIT 500
''').fetchall()

existing = {r[1]: r[0] for r in conn.execute('SELECT id, LOWER(title) FROM gaps')}
new_clusters = defaultdict(list)
api_calls = 0
tokens = 0
errors = 0

print(f"500 signals, 10 per call = ~50 API calls\n")

BATCH = 10
for start in range(0, len(signals), BATCH):
    batch = signals[start:start+BATCH]
    items = "\n".join([f'{i}. "{((r[1] or "") + " " + (r[2] or "")).strip()}"'[:280] for i, r in enumerate(batch)])
    
    prompt = f'''Extract product/service name and problem from each item.
Return ONLY JSON array: [{{"product":"Name","problem":"pricing|support|bug|missing|complexity|billing|other"}}, ...]

{items}

If no specific product use "other".'''

    try:
        r = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}'},
            json={'model': 'google/gemini-2.5-flash-lite',
                  'messages': [{'role': 'user', 'content': prompt}],
                  'temperature': 0.0, 'max_tokens': 200,
                  'response_format': {'type': 'json_object'}},
            timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            resp = data['choices'][0]['message']['content']
            tokens += data.get('usage', {}).get('total_tokens', 0)
            api_calls += 1
            
            items_data = json.loads(resp)
            if isinstance(items_data, list):
                for item in items_data:
                    if isinstance(item, dict):
                        product = (item.get('product') or 'other').strip().lower()
                        problem = (item.get('problem') or 'other').strip().lower()
                        if problem not in ['pricing','support','bug','missing','complexity','billing']:
                            problem = 'other'
                        new_clusters[f"{product}||{problem}"].append(batch[0][0])
        else:
            errors += 1
    except:
        errors += 1
    
    done = min(start + BATCH, len(signals))
    print(f"  {done}/{len(signals)}  clusters:{len(new_clusters)}  calls:{api_calls}  errors:{errors}")
    time.sleep(0.3)

print(f"\nDone extraction → {len(new_clusters)} clusters from {api_calls} calls")

# Create gaps and assign
new_gaps = 0
assigned = 0
for key, sids in sorted(new_clusters.items(), key=lambda x: len(x[1]), reverse=True):
    if len(sids) < 3:
        continue
    product, problem = key.split('||')
    pname = product.title().replace('Other', 'Other')
    pname_full = pname.title() + '.com' if pname not in ['other', 'Other'] and '.com' not in pname else pname
    ptitle = f"{pname_full} -- {problem.title() + ' Issues'}" if problem != 'other' else f"{pname_full} -- Other"
    
    try:
        conn.execute('INSERT INTO gaps (title, slug, evidence_count, heat_score, category, gap_validity, signal_ids, sample_quotes, source_types, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (ptitle, ptitle.lower().replace(' ','-').replace('_','-'), len(sids),
             min(0.95, 0.3+len(sids)*0.005), problem, 'pending',
             json.dumps(sids[:50]), '[]', '[]', time.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
        gid = conn.lastrowid
        for sid in sids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gid, sid))
            assigned += 1
        new_gaps += 1
    except:
        pass
    if new_gaps % 10 == 0:
        conn.commit()

conn.commit()
total_gaps = conn.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]
with_gap = conn.execute('SELECT COUNT(*) FROM signals WHERE gap_id IS NOT NULL').fetchone()[0]
cost = tokens * 0.000078

print(f"\n{'='*55}")
print(f"NEW GAPS:     {new_gaps}")
print(f"SIGS ASSIGNED: {assigned}")
print(f"TOTAL GAPS:   {total_gaps}")
print(f"IN GAPS:      {with_gap:,}")
print(f"COST:         ${cost:.4f} ({tokens:,} tokens)")
print(f"{'='*55}")

print("\nTop new gaps:")
for r in conn.execute('SELECT title, evidence_count, category FROM gaps WHERE created_at > datetime("now", "-30 minutes") ORDER BY evidence_count DESC LIMIT 15'):
    print(f"  {r[0]:<50} {r[1]:>5} ({r[2]})")

conn.close()
