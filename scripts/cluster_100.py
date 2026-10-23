#!/usr/bin/env python3
"""Process unclustered signals in tiny batches to avoid timeouts."""
import sqlite3, json, requests, re, time
from collections import defaultdict

LIVE = '/home/dario/.openclaw/workspace/3. gapfeed/code/data/gapfeed_unified.db'
KEY = open('/home/dario/Elitza/secrets/openrouter.key').read().strip()

conn = sqlite3.connect(LIVE)

# Get unclustered signals (limit for this batch)
unclustered = conn.execute('''
    SELECT id, source, source_url, title, content 
    FROM signals 
    WHERE gap_id IS NULL
    LIMIT 100
''').fetchall()

print(f"Processing {len(unclustered):,} signals...")

# Get existing gaps
existing_gaps = {}
for r in conn.execute('SELECT id, title, category FROM gaps'):
    existing_gaps[r[1].lower()] = (r[0], r[2])

def extract_product_problem(text):
    """Extract product name and problem type."""
    prompt = f'''From text, extract:
1. Product/service name
2. Problem: pricing, support, bug, missing_feature, complexity, billing, or other

Text: "{text[:180]}"

Return JSON: {{"product": "Name", "problem": "category"}}'''

    try:
        r = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {KEY}'},
            json={'model': 'google/gemini-2.5-flash-lite', 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.0, 'max_tokens': 40, 'response_format': {'type': 'json_object'}},
            timeout=15
        )
        data = json.loads(r.json()['choices'][0]['message']['content'])
        product = data.get('product', 'Unknown').strip()
        problem = data.get('problem', 'other').strip()
        return product, problem if problem in ['pricing', 'support', 'bug', 'missing_feature', 'complexity', 'billing'] else 'other'
    except:
        return 'Unknown', 'other'

# Process signals
clusters = defaultdict(list)
for signal_id, source, url, title, content in unclustered:
    text = (title or '') + ' ' + (content or '')
    if len(text.strip()) < 20:
        continue
    
    product, problem = extract_product_problem(text)
    clusters[f"{product}__{problem}"].append(signal_id)
    time.sleep(0.2)

print(f"Found {len(clusters)} unique product+problem combos")

# Create/update gaps
created = 0
updated = 0
new_signals_clustered = 0

for key, signal_ids in clusters.items():
    product, problem = key.split('__')
    gap_title = f"{product} — {problem.replace('_', ' ').title() + ' Issues'}"
    gap_key = gap_title.lower()
    
    if gap_key in existing_gaps:
        gap_id, _ = existing_gaps[gap_key]
        updated += 1
        for sig_id in signal_ids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gap_id, sig_id))
    else:
        conn.execute('''
            INSERT INTO gaps (title, slug, evidence_count, heat_score, category, gap_validity, signal_ids, sample_quotes, source_types, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'active')
        ''', (
            gap_title, gap_title.lower().replace(' ', '-').replace('—', '-'),
            len(signal_ids), 0.5, problem, 'pending',
            json.dumps(signal_ids[:50]), '[]', '["reddit"]'
        ))
        gap_id = conn.lastrowid
        existing_gaps[gap_key] = (gap_id, problem)
        created += 1
        for sig_id in signal_ids:
            conn.execute('UPDATE signals SET gap_id = ? WHERE id = ?', (gap_id, sig_id))
    new_signals_clustered += len(signal_ids)

conn.commit()

total_gaps = conn.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]
remaining = conn.execute('SELECT COUNT(*) FROM signals WHERE gap_id IS NULL').fetchone()[0]

print(f"Done: {created} new gaps, {updated} updated")
print(f"Total gaps: {total_gaps}")
print(f"Remaining unclustered: {remaining}")
