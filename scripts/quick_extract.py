#!/usr/bin/env python3
"""Quick extraction of 500 Other/Other signals."""
import sqlite3, json, requests, re, time
from collections import defaultdict

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

conn = sqlite3.connect(LIVE, timeout=30)
other_signals = conn.execute('''
    SELECT s.id, s.title, s.content FROM signals s
    JOIN gaps g ON s.gap_id = g.id
    WHERE LOWER(g.title) = 'other -- other issues'
    AND length(s.content) >= 30 ORDER BY RANDOM() LIMIT 500
''').fetchall()

print(f"500 signals to extract")

existing = {r[1]: r[0] for r in conn.execute('SELECT id, LOWER(title) FROM gaps')}
new_clusters = defaultdict(list)
api_calls = 0
tokens = 0

BATCH = 5
for i, (sid, title, content) in enumerate(other_signals[:500]):
    if i % 5 == 0:
        print(f"{i+1}/{len(other_signals)}...", end=' ', flush=True)
    
    text = f"{(title or '')} {(content or '')}"[:200]
    prompt = f'Product: "{text}"\nReturn JSON: {{"product":"name","problem":"category"}}'
    
    try:
        r = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}'},
            json={'model': 'google/gemini-2.5-flash-lite',
                  'messages': [{'role': 'user', 'content': prompt}],
                  'temperature': 0.0, 'max_tokens': 30,
                  'response_format': {'type': 'json_object'}},
            timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            content_resp = data['choices'][0]['message']['content']
            try:
                info = json.loads(content_resp)
                product = (info.get('product', 'other') or 'other').lower()
                problem = (info.get('problem', 'other') or 'other').lower()
                if problem not in ['pricing','support','bug','missing','complexity','billing']:
                    problem = 'other'
                new_clusters[f"{product}||{problem}"].append(sid)
                tokens += data.get('usage', {}).get('total_tokens', 0)
            except:
                pass
            api_calls += 1
    except:
        pass
    
    time.sleep(0.2)

print(f"\nExtracted into {len(new_clusters)} clusters")

# Create gaps
new_gaps = 0
for key, sids in sorted(new_clusters.items(), key=lambda x: len(x[1]), reverse=True)[:50]:
    if len(sids) < 3: continue
    product, problem = key.split('||')
    ptitle = f"{product.title()} -- {problem.title() + ' Issues'}"
    
    try:
        conn.execute('INSERT INTO gaps (title, slug, evidence_count, heat_score, category, gap_validity, signal_ids, sample_quotes, source_types, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (ptitle, ptitle.lower().replace(' ','-'), len(sids), 0.5, problem, 'pending',
             json.dumps(sids[:50]), '[]', '[]', time.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
        gid = conn.lastrowid
        for sid in sids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gid, sid))
        new_gaps += 1
    except:
        pass
    if new_gaps % 10 == 0:
        conn.commit()

conn.commit()

total_gaps = conn.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]
print(f"\nDone! New gaps: {new_gaps}, Total: {total_gaps}")
print(f"Cost: ~${(tokens * 0.000078):.3f}")
